# 171. Dynamic descriptions

> Checklist item 171 — [now] — *[[...]] inline blocks weaving state, push-on-change for shared/expensive state*

**What you'll build:** a lighthouse gallery whose description *reads the
world* — it reports whether the great lamp is lit, and paints a swept-beam
line only when it is — with the shared lamp state pushed onto the room by
a ticker, not fetched per look. (Builder permission: `@desc`, `@set`,
`@behavior` are builder tools.)

**Concepts:** `[[...]]` inline blocks that weave live state into prose,
`result` as the substituted value, and the **push-on-change** idiom —
compute expensive/shared state once on a ticker and stamp it onto the
object, so the render-time block stays a cheap local read.

See [inline functions in text](242_inline_functions.md) for the `[[...]]`
fundamentals (the `viewer` binding, per-look randomness, stateful text);
this tutorial is about **descriptions driven by shared state** and the
performance idiom that keeps them fast.

## How it works

**A description can read the world.** Any `[[...]]` block in a desc runs
through the script sandbox when someone looks, with `me` bound to the
described object; whatever it assigns to `result` replaces the block. So
a room can report its own state — `V('lamp_state', 'dark')` —
and a second block can *conditionally exist*: assign a colored line when
lit, the empty string otherwise, and low-state viewers simply never read
it. Multiple blocks compose in one description.

**Keep render-time blocks cheap and local.** Blocks run **per look, per
viewer, on the look's own call stack**, and the sandbox's recursion cap
is currently absolute (a known defect) — so a block that chases a *remote*
value through nested `get_attr('<other object>', ...)` calls can fail
closed depending on how deep the dispatch already is. The robust habit:
each block does **one shallow read of `me`**. Anything remote or
expensive gets **pushed** onto the object ahead of time.

**Push-on-change beats pull-per-look.** The lamp's real state is *zone*
state — many rooms share it. Instead of every room's desc reaching across
to a master each look (remote, repeated, fragile), the zone master's
**ticker** computes the state and **stamps** each room's `lamp_state`
attribute, announcing transitions once. The remote lookup happens **once
per change, on the worker stack**; the desc block is forever a single
local read. This is the same discipline the
[weather system](036_weather_system.md) uses — and the reason to reach
for it here is that a lighthouse beam visible across a whole cape is
exactly the kind of shared state you must not pull per viewer.

## Build it

Dig the gallery, put it in a zone, seed the shared state, and hang a
two-block description — a state line and a conditional beam line:

```text
@dig Lighthouse Gallery = up, down
up
@zone here = cape
@set here/lamp_state = dark
@desc here = A spiral stair climbs to the lamp room. [[result = 'The great lamp is ' + V('lamp_state', 'dark') + '.']] [[result = ansi('yh', 'A beam sweeps the black water below.') if V('lamp_state', 'dark') == 'lit' else '']]
```

The keeper — a zone master whose tick computes the lamp state and
**pushes** it to every cape room, announcing only real transitions:

```text
@create lamp keeper
@zone/master lamp keeper = cape
drop lamp keeper
@set lamp keeper/on_tick = state = 'lit' if (now() // 30) % 2 == 0 else 'dark'; [(set_attr(r, 'lamp_state', state), remit(r, 'The lamp ' + ('flares to life.' if state == 'lit' else 'gutters out.'))) for r in zone_rooms('cape') if get_attr(r, 'lamp_state', 'dark') != state]
@behavior lamp keeper = script_ticker, interval:15
```

The desc reads only `me`'s local `lamp_state`; the keeper is what makes
that local value true. Every cape room added later gets the beam for
free — membership is the tag.

## Try it

```text
look
  Lighthouse Gallery
  A spiral stair climbs to the lamp room. The great lamp is dark.
```

Flip the state by hand (the GM override) and look again:

```text
@set here/lamp_state = lit
look
  ... The great lamp is lit. A beam sweeps the black water below.
```

The second block only *exists* when lit. Left alone, the keeper's tick
drives the cycle — everyone in the cape hears "The lamp flares to life."
on the transition, and each room's desc re-weaves on the next look with a
single local read. `@examine here` shows the raw `[[...]]` source;
`look` shows the render.

## Going further

- **Per-viewer *and* shared:** combine a pushed shared read with a
  `viewer`-based one — `... if skill('observation') >= 12 else ''` — so
  the beam is visible to all but a spotted smuggler's silhouette only to
  sharp eyes (see [inline functions](242_inline_functions.md)).
- **Time without a ticker:** `now()` in the block itself gives a cycle
  with no master at all — fine when the state is cheap and purely a
  function of the clock; reach for push-on-change once other rooms or
  expensive lookups are involved.
- **Delegate the renderer:** keep a long description generator in one
  function attribute and call `result = eval_attr(me, 'render')` from
  several rooms' descs — softcode's subroutine.
- **Mechanical, not just flavor:** a [hazard tick](043_hazard_room.md)
  can read the same pushed `lamp_state` to blind night raiders while the
  beam sweeps.
