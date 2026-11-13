"""
Global softcode commands (KERNEL_PLAN 6.7): objects tagged
``global_commands`` offer their $-commands from every room.
"""

from __future__ import annotations

import pytest

from realm.testing import Simulator


@pytest.fixture
def world():
    sim = Simulator()
    office = sim.room("Office")
    tavern = sim.room("Tavern")
    nexus = sim.room("Nexus")                 # where the global object lives
    alice = sim.player("Alice", location=tavern)
    finger = sim.obj("finger service", location=nexus)
    finger.db.set("cmd_finger", "$+finger *:pemit(enactor, 'global: ' + arg0)")
    finger.add_tag("global_commands")
    try:
        yield sim, office, tavern, alice, finger
    finally:
        sim.close()


async def test_a_global_command_fires_from_any_room(world):
    sim, office, tavern, alice, _finger = world
    await sim.do(alice, "+finger Bob")
    assert "global: Bob" in sim.seen(alice)
    alice.location = office
    await sim.do(alice, "+finger Cat")
    assert "global: Cat" in sim.seen(alice)


async def test_a_room_local_command_wins(world):
    sim, _office, tavern, alice, _finger = world
    local = sim.obj("tavern board", location=tavern)
    local.db.set("cmd_finger", "$+finger *:pemit(enactor, 'local: ' + arg0)")
    await sim.do(alice, "+finger Bob")
    out = sim.seen(alice)
    assert "local: Bob" in out and "global: Bob" not in out


async def test_only_admins_may_add_the_tag(world):
    sim, _office, tavern, _alice, _finger = world
    builder = sim.player("Bilda", location=tavern)
    builder.add_tag("builder")
    admin = sim.player("Ada", location=tavern)
    admin.add_tag("admin")
    gadget = sim.obj("gadget", location=tavern)
    await sim.do(builder, f"@tag #{gadget.id} = global_commands")
    assert not gadget.has_tag("global_commands")
    await sim.do(admin, f"@tag #{gadget.id} = global_commands")
    assert gadget.has_tag("global_commands")
