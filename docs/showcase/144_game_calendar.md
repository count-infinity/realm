# 144. Game calendar & clock

> Checklist item 144 ([now]): *softcode clock, custom epoch, month-name tables, integer date arithmetic*

**What you'll build:** A ship's chronometer that keeps a full sci-fi
calendar (a decimal Concord Standard date with named months) and a
`$date` command anyone aboard can read. One object, one counter, and a
little integer arithmetic. Why `$date` and not `$time`? The engine
already ships a builtin `time` command, and builtins dispatch *before*
softcode `$`-triggers, so a softcode `$time` would never fire. Pick a
verb the engine leaves free.

**Concepts:** a softcode clock (the engine ships no game calendar, so
you build one from a counter and a renderer), a monotonic game-time
counter on a [`script_ticker`](../reference/softcode.md#lifecycle-hooks),
deriving date fields by integer division, and month tables as plain
attributes every script can read.

## How it works

The finished clock is a single object holding one number that only ever
grows, plus a read-out command that divides that number into a date the
moment someone asks. This section explains why one counter is the whole
clock, why the calendar uses off-Earth constants, and how the month
names live where any script can reach them.

**One monotonic counter is the whole clock.** The chronometer holds
`game_min`, the total game-minutes since the calendar's year zero, and
its [`on_tick`](../reference/softcode.md#lifecycle-hooks) adds `step`
minutes each world tick. Everything else is *derived*: rather than
storing the year, the month, and the hour separately (three attributes
that can disagree), you store one number and divide it out on demand.
This is the same shape as the town clock in
[tutorial 068](068_npc_schedule.md), which advances one `hour` attribute
modulo 24; here that one attribute grows into a whole calendar. (For the
machinery those engine clocks run on, see
[tutorial 145](145_scheduled_events.md); for a calendar that keeps
flowing across a reboot, [tutorial 152](152_persistent_timers.md); for
changing how fast game-time runs, [tutorial 153](153_time_scaling.md).)

REALM runs two *real* clocks under the hood: a fast real-time heartbeat
measured in seconds, and integer combat and effect beats. Neither is a
*fiction* clock, because "what year is it in the game" is content, so it
lives in softcode.

**The calendar is decimal, and that is a design choice.** Concord
Standard runs 60-minute hours, **20-hour days**, **30-day months**, and
**10 months** to a year, round numbers that make the division obvious
and the setting feel off-Earth. Swap the constants and the month table
for any calendar you like, and the `$date` renderer works the same.

**Month names are a table, so anyone can read them.** `months` is a list
attribute and the renderer indexes it. Attribute reads are open to every
script through [`get_attr`](../reference/softcode.md#fn-get_attr), so an
NPC greeting, a festival trigger, or a day/night desc can all ask the
chronometer what date it is.

## Build it

First, somewhere to hang the clock, then the chronometer object itself,
dropped so it stands in the world:

```text
@dig Observation Deck = obdeck, out
obdeck
@create ship chronometer
drop ship chronometer
```

Now the counter and its tables. `game_min` is the one number that grows;
`step` is how many game-minutes each tick adds; `epoch_year` sets the
calendar's year zero; and `months` is the name table the renderer will
index:

```text
@set ship chronometer/game_min = 0
@set ship chronometer/step = 30
@set ship chronometer/epoch_year = 812
@set ship chronometer/months = ["Ignis", "Ventus", "Terra", "Aqua", "Lumen", "Umbra", "Ferro", "Nix", "Sol", "Void"]
```

The tick advances the clock. Its `on_tick` is a single statement:
[`incr`](../reference/softcode.md#fn-incr) bumps `game_min` by
[`V('step', 30)`](../reference/softcode.md#fn-v), which reads `step` off
the chronometer. Attaching a `script_ticker` at `interval:1` fires that
`on_tick` once per world tick (~4s), so 30 game-minutes pass each tick,
brisk enough to watch a day roll over while testing:

```text
@set ship chronometer/on_tick = incr('game_min', V('step', 30))
@behavior ship chronometer = script_ticker, interval:1
```

Finally the `$date` read-out. It reads the one counter, divides out each
field (minute, hour, day, month, year), indexes the month table, and
sends the line to the reader with
[`pemit`](../reference/softcode.md#fn-pemit). The magic numbers are the
unit sizes multiplied up: `1200 = 60x20` game-minutes per day,
`36000 = 1200x30` per month, and `360000 = 36000x10` per year.
[`right`](../reference/softcode.md#fn-right) keeps the two rightmost
characters of `'0' + str(x)`, the zero-pad idiom:

```text
@set ship chronometer/cmd_date = '''
$date:
m = V('game_min', 0)
mo = V('months', [])
minute = m % 60
hour = (m // 60) % 20
day = (m // 1200) % 30 + 1     # days count from 1; minute/hour/month from 0
month = (m // 36000) % 10
year = V('epoch_year', 0) + m // 360000
stamp = f'CS {year}.{right("0" + str(month + 1), 2)}.{right("0" + str(day), 2)} // {right("0" + str(hour), 2)}:{right("0" + str(minute), 2)}'
pemit(enactor, f'{stamp} -- month of {mo[month] if mo else "?"}.')
'''
```

## Try it

Force one tick to advance the clock by 30 game-minutes with
`@tr <object>/<attribute>`, then read the date. Any player standing on
the Observation Deck can type `date`, since the command lives on the
chronometer they share:

```text
> @tr ship chronometer/on_tick
> date
CS 812.01.01 // 00:30 -- month of Ignis.
```

Jump the counter forward to prove the arithmetic. Setting `game_min`
straight is a builder override that stands in for a long stretch of
ticks:

```text
> @set ship chronometer/game_min = 88662
> date
CS 812.03.14 // 17:42 -- month of Terra.
```

88662 minutes is 2 months (72000), 13 days (15600), 17 hours (1020) and
42 minutes past year zero, which the renderer shows as the third month,
the 14th day, 17:42. Let it run and the days tick past on their own, and
every clock reader in your game sees the same date.

## Going further

- **Weekdays & festivals:** add a `days` table and index it by
  `(m // 1200) % len(days)`, then a `$date` line that names market-day
  and a scheduler ([tutorial 145](145_scheduled_events.md)) that fires
  the festival only on it.
- **A wall clock in the desc:** give the Observation Deck a `[[...]]`
  block that reads the chronometer, but stamp the time onto the room on
  the tick and read it locally, the push-on-change discipline of
  [tutorial 036](036_weather_system.md), rather than a remote read every
  look.
- **Seasons drive weather:** feed `month` into the weather master's
  table choice so winter months pick the snow table.
- **It should survive downtime:** this counter pauses while the server is
  down. To keep game-time flowing across a reboot, anchor it to
  [`now()`](../reference/softcode.md#fn-now) instead of a tick counter.
  [Tutorial 152](152_persistent_timers.md) shows the absolute-deadline
  trick that makes it so.
