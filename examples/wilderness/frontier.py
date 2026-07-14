"""
Frontier — a demo wilderness region (docs/design/wilderness-requirements.md).

A 21x21 procedural frontier: a persistent trailhead room with a gate exit
into the region at (10, 10), a region master whose softcode map-provider
derives terrain deterministically from the coordinate (no ``rand()`` — a
reaped cell must re-materialize identically), and an authored exit back to
the trailhead at the start coordinate.

The provider embeds the trailhead's object id in ``cell_exits`` softcode,
so the exported area must be imported with ``preserve_ids=True`` (the
canonical first-boot path) — id remapping does not rewrite softcode.
"""

from __future__ import annotations

IS_VALID = "result = 0 <= x <= 20 and 0 <= y <= 20"

CELL_NAME = (
    "kinds = ['Windswept Meadow', 'Pine Forest', 'Rocky Scree',"
    " 'Creek Crossing']\n"
    "result = kinds[(x * 7 + y * 13) % 4]"
)

CELL_DESC = (
    "descs = ["
    "'Knee-high grass bends under a steady wind.', "
    "'Pines crowd close; the light falls in narrow blades.', "
    "'Loose rock shifts underfoot between stubborn thistles.', "
    "'A cold creek chatters over smooth stones.']\n"
    "result = descs[(x * 7 + y * 13) % 4]"
    " + ' [' + str(x) + ', ' + str(y) + ']'"
)

CELL_TERRAIN = (
    "result = ['meadow', 'forest', 'rocks', 'creek'][(x * 7 + y * 13) % 4]"
)

EDGE_MSG = "The frontier ends in an impassable wall of bramble."

# Pine-forest cells shelter a wolf (deterministic here; a real game
# would roll an encounter table — cell_populate MAY be random, unlike
# is_valid/cell_exits). Passive by default: give it the 'aggressive'
# behavior for real teeth.
CELL_POPULATE = (
    "wolf = {'name': 'a frontier wolf',"
    " 'description': 'Lean and gray, watching from the treeline.',"
    " 'tags': ['npc'],"
    " 'attrs': {'hp': 8, 'max_hp': 8, 'skill_melee': 10}}\n"
    "result = [wolf] if (x * 7 + y * 13) % 4 == 1 else []"
)


def cell_exits_code(trailhead_id: str) -> str:
    """The open directions — plus, at the start coordinate, the authored
    exit back to the persistent world (R5)."""
    return (
        "exits = ['north', 'south', 'east', 'west']\n"
        "if x == 10 and y == 10:\n"
        "    exits = exits + [{'name': 'trailhead',"
        f" 'destination': '{trailhead_id}', 'aliases': ['out']}}]\n"
        "result = exits"
    )


async def create_frontier(repo) -> dict:
    """Build the frontier's persistent seam: trailhead room, region
    master, gate exit. Cells are never built here — they materialize when
    someone walks."""
    from realm.core.objects import GameObject

    trailhead = GameObject(
        name="Frontier Trailhead",
        description=(
            "A weathered signpost marks where the road gives out. Beyond "
            "the gate, open frontier rolls to the horizon."),
        tags=["room", "start_room"],
    )
    await repo.save(trailhead)

    master = GameObject(name="frontier", tags=["wilderness_region"])
    master.db.set("is_valid", IS_VALID)
    master.db.set("cell_name", CELL_NAME)
    master.db.set("cell_desc", CELL_DESC)
    master.db.set("cell_terrain", CELL_TERRAIN)
    master.db.set("cell_exits", cell_exits_code(trailhead.id))
    master.db.set("cell_populate", CELL_POPULATE)
    master.db.set("edge_msg", EDGE_MSG)
    master.db.set("start_coord", [10, 10])
    await repo.save(master)

    gate = GameObject(name="gate", tags=["exit"])
    gate.db.set("aliases", ["frontier", "g"])
    gate.db.set("dest_resolver", "wilderness")
    gate.db.set("wild_region", "frontier")
    gate.db.set("wild_x", 10)
    gate.db.set("wild_y", 10)
    gate.location = trailhead
    await repo.save(gate)

    return {"trailhead": trailhead, "master": master, "gate": gate}
