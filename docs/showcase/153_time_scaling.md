# 153. Time scaling

> Checklist item 153 ([now]): *clock factors, world tick vs beats, combat pace*

**What you'll build:** A master chronometer whose rate is a dial, so
`set rate 120` makes an in-game day pass four times faster than `set rate
30`, plus the understanding of how that fiction-time knob relates to
REALM's two *real* clocks, day/night cycles, and zones.

**Concepts:** the split between **real time** (the seconds and beats the
engine runs on) and **game time** (the fiction you author), where the
"TIME_FACTOR" lives in REALM (your softcode clock's `step`, not an engine
setting), and how scaling one clock scales everything that reads it.

## How it works

The finished chronometer is one object holding a single counter, a `step`,
a tick that advances it, and two commands: one reads the clock, the other
changes the rate live. This section answers where that rate really lives,
how one number turns into a speed, and why turning it moves the whole
fictional world at once.

### Where does the time factor live?

REALM ships no engine TIME_FACTOR, and that is deliberate. The kernel runs
two *real* clocks (the real-time heartbeat and integer beats, see
[145](145_scheduled_events.md)) to pace *mechanics*: when a fuse fires, how
fast a fight resolves. They are wall-clock and turn-clock, not the *year in
the story*. Fiction time, the sense in which "a day passes", is content, so
it lives in the softcode clock you build, and its scale is just one number:
how many game-minutes the clock advances per tick.

### How the one number becomes a speed

The conversion is worth seeing plainly. A `script_ticker` behavior with
`interval:N` fires every `N × WORLD_TICK` real seconds, and `WORLD_TICK` is
4 seconds. If each tick adds `step` game-minutes, then:

```
game-minutes per real-second  =  step / (interval × WORLD_TICK)
```

That ratio **is** your TIME_FACTOR. Raise `step` (or lower `interval`) and
game-time dilates faster; there is no engine flag to hunt for. At `step 30,
interval 1` a game-day (1440 minutes) takes 1440 / 30 = 48 ticks, about 3.2
real minutes; `set rate 120` and the same day takes 48 real seconds.

### Why one dial moves the whole world

Because a day/night desc ([037](037_day_night_descs.md)), a business-hours
gate ([151](151_business_hours.md)), an NPC schedule
([068](068_npc_schedule.md)), and a calendar ([144](144_game_calendar.md))
all read the *same* `game_min`/`hour` attribute, turning the one dial
speeds or slows all of them in lockstep: the whole fictional world's clock,
not just the display.

## Build it

The chronometer needs somewhere to hang, then the object itself:

```text
@dig Chronometry Lab = chronlab, out
chronlab
@create master chronometer
drop master chronometer
```

The counter and its rate are plain data. `game_min` is the monotonic
game-minute count, and `step` is the dial, the game-minutes added per tick:

```text
@set master chronometer/game_min = 0
@set master chronometer/step = 30
```

The tick is a single expression: each world beat, [`incr`](../reference/softcode.md#fn-incr)
adds `step` (read off `me` with [`V`](../reference/softcode.md#fn-v)) to
`game_min`. Attaching `script_ticker` at `interval:1` runs that
[`on_tick`](../reference/softcode.md#lifecycle-hooks) once per world beat,
roughly every 4 seconds. Because the tick re-reads `step` every time,
changing the dial takes hold on the very next tick:

```text
@set master chronometer/on_tick = incr('game_min', V('step', 30))
@behavior master chronometer = script_ticker, interval:1
```

The `set rate` command rewrites the dial while the world runs. On a good
value it stamps the new `step` with
[`set_attr`](../reference/softcode.md#fn-set_attr) and confirms to the
caller with [`pemit`](../reference/softcode.md#fn-pemit):

```text
@set master chronometer/cmd_rate = '''
$set rate *:
# whole digits only, so a word or a negative leaves the rate as it was
if trim(arg0).isdigit():
    set_attr(me, 'step', int(arg0))
    pemit(enactor, 'Time now advances ' + arg0 + ' game-minutes per world tick.')
else:
    pemit(enactor, 'Whole minutes only.')
'''
```

The check is [`trim`](../reference/softcode.md#fn-trim)`(arg0).isdigit()`,
where `arg0` is the wildcard capture from `$set rate *`. The `clock`
command reads the counter and divides it into a day number and a 24-hour
time, zero-padding each field with
[`right`](../reference/softcode.md#fn-right):

```text
@set master chronometer/cmd_clock = '''
$clock:
m = V('game_min', 0)
hh = right('0' + str((m // 60) % 24), 2)
mm = right('0' + str(m % 60), 2)
pemit(enactor, 'Day ' + str(m // 1440 + 1) + ', ' + hh + ':' + mm)
'''
```

## Try it

At the default rate, one tick is half a game-hour:

```text
> @tr master chronometer/on_tick
> clock
Day 1, 00:30
```

Turn the dial up and watch the same tick cover four times the ground:

```text
> set rate 120
Time now advances 120 game-minutes per world tick.
> @tr master chronometer/on_tick
> clock
Day 1, 02:30
```

One tick, two game-hours. Nothing else changed: the tick script and the
clock reader are untouched, and only the `step` between them moved. Slow it
back down with `set rate 15` for a languid world where dusk takes its time.

## Real time vs game time, and where each belongs

The dial only touches *fiction* time, so keep the boundary clear:

- **Real-time seconds** (fuses, decay, spawns, `wait()`/`expire()`) hold
  steady regardless of the dial: a 30-second bomb is 30 real seconds
  whether the calendar is racing or crawling. That is correct, because
  infrastructure is wall-clock ([145](145_scheduled_events.md)).
- **Beats** (combat, effects) scale with *combat pace* rather than your
  calendar, so a slowed fight dilates its own poison independently of what
  year it is.
- **Game time** (your `game_min`) is the only thing this dial moves, and it
  moves everything that reads it.

Mixing them is the classic mistake: reserve `wait()`/`expire()` for
real-world timing and the game clock for the fiction. A fuse pinned to
`game_min` would detonate at a different real speed each time you change the
rate.

## Going further

- **Per-zone time:** give a zone master its own `time_factor` and compute a
  *local* game-time as `base + (game_min - anchored) × factor`, for a
  relativistic anomaly where a day outside is an hour inside, or a sleepy
  hamlet where time drags. Rooms in the zone read their master's local clock
  instead of the global one.
- **Pause time:** `set rate 0` freezes the calendar (the tick adds nothing)
  while the server keeps running, which is handy for a GM staging a scene.
- **Faster nights:** scale asymmetrically by having `on_tick` add more
  minutes when `hour` is nocturnal, giving long days and short nights, since
  the step is just softcode.
- **Anchor it to real time:** to make the dial *also* survive reboots,
  compute game-time from [`now()`](../reference/softcode.md#fn-now) and a
  stored factor rather than a tick counter, the absolute-deadline idiom of
  [152](152_persistent_timers.md).
