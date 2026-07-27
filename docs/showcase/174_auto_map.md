# 174. Auto-map generator

> Checklist item 174 ([now]): *exits() graph traversal, ASCII grid render, unmappable-link handling*

**What you'll build:** a `map <zone>` command that draws an ASCII map of a
zone. It assigns grid coordinates by following compass exits out from where you
stand, renders the rooms into a grid, and names the links it leaves off (stairs,
portals, oddly-named exits). A builder lays the zone out with the OLC commands,
while the `map` verb itself is a plain `$`-command that any onlooker standing by
the cartographer can run.

**Concepts:** a coordinate flood over the [`exits`](../reference/softcode.md#fn-exits)
graph, compass directions as coordinate deltas, an ASCII grid render, and honest
unmappable-link reporting.

## How it works

The cartographer is one object you drop in a zone. Typing `map <zone>` walks the
zone's rooms by their compass exits, assigns each a grid coordinate relative to
where you stand, prints a small ASCII grid of two-letter room abbreviations, and
names any exit that has no place on flat compass paper. This section answers four
questions: how a room earns a coordinate, how those coordinates spread across the
whole zone, why some rooms are left off, and how the map cleans up after itself.

### How a room earns a coordinate

Each compass direction is a step on a 2-D grid: north is `[0, 1]`, south is
`[0, -1]`, east is `[1, 0]`, west is `[-1, 0]`. Anchor the room you stand in at
`[0, 0]`, and every other room's coordinate is the running sum of the steps that
reach it. The `dirs` dict holds those four deltas, and the map keys on exit
names, so only exits literally named `north`, `south`, `east`, or `west` move
the pen.

### How the coordinates spread across the zone

The map parks each room's coordinate in a `coord_<id>` attribute on the
cartographer itself, written with [`set_attr`](../reference/softcode.md#fn-set_attr)
and read back with [`V`](../reference/softcode.md#fn-v), which reads an attribute
off `me` (the cartographer). Rather than manage a frontier queue by hand, the
command floods by relaxation: one pass looks at every room that already holds a
coordinate and hands each of its compass-neighbors a coordinate, and that pass
repeats `len(rooms)` times. That many passes exceeds any zone's diameter, so the
coordinates propagate all the way out. [`exits`](../reference/softcode.md#fn-exits)
lists a room's open exits, [`name`](../reference/softcode.md#fn-name) reads an
exit's direction word, and the exit's destination room id lives in its
`destination` attribute, which [`get_attr`](../reference/softcode.md#fn-get_attr)
reads and [`get`](../reference/softcode.md#fn-get) resolves into the room object.

The sandbox permits list and dict mutation (`append`, `pop`, and item
assignment) inside a `'''` script, so a textbook queue-based BFS is equally
writable here. The relaxation flood is chosen because it keeps every coordinate
in an inspectable attribute and expresses the traversal as plain nested loops;
the queue form appears under "Going further".

### Why some rooms are left off

A zone is not a flat grid. `up`, `down`, a named `portal`, or a one-way `slide`
have no place on 2-D compass paper, so a room reachable only through such a link
never receives a coordinate. The render reports what it did place ("4/5 rooms"),
and a separate line names every non-compass exit as `room/exit`, so nothing
vanishes silently.

### Rendering and cleanup

From the placed coordinates the command finds the bounding box (the smallest and
largest x and y), then walks the grid top to bottom (y descending) and left to
right (x ascending). Each cell prints a two-letter abbreviation from
[`left`](../reference/softcode.md#fn-left) for the room that sits there, or four
spaces for an empty cell. Afterward it deletes every `coord_<id>` attribute with
[`del_attr`](../reference/softcode.md#fn-del_attr), because the map is a view
rather than stored state.

## Build it

First lay out a small zone with a compass core and one non-compass link, a
cellar reached by `down`. These OLC commands (`@dig`, `@zone`) require the
builder role:

```text
@dig Keep Hub = enter, leave
enter
@zone here = keep
@dig East Wing = east, west
east
@zone here = keep
@dig Watchtower = north, south
north
@zone here = keep
south
west
@dig North Hall = north, south
north
@zone here = keep
south
@dig Cellar = down, up
down
@zone here = keep
up
```

Create the cartographer and drop it in the room, so its `$map` verb is present
to anyone standing there:

```text
@create cartographer
drop cartographer
```

Now the verb. It reads the zone name with
[`trim`](../reference/softcode.md#fn-trim), gathers the zone's rooms with
[`zone_rooms`](../reference/softcode.md#fn-zone_rooms), floods coordinates over
the compass exits, prints the grid and the unmappable list with
[`pemit`](../reference/softcode.md#fn-pemit), and wipes its scratch. It is a
script with control flow, so it is a `'''` heredoc block (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)).
`$map` is a `$`-command, which dispatches only for the object it is typed at, so
it needs no `target` guard the way a room-wide
[`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks) hook would (see
[Guard on `target`](../reference/softcode.md#guard-on-target)):

```text
@set cartographer/cmd_map = '''
$map *:
z = trim(arg0)
rooms = zone_rooms(z)
dirs = {'north': [0, 1], 'south': [0, -1], 'east': [1, 0], 'west': [-1, 0]}
# Start clean, then anchor the room you stand in at the origin.
for r in rooms:
    del_attr(me, 'coord_' + r.id)
set_attr(me, 'coord_' + here.id, [0, 0])
# Relaxation flood: len(rooms) passes exceed any zone's diameter, so
# coordinates propagate fully. Each coordinate is parked on the cartographer.
for step in range(len(rooms)):
    for s in rooms:
        base = V('coord_' + s.id)
        if base is None:
            continue
        for e in exits(s):
            nm = name(e).lower()
            if nm not in dirs:
                continue
            d = get('#' + str(get_attr(e, 'destination', '')))
            if d is not None and V('coord_' + d.id) is None:
                set_attr(me, 'coord_' + d.id, [base[0] + dirs[nm][0], base[1] + dirs[nm][1]])
placed = [r for r in rooms if V('coord_' + r.id) is not None]
xs = [V('coord_' + r.id)[0] for r in placed]
ys = [V('coord_' + r.id)[1] for r in placed]
pemit(enactor, f'Map of {z} ({len(placed)}/{len(rooms)} rooms placed):')
# Top to bottom (y descending), left to right (x ascending), one cell per point.
for y in range(max(ys), min(ys) - 1, -1):
    row = ''
    for x in range(min(xs), max(xs) + 1):
        cell = [r for r in placed if V('coord_' + r.id) == [x, y]]
        row = row + ('[' + left(name(cell[0]), 2) + ']' if cell else '    ')
    pemit(enactor, row)
unmap = [f'{name(s)}/{name(e)}' for s in rooms for e in exits(s) if name(e).lower() not in dirs]
pemit(enactor, 'Unmappable links: ' + (', '.join(unmap) if unmap else 'none'))
# The map is a view, not state, so wipe the scratch coordinates.
for r in rooms:
    del_attr(me, 'coord_' + r.id)
'''
```

## Try it

Stand in the hub so it anchors the origin, then map:

```text
> enter
> map keep
  Map of keep (4/5 rooms placed):
  [No][Wa]
  [Ke][Ea]
  Unmappable links: Keep Hub/leave, Keep Hub/down, Cellar/up
```

North Hall and the Watchtower sit above the Hub and East Wing. The Cellar,
reachable only by `down`, has no compass path from the origin, so it stays off
the grid and its links are named instead. The scratch `coord_*` attributes are
gone (`@examine cartographer` shows none), so the map left no state behind.

## Going further

- **Draw the doors:** between horizontally-adjacent placed rooms, print `-`
  where a compass exit connects them and `|` for a vertical connection, a richer
  grid than solid cells.
- **You-are-here:** mark the viewer's current room specially (`@` in place of
  the abbreviation) by comparing `r is here`.
- **Wider graphs:** raise the two-letter abbreviation to three, or key a legend
  of numbers to full room names beneath the grid, for when names collide.
- **A queue-based BFS:** because the sandbox allows `append` and `pop`, the flood
  rewrites as a textbook breadth-first search: seed a `frontier = [here]`, then
  `while frontier:` pop a room, and for each unvisited compass-neighbor set its
  coordinate and append it. That visits each room once instead of running
  `len(rooms)` full passes.
- **Map the dungeon:** point it at the [random dungeon](167_random_dungeon.md)'s
  `dungeon:run` set (swap `zone_rooms(z)` for
  [`search_world(tag='dungeon:run')`](../reference/softcode.md#fn-search_world))
  to draw a layout you just generated.