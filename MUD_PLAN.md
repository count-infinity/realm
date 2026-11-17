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
| 4 | Skills you can use: ability commands and the Merc class skills | M | [x] |
| 5 | Progression: use, practice, idle training, timed actions | L | [x] |
| 6 | Accounts: one login, many characters, account data, achievements, bans | L | [x] |
| 7 | Communication: tells, channels, socials, mail | M | [x] |
| 8 | The world clock: game time, day and night, weather | S–M | [x] |
| 9 | Operating a live game: sessions, throttling, shutdown, backup, migrate | M | [x] |
| 10 | Comfort: pager, editor, aliases | M | [x] |
| 11 | Merc parity: the remaining Diku pieces | M | [x] |
| 12 | Hunger, thirst and fatigue, after CoffeeMud | M | [x] |
| 13 | Pets, charmed followers and mounts | M–L | [x] |
| 14 | Clans with governments, after CoffeeMud | L | [x] |
| 15 | Quests | M | [x] |
| 16 | A browser client (optional, see Decision D3) | M | [x] |
| 17 | Proof: the first hour, the guide, 0.3.0 | S | [x] |

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
  its penalty). *Decided 2026-11-16: `respawn` everywhere, as the engine
  default ("Does no good to get conscious in a room of aggros"); a game
  that wants the old rule sets `PLAYER_DEATH = "unconscious"`.*
- **D2. How many characters an account may hold.** Default:
  `MAX_CHARACTERS = 5`. An account with exactly one character enters play
  straight after `connect`; otherwise the account menu is shown.
  *Decided 2026-11-16: 5 is the default, and the limit is per account:
  as CoffeeMud's `BONUSCHARLIMIT`, an account can hold extra slots that
  rewards (achievements) and admins raise.*
- **D3. Whether to ship a browser client** (step 16). Default: yes, one
  static page served beside the existing WebSocket protocol. *Decided
  2026-11-16: not yet. The page step 16 built stays in the tree, off
  (`WEB_CLIENT = False`) and unadvertised; finishing and shipping it is a
  BACKLOG item.*
- **D4. Whether a sleeping character can hear the room.** Default: no
  speech or room messages reach a sleeper except tells, which wake nobody
  but are delivered. *Confirmed 2026-11-16.*
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
- [x] With `--system merc`, `config.py` also gets
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

- [x] A `feature.fallback`: when no command matches, look for an
      `ability_def` (not a `spell_def`; spells keep `cast`) whose name or
      one of its `aliases` is the typed verb and that `can_invoke` allows
      the player. If found, resolve the rest of the line as the target and
      call `invoke_ability(player, adef, target, verb=adef.name)`.
- [x] Command `abilities` (alias `ab`): what the character can invoke, with
      cost.
- [x] A cooldown cost: `{"cooldown": <beats>}` in a cost spec, alone or
      beside a pool cost. Store the ready time per ability on the actor
      (`ability_ready`, a dict) against the world's monotonic clock and
      refuse with "You are not ready to <name> again yet." (This is the
      "cooldown cost spec" deferred in BACKLOG.)
- [x] An ability effect of type `check`: `{"type": "check", "skill": ...,
      "on_fail": "stop"}` rolls the actor's skill through `check()` before
      the effects after it. A failed check sends the definition's
      `fail_msg` and applies nothing more. This is what makes a skill miss.
- [x] Tests: `kick fido` runs a `kick` ability; an unknown verb still
      reaches softcode `$`-commands; a cooldown refuses the second use and
      allows the third after the beats pass; a failed check deals no
      damage.

### 4.2 The Merc class skills

In `realm/packs/merc-classic/` (data) and `realm/games/merc/` (rules).

