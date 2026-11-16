# REALM MUD Plan

A staged plan to take REALM from "an engine with a combat demo" to a MUD
system a developer can open to players: pick a rules system, start the
server, and build, with no large piece of a normal MUD missing.

It follows `KERNEL_PLAN.md` (finished 2026-11-14, version 0.2.0) and is
held to the same rules: `VISION.md`, the feature API, the public API and
the boundary tests.

Execute the steps **in order**. Tick boxes as work lands. Every step ships
on its own and leaves the suite green.

| # | Step | Size | Status |
|---|------|------|--------|
| 1 | Starting points: `--system`, and templates that are full scaffolds | S | [x] |
| 2 | The solo loop: regeneration, rest, recovery, death, movement cost | M | [x] |
| 3 | The character sheet: equipment, skills, prompt, consumables | M | [x] |
| 4 | Skills you can use: ability commands and the Merc class skills | M | [ ] |
| 5 | Progression: use, practice, idle training, timed actions | L | [ ] |
| 6 | Accounts: one login, many characters, account data, achievements, bans | L | [ ] |
| 7 | Communication: tells, channels, socials, mail | M | [ ] |
| 8 | The world clock: game time, day and night, weather | S–M | [ ] |
| 9 | Operating a live game: sessions, throttling, shutdown, backup, migrate | M | [ ] |
| 10 | Comfort: pager, editor, aliases | M | [ ] |
| 11 | Merc parity: the remaining Diku pieces | M | [ ] |
| 12 | Hunger, thirst and fatigue, after CoffeeMud | M | [ ] |
| 13 | Pets, charmed followers and mounts | M–L | [ ] |
| 14 | Clans with governments, after CoffeeMud | L | [ ] |
| 15 | Quests | M | [ ] |
| 16 | A browser client (optional, see Decision D3) | M | [ ] |
| 17 | Proof: the first hour, the guide, 0.3.0 | S | [ ] |

Steps 2 to 5 make one character playable alone. Step 6 is independent of
them and may be done at any point after step 1, but steps 7 and 9 assume
it (mail and bans are addressed to accounts). Steps 12 to 15 are the four
game systems that were softcode builds in the showcase and are now engine
features; each stands alone once its listed dependencies are done.

---

## What "complete" means here

The plan is finished when a developer can do the following on a fresh
install, and a test proves each line (step 17):

1. `realm init mygame --system merc --template midgaard`, `realm start`.
2. Create an account, then two characters on it.
3. Play one character alone from level 1 to level 2: fight, be hurt,
   recover by resting, die, come back, loot, sell, wear what was bought,
   and see all of it on `score`, `equipment` and the prompt.
4. Use a class skill by name (`kick fido`), improve a skill by using it,
   spend practices at a guildmaster, and leave a skill training while
   logged out.
5. Talk to another player in another room (`tell`, a channel), and leave
   mail for one who is offline.
6. Earn an achievement on one character and see its effect on the other.
7. As an administrator: ban an account, reset a password, announce a
   shutdown, back the database up, and restore it.
8. Grow hungry, eat, and stop being hungry.
9. Buy a pet that follows and fights for the character, and ride a horse
   that pays the movement cost.
10. Found a clan under a chosen government, accept a member, speak on
    its channel, and pass a door locked to it.
11. Take a quest from an NPC, see it in the journal, finish it and be
    paid.
12. Build onto the world in softcode with no restart, as today.

It does not mean every Diku feature. The non-goals are listed below so
nobody builds them by accident.

## Non-goals

- **A MOBprog transpiler.** ROM mob programs stay unconverted on import.
  They are a language port, not a mapping, and softcode replaces them.
- **Clan conquest, trophies, clan items and the rest of CoffeeMud's clan
  extras.** Step 14 takes its governments, positions, powers, votes,
  treasury, tax, levels and declared relations. It leaves out conquering
  areas, trophies, enchanted clan items, ordering underlings about, the
  morgue, clan journals, calendars and web pages. A declared war is a
  fact softcode can read; who may attack whom stays the `crime` feature's
  and the zone's business.
- **Deities and kinship.** CoffeeMud's theocracy and family governments
  need them. The guide shows how a game builds either with position
  locks.
- **Drunkenness, encumbrance, elections, branching-quest tooling.** These
  stay softcode builds in `docs/showcase/` (139, 136, 223, 201), on top of
  the engine systems this plan adds.
- **A web site or REST API** (capability audit G1), Discord or email
  bridges (G5). Step 16 is only a play client.
- **A second database backend.**

## Decisions for the maintainer

Each has a default. Use the default if nobody answers, and record it in the
Decision log.

- **D1. What happens when a player's vital pool is spent.** Default: the
  engine default stays `unconscious` (now with natural recovery, step 2),
  and the Merc scaffold and the Midgaard template set
  `PLAYER_DEATH = "respawn"` (a corpse with the character's belongings, the
  character returns to its home at 1 hit point, the rules system applies
  its penalty).
- **D2. How many characters an account may hold.** Default:
  `MAX_CHARACTERS = 5`. An account with exactly one character enters play
  straight after `connect`; otherwise the account menu is shown.
- **D3. Whether to ship a browser client** (step 16). Default: yes, one
  static page served beside the existing WebSocket protocol.
- **D4. Whether a sleeping character can hear the room.** Default: no
  speech or room messages reach a sleeper except tells, which wake nobody
  but are delivered.
- **D5. Where learn-by-use applies by default.** Default: Merc uses it for
  every skill (the SMAUG hybrid: practice to a floor, use to the cap);
  GURPS and D20 stay point-buy. Per-skill `progression` overrides either.
- **D6. Which games have hunger and thirst.** *Decided 2026-11-14:* Merc
  only, with CoffeeMud's mechanics (step 12): the `needs` feature acts on
  whoever has the `food` and `water` pools, and only `MercSystem` gives
  them to its characters.
- **D7. Who may found a clan.** *Decided 2026-11-14:* a clan system like
  CoffeeMud's, with different forms of leadership (step 14). Following
  CoffeeMud, a player founds a clan for `CLAN_COST` and chooses its
  government; setting `CLAN_COST = None` leaves founding to
  administrators.
- **D8. How many companions a character may have.** *Decided 2026-11-14:*
  configurable, by a formula a game writes in `config.py`
  (`COMPANION_LIMIT_RULE`), as CoffeeMud derives it from charisma; else
  the game system's hook; else two (step 13.1).

---

## How to work this plan

**Baseline when this plan was written**

- Commit `4adc058` (2026-11-14) plus an uncommitted `README.md`. `pytest -q`
  reports **2716 passed**. `ruff check realm/` reports **14** findings; do
  not add new ones.
- Find code by function name, not line number. Names in this plan were
  checked against that commit.

**Rules for whoever executes a step**

1. One step at a time. Start with a clean tree and a green suite
   (`source venv/bin/activate && pytest -q`).
2. Run the suite after every task, in both orders (`pytest -q` and
   `pytest -q -p no:randomly`). Never tick a box on a red suite.
3. Test first. Write the test that pins the new behavior, watch it fail for
   the right reason, then make it pass. A test that passes on its first run
   must be shown able to fail.
4. No compatibility shims and no re-exports. When a name moves, fix every
   use in `realm/`, `tests/`, `docs/` and `scripts/`.
5. Fail loudly (VISION invariant 10). A collision or an unknown name
   raises, or logs at WARNING with the fix in the message.
6. Docs are part of done. Each step lists the docs it touches. After
   changing softcode functions, events or settings, run
   `python scripts/gen_softcode_docs.py` and
   `python scripts/gen_config_docs.py`.
7. The maintainer commits. Do not commit. End each task with a suggested
   commit message, with no co-author or tool attribution line.
8. When the code disagrees with this plan, stop and write the deviation in
   the **Decision log** at the bottom before continuing. Do not quietly
   build a different design.
9. Saved worlds keep loading. A step that changes how something is stored
   says how an existing database is carried over, and tests it.

**Where new code goes**

Everything in this plan is a feature or part of one. Nothing here belongs
in the kernel except the few seams named in the steps (each is marked
**Kernel seam**). The checklist for a new built-in feature `x`:

- [ ] A package `realm/std/x/`: `feature.py` declares it, the other
      modules are its parts, `__init__.py` lists its public names with
      `realm._exports.exports` (or `__all__: list[str] = []`).
- [ ] Its name in `CLASSIC` (`realm/std/__init__.py`). Position matters
      for observers and markers, which run in list order.
- [ ] Its row in `FEATURE_ALL` (`tests/test_public_api.py`) and, where the
      frozen lists in `tests/test_features.py` change (commands, observers,
      behavior ids, softcode names), an "added after the freeze" entry
      beside the existing ones.
- [ ] It imports another feature's parts only when it `requires` it.
      Otherwise it asks `world.services.get("name")` and copes with None
      (`tests/test_boundaries.py` enforces this).
- [ ] Its row in the built-in table of `docs/guides/features.md`, its
      settings in the regenerated `docs/reference/config.md`, and a line in
      `CHANGELOG.md` under a new `0.3.0` heading.

A Merc-only rule goes in `realm/games/merc/`, never in `realm/std/`.

**Vocabulary**

- **Pool**: a bounded number on an object (`realm/core/pools.py`,
  `docs/guides/pools.md`). The **damage pool** is where harm lands; the
  **vital pool** is the one whose spending means the object is down.
- **Settle**: `pools.settle(change)`, which announces a pool change and is
  where death and `ON_HITPRCNT` happen.
- **Game system**: the `GameSystem` subclass named by `GAME_SYSTEM`
  (`realm/std/rules/system.py`), reached as `get_world().rules`.
- **Definition object**: an in-world object tagged as data
  (`skill_def`, `ability_def`, ...), declared with `feature.def_kind` and
  read with `realm.defs.find_def`.
- **Account**: introduced in step 6: the thing a person logs in to, owning
  one or more characters.

---

## Step 1 — Starting points

**Goal.** `realm init` can produce any stock rules system on an empty
world, and a template game is a full scaffold, with a place for code and a
passing test.

**Depends on.** Nothing.

Today `realm init mygame` always inherits GURPS in `rules.py`; getting Merc
means editing two lines by hand. `realm init mygame --template midgaard`
copies `config.py` and the area file and nothing else: no `game.py`, no
`rules.py`, no test, no README, and its `config.py` names
`realm.games.merc.system.MercSystem` directly, so the game has no rules
class of its own to change.

### 1.1 `--system`

- [x] Add `--system gurps|d20|merc` to `realm init` (default `gurps`). It
      selects the class `rules.py` inherits and the import line above it.
      Keep `rules.py.template` valid Python: rewrite the two lines in
      `cmd_init` the way `_rewrite` already edits `config.py.template`.
- [x] The commented examples in `rules.py.template` name GURPS's
      `TEMPLATES`. Give each system its own example block (GURPS
      `TEMPLATES`, D20 `CLASSES`, Merc `MERC_CLASSES`), selected by
      `--system`.
- [x] `--system` with `--features social` or `--features bare` is an error
      that says those presets have no rules.
- [ ] With `--system merc`, `config.py` also gets
      `PLAYER_DEATH = "respawn"` once step 2 adds that setting (leave a
      note in the Decision log if step 1 lands first; add the line in 2.4).
- [x] Tests in `tests/test_init_scaffold.py`: for each system, scaffold
      into `tmp_path`, check `resolve_game_system` returns a `GameRules`
      whose base is that system, and run the scaffold's own `pytest` in a
      subprocess.

### 1.2 Templates are scaffolds

- [x] Give `realm/examples/midgaard/` and `realm/examples/spacegame/` their
      own `rules.py` (a `GameRules` subclass of `MercSystem` / `GurpsSystem`)
      and `game.py` (`feature = Feature("<name>")`, the three commented
      examples). Their `config.py` sets `GAME_SYSTEM = "rules.GameRules"`
      and `FEATURES = [*CLASSIC, "game"]`. The spacegame's `ships.py` stays.
- [x] `_init_from_template` copies the example, then writes
      `tests/test_game.py` and `README.md` from the scaffold templates when
      the example does not carry them.
- [x] `--template` and `--system` together are an error (the template
      decides).
- [x] `tests/test_midgaard_playable.py` and `tests/test_spacegame.py` load
      the examples; two games now define top-level modules named `rules`
      and `game`, so use the `clean_import_state` pattern from
      `tests/test_init_scaffold.py` wherever an example's `config.py` is
      loaded.
- [x] Extend the scaffold tests: each template scaffolds, its own `pytest`
      passes in a subprocess, and its start room is the example's (the
      Common Square, the docking bay).
- [x] `tests/test_packaging.py`: the wheel-only run uses
      `--template midgaard` as well as `spacegame`.

### Acceptance

- [x] `realm init a --system merc && cd a && pytest -q && realm features --check`
      succeeds, and `score` in that game speaks Merc.
- [x] `realm init b --template midgaard && cd b && pytest -q` succeeds and
      `b/` contains `game.py`, `rules.py`, `tests/test_game.py`, `README.md`.

