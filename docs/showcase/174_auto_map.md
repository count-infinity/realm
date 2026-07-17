# 174. Auto-map generator

> Checklist item 174 — [now] — *coordinate flood over exits(), ASCII grid render, unmappable-link handling*

**What you'll build:** a `map <zone>` command that draws an ASCII map of a
zone — it assigns grid coordinates by following compass exits out from
where you stand, renders the rooms into a grid, and lists the links it
*couldn't* place (stairs, portals, oddly-named exits). (Builder
permission: the cartographer is a builder tool.)

**Concepts:** a coordinate **flood** over the `exits()` graph (BFS's
job, done with relaxation passes so it fits softcode's comprehension
idiom), compass directions as coordinate deltas, an ASCII grid render,
and honest **unmappable-link** reporting.

## How it works

**Compass exits are coordinate deltas.** north is `(0, +1)`, east is
`(+1, 0)`, and so on. Anchor the room you're standing in at `(0, 0)` and
every other room's coordinate is just the sum of the steps to reach it.

**Flood instead of a hand-rolled BFS.** A textbook BFS pushes and pops a
frontier queue — but softcode has no clean in-comprehension queue
mutation (assignment isn't allowed inside a comprehension, and the
sandbox blocks the dunder methods you'd reach for). So we flood by
**relaxation**: store each room's coordinate in a `coord_<id>` attribute
on the cartographer, and repeat "for every known room, give its
compass-neighbors their coordinate" `len(rooms)` times — more than the
graph's diameter, so it fully propagates. The nested comprehension
`[[ ...propagate... ] for step in range(len(rooms))]` is the whole
traversal; `set_attr`/`get_attr` are the sanctioned mutation the sandbox
allows.

**Unmappable links are reported, not dropped.** A zone isn't a flat grid:
`up`/`down`, a named `portal`, a one-way `slide` have no place on 2-D
compass paper. Rooms reachable *only* through such links never get a
coordinate — so the render shows what it *can* place ("4/5 rooms"), and a
separate line names every non-compass exit so nothing vanishes silently.

**Render, then clean up.** From the placed coordinates: find the bounding
box, and for each grid cell print a two-letter room abbreviation or
blank. Afterward, delete the `coord_<id>` scratch attributes — the map is
a view, not state.

## Build it

A small zone with a compass core and one non-compass link (a cellar
reached by `down`):

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

The cartographer. It floods coordinates from where you stand, renders the
grid top-to-bottom, lists unmappable links, and wipes its scratch:

```text
@create cartographer
drop cartographer
@set cartographer/cmd_map = $map *: z = trim(arg0); rooms = zone_rooms(z); dirs = {'north': [0, 1], 'south': [0, -1], 'east': [1, 0], 'west': [-1, 0]}; [del_attr(me, 'coord_' + r.id) for r in rooms]; set_attr(me, 'coord_' + here.id, [0, 0]); [[set_attr(me, 'coord_' + d.id, [V('coord_' + s.id)[0] + dirs[nm][0], V('coord_' + s.id)[1] + dirs[nm][1]]) for s in rooms for e in exits(s) for nm in [name(e).lower()] if nm in dirs for d in [get('#' + str(get_attr(e, 'destination', '')))] if d is not None and V('coord_' + s.id) is not None and V('coord_' + d.id) is None] for step in range(len(rooms))]; placed = [r for r in rooms if V('coord_' + r.id) is not None]; xs = [V('coord_' + r.id)[0] for r in placed]; ys = [V('coord_' + r.id)[1] for r in placed]; pemit(enactor, f'Map of {z} ({len(placed)}/{len(rooms)} rooms placed):'); [pemit(enactor, ''.join(['[' + left(name([r for r in placed if V('coord_' + r.id) == [x, y]][0]), 2) + ']' if [r for r in placed if V('coord_' + r.id) == [x, y]] else '    ' for x in range(min(xs), max(xs) + 1)])) for y in range(max(ys), min(ys) - 1, -1)]; unmap = [f'{name(s)}/{name(e)}' for s in rooms for e in exits(s) if name(e).lower() not in dirs]; pemit(enactor, 'Unmappable links: ' + (', '.join(unmap) if unmap else 'none')); [del_attr(me, 'coord_' + r.id) for r in rooms]
```

## Try it

Stand in the hub so it anchors the origin, then map:

```text
enter
map keep
  Map of keep (4/5 rooms placed):
  [No][Wa]
  [Ke][Ea]
  Unmappable links: Keep Hub/leave, Keep Hub/down, Cellar/up
```

North Hall and the Watchtower sit above the Hub and East Wing; the Cellar
— reachable only by `down` — can't be placed, so it's left off the grid
and its links are named instead. The scratch `coord_*` attributes are
gone (`@examine cartographer` is clean) — the map didn't leave state
behind.

## Engine gaps

- Softcode has no in-comprehension collection mutation (no assignment in
  comprehensions; the sandbox blocks `__setitem__` and friends), so the
  BFS is expressed as `len(rooms)` relaxation passes with coordinates
  parked in object attributes. It's O(rooms × edges × passes) — fine for
  command-frequency use on human-sized zones, heavier than a native BFS
  would be.

## Going further

- **Draw the doors:** between horizontally-adjacent placed rooms, print
  `-` where a compass exit connects them, `|` for vertical — a richer
  grid than solid cells.
- **You-are-here:** mark the viewer's current room specially (`@` instead
  of the abbreviation) by comparing `r is here`.
- **Wider graphs:** raise the two-letter abbreviation to three, or key a
  legend of numbers to full room names beneath the grid, when names
  collide.
- **Map the dungeon:** point it at the [random dungeon](167_random_dungeon.md)'s
  `dungeon:run` set (swap `zone_rooms(z)` for `search_world(tag=...)`) to
  draw a layout you just generated.
