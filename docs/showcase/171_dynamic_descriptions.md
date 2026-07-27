# 171. Dynamic descriptions

> Checklist item 171 ([now]): *descriptions that weave live state via `[[...]]` inline evaluation*

**What you'll build:** a lighthouse gallery whose description *reads the
world*. It reports whether the great lamp is lit, and it paints a
swept-beam line only while the lamp burns. The shared lamp state is
pushed onto the room by a ticker rather than fetched on every look.

**Concepts:** `[[...]]` inline blocks that weave live state into prose,
`result` as the substituted value, and the **push-on-change** idiom, where
a ticker computes expensive or shared state once and stamps it onto the
object so the render-time block stays a cheap local read.

See [inline functions in text](242_inline_functions.md) for the `[[...]]`
fundamentals (the `viewer` binding, per-look randomness, stateful text).
This tutorial is about descriptions driven by *shared* state and the
performance idiom that keeps them fast.

## How it works

The finished gallery has two moving parts: a description with two inline
blocks (one that always prints the lamp's state, one that prints a beam
line only when lit), and a zone master whose ticker keeps every cape
room's `lamp_state` current. This section answers three questions: how a
description reads the world, why render-time blocks stay local, and why
the ticker pushes the state instead of each room pulling it.

### How a description reads the world

Any `[[...]]` block in a description runs through the script sandbox when
someone looks, with `me` bound to the described object and `viewer` bound
to the looker. Whatever the block assigns to `result` replaces the block
in the rendered text. So a room reports its own state by reading a local
attribute with [`V`](../reference/softcode.md#fn-v) (`V('lamp_state',
'dark')`), and a second block can *conditionally exist*: it assigns a
colored line when the lamp is lit and the empty string otherwise, so a
viewer of a dark gallery sees nothing where the beam would be. Multiple
blocks compose in one description.

### Why render-time blocks stay local

Blocks run **per look, per viewer, on the look's own call stack**, and the
sandbox's recursion cap is currently absolute (a known defect), so a block
that chases a *remote* value through nested
[`get_attr`](../reference/softcode.md#fn-get_attr)`('<other object>', ...)`
calls may fail closed depending on how deep the dispatch already is. The
robust habit is that each block does **one shallow read of `me`**. Anything
remote or expensive is **pushed** onto the object ahead of time.

### Why the ticker pushes the state

The lamp's real state is *zone* state, since many rooms share it. Rather
than every room's description reaching across to a master on each look
(remote, repeated, fragile), the zone master's **ticker** computes the
state and **stamps** each cape room's `lamp_state` attribute, announcing
only real transitions. The remote lookup happens once per change on the
worker stack, and the description block stays a single local read. This is
the same discipline the [weather system](036_weather_system.md) uses, and
the reason to reach for it here is that a lighthouse beam visible across a
whole cape is exactly the kind of shared state that should not be pulled
per viewer. The tick fires on the keeper alone through the `script_ticker`
behavior ([lifecycle hooks](../reference/softcode.md#lifecycle-hooks)), so
it needs no per-object [`target` guard](../reference/softcode.md#guard-on-target).

## Build it

Dig the gallery, put it in the `cape` zone, and seed the shared state so
the first look has something to read:

```text
@dig Lighthouse Gallery = up, down
up
@zone here = cape
@set here/lamp_state = dark
```

Hang a two-block description: the first block always prints the lamp's
state, and the second uses [`ansi`](../reference/softcode.md#fn-ansi) to
paint a beam line only when the lamp is lit, printing nothing otherwise.
Both are single-expression inline blocks, so this stays one `@desc` line:

```text
@desc here = A spiral stair climbs to the lamp room. [[result = 'The great lamp is ' + V('lamp_state', 'dark') + '.']] [[result = ansi('yh', 'A beam sweeps the black water below.') if V('lamp_state', 'dark') == 'lit' else '']]
```

Create the keeper as a zone master for `cape`, and drop it into the room so
it lives in the world:

```text
@create lamp keeper
@zone/master lamp keeper = cape
drop lamp keeper
```

Give the keeper a tick that computes the lamp state from the clock, walks
every cape room with [`zone_rooms`](../reference/softcode.md#fn-zone_rooms),
stamps the changed rooms with
[`set_attr`](../reference/softcode.md#fn-set_attr), and announces each
change to the people standing there with
[`remit`](../reference/softcode.md#fn-remit):

```text
@set lamp keeper/on_tick = '''
state = 'lit' if (now() // 30) % 2 == 0 else 'dark'
for r in zone_rooms('cape'):
    # push and announce only where the computed state differs from the room's
    if get_attr(r, 'lamp_state', 'dark') != state:
        set_attr(r, 'lamp_state', state)
        remit(r, 'The lamp ' + ('flares to life.' if state == 'lit' else 'gutters out.'))
'''
```

Attach the `script_ticker` behavior so the tick runs on an interval:

```text
@behavior lamp keeper = script_ticker, interval:15
```

The description reads only `me`'s local `lamp_state`; the keeper is what
keeps that local value true. Every cape room the keeper finds has its
`lamp_state` pushed on each transition, so giving a new room the same
two-block description makes the beam appear with no extra wiring. Zone
membership is just the tag.

## Try it

```text
look
  Lighthouse Gallery
  A spiral stair climbs to the lamp room. The great lamp is dark.
```

Flip the state by hand (the GM override) and look again. The state line
now reads `lit`, and the second block, empty until now, prints the beam:

```text
@set here/lamp_state = lit
look
  ... The great lamp is lit. A beam sweeps the black water below.
```

Left alone, the keeper's tick drives the cycle: everyone standing in a
cape room hears "The lamp flares to life." on the transition, and each
room's description re-weaves on the next look with a single local read.
[`now`](../reference/softcode.md#fn-now)`() // 30` is steady within a
single moment, so a tick only announces when the computed state crosses a
boundary. `@examine here` shows the raw `[[...]]` source, while `look`
shows the render.

## Going further

- **Per-viewer *and* shared:** combine a pushed shared read with a
  `viewer`-based one, such as `... if skill('observation') >= 12 else ''`,
  so the beam is visible to all but a spotted smuggler's silhouette shows
  only to sharp eyes (see [inline functions](242_inline_functions.md)).
- **Time without a ticker:** `now()` in the block itself gives a cycle
  with no master at all, which is fine when the state is cheap and purely a
  function of the clock. Reach for push-on-change once other rooms or
  expensive lookups are involved.
- **Delegate the renderer:** keep a long description generator in one
  function attribute and call
  `result = `[`eval_attr`](../reference/softcode.md#fn-eval_attr)`(me, 'render')`
  from several rooms' descriptions, which is softcode's subroutine.
- **Mechanical, not just flavor:** a [hazard tick](043_hazard_room.md) can
  read the same pushed `lamp_state` to blind night raiders while the beam
  sweeps.
