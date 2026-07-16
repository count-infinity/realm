# 045. Procedural wilderness

> Checklist item 45 — [now] — *wilderness regions, map-provider attrs, cell reaping*

**What you'll build:** A 21x21 procedural frontier: one region master
whose softcode derives terrain from coordinates, one gate exit into it
— and rooms that exist only while someone stands in them. Wilderness
is **native**; you author the *map function*, the engine does the
rooms.

**Concepts:** `wilderness_region` masters, map-provider attributes
(`is_valid`, `cell_name`, `cell_desc`, `edge_msg`) as softcode over
`x`/`y`, gate exits (`dest_resolver = wilderness`), shared ephemeral
cells and reaping, `enter_wilderness()`.

## How it works

A wilderness **region** is a master object tagged `wilderness_region`
whose attributes are little softcode functions of the coordinate. When
someone walks toward `(x, y)`, the engine asks the master:

| attribute | answers | contract |
|---|---|---|
| `is_valid` | is `(x, y)` inside the map? | **deterministic** — the boundary |
| `cell_name` | the room name there | deterministic |
| `cell_desc` | the room description | deterministic |
| `cell_exits` | which directions open (optional; default N/S/E/W) | deterministic |
| `cell_populate` | prototypes to spawn (optional) | *may* be random |
| `edge_msg` | what walking off the map says | plain text |

Each runs with `x` and `y` bound and returns via `result`. Determinism
matters because cells are **ephemeral**: a materialized cell is a real
room (tagged `wildcell:<region>:<x>,<y>` and `zone:wilderness:<region>`),
shared by everyone at that coordinate, reaped when it's sat empty —
and a reaped cell must re-materialize *identically* when someone walks
back. So derive terrain from the coordinate (`(x * 7 + y * 13) % 4`
below), never from `rand()` — except in `cell_populate`, where a random
encounter re-rolling per visit is exactly what you want.

Getting in: a **gate exit** with `dest_resolver = wilderness` plus a
region name and entry coordinate — a normal traversal, like the
instance portal ([tutorial 044](044_instanced_room.md)). Between
cells, no softcode at all: each cell's exits are real exits with
deferred destinations; walking north materializes the neighbor on
demand. Off the map, the walk fails with your `edge_msg`. And
`enter_wilderness(player, region, x, y)` is the scripted seam — a
waystone, a shipwreck, a teleport mishap.

## Build it

The region master — the whole map is five attributes:

```text
@create frontier
@tag frontier = wilderness_region
drop frontier
@set frontier/is_valid = result = 0 <= x <= 20 and 0 <= y <= 20
@set frontier/cell_name = result = ['Windswept Meadow', 'Pine Forest', 'Rocky Scree', 'Creek Crossing'][(x * 7 + y * 13) % 4]
@set frontier/cell_desc = result = ['Knee-high grass bends under a steady wind.', 'Pines crowd close, and the light falls in narrow blades.', 'Loose rock shifts underfoot between stubborn thistles.', 'A cold creek chatters over smooth stones.'][(x * 7 + y * 13) % 4]
@set frontier/edge_msg = The frontier ends in an impassable wall of bramble.
```

The gate in, at the map's center:

```text
@create trail gate
@tag trail gate = exit
drop trail gate
@set trail gate/dest_resolver = wilderness
@set trail gate/wild_region = frontier
@set trail gate/wild_x = 10
@set trail gate/wild_y = 10
```

And a scripted entrance — the corner-marker waystone (typing its
`$`-command is consent, so it may move you):

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

Bring a friend through the gate: they stand in *your* meadow — cells
are shared, not instanced. Hop home (`@teleport me = The Workshop` —
the builder's prerogative; players get an authored way back, see
below), then take the waystone to the corner and find the map's edge:

```text
touch waystone
  The waystone drags the world sideways. You stand at the frontier corner-marker.
south
  The frontier ends in an impassable wall of bramble.
west
  The frontier ends in an impassable wall of bramble.
```

`@examine here` in any cell shows the `ephemeral` and
`wildcell:frontier:x,y` tags. Walk away and the empty cells quietly
reap; walk back and the same meadow grows back from the same formula.

## Going further

- **A way home:** `cell_exits` can add an authored exit at the start
  coordinate — `result = ['north', 'south', 'east', 'west',
  {'name': 'trailhead', 'destination': '<room id>'}]` at `(10, 10)` —
  see `examples/wilderness/` for the full worked region.
- **Terrain that matters:** add a `cell_terrain` attr and let a
  hazard-style tick ([tutorial 043](043_hazard_room.md)) read it —
  creek cells that demand the swimming roll from
  [tutorial 039](039_underwater_room.md).
- **Encounters:** `cell_populate` returns spawn prototypes — wolves
  in forest cells (`examples/wilderness/frontier.py` rolls exactly
  this); they're ephemeral like the cell, so nothing leaks.
- **Weather over the wilds:** cells are tagged
  `zone:wilderness:frontier`, so a weather master
  ([tutorial 036](036_weather_system.md)) can rain on whichever cells
  currently exist.
