# LDMud vs REALM

A reference comparison against **LDMud** (a modern LPMud driver: `src/` is
the C kernel — `interpret.c` is the ~25K-line LPC bytecode VM,
`simulate.c`/`object.c` the object lifecycle, `closure.c` code-as-data,
`heartbeat.c`/`call_out.c`/`backend.c` scheduling, `efuns.c`/`func_spec` the
~600 builtins, `simul_efun.c` the mudlib escape-hatch; `mudlib/` is the LPC
game layer — here reduced to `master_skeleton.c` and `applied_spec`, the
contract between driver and game). It maps what LPMud does onto what REALM
does, and flags what's worth stealing.

LPMud is the sharpest possible mirror for REALM's "engine, not game" thesis,
because **LPMud already drew exactly this line — and put it in a radically
different place.** LambdaMOO and PennMUSH are single-process worlds where
softcode lives in the DB; LPMud, like REALM, has a genuine *kernel* (the C
driver) and a genuine *game* (the mudlib). The question is not *whether* to
split engine from game — both did — but **how much language, and how much
trust, to hand the game layer.**

## The one deep difference

**LPMud makes the game a full compiled programming language running native;
REALM makes the game data plus a small sandboxed softcode surface.** In
LPMud the mudlib *is* the game, and it is written in **LPC** — a real
C/Java-flavored, statically-typed, object-oriented language. Every room,
every sword, every monster is a `.c` file that the driver **compiles to
bytecode at load time** (`interpret.c`) and runs at native-ish speed with no
sandbox. A builder wanting a new kind of thing writes a class, `inherit`s a
base class, and overrides methods. REALM refused precisely this: game-meaning
is **data + a denylist subset of Python run through `safe_eval`**
(`realm/scripting/sandbox.py`), and a "kind of thing" is a `GameObject` plus
tags + behaviors + data-driven packs — no compiled per-object language, no
inheritance tree. LPMud reaches new behavior by **subclassing in a full
language**; REALM by **attaching data to a fixed kernel**. Nearly every row
below flows from that, and from the safety bargain it forces.

## 1. Object & inheritance model

| | LDMud | REALM |
|---|---|---|
| Identity | `name#clonenum` (`"std/thing#45"`, `object.c:99`) | UUID string `id` |
| "Kind" | a **compiled `.c` program**; `blueprint` (the loaded file) vs `clone` (instance sharing the program, `object.c:89-99`) | prototype `parent` + `tags` + behaviors + pack `class_def`s |
| Instancing | `clone_object(file)` efun (`func_spec:527`) → new clone sharing the blueprint's bytecode | create / ephemeral clone; no compiled program to share |
| Reuse | **`inherit "base";`** — real OO single/multiple inheritance resolved at compile (`object.c:763`, `sys/inherit_list.h`) | attach behavior / merge data defs; **no inheritance** |
| Method call | `ob->verb(args)` = `call_other` dispatch (`func_spec:512`), late-bound by name | behavior dispatch + softcode `$`-commands; no `->` |
| Lightweight objs | **LWObjects** (`lwobject.c`) — struct-like value objects, no clone#, cheap by the thousand | *none* — every entity is a full `GameObject` |
| Code as data | **closures**: efun/lfun/simul-efun pointers + runtime-compiled **`lambda`** (`closure.c:1-40`) | softcode strings eval'd in the sandbox; no first-class closure value |
| Persistence | `save_object`/`restore_object` to flat files, per-object, opt-in | incremental SQLite dirty-sweep + WAL, automatic |

The load-time compile is the crux: an LPMud object literally *is a program*.
REALM has no compile step for game content — content is rows and short
scripts the kernel interprets.

## 2. The softcode / language model

| | LDMud (LPC) | REALM softcode |
|---|---|---|
| Nature | full statically-typed OO language → **bytecode → native VM** (`interpret.c`) | denylist subset of **real Python**, `exec` in a locked namespace (`safe_eval.py`) |
| Scope | the **entire game** — every object is LPC | a **thin surface**: `$`-commands, `^listen`, `ON_<EVENT>`, `[[…]]`, `on_tick`, `wait()`/`prompt()` |
| Power | Turing-complete, classes, inheritance, closures, pointers, structs, typed vars | Turing-complete expressions/statements, but **no classes, no imports, no attribute-walking** past the denylist |
| Execution | **native, unsandboxed** — trusted because *builders are trusted* (wizard = coder) | **sandboxed** — builders are *not* trusted; the language itself is the containment |
| Runaway control | **eval-cost budget** per thread (`i-eval_cost.h`, `MAX_EVAL_COST`) → thread aborts | wall-clock / call-count limits in the sandbox |
| Extending the builtins | write a **simul-efun** in LPC (`simul_efun.c`) — see §4 | write a **`@softcode_function`** native binding |

