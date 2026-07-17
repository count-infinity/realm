# 144. Game calendar & clock

> Checklist item 144 — [now] — *softcode clock, now() arithmetic, month-name tables, $date*

**What you'll build:** A ship's chronometer that keeps a full sci-fi
calendar — a decimal Concord Standard date with named months — and a
`$date` command anyone aboard can read. One object, one counter, and a
little integer arithmetic. (Why `$date` and not `$time`? The engine
already ships a builtin `time` command, and builtins dispatch *before*
softcode `$`-triggers — so softcode can't shadow `time`. Pick a verb the
engine hasn't taken.)

**Concepts:** the softcode clock (the engine ships no game calendar —
you build a better one in two lines), a monotonic game-time counter on a
`script_ticker`, deriving date fields by integer division, and month
tables as plain attributes every script can read.

## How it works

REALM runs two *real* clocks under the hood — a fast real-time
heartbeat (seconds) and integer combat/effect **beats**. Neither is a
*fiction* clock: "what year is it in the game" is content, so it lives
in softcode, exactly like the town clock in
[tutorial 068](068_npc_schedule.md) — only here we grow that one `hour`
attribute into a whole calendar. (For the machinery those two engine
clocks run on, see [tutorial 145](145_scheduled_events.md); for a
calendar that keeps flowing across a reboot, [tutorial
152](152_persistent_timers.md); for changing how fast game-time runs,
[tutorial 153](153_time_scaling.md).)

**One monotonic counter is the whole clock.** The chronometer holds
`game_min` — total game-minutes since the calendar's year zero — and its
`on_tick` adds `step` minutes each world tick. Everything else is
*derived*: you never store the year, the month, and the hour
separately (three attributes that can disagree), you store one number
and divide it out on demand.

**The calendar is decimal, and that's a design choice.** Concord
Standard runs 60-minute hours, **20-hour days**, **30-day months**, and
**10 months** to a year — clean powers that make the division obvious
and the setting feel off-Earth. Swap the constants and the month table
for any calendar you like; the `$time` renderer doesn't care.

**Month names are a table, so anyone can read them.** `months` is a
list attribute; the renderer indexes it. Attribute reads are open to
every script (the one-clock-many-readers move), so an NPC greeting, a
festival trigger, or a day/night desc can all ask the chronometer what
date it is.

## Build it

Somewhere to hang the clock, then the chronometer itself — its counter,
its tables, and the tick that advances it. `step:30` at `interval:1`
means 30 game-minutes per world tick (~4s) — brisk enough to watch a day
roll over while testing:

```text
@dig Observation Deck = obdeck, out
obdeck
@create ship chronometer
drop ship chronometer
@set ship chronometer/game_min = 0
@set ship chronometer/step = 30
@set ship chronometer/epoch_year = 812
@set ship chronometer/months = ["Ignis", "Ventus", "Terra", "Aqua", "Lumen", "Umbra", "Ferro", "Nix", "Sol", "Void"]
@set ship chronometer/on_tick = set_attr(me, 'game_min', get_attr(me, 'game_min', 0) + get_attr(me, 'step', 30))
@behavior ship chronometer = script_ticker, interval:1
```

Now the `$date` read-out. It pulls the one counter and divides out each
field — minute, hour, day, month, year — then indexes the month table.
`right('0' + str(x), 2)` is the zero-pad idiom:

```text
@set ship chronometer/cmd_date = $date: m = get_attr(me, 'game_min', 0); mo = get_attr(me, 'months', []); minute = m % 60; hour = (m // 60) % 20; day = (m // 1200) % 30 + 1; month = (m // 36000) % 10; year = get_attr(me, 'epoch_year', 0) + m // 360000; pemit(enactor, 'CS ' + str(year) + '.' + right('0' + str(month + 1), 2) + '.' + right('0' + str(day), 2) + ' // ' + right('0' + str(hour), 2) + ':' + right('0' + str(minute), 2) + ' -- month of ' + (mo[month] if mo else '?') + '.')
```

The magic numbers are just the unit sizes multiplied up: `1200 = 60×20`
(minutes per day), `36000 = 1200×30` (per month), `360000 = 36000×10`
(per year).

## Try it

```text
@tr ship chronometer/on_tick        force one tick: +30 game-minutes
date
   -> CS 812.01.01 // 00:30 -- month of Ignis.
```

Jump the clock forward to prove the arithmetic (a GM override — set the
counter straight):

```text
@set ship chronometer/game_min = 88662
date
   -> CS 812.03.14 // 17:42 -- month of Terra.
```

88662 minutes is 2 months (72000), 13 days (15600), 17 hours (1020) and
42 minutes past year zero — so the third month, the 14th day, 17:42. Let
it run and the days tick past on their own; every clock reader in your
game sees the same date.

## Going further

- **Weekdays & festivals:** add a `days` table and index it by
  `(m // 1200) % len(days)`; a `$time` line that names market-day, and a
  scheduler ([tutorial 145](145_scheduled_events.md)) that only fires the
  festival on it.
- **A wall clock in the desc:** give the Observation Deck a `[[...]]`
  block that reads the chronometer — but stamp the time onto the room on
  the tick and read it locally, the push-on-change discipline of
  [tutorial 036](036_weather_system.md), rather than a remote read every
  look.
- **Seasons drive weather:** feed `month` into the weather master's
  table choice so winter months pick the snow table.
- **It should survive downtime:** this counter pauses while the server is
  down. To keep game-time flowing across a reboot, anchor it to `now()`
  instead of a tick counter — [tutorial 152](152_persistent_timers.md)
  shows the absolute-deadline trick that makes it so.
