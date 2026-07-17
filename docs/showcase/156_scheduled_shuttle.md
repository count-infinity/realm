# 156. Scheduled shuttle

> Checklist item 156 — now — *a ticker-driven moving room on a fixed route, boarding windows*

**What you'll build:** An automated shuttle that runs a loop of three
platforms on its own clock. It pulls in, opens its doors for boarding,
then — on the next beat — seals up and glides to the next stop, carrying
whoever climbed aboard. No driver; the timetable is a `script_ticker`.

**Concepts:** the [drivable vehicle](155_drivable_vehicle.md)'s
moving-boarding-exit made **autonomous** with `on_tick`
([tutorial 036](036_weather_system.md)); a **route** as a list of stop
ids the cabin walks in a loop; the **`closed` boarding window** so you
can only board while the doors are open.

## How it works

**Same cab, no hands on the wheel.** Like the rover, the shuttle is a
cabin room with a `shuttle` boarding exit out in the world and a `hatch`
back to the current stop. The difference is who drives: a `script_ticker`
fires the cabin's `on_tick`, and *that* does the departure — instead of
a player typing `drive`.

**The route is a list; the beat advances it.** The cabin holds an
ordered `stops` list of platform ids and an `idx` cursor. Each tick:
seal the boarding exit (`closed`), advance `idx` around the loop
(`% len`), `teleport_obj` the boarding exit to the next platform, relink
the `hatch`, unseal, and announce the arrival. Riders sit in the cabin
through all of it — they move with it for free.

**The boarding window is the `closed` tag.** Between beats the doors
stand open at the current platform; the moment the shuttle departs it
seals the exit, so a late runner hits "The shuttle is closed" and waits
for the next loop. Tighten or loosen the window by changing the ticker's
`interval` — the timetable is one number.

## Build it

Three platforms and the cabin:

```text
@dig Platform One
@teleport me = Platform One
@dig Platform Two
@teleport me = Platform One
@dig Platform Three
@teleport me = Platform One
@dig The Shuttle Cabin
@teleport me = The Shuttle Cabin
@open hatch = Platform One
@teleport me = Platform One
@open shuttle = The Shuttle Cabin
```

Wire the cabin: the route, the cursor, and handles to its two exits:

```text
@teleport me = The Shuttle Cabin
@eval cab=here; p1=get('Platform One'); p2=get('Platform Two'); p3=get('Platform Three'); set_attr(cab,'stops',[p1.id,p2.id,p3.id]); set_attr(cab,'idx',0); hatch=[e for e in contents(cab) if has_tag(e,'exit') and name(e)=='hatch'][0]; board=[o for o in search_world(name='shuttle') if has_tag(o,'exit')][0]; set_attr(cab,'hatch','#'+hatch.id); set_attr(cab,'board','#'+board.id); result='shuttle wired'
```

The timetable — one `on_tick` that seals, advances, relocates the
boarding exit, relinks, and reopens — plus the heartbeat that runs it:

```text
@set The Shuttle Cabin/on_tick = cab=me; stops=get_attr(cab,'stops'); cur=get('#'+str(stops[get_attr(cab,'idx')])); board=get(get_attr(cab,'board')); add_tag(board,'closed'); remit(cur,'The shuttle doors seal; it slides out of the station.'); nxt=(get_attr(cab,'idx')+1) % len(stops); set_attr(cab,'idx',nxt); dest=get('#'+str(stops[nxt])); teleport_obj(board,dest); set_attr(get(get_attr(cab,'hatch')),'destination',dest.id); remove_tag(board,'closed'); remit(dest,'The shuttle glides in; the doors open. Now boarding.'); remit(cab,'The cabin sways as the shuttle changes track.')
@behavior The Shuttle Cabin = script_ticker, interval:15
@teleport me = Platform One
```

## Try it

Board at Platform One while the doors are open:

```text
shuttle             -> you board The Shuttle Cabin
```

Wait for the beat (or force one with `@tr The Shuttle Cabin/on_tick`):

```text
                    -> "The cabin sways as the shuttle changes track."
hatch               -> you step out onto Platform Two
```

Watch a platform without boarding and you'll see the loop breathe:
"...doors seal; it slides out" here, "...glides in; now boarding" one
stop down. Try to `shuttle` the instant after it departs — "The shuttle
is closed" — the boarding window shut with the doors. `@examine The
Shuttle Cabin` shows the `idx` cursor stepping 0 → 1 → 2 → 0 around the
route.

## Going further

- **Timed dwell:** run two tickers ([tutorial 036](036_weather_system.md)
  supports several) — a slow one that departs, a fast one that only
  *warns* ("doors closing!") a beat before — a real boarding countdown.
- **Express vs local:** a second `stops` list and an `express` flag the
  `on_tick` picks between, so rush hour skips Platform Two.
- **Fares:** gate the `shuttle` boarding exit with a [toll](030_toll_gate.md)
  so you tap a fare to board, or sell passes the driver-NPC checks.
- **A visible arrivals board:** stamp the next stop onto a sign at each
  platform (push-on-change) and read it with a `[[...]]` desc — riders
  see "Next: Platform Three" without asking.
