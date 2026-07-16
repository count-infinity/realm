# 023. Conveyor Belt

> Checklist item 23 — [now] — *script_ticker, move_to, room chaining*

**What you'll build:** A freight line: drop a crate on the belt in the
workshop and it rides — clattering room to room on the server's
heartbeat — until it slides off onto the loading dock floor, three
rooms away, with nobody carrying it.

**Concepts:** `script_ticker` as the machine's motor, an `on_tick`
that relocates its own contents, `next_stop` attributes as the chain's
wiring (each segment knows only its successor — the classic linked
list, in furniture), and `teleport_obj` for cargo handling — plus why
the belt is *allowed* to fling other people's crates around.

## How it works

**A segment is a container with a destination.** Each belt is an
ordinary `container = true` thing (so `put crate in belt alpha` is
stock machinery, wards and all) holding one attribute: `next_stop`,
the `#id` of wherever its cargo goes next. Chaining is nothing but
each segment pointing at the next; the last one points at a *room*,
which is how the line ends — cargo teleported into a room is simply
on the floor. Extending the line is one new segment and one rewired
attribute, and no other segment knows it happened.

**The motor is a ticker.** `@behavior <belt> = script_ticker,
interval:1` runs the belt's `on_tick` every heartbeat: count the
cargo, relocate all of it to `next_stop`, and rattle audibly if
anything moved. An item that lands on segment beta mid-tick rides
onward on beta's *next* tick — one hop per beat, which is what makes
it a conveyor and not a teleporter. Note the script reads
`get_attr(me, 'next_stop')` *inside* the comprehension: softcode
one-liners can't see their own earlier locals from inside a
comprehension body, so keep reads inline there (locals are fine
everywhere else on the line).

**Why the belt may move your crate.** `teleport_obj` requires
relocation authority — and anything standing *inside* the belt
qualifies, because the belt controls its own interior (the room-owner
teleport rule: you may shove around what stands in a place you own).
Whoever made the crate, once it's on the belt, it rides.
`teleport_obj` tunnels past wards but still honors the destination's
locks; use plain `move_to` instead if warded rooms should be able to
refuse freight.

## Build it

Segment alpha, in the workshop — motor, cargo script, and all:

```text
@create belt alpha
@set belt alpha/container = true
drop belt alpha
@set belt alpha/on_tick = n = len(contents(me)); [teleport_obj(o, get_attr(me, 'next_stop')) for o in contents(me)]; remit(loc(me), 'The belt clatters; the cargo slides out of sight.') if n else None
@behavior belt alpha = script_ticker, interval:1
```

Dig down the line and lay segment beta (same script, same motor):

```text
@dig Packing Floor = downline, upline
downline
@create belt beta
@set belt beta/container = true
drop belt beta
@set belt beta/on_tick = n = len(contents(me)); [teleport_obj(o, get_attr(me, 'next_stop')) for o in contents(me)]; remit(loc(me), 'The belt clatters; the cargo slides out of sight.') if n else None
@behavior belt beta = script_ticker, interval:1
@dig Loading Dock = downline, upline
```

Wire the chain — alpha feeds beta, beta dumps onto the dock floor —
then walk home:

```text
@eval a = get('belt alpha'); b = get('belt beta'); set_attr(a, 'next_stop', '#' + b.id); set_attr(b, 'next_stop', '#' + get('Loading Dock').id); result = 'belt line wired'
upline
```

## Try it

```text
@create crate of gears
put crate of gears in belt alpha
```

Then watch the heartbeats: the workshop hears `The belt clatters; the
cargo slides out of sight.` as the crate jumps to belt beta; a beat
later the Packing Floor hears the same as beta hands it on; walk
`downline`, `downline` and the crate of gears is sitting on the
Loading Dock floor, ready to `get`. Ride two crates a beat apart and
they arrive in order, one hop per tick, forever — until someone
`@behavior/remove`s a motor or `@tag <belt> = halt`s the line.

## Going further

- **A return loop:** point the dock's own belt back at alpha and the
  line becomes a circle — luggage carousels are conveyor belts that
  ate their tails.
- **Sorting:** make the tick choose `next_stop` per item —
  `get_attr(me, 'next_' + ('cold' if has_tag(o, 'perishable') else 'dry'))`
  — and the belt is a router;
  [018](018_refrigerator.md)'s peaches would appreciate the cold
  branch.
- **A slow line:** `interval:8` moves cargo every ~30 seconds; add
  `@behavior/set` to retune a running line without touching the
  script.
- **Passengers:** the tick deliberately moves *everything* inside;
  gate with `if not has_tag(o, 'player')` — or don't, and the belt is
  also a ride ([034](checklist.md)'s climbing exit for people with
  no legs to climb).
