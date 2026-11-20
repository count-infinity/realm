"""
A door has two sides that agree (BACKLOG 2026-11-17).

ROM keeps both faces of a door in step: ``do_open``, ``do_close``,
``do_lock`` and ``do_unlock`` change the exit in the room beyond that leads
back (``pexit_rev``) too, and the room beyond hears "The $d opens." /
"The $d closes.". Here the far side is the exit's ``partner`` when it is
paired (``@dig``), else the one exit in its destination leading back to
its room (a converted ROM area pairs nothing).
"""

from __future__ import annotations

import pytest

from realm.core.pairing import far_side
from realm.testing import Simulator


@pytest.fixture
def sim():
    s = Simulator()
    try:
        yield s
    finally:
        s.close()


def _gate(sim, *, tags=("exit", "door", "closed")):
    """Inside and Outside the Gate, a west/east pair of unpaired exits."""
    inside, outside = sim.room("Inside the Gate"), sim.room("Outside the Gate")
    west = sim.obj("west", location=inside, tags=list(tags), destination=outside.id,
                   keywords="gate", key_id="citykey")
    east = sim.obj("east", location=outside, tags=list(tags), destination=inside.id,
                   keywords="gate", key_id="citykey")
    return inside, outside, west, east


def test_the_far_side_is_the_partner_else_the_way_back(sim):
    inside, outside, west, east = _gate(sim)
    assert far_side(west) is east and far_side(east) is west
    # A one-way exit has no far side; nor has a way into a room whose only
    # way back leads somewhere else.
    yard = sim.room("Yard")
    hole = sim.obj("hole", location=inside, tags=["exit"], destination=yard.id)
    assert far_side(hole) is None
    sim.obj("ladder", location=yard, tags=["exit"], destination=outside.id)
    assert far_side(hole) is None
    # Two ways back: the reverse direction's (ROM's rev_dir) is the one.
    sim.obj("window", location=outside, tags=["exit"], destination=inside.id)
    assert far_side(west) is east
    # A pairing wins over the way back.
    from realm.core.pairing import pair_exits
    pair_exits(hole, sim.obj("rope", location=yard, tags=["exit"], destination=inside.id))
    assert far_side(hole).name == "rope"


async def test_open_and_close_move_both_sides(sim):
    inside, outside, west, east = _gate(sim)
    pat = sim.player("Pat", location=inside)
    sam = sim.player("Sam", location=outside)
    await sim.do(pat, "open gate")
    assert not west.has_tag("closed") and not east.has_tag("closed")
    assert "The gate opens." in sim.seen(sam)
    await sim.do(pat, "close gate")
    assert west.has_tag("closed") and east.has_tag("closed")
    assert "The gate closes." in sim.seen(sam)
    await sim.do(sam, "open gate")                   # from the other side
    assert not west.has_tag("closed") and not east.has_tag("closed")
    await sim.do(pat, "west")
    assert pat.location is outside


async def test_lock_and_unlock_move_both_sides(sim):
    inside, outside, west, east = _gate(sim)
    pat = sim.player("Pat", location=inside)
    sim.obj("a city key", location=pat, tags=["thing"], unlocks="citykey")
    sam = sim.player("Sam", location=outside)
    await sim.do(pat, "lock gate")
    assert west.has_tag("locked") and east.has_tag("locked")
    await sim.do(sam, "open gate")
    assert east.has_tag("closed")                    # locked from this side too
    await sim.do(pat, "unlock gate")
    assert not west.has_tag("locked") and not east.has_tag("locked")
    await sim.do(sam, "open gate")
    assert not west.has_tag("closed")


async def test_a_paired_door_and_a_keycard_and_a_script(sim):
    # @dig pairs the faces; a keycard swipe and a script's ``open`` line
    # move both, as the commands do.
    inside, outside = sim.room("Lab"), sim.room("Vault")
    a = sim.obj("vault door", location=inside, tags=["exit", "door", "closed"],
                destination=outside.id, key_id="vault")
    b = sim.obj("lab door", location=outside, tags=["exit", "door", "closed"],
                destination=inside.id, key_id="vault")
    from realm.core.pairing import pair_exits
    pair_exits(a, b)
    pat = sim.player("Pat", location=inside)
    sim.obj("keycard", location=pat, tags=["thing"], unlocks="vault")
    await sim.do(pat, "use keycard on vault door")
    assert a.has_tag("locked") and b.has_tag("locked")
    await sim.do(pat, "use keycard on vault door")
    assert not a.has_tag("locked") and not b.has_tag("locked")
    imp = sim.obj("imp", location=inside, tags=["npc"])
    await sim.eval(imp, "cmd('open vault door')", enactor=pat)
    assert not a.has_tag("closed") and not b.has_tag("closed")


async def test_a_picked_lock_opens_both_sides(sim, monkeypatch):
    from realm.std.stealth import commands as stealth_commands
    inside, outside, west, east = _gate(sim, tags=("exit", "door", "closed", "locked"))
    pat = sim.player("Pat", location=inside)
    monkeypatch.setattr(stealth_commands, "check",
                        lambda *a, **k: type("R", (), {"success": True, "margin": 5})())
    await sim.do(pat, "pick west")
    assert not west.has_tag("locked") and not east.has_tag("locked")


async def test_pick_finds_a_door_by_its_keywords(sim, monkeypatch):
    # ``pick gate`` as ``open gate`` (``door_named``), and names the door.
    from realm.std.stealth import commands as stealth_commands
    inside, outside, west, east = _gate(sim, tags=("exit", "door", "closed", "locked"))
    pat = sim.player("Pat", location=inside)
    monkeypatch.setattr(stealth_commands, "check",
                        lambda *a, **k: type("R", (), {"success": True, "margin": 5})())
    await sim.do(pat, "pick gate")
    assert not west.has_tag("locked") and not east.has_tag("locked")
    assert "Click. You defeat the lock on the gate." in sim.seen(pat)
