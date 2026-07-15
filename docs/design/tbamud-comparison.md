# tbaMUD DG Scripts vs REALM

A reference comparison against **tbaMUD** (the living CircleMUD/DikuMUD
continuation) and specifically its **DG Scripts** engine — the richest
trigger-scripting language in the Diku family. Pulled from the `~/tbamud`
source: `dg_scripts.h` for the trigger-type bitvectors, `dg_triggers.c` for
the ~40 trigger dispatch functions, `dg_scripts.c` for the script driver and
control flow, `dg_variables.c` for the `%var%`/dotted-field model,
`dg_event.c` for the timed-event queue, and `dg_mobcmd.c`/`dg_objcmd.c`/
`dg_wldcmd.c` for the command sub-language.

Sits alongside the PennMUSH / LambdaMOO / CoffeeMud / Evennia lineages REALM
already draws on. DG Scripts is the sharpest mirror for REALM's **event-hook
surface** specifically: where MOO is "the whole game is softcode objects" and
Penn is "action-attributes on everything," DG is **a purpose-built trigger
DSL with a mature, TYPED trigger taxonomy** — a curated list of ~40 named
event hooks, each wired into a specific call site in the game's C. That list
is the gold this document mines: it enumerates exactly which game moments a
mature Diku engine thought worth exposing to builders, and therefore surfaces
precisely which event hooks REALM's `ON_<EVENT>` surface is still missing.

## The one deep difference

**DG Scripts is a closed, typed trigger vocabulary + string-substitution DSL;
REALM is an open, data-driven event stream + a Python-subset softcode.** In
DG, a "trigger type" is a bit in a bitvector (`MTRIG_GREET`, `OTRIG_WEAR`,
`WTRIG_RESET`; `dg_scripts.h:53-110`) and a matching C dispatch function
(`greet_mtrigger`, `wear_otrigger`, `reset_wtrigger`) called by hand from the
relevant game code. The taxonomy is **rich but frozen**: adding a new trigger
type means editing C, adding a bit, and inserting a call site. In REALM, an
"event" is just a propagated `Action` with a type string; `ON_<EVENT>`
softcode matches on the suffix (`triggers.py:170-173`), and firing a brand-new
event is one `act(target, msg, type='on_whatever')` call — no core edit. So
**DG's surface is larger today but closed; REALM's is smaller today but
open-ended by construction.** Nearly every row below flows from that.

A second structural difference: **a DG trigger is simultaneously a reaction
and an interception.** The same `greet_mtrigger`/`get_otrigger`/`drop_otrigger`
runs the script *and* reads its `return 0/1` to allow or block the action
(`dg_triggers.c:227-233, 698-720`). REALM splits these into a **two-pass**
model — `on_check` (permission pass: block/modify) then `on_react` (reaction
pass) (`realm/core/propagation.py:401-427`, `realm/core/behaviors.py:5-11`) —
which is cleaner but means a DG "greet trigger that blocks entry" maps to
*two* REALM hooks, not one.

---

## Part 1 — The trigger taxonomy (the gold)

DG defines trigger types per attach-target: **mob** (`MTRIG_*`), **object**
(`OTRIG_*`), **room/world** (`WTRIG_*`) (`dg_scripts.h:53-110`). Each is
gated by a numeric argument `narg` that is *typed per trigger* — a percent
chance for RANDOM/GREET/etc., a minimum coin amount for BRIBE, an HP-percent
threshold for HITPRCNT, the game-hour for TIME, a position-bitvector for the
object COMMAND trigger. That "**every trigger carries one typed numeric
parameter**" idea is itself worth noting.

Legend: ● have · ◑ partial · ✗ **GAP** (no REALM equivalent).

### Mob triggers (`MTRIG_*`)

