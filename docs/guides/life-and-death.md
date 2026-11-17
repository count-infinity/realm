# Life and Death

How a character is hurt, recovers, goes down and carries on, alone, with no
other player to help. Four pieces do it:

- **Regeneration** (the `vitals` feature): out of combat, pools refill over
  time.
- **Positions** (`vitals`): `rest` and `sleep` refill them faster, at a
  cost.
- **Coming round** (`combat`): an unconscious character whose vital pool
  rises above spent gets up.
- **Death** (`combat`): what happens when the vital pool is spent: by
  default a player leaves a corpse and wakes at home; a game can have its
  players fall unconscious instead.
- **Hunger, thirst and fatigue** (`needs`): a stomach that empties with
  time and walking, food and drink to fill it, slower recovery while
  hungry or thirsty, and death after hours ignored.

Under the Merc rules, walking also spends movement points, which
regeneration then restores.

## Regeneration

Every `REGEN_INTERVAL` seconds (default 15), each character (a player or
an `npc`) that is not tagged `in_combat` regains some of every pool below
full. A down pool (hit points, mana) rises toward its max; an up pool
(stress, heat) falls toward its floor. A pool with no max does not
regenerate.

How much is the game system's answer, `regen(obj, pool_name)`:

| System | `regen` per tick, standing |
|---|---|
| neutral `GameSystem` (GURPS, D20) | a twentieth of the pool's max, at least 1 |
| `MercSystem` | `hp`: (constitution − 3 + level ÷ 2) ÷ 4; `mana`: (the better of intelligence and wisdom + level) ÷ 4; `move`: (dexterity + level) ÷ 4; each at least 1 |
| no `rules` feature | 1 |

That amount is multiplied by every multiplier on the `vitals` service:
`REST_REGEN` (2) while resting, `SLEEP_REGEN` (4) asleep, and whatever
other features add (`needs` halves it for hunger and for thirst). A feature
adds its own factor like this:

```python
@feature.on_boot
async def _sickness_slows_healing(world):
    vitals = world.services.get("vitals")
    if vitals is not None:
        vitals.multipliers.append(
            lambda obj, pool: 0.5 if obj.has_tag("diseased") else 1.0)
```

A pool that should not refill on its own says so in its definition:

    @set ship/pools = {"shields": {"overflow": "hull", "regen": False}, "hull": {}}

Unconscious characters regenerate too. That is how a lone player knocked
out comes round.

Only characters known to be below full are swept: the `vitals` feature
notes them as their pools change, and finds the ones saved below full when
the server boots.

## Positions: rest, sleep, stand

A position is a tag: `resting` or `sleeping`. Standing is neither.

| Command | Does |
|---|---|
| `rest` | sit down: regeneration × `REST_REGEN`. From sleep, you wake and sit up |
| `sleep` | lie down: regeneration × `SLEEP_REGEN` |
| `stand` (or `wake`) | get up |

Neither `rest` nor `sleep` works in a fight. A resting or sleeping
character does not walk ("You need to stand up first."). Anyone who does
something hostile to them (an attack, a hostile spell) stands them up.

A sleeper (Decision D4):

- sees nothing but themselves;
- hears nothing said or done in the room. What is addressed to them, where
  they are the target of the action, still arrives, so a tell gets
  through;
- may type only `wake`, `stand`, `help`, `who`, `score`, `quit`, `tell`
  and `reply`. Anything else is answered "You are asleep."

Other people see `Pat (resting)` or `Pat (sleeping)` in the room.

A game that wants none of this leaves `vitals` out of `FEATURES`. The
showcase has a softcode version of resting for such a game
([138](../showcase/138_sleep_rest.md)).

## Who a fight is with

