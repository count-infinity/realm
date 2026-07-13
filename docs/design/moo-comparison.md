# LambdaMOO vs REALM

A reference comparison against **LambdaMOO** (the wrog fork, ~34K LOC of C:
`parser.y`/`code_gen.c`/`execute.c` = the MOO language VM; `db_*.c` = the
object model; `tasks.c`/`timers.c` = suspend/fork/tick-limits; `functions.c`
= builtins; `waif.c` = lightweight objects), the MOO Programmer's Manual
(1.8.x), and a real MOO program (`genpet` — a generic pet). It maps what MOO
does onto what REALM does, and flags what's worth stealing.

Sits alongside the CoffeeMud / PennMUSH / Evennia lineages REALM already
draws on — MOO is the MU* that took "the whole game is softcode objects in
the DB" the furthest, so it's the sharpest mirror for REALM's
"Godot of MU*s" thesis.

## The one deep difference

**MOO is inheritance-of-objects; REALM is composition-of-data.** Everything
in MOO is an object with a number (`#495`) in a single-inheritance parent
chain; you build a pet by parenting off `$generic_thing`, overriding verbs
and clobbering properties. REALM has no typeclass tree — a "kind of thing"
is a `GameObject` plus **tags + behaviors + data-driven defs**
(`class_def`/`skill_def`/packs). MOO reaches new behavior by *subclassing*;
REALM by *attaching*. Nearly every row below flows from that.

## 1. Object model

| | LambdaMOO | REALM |
|---|---|---|
| Identity | `#N` integer (objects ≡ ints) | UUID string `id` |
| "Kind" | single-inheritance `parent()`/`chparent` chain | prototype `parent` + `tags` + behaviors + pack `class_def`s |
| Method reuse | override verb + `pass(@args)` to call parent | attach behavior / merge data defs; no `pass()` |
| Built-in props | `name owner location contents programmer wizard r w f` | `name description location contents parent owner tags locks` |
| Lifecycle | `create(parent)` / `recycle()` / `valid()` | create / `destroy_obj` / ephemeral clone via `import_objects` |
| Lightweight objs | **WAIFs** (`:`-prefixed props, ref-counted, no `#`, thousands cheap) + **ANON** anonymous objects | *none* — every entity is a full `GameObject` (the `ephemeral` tag makes some transient, but not lightweight) |
| Persistence | periodic full-DB flat-file checkpoint | incremental SQLite dirty-sweep + WAL |

## 2. The programming language

