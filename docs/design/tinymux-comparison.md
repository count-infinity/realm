# TinyMUX Comparison vs REALM (a DELTA against the Penn survey)

TinyMUX is a **Penn-family cousin**, not a separate lineage: the softcode
model, the `#dbref` object graph, attributes, `$`-commands, `@`-actions,
locks, and roughly **250 built-in functions** overlap ~90% with PennMUSH. So
this is **not** a re-survey. It is a **delta** against the existing
[PennMUSH inventory](pennmush-inventory.md): what MUX *adds* or does
*differently*, and only that. Where a MUX feature is already covered by the
Penn survey (vectors, JSON, `timefmt`, connection introspection,
action-attributes), it is called out as **already flagged** and not
re-derived.

Read against the Penn survey's headline — *"most of Penn's 531 functions
exist because MUSHcode has no native data structures, and REALM subsumes
~200 of them by being Python"* — the same verdict holds verbatim for MUX.
The MUX function table is `builtin_function_list[]` at
`~/tinymux/mux/modules/engine/functions.cpp:14903` (250 entries). The
strings/lists/math/bit/control half evaporates into Python identically.
**Don't re-read that conclusion here; it's unchanged.** This doc is only
about the residue that is *MUX-specific*.

> **Provenance note — this is a modernized fork.** The tree at `~/tinymux`
> is built with `./configure --enable-realitylvls --enable-wodrealms`
> (`~/tinymux/CLAUDE.md`) and has been re-architected well past stock
> TinyMUX 2.x: the softcode engine is a dlopen'd **COM-style module**
> (`engine.so`), there is a softcode **JIT** (AST → HIR → native codegen),
> an embedded **Lua 5.4** interpreter, WebSocket/GMCP transport, and
> reality-levels/World-of-Darkness flags compiled in. Where a delta is a
> *fork* addition rather than *stock MUX*, this doc says so — because the
> fork's additions (microkernel modules, JIT, second language) are exactly
> the ones that speak to REALM's thesis, and it would be dishonest to
> present them as generic "MUX."

---

## Part 1 — MUX-distinct softcode functions (not in the Penn survey)

Screened against the Penn survey's function lists. Functions MUX shares with
Penn (the string/list/math bulk, plus vectors/JSON/time already flagged in
Penn Part 2) are omitted. What remains — genuinely MUX-distinct or
notably-different builtins:

| MUX function(s) | What it does | Not in Penn survey because | REALM angle |
|---|---|---|---|
| **`ROUTE`** (`funceval2.cpp:2935`) | `route(src, dest[, distance\|path\|rebuild])` — **server-native BFS pathfinding** over `NAVIGABLE`-flagged rooms; returns next-hop, full path, or hop-distance, with a rebuildable route cache | Penn has no in-server pathfinding primitive | **High value.** NPC autopilot / "walk to" / flee / patrol want exactly this. A `@softcode_function route()` over REALM's room graph is a clean native binding. |
| **`LMATH` / `LIMATH`** (`funmath.cpp:512`) | `lmath(add, 1 2 3)` = fold a math op across a list in one call (`LIMATH` = integer variant) | Penn expresses this via `fold()`/`reduce` idioms | Redundant — Python `sum()`/`math.prod()`/`functools.reduce`. Skip. |
| **`DIST2D` / `DIST3D`** | Euclidean distance between 2- or 3-tuples | Penn survey listed the vector family but not the distance helpers | Pairs with the vectors already flagged for the **3D spatial sidecar**. Ship alongside them. |
| **`CONNLOG` / `ADDRLOG` / `CONNRECORD` / `CONNLAST` / `CONNLEFT` / `CONNTOTAL`** (`functions.cpp` ~12440) | Query the **persistent connection-history log** from softcode: `connlog(player[,limit])` → `id\|player\|connect\|disconnect\|host\|ip\|reason` records | Penn's `conn`/`idle` (already flagged) read *live* sessions; MUX also persists and queries *historical* logins | Extends the Penn "connection introspection" steal-item into **historical** territory — useful for alt-detection / staff tooling. Note as a superset. |
| **`RXLEVEL` / `TXLEVEL` / `HASRXLEVEL` / `HASTXLEVEL` / `LISTRLEVELS`** | Read/test an object's **reality levels** — an orthogonal visibility layer (an object at reality level "umbra" is invisible to viewers who can't perceive it) | Penn has no reality-level system | A distinct **visibility-layering** idea (see Part 3). Orthogonal to locks/roles. |
| **`GRAPHEMES` / `ACCENT` / `STRIPACCENTS` / `STRDISTANCE`** (`functions.cpp:12436`) | Unicode grapheme-cluster explode, accent apply/strip, Levenshtein edit distance | Penn is byte/ASCII-centric; MUX is UTF-8 native | REALM is Python 3 → grapheme-awareness and `difflib`/edit-distance are library calls, not features. Redundant. |
| **`SOUNDEX` / `SOUNDLIKE`** | Phonetic matching | Penn lacks | Minor; a library call in Python if ever wanted. |
| **`LUA`** (`functions.cpp:13285`) | `lua(obj/attr[, args…])` — execute an attribute as a **Lua 5.4 script** in a sandbox, args via `mux.args` | Penn has one softcode language | **Conceptually interesting** (see Part 5): precedent for a *second* embedded scripting dialect alongside MUSHcode. |
| **`MAPSQL` + `SQL` + `RS*` cursor family** (`RSNEXT RSPREV RSREC RSRECNEXT RSRECPREV RSROWS RSRELEASE RSERROR`) | `mapsql(obj/attr, query)` maps softcode over result rows; the `RS*` set is a **stateful recordset cursor** — open a query, step rows/records forward/back, release | Penn's `sql()`/`mapsql()` (already flagged) are one-shot; MUX adds a **cursor** and runs async (Part 4) | The cursor is the delta. Only relevant if REALM ever exposes SQL to softcode (it deliberately doesn't — SQLite *is* the backend). |
| **`ASTEVAL` / `ASTBENCH` / `JITSTATS` / `BENCHMARK` / `RVBENCH` / `CACHESTATS`** | Introspect/benchmark the softcode **compiler/JIT** and evaluation caches | Penn's parser is a tree-walker with nothing to introspect | Tooling for the fork's JIT (Part 5). Not a game feature. |
| **`GMCP`** | Emit a GMCP (OOB) package to a client from softcode | Penn survey noted JSON-for-clients but not a GMCP verb | Small: a `gmcp()` binding is the softcode side of REALM's OOB/GMCP story. Worth pairing with the already-flagged JSON functions. |
| **`FCOUNT` / `FDEPTH` / `OBJMEM` / `PLAYMEM` / `STRMEM`** | Runtime introspection: current function-call count/recursion depth; memory used by an object/player/string | Penn lacks most | Debug tooling; a `@stats`-adjacent nicety. Low priority. |
| **`LATTRCMDS` / `LCMDS`** (`functions.cpp:12097`) | List the `$`-command attributes on an object / all commands it responds to | Penn's `lattr` (already flagged) globs attributes but doesn't single out `$`-commands | Nice **softcode-command introspection** — "what commands does this object define?" Pairs with the Penn `lattr` steal-item. |
| **`BASECONV` / `SPELLNUM` / `ROMAN` / `DIGITTIME` / `ETIMEFMT` / `SINGLETIME`** | Base conversion, number-to-words, roman numerals, duration formatters | Penn survey covered `timefmt`/`convtime` but not these | Trivial in Python; skip except as `timefmt` companions. |

**Bottom line on functions:** after subtracting Python-subsumed builtins and
Penn-shared ones, the *only* MUX function worth stealing that the Penn survey
didn't already flag is **`route()`** (native pathfinding). `connlog` and
`lattrcmds` are **extensions** of items Penn already put on the list. Every
other MUX-distinct function is either a Python one-liner or fork-JIT tooling.
This half of MUX is almost entirely redundant with the existing survey.

---

## Part 2 — The queue / semaphore / `@program` model vs REALM's `wait()`/`prompt()`

**This is where MUX genuinely out-specs Penn**, and it maps directly onto
REALM's `wait()`/`prompt()` and the *"user-visible task handles"* steal-item
carried over from the MOO review. MUX's command queue is in
`~/tinymux/mux/modules/engine/cque.cpp`; the low-level scheduler in
`timer.cpp`.

### 2a. Tasks carry PIDs — inspectable and killable (validates "task handles", partially)

Every queued task has a **PID** (`m_Ticket`, `cque.cpp:567`). Players get:

- **`@ps`** (`do_ps`, `cque.cpp:1806`) — list your pending tasks: wait queue,
  semaphores, and pending SQL queries, each with its PID and time-to-run.
- **`@halt/pid <pid>`** (`halt_que_pid`, `cque.cpp:633`) — kill **one
  specific task by PID**; `@halt <obj>` kills all of an object's tasks.
- **`@drain` / `@notify`** — manage semaphore queues (below).

So MUX **does** have user-visible task handles — but they are **inspection +
kill only**. The PID is minted by the scheduler and surfaced by `@ps`; there
is **no** `x = @wait(...)` that *returns* a handle you capture at spawn time
and pass around. This **partially validates** the MOO steal-list item: MUX
proves handles are useful for *management* (list/kill), but even MUX doesn't
make them first-class *values*. If REALM adds task handles, the ambition
should be **higher than MUX** — a real handle object returned by `wait()`,
with `.cancel()`, not just a `@ps`/`@halt` pair.

### 2b. Semaphores — a first-class cross-task synchronization primitive REALM lacks

This is the biggest MUX-over-Penn-over-REALM delta. `@wait` has two forms
(`do_wait`, `cque.cpp:1435`):

- `@wait <secs>=<cmd>` — a **timed** wait (= REALM `wait(secs)`).
- `@wait <obj>/<attr>=<cmd>` — a **semaphore** wait. The command blocks on a
  **counting semaphore** stored in an integer attribute on `<obj>`
  (`add_to` bumps the counter, `cque.cpp:47`; default attr `A_SEMAPHORE`).
  An optional timeout may be attached (`@wait <obj>/<attr>/<secs>=<cmd>`,
  the `Task_SemaphoreTimeout` path, `cque.cpp:431`).

Release is explicit and separate (`nfy_que`/`do_notify`, `cque.cpp:916`):

- **`@notify <obj>/<attr>`** — release **one** waiting task (FIFO).
- **`@notify/all`** — drain **all** waiters (run them).
- **`@drain <obj>/<attr>`** — discard waiters **without** running them.

That is a genuine **producer/consumer / rendezvous** primitive between
*independent* tasks and *different* objects: task A parks on a counter, task B
(later, elsewhere) notifies it. REALM's `wait()` is a **sleep** — the same
task's own continuation resuming after a delay — with **no** cross-task
signalling. There is no REALM way today for one softcode task to *block until
another task signals it*.

**Assessment for REALM:** this is worth stealing, but **not** as Penn's
attribute-counter API. The Pythonic shape is an **event/condition object**:
`ev = event(); wait(ev)` in one handler, `notify(ev)` / `notify_all(ev)` in
another — a named async rendezvous. The semaphore-in-an-attribute encoding is
a MUSHcode kludge for "no data structures"; REALM has objects and can model
the synchronization primitive directly. The *idea* (cross-task blocking
rendezvous) is the steal; the *encoding* is not.

### 2c. `@program` — a continuation with snapshotted register state (validates `prompt()`)

`@program <player>=<obj>/<attr>` (`do_prog`, `~/tinymux/mux/modules/engine/predicates.cpp:1398`)
redirects the player's **next line of raw input** into `<attr>`, which is then
evaluated. Crucially, it **snapshots the Q-register environment** at the point
of the prompt — `program->wait_regs[i] = mudstate.global_regs[i]` and the
named registers, `predicates.cpp:1516–1535` — and restores them when the input
arrives, so the continuation **resumes with the same lexical environment** it
was suspended in. `@quitprogram` (`do_quitprog`, `predicates.cpp:1334`)
cancels a pending prompt.

**This is precisely REALM's `prompt()`** — suspend a softcode task, capture the
next line, resume with state intact. MUX **validates** the `prompt()` design.
Two deltas worth noting:

1. **State capture is explicit and register-scoped** in MUX (it copies the
   `%q`/named regs). REALM's advantage: because a REALM handler is a *real
   suspended Python coroutine*, the *entire* local scope is preserved
   automatically — MUX has to manually copy the register file because
   MUSHcode has no closures. REALM's `prompt()` is strictly cleaner **by
   construction**, the same way its functions beat Penn's by construction.
