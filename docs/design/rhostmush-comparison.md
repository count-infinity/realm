# RhostMUSH Comparison vs REALM (a DELTA against the Penn + MUX surveys)

RhostMUSH is a **TinyMUSH-family cousin**, sharing the `#dbref` object graph,
attributes, `$`-commands, `@`-actions, boolexp locks, and `u()`/ufun softcode
with PennMUSH and TinyMUX — roughly **85% overlap**. So this is **not** a
re-survey. It is a **delta** against the existing
[PennMUSH inventory](pennmush-inventory.md) and
[TinyMUX comparison](tinymux-comparison.md): what Rhost *adds* or does
*differently*, and only that. Where a Rhost feature is already covered by
either survey (the string/list/math builtins → Python, reality-levels →
MUX `RXLEVEL`, comsys/mail → the known comms gap), it is called out as
**already flagged** and not re-derived.

Rhost's reputation is "the kitchen-sink MUSH" — the largest built-in function
set of any MUSH, plus the most granular permission model. Read against the Penn
survey's headline — *"most MUSH functions exist because MUSHcode has no native
data structures, and REALM subsumes ~200 of them by being Python"* — that
verdict holds verbatim: `functions.c` is ~45k lines and evaporates almost
entirely. **The residue that matters is not functions at all.** It is four
*shapes of authority* Rhost's permission model expresses that REALM's does not,
two *policies* for the sidefx binding layer, and — turned up while comparing
Rhost's Lua sandbox against REALM's — **a live DoS in REALM's own script
sandbox, now fixed** (Part 2).

Source read at `~/RhostMUSH/trunk/Server/src/` via `cat -n`/`grep` (line
numbers exact). Screened against `~/pennmush/` and `~/tinymux/`.

---

## Part 1 — Permissions & authority (the crown jewel)

REALM's model: cumulative **roles** (god/admin/builder/player/guest as tags), a
closed 6-entitlement registry (`realm/permissions/entitlements.py:38`),
`role_def` "roles as data," boolexp locks, and `controls()`. The MUX survey
already concluded *"steal the power catalogue, not the bit-flag mechanism"*
([tinymux-comparison.md](tinymux-comparison.md) Part 3). Rhost's delta is not
*more powers* — it is that authority is **subtractive, hidden, and
runtime-reconfigurable**, and REALM's additive role+entitlement model cannot
currently express three of those shapes.

### 1a. Subtractive per-holder capability denial (`@depower` / `DePriv`) — STEAL

Every Rhost wizard capability is checked through one macro,
`DePriv(thing, target, DP_x, POWERword, level)` (impl `flags.c:4878`), against a
depower catalogue `depow_table[]` (`flags.c:826`): `BOOT FORCE NUKE EXAMINE
LOCKS STEAL TEL_ANYWHERE MODIFY …`. Core predicates are *defined* as "flag set
AND not depowered" — `Dark(x)` is `!DePriv(x,…DP_DARK…) && (Flags&DARK)`
(`flags.h:897`). So an operator takes a full wizard and removes exactly
`@nuke`, leaving everything else.

REALM entitlements are **additive only**. The sole subtraction is the
all-or-nothing `quelled` tag (`roles.py:87`), which drops you to PLAYER
wholesale. There is no way to say "full admin, minus `LOCK_BYPASS`" or "wizard
who cannot `@force`." A `role_def` (`entitlements.py:126`) can only *union*
grants.

**STEAL — entitlement/role layer.** Add a per-object *entitlement-denial* set
that subtracts from `entitlements_of()` after the role/role_def union resolves.
Steal the **subtractive-override mechanism at REALM's coarse grain** — not
Rhost's 37-way FORCE/BOOT/NUKE split, which is exactly the flag-soup REALM
rejected.

### 1b. Permissioned + hidden tags via a `tag_def` registry — STEAL

Every Rhost flag/toggle carries **four** independent permission masks, not one:
`listperm` (*who may SEE it when set*), `setovperm`, `usetovperm`, `typeperm`
(which object types may hold it) — `flags.h:594`. All four are reconfigurable
live via `@flagdef` / `@toggledef` / `@totemdef` (`do_flagdef`, `flags.c:5831`),
and `@totemdef` mints entirely new named flags with full ACLs. A flag with
`listperm & CA_NO_GUEST` is genuinely invisible to guests (`flags.c:2914`).