| | LambdaMOO | REALM softcode |
|---|---|---|
| Nature | bespoke Algol-ish language → bytecode → resource-limited VM | denylist subset of **real Python**, `exec` in a locked namespace (`safe_eval.py`) |
| Types | INT, FLOAT, STR, **OBJ**, **ERR**, LIST, MAP, WAIF, ANON | Python int/float/str/list/**dict**/bool + GameObject refs |
| Syntax | `if…endif`, `for x in (l)…endfor`, `obj:verb()`, `obj.prop`, `$sysprop`, `?|` ternary, `@` splice | Python: `if:`, `for x in l:`, function calls, refs by `#id`/name |
| Errors | **first-class ERR values** + `try/except/finally` + backtick `` `x!E_PROPNF=>0' `` + `raise()` | Python exceptions + `try/except`; **no first-class error *value* type**, fail-closed |
| Preemption | **ticks + seconds budget per task** → `E_QUOTA` | wall-clock/call-count limits in the sandbox; not user-visible tick math |
| Object glue | `add_property`, `add_verb`, `set_verb_code`, `verb_code` — code is a first-class, in-DB, editable property | attrs via `set_attr`; verbs/behaviors attached; code is an attr string but not the same reflective surface |

Capability parity is closer than it looks — both are Turing-complete with
control flow, error handling, and live in-game editing. The divergence is
**idiom** (MOO DSL vs Python) and **two things MOO exposes that REALM
doesn't**: a first-class `ERR` value and an explicit tick budget.

## 3. Verbs vs commands+methods — the biggest *language* gap

MOO's **verb** is one thing that is simultaneously a **method**
(`pet:sound()`) and a **command** (`follow bob with pet`), dispatched by a
parser against a rich **verb-args spec**: `dobj/prep/iobj ∈ {none, any,
this}` across ~20 named prepositions, with `foo*bar` wildcard names,
auto-binding `dobjstr/iobjstr/prepstr/argstr`. Defining
`@verb pet:"follow" any with this` *is* the grammar.

REALM splits these: hardcoded Python `Command`s + softcode **`$`-commands**
on objects + verb cores, and command→object matching is pattern/prefix
based, **without** MOO's declarative dobj/prep/iobj slot system. This is
where a MOO person would most feel the loss of "parity" — REALM has no
`set_verb_args`-style command grammar living on the object. (See also the
PennMUSH `$`-command survey — Penn has the same idea REALM partially has.)

## 4. Permissions

Conceptually close, different mechanism:

| MOO | REALM |
|---|---|
| `wizard` bit / `programmer` bit | roles PLAYER/BUILDER/ADMIN/GOD |
| verb runs **with its owner's perms**; `set_task_perms`, `caller_perms()` | `controls()` predicate + **owner-delegation** (an owned object wields its owner's authority — the same idea as `set_task_perms`) |
| per-prop/verb `r w x c` flags | `attr_flags` (secret/visual/safe) + PROTECTED_ATTRS, but **reads default-open** (a deliberate inversion of MOO's read-gated model) |
| `+x` = callable from code | `reach`/`control`/`enter` locks + executor-authority on mutation |
| native code = C only (recompile) | **two-tier trust**: sandboxed softcode *plus* `@softcode_function` native bindings deployable without a recompile |

`caller_perms()`/`set_task_perms` ≈ REALM's Penn owner-delegation almost
exactly.

## 5. Tasks & concurrency

| MOO | REALM |
|---|---|
| cooperative tasks, tick/second budget | asyncio + one global tick heartbeat |
| `suspend(secs)`, `fork(id)…endfork`, `resume`, `kill_task`, `queued_tasks` | `wait(secs, cmd)` one-shots, `on_tick`/`script_ticker` behaviors |
| `read([obj],[timeout])` interactive input inside a task | `prompt(target, text, callback)` (≈ `read`) |

REALM has the *scheduling* (wait, ticks, prompt) but **not user-visible task
handles** — no `fork`/`task_id`/`kill_task`/`queued_tasks`. A builder can't
spawn and later cancel a named background task from softcode the way MOO's
`fork`/`kill_task` allows.

## 6. The genpet pattern, in REALM

The example ports cleanly — arguably more cleanly:

| genpet (MOO) | REALM equivalent |
|---|---|
| `tell_may_be_broken` verb fired by every room `tell` | **`^listen` / `ON_<EVENT>` trigger** — react to overheard speech/events (structured, vs overloading `tell`) |
| `msg_lapse > noisy` throttle counter | an ordinary `db.attr` counter — identical idiom |
| `fork(0) … moveto … endfork` to follow async | `wait(0, 'follow …')` or a `move` actuator in the trigger |
| `this:random_msg()`, `$string_utils:match_player` | native `ansi()`/string fns + `search_world`; game logic stays softcode |
| state in `this.masters`, `this.lazy`, … | state in `db.*` attrs — identical |
| autonomy via message-hook, *not* a per-tick daemon | same choice available: `^listen` (event-driven) **or** `script_ticker` (daemon) |

The one thing MOO's stdlib does that REALM's doesn't:
`$string_utils`/`$list_utils` are **in-DB softcode objects any wizard can
read and patch**; REALM's equivalents are native Python bindings (faster,
but not in-game-editable). That's the two-tier-trust trade-off REALM made on
purpose.

## Verdict & steal-list

**REALM already has parity on:** live in-game editing, Turing-complete
scripting with control flow + error handling, owner-delegated permissions,
per-viewer messaging, event-driven autonomy, deferred/scheduled behavior, a
corified-ish stdlib.

**Genuinely worth stealing from MOO** (ranked):

1. **A declarative verb-args command grammar** on objects
   (dobj/prep/iobj/wildcards) — the clearest "MOO coding parity" gap, and it
   would make `$`-commands far more expressive. (PennMUSH is the other model
   to weigh here.)
2. **First-class `ERR` values + a backtick-style catch** — cheap, and makes
   softcode error handling idiomatic rather than fail-closed.
3. **WAIFs** — lightweight, ref-counted, non-DB value-objects for the
   thousands-of-arrows / mail-message case, so those don't pollute the
   object space.
4. **User-visible task handles** — `fork`/`task_id`/`kill_task` so builders
   can manage long-running background softcode.

**Where REALM is already ahead:** composition over deep inheritance,
incremental SQLite persistence, the two-tier native-binding escape hatch,
structured two-pass action propagation with multiroom reach, and ephemeral
instanced rooms.

*Status: reference comparison, no decisions taken. Decisions to be revisited
after the PennMUSH softcode/attribute survey.*