| DG trigger | Fires when (`dg_triggers.c`) | REALM equivalent | Status |
|---|---|---|---|
| `COMMAND` | actor types a command in the room; prefix-matched, `return 1` swallows it (`:297`) | `$`-command (`CMD_`/`$greet`) | ● have |
| `SPEECH` | actor says a word/phrase; `word_check` phrase match (`:340`) | **`^listen`** (`LISTEN_`) | ● have (strength) |
| `ACT` | a word/phrase passes through `act()` the mob witnesses — socials, combat msgs (`:373`) | `^listen` matches speech only; arbitrary act-text match | ◑ partial |
| `GREET` | someone the mob can see enters; `return 0` **blocks entry** (`:200`) | `ON_ENTER` react + `on_check` block | ◑ partial (2 hooks) |
| `GREET_ALL` | anything enters, even unseen (`:212`) | `ON_ENTER` (no visibility gate) | ● have |
| `ENTRY` | the mob itself arrives in a room (`:281`) | `ON_ARRIVE` | ● have |
| `LEAVE` | someone the mob sees leaves; can block (`:587`) | `ON_LEAVE` (+ `on_check`) | ● have |
| `DEATH` | the mob dies (`:491`) | `ON_DEATH` | ● have |
| `RECEIVE` | actor gives the mob an object; can block/refuse (`:463`) | `ON_RECEIVE` | ● have |
| `BRIBE` | coins given to the mob, `narg` = min amount (`:127`) | `ON_PAYMENT` (buy-shaped, no min-amount gate) | ◑ partial |
| `FIGHT` | **every combat pulse** while the mob fights (`:416`) | — (no per-round combat pulse) | ✗ **GAP** |
| `HITPRCNT` | fighting **and** HP ≤ `narg`% — the "flee at low HP" hook (`:441`) | — (no HP-threshold trigger) | ✗ **GAP** |
| `CAST` | the mob is targeted by a spell; binds `%spell%`/`%spellname%` (`:535`) | — (no ability-targeted hook) | ✗ **GAP** |
| `DAMAGE` | the mob takes damage; `return` **modifies the damage** (`:560`) | `ON_DAMAGE` (+ `on_check` to modify) | ● have |
| `LOAD` | the mob is spawned/instantiated (`:511`) | — (no spawn/load hook) | ✗ **GAP** |
| `MEMORY` | the mob sees someone it `mremember`ed (`:236`) | — (no NPC memory + sighting) | ✗ **GAP** |
| `DOOR` | a door in the room is opened/closed/(un)locked; binds `%cmd%`/`%direction%` (`:617`) | — (no door-manipulation event) | ✗ **GAP** |
| `RANDOM` | random pulse, `narg`% chance (`:110`) | `on_tick` behavior + random gate | ◑ partial |
| `TIME` | game hour == `narg` (`:645`) | `on_tick` + time check | ◑ partial |
| `GLOBAL` | *modifier* — check even if zone empty (`dg_scripts.h:54`) | n/a (REALM fires regardless of occupancy) | — n/a |

### Object triggers (`OTRIG_*`)

| DG trigger | Fires when (`dg_triggers.c`) | REALM equivalent | Status |
|---|---|---|---|
| `COMMAND` | actor types a command while obj is in equip/inven/room — scoped by `narg` position bits (`:723`) | `$`-command (no declarative worn-vs-carried-vs-room scope) | ◑ partial |
| `GET` | obj picked up; can block the get (`:698`) | `ON_GET` | ● have |
| `DROP` | obj dropped; can block (`:835`) | `ON_DROP` | ● have |
| `GIVE` | obj given; binds `%victim%`; can block (`:859`) | `ON_GIVE` | ● have |
| `WEAR` | obj equipped; can block (`:784`) | — (no equip event) | ✗ **GAP** |
| `REMOVE` | obj unequipped; can block (`:808`) | — (no unequip event) | ✗ **GAP** |
| `CONSUME` | obj eaten/drunk/quaffed; binds `%command%` = eat/drink/quaff (`:967`) | `ON_USE` (no eat/drink distinction) | ◑ partial |
| `TIMER` | the object's own countdown timer hits 0 (`:682`) | — (no per-object timer→fire; `wait()` is script-scoped) | ✗ **GAP** |
| `LOAD` | obj is spawned/loaded (`:885`) | — (no spawn/load hook) | ✗ **GAP** |
| `CAST` | obj targeted by a spell (`:909`) | — | ✗ **GAP** |
| `LEAVE` | someone leaves the room the obj is in (`:934`) | `ON_LEAVE` (obj witnesses via propagation) | ● have |
| `RANDOM` | random pulse, `narg`% (`:666`) | `on_tick` + random | ◑ partial |
| `TIME` | game hour == `narg` (`:1002`) | `on_tick` + time | ◑ partial |