2. **`@program` can target *another* player** — a wizard captures someone
   else's input line (subject to `Prog` power / `Controls`,
   `predicates.cpp:1428`). That's a distinct capability (staff-driven guided
   input, "type your password now" flows). REALM's `prompt()` prompts *self*;
   a controls()-gated "prompt on behalf of" variant would match it.

### 2d. Async external I/O is queued, not blocking

`do_query`/`sql_que` puts SQL queries **on the same scheduler** with a
timeout, and results are delivered **asynchronously** (the `RS*`/SQL-timeout
task class in `@ps`). External I/O is a queue citizen, not a blocking call —
serviced by the out-of-process `sqlslave` (Part 4). Penn's `sql()` blocks the
whole server. **The idiom — model external I/O as a scheduled task with a
timeout rather than a synchronous call — is worth internalizing** for any
REALM softcode primitive that touches the network or a slow resource.

---

## Part 3 — Flags & powers vs REALM's roles / tags / `controls()`

MUX (like Penn) splits authority into **two** orthogonal systems; REALM folds
the equivalent into three (roles, tags, `controls()`). The mapping:

### Flags (`~/tinymux/mux/modules/engine/flags.cpp`) — binary state/behavior markers (~90)

`ALONE ABODE ANSI AUDIBLE DARK ENTER_OK HALTED INHERIT JUMP_OK LINK_OK
MONITOR MYOPIC NOSPOOF OPAQUE PUPPET QUIET ROBOT SAFE STICKY TRANSPARENT
VERBOSE WIZARD …`. These are per-object booleans that gate engine behavior.
REALM's equivalent is **tags** plus a handful of typed behaviors. Three
sub-groups of MUX flags are worth a specific REALM note:

- **`MARKER0`–`MARKER9`** — ten **user-definable** flags with no engine
  meaning. This is literally "let builders invent their own boolean tags" —
  **REALM's `tags` set subsumes this outright** (arbitrary named tags, not a
  fixed pool of ten). REALM is strictly better here.
- **Client-capability flags** — `UNICODE TRUECOLOR COLOR256 HTML ANSI ACCENTS
  KEEPALIVE`. MUX records negotiated client capabilities *as object flags*.
  REALM keeps these at the **session layer**, not on the persistent object —
  cleaner separation; don't copy MUX here.
- **Reality / WoD flags** — `FAE CHIMERA PEERING UMBRA SHROUD MATRIX MEDIUM
  DEAD` (the `--enable-wodrealms`/`--enable-realitylvls` set). These implement
  the **reality-levels** visibility layer (Part 1). Orthogonal to locks: two
  objects in the same room can be mutually invisible by reality level. REALM
  has no such layer; if a themed game ever needs "planes"/"phases," this is a
  clean orthogonal-visibility model to remember — but it's niche, not core.

### Powers (`~/tinymux/mux/modules/engine/powers.cpp`) — granular capabilities (~35)

`announce boot builder chown_anything comm_all control_all dark expanded_who
find_unfindable free_money free_quota guest halt hide idle link_anywhere
long_fingers monitor no_destroy no_mail_expire pass_locks poll prog quota
search see_all see_hidden see_queue siteadmin stat_any steal_money tel_anything
tel_anywhere unkillable`.

**This is the real authority delta.** Powers are **fine-grained capability
grants decoupled from the coarse `WIZARD`/`ROYALTY` roles**. `pass_locks`,
`tel_anywhere`, `see_all`, `long_fingers` (touch remote objects), `see_queue`,
`no_destroy`, `prog` — each is an à-la-carte permission you can hand to a
non-wizard. The check is a bit test (`ph_any`, `powers.cpp:15`) layered *on
top of* the `Controls()` authority test.

Mapped onto REALM:

- REALM's **roles** are the coarse `WIZARD`/`ROYALTY` tier.
- REALM's **`controls()`** is MUX's `Controls()` — the ownership/authority
  spine.
- **MUX powers are what you get when a role can be decomposed into individual
  capabilities.** REALM has no à-la-carte capability layer between "has role"
  and "controls this object." If REALM ever finds roles too coarse (e.g. a
  trusted builder who may `@teleport` anywhere but is not a full admin), the
  **MUX power list is a ready-made vocabulary of exactly which capabilities
  are worth naming**. That's the steal here — not a mechanism (REALM's
  role+controls+owner-delegation is already more principled than flag bits),
  but the **enumerated capability catalogue**.

