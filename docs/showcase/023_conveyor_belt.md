# 023. Conveyor Belt

> Checklist item 23 ([now]): *script_ticker, move_to, room chaining*

**What you'll build:** A freight line. Drop a crate on the belt in the
workshop and it rides room to room on the server's heartbeat, clattering as it
goes, until it slides off onto the loading dock floor three rooms away, with
nobody carrying it.

**Concepts:** the `script_ticker` behavior as the machine's motor, an
[`on_tick`](../reference/softcode.md#lifecycle-hooks) script that relocates its
own contents with [`move_to`](../reference/softcode.md#fn-move_to), `next_stop`
attributes as the chain's wiring (each segment names only its successor, a
linked list built out of furniture), and why the belt is allowed to move a
crate you never gave it.

It reuses the `script_ticker` motor from the [flashlight](006_flashlight.md)
and the `container` tag from the [basic container](014_basic_container.md).

## How it works

The finished line is a row of containers, each carrying one attribute that
names where its cargo goes next, and each running the same short ticker. A
crate dropped on the first segment is relocated one segment onward every time
that segment ticks, until it reaches the end of the chain, which is a room, and
a crate in a room is simply on the floor. This section answers three questions:
what a segment is, what drives it, and why a belt may move cargo its builder
does not own.

### What is a belt segment?

Each belt is an ordinary thing tagged `container`, so `put crate in belt alpha`
is stock machinery, the same verbs the [basic container](014_basic_container.md)
switches on. Beyond the tag it holds one piece of data: `next_stop`, the `#id`
of wherever its cargo goes next. Chaining is nothing more than each segment
naming the next, and the last segment names a *room* instead of another belt.
That is how the line ends, because cargo moved into a room lands on its floor.
Extending the line is one new segment and one rewired attribute, and no other
segment knows it happened.

### What drives it?

The motor is the `script_ticker` behavior, the same heartbeat the
[flashlight](006_flashlight.md) drains its battery on. `@behavior belt alpha =
script_ticker, interval:1` runs the belt's
[`on_tick`](../reference/softcode.md#lifecycle-hooks) attribute on a cadence:
read `next_stop`, hand every piece of cargo one hop toward it with
[`move_to`](../reference/softcode.md#fn-move_to), and rattle audibly only if
something actually moved. The interval counts world beats, not seconds. A beat
is one `WORLD_TICK`, about four seconds by default, so `interval:1` fires once
per beat. Each time a belt ticks it hands whatever sits on it one segment
onward, so a crate travels the line segment by segment on the heartbeat instead
of jumping to the far end at once. Because a ticker fires only on the object it
is attached to, `me` inside `on_tick` is always this belt, so the script needs
no `target` guard of the kind a room-wide reaction hook does.

### Why may the belt move your crate?

[`move_to`](../reference/softcode.md#fn-move_to) relocates an object only for
someone with relocation authority over it, and that authority is granted two
ways: you own the object, or you own the place it stands. A crate on the belt
stands *inside* the belt, and the belt controls its own interior, so the belt
may move it onward no matter who created it. Whoever made the crate, once it is
on the belt, it rides. `move_to` still honors the destination's wards and
locks, so a warded room can refuse freight; passing `force=True`, which is what
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj) does, shoves cargo
past wards (though never past locks) for a belt nothing can jam.

## Build it

Segment alpha lives in the workshop. Create it, tag it a `container` so the
stock `put` and `get` verbs work, and drop it so it rests on the floor rather
than in your hands:

```text
@create belt alpha
@tag belt alpha = container
drop belt alpha
```

The motor's script is a `'''` multi-line block (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)).
Its steps in order: read the destination once with
[`V`](../reference/softcode.md#fn-v), snapshot the cargo with
[`contents`](../reference/softcode.md#fn-contents), move each piece one hop
toward `next_stop`, then rattle the belt's room with
[`remit`](../reference/softcode.md#fn-remit) to
[`loc(me)`](../reference/softcode.md#fn-loc), but only if it was carrying
anything:

```text
@set belt alpha/on_tick = '''
dest = V('next_stop')  # a belt #id, or the dock room at the end of the line
cargo = contents(me)
for o in cargo:
    move_to(o, dest)  # the belt controls its own interior, so it may relocate its cargo
if cargo:
    remit(loc(me), 'The belt clatters; the cargo slides out of sight.')
'''
```

Attach the ticker that runs that script. `interval:1` fires `on_tick` every
world beat, so cargo hops once each heartbeat:

```text
@behavior belt alpha = script_ticker, interval:1
```

Dig down the line and lay segment beta one room on. It is alpha again: create
it, tag it, drop it:

```text
@dig Packing Floor = downline, upline
downline
@create belt beta
@tag belt beta = container
drop belt beta
```

Give beta the identical motor and script, because a belt is a belt:

```text
@set belt beta/on_tick = '''
dest = V('next_stop')
cargo = contents(me)
for o in cargo:
    move_to(o, dest)
if cargo:
    remit(loc(me), 'The belt clatters; the cargo slides out of sight.')
'''
@behavior belt beta = script_ticker, interval:1
```

The line needs an end. Dig the loading dock one more room down; its floor is
where the freight finally lands:

```text
@dig Loading Dock = downline, upline
```

Wire the chain with [`set_attr`](../reference/softcode.md#fn-set_attr): alpha
feeds beta, and beta points at the Loading Dock room itself.
[`get`](../reference/softcode.md#fn-get) resolves each segment by name, and
`'#' + <id>` is the reference the tick reads back as `next_stop`:

```text
@eval a = get('belt alpha'); b = get('belt beta'); set_attr(a, 'next_stop', '#' + b.id); set_attr(b, 'next_stop', '#' + get('Loading Dock').id); result = 'belt line wired'
```

Walk back up the line to the workshop:

```text
upline
```

## Try it

Make a crate and set it on the first belt. On a live server the heartbeat
carries it from here; to watch a single hop on demand, force one beat with
`@tr belt alpha/on_tick`, which runs the bare `on_tick` code exactly as the
ticker would (the [flashlight](006_flashlight.md) covers what `@tr` can and
cannot fire):

```text
> @create crate of gears
  Created: crate of gears (#e9af9418)
> put crate of gears in belt alpha
  You put a crate of gears in the belt alpha.
> @tr belt alpha/on_tick
  The belt clatters; the cargo slides out of sight.
  Triggered belt alpha/on_tick.
```

The crate is gone from belt alpha; it landed on belt beta, one room down. Walk
after it, force beta's beat, and it slides onto the dock floor with nobody
holding it:

```text
> downline
  Packing Floor
> look belt beta
  belt beta
  Contains:
    crate of gears
> @tr belt beta/on_tick
  The belt clatters; the cargo slides out of sight.
  Triggered belt beta/on_tick.
> downline
  Loading Dock
  You see:
    a crate of gears
> get crate of gears
  You pick up a crate of gears.
```

An idle belt stays quiet: with nothing on it the `if cargo:` guard is false, so
a beat passes with no clatter. Ride two crates a beat apart and they arrive in
order, one behind the other, for as long as the motors run, until someone
detaches a belt's `script_ticker` with `@behavior/remove` or halts the whole
line with `@tag belt alpha = halt`.

## Going further

- **A return loop:** point the dock's own belt back at alpha and the line
  becomes a circle, which is all a luggage carousel is.
- **Sorting by cargo:** make the tick choose `next_stop` per item with
  [`has_tag`](../reference/softcode.md#fn-has_tag), for example
  `V('next_' + ('cold' if has_tag(o, 'perishable') else 'dry'))`, and the belt
  becomes a router; the [refrigerator](018_refrigerator.md)'s peaches would take
  the cold branch.
- **A slower line:** `interval:8` moves cargo about every thirty seconds, and
  `@behavior/set belt alpha = script_ticker, interval:8` retunes a running line
  without touching the script.
- **Passengers:** the tick moves *everything* inside a segment, so gate it with
  `if not has_tag(o, 'player')` to keep people off, or leave it open and the
  belt is also a ride, like the [climbing exit](034_climbing_exit.md) for
  anyone with no legs to climb.