Capability is *wildly* asymmetric here in LPMud's favor: LPC is a complete
programming language, REALM softcode is deliberately a fenced expression
layer. That gap is not a REALM deficiency — it is invariant #5 (two-tier
trust) and the whole reason `safe_eval` exists. **LPMud's answer to "who may
write code" is "wizards, and wizards are trusted, and the code runs native";
REALM's answer is "anyone, and no one is trusted, so the code is caged."**

## 3. Security & authority — the MASTER OBJECT vs `controls()`

LPMud's security kernel is one privileged LPC object, the **master object**,
that the C driver *calls back into* for every sensitive decision. The driver
holds no policy; it asks the master. This is the deepest structural parallel
to — and contrast with — REALM's `controls()`.

| | LDMud master object | REALM |
|---|---|---|
| Locus of policy | a single mudlib object the driver applies into (`applied_spec %master`) | `controls(actor, obj)` predicate (`realm/permissions/locks.py:226`) + locks |
| File reads/writes | driver calls `valid_read`/`valid_write(path, euid, fun, caller)`; master returns the real path or `0` (`master_skeleton.c:1040-1054`) | lock checks + role gate; no per-path mudlib callback |
| Catch-all gate | `privilege_violation(op, who, arg…)` — one apply for snoop, shutdown, bind, etc. (`master_skeleton.c:856`) | `controls()` + role (PLAYER/BUILDER/ADMIN/GOD) + `attr_flags`/PROTECTED_ATTRS |
| Identity/capability | every object carries **uid** (theoretical) + **euid** (effective) (`master_skeleton.c:1004-1026`); efuns `getuid`/`geteuid` (`func_spec:667-668`); strict-euids blocks load/clone without a nonzero euid | executor authority + **owner-delegation** (an owned object wields its owner's authority) |
| Who grants identity | the master hands out (e)uids — `get_master_uid` (`master_skeleton.c:263`), `valid_exec` (`959`) | roles assigned to accounts; delegation via ownership |
| Shadowing / snoop / trace | `query_allow_shadow`, `valid_snoop`, `valid_trace` applies | lock predicates |
| Native code | **C efuns only** — recompile the driver | **two-tier**: sandboxed softcode *plus* `@softcode_function` native bindings, deployable without recompiling |

The master-object pattern is genuinely elegant and portable: **the kernel
enforces a decision it does not itself make, by calling a single well-known
policy object.** REALM's `controls()` is the same *idea* collapsed into a
predicate rather than a callback object — the euid split
(theoretical-vs-effective permission) is precisely REALM's owner-delegation,
and `valid_read`/`valid_write` returning a *rewritten path* (not just a
bool) is strictly more expressive than a boolean lock.

## 4. Extensibility escape-hatch — sefun vs `@softcode_function`

Both systems have a deliberate seam between "game code" and "engine
builtins," and both provide a way to add pseudo-builtins *without touching
the kernel.* This is the closest structural match in the whole comparison.

| | LDMud | REALM |
|---|---|---|
| Kernel builtins | **efuns** — C, in `efuns.c`/`func_spec`, ~600 of them; recompile to change | Python `Command`s + kernel primitives |
| Deploy-time pseudo-builtins | **simul-efuns** — extra "efuns" *written in LPC* in one object the master names via `get_simul_efun`; callable everywhere like a real efun (`simul_efun.c:1-24`) | **`@softcode_function`** native bindings — Python fns exposed into the sandbox namespace |
| Hot-swap | master can name **backup sefun objects** so a removed sefun keeps resolving for old programs (`simul_efun.c:10-23`) | redeploy bindings without a server rebuild |
| Trust tier | sefun is *still LPC*, still native, still wizard-written | binding is native Python, **operator/pack-author only** — the trust boundary is enforced |

The match is close but the trust model inverts: an LPMud **sefun is written
in the same untrusted-by-REALM's-standards language as everything else** (LPC,
by any wizard), whereas a REALM `@softcode_function` is the *privileged* tier
precisely because native Python is unsafe. LPMud has no equivalent of "a
lower tier that is safe by construction" — in LPMud *all* game code is the
privileged tier.

