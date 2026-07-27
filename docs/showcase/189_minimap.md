# 189. In-room minimap

> Checklist item 189 ([now]): *ON_LOOK pemit, exits() BFS, ASCII grid render*

**What you'll build:** a compact ASCII map of the rooms immediately around
you, painted under the room description every time you look. An `@` marks where
you stand, and a room's initial marks each neighbour out to two steps.

**Concepts:** the [`ON_LOOK`](../reference/softcode.md#lifecycle-hooks) hook on a
room, a two-wave breadth-first walk over the
[`exits`](../reference/softcode.md#fn-exits) graph, coordinate layout, and
[`eval_attr`](../reference/softcode.md#fn-eval_attr) as a subroutine so the hook
stays one line.

## How it works

The finished minimap is a five-by-five block of characters printed beneath the
room description on every look: `@` at the centre for you, a room's capitalised
initial for each mapped neighbour, and `.` for empty ground. This section
answers three questions: how a look reaches the room's script, how that script
turns nearby exits into grid cells, and why the render lives in its own
attribute.

### How a look reaches the room

Looking at a room propagates an `event:look` whose target is the room itself
(see [the event model](../architecture/events.md) and the guided tour in
[245](245_event_bus_tour.md)), so the room's
[`ON_LOOK`](../reference/softcode.md#lifecycle-hooks) hook fires with
[`enactor`](../reference/softcode.md#event-data-namespace) bound to the looker.
That hook runs as a triggered script during look propagation, which finishes
before the description renders, so it is off the render call stack. Because of
that it is free to step out to neighbouring rooms and read their exits, whereas
a render-time `[[...]]` description block keeps to shallow local reads (see
[036](036_weather_system.md) for why render-time blocks stay shallow).

A look at any object in the room propagates through the room too, so the room's
`ON_LOOK` fires on those looks as well. The hook therefore guards with
`if target is me:` (see [Guard on
`target`](../reference/softcode.md#guard-on-target)) so the map paints only on a
look at the room, not when you look at, say, a crate standing in it.

### How the script turns exits into a grid

The map is a breadth-first walk from where you stand, unrolled to a fixed radius
of two: *wave 1* is every cardinal neighbour of the centre, and *wave 2* is
every cardinal neighbour of those. A `dirs` table turns an exit's
[`name`](../reference/softcode.md#fn-name) into an `[dx, dy]` step, and each cell
carries the running offset from the centre. Only exits named `north`, `south`,
`east`, or `west` count, so a `portal` or `ladder` is skipped, which keeps the
picture legible.

Each wave reads a room's open exits with `exits`, takes the exit's destination
id from its `destination` attribute with
[`get_attr`](../reference/softcode.md#fn-get_attr), and resolves that id to a
room with [`get`](../reference/softcode.md#fn-get). Wave 2 also drops any cell
that steps back onto the centre. The cells drop into a `"x,y" -> room` dict built
from `w2 + w1 + [origin]`, so nearer rooms and the centre are written last and
win at a shared coordinate, since a dict literal keeps the last write. The grid
then walks `y` then `x` from `-2` to `2`:
[`left`](../reference/softcode.md#fn-left) takes a room's first letter,
[`capstr`](../reference/softcode.md#fn-capstr) upper-cases it,
[`ansi`](../reference/softcode.md#fn-ansi) colours the heading, and
[`pemit`](../reference/softcode.md#fn-pemit) sends the block to the looker after
the look.

### Why the renderer lives in its own attribute

The walk is the heavy part, so it lives in a `render_map` attribute and the hook
just calls it with `eval_attr(me, 'render_map')`. `eval_attr` runs the attribute
as a subroutine of the caller: the executor and `enactor` are left unchanged, so
`me` inside `render_map` is still the room that ran the hook and `render_map`
still knows who looked. (It is not Penn's `u()`, which swaps the executor to the
attribute's owner and can escalate; this call runs as the caller and cannot.)
Keeping the renderer in its own attribute means you can rewrite the map style
without touching the hook.

The [174 auto-map](174_auto_map.md) draws a whole zone on demand; this one stays
deliberately small, showing nearby rooms on every look.

## Build it

Dig a little district around where you stand: four cardinal wings, plus one room
a second step north so wave 2 has something to find.

```text
@dig North Wing = north, south
@dig East Wing = east, west
@dig West Wing = west, east
@dig South Wing = south, north
north
@dig Observation Deck = north, south
south
```

The last two lines walk you north into North Wing to dig the Observation Deck
beyond it, then step back south to the centre.

Now the renderer. It reads as a lot, but it is just the two waves, the merge,
and the grid. It stays on a single line so the hook can call it as a subroutine,
and because it reads the live exit list there is nothing to keep in sync:

```text
@set here/render_map = dirs = {'north': [0, -1], 'south': [0, 1], 'east': [1, 0], 'west': [-1, 0]}; w1 = [[dirs[name(e)][0], dirs[name(e)][1], get('#' + str(get_attr(e, 'destination', '')))] for e in exits(me) if name(e) in dirs]; w1 = [c for c in w1 if c[2]]; w2 = [[c[0] + dirs[name(e)][0], c[1] + dirs[name(e)][1], get('#' + str(get_attr(e, 'destination', '')))] for c in w1 for e in exits(c[2]) if name(e) in dirs]; w2 = [c for c in w2 if c[2] and c[2].id != me.id]; seen = {f'{c[0]},{c[1]}': c[2] for c in (w2 + w1 + [[0, 0, me]])}; grid = ['  '.join(['@' if x == 0 and y == 0 else (capstr(left(name(seen[f'{x},{y}']), 1)) if f'{x},{y}' in seen else '.') for x in [-2, -1, 0, 1, 2]]) for y in [-2, -1, 0, 1, 2]]; pemit(enactor, ansi('ch', 'Nearby') + '\n' + '\n'.join(grid))
```

Reading it in pieces:

- `dirs` maps an exit *name* to its `[dx, dy]` step. Only these four named exits
  count toward the grid, so a `portal` or `ladder` is skipped, which is what
  keeps the picture legible.
- `w1` steps once from `me`; `w2` steps again from each `w1` room and drops any
  cell that lands back on the centre (`c[2].id != me.id`).
- `seen` is built from `w2 + w1 + [origin]` so nearer rooms and the centre
  overwrite farther ones at the same coordinate, because a dict literal keeps the
  last write.
- `grid` walks `y` then `x` from `-2` to `2`; `left(..., 1)` takes a room's first
  letter, `capstr` upper-cases it, and a cell not in `seen` renders as `.`.

Finally, hang it on the look. The hook fires for every look that passes through
the room, so it guards with `if target is me:` to paint only when you look at the
room itself, not when you look at an object standing in it:

```text
@set here/on_look = if target is me: eval_attr(me, 'render_map')
```

## Try it

```text
> look
The Workshop
...
Nearby
.  .  O  .  .
.  .  N  .  .
.  W  @  E  .
.  .  S  .  .
.  .  .  .  .
```

`@` is you; `N`, `E`, `W`, and `S` are the four wings; `O` is the Observation
Deck two steps north. The renderer keys off `me`, the room that ran the hook, so
the same two attributes dropped in another room re-centre the map there: set
`render_map` and `on_look` on the East Wing and a look there maps from the East
Wing, with The Workshop (initial `T`) now one cell west of `@`. Add or dig
another exit and it shows up on the next look, because `render_map` reads the
live exit list each time; there is no map to maintain.

## Going further

- **Exploration memory:** stamp each visited room's id into a set keyed by the
  looker (`set_attr(me, 'seen_' + enactor.id, ...)`), and render `?` for a
  coordinate the viewer has not personally reached yet, giving per-player fog of
  war with no engine support required.
- **Wider view:** add diagonals to `dirs` and widen the grid range to `[-3..3]`
  for a 7x7; the two-wave shape is unchanged.
- **Corridors:** render `-` and `|` between cells that share an exit for a
  connected look, reading the same `seen` dict.
- **A `$map` verb:** the same `eval_attr(me, 'render_map')` behind a `$map`
  command-trigger gives players an on-demand recall without a full `look`.
```
