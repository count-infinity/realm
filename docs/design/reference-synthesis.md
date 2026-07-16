# Reference Synthesis — What 11 MU*s Say REALM Is Missing

A cross-reference roll-up of every reference comparison REALM has done. The
2026-07 sweep added seven codebases across four lineages — **AresMUSH**
(modern Ruby MUSH), **LDMud** (LPMud driver/LPC), the **SMAUG/Diku family**
(SmaugFUSS, SWRFUSS, SWFOTEFUSS), **tbaMUD** (CircleMUD/DG Scripts), and
**TinyMUX** (MUSH) — joining the earlier **CoffeeMud**, **Evennia**,
**PennMUSH**, and **LambdaMOO** studies. Read this doc for the deduplicated,
ranked verdict; each row links to the full comparison.

## The headline: the thesis holds

Eleven independent lineages, and **nothing challenges REALM's core
architecture.** The opposite — the sweep keeps *converging* on it:

- **Microkernel + pluggable modules** shows up independently in LDMud
  (driver/mudlib), TinyMUX (COM modules dlopening the softcode VM itself +
  Lua), and AresMUSH (plugin modules). REALM's "abstract kernel, game as
  data/softcode" is the mainstream endpoint, not a bet.
- **The escape-hatch tier is universal** — LPMud `simul_efun`, MUX native
  modules, Penn/MUX hardcode — validating `@softcode_function`.
- The **power-vs-safety fork** is the one real philosophical divergence:
  LPMud and AresMUSH put game logic in a *full native language* (trusted
  authors, no sandbox); REALM contains by construction (`safe_eval`). Both
  camps exist in the wild; REALM's two-tier trust is a legitimate, arguably
  safer, point on the spectrum — not a naïveté.
- **Confirmed anti-patterns** (things REALM already refuses, now seen
  failing in the wild): SMAUG's 45-field `struct skill_type`
  (mega-descriptor, invariant 6), AresMUSH's `class Character` reopening
  (attribute smearing that tags+behaviors avoids), SMAUG's `dlsym`
  bind-behavior-to-C, THAC0-as-engine. Seeing these validates the
  composition model.

So this is a gap-list at the **edges**, not a course correction.

## Tier 1 — genuine kernel gaps, high value, low effort (do these)

| Gap | What | Sources | Why it's cheap |
|---|---|---|---|
| **Missing event hooks** | ✅ **SHIPPED 2026-07-15** (`realm/core/events.py`, `tests/test_event_hooks.py`): `REMOVE`/`WIELD`/`UNWIELD` + `LOCK`/`UNLOCK` (gated), `RECEIVE`, `LOAD`, `HITPRCNT`, `CAST` (a `cast()` primitive + `event:on_cast`), `EXPIRE` (object self-expiry via `reap_expired`). Reconciled `STANDARD_EVENTS`. `WEAR`/`GET`/`DROP`/`OPEN`/`CLOSE`/`USE`/`PUT` already fired — the review overstated the gap. Remaining: `MEMORY` (NPC re-sight), `FIGHT` (per-round). | tbaMUD (DG Scripts) | REALM's event stream is **open** — each was a new `fire_event()` **call site, not a language change**, exactly as predicted. |
| **Cancelable task handles** | ✅ **SHIPPED 2026-07-15** — `wait(secs, cmd)` returns an opaque handle id; `cancel_wait(id)` calls a pending wait off before it fires (a defuse), gated so only a controller of the scheduling object may cancel. `realm/scripting/engine.py` (id-keyed `_waits`), `tests/test_wait_cancel.py`. | LDMud (`call_out`/`remove_call_out`), MOO (`fork`/`kill_task`), TinyMUX (`@halt/pid`) | Delivered the returned-handle + cancel pair. A `waits()` *list* (queued_tasks/@ps) is the optional follow-up; persistent (reboot-surviving) waits remain a separate backlog item. |
| **Object self-expiry (`TIMER`)** | ✅ **SHIPPED 2026-07-15** — a tick-checked `db.expires_at` fires `event:on_expire` via `reap_expired` (`realm/core/events.py`); DecayBehavior's `db.decay_left` countdown already covered physical rot | tbaMUD (`OTRIG_TIMER`), SMAUG (`mpsleep`) | reused the reaper pattern already built for ephemerals. |