- [x] `skills.json` in the pack: `kick` (warrior, barbarian; damage by
      level), `bash` (warrior; damage and a `stunned` modifier effect for
      one round), `backstab` (thief; needs a piercing weapon and a target
      not fighting; multiplied weapon damage), `rescue` (warrior; takes an
      attacker off an ally by retargeting the encounter participant),
      `disarm` (warrior, thief; unwields the target's weapon to the floor),
      `trip` (thief; `resting` position on the victim). Each has a `check`
      effect on the skill of the same name and a cooldown.
- [x] `rescue` and `disarm` need more than an effect list. Give them an
      `on_invoke` softcode body if the softcode functions suffice;
      otherwise add softcode functions to `combat` (`retarget(attacker,
      new_target)`, `disarm(target)`), harm-gated.
- [x] Passive defenses in `MercRuleset.roll_attack`: after a hit is
      rolled, the defender's `dodge`, then `parry` (wielding a weapon),
      then `shield_block` (wearing a shield) each get one percentile
      chance, scaled by level difference, to turn it aside, with its own
      message. Each is rolled through `check()` so step 5's learn-by-use
      applies.
- [x] `second_attack` and `third_attack` for warriors as percentile
      chances of an extra swing in the encounter's attack resolution, via
      `Ruleset.resolve_special_maneuver` or a new `Ruleset.extra_attacks`
      hook, whichever keeps `CombatEncounter` free of Merc names.
- [x] `MERC_CLASSES` starting skills match the pack's skill names.
- [x] Tests on a Merc world: each skill's success and failure, class
      gating, the weapon requirement for backstab, a rescue that changes
      who the mob attacks, a dodge that turns a hit into a miss.

### Acceptance

- [x] On Midgaard a level-1 warrior can `kick` and `bash`, a thief can
      `backstab` an unaware fido, and `abilities` lists exactly what each
      class can use.

### Docs

- [x] `docs/guides/abilities.md`: abilities as commands, the `check`
      effect, cooldowns.
- [x] `docs/guides/game-systems.md`: what Merc now implements.
- [x] Regenerate the softcode reference.

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

- [x] `progression_of(obj, skill) -> str`: the skill definition's
      `progression` attribute (`points`, `practice`, `use`, `idle`), else
      `GameSystem.default_progression` (a class attribute: `"points"` on
      `PointBuyMixin`, `"use"` on `MercSystem` per Decision D5, `None` on
      the neutral base, meaning skills do not improve).
- [x] `GameSystem.skill_cap(obj, skill) -> int | None`: neutral None (no
      cap); Merc: a per-class maximum from the skill definition's
      `class_caps`, default 75 below the class's level-gate and 95 at it.
- [x] `GameSystem.on_skill_used(obj, result) -> None`, called at the end of
      `check()` in `realm/std/rules/checks.py` and by nothing else. It is
      synchronous (so is `check()`); it may change attributes and call
      `obj.msg`, and may not propagate actions. The base implementation
      dispatches to the model: only `use` does anything here.
- [x] Combat attack rolls do not pass through `check()` under Merc and
      D20. `CombatSystem.attack` reports them: after the attack roll it
      calls `rules.on_skill_used(attacker, CheckResult(...))` with the
      weapon's `skill` attribute (default `melee`) and the roll's success.
      Do it once in `CombatSystem`, not in each ruleset.
- [x] Tests: the hook runs once per check and once per swing, with the
      right skill; a world with no `rules` feature is unaffected.

### 5.2 Learn by use

- [x] The `use` model in `progression.py`: each use adds to
      `skill_xp_<name>`, more for a success than a failure, nothing when
      the roll could not fail or could not succeed. When it reaches
      `use_xp_needed(level)` (rising with level) the level goes up by one,
      the counter resets, and the character is told
      "You have become better at <skill>!". Nothing is gained at or above
      `skill_cap`. A skill at level 0 that the character was never taught
      does not improve by use unless its definition says
      `untrained_use = True`.
- [x] A softcode route for a builder-authored curve: a `progress_rule`
      attribute on the skill definition, evaluated in the `rule` profile
      with `level`, `success` and `xp` bound, returning the experience to
      add. It mirrors `resolve_rule`.
- [x] `skills` (3.2) shows progress toward the next level for `use` skills.
- [x] Tests: repeated successful checks raise a skill; failures raise it
      more slowly; the cap holds; a combat skill rises from swings; a
      `progress_rule` replaces the curve; a `points` skill is untouched.

### 5.3 Practice

- [x] Command `practice [skill]` in `rules`, usable in a room holding an
      NPC with the new `trainer` behavior (declare it in `rules`; params:
      `teaches`, a list of skill names or `"class"` for the character's
      class list; `max_level`, how far practice carries a skill, default
      a third of the cap). With no argument it lists what this trainer
      teaches and the character's levels. With one it spends a practice
      and raises the skill by an amount from the character's intelligence,
      up to the trainer's maximum.
- [x] Command `train <stat>` at a trainer whose behavior has
      `trains_stats = True`: spends a `train` (Merc gives one per level
      besides practices) to raise a characteristic by one, to the class
      maximum.
- [x] `MercSystem.advance_level` grants trains. The ROM importer attaches
      `trainer` to mobs with the ROM `ACT_PRACTICE` and `ACT_TRAIN` flags;
      regenerate Midgaard and check the guildmasters have it.
- [x] Tests: practicing with and without a trainer; the practice floor;
      running out of practices; `train strength`.

### 5.4 Idle training

- [x] The `idle` model: a character has `training` (a skill name) and
      `training_since` (a wall-clock timestamp). Accrual is computed
      lazily by `accrue_training(obj)`: skill points per minute from the
      skill definition's two governing attributes, levels bought at
      `idle_cost(level)`. It is called at login, by `skills` and `score`,
      at the start of any check of that skill, and by a `feature.reaper`
      sweep over online characters that announces "You have finished
      training <skill> to level N." Offline time counts. No timer runs
      while the player is away.
- [x] Commands `study <skill>` (start; one skill at a time, needs
      `progression = idle` and any `requires` prerequisites on the
      definition) and `study stop`. `skills` shows the skill in training
      and when its next level lands.
- [x] A cap on banked offline time: setting `IDLE_TRAINING_MAX_HOURS`
      (default 0, unlimited).
- [x] Tests with an injected clock: eight hours offline raise a skill by
      the expected levels; the cap limits it; switching skills banks the
      first; a `use` skill refuses `study`.

### 5.5 Timed actions

For crafting, gathering and anything else that takes time at a place.
Create `realm/std/tasks/` (no `requires`).

- [x] Softcode function `start_task(seconds, done_attr, label='',
      interrupt_attr=None)`: the enactor becomes busy (tag `busy`, a `task`
      attribute holding the label, finish time and the object and
      attributes to run). When the time passes, a `feature.reaper` clears
      it and runs `done_attr` on the object that started it, with the
      enactor bound. Unlike `wait()`, a task survives a reboot (it is
      stored on the character) and is tied to one character at one place.
- [x] A task is interrupted, running `interrupt_attr`, when the character
      moves (an `after_traverse` hook), enters combat (an observer on
      hostile actions), or types `stop`. Starting a task while busy is
      refused. A `feature.marker` shows `(busy)`.
- [x] Softcode functions `task_of(obj)` (read-only: the label and seconds
      left, or None) and `stop_task(obj)`.
- [x] Rewrite showcase 122 (recipe crafting) to take time with
      `start_task`, and add a showcase build "a skill learned at the
      forge": a `smithing` skill definition with `progression = use`,
      raised by crafting, and a `metallurgy` skill with
      `progression = idle`. This is the worked example of mixing models.
- [x] Tests: a task completes and runs its script; moving interrupts it;
      a task survives `Simulator` teardown and reload of the character; a
      second task is refused.

### Acceptance

- [x] One Merc game runs all four models at once: `melee` by use,
      `lockpicking` by practice then use, a custom `herbalism` by idle
      study, and a GURPS game keeps buying skills with points. A test
      builds each and checks the level rises the way that model says.

### Docs

- [x] New guide `docs/guides/progression.md`: the four models, how to set
      one per skill, caps, the trainer behavior, `progress_rule`, idle
      training, timed tasks. Add to `mkdocs.yml`.
- [x] `docs/design/skills-inventory.md`: mark the seams built.
- [x] `docs/guides/creating-your-own-system.md`: `default_progression`,
      `skill_cap`, `on_skill_used`.
- [x] Regenerate the softcode and config references.
- [x] `README.md` "What is not built yet": remove the progression bullet.

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

- [x] An account is a `GameObject` tagged `account`, with no location. It
      holds `password` (the scrypt hash, already a protected attribute),
      `characters` (a list of character ids), `created`, `last_login`,
      `email` (optional), `banned_until` and `ban_reason`, and whatever a
      game adds. A character holds `account` (the account's id).
- [x] Account names are unique among accounts, character names among
      characters. The two namespaces are separate.
- [x] `account_of(character) -> GameObject | None` and
      `characters_of(account) -> list[GameObject]` in `account.py`, public
      through `realm.std.accounts.__all__`.
- [x] The first account created on an empty database is the superuser's:
      the first character created on it gets the `god` tag, as the first
      character does today.
- [x] Tests: creation, uniqueness, the links both ways, the hash is not
      readable from softcode.

### 6.2 Carrying existing worlds over

- [x] A `feature.on_boot` step in `accounts`: every `player` object that
      has a `password` and no `account` gets an account of the same name
      holding that password, and the password attribute is removed from
      the character. It logs one INFO line per account made and is a no-op
      on the second boot.
- [x] Tests: a store built the old way boots, the player can
      `connect <same name> <same password>`, and lands in the same
      character in the same room.

### 6.3 Login and the account menu

Rewrite `Accounts.handle_login` and its helpers in `login.py`.
`Session` gains an `account` field beside `player`.

- [x] At the welcome screen: `connect <account> <password>` and
      `create <account> <password>`. `who` and `quit` as now.
- [x] After `connect`: with exactly one character, enter play with it
      (Decision D2). Otherwise show the menu: the account's characters
      with level and class when the rules system has them, and the
      commands `play <name>`, `new <name>`, `delete <name>` (asks for the
      password again; refused for a character holding the `god` tag unless
      it is the last), `password`, `quit`.
- [x] `new <name>` creates a character on the account, refuses past
      `MAX_CHARACTERS` (a setting, default 5), and starts the rules
      system's chargen exactly as `create` does today.
- [x] After `create <account> <password>` the player is asked for a first
      character name and continues into chargen, so a new player still
      reaches the game in two prompts.
- [x] In play: command `characters` returns to the menu without closing
      the connection (the character leaves the room as on `logout`).
      `logout` returns to the welcome screen.
- [x] One account, one session in play at a time (a second login takes
      over, with a message to the old connection), unless
      `ACCOUNT_MULTIPLAY = True`, which allows one session per character.
- [x] `password <old> <new>` in play and from the menu.
- [x] The login rate limit in `AuthService` keys on the account name.
- [x] Tests (`tests/test_accounts.py`): the whole menu; chargen from
      `new`; the character limit; switching characters; take-over; a wrong
      old password; every test that logged in as a character before now
      logs in to its account (`Simulator.player()` is unaffected: it makes
      a character with a session and no account unless asked;
      add `Simulator.account(name, *characters)`).

### 6.4 Account data in softcode

- [x] Softcode functions, declared by `accounts`, group "Accounts":
      `account_attr(obj, name, default=None)` (read-only; the attribute on
      the character's account, None for a character with none),
      `set_account_attr(obj, name, value)` and
      `incr_account_attr(obj, name, by=1)`. The setters require the
      executor to control the character and are refused for the protected
      attributes and for anything flagged `system`. `account_characters(obj)`
      returns the names of the account's characters (read-only).
- [x] Tests: a value set from one character is read from another on the
      same account and not from a stranger's.

### 6.5 Achievements

Create `realm/std/achievements/` (`requires=["accounts"]`).

- [x] An achievement is a definition object tagged `achievement_def`
      (`feature.def_kind("achievement", "achievement_def")`): a name, a
      `description`, `hidden` (not listed until earned), `scope`
      (`account`, the default, or `character`), and `grants`: tags to add,
      and check modifiers by skill name or `"all"`.
- [x] Softcode `grant_achievement(obj, name)` (builder-gated like other
      state-changing functions): records it with a timestamp in
      `achievements` on the account, or on the character for that scope,
      once. It fires `account:on_achievement` (hook `ACHIEVEMENT`, payload
      `achievement`), tells the player, and applies the grants.
      `has_achievement(obj, name)` is read-only.
- [x] Applying grants: tags are added to every character of the account
      when the achievement is earned, and to each character at login
      (an observer on the connect event), so a character made later gets
      them. Check modifiers are answered by a `feature.check_modifier`
      that sums the earned achievements' modifiers for that skill; cache
      the sum per account and drop the cache when an achievement is
      granted or definitions reload (`feature.on_reload`).
- [x] Command `achievements`: earned ones with dates, unearned visible
      ones, a count of hidden ones remaining.
- [x] Tests: earned on one character, the tag and a +1 check modifier
      apply on a second character of the account after it logs in, and not
      on another account; a `character` scope stays put; granting twice
      does nothing; a hidden one is not listed.
- [x] Rewrite showcase 207 (achievements) on top of this, keeping its
      softcode watchers as the thing that decides when to grant.

### 6.6 Bans and administration

- [x] Command `@account <name>` (admin): shows the account, its
      characters, last login and address. Switches: `/password <new>`
      resets it; `/ban <duration> = <reason>` and `/unban`;
      `/boot` disconnects its sessions.
- [x] `@sitelock <address-or-prefix> [= reason]`, `@sitelock/remove`,
      `@sitelock/list` (admin): stored on a singleton object tagged
      `sitelock_registry`. Checked when a connection opens and at
      `create`.
- [x] `connect` refuses a banned account with the reason and expiry.
- [x] Every ban, unban, password reset and sitelock change is logged at
      INFO on a `realm.admin` logger, naming who did it and to whom.
- [x] Tests for each, including expiry with an injected clock.

### Acceptance

- [x] `tests/test_accounts.py` and `tests/test_achievements.py` pass, and
      the migration test of 6.2.
- [x] `git grep -n "db.password\|'password'" realm/` finds the attribute
      only in `accounts` and the protected-attribute tables.

### Docs

- [x] New guide `docs/guides/accounts.md`: accounts and characters, the
      menu, the settings, account data in softcode, achievements with a
      worked example ("slay the banshee on any character, and every
      character gets +1 to will"), bans.
- [x] `docs/getting-started/first-game.md` and `quickstart.md`:
      `create <account> <password>` and the first character.
- [x] Every doc, tutorial chapter and showcase transcript that types
      `create Keeper mypassword` or `connect ...` (grep for both).
- [x] `docs/architecture/sessions.md`: the account field and the menu
      state.
- [x] `README.md` "What is not built yet": remove the accounts bullet.
- [x] Regenerate the softcode and config references.

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

- [x] `tell <player> <message>` (alias `t`) and `reply <message>` (alias
      `r`) to the last teller. Delivered to an online player anywhere,
      refused for one who is offline (pointing at `mail`) or who has the
      teller in their `ignore` list. `tell` propagates an action
      (`comm:on_tell`, hook `TELL`) with the recipient as target and no
      room audience, so softcode can react and wards can veto.
- [x] `ignore <player>`, `ignore` (list), `unignore <player>`.
- [x] `afk [message]`: a tag and message; tellers are shown it.
- [x] Tests: delivery across rooms, reply, ignore, offline, a ward that
      blocks tells in a silenced room.

### 7.2 Channels

- [x] A channel is a definition object tagged `channel_def`: a name, an
      optional `alias`, a `speak` lock and a `listen` lock (so `immtalk`
      is admin-only by data), a `format` template, `history` size.
- [x] Each channel name and alias is a command through a
      `feature.fallback` (`gossip hello`). `channels` lists them with
      on/off state; `channel <name> on|off` toggles; `channel <name>
      history` shows recent lines. Preferences are stored on the account
      when there is one, else the character.
- [x] A message is one propagated action (`comm:on_channel`, hook
      `CHANNEL`, payload `channel`, `message`), delivered to every online
      listener who passes the listen lock and has it on.
- [x] The `channels` content ships three by default in a small pack
      imported by the scaffold's `init_world`: `gossip`, `newbie`,
      `immtalk`.
- [x] Softcode: `cemit(channel, text)` (builder-gated) and
      `channel_members(channel)` (read-only).
- [x] Tests: speaking and hearing, locks, toggling, history, softcode.

### 7.3 Socials

In `realm/std/talk/`.

- [x] A social is a definition object tagged `social_def` with up to five
      message templates (to the actor with no target, to the room with no
      target, to the actor with a target, to the target, to the room with
      a target), using the existing `{actor}` and `{target}` formatting.
- [x] A `feature.fallback` runs a social whose name is the typed verb.
      `socials` lists them.
- [x] Ship a pack of the common Diku socials (smile, nod, bow, laugh, wave,
      shrug, and so on; at least forty) as `realm/packs/socials-classic/`.
      The ROM importer may later read `#SOCIALS`; not in this step.
- [x] Tests: with and without a target, an unseen actor reads as
      "Someone", a social named like a real command never shadows it.

### 7.4 Mail

Create `realm/std/mail/` (`requires=["accounts"]`).

- [x] Messages are objects tagged `mail` held by the recipient's account
      (not in any room), with `sender`, `to`, `subject`, `body`, `sent`,
      `read`.
- [x] Commands: `mail` (list), `mail <n>` (read), `mail <player> =
      <subject>/<body>` (send; the body may use the editor of step 10 when
      it exists), `mail/delete <n>`, `mail/reply <n> = <body>`. Sending to
      a character delivers to that character's account.
- [x] At login a player is told how many unread messages wait. An online
      recipient is told when mail arrives.
- [x] A limit per account (`MAIL_LIMIT`, default 100) and softcode
      `send_mail(to, subject, body)` for system mail (builder-gated).
- [x] Tests: send to an offline player, read after login, delete, the
      limit, system mail.

### Acceptance

- [x] Two players in different rooms hold a conversation by `tell` and on
      `gossip`; one logs out; the other mails them; the first logs in and
      reads it.

### Docs

- [x] New guide `docs/guides/communication.md`. Add to `mkdocs.yml`.
- [x] `docs/guides/features.md`: rows for `channels` and `mail`; the
      `talk` row gains socials.
- [x] Regenerate the softcode reference.

---

## Step 8 — The world clock

**Goal.** The world has a time of day, a calendar and weather that
builders can react to.

**Depends on.** Nothing in this plan (uses the `sight` feature).

Today `time` prints the server's wall clock.

Create `realm/std/clock/`.

- [x] Game time derives from elapsed real time since an epoch stored on a
      singleton object tagged `world_clock`, at `GAME_TIME_RATIO` game
      seconds per real second (a setting, default 30, so a game day lasts
      48 real minutes). A calendar from settings: `HOURS_PER_DAY`,
      `DAYS_PER_MONTH`, `MONTH_NAMES`, `DAY_NAMES`. The clock keeps running
      across restarts because it is derived, not counted.
- [x] Softcode, read-only: `game_time()` returns hour, day, month, year,
      and `time_of_day()` returns one of dawn, day, dusk, night.
- [x] A `feature.reaper` notices when the hour changes and fires
      `time:on_hour` (hook `HOUR`, payload `hour`) and, at the four
      boundaries, `time:on_dawn`, `on_day`, `on_dusk`, `on_night`, on each
      zone master and each room holding a player, so softcode can light
      lamps and open shops without a ticker per object.
- [x] Day and night: a room tagged `outdoors` is dark at night. Implement
      it as a `feature.sight_rule` plus the room-lit answer, asking the
      `sight` service; without `sight`, night changes nothing.
      **If** `sight.room_is_lit` cannot be extended from another feature,
      add a list of extra darkness tests to the `sight` service that
      `clock` appends to, rather than importing `sight` from `clock`.
- [x] Weather per zone: a zone master with a `weather` attribute (a list
      of states with weights, or a softcode expression) gets a current
      state rolled each game hour, stored on the master, announced to
      outdoor rooms in the zone when it changes, and readable with
      `weather(here)`. No effect on rules; builders hook it.
- [x] Commands `time` (game time first, server time after) and `weather`.
      The ROM importer tags non-`inside` sectors `outdoors`.
- [x] Tests with an injected clock: the calendar, the hour event firing
      once per hour, an outdoor room dark at night and lit by a torch, a
      weather change announced outdoors and not indoors.

### Docs

- [x] New guide `docs/guides/time-and-weather.md`. Add to `mkdocs.yml`.
- [x] `docs/design/time-and-beats.md`: the third clock.

---

## Step 9 — Operating a live game

**Goal.** An administrator can keep a public server healthy and recover
from a bad day.

**Depends on.** Step 6.

- [x] **Idle and link-dead sessions.** Settings `IDLE_TIMEOUT` (minutes;
      0 off; admins exempt) and `LINKDEAD_SECONDS` (default 120). A
      connection that drops without `quit` leaves the character in the
      room tagged `linkdead` (a marker shows it) for that long, during
      which a new `connect` resumes it in place; then it is removed from
      the room as on logout. A character in combat when the link drops
      keeps fighting with its default action.
- [x] **Flood control** (capability audit G13). **Kernel seam** in the
      session input path: a per-session token bucket
      (`COMMAND_RATE`, `COMMAND_BURST` settings); over the limit, input is
      dropped with one warning line, and a session that stays over it for
      `FLOOD_DISCONNECT_SECONDS` is closed and logged.
- [x] **Presence in softcode** (G4): `online_players()`, `idle_seconds(obj)`
      (read-only). `who` shows idle time, the `afk` and `linkdead` marks,
      and hides players the viewer cannot see. `basics` offers a service
      (`world.services["who"]`) holding `fields`, a list of
      `(viewer, player) -> str | None` callables whose answers are shown
      beside a name; class titles (step 11) and clan tags (step 14) are
      entries in it.
- [x] **Announce and stop.** `@wall <message>` (admin) to every session.
      `@shutdown [seconds] [= reason]` and `@shutdown/cancel`: counts down
      with announcements, saves everything, stops the server cleanly.
      `@reboot` does the same and exits with a status a supervisor can
      restart on (document the systemd unit).
- [x] **Snoop and freeze.** `@snoop <player>` (admin; logged on
      `realm.admin`; the target's
      output is echoed to the admin) and `@freeze` / `@thaw` (a frozen
      player's input is refused with a notice).
- [x] **Backup.** `realm backup [file]` copies the live database with
      SQLite's online backup API (safe while the server runs) to
      `data/backups/<name>-<timestamp>.db` by default, and
      `realm backup --keep N` prunes older ones. A setting
      `BACKUP_INTERVAL_HOURS` (default 0, off) makes the server do it.
      `realm restore <file>` refuses while the server is running.
- [x] **Migrate.** `realm migrate`: `PersistenceManager` already stamps
      `PRAGMA user_version` and refuses a newer schema. Add an ordered
      list of migration functions keyed by version, run by
      `realm migrate` (and refused at `realm start` with a message telling
      the operator to run it, never run silently). The account conversion
      of 6.2 stays a boot step because it changes objects, not the schema.
- [x] Tests for each: sessions with an injected clock, the token bucket,
      a backup taken during writes that restores to the same object count,
      a migration from a version-1 file.

### Docs

- [x] New guide `docs/guides/operations.md`: settings, the admin commands,
      backup and restore, running under systemd, upgrading. Add to
      `mkdocs.yml`.
- [x] Close capability audit G4 and G13 and the BACKLOG `realm migrate`
      entry.

---

## Step 10 — Comfort

**Goal.** Long output is readable, long text is editable, and players can
shorten what they type.

**Depends on.** Step 3 (the prompt).

- [x] **Pager** (BACKLOG "Output pager"). **Kernel seam** on `Session`:
      `send_paged(text)`. Output longer than the client's reported height
      (NAWS when negotiated, else `PAGE_LENGTH`, default 24, per-player
      `pagelength` attribute, 0 off) is held; the prompt becomes
      "[more: enter, b back, q quit]" and the next line of input drives
      it. `help`, `@examine`, `who`, `skills`, `socials`, channel history
      and mail use it.
- [x] **Editor** (BACKLOG "In-game multiline text editor"). `@edit
      <obj>/<attr>` and `@edit <obj>` for the description open a line
      editor as a session input handler: append lines, `.l` list, `.d N`
      delete, `.i N text` insert, `.r N text` replace, `.s` save, `.q`
      quit without saving, `.h` help. Softcode attributes are validated on
      save the way `@set` validates them. `mail` and `@desc` with no text
      open it.
- [x] **Aliases.** `alias <word> = <command line>`, `alias` (list),
      `unalias <word>`: stored on the character, expanded by an
      `input_interceptor` before dispatch, with `$1`..`$9` and `$*`, no
      recursion, and never over a word that begins with `@`.
- [x] **Per-player display options** (capability audit G7): `config`
      command listing and setting `color`, `pagelength`, `prompt`,
      `autoloot` and the rest (step 11 adds toggles), stored on the
      account when there is one.
- [x] Tests for each, including the pager and editor through
      `Simulator.submit_line`.

### Docs

- [x] `docs/guides/world-management.md`: `@edit`.
- [x] A short "Player settings" section in `docs/guides/character-sheet.md`.
- [x] Close the two BACKLOG entries and audit G7.

---

## Step 11 — Merc parity

**Goal.** A converted ROM area plays the way a Diku player expects.

**Depends on.** Steps 2 to 5.

Read "MERC parity: the punch list" in `docs/development/rom-import.md`
first; it ranks what is left from a run over 189 real area files.

- [x] **Special procedures.** Apply the `rom_spec:* -> behavior` table
      under "Behavioral spec_procs" in that guide: `spec_thief` to the
      `steal` behavior, `spec_guard` / `spec_patrolman` /
      `spec_executioner` to `guard`, `spec_poison` to `venomous`,
      `spec_fido` and `spec_janitor` to `scavenger` (with a corpse-eating
      parameter for the fido). Anything new and Merc-only goes in
      `realm/games/merc/behaviors.py`. The importer attaches them; the
      faction and bespoke procedures stay in the capability-gap report.
- [x] **Player toggles**: `autoloot`, `autogold`, `autosplit`, `autoexit`,
      `brief`, read by the death path, the party award and the room
      renderer through attributes, set with `config` (step 10).
- [x] **Group play**: experience from a kill is split by level among party
      members in the room (`MercSystem`), `split <amount>` shares coins,
      `group` is an alias of `party`, and `report` says the character's
      pools aloud.
- [x] **Looking around**: `scan` (who is one room away in each direction,
      respecting sight), `exits` (the long form), `where` (players in the
      same zone), `consider` using level difference under Merc.
- [x] **Alignment**: an `alignment` attribute moved by kills of good and
      evil mobs (the importer already reads it), shown on `score`, and
      checked by equipment tagged `anti_good` / `anti_evil` /
      `anti_neutral` (the item zaps off when worn).
- [x] **Level limits and titles**: `LEVEL_CAP` (default 50), a class title
      per level band shown on `who`, item level restrictions on `wear`.
- [x] **Recall**: `recall` spends half the `move` pool under Merc and is
      refused in a room tagged `no_recall` and in combat without a check.
- [x] Regenerate the Midgaard area with every importer change in this
      plan and update `tests/test_midgaard_playable.py`.
- [x] Tests for each item on a Merc world.

### Docs

- [x] `docs/development/rom-import.md`: rewrite the punch list as what
      converts now, and what still does not (MOBprogs).
- [x] `docs/guides/game-systems.md`: a "What Merc implements" table.
- [x] `README.md` "What is not built yet": the Merc bullet shrinks to
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

- [x] Hunger and thirst are two pools, `food` and `water` (down pools:
      full at max, spent at 0, `regen=False`), so everything that works on
      pools works on them: the prompt can show them, softcode can read
      them, an item can fill them. Fatigue is a third, `fatigue` (an up
      pool, `regen=False`). A character has a need exactly when it has
      that pool.
- [x] The game system decides who has them (Decision D6):
      `MercSystem.pools()` adds `food` and `water`, and its baseline gives
      a new character full ones. GURPS and D20 do not. No stock system
      declares `fatigue`; a game adds it in its own `pools()`. NPCs are
      never given any of them.
- [x] Capacity. Settings `FOOD_FULL` (default 500) and `WATER_FULL`
      (default 1000) are the base maximums. `GameSystem.stomach(obj) ->
      tuple[int, int]` returns the character's two maximums; the neutral
      answer scales the settings by `weight / NEEDS_BASE_WEIGHT` (a
      setting, default 150) when the character has a `weight` attribute
      and returns them unscaled when it does not.

### 12.2 Losing them

- [x] A `feature.reaper` runs every `NEEDS_INTERVAL` seconds (a setting,
      default 4, CoffeeMud's tick) over online players who have the pools.
      It skips a sleeping character (2.2), an admin, a character tagged
      `no_needs`, and a room whose zone sets `no_needs`. For the rest it
      harms `food` by the weight factor and `water` by the weight factor
      times the room's thirst rate, both scaled by the `FOOD_LOSS` and
      `WATER_LOSS` settings (percentages, default 100), and settles.
      Fractions accumulate on the character (`food_debt`, `water_debt`) so
      a light character still gets hungry.
- [x] The thirst rate of a room is 1, plus 1 for each of the tags
      `climate:hot`, `climate:dry` and `climate:windy`, minus 1 for
      `climate:wet`, never below 0. The tags are read from the room, else
      from its zone masters (`zone_property`).
- [x] Exertion: an `after_traverse` hook charges one more interval's loss
      for each room walked.
- [x] `fatigue` rises by 1 per interval while awake and falls by
      `FATIGUE_SLEEP_RECOVERY` (default 3) per interval while asleep.
- [x] Offline time does not count for any of them.

### 12.3 Going without

- [x] While `food` or `water` is spent the character accumulates
      `hungry_ticks` / `thirsty_ticks` (reset to 0 the moment the pool is
      above 0). Every `NEEDS_REMINDER_TICKS` (default 60) the player is
      told, by how far along they are toward the death limit: "You are
      hungry." in the first half, "You are famished! Eat something!" past
      half, "You are starved! Eat something!" past three quarters, and
      "You are starved, and near death. EAT SOMETHING!" on each of the last
      30 ticks; the thirst lines are thirsty, parched, dehydrated.
- [x] Death. Settings `HUNGER_DEATH_HOURS` (default 12) and
      `THIRST_DEATH_HOURS` (default 6) of online time. Past the limit the
      character is told "YOU ARE DYING OF HUNGER!" and its vital pool is
      spent through `pools.harm` and `settle`, so the ordinary death path
      of 2.4 runs, with no killer. 0 disables death from that need.
- [x] Slower recovery. `needs` appends a multiplier to the `vitals`
      service's list (2.1): 1.0, less 0.5 while hungry, less 0.5 while
      thirsty, so a character that is both recovers nothing; and, for the
      `mana` and `move` pools only, half again while `fatigue` is spent.
      Without `vitals` this part is skipped.
- [x] `HUNGRY_AWARD` (default 1.0): a factor on experience and character
      point awards while hungry or thirsty. 1.0 changes nothing; a game
      that wants CoffeeMud's "no experience while hungry" sets 0. To apply
      it, give the `rules` feature one small seam: `award(player, amount)`
      in `realm/std/rules/system.py`, which passes the amount through
      `award_filters` (a list of `(player, amount) -> int` on the `rules`
      service) and then calls `GameSystem.grant_award`. The death path and
      quest rewards call `award`, never `grant_award` directly. `needs`
      appends a filter; clan tax (14.4) appends another.
- [x] When `fatigue` is spent the player is told "You are exhausted." at
      the reminder interval. Nothing else happens; sleep cures it.

### 12.4 Eating and drinking

- [x] Food carries `nourishment` (how much it holds in all) and `bite`
      (how much one `eat` takes; default: all of it). `eat` moves one bite
      into `food`, scaled by the `FOOD_GAIN` setting (a percentage,
      default 100), and destroys the item when its nourishment is gone.
      Eating when full is refused ("You are too full to eat more.").
      This replaces the `restores = {"food": n}` form for food in 3.4;
      `restores` stays for other pools (a potion that restores `hp`).
- [x] A drink container carries `liquid`, `liquid_held` and
      `liquid_remaining`, and `sip` (default 50). `drink` moves one sip
      into `water`, scaled by `WATER_GAIN`, and lowers what remains. An
      object tagged `fountain` never runs dry. `fill <container>
      <fountain>` refills. A room tagged `water_source` (a river, a
      well) can be drunk from with `drink` alone.
- [x] The ROM importer writes `nourishment` for food from its value,
      `liquid`, `liquid_held` and `liquid_remaining` for drink containers
      from the liquid table, and tags fountains. Regenerate Midgaard.

### 12.5 Showing it

- [x] `score` under Merc says "You are hungry." and "You are thirsty."
      the Diku way when a pool is at a quarter or less, and does not list
      `food` and `water` as numbers beside hit points.
      `MercSystem.score_lines` does this itself; `pool_lines` gains an
      `exclude` argument so it can leave the pools out. The neutral sheet
      lists them like any pool.
- [x] Softcode, read-only: `hungry(obj)` and `thirsty(obj)`.
- [x] Rewrite showcase 137 to configure this feature instead of building
      the meters by hand.
- [x] Tests (`tests/test_needs.py`, with an injected clock): the pools
      fall over time, faster for a heavy character, and only for online,
      awake players who have them; a hot dry room doubles thirst and a wet
      one removes it; walking costs extra; the reminder lines escalate;
      death arrives at the limit through the normal death path and not at
      all when the setting is 0; hunger and thirst each halve
      regeneration; a bite at a time empties a loaf; a fountain is not
      consumed; fatigue rises awake and falls asleep; a GURPS character is
      never hungry; a `no_needs` zone is exempt.

### Docs

- [x] A "Hunger, thirst and fatigue" section in
      `docs/guides/life-and-death.md`, with the settings and the climate
      tags, and a note on where the numbers come from.
- [x] `docs/guides/features.md`: the `needs` row.
- [x] `docs/development/rom-import.md`: food, drink and fountains.
- [x] Regenerate the softcode and config references.

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

- [x] **Design.** A companion is an NPC with a `master` attribute holding
      a character's id. That is the whole relationship: it does not change
      who owns or controls the object for building purposes. A companion
      follows its master (the existing `following` attribute is set with
      it).
- [x] `master_of(obj)`, `companions_of(character)`,
      `set_master(npc, character | None)` in `companions.py`; public names
      of the package.
- [x] The limit (Decision D8), after CoffeeMud's `FORMULA_MAXFOLLOW`
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
- [x] `COMPANION_LEVEL_DIFF` (a setting, default 0, off), after
      CoffeeMud's `FOLLOWLEVELDIFF`: a creature more than that many levels
      above the character cannot be bonded.
- [x] Commands: `companions` (list, with condition), `order <name|all>
      <command>`, `dismiss <name>`. `order` runs the command as the
      companion through the real dispatcher (the mechanism `@force` uses),
      and refuses any command whose permission is above `player`, `order`
      itself, and `quit`; a game narrows it further with the
      `ORDER_REFUSED` setting (a list of command names).
- [x] Fighting together. An observer on hostile actions: when a master
      attacks or is attacked, each of its companions in the room joins
      the encounter on its side, through the `combat` service (do not
      import `combat`; without it companions only follow). A kill by a
      companion is credited to its master: `CombatManager._npc_death`
      asks the `companions` service for the killer's master before paying
      the award, and the death event's killer stays the companion.
- [x] Leaving and returning. When the master logs out, companions with a
      `master` are taken out of the world with it (location None, their
      room remembered) and come back beside the master at login. A
      companion whose master is deleted is released.
- [x] A dead companion leaves the list. A companion never attacks its
      master while the relationship holds (a check ward on hostile
      actions, declared by the feature).
- [x] Softcode: `master(obj)` and `companions(obj)` read-only;
      `set_master(obj, master)` and `release(obj)` for builders. Events
      `companion:on_bond` and `companion:on_release` (hooks `BOND`,
      `RELEASE`).
- [x] Tests (`tests/test_companions.py`): bonding and the limit from
      each of its three layers, including a charisma rule and a companion
      that has companions of its own; the level difference; `order` runs a
      command and refuses an admin one; a companion follows through
      an exit, joins its master's fight, and its kill pays the master; it
      leaves and returns with the master across logout.

### 13.2 Pets from shops, and charm

- [x] A shopkeeper with `sells_pets = True` (a parameter on the existing
      `shopkeeper` behavior in `realm/std/economy/shop.py`, read through a
      service so `economy` does not import `companions`) sells clones of
      the creatures in its `pet_stock` list: `list` shows them, `buy
      <pet>` clones one, bonds it to the buyer and charges the price.
- [x] The ROM importer handles `ROOM_PET_SHOP`: the mobs reset into the
      following room become the shop's `pet_stock`. Midgaard's pet shop
      must sell after regeneration.
- [x] A timed effect behavior `charmed` (in `companions`, built on
      `TimedEffectBehavior` through the `effects` service or by requiring
      `effects`; choose and record): while it lasts the target has the
      caster as master; when it expires the bond is released and, with
      `turns_hostile = True`, the creature attacks its former master.
      Players cannot be charmed unless the zone allows it
      (`zone_property(room, "pvp")`).
- [x] `charm person` in `realm/packs/merc-classic/`: an ability whose
      effect applies `charmed`, with `save = negates` and a level check.
- [x] Tests: buying a pet; the charm lasting and expiring; a saved target;
      the limit shared between pets and charmed creatures.

### 13.3 Mounts

- [x] A companion tagged `mount` can be ridden. Commands `mount <name>`
      (alias `ride`) and `dismount`. Riding is one attribute each way:
      `riding` on the rider, `ridden_by` on the mount. A mount carries one
      rider; a rider rides one mount; nobody mounts in combat; a rider who
      falls unconscious, sleeps or dies is dismounted.
- [x] Moving. The mount follows as any companion does. Where a game
      charges movement (2.5), the cost is paid from the mount's `move`
      pool instead of the rider's: the Merc traversal gate asks the
      `companions` service who pays. A mount with no movement left
      refuses to go ("Your mount is too exhausted.").
- [x] **Kernel seam.** Movement lines are fixed strings in
      `realm/core/movement.py` ("{actor} leaves north.", "{actor}
      arrives."). Add `feature.move_describer(fn)`:
      `(actor, direction, phase) -> str | None`, `phase` being `leave` or
      `arrive`, stored on `World.move_describers`; the first non-None
      answer replaces the room line. `companions` declares one:
      "{actor} rides north on a grey mare." The actor's own line follows
      the same hook. This seam also serves sneaking and flying later.
- [x] A `feature.marker` shows `(riding a grey mare)` on the rider and
      hides the mount's own line from room listings while ridden (a sight
      rule is wrong here: the mount is visible; use the room renderer's
      grouping hook or a `ridden` marker and record the choice).
- [x] Rooms tagged `no_mount` (and, by default, rooms with the
      `sector:inside` tag when `MOUNTS_INDOORS` is False) refuse a mounted
      traveler through a `feature.traversal_gate`.
- [x] `GameSystem.mounted_modifiers(rider, mount) -> dict` (neutral
      empty): a hook for a ruleset that wants a to-hit or defense change
      while mounted. Merc leaves it empty.
- [x] A mount shop is a pet shop whose stock is tagged `mount`.
- [x] Rewrite showcase 65 and 158 on top of this feature.
- [x] Tests: mounting rules; a ride through two rooms shows the riding
      line and drains the mount's movement, not the rider's; a `no_mount`
      room refuses; being knocked out dismounts.

### Docs

- [x] New guide `docs/guides/companions.md`: pets, orders, charm, mounts,
      the settings and the softcode functions. Add to `mkdocs.yml`.
- [x] `docs/guides/features.md`: the `companions` row and
      `feature.move_describer`.
- [x] `docs/tutorial/13-the-enthrall-spell.md`: a closing note pointing at
      the stock `charmed` effect.
- [x] Regenerate the softcode and config references.

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

- [x] A government is a definition object tagged `clan_government_def`
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

- [x] A position is a dict: `id`, `name`, `plural`, `rank` (0 is highest;
      two positions may share a rank), `max` (holders allowed; None for no
      limit), `lock` (a lock expression a holder must pass, for example a
      class), `public` (whether outsiders see who holds it) and `powers`.
- [x] The powers, each a string: `accept`, `reject`, `assign` (promote and
      demote), `exile`, `set_home`, `set_donate`, `premise`, `motd_write`,
      `motd_read`, `withdraw`, `deposit`, `deposit_list`, `tax`,
      `declare` (relations), `channel`, `list_members`, `home_privs`,
      `benefits`, `titles`, `vote_assign` and `vote_other`. A definition
      naming any other power is refused when definitions load.
- [x] A power no position holds outright is decided by vote (14.3):
      assignments among holders of `vote_assign`, everything else among
      holders of `vote_other`. A power that nobody holds and nobody can
      vote on cannot be used in that government, and the command says so.
- [x] `auto_promote`: `none` leaves the top position to appointment or
      vote. `rank` fills a vacant top position with the longest-serving
      member of the next rank down. `level` gives it to the highest-level
      qualifying member, `xp` to whoever has donated the most experience
      and `gold` to whoever has donated the most money, re-evaluated
      whenever those change, displacing the holder.
- [x] Ship the governments as a pack, `realm/packs/clan-governments/`,
      imported by the scaffold's `init_world`: `gang`, `guild`, `union`,
      `fellowship`, `anarchy`, `co-op`, `meritocracy` and `plutocracy`,
      with the positions, limits and powers of the CoffeeMud file.
      `theocracy`, `family` and `profession` depend on deities, kinship
      and class grants that REALM does not have; describe in the guide how
      a game builds them with position locks, and do not ship them.
- [x] Tests: each shipped government loads and validates; a malformed one
      (unknown power, no positions, an `accept_position` that does not
      exist) is refused with its name.

### 14.2 The clan and its members

- [x] A clan is an object tagged `clan`, with no location: `name`,
      `government` (the definition's name), `members` (character id to
      `{position, joined, donated_xp, donated_gold}`), `premise`, `motd`,
      `treasury`, `home` and `donate_room` (room ids), `tax` (a
      percentage), `xp`, `level`, `relations` (clan name to relation),
      `status` (`pending` or `active`) and `founded`. A character has a
      `clans` attribute mapping category to clan id.
- [x] Founding (Decision D7). `clan found <name> = <government>`: costs
      `CLAN_COST` (a setting, default 10000) through the `economy`
      service, needs `CLAN_MIN_LEVEL` (default 1), and makes the founder
      the holder of the top position. With `CLAN_COST = None` only
      `@clan create <name> = <government>, <leader>` (admin) founds one. A
      clan is `pending` until it has `CLAN_MIN_MEMBERS` (default 1)
      members; a pending clan cannot declare relations or levy a tax.
- [x] Joining: `clan apply <clan>` (refused by `required_lock`, by
      `CLAN_MAX_MEMBERS` when not 0, and when the character already has a
      clan in that category), `clan accept <player>` and `clan reject
      <player>` for holders of those powers, `clan leave`.
- [x] Positions: `clan assign <member> = <position>` (the `assign` power,
      or a vote), refused when the position is full or the member fails
      its lock; nobody assigns a position at or above their own rank
      unless they hold the top one. `clan exile <member>`.
- [x] Information: `clan` (your clans), `clan info <clan>` (premise,
      government, level, public position holders), `clan who` (roster by
      position, online first; needs `list_members`), `clans` (every active
      clan with its government and size), `clan governments` (what a
      founder may choose, with descriptions).
- [x] Text and places: `clan premise = <text>`, `clan motd = <text>`
      (shown to members at login to those with `motd_read`), `clan home`
      and `clan donate` set from the room the holder stands in, and `clan
      recall` takes a member with `home_privs` to the clan home under the
      same rules as `recall`.
- [x] `clan disband` by the top position, after confirmation; the treasury
      returns to the holder.
- [x] Tests: founding with and without the cost; the whole life of a
      member in a `gang` (apply, accept, assign, exile) and each command
      refused without its power; a full position refused; a position lock
      refusing an unqualified member; two categories at once and a second
      clan in one category refused.

### 14.3 Voting

- [x] An action that must be voted on opens a vote stored on the clan:
      what is proposed, by whom, when it closes (`vote_days` game days
      from now), and the ballots. `clan votes` lists open votes; `clan
      vote <n> yes|no` casts or changes a ballot; the proposer may
      withdraw one.
- [x] A vote passes as soon as more than half of all eligible voters have
      said yes, and fails as soon as that is impossible. Otherwise it is
      counted when it closes: it passes with a majority of ballots cast if
      at least `vote_quorum` percent of eligible voters voted. A passed
      vote carries out its action as if a holder of the power had typed
      it; either outcome is announced on clan talk and to the proposer.
- [x] A `feature.reaper` closes votes that have run out. Game days come
      from the `clock` service (step 8); in a game without `clock`, one
      game day is counted as one real hour, and the guide says so.
- [x] Tests with an injected clock: a `fellowship` assigns its leader by
      vote; early pass, early fail, quorum failure at the deadline; a
      member without `vote_assign` cannot vote on an assignment; a `gang`
      never opens a vote.

### 14.4 Treasury, tax, levels and benefits

- [x] `clan deposit <amount>` and `clan withdraw <amount>` against the
      `economy` service, by power; without `economy` the commands say the
      treasury is unavailable. Each deposit adds to the member's
      `donated_gold`. `clan deposits` (the `deposit_list` power) shows who
      has given what.
- [x] `clan tax <percent>` (the `tax` power; at most `CLAN_MAX_TAX`,
      default 25). While set, that share of every experience or
      character-point award a member earns goes to the clan's `xp` and to
      the member's `donated_xp` instead of to the member. `clans` appends
      a filter to the `rules` service's `award_filters` (12.3).
      `clan donate xp <amount>` gives directly, where the rules system has
      spendable experience or points.
- [x] Clan levels: when `xp` reaches the government's `xp_per_level` for
      the next level, the clan's `level` rises and members are told.
- [x] Benefits: each `benefits` entry at or below the clan's level grants
      its tags, check modifiers and pool-maximum bonuses to members whose
      position has the `benefits` power. Apply them the way achievements
      are applied (6.5): tags at login and when the level or membership
      changes, check modifiers through a `feature.check_modifier` with a
      cache dropped on those same changes. Removing a member removes the
      tags.
- [x] `auto_promote` of `xp` and `gold` is re-evaluated after every
      donation and tax payment.
- [x] Tests: deposit and withdraw by power; tax diverting a share of a
      kill award; a clan reaching level 2 and its members gaining the
      benefit, and losing it on exile; a `plutocracy` changing leader when
      someone out-donates the holder.

### 14.5 Relations

- [x] `clan declare <clan> = war|hostile|neutral|friendly|ally` (the
      `declare` power, or a vote; both clans must be `rivalrous` and
      active). The relation is one-sided as declared; `clan relations`
      shows both sides. An alliance holds only when both have declared it.
- [x] Read-only softcode `clan_relation(a, b)` returns the relation of
      clan `a` toward `b`, and `clans_at_war(a, b)` is true when either
      has declared war. These are for builders and for a game's own
      player-killing rules; the engine attaches no combat consequence
      (see Non-goals).
- [x] Tests: declaring, the alliance needing both sides, a pending clan
      refused, softcode reading it.

### 14.6 Upkeep

- [x] A `feature.reaper`, on a slow cadence, using members' last login
      from their accounts:
  - dissolves a clan when fewer than `CLAN_MIN_MEMBERS` of its members
    have logged in within `CLAN_DEATH_DAYS` (a setting in game days,
    default 2160; 0 disables), returning nothing and announcing it;
  - replaces the holders of the top position when every one of them has
    been absent for `CLAN_OVERTHROW_DAYS` (default 952; 0 disables), with
    the highest-ranking qualifying member who has logged in recently.
- [x] The roster prunes itself: a member id that no longer resolves to a
      character is dropped the next time the roster is read, so deleting a
      character (6.3) needs no call into `clans`.
- [x] Tests with an injected clock for both rules and for pruning.

### 14.7 Talk, who, locks and softcode

- [x] Clan talk: `clantalk <message>` (alias `ct`) for members whose
      position has the `channel` power: one propagated action
      (`clan:on_talk`, hook `CLANTALK`) delivered to online members, with
      history. Build it on the channel delivery code of 7.2 through the
      `channels` service; without it the command says clan talk is
      unavailable. A member of clans in two categories names the clan:
      `ct <clan> <message>`.
- [x] `who` shows the clan name and, for a public position, its title:
      `clans` appends an entry to the `who` service's `fields` list
      (step 9).
- [x] Read-only softcode, also available in lock expressions: `clan(obj,
      category='')` (the clan's name or None), `clan_position(obj)` (the
      position id), `clan_rank(obj)` (the rank number, 0 highest),
      `clan_has_power(obj, power)`, `clan_level(name)` and
      `clan_members(name)`. A hall door is
      `@lock door = clan(enactor) == 'Ravens'`; an armory is
      `clan_has_power(enactor, 'home_privs')`.
- [x] Builder-gated softcode `clan_add(obj, name, position=None)` and
      `clan_remove(obj, name)`. Events `clan:on_join`, `clan:on_leave`,
      `clan:on_assign`, `clan:on_level` (hooks `CLANJOIN`, `CLANLEAVE`,
      `CLANASSIGN`, `CLANLEVEL`).
- [x] Admin: `@clan create`, `@clan delete <name>`, `@clan set
      <name>/<field> = <value>`, `@clan xp <name> = <amount>`.
- [x] Rewrite showcase 221 and 222 to use the feature. Showcase 223
      (elections) becomes an example of choosing the `union` government.
- [x] Tests: clan talk reaching only members with the power; a door
      locked by clan, by rank and by power; the softcode functions.

### Acceptance

- [x] `tests/test_clans.py` passes, and one test founds a clan under each
      shipped government and checks who can and cannot do each of:
      accept a member, assign a position, withdraw from the treasury.

### Docs

- [x] New guide `docs/guides/clans.md`: founding, the shipped governments
      in a table (who rules, how the top position is filled, what is
      voted on), positions and powers, voting, the treasury and tax,
      levels and benefits, relations, upkeep, the settings, the softcode
      functions, and how to write a government of your own, with a
      theocracy as the worked example. Add to `mkdocs.yml`.
- [x] `docs/guides/features.md`: the `clans` row.
- [x] Regenerate the softcode and config references.

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

- [x] A quest is a definition object tagged `quest_def`
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

- [x] Objective kinds, each a dict with `kind`, a `count` (default 1) and
      a matcher: `kill` (a name, a tag or a `prototype_vnum`), `collect`
      (items held; `consume = True` takes them at turn-in), `deliver` (an
      item given to an NPC), `visit` (a room id or tag), `talk` (an NPC),
      `use` (an object), and `custom` (a key advanced only from softcode).
- [x] A definition is validated when definitions load
      (`feature.on_reload` and boot): an unknown objective kind, a stage
      with no objectives or a reward naming a missing prototype is an
      error naming the quest.

### 15.2 Tracking

- [x] A character's progress is in two attributes: `quests`
      (`{quest: {"stage", "counts", "accepted", "deadline"}}`) and
      `quests_done` (`{quest: timestamp}`); for `scope = account` the
      second lives on the account.
- [x] One `feature.observer` turns events into progress: `combat:on_death`
      for `kill` (credit goes to the killer, to the killer's master when
      it is a companion, and to party members in the room), `item:on_get`
      and `item:on_give` for `collect` and `deliver`, the room-entry event
      for `visit`, `item:on_use` for `use`. Keep an index of which online
      characters have an active objective of each kind, so the observer
      returns at once for an action nobody is waiting on.
- [x] `talk <npc>` is a new command in this feature (it fires
      `quest:on_talk`, hook `TALK`, which NPC softcode may also answer),
      and it advances `talk` objectives.
- [x] Finishing the last objective of a stage moves to the next, shows
      its text and runs `on_stage`. Finishing the last stage completes the
      quest at once when it has no giver, else marks it ready to hand in.
- [x] A `feature.reaper` fails quests past their deadline and runs
      `on_fail`.
- [x] Events `quest:on_accept`, `quest:on_advance`, `quest:on_complete`,
      `quest:on_fail` (hooks `QUESTACCEPT`, `QUESTADVANCE`,
      `QUESTCOMPLETE`, `QUESTFAIL`).

### 15.3 Players and builders

- [x] Commands: `quests` (alias `journal`: active quests with the current
      stage and counts; `quests done` for the history), `quest <name>`
      (detail), `quest list` (what the givers in this room offer you),
      `quest accept <name>`, `quest complete <name>` (at the giver),
      `quest abandon <name>`.
- [x] The behavior `quest_giver` (parameter `quests`, a list of names). A
      `feature.marker` shows `(!)` beside a giver with something to offer
      the looker and `(?)` beside one waiting for a hand-in.
- [x] Softcode: read-only `quest_state(obj, quest)` (None, a stage number,
      `'ready'` or `'done'`) and `quest_count(obj, quest, key)`;
      builder-gated `quest_offer`, `quest_advance(obj, quest, key, by=1)`,
      `quest_complete` and `quest_fail`. `quest_state` is available in
      lock expressions, so a door can open to those who finished a quest.
- [x] Rewards are paid through what exists: the `award` function of the
      `rules` feature (12.3; so hunger and clan tax apply to quest
      experience too), the `economy` service, `ops.clone` for items, the `achievements`
      service. A reward whose feature is absent is skipped with a WARNING
      naming the quest.
- [x] Ship one quest in the Midgaard template (kill five fidos for the
      baker, for experience and a loaf) so a fresh game has a working
      example, and import it in the template's `init_world`.
- [x] Rewrite showcase 198, 199 and 200 as quest definitions. Branching
      quests (201) stay softcode, using `custom` objectives and the hooks.
- [x] Tests (`tests/test_quests.py`): each objective kind; stages; the
      giver's offer, the lock and the hand-in; rewards with and without
      `economy`; party and companion kill credit; repeat cooldown; the
      time limit; account scope across two characters; softcode advance;
      a malformed definition refused at load.

### Docs

- [x] New guide `docs/guides/quests.md`: the definition table, each
      objective kind with an example, the journal, the softcode functions,
      and one complete quest built in-game. Add to `mkdocs.yml`.
- [x] `docs/guides/features.md`: the `quests` row.
- [x] Regenerate the softcode reference.

---

## Step 16 — A browser client (optional, Decision D3)

**Goal.** Someone with only a browser can play.

**Depends on.** Step 3 (the prompt), step 10 (the pager).

- [x] One static page (HTML, CSS and plain JavaScript, no build step) in
      `realm/web/`, served by the existing WebSocket protocol's HTTP
      server at `/` when `ENABLE_WEBSOCKET` and a new `WEB_CLIENT = True`
      are set. It connects to the WebSocket endpoint, renders the
      protocol's color output, keeps input history, shows the prompt in a
      fixed line, and shows the `Char.Vitals` out-of-band data as bars.
- [x] It ships inside the wheel (`tests/test_packaging.py` checks the file
      is served from a copy of the package alone).
- [x] Tests: the page is served; a WebSocket session can log in and
      `look` (an integration test with `aiohttp`'s test client, skipped
      when `aiohttp` is not installed).

### Docs

- [x] `docs/protocols/overview.md`: the browser client and its settings.

---

## Step 17 — Proof

**Goal.** The claim "no large gaps" is a test, and the documentation says
what a newcomer needs.

**Depends on.** Everything above.

- [x] `tests/test_first_hour.py`: one scripted session on the Midgaard
      template, driven through the Simulator's real input path, that does
      each numbered line of "What 'complete' means here" at the top of
      this plan and asserts what the player sees. It is the acceptance
      test of the whole plan. Keep it deterministic (seed the dice, inject
      the clocks).
- [x] Run `tests/showcase/` and fix any build this plan changed (the
      login transcripts, achievements, crafting, hunger, the pet and the
      mount, organizations, the quest builds).
- [x] New page `docs/getting-started/your-first-mud.md`: the path for a
      developer who wants a Diku-style game and wants to build. It walks
      from `realm init --system merc --template midgaard` through making
      an account, playing the first hour, granting a builder, adding a
      room, a mob with a `trainer` behavior, a channel, a quest and a
      clan, and where to go next for rules changes. Link it first in the
      README and in `docs/index.md`.
- [x] `README.md`: rewrite "What is not built yet" from what is actually
      left, and "What is there" from what this plan added.
- [x] `docs/reference/public-api.md` and `tests/test_public_api.py`: every
      feature added by this plan has its row and its frozen `__all__`.
- [x] `CHANGELOG.md`: the `0.3.0` entry. State what a 0.2.0 game must
      change: logins are accounts (existing characters are converted at
      boot), `firstaid` no longer removes `unconscious` directly, `score`
      and `inventory` no longer list skills and worn items, and the new
      settings. State what did not change.
- [x] Bump `realm.__version__` and `pyproject.toml` to `0.3.0`
      (`tests/test_public_api.py::test_one_version`).
- [x] Update `CLAUDE.md` key files for the new features.

### Acceptance

- [x] `tests/test_first_hour.py` passes. The suite is green in both
      orders. `ruff check realm/` reports no more than the baseline.
- [x] From an empty directory with only the package on the path:
      `realm init demo --system merc --template midgaard && cd demo &&
      pytest -q && realm features --check` succeeds.
- [x] Every "What is not built yet" bullet in the README of 2026-11-14 is
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
| 2026-11-15 | 4.1 | Cooldown ready times are wall-clock seconds (`time.time()`), not the monotonic clock the plan names; a cooldown is in world beats of `WORLD_BEAT` seconds. | A monotonic value saved on a character means nothing after a restart; the kernel's expiry already uses wall time. |
| 2026-11-15 | 4.1 | An ability typed as its own verb reads "You kick the rat." (not "You kick kick at the rat."), with a third-person room line ("bashes"). A failed `check` replaces the success lines with `fail_msg` and a room line. The cooldown is checked before any pool is spent and started only after. | The plan left the messages open. |
| 2026-11-15 | 4.2 | Rescue and disarm are ability effect types (`rescue`, `disarm`), calling new `CombatManager.attackers_of` / `retarget` / `disarm`; the softcode functions `attackers()`, `retarget()` and `disarm()` call the same methods. An ability's softcode runs as its definition object, which is in no room, so reach-gated softcode cannot touch the fight from there. Backstab needs new def fields (`requires_weapon`, `target_unaware`) and a `weapon_damage` effect; trip a `tag` effect; rescue `target_fighting`. | The plan's softcode route does not reach; the functions are added anyway for traps and NPCs. |
| 2026-11-15 | 4.2 | Passive defenses live in `MercRuleset.roll_attack` (a hit turned aside becomes a miss whose `effects` names the defense, and `format_attack_message` words it), and only a defender with a trained skill (`skill_<name>` above 0) defends. Chances follow ROM: dodge and parry half the skill, shield block a fifth plus 3, each plus the defender's level minus the attacker's; second attack half, third a quarter and only after a second. `Ruleset.extra_attacks(attacker)` is the new neutral hook. | The plan left the formulas to ROM. |
| 2026-11-15 | 4.2 | Barbarians lose `rescue` (rescue is the warrior's, per the plan) and gain `kick`; disarm is level 10, so level-1 lists are warrior kick/bash/rescue, barbarian kick, thief backstab/trip. Starting weapons carry a `damage_type` (the dagger is piercing, for backstab). The ROM importer now writes weapons' `damage_type` from the attack word, recovering words that old-format files stored as flag letters, and Midgaard was refreshed with the dev script. | Backstab needs to know a dagger pierces. |
| 2026-11-15 | 4.2 | A trip's `resting` would be undone at once by vitals' rule that a hostile act stands the victim up: the `tag` effect records `extra["tagged"]` and the rule skips an act that set the position; the pack orders trip's damage before its tag, since the damage is a separate hostile event. | The two plan items conflict as written. |
| 2026-11-15 | Decisions | D5 confirmed by the maintainer ("go"): Merc learns every skill by use after practice to a floor; GURPS and D20 stay point-buy; per-skill `progression` overrides. | The maintainer's answer. |
| 2026-11-15 | 5.1 | Kernel helper `realm.core.defs.def_objects(kind)`: a kind's definition objects unparsed, cached and invalidated with `all_defs`. | The `skill` kind parses to `(stat, penalty)` and skips definitions without both; progression fields and progression-only definitions need the objects, on the hot check path. |
| 2026-11-15 | 5.1 | Added hooks the plan implies: `check_was_open` (Merc: a 0% or 100% chance is certain), `use_xp_gain`, `use_xp_needed`, `idle_cost`, `class_skills`, `stat_max`. A swing reports `effective` as the ruleset's to-hit target. Only player characters learn. `on_skill_used` tolerates a result without a `skill` (stand-in resolvers in tests and games). | The plan names the behaviors but not where the numbers live. |
| 2026-11-15 | 5.1 | Merc's cap: a skill's `class_caps`; else for a class skill (its starting skills and every ability_def listing the class) 95 once the character reaches the ability's level and 75 before; 75 outside the class. | Reading of "75 below the class's level-gate and 95 at it". |
| 2026-11-15 | 5.2 | An untrained skill (with `untrained_use`) and an idle skill start counting from the skill's untrained default, not 0. | Under GURPS an untrained skill already has an attribute default (dexterity 10 - 5 = 5); writing 1 over it would lower it. Found writing showcase 253. |
| 2026-11-15 | 5.3 | Practice works for `practice` and `use` skills; a trainer teaching `"class"` teaches the character's own class skills, so any guildmaster teaches anyone. The shipped Midgaard places only the cleric's guildmaster (the converted area has no inner sanctums or resets for the other three); the mage, thief and warrior guildmaster prototypes carry `trainer` for a game that places them. | The area file's content, not the engine. |
| 2026-11-15 | 5.4 | One skill in study at a time (`training`, `training_since`, `sp_<name>`), not a queue. The reaper sweeps online characters (all player characters when the world has no session manager, as in tests). | The plan's own shape. |
| 2026-11-15 | 5.5 | `start_task`, `stop_task` and the interruptions run through queued world ops; `stop_task` is allowed for the object that started the task or anything that may mutate the character. `stop`, `study`, `train` and `practice` offer a line they cannot use to softcode `$`-commands first, and showcase 217's exit `study` was renamed `in` (an exact command name now wins over the exit). | Several showcase builds define `$study` and `$stop`. |
| 2026-11-15 | 6.1 | Account and character names are one word of letters, digits and `_`, at most 30 long; a password is at least 4 characters. The first account on an empty database is marked `founder`, and its first character gets `god`. | The plan left the rules for names open. |
| 2026-11-15 | 6.3 | The menu keeps a pending question (a first character's name, the password before a delete) in the session's `account_pending` data, not `session.prompt()`, which waits on the next line inside the handler of the current one and would deadlock the input pump. | Login runs inside the input pump. |
| 2026-11-15 | 6.3 | `delete` refuses only the last `god` character on the server ("refused for a character holding the god tag unless it is the last" read as: the server must keep a superuser). | Ambiguous in the plan; this reading cannot strand a server without one. |
| 2026-11-15 | 6.3 | Without `ACCOUNT_MULTIPLAY` the take-over happens at `connect` (every other connection of the account is told and closed). With it, `play` takes over a character another connection holds. A failed `connect` to an account that does not exist is not counted by the rate limit. | The plan's two cases. |
| 2026-11-15 | 6.4 | The account setters need the executor to control the character, and players are controlled only by themselves, their owner and admins, so a world object setting account data must be an admin's. `system`-flagged attributes are refused even to admins, as the plan says. | The control rules already in the engine. |
| 2026-11-15 | 6.5 | `grant_achievement` is harm-gated (a builder's tool, like the other state-changing functions) and needs no control of the character; it awards players only. The check-modifier cache is per character, cleared on every grant and on reload. An achievement for a character with no account is kept on the character. | Simplest correct caching. |
| 2026-11-15 | 6.5 | Showcase 207's three Explorer tiers are three achievements (Wanderer, Pathfinder, Cartographer); the Chronicle's watcher and tier table still decide when; the engine's `achievements` replaces the hand-made `$badges`. | The plan: keep the softcode watchers as what decides. |
| 2026-11-15 | 6.6 | `@account/password <name> = <new>` (the `=` form, like the other admin commands), ban durations `30m`/`2h`/`3d`/`1w`/`forever` (stored as the string `forever`). The sitelock check runs as a session-manager `on_connect` callback, so a Simulator (which has none) never sitelocks. | The plan left the syntax open. |
| 2026-11-15 | 6 | `GameServer.stop` now disconnects sessions before closing the world. | A player still in play at shutdown could not be announced or saved: the world was gone (found by the new login tests, the first to stop a server with players in play). |
| 2026-11-15 | 7.1 | Tells, ignore and afk live in the new `channels` feature (the plan's `realm/std/channels/`). A tell's chain is the teller, both rooms as rooms only (a ward in either refuses it; no bystander overhears), then the recipient. Names in tells and channel lines are written out, not perceived: a listener in another room would otherwise read "Someone". | Remote speech has no line of sight. |
| 2026-11-15 | 7.2 | A channel line is delivered to each member directly, with the world's deaf rules consulted (a sleeper misses it, Decision D4) instead of through room delivery; the speaker always hears their own line. A channel's command defers to a world `$`-command of the same word, and so do socials. | Built-ins must not shadow world verbs (step 3's rule). |
| 2026-11-15 | 7.2 | The Simulator now keeps a real `SessionManager` (new `SessionManager.adopt`), so tells and channels find online players the same way in tests as on a server. | "Who is online" had no answer in the Simulator. |
| 2026-11-15 | 7.2 | The scaffold's `config.py` gains a live `init_world` that imports the `channels` and `socials-classic` packs (before, it was a comment); Midgaard and the space station import them too. | The plan's "imported by the scaffold's init_world". |
| 2026-11-15 | 7.3 | A social's five lines are the attributes `actor`, `room`, `actor_at`, `target`, `room_at`. A social is an `event:social` action with the `SOCIAL` hook. The pack has 48 socials. | `self` (the first choice) collides with Python's `self` in keyword APIs such as `Simulator.obj`. |
| 2026-11-15 | 7.4 | A message's location is the recipient's account (accounts have no location, so mail is in no room). Showcase 75's softcode mail now runs without the `mail` feature, whose `mail` command would answer first. | The plan's "held by the recipient's account". |
| 2026-11-15 | 8 | Night darkness uses the existing `outdoor` tag (the ROM importer already writes it for every non-interior room), not a new `outdoors`; city rooms are also tagged `lamplit`, which keeps them lit, as ROM's `room_is_dark` does for city and inside sectors. | Two near-identical tags would be a trap; the city rule is ROM's. |
| 2026-11-15 | 8 | `room_is_lit` could not be extended from outside, so the `sight` service gains `add_darkness_test(fn)` (the plan's fallback); `clock` adds its test at install and removes it when the world closes. | The plan's own instruction. |
| 2026-11-15 | 8 | A new world's clock starts at 08:00 on day 1 (the epoch is set back by eight game hours), and is made at boot or on first read. Dawn is the hour a quarter into the day, dusk the hour 19/24 in; `on_day` and `on_night` fire the hour after dawn and dusk. | Starting at midnight would make every outdoor room dark the moment a world is made. |
| 2026-11-15 | 8 | The hour's hooks run directly on each target (zone masters and rooms holding players), after one action with an empty chain for observers; propagating to each room would also fire every zone master once per room. | "Once per hour". |
| 2026-11-15 | 8 | `MemoryStore` gains `register(obj)`, matching `PersistenceManager.register`, so sync code (the clock made on first read) can add an object to either store. | The two stores had no common sync add. |
| 2026-11-15 | 8 | A weather rule binds `hour` and `current`; `time_of_day()` is the read-only function, not a bound value. | Binding a value under the function's name hid the function (found testing the guide's example). |
| 2026-11-16 | 9.1 | `IDLE_TIMEOUT`, `LINKDEAD_SECONDS`, the flood settings and the backup settings are kernel `Settings`, not a feature's: the session layer and the server read them. A dropped connection is told apart from a deliberate close by who closes it: protocol adapters call the new `SessionManager.connection_lost`, and every other close (`quit`, `@boot`, idle, shutdown, a take-over) is deliberate. The server's session clock (`realm.gateway.session.clock`) is the injectable clock. | The plan names the settings but not where they live; this keeps every existing close path unchanged. |
| 2026-11-16 | 9.1 | At link loss the room hears "has lost their link." as a line only; `ON_DISCONNECT` fires once, when the character leaves play (the wait ends, or at once for a deliberate close), with "has disconnected.". Reconnecting in time fires `ON_CONNECT` (`returning`) as any re-login does. "Removed from the room as on logout" is read as leaving play: offline characters stay in their rooms in REALM, as on logout. A combatant keeps fighting because combat never consulted the connection. | Firing `ON_DISCONNECT` at both moments would tell softcode a character left twice. |
| 2026-11-16 | 9.2 | The flood bucket applies to connections a protocol made (`SessionManager.create_session`), not to sessions a test harness adopts. A flood lasts until the bucket is full again (the client slowed down), so a client that keeps sending a little over the rate is closed after `FLOOD_DISCONNECT_SECONDS`. A `'''` block counts as one line. | The Simulator feeds build transcripts through `submit_input` at machine speed. |
| 2026-11-16 | 9.3 | `online_players` and `is_online` moved from `channels` to the kernel's session module (`realm.gateway.session`, and `SessionManager` methods), because `channels` may not import `basics`. `online_players()` in softcode lists the players the running object can see. The login screen's `who` is unchanged. | The feature-boundary test; the plan's "hides players the viewer cannot see", applied to softcode too. |
| 2026-11-16 | 9.4 | The admin commands are a new feature, `operations` (in `CLASSIC`). `@shutdown` with no count waits 60 seconds; the countdown announces at once, at each minute and at 30, 10 and 5 seconds. `@reboot` exits with status 3. `CommandDispatcher.server` is now a declared attribute (None in a Simulator, where `@shutdown` says there is no server). | The plan left the default, the cadence and the status open. |
| 2026-11-16 | 9.5 | A snoop that would loop (the target already sees the admin's output) is refused, and either side's disconnect ends it. A frozen player may still `quit`. | A loop would recurse forever; a frozen player must still be able to leave. |
| 2026-11-16 | 9.6 | `realm restore` (and `realm migrate`) know the server is running from a pid file beside the database (`game.db.pid`), written at start and removed at stop; a pid file naming a dead process is ignored. Added `BACKUP_KEEP` for the automatic backups. | SQLite gives no reliable "in use" signal; `--keep` needed a setting for the server's own backups. |
| 2026-11-16 | 9.7 | The schema is now v2: an index on `parent_id`, so the migration path has a real first step. An unstamped database holding the objects table counts as v1. `PersistenceManager._flush_queue` became the public `flush()` (the server flushes before a backup and at the end of a countdown). | A migration framework with nothing to migrate cannot be tested from a version-1 file, as the plan asks. |
| 2026-11-16 | 10.1 | A screen is the player's `pagelength` option, else the client's reported height (NAWS, a web client's resize), else the new kernel setting `PAGE_LENGTH`; a page holds one line less (the pager's prompt is the last). Enter, `b` and `q` drive it; any other line stops paging and runs as a command; showing the last page ends it. A connection with no prompt line (a test session) gets the pager's prompt as a line of output. A bare enter reaches the input path only while paging, and otherwise shows the prompt again. | The plan named the inputs but not their order, nor what other input does. |
| 2026-11-16 | 10.1 | The input path is one kernel function, `realm.server.world.route_input` (held pages, a pending prompt or the editor, the interceptors, the dispatcher), used by the server, `Simulator.input` and `Simulator.submit_line`; `submit_line` therefore now runs interceptors and prompts too, not only the dispatcher. | The plan asks for pager and editor tests through `submit_line`; two copies of the routing would drift. |
| 2026-11-16 | 10.2 | The editor is kernel (`realm.gateway.editor`), because `building` (`@edit`, `@desc`) and `mail` (which does not require `building`) both open it. `.s` closes it, except that a softcode attribute saved with `@set`'s "will not run" warning keeps it open to fix; saving an empty text clears; an attribute holding a non-string is refused. `@desc <obj>` with no `=` now opens the editor (it used to clear the description; `@desc <obj> =` still clears). `mail <player> = <subject>` and `mail/reply <n>` with no body open it. Lines reach it as typed (`Session.raw_lines`), so WebSocket text is no longer stripped before `submit_input`. Undo, search and a softcode way to open it (BACKLOG notes) are not built. | "Validated on save the way `@set` validates them": `@set` warns and stores, so the editor stores and gives the builder the chance to fix. |
| 2026-11-16 | 10.3 | Aliases live in `basics`. The interceptor contract is extended: an interceptor may return a string, which replaces the line for later interceptors and the dispatcher; the alias interceptor runs at order 5 (after `accounts`' creation at 0 and a freeze at 1, before sleep at 10, so an aliased `wake` wakes). A line with no `$` placeholder gets the typed words appended. An alias is one word (`\w`, up to 20); `alias` and `unalias` cannot be aliased; `ALIAS_LIMIT` (50). No `;` multi-command lines (the dispatcher has none). | An interceptor that dispatched the expansion itself would skip later interceptors and the server's flush of bystanders. |
| 2026-11-16 | 10.4 | Options are offered by a `basics` service, `world.services["options"]` (as `who` fields are), not a new `Feature` declaration. Where they are kept is kernel (`realm.core.options`): the account named by the character's `account` attribute, else the character; `ACCOUNT_TAG` moved there from `realm.std.accounts.account`. A character's own `color`/`prompt` (and any declared option) move to its account in `accounts`' `play()` the next time it enters play; a value already on the account wins and the character's copy is deleted. | The telnet edge, the pager and the prompt are kernel or `basics` and may not import `accounts`; a login observer would have joined the frozen observer lists of games without accounts. |
| 2026-11-16 | 10.4 | Audit G7 closed with two options, `screenreader` (color stripped, lines drawn only from `-=_*~+#\|.:` dropped) and `palette` (`r=m b=c`, a per-player swap of color letters, brightness kept), applied at the telnet edge. The WebSocket writer still sends markup segments for the client to style; the step 16 client is where it honours them. | G7 named both; the WebSocket client draws its own colors. |
| 2026-11-16 | 11.1 | `spec_guard`, `spec_patrolman` and `spec_executioner` map to the `peacekeeper` behavior, not `guard` as the plan says: `guard` blocks movement and would wall off Midgaard's streets, and the importer already mapped the watch to `peacekeeper`. Its new `protect` parameter carries ROM's other duties: `evil` (spec_guard: the lowest alignment below 300 fighting someone else) and `fights` (spec_patrolman: any fight, the higher-level side). It reads `alignment` as a plain attribute, so it stays in `crime`; nothing new is Merc-only and `realm/games/merc/behaviors.py` was not needed. The fido's corpse-eating parameter (`scavenger`'s `eat_corpses`) already existed. | The plan's name for the behavior predates the crime layer. |
| 2026-11-16 | 11.1 | The `#SPECIALS` reader called `line()` after the spec name, which skips to the next line when the spec has no trailing comment, so every other spec of such a file was lost; it now reads only the rest of the line (`Reader.rest_of_line`). | Found by the step's importer test. |
| 2026-11-16 | 11.2 | `autoloot`, `autogold` and `autosplit` are declared by `combat` (its death path reads them), `autoexit` and `brief` by `look`. An NPC's money (`credits`) now goes into its corpse; `get all from <corpse>` and `get gold\|coins\|money from <corpse>` take it and `look` shows it. `autoloot` takes the money too and `autogold` applies only without it (ROM). `brief` shortens only rooms one arrives in (`render_room(..., arrival=True)`: walking, following, recall, respawn, login), not `look` (ROM's `do_look "auto"`). `autoexit` defaults on (the room display unchanged), the others off. | Money is a balance, not an object, so a corpse needed somewhere to hold it. |
| 2026-11-16 | 11.3 | New `GameSystem.share_award(award, members)` (neutral equal shares, Merc ROM's level-weighted `group_gain`) and `on_kill(member, victim)`; `split` is an `economy` command (`split_money` on its service, the party from `social`'s service), `report` a `talk` command built from the kernel's pool functions. `group` was already `party`'s alias. | The party award lived in combat's death path; the system decides the shares. |
| 2026-11-16 | 11.4 | `scan`, `exits` and `where` are `look` commands. `where` lists visible players sharing a `zone:` tag with the viewer's room; rooms in no zone count as one zone. `scan`, `exits`, `where`, `report` (and `split` when the amount is not a number) offer the line to a world `$`-command first: showcase 193 builds `$scan` and 198 `$report`. `sc` became an explicit alias of `score`, since `scan` made it ambiguous. `consider` asks the new `GameSystem.consider` first (Merc: ROM's seven level lines) and then still shows the attitude. | Built-ins must not shadow world verbs; ROM resolves `sc` to score. |
| 2026-11-16 | 11.5 | Alignment moves by Merc 2.2's rule (far more evil victim: up by a quarter of the gap past 500; far more good: down; else a quarter toward 0), not ROM's experience-scaled one, and is shown with ROM's nine words. `GameSystem.repels(player, item)` and `zap(player, item)` (no event; the item falls to the floor) run on `wear`, `wield`, and after a kill changes the wearer. | "Merc parity"; the simpler rule needs no experience figure. |
| 2026-11-16 | 11.6 | `LEVEL_CAP` is the `merc` feature's setting; at the cap experience still accrues. Titles are per class at levels 1, 5, 10, 15, 20, 30, 40 and 50 (`titles` in `MERC_CLASSES`), taken from ROM's title table (the barbarian's are new), shown by `who` through `GameSystem.who_title`. An item's `level` gates `wear` and `wield` (`GameSystem.wear_refusal`), not `quaff` and the rest. | The plan's "a class title per level band"; ROM gates only wearing in `wear_obj`. |
| 2026-11-16 | 11.7 | "Refused ... in combat without a check" read as ROM's: in a fight recall takes a successful `recall` check (`GameSystem.recall_refusal`; Merc's untrained `recall` is wisdom + 37, 50% at 13) and costs 25 experience, as ROM's does; it leaves the fight (`CombatManager.withdraw`). Recall goes home, else the world's start room (it used to refuse a character with no home, which every new character was), and shows the room. | The two readings differ; ROM's is the Diku player's expectation. |
| 2026-11-16 | 11.8 | Midgaard was refreshed with `scripts/dev/refresh_rom_items.py` (its `.are` source is not in the repository): mobs' `gold` became `rom_wealth` plus `credits` (wealth / 100, ROM's silver in gold), the watch's peacekeepers got `protect="evil"`. It has no `anti_*` items, and its stored room flags are empty, so no `no_recall` rooms. A database made from the old file is not migrated: it is content, not storage, and keeps loading. `test_character_sheet`'s level-1 warrior is now refused the armoury's scale mail and is raised to its level first. | The plan's "regenerate it", without the source. |
| 2026-11-16 | 11.4 | `sp` is an alias of `spells` and `rep` of `reply`, as `sc` is of `score`. | `split` and `report` made both prefixes ambiguous; players typed them before step 11 and got `spells` and `reply`. |
| 2026-11-16 | 12.1 | The stomach settings `FOOD_FULL`, `WATER_FULL` and `NEEDS_BASE_WEIGHT` are declared by `rules` (`GameSystem.stomach` reads them, and Merc's baseline uses it without `needs`), `FOOD_GAIN` and `WATER_GAIN` by `items` (`eat` and `drink` read them); the rest by `needs`. New `GameSystem.fill_stomach(player)`, called by `apply_baseline` and by the `rules` login observer, so a Merc character made before this step gets full pools at its next login. | Each setting belongs to the feature that reads it, so a game without `needs` still configures its stomach and its food; the login call is how a saved world is carried over. |
| 2026-11-16 | 12.2 | The weight factor is `weight / NEEDS_BASE_WEIGHT` (1 without a weight) for the loss as well as the stomach, so a base character loses 1 food a tick and empties in about 33 minutes; CoffeeMud loses `weight / 500` (its 150-pound human takes about 2 hours; `FOOD_LOSS = WATER_LOSS = 30` reproduces it) and grows the stomach only per whole 250 pounds. | The plan's "the weight factor" read as the one 12.1 defines; Diku's pace by default; documented in the guide. |
| 2026-11-16 | 12.2 | The reaper runs every `REAP_INTERVAL` (5 s), longer than `NEEDS_INTERVAL` (4 s), so each sweep runs one tick per whole interval passed since the last (at most 10, so a stalled server starves nobody); the clock is `realm.std.needs.needs.now` (monotonic). A sleeping character loses nothing but still counts toward starving, as in CoffeeMud; an exempt one (admin, `no_needs`) neither loses nor counts, but sleep still lowers its fatigue. | A reaper cannot run faster than the reaper loop; CoffeeMud counts hungry ticks outside its sleeping check. |
| 2026-11-16 | 12.2 | Climate tags are read from the room, else from its zone masters' tags (not `zone_property`, which reads attributes); `no_needs` on a zone is a zone master attribute through `zone_property`. The plan's test "a hot dry room doubles thirst" is tested as hot doubles and hot and dry triples (1 + 1 + 1), which is the plan's own rule. | Tags on a master are the natural way to give a zone a climate; the arithmetic follows the rule as written. |
| 2026-11-16 | 12.3 | A need counts and reminds as CoffeeMud does: on the first tick and every `NEEDS_REMINDER_TICKS` after, every tick of the last 30; each need on its own (CoffeeMud lets thirst's near-death line hide hunger's). After the death from hunger or thirst, food and water are full again and the counts cleared (CoffeeMud's `resetToMaxState` on death), whatever `PLAYER_DEATH` did. The counts reset through a `needs` observer on `pool:on_change`, so any source that fills the pool (softcode `mend_pool`) resets them. | Without a refill a respawned character would die again on the next tick. |
| 2026-11-16 | 12.3 | The `rules` service is new: `world.services["rules"]` is a `RulesService` holding `award_filters`; `award(player, amount)` returns what it paid and pays nothing when the filters leave 0. `needs` must come after `rules` and `vitals` in `FEATURES` (its `on_install` appends to their services) and raises a `FeatureError` naming the order otherwise; `CLASSIC` lists it right after `vitals`. | The plan names the service; the order check fails loudly instead of silently skipping the multiplier. |
| 2026-11-16 | 12.4 | `eat` and `drink` keep `restores` for every pool and `charges` for a drink with no liquid (3.4's potion-like flask), so items converted before this step still work; a food with no `nourishment` is eaten whole. A full stomach refuses only an item that would fill it (food with nourishment, a liquid). Messages: "You take a bite of X." for a partial bite, "You drink water from X." (the liquid's name), "You drink water here." from a `water_source` room, and CoffeeMud's "You are no longer hungry.", "You are full.", "You are no longer thirsty.", "You have drunk all you can.". `drink` alone uses a fountain in the room first, then a `water_source` room; `fill <container>` alone does the same; filling a container that holds another liquid is refused, as ROM does. `fill` fires no gated event. | The plan left the messages and the bare forms open; ROM's `do_drink` and `do_fill` find a fountain themselves. |
| 2026-11-16 | 12.4 | The importer uses CoffeeMud's importer's scale: food `nourishment` = ROM hours × 20, drink `liquid_held` and `liquid_remaining` = units × 30 (CoffeeMud multiplies the remaining water by only 10, which leaves a full skin a third full; one factor here). Old-format numeric liquids are named from ROM 2.4's `liq_table` (an unknown index is water, reported). The liquid is only a name: ROM's per-liquid thirst, fullness and drunkenness are not modeled. Midgaard was refreshed with `scripts/dev/refresh_rom_items.py`, which now drops `restores` and `charges` from food and drink. | The plan says "from the liquid table" without a scale; CoffeeMud's is the reference. |
| 2026-11-16 | 12.4 | `fill` made `fi` ambiguous; `fi` is now an alias of `firstaid`, which it reached by prefix before. | Players' short forms keep working (the step 11 lesson). |
| 2026-11-16 | 12.5 | Merc's score lines "You are hungry." / "You are thirsty." come at the end of the sheet, at a quarter or less of the max; softcode `hungry(obj)` and `thirsty(obj)` are True only when the pool is empty (the state that slows recovery), and read the pool only where `pool()` could. Showcase 137 now uses an admin-owned enlistment terminal to give a GURPS crew the pools, since a GURPS game declares none. | The plan's two thresholds kept as written; the showcase is in-game only. |
| 2026-11-16 | 12.5 | `report` says only the pools that recover on their own (`regen`), so Merc's report stays ROM's hp, mana and move; food and water are on `score`. | Reporting a stomach aloud was an accident of listing every pool. |
| 2026-11-16 | 13.1 | Bonding writes four things, all undone by a release: `master`, `following`, the `companion` tag (the index `companions_of` reads through the store's tag index) and the `companion` behavior (the ward on hostile actions). `set_master(npc, master)` is async (it fires `companion:on_bond`/`on_release`, `adata('how')`/`adata('reason')`) and returns the refusal line or None. The third layer of the limit is the neutral `GameSystem.companion_limit` returning 2; the rule layer binds `me` and `level` itself (the `rule` profile binds neither). | The plan's "the neutral answer, 2" needs no separate default once the base hook gives it; events need an await. |
| 2026-11-16 | 13.1 | `COMPANION_LEVEL_DIFF` refuses only a creature too far above ("is too advanced for you"), as the plan says; CoffeeMud also refuses one too far below, and ROM's pet shop refuses any pet above the buyer's level, which cannot be said with 0 meaning off. | The plan's rule; noted in the guide. |
| 2026-11-16 | 13.1 | `order` finds the command a line would run with a new kernel method, `CommandDispatcher.resolve(line)` (token, name, alias, unique prefix); a line that resolves to no built-in (an exit name, a softcode `$`-command) is allowed and meets the companion's own permissions. The companion's replies come back through the `@force` puppet session. A character who is itself a companion cannot order (ROM). | `order` must judge a command before running it; the dispatcher's own matching is the only right answer. |
| 2026-11-16 | 13.1 | Fighting together is an observer registered in `on_install` (after `combat`'s, so the encounter exists) on every hostile action, each round's `combat:on_attack` included; a companion joins through a new `CombatManager.assist(helper, target)`, which changes no one else's target. A master's hostile act on its own companion releases it (CoffeeMud breaks a charm so), so the ward never leaves a companion locked in a fight with its master. The kill award goes to the master's party; autoloot stays the killer's (ROM's pets do not loot). | `initiate` would turn the enemy on the companion; the plan's ward alone would leave an ordered attack blocked every round. |
| 2026-11-16 | 13.1 | Companions leave on `event:disconnect` (quit, logout, the character menu, a dropped link once `LINKDEAD_SECONDS` pass) and come back on `event:connect`; the room they waited in is `companion_room`. A charmed creature is freed instead (CoffeeMud and ROM end a charm when the charmer quits). A deleted master is found by a reaper sweep (`release_orphans`): nothing announces a deletion. `wandering` and `aggressive` leave an NPC with a `master` alone (ROM skips charmed mobs). | Only these events exist; ROM saves pets with the player but frees charmed mobs. |
| 2026-11-16 | 13.2 | `charmed` subclasses `TimedEffectBehavior`, so `companions` requires `effects` as well as `social`. It is applied by a new abilities effect type `charm` that calls the `companions` service (as `rescue` and `disarm` call `combat`), not by the generic `behavior` effect: the limit, the level check and the `pvp` zone rule must refuse before anything attaches, and the bond fires `BOND`. On expiry the release fires `RELEASE` (`charm_ended`); removed early (`remove_effect`, a respawn's cleanup) it unbinds without the event. Softcode `apply_effect` does not offer `charmed`. | A behavior's `attach` cannot refuse or await. |
| 2026-11-16 | 13.2 | `charm person` in `merc-classic`: ROM 2.4's mage spell (level 20, 5 mana), `per_level: 4` beats (ROM's `number_fuzzy(level / 4)` hours at 60 s, against a 4 s beat), `save: negates`, level check (target above the caster fails). It is not `hostile`: ROM's failed charm starts a fight, but a hostile charm that lands would be the master attacking its new companion, which releases it. Also refused: a target that already has a master, a caster that is charmed, the caster themself. | Taken from ROM; the hostility conflicts with 13.1's rule. |
| 2026-11-16 | 13.2 | `pet_stock` holds object ids. The importer names the prototypes (`rom_mob_<vnum>`) of every mob reset into the next room, without ROM's `ACT_PET` requirement (Midgaard's kitten to wolf do not carry it), and gives each a `value` of ROM's `10 * level * level` silver in gold (`pet_price`). A pet shop room with no shopkeeper sells nothing (ROM needs none). Midgaard's stored room flags are empty (its `.are` is not in the repository), so the refresh script gained `--room-flags VNUM=LETTERS` and Midgaard was refreshed with `--room-flags 3031=M`. | The plan's rule; the source is missing. |
| 2026-11-16 | 13.3 | Only a mount's master rides it, with no skill roll (SMAUG's `mount` is a skill anyone may try on any mountable mob). A mount with no `move` pool carries its rider free; a rider spends no food or water walking (`needs` asks the service, as CoffeeMud spends only a walker's energy); a fleeing rider's mount bolts with it (CoffeeMud), though `social` brings no followers on a flee. A ridden mount refuses to walk off from under its rider. | The plan names riding a companion; the rest follows CoffeeMud. |
| 2026-11-16 | 13.3 | The kernel seam has a third phase, `own`, for the walker's own line ("You ride north on a grey mare."); "" means no line (a ridden mount's own steps). Describers are asked for walks (`move_through_exit`), not for `move_to` placements. | "The actor's own line follows the same hook" needs its own phase: the room's template cannot be the walker's. |
| 2026-11-16 | 13.3 | The mount is left out of room listings by a `ridden` tag the room renderer skips (the plan's "ridden marker"), not a sight rule or the grouping hook; `scan` still names it. Dismounting: `sleep` asks the `companions` service (there is no propagated position event); going down is an observer on `combat:on_death`; being placed elsewhere (recall, a teleport) is an observer on `event:on_enter` without an exit. `mounted_modifiers` returns `{"attack": n, "defense": n}`, added to the rider's attack roll and against attacks on the rider (`CombatSystem.attack` asks through the service). | The plan left the hiding choice and the hook's shape open. |
| 2026-11-16 | 13.1 | `mount` made `mo` ambiguous; `mo` is now an alias of `credits` (`money`), which it reached by prefix before. No other 1-4 letter prefix of an existing command or showcase `$`-verb changed; showcase 082's suggested `$order` verb is renamed `$backissue`, since the built-in `order` would shadow it. | The step 11 lesson. |
| 2026-11-16 | 13.3 | Showcase 65 is rebuilt on the feature (heel calls `set_master` and restores `following`; stay deletes only `following`); showcase 158 drops riding by containment for a `$claim rusty` that calls `set_master`, the built-in `mount`/`dismount`, and a `no_mount` stable. | The plan's rewrite; the built-in `mount` shadows the old `$mount`. |
| 2026-11-16 | 14.1 | Governments keep CoffeeMud's percentage limits (`max: "2%"`, at least 1 holder). Powers map `CREATE_MOTD`/`READ_MOTD`/`CLAN_BENEFITS`/`CLAN_TITLES` to `motd_write`/`motd_read`/`benefits`/`titles`; `PROPERTY_OWNER`, `ORDER_*`, `CREATE_LAW`, `ENCHANT`, `MORGUE`, `JOURNAL` and `CREATE_CALENDAR` are dropped. Only acts are voted on (accept, reject, assign, exile, set_home, set_donate, premise, motd_write, withdraw, tax, declare); privileges never are. The co-op's House Mother and Father carry no gender locks; the plutocracy's lower positions are Tenant and Serf (CoffeeMud reuses Hard Worker and Worker); level benefits are only CoffeeMud's hit point, mana and movement bonuses at its levels. Defaults: `vote_days` 24, `vote_quorum` 50 (a shipped government without `VOTING` data gets 24 and 100). | REALM characters have no sex, no stat, armor or faction adjusters to grant; the plan's rule ("a power no position holds outright is voted on") agrees with CoffeeMud's `VOTING` lists for the eight shipped governments. |
| 2026-11-16 | 14.1 | `auto_promote: rank`'s "next rank down" is the highest rank anyone below the top holds, and a vacancy is no holder of any top-rank position (the co-op has two). `xp`/`gold`: the first position goes to the leader by that measure (a holder keeps it on a tie; a challenger must have given something), the displaced holder to the accept position; `level` is re-evaluated by the upkeep, since nothing announces a level change. | A gang of a boss and members must still find an heir; a tie should not flip the leader back and forth. |
| 2026-11-16 | 14.2 | An applicant holds its place in the category but is not in the clan: `clan()`, `who`, clan talk and the member count leave it out, and `clan:on_join` fires on acceptance, not on applying. The founder must pass the top position's lock and `required_lock`. | A door locked by clan must not open for someone who has only applied. |
| 2026-11-16 | 14.2 | Assigning someone to a full **top** position makes them its holder and the longest holder steps down to the accept position (CoffeeMud's `ClanAssign`); any other full position is refused as planned. The last holder of the top rank cannot be moved off it until replaced. The rank rule also covers the member acted on: nobody assigns or exiles a member at or above their own rank unless they hold the top position. A passed vote is exempt from the rank rule. | Without the displacement a fellowship could never vote in a new First Citizen (max 1) and a boss could never hand over. |
| 2026-11-16 | 14.2 | `clan disband` asks for `clan disband <name>` as its confirmation instead of a yes/no prompt. A subcommand that needs a power acts in the first of the character's clans whose position holds or may vote on it (the default category first); `leave`, `who`, `info`, `relations` and `vote` take a clan name. | A session prompt holds the command until the next line; the plan does not say how a member of two clans picks one. |
| 2026-11-16 | 14.3 | The proposer's yes is counted when a vote opens; "fails as soon as impossible" is judged on the ballots cast so far. A vote stores resolved arguments (member id, position, room id, amount, clan and relation); a passed vote re-checks them when it is carried out and announces a refusal. | CoffeeMud skips the vote when one member can vote; counting the yes gives that and needs no special case. |
| 2026-11-16 | 14.3 | Clan times are wall-clock (`realm.std.clans.clans.now`, which tests patch); a game day is `3600 * HOURS_PER_DAY / GAME_TIME_RATIO` real seconds from the `clock` service's calendar, one real hour without `clock`. The reaper closes expired votes every sweep and runs the upkeep at most once a game hour. | Game time is derived from wall time, so the two count the same; account `last_login` is wall time too. |
| 2026-11-16 | 14.4 | New `GameSystem.spendable_award(player)` / `spend_award(player, amount)` for `clan donate xp` (neutral None; `PointBuyMixin` unspent `character_points`; Merc experience toward the next level, so giving never costs a level); it needs the `deposit` power. Clan experience is cumulative (CoffeeMud's `setExp`), `xp_per_level` defaulting to its `DEFAULT_XP_FORMULA`. Pool bonuses and tags are remembered on the character (`clan_pool_bonus`, `clan_tags`) so only what clans gave is taken back. Promotions and level events raised by the synchronous tax filter fire as tasks right after it. | The plan names the command but not where the game system's spendable currency lives; `award_filters` are synchronous. |
| 2026-11-16 | 14.6 | "Played" is: online now, else the account's `last_login`, never earlier than joining the clan. Overthrown leaders step down to the accept position. The last member to leave dissolves the clan at once. | A character without an account (or newly joined) must not count as long gone. |
| 2026-11-16 | 14.7 | In a lock expression the one trying is `caller` (REALM's lock vocabulary), so the plan's `@lock door = clan(enactor) == 'Ravens'` reads `clan(caller) == 'Ravens'`; the read-only functions take an optional `category`; `clan_has_power` is true only for a power held outright. The clan events target the clan object (as a channel line targets its `channel_def`). `ct` alone shows the recent lines. | `enactor` is not bound in the lock profile. |
| 2026-11-16 | 14.7 | `channels` offers its delivery path as `world.services["channels"]` (`deliver`, `remember`; `broadcast` now uses it), and `basics` offers `recall`'s rules as `world.services["recall"]` (`to(player, room, session)`, `cmd_recall` split into `recall_to`). | The plan says clan talk and `clan recall` reuse them through services; neither had one. |
| 2026-11-16 | 14.7 | `cl` is now an alias of `close` and `@cl` of `@clone`, which they reached by prefix before `clan`/`clantalk` and `@clan`. No other 1-4 letter prefix of an existing command changed (scripted against the dispatcher, with and without Merc), and no showcase `$`-verb or exit collides. | The step 11 lesson. |
| 2026-11-16 | 14.7 | Showcase 221 and 222 are rebuilt on the feature (an admin `@clan create`s the Void Runners, a back room locked with `clan(caller)`, lockers warded by `clan()` and `clan_has_power()`); 223 is the `union` government; each build imports the governments with `@pack clan-governments`, which `import_pack` now skips when present (`clan_government_def` joins its idempotent tags). | The showcase harness has no money and no `init_world`. |
| 2026-11-16 | 15 | References: tbaMUD's autoquests (`src/quest.c`, `quest.h`) and CoffeeMud's QuestMaker templates (`resources/quests/templates`). Taken: the questmaster's list/accept/abandon/history, objective types (find, kill, return; CoffeeMud's collect, delivery, killer, travel), time limit, repeatable, gold/experience/object rewards, a criteria mask (as `accept_lock`). Left out: quest points, quit penalties, "save a mob", "clear a room", escort/protect/capture/dispel/invasion templates, world-timed auto/competitive/random/holiday quests, faction rewards; one active quest at a time (tbaMUD) is not enforced. Recorded in docs/guides/quests.md. | The maintainer's references; each left-out piece builds on `custom` objectives and the hooks. |
| 2026-11-16 | 15.1 | `giver` is a name, an `#id` or a matcher dict. A giver is an NPC (tagged `npc`) or anything with the `quest_giver` behavior; the behavior's `quests` lists quests an object offers without being their giver (they are handed in to the giver). A quest with no giver may be taken with `quest accept` anywhere. | The plan names both `giver` and the behavior without saying how they relate; the tag test keeps the `(!)` marker from matching every listed thing. |
| 2026-11-16 | 15.1 | An objective's matcher is any of `id`, `name` (word-prefix, as players type), `tag`, `prototype_vnum`, all of which must agree; an optional `key` (default: its kind; two in a stage with one key are refused) and `text` (the journal's label); `deliver` names its recipient in `to`; `use` matches the object used or the item used on it. An item reward is a prototype's object id or the name of one `prototype`-tagged object. A malformed definition is reported through the definition loader (WARNING, naming the quest and the fault) and skipped; boot and `@reload` read the definitions so the warning appears then. | The plan leaves the matcher's shape and the error's form open; the loader already logs unreadable definitions by name. |
| 2026-11-16 | 15.2 | `stage` is 1-based, or `"ready"` once every stage is met and a giver waits. Counts are per stage, cleared when a stage ends (kept at ready, for the hand-in's check). A `collect` objective counts what is held now (live, not stored) and is checked again at the hand-in; `consume` takes the items when their stage ends, at the hand-in for a giver quest's last stage. Kills count on any `combat:on_death` with a killer. `quest:on_advance` fires per stage, not per count. Quest events target the giver when they happen at one (accepting, handing in), else the quest's definition object. The time limit runs until the hand-in. | Details the plan leaves open; a held count needs no "counted" bookkeeping, and the giver as target lets its own `ON_QUESTCOMPLETE` speak. |
| 2026-11-16 | 15.2 | The index maps each objective kind to the online characters with one in their current stage. It is rebuilt (from the playing sessions) whenever the quest definitions change, at boot and `@reload`; login and logout add and drop a character; accepting, advancing and ending a quest re-index them. The reaper sweeps only indexed characters with a deadline; an absent character's expired quest fails at their next login. | "Online characters", per the plan; a definition edited in play must not leave the index stale. |
| 2026-11-16 | 15.3 | `quest_offer(obj, quest)` starts the quest for `obj` as if accepted (False when they may not take it) rather than prompting. The four builder functions need HARM and act after the script (queue kinds `quest_offer`, `quest_advance`, `quest_complete`, `quest_fail`). For `scope = account`, `quests_done` lives on the account; another character may take the quest while one is on it. | The plan names `quest_offer` without saying what offering is; a session prompt would hold the player's next line. |
| 2026-11-16 | 15.3 | New service seams: `RulesService.award(player, amount)` (the module's `award`, filters and all) and `world.services["achievements"]` (`grant`, `has`), offered by `achievements`' `on_install`. | `quests` may not import `rules` or `achievements` (boundary test), and the plan's "achievements service" did not exist. |
| 2026-11-16 | 15.3 | `talk` with no name, a name nobody here answers to, or a player, is offered to the world's softcode `$`-commands first, so showcase 067's `$talk` still works. `ta` is now an alias of `get`, which it reached by prefix (through `take`) before `talk`; `qu` and `que` were already ambiguous and now also list `quest` and `quests`; no other 1-4 letter prefix changed (scripted against the dispatcher, with and without Merc). Of the showcase's `$`-verbs only 198's `$quests` (rewritten) and 067's `$talk` collide. | The step 11 lesson. |
| 2026-11-16 | 15.3 | The converted Midgaard area places no baker (and its bottle of beer carries mob 3001's shopkeeper behaviors: a `rom_import` defect, logged in BACKLOG). The template's `init_world` clones the baker from `rom_mob_3001` into the Bakery with a loaf to sell, then imports `data/quests.json`: "Fido trouble", five kills of `prototype_vnum` 3062 for 250 award and a bread (`#rom_obj_3011`), repeatable hourly. An existing Midgaard database does not get it (`init_world` runs once). | The plan's "for the baker" needs a baker; re-converting the area is a separate fix. |
| 2026-11-16 | 15.3 | Showcase 198 is The Cinder Road (use, then collect with `consume`, a giver, `ON_QUESTCOMPLETE`, a `quest_state` gate); 199 is a giverless `deliver` quest offered through `quest_giver`, with `time_limit`, `on_accept` minting the orders and `on_fail` tagging them stale (the Agent's `ON_RECEIVE` now only answers); 200 is a giverless `collect` by tag, whose count is what is held rather than the old monotonic tally (its Going further shows the `custom` objective for that). 201's build is unchanged; a Going further entry adds a `custom` objective to put the fork in the journal. | "Rewrite 198 to 200 as quest definitions; 201 stays softcode." |
| 2026-11-16 | Decisions | D3 was not answered; the default holds: one static page (`realm/web/index.html`, HTML, CSS and plain JavaScript in one file, no build step, nothing fetched from elsewhere) served at `/` by the existing WebSocket server when `ENABLE_WEBSOCKET` and the new `WEB_CLIENT` are set. | The plan's default when nobody answers. |
| 2026-11-16 | 16 | The page is titled with `GAME_NAME` (a `{{GAME_NAME}}` placeholder filled, escaped, when the server reads the page at start) and connects to `ws` relative to its own URL, so it works behind a proxy that serves the game under a path. `WEB_CLIENT` without `ENABLE_WEBSOCKET` logs a WARNING with the fix at start. `WebSocketServer.make_app()` builds the routes without running them, for aiohttp's test client. The wheel needed no `pyproject.toml` change: hatchling ships every file under `realm/` (checked by building one). | The plan named the setting and the route, not how the page finds the socket or names the game. |
| 2026-11-16 | 16 | The player's `color`, `screenreader` and `palette` options (10.4) are applied on the server, at the WebSocket edge, as at telnet: one `realm.core.options.display_for(player)` (a `Display`) used by both edges, and `realm.core.markup.recolor` for a style. Color off and screenreader send plain text (screenreader also drops decoration lines); a palette swaps the letters in the segments' style keys. The page itself has no settings of its own. | Step 10's log left the honouring to this step; doing it on the server keeps one rule for both protocols and works for any WebSocket client, not only this page. |
| 2026-11-16 | 16 | The WebSocket prompt frame carried raw markup (`\|r`); it is now styled like text: `text` plain, plus `segments` when colored, with the options applied. The pager's prompt arrives as a prompt frame and the page shows it in the prompt line; a blank enter is sent as an empty line, which turns the page. The page reports its output area in characters as `resize`, so `page_length` is what fits on the screen. | The page has to draw the prompt; raw markup was a defect from step 3. |
| 2026-11-16 | 16 | **Kernel addition:** `Session.write_prompt` sends `Char.Vitals` (every declared pool plus the damage and vital pools, `name` and `max_name`; `realm.gateway.session.vitals_of`) to any client with an OOB channel whenever it differs from the last one sent. The page draws a bar for each `name` with a `max_name` and merges each `Char.Vitals` it receives (combat's `{hp, max_hp, round}` included). | The engine sent `Char.Vitals` only in combat rounds, so the bars the step asks for would have been empty out of a fight and stale after one. The prompt is the one point every protocol reaches after each batch of output. GMCP clients gain the same. |
| 2026-11-16 | 16 | A plain-text frame that starts with `{` is sent as `{"type": "text", "text": ...}`, so a string frame starting with `{` is always JSON. Lines that carry a password (`connect`/`create <name> <password>`, any first word containing `password`) are echoed masked in the page and kept out of its input history; the page echoes commands with `aria-hidden` so a screen reader does not read them back. | Without the first, `@emit {"type": "prompt", ...}` could pass for a frame in other players' clients. The login line carries the password in clear, and nothing tells a WebSocket client to hide it. |
| 2026-11-16 | 17 | `realm init <name> --system merc --template midgaard` is accepted: `--system` with `--template` may name the template's own rules system (read from the `from realm.games.<x> import <X>System` line of its `rules.py`) and is refused, with the one to use, when it names another or the template has no `rules.py` (step 1 refused the pair outright). | The plan's first line, the Acceptance and the new guide use exactly that command. |
| 2026-11-16 | 17 | `test_first_hour` runs a real `GameServer` on its own database in a `realm init` directory (`tick_interval=0`, no telnet). A line goes in through `Session.submit_input` and on through `GameServer._on_command`, as the input pump would call it (the `Simulator.submit_line` pattern), a second of fake clock per line; time passes by moving one fake clock patched into every call-through clock and calling the server's `_reap`; combat rounds are the encounter's `resolve_round`, fired by hand; spawners are ticked by hand for the fidos to return. Dice are seeded, and loaded (`Fate`: an attacker's dice and the defense against it, or a character's own checks, at best or worst) for the fights the story needs won or lost. Line 11's quest is taken before line 3 so the fidos count; each section names its line. | Login, backup and restore need a real server and a file; the beat loop and the server's heartbeat run on wall-clock timers; seeded dice alone would make the story change with any new roll in the engine. |
| 2026-11-16 | 17 | The Midgaard template ships three small data files: `achievements.json` (Friend of the Baker, granting the tag `baker_friend`, the reward of "Fido trouble"), `stable.json` (a brown horse, tagged `mount`, added by `init_world` to the pet shop's stock) and `skills.json` (lore, `progression: idle`). The welcome banner now says `create` / `connect <account> <password>`. | On a fresh install lines 4 (no skill could be studied: Merc's are all `use`), 6 (no achievement existed) and 9 (ROM's Midgaard sells no mount) could not be done without a builder; the banner still spoke of creating a character. |
| 2026-11-16 | 17 | In the test the superuser pays for her clan with `@set me/credits = 10080`; `CLAN_COST` stays 10000. One companion at Merc level 3 (`1 + level // 10`), so the dog is dismissed before the horse is bought. | Nobody earns 10000 gold in a first hour; both are the shipped rules, shown as they are. |
| 2026-11-16 | 17 | Engine fix: a character out of play (quit, or switched away from with `characters`) is not listed in its room or by `scan`; a link-dead one still is, marked (`realm.std.look.render.out_of_play`: not online and not `linkdead`, in a world with a session manager). Not a `sight_rule`. | Cole stood listed under "Players here" while Bree played (Diku takes a quitter out of the world; Penn leaves a disconnected player out of `look`). A sight rule would hide session-less players in the many tests and tools that make them. |
| 2026-11-16 | 17 | Engine fix: `realm.commands.base.find_victim(ctx, name)`: `kill`, the combat maneuvers' targets, `firstaid`, a typed ability and `cast` aimed at `victim`/`ally` (`realm.std.abilities.target_kind`) match a player, an NPC or anything with a damage pool. | `kill fido` beside "the corpse of fido dog" was ambiguous, and with only the corpse there `kick fido` kicked the corpse. Things with a damage pool stay targets (a training dummy, a ship). |
| 2026-11-16 | 17 | Engine fix: a fight continues only while a living participant has another as its target (`CombatEncounter._check_continue`). | Bree killed by the vagabond left it and the alley cat in an encounter with no one to hit, `in_combat` for ever. |
| 2026-11-16 | 17 | Engine fix: `get_combatant(obj)` rebuilds its cached wrapper when the cached one wraps another object with the same id. | After `realm restore` and a new server in the same process the vagabond was fought through the wrapper of its old object: "defeated" at 67 hp, and the pet never joined. |
| 2026-11-16 | 17 | Importer fixes (`realm/tools/rom_import.py`): resets read as ROM's `load_resets` (a `*` line is a comment, a reset's trailing comment ends with its line; `O` has three fields after the if-flag, not four); `#SHOPS` patches the keeper mob only and `P` puts into an object only; a spawner's or zone reset's prototype carries `prototype_vnum`; `ACT_SCAVENGER` maps to a scavenger that picks up and eats no corpse (`scavenger_behavior()`). `scripts/dev/refresh_rom_items.py` mends shops on objects, spawner vnums and scavengers, and the shipped Midgaard was refreshed with it (22 objects lost a shop, 50 spawners gave their mob its vnum, 42 scavengers lost their appetite). | The baker's missing and the beer's shop (BACKLOG, step 15) were these; respawned fidos did not count for "Fido trouble", which needs five kills and Midgaard places four; cityguards ate the corpses players had just made. |
| 2026-11-16 | 17 | Midgaard is not re-converted: its `.are` is not in the repository, so the placements the old reader lost (the baker, the mage, warrior and thief guildmasters) stay lost. The template's `init_world` keeps cloning the baker; the cleric's guildmaster (`teaches: class`) teaches every class. Logged in BACKLOG and the README's "not built yet". | Re-creating them by hand would be guessing at the source; the importer is fixed and tested for the next conversion. |
| 2026-11-16 | 17 | Engine fixes found running the guide on a real `realm start` over telnet: `quit` (and anything that destroys its own session) through the input pump no longer cancels its own teardown (`Session.stop_input_pump` leaves the running pump alone, which then ends); help and the `channels` footer escape pipes (`on\|off\|history` lost `\|h` to the bold markup); the prompt is not shown under the class menu (`basics`' renderer returns None while `chargen_step` is set). | The session stayed registered with its character and the connection open; the text was garbled; "<20hp 100m 100mv>" appeared before there was a class. The test drives `_on_command` directly, so the pump defect has its own test in `test_session.py`. |
| 2026-11-16 | 17 | Not fixed, logged in BACKLOG and the README: pets and mounts stay behind on `recall`; `Room.Info` only on movement; ability cooldowns, corpse locks, mail, achievement and channel dates and the combat beat loop read the wall clock directly; a wall prints the typist's prompt twice. aiohttp is not in the dev venv, so the four browser-client tests skip. | None of them is needed by a line of "What 'complete' means here"; each is small and named for whoever takes it. |
| 2026-11-16 | 17 | `docs/getting-started/your-first-mud.md` was written from a real `realm init` and `realm start` in a scratch directory, played over telnet by a script, two connections at once; the fight, death, shop and practice excerpts are from `test_first_hour`'s run of the same game. Linked first in the README, `docs/index.md` and `mkdocs.yml`. | The plan: run every doc example. |
| 2026-11-16 | 17 | 0.3.0: the CHANGELOG's 0.3.0 entry is a release entry with "Upgrading from 0.2.0", "What did not change" and "New settings" before the step entries; `docs/reference/public-api.md` gains rows for `accounts`, `companions`, `clans` and `quests` and lists the features with no public names, and `tests/test_public_api.py` checks the page against the frozen lists. | The plan's last tasks; the page had not been updated since 0.2.0. |
