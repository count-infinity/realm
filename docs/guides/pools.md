# Pools: Health and Resources on Anything

Hit points, shields, hull, mana, stress, a harm clock, a door's structure
and a reactor's heat are the same thing to REALM: a **pool**, a number
stored in an attribute, perhaps with a maximum beside it. One kernel module,
`realm/core/pools.py`, changes those numbers for damage, healing and costs,
and tells the world when they change.

A pool named `hp` is the attributes `hp` and `max_hp`, exactly as they are
saved. Nothing is migrated, and softcode that reads `get_attr(obj, 'hp')`
keeps working.

## What a pool is

Any attribute that holds a number is already a pool with default settings:
it goes **down** under harm, stops at 0, is capped by `max_<name>` when that
attribute exists, and is **spent** at 0. To change how one behaves, give it
a definition.

| Setting | Default | Meaning |
|---|---|---|
| `attr` | the pool's name | the attribute that stores the value |
| `max_attr` | `max_<name>` | the attribute that stores the maximum; no value means unbounded |
| `direction` | `"down"` | `"down"`: harm lowers it, spent at or below `spent_at`. `"up"`: harm raises it, spent at its max (stress, a harm clock, heat) |
| `floor` | `0` | the lowest value harm, mending or spending can leave; `None` allows negatives |
| `spent_at` | `0` | a down pool is spent at or below this |
| `overflow` | none | harm this pool could not absorb goes on to the named pool |
| `soak_attr` | none | an attribute read as a flat reduction before harm lands, when the caller asks for soak |
| `regen` | `True` | whether it recovers on its own over time, with the `vitals` feature ([Life and Death](life-and-death.md)) |

## Where a definition comes from

The first of these that defines the pool wins, and it is used whole: a
partial spec is not merged with a definition further down the list.

1. The object's own `pools` attribute, a dict of pool name to settings:

        @set ship/pools = {"shields": {"overflow": "hull"}, "hull": {"soak_attr": "armor"}}

2. The same attribute on the object's `@parent`, then its parent.
3. A world default, from the rules system (`GameSystem.pools()`) or a
   feature (`feature.pool(Pool("shields", overflow="hull"))`). Two different
   definitions of one name from different sources stop the world at boot.
4. Implicit: the attribute holds a number.

An unknown setting in a `pools` attribute, or a `direction` other than
`"down"` or `"up"`, raises an error naming the object. So does a chain of
`overflow` pools that loops back on itself.

## Which pool takes the damage

`damage_pool(obj)` is where harm lands first: the object's `damage_pool`
attribute, else the `DAMAGE_POOL` setting (default `"hp"`). An object
without that pool cannot be harmed. `vital_pool(obj)` follows the overflow
chain from there to its end: the pool whose spending is the object's
defeat. For a character it is `hp` both ways. For the ship above, with
`damage_pool` set to `shields`, harm lands in `shields` and the vital pool
is `hull`.

## Changing a pool

From Python:

```python
from realm import pools

change = pools.harm(ship, "shields", 10, soak=True)  # lowers shields, spills into hull
await pools.settle(change, source=attacker)          # ON_POOL, ON_SPENT

pools.mend(player, "hp", 5)        # toward max; an up pool toward its floor
pools.spend(caster, "mana", 15)    # all or nothing; None when short
pools.set_pool(player, "hp", 12, max=12)   # chargen, a level gain
```

`harm`, `mend` and `spend` change memory only and fire nothing, so the
softcode worker thread can call them. Each returns a `PoolChange` with
`old`, `new`, `requested`, `applied`, `soaked`, `became_spent` and
`spilled` (the change made to the overflow pool); `total_applied` adds up
the chain.

Harm into shields holding 4, with a hull behind them whose armor is 2:

| | shields | hull |
|---|---|---|
| before | 4 | 30 |
| `harm(ship, "shields", 10)` | 0 (took 4) | 24 (took the other 6) |
| `harm(ship, "shields", 10, soak=True)` | 0 (took 4) | 26 (6, less 2 soaked) |

Soak applies at each pool the harm reaches.

## Stock damage and healing use pools

Everything in the stock features that hurts or heals goes through this
module, so it works on whatever pool an object names:

| Source | What it does |
|---|---|
| a swing, a damaging ability (`combat:on_damage`) | the ruleset's `apply_damage` ends in `Ruleset.write_damage`: `harm` on the damage pool with soak, settled once the blow lands |
| softcode `damage()`, a damage-over-time effect | resistances when typed, then `harm` on the damage pool with soak; no damage event (the deliberate bypass) |
| softcode `harm_pool()` | `harm` on the named pool, no soak: the raw pool change |
| `heal()`, `firstaid`, a healer NPC, regeneration, a `heal` ability effect | `mend` on the damage pool |
| an ability cost `{"pool": "mana", "n": 15}` | `spend`: blocked with "You don't have the mana." when short |
| chargen, a level gain | `set_pool` |

