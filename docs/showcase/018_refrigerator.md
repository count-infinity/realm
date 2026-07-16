# 018. Refrigerator

> Checklist item 18 — [now] — *decay behavior, ON_PUT/ON_GET adjusting decay ticks*

**What you'll build:** Two ripe peaches on a timer. The one on the
counter collapses into mush; its twin in the icebox is still worth
eating days later — and neither the peach nor the icebox knows the
other's name.

**Concepts:** freshness as a plain attribute burned down by a
`script_ticker`, and the **holder-modified rate** pattern: the food
owns its decay, the container merely *publishes an environment value*
(`decay_rate`), and the food reads whatever its current holder says.
One attribute name is the entire coupling.

## How it works

**The item owns its clock.** Each perishable carries `freshness` and a
`script_ticker` behavior whose `on_tick` script subtracts the going
rate, then checks for zero. State lives in attributes, so a peach
keeps ripening across reboots exactly where it left off.

**The holder sets the rate.** The tick reads
`get_attr(loc(me), 'decay_rate', 1)` — *whatever currently holds me*.
On the floor, `loc(me)` is the room: no attribute, default 1, full-speed
rot. In your pack, it's you: same default (body heat is no kindness to
fruit). In the icebox, the container answers 0.25 and the peach ages at
quarter speed. A freezer is `0`, a compost heap is `3`, and a walk-in
cold room sets it on the *room* — location is location, and nothing
subscribes to anything.

Why not have the fridge's `ON_PUT`/`ON_GET` hooks rewrite the item's
timer, as the audit sketched? Because event hooks don't hand the
script the item (see [Engine gaps](#engine-gaps)) — and because
rate-at-read needs no bookkeeping at all: there is no pair of hooks to
desync when a conveyor, a thief, or an admin teleport moves the food.
The peach asks its holder *every tick*; it cannot be wrong for longer
than one.

**Rot is a replacement, not a flag.** At zero the peach announces
itself, spawns `a slick of brown mush` wherever it lies (floor,
pocket, or icebox shelf — `loc(me)` again), and destroys itself. An
object may always destroy itself; no authority questions arise.

## Build it

The icebox is a stock container plus one published number:

```text
@create icebox
@set icebox/container = true
drop icebox
@set icebox/decay_rate = 0.25
@desc icebox = An enameled chest humming to itself. Frost feathers the seams.
```

The peach. Freshness 6; the description reads the attribute so `look`
is the freshness gauge; the tick does subtract-check-replace. Tick
interval 1 is *peach time* — one freshness point per heartbeat, brisk
enough to watch; a kitchen you actually cook in wants `interval:150`:

```text
@create ripe peach
@set ripe peach/freshness = 6
@desc ripe peach = [[f = get_attr(me, 'freshness', 6); result = 'Bursting with juice.' if f > 4 else ('Going soft and winey.' if f > 0 else 'Compost.')]]
@set ripe peach/on_tick = f = get_attr(me, 'freshness', 6) - get_attr(loc(me), 'decay_rate', 1); set_attr(me, 'freshness', f); (remit(here, 'The ' + name(me) + ' collapses into a slick of brown mush.'), create_obj('a slick of brown mush', [], loc(me)), destroy_obj(me)) if f <= 0 else None
@behavior ripe peach = script_ticker, interval:1
```

Its control-group twin — identical fruit, different fate:

```text
@create twin peach
@set twin peach/freshness = 6
@desc twin peach = [[f = get_attr(me, 'freshness', 6); result = 'Bursting with juice.' if f > 4 else ('Going soft and winey.' if f > 0 else 'Compost.')]]
@set twin peach/on_tick = f = get_attr(me, 'freshness', 6) - get_attr(loc(me), 'decay_rate', 1); set_attr(me, 'freshness', f); (remit(here, 'The ' + name(me) + ' collapses into a slick of brown mush.'), create_obj('a slick of brown mush', [], loc(me)), destroy_obj(me)) if f <= 0 else None
@behavior twin peach = script_ticker, interval:1
```

Stage the experiment:

```text
drop ripe peach
put twin peach in icebox
```

## Try it

`look ripe peach` — `Bursting with juice.` Now wait six heartbeats
(about 24 seconds at the default tick).

The counter peach walks the whole arc: `Bursting with juice.` →
`Going soft and winey.` → the room sees `The ripe peach collapses
into a slick of brown mush.` and the floor holds mush where fruit
was. Now `get twin peach from icebox` and `look twin peach`: the twin
spent the same six ticks losing a point and a half, and still says
`Bursting with juice.` Carry it around and it decays at full speed
from wherever its freshness stands; put it back and the cold resumes.
No hook ever fired; the rate followed the location.

## Engine gaps

- `ON_<EVENT>` trigger scripts get no binding for the action payload —
  `adata()` exists only in the `on_check` ward namespace. A fridge's
  `ON_PUT` therefore can't reference *which* item just arrived (and
  the carried item's own `ON_PUT` never fires, since a carried item
  isn't among the action's witnesses). The audit's
  "ON_PUT/ON_GET adjust the item's decay-ticks" bookkeeping is thus
  unwritable as stated; the holder-rate pattern above needs no item
  reference and is the honest replacement. (Same gap worked around in
  [019](019_trash_incinerator.md) with a deferred sweep.)

## Going further

- **Door discipline:** have the icebox's `ON_OPEN`/`ON_CLOSE` scripts
  set its own `decay_rate` to 1 and 0.25 respectively — leave the door
  open, spoil the milk. The peaches need no change; they read the rate
  fresh every tick.
- **A freezer aisle:** `@set here/decay_rate = 0` on a room chills
  everything dropped in it — the peach already honors it.
- **Eat the window:** a `$eat *` command that checks `freshness > 0`
  before healing — past zero there's only mush to regret.
- **Full larder:** item 146 does food and drink properly; this build
  is its smallest honest core — freshness, a ticker, and a rate the
  world publishes.
