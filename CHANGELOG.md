# Changelog

## 0.3.0 — the MUD plan

`MUD_PLAN.md`, steps 1 to 17: REALM goes from an engine with a combat
demo to a MUD system a developer can open to players. `realm init mygame
--system merc --template midgaard` makes a Diku game with accounts,
classes, skills that improve, death and recovery, shops, pets and mounts,
hunger, tells and channels and mail, clans, quests, achievements, a world
clock, operator tools and a browser client; `tests/test_first_hour.py`
plays its first hour. The step entries below say what each added; this
section says what a 0.2.0 game must do to move up.

### Upgrading from 0.2.0

Run these once, in the game's directory, with the server stopped:

```text
realm backup
realm migrate        # the schema is now v2 (MUD_PLAN step 9)
```

A 0.2.0 database is refused at start until it is migrated
(`SchemaOutOfDateError`, with the command to run). Then:

- **Logins are accounts.** `create <account> <password>` and `connect
  <account> <password>` log in to an account that holds the characters
  (`MAX_CHARACTERS`, 5). On the first boot every character that has a
  password is given an account of the same name, holding it, so players
  log in with the name and password they had. Code that read
  `player.db.password` or named characters at login reads accounts now
  (`realm.std.accounts.account_of`, `characters_of`; `Session.account`).
- **A fallen player respawns** (Decision D1, decided 2026-11-16).
  `PLAYER_DEATH` now defaults to `"respawn"` in every game, GURPS, D20,
  Merc or none: a player whose vital pool is spent leaves a corpse of what
  they carried where they fell, pays the game system's `on_death` penalty
  (none outside Merc) and wakes at home one point short of spent. A 0.2.0
  game whose players fell unconscious in place keeps that rule with one
  line in `config.py`:

  ```python
  PLAYER_DEATH = "unconscious"
  ```

- **`firstaid` no longer removes `unconscious`.** It mends the damage
  pool; a character rises ("You come to.") when its vital pool climbs
  above spent, by any cause. Softcode that removed the tag to revive
  someone should `mend` (or `heal`) instead.
- **`score` and `inventory` say less.** Skills moved to `skills`, and worn
  and wielded items to `equipment`; `inventory` lists only what is
  carried. Softcode or tests that read them from `score` or `inventory`
  read the new commands.
- **New commands may answer before an old exit or `$`-command** of the
  same name or prefix: `abilities`, `achievements`, `afk`, `alias`,
  `channel`, `channels`, `characters`, `clan`, `clans`, `clantalk`,
  `companions`, `config`, `dismiss`, `dismount`, `drink`, `eat`,
  `equipment`, `exits`, `fill`, `ignore`, `mail`, `mount`, `order`,
  `password`, `practice`, `prompt`, `quaff`, `quest`, `quests`, `recite`,
  `reply`, `report`, `rest`, `scan`, `skills`, `sleep`, `socials`,
  `split`, `stand` (`wake`), `stop`, `study`, `talk`, `tell`, `train`,
  `unalias`, `unignore`, `weather`, `where`, `zap`, a channel's name, and
  the administrators' `@account`, `@clan`, `@edit`, `@freeze`, `@thaw`,
  `@reboot`, `@shutdown`, `@sitelock`, `@snoop`, `@wall`. Rename the exit
  (`prom` now runs `prompt`). Some short forms moved to keep their old
  meaning: `fi` is `firstaid`, `sc` `score`, `sp` `spells`, `rep`
  `reply`, `cl` `close`, `@cl` `@clone`, `ta` `get`, `mo` `credits`. A
  bare `talk` and `study`, and a `cast` or consumable line the engine
  cannot use, still reach the world's `$`-commands first.
- **`@desc <obj>` with no `=`** opens the line editor; it used to clear the
  description. `@desc <obj> =` still clears it.
- **Night falls.** `outdoor` rooms are dark at night unless `lamplit` or
  lit; the ROM importer tags city streets `lamplit`. Tag a room `lamplit`
  to keep it lit, or leave `clock` out of `FEATURES`.
- **A character out of play is not in its room's listing** (step 17): a
  player who quit is no longer listed under "Players here" or by `scan`;
  a link-dead one is, marked.
- **`kill`, typed abilities and `cast` aim at creatures**: a player, an
  NPC or anything with a damage pool, never a corpse or a plain thing
  (step 17).
- **A game that lists its features** (not `[*CLASSIC, "game"]`) gets none
  of the new ones until it adds them: `vitals`, `needs`, `channels`,
  `mail`, `tasks`, `achievements`, `clock`, `operations`, `companions`,
  `clans`, `quests`. Their order matters (`realm features --check`).
- **New content to import** into a world made before 0.3.0: `@pack import
  channels`, `@pack import socials-classic`, `@pack import
  clan-governments`; a Merc game's `merc-classic` pack gained
  `skills.json` (kick, bash, backstab, rescue, disarm, trip) and `charm
  person`.