REALM tags are free-form strings; any builder can add any tag subject only to
`controls()`. There is **no per-tag policy** and **no hidden tag**: REALM cannot
express "only admins may set `FROZEN`," "the `SUSPECT` tag is invisible to
non-staff," or "this tag is valid only on rooms." `may_change_role_tag`
(`roles.py:172`) gates only the 5 role tags.

**STEAL — tag layer, as an optional `tag_def` registry** mirroring the existing
`role_def` "tags as data" pattern: a `tag_def` object naming a tag plus
`set`/`unset`/**`see`**/`type` policy. Free-form tags stay the default. The
**hidden-tag (see-mask)** half is the highest-value piece — staff-only
invisible state (`SUSPECT`, monitored) that survives `@examine` — and REALM has
no current expression for it.

### 1c. Data-driven runtime command/switch access (`access` / `cf_access`) — STEAL

Each Rhost command carries `perms`/`perms2` bitmasks plus a per-switch NAMETAB
(`command.h:224`); the gate is `check_access` (`command.c:2240`). An operator
re-permissions **any command or any single switch at runtime**:
`access <cmd>=<perms>` / `access <cmd>/<switch>=<perms>` (`cf_access`,
`command.c:5704`). It even goes meta: `cf_cf_access` sets who may change each
*config directive itself* (`conf.c:4217`).

REALM command access is a **coarse role tier baked into code**:
`has_permission(actor, permission)` against a fixed map (`roles.py:216`), not
per-switch, not re-gatable without editing the command class. REALM's own code
flags this as an open question (`roles.py:224`: *"Command authorization belongs
at the service layer"*).

**STEAL — command-dispatch layer.** A data-driven command-access table
(overridable per command, ideally per switch) that the dispatcher consults,
defaulting to the code-declared tier. This advances REALM invariant #4 and the
parked backlog item, and pairs with the filed *object-command discoverability*
work (both make the command layer data-driven). Take the *table*, not the
CA-bit encoding. A **deny-if-tag / boolexp** clause on an entry subsumes Rhost's
`CA_NO_GUEST`/`NO_SUSPECT` negative gates for free.

### Already covered / NO

- **`NoCode` per-object softcode freeze** (`flags.h:179`, owner-inherited via
  `NoCode(x)` at `flags.h:854`) — **ALREADY COVERED.** REALM's `halt` tag is
  the PennMUSH-`HALT` equivalent and gates the *entire* softcode surface:
  `$`-commands and `^listen` (`triggers.py:402`), `ON_<EVENT>` triggers
  (`engine.py:547`), and the central execution gate (`engine.py:482`). `@chown`
  auto-halts scripted objects on transfer (`admin.py:131`) — the exact
  moderation use case. The *only* sliver Rhost adds is **owner-inheritance**
  (freeze a player → all their objects freeze in one move); REALM's `halt` is
  per-object. Minor convenience; file it, don't build machinery for it.
- **Graded-by-rank capabilities** (`POWER_LEVEL_GUILD/ARCH/COUNC`, 2-bit values,
  `flags.h:266`; the Immortal>Wizard>Councilor>Architect>Guildmaster ladder,
  `command.c:5177`) — **INTERESTING BUT NO, by design.** REALM chose a flat
  5-role ladder; graded-by-target-rank is the flag-soup it rejected. One idea
  worth noting, not building: REALM's `CONTROL_ALL` is absolute, so "admins
  can't act on peer admins" is inexpressible.
- **`levels.c`** is `#ifdef REALITY_LEVELS`, not RPG tiers — the same
  orthogonal-visibility layer the **MUX survey already flagged** as niche
  (RXLEVEL/TXLEVEL). **REDUNDANT.**
- **Totems as themeable user-flags**, `autoreg.c` email registration, the
  Guest/Wanderer tiers — subsumed by REALM's free-form tags / existing guest
  role, or tangential moderation features. **ALREADY COVERED / out of scope.**

---

## Part 2 — The sidefx binding layer, and a REALM sandbox DoS it surfaced

Rhost's famed "side-effect functions" (`set/create/link/tel/pemit/dig/…`,
`functions.c:40836`) are **not** a Rhost invention — Penn ships them
(`~/pennmush/src/function.c:393`) and the Penn survey already mapped them to
`create_obj`/comm/OLC. **ALREADY COVERED.** But Rhost's *gating architecture*
around them yields two policies REALM should adopt when it exposes
state-mutating `@softcode_function` bindings.

