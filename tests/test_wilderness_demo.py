"""
The frontier demo region (examples/wilderness) driven end-to-end: gate in,
walk cells, authored back-exit out — proving the shipped example's
provider softcode (list/dict literals, subscripts) evaluates in the
sandbox and the R5 seam works both ways.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from realm.core import wilderness
from realm.testing import Simulator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent
                       / "examples" / "wilderness"))

from frontier import EDGE_MSG, create_frontier  # noqa: E402

TERRAIN = {"meadow", "forest", "rocks", "creek"}


@pytest.fixture
def world():
    sim = Simulator()
    wilderness.reset()
    try:
        yield SimpleNamespace(sim=sim, store=sim.store)
    finally:
        wilderness.reset()
        sim.close()


@pytest.mark.asyncio
async def test_frontier_walkabout(world):
    w = world
    built = await create_frontier(w.store)
    alice = w.sim.player("Alice", location=built["trailhead"])

    # In through the gate — the deferred destination materializes (10,10).
    await w.sim.do(alice, "gate")
    start_cell = alice.location
    assert start_cell.has_tag("wildcell:frontier:10,10")
    assert TERRAIN & {t for t in ("meadow", "forest", "rocks", "creek")
                      if start_cell.has_tag(t)}

    # Walk a few cells; each derives deterministically from its coord.
    await w.sim.do(alice, "north")
    assert alice.location.has_tag("wildcell:frontier:10,11")
    # (10,11) is pine forest ((x*7+y*13)%4 == 1) — a wolf lives here,
    # born ephemeral + zone-tagged so it dies with the cell.
    wolves = [o for o in alice.location.contents if o.has_tag("npc")]
    assert len(wolves) == 1
    assert wolves[0].name == "a frontier wolf"
    assert wolves[0].has_tag("ephemeral")
    await w.sim.do(alice, "east")
    assert alice.location.has_tag("wildcell:frontier:11,11")

    # The provider's terrain is a pure function of the coordinate.
    again = await wilderness.materialize_cell("frontier", 10, 11, w.store)
    assert again.name == wilderness.cell_for("frontier", 10, 11).name

    # Out through the authored back-exit at the start coordinate (R5).
    await w.sim.do(alice, "south")
    await w.sim.do(alice, "west")
    assert alice.location is start_cell
    await w.sim.do(alice, "trailhead")
    assert alice.location is built["trailhead"]


@pytest.mark.asyncio
async def test_frontier_edge_is_a_bramble_wall(world):
    w = world
    built = await create_frontier(w.store)
    alice = w.sim.player("Alice", location=built["trailhead"])

    await wilderness.enter_cell(alice, "frontier", 10, 20, w.store)
    await w.sim.do(alice, "north")              # y=21 is out of bounds

    assert alice.location.has_tag("wildcell:frontier:10,20")
    assert wilderness.cell_for("frontier", 10, 21) is None
    assert any(EDGE_MSG in line for line in w.sim.seen(alice))
