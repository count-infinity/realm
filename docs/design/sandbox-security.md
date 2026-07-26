# Softcode Sandbox Security

## Threat model

Untrusted players can attach softcode to their own objects (the MUSH
"build bit for everyone" model). So softcode is adversarial input: assume a
motivated attacker with unlimited retries, whose object runs its hooks and
`$`-commands while *other players* are the enactor. Two distinct properties
must hold.

1. **Host safety.** Softcode cannot reach the interpreter, the OS, the
   filesystem, or the process's Python objects. No escape to `eval`,
   `__import__`, module globals, or arbitrary attributes.
2. **In-game authority.** An object may only read and mutate what its owner
   *controls* (`controls(executor, target)`). It cannot write another
   player's attributes, move another player, read `secret` attributes it
   does not own, or escalate its own privileges. A hostile object acting
   with a *victim* as `enactor` cannot act with the victim's authority.

Host safety is a property of the *language* boundary. Authority is a
property of the *domain* boundary. They fail in different ways and are
defended by different walls.

## The principle: unreachability, not prohibition

REALM's softcode is real Python run through `exec`, chosen so builders write
real `if`/`for`/comprehensions/f-strings. That choice makes a blocklist
approach lose eventually: the sandbox once rejected `x.__class__` at the AST
but still let `'{0.__class__}'.format(x)` through, because `str.format` does
attribute access at runtime from inside a string the validator cannot see.
Every stdlib gadget that performs attribute access from data is another
bypass waiting to be found.

The durable answer is **capability security**: arrange things so that even if
a check is missed, there is *nothing dangerous on the other side*. Don't make
`__class__` "hard to reach"; make sure that reaching it lands on nothing
useful (no real builtins in the frame, no raw domain objects in the
namespace). Prohibition (the AST filter) is the cheap first line;
unreachability is the wall.

## Wall 1 — Host safety (LANDED)

The one validator lives in `realm/core/safe_eval.py` and is shared by the
script sandbox, `@lock` expressions, and combat strategy conditions. It runs
at parse time, before execution, so it covers every path expressible in
Python *syntax*:

- **Forbidden nodes:** `import`, `from-import`, `global`, `nonlocal`.
- **Forbidden names:** `eval`, `exec`, `compile`, `open`, `getattr`,
  `setattr`, `type`, `object`, `super`, `globals`, `vars`, `__import__`, … —
  and any name starting with `_`.
- **Forbidden attributes:** any attribute starting with `_`, plus the
  `str.format`/`format_map` family (the data-channel escape above; blocking
  the attribute catches every receiver, `x.format(...)` and
  `str.format(x,...)` alike). f-strings compile to AST `FormattedValue`
  nodes and stay fully validated, so real softcode is unaffected — the
  tutorials and world use f-strings exclusively.
- **Exception shapes:** bare `except:` and `except BaseException` are
  rejected, so a script cannot swallow the resource-limit kill.

The exec frame carries an **empty `__builtins__`** (`realm/scripting/
sandbox.py`). Without an explicit key, CPython auto-injects the real
`builtins` module, leaving every real builtin one missed-underscore-path
away. An empty dict makes the safe surface an **allowlist**
(`SAFE_BUILTINS`: the common functions, types, and a curated set of
`Exception` subclasses) rather than "all real builtins minus a blocklist."
`BaseException` and its non-`Exception` children are deliberately absent so
the kill stays uncatchable.

Note this alone is not sufficient, which is *why* the `str.format` block
matters: reachable function objects (`V`, `set_attr`, …) still carry their
own module `__globals__`, whose `__builtins__` is real. Emptying the frame's
builtins removes the direct reach; the format block removes the data-channel
that walked to the function objects' globals. Both are required.

Resource limits (also `sandbox.py`): per-script wall-clock, call-count, and
recursion-depth budgets, enforced by a `sys.settrace` watchdog the script
cannot clear (`sys` is not in the namespace). See
[time and beats](time-and-beats.md).

