"""
Tutorial Act II ("Across the Gullwater") — every mechanic the tutorial
teaches, driven end-to-end exactly as a builder would type it: an ocean
wilderness region authored via attrs, a boat as a vehicle ($board /
$row softcode), drowning built from primitives (a cell_populate
undertow), and a landmark instance portal into a sunken wreck.

If this file is green, the tutorial's typed lines work.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from realm.core import instances, wilderness
from realm.testing import Simulator

IS_VALID = "result = 0 <= x <= 6 and 0 <= y <= 6"
CELL_NAME = "result = 'Open Water'"
CELL_DESC = "result = 'Grey swells roll to the horizon.'"
EDGE_MSG = "The swells grow too steep to row."

# Single-line softcode, verbatim what the tutorial has the builder type
# (a client sends one line). The undertow checks only DIRECT cell
# contents — players aboard the boat are inside the boat, not the cell.
UNDERTOW_TICK = (
    "[(damage(p, 2), pemit(p, 'You slip under, choking on brine!'))"
    " if not skill_check(p, 'swimming')"
    " else pemit(p, 'You fight the swell and tread water.')"
    " for p in contents(here) if has_tag(p, 'player')]"
)

CELL_POPULATE = (
    "undertow = {'name': 'the undertow', 'tags': ['hazard'],"
    " 'attrs': {'on_tick': " + repr(UNDERTOW_TICK) + "},"
    " 'behaviors': [{'behavior_id': 'script_ticker',"
    " 'params': {'interval': 8}}]}; "
    "result = [undertow]"
)


def cell_exits_code(jetty_id: str) -> str:
    """The tutorial's final cell_exits line: 4-way compass everywhere,
    the jetty back-exit at the start coordinate, and at the landmark
    (3, 3) a portal down into the shared 'wreck' instance."""
    return (
        "result = ['north', 'south', 'east', 'west']"
        f" + ([{{'name': 'jetty', 'destination': '{jetty_id}',"
        " 'aliases': ['out']}] if x == 0 and y == 0 else [])"
        " + ([{'name': 'wreck', 'attrs':"
        " {'dest_resolver': 'instance', 'instance_template': 'wreck',"
        f" 'instance_mode': 'shared', 'instance_return': '{jetty_id}'"
        "}}] if x == 3 and y == 3 else [])"
    )


@pytest.fixture
def world():
    sim = Simulator()
    wilderness.reset()
    jetty = sim.room("The Jetty")
    jetty.add_tag("start_room")

    # The sunken wreck — an authored template zone (Act II part 9),
    # with an authored exit back out to the persistent world.
    hold = sim.room("The Flooded Hold")
    hold.add_tag("zone:wreck")
    hold.add_tag("instance_template")
    hold.add_tag("instance_entry")
    surface = sim.obj("surface", location=hold, tags=["exit"])
    surface.db.set("destination", jetty.id)

    # The ocean region, authored exactly as the tutorial does with @set.
    sea = sim.obj("gullwater", tags=["wilderness_region"])
    sea.db.set("is_valid", IS_VALID)
    sea.db.set("cell_name", CELL_NAME)
    sea.db.set("cell_desc", CELL_DESC)
    sea.db.set("cell_terrain", "result = 'water'")
    sea.db.set("cell_populate", CELL_POPULATE)
    sea.db.set("cell_exits", cell_exits_code(jetty.id))
    sea.db.set("edge_msg", EDGE_MSG)
    sea.db.set("idle_ttl", 120)

    # The ferry: a boat you board and row (Act II part 7).
    ferry = sim.obj("the ferry", location=jetty)
    ferry.db.set("cmd_board", "$board:move_to(enactor, me)")
    ferry.db.set("cmd_row", "$row *:move %0")
    ferry.db.set("cmd_ashore", "$ashore:move_to(enactor, loc(me))")

    # The gate exit into the sea at (0, 0).
    gate = sim.obj("sea", location=jetty, tags=["exit"])
    gate.db.set("dest_resolver", "wilderness")
    gate.db.set("wild_region", "gullwater")
    gate.db.set("wild_x", 0)
    gate.db.set("wild_y", 0)

    alice = sim.player("Alice", location=jetty)
    alice.db.set("hp", 10)
    alice.db.set("max_hp", 10)
    alice.db.set("home", jetty.id)
    alice.db.set("skill_swimming", 3)   # can't swim — 3d6 vs 3 barely lands
    try:
        yield SimpleNamespace(sim=sim, store=sim.store, jetty=jetty,
                              hold=hold, sea=sea, ferry=ferry, alice=alice)
    finally:
        wilderness.reset()
        sim.close()


def _ticker(obj):
    return next(b for b in obj.get_behaviors()
                if b.behavior_id == "script_ticker")


def _undertow(cell):
    return next(o for o in cell.contents if o.name == "the undertow")


@pytest.mark.asyncio
class TestActTwo:

    async def test_boarding_and_rowing_across_open_water(self, world):
        """$board puts the walker in the boat; $row moves the BOAT, and
        a crewed boat materializes fresh ocean."""
        w = world
        await w.sim.do(w.alice, "board")
        assert w.alice.location is w.ferry

        # Rowing while ashore: the ferry walks the gate exit itself.
        await w.sim.do(w.alice, "row sea")
        assert w.ferry.location is not w.jetty
        assert w.ferry.location.has_tag("wildcell:gullwater:0,0")
        assert w.alice.location is w.ferry          # riding, not swimming

        await w.sim.do(w.alice, "row north")
        assert w.ferry.location.has_tag("wildcell:gullwater:0,1")

    async def test_the_undertow_spares_the_boat_and_takes_the_swimmer(self, world):
        """Drowning from primitives: the cell_populate undertow ticks a
        swim check against players directly in the water — passengers
        inside the boat are not in the cell's direct contents."""
        w = world
        await w.sim.do(w.alice, "board")
        await w.sim.do(w.alice, "row sea")
        cell = w.ferry.location
        undertow = _undertow(cell)

        # Aboard: the tick never sees her.
        await _ticker(undertow).tick(undertow, 1.0)
        assert int(w.alice.db.get("hp")) == 10

        # Overboard: untrained swimming — the sea takes its due.
        await w.sim.do(w.alice, "ashore")
        assert w.alice.location is cell
        for _ in range(8):
            await _ticker(undertow).tick(undertow, 1.0)
        assert int(w.alice.db.get("hp")) < 10

        # Back aboard: safe again.
        await w.sim.do(w.alice, "board")
        hp = int(w.alice.db.get("hp"))
        await _ticker(undertow).tick(undertow, 1.0)
        assert int(w.alice.db.get("hp")) == hp

    async def test_the_wreck_landmark_is_an_instance_portal(self, world):
        """At (3,3) the provider authors a portal exit; walking it
        materializes a per-party copy of the wreck, with evacuation back
        to the Jetty."""
        w = world
        await wilderness.enter_cell(w.alice, "gullwater", 3, 3, w.store)
        landmark = w.alice.location
        assert any(o.name == "wreck" for o in landmark.contents)

        await w.sim.do(w.alice, "wreck")
        assert w.alice.location.has_tag("ephemeral")
        assert w.alice.location.name == "The Flooded Hold"
        assert instances.instance_for("wreck", w.alice) is not None

        # The authored escape: the clone's 'surface' exit still points
        # at the real, persistent Jetty (external ids survive import).
        await w.sim.do(w.alice, "surface")
        assert w.alice.location is w.jetty

        # And a reaped straggler lands at instance_return (the Jetty).
        await w.sim.do(w.alice, "sea")              # walk back in afoot
        await wilderness.enter_cell(w.alice, "gullwater", 3, 3, w.store)
        await w.sim.do(w.alice, "wreck")
        master = instances.instance_for("wreck", w.alice)
        await instances.destroy_instance(master, w.store)
        assert w.alice.location is w.jetty          # instance_return

    async def test_the_sea_reaps_behind_the_expedition(self, world):
        """Cells (and their undertows) die at TTL once the boat has
        passed; the water ahead is always fresh."""
        w = world
        await w.sim.do(w.alice, "board")
        await w.sim.do(w.alice, "row sea")
        await w.sim.do(w.alice, "row north")
        wake = wilderness.cell_for("gullwater", 0, 0)
        undertow = _undertow(wake)

        reaped = await wilderness.reap_wilderness(
            w.store, now=time.time() + 10_000)

        assert reaped >= 1
        assert wilderness.cell_for("gullwater", 0, 0) is None
        assert w.store.get_cached(undertow.id) is None
        # The occupied cell (crewed boat inside) survives.
        assert w.ferry.location is wilderness.cell_for("gullwater", 0, 1)