### Room / world triggers (`WTRIG_*`)

| DG trigger | Fires when (`dg_triggers.c`) | REALM equivalent | Status |
|---|---|---|---|
| `COMMAND` | actor types a command in the room (`:1077`) | `$`-command on the room | ● have |
| `SPEECH` | actor speaks in the room (`:1116`) | `^listen` on the room | ● have |
| `ENTER` | a character enters the room; can block (`:1054`) | `ON_ENTER` (+ `on_check`) | ● have |
| `LEAVE` | a character leaves the room (`:1204`) | `ON_LEAVE` | ● have |
| `DROP` | something is dropped in the room (`:1147`) | `ON_DROP` (room witnesses) | ● have |
| `RESET` | **the zone repops** — the respawn/decorate hook (`:1022`) | — (no zone-reset event) | ✗ **GAP** |
| `LOGIN` | a player logs into the MUD *in this room* (`:1275`) | `ON_CONNECT` (global, not room-scoped) | ◑ partial |
| `CAST` | a spell is cast in the room (`:1175`) | — | ✗ **GAP** |
| `DOOR` | a door in the room is manipulated (`:1230`) | — | ✗ **GAP** |
| `RANDOM` | random pulse, `narg`% (`:1038`) | `on_tick` + random | ◑ partial |
| `TIME` | game hour == `narg` (`:1256`) | `on_tick` + time | ◑ partial |

### Where REALM is already *ahead* of the DG taxonomy

REALM's `STANDARD_EVENTS` (`triggers.py:180-197`) plus `ON_FAIL`/`ON_PAYMENT`/
`ON_LOOK`/`ON_PUSH` include hooks DG has **no** direct trigger for:

| REALM event | DG equivalent | Note |
|---|---|---|
| `ON_FAIL` | — (none) | blocked/dead-end action hook (Penn `@afail`); DG only has per-action `return 0`, no dedicated fail trigger |
| `ON_LOOK` | — (none) | fires when the object is examined; DG has no "look-at" trigger |
| `ON_DISCONNECT` | — (none) | DG has `LOGIN` but no logout trigger |
| `ON_ATTACK` / `ON_KILL` | — (partial) | DG has `FIGHT`/`DEATH`; explicit attack/kill events are cleaner |
| `ON_PUSH` | — | button/lever style actuation |

---

## Part 2 — The variable model

### DG: `%var%` substitution + dotted read-only fields

Before each command line runs, `var_subst` (`dg_variables.c`) textually
replaces `%name%` / `%name.field%` / `%name.field(sub)%` tokens. Values are
**always strings**; there are no typed object values, only UID strings that
re-resolve on field access.

