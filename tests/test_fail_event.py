"""
event:on_fail — the PennMUSH ``@afail`` parity hook.

A blocked, closed, or dead-end exit fires ``event:on_fail``, so an object's
``ON_FAIL`` softcode can react (a locked-door taunt) — and, crucially, a
**dead-end** exit's ``ON_FAIL`` can *materialize* the room beyond it (an
instanced area / a wilderness cell) and move the walker in, with the default
"leads nowhere" line suppressed. See docs/design/pennmush-inventory.md.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.permissions.locks import LockType
from realm.testing import Simulator


@pytest.fixture
def world():
    sim = Simulator()
    hall = sim.room("Hall")
    north = sim.obj("north", location=hall, tags=["exit"])   # a dead-end exit
    alice = sim.player("Alice", location=hall)
    try:
        yield SimpleNamespace(sim=sim, hall=hall, north=north, alice=alice)
    finally:
        sim.close()


@pytest.mark.asyncio
class TestFailEvent:

    async def test_dead_end_exit_fires_on_fail(self, world):
        w = world
        w.north.db.set("on_fail", "pemit(enactor, 'The wall shimmers.')")
        await w.sim.do(w.alice, "north")
        assert any("The wall shimmers." in m for m in w.sim.seen(w.alice))

    async def test_locked_exit_fires_on_fail(self, world):
        w = world
        vault = w.sim.room("Vault")
        w.north.db.set("destination", vault.id)          # has a destination…
        w.north.locks[LockType.BASIC.value] = "False"    # …but is locked
        w.north.db.set("on_fail", "pemit(enactor, 'It rattles, locked.')")
        await w.sim.do(w.alice, "north")
        assert any("It rattles, locked." in m for m in w.sim.seen(w.alice))

    async def test_the_actor_is_the_enactor(self, world):
        w = world
        # ON_FAIL runs with the mover bound as enactor.
        w.north.db.set("on_fail", "pemit(enactor, name(enactor))")
        await w.sim.do(w.alice, "north")
        assert any("Alice" in m for m in w.sim.seen(w.alice))


@pytest.mark.asyncio
class TestPortalViaFail:
    """The headline case: a dead-end exit is a portal — its ON_FAIL
    materializes an instanced area and sends the walker through."""

    def _template(self, sim):
        entry = sim.room("Crypt Entrance")
        entry.add_tag("zone:crypt")
        entry.add_tag("instance_template")
        entry.add_tag("instance_entry")
        return entry

    async def test_dead_end_portal_materializes_and_moves(self, world):
        w = world
        entry = self._template(w.sim)
        w.north.db.set("on_fail", "enter_instance(enactor, 'crypt')")

        await w.sim.do(w.alice, "north")

        # Walked into a fresh ephemeral copy — not the template, not the hall.
        assert w.alice.location is not w.hall
        assert w.alice.location is not entry
        assert w.alice.location.has_tag("ephemeral")

    async def test_dead_end_message_suppressed_when_handler_moves(self, world):
        w = world
        self._template(w.sim)
        w.north.db.set("on_fail", "enter_instance(enactor, 'crypt')")

        await w.sim.do(w.alice, "north")

        joined = " ".join(w.sim.seen(w.alice))
        assert "lead anywhere" not in joined
        assert "nowhere" not in joined

    async def test_dead_end_message_shown_when_handler_does_nothing(self, world):
        w = world
        w.north.db.set("on_fail", "pemit(enactor, 'A cold draft.')")

        await w.sim.do(w.alice, "north")

        joined = " ".join(w.sim.seen(w.alice))
        assert "A cold draft." in joined
        assert w.alice.location is w.hall            # not moved
        assert "lead anywhere" in joined              # default line still shown

    async def test_only_the_enactor_may_be_sent_in(self, world):
        w = world
        self._template(w.sim)
        bob = w.sim.player("Bob", location=w.hall)
        # The exit tries to shove BOB (not the walker) into the instance —
        # refused: the exit controls neither player, and Bob isn't the
        # enactor. The enactor-consent relaxation is scoped to the walker.
        w.north.db.set("on_fail", f"enter_instance('#{bob.id}', 'crypt')")

        await w.sim.do(w.alice, "north")

        assert bob.location is w.hall