---

## Part 4 — Built-in subsystems REALM lacks (channels / mail / async SQL)

All three are **loadable modules** in this fork (`~/tinymux/mux/modules/`),
which is itself the story of Part 5. As *features*, they are the same gaps the
Penn survey already named ("player channels & mail: a comms system") — MUX
just has richer, more softcode-integrated versions.

### comsys — channels (`~/tinymux/mux/modules/engine/comsys.cpp`, 5.3k lines)

A full channel system: named channels with **owner objects**, aliases, titles,
a scrollback **history buffer** (`CBUFFER`/`CRECALL`), and `CWHO`/`CUSERS`
membership. The MUX-distinct twist over Penn is the **mogrifier** — per-channel
softcode hooks on the channel's owner object that transform traffic:

- `MOGRIFY`BLOCK`` — veto/allow a message (`comsys.cpp:1578`).
- `MOGRIFY`MESSAGE`` — rewrite the message text (`comsys.cpp:1654`).
- `MOGRIFY`FORMAT`` — channel-wide format wrapper (like a shared
  `@chatformat`), evaluated by `call_mogrifier` (`comsys.cpp:1262`).

That is a **softcode transformation pipeline attached to a channel** — exactly
the kind of "data-driven behavior hook" REALM's design likes. If/when REALM
grows player channels, **channels-with-`ON_MESSAGE`-style softcode hooks**
(block / transform / format) is the model to copy, not a hardcoded formatter.
REALM has structured *log* channels today but no player chat.

### @mail — messaging (`~/tinymux/mux/modules/engine/mail.cpp`, 5.8k lines)

Full player mail with folders, and — the delta — **softcode read access**:
`MAILLIST MAILINFO MAILFROM MAILSUBJ MAILSIZE MAILFLAGS MAILSEND MAILREVIEW
MAILSTATS MALIAS`. Because the mailbox is queryable from softcode, builders can
write **their own mail UIs / notifiers / auto-responders** in softcode instead
of being stuck with the built-in commands. REALM has no player mail; if it
adds one, **expose it to softcode the way MUX does** (a `mail()` function
family) so the UI is data-driven rather than hardcoded.

### sqlslave — async external SQL (`~/tinymux/mux/modules/sqlslave/sqlslave.cpp`)

An **out-of-process** SQL slave: a separate process holds the MySQL connection
and services queries over a COM-style IPC interface (`CQueryServer :
mux_IQueryControl`, `sqlslave.cpp:20`; `Query()` at `:33`). The main game
**never blocks** on the database — queries are queued on the scheduler
(Part 2d) and results arrive async. This is the architecturally-cleanest part
of MUX's SQL story and the reason the `RS*` cursor exists.

**REALM angle:** REALM deliberately uses SQLite *as its backend* and doesn't
expose SQL to softcode, so the *feature* is a non-goal. But the **pattern** —
*push slow/blocking external I/O into a separate process (or thread/async
task) and deliver results back through the scheduler* — is the transferable
idea, and it generalizes beyond SQL to any HTTP/LLM/file call a REALM softcode
primitive might someday make. (MUX also isolates DNS and the info-slave the
same way, `~/tinymux/mux/src/slave.cpp`.)

---

## Part 5 — Cleaner MUX idioms (mostly this fork's modernization)

These are the MUX ideas that speak **directly to REALM's "Godot of MU*s /
data-driven microkernel" thesis** — and they are largely this fork's
additions, not stock MUX.

### 5a. COM-style microkernel with loadable modules — *the* parallel

The netmux core **dlopens** its subsystems as modules with a COM-like
`IUnknown` contract (`QueryInterface`/`AddRef`/`Release` + class factories).
`~/tinymux/mux/src/modules.cpp:115` loads **`engine.so`** — *the entire
softcode engine* — as a module via `mux_AddModule("engine", "./bin/engine.so")`;
comsys, mail, sqlslave, and lua register the same way (`mail_mod.cpp:86`
`mux_GetClassObject`, `:297` `QueryInterface`). A small kernel; everything
else is a swappable module behind an interface.

**This is REALM's microkernel framing, proven in C++.** It's the strongest
single point of convergence in the whole comparison: MUX independently arrived
at "tiny core + modules behind interfaces," down to making the softcode VM
itself a module. It validates REALM's architecture direction — and REALM's
Python module/entry-point system is a **more ergonomic** realization of the
same idea than hand-rolled COM in C++. Convergent design, REALM cleaner by
language.