| DG construct | Example | REALM equivalent |
|---|---|---|
| Bound actor/self | `%actor%`, `%self%` | handler namespace `enactor` / `executor` (`self`) |
| Event payload vars | `%arg%`, `%cmd%`, `%speech%`, `%direction%`, `%amount%`, `%damage%`, `%spell%`, `%object%`, `%victim%` | namespace binds `captures` / event fields |
| Char dotted fields | `%actor.name%` `%actor.level%` `%actor.hitp%` `%actor.maxhitp%` `%actor.gold%` `%actor.sex%` `%actor.class%` `%actor.align%` `%actor.pos%` `%actor.room%` `%actor.vnum%` `%actor.id%` (`dg_variables.c:590-1130`) | **native**: `enactor.name`, `enactor.db.hp`, `enactor.location` — real object attribute access, not substitution |
| Char method-fields | `%actor.varexists(x)%`, `%actor.skill(name)%`, `%actor.has_item(vnum)%`, `%actor.eq(pos)%`, `%actor.canbeseen%` (`:693-1108`) | Python method/attr calls on the object |
| Obj dotted fields | `%obj.shortdesc%` `%obj.type%` `%obj.cost%` `%obj.weight%` `%obj.vnum%` `%obj.contents%` `%obj.carried_by%` `%obj.worn_by%` `%obj.room%` `%obj.wearflag%` (`:1181-1360`) | native object attributes |
| Obj value setter | `%obj.oset(...)%` mutates obj vals inline (`:1283`) | `obj.set_attr(...)` |
| Room dotted fields + exits | `%room.name%` `%room.vnum%` `%room.people%` `%room.north.vnum%` `%room.north.room%` (`:1398-1587`) | `location.exits['north'].destination` etc. |
| Special / global vars | `%global.X%`, `%time.hour%`, `%people.<vnum>%`, `%findmob.<room>(<vnum>)%`, `%findobj.<room>(<vnum>)%`, `%random.char%`, `%random.dir%`, `%random.N%` (`:415-560`) | `search_world`, `now()`, list comprehensions, `random` — Python library |

**Verdict: REALM is ahead on expressiveness, DG is ahead on curation.** DG's
`%actor.field%` is a *safe, read-only, curated* vocabulary — a builder can
never crash the mud or leak internals through it, because each field is a
hand-written C accessor. REALM's `enactor.db.hp` is real Python: more
powerful (arbitrary methods, real math, real objects) but relies on the
sandbox rather than a curated field list. The one genuinely nice DG ergonomic
REALM should note: **the flat `%actor.field%` path syntax is readable inline
in text**, which is exactly what REALM's `[[...]]` inline-Python already
delivers in descriptions — REALM has the mechanism; DG has the terser idiom.

### DG variable scopes — and the two REALM lacks

| DG scope | Mechanism (`dg_scripts.c`) | Lifetime | REALM equivalent |
|---|---|---|---|
| Local | `set`/`eval name …` (`:1746`, `:1765`) | freed at trigger end (`:2712`) | Python locals in the handler namespace |
| Global | `global name` promotes a local to the script's `global_vars` (`:2349`) | persists on the object's script | `obj.db.*` attributes |
| Player-persistent | globals on a PC script are saved to the pfile (`read_saved_vars`/`save_char_vars`) | across logins | `obj.db.*` (persisted) |
| **Remote** | `remote var <uid>` **writes a local var into *another* object's globals** (`:2103`) | on the target | `other.set_attr(...)` (any reachable obj, gated by authority) |
| **Context** | `context <n>` namespaces globals so statics can be partitioned (`:2379`) | per-script | — (no global namespacing) |

`remote` (cross-object variable write) maps cleanly to REALM's `set_attr` on
any reachable object — REALM's is *cleaner* because it's authority-gated
rather than UID-addressed. **`context`** (numeric namespacing of globals so
the same trigger reused on many objects keeps separate static state) has **no
REALM equivalent** — a minor gap, easily served by attribute-key prefixing.

---

## Part 3 — Control flow & the command sub-language

### Control flow

The script driver (`dg_scripts.c:2481`) is a line-at-a-time interpreter over
a linked list of command strings. Its whole control-flow vocabulary:

| DG construct | `dg_scripts.c` | REALM (Python softcode) |
|---|---|---|
| `if` / `elseif` / `else` / `end` | `:2553-2592`, `process_if:1594` | native `if/elif/else` |
| `while` / `done` (100-iter cap, auto-`wait 1` every 30) | `:2570-2617` | native `while`/`for` (sandbox call-count cap) |
| `switch` / `case` / `break` / `done` | `:2583-2622` | native `match`/`if` |
| `set` / `unset` / `eval` | `:2665-2669`, `:1746` | assignment; `del` |
| `global` / `context` / `remote` / `rdelete` | `:2650-2660` | `set_attr` / `del_attr` on self or others |
| `wait <n> [s|t]` / `wait until HH:MM` | `process_wait:1689` | `wait(secs, cmd)` |
| `return <0/1>` (allow/deny the action) | `process_return:2065` | `on_check` → `block()` / `modify()` |
| `attach` / `detach <trig> <uid>` (add/remove a trigger at runtime) | `:1787`, `:1869` | `set_attr` an `ON_*` attr / attach a behavior at runtime |
| `halt` | `:2641` | `return` from the handler |
| `nop`, `extract`, `makeuid`, `dg_letter` | `:2630-2639` | Python slicing / string ops |
| `dg_cast`, `dg_affect` | `dg_misc.c` | ability/effect softcode functions |
| Expression ops: `\|\| && == != <= >= < > /= (contains) + - * / !` | `eval_op:1376` | Python operators (int-only in DG; REALM has full numeric tower) |

**Verdict:** REALM's Python control flow strictly dominates DG's — real
loops, comprehensions, `match`, arbitrary math, string methods, exceptions —
all the things DG bolts on as `while`/`switch`/`extract`/`eval`. The two DG
constructs worth naming: **`return` as action-veto** (REALM does this through
the `on_check` block/modify pass, not a return value) and **runtime
`attach`/`detach`** (REALM covers via setting an `ON_*` attr or attaching a
behavior live).

### The command sub-language (actuators)

DG gives each attach-target a parallel command set — the verbs a trigger uses
to *act on the world*. These are REALM's `act()` + softcode functions.

| DG mob (`interpreter.c:375-396`) | DG obj (`dg_objcmd.c:809`) | DG room (`dg_wldcmd.c:633`) | purpose → REALM |
|---|---|---|---|
| `mecho` `mechoaround` `msend` `mrecho` | `oecho` `oechoaround` `osend` `orecho` | `wecho` `wechoaround` `wsend` `wrecho` | targeted output → `pemit`/`oemit`/`act` |
| `masound` | `oasound` | `wasound` | echo to adjacent rooms → `act` multiroom reach |
| `mzoneecho` | `ozoneecho` | `wzoneecho` | zone-wide echo → zone-master `act` |
| `mload` `mpurge` | `oload` `opurge` | `wload` `wpurge` | spawn/destroy → `create_obj`/`destroy_obj` |
| `mteleport` `mgoto` `mat` `momve` | `oteleport` `omove` | `wteleport` `wat` `wmove` | move things → `move`/`act(type=on_enter)` |
| `mforce` | `oforce` | `wforce` | make another obj run a command → `act`/actuator |
| `mkill` `mdamage` | `odamage` | `wdamage` | combat → damage softcode fn |
| `mdoor` | `odoor` | `wdoor` | edit exits/doors → exit mutation |
| `mtransform` | `otransform` | — | swap a mob/obj's prototype → re-tag/re-parent |
| `mremember`/`mforget` `mhunt` `mfollow` | — | — | `mfollow` → follow chain (`realm/core/party.py`, cascaded by the movement kernel); `mremember`/`mhunt` memory-and-pursuit → **no REALM equivalent** |
| `mlog` | `olog` | `wlog` | builder log → structured log channels |
| — | `osetval` `otimer` | — | set obj vals / arm timer → `set_attr` |