### 2a. Per-task state-mutation budget — STEAL

A counter (`mudstate.sidefx_currcalls`) bumped in every sidefx function and
enforced centrally in the evaluator (`eval.c:1872`): once it reaches
`sidefx_maxcalls` (default 1000, `conf.c:291`), evaluation aborts. This caps
the number of *mutations* one command evaluation may perform, **independent of**
recursion/function-call limits — a runaway `iter(lnum(100000), create(...))` is
bounded specifically.

**STEAL — kernel/scheduler primitive.** When REALM exposes mutating softcode
bindings, a per-task *mutation budget* enforced in the softcode scheduler (not
per-function) is the clean DoS guard. Neither Penn nor MUX has a mutation-scoped
budget. Cheap; a counter and a check.

### 2b. A mutating function reuses the equivalent command's own permission check — STEAL

Every Rhost sidefx function looks up the corresponding hard command and runs
*its* access gates before acting: `fun_create` does `ohtab_find("@create")` then
`check_access(...)` (`functions.c:41190`). So `func()` authority ≡ `@command`
authority — softcode can never be a privilege-escalation path around a
locked-down command. (Penn re-implements each function's permission logic
inline, so the two can drift.)

**STEAL — binding-registry policy.** For REALM's `@softcode_function` bindings,
the invariant *"a binding that performs action X reuses the same permission
check as the command that performs X"* is a clean, auditable rule. It **folds
into the existing `@function` backlog entry** as a required design constraint.

### 2c. The Lua sandbox pointed at a live REALM DoS — FOUND & FIXED (2026-07-23)

Rhost's Lua sandbox deletes `pcall`/`xpcall` on purpose (`lua.c:357`) with the
rationale: *"they catch luaL_error from the alarm timer hook, allowing scripts
to bypass the 5ms kill switch silently."* Applying that lens to REALM's sandbox
exposed the same class of hole, **exploitable in REALM today**:

REALM's loop watchdog is a `sys.settrace` tracer that raises `ScriptTimeout`
(`sandbox.py`), `ScriptTimeout` subclassed `Exception`, and `ast.Try` was **not**
forbidden — and CPython *disables a trace function that raises*. So
`try: while True: pass` `except Exception: while True: pass` catches the first
timeout and runs the rest of the script with **no watchdog at all**, pinning an
uninterruptible `run_in_executor` thread → server-wide DoS. Verified by running
the exploit under an OS timeout.

**Fixed this session** (see the SHIPPED BACKLOG entry): resource-kills now raise
through a `BaseException` wrapper (a script's `except Exception` can't catch
them, translated back to the public `ScriptTimeout` at the trusted boundary),
the validator rejects the catch-all handlers that reach `BaseException` (bare
`except:` / `except BaseException`; no existing softcode used either), and a
per-script **recursion-depth ceiling** counted via the tracer's call/return
events closes a sibling vector (recursion that catches its own
`RecursionError`, which the *time* watchdog cannot catch near the ceiling where
the tracer has no stack). This is the settrace-based per-execution depth limit
that the *"AST injection"* backlog entry (2126) named but didn't pursue — and it
counts lambda calls too, which AST injection cannot.

### `EXECSCRIPT` — INTERESTING BUT NO

`functions.c:21040`: softcode shells out to an external OS executable
(path-sanitized, `@power`-gated). The *intent* — softcode reaching trusted
external computation — is exactly what REALM's `@softcode_function`
Python-binding registry already provides, in-process and typed. The OS-exec
escape hatch is the unsafe version of REALM's architecture. Confirms the need,
not the mechanism.

---

## Part 3 — Perception & content