### 5b. Softcode JIT (AST → HIR → native code)

This fork **compiles softcode to native machine code**: `ast.cpp` (2.9k lines)
builds an AST, `hir_lower.cpp` (3.9k) lowers to a high-level IR, `hir_opt.cpp`
(1.3k) optimizes it, and `dbt.cpp` + `dbt_elf64.cpp` emit **native code into an
RWX buffer** with a PC-keyed code cache (`jit_alloc`, `dbt.cpp:186`;
`native_code` cache, `dbt.cpp:115`). `JITSTATS`/`BENCHMARK` expose it.

Penn (and stock MUX) tree-walk softcode. REALM's `safe_eval` currently
interprets a Python subset. **The transferable idea: hot softcode can be
compiled/cached rather than re-parsed every tick.** REALM's path is far
gentler than emitting ELF — *compile the safe-AST to Python bytecode once and
cache it*, keyed by attribute version. Same payoff (skip re-parse on hot
paths), no machine-code machinery. Worth remembering if softcode perf ever
bites; premature today.

### 5c. A second embedded language (Lua) behind the same module interface

`lua(obj/attr, …)` (`functions.cpp:13285`) runs an attribute as **Lua 5.4** in
a sandbox, dispatched through a Lua *module* (`mudstate.pILuaControl`). MUX
thus offers **two** softcode dialects — MUSHcode and Lua — behind one module
seam. This is a precedent for REALM's own model: REALM's softcode is a
sandboxed Python subset, and the `@softcode_function` binding seam is exactly
the place a *second* dialect (or a richer Python tier for trusted authors)
could plug in. Not a near-term need, but a validation that "more than one
scripting surface, behind a stable seam" is a sane thing to want.

### 5d. Minor cleaner idioms

- **External I/O as scheduled tasks** (Part 2d/4) — already covered; the
  single most portable idiom.
- **`route()` as a native primitive** (Part 1) — pathfinding belongs in the
  kernel, exposed to softcode, not re-implemented in slow softcode per game.
- **`@ps`/`@halt/pid` task management** (Part 2a) — a minimum-viable task-handle
  UX REALM should meet or beat.

---

## Verdict

- **Softcode functions: ~90% redundant with the Penn survey.** After Python
  subsumption and Penn overlap, the *only* net-new steal is **`route()`**
  (native pathfinding); `connlog` and `lattrcmds` are extensions of
  already-flagged Penn items. Everything else is a Python one-liner or JIT
  tooling. Do not re-port MUX's function table.
- **The queue/semaphore/`@program` model is the real reason to read MUX.** It
  **validates `prompt()`** (`@program` = continuation with saved registers;
  REALM's coroutine version is cleaner by construction), **partially
  validates task handles** (PIDs are list/kill-only, not first-class values —
  REALM should aim higher), and surfaces the **one primitive REALM genuinely
  lacks: a cross-task blocking rendezvous** (semaphores / `@notify`), which
  REALM should adopt as an *event/condition object*, not an attribute counter.
- **Powers give REALM a ready-made capability vocabulary** if roles ever prove
  too coarse — steal the *catalogue*, not the bit-flag mechanism.
- **Subsystems (channels/mail/async-SQL) are the same gaps Penn already
  named**, but MUX shows the *softcode-integrated* way to build them: channel
  **mogrifier hooks**, softcode-readable **mail**, and **out-of-process async
  I/O** delivered through the scheduler.
- **Architecturally, MUX's biggest gift is confirmation:** its COM-style
  **microkernel with the softcode engine itself as a loadable module** is
  REALM's thesis, independently arrived at in C++ — REALM's Python realization
  is the more ergonomic version of the same idea.

*Status: reference survey, no decisions taken — captured for evaluation. This
is a delta against [pennmush-inventory.md](pennmush-inventory.md); see also
[moo-comparison.md](moo-comparison.md) and the
[features-roadmap.md](features-roadmap.md). Source read at
`~/tinymux/mux/modules/engine/` (a modernized `--enable-realitylvls
--enable-wodrealms` fork with a softcode JIT and COM modules — fork-specific
deltas flagged inline).*
</content>
</invoke>
