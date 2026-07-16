# 037. Day/night cycle

> Checklist item 37 — [now] — *softcode clock from now(), [[...]] time-branching descs*

**What you'll build:** A plaza whose description follows the hour —
morning shadows, afternoon light, lamplit night — and which goes
*genuinely* dark after nine, using the engine's darkness rules, all
driven by one softcode clock.

**Concepts:** the softcode game clock (one object, one `on_tick`),
`[[...]]` blocks branching on shared state, driving the engine's `dark`
tag from a ticker, tag-based visibility, authority over your own rooms.

## How it works

REALM ships no global calendar — deliberately, because a clock is two
lines of softcode: an object whose `on_tick` increments an `hour`
attribute modulo 24 ([tutorial 068](068_npc_schedule.md) built this
exact clock to run a shopkeeper's day). Attribute reads are open, so
every desc in town can ask `get_attr('town clock', 'hour', 12)`.

Two layers make the cycle *felt*:

1. **Text follows the hour.** The clock's sweep stamps a `daypart`
   attribute (`morning` / `afternoon` / `night`) onto every outdoor
   room in the zone, and a `[[...]]` block in the room description
   branches on it — three different sentences, swapped by game time.
   Why stamp instead of having the block ask the clock directly?
   Blocks run at look time, per viewer, *on the look's own call
   stack* — keep them to cheap local `me`-reads and let the ticker
   (which runs on its own worker stack) do the remote read once per
   hour. Push-on-change: same rule the weather system lives by
   ([tutorial 036](036_weather_system.md)).

2. **Night is real darkness.** The engine already knows what `dark`
   means: a `dark`-tagged room renders pitch black, hides its contents,
   and blocks targeting unless there's a lit light source or the viewer
   has `nightvision` ([tutorial 038](038_dark_room.md) tours those
   rules). So the clock's `on_tick` also *toggles the `dark` tag* on
   every outdoor room in the zone: `add_tag` at 21:00, `remove_tag` at
   6:00. Contents visibility swaps with game time because the
   perception engine is doing the work — softcode just flips the flag.

Authority note: `add_tag`/`remove_tag` mutate the rooms, so the clock
must *control* them. Your own clock toggling your own rooms works by
owner delegation (your objects act with your authority); a town-wide
clock on a live game is admin-owned for the same reason.

Pick the tempo with the ticker interval: `interval:1` is one game hour
per world tick (brisk — good for building), `interval:225` makes a
15-minute hour at the default 4-second tick.

## Build it

The plaza, zoned and marked as open sky:

```text
@dig Sundial Plaza = plaza, back
plaza
@zone here = town
@tag here = outdoors
```

The clock. Its tick advances the hour, then sweeps the zone's outdoor
rooms — stamping the `daypart` and flipping the engine's `dark` tag by
the hour band:

```text
@create town clock
drop town clock
@set town clock/hour = 8
@set town clock/on_tick = h = (get_attr(me, 'hour', 0) + 1) % 24; set_attr(me, 'hour', h); night = h >= 21 or h < 6; dp = 'night' if night else ('morning' if h < 12 else 'afternoon'); [(set_attr(r, 'daypart', dp), (add_tag(r, 'dark') if night else remove_tag(r, 'dark'))) for r in zone_rooms('town') if has_tag(r, 'outdoors')]
@behavior town clock = script_ticker, interval:1
```

The time-branching description — a local read of the stamp, defaulting
to morning until the first sweep lands:

```text
@desc here = A worn sundial crowns the plaza. [[dp = get_attr(me, 'daypart', 'morning'); result = 'Lamplight pools on the cobbles, and the gnomon points at nothing.' if dp == 'night' else ('Long morning shadows sweep the dial.' if dp == 'morning' else 'The gnomon leans into the afternoon light.')]]
```

## Try it

```text
look                    (hour 8)
  A worn sundial crowns the plaza. Long morning shadows sweep the dial.
                        (let five hours tick past — hour 13)
look
  A worn sundial crowns the plaza. The gnomon leans into the afternoon light.
                        (nine more — hour 22, the sweep tags the plaza dark)
look
  It is pitch black here. You can't see a thing.
```

That last line is the point: after curfew the plaza isn't *described*
as dark, it **is** dark — the sundial, the clock, and anything dropped
on the cobbles vanish from `look` and from targeting. Come back with a
lit lantern (or nightvision goggles, [tutorial 038](038_dark_room.md))
and you'll read the lamplight line of the desc. At dawn the sweep
clears the tag and the morning sentence returns.

## Going further

- **A real calendar:** the hour counter generalizes — roll days,
  month names, and a year from `now()` arithmetic on the same object,
  and let festival descs branch on `month`.
- **Night-only presences:** the same sweep can `add_tag(flower,
  'invisible')` at dawn and remove it at dusk — a night-blooming
  garden whose contents literally aren't there by day.
- **Schedules everywhere:** the clock is already driving descs and
  darkness; [tutorial 068](068_npc_schedule.md) hangs a shopkeeper's
  working day off the identical attribute. One clock, many readers.
- **Street lamps:** drop a `light`-tagged lamp object in a plaza and
  the engine exempts that square from night darkness — a lamplighter
  NPC who carries them out at dusk is item 68's commute plus item 6's
  light toggle.