## Tier 2 — kernel gaps, real but bigger or opportunistic

| Gap | What | Sources |
|---|---|---|
| **Area-reset / repop primitive** | ✅ **SHIPPED 2026-07-15** — `ZoneResetBehavior` **on the zone master** (composition layer, not a kernel sweep — repop belongs on the owner object, per `ldmud-comparison.md`). Attach `@behavior <master> = zone_reset`; when due + **empty** it clears its prior spawns and reloads `reset_spec` fresh (SMAUG clear-then-repop — no accumulation, removed entries purged) and fires `ON_RESET`. Shares one `spawn_tracked` core with `SpawnerBehavior`. `realm/behaviors/zone_reset.py`, `tests/test_zone_reset.py`. | SMAUG (`area_update`/`reset_area`), tbaMUD (`RESET` trigger) | The presence gate ("only reset while nobody's watching") is the point vs per-room spawners. |
| **Counting semaphore / cross-task rendezvous** | one task blocks until N others signal (`@wait obj/attr` + `@notify`) | TinyMUX — steal the *idea* as a Pythonic event/condition object, not the attribute-counter |
| **`reset()` / `clean_up()` lifecycle pair** | periodic self-repop + return-value-driven idle self-GC | LDMud — `clean_up` overlaps the ephemeral reaper; `reset` overlaps area-reset above |
| **Granular capability vocabulary** | fine-grained powers (`pass_locks`, `tel_anywhere`, `see_queue`…) beneath the role tiers | TinyMUX (~35 powers), LDMud (uid/euid) — only if GUEST/PLAYER/BUILDER/ADMIN/GOD proves too coarse |

## Tier 3 — small reusable mechanisms (mine, don't port)

- **Bipolar self-alignment axis** — a self-morality track (light↔dark) that
  drifts toward a declared allegiance and decays off-type skills; distinct
  from REALM's *per-observer* disposition (which is standing, not morality).
  Generalizes to law/chaos, honor/corruption. *(SWFOTE)*
- **Regenerating capped resource pool + tick driver** — a named "mana/force
  pool" primitive over raw attrs. *(SWFOTE, CoffeeMud)*
- **Ability-prerequisite predicate in the resolver** — rank/skill gates on
  a power, enforced where resolution happens. *(SWFOTE)*
- **Native pathfinding `route()`** — server-side BFS over navigable rooms
  for NPC autopilot; a natural `@softcode_function` binding. *(TinyMUX)*
- **`%actor.field%` dotted-field variable ergonomics** — DG's live
  field-access is nicer than string juggling; REALM already has real Python
  field access, but the *terse trigger sugar* is worth a look. *(tbaMUD)*

## The reserved spatial primitive — now concretely specced

SWR ([swr-space-comparison.md](swr-space-comparison.md)) de-risks the one
big reserved item on the roadmap. A ship runs a **room graph + a thin
coordinate sidecar simultaneously**: interior rooms (never move) plus ~9
floats (pos/heading/jump-target) that exist only while flying, driven by one
slow **integrate-and-threshold** ticker — no forces, no real collision.
Verdict: a full **discrete** space game (systems = rooms, jumps = exits,
docking = exit traversal, scalar shield/hull combat) is **softcode-buildable
today**; only continuous intra-system range/heading/homing needs the sidecar.
**Action:** design the *dual-identity ship* and the *two-world dock object*
(a room vnum that is also a coordinate point) up front, so a discrete game
ships now and continuous flight bolts on later without reworking interiors.

## Architecture lessons (guidance, not features)

- **API-first: business logic is a module function both a thin telnet
  adapter and a thin web adapter call** (`Scenes.emit_pose`). The single
  most stealable *discipline* for REALM's OOB/WebSocket surface. *(AresMUSH)*