## 5. Scheduling

| | LDMud | REALM |
|---|---|---|
| Periodic per-object | **`heart_beat()`** apply, toggled by `set_heart_beat`/`configure_object OC_HEART_BEAT` (`efuns.c:4891-4897`); backend drives all beats each cycle (`heartbeat.c:14-22`); **skipped entirely when no player is online** (`heartbeat.c:21-22`) | `on_tick`/`script_ticker` behaviors on one global heartbeat |
| Deferred one-shot | **`call_out(fn, delay, …)`** (`func_spec:503`) — delayed call, command-giver preserved | `wait(secs, cmd)` one-shots |
| **Task handles** | **`call_out_info()` / `find_call_out()` / `remove_call_out()`** (`func_spec:504-506`) — enumerate, find, and **cancel** pending callouts | *none* — no user-visible handle to cancel a scheduled job |
| Fork-bomb guard | callouts of one user share **`MAX_EVAL_COST`** (`call_out.c:8-11`) | sandbox eval limits |
| World upkeep | **`reset()`** / `H_RESET` re-runs periodically to repopulate/reset objects (`backend.c:1343-1372`, `time_reset`) | no kernel `reset` primitive; repop is softcode/behavior |
| Idle GC | **`clean_up(int)`** / `H_CLEAN_UP` — driver calls unreferenced objects; return nonzero to be called again, else the object is auto-destructed (`backend.c:1444-1462`) | ephemeral-tag transience; no return-value-driven self-GC apply |

