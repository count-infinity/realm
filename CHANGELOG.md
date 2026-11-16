# Changelog

## 0.3.0 — the MUD plan (in progress)

The steps of `MUD_PLAN.md`, recorded as they land.

### The character sheet (step 3)

- `GameSystem.wear_slots()` (Merc: Diku's 14 places, two fingers, necks
  and wrists) and `wear <item> replace`; `equipment` (`eq`) lists every
  slot; `inventory` no longer lists worn or wielded items. `wear` and
  `remove` moved to `realm.std.items.equipment`.
- `skills` (`sk`), grouped by a skill_def's `group`, in the system's own
  terms (`GameSystem.format_skill`); `score` no longer lists skills.
  `define_skill` takes `group=`.
- The prompt (closes capability gap G10): kernel seam `feature.prompt` /
  `World.prompt_renderer`; `Session.set_prompt_writer` and
  `flush_output(prompt=)`; telnet offers EOR and ends a prompt with
  `IAC EOR` (or `IAC GA`); WebSocket sends a `prompt` frame. `basics`
  declares the default (setting `PROMPT`, command `prompt`);
  `Simulator.prompt(player)`. The Merc scaffold and Midgaard set
  `PROMPT = "<{hp}hp {mana}m {move}mv> "`.
- Consumables: `eat` and `drink` (events `item:on_eat`, `item:on_drink`,
  hooks `EAT`, `DRINK`; the item's `restores` and `charges`); `quaff`,
  `recite`, `zap` and `brandish` (the item's `spells` at its
  `spell_level`). `invoke_ability` takes `free=` and `level=`. A line
  these commands cannot use goes to the world's `$`-commands first.
- The ROM importer writes Merc slot names (`held`, `light`), and
  consumable fields, translating ROM spell slot numbers; the Midgaard area
  is refreshed (`scripts/dev/refresh_rom_items.py`).
- Saved worlds: worn items saved before 0.3.0 have no wear order; the
  first `wear ... replace` treats them as oldest. An exit whose name is a
  prefix of a new command (`prom` for `prompt`) now runs the command;
  rename the exit.

### The solo loop (step 2)

- New feature `vitals` (in `CLASSIC`): characters regain their pools out
  of combat every `REGEN_INTERVAL` seconds, by the game system's new
  `regen(obj, pool)` hook; `rest`, `sleep` and `stand` (`wake`) multiply it
  by `REST_REGEN` and `SLEEP_REGEN`. Resting and sleeping characters do not
  walk; a hostile act stands them up; a sleeper sees and hears nothing it
  is not party to and is answered "You are asleep." for most input.
  `world.services["vitals"].multipliers` lets other features scale it.
- `Pool` has a new setting, `regen` (default True).
- Coming round: an `unconscious` character whose vital pool rises above
  spent, by any cause, gets up ("You come to."). `firstaid` no longer
  removes the tag itself.
- `when_spent = "respawn"` and the `PLAYER_DEATH` setting (`"unconscious"`
  by default): a player who dies leaves `corpse of <name>` with what they
  carried (not `soulbound` items), locked to them for `CORPSE_LOCK_SECONDS`,
  pays `GameSystem.on_death` (Merc: a quarter of a level's experience) and
  wakes at home at 1 point. The Merc scaffold and Midgaard set it.
- Merc: walking spends `move` by the destination's `move_cost` or sector.
- Kernel seam: `feature.deaf_rule` / `World.deaf_rules`, consulted by
  `deliver_messages`. `realm.testing.Simulator.input` feeds a line through
  the input interceptors as a connection does.
- `world.services["effects"].clear(obj)` ends a character's timed effects.
- Scavengers no longer eat a player's corpse.
- Saved worlds: nothing stored changes. A character saved below full starts
  regenerating at boot. A game that built resting in softcode (showcase
  138) and keeps `vitals` loaded will find the engine's `rest` and `wake`
  answer first; leave `vitals` out of `FEATURES` to keep the softcode.

### Starting points (step 1)

- `realm init --system gurps|d20|merc` picks the rules system the
  scaffold's `rules.py` inherits (GURPS by default), and its commented
  examples are written for that system (GURPS `TEMPLATES`, D20 `CLASSES`,
  Merc `MERC_CLASSES`). `--system` with `--features social` or `bare`, or
  with `--template`, is refused.
- The `midgaard` and `spacegame` templates are full scaffolds: each has its
  own `rules.py` (a `GameRules` subclass of `MercSystem` / `GurpsSystem`),
  `game.py`, and `config.py` with `GAME_SYSTEM = "rules.GameRules"` and
  `FEATURES = [*CLASSIC, "game"]`. `realm init --template` also writes
  `tests/test_game.py` and `README.md` when the example has none.
- The GURPS class example in the scaffold's `rules.py` imported
  `ChoiceStep` in the class body, where its method could not see it;
  uncommented, it raised `NameError`. The import is now inside the method.
- Saved worlds: unchanged. The examples' `GameRules` keep the stock
  `system_id` (`merc`, `gurps`), so characters in an existing Midgaard or
  station database still match their rules. A game scaffolded from a
  template before 0.3.0 keeps working as it was.

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
- **Darkness and invisibility are a feature, `sight`.** It is in
  `CLASSIC`, so a game using `CLASSIC` sees no change. A game with its own
  `FEATURES` list adds `"sight"` to keep `dark` rooms, `light` sources,
  `nightvision`, `invisible`/`see_invisible` and the `glowing`/`magic`/
  `invisible` markers; without it those tags do nothing. (The `social` and
  `bare` scaffold presets leave it out.) `realm.core.perception` no longer
  has `room_is_lit`, `can_see_room` or the tag constants: they are in
  `realm.std.sight`.
- **Soak applies to every kind of damage**, typed or not: softcode
  `damage()` and damage over time subtract a pool's `soak_attr` like a
  swing does. `harm_pool()` stays raw. (Stock `hp` defines no soak, so
  characters are unaffected.)
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
- The `sight` feature (above).
- The spacegame example's ships are pools (shields overflowing into an
  armored hull), so stock damage reaches them; `Spaceship.take_damage`
  returns the `PoolChange`.