### Docs

- [x] `README.md` "Pick a starting point": replace the hand-edit of
      `rules.py` with `--system merc`, and drop the sentence saying the
      template has no `game.py`.
- [x] `docs/getting-started/first-game.md`: `--system`.

---

## Step 2 — The solo loop

**Goal.** A character playing alone can be hurt, recover, be defeated and
carry on, without another player's help.

**Depends on.** Step 1 for the scaffold setting only.

Today nothing regenerates: hit points and mana only return through
`firstaid`, a `healer` NPC, a spell or a `regeneration` effect. The only
code that removes the `unconscious` tag is `cmd_firstaid`
(`realm/std/combat/commands.py`), so a player knocked out alone stays down
for good. There is no rest or sleep. Merc declares a `move` pool that
nothing spends.

### 2.1 Natural regeneration: the `vitals` feature

Create `realm/std/vitals/` (no `requires`).

- [x] **Design.** A character (player or `npc`) regains each of its
      declared down pools over time while out of combat. The amount per
      tick is the game system's to decide; without a `rules` feature it is
      a flat 1.
- [x] `GameSystem.regen(obj, pool_name) -> int` in
      `realm/std/rules/system.py`, neutral default
      `max(1, pool_max // 20)`. `MercSystem.regen` uses level and
      constitution for `hp`, intelligence or wisdom for `mana`, dexterity
      for `move`.
- [x] `vitals` keeps a set of object ids that are below max, fed by an
      observer on `pool:on_change` (add when below max, drop when full)
      and seeded once in `on_boot` by scanning cached characters. This
      avoids sweeping every NPC in the world every tick.
- [x] A `feature.reaper` sweeps that set every `REGEN_INTERVAL` seconds (a
      new setting, default 15): for each character not tagged `in_combat`,
      `pools.mend` each declared down pool by
      `regen × position multiplier` (2.2) and `await pools.settle(...)`.
      An up pool (stress, heat) falls toward its floor the same way.
      An object may opt out with `no_regen` in its `pools` spec for that
      pool; add `regen: bool = True` to `Pool` and `SPEC_KEYS`.
- [x] `vitals` asks `world.rules` for the amount when it exists. It does
      not `require` rules: read `get_world().rules` and fall back to 1.
- [x] `vitals` offers a service (`world.services["vitals"]`) holding
      `multipliers`, a list of `(obj, pool_name) -> float` whose product
      scales each tick. The position multipliers of 2.2 are its first
      entries, and other features append their own (hunger, step 12).
- [x] Tests (`tests/test_vitals.py`): a hurt player regains hit points
      after one interval and stops at max; a fighter in combat does not; a
      ship's shields regain only if its spec allows; with `features=[...]`
      lacking `vitals` nothing regenerates; Merc's amounts differ by
      level.

### 2.2 Rest, sleep, stand, wake

In `vitals`.

- [x] Commands `rest`, `sleep`, `stand`, `wake` (alias `stand` for both
      ways up). Position is a tag: `resting` or `sleeping` (standing is
      neither). Regeneration multiplies by `REST_REGEN` (default 2) and
      `SLEEP_REGEN` (default 4), both settings.
- [x] A `feature.traversal_gate`: a resting or sleeping actor does not
      move ("You need to stand up first.").
- [x] A `feature.observer`: a hostile action (the `hostile` action tag)
      against a resting or sleeping character stands it up, with a line to
      the room.
- [x] A `feature.input_interceptor` for a sleeping player: every line
      except `wake`, `stand`, `help`, `who`, `score`, `quit`, `tell` and
      `reply` is answered "You are asleep." and consumed.
- [x] Decision D4: a `feature.sight_rule` hides everything but themselves
      from a sleeping viewer, and message delivery to a sleeper is
      suppressed for room audiences. **Kernel seam:** if
      `realm/core/propagation.py::deliver_messages` has no way to skip a
      recipient, add `World.deaf_rules` (a list of
      `(recipient, action) -> bool`) declared by `feature.deaf_rule`, and
      consult it in the one delivery function. Tells bypass it.
- [x] A `feature.marker` shows `(resting)` or `(sleeping)` in room
      listings.
- [x] Tests: each command and its refusal lines; moving while resting is
      refused; an attack stands the victim; a sleeper sees "You are
      asleep." for `look` and does not receive a `say` in the room.

### 2.3 Coming round

- [x] In `realm/std/combat/vitals.py`, add a third observer on
      `pool:on_change`: when the pool is the object's vital pool, the
      object is tagged `unconscious`, and the pool is no longer spent,
      remove the tag, tell the character "You come to." and the room that
      they stir. Delete the tag removal from `cmd_firstaid`: healing the
      vital pool above spent is what revives, through this observer.
- [x] Unconscious characters regenerate (2.1 does not skip them), so a
      lone player comes round after `REGEN_INTERVAL` or two.
- [x] Tests: knocked out by softcode `damage()`, a solo player is
      conscious again after regeneration ticks; `firstaid` and softcode
      `heal()` both revive through the observer; an unconscious player
      cannot move (the existing gate) until then.

### 2.4 Death and respawn

- [x] Add the value `respawn` to `WHEN_SPENT`
      (`realm/std/combat/manager.py`). It is allowed for players. In
      `handle_death` it:
  1. announces `combat:on_death` with `fatal` True (before the body
     changes, as now);
  2. leaves `corpse of <name>` in the room holding everything the
     character carried, except items tagged `soulbound`, with the `decay`
     behavior when registered, owned by the character so only they (and
     admins) pass its `get` lock for `CORPSE_LOCK_SECONDS` (a setting,
     default 300; 0 leaves it open);
  3. calls `rules.on_death(player, killer)` (new `GameSystem` hook,
     neutral: nothing; `MercSystem`: lose a quarter of the experience
     toward the next level, never a level);
  4. sets the vital pool to 1 with `pools.set_pool`, clears `in_combat`,
     `resting`, `sleeping` and timed effects, and moves the character to
     its `home`, else the start room, showing the room.
- [x] A setting on the `combat` feature, `PLAYER_DEATH`
      (`"unconscious"` or `"respawn"`, default `"unconscious"`), is what
      `when_spent(obj)` returns for a player with no `when_spent`
      attribute.
- [x] The Merc scaffold (1.1) and `realm/examples/midgaard/config.py` set
      `PLAYER_DEATH = "respawn"`.
- [x] The kill award is not paid for a player death.
- [x] Tests (`tests/test_death_observer.py`): under `respawn` a defeated
      player is in their home at 1 hit point, their sword is in the corpse
      where they fell, another player cannot loot it before the lock time
      and can after, Merc experience drops and the level does not;
      `ON_DEATH` fires once with `fatal` True.

### 2.5 Movement costs movement

In `realm/games/merc/feature.py`.

- [x] A `feature.traversal_gate` (reason `exhausted`): a player with a
      `move` pool spends the destination room's cost with `pools.spend`
      and is refused ("You are too exhausted.") when it cannot pay. Cost
      is the room's `move_cost` attribute, else by its `sector:<name>` tag
      (the ROM importer writes these): inside 1, city 2, field 2, forest
      3, hills 4, mountain 6, water 4; default 1. NPCs and fleeing actors
      are exempt. Settle the change.
- [x] Tests: walking drains `move`; a walk the pool cannot pay is refused
      and fires `event:on_fail` with reason `exhausted`; resting restores
      it; a GURPS world is unaffected.

### Acceptance

- [x] A scripted solo run on the Midgaard example
      (`tests/test_solo_loop.py`): a level-1 warrior fights a fido, loses
      hit points, rests to full, is killed by softcode damage, wakes in
      the Common Square with a corpse left behind, walks back and recovers
      the weapon.
- [x] No test or stock path leaves a lone player unable to act.

### Docs

- [x] New guide `docs/guides/life-and-death.md`: regeneration, positions,
      coming round, `PLAYER_DEATH`, `when_spent`, movement cost. Add it to
      `mkdocs.yml` under "Build your game".
- [x] `docs/guides/pools.md`: the `regen` setting and the new `respawn`
      row in the `when_spent` table.
- [x] `docs/guides/game-systems.md`: `regen` and `on_death`.
- [x] `README.md` "What is not built yet": remove what this step built.

---

## Step 3 — The character sheet

**Goal.** A player can see what they wear, what they know and how they are
doing without typing a command, and potions, food and wands do something.

**Depends on.** Step 2 for the pools the prompt shows.

Today worn items appear only as "(worn on head)" marks inside `inventory`,
one item per `db.slot` with no list of slots. There is no `skills` command
and no prompt (capability audit G10). The ROM importer tags potions,
scrolls, wands, food and drink, and nothing consumes them.

### 3.1 Equipment

In `realm/std/items/`.

