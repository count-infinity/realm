# Changelog

## 0.3.0 — the MUD plan (in progress)

The steps of `MUD_PLAN.md`, recorded as they land.

### Operating a live game (step 9)

- Link-dead characters: a connection that drops without `quit` leaves the
  character in the room, tagged `linkdead` (shown `(linkdead)`), for
  `LINKDEAD_SECONDS` (120); connecting again resumes it in place, else it
  leaves play. Protocol adapters call the new
  `SessionManager.connection_lost(session)`; `destroy_session(session,
  reason=...)` records `Session.close_reason` (`CLOSED` or `LINK_LOST`).
  `ON_DISCONNECT` now fires when a character leaves play: for a dropped
  link, when its wait ends.
- `IDLE_TIMEOUT` (minutes, 0 off; admins exempt) closes idle connections.
- Flood control (audit G13): a token bucket per connection (`COMMAND_RATE`
  10, `COMMAND_BURST` 30); a dropped line warns once; a flood lasting
  `FLOOD_DISCONNECT_SECONDS` (30) closes the connection and is logged.
- Presence (audit G4): `who` shows idle time and the `afk` and `linkdead`
  marks, and leaves out players the viewer cannot see;
  `world.services["who"].fields` adds marks; softcode `online_players()`
  and `idle_seconds(obj)`. `online_players` and `is_online` moved from
  `realm.std.channels.common` to `realm.gateway.session` (and
  `SessionManager.online_players()` / `is_online()`); `cmd_who` moved to
  `realm.std.basics.presence`.
- New feature `operations` (in `CLASSIC`): `@wall`, `@shutdown [seconds]
  [= reason]` and `/cancel`, `@reboot` (`realm start` exits with status 3),
  `@snoop`, `@freeze` / `@thaw`; logged on `realm.admin`.
- `realm backup [file] [--keep N]` (SQLite online backup, default
  `data/backups/<name>-<timestamp>.db`), `realm restore <file>` (refused
  while the server runs: the server keeps `<db>.pid`), settings
  `BACKUP_INTERVAL_HOURS` and `BACKUP_KEEP`.
- `realm migrate`: the schema is now v2 (an index on `parent_id`); a server
  refuses an older database with `SchemaOutOfDateError` and a message to
  run `realm migrate`. `PersistenceManager._flush_queue` is now `flush()`.
  `CommandDispatcher.server` is declared (None in a Simulator).
- Saved worlds: **run `realm migrate` once** (after `realm backup`) before
  starting a database made by an earlier REALM. Characters left link-dead
  by a crash are cleared at start.

### The world clock (step 8)

- New feature `clock` (in `CLASSIC`): game time derived from an epoch on a
  `world_clock` object at `GAME_TIME_RATIO` (30); calendar settings
  `HOURS_PER_DAY`, `DAYS_PER_MONTH`, `MONTH_NAMES`, `DAY_NAMES`; a new
  world starts at 08:00. Softcode `game_time()`, `time_of_day()`,
  `weather(room)`; `time` shows game time first (it replaces the `basics`
  command); `weather`.
- Events `time:on_hour` (`HOUR`), `on_dawn`, `on_day`, `on_dusk`,
  `on_night`, fired once per game hour on zone masters and rooms holding
  players.
- Night: `outdoor` rooms are dark at night unless `lamplit` or lit by a
  light source. The `sight` service gains `add_darkness_test`.
- Weather per zone master (`weather`, `weather_messages`, `weather_now`).
- The ROM importer tags city rooms `lamplit`; Midgaard refreshed.
- `MemoryStore.register(obj)`, the same sync call as
  `PersistenceManager.register`.
- Saved worlds: the clock starts at the first boot after upgrading.
  Imported areas' `outdoor` rooms now go dark at night; tag a room
  `lamplit` to keep it lit.

### Communication (step 7)

- New feature `channels` (in `CLASSIC`): `tell` (`t`), `reply` (`r`),
  `ignore`, `unignore`, `afk`; channels as `channel_def` data with `speak`
  and `listen` locks, a `format` and history; `channels`, `channel <name>
  on|off|history`; a channel's name is a command; events `comm:on_tell`
  (`TELL`) and `comm:on_channel` (`CHANNEL`); softcode `cemit`,
  `channel_members`. The `channels` pack ships gossip, newbie and immtalk.
- `talk` gains socials: `social_def` data, `socials`, the `event:social`
  action (`SOCIAL`); the `socials-classic` pack ships 48.
- New feature `mail` (in `CLASSIC`, needs `accounts`): `mail` and its
  switches, unread count at login, `MAIL_LIMIT`, softcode `send_mail`.
- The scaffold's `config.py` now has a live `init_world` importing the
  `channels` and `socials-classic` packs; Midgaard and the space station
  import them too.
