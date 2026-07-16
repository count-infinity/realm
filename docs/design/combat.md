# Combat System Design: Beats, Queues, and Strategies

**Status:** SHIPPED (2026-07-03) — all five phases delivered and
verified (642 unit tests incl. 24 combat; 24-check live telnet drive:
PvP beat duel, PvE kill + corpse, heist failure path). Open Questions
were resolved to the
recommended options: (1) slowest participant's beat wins, clamped to
server config; (2) per-player `combat_default` = attack | defend |
repeat | nothing, defaulting to repeat-last; (3) PCs fall unconscious
in place and are revivable by first aid, mobs die into lootable
corpses; (4) Attack/Defend/Flee/Wait in v1, GURPS maneuvers phase 3;
(5) initiative fixed per encounter; (6) lock-style safe expressions for
strategies; (7) leaving the room mid-combat requires `flee`, other
commands stay free.
**Date:** 2026-07-03

## Vision

Real-time-with-consent combat. A fight advances on a **combat beat** —
a configurable interval (4s to 2m) between action resolutions. During
each beat window, every participant **queues** their next action
(`attack guard`, `all-out defense`, `flee north`); the queued action is
freely **changeable until the beat fires**, at which point all queued
actions resolve in initiative order. Players who want tactical,
almost-turn-based play set long beats; players who want visceral
hack-and-slash set short ones.

Later, **strategies** make selection smart: an ordered list of
`condition → action` rules ("if my HP is below 5, flee") that picks the
action automatically when the player hasn't queued one — the same
mechanism drives NPC combat AI, so player automation and monster
brains are one system.

## What already exists (build on, don't rebuild)

| Piece | Where | State |
|---|---|---|
| Per-swing resolution | `realm/combat/system.py` `CombatSystem.attack()` | Working: propagated `combat:on_attack` (blockable) → ruleset attack roll → active defense → damage (blockable) → death propagation → message dict |
| Swappable rulesets | `realm/combat/ruleset.py` ABC + `rulesets/gurps.py`, `rulesets/d20.py` | Working; GURPS 3d6 attack/dodge-parry/damage-DR/initiative |
| Combatant wrapper | `realm/combat/combatant.py` | Works (stats/HP via `db.*`); has a module-global cache to fix |
| Combat NPC behaviors | `realm/combat/behaviors.py` | Skeletons with stubbed movement/speech — to be finished against the new encounter layer |
| Server heartbeat | `GameServer._tick_loop` | Working; drives behaviors + flushes sessions |
| Skill checks/contests | `realm/core/checks.py` | Working; pluggable resolver |
| Safe expressions | `realm/permissions/locks.py` evaluator | Working; the strategy-condition language candidate |

**The genericity question, answered concretely.** The Java-style
swappable interface already exists and works: `Ruleset` owns *how a
swing resolves* (attack roll, defense, damage, defeat). The new
encounter layer is deliberately **ruleset-agnostic** — it owns time
(beats), membership, queues, and delivery, and knows nothing about
dice. The one place vocabulary leaks between them is *what actions a
combatant may queue* (GURPS has All-Out Attack and Feint; D20 has its
own verbs). We capture that as **data, not methods**: each ruleset
publishes a `maneuvers()` list of descriptors, and the encounter engine
schedules whatever it's given. Two clean seams — `Ruleset.maneuvers()`
and `Ruleset.resolve_special_maneuver(...)` — rather than an
explosion of interacting interface methods.

```
Commands (attack/queue/flee/combat) ─┐
Strategies (condition → action)      ├─> CombatEncounter (beats, queues, membership)
NPC behaviors (join/select)          ┘         │ per beat, initiative order
                                               ▼
                                     Ruleset.resolve(maneuver)  ← GURPS | D20 | yours
                                               │
                                               ▼
                                     propagation engine (on_attack/on_damage/on_death,
                                     blockable, observable by behaviors & softcode)
```

## Architecture

### 1. `realm/combat/maneuver.py` — the action vocabulary

```python
@dataclass(frozen=True)
class Maneuver:
    key: str                  # "attack", "all_out_attack", "defend", "flee"
    name: str                 # display
    aliases: tuple[str, ...]
    needs_target: bool        # target resolution at queue time, revalidated at fire
    cost: int = 1             # beats consumed
    help_text: str = ""
    # resolution is ruleset-side, dispatched on key
```

`QueuedAction` = `(maneuver_key, target_id | None, args: str)` — stored
on the participant entry in the encounter (runtime), mirrored to
`obj.db.combat_queued` for inspectability (`@examine` shows what an NPC
is winding up — and a `telegraph` option can show players too).

