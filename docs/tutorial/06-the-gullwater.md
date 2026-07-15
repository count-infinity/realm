# Part 6 — The Gullwater

Act II. The banshee is dead and the lamp is lit, but the ferryman
still won't row — not until someone brings back the keeper's chart
from the supply ship that never made harbor. Between the isle and the
mainland lies the Gullwater. It doesn't exist yet, and mostly never
will: a **wilderness region** materializes its rooms when someone
walks in and evaporates them a couple of minutes after the last player
leaves. A whole sea costs nothing until it's sailed.

## A region is one object

```text
@create gullwater
@tag gullwater = wilderness_region
@set gullwater/is_valid = result = 0 <= x <= 6 and 0 <= y <= 6
@set gullwater/cell_name = result = 'Open Water'
@set gullwater/cell_desc = result = 'Grey swells roll to the horizon. The Gullwing light burns small behind you.'
@set gullwater/cell_terrain = result = 'water'
@set gullwater/edge_msg = The swells grow too steep to row.
```

Those attributes are the **map-provider**: softcode evaluated per
coordinate, with `x` and `y` bound. `is_valid` draws the map's edge (a
7×7 sea); walking past it shows `edge_msg` and nothing is created.
One rule matters: `is_valid` (and `cell_exits`, below) must be *pure
functions of x and y* — cells are reaped and rebuilt constantly, and
a coin-flip there would redraw your geography behind your back.

## The gate

First, note your Jetty's id — you'll need it twice in this act:

```text
@eval result = here.id
```

An exit is just a tagged object. This one has no destination — the
engine materializes one when it's walked:

```text
@create sea
@tag sea = exit
drop sea
@set sea/dest_resolver = wilderness
@set sea/wild_region = gullwater
@set sea/wild_x = 0
@set sea/wild_y = 0
```

## The way home

The provider decides each cell's exits too. Give the entry coordinate
a way back (paste your Jetty id over `JETTY`):

```text
@set gullwater/cell_exits = result = ['north', 'south', 'east', 'west'] + ([{'name': 'jetty', 'destination': 'JETTY', 'aliases': ['out']}] if x == 0 and y == 0 else [])
```

## Checkpoint

Type `sea`. You're standing on Open Water — a real room that didn't
exist a second ago. Walk `north`, `east`, `look` around; every cell
is distinct (its own light, its own future fights). Walk back to
where you entered and `jetty` brings you home. Yes, you're walking on
water. Part 8 makes the sea object to that.

!!! info "Learn more"
    Cells are *real rooms* — combat, stealth, and speech are scoped
    per cell, which is why the engine materializes rooms instead of
    faking coordinates with descriptions. Empty cells reap after
    ~2 minutes (`@set gullwater/idle_ttl = 120` to tune). The full
    spec: docs/design/wilderness-requirements.md.