### `senses.c` — INTERESTING BUT NO (REALM is already deeper)

The file most expected to yield gold. It is 199 lines: four near-identical
commands `do_touch`/`do_taste`/`do_listen`/`do_smell`, each firing a
self/others/action attribute triple via `did_it` (touch → `A_STOUCH`/`A_SOTOUCH`/
`A_SATOUCH`, `senses.c:59`). The damning detail: the visibility gate is
**identical to sight** — `Cloak`/`SCloak` (`senses.c:57`). There is **no
cross-modal perception**: you cannot smell what you can't see, hear in the dark,
or listen through a wall.

REALM's `can_see` (`realm/core/perception.py:81`) is strictly richer
(invisibility + darkness + hidden/stealth + see-all), and REALM adds per-looker
disguise/recognition naming and per-listener speech renderers (languages,
whispers) that senses.c has no analog for. The `did_it` triple is exactly
REALM's `Action.add_message(..., success_only=True)` (`verbs.py:257`).
**Importing senses.c's design would be a regression.** If multi-sensory flavor
is ever wanted, add `smell`/`listen`/`touch` verbs on the existing verb +
`describe.py` machinery, and gate each sense *differently* (hear-in-dark,
smell-through-exits) — which Rhost structurally cannot.

### `@saystring` — STEAL (small)

`speech.c:178` (and shout at `:1609`): before formatting a `say`, Rhost pulls
the speaker's `A_SAYSTRING` and substitutes it for the literal "says." A player
sets `@saystring me=growls` → everyone hears `Zeke growls, "…"`. REALM's say
verb is hardcoded (`verbs.py:257`), but it already reskins the speaker's *name*
in speech (`voice_as`, `propagation.py:208`).

**STEAL (small) — the natural completion of the `voice_as` seam.** Read an
optional `db.say_verb` in the say template. Additive flavor, no kernel change.

### Already covered

- **`did_it` self/others/action triple**, **reality-level-filtered descriptions**
  (`look.c:2174`), **Cloak-on-all-senses**, the **`@nameformat`/`@conformat`
  per-object display templates** (`look.c`), the **`M_@EMIT` outbound transform
  hook** — all either covered by REALM's `Action.add_message` + `render.py` +
  `@detail` + `register_speech_renderer`, or (reality levels) already flagged in
  the MUX survey. The one filing-worthy idea is a **dark-variant display
  format**, and REALM already has `db.dark_msg` (`render.py:107`).
- **`news.c` (MushNews)** — a Usenet-style forum with per-group read/post/admin
  lock triples and per-user unread tracking (`news.c:109`). A clean data model,
  but it is REALM's existing lock system applied to a BBS. **File as a
  data-model reference for the known comms gap**, not a novel mechanism.
- **`door*.c` / `empire.c`** — `door.c:385` opens an **outbound TCP socket** and
  multiplexes it into a player's session; `door_mush.c` bridges to another MUSH,
  `empire.c` is a **client to the external Empire war-game server**. Niche,
  security-sensitive, unrelated to game modeling. **INTERESTING BUT NO** — if
  REALM ever wants an external bridge, Python `asyncio` makes it a library, not
  an engine feature.

---

## Part 4 — Architecture (mostly non-lessons)

### `LUA` as an external API surface — STEAL (optional)

Unlike MUX, Rhost's Lua is **not** an in-game `lua()` softcode function — it is
reachable **only** through the built-in HTTP server: a request carries the
script in an `X-Lua` header (`netcommon.c:6407`), authenticated as
`#dbref:password` requiring `POWER_API` + a per-object `TOTEM_API_LUA` flag +
an IP allowlist (`netcommon.c:6510`), runs in a fresh interpreter with
world bindings (`rhost.get()`, permission-checked, `lua.c:126`), and returns
**JSON**.

The MUX survey already settled the *"second in-game dialect"* question as a NO
([tinymux-comparison.md](tinymux-comparison.md) §5c). Rhost's angle is
**orthogonal**: scripting as the *external integration API* — for web
dashboards, bots, tooling — capability-gated and resource-limited.