### 2. `Ruleset` additions (backward compatible)

- `maneuvers() -> list[Maneuver]` — base provides `attack`, `defend`,
  `flee`, `wait` plus the ranged vocabulary (`shoot`, `aim`, `close`,
  `withdraw`, `cover` — a two-band range model: engaged vs at-range,
  with cover and accumulating aim bonuses); GURPS overrides to add
  `all_out_attack`, `all_out_defense`, `feint`.
- `resolve_special_maneuver(combat_system, encounter, actor, action,
  target)` — base maneuvers (attack, defend, flee, and the ranged set)
  resolve in the encounter engine itself; rulesets implement this hook
  only for their own vocabulary (GURPS: AoA/AoD/Feint).
- Everything already implemented (roll_attack/defense/damage) is
  untouched — the encounter engine composes it.

### 3. `realm/combat/encounter.py` — the beat engine (new, the core)

```python
class CombatEncounter:
    id, room, participants: dict[obj_id -> Participant]
    beat_seconds: float        # clamped to server [min, max] config
    round_number: int
    _task: asyncio.Task        # own timer: sleep(beat) → fire → repeat

class Participant:
    obj, queued: QueuedAction | None, last_action, joined_round
```

Per beat:
1. Snapshot queues (further changes apply to the *next* beat).
2. Initiative order via `ruleset.roll_initiative` (or stable per-fight
   order — see Open Questions).
3. For each living participant, determine the action:
   queued → else strategy match → else **default policy** (see Open
   Questions), then it resolves — base maneuvers in the engine,
   specials via `ruleset.resolve_special_maneuver(...)`.
4. Deliver messages (attacker/defender/others through per-looker
   perception — an unseen attacker reads as "Someone").
5. Prune: dead/fled/disconnected; end the encounter when one side
   remains; announce the round summary + "next beat in Ns" prompt.

`CombatManager` (on `GameServer`, like `script_engine`): creates/joins/
merges encounters (one per room; a second fight in the same room joins
the existing encounter), cancels tasks on stop. Encounters are
**runtime-only** (not persisted); on reboot fights simply end (HP et
al. persist normally via the dirty sweep).

Beat pacing: each participant has `db.combat_beat` (a `pace` command
sets it; server config `COMBAT_BEAT_MIN/MAX/DEFAULT` clamps). The
*encounter* beat derives from participants' preferences — resolution
rule pending (Open Question 1).

### 4. Commands (`realm/commands/builtin/combat.py`)

- `attack <target>` — starts/joins the room's encounter, queues an
  attack. Hostile action: propagates through the normal gate first
  (locks/behaviors can veto starting a fight — pacifist rooms).
- `queue <maneuver> [target]` (maneuver aliases like `aoa`, `fire` work
  inside `queue`; only `defend` is a bare command) — sets/replaces the
  queued action; confirmation shows what will fire and when.
- `flee [exit]` — queues a disengage attempt (resolved on the beat as
  a `flee` skill check — solo, not opposed; auto-moves through the
  exit on success). Deferred exits (wilderness cell edges) are valid
  flee routes — the destination resolves during the move; instance
  portals (private per-walker destinations) are excluded from flee,
  since fleeing into a freshly imported private dungeon is an
  unpursuable teleport. An exit that refuses the move (lock, skill
  gate) drags you back into the fight.
- `combat` — status: participants, HP bars, your queued action,
  seconds to next beat.
- `pace <seconds>` — set personal beat preference.
- `combatdefault <attack|defend|repeat|nothing>`, `wimpy <pct>|off`,
  `defend` (bare shortcut), `wield`/`unwield`, `firstaid` — shipped. An
  explicit `stop`/`yield` command did NOT ship; you leave combat via
  `flee`, defeat, or the fight ending.

### 5. Strategies (the future-proofed seam, minimal v1)

`db.combat_strategy = [["me.hp < 5", "flee"], ["target.hp < 3", "all_out_attack"], ["", "attack"]]`

- Conditions are **lock-style safe expressions** (reusing the existing
  validated evaluator; namespace: `me`, `target`, `round`, plus safe
  builtins). Empty condition = always.
- Evaluated top-down at beat time *only when nothing is queued*
  (manual queue always wins).
- **NPCs use exactly this**: `AggressiveBehavior`/guard escalation just
  writes a strategy list and joins the encounter. One selection engine
  for players, automation, and AI.
- v1 ships the evaluator + `strategy` builder command may be deferred
  (players can `@set` it; a friendly editor command later).

### 6. Integration & aftermath

