# 151. Business hours

> Checklist item 151 — [now] — *object-side time-gate, clock-driven open/closed state, push-on-change desc*

**What you'll build:** A trade terminal that only works during market
hours. Between 09:00 and 17:00 its light is green and `access terminal`
opens the markets; after hours the screen is dark and it turns you away.
The gate lives on the object, driven by a shared clock.

**Concepts:** an **object-side time-gate** (the thing checks the clock
itself, rather than an NPC walking away), a `script_ticker` that stamps
an `open` flag, and a `[[...]]` desc that reads that flag with a single
shallow local — the push-on-change discipline.

## How it works

There are two honest ways to close a shop for the night, and they teach
different things:

- **Move the keeper.** In [tutorial 068](068_npc_schedule.md), Verity
  literally locks up and walks home; the shop is closed because the
  `shopkeeper` behavior is no longer in the room. Presence *is* the
  mechanic — beautiful for a living NPC.
- **Gate the object.** A vending terminal, an airlock, an automated
  bank has no keeper to send home. It reads the clock and refuses service
  itself. That's this tutorial — the time-gate as a property of the
  device.

**One shared clock, read by the device.** The terminal doesn't keep its
own time; it reads an `hour` off a colony/market clock (the
[068](068_npc_schedule.md)/[144](144_game_calendar.md) pattern). The
gate is one comparison: `open_hour <= hour < close_hour`.

**The tick stamps state; the desc reads it.** Rather than recompute
open/closed inside the description on every look, the terminal's
`on_tick` computes the flag *once per tick* and stamps an `open`
attribute on itself; the `[[...]]` desc block does a single shallow
`V('open', 0)`. That's the **push-on-change** rule from
[tutorial 036](036_weather_system.md): compute on the ticker (its own
worker stack), read locally at render time. Deep remote reads inside a
desc — reaching across to the clock every look, per viewer — are exactly
what to avoid.

## Build it

A market clock (the minimal hour-ticker) and the annex it serves:

```text
@dig Trade Annex = annex, out
annex
@create market clock
drop market clock
@set market clock/hour = 8
@set market clock/on_tick = set_attr(me, 'hour', (V('hour', 0) + 1) % 24)
@behavior market clock = script_ticker, interval:1
```

The terminal: its hours, the refresh that stamps `open`, the tick that
runs it, a seeded `open` for the desc to read before the first tick, and
the light in its description:

```text
@create trade terminal
drop trade terminal
@set trade terminal/open_hour = 9
@set trade terminal/close_hour = 17
@set trade terminal/open = 0
@set trade terminal/refresh = h = get_attr('market clock', 'hour', 12); set_attr(me, 'open', 1 if V('open_hour', 9) <= h < V('close_hour', 17) else 0)
@set trade terminal/on_tick = eval_attr(me, 'refresh')
@behavior trade terminal = script_ticker, interval:1
@desc trade terminal = A wall-mounted trade console. [[result = 'A green OPEN light glows steadily.' if V('open', 0) else 'A red CLOSED light glows; the screen is dark.']]
```

And the gate itself — `access` reads the stamped flag, not the clock:

```text
@set trade terminal/cmd_access = $access terminal: pemit(enactor, 'ACCESS GRANTED. The markets are live -- place your orders.') if V('open', 0) else pemit(enactor, 'The screen is dark. Trade hours are ' + str(V('open_hour', 9)) + ':00 to ' + str(V('close_hour', 17)) + ':00.')
```

## Try it

It's 08:00 and seeded closed:

```text
look trade terminal   -> ... A red CLOSED light glows; the screen is dark.
access terminal       -> The screen is dark. Trade hours are 9:00 to 17:00.
```

Roll the clock to opening (force a tick on the clock, then the terminal
so it re-reads):

```text
@tr market clock/on_tick    hour 8 -> 9
@tr trade terminal/on_tick  refresh: open = 1
look trade terminal         -> ... A green OPEN light glows steadily.
access terminal             -> ACCESS GRANTED. The markets are live -- place your orders.
```

Run the clock on to 17:00 and the next terminal tick stamps it shut
again — green light to red, granted to dark — all from one comparison
against a clock the whole station shares.

## Going further

- **Physically lock the door:** in `refresh`, `add_tag`/`remove_tag` a
  `closed` tag on the annex's entrance exit when closing/opening — after
  hours the shop is not just unresponsive but sealed (068's "lock up
  behind her").
- **Holidays & weekends:** gate on the calendar too — read
  [144](144_game_calendar.md)'s `day`/`month` and close on festival days
  from a schedule row ([145](145_scheduled_events.md)).
- **Happy hour pricing:** stamp a `markup` alongside `open` and have a
  shopkeeper read it — cheaper drinks 16:00–18:00.
- **Staffed hours, automated after:** compose both closings — the keeper
  works the counter by day (068), the terminal takes over the night
  shift.