- **An area converted from ROM before 0.3.0** keeps its old data (no
  money on mobs, food and drink as `restores`, no pet shop, shopkeeping
  objects, respawns without `prototype_vnum`, things named by their
  keywords, "sword long", with the short description unused in
  `short_desc`, and every room flag written as a number lost) until it is
  converted again or refreshed with `scripts/dev/refresh_rom_items.py`; a
  database keeps what it imported until the area is imported again. A
  Midgaard database made before keeps its old town (see "Midgaard from
  ROM 2.4's own area file").
- **Python names that moved:** `online_players` and `is_online` from
  `realm.std.channels.common` to `realm.gateway.session`; `cmd_who` to
  `realm.std.basics.presence`; `wear` and `remove` to
  `realm.std.items.equipment`; `ACCOUNT_TAG` from
  `realm.std.accounts.account` to `realm.core.options`;
  `rom_import.consumable_fields` is `item_fields`;
  `PersistenceManager._flush_queue` is `flush()`; `make_ws_writer(ws,
  player)` takes the function that names the player. None of these was a
  public name.

### What did not change

- **The public API** (`docs/reference/public-api.md`): `realm.__all__` and
  the games' names are as in 0.2.0; features only gained names
  (`accounts`, `companions`, `clans`, `quests`).
- **Saved worlds load**, after `realm migrate`: object ids, attribute
  names, tags and behavior ids are as they were. What a step stores anew
  (accounts, food and water, quest progress, clan membership, wear order)
  is added to an existing object when it is first needed, at boot or at
  the character's next login.
- **Action types, `ON_<EVENT>` hooks and softcode functions** were only
  added, never renamed or removed.
- **Content packs, area files** (worldio JSON) and `@pack`, `@import`,
  `realm pack`, `realm export` / `realm import`.
- **GURPS and D20** play as before: hunger, learning by use, alignment and
  the Diku sheet are Merc's (Decisions D5, D6).

### New settings

Each is documented in [Configuration](docs/reference/config.md) and has a
default; a game sets only what it wants different.

| Feature or area | Settings |
|---|---|
| server | `LINKDEAD_SECONDS`, `IDLE_TIMEOUT`, `COMMAND_RATE`, `COMMAND_BURST`, `FLOOD_DISCONNECT_SECONDS`, `BACKUP_INTERVAL_HOURS`, `BACKUP_KEEP`, `PAGE_LENGTH`, `WEB_CLIENT` |
| `accounts` | `MAX_CHARACTERS`, `ACCOUNT_MULTIPLAY` |
| `basics` | `PROMPT`, `ALIAS_LIMIT` |
| `combat` | `PLAYER_DEATH`, `CORPSE_LOCK_SECONDS` |
| `vitals` | `REGEN_INTERVAL`, `REST_REGEN`, `SLEEP_REGEN` |
| `needs` | `NEEDS_INTERVAL`, `FOOD_LOSS`, `WATER_LOSS`, `NEEDS_REMINDER_TICKS`, `HUNGER_DEATH_HOURS`, `THIRST_DEATH_HOURS`, `HUNGRY_AWARD`, `FATIGUE_SLEEP_RECOVERY` |
| `rules` | `FOOD_FULL`, `WATER_FULL`, `NEEDS_BASE_WEIGHT`, `IDLE_TRAINING_MAX_HOURS` |
| `items` | `FOOD_GAIN`, `WATER_GAIN` |
| `merc` | `LEVEL_CAP` |
| `mail` | `MAIL_LIMIT` |
| `clock` | `GAME_TIME_RATIO`, `HOURS_PER_DAY`, `DAYS_PER_MONTH`, `MONTH_NAMES`, `DAY_NAMES` |
| `companions` | `COMPANION_LIMIT_RULE`, `COMPANION_LEVEL_DIFF`, `ORDER_REFUSED`, `MOUNTS_INDOORS` |
| `clans` | `CLAN_COST`, `CLAN_MIN_LEVEL`, `CLAN_MIN_MEMBERS`, `CLAN_MAX_MEMBERS`, `CLAN_MAX_TAX`, `CLAN_DEATH_DAYS`, `CLAN_OVERTHROW_DAYS` |

### The maintainer's decisions, and two first-hour items (after the plan)

- **Respawn is the default** (Decision D1): `PLAYER_DEATH` defaults to
  `"respawn"` for every game; `"unconscious"` is the rule a game sets
  (see "Upgrading from 0.2.0"). The Merc scaffold and the Midgaard
  template no longer write `PLAYER_DEATH` into `config.py`. A respawned
  player wakes one point short of spent, which for a harm clock (an `up`
  pool) is one below its max and for a pool spent at 2 is 3 (it was set
  to 1 whatever the pool).
- **Each account has its own character limit** (Decision D2, after
  CoffeeMud's `BONUSCHARLIMIT`): `MAX_CHARACTERS` (5) plus the account's
  `bonus_characters`, which `@account/slots <name> = <n>` sets (logged on
  `realm.admin`), plus the `characters` an account achievement's `grants`
  give (`{"characters": 1}`, counted from what the account has earned).
  The character menu shows it ("Your characters (2 of 6):"), `@account`
  shows how it adds up, and the softcode `character_limit(obj)` reads it.
  The accounts service's `slot_sources` is where a feature adds its own.
  `set_account_attr` and `incr_account_attr` now refuse the records the
  engine keeps on an account (`characters`, `bonus_characters`,
  `achievements`, `created`, `last_login`, `last_address`,
  `banned_until`, `ban_reason`).
- **Pets and mounts come along on `recall`**, as ROM's pet does: a
  companion beside its master recalls with it, and a rider recalls on its
  mount. The seam is the new reserved action tag `accompanied`
  (`realm.core.action_tags.ACCOMPANIED`), which `recall` puts on its move;
  a softcode gate spell opts in with `move_to(enactor, dest,
  tags=['accompanied'])`. `@tel`, `teleport_obj` and a summons still move
  the mover alone.
- **One prompt after an announcement**: `@shutdown` (and anything else
  whose output is flushed while the command runs) no longer writes the
  typist's prompt twice. `Session.input_arrived()` marks the prompt on the
  screen as answered; `GameServer._on_command` calls it.

### Midgaard from ROM 2.4's own area file (after the plan)

- The shipped `midgaard.json` is converted again, from ROM 2.4b6's
  `area/midgaard.are` (how, exactly: [Importing ROM areas, "The shipped
  Midgaard"](docs/development/rom-import.md#the-shipped-midgaard)). The
  baker keeps the Bakery and sells his bread and pies; the mage, cleric,
  thief and warrior guildmasters are in their guilds; Hassan guards the
  Temple of Mota; the knight templar, the janitor, the maid, a sparrow and
  Melancholy are back. The earlier file was a modified Midgaard (a morgue,
  a zoo, a chess board, a cesspool for the donation pit, exits to areas
  REALM does not ship) that had lost those placements.
- **Names read as ROM's do.** The importer names a mob or object by its
  short description ("the baker", "a long sword", "a big pot pie") and
  gives it its ROM keywords as `aliases` (the whole list and each word),
  so `buy potpie` and `get sword long` still work. `short_desc` is no
  longer written. `scripts/dev/refresh_rom_items.py` renames a file
  converted before.
- A plural drops a leading "the" as it drops "a": two of "the cityguard"
  read "2 cityguards" (`realm.core.language.pluralize`).
- A shopkeeper does not sell what it wears or wields (a converted mob's
  equipped gear carries a `worn` attribute): the baker no longer offers
  his long sword.
- The ROM importer reads a bit-vector written as a decimal number
  (Midgaard's room flags, older areas' ACT and extra flags) as its letters;
  such flags were dropped, so a numbered sentinel wandered and a numbered
  pet shop sold nothing. A potion, pill, scroll, wand or staff that names
  no spell is reported. The refresh script gains `--spells
  VNUM[,VNUM]=spell[+spell]`, which gives back spells a source file lost.
- The Midgaard template: each class's guild bar lets in only that class
  (`GUILD_BARS` in its `config.py`, an `enter` lock; barbarians use the
  swordsmen's), so each class practises at its own guildmaster; the
  cloned baker is gone, and "Fido trouble" is the real baker's (`giver`
  `{"name": "baker", "prototype_vnum": 3001}`).
- Saved worlds: a Midgaard database made before boots and plays as it did
  (`init_world` runs only on an empty database): its keyword names, its
  cloned baker and its everyone's-guildmaster stay. Start a new database
  for the new town.

### Clocks a test can move (after the plan, 2026-11-17)

- Every time the engine reads for a game reason now goes through a
  module-level `now()` that the code calls through its module, so a test
  moves it with `monkeypatch.setattr("realm.std.mail.mail.now", ...)`.
  New ones: ability cooldowns (`realm.std.abilities.abilities`, which the
  `abilities` listing reads too), corpse locks (`combat.corpses`), mail
  dates (`mail.mail`), achievement dates (`achievements.achievements`),
  channel and clan-talk history (`channels.channels`), the combat beat
  (`combat.encounter`), zone resets (`spawning.zone_reset`), the login
  throttle (`accounts.auth`), softcode `wait()`'s due times
  (`realm.scripting.waits`, what `waits.tick()` fires by) and object
  expiry (`realm.core.events`, which softcode `expire()` and `now()` read).
  Stored times keep their meaning: what was wall-clock in the database
  (cooldowns, locks, dates, `expires_at`, `last_reset`) still is.
- One name for all of them: `realm.gateway.session.clock` is
  `realm.gateway.session.now`, `realm.std.vitals.regen.monotonic` is
  `regen.now`, and the instances and wilderness `_clock` is `now`.
  `AuthService` no longer takes `clock=`. The reapers' explicit time is
  `at=` (`reap_expired(store, at=...)`, `reap_idle`, `reap_wilderness`),
  so it no longer hides the module's `now`.
- The combat beat loop's look at the clock is `CombatEncounter.beat()`:
  it fires the round when the beat is due on `now()`, sets the next one a
  beat away, and closes the fight once it is over. The loop calls it each
  time it wakes (it still sleeps in real time, at most `POLL_SECONDS`); a
  test moves the clock to the beat (`seconds_to_beat`) and calls it.
- New `realm.testing.FakeClock` and the `clock` fixture: one fake time for
  every engine clock (`realm.testing.clock.ENGINE_CLOCKS`),
  `clock.advance(seconds)` moves them all. `tests/test_clocks.py` fails
  when a module reads the time any other way, or adds a `now()` the list
  does not name ([Testing, "Moving time"](docs/development/testing.md#moving-time)).
- `tests/test_first_hour.py` uses it: its fights run by moving the clock
  to each beat, not by firing `resolve_round` by hand, and it asserts the
  story's dates on mail and achievements.

### The first hour (step 17)

- `tests/test_first_hour.py` plays each line of the plan's "What
  'complete' means here" on a game made by `realm init demo --system merc
  --template midgaard` and run by a real server on its own database: an
  account and two characters, a level gained alone (hurt, rested, killed,
  back, looting, selling, buying, wearing), a kicked fido, practice and
  study, tells, gossip and mail, an achievement shared by an account, an
  administrator's ban, password reset, shutdown, backup and restore,
  hunger, a pet and a horse, a clan and its door, a quest, and a loft built
  live in softcode.
- `realm init <name> --system merc --template midgaard` works: `--system`
  with `--template` may name the template's own rules system, and is
  refused (with the one to use) when it names another or the template has
  none.
- New page [Your First MUD](docs/getting-started/your-first-mud.md).
- A character out of play (quit, or switched away from with `characters`)
  is not listed in its room or by `scan`; link-dead ones still are,
  marked (`realm.std.look.render.out_of_play`).
- New `realm.commands.base.find_victim(ctx, name)`: whom `kill`, the
  combat maneuvers, `firstaid`, a typed ability and `cast` aim at is a
  player, an NPC or anything with a damage pool, so `kill fido` beside
  "the corpse of fido dog" is not ambiguous and `kick` no longer kicks the
  corpse. New `realm.std.abilities.target_kind(adef)`.
- A fight ends when no living participant has another as its target (two
  mobs whose quarry died or fled used to stay in combat forever).
- `get_combatant(obj)` wraps the object it is given: a world loaded again
  in the same process (a restored backup, a second server) no longer
  fights through wrappers of the old objects.
- The ROM importer: reset lines are read as ROM's loader reads them (a `*`
  line is a comment, a reset's trailing comment never swallows the next
  line), which lost mob placements and gave their stock to the mob before;
  `#SHOPS` patches the keeper mob only, not an object with the same vnum;
  `P` resets put into an object, not a mob with the same vnum; a spawner's
  or zone reset's prototype carries `prototype_vnum`, so a quest or lock
  that names a mob by vnum knows its respawns.
  `ACT_SCAVENGER` picks things up and eats no corpse
  (`rom_import.scavenger_behavior()`; only `spec_fido` eats them).
  `scripts/dev/refresh_rom_items.py` mends the shops, spawners and
  scavengers of an area converted before, and the shipped Midgaard was
  refreshed with it.
- `quit`, or anything else that destroys its own session, through a
  connection's input pump no longer cancels its own teardown
  (`Session.stop_input_pump` leaves the running pump to end after that
  line): the session stayed registered with its character and the
  connection open.
- `help <command>` and the `channels` footer show a pipe as a pipe
  (`on|off|history` lost `|h` to the bold markup).
- No prompt is shown while a character is being made (`basics`' renderer
  returns None while `chargen_step` is set).
- The Midgaard template: "Fido trouble" makes its finisher a Friend of the
  Baker (`data/achievements.json`), shared by the account; the pet shop
  sells a brown horse (`data/stable.json`); lore is a skill studied while
  away (`data/skills.json`); the welcome banner says how to `create` and
  `connect`.
- Saved worlds: nothing stored changes. A Midgaard database made before
  keeps its shopkeeping bottles, its corpse-eating cityguards and its
  respawns without `prototype_vnum` until the area is imported again.
- Version 0.3.0.

### A browser client (step 16)

- A browser client (Decision D3): one page of HTML, CSS and plain
  JavaScript, `realm/web/index.html`, with no build step and nothing
  fetched from elsewhere, shipped in the wheel. New setting `WEB_CLIENT`
  (default `False`): with `ENABLE_WEBSOCKET` the WebSocket server serves
  the page at `/` (titled with `GAME_NAME`), and the page connects to
  `/ws` beside it. `WEB_CLIENT` without `ENABLE_WEBSOCKET` logs a WARNING
  at start with the fix ([Protocols](docs/protocols/overview.md#the-browser-client)).
- The page shows colored output, keeps input history (password lines are
  echoed masked and not kept), shows the prompt in a fixed line, draws
  `Char.Vitals` as bars and the room name from `Room.Info`, sends a blank
  line to turn the pager's page, and reports its size so the pager fits
  the screen. It works at phone width, follows light and dark themes, and
  is built for screen readers (a labelled input that keeps the focus, a
  polite live region for output).
- The player's `color`, `screenreader` and `palette` options now apply to
  WebSocket output as at the telnet edge (`realm.core.options.Display`,
  `display_for`; `realm.core.markup.recolor`). The WebSocket prompt frame
  is styled like text (`text` plain, `segments` when colored) instead of
  carrying raw markup. Plain text that starts with `{` is sent as a JSON
  text frame, so it cannot pass for a frame. `make_ws_writer(ws, player)`
  takes the function that names the connection's player.
- `Session.write_prompt` sends `Char.Vitals` (every declared pool plus the
  damage and vital pools, `name` and `max_name`) to a client with an
  out-of-band channel whenever it changed since the last one sent, so the
  bars, and any GMCP client's gauges, follow regeneration and spending,
  not only combat rounds.
- `WebSocketServer.make_app()` builds the aiohttp application (its routes)
  without running it.
- Saved worlds: nothing stored changes.

### Quests (step 15)

- New feature `quests` (in `CLASSIC`, after `clans`; requires nothing),
  after tbaMUD's autoquests and CoffeeMud's QuestMaker templates
  ([Quests](docs/guides/quests.md)). Quests are data: `quest_def` objects
  (`feature.def_kind("quest", ...)`) with `description`, `giver`,
  `accept_lock`, `stages` (each `text` and `objectives`), `rewards`
  (`award`, `credits`, `items`, `achievement`, `tags`), `repeatable`,
  `time_limit`, `scope` (`character` or `account`) and `on_accept`,
  `on_stage`, `on_complete`, `on_fail` softcode. A definition with an
  unknown objective kind or key, no stages, an empty stage, two objectives
  sharing a key or a reward naming no prototype is logged by name and
  skipped when definitions load.
- Objectives `kill` (the killer's, a companion's master's, the party's in
  the room), `collect` (what is held; `consume`), `deliver` (an item given
  to `to`), `visit`, `talk`, `use` and `custom` (softcode only), matched
  by `id`, `name`, `tag` and `prototype_vnum`, tracked by one observer on
  `combat:on_death`, `item:on_get`, `item:on_give`, `event:on_enter`,
  `quest:on_talk` and `item:on_use`, with an index of who online waits on
  which kind. A reaper fails quests past their `time_limit` (an absent
  character's at their next login).
- Commands `quests` (`journal`; `quests done`), `quest` (`list`, `<name>`,
  `accept`, `complete`, `abandon`) and `talk <npc>` (fires
  `quest:on_talk`, hook `TALK`; a bare `talk` goes to the world's `$talk`
  first). The `quest_giver` behavior (`quests`); the `(!)` and `(?)`
  markers beside givers. `ta` is now an alias of `get` (take), which it
  reached by prefix before `talk`.
- Rewards through the `rules` service's new `award(player, amount)` (so
  the award filters apply: hunger, clan tax), the `economy` service, a
  clone of each prototype, and the `achievements` feature's new service
  (`world.services["achievements"]`: `grant`, `has`); a reward whose
  feature is absent is skipped with a WARNING naming the quest.
- Softcode `quest_state`, `quest_count` (read-only, so also in locks:
  `quest_state(caller, 'Fido trouble') == 'done'`), `quest_offer`,
  `quest_advance`, `quest_complete`, `quest_fail` (builders). Events
  `quest:on_accept`, `quest:on_advance`, `quest:on_complete`,
  `quest:on_fail` (hooks `QUESTACCEPT`, `QUESTADVANCE`, `QUESTCOMPLETE`,
  `QUESTFAIL`).
- The Midgaard template ships "Fido trouble" (`data/quests.json`): the
  baker, placed in the Bakery from its prototype by `init_world`, wants
  five fidos for 250 experience and a loaf.
- Showcase 198, 199 and 200 are rebuilt as quest definitions; 201
  (branching) stays softcode, with a `custom` objective to put the fork in
  the journal; 067 notes that a bare `talk` still reaches `$talk`.
- Saved worlds: nothing stored changes; progress is two new attributes
  (`quests`, `quests_done`). A world gains the feature at its next start;
  an existing Midgaard database does not get the baker's quest
  (`init_world` runs once), and builds it as the guide shows.

### Clans with governments (step 14)

- New feature `clans` (in `CLASSIC`, after `clock`; requires nothing, and
  must come after `basics` and `rules`), after CoffeeMud's clans
  ([Clans](docs/guides/clans.md); Decision D7). Governments are data:
  `clan_government_def` objects (`feature.def_kind("clan_government", ...)`)
  with ordered positions (`id`, `name`, `plural`, `rank`, `max` as a number
  or a percentage, `lock`, `public`, `powers`), `accept_position`,
  `applicant_position`, `required_lock`, `auto_promote` (`none`, `rank`,
  `level`, `xp`, `gold`), `category`, `rivalrous`, `vote_days`,
  `vote_quorum`, `xp_per_level`, `benefits`, `on_join`, `on_leave`. A
  definition naming an unknown power, with no positions or with an
  `accept_position` it lacks is refused, by name, when definitions load.
- New pack `clan-governments`: gang, guild, union, fellowship, anarchy,
  co-op, meritocracy and plutocracy, translated from
  `clangovernments.xml`; the scaffold's `init_world` and the Midgaard and
  space game examples import it. `import_pack` skips a
  `clan_government_def` already present, as it does classes and skills.
- Command `clan`: found (`CLAN_COST`, 10000; `CLAN_MIN_LEVEL`), apply,
  accept, reject, leave, assign, exile, info, who, governments, premise,
  motd, home, donate, recall, disband, votes, vote, deposit, withdraw,
  deposits, tax, donate xp, declare, relations. `clans` lists the active
  clans; `clantalk` (`ct`) is clan talk; `@clan create|delete|set|xp` for
  administrators. `cl` is now an alias of `close` and `@cl` of `@clone`,
  which they reached by prefix before `clan` and `@clan`.
- Votes: a power no position holds outright is voted on by the holders of
  `vote_assign` (assignments) or `vote_other`; decided early, else counted
  against `vote_quorum` after `vote_days` game days (the `clock` service's;
  an hour each without it), by a reaper.
- The treasury (through the `economy` service), a tax on experience and
  character-point awards (`CLAN_MAX_TAX`, 25; a filter on the `rules`
  service's `award_filters`), clan experience and levels, and level
  benefits (tags, check modifiers, pool maximums) applied as achievements
  are. New `GameSystem.spendable_award(player)` and `spend_award(player,
  amount)` for `clan donate xp` (unspent character points; Merc's
  experience toward the next level).
- Relations (`war`, `hostile`, `neutral`, `friendly`, `ally`), one-sided;
  softcode `clan_relation`, `clans_at_war`. Upkeep: `CLAN_MIN_MEMBERS`,
  `CLAN_MAX_MEMBERS`, `CLAN_DEATH_DAYS` (2160), `CLAN_OVERTHROW_DAYS`
  (952); the roster drops deleted characters when read.
- `who` shows a member's clan (and a public position's title). Softcode
  `clan`, `clan_position`, `clan_rank`, `clan_has_power`, `clan_level`,
  `clan_members` (read-only, so also in lock expressions:
  `clan(caller) == 'Ravens'`), `clan_add` and `clan_remove` (builders).
  Events `clan:on_join`, `clan:on_leave`, `clan:on_assign`,
  `clan:on_level`, `clan:on_talk` (hooks `CLANJOIN`, `CLANLEAVE`,
  `CLANASSIGN`, `CLANLEVEL`, `CLANTALK`).
- `channels` offers its delivery path as `world.services["channels"]`
  (`deliver`, `remember`); `basics` offers `recall`'s rules as
  `world.services["recall"]` (`to(player, room, session)`).
- Showcase 221 and 222 are rebuilt on the feature; 223 (elections) now
  chooses the `union` government.
- Saved worlds: nothing stored changes; a world gains the feature at its
  next start, and its governments with `@pack clan-governments` (or
  `realm pack import clan-governments`).

### Pets, charmed followers and mounts (step 13)

- New feature `companions` (in `CLASSIC`, after `social`; requires
  `social` and `effects`), after CoffeeMud's followers and ROM's pet shops
  and charm person ([Pets, Charm and Mounts](docs/guides/companions.md)).
  A companion is an NPC whose `master` attribute names a character;
  bonding also sets `following`, the `companion` tag and the `companion`
  behavior (a ward: it never acts hostile toward its master). Public
  `master_of`, `companions_of`, `set_master` (`realm.std.companions`);
  the `companion:on_bond` / `companion:on_release` events (`BOND`,
  `RELEASE` hooks); softcode `master`, `companions`, `set_master`,
  `release`.
- The companion limit (Decision D8): the `COMPANION_LIMIT_RULE` setting (a
  rule expression, `me` and `level` bound; CoffeeMud's
  `FORMULA_MAXFOLLOW`), else new `GameSystem.companion_limit` (2; Merc `1 +
  level // 10`); companions of companions count. `COMPANION_LEVEL_DIFF`
  (0, off) after CoffeeMud's `FOLLOWLEVELDIFF`.
- Commands `companions`, `order <name|all> <command>` (through the real
  dispatcher, as `@force`; refuses commands above `player`, `order`,
  `quit` and the `ORDER_REFUSED` setting), `dismiss`, `mount` (`ride`),
  `dismount`. `mo` is now an alias of `credits` (`money`), which it
  reached by prefix before `mount`.
- Companions in the room join their master's fights (new
  `CombatManager.assist`); a companion's kill pays its master (the death
  event still names the companion); a master who attacks its companion
  breaks the bond. They leave the world with a master who leaves play and
  come back at login; a charm ends instead; a companion whose master is
  deleted is released. `wandering` and `aggressive` leave an NPC with a
  `master` alone.
- Pet shops: the `shopkeeper` behavior's `sells_pets` and `pet_stock`
  (object ids); `list` shows "Pets for sale:", `buy` clones one and bonds
  it to the buyer, through the `companions` service. The ROM importer
  handles `ROOM_PET_SHOP` (the next room's mobs are the stock, priced
  `10 * level * level` silver); the refresh script takes `--room-flags
  3031=M`, and Midgaard's pet shop sells.
- Charm: the `charmed` timed effect (`turns_hostile`), applied by the
  abilities' new `charm` effect (`duration`, `per_level`, `level_check`,
  `save`); players only where the zone allows `pvp`. The `merc-classic`
  pack ships `charm person`.
- Mounts: a companion tagged `mount` is ridden by its master (`riding` /
  `ridden_by`, the `ridden` tag); "(riding a grey mare)" marks the rider
  and the room listing leaves the mount out; `no_mount` rooms, and
  `sector:inside` ones unless `MOUNTS_INDOORS`, refuse a rider; under Merc
  the mount pays each step from its `move` pool ("Your mount is too
  exhausted."), and a rider spends no food or water walking; sleeping,
  going down or being moved without the mount dismounts. New
  `GameSystem.mounted_modifiers(rider, mount)` (`{}`) reaches attack rolls.
- **Kernel seam** `feature.move_describer(fn)`: `(actor, direction,
  phase) -> str | None` for a walk's `leave`, `arrive` and `own` lines
  (`World.move_describers`, `realm.core.movement.move_line`). New
  `CommandDispatcher.resolve(line)`: the built-in command a line would
  run.
- Showcase 65 (a pet) and 158 (a mount) are rebuilt on the feature.
- Saved worlds: nothing stored changes; a world gains the feature at its
  next start. A database made from an earlier Midgaard keeps a pet shop
  keeper that does not sell pets until the area is imported again.

### Hunger, thirst and fatigue (step 12)

- `report` says only pools that recover on their own (hp, mana, move), not
  food and water.
- New feature `needs` (in `CLASSIC`, after `vitals`), after CoffeeMud's
  (Decision D6): `food` and `water` are down pools that do not refill on
  their own, `fatigue` an up pool. Every `NEEDS_INTERVAL` (4 s) an online,
  awake player loses food by its weight factor (`weight /
  NEEDS_BASE_WEIGHT`) and water by that times the room's thirst rate (1,
  plus `climate:hot`, `climate:dry`, `climate:windy`, minus `climate:wet`;
  the room's tags, else its zone masters'); walking costs one more
  interval. Administrators, characters tagged `no_needs` and `no_needs`
  zones are exempt. An empty pool counts `hungry_ticks` / `thirsty_ticks`
  with CoffeeMud's escalating reminders, and past `HUNGER_DEATH_HOURS`
  (12) / `THIRST_DEATH_HOURS` (6) spends the vital pool, so the ordinary
  death path runs. Hunger and thirst each halve recovery (a `vitals`
  multiplier); spent fatigue halves mana and movement recovery and says
  "You are exhausted.". Softcode `hungry(obj)`, `thirsty(obj)`. Settings
  `NEEDS_INTERVAL`, `FOOD_LOSS`, `WATER_LOSS`, `NEEDS_REMINDER_TICKS`,
  `HUNGER_DEATH_HOURS`, `THIRST_DEATH_HOURS`, `HUNGRY_AWARD`,
  `FATIGUE_SLEEP_RECOVERY`.
- Merc declares `food` and `water` (`MercSystem.pools`); `score` says "You
  are hungry." / "You are thirsty." at a quarter or less and no longer
  lists them as numbers (`pool_lines(obj, exclude=)`). New
  `GameSystem.stomach(obj)` (`FOOD_FULL` 500, `WATER_FULL` 1000, scaled by
  weight; settings of `rules`) and `fill_stomach(player)`, which
  `apply_baseline` and the `rules` login observer call.
- Awards: new `award(player, amount)` in `realm.std.rules.system`, which
  runs `world.services["rules"].award_filters` (new `RulesService`) before
  `GameSystem.grant_award`; the kill award goes through it. `HUNGRY_AWARD`
  (1.0) scales awards while hungry or thirsty.
- `eat` takes one `bite` of a food's `nourishment` into `food` (scaled by
  `FOOD_GAIN`), gone when the nourishment is; `drink` takes one `sip` (50)
  of a container's `liquid_remaining` into `water` (scaled by
  `WATER_GAIN`); a `fountain` never runs dry; `drink` alone drinks from a
  fountain here or a `water_source` room; a full stomach refuses more. New
  command `fill <container> [<fountain>]` (`items`); `fi` is now an alias
  of `firstaid`, which it used to reach by prefix. `restores` still mends
  any pool; a drink without a liquid still uses `charges`.
- The importer writes food's `nourishment` (hours × 20), a drink
  container's `liquid` (named from ROM's liquid table when old-format),
  `liquid_held` and `liquid_remaining` (units × 30), and tags fountains
  `fountain`, instead of `restores` and `charges`; the refresh script
  drops those, and the shipped Midgaard was refreshed with it.
- Showcase 137 now configures the feature (an enlistment terminal gives
  the pools, a ration pack, a tap, a canteen, a hot engine room, a
  `no_needs` lounge) instead of building meters in softcode.
- Saved worlds: a Merc character made before this has no `food` or
  `water`; it is given both, full, at its next login. Food and drink
  already in a database made from an earlier Midgaard keep their old
  `restores` and `charges` until the area is imported again: a loaf fills
  only its ROM hours (18 of 500), a cup 4 water a charge; fountains,
  already tagged `fountain`, work as fountains.

### Merc parity (step 11)

- Special procedures: the importer maps `spec_patrolman` too, and the
  town watch's `peacekeeper` gains `protect`: `spec_guard` imports with
  `protect="evil"` (also attacks the most evil fighter in a brawl),
  `spec_patrolman` with `"fights"` (breaks up any fight, the stronger side
  first), `spec_executioner` with none. The `#SPECIALS` reader no longer
  skips the line after a spec with no trailing comment (half the specials
  of such a file were lost). New `CombatManager.target_of(obj)` and
  `withdraw(obj)`.
- Player settings `autoloot`, `autogold`, `autosplit` (`combat`) and
  `autoexit`, `brief` (`look`). An NPC's money (`credits`) goes into its
  corpse; `get all from <corpse>` and `get gold from <corpse>` take it, and
  `look` shows it. `render_room(room, viewer, arrival=True)` is how a
  room reads on arriving (walk, follow, recall, respawn, login), which
  `brief` shortens. New `realm.std.items.inventory.take_all`, `take_money`.
- Groups: the kill award is divided by the new `GameSystem.share_award`
  (neutral: equal shares; Merc: by level) and each member then sees
  `on_kill`; `split <amount>` (`economy`, `split_money` on the economy
  service); `report` (`talk`) says the character's pools aloud.
- Looking around (`look`): `scan`, `exits`, `where`; `consider` asks the
  game system first (`GameSystem.consider`; Merc: ROM's level lines).
  `sc` is now an alias of `score`, `sp` of `spells` and `rep` of `reply`, since `scan`, `split` and `report` share their letters.
- Merc: `alignment` (-1000 to 1000, on `score`), moved by kills by Merc's
  rule; items tagged `anti_good`/`anti_evil`/`anti_neutral` zap off
  (`GameSystem.repels`, `zap`) when worn, wielded, or when a kill changes
  the wearer; an item's `level` is the least to wear or wield it
  (`wear_refusal`); `LEVEL_CAP` (50); class titles on `who`
  (`who_title`, each class's `titles`); `recall` halves `move` and costs
  25 experience out of a fight (`after_recall`).
- `recall` (`basics`): home, else the start room (it used to refuse
  without a home); refused in a `no_recall` room; in a fight it takes a
  `recall` check (`GameSystem.recall_refusal`) and leaves the fight; it
  shows the room it lands in.
- The importer writes a mob's money as `credits` (ROM's `wealth` / 100;
  the raw figure as `rom_wealth`, replacing `gold`), tags `anti_*` items
  and `no_recall` rooms; `scripts/dev/refresh_rom_items.py` does the same
  to a converted file, and the shipped Midgaard was refreshed with it.
- Saved worlds: nothing to run; nothing is stored differently. A
  database made from an earlier Midgaard keeps its mobs as they were (no
  money, guards without `protect`) until the area is imported again.

### Comfort (step 10)

- The pager: `Session.send_paged(text)` holds output longer than one screen
  (the player's `pagelength`, else the client's NAWS height, else the new
  kernel setting `PAGE_LENGTH`, 24; 0 off); the prompt becomes
  `[more: enter, b back, q quit]`, and enter, `b` and `q` drive it (any
  other line stops paging and runs). `help`, `who`, `@examine`, `skills`,
  `socials`, `config`, `alias`, channel history and `mail` page.
- The line editor (`realm.gateway.editor.open_editor`): `@edit
  <obj>/<attr>`, `@edit <obj>` and `@desc <obj>` (no `=`) edit a line at a
  time with `.l`, `.d N`, `.i N text`, `.r N text`, `.s`, `.q`, `.h`; saving
  goes through `@set`'s and `@desc`'s ops, and a script that will not run is
  saved with the warning and the editor stays open. `mail <player> =
  <subject>` and `mail/reply <n>` with no body write the letter in it.
  `@desc <obj>` with no `=` used to clear the description; `@desc <obj> =`
  still does.
- Aliases: `alias <word> = <command>` (`$1`..`$9`, `$*`), `alias`,
  `unalias`; kept on the character (`aliases`), at most `ALIAS_LIMIT` (50);
  expanded once, never over an `@` word.
- Player settings (audit G7): `config` lists and sets `color`,
  `pagelength`, `prompt`, `screenreader` (no color, no decoration lines)
  and `palette` (`r=m b=c`); features add settings through
  `world.services["options"]` (`realm.std.basics.options.Option`). Settings
  live on the account when there is one (`realm.core.options`:
  `get_option`, `set_option`, `clear_option`, `options_holder`); `color` and
  `prompt` now read from there. `ACCOUNT_TAG` moved from
  `realm.std.accounts.account` to `realm.core.options`.
- The input path is one function, `realm.server.world.route_input` (held
  pages, then a pending prompt or the editor, then the interceptors, then
  the dispatcher), used by the server, `Simulator.input` and
  `Simulator.submit_line` (which now runs interceptors too). An input
  interceptor may return a string to replace the line. A bare enter
  reaches the session only while paging; the editor's lines arrive as typed
  (`Session.raw_lines`). WebSocket text is no longer stripped before
  `submit_input`.
- Saved worlds: nothing to run. A character's own `color` and `prompt` move
  to its account the next time it enters play.

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
  by default when this step shipped; `"respawn"` since Decision D1, see
  "The maintainer's decisions" above): a player who dies leaves `corpse of <name>` with what they
  carried (not `soulbound` items), locked to them for `CORPSE_LOCK_SECONDS`,
  pays `GameSystem.on_death` (Merc: a quarter of a level's experience) and
  wakes at home at 1 point.
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
