# 037. Day/night cycle

> Checklist item 37 ([now]): *softcode clock from now(), [[...]] time-branching descs*

**What you'll build:** A plaza whose description follows the hour (morning
shadows, afternoon light, lamplit night) and which goes genuinely dark
after nine using the engine's darkness rules, all driven by one softcode
clock.

**Concepts:** the softcode game clock (one object, one
[`on_tick`](../reference/softcode.md#lifecycle-hooks)), `[[...]]` blocks
branching on shared state, driving the engine's `dark` tag from a ticker,
tag-based visibility, and authority over your own rooms.

## How it works

A plaza that reads the hour has two moving parts that never touch each
other directly: a clock object that advances the time and stamps it around
town, and a room description that reads whatever the clock last stamped.
This section covers where the time lives, how the text follows it, and how
night becomes real darkness rather than a darker sentence.

### Where does the time come from?

REALM ships no global calendar, and that is deliberate, because a clock is
two lines of softcode: an object whose `on_tick` increments an `hour`
attribute modulo 24. [Tutorial 068](068_npc_schedule.md) builds this same
clock to run a shopkeeper's working day. Attribute reads are open, so every
description in town can ask
[`get_attr`](../reference/softcode.md#fn-get_attr)`('town clock', 'hour',
12)` by name.

### How does the text follow the hour?

Each tick the clock stamps a `daypart` attribute (`morning`, `afternoon`,
or `night`) onto every outdoor room in the zone with
[`set_attr`](../reference/softcode.md#fn-set_attr), and a `[[...]]` block in
the room description branches on it, so three different sentences swap by
game time. Why stamp the rooms instead of having the block ask the clock
directly? Inline blocks run at look time, once per viewer, on the look's own
call stack, so the robust idiom is to keep them to one cheap local read
(here [`V`](../reference/softcode.md#fn-v)`('daypart', ...)`, which reads the
room's own attribute) and let the ticker, which runs on its own worker
stack, do the cross-room stamping once per hour. That push-on-change split
is the same rule the weather system lives by
([tutorial 036](036_weather_system.md)).

### How does night become real darkness?

The engine already knows what `dark` means: a `dark`-tagged room renders
pitch black, hides its contents, and blocks targeting unless a lit light
source is present or the viewer has `nightvision`
([tutorial 038](038_dark_room.md) tours those rules). So the same sweep also
toggles the tag, adding it with
[`add_tag`](../reference/softcode.md#fn-add_tag) from 21:00 and clearing it
with [`remove_tag`](../reference/softcode.md#fn-remove_tag) at 06:00.
Contents visibility swaps with game time because the perception engine does
the work; the softcode only flips the flag.

`add_tag`, `remove_tag`, and `set_attr` all mutate the rooms, so the clock
must control them. Your own clock toggling your own rooms works by owner
delegation, since your objects act with your authority, and a town-wide
clock on a live game is admin-owned for the same reason.

Pick the tempo with the ticker interval. `interval:1` is one game hour per
world tick, which is brisk and good for building, while `interval:225` makes
a 15-minute hour at the default 4-second tick.

## Build it

The plaza, zoned and marked as open sky so the sweep will find it:

```text
@dig Sundial Plaza = plaza, back
plaza
@zone here = town
@tag here = outdoors
```

The clock is an ordinary object. Drop it so it stands in the world, and
give it a starting hour:

```text
@create town clock
drop town clock
@set town clock/hour = 8
```

Its tick advances the hour, then sweeps the zone's outdoor rooms, stamping
each room's `daypart` and flipping the engine's `dark` tag by the hour band.
The body is control flow, so it is a `'''` heredoc block (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)):

```text
@set town clock/on_tick = '''
h = (V('hour', 0) + 1) % 24
set_attr(me, 'hour', h)
night = h >= 21 or h < 6
dp = 'night' if night else ('morning' if h < 12 else 'afternoon')
for r in zone_rooms('town'):
    if has_tag(r, 'outdoors'):        # only open-sky rooms get a daypart
        set_attr(r, 'daypart', dp)
        if night:
            add_tag(r, 'dark')        # the perception engine renders this pitch black
        else:
            remove_tag(r, 'dark')
'''
```

Attach the ticker so the clock runs on the world heartbeat:

```text
@behavior town clock = script_ticker, interval:1
```

The time-branching description does a single local read of the stamp,
defaulting to morning until the first sweep lands:

```text
@desc here = A worn sundial crowns the plaza. [[dp = V('daypart', 'morning'); result = 'Lamplight pools on the cobbles, and the gnomon points at nothing.' if dp == 'night' else ('Long morning shadows sweep the dial.' if dp == 'morning' else 'The gnomon leans into the afternoon light.')]]
```

## Try it

```text
look                    (hour 8)
  A worn sundial crowns the plaza. Long morning shadows sweep the dial.
                        (let five hours tick past, hour 13)
look
  A worn sundial crowns the plaza. The gnomon leans into the afternoon light.
                        (nine more, hour 22, the sweep tags the plaza dark)
look
  It is pitch black here. You can't see a thing.
```

That last line is the point: after curfew the plaza is not *described* as
dark, it **is** dark, so the sundial, the clock, and anything dropped on the
cobbles vanish from `look` and from targeting. Come back with a lit lantern
(or nightvision goggles, [tutorial 038](038_dark_room.md)) and you will read
the lamplight line of the desc. At dawn the sweep clears the tag and the
morning sentence returns.

## Going further

- **A real calendar:** the hour counter generalizes, so roll days, month
  names, and a year from [`now()`](../reference/softcode.md#fn-now)
  arithmetic on the same object, and let festival descs branch on `month`.
- **Night-only presences:** the same sweep can `add_tag(flower,
  'invisible')` at dawn and remove it at dusk, giving a night-blooming
  garden whose contents literally are not there by day.
- **Schedules everywhere:** the clock is already driving descs and darkness,
  and [tutorial 068](068_npc_schedule.md) hangs a shopkeeper's working day
  off the identical attribute. One clock, many readers.
- **Street lamps:** drop a `light`-tagged lamp object in a plaza and the
  engine exempts that square from night darkness, so a lamplighter NPC who
  carries them out at dusk is [tutorial 068](068_npc_schedule.md)'s commute
  plus the [flashlight](006_flashlight.md)'s light toggle.
```