- **Watchful escalation**: `on_spot`, a guard with `hostile=True` param
  (or alert ≥ N) joins/starts the encounter targeting the intruder —
  this is what makes stealth stakes real.
- **Death**: `combat:on_death` already propagates. Consequence policy
  pending (Open Question 3). NPC death v1: corpse container (`corpse of
  X`, holds inventory, decays after N ticks via a `DecayBehavior`).
- **First aid**: `firstaid [target|me]` — skill check, heals margin-based
  amount, usable out of combat only (Story 3/5 requirement).
- **Softcode**: ON_ATTACK/ON_DAMAGE/ON_DEATH triggers already fire via
  the script-engine observer; strategies + `skill_check` close the loop.

### 7. Cleanups executed alongside (review debt in touched files)

- Replace `combatant._combatant_cache` module global with per-encounter
  wrapping — NOT done; the module-global cache in `combatant.py`
  remains the live path.
- Finish/de-stub `combat/behaviors.py` against the encounter API
  (flee/wander stubs become real moves via `move_through_exit`).
- Drop the always-true `hasattr(ruleset, 'roll_defense')` guard.

## Reference findings: solar_frontiers GURPS combat (analyzed 2026-07-03)

The Evennia predecessor already implemented this design's core — a
declaration window with initiative-ordered burst resolution, timed out
by the **slowest PC's `db.combat_speed`** (2–120s), with per-player
`combatdefault` (attack/defend/nothing), `wimpy` (auto-flee below % HP)
and `autowield`. That validates the beat/queue model; what follows are
the steals and anti-lessons that adjust this plan.

**Adopted into this design:**

1. **Hostile-tag auto-combat with "already_acted" credit.** Any action
   tagged `hostile` initiates the encounter, and the initiating action
   counts as the initiator's first-round action (casting the fireball
   IS your turn). REALM combat actions already carry `tags={"hostile"}`
   — the CombatManager observes propagation for them (same observer
   seam the script engine uses). → Phase 2.
2. **All combat messaging through propagation.** solar_frontiers'
   documented #1 regret: combat narration hard-coded `msg_contents`,
   bypassing the message pass, so behaviors/softcode could never
   intercept it and attack rolls had to be retrofitted into
   propagation. REALM will attach attacker/defender/others lines to
   the propagated combat actions (`success_only` staging) so the
   normal delivery path — perception masking included — applies.
   `Ruleset.format_attack_message` feeds templates, not sends.
3. **Per-player pacing knobs as plain db attributes** (softcode-
   editable): `combat_beat`, `combat_default` (attack | defend |
   repeat | nothing), and **wimpy implemented as sugar** — the `wimpy
   30` command just writes the strategy rule
   `["me.hp_percent < 30", "flee"]`, proving strategies subsume the
   special cases.
4. **Source-tracked modifiers with visible roll math.** Their
   `collect_modifiers` ownership table and "rolled 9 vs 13 (-2
   darkness) — HIT!" transparency carry over: modifier collection
   stays generic (tags/conditions/equipment/room), only the math is
   per-ruleset.
5. **Defeat asymmetry**: PCs fall unconscious in place and wait for
   healing; mobs die into lootable corpses + CP-style awards. (This
   updates the Q3 recommendation below.)

**Anti-lessons (what their Evennia implementation fought):**

- Per-fight 1-second polling scripts just to implement a timeout —
  REALM encounters own a real async timer instead.
- Non-persistent script state needing defensive re-init and `delay(0)`
  deferred deletion — REALM encounters are honest runtime objects with
  a manager lifecycle.
- Replace-merged cmdsets that had to re-add look/help and grew an
  `abort` escape hatch for stuck fights — REALM keeps the normal
  dispatcher; combat adds commands, never replaces the set. An
  explicit `yield`/end path is designed in, not patched in.