A combatant is out of the fight when its vital pool is spent
(`Combatant.vital_spent`); no ruleset decides otherwise. Combat's status
line and strategies (`me.hp_percent`) read the vital pool. Damage
stops at a pool's `floor`, 0 by default, for every source. A game whose
characters go below zero gives its `hp` pool `floor=None` (in
`GameSystem.pools()` or a feature's `feature.pool`), and a `spent_at` below
zero if they should keep fighting there.

## Death and the HP threshold

With the `combat` feature installed, three observers watch every object's
vital pool, whatever moved it: a swing, a spell, a poison tick, a trap,
softcode `damage()` or `harm_pool()`, regeneration.

- **Spent:** the combat manager's death path runs once, with the source as
  the killer. `ON_DEATH` fires, then the body is dealt with as its
  `when_spent` attribute says (below).
- **Falling through `hitprcnt`:** an object with `hitprcnt` set (a percent)
  fires `ON_HITPRCNT` once, as its vital pool drops from above that percent
  to at or below it, with `adata('percent')` and `adata('threshold')`. The
  change that spends the pool fires `ON_DEATH` instead. An up pool counts
  what is left below its max: a harm clock at 4 of 6 is at 33 percent.
- **Rising above spent while `unconscious`:** the object comes round: the
  tag goes, it is told "You come to." and the room sees it stir.

Spending any other pool (shields, mana, heat) does neither. Its own
`ON_SPENT` hook still fires.

`when_spent` says what death does to the body:

| `when_spent` | What happens | `adata('fatal')` |
|---|---|---|
| `unconscious` | tagged `unconscious` where it fell; comes round when its vital pool rises above spent (regeneration, healing). A player's default unless `PLAYER_DEATH` says otherwise | False |
| `respawn` | players only: a corpse of what they carried stays, the player wakes at home at 1 point and pays the game system's `on_death` penalty; no kill award ([Life and Death](life-and-death.md#death)) | True |
| `corpse` | replaced by a lootable corpse holding its contents; the killer's party gets the award. Any other object's default | True |
| `destroy` | destroyed the way `@destroy` does it: an exit unpairs, a player inside is moved out, other contents go with it | True |
| `none` | nothing: the object's own `ON_SPENT` softcode decides | False |

A player may only be `unconscious`, `respawn` or `none`, and only a player
may be `respawn`. Any other value is an error naming the object. A player
with no `when_spent` follows the `PLAYER_DEATH` setting (`"unconscious"`
unless the game sets `"respawn"`).

    @set ship/when_spent = none
    @set ship/on_spent = if adata('pool') == 'hull': remit(here, 'The ship breaks apart.')
    @set ogre/hitprcnt = 25
    @set ogre/on_hitprcnt = if target is me: force(me, 'flee')

## Hooks

`settle` propagates one `pool:on_change` for each pool in the chain that
moved, and a `pool:on_spent` right after the change that crossed a pool
into spent. Both fire on the object that owns the pool, as `ON_POOL` and
`ON_SPENT`, with `adata('pool')`, `adata('old')`, `adata('new')`,
`adata('applied')` and `adata('source')`:

    @set ship/on_spent = if adata('pool') == 'hull': remit(here, 'The ship breaks apart.')

A pool already spent does not fire `ON_SPENT` again, and a change that moved
nothing fires nothing.

## Softcode

| Function | |
|---|---|
| `pool(obj, name)`, `pool_max(obj, name)` | the value and maximum (None when absent) |
| `has_pool(obj, name)`, `spent(obj, name)` | read-only tests |
| `harm_pool(obj, name, n)` | harm something in reach; harm-gated (needs HARM, like `damage()`); returns the amount taken |
| `mend_pool(obj, name, n)` | mend something in reach; returns the amount mended |
| `spend_pool(name, n)` | pay from the executor's own pool; False, with nothing spent, when short |

The change happens during the run; `ON_POOL` and `ON_SPENT` fire, and the
object is saved, after the script finishes. A trap that stresses whoever
steps on it:

    @set trap/on_enter = harm_pool(enactor, 'stress', 2)

See the [softcode reference](../reference/softcode.md#pools) for each
function's signature.

## Worked examples

Each of these runs in `tests/test_pools_in_play.py`, and none of the
objects has an `hp` attribute.

### A ship: shields over an armored hull

```text
@create ship
@tag ship = npc
@set ship/pools = {"shields": {"overflow": "hull"}, "hull": {"soak_attr": "armor"}}
@set ship/shields = 20
@set ship/max_shields = 20
@set ship/hull = 30
@set ship/max_hull = 30
@set ship/armor = 2
@set ship/damage_pool = shields
@set ship/when_spent = none
@set ship/on_spent = if adata('pool') == 'hull': remit(here, 'The ship breaks apart.')
```

`attack ship` works under every stock ruleset. Each blow empties the
shields first; what they cannot hold spills into the hull, less the 2 its
armor soaks. When the hull reaches 0 the ship is out of the fight, its
`ON_SPENT` hook fires once, and `when_spent = none` leaves the hulk where
it is for the hook to describe. Its `npc` tag is what makes it something
the `attack` command will fight.

### A harm clock

```text
@set Rue/pools = {"harm": {"direction": "up"}}
@set Rue/harm = 0
@set Rue/max_harm = 6
@set Rue/damage_pool = harm
```

`damage(Rue, 2)` from a trap fills the clock: 2, 4, 6. The third segment
spends it, and Rue falls unconscious through the same death path a sword
uses. `hitprcnt` counts what is left of the clock: at 4 of 6, 33 percent.

### A door with structure

```text
@set vault door/structure = 10
@set vault door/max_structure = 10
@set vault door/damage_pool = structure
@set vault door/when_spent = destroy
```

Any damage reaches it: an ability's `damage` effect, softcode `damage()`.
When its structure is spent the door is destroyed the way `@destroy` does
it, and the exit on the far side forgets its partner.
