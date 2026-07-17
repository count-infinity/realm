# 189. In-room minimap

> Checklist item 189 — [now] — *ON_LOOK, exits() BFS, ASCII render*

**What you'll build:** a compact ASCII map of the rooms immediately
around you, painted under the room description every time you look — a
`@` for where you stand, an initial for each neighbour out to two steps.

**Concepts:** the `ON_LOOK` hook on a room, a **breadth-first walk** over
the `exits()` graph unrolled into two comprehension "waves", coordinate
layout, and `eval_attr()` as a subroutine so the hook stays one line.

## How it works

Looking at a room propagates an `event:look` whose target is the room
itself, so the room's **`ON_LOOK`** attribute fires with `enactor` bound
to the looker. That is a script on the *worker* stack — unlike a
`[[...]]` description block it can walk to neighbouring rooms and read
their exits without tripping the inline render-time limits (see
[036](036_weather_system.md) for why render-time blocks stay shallow).

The map is a BFS from `here`. REALM scripts favour **comprehensions over
statement loops** (a live `@set` is one line), so we unroll the search to
a fixed radius of two: *wave 1* is every cardinal neighbour of `here`;
*wave 2* is every cardinal neighbour of those. Each cell carries an
`[x, y]` offset from the centre, accumulated as we step; a direction
table turns an exit's name into that step. We drop the results into a
`"x,y" -> room` dict (closer waves written last so they win), then render
a 5x5 grid: `@` at the origin, the room's capitalised initial where a
cell is known, `.` everywhere else.

The heavy part lives in a **`render_map`** attribute and the hook just
calls it with `eval_attr(me, 'render_map')`. `eval_attr` is Penn's
`u()`: it runs the attribute as a function *with the caller's authority
and enactor intact*, so `render_map` still knows who looked, and its
`pemit(enactor, ...)` is delivered after the look like any other. Keeping
the renderer in its own attribute means you can rewrite the map style
without touching the hook.

The 174 auto-map (a whole-zone atlas) does the general case; this one
stays deliberately small — *nearby* rooms, on every look.

## Build it

Dig a little district around where you stand — four cardinal wings, plus
one room a second step to the north so wave 2 has something to find:

```text
@dig North Wing = north, south
@dig East Wing = east, west
@dig West Wing = west, east
@dig South Wing = south, north
north
@dig Observation Deck = north, south
south
```

The last two lines walk you north into North Wing to dig the Observation
Deck beyond it, then back south to the centre. Now the renderer. It reads
as a lot, but it is just the two waves, the merge, and the grid — one
attribute:

```text
@set here/render_map = dirs = {'north': [0, -1], 'south': [0, 1], 'east': [1, 0], 'west': [-1, 0]}; w1 = [[dirs[name(e)][0], dirs[name(e)][1], get('#' + str(get_attr(e, 'destination', '')))] for e in exits(me) if name(e) in dirs]; w1 = [c for c in w1 if c[2]]; w2 = [[c[0] + dirs[name(e)][0], c[1] + dirs[name(e)][1], get('#' + str(get_attr(e, 'destination', '')))] for c in w1 for e in exits(c[2]) if name(e) in dirs]; w2 = [c for c in w2 if c[2] and c[2].id != me.id]; seen = {f'{c[0]},{c[1]}': c[2] for c in (w2 + w1 + [[0, 0, me]])}; grid = ['  '.join(['@' if x == 0 and y == 0 else (capstr(left(name(seen[f'{x},{y}']), 1)) if f'{x},{y}' in seen else '.') for x in [-2, -1, 0, 1, 2]]) for y in [-2, -1, 0, 1, 2]]; pemit(enactor, ansi('ch', 'Nearby') + '\n' + '\n'.join(grid))
```

Reading it in pieces:

- `dirs` maps an exit *name* to its `[dx, dy]` step. Only these named
  exits count toward the grid; a `portal` or `ladder` is skipped, which
  is what keeps the picture legible.
- `w1` steps once from `me`; `w2` steps again from each `w1` room and
  drops any cell that lands back on the centre (`c[2].id != me.id`).
- `seen` is built from `w2 + w1 + [origin]` so nearer rooms (and the
  centre) overwrite farther ones at the same coordinate — dict literals
  keep the last write.
- `grid` walks `y` then `x` from `-2` to `2`; `left(..., 1)` takes a
  room's first letter and `capstr` upper-cases it; cells not in `seen`
  render as `.`.

Finally, hang it on the look:

```text
@set here/on_look = eval_attr(me, 'render_map')
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

`@` is you; `N`/`E`/`W`/`S` are the four wings; `O` is the Observation
Deck two steps north. Walk `east` and look again — the grid re-centres on
you, because `me` is always whatever room ran the hook. Add or dig
another exit and it appears next look; there is no map to maintain.

## Going further

- **Exploration memory:** stamp each visited room's id into a set keyed
  by the looker (`set_attr(me, 'seen_' + enactor.id, ...)`), and render
  `?` for a coordinate the viewer has not personally reached yet — fog of
  war, per player, no engine support required.
- **Wider view:** add `[2, 0]`-style diagonals to `dirs` and widen the
  grid range to `[-3..3]` for a 7x7; the two-wave shape is unchanged.
- **Corridors:** render `-` and `|` between cells that share an exit for
  a connected look, reading the same `seen` dict.
- **A `$map` verb:** the same `eval_attr(me, 'render_map')` behind a
  `$map` command-trigger gives players an on-demand recall without a full
  `look`.