`kill <name>`, a combat maneuver's target, `firstaid <name>`, a class skill
typed at someone (`kick fido`) and `cast <spell> <name>` look for a player,
an NPC, or anything with a damage pool (a training dummy, a ship's hull)
in the room, never a corpse or a plain thing: `kill fido` beside "the
corpse of fido dog" means the fido. A fight goes on while one living
fighter has another as its target; when the last of one side dies, flees
or leaves, the others stop (two mobs whose quarry is gone do not stay in
combat).

## Coming round

A character whose vital pool is spent and whose death rule is
`unconscious` is tagged `unconscious`. It cannot walk or fight. When its
vital pool rises above spent again, by any cause (regeneration,
`firstaid`, a healing spell, softcode `heal()`), the tag goes, the
character is told "You come to." and the room sees them stir.

## Death

When an object's vital pool is spent, the combat manager's death path runs
once. `ON_DEATH` fires first, then the body is dealt with as its
`when_spent` attribute says. Without one, a player follows the
`PLAYER_DEATH` setting and anything else leaves a corpse.

| `when_spent` | What happens | Who |
|---|---|---|
| `unconscious` | tagged `unconscious` where it fell; comes round as it heals | anyone |
| `respawn` | dies: see below | players only; a player's default |
| `corpse` | a lootable corpse holding what it carried and its money; the killer's party is paid the kill award (see below) | not players; anything else's default |
| `destroy` | destroyed, as `@destroy` does it | not players |
| `none` | nothing; the object's `ON_SPENT` softcode decides | anyone |

When a player's party kills something, the game system divides the award
among the party members in the room (`share_award`: equal shares, or
under Merc by level, so a level 3 and a level 1 split it 3:1) and then
each sees the kill (`on_kill`: under Merc, alignment moves). The corpse
holds the victim's money as well as its belongings; the killer's
`autoloot` setting takes everything from it at once, `autogold` only the
money, and `autosplit` shares money taken that way with the party, as
`split <amount>` does ([Player settings](character-sheet.md#player-settings)).

`PLAYER_DEATH` (`"respawn"` or `"unconscious"`) is the default for players.
It is `"respawn"` unless a game's `config.py` says otherwise, whatever its
rules (GURPS, D20, Merc or none): a player who comes round where they fell
can wake in a room of the creatures that dropped them (Decision D1). A
game whose players should fall and wait for help (a duel, a clone bay)
sets:

    PLAYER_DEATH = "unconscious"

Under `respawn`, a player who dies:

1. fires `ON_DEATH` with `adata('fatal')` True;
2. leaves `corpse of <name>` where they fell, holding everything they
   carried except items tagged `soulbound`. For `CORPSE_LOCK_SECONDS`
   (default 300; 0 for never) only they, and administrators, may take from
   it. It rots like any corpse when the `npc` feature is loaded, and
   scavengers leave it alone;
3. pays the game system's `on_death(player, killer)` penalty. The neutral
   one is nothing; Merc takes a quarter of a level's experience, never a
   level;
4. returns to their `home`, else the start room (where new characters
   begin), one point short of spent in their vital pool (1
   hit point; one below the top of a harm clock), standing, out of
   combat, and with every timed effect ended. They see the room they wake
   in.

A player's death pays no kill award.

    @set Pat/when_spent = unconscious         # this one player never dies
    @tag the Vorpal Ring = soulbound          # stays with its owner through death

## Movement costs movement (Merc)

Under Merc, a player pays for each step out of the `move` pool: the
destination room's `move_cost` attribute, else the cost of its
`sector:<name>` tag (the ROM importer writes these), else 1.

| Sector | Cost | Sector | Cost |
|---|---|---|---|
| inside | 1 | mountain | 6 |
| city | 2 | water, water_swim | 4 |
| field | 2 | water_noswim | 1 |
| forest | 3 | underwater, desert | 6 |
| hills | 4 | air | 10 |

A player who cannot pay stays put: "You are too exhausted.", and the exit
fires `ON_FAIL` with `adata('reason')` `exhausted`. NPCs and a fleeing
character walk free. Resting restores movement fastest.

    @set The Long Stair/move_cost = 8

## Hunger, thirst and fatigue

The `needs` feature, after CoffeeMud's. Each need is a pool, so everything
that works on pools works on it: the prompt shows it (`{food}`,
`{water}`), softcode reads it (`pool(enactor, 'food')`), `restores` on an
item fills it.

| Pool | Kind | Spent | Who has it |
|---|---|---|---|
| `food` | down, `regen: False` | at 0: hungry | Merc characters (Decision D6) |
| `water` | down, `regen: False` | at 0: thirsty | Merc characters |
| `fatigue` | up, `regen: False` | at its max: exhausted | nobody, until a game adds it |

A character has a need exactly when it has that pool. The game system
decides who does: `MercSystem.pools()` declares `food` and `water`, and a
new Merc character starts with both full. GURPS and D20 declare neither.
NPCs are never given them. A Merc character made before this (a saved
world) is given full ones when it next logs in.

### The stomach

`GameSystem.stomach(obj)` says how much a character holds when full:
`FOOD_FULL` (500) and `WATER_FULL` (1000), scaled by `weight /
NEEDS_BASE_WEIGHT` (150) when the character has a `weight`. A 300-pound
ogre holds 1000 and 2000.

### Getting hungry

Every `NEEDS_INTERVAL` seconds (4) each online player with needs loses
food and water:

- food: its weight factor (`weight / NEEDS_BASE_WEIGHT`, 1 without a
  weight), times `FOOD_LOSS` percent (100);
- water: the weight factor times the room's thirst rate, times
  `WATER_LOSS` percent (100).

Fractions carry over (`food_debt`, `water_debt`), so a light character
still gets hungry, only slower. Walking a room costs one more interval's
loss. At the defaults a character of the base weight empties a full stomach
in about 33 minutes and runs dry in about an hour, sooner in the heat.

Nothing is lost while asleep, by an administrator, by a character tagged
`no_needs`, or in a zone whose master sets `no_needs`. Time offline does
not count for anything.

The thirst rate of a room is 1, plus 1 for each of `climate:hot`,
`climate:dry` and `climate:windy`, minus 1 for `climate:wet`, never below
0. The tags are read from the room, else from its zone masters:

```text
@tag here = climate:hot
@tag here = climate:dry              # thirst three times as fast here
@create Sea Wind
@zone/master Sea Wind = coast
@tag Sea Wind = climate:windy        # every room in the coast zone
@create Inn Ledger
@zone/master Inn Ledger = inn
@set Inn Ledger/no_needs = 1         # nobody in the inn zone gets hungry
```

### Going without

While food (or water) is spent, the character counts `hungry_ticks` (or
`thirsty_ticks`), reset the moment the pool rises above 0. On the first
tick and every `NEEDS_REMINDER_TICKS` (60) after, they are told how far
along they are toward the death limit:

| How far | Hunger | Thirst |
|---|---|---|
| the first half | You are hungry. | You are thirsty. |
| past half | You are famished! Eat something! | You are parched! Drink something! |
| past three quarters | You are starved! Eat something! | You are dehydrated! Drink something! |
| each of the last 30 ticks | You are starved, and near death. EAT SOMETHING! | You are dehydrated, and near death. DRINK SOMETHING! |

The limit is `HUNGER_DEATH_HOURS` (12) or `THIRST_DEATH_HOURS` (6) of
online time. Past it the character is told "YOU ARE DYING OF HUNGER!" (or
THIRST) and its vital pool is spent, so the ordinary [death](#death) path
runs, with no killer: `ON_DEATH`, then `PLAYER_DEATH`. Its food and water
are then full again. 0 turns death from that need off; the reminders go
on.

Hunger takes half of every recovery and thirst the other half: a
character both hungry and thirsty regenerates nothing. `HUNGRY_AWARD`
(1.0) multiplies experience and character point awards while hungry or
thirsty; set 0 for CoffeeMud's "no experience while hungry". Every award
passes through `award(player, amount)` in `realm/std/rules/system.py`,
whose `award_filters` (on `world.services["rules"]`) are where `needs`
does this.

### Fatigue

A game that wants fatigue adds the pool in its own rules, with a max that
is how long a character can stay awake:

```python
from realm.core.pools import Pool
from realm.games.merc.system import MercSystem


class GameRules(MercSystem):
    def pools(self):
        return [*super().pools(), Pool("fatigue", direction="up", regen=False)]

    def baseline_stats(self):
        # CoffeeMud: fatigued after 3000 ticks awake (about 3 hours)
        return {**super().baseline_stats(), "fatigue": 0, "max_fatigue": 3000}
```

It rises by 1 each interval awake and falls by `FATIGUE_SLEEP_RECOVERY`
(3) asleep. Spent, it halves mana and movement recovery, and "You are
exhausted." comes at the reminder interval. Nothing else happens; sleep
cures it.

### Eating and drinking

Food carries `nourishment` (all it holds) and `bite` (how much one `eat`
takes; without it, the whole). `eat` moves a bite into `food`, scaled by
`FOOD_GAIN` percent (100), and the food is gone when its nourishment is. A
full stomach refuses: "You are too full to eat more."

A drink container carries `liquid` (its name), `liquid_held`,
`liquid_remaining` and `sip` (default 50). `drink` moves a sip into
`water`, scaled by `WATER_GAIN` (100), and lowers what remains. Something
tagged `fountain` never runs dry. `drink` alone drinks from a fountain
here, or from the room itself when it is tagged `water_source` (a river,
a well). `fill <container> [<fountain>]` refills a container.

```text
@create a loaf of bread
@tag a loaf of bread = food
@set a loaf of bread/nourishment = 300
@set a loaf of bread/bite = 100      # three bites
@create a water skin
@tag a water skin = drink
@set a water skin/liquid = water
@set a water skin/liquid_held = 300
@set a water skin/liquid_remaining = 300
@tag here = water_source             # now `drink` and `fill skin` work here
```

Merc's `score` says "You are hungry." and "You are thirsty." when a pool
is at a quarter or less, and does not list them as numbers. Softcode
`hungry(obj)` and `thirsty(obj)` are True when the pool is empty.

### Where the numbers come from

CoffeeMud (`coffeemud.ini` `HUNGER` and `THIRST`,
`Libraries/MUDFight.java` `expendEnergy`, `Common/DefaultCharState.java`,
`Locales/StdRoom.java` `thirstPerRound`, the `FORMULA_*RECOVER` entries).

Taken from it: the 500 and 1000 stomach; loss every 4-second tick, by
weight, with fractions carried; the thirst rate from hot, dry, windy and
wet; walking spending a tick's worth; nothing lost asleep or by an
immortal; the 12 and 6 hour death limits, the reminder every 60 ticks and
its words; hunger and thirst each taking half of a recovery and fatigue
half of mana and movement; a body restored to full by death; bites and
sips, "You are no longer hungry." and "You have drunk all you can."; the
importer's scale (a ROM food's hours times 20, a drink's units times 30).

Changed: CoffeeMud loses `weight / 500` a tick and grows a stomach only
for every whole 250 pounds; here both scale by `weight /
NEEDS_BASE_WEIGHT`, so a character of the base weight loses 1 a tick and
gets hungry in about half an hour, Diku's pace (CoffeeMud's 150-pound
human takes about two hours: `FOOD_LOSS = 30` and `WATER_LOSS = 30` give
that). A sip is 50, not 250. Eating or drinking on a full stomach is
refused, as ROM does.

Left out: weather (CoffeeMud's drought, heat wave and rain change the
thirst rate), each locale's own base thirst (use the climate tags),
liquids that are not water (salt water, liquor and drunkenness), food
that decays, obesity, and the drinking and eating of NPCs.

## Settings

| Key | Default | Feature |
|---|---|---|
| `REGEN_INTERVAL` | 15 | vitals |
| `REST_REGEN` | 2 | vitals |
| `SLEEP_REGEN` | 4 | vitals |
| `PLAYER_DEATH` | `"respawn"` | combat |
| `CORPSE_LOCK_SECONDS` | 300 | combat |
| `NEEDS_INTERVAL` | 4 | needs |
| `FOOD_LOSS`, `WATER_LOSS` | 100 (percent) | needs |
| `NEEDS_REMINDER_TICKS` | 60 | needs |
| `HUNGER_DEATH_HOURS` | 12 | needs |
| `THIRST_DEATH_HOURS` | 6 | needs |
| `HUNGRY_AWARD` | 1.0 | needs |
| `FATIGUE_SLEEP_RECOVERY` | 3 | needs |
| `FOOD_FULL`, `WATER_FULL` | 500, 1000 | rules |
| `NEEDS_BASE_WEIGHT` | 150 | rules |
| `FOOD_GAIN`, `WATER_GAIN` | 100 (percent) | items |

See also [Pools](pools.md) for the pools themselves and
[Game Systems](game-systems.md) for `regen`, `on_death` and `stomach`.
