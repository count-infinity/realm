"""
move_to — the vetoable, movement-tagged relocation (the ``move_and_slide``
of REALM movement). A game ``cast teleport`` rides it, so wards that block by
*category* (``has_atag('movement')``) stop it without knowing the spell
exists — while ``teleport_obj`` (= ``move_to(force=True)``) skips the wards
but still honors locks and authority. Both the origin AND the destination
get an event-veto (the destination check a static lock can't express). See
docs/design/pennmush-inventory.md and the CoffeeMUD flag-mask model.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.core.movement import move_to
from realm.permissions.locks import LockType
from realm.testing import Simulator

BOUND = "block('Chains of binding hold you fast.') if has_atag('movement') else None"
WARDED = "block('The wards flare.') if has_atag('magic') else None"


@pytest.fixture
def world():
    sim = Simulator()
    hall = sim.room("Hall")
    sanctum = sim.room("Sanctum")
    alice = sim.player("Alice", location=hall)
    try:
        yield SimpleNamespace(sim=sim, hall=hall, sanctum=sanctum, alice=alice)
    finally:
        sim.close()


@pytest.mark.asyncio
class TestMoveToPython:
    """The primitive directly (so we can read its bool result)."""

    async def test_relocates(self, world):
        w = world
        moved = await move_to(w.alice, w.sanctum)
        assert moved is True
        assert w.alice.location is w.sanctum

    async def test_bound_ward_on_origin_fizzles(self, world):
        w = world
        w.hall.db.set("on_check", BOUND)
        moved = await move_to(w.alice, w.sanctum)
        assert moved is False
        assert w.alice.location is w.hall
        assert any("binding" in m for m in w.sim.seen(w.alice))

    async def test_ward_on_mover_fizzles(self, world):
        w = world
        w.alice.db.set("on_check", BOUND)          # the bind is on the PC
        moved = await move_to(w.alice, w.sanctum)
        assert moved is False
        assert w.alice.location is w.hall

    async def test_destination_vetoes_incoming(self, world):
        w = world
        # The destination's OWN event-veto — what a static lock can't do.
        w.sanctum.db.set("on_check", BOUND)
        moved = await move_to(w.alice, w.sanctum)
        assert moved is False
        assert w.alice.location is w.hall

    async def test_enter_lock_honored(self, world):
        w = world
        w.sanctum.locks[LockType.ENTER.value] = "False"
        moved = await move_to(w.alice, w.sanctum)
        assert moved is False
        assert w.alice.location is w.hall

    async def test_teleport_lock_honored(self, world):
        w = world
        # A "walkable but no teleporting in" sanctum: the game teleport path
        # now honors the teleport lock (it didn't before the unification).
        w.sanctum.locks[LockType.TELEPORT.value] = "False"
        moved = await move_to(w.alice, w.sanctum)
        assert moved is False
        assert w.alice.location is w.hall

    async def test_force_skips_wards_but_not_the_teleport_lock(self, world):
        w = world
        w.hall.db.set("on_check", BOUND)                    # a WARD on origin
        w.sanctum.locks[LockType.TELEPORT.value] = "False"  # a LOCK on dest
        # force tunnels past the Bound ward — but the teleport lock is not a
        # ward, so it still holds. (This is the whole point of the split.)
        moved = await move_to(w.alice, w.sanctum, force=True)
        assert moved is False
        assert w.alice.location is w.hall

    async def test_force_skips_a_ward_when_no_lock_stops_it(self, world):
        w = world
        w.hall.db.set("on_check", BOUND)
        moved = await move_to(w.alice, w.sanctum, force=True)
        assert moved is True
        assert w.alice.location is w.sanctum

    async def test_forced_arrival_still_fires_on_enter(self, world):
        w = world
        witness = w.sim.player("Witness", location=w.sanctum)
        await move_to(w.alice, w.sanctum, force=True)
        # "Skip the gates, keep the notification" — the room sees the arrival.
        assert any("arrives" in m for m in w.sim.seen(witness))

    async def test_destination_ward_also_stops_walk_ins(self, world):
        w = world
        # The same sanctum ward that vetoes teleport-in vetoes WALKING in —
        # one choke point (pre_enter fires on both movement paths).
        w.sanctum.db.set("on_check", BOUND)
        door = w.sim.obj("door", location=w.hall, tags=["exit"])
        door.db.set("destination", w.sanctum.id)

        await w.sim.do(w.alice, "door")

        assert w.alice.location is w.hall

    async def test_magic_tag_is_selective(self, world):
        w = world
        w.sanctum.db.set("on_check", WARDED)       # blocks only magic
        # A mundane move slips through the anti-magic ward…
        assert await move_to(w.alice, w.sanctum) is True
        w.alice.location = w.hall
        # …but a magic-tagged move is caught.
        assert await move_to(w.alice, w.sanctum, extra_tags=["magic"]) is False
        assert w.alice.location is w.hall


@pytest.mark.asyncio
class TestMoveToSoftcode:
    """The softcode surface — a spell casting move_to(enactor, dest)."""

    async def test_cast_teleport_moves_the_enactor(self, world):
        w = world
        res, err = await w.sim.eval(
            w.alice, f"move_to(enactor, '#{w.sanctum.id}', tags=['magic'])",
            enactor=w.alice)
        assert err is None
        assert w.alice.location is w.sanctum

    async def test_bound_ward_stops_cast_teleport(self, world):
        w = world
        w.hall.db.set("on_check", BOUND)
        res, err = await w.sim.eval(
            w.alice, f"move_to(enactor, '#{w.sanctum.id}', tags=['magic'])",
            enactor=w.alice)
        assert err is None
        assert w.alice.location is w.hall            # the bind held
        assert any("binding" in m for m in w.sim.seen(w.alice))  # reason shown

    async def test_raw_teleport_obj_bypasses_the_ward(self, world):
        w = world
        w.hall.db.set("on_check", BOUND)
        # force skips the on_check wards (not locks/authority) — the wizard
        # path tunnels past a Bound field: the kernel/game split.
        res, err = await w.sim.eval(
            w.alice, f"teleport_obj(enactor, '#{w.sanctum.id}')",
            enactor=w.alice)
        assert err is None
        assert w.alice.location is w.sanctum

    async def test_cannot_move_a_non_enactor_you_dont_control(self, world):
        w = world
        bob = w.sim.player("Bob", location=w.hall)
        res, err = await w.sim.eval(
            w.alice, f"move_to('#{bob.id}', '#{w.sanctum.id}')",
            enactor=w.alice)
        assert err is None
        assert res is None                           # bare call, no result var
        assert bob.location is w.hall                # refused
