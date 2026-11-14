# Changelog

## 0.2.0 — the kernel plan

The engine was split into a small kernel and features
(`KERNEL_PLAN.md`, steps 1 to 9). A game written against 0.1.0 needs the
changes below; the [Public API](docs/reference/public-api.md) lists the
names that will not move again without an entry here.

### What did not change

- **Saved worlds.** The database format, object ids, attribute names
  (`hp` and `max_hp` included), tags and behavior ids are as they were. A
  0.1.0 database loads as is.
- **Action type strings** (`combat:on_damage`, `item:on_get`,
  `event:on_hitprcnt`, ...) and the `ON_<EVENT>` hook names.
- **Softcode function names and arguments.** Functions were only added
  (the pool functions).
- **Content packs and area files** (worldio JSON), and `@pack`,
  `@import`, `realm pack`, `realm export` / `realm import`.

### Configuration

- `GAME_SYSTEM` paths: `realm.systems.GurpsSystem` is now
  `realm.games.gurps.system.GurpsSystem`, and likewise
  `realm.games.d20.system.D20System` and
  `realm.games.merc.system.MercSystem`. A path to your own `rules.py`
  (`"rules.GameRules"`) is unchanged.
- The `register_commands` and `register_protocols` config callbacks are
  gone. Declare commands and protocols on your game's feature in `game.py`
  (`feature.command(...)`, `feature.protocol(...)`) and list it:
  `FEATURES = [*CLASSIC, "game"]`. `init_world`, `on_start` and `on_stop`
  remain.
- `FEATURES` lists the features a game is made of (default: every
  built-in, `realm.CLASSIC`).
- New keys: `DAMAGE_POOL` (default `"hp"`) and the keys features declare
  (`realm features` lists them; `docs/reference/config.md`).
- Python 3.12 or newer.

### Module moves

Import from the public homes (`from realm import Feature, GameObject`,
`from realm.std.rules import GameSystem`); the modules behind them may
move again. The moves, by old path under `realm/`:

| Old | New |
|---|---|
| `systems/gurps.py`, `d20.py`, `merc.py` | `games/<name>/system.py` |
| `combat/rulesets/<name>.py` | `games/<name>/ruleset.py` (registered by `feature.ruleset`) |
| `systems/base.py` | `std/rules/system.py` |
| `systems/definitions.py` | `std/rules/definitions.py` |
| `core/checks.py` | `std/rules/checks.py` |
| `systems/abilities.py`, `systems/spells.py` | `std/abilities/abilities.py`, `spells.py` |
| `systems/crime.py` | `std/crime/crime.py` |
| `combat/*.py` (system, ruleset, encounter, manager, combatant, behaviors, strategy, maneuver, damage) | `std/combat/<same name>.py` |
| `core/instances.py`, `core/wilderness.py` | `std/instances/instances.py`, `std/wilderness/wilderness.py` |
| `core/economy.py` | `std/economy/credits.py` |
| `core/disposition.py`, `core/party.py` | `std/social/disposition.py`, `party.py` |
| `core/describe.py`, `core/render.py` | `std/look/describe.py`, `render.py` |
| `core/pairing.py` | `std/building/pairing.py` |
| `behaviors/npc.py`, `decay.py` | `std/npc/behaviors.py`, `decay.py` |
| `behaviors/spawner.py`, `zone_reset.py` | `std/spawning/spawner.py`, `zone_reset.py` |
| `behaviors/shop.py` | `std/economy/shop.py` |
| `behaviors/caster.py` | `std/abilities/caster.py` |
| `behaviors/effects.py` | `std/effects/behaviors.py` |
| `behaviors/scripted.py`, `ticker.py` | `scripting/scripted_behavior.py`, `scripting/ticker.py` |
| `commands/builtin/<x>.py` | `std/<feature>/commands.py` (`combat`, `talk`, `movement`, `look`, `items`, `basics`, `social`, `economy`, `abilities`; `points`/`improve` in `std/rules`, `hide`/`search`/`pick` in `std/stealth`) |
| `commands/olc/<x>.py` | `std/building/<x>.py` |
| `core/verbs.py` | `std/talk/verbs.py`, `std/items/verbs.py` |
| `core/perception.py` (stealth) | `std/stealth/stealth.py` |
| `core/action_types.py` (feature members) | `std/<feature>/actions.py` (`CombatAction`, `ItemAction`, `TalkAction`, ...) |
| `server/game.py` (login, chargen, who, welcome) | the `accounts` feature, `std/accounts/` |
| `server/dispatcher.py`, `persistence/repository.py`, `config/defaults.py` | deleted |
| `examples/` (repository root) | `realm/examples/` (`realm init --template` works from a wheel) |
| `scripts/rom_import.py`, `rom_import_batch.py` | `realm import-rom` (`realm/tools/rom_import.py`) |