**STEAL (the pattern, not the language; optional).** Binds to REALM's
HTTP/websocket layer and the two-tier trust invariant. A first-class,
capability-gated, resource-limited scripting endpoint that runs *Python* against
the live world and returns JSON — a middle tier between sandboxed in-game
softcode and deploy-time native bindings. Downgrade to NO if REALM decides it
never wants remote scripting.

### Non-lessons — REDUNDANT / NO

- **MDBX backend + attribute-chunk cache** (`udb_mdbx_*`, `udb_acache.c`) — a C
  server's on-disk attribute store with zero-copy mmap reads and LRU eviction.
  REALM holds the whole object graph as live Python in RAM with periodic
  dirty-flush; there is no cache-miss-to-disk path to engineer. The one
  transferable idea (batch dirty writes in one transaction) REALM already does
  (`persistence/manager.py:179`). **REDUNDANT.**
- **`compress.c`** (8-bit bigram attribute compression), **`websock2.c` /
  `telnet_io.c` + libtelnet** (hand-rolled framing/negotiation) — a Unicode
  Python stack on Twisted subsumes all of it; REALM already has
  telnet/websocket/GMCP. **REDUNDANT.** (Lone note: Rhost negotiates RFC 2066
  CHARSET; check REALM advertises charset, otherwise nothing.)
- **Semaphores / `@wait`** (`cque.c:161`) — the classic attribute-counter model
  the **MUX survey already dissected** and recommended replacing with a proper
  event/condition object. REALM has one-shot `schedule_wait` but no cross-task
  rendezvous — a gap **already documented**. Rhost adds nothing new.
- **`sqlite.c` + `heavy_cpu_lockdown` circuit breaker** (`functions.c:4402`) — a
  global panic switch for synchronous blocking queries on the single-threaded
  server. REALM runs blocking I/O off-loop (Twisted/`run_in_executor`), so the
  problem dissolves and no lockdown is needed. **INTERESTING BUT NO.**

---

## Verdict

After subtracting Python, the Penn/MUX surveys, and the honest no's, RhostMUSH's
150k lines yield:

**Steal (ranked):**

1. **[SHIPPED 2026-07-23] Sandbox DoS fix** — the try/except-swallows-the-watchdog
   hole the Lua sandbox pointed at. Verified and closed.
2. **Subtractive capability denial** (1a) — "full admin minus X"; entitlement layer.
3. **Permissioned + hidden tags** (1b) — a `tag_def` registry with a `see` mask;
   the hidden-tag half is the highest-value new expression.
4. **Data-driven runtime command/switch access** (1c) — advances REALM's own
   parked "command authorization at the service layer" question.
5. **Per-task state-mutation budget** (2a) — DoS guard for future sidefx bindings.
6. **Mutating-function-reuses-the-command's-permission-check** (2b) — folds into
   the `@function` backlog entry as a design constraint.
7. **Scripting-as-capability-gated-HTTP-API** (4, optional) — Python against the
   live world, returning JSON; a trust tier between softcode and native bindings.
8. **`@saystring`** (Part 3, small) — per-speaker say-verb; completes `voice_as`.

**The famous parts are non-lessons:** the 45k-line function library evaporates
(Python + Penn/MUX); `senses.c` is *weaker* than REALM's perception kernel and
would be a regression to import; MDBX/cache/compression/transports/semaphores
are all subsumed by REALM's in-memory + Twisted + SQLite stack; the second-Lua
dialect and `EXECSCRIPT`/`door`/`empire` bridges are settled or misaligned NOs.
`NoCode` is already REALM's `halt` tag (PennMUSH-`HALT` parity).

Rhost's one reusable *idea* is **not granularity** — REALM rightly rejected the
200-flag soup — it is that authority can be **subtractive, hidden, and
data-driven**, three shapes REALM's additive model cannot express, each binding
to an existing layer (entitlements, tags, dispatch) with no new flag machinery.

*Status: reference survey, no decisions taken beyond the shipped security fix —
captured for evaluation. Delta against [pennmush-inventory.md](pennmush-inventory.md)
and [tinymux-comparison.md](tinymux-comparison.md). Source read at
`~/RhostMUSH/trunk/Server/src/`.*