- [x] `GameSystem.wear_slots() -> list[tuple[str, int]]`: slot names and
      how many items each holds. Neutral: `[]`, meaning any slot name, one
      item each (today's behavior). `MercSystem`: light, finger ×2, neck
      ×2, body, head, legs, feet, hands, arms, shield, about, waist, wrist
      ×2, held. `items` reads it through `world.rules` when present.
- [x] `cmd_wear` honors the count, replacing the oldest item in a full
      slot only when asked (`wear ring replace`), otherwise refusing with
      what is worn there.
- [x] New command `equipment` (alias `eq`): the slots in system order with
      what fills them, "nothing" for empty ones, and the wielded weapon.
      `inventory` stops listing worn and wielded items.
- [x] The ROM importer (`realm/tools/rom_import.py`) writes a `slot` from
      the object's wear flags using the Merc slot names; check the
      Midgaard area and regenerate it if slots are missing.
- [x] Tests: two rings on a Merc character, a third refused; `equipment`
      lists all slots; a GURPS world behaves as before.

### 3.2 Skills

In `realm/std/rules/`.

- [x] New command `skills` (alias `sk`): the character's trained skills
      with level, grouped by the skill definition's `group` attribute when
      it has one, and for each how it improves (step 5 fills this in;
      until then the level only). `score` stops listing skills.
- [x] Tests under GURPS, D20 and Merc.

### 3.3 The prompt

- [x] **Kernel seam.** `feature.prompt(fn, replace=False)`:
      `(player) -> str | None`, one per game, stored on
      `World.prompt_renderer`. The server (`GameServer._on_command`, and
      wherever output is flushed for a session outside a command) sends
      the rendered prompt after a batch of output for a session with a
      player, followed by telnet GA or EOR when the client negotiated it.
      A session in a softcode prompt or the pager (step 10) shows that
      prompt instead.
- [x] The `basics` feature declares the default: a template in the
      player's `prompt` attribute, else the `PROMPT` setting, default
      `"<{hp}/{max_hp}hp> "`. Tokens: every declared pool by name and
      `max_<name>`, `{name}`, `{room}`, `{combat}` (the opponent's
      condition word in a fight, else empty), and `{level}` and `{xp}`
      when the attributes exist. An unknown token is left as typed.
- [x] Command `prompt [template|default|off]`.
- [x] The Merc scaffold sets
      `PROMPT = "<{hp}hp {mana}m {move}mv> "`.
- [x] `Simulator.seen()` does not include prompts (they are not messages);
      add `Simulator.prompt(player)` for tests.
- [x] Tests: the default and a custom template; a prompt follows command
      output and follows unsolicited room output once, not per line; no
      prompt before login.

### 3.4 Consumables

- [x] In `items`: commands `eat` and `drink`. The target is tagged `food`
      or `drink`. Each fires a gated `item:on_eat` / `item:on_drink`
      (hooks `EAT`, `DRINK`), mends pools named in the item's `restores`
      attribute (`{"hp": 5}`), and then destroys food or lowers a drink
      container's `charges`. Softcode on the item still runs.
- [x] In `abilities`: commands `quaff <potion>`, `recite <scroll> [target]`
      and `zap <wand> [target]` (alias `brandish` for a `staff`, which
      targets the room). Each invokes the ability definitions named in the
      item's `spells` attribute through `invoke_ability` at the item's
      `spell_level`, with no cost and no class check, then destroys the
      potion or scroll or lowers `charges`.
- [x] The ROM importer writes `spells`, `spell_level` and `charges` from
      the object values for those item types, and `restores` for food and
      drink. Unknown spell names go to the capability-gap report.
- [x] Tests: quaffing a cure light potion heals and consumes it; a wand
      with no charges fizzles; reciting a scroll of fireball starts a
      fight like `cast` does; eating restores and removes the food.

### Acceptance

- [x] On the Midgaard example a new character can buy an item at a shop,
      `wear` it, see it under `equipment`, quaff a potion, and watch the
      prompt change as hit points move.

### Docs

- [x] `docs/guides/character-sheet.md`: slots, `equipment`, `skills`, the
      prompt tokens and `feature.prompt`. Add to `mkdocs.yml`.
- [x] `docs/guides/features.md`: the `feature.prompt` and
      `feature.deaf_rule` rows.
- [x] `docs/development/rom-import.md`: consumables and slots now convert.
- [x] Close capability audit G10.

---

## Step 4 — Skills you can use

**Goal.** A class skill is something a player types.

**Depends on.** Step 2.

Today an ability is reached only through `cast <spell>` or softcode
`use_ability()`. Merc classes start with `rescue`, `backstab`,
`shield_block` and `dodge` percentages that no code reads.

### 4.1 Ability names as commands

In `realm/std/abilities/`.

- [ ] A `feature.fallback`: when no command matches, look for an
      `ability_def` (not a `spell_def`; spells keep `cast`) whose name or
      one of its `aliases` is the typed verb and that `can_invoke` allows
      the player. If found, resolve the rest of the line as the target and
      call `invoke_ability(player, adef, target, verb=adef.name)`.
- [ ] Command `abilities` (alias `ab`): what the character can invoke, with
      cost.
- [ ] A cooldown cost: `{"cooldown": <beats>}` in a cost spec, alone or
      beside a pool cost. Store the ready time per ability on the actor
      (`ability_ready`, a dict) against the world's monotonic clock and
      refuse with "You are not ready to <name> again yet." (This is the
      "cooldown cost spec" deferred in BACKLOG.)
- [ ] An ability effect of type `check`: `{"type": "check", "skill": ...,
      "on_fail": "stop"}` rolls the actor's skill through `check()` before
      the effects after it. A failed check sends the definition's
      `fail_msg` and applies nothing more. This is what makes a skill miss.
- [ ] Tests: `kick fido` runs a `kick` ability; an unknown verb still
      reaches softcode `$`-commands; a cooldown refuses the second use and
      allows the third after the beats pass; a failed check deals no
      damage.

### 4.2 The Merc class skills

In `realm/packs/merc-classic/` (data) and `realm/games/merc/` (rules).

- [ ] `skills.json` in the pack: `kick` (warrior, barbarian; damage by
      level), `bash` (warrior; damage and a `stunned` modifier effect for
      one round), `backstab` (thief; needs a piercing weapon and a target
      not fighting; multiplied weapon damage), `rescue` (warrior; takes an
      attacker off an ally by retargeting the encounter participant),
      `disarm` (warrior, thief; unwields the target's weapon to the floor),
      `trip` (thief; `resting` position on the victim). Each has a `check`
      effect on the skill of the same name and a cooldown.
- [ ] `rescue` and `disarm` need more than an effect list. Give them an
      `on_invoke` softcode body if the softcode functions suffice;
      otherwise add softcode functions to `combat` (`retarget(attacker,
      new_target)`, `disarm(target)`), harm-gated.
- [ ] Passive defenses in `MercRuleset.roll_attack`: after a hit is
      rolled, the defender's `dodge`, then `parry` (wielding a weapon),
      then `shield_block` (wearing a shield) each get one percentile
      chance, scaled by level difference, to turn it aside, with its own
      message. Each is rolled through `check()` so step 5's learn-by-use
      applies.
- [ ] `second_attack` and `third_attack` for warriors as percentile
      chances of an extra swing in the encounter's attack resolution, via
      `Ruleset.resolve_special_maneuver` or a new `Ruleset.extra_attacks`
      hook, whichever keeps `CombatEncounter` free of Merc names.
- [ ] `MERC_CLASSES` starting skills match the pack's skill names.
- [ ] Tests on a Merc world: each skill's success and failure, class
      gating, the weapon requirement for backstab, a rescue that changes
      who the mob attacks, a dodge that turns a hit into a miss.

### Acceptance

- [ ] On Midgaard a level-1 warrior can `kick` and `bash`, a thief can
      `backstab` an unaware fido, and `abilities` lists exactly what each
      class can use.

### Docs

- [ ] `docs/guides/abilities.md`: abilities as commands, the `check`
      effect, cooldowns.
- [ ] `docs/guides/game-systems.md`: what Merc now implements.
- [ ] Regenerate the softcode reference.

---

## Step 5 — Progression

**Goal.** A game can make any skill improve by spending points, by practice
at a trainer, by being used, or by training over real time, and can mix
them skill by skill.

**Depends on.** Steps 3 and 4.

The design is already written: `docs/design/skills-inventory.md`, "Axis 3 —
Progression" and "The seams to build". Read it first. This step builds it.
Point-buy exists. Merc characters earn `practices` with nothing to spend
them on. Use and idle training are unbuilt.

The one invariant: whatever the model, it writes the plain `skill_<name>`
level, so `skill_level()` stays an attribute read and no ruleset changes.

### 5.1 The seam

In `realm/std/rules/`. Create `progression.py`.

- [ ] `progression_of(obj, skill) -> str`: the skill definition's
      `progression` attribute (`points`, `practice`, `use`, `idle`), else
      `GameSystem.default_progression` (a class attribute: `"points"` on
      `PointBuyMixin`, `"use"` on `MercSystem` per Decision D5, `None` on
      the neutral base, meaning skills do not improve).
- [ ] `GameSystem.skill_cap(obj, skill) -> int | None`: neutral None (no
      cap); Merc: a per-class maximum from the skill definition's
      `class_caps`, default 75 below the class's level-gate and 95 at it.
- [ ] `GameSystem.on_skill_used(obj, result) -> None`, called at the end of
      `check()` in `realm/std/rules/checks.py` and by nothing else. It is
      synchronous (so is `check()`); it may change attributes and call
      `obj.msg`, and may not propagate actions. The base implementation
      dispatches to the model: only `use` does anything here.
- [ ] Combat attack rolls do not pass through `check()` under Merc and
      D20. `CombatSystem.attack` reports them: after the attack roll it
      calls `rules.on_skill_used(attacker, CheckResult(...))` with the
      weapon's `skill` attribute (default `melee`) and the roll's success.
      Do it once in `CombatSystem`, not in each ruleset.
- [ ] Tests: the hook runs once per check and once per swing, with the
      right skill; a world with no `rules` feature is unaffected.

### 5.2 Learn by use

- [ ] The `use` model in `progression.py`: each use adds to
      `skill_xp_<name>`, more for a success than a failure, nothing when
      the roll could not fail or could not succeed. When it reaches
      `use_xp_needed(level)` (rising with level) the level goes up by one,
      the counter resets, and the character is told
      "You have become better at <skill>!". Nothing is gained at or above
      `skill_cap`. A skill at level 0 that the character was never taught
      does not improve by use unless its definition says
      `untrained_use = True`.
- [ ] A softcode route for a builder-authored curve: a `progress_rule`
      attribute on the skill definition, evaluated in the `rule` profile
      with `level`, `success` and `xp` bound, returning the experience to
      add. It mirrors `resolve_rule`.
- [ ] `skills` (3.2) shows progress toward the next level for `use` skills.
- [ ] Tests: repeated successful checks raise a skill; failures raise it
      more slowly; the cap holds; a combat skill rises from swings; a
      `progress_rule` replaces the curve; a `points` skill is untouched.

### 5.3 Practice

- [ ] Command `practice [skill]` in `rules`, usable in a room holding an
      NPC with the new `trainer` behavior (declare it in `rules`; params:
      `teaches`, a list of skill names or `"class"` for the character's
      class list; `max_level`, how far practice carries a skill, default
      a third of the cap). With no argument it lists what this trainer
      teaches and the character's levels. With one it spends a practice
      and raises the skill by an amount from the character's intelligence,
      up to the trainer's maximum.
- [ ] Command `train <stat>` at a trainer whose behavior has
      `trains_stats = True`: spends a `train` (Merc gives one per level
      besides practices) to raise a characteristic by one, to the class
      maximum.
- [ ] `MercSystem.advance_level` grants trains. The ROM importer attaches
      `trainer` to mobs with the ROM `ACT_PRACTICE` and `ACT_TRAIN` flags;
      regenerate Midgaard and check the guildmasters have it.
- [ ] Tests: practicing with and without a trainer; the practice floor;
      running out of practices; `train strength`.

### 5.4 Idle training

- [ ] The `idle` model: a character has `training` (a skill name) and
      `training_since` (a wall-clock timestamp). Accrual is computed
      lazily by `accrue_training(obj)`: skill points per minute from the
      skill definition's two governing attributes, levels bought at
      `idle_cost(level)`. It is called at login, by `skills` and `score`,
      at the start of any check of that skill, and by a `feature.reaper`
      sweep over online characters that announces "You have finished
      training <skill> to level N." Offline time counts. No timer runs
      while the player is away.
- [ ] Commands `study <skill>` (start; one skill at a time, needs
      `progression = idle` and any `requires` prerequisites on the
      definition) and `study stop`. `skills` shows the skill in training
      and when its next level lands.
- [ ] A cap on banked offline time: setting `IDLE_TRAINING_MAX_HOURS`
      (default 0, unlimited).
- [ ] Tests with an injected clock: eight hours offline raise a skill by
      the expected levels; the cap limits it; switching skills banks the
      first; a `use` skill refuses `study`.

### 5.5 Timed actions

For crafting, gathering and anything else that takes time at a place.
Create `realm/std/tasks/` (no `requires`).

- [ ] Softcode function `start_task(seconds, done_attr, label='',
      interrupt_attr=None)`: the enactor becomes busy (tag `busy`, a `task`
      attribute holding the label, finish time and the object and
      attributes to run). When the time passes, a `feature.reaper` clears
      it and runs `done_attr` on the object that started it, with the
      enactor bound. Unlike `wait()`, a task survives a reboot (it is
      stored on the character) and is tied to one character at one place.
- [ ] A task is interrupted, running `interrupt_attr`, when the character
      moves (an `after_traverse` hook), enters combat (an observer on
      hostile actions), or types `stop`. Starting a task while busy is
      refused. A `feature.marker` shows `(busy)`.
- [ ] Softcode functions `task_of(obj)` (read-only: the label and seconds
      left, or None) and `stop_task(obj)`.
- [ ] Rewrite showcase 122 (recipe crafting) to take time with
      `start_task`, and add a showcase build "a skill learned at the
      forge": a `smithing` skill definition with `progression = use`,
      raised by crafting, and a `metallurgy` skill with
      `progression = idle`. This is the worked example of mixing models.
- [ ] Tests: a task completes and runs its script; moving interrupts it;
      a task survives `Simulator` teardown and reload of the character; a
      second task is refused.

### Acceptance

- [ ] One Merc game runs all four models at once: `melee` by use,
      `lockpicking` by practice then use, a custom `herbalism` by idle
      study, and a GURPS game keeps buying skills with points. A test
      builds each and checks the level rises the way that model says.

### Docs

- [ ] New guide `docs/guides/progression.md`: the four models, how to set
      one per skill, caps, the trainer behavior, `progress_rule`, idle
      training, timed tasks. Add to `mkdocs.yml`.
- [ ] `docs/design/skills-inventory.md`: mark the seams built.
- [ ] `docs/guides/creating-your-own-system.md`: `default_progression`,
      `skill_cap`, `on_skill_used`.
- [ ] Regenerate the softcode and config references.
- [ ] `README.md` "What is not built yet": remove the progression bullet.

### Closes

- BACKLOG "Progression seam", "Idle training" and "Generic timed
  gather/craft action core" under the skill system entry, and the deferred
  cooldown cost spec.

---

## Step 6 — Accounts

**Goal.** A person logs in to an account that owns several characters.
Data and achievements on the account reach every one of them.

**Depends on.** Step 1. Independent of steps 2 to 5.

Today a login is a character: `AuthService` (`realm/std/accounts/auth.py`)
finds a `player`-tagged object by name and checks the `password` attribute
on it. There is nothing above the character to hold shared state, no
command to change a password, and no ban list (capability audit G12).

### 6.1 The account object

In `realm/std/accounts/`. Create `account.py`.

- [ ] An account is a `GameObject` tagged `account`, with no location. It
      holds `password` (the scrypt hash, already a protected attribute),
      `characters` (a list of character ids), `created`, `last_login`,
      `email` (optional), `banned_until` and `ban_reason`, and whatever a
      game adds. A character holds `account` (the account's id).
- [ ] Account names are unique among accounts, character names among
      characters. The two namespaces are separate.
- [ ] `account_of(character) -> GameObject | None` and
      `characters_of(account) -> list[GameObject]` in `account.py`, public
      through `realm.std.accounts.__all__`.
- [ ] The first account created on an empty database is the superuser's:
      the first character created on it gets the `god` tag, as the first
      character does today.
- [ ] Tests: creation, uniqueness, the links both ways, the hash is not
      readable from softcode.

### 6.2 Carrying existing worlds over

- [ ] A `feature.on_boot` step in `accounts`: every `player` object that
      has a `password` and no `account` gets an account of the same name
      holding that password, and the password attribute is removed from
      the character. It logs one INFO line per account made and is a no-op
      on the second boot.
- [ ] Tests: a store built the old way boots, the player can
      `connect <same name> <same password>`, and lands in the same
      character in the same room.

### 6.3 Login and the account menu

Rewrite `Accounts.handle_login` and its helpers in `login.py`.
`Session` gains an `account` field beside `player`.

- [ ] At the welcome screen: `connect <account> <password>` and
      `create <account> <password>`. `who` and `quit` as now.
- [ ] After `connect`: with exactly one character, enter play with it
      (Decision D2). Otherwise show the menu: the account's characters
      with level and class when the rules system has them, and the
      commands `play <name>`, `new <name>`, `delete <name>` (asks for the
      password again; refused for a character holding the `god` tag unless
      it is the last), `password`, `quit`.
- [ ] `new <name>` creates a character on the account, refuses past
      `MAX_CHARACTERS` (a setting, default 5), and starts the rules
      system's chargen exactly as `create` does today.
- [ ] After `create <account> <password>` the player is asked for a first
      character name and continues into chargen, so a new player still
      reaches the game in two prompts.
- [ ] In play: command `characters` returns to the menu without closing
      the connection (the character leaves the room as on `logout`).
      `logout` returns to the welcome screen.
- [ ] One account, one session in play at a time (a second login takes
      over, with a message to the old connection), unless
      `ACCOUNT_MULTIPLAY = True`, which allows one session per character.
- [ ] `password <old> <new>` in play and from the menu.
- [ ] The login rate limit in `AuthService` keys on the account name.
- [ ] Tests (`tests/test_accounts.py`): the whole menu; chargen from
      `new`; the character limit; switching characters; take-over; a wrong
      old password; every test that logged in as a character before now
      logs in to its account (`Simulator.player()` is unaffected: it makes
      a character with a session and no account unless asked;
      add `Simulator.account(name, *characters)`).

### 6.4 Account data in softcode

- [ ] Softcode functions, declared by `accounts`, group "Accounts":
      `account_attr(obj, name, default=None)` (read-only; the attribute on
      the character's account, None for a character with none),
      `set_account_attr(obj, name, value)` and
      `incr_account_attr(obj, name, by=1)`. The setters require the
      executor to control the character and are refused for the protected
      attributes and for anything flagged `system`. `account_characters(obj)`
      returns the names of the account's characters (read-only).
- [ ] Tests: a value set from one character is read from another on the
      same account and not from a stranger's.

### 6.5 Achievements

Create `realm/std/achievements/` (`requires=["accounts"]`).

- [ ] An achievement is a definition object tagged `achievement_def`
      (`feature.def_kind("achievement", "achievement_def")`): a name, a
      `description`, `hidden` (not listed until earned), `scope`
      (`account`, the default, or `character`), and `grants`: tags to add,
      and check modifiers by skill name or `"all"`.
- [ ] Softcode `grant_achievement(obj, name)` (builder-gated like other
      state-changing functions): records it with a timestamp in
      `achievements` on the account, or on the character for that scope,
      once. It fires `account:on_achievement` (hook `ACHIEVEMENT`, payload
      `achievement`), tells the player, and applies the grants.
      `has_achievement(obj, name)` is read-only.
- [ ] Applying grants: tags are added to every character of the account
      when the achievement is earned, and to each character at login
      (an observer on the connect event), so a character made later gets
      them. Check modifiers are answered by a `feature.check_modifier`
      that sums the earned achievements' modifiers for that skill; cache
      the sum per account and drop the cache when an achievement is
      granted or definitions reload (`feature.on_reload`).
- [ ] Command `achievements`: earned ones with dates, unearned visible
      ones, a count of hidden ones remaining.
- [ ] Tests: earned on one character, the tag and a +1 check modifier
      apply on a second character of the account after it logs in, and not
      on another account; a `character` scope stays put; granting twice
      does nothing; a hidden one is not listed.
- [ ] Rewrite showcase 207 (achievements) on top of this, keeping its
      softcode watchers as the thing that decides when to grant.

### 6.6 Bans and administration

- [ ] Command `@account <name>` (admin): shows the account, its
      characters, last login and address. Switches: `/password <new>`
      resets it; `/ban <duration> = <reason>` and `/unban`;
      `/boot` disconnects its sessions.
- [ ] `@sitelock <address-or-prefix> [= reason]`, `@sitelock/remove`,
      `@sitelock/list` (admin): stored on a singleton object tagged
      `sitelock_registry`. Checked when a connection opens and at
      `create`.
- [ ] `connect` refuses a banned account with the reason and expiry.
- [ ] Every ban, unban, password reset and sitelock change is logged at
      INFO on a `realm.admin` logger, naming who did it and to whom.
- [ ] Tests for each, including expiry with an injected clock.

### Acceptance

- [ ] `tests/test_accounts.py` and `tests/test_achievements.py` pass, and
      the migration test of 6.2.
- [ ] `git grep -n "db.password\|'password'" realm/` finds the attribute
      only in `accounts` and the protected-attribute tables.

### Docs

- [ ] New guide `docs/guides/accounts.md`: accounts and characters, the
      menu, the settings, account data in softcode, achievements with a
      worked example ("slay the banshee on any character, and every
      character gets +1 to will"), bans.
- [ ] `docs/getting-started/first-game.md` and `quickstart.md`:
      `create <account> <password>` and the first character.
- [ ] Every doc, tutorial chapter and showcase transcript that types
      `create Keeper mypassword` or `connect ...` (grep for both).
- [ ] `docs/architecture/sessions.md`: the account field and the menu
      state.
- [ ] `README.md` "What is not built yet": remove the accounts bullet.
- [ ] Regenerate the softcode and config references.

### Closes

- Capability audit G12. Showcase checklist item 178.

---

## Step 7 — Communication

**Goal.** Players can reach each other anywhere, and leave word for someone
who is not there.

**Depends on.** Step 6 (mail is addressed to characters and delivered to
accounts; channel preferences can be account-wide).

Today all speech is in the room: `say`, `pose`, `emit`, `ooc`, `shout`,
`whisper`.

### 7.1 Tells

Create `realm/std/channels/`.

- [ ] `tell <player> <message>` (alias `t`) and `reply <message>` (alias
      `r`) to the last teller. Delivered to an online player anywhere,
      refused for one who is offline (pointing at `mail`) or who has the
      teller in their `ignore` list. `tell` propagates an action
      (`comm:on_tell`, hook `TELL`) with the recipient as target and no
      room audience, so softcode can react and wards can veto.
- [ ] `ignore <player>`, `ignore` (list), `unignore <player>`.
- [ ] `afk [message]`: a tag and message; tellers are shown it.
- [ ] Tests: delivery across rooms, reply, ignore, offline, a ward that
      blocks tells in a silenced room.

### 7.2 Channels

- [ ] A channel is a definition object tagged `channel_def`: a name, an
      optional `alias`, a `speak` lock and a `listen` lock (so `immtalk`
      is admin-only by data), a `format` template, `history` size.
- [ ] Each channel name and alias is a command through a
      `feature.fallback` (`gossip hello`). `channels` lists them with
      on/off state; `channel <name> on|off` toggles; `channel <name>
      history` shows recent lines. Preferences are stored on the account
      when there is one, else the character.
- [ ] A message is one propagated action (`comm:on_channel`, hook
      `CHANNEL`, payload `channel`, `message`), delivered to every online
      listener who passes the listen lock and has it on.
- [ ] The `channels` content ships three by default in a small pack
      imported by the scaffold's `init_world`: `gossip`, `newbie`,
      `immtalk`.
- [ ] Softcode: `cemit(channel, text)` (builder-gated) and
      `channel_members(channel)` (read-only).
- [ ] Tests: speaking and hearing, locks, toggling, history, softcode.

### 7.3 Socials

In `realm/std/talk/`.

- [ ] A social is a definition object tagged `social_def` with up to five
      message templates (to the actor with no target, to the room with no
      target, to the actor with a target, to the target, to the room with
      a target), using the existing `{actor}` and `{target}` formatting.
- [ ] A `feature.fallback` runs a social whose name is the typed verb.
      `socials` lists them.
- [ ] Ship a pack of the common Diku socials (smile, nod, bow, laugh, wave,
      shrug, and so on; at least forty) as `realm/packs/socials-classic/`.
      The ROM importer may later read `#SOCIALS`; not in this step.
- [ ] Tests: with and without a target, an unseen actor reads as
      "Someone", a social named like a real command never shadows it.

### 7.4 Mail

Create `realm/std/mail/` (`requires=["accounts"]`).

- [ ] Messages are objects tagged `mail` held by the recipient's account
      (not in any room), with `sender`, `to`, `subject`, `body`, `sent`,
      `read`.
- [ ] Commands: `mail` (list), `mail <n>` (read), `mail <player> =
      <subject>/<body>` (send; the body may use the editor of step 10 when
      it exists), `mail/delete <n>`, `mail/reply <n> = <body>`. Sending to
      a character delivers to that character's account.
- [ ] At login a player is told how many unread messages wait. An online
      recipient is told when mail arrives.
- [ ] A limit per account (`MAIL_LIMIT`, default 100) and softcode
      `send_mail(to, subject, body)` for system mail (builder-gated).
- [ ] Tests: send to an offline player, read after login, delete, the
      limit, system mail.

### Acceptance

- [ ] Two players in different rooms hold a conversation by `tell` and on
      `gossip`; one logs out; the other mails them; the first logs in and
      reads it.

### Docs

- [ ] New guide `docs/guides/communication.md`. Add to `mkdocs.yml`.
- [ ] `docs/guides/features.md`: rows for `channels` and `mail`; the
      `talk` row gains socials.
- [ ] Regenerate the softcode reference.

---

## Step 8 — The world clock

**Goal.** The world has a time of day, a calendar and weather that
builders can react to.

**Depends on.** Nothing in this plan (uses the `sight` feature).

Today `time` prints the server's wall clock.

Create `realm/std/clock/`.

- [ ] Game time derives from elapsed real time since an epoch stored on a
      singleton object tagged `world_clock`, at `GAME_TIME_RATIO` game
      seconds per real second (a setting, default 30, so a game day lasts
      48 real minutes). A calendar from settings: `HOURS_PER_DAY`,
      `DAYS_PER_MONTH`, `MONTH_NAMES`, `DAY_NAMES`. The clock keeps running
      across restarts because it is derived, not counted.
- [ ] Softcode, read-only: `game_time()` returns hour, day, month, year,
      and `time_of_day()` returns one of dawn, day, dusk, night.
- [ ] A `feature.reaper` notices when the hour changes and fires
      `time:on_hour` (hook `HOUR`, payload `hour`) and, at the four
      boundaries, `time:on_dawn`, `on_day`, `on_dusk`, `on_night`, on each
      zone master and each room holding a player, so softcode can light
      lamps and open shops without a ticker per object.
- [ ] Day and night: a room tagged `outdoors` is dark at night. Implement
      it as a `feature.sight_rule` plus the room-lit answer, asking the
      `sight` service; without `sight`, night changes nothing.
      **If** `sight.room_is_lit` cannot be extended from another feature,
      add a list of extra darkness tests to the `sight` service that
      `clock` appends to, rather than importing `sight` from `clock`.
- [ ] Weather per zone: a zone master with a `weather` attribute (a list
      of states with weights, or a softcode expression) gets a current
      state rolled each game hour, stored on the master, announced to
      outdoor rooms in the zone when it changes, and readable with
      `weather(here)`. No effect on rules; builders hook it.
- [ ] Commands `time` (game time first, server time after) and `weather`.
      The ROM importer tags non-`inside` sectors `outdoors`.
- [ ] Tests with an injected clock: the calendar, the hour event firing
      once per hour, an outdoor room dark at night and lit by a torch, a
      weather change announced outdoors and not indoors.

### Docs

- [ ] New guide `docs/guides/time-and-weather.md`. Add to `mkdocs.yml`.
- [ ] `docs/design/time-and-beats.md`: the third clock.

---

## Step 9 — Operating a live game

**Goal.** An administrator can keep a public server healthy and recover
from a bad day.

**Depends on.** Step 6.

- [ ] **Idle and link-dead sessions.** Settings `IDLE_TIMEOUT` (minutes;
      0 off; admins exempt) and `LINKDEAD_SECONDS` (default 120). A
      connection that drops without `quit` leaves the character in the
      room tagged `linkdead` (a marker shows it) for that long, during
      which a new `connect` resumes it in place; then it is removed from
      the room as on logout. A character in combat when the link drops
      keeps fighting with its default action.
- [ ] **Flood control** (capability audit G13). **Kernel seam** in the
      session input path: a per-session token bucket
      (`COMMAND_RATE`, `COMMAND_BURST` settings); over the limit, input is
      dropped with one warning line, and a session that stays over it for
      `FLOOD_DISCONNECT_SECONDS` is closed and logged.
- [ ] **Presence in softcode** (G4): `online_players()`, `idle_seconds(obj)`
      (read-only). `who` shows idle time, the `afk` and `linkdead` marks,
      and hides players the viewer cannot see. `basics` offers a service
      (`world.services["who"]`) holding `fields`, a list of
      `(viewer, player) -> str | None` callables whose answers are shown
      beside a name; class titles (step 11) and clan tags (step 14) are
      entries in it.
- [ ] **Announce and stop.** `@wall <message>` (admin) to every session.
      `@shutdown [seconds] [= reason]` and `@shutdown/cancel`: counts down
      with announcements, saves everything, stops the server cleanly.
      `@reboot` does the same and exits with a status a supervisor can
      restart on (document the systemd unit).
- [ ] **Snoop and freeze.** `@snoop <player>` (admin; logged on
      `realm.admin`; the target's
      output is echoed to the admin) and `@freeze` / `@thaw` (a frozen
      player's input is refused with a notice).
- [ ] **Backup.** `realm backup [file]` copies the live database with
      SQLite's online backup API (safe while the server runs) to
      `data/backups/<name>-<timestamp>.db` by default, and
      `realm backup --keep N` prunes older ones. A setting
      `BACKUP_INTERVAL_HOURS` (default 0, off) makes the server do it.
      `realm restore <file>` refuses while the server is running.
- [ ] **Migrate.** `realm migrate`: `PersistenceManager` already stamps
      `PRAGMA user_version` and refuses a newer schema. Add an ordered
      list of migration functions keyed by version, run by
      `realm migrate` (and refused at `realm start` with a message telling
      the operator to run it, never run silently). The account conversion
      of 6.2 stays a boot step because it changes objects, not the schema.
- [ ] Tests for each: sessions with an injected clock, the token bucket,
      a backup taken during writes that restores to the same object count,
      a migration from a version-1 file.

### Docs

- [ ] New guide `docs/guides/operations.md`: settings, the admin commands,
      backup and restore, running under systemd, upgrading. Add to
      `mkdocs.yml`.
- [ ] Close capability audit G4 and G13 and the BACKLOG `realm migrate`
      entry.

---

## Step 10 — Comfort

**Goal.** Long output is readable, long text is editable, and players can
shorten what they type.

**Depends on.** Step 3 (the prompt).

- [ ] **Pager** (BACKLOG "Output pager"). **Kernel seam** on `Session`:
      `send_paged(text)`. Output longer than the client's reported height
      (NAWS when negotiated, else `PAGE_LENGTH`, default 24, per-player
      `pagelength` attribute, 0 off) is held; the prompt becomes
      "[more: enter, b back, q quit]" and the next line of input drives
      it. `help`, `@examine`, `who`, `skills`, `socials`, channel history
      and mail use it.
- [ ] **Editor** (BACKLOG "In-game multiline text editor"). `@edit
      <obj>/<attr>` and `@edit <obj>` for the description open a line
      editor as a session input handler: append lines, `.l` list, `.d N`
      delete, `.i N text` insert, `.r N text` replace, `.s` save, `.q`
      quit without saving, `.h` help. Softcode attributes are validated on
      save the way `@set` validates them. `mail` and `@desc` with no text
      open it.
- [ ] **Aliases.** `alias <word> = <command line>`, `alias` (list),
      `unalias <word>`: stored on the character, expanded by an
      `input_interceptor` before dispatch, with `$1`..`$9` and `$*`, no
      recursion, and never over a word that begins with `@`.
- [ ] **Per-player display options** (capability audit G7): `config`
      command listing and setting `color`, `pagelength`, `prompt`,
      `autoloot` and the rest (step 11 adds toggles), stored on the
      account when there is one.
- [ ] Tests for each, including the pager and editor through
      `Simulator.submit_line`.

### Docs

- [ ] `docs/guides/world-management.md`: `@edit`.
- [ ] A short "Player settings" section in `docs/guides/character-sheet.md`.
- [ ] Close the two BACKLOG entries and audit G7.

---

## Step 11 — Merc parity

**Goal.** A converted ROM area plays the way a Diku player expects.

**Depends on.** Steps 2 to 5.

Read "MERC parity: the punch list" in `docs/development/rom-import.md`
first; it ranks what is left from a run over 189 real area files.

- [ ] **Special procedures.** Apply the `rom_spec:* -> behavior` table
      under "Behavioral spec_procs" in that guide: `spec_thief` to the
      `steal` behavior, `spec_guard` / `spec_patrolman` /
      `spec_executioner` to `guard`, `spec_poison` to `venomous`,
      `spec_fido` and `spec_janitor` to `scavenger` (with a corpse-eating
      parameter for the fido). Anything new and Merc-only goes in
      `realm/games/merc/behaviors.py`. The importer attaches them; the
      faction and bespoke procedures stay in the capability-gap report.
- [ ] **Player toggles**: `autoloot`, `autogold`, `autosplit`, `autoexit`,
      `brief`, read by the death path, the party award and the room
      renderer through attributes, set with `config` (step 10).
- [ ] **Group play**: experience from a kill is split by level among party
      members in the room (`MercSystem`), `split <amount>` shares coins,
      `group` is an alias of `party`, and `report` says the character's
      pools aloud.
- [ ] **Looking around**: `scan` (who is one room away in each direction,
      respecting sight), `exits` (the long form), `where` (players in the
      same zone), `consider` using level difference under Merc.
- [ ] **Alignment**: an `alignment` attribute moved by kills of good and
      evil mobs (the importer already reads it), shown on `score`, and
      checked by equipment tagged `anti_good` / `anti_evil` /
      `anti_neutral` (the item zaps off when worn).
- [ ] **Level limits and titles**: `LEVEL_CAP` (default 50), a class title
      per level band shown on `who`, item level restrictions on `wear`.
- [ ] **Recall**: `recall` spends half the `move` pool under Merc and is
      refused in a room tagged `no_recall` and in combat without a check.
- [ ] Regenerate the Midgaard area with every importer change in this
      plan and update `tests/test_midgaard_playable.py`.
- [ ] Tests for each item on a Merc world.

### Docs

- [ ] `docs/development/rom-import.md`: rewrite the punch list as what
      converts now, and what still does not (MOBprogs).
- [ ] `docs/guides/game-systems.md`: a "What Merc implements" table.
- [ ] `README.md` "What is not built yet": the Merc bullet shrinks to
      MOBprogs.

---

## Step 12 — Hunger and thirst

**Goal.** A game that wants survival needs has them as a stock system,
modeled on CoffeeMud's: a stomach that empties with time and exertion,
food eaten a bite at a time, thirst that depends on the climate, slower
recovery while hungry or thirsty, and death only after a long time
ignored.

**Depends on.** Steps 2 (regeneration, sleep) and 3 (`eat`, `drink`).

Today this exists only as a softcode build (showcase 137), which each game
must copy and maintain.

**The CoffeeMud model this follows** (`~/CoffeeMud`: `coffeemud.ini`
`HUNGER`, `THIRST` and the `FORMULA_*RECOVER` entries;
`Libraries/MUDFight.java::expendEnergy`; `Common/DefaultCharState.java`;
`Locales/StdRoom.java::thirstPerRound`). Read those before starting.

- A stomach holds 500 units of food and 1000 of drink by default, scaled
  by body weight.
- Every tick an awake, mortal character loses food in proportion to its
  weight, and water in proportion to its weight times the room's thirst
  rate: one, plus one each for a hot, dry or windy climate, minus one for
  a wet one. Walking spends the same again.
- At zero the character is told so at intervals, in rising alarm (hungry,
  famished, starved, near death), and dies after twelve real hours hungry
  or six thirsty.
- Being hungry removes half of each recovery (hit points, mana, movement)
  and being thirsty removes the other half. Fatigue, a third need, builds
  while awake, falls while asleep, and halves mana and movement recovery.

Create `realm/std/needs/` (no `requires`).

### 12.1 The pools

- [ ] Hunger and thirst are two pools, `food` and `water` (down pools:
      full at max, spent at 0, `regen=False`), so everything that works on
      pools works on them: the prompt can show them, softcode can read
      them, an item can fill them. Fatigue is a third, `fatigue` (an up
      pool, `regen=False`). A character has a need exactly when it has
      that pool.
- [ ] The game system decides who has them (Decision D6):
      `MercSystem.pools()` adds `food` and `water`, and its baseline gives
      a new character full ones. GURPS and D20 do not. No stock system
      declares `fatigue`; a game adds it in its own `pools()`. NPCs are
      never given any of them.
- [ ] Capacity. Settings `FOOD_FULL` (default 500) and `WATER_FULL`
      (default 1000) are the base maximums. `GameSystem.stomach(obj) ->
      tuple[int, int]` returns the character's two maximums; the neutral
      answer scales the settings by `weight / NEEDS_BASE_WEIGHT` (a
      setting, default 150) when the character has a `weight` attribute
      and returns them unscaled when it does not.

### 12.2 Losing them

- [ ] A `feature.reaper` runs every `NEEDS_INTERVAL` seconds (a setting,
      default 4, CoffeeMud's tick) over online players who have the pools.
      It skips a sleeping character (2.2), an admin, a character tagged
      `no_needs`, and a room whose zone sets `no_needs`. For the rest it
      harms `food` by the weight factor and `water` by the weight factor
      times the room's thirst rate, both scaled by the `FOOD_LOSS` and
      `WATER_LOSS` settings (percentages, default 100), and settles.
      Fractions accumulate on the character (`food_debt`, `water_debt`) so
      a light character still gets hungry.
- [ ] The thirst rate of a room is 1, plus 1 for each of the tags
      `climate:hot`, `climate:dry` and `climate:windy`, minus 1 for
      `climate:wet`, never below 0. The tags are read from the room, else
      from its zone masters (`zone_property`).
- [ ] Exertion: an `after_traverse` hook charges one more interval's loss
      for each room walked.
- [ ] `fatigue` rises by 1 per interval while awake and falls by
      `FATIGUE_SLEEP_RECOVERY` (default 3) per interval while asleep.
- [ ] Offline time does not count for any of them.

### 12.3 Going without

- [ ] While `food` or `water` is spent the character accumulates
      `hungry_ticks` / `thirsty_ticks` (reset to 0 the moment the pool is
      above 0). Every `NEEDS_REMINDER_TICKS` (default 60) the player is
      told, by how far along they are toward the death limit: "You are
      hungry." in the first half, "You are famished! Eat something!" past
      half, "You are starved! Eat something!" past three quarters, and
      "You are starved, and near death. EAT SOMETHING!" on each of the last
      30 ticks; the thirst lines are thirsty, parched, dehydrated.
- [ ] Death. Settings `HUNGER_DEATH_HOURS` (default 12) and
      `THIRST_DEATH_HOURS` (default 6) of online time. Past the limit the
      character is told "YOU ARE DYING OF HUNGER!" and its vital pool is
      spent through `pools.harm` and `settle`, so the ordinary death path
      of 2.4 runs, with no killer. 0 disables death from that need.
- [ ] Slower recovery. `needs` appends a multiplier to the `vitals`
      service's list (2.1): 1.0, less 0.5 while hungry, less 0.5 while
      thirsty, so a character that is both recovers nothing; and, for the
      `mana` and `move` pools only, half again while `fatigue` is spent.
      Without `vitals` this part is skipped.
- [ ] `HUNGRY_AWARD` (default 1.0): a factor on experience and character
      point awards while hungry or thirsty. 1.0 changes nothing; a game
      that wants CoffeeMud's "no experience while hungry" sets 0. To apply
      it, give the `rules` feature one small seam: `award(player, amount)`
      in `realm/std/rules/system.py`, which passes the amount through
      `award_filters` (a list of `(player, amount) -> int` on the `rules`
      service) and then calls `GameSystem.grant_award`. The death path and
      quest rewards call `award`, never `grant_award` directly. `needs`
      appends a filter; clan tax (14.4) appends another.
- [ ] When `fatigue` is spent the player is told "You are exhausted." at
      the reminder interval. Nothing else happens; sleep cures it.

### 12.4 Eating and drinking

- [ ] Food carries `nourishment` (how much it holds in all) and `bite`
      (how much one `eat` takes; default: all of it). `eat` moves one bite
      into `food`, scaled by the `FOOD_GAIN` setting (a percentage,
      default 100), and destroys the item when its nourishment is gone.
      Eating when full is refused ("You are too full to eat more.").
      This replaces the `restores = {"food": n}` form for food in 3.4;
      `restores` stays for other pools (a potion that restores `hp`).
- [ ] A drink container carries `liquid`, `liquid_held` and
      `liquid_remaining`, and `sip` (default 50). `drink` moves one sip
      into `water`, scaled by `WATER_GAIN`, and lowers what remains. An
      object tagged `fountain` never runs dry. `fill <container>
      <fountain>` refills. A room tagged `water_source` (a river, a
      well) can be drunk from with `drink` alone.
- [ ] The ROM importer writes `nourishment` for food from its value,
      `liquid`, `liquid_held` and `liquid_remaining` for drink containers
      from the liquid table, and tags fountains. Regenerate Midgaard.

### 12.5 Showing it

- [ ] `score` under Merc says "You are hungry." and "You are thirsty."
      the Diku way when a pool is at a quarter or less, and does not list
      `food` and `water` as numbers beside hit points.
      `MercSystem.score_lines` does this itself; `pool_lines` gains an
      `exclude` argument so it can leave the pools out. The neutral sheet
      lists them like any pool.
- [ ] Softcode, read-only: `hungry(obj)` and `thirsty(obj)`.
- [ ] Rewrite showcase 137 to configure this feature instead of building
      the meters by hand.
- [ ] Tests (`tests/test_needs.py`, with an injected clock): the pools
      fall over time, faster for a heavy character, and only for online,
      awake players who have them; a hot dry room doubles thirst and a wet
      one removes it; walking costs extra; the reminder lines escalate;
      death arrives at the limit through the normal death path and not at
      all when the setting is 0; hunger and thirst each halve
      regeneration; a bite at a time empties a loaf; a fountain is not
      consumed; fatigue rises awake and falls asleep; a GURPS character is
      never hungry; a `no_needs` zone is exempt.

### Docs

- [ ] A "Hunger, thirst and fatigue" section in
      `docs/guides/life-and-death.md`, with the settings and the climate
      tags, and a note on where the numbers come from.
- [ ] `docs/guides/features.md`: the `needs` row.
- [ ] `docs/development/rom-import.md`: food, drink and fountains.
- [ ] Regenerate the softcode and config references.

---

## Step 13 — Pets, charmed followers and mounts

**Goal.** A character can own a creature that follows, obeys and fights
for it, can charm one for a while, and can ride one.

**Depends on.** Steps 2 (movement cost) and 4 (ability effects).

Today the parts exist and the system does not. Following is one attribute
(`following`, `realm/std/social/party.py`) and the `social` feature brings
followers through exits. Softcode `force()` makes something you control
run a command. Showcase 65 (a pet) and 158 (a mount) and tutorial chapter
13 (an enthrall spell) each assemble those by hand.

Create `realm/std/companions/` (`requires=["social"]`).

### 13.1 Companions

- [ ] **Design.** A companion is an NPC with a `master` attribute holding
      a character's id. That is the whole relationship: it does not change
      who owns or controls the object for building purposes. A companion
      follows its master (the existing `following` attribute is set with
      it).
- [ ] `master_of(obj)`, `companions_of(character)`,
      `set_master(npc, character | None)` in `companions.py`; public names
      of the package.
- [ ] The limit (Decision D8), after CoffeeMud's `FORMULA_MAXFOLLOW`
      (`1 + (charisma - 6) / 3` in its `coffeemud.ini`, evaluated in
      `Libraries/CharCreation.java::getMaxFollowers`). Three layers, first
      one that answers wins:
  1. the setting `COMPANION_LIMIT_RULE`, a rule expression (the softcode
     `rule` profile, like `resolve_rule`) with `me` bound to the
     character and `level` to its level, so a game writes
     `"1 + (get_attr(me, 'charisma', 10) - 6) // 3"` in `config.py`;
  2. `GameSystem.companion_limit(character) -> int`, for a system that
     wants code;
  3. the neutral answer, 2.

      `MercSystem.companion_limit` is `1 + level // 10` (Diku has no
      charisma). The count is CoffeeMud's `totalFollowers`: each companion
      plus that companion's own companions. `set_master`, buying a pet
      (13.2) and a charm that lands all refuse past the limit, with a
      line saying so. `companions` ends with "You have 1 of 3 followers."
- [ ] `COMPANION_LEVEL_DIFF` (a setting, default 0, off), after
      CoffeeMud's `FOLLOWLEVELDIFF`: a creature more than that many levels
      above the character cannot be bonded.
- [ ] Commands: `companions` (list, with condition), `order <name|all>
      <command>`, `dismiss <name>`. `order` runs the command as the
      companion through the real dispatcher (the mechanism `@force` uses),
      and refuses any command whose permission is above `player`, `order`
      itself, and `quit`; a game narrows it further with the
      `ORDER_REFUSED` setting (a list of command names).
- [ ] Fighting together. An observer on hostile actions: when a master
      attacks or is attacked, each of its companions in the room joins
      the encounter on its side, through the `combat` service (do not
      import `combat`; without it companions only follow). A kill by a
      companion is credited to its master: `CombatManager._npc_death`
      asks the `companions` service for the killer's master before paying
      the award, and the death event's killer stays the companion.
- [ ] Leaving and returning. When the master logs out, companions with a
      `master` are taken out of the world with it (location None, their
      room remembered) and come back beside the master at login. A
      companion whose master is deleted is released.
- [ ] A dead companion leaves the list. A companion never attacks its
      master while the relationship holds (a check ward on hostile
      actions, declared by the feature).
- [ ] Softcode: `master(obj)` and `companions(obj)` read-only;
      `set_master(obj, master)` and `release(obj)` for builders. Events
      `companion:on_bond` and `companion:on_release` (hooks `BOND`,
      `RELEASE`).
- [ ] Tests (`tests/test_companions.py`): bonding and the limit from
      each of its three layers, including a charisma rule and a companion
      that has companions of its own; the level difference; `order` runs a
      command and refuses an admin one; a companion follows through
      an exit, joins its master's fight, and its kill pays the master; it
      leaves and returns with the master across logout.

### 13.2 Pets from shops, and charm

- [ ] A shopkeeper with `sells_pets = True` (a parameter on the existing
      `shopkeeper` behavior in `realm/std/economy/shop.py`, read through a
      service so `economy` does not import `companions`) sells clones of
      the creatures in its `pet_stock` list: `list` shows them, `buy
      <pet>` clones one, bonds it to the buyer and charges the price.
- [ ] The ROM importer handles `ROOM_PET_SHOP`: the mobs reset into the
      following room become the shop's `pet_stock`. Midgaard's pet shop
      must sell after regeneration.
- [ ] A timed effect behavior `charmed` (in `companions`, built on
      `TimedEffectBehavior` through the `effects` service or by requiring
      `effects`; choose and record): while it lasts the target has the
      caster as master; when it expires the bond is released and, with
      `turns_hostile = True`, the creature attacks its former master.
      Players cannot be charmed unless the zone allows it
      (`zone_property(room, "pvp")`).
- [ ] `charm person` in `realm/packs/merc-classic/`: an ability whose
      effect applies `charmed`, with `save = negates` and a level check.
- [ ] Tests: buying a pet; the charm lasting and expiring; a saved target;
      the limit shared between pets and charmed creatures.

### 13.3 Mounts

- [ ] A companion tagged `mount` can be ridden. Commands `mount <name>`
      (alias `ride`) and `dismount`. Riding is one attribute each way:
      `riding` on the rider, `ridden_by` on the mount. A mount carries one
      rider; a rider rides one mount; nobody mounts in combat; a rider who
      falls unconscious, sleeps or dies is dismounted.
- [ ] Moving. The mount follows as any companion does. Where a game
      charges movement (2.5), the cost is paid from the mount's `move`
      pool instead of the rider's: the Merc traversal gate asks the
      `companions` service who pays. A mount with no movement left
      refuses to go ("Your mount is too exhausted.").
- [ ] **Kernel seam.** Movement lines are fixed strings in
      `realm/core/movement.py` ("{actor} leaves north.", "{actor}
      arrives."). Add `feature.move_describer(fn)`:
      `(actor, direction, phase) -> str | None`, `phase` being `leave` or
      `arrive`, stored on `World.move_describers`; the first non-None
      answer replaces the room line. `companions` declares one:
      "{actor} rides north on a grey mare." The actor's own line follows
      the same hook. This seam also serves sneaking and flying later.
- [ ] A `feature.marker` shows `(riding a grey mare)` on the rider and
      hides the mount's own line from room listings while ridden (a sight
      rule is wrong here: the mount is visible; use the room renderer's
      grouping hook or a `ridden` marker and record the choice).
- [ ] Rooms tagged `no_mount` (and, by default, rooms with the
      `sector:inside` tag when `MOUNTS_INDOORS` is False) refuse a mounted
      traveler through a `feature.traversal_gate`.
- [ ] `GameSystem.mounted_modifiers(rider, mount) -> dict` (neutral
      empty): a hook for a ruleset that wants a to-hit or defense change
      while mounted. Merc leaves it empty.
- [ ] A mount shop is a pet shop whose stock is tagged `mount`.
- [ ] Rewrite showcase 65 and 158 on top of this feature.
- [ ] Tests: mounting rules; a ride through two rooms shows the riding
      line and drains the mount's movement, not the rider's; a `no_mount`
      room refuses; being knocked out dismounts.

### Docs

- [ ] New guide `docs/guides/companions.md`: pets, orders, charm, mounts,
      the settings and the softcode functions. Add to `mkdocs.yml`.
- [ ] `docs/guides/features.md`: the `companions` row and
      `feature.move_describer`.
- [ ] `docs/tutorial/13-the-enthrall-spell.md`: a closing note pointing at
      the stock `charmed` effect.
- [ ] Regenerate the softcode and config references.

---

## Step 14 — Clans

**Goal.** Players can found and run organizations the way CoffeeMud lets
them: a clan chooses a form of government, the government says which
positions exist and what each may do, and some decisions are taken by
vote.

**Depends on.** Steps 6 (accounts, for last-login times), 7 (channels)
and 8 (the game calendar, for vote and upkeep periods), and the `economy`
feature through its service.

Today this is two softcode builds (showcase 221 and 222) with fixed ranks.

**The CoffeeMud model this follows** (`~/CoffeeMud`:
`resources/clangovernments.xml`, the `Clan.Function` enum and the
relation constants in `Common/interfaces/Clan.java`, and the `CLAN*`,
`MINCLAN*`, `MAXCLAN*` and `DAYSCLAN*` entries of `coffeemud.ini`). Read
`clangovernments.xml` before starting; the stock governments below are a
translation of it.

- A government is data: an ordered list of positions, each with a name, a
  rank, a limit on how many may hold it, a mask saying who qualifies, and
  the powers it grants.
- Eleven governments ship: a gang ruled by one boss, a guild with several
  masters, a union with elected leaders, a fellowship where everything is
  voted on, a theocracy, a family, an anarchy, a profession, a co-op, a
  meritocracy ruled by whoever has given the clan the most experience,
  and a plutocracy ruled by whoever has given it the most money.
- The top position can be filled by appointment, by rank, by level, by
  experience donated or by money donated.
- Clans have a treasury, a tax on members' experience, their own
  experience and levels with benefits at each level, declared relations
  with other clans, and upkeep rules that dissolve dead clans and replace
  absent leaders.

Create `realm/std/clans/` (no `requires`; `economy`, `basics`, `channels`,
`accounts` and `clock` are reached through services).

### 14.1 Governments as data

- [ ] A government is a definition object tagged `clan_government_def`
      (`feature.def_kind("clan_government", "clan_government_def")`):

      | Attribute | Meaning |
      |---|---|
      | `description` | one line, shown when a founder chooses |
      | `positions` | an ordered list, highest rank first (below) |
      | `accept_position` | where an accepted applicant lands |
      | `applicant_position` | where someone who has applied waits; None means anyone who applies is in at once |
      | `required_lock` | a lock expression: who may apply at all |
      | `auto_promote` | how the top position is filled: `none`, `rank`, `level`, `xp` or `gold` (below) |
      | `category` | a character may belong to one clan per category; default `""` |
      | `rivalrous` | whether clans of this kind may declare relations |
      | `vote_days`, `vote_quorum` | how long a vote stays open, in game days, and the percentage of eligible voters needed |
      | `xp_per_level` | a rule expression over `level` giving the clan experience for the next clan level |
      | `benefits` | a list of `{level, tags, check_mods, pool_max}` granted to members once the clan reaches that level |
      | `on_join`, `on_leave` | softcode run for a member joining or leaving |

- [ ] A position is a dict: `id`, `name`, `plural`, `rank` (0 is highest;
      two positions may share a rank), `max` (holders allowed; None for no
      limit), `lock` (a lock expression a holder must pass, for example a
      class), `public` (whether outsiders see who holds it) and `powers`.
- [ ] The powers, each a string: `accept`, `reject`, `assign` (promote and
      demote), `exile`, `set_home`, `set_donate`, `premise`, `motd_write`,
      `motd_read`, `withdraw`, `deposit`, `deposit_list`, `tax`,
      `declare` (relations), `channel`, `list_members`, `home_privs`,
      `benefits`, `titles`, `vote_assign` and `vote_other`. A definition
      naming any other power is refused when definitions load.
- [ ] A power no position holds outright is decided by vote (14.3):
      assignments among holders of `vote_assign`, everything else among
      holders of `vote_other`. A power that nobody holds and nobody can
      vote on cannot be used in that government, and the command says so.
- [ ] `auto_promote`: `none` leaves the top position to appointment or
      vote. `rank` fills a vacant top position with the longest-serving
      member of the next rank down. `level` gives it to the highest-level
      qualifying member, `xp` to whoever has donated the most experience
      and `gold` to whoever has donated the most money, re-evaluated
      whenever those change, displacing the holder.
- [ ] Ship the governments as a pack, `realm/packs/clan-governments/`,
      imported by the scaffold's `init_world`: `gang`, `guild`, `union`,
      `fellowship`, `anarchy`, `co-op`, `meritocracy` and `plutocracy`,
      with the positions, limits and powers of the CoffeeMud file.
      `theocracy`, `family` and `profession` depend on deities, kinship
      and class grants that REALM does not have; describe in the guide how
      a game builds them with position locks, and do not ship them.
- [ ] Tests: each shipped government loads and validates; a malformed one
      (unknown power, no positions, an `accept_position` that does not
      exist) is refused with its name.

### 14.2 The clan and its members

- [ ] A clan is an object tagged `clan`, with no location: `name`,
      `government` (the definition's name), `members` (character id to
      `{position, joined, donated_xp, donated_gold}`), `premise`, `motd`,
      `treasury`, `home` and `donate_room` (room ids), `tax` (a
      percentage), `xp`, `level`, `relations` (clan name to relation),
      `status` (`pending` or `active`) and `founded`. A character has a
      `clans` attribute mapping category to clan id.
- [ ] Founding (Decision D7). `clan found <name> = <government>`: costs
      `CLAN_COST` (a setting, default 10000) through the `economy`
      service, needs `CLAN_MIN_LEVEL` (default 1), and makes the founder
      the holder of the top position. With `CLAN_COST = None` only
      `@clan create <name> = <government>, <leader>` (admin) founds one. A
      clan is `pending` until it has `CLAN_MIN_MEMBERS` (default 1)
      members; a pending clan cannot declare relations or levy a tax.
- [ ] Joining: `clan apply <clan>` (refused by `required_lock`, by
      `CLAN_MAX_MEMBERS` when not 0, and when the character already has a
      clan in that category), `clan accept <player>` and `clan reject
      <player>` for holders of those powers, `clan leave`.
- [ ] Positions: `clan assign <member> = <position>` (the `assign` power,
      or a vote), refused when the position is full or the member fails
      its lock; nobody assigns a position at or above their own rank
      unless they hold the top one. `clan exile <member>`.
- [ ] Information: `clan` (your clans), `clan info <clan>` (premise,
      government, level, public position holders), `clan who` (roster by
      position, online first; needs `list_members`), `clans` (every active
      clan with its government and size), `clan governments` (what a
      founder may choose, with descriptions).
- [ ] Text and places: `clan premise = <text>`, `clan motd = <text>`
      (shown to members at login to those with `motd_read`), `clan home`
      and `clan donate` set from the room the holder stands in, and `clan
      recall` takes a member with `home_privs` to the clan home under the
      same rules as `recall`.
- [ ] `clan disband` by the top position, after confirmation; the treasury
      returns to the holder.
- [ ] Tests: founding with and without the cost; the whole life of a
      member in a `gang` (apply, accept, assign, exile) and each command
      refused without its power; a full position refused; a position lock
      refusing an unqualified member; two categories at once and a second
      clan in one category refused.

### 14.3 Voting

- [ ] An action that must be voted on opens a vote stored on the clan:
      what is proposed, by whom, when it closes (`vote_days` game days
      from now), and the ballots. `clan votes` lists open votes; `clan
      vote <n> yes|no` casts or changes a ballot; the proposer may
      withdraw one.
- [ ] A vote passes as soon as more than half of all eligible voters have
      said yes, and fails as soon as that is impossible. Otherwise it is
      counted when it closes: it passes with a majority of ballots cast if
      at least `vote_quorum` percent of eligible voters voted. A passed
      vote carries out its action as if a holder of the power had typed
      it; either outcome is announced on clan talk and to the proposer.
- [ ] A `feature.reaper` closes votes that have run out. Game days come
      from the `clock` service (step 8); in a game without `clock`, one
      game day is counted as one real hour, and the guide says so.
- [ ] Tests with an injected clock: a `fellowship` assigns its leader by
      vote; early pass, early fail, quorum failure at the deadline; a
      member without `vote_assign` cannot vote on an assignment; a `gang`
      never opens a vote.

### 14.4 Treasury, tax, levels and benefits

- [ ] `clan deposit <amount>` and `clan withdraw <amount>` against the
      `economy` service, by power; without `economy` the commands say the
      treasury is unavailable. Each deposit adds to the member's
      `donated_gold`. `clan deposits` (the `deposit_list` power) shows who
      has given what.
- [ ] `clan tax <percent>` (the `tax` power; at most `CLAN_MAX_TAX`,
      default 25). While set, that share of every experience or
      character-point award a member earns goes to the clan's `xp` and to
      the member's `donated_xp` instead of to the member. `clans` appends
      a filter to the `rules` service's `award_filters` (12.3).
      `clan donate xp <amount>` gives directly, where the rules system has
      spendable experience or points.
- [ ] Clan levels: when `xp` reaches the government's `xp_per_level` for
      the next level, the clan's `level` rises and members are told.
- [ ] Benefits: each `benefits` entry at or below the clan's level grants
      its tags, check modifiers and pool-maximum bonuses to members whose
      position has the `benefits` power. Apply them the way achievements
      are applied (6.5): tags at login and when the level or membership
      changes, check modifiers through a `feature.check_modifier` with a
      cache dropped on those same changes. Removing a member removes the
      tags.
- [ ] `auto_promote` of `xp` and `gold` is re-evaluated after every
      donation and tax payment.
- [ ] Tests: deposit and withdraw by power; tax diverting a share of a
      kill award; a clan reaching level 2 and its members gaining the
      benefit, and losing it on exile; a `plutocracy` changing leader when
      someone out-donates the holder.

### 14.5 Relations

- [ ] `clan declare <clan> = war|hostile|neutral|friendly|ally` (the
      `declare` power, or a vote; both clans must be `rivalrous` and
      active). The relation is one-sided as declared; `clan relations`
      shows both sides. An alliance holds only when both have declared it.
- [ ] Read-only softcode `clan_relation(a, b)` returns the relation of
      clan `a` toward `b`, and `clans_at_war(a, b)` is true when either
      has declared war. These are for builders and for a game's own
      player-killing rules; the engine attaches no combat consequence
      (see Non-goals).
- [ ] Tests: declaring, the alliance needing both sides, a pending clan
      refused, softcode reading it.

### 14.6 Upkeep

- [ ] A `feature.reaper`, on a slow cadence, using members' last login
      from their accounts:
  - dissolves a clan when fewer than `CLAN_MIN_MEMBERS` of its members
    have logged in within `CLAN_DEATH_DAYS` (a setting in game days,
    default 2160; 0 disables), returning nothing and announcing it;
  - replaces the holders of the top position when every one of them has
    been absent for `CLAN_OVERTHROW_DAYS` (default 952; 0 disables), with
    the highest-ranking qualifying member who has logged in recently.
- [ ] The roster prunes itself: a member id that no longer resolves to a
      character is dropped the next time the roster is read, so deleting a
      character (6.3) needs no call into `clans`.
- [ ] Tests with an injected clock for both rules and for pruning.

### 14.7 Talk, who, locks and softcode

- [ ] Clan talk: `clantalk <message>` (alias `ct`) for members whose
      position has the `channel` power: one propagated action
      (`clan:on_talk`, hook `CLANTALK`) delivered to online members, with
      history. Build it on the channel delivery code of 7.2 through the
      `channels` service; without it the command says clan talk is
      unavailable. A member of clans in two categories names the clan:
      `ct <clan> <message>`.
- [ ] `who` shows the clan name and, for a public position, its title:
      `clans` appends an entry to the `who` service's `fields` list
      (step 9).
- [ ] Read-only softcode, also available in lock expressions: `clan(obj,
      category='')` (the clan's name or None), `clan_position(obj)` (the
      position id), `clan_rank(obj)` (the rank number, 0 highest),
      `clan_has_power(obj, power)`, `clan_level(name)` and
      `clan_members(name)`. A hall door is
      `@lock door = clan(enactor) == 'Ravens'`; an armory is
      `clan_has_power(enactor, 'home_privs')`.
- [ ] Builder-gated softcode `clan_add(obj, name, position=None)` and
      `clan_remove(obj, name)`. Events `clan:on_join`, `clan:on_leave`,
      `clan:on_assign`, `clan:on_level` (hooks `CLANJOIN`, `CLANLEAVE`,
      `CLANASSIGN`, `CLANLEVEL`).
- [ ] Admin: `@clan create`, `@clan delete <name>`, `@clan set
      <name>/<field> = <value>`, `@clan xp <name> = <amount>`.
- [ ] Rewrite showcase 221 and 222 to use the feature. Showcase 223
      (elections) becomes an example of choosing the `union` government.
- [ ] Tests: clan talk reaching only members with the power; a door
      locked by clan, by rank and by power; the softcode functions.

### Acceptance

- [ ] `tests/test_clans.py` passes, and one test founds a clan under each
      shipped government and checks who can and cannot do each of:
      accept a member, assign a position, withdraw from the treasury.

### Docs

- [ ] New guide `docs/guides/clans.md`: founding, the shipped governments
      in a table (who rules, how the top position is filled, what is
      voted on), positions and powers, voting, the treasury and tax,
      levels and benefits, relations, upkeep, the settings, the softcode
      functions, and how to write a government of your own, with a
      theocracy as the worked example. Add to `mkdocs.yml`.
- [ ] `docs/guides/features.md`: the `clans` row.
- [ ] Regenerate the softcode and config references.

---

## Step 15 — Quests

**Goal.** A builder defines a quest as data, and the engine tracks it:
who has it, how far along they are, and what they get.

**Depends on.** Steps 5 (awards), 6 (achievements and account scope) and
13 (kills by a companion count).

Today showcase 198 to 200 build a quest master, a delivery and a counter
in softcode, each tracking its own state.

Create `realm/std/quests/` (no `requires`; rules, economy and
achievements are reached through `world.rules` and services).

### 15.1 The definition

- [ ] A quest is a definition object tagged `quest_def`
      (`feature.def_kind("quest", "quest_def")`):

      | Attribute | Meaning |
      |---|---|
      | `description` | shown when offered and in the journal |
      | `giver` | the NPC that offers and accepts it back; None for one taken anywhere |
      | `accept_lock` | a lock expression over the player (level, class, a quest already done) |
      | `stages` | an ordered list; each has `text` and `objectives` |
      | `rewards` | `award` (through the game system's `grant_award`), `credits`, `items` (prototypes to clone), `achievement`, `tags` |
      | `repeatable` | False, or the seconds before it may be taken again |
      | `time_limit` | seconds to finish, or None |
      | `scope` | `character` (default) or `account`: done once per account |
      | `on_accept`, `on_stage`, `on_complete`, `on_fail` | softcode run at each point |

- [ ] Objective kinds, each a dict with `kind`, a `count` (default 1) and
      a matcher: `kill` (a name, a tag or a `prototype_vnum`), `collect`
      (items held; `consume = True` takes them at turn-in), `deliver` (an
      item given to an NPC), `visit` (a room id or tag), `talk` (an NPC),
      `use` (an object), and `custom` (a key advanced only from softcode).
- [ ] A definition is validated when definitions load
      (`feature.on_reload` and boot): an unknown objective kind, a stage
      with no objectives or a reward naming a missing prototype is an
      error naming the quest.

### 15.2 Tracking

- [ ] A character's progress is in two attributes: `quests`
      (`{quest: {"stage", "counts", "accepted", "deadline"}}`) and
      `quests_done` (`{quest: timestamp}`); for `scope = account` the
      second lives on the account.
- [ ] One `feature.observer` turns events into progress: `combat:on_death`
      for `kill` (credit goes to the killer, to the killer's master when
      it is a companion, and to party members in the room), `item:on_get`
      and `item:on_give` for `collect` and `deliver`, the room-entry event
      for `visit`, `item:on_use` for `use`. Keep an index of which online
      characters have an active objective of each kind, so the observer
      returns at once for an action nobody is waiting on.
- [ ] `talk <npc>` is a new command in this feature (it fires
      `quest:on_talk`, hook `TALK`, which NPC softcode may also answer),
      and it advances `talk` objectives.
- [ ] Finishing the last objective of a stage moves to the next, shows
      its text and runs `on_stage`. Finishing the last stage completes the
      quest at once when it has no giver, else marks it ready to hand in.
- [ ] A `feature.reaper` fails quests past their deadline and runs
      `on_fail`.
- [ ] Events `quest:on_accept`, `quest:on_advance`, `quest:on_complete`,
      `quest:on_fail` (hooks `QUESTACCEPT`, `QUESTADVANCE`,
      `QUESTCOMPLETE`, `QUESTFAIL`).

### 15.3 Players and builders

- [ ] Commands: `quests` (alias `journal`: active quests with the current
      stage and counts; `quests done` for the history), `quest <name>`
      (detail), `quest list` (what the givers in this room offer you),
      `quest accept <name>`, `quest complete <name>` (at the giver),
      `quest abandon <name>`.
- [ ] The behavior `quest_giver` (parameter `quests`, a list of names). A
      `feature.marker` shows `(!)` beside a giver with something to offer
      the looker and `(?)` beside one waiting for a hand-in.
- [ ] Softcode: read-only `quest_state(obj, quest)` (None, a stage number,
      `'ready'` or `'done'`) and `quest_count(obj, quest, key)`;
      builder-gated `quest_offer`, `quest_advance(obj, quest, key, by=1)`,
      `quest_complete` and `quest_fail`. `quest_state` is available in
      lock expressions, so a door can open to those who finished a quest.
- [ ] Rewards are paid through what exists: the `award` function of the
      `rules` feature (12.3; so hunger and clan tax apply to quest
      experience too), the `economy` service, `ops.clone` for items, the `achievements`
      service. A reward whose feature is absent is skipped with a WARNING
      naming the quest.
- [ ] Ship one quest in the Midgaard template (kill five fidos for the
      baker, for experience and a loaf) so a fresh game has a working
      example, and import it in the template's `init_world`.
- [ ] Rewrite showcase 198, 199 and 200 as quest definitions. Branching
      quests (201) stay softcode, using `custom` objectives and the hooks.
- [ ] Tests (`tests/test_quests.py`): each objective kind; stages; the
      giver's offer, the lock and the hand-in; rewards with and without
      `economy`; party and companion kill credit; repeat cooldown; the
      time limit; account scope across two characters; softcode advance;
      a malformed definition refused at load.

### Docs

- [ ] New guide `docs/guides/quests.md`: the definition table, each
      objective kind with an example, the journal, the softcode functions,
      and one complete quest built in-game. Add to `mkdocs.yml`.
- [ ] `docs/guides/features.md`: the `quests` row.
- [ ] Regenerate the softcode reference.

---

## Step 16 — A browser client (optional, Decision D3)

**Goal.** Someone with only a browser can play.

**Depends on.** Step 3 (the prompt), step 10 (the pager).

- [ ] One static page (HTML, CSS and plain JavaScript, no build step) in
      `realm/web/`, served by the existing WebSocket protocol's HTTP
      server at `/` when `ENABLE_WEBSOCKET` and a new `WEB_CLIENT = True`
      are set. It connects to the WebSocket endpoint, renders the
      protocol's color output, keeps input history, shows the prompt in a
      fixed line, and shows the `Char.Vitals` out-of-band data as bars.
- [ ] It ships inside the wheel (`tests/test_packaging.py` checks the file
      is served from a copy of the package alone).
- [ ] Tests: the page is served; a WebSocket session can log in and
      `look` (an integration test with `aiohttp`'s test client, skipped
      when `aiohttp` is not installed).

### Docs

- [ ] `docs/protocols/overview.md`: the browser client and its settings.

---

## Step 17 — Proof

**Goal.** The claim "no large gaps" is a test, and the documentation says
what a newcomer needs.

**Depends on.** Everything above.

- [ ] `tests/test_first_hour.py`: one scripted session on the Midgaard
      template, driven through the Simulator's real input path, that does
      each numbered line of "What 'complete' means here" at the top of
      this plan and asserts what the player sees. It is the acceptance
      test of the whole plan. Keep it deterministic (seed the dice, inject
      the clocks).
- [ ] Run `tests/showcase/` and fix any build this plan changed (the
      login transcripts, achievements, crafting, hunger, the pet and the
      mount, organizations, the quest builds).
- [ ] New page `docs/getting-started/your-first-mud.md`: the path for a
      developer who wants a Diku-style game and wants to build. It walks
      from `realm init --system merc --template midgaard` through making
      an account, playing the first hour, granting a builder, adding a
      room, a mob with a `trainer` behavior, a channel, a quest and a
      clan, and where to go next for rules changes. Link it first in the
      README and in `docs/index.md`.
- [ ] `README.md`: rewrite "What is not built yet" from what is actually
      left, and "What is there" from what this plan added.
- [ ] `docs/reference/public-api.md` and `tests/test_public_api.py`: every
      feature added by this plan has its row and its frozen `__all__`.
- [ ] `CHANGELOG.md`: the `0.3.0` entry. State what a 0.2.0 game must
      change: logins are accounts (existing characters are converted at
      boot), `firstaid` no longer removes `unconscious` directly, `score`
      and `inventory` no longer list skills and worn items, and the new
      settings. State what did not change.
- [ ] Bump `realm.__version__` and `pyproject.toml` to `0.3.0`
      (`tests/test_public_api.py::test_one_version`).
- [ ] Update `CLAUDE.md` key files for the new features.

### Acceptance

- [ ] `tests/test_first_hour.py` passes. The suite is green in both
      orders. `ruff check realm/` reports no more than the baseline.
- [ ] From an empty directory with only the package on the path:
      `realm init demo --system merc --template midgaard && cd demo &&
      pytest -q && realm features --check` succeeds.
- [ ] Every "What is not built yet" bullet in the README of 2026-11-14 is
      either gone or names a listed non-goal.

---

## Decision log

Record every deviation from this plan here before continuing: the date,
the step, what was decided and why.

| Date | Step | Decision | Reason |
|---|---|---|---|
| 2026-11-14 | Decisions | D6: hunger and thirst for Merc only, built on CoffeeMud's mechanics (stomach capacity by weight, loss by tick, exertion and climate, bite-sized eating, escalating reminders, death after 12 hours hungry or 6 thirsty, each need halving recovery, fatigue as an optional third). | The maintainer's answer. |
| 2026-11-14 | Decisions | D7: clans follow CoffeeMud: governments as data (positions, limits, locks, powers), votes, treasury, tax, clan levels and benefits, relations, upkeep; players found clans for `CLAN_COST`. Conquest, trophies, clan items, ordering underlings, theocracy and family are left out (Non-goals). | The maintainer's answer; the left-out parts need systems REALM lacks. |
| 2026-11-14 | Decisions | D8: the companion limit is a configurable rule expression (`COMPANION_LIMIT_RULE`), then `GameSystem.companion_limit`, then 2; companions of companions count; `COMPANION_LEVEL_DIFF` as in CoffeeMud. | The maintainer's answer. |
| 2026-11-14 | 1.1 | Step 1 landed before step 2, so `realm init --system merc` does not yet write `PLAYER_DEATH = "respawn"`; step 2.4 adds the setting and the line in the scaffold's `config.py` (and in the Midgaard template, per D1). | The plan's own instruction for this order. |
| 2026-11-14 | 1.1 | The per-system examples are three snippet files, `realm/templates/rules_examples_<system>.template`, put in place of a marker line in `rules.py.template` (which stays valid Python and names GURPS in its two rewritten lines). The Merc example overrides `MercSystem._classes()` and the D20 one `D20System._class_options()`, since chargen, first-level hit points and the starting weapon all read the class table from there; neither is renamed to a public hook in this step. | One place per system's example text; no rename outside the step's scope. |
| 2026-11-14 | 1.2 | The examples' `GameRules` do not set `system_id`; they keep `merc` and `gurps`. The scaffold's own `rules.py` still sets the game's id. | Characters are stamped with `system_id`; a new id would make every character in an existing Midgaard or station database log in under the "made under different rules" warning (rule 9). |
| 2026-11-14 | 1.2 | `test_midgaard_playable.py` and `test_spacegame.py` are unchanged: neither loads an example's `config.py` (they import the area JSON and `ships.py` directly). The new tests that do load one use `clean_import_state`. | Nothing to isolate there. |
| 2026-11-15 | 2.1 | Regeneration covers an object's declared pools plus its damage and vital pools when those are implicit, so a world with no `rules` feature (no world-default `hp`) still regenerates hit points by 1. An up pool with no floor falls toward 0. | The plan's "without a rules feature it is a flat 1" needs a pool to apply it to. |
| 2026-11-15 | 2.1 | The reaper is a module function (`realm.std.vitals.regen.regen_sweep`) that asks the world's service; the service keeps the interval with `time.monotonic`, since reapers run every `REAP_INTERVAL` (5 s), not every `REGEN_INTERVAL`. | `feature.reaper` is declared once per feature, not per world. |
| 2026-11-15 | 2.2 | `stand` is the command and `wake` its alias. The sleeper's input filter accepts each allowed word and any alias of an allowed command (`score` is an alias of `points`). Added `Simulator.input(player, line)`, which runs the input interceptors before the dispatcher, as a live connection does; `Simulator.do` is unchanged. | Testing the interceptor needs the live input path. |
| 2026-11-15 | 2.2 | The deaf rule is `(recipient, action) -> bool`, and `vitals` answers True for a sleeper who is neither the action's actor nor its target. Messages sent with `room.msg_contents` (not through `deliver_messages`), such as combat's "X collapses", still reach a sleeper. | The plan's one delivery function is `deliver_messages`; the direct broadcasts are left for a later step. |
| 2026-11-15 | 2.2 | Showcase 138 (sleep and rest in softcode) now runs its test in a world without `vitals`, and its page says the engine does this natively. | With `vitals` loaded the engine's `rest` and `wake` answer before its `$`-commands. |
| 2026-11-15 | 2.4 | The corpse's loot lock is a behavior on the corpse, `corpse_claim` (a new behavior id), not a `get` lock. | Taking from a container checks the item's lock, not the container's; the corpse sees the `get` as a bystander and can veto it. |
| 2026-11-15 | 2.4 | Scavengers skip corpses tagged `player_corpse`. | Midgaard's fido is a scavenger and would eat a dead player's gear; ROM's `spec_fido` eats NPC corpses only. |
| 2026-11-15 | 2.4 | `when_spent = respawn` on anything but a player is an error, like `corpse` on a player. Respawn places the player directly (no `on_enter`, no locks) in their `home`, else `world.startup_room`, else a `start_room`-tagged room. Timed effects end through a new `world.services["effects"].clear(obj)`, so `combat` does not import `effects`. | Boundary tests; a death must not be refusable by a lock. |
| 2026-11-15 | 2.4 | `PLAYER_DEATH = "respawn"` is written by `realm init --system merc` and set in the Midgaard template (the 1.1 note above is done). | Decision D1. |
| 2026-11-15 | 2.5 | The cost table is ROM's `movement_loss` (adds `water_swim` 4, `water_noswim` 1, `underwater` 6, `air` 10, `desert` 6, and `water` 4 for hand-built rooms), charged for the destination only. Only a declared `move` pool is charged. The gate pays before the destination's lock and `on_leave` checks, so a step refused after it still costs. | ROM's names are what the importer writes; a numeric `move` attribute in another system must not be drained. |
| 2026-11-15 | 3.1 | `wear` and `remove` moved from `realm.std.items.commands` to a new `realm.std.items.equipment` (with `equipment`), and `items.commands.gated_item_action` gates an item action without a command context. Worn order is a per-character counter (`wear_seq` / `worn_seq`); an item worn before it existed counts as oldest. | The slot logic, the replace path and the listing share one module. |
| 2026-11-15 | 3.1 | The importer names ROM's hold flag `held` and gives a light source the `light` slot, as Merc does, so potions, scrolls and gems become wearable in `held` (ROM holds them too). ROM 2.4's `float` has no Merc slot: such items are not wearable and the converter reports it. The Midgaard `.are` source is not in the repository, so the area was refreshed from the raw fields it keeps (`rom_wear`, `rom_values`) with a new `scripts/dev/refresh_rom_items.py`, not re-converted. | The plan's "regenerate it if slots are missing" needs a source file that is not there. |
| 2026-11-15 | 3.2 | Added `GameSystem.format_skill(skill, level)` (D20 `+14`, Merc `14%`) and `define_skill(..., group=)`. | Each system writes a level its own way; a group needs a way to be set. |
| 2026-11-15 | 3.3 | A prompt is not a message: it goes to a separate session channel (`Session.set_prompt_writer`), written by `flush_output` after any output or when asked (`prompt=True`, which the server passes for the typist). Telnet sends `IAC GA` only when the client refused to suppress go-ahead, since REALM offers SGA; a newline starts output written after a prompt. A template set with the `prompt` command gets a trailing space, because the dispatcher strips input. | Keeping prompts out of the message queue is what keeps `Simulator.seen()` free of them and lets a batch of lines carry one prompt. |
| 2026-11-15 | 3.3 | The dispatcher prefix-matches commands before trying exits (ROM's `interpret` does the same), so the new `prompt` took showcase 149's exit `prom`; the exit was renamed `promenade`. The dispatcher is unchanged. | Changing command resolution is outside this step; recorded in the changelog for games with short exit names. |
| 2026-11-15 | 3.4 | `eat`, `drink`, `quaff`, `recite` and `zap` offer a line they cannot use to the world's softcode `$`-commands before refusing it, as `cast` already does. Food and drink restore `food` and `water` pools, which no system has until step 12; a drink is 4 of a ROM container's units. Pills are tagged `potion` (quaffed) and reported as a gap. A spell no spell_def defines does nothing ("Nothing happens.") and the item is used up all the same. `brandish` aims a harmful spell at every other character in the room and a kind one at everyone. ROM spell slot 507, used by five Midgaard items, is not in the slot table and is reported as a gap. | Built-ins must not shadow world verbs (several showcase builds define `$eat` and `$drink`); the rest fills in what the plan left open. |
