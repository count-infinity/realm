"""
Room-owner relocation authority — PennMUSH's ``tport_control_ok``.

A builder may teleport / shove around what stands in a room they *own*
(without being able to ``@set`` or ``@destroy`` it — relocation is weaker
than control). ``anchored`` is the opt-out (Penn's ``HEAVY``). The critical
safety property: a *co-located unowned object* must NOT gain this authority
(the world-trusts-world confused-deputy hole), so the room must be owned.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.core.objects import GameObject
from realm.permissions.locks import may_relocate
from realm.testing import Simulator


def _obj(name, **kw):
    return GameObject(name=name, **kw)


class TestMayRelocatePredicate:
    """Pure-predicate coverage — no world needed."""

    def test_owner_of_the_room_may_move_an_occupant(self):
        builder = _obj("Builder", tags=["player"])
        room = _obj("Shop", tags=["room"], owner=builder)
        pc = _obj("Visitor", tags=["player"], location=room)
        assert may_relocate(builder, pc) is True

    def test_non_owner_of_the_room_may_not(self):
        builder = _obj("Builder", tags=["player"])
        stranger = _obj("Stranger", tags=["player"])
        room = _obj("Shop", tags=["room"], owner=builder)
        pc = _obj("Visitor", tags=["player"], location=room)
        assert may_relocate(stranger, pc) is False

    def test_anchored_occupant_resists_room_owner(self):
        builder = _obj("Builder", tags=["player"])
        room = _obj("Shop", tags=["room"], owner=builder)
        pc = _obj("Visitor", tags=["player", "anchored"], location=room)
        assert may_relocate(builder, pc) is False

    def test_but_the_objects_own_controller_still_moves_it_anchored(self):
        # anchored only blocks the room-owner path (rule 2), not control.
        owner = _obj("Owner", tags=["player"])
        gizmo = _obj("gizmo", tags=["anchored"], owner=owner)
        assert may_relocate(owner, gizmo) is True

    def test_unowned_room_grants_no_relocation_authority(self):
        # The Void / system rooms have no owner — nobody gains the loc power.
        builder = _obj("Builder", tags=["player"])
        room = _obj("The Void", tags=["room"])          # owner=None
        pc = _obj("Visitor", tags=["player"], location=room)
        assert may_relocate(builder, pc) is False

    def test_hole_stays_closed_colocated_object_cannot_move_occupant(self):
        # THE regression guard: an unowned object sitting in a builder-owned
        # room must not gain relocation authority over occupants via
        # world-trusts-world. Only the room's owner does.
        builder = _obj("Builder", tags=["player"])
        room = _obj("Shop", tags=["room"], owner=builder)
        bystander = _obj("statue", location=room)        # unowned
        pc = _obj("Visitor", tags=["player"], location=room)
        assert may_relocate(bystander, pc) is False

    def test_admin_may_relocate_anything(self):
        admin = _obj("Wiz", tags=["player", "admin"])   # admin role via tag
        room = _obj("Anywhere", tags=["room"])
        pc = _obj("Visitor", tags=["player", "anchored"], location=room)
        assert may_relocate(admin, pc) is True


@pytest.fixture
def world():
    sim = Simulator()
    builder = sim.player("Builder")
    shop = sim.room("Shop")
    shop.owner = builder                 # the builder owns this room
    builder.location = shop              # …and stands in it (to type $-cmds)
    jail = sim.room("Jail")
    visitor = sim.player("Visitor", location=shop)
    try:
        yield SimpleNamespace(sim=sim, builder=builder, shop=shop, jail=jail,
                              visitor=visitor)
    finally:
        sim.close()


@pytest.mark.asyncio
class TestRoomScriptRelocation:
    """End-to-end. The target is a THIRD party (not the command typer), so
    the enactor-consent path is out — only ``may_relocate`` decides."""

    async def test_owned_room_script_may_move_an_occupant(self, world):
        w = world
        # A trap the builder OWNS, in the builder's room; the builder
        # triggers it against a visitor standing there.
        trap = w.sim.obj("trap", location=w.shop)
        trap.owner = w.builder
        trap.db.set("cmd_spring", f"$spring:move_to('#{w.visitor.id}', "
                                  f"'#{w.jail.id}')")
        await w.sim.do(w.builder, "spring")
        assert w.visitor.location is w.jail

    async def test_colocated_unowned_object_still_cannot(self, world):
        w = world
        # An UNOWNED statue in the same owned room has no authority of its
        # own — even the room owner can't launder authority through it.
        statue = w.sim.obj("statue", location=w.shop)     # owner=None
        statue.db.set("cmd_zap", f"$zap:move_to('#{w.visitor.id}', "
                                 f"'#{w.jail.id}')")
        await w.sim.do(w.builder, "zap")
        assert w.visitor.location is w.shop               # refused

    async def test_anchored_visitor_resists_the_room_script(self, world):
        w = world
        w.visitor.add_tag("anchored")
        trap = w.sim.obj("trap", location=w.shop)
        trap.owner = w.builder
        trap.db.set("cmd_spring", f"$spring:move_to('#{w.visitor.id}', "
                                  f"'#{w.jail.id}')")
        await w.sim.do(w.builder, "spring")
        assert w.visitor.location is w.shop               # anchored
