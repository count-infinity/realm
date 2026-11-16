# Life and Death

How a character is hurt, recovers, goes down and carries on, alone, with no
other player to help. Four pieces do it:

- **Regeneration** (the `vitals` feature): out of combat, pools refill over
  time.
- **Positions** (`vitals`): `rest` and `sleep` refill them faster, at a
  cost.
- **Coming round** (`combat`): an unconscious character whose vital pool
  rises above spent gets up.
- **Death** (`combat`): what happens when the vital pool is spent, from
  falling unconscious to leaving a corpse and waking at home.

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
other features add. A feature adds its own factor like this:

```python
@feature.on_boot
async def _hunger_slows_healing(world):
    vitals = world.services.get("vitals")
    if vitals is not None:
        vitals.multipliers.append(
            lambda obj, pool: 0.5 if obj.has_tag("hungry") else 1.0)
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
| `unconscious` | tagged `unconscious` where it fell; comes round as it heals | anyone; a player's default |
| `respawn` | dies: see below | players only |
| `corpse` | a lootable corpse; the killer's party is paid the kill award | not players; anything else's default |
| `destroy` | destroyed, as `@destroy` does it | not players |
| `none` | nothing; the object's `ON_SPENT` softcode decides | anyone |

`PLAYER_DEATH` (`"unconscious"` or `"respawn"`) is the default for players.
The Merc scaffold (`realm init --system merc`) and the Midgaard template
set it to `respawn`.

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
4. returns to their `home`, else the start room, with 1 point in their
   vital pool, standing, out of combat, and with every timed effect
   ended. They see the room they wake in.

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

## Settings

| Key | Default | Feature |
|---|---|---|
| `REGEN_INTERVAL` | 15 | vitals |
| `REST_REGEN` | 2 | vitals |
| `SLEEP_REGEN` | 4 | vitals |
| `PLAYER_DEATH` | `"unconscious"` | combat |
| `CORPSE_LOCK_SECONDS` | 300 | combat |

See also [Pools](pools.md) for the pools themselves and
[Game Systems](game-systems.md) for `regen` and `on_death`.
