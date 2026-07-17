# 153. Time scaling

> Checklist item 153 — [now] — *game-time vs real-time, the TIME_FACTOR knob, per-zone scaling*

**What you'll build:** A master chronometer whose **rate is a dial** —
`set rate 120` makes an in-game day fly by four times faster than `set
rate 30` — and the understanding of how that fiction-time knob relates to
REALM's two *real* clocks, day/night cycles, and zones.

**Concepts:** the split between **real time** (seconds/beats the engine
runs on) and **game time** (the fiction you author), where the
"TIME_FACTOR" lives in REALM (your softcode clock's `step`, not an engine
setting), and how scaling one clock scales everything that reads it.

## How it works

**REALM has no engine TIME_FACTOR — on purpose.** The kernel's two real
clocks (the real-time heartbeat and integer beats, see
[145](145_scheduled_events.md)) exist to pace *mechanics* — when a fuse
fires, how fast a fight beats. They are wall-clock and turn-clock; they
are not the *year in the story*. Fiction time — "a day passes" — is
content, so it lives in the softcode clock you build, and **its scale is
just one number**: how many game-minutes the clock advances per tick.

The conversion is worth seeing plainly. A `script_ticker` with
`interval:N` fires every `N × WORLD_TICK` real seconds (`WORLD_TICK` ≈
4s). If the tick adds `step` game-minutes, then:

```
game-minutes per real-second  =  step / (interval × WORLD_TICK)
```

That ratio **is** your TIME_FACTOR. Raise `step` (or lower `interval`)
and game-time dilates faster; there's no engine flag to hunt for. At
`step 30, interval 1` a game-day (1440 min) takes 1440/30 = 48 ticks ≈
3.2 real minutes; `set rate 120` and it's 48 real seconds.

**Everything that reads the clock scales together.** Because a
day/night desc ([037](037_day_night_descs.md)), a business-hours gate
([151](151_business_hours.md)),
an NPC schedule ([068](068_npc_schedule.md)), and a calendar
([144](144_game_calendar.md)) all read the *same* `game_min`/`hour`
attribute, turning the one dial speeds or slows all of them in lockstep —
the whole fictional world's clock, not just the display.

## Build it

The chronometer, with its rate as data and two verbs — read the clock,
and change the rate live:

```text
@dig Chronometry Lab = chronlab, out
chronlab
@create master chronometer
drop master chronometer
@set master chronometer/game_min = 0
@set master chronometer/step = 30
@set master chronometer/on_tick = incr('game_min', V('step', 30))
@behavior master chronometer = script_ticker, interval:1
@set master chronometer/cmd_rate = $set rate *: (set_attr(me, 'step', int(arg0)), pemit(enactor, 'Time now advances ' + arg0 + ' game-minutes per world tick.')) if trim(arg0).isdigit() else pemit(enactor, 'Whole minutes only.')
@set master chronometer/cmd_clock = $clock: m = V('game_min', 0); pemit(enactor, 'Day ' + str(m // 1440 + 1) + ', ' + right('0' + str((m // 60) % 24), 2) + ':' + right('0' + str(m % 60), 2))
```

## Try it

At the default rate, one tick is half a game-hour:

```text
@tr master chronometer/on_tick    +30 game-minutes
clock                             -> Day 1, 00:30
```

Turn the dial up and watch the same tick cover four times the ground:

```text
set rate 120     -> Time now advances 120 game-minutes per world tick.
@tr master chronometer/on_tick
clock            -> Day 1, 02:30
```

One tick, two game-hours. Nothing else changed — the tick script and the
clock reader are untouched; only the `step` between them moved. Slow it
back down with `set rate 15` for a languid world where dusk takes its
time.

## Real time vs game time, and where each belongs

The dial only touches *fiction* time. Keep the boundary clear:

- **Real-time seconds** (fuses, decay, spawns, `wait()`/`expire()`) do
  **not** scale with your dial — a 30-second bomb is 30 real seconds
  whether the calendar is racing or crawling. That's correct: infrastructure
  is wall-clock ([145](145_scheduled_events.md)).
- **Beats** (combat, effects) scale with *combat pace*, not your calendar —
  a slowed fight dilates its poison, independent of what year it is.
- **Game time** (your `game_min`) is the only thing this dial moves, and
  it moves everything that reads it.

Mixing them is the classic bug: don't drive a bomb fuse off `game_min`
(it'd detonate at a different real speed when you change the rate) — use
`wait()`/`expire()` for real-world timing, and the game clock only for the
fiction.

## Going further

- **Per-zone time:** give a zone master its own `time_factor` and compute
  a *local* game-time as `base + (game_min - anchored) × factor` — a
  relativistic anomaly where a day outside is an hour inside, or a
  sleepy hamlet where time drags. Rooms in the zone read their master's
  local clock instead of the global one.
- **Pause time:** `set rate 0` freezes the calendar (the tick adds
  nothing) without stopping the server — handy for a GM staging a scene.
- **Faster nights:** scale asymmetrically by having `on_tick` add more
  minutes when `hour` is nocturnal — long days, short nights — since the
  step is just softcode.
- **Anchor it to real time:** to make the dial *also* survive reboots,
  compute game-time from `now()` and a stored factor rather than a tick
  counter — the absolute-deadline idiom of
  [152](152_persistent_timers.md).
