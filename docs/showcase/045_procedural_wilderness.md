# 045. Procedural wilderness

> Checklist item 45 ([now]): *wilderness regions, map-provider attrs, cell reaping*

**What you'll build:** A 21x21 procedural frontier from one region master
whose softcode derives terrain from coordinates, one gate exit into it, and
rooms that exist only while someone stands in them. Wilderness is native, so
you author the map function and the engine builds the rooms.

**Concepts:** `wilderness_region` masters; map-provider attributes
(`is_valid`, `cell_name`, `cell_desc`, `edge_msg`) written as softcode over
bound `x`/`y`; gate exits (`dest_resolver = wilderness`); shared ephemeral
cells and reaping; the [`enter_wilderness`](../reference/softcode.md#fn-enter_wilderness)
seam.

## How it works

The finished region is a single persistent object plus one doorway. You never
dig the wilderness rooms yourself: each cell is materialized the instant a
player walks toward it, from softcode you write once on the master. This
section explains what those attributes answer, why they must be deterministic,
and how a walker gets in and out.

### What the master answers

A wilderness region is a master object tagged `wilderness_region` whose name is
the region id. Its attributes are small softcode functions of a coordinate.
When someone walks toward `(x, y)`, the engine evaluates the relevant attribute
with `x` and `y` bound, and each returns its answer through `result`:

| attribute | answers | contract |
|---|---|---|
| `is_valid` | is `(x, y)` inside the map? | deterministic, the boundary |
| `cell_name` | the room name there | deterministic |
| `cell_desc` | the room description | deterministic |
| `cell_exits` | which directions open (optional; default N/S/E/W) | deterministic |
| `cell_populate` | prototypes to spawn (optional) | may be random |
| `edge_msg` | what walking off the map says | plain text, never evaluated |

### Why terrain must come from the coordinate

Cells are ephemeral. A materialized cell is a real room tagged
`wildcell:<region>:<x>,<y>` and `zone:wilderness:<region>`, shared by everyone
standing at that coordinate, and reaped once it has sat empty past the region's
idle TTL. Because a reaped cell must regrow identically when someone walks back,
`is_valid`, `cell_name`, and `cell_desc` derive terrain from `(x, y)` alone (the
`(x * 7 + y * 13) % 4` hash below), never from [`rand`](../reference/softcode.md#fn-rand).
The one exception is `cell_populate`: an encounter that re-rolls on every visit
is exactly what a random spawn table wants, and the reap-and-regrow cycle
re-rolls it for free.

### Getting in, moving around, and getting out

A gate is a normal exit with `dest_resolver = wilderness` plus a region name and
an entry coordinate, so walking it is an ordinary traversal, the same shape as
the instance portal in the [instanced room](044_instanced_room.md). Between
cells there is no softcode at all: each cell's directional exits are real exits
with deferred destinations, so walking north asks the movement kernel to
materialize the neighbor on demand, only after the origin-side locks and wards
have passed. Walking toward a coordinate where `is_valid` is false is a plain
dead-end, and the kernel prints your `edge_msg`. For a scripted entrance (a
waystone, a shipwreck, a teleport mishap),
[`enter_wilderness(player, region, x, y)`](../reference/softcode.md#fn-enter_wilderness)
runs the same machinery from any trigger.

## Build it

The region master is the whole map. Create it, tag it, and drop it so it lives
in the room rather than your hands:

```text
@create frontier
@tag frontier = wilderness_region
drop frontier
```

`is_valid` is the boundary, a single deterministic expression that returns true
for the 21x21 square and false everywhere else:

```text
@set frontier/is_valid = result = 0 <= x <= 20 and 0 <= y <= 20
```

The name and description are the flavor pair. Both classify the coordinate into
one of four terrains with the same hash, so a cell's name and description always
agree, and both regrow identically after a reap. Written as `'''` blocks
(see [multi-line input](../guides/world-management.md#multi-line-input-heredocs)),
the terrain index is named once and the selection reads plainly:

```text
@set frontier/cell_name = '''
terrain = (x * 7 + y * 13) % 4  # same coordinate always gives the same terrain, so a reaped cell regrows identically
if terrain == 0:
    result = 'Windswept Meadow'
elif terrain == 1:
    result = 'Pine Forest'
elif terrain == 2:
    result = 'Rocky Scree'
else:
    result = 'Creek Crossing'
'''

@set frontier/cell_desc = '''
terrain = (x * 7 + y * 13) % 4  # the same index the name uses, so the two never disagree
descs = ['Knee-high grass bends under a steady wind.', 'Pines crowd close, and the light falls in narrow blades.', 'Loose rock shifts underfoot between stubborn thistles.', 'A cold creek chatters over smooth stones.']
result = descs[terrain]
'''
```

`edge_msg` is plain text, not softcode: the engine copies it onto each cell's
compass exits as the dead-end message, so walking off the map reads it back:

```text
@set frontier/edge_msg = The frontier ends in an impassable wall of bramble.
```

The gate in sits at the map's center. It is an ordinary exit whose destination
is deferred to the `wilderness` resolver, with the region and entry coordinate
carried as attributes:

```text
@create trail gate
@tag trail gate = exit
drop trail gate
@set trail gate/dest_resolver = wilderness
@set trail gate/wild_region = frontier
@set trail gate/wild_x = 10
@set trail gate/wild_y = 10
```

And a scripted entrance, a corner-marker waystone. Typing its `$`-command is the
player's consent to be moved, so
[`enter_wilderness`](../reference/softcode.md#fn-enter_wilderness) may relocate
the enactor, and [`pemit`](../reference/softcode.md#fn-pemit) tells them where
they landed:

```text
@create corner waystone
drop corner waystone
@set corner waystone/cmd_touch = $touch waystone: enter_wilderness(enactor, 'frontier', 0, 0); pemit(enactor, 'The waystone drags the world sideways. You stand at the frontier corner-marker.')
```

## Try it

```text
trail gate
  Windswept Meadow          <- (10,10): the formula says meadow
north
  Pine Forest               <- (10,11) materialized as you walked
```

Bring a friend through the gate and they stand in your meadow, because cells are
shared, not instanced. Hop home (`@teleport me = The Workshop` is the builder's
shortcut; players reach home through an authored exit, see below), then take the
waystone to the corner and find the map's edge:

```text
touch waystone
  The waystone drags the world sideways. You stand at the frontier corner-marker.
south
  The frontier ends in an impassable wall of bramble.
west
  The frontier ends in an impassable wall of bramble.
```

`@examine here` in any cell shows the `ephemeral` and `wildcell:frontier:x,y`
tags. Walk away and the empty cells quietly reap; walk back and the same meadow
grows back from the same formula.

## Going further

- **A way home:** `cell_exits` can add an authored exit at the start
  coordinate. Return the compass directions plus a
  `{'name': 'trailhead', 'destination': '<room id>'}` entry only when
  `x == 10 and y == 10`, and see `examples/wilderness/` for the full worked
  region.
- **Terrain that matters:** add a `cell_terrain` attribute and let a
  hazard-style tick ([tutorial 043](043_hazard_room.md)) read it, so creek
  cells demand the swimming roll from [tutorial 039](039_underwater_room.md).
- **Encounters:** `cell_populate` returns spawn prototypes, so wolves prowl the
  forest cells (`examples/wilderness/frontier.py` spawns exactly this). The
  spawns are ephemeral like the cell, so nothing leaks.
- **Weather over the wilds:** cells are tagged `zone:wilderness:frontier`, so a
  weather master ([tutorial 036](036_weather_system.md)) can rain on whichever
  cells currently exist.
```