- `SessionManager.adopt(session)`; the Simulator keeps a real session
  manager, so who is online reads the same in tests as on a server.
- Showcase 75 (mail in softcode) now runs without the `mail` feature, and
  its page says the engine does this.
- Saved worlds: a game made before 0.3.0 has no channels or socials until
  it imports the packs (`@pack import channels`,
  `@pack import socials-classic`).

### Accounts (step 6)

- **Login changes.** A person logs in to an account: `create <account>
  <password>` then a first character's name; `connect <account>
  <password>`, straight into play with one character, else a menu (`play`,
  `new`, `delete`, `password`, `quit`). In play: `characters`, `password`.
  Settings `MAX_CHARACTERS` (5) and `ACCOUNT_MULTIPLAY` (False: a second
  login takes over).
- Accounts are objects tagged `account` (`realm.std.accounts.account`);
  `account_of` and `characters_of` are public in `realm.std.accounts`.
  `Session.account`; `AuthService.authenticate` returns an account,
  `create_account` makes one and `create_character` a character on it.
  `Simulator.account(name, *characters)`.
- Saved worlds: on the first boot, every character with a password gets an
  account of the same name holding it, and logs in as before.
- Softcode `account_attr`, `set_account_attr`, `incr_account_attr`,
  `account_characters` (group "Accounts").
- New feature `achievements` (in `CLASSIC`): `achievement_def` data,
  `grant_achievement`, `has_achievement`, `achievements`, the
  `account:on_achievement` event (hook `ACHIEVEMENT`); grants of tags and
  check modifiers reach every character of the account.
- `@account` (show, `/password`, `/ban`, `/unban`, `/boot`) and
  `@sitelock`; changes logged on `realm.admin`. Closes capability gap G12
  and showcase 178. Showcase 207 is rebuilt on the achievements feature.
- `GameServer.stop` disconnects sessions before closing the world, so a
  player still in play at shutdown is announced and saved.

### Progression (step 5)

- Four ways a skill improves, chosen per skill by the skill_def's
  `progression` (else `GameSystem.default_progression`: `points` on
  `PointBuyMixin`, `use` on Merc, None on the neutral base):
  `realm.std.rules.progression`.
- Learn by use: `GameSystem.on_skill_used`, called at the end of every
  `check()` and by `CombatSystem.attack` after each attack roll (the
  weapon's `skill`); `skill_cap`, `check_was_open`, `use_xp_gain`,
  `use_xp_needed`; a skill_def's `progress_rule`, `untrained_use`,
  `class_caps`. Merc caps skills SMAUG-style (75/95).
- Practice: the `trainer` behavior and the `practice` and `train`
  commands; Merc grants one train per level; the ROM importer makes
  ACT_PRACTICE/ACT_TRAIN mobs trainers (Midgaard refreshed).
- Idle training: `study`, lazy accrual from the wall clock
  (`accrue_training`), `idle_cost`, a definition's `attributes`, `rank`
  and `requires`; setting `IDLE_TRAINING_MAX_HOURS`.
- New feature `tasks` (in `CLASSIC`): softcode `start_task`, `task_of`,
  `stop_task`; command `stop`; the `(busy)` marker.
- Kernel: `realm.core.defs.def_objects(kind)`.
- `skills` shows a `use` skill's progress and the skill in training.
- Showcase 122 crafts over time with `start_task`; new showcase 253, a
  skill learned at the forge. Showcase 217's exit is now `in`, since
  `study` is a command.
- Saved worlds: nothing stored changes. Merc characters now learn every
  skill by use, from the level they have.

### Skills you can use (step 4)

- An `ability_def` is a command: typing its name or one of its `aliases`
  runs it, when no command or exit matches and the player may use it.
  `abilities` (`ab`) lists them. Costs take `"cooldown": <beats>`;
  effects add `check`, `weapon_damage`, `tag`, `rescue` and `disarm`;
  dice may say `{level}`; defs may set `requires_weapon`,
  `target_unaware`, `target_fighting`, `hostile`, `fail_msg`.
- The merc-classic pack adds `skills.json`: kick, bash, backstab, rescue,
  disarm, trip. `MERC_CLASSES` starting skills match (barbarians no longer
  start with `rescue`); starting weapons carry a `damage_type`.
- `MercRuleset`: dodge, parry and shield block; second and third attack
  through a new `Ruleset.extra_attacks` hook.
- Combat: `CombatManager.attackers_of`, `retarget`, `disarm`; softcode
  `attackers()` (readonly), `retarget()` and `disarm()` (harm).
- The ROM importer writes a weapon's `damage_type` from its attack word;
  `consumable_fields` is now `item_fields`. Midgaard refreshed.
- Saved worlds: a Merc character made before 0.3.0 has its old starting
  skills; give it the new ones with `@set` if wanted.

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