### Known residual host risk

The AST filter is a blocklist of gadgets, so an unknown future data-channel
gadget (some stdlib `__format__`/`__getitem__` reachable without import) is
possible in principle. Memory is the sharper gap: `'x' * 10**10` allocates in
a single bytecode op before the next line-trace fires, and CPython has no
per-thread memory cap. Both point at Wall 3.

## Wall 2 — Authority façade (read handle LANDED; write-sugar + full audit remaining)

**Shipped (`realm/scripting/handle.py`, `tests/test_sandbox_handle.py`):**
the read handle, interned per run, wired at the sandbox boundary
(`ScriptSandbox`: namespace values wrapped, function args unwrapped / object
returns wrapped, `result` unwrapped on the way out). All six battery
exploits — cross-owner attr-assign, cross-owner `.db.set`, teleport,
ownership/tag escalation, protected-attr read — are now blocked, and the
full suite stayed green (2101), i.e. **zero migration**: `.db.get`/`.db.all`
reads and every field read survive via the read-only view, so no existing
softcode changed. Remaining: the guarded db-attr *write*-sugar (deferred)
and completing the function-layer audit below for the lower-traffic mutators.
The rest of this section is the design as built.

**Also covered: the expression paths.** Locks, `@detail`/`desc_extras`
conditions, combat strategy, and check rules use `safe_eval.eval_expression`
/`eval_bool` directly, *not* the script sandbox, so they bound raw objects —
a confirmed exploit: a hostile detail row `["viewer.db.set('marked',1) or
False", ...]` mutated anyone who looked. `handle.guard_namespace(namespace,
principal)` now wraps the object-valued entries (`viewer`; lock `caller`/
`target`/`owner`) in the same read-only handles, with a small
safe-predicate-method whitelist (`has_tag`, `has_entitlement`) so real lock
expressions (`caller.has_tag('key')`, `caller.id == owner.id`,
`caller.db.get(...)`) keep working while `caller.db.set(...)` dies. Applied
in `describe.py` and `locks.py`. Strategy binds a curated `CombatantView`
(no `.db`) and checks bind only lambdas, so both were already safe. Tests:
`TestExpressionPaths`.



Today the namespace hands softcode **live `GameObject` instances** (`me`,
`here`, `enactor`, `get()`), whose ordinary non-underscore surface bypasses
`controls()` entirely:

```python
get('vault').db.x = 9            # write an object owned by someone else
get('vault').db.set('y', 9)      # ...via method too
get('Bob').location = get('trap')   # move another player past every lock
get('Bob').db.get('password')    # read a secret attr, ignoring the flag
```

`me.owner = me` and `me.tags.add('admin')` happen to fail today — but only
because `owner` is a property without a setter and `tags` returns an
immutable view. That is safety by happenstance, not by design.

The AST cannot fix this: `obj.location = x` is innocent-looking non-private
syntax. The fix is to **stop exposing raw objects**.

### Decision (2026-07-25): a capability handle that delegates to the guarded reader

`me`/`here`/`enactor`/`get()` return an opaque **handle** — a small Python
class, interned per run — whose *attribute access delegates to the guarded
functions*. `x.name`/`x.id`/`x.hp` route through `__getattr__` to the same
reader `get_attr` uses, so **every read flows through the one `controls()`/
`secret` chokepoint by construction**, with nothing to hand-whitelist. This
is the Python equivalent of Lua/Roblox's locked-metatable `__index`.

Chosen over the bare-token variant (function-only, `name(x)` everywhere)
because it is both more intuitive *and* smaller migration: `enactor.id` and
`viewer.description` keep working unchanged. Both spellings coexist and route
to the same policy — `x.name` and `name(x)` are two spellings, not two
policies — so tutorials need no rewrite of existing attribute reads.