Coverage is broad (echo/spawn/move/force/combat/log all map to `act` +
softcode functions), with the honest gaps being **`mtransform`** (hot-swap a
running entity's prototype) and the **`mremember`/`mhunt`** NPC
memory-and-pursuit pair.

---

## Part 4 — Timed events: `dg_event.c` vs REALM tick + `wait()`

DG's `dg_event.c` is a **bucketed priority queue keyed on the game pulse**
(`event_create`/`event_process`, `dg_event.c:57,109`; `queue_enq` buckets by
`key % NUM_EVENT_QUEUES`, `:206`). It exists *only* to implement the script
`wait` command: `process_wait` schedules a `trig_wait_event` and stashes
`trig->curr_state` so the driver resumes mid-script when the event fires
(`dg_scripts.c:1741`). There is no user-visible task handle — you cannot name,
query, or cancel a pending wait from softcode.

| | DG Scripts | REALM |
|---|---|---|
| Deferral primitive | `wait <n> s\|t` / `wait until HH:MM` → pulse-queued resume | `wait(secs, cmd)` one-shot deferral |
| Periodic behavior | `RANDOM`/`TIME` triggers on the DG pulse; `while`+`wait 1` loops | `on_tick` behaviors / `script_ticker` |
| Scheduler | single pulse-bucketed queue, script-internal only | asyncio + global heartbeat |
| Cancel / introspect a pending timer | — (no handle) | — (also no user-visible task handle; see MOO `fork`/`kill_task` note) |

REALM and DG land in the **same place**: both have one-shot deferral and
periodic ticks, neither exposes cancellable named task handles to the builder.
The one DG nicety: **`wait until <game-clock time>`** (resume at 14:30 mud
time) is a clock-relative deferral REALM's `wait(secs)` doesn't express
directly.

---

## Capabilities REALM lacks (the GAP list)

Every DG trigger with **no** REALM `ON_<EVENT>` today, i.e. game moments a
mature Diku engine exposes that REALM currently cannot hook:

1. **`WEAR` / `REMOVE`** — the equip/unequip lifecycle. High value: cursed
   gear, set bonuses, "you can't remove this," attribute mods on equip. REALM
   has `GET`/`DROP`/`GIVE` but nothing fires when an item is *worn*.
2. **`LOAD`** (mob **and** obj) — the spawn/instantiation hook. Decorate a
   freshly spawned NPC, roll random inventory, set per-instance state at
   birth. Currently REALM has no "just came into existence" event.
3. **`HITPRCNT`** — fire when a fighter drops below N% HP. The canonical
   "flee / call for help / enrage at low health" hook; directly relevant to
   GURPS combat AI. No REALM equivalent.
4. **`RESET`** — the zone-repop hook. Re-lock doors, reset puzzles, restock
   shops when the area regenerates. REALM has no zone-reset event.
5. **`FIGHT`** — a per-combat-round pulse on a combatant. Enables round-by-
   round tactical AI. REALM's `on_tick` is not combat-scoped.
6. **`CAST`** (mob/obj/room) — fire when targeted by a spell/ability. The
   natural home for GURPS resistance rolls, ward reactions, "reflects magic."
7. **`DOOR`** — fire when an exit is opened/closed/locked/unlocked. Trap
   doors, alarms, one-way seals.
8. **`TIMER`** — a per-object countdown that fires on expiry (self-destruct,
   decay, fuse). REALM's `wait()` is script-scoped, not an object property.
9. **`MEMORY` + `mremember`/`mhunt`** — NPC remembers an actor and reacts on
   next sighting; pursuit across rooms. No REALM analog.
10. **`CONSUME`** — eat/drink/quaff distinction (partly served by `ON_USE`).
11. **`BRIBE`** — give-coins-to-NPC with a minimum-amount gate (partly served
    by `ON_PAYMENT`, which is buy-shaped).
12. **`LOGIN`** (room-scoped) — REALM's `ON_CONNECT` is global, not "logged
    in *in this room*."

Plus one non-event capability: **`context`** (numeric namespacing of a
trigger's persistent globals) and **`mtransform`** (hot-swap a live entity's
prototype).

---

## Different philosophy

- **Typed trigger taxonomy vs open event stream.** DG's ~40 hooks are the
  engine's exhaustive, hand-wired vocabulary of "things that can happen";
  their strength is that the list is *curated and complete for a Diku* — a
  builder learns it once. REALM fires arbitrary `Action` types and matches by
  name, so its list is shorter today but grows without touching the core. The
  gap list above is therefore not an architecture problem for REALM — it's a
  **backlog of `act()` call sites to add**, each a few lines, not a language
  extension.

- **Reaction-with-return-value vs two-pass check/react.** A DG trigger both
  reacts and vetoes (`return 0` blocks the get/drop/enter). REALM separates
  the veto (`on_check` → `block`/`modify`) from the reaction (`on_react`),
  which is why several "have" rows above are really "have, as two hooks." This
  is a genuine REALM improvement (interception is a distinct, inspectable
  pass) but costs one concept of DG's economy.

- **String substitution vs live objects.** `%actor.level%` is text splicing
  over UID strings resolved through curated C accessors — safe, uncrashable,
  read-mostly. `enactor.db.level` is a real object attribute in a sandbox —
  more powerful, but the safety comes from the sandbox denylist, not from the
  field vocabulary being finite. DG trades power for a guarantee; REALM trades
  the guarantee for Python.

- **`narg`: one typed parameter per trigger.** DG bakes a single numeric knob
  into every trigger (chance %, HP threshold, coin minimum, hour). REALM
  expresses the same by writing the condition in Python inside the handler.
  DG's is terser for the common case; REALM's is unbounded.

---

## Steal-list (ranked)

1. **Add the missing equip/lifecycle event hooks** — `ON_WEAR` / `ON_REMOVE`
   first (equip lifecycle is the single most-requested Diku hook REALM
   lacks), then `ON_LOAD`/`ON_SPAWN` (per-instance init at birth). Each is one
   `act(obj, …, type='on_wear')` call site plus a doc line. Highest
   value-to-effort ratio on this list.
2. **Combat-state hooks: `ON_HITPRCNT` and `ON_FIGHT`.** An HP-threshold event
   ("below 25%") and a per-round combat pulse. Directly enable GURPS AI —
   flee, call reinforcements, enrage — which REALM currently cannot express
   without a polling tick. Pair the threshold with DG's `narg` idea: let the
   trigger carry the percentage.
3. **`ON_RESET` (zone repop) and `ON_TIMER` (per-object countdown).** The two
   "environmental clock" hooks: area regeneration and object self-expiry.
   `ON_TIMER` in particular gives objects a decay/fuse primitive that
   `wait()` can't (it dies with the script).
4. **`ON_CAST` / ability-targeted event.** When an object/mob is the target of
   an ability, fire an event carrying the ability id — the natural seam for
   GURPS resistance rolls and ward reactions. Complements the existing
   `on_check` interception.
5. **`ON_DOOR` (exit manipulation) and eat/drink specialization of `ON_USE`.**
   Lower priority but cheap; traps, alarms, and consumable distinctions.
6. **Per-trigger `narg`-style typed parameter as a convention.** Adopt DG's
   "one numeric knob" ergonomic for probability/threshold events — e.g.
   `&ON_HITPRCNT.threshold = 25` or a leading `chance%:` on the action — so
   the common gated-trigger case doesn't need a hand-written Python guard.
7. **A curated read-only field-path vocabulary for text** (`%actor.field%`
   ergonomics). REALM already has the mechanism (`[[...]]` inline Python); the
   steal is the *terse, safe path syntax* for builders who shouldn't write
   Python — a whitelisted `{actor.name}`/`{actor.hp}` surface that resolves
   through curated accessors, exactly like DG's dotted fields.
8. **`context`-style namespacing** for persistent trigger state reused across
   many objects — minor, served today by attribute-key prefixing but worth a
   convention.
9. **NPC `memory` + `hunt`/`follow`** — a remember-and-pursue subsystem
   (`ON_MEMORY` + actuators). A whole feature, not a hook; parked but noted.

---

*Status: reference comparison, no decisions taken. The actionable output is
the GAP list — `WEAR`/`REMOVE`, `LOAD`/spawn, `HITPRCNT`/`FIGHT`, `RESET`,
`TIMER`, `CAST`, `DOOR` — each a new `act()` call site on REALM's existing
event stream, not a language change. See also
[PennMUSH Inventory](pennmush-inventory.md) and
[LambdaMOO Comparison](moo-comparison.md).*