- Dual condition clocks (round-ticks in combat, delay-ticks outside)
  caused double-tick bugs. REALM runs one real-time heartbeat that *mints*
  beats (the encounter's round in combat, the ambient beat outside), and a
  single `in_combat` guard (`beats.ambient_beat_targets`) ensures a
  combatant's effects advance from exactly one source — its encounter — never
  also from the ambient driver. One clock, one owner per object. See
  [Time, Ticks & Beats](time-and-beats.md).
- Data/rules disconnects (weapon YAML parsed but ignored; hit-location
  plumbing with no producer) — anything Phase 1 doesn't consume, it
  doesn't parse.

Flavor worth keeping for a later phase: the forced-Ready-on-entry rule
with Fast-Draw to bypass — cheap depth that makes weapon readiness
matter.

## Reference findings: CoffeeMud combat loop (analyzed 2026-07-03)

CoffeeMud has no separate combat loop — the round IS the global tick,
paced by a per-actor action-point float (`actions += speed` per tick,
attacks cost 1.0, fractions carry) plus a wall-clock gate
(`now >= last + cost/speed × tick`). Its per-actor command queue
(`MUDCmdProcessor`) is "changeable until it fires" via
cancel-on-enqueue and a priority-prepend for reflexive actions.

**Adopted into this design:**

1. **`Maneuver.cost` field (in beats).** CoffeeMud's action economy
   distilled to the beat model: v1 maneuvers all cost 1 beat, but the
   schema supports multi-beat wind-ups (Aim persisting across beats,
   heavy attacks costing 2) and — later — speed/haste granting extra
   resolutions. We do NOT adopt the full action-point float in v1; the
   user's model is a decision window, not an economy. Noted as the
   phase-3+ path if attacks-per-beat differentiation is wanted.
2. **Override-flagged strategy rules (the wimpy fix).** CoffeeMud's
   priority-prepend shows reflexive actions must preempt the queue.
   Plain strategy rules fire only when nothing is queued (manual
   intent wins), but a rule flagged with `!` ("!me.hp_percent < 30" →
   flee) is evaluated even over a manual queue — `wimpy 30` writes an
   override rule. Safety reflexes beat declared intent.
3. **Defender-side resolution and auto-retaliation.** CoffeeMud splits
   post_attack (attacker announces) from handleBeingAssaulted
   (defender rolls to-hit, applies damage, and sets its own victim).
   Mirrored: the attacked party auto-joins the encounter targeting the
   attacker; retaliation logic lives on the defender.
4. **Late-bound damage token.** Messages carry a `{damage}` placeholder
   rendered only after the propagation check pass has let armor/wards/
   resistances mutate the amount — never bake the number in early.
5. **Flee fallback details**: bare `flee` picks a random open exit
   ("up" only as a last resort); a failed flee costs the beat.

Not adopted: CoffeeMud's probabilistic NPC skill selector
(`CombatAbilities` modes) — strategy rules are strictly more
expressive; a `chance(25)` condition function gives back the
probabilistic flavor inside the strategy system if wanted.

## Delivery phases (each lands green: unit tests + live telnet drive)

1. **Encounter engine + attack/flee/combat/pace commands**, base
   maneuvers only, default-action policy, GURPS ruleset resolving —
   *the playable core.*
2. **Guard escalation + death/corpse/first-aid** — Watchful → combat;
   Story 3 and Story 5's opener playable end to end.
3. **GURPS maneuver set + defend modifiers** — AoA/AoD/Aim/Feint as
   data-driven maneuvers proving the vocabulary seam (D20 keeps base
   verbs, proving genericity).
4. **Strategies** — expression evaluator, NPC selection via strategy
   lists, player `@set`-able strategies.
5. **Heist integration** — Nexagen guards fight back; failure path
   playthrough added to the e2e (spotted → combat → flee → re-hide).

## Open Questions (answers shape Phase 1)

1. **Whose beat wins in a shared encounter?** Options: (a) slowest
   participant's preference (everyone gets time to think — my
   recommendation), (b) fastest (pressure!), (c) average, (d) fixed
   per-room/zone override for arenas. NPCs express no preference.
2. **Default action when the beat fires with nothing queued and no
   strategy:** now recommended per solar_frontiers precedent: a
   per-player `combat_default` setting (attack | defend | repeat-last |
   nothing), defaulting to repeat-last. Confirm or override.
3. **Player defeat consequence, v1:** updated recommendation per
   solar_frontiers precedent: (a) unconscious in place, revivable by
   first aid/healing, mobs die into lootable corpses. (b) arcade
   respawn or (c) GURPS death spirals remain options — (c) fits
   phase 3+.
4. **GURPS depth for v1 maneuvers:** just Attack/Defend/Flee first
   (recommendation), with AoA/AoD/Aim/Feint in phase 3 — or do you
   want the full maneuver list from day one?
5. **Initiative:** re-rolled each round, or rolled once per encounter
   (GURPS RAW is a fixed Basic Speed order — recommendation: fixed
   per-encounter, cheaper and more predictable)?
6. **Strategy language:** lock-style Python expressions
   (`me.hp < 5 and target.name == 'guard'`) — consistent with locks,
   already sandboxed (recommendation) — or a softcode-ish mini-syntax?
7. **Mid-combat restrictions:** while in an encounter, should movement
   (other than flee), get/drop, etc. be blocked, penalized, or free?
   (Recommendation: leaving the room requires `flee`; everything else
   free in v1.)
