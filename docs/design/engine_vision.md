# REALM Engine Vision: the Godot of MU*s

Status: capability tracker — the living record of *what softcode can do
today* and what's left. The durable principles (the invariants every
change is judged against) live in the root **`VISION.md`**; when this doc
and VISION.md disagree, VISION.md wins.

## The thesis

REALM is a **game engine**, not a game. The way Godot obfuscates the
complexity of physics, movement, and tweening while leaving game logic
to GDScript, REALM obfuscates the complexity of a MU* — propagation,
persistence, perception, combat scheduling, movement, locks — while
leaving the *game* to softcode. Specific games (a GURPS MU*, a D20
MU*) are implementations layered on the engine, and those layers
should themselves be reachable from softcode.

**Almost all functionality available to softcode, with permissions on
softcode.** Turing-complete scripting inside the engine world is the
product; hardcoded behaviors are the fast path and the reference
implementations, not the only path.

The two-layer rule for every new feature:

1. **Hardcode** the mechanism (fast, tested, one implementation) —
   propagation observers, behaviors, managers.
2. **Expose** it to softcode — a ScriptFunction, a script command, a
   builder command, or a trigger event — gated by the authority model.

A feature that ships without its softcode surface is half-shipped;
track the other half in BACKLOG.md.

## The softcode platform today (2026-07-15)

Turing-complete: YES — sandbox scripts are restricted Python (loops,
comprehensions, function defs) under resource limits (time / calls /
recursion / output). What varies is API surface:

| Capability | Softcode surface | State |
|---|---|---|
| React (commands, speech, events) | `$cmd`, `^listen`, `ON_<EVENT>` attrs | SHIPPED |
| Time | `script_ticker` behavior → `on_tick` | SHIPPED |
| Speak | say/pose/emit/whisper, pemit/remit/oemit | SHIPPED |
| Read world | get/name/loc/owner/contents/tags/attrs | SHIPPED |
| Mutate attrs/tags | set_attr/del_attr/add_tag/remove_tag | SHIPPED (authority-gated) |
| Move self | `move <exit>` — full movement pathway | SHIPPED |
| Chain scripts | `trigger obj/attr`, `@tr`, `eval_attr()` (Penn's u() — call an attr as a function) | SHIPPED |
| Duplicate | `@clone`, spawner prototypes | SHIPPED |
| Skill system | skill_check / contest | SHIPPED |
| Create/destroy objects | create_obj / destroy_obj | SHIPPED (authority-gated) |
| Teleport objects | move_to (ward/lock-checked, tags for anti-magic) / teleport_obj (= move_to force=True, ward bypass) | SHIPPED (authority-gated) |
| Behaviors from scripts | behaviors / attach_behavior / detach_behavior | SHIPPED (authority-gated) |
| Locks from scripts | set_lock / clear_lock / test_lock | SHIPPED (authority-gated, validated) |
| Combat from scripts | damage / heal (proximity authority, death path), start_combat | SHIPPED |
| Effects sugar | apply_effect / remove_effect (proximity authority) + check_mods auto-modifiers | SHIPPED |
| Inline eval in text | [[...]] blocks in descriptions — sandbox per viewer, state via attrs, now() | SHIPPED (2026-07-05) |
| Manipulation verbs | get/take/drop/give/open/close script commands + `cmd()` | SHIPPED (shared cores in realm/core/verbs.py — commands and scripts run identical code) |
| Full dispatcher access | @force + force() — PuppetSession through the real dispatcher, controls()-gated, target's own permissions apply | SHIPPED (2026-07-05) |
| Economy | credits/adjust_credits/transfer_credits + ShopkeeperBehavior + ON_PAYMENT | SHIPPED (2026-07-05) |
| World queries | search_world(tag/attr/value/name) capped; zone_rooms/zones_of; protected attrs | SHIPPED (2026-07-07) |
| Client OOB (GMCP) | oob(target, package, data) + msg_oob; Room.Info/Char.Vitals built-in | SHIPPED (2026-07-06) |
| Scheduling beyond ticks | `wait(sec, cmd)` / `wait <sec> <cmd>` one-shots on the heartbeat | SHIPPED (in-memory, like MUSH @waits) |
| NPC disposition | disposition / adjust_disposition / reaction_roll (per-character -5..+5 bands) | SHIPPED (2026-07-04) |
| Ask player for input | prompt(target, text, callback) — response fires the named callback attr | SHIPPED (2026-07-09) |
| Instanced areas | enter_instance(player, template, mode='solo'/'shared') — private transient copies of a template area, reaped when idle; instance portals + follower routing built in | SHIPPED (2026-07-12) |
| Wilderness regions | enter_wilderness(player, region, x, y) — cells materialize on demand; cell exits are real exits with deferred destinations, so walking needs no softcode | SHIPPED (2026-07-14) |

## Permissions on softcode (the authority model)

Scripts run **as their object** (the executor), never as the enactor.
One predicate decides every mutation: `controls(actor, obj)`:

1. You control yourself.
2. You control what you own.
3. ADMIN+ controls everything.
4. BUILDER controls unowned (world-built) NON-PLAYER objects.
5. The world trusts the world: unowned non-player objects control each
   other (world NPCs poking world props — the MUSH equivalent is
   everything sharing a wizard owner).
6. PennMUSH delegation: your objects act with YOUR authority — an owned
   object controls whatever its owner controls (siblings share state; a
   builder's gadget reaches world props). Sound because only the owner
   can script the object; `@chown` HALTS scripted objects so old code
   never runs with the new owner's authority.
7. Otherwise the object's `control` lock decides.

Applied at three layers:

- **Builder commands** (@set/@desc/@tag/@lock/@behavior/@tr/...):
  caller must control the target.
- **ScriptFunctions mutations** (set_attr, add_tag, create/destroy/
  teleport, attach_behavior...): executor must control the target.
  Self-modification always works — an NPC managing its own counters
  is the normal case.
- **Trigger locks**: `use` lock gates who can fire an object's
  `$`-commands; `listen` gates whose speech its `^listen` patterns
  overhear; `command` gates who may `trigger`/@tr its named scripts.

Ownership: objects you @create/@clone are yours. World-init objects
are unowned (staff territory). `@chown` transfers.

## Known trade-off: script threads vs the event loop

Sandbox scripts run in a worker thread (so runaway scripts can't stall
the loop). Read functions are safe; mutations (set_attr, location
changes) rely on the GIL and have not bitten yet, but a busy tick loop
could observe mid-script state. Session/async work is already queued
and drained on-loop after execution (pemit/save/destroy). If this ever
bites: move mutations into the queue wholesale, or run scripts on-loop
with an instruction budget. Tracked in BACKLOG.

## Ruleset packages (the GURPS/D20 story) — GameSystem, SHIPPED 2026-07-04

`realm/systems/` is the system-package seam: a **GameSystem** (Abstract
Factory, selected by a dotted import path — `GAME_SYSTEM = "rules.GameRules"`
or `"realm.systems.GurpsSystem"` in config) bundles the
combat ruleset name, skill definitions/defaults, advancement costs
(`improve_cost`), baseline stats, and the chargen flow. Chargen is a
Template Method: the server owns the prompt→answer→advance loop
(state in `db.chargen_step`, reboot-safe, quit/reconnect handled);
systems supply `ChargenStep`s. `ChoiceStep` covers menus (GURPS
templates, D20 classes); point-buy steps later are new step classes,
no flow changes. Remaining for a full "asset-store" story: effect
vocabulary per system, softcode access to system queries, chargen
authored IN softcode, distribution/packaging for ruleset packages
(area-level @pack/@export/@import shipped 2026-07-09; system packages
still pending).