### Removed setters

The module-global setters (`set_game_system`, `set_combat_manager`,
`set_check_resolver`, `get_engine`, `reset_engine`, the sigil setters and
the rest) are gone. Engine code reads the running world:
`get_world().rules`, `.store`, `.engine`, `.scripts`,
`.services["combat"]`, `.services["checks"]`, and `setting("KEY")` for
configuration. Tests take a `Simulator` or the `world` fixtures
(`pytest_plugins = ["realm.testing.fixtures"]`).

### Behavior changes

- **`ON_HITPRCNT`** fires when an object's vital pool falls through its
  `hitprcnt` from any source (poison, traps, softcode `damage()`, spells),
  not only from a swing, and after the hit message rather than before it.
  An up pool (a harm clock) counts what is left below its max.
- **Death is an observer.** A spent vital pool runs the death path once,
  whatever spent it; damage to something already down no longer kills it
  again. What death does to the body is `obj.db.when_spent`:
  `unconscious` (a player's default), `corpse` (anything else's),
  `destroy` or `none`.
- **Damage stops at a pool's floor** (0) on every path; softcode
  `damage()`, damage over time and the Merc ruleset used to drive `hp`
  negative. A game that wants negatives gives its `hp` pool `floor=None`.
- **Advancement is opt-in.** `GameSystem` alone has no character-point
  economy (`improve_cost` is `None`, kills award nothing, `score` lists
  pools); GURPS and D20 use `PointBuyMixin`. A custom system that relied
  on the old defaults mixes it in: `class MySystem(PointBuyMixin, GameSystem)`.
  Under Merc, `improve` says the game has no skill purchase.

### Python API changes

- `Combatant.hp`, `max_hp`, `hp_percent` are `vital`, `vital_max`,
  `vital_percent` (read-only); `Combatant.vital_spent` replaces
  `Ruleset.is_defeated`. Strategy conditions keep `me.hp` and
  `me.hp_percent`.
- A ruleset's `apply_damage` ends in `self.write_damage(target, amount)`;
  `Ruleset.required_stats` is gone.
- `deal_damage` returns `(dealt, action, changes)`; the caller settles the
  pool changes (`realm.pools.settle`). `CombatResult.changes` carries a
  swing's, and `CombatEncounter.land` settles them.
  `CombatManager.handle_defeat` and the softcode `death_check` queue kind
  are gone.
- `apply_resisted` returns a `PoolChange`.

### Added

- Pools (`realm.pools`, `realm.Pool`, `docs/guides/pools.md`): health and
  resources on anything, with softcode `pool`, `harm_pool`, `mend_pool`,
  `spend_pool`, `spent`.
- The public API (`realm.__all__`, each feature's `__all__`), frozen by a
  test.
- Add-on features as installable packages (the `realm.features`
  entry-point group) and `realm features [--check]`.
- `realm init --features classic|social|bare`, and a scaffold with
  `tests/test_game.py` and a README; `Simulator.from_game(dir)` and
  `Simulator.start()`.
- `realm import-rom`.
