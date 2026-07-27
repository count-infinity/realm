# 151. Business hours

> Checklist item 151 ([now]): *clock-driven behavior attach/detach, [[...]] closed states*

**What you'll build:** A trade terminal that only works during market
hours. Between 09:00 and 17:00 its light is green and `access terminal`
opens the markets; after hours the screen is dark and it turns you away.
The gate lives on the object, driven by a shared clock.

**Concepts:** an object-side time-gate (the device checks the clock
itself, rather than an NPC walking away), a `script_ticker` that stamps
an `open` flag, and a `[[...]]` description that reads that flag with a
single shallow local read, which is the push-on-change discipline.

## How it works

The finished device is three cooperating pieces: a clock object that
advances an `hour`, a ticker on the terminal that reads that hour and
stamps an `open` flag on itself, and a `[[...]]` description plus an
`access` command that both consult the stamped flag. This section
answers where the time lives, how the terminal decides open from closed,
and why the flag is stamped by the ticker instead of computed at look
time.

### Why gate the object instead of moving a keeper?

There are two honest ways to close a shop for the night, and they teach
different things. In [tutorial 068](068_npc_schedule.md), Verity locks up
and walks home, so the shop is closed because the `shopkeeper` behavior
is no longer in the room; presence is the mechanic, which is right for a
living NPC. A vending terminal, an airlock, or an automated bank has no
keeper to send home, so it reads the clock and refuses service itself.
That is this tutorial: the time-gate as a property of the device.

### Where does the time live?

The terminal does not keep its own time. It reads an `hour` off a shared
market clock, the same pattern the NPC schedule
([068](068_npc_schedule.md)) and game calendar
([144](144_game_calendar.md)) use. The gate is one comparison,
`open_hour <= hour < close_hour`, so the whole station opens and closes
against one authority.

### Why stamp the flag on a tick instead of at look time?

Rather than recompute open versus closed inside the description on every
look, the terminal's [`on_tick`](../reference/softcode.md#lifecycle-hooks)
computes the flag once per tick and stamps an `open` attribute on itself
with [`set_attr`](../reference/softcode.md#fn-set_attr). The
`[[...]]` description then does a single shallow
[`V`](../reference/softcode.md#fn-v)`('open', 0)`. That is the
push-on-change rule from the [weather system](036_weather_system.md):
compute on the ticker, which runs on its own worker stack, and read
locally at render time. A description block runs per look and per viewer
on the look's own call stack, so a deep remote read there (reaching
across to the clock every look) is exactly what push-on-change avoids.

## Build it

First dig the annex the terminal serves, step into it, and stand up a
minimal market clock whose only job is to advance one `hour` per beat.
The clock carries a `script_ticker` so its `on_tick` fires on the
heartbeat:

```text
@dig Trade Annex = annex, out
annex
@create market clock
drop market clock
@set market clock/hour = 8
@set market clock/on_tick = set_attr(me, 'hour', (V('hour', 0) + 1) % 24)
@behavior market clock = script_ticker, interval:1
```

Now create the terminal and set its trading window, plus a seeded `open`
of 0 so the description has something to read before the first tick:

```text
@create trade terminal
drop trade terminal
@set trade terminal/open_hour = 9
@set trade terminal/close_hour = 17
@set trade terminal/open = 0
```

The `refresh` routine reads the clock's hour once with
[`get_attr`](../reference/softcode.md#fn-get_attr) and stamps `open` from
the one comparison. Its two statements make it a multi-line block:

```text
@set trade terminal/refresh = '''
h = get_attr('market clock', 'hour', 12)
set_attr(me, 'open', 1 if V('open_hour', 9) <= h < V('close_hour', 17) else 0)
'''
```

The ticker runs `refresh` once per beat with
[`eval_attr`](../reference/softcode.md#fn-eval_attr), and the description
reads only the stamped flag, so the green or red light is a local read:

```text
@set trade terminal/on_tick = eval_attr(me, 'refresh')
@behavior trade terminal = script_ticker, interval:1
@desc trade terminal = A wall-mounted trade console. [[result = 'A green OPEN light glows steadily.' if V('open', 0) else 'A red CLOSED light glows; the screen is dark.']]
```

Finally the gate itself. The `access` command reads the stamped flag,
never the clock, and reports the posted hours when the screen is dark.
It is a global `$`-command that any player in the room may type, so it
takes no `target` guard:

```text
@set trade terminal/cmd_access = '''
$access terminal:
if V('open', 0):
    pemit(enactor, 'ACCESS GRANTED. The markets are live -- place your orders.')
else:
    pemit(enactor, f"The screen is dark. Trade hours are {V('open_hour', 9)}:00 to {V('close_hour', 17)}:00.")
'''
```

The [`pemit`](../reference/softcode.md#fn-pemit) sends its line only to
the player who typed the command.

## Try it

It is 08:00 and the terminal is seeded closed, so the light is red and
`access` reports the posted hours:

```text
> look trade terminal
A wall-mounted trade console. A red CLOSED light glows; the screen is dark.

> access terminal
The screen is dark. Trade hours are 9:00 to 17:00.
```

Roll the clock to opening. Force one tick on the clock to move the hour
from 8 to 9, then one tick on the terminal so its `refresh` re-reads and
stamps `open`:

```text
> @tr market clock/on_tick
Triggered market clock/on_tick.

> @tr trade terminal/on_tick
Triggered trade terminal/on_tick.

> look trade terminal
A wall-mounted trade console. A green OPEN light glows steadily.

> access terminal
ACCESS GRANTED. The markets are live -- place your orders.
```

Run the clock on to 17:00 and the next terminal tick stamps it shut
again, green light back to red and granted back to dark, all from one
comparison against a clock the whole station shares.

## Going further

- **Physically lock the door:** in `refresh`, use
  [`add_tag`](../reference/softcode.md#fn-add_tag) and
  [`remove_tag`](../reference/softcode.md#fn-remove_tag) to put a
  `closed` tag on the annex entrance when closing and take it off when
  opening, so after hours the shop is sealed as well as unresponsive.
- **Holidays and weekends:** gate on the calendar too, reading
  [144](144_game_calendar.md)'s `day` and `month` and closing on festival
  days from a schedule row ([145](145_scheduled_events.md)).
- **Happy hour pricing:** stamp a `markup` alongside `open` and have a
  shopkeeper read it, so drinks are cheaper from 16:00 to 18:00.
- **Staffed hours, automated after:** compose both closings, with the
  keeper working the counter by day ([068](068_npc_schedule.md)) and the
  terminal taking over the night shift.