Invariants that make it airtight (the read rule is the load-bearing one):

- **Object-valued reads return handles, never raw objects** — no
  `x.location.owner...` walk back to the real graph. This lives in the
  *central* reader, so there is one place to get right, not a per-field list.
- **`.db` is neutralized**: `x.db` resolves to the attribute named `db`
  (`None`), so `x.db.set(...)` and `get('v').db.x = 9` both die for free.
- **Internals in `_`-slots** (`_id`, `_ctx`), unreachable because Wall 1
  blocks `_`-attrs, `getattr`, and format. The handle adds **no host-safety
  surface** — host safety stays the AST's job; the handle is purely the
  authority layer.
- **Writes:** db attrs may route through `set_attr` (guarded); structural
  fields (`location`/`owner`/`tags`/`name`/`description`) are NOT
  attribute-writable — they need their verbs (`move_to`, `@name`,
  `add_tag`) so locks, events, and indexes fire. `description` has no
  softcode setter (the gap 008 documented) and raises. v1: reads-as-sugar,
  writes stay explicit; add guarded db-attr write-sugar once reads are
  proven.

Migration scope across all showcase + world softcode is therefore tiny:
the 338 `.id` and ~6 `.description` reads keep working; only the ~12 `.db`
reads (`x.db.get`, `x.db.all`) migrate to `get_attr(x, k)` and a new
`attrs(x)` enumerator.

### Load-bearing constraint: `target is me` must keep working

Every reactive hook guards with `if target is me:`. Handles are therefore
**interned per run** (one handle per object per execution), so `is` and `==`
both hold for the same object. This preserves the `is` house rule the
tutorials standardized on. Pin it with a test first.

### Necessary but not sufficient: the function-layer audit

The façade routes all mutation through the functions, so the functions must
be audited to check `controls()` on the *correct subject*:

- A hostile object runs with a victim as `enactor`; `move_to(enactor, trap)`
  must be refused (executor does not control the enactor).
- `get_attr`/`V` must gate `secret`-flagged attributes on `controls()` so a
  passer-by cannot read another player's secrets.
- `set_attr` already checks control, `PROTECTED_ATTRS`, and the `safe` flag
  (see [object identity](object-identity.md)); confirm every sibling
  mutator (`incr`, `decr`, `del_attr`, `create_obj(location=...)`,
  `transfer_credits`, pairing, tag writes) does the same.

## Wall 3 — Isolation belt (ROADMAP)

Walls 1-2 are suspenders. The belt, for the adversarial model, is real
isolation: run softcode in a **sub-interpreter (PEP 734) or a separate
process** with `setrlimit` (address space, CPU) and a marshalled API instead
of shared live objects. This is the only layer that:

- caps memory (the one thing in-process CPython cannot do), and
- survives an unknown future host gadget, because there is no shared object
  graph or real builtins to reach in the first place.

It is heavyweight (marshalling replaces object sharing, which reshapes the
function layer) and should be designed so Wall 2's façade API is the
marshalling boundary — i.e. build Wall 2 such that Wall 3 slots in without a
softcode-visible rewrite.

## Status

| Wall | Scope | State |
|---|---|---|
| 1 | Host: AST filter + empty `__builtins__` + `str.format` block + allowlist | **Landed** (`tests/test_scripting.py::TestScriptSandbox`) |
| 2 | Authority: read handle (interned, guarded reads, writes blocked) — sandbox, inline `[[...]]`, AND expression paths (locks/`@detail`) | **Landed** (`tests/test_sandbox_handle.py`, 21); write-sugar + full mutator audit remain, see BACKLOG |
| 3 | Isolation: sub-interpreter/process + `setrlimit` (memory) | Roadmap; see BACKLOG |

See also: [object identity](object-identity.md) (the authority model,
`controls`, `PROTECTED_ATTRS`, attrflags), [action phases](action-phases.md)
(how gated verbs enforce permission).