- **`prompt()` is validated** — MUX's `@program` and REALM's `prompt()`
  solve the same problem; REALM's native-tier coroutine prompt
  (`session.prompt`) preserves scope automatically, while the softcode-tier
  `prompt()` chains via callback attributes, `@program`-style.
  No change needed; confidence gained. *(TinyMUX)*
- **Path-rewriting security callback** — LDMud's master object returns a
  *rewritten path* from `valid_read`/`valid_write`, not a bool; an idea for
  REALM's pack/worldio file access. *(LDMud)*

## Game content → packs (NOT the kernel)

Deliberately **not** kernel work — REALM would express each as a content
pack + softcode: clans/councils/deities/favor/houses/corpse-decay (SMAUG),
the Force catalog & lore (SWFOTE), FS3 combat (AresMUSH), starship/planet
genre content (SWR), THAC0/level tables (SMAUG). Mine the *field lists and
formulas* (the `affect_data` timed-modifier shape, favor-delta tables, decay
staging); never port the C.

## Whole subsystems REALM lacks (game-layer, but coherent)

A recurring theme: the **community/social suite** — scenes / RP pose-logging,
jobs/tickets, BBS, mail, role-gated channels (AresMUSH; MUX comsys/mail;
Penn `@mail`). Game-layer, not kernel, but substantial and cohesive. If
REALM ever wants to court the MUSH/RP audience, this is one coherent
"social pack" worth scoping as its own effort. Also recurring:
**JSON/SQL-from-softcode** (Penn/MUX) and **external-service bridges**
(Discord) — already flagged in the Penn survey.

## Index of comparisons

| Reference | Lineage | Doc | Sharpest takeaway |
|---|---|---|---|
| CoffeeMud | Java OO | (in-repo prior work) | flag-mask events → REALM's action-tags |
| Evennia | Python/Django | `moo-comparison.md` refs | `move_to` hook chain; pooled rooms |
| PennMUSH | MUSH | `pennmush-inventory.md` | `@afail`→`on_fail`; 531 fns (½ free from Python) |
| LambdaMOO | MOO | `moo-comparison.md` | WAIFs, ERR values, task handles, verb-args grammar |
| **AresMUSH** | modern Ruby | `aresmush-comparison.md` | API-first module functions; social suite |
| **LDMud** | LPMud/LPC | `ldmud-comparison.md` | power-vs-safety fork; `call_out` task handles; master object |
| **SmaugFUSS** | Diku/SMAUG | `smaug-comparison.md` | area-reset primitive; mega-descriptor anti-pattern |
| **SWRFUSS** | SMAUG/space | `swr-space-comparison.md` | dual-identity ship; coordinate sidecar spec |
| **SWFOTEFUSS** | SMAUG/SW | `swfote-comparison.md` | self-alignment axis; resource-pool; prereq graph |
| **tbaMUD** | Circle/DG | `tbamud-comparison.md` | the missing event-hook checklist (Tier 1) |
| **TinyMUX** | MUSH | `tinymux-comparison.md` | semaphores; `route()`; module architecture |

## Recommended next actions

1. ✅ **Add the Tier-1 event hooks** — shipped 2026-07-15 (see Tier 1);
   each was one `fire_event()` call site with its own `<domain>:on_<event>`
   action_type, as predicted. `MEMORY` and per-round `FIGHT` remain. The
   paired `TIMER`/`ON_EXPIRE` object-expiry hook shipped alongside.
2. **Give `wait()` cancelable handles** — three lineages asked for it.
3. Keep **continuous space** on the roadmap with SWR's dual-identity-ship
   design as the concrete plan (wilderness has since shipped —
   `realm/core/wilderness.py`; discrete space rides on it).
4. Bank the Tier-2/3 mechanisms (alignment axis, resource pool, area-reset,
   semaphores) as pack/kernel candidates; none are urgent.

*Status: reference synthesis, no decisions taken. The individual comparison
docs hold the citations; this is the map.*
