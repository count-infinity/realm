# 018. Refrigerator

> Checklist item 18 ([now]): *decay behavior, ON_PUT/ON_GET adjusting decay ticks*

**What you'll build:** Two ripe peaches on a timer. The one on the counter
collapses into mush; its twin in the icebox is still worth eating long after,
and neither the peach nor the icebox knows the other's name.

**Concepts:** freshness as a plain attribute burned down by a
[`script_ticker`](006_flashlight.md), and the holder-modified rate pattern:
the food owns its decay, the container merely publishes an environment value
(`decay_rate`), and the food reads whatever its current holder says. One
attribute name is the entire coupling.

## How it works

The finished build is two peaches and an icebox that never speak to each
other. Each peach carries its own freshness meter and a clock that burns it
down, while the icebox does nothing but publish one number. A peach reads that
number off whatever currently holds it and ages at that rate, so the cold
slows a peach's clock without the icebox ever touching the peach. This section
answers four questions: what runs the countdown, where the rate comes from,
why the icebox stays out of it, and what happens when the meter hits zero.

### What runs the countdown?

Each perishable carries a `freshness` attribute and a
[`script_ticker`](006_flashlight.md) behavior whose
[`on_tick`](../reference/softcode.md#lifecycle-hooks) script fires on a
cadence. One call does the whole beat:
[`decr('freshness', rate, default=6)`](../reference/softcode.md#fn-decr) reads
the meter, subtracts the going rate, writes it back, and hands you the new
value to test. The `default=6` is load-bearing, because it is what an unset
`freshness` counts as, so a peach whose attribute was never written starts
full instead of rotting from zero. State lives in an attribute, so a peach
keeps ripening across reboots exactly where it left off. (The flashlight's
battery drains on this same ticker.)

### Where does the rate come from?

The tick reads
[`get_attr(loc(me), 'decay_rate', 1)`](../reference/softcode.md#fn-get_attr),
the `decay_rate` of whatever currently holds the peach.
[`loc(me)`](../reference/softcode.md#fn-loc) is the immediate container: on the
floor it is the room, in your pack it is you, on the icebox shelf it is the
icebox. The room and the player publish no `decay_rate`, so both default to 1
and the fruit rots at full speed (body heat is no kindness to fruit). The
icebox publishes 0.25, so a peach on its shelf ages at quarter speed. A freezer
would publish 0, a compost heap 3, and a walk-in cold room sets the number on
the room itself. Location is the whole coupling, and nothing subscribes to
anything.

### Why not let the icebox adjust the timer on ON_PUT/ON_GET?

The checklist sketches the fridge rewriting each item's decay ticks in an
`ON_PUT`/`ON_GET` pair, and that is buildable:
[`adata('item')`](../reference/softcode.md#event-data-namespace) names the
arriving item inside a container's
[`ON_PUT`](../reference/softcode.md#lifecycle-hooks), so the bookkeeping is
writable (the [basic container](014_basic_container.md) reads the same
payload). It is still the wrong shape. Reading the rate at tick time needs no
bookkeeping at all. There is no pair of hooks to fall out of sync, and the
relocations that move food without firing a put or get hook at all (an admin
teleport, a conveyor hop) would quietly skip a hook-based adjustment. A carried
item is not even among a put's witnesses, so the food's own `ON_PUT` stays
silent in the very case you most want to catch. The peach asks its holder every
beat, so it can be wrong for at most one.

### What happens at zero?

Rot is a replacement, not a flag. When the meter reaches zero the peach
announces its collapse to the room it lies in with
[`remit`](../reference/softcode.md#fn-remit), mints
[`a slick of brown mush`](../reference/softcode.md#fn-create_obj) at `loc(me)`
so the mush lands exactly where the fruit was, and then removes itself with
[`destroy_obj(me)`](../reference/softcode.md#fn-destroy_obj). An object may
always destroy itself, so no permission question arises.

## Build it

The decay script is a multi-line
[`'''` block](../guides/world-management.md#multi-line-input-heredocs);
everything else is one line.

The icebox is a stock [`container`](014_basic_container.md) with one published
number. Tag it `container` to switch on the built-in `put` and `get` verbs,
drop it into the room, and set the one attribute the peaches will read:

```text
@create icebox
@tag icebox = container
drop icebox
@set icebox/decay_rate = 0.25
@desc icebox = An enameled chest humming to itself. Frost feathers the seams.
```

Now the peach. Freshness starts at 6, and the description reads that meter
through an inline `[[...]]` block with [`V`](../reference/softcode.md#fn-v), so
`look` doubles as a freshness gauge:

```text
@create ripe peach
@set ripe peach/freshness = 6
@desc ripe peach = [[f = V('freshness', 6); result = 'Bursting with juice.' if f > 4 else ('Going soft and winey.' if f > 0 else 'Compost.')]]
```

The tick is the heart of it. Its steps in order: burn the meter down by the
current holder's rate, and if nothing is left, announce the collapse to the
room with [`remit`](../reference/softcode.md#fn-remit), drop a slick of mush
where the peach lay, and destroy the peach. Then attach the `script_ticker`
that runs it, with `interval:1` firing it once per heartbeat (brisk enough to
watch; a real pantry would use a far slower interval):

```text
@set ripe peach/on_tick = '''
f = decr('freshness', get_attr(loc(me), 'decay_rate', 1), default=6)  # rate is the holder's, read fresh each beat
if f <= 0:
    remit(here, f'The {name(me)} collapses into a slick of brown mush.')
    create_obj('a slick of brown mush', [], loc(me))  # mush lands wherever the peach lies
    destroy_obj(me)
'''
@behavior ripe peach = script_ticker, interval:1
```

The twin is the control group: identical fruit, headed for the cold. Build it
exactly the same way:

```text
@create twin peach
@set twin peach/freshness = 6
@desc twin peach = [[f = V('freshness', 6); result = 'Bursting with juice.' if f > 4 else ('Going soft and winey.' if f > 0 else 'Compost.')]]
@set twin peach/on_tick = '''
f = decr('freshness', get_attr(loc(me), 'decay_rate', 1), default=6)
if f <= 0:
    remit(here, f'The {name(me)} collapses into a slick of brown mush.')
    create_obj('a slick of brown mush', [], loc(me))
    destroy_obj(me)
'''
@behavior twin peach = script_ticker, interval:1
```

Stage the experiment: one peach on the counter, its twin on ice.

```text
drop ripe peach
put twin peach in icebox
```

## Try it

Fresh out of the build, one peach sits on the counter and one rides in the
icebox. `look` reads the gauge:

```text
look ripe peach     -> Bursting with juice.
```

Now let the counter peach age. Its tick fires once a heartbeat and, on the
floor, subtracts a full point each time, because the room publishes no
`decay_rate` and the rate defaults to 1. Four beats in it is down to 2, and
`look ripe peach` reads `Going soft and winey.`; two beats after that the meter
reaches zero, the room reads `The ripe peach collapses into a slick of brown
mush.`, and a slick of mush now lies where the fruit was.

The twin spent those same six beats on ice at quarter speed, losing a point and
a half in all, so it sits at 4.5 and still looks brand new:

```text
get twin peach from icebox     -> You pick up a twin peach.
look twin peach                -> Bursting with juice.
```

Carry the twin around and it rots at full speed from wherever its meter stands,
because `loc(me)` is now you and you publish no rate; put it back and the cold
resumes at a quarter point a beat. No put or get hook ever fired. The rate
simply followed the fruit's location.

## Going further

- **Leave the door open, spoil the milk:** give the icebox
  [`ON_OPEN` and `ON_CLOSE`](../reference/softcode.md#lifecycle-hooks) scripts
  that set its own `decay_rate` to 1 and 0.25. The peaches need no change,
  since they read the rate fresh every beat.
- **A freezer aisle:** `@set here/decay_rate = 0` chills everything dropped in
  a room, and the peach already honors it.
- **Eat the window:** a `$eat *` command that checks `freshness > 0` before it
  heals, because past zero there is only mush to regret.
- **Fuller decay:** [item 146](146_item_decay.md) weighs the three ways to age
  the world (a batch sweeper, this per-item ticker, and `expire()`); this
  fridge is the smallest honest version of the middle one.