LPMud's scheduling is the most *directly* stealable area: `call_out` +
`find_call_out`/`remove_call_out` is exactly the user-visible task-handle
system REALM lacks (the same gap flagged against MOO's `fork`/`kill_task`),
and `reset()`/`clean_up()` are two clean primitives REALM has no direct
answer for.

## Capabilities REALM lacks (by design or by gap)

- **A full compiled language per object** — *by design.* LPC gives every
  builder classes, inheritance, closures, typed variables, pointers. REALM
  refused this (invariants #2, #5): the softcode surface is fenced and
  sandboxed on purpose. This is the single biggest capability difference and
  it is a deliberate non-feature.
- **Real inheritance (`inherit`)** — *by design.* REALM chose
  composition-of-data over inheritance-of-objects (same stance as the MOO
  comparison).
- **`->` / `call_other` late-bound method dispatch** — REALM has no
  object-to-object "call this method by name" from softcode.
- **First-class closures / `lambda`** (`closure.c`) — code as a passable
  value; REALM softcode has no closure value.
- **User-visible task handles** — `find_call_out`/`remove_call_out`; a *gap*,
  and a clean one to close.
- **`reset()` and `clean_up()` lifecycle applies** — kernel-driven repop and
  idle self-GC; REALM has neither as a primitive.
- **Path-rewriting security callbacks** — `valid_read`/`valid_write` return a
  *transformed path*, not a bool; strictly more expressive than a lock.
- **Lightweight value-objects (LWObjects)** — the same want flagged as WAIFs
  against MOO.

## The different philosophy: power vs safety

MOO and REALM argue about *inheritance vs composition*. LPMud and REALM argue
about something deeper: **how much power to hand the person who extends the
game, and how to contain it.**

LPMud's bargain is **maximum power, contained by identity.** Every builder is
a wizard; a wizard writes a full compiled language that runs native; the
containment is *not* the language (it's unrestricted) but the **master
object + uid/euid capability system + eval-cost budget**. Safety is a
perimeter (who are you, what's your euid, have you burned your ticks), not a
property of the code. The upside is staggering expressiveness — the mudlib is
a real program. The downside is that the trust boundary is *social and
operational*: you must trust your wizards, because the driver can't stop
hostile LPC, only mis-*identified* LPC.

REALM's bargain is the inverse: **bounded power, contained by construction.**
Nobody is trusted with native execution from an in-game prompt (invariant
#5). The containment *is* the language — `safe_eval`'s denylist means the
code physically cannot do the dangerous thing, so REALM can hand a softcode
surface to *any* builder, live, without a wizard-vetting ceremony. The cost
is exactly the capability list above: no classes, no inheritance, no
closures, no `->`. REALM deliberately traded LPC's power for the ability to
let untrusted people write code safely — and then bought *back* the missing
power for trusted authors via the `@softcode_function` native tier.

So LPMud is the strongest possible statement of the thesis REALM rejected:
"the game is a full program, and safety comes from *who runs it*." REALM's
counter-thesis: "the game is data plus a caged expression layer, and safety
comes from *what the layer can express* — with a separate, explicitly
privileged native tier for the rest." Both are coherent. LPMud optimizes for
builder power on a small trusted team; REALM optimizes for safe extension by
an untrusted many.

## Verdict & steal-list

**REALM already has parity on:** the engine/game split itself (LPMud proves
the microkernel instinct is right), a single authority chokepoint
(`controls()` ≈ master object), a deploy-time native escape hatch
(`@softcode_function` ≈ simul-efun, and REALM's *two-tier* version is safer),
owner-delegation (≈ euid), per-object periodic behavior (`on_tick` ≈
`heart_beat`), and deferred one-shots (`wait` ≈ `call_out`).

**Genuinely worth stealing from LPMud** (ranked — honest that much of LPMud's
power is exactly what REALM chose *not* to have):

1. **User-visible task handles** — `call_out` returning a handle plus
   `find_call_out`/`remove_call_out` (`func_spec:503-506`). REALM's `wait()`
   is fire-and-forget; letting softcode *cancel/enumerate* its scheduled jobs
   is cheap, portable, and closes a real gap (the same one MOO's `fork`/`kill`
   exposed). Highest-value, lowest-conflict steal.
2. **The `reset()` / `clean_up()` lifecycle pair** — kernel-driven periodic
   repopulate (`reset`, `backend.c:1343`) and **return-value-driven idle
   self-GC** (`clean_up`, `backend.c:1444-1462`). `clean_up` in particular is
   elegant: the kernel offers idle objects a chance to justify their
   existence or be reaped. A natural fit for REALM's ephemeral tag as a
   softcode-facing `on_cleanup` behavior.
3. **Path-rewriting security callbacks** — model `valid_read`/`valid_write`
   (`master_skeleton.c:1040-1054`): a policy hook that returns a *rewritten
   target* (or deny), not just a bool. Generalizes `controls()` for cases
   where authority should *remap* an action, not merely veto it.
4. **The euid / theoretical-vs-effective split, made explicit** — REALM's
   owner-delegation already *is* euid; naming it and exposing "act with
   whose authority" as a first-class softcode concept (`set_task_perms`-style)
   would sharpen the model (`master_skeleton.c:1004-1026`).
5. **Backup-object hot-swap for native bindings** — LPMud keeps *old* sefuns
   resolving via backup objects so live code doesn't break on redeploy
   (`simul_efun.c:10-23`). A versioning discipline worth copying for
   `@softcode_function` deploys.
6. **The eval-cost budget as a first-class, queryable number** — REALM caps
   sandbox runtime; LPMud makes the *remaining* budget inspectable
   (`i-eval_cost.h`), which lets long jobs voluntarily `call_out` their
   continuation. Useful idiom if REALM ever wants cooperative long tasks.

**Explicitly NOT stealing** (this is the thesis, not an oversight): LPC's
full compiled per-object language, `inherit`, `->` dispatch, and first-class
closures. Handing every builder a native compiled language is exactly the
power REALM refused in favor of sandboxed-softcode-for-all plus a
native-binding tier for the trusted few. LPMud is the reference for *how far
the game layer can go*; REALM's boundary is drawn deliberately short of it.

**Where REALM is already ahead:** untrusted-safe live coding (LPMud can't let
a random builder write LPC), the two-tier trust model (sefuns are all one
tier), automatic incremental persistence (LPMud's `save_object` is manual and
per-object), and structured two-pass action propagation with multiroom reach.

*Status: reference comparison, no decisions taken. The scheduling steals
(task handles, `reset`/`clean_up`) are the concrete follow-ups; revisit
alongside the MOO `fork`/`kill_task` gap, which is the same decision.*
