"""
The before/apply/after trio (docs/design/action-phases.md): every action's
engine effect runs BETWEEN the permission pass and the reaction pass.

The one rule these tests pin: `on_check` sees the world before, `ON_<EVENT>`
sees the world after, and the veto is the only thing that stops the middle.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.core.economy import adjust_credits, get_credits
from realm.testing import Simulator


@pytest.fixture
def sim():
    s = Simulator()
    s.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: list(s._sessions.values()))
    try:
        yield s
    finally:
        s.close()


def player_with_key(sim, room, key_id="brass"):
    p = sim.player("Ada", location=room)
    p.add_tag("builder")
    key = sim.obj("brass key", location=p)
    key.db.set("unlocks", key_id)
    return p


class TestHooksSeePostState:

    async def test_on_lock_sees_itself_locked(self, sim):
        room = sim.room("R")
        ada = player_with_key(sim, room)
        chest = sim.obj("chest", location=room,
                        tags=["thing", "container", "closable"])
        chest.db.set("key_id", "brass")
        chest.db.set("on_lock",
                     "if target is me: set_attr(me, 'saw_locked', has_tag(me, 'locked'))")
        await sim.do(ada, "lock chest")
        assert chest.has_tag("locked")
        assert chest.db.get("saw_locked") is True   # POST-state inside the hook

    async def test_on_open_sees_itself_open(self, sim):
        room = sim.room("R")
        ada = player_with_key(sim, room)
        chest = sim.obj("chest", location=room,
                        tags=["thing", "container", "closable", "closed"])
        chest.db.set("on_open",
                     "if target is me: set_attr(me, 'saw_closed', has_tag(me, 'closed'))")
        await sim.do(ada, "open chest")
        assert chest.db.get("saw_closed") is False  # already open in the hook

    async def test_on_get_sees_item_in_taker_inventory(self, sim):
        room = sim.room("R")
        ada = player_with_key(sim, room)
        idol = sim.obj("idol", location=room)
        idol.db.set("on_get",
                    "if target is me: set_attr(me, 'holder', loc(me).name)")
        await sim.do(ada, "get idol")
        assert idol.location is ada
        assert idol.db.get("holder") == "Ada"       # loc(me) is the TAKER now

    async def test_on_put_sees_item_inside(self, sim):
        room = sim.room("R")
        ada = player_with_key(sim, room)
        pebble = sim.obj("pebble", location=ada)
        sack = sim.obj("sack", location=room, tags=["thing", "container"])
        sack.db.set("on_put",
                    "if target is me: set_attr(me, 'count_at_hook', len(contents(me)))")
        await sim.do(ada, "put pebble in sack")
        assert pebble.location is sack
        assert sack.db.get("count_at_hook") == 1   # POST-state: already inside

    async def test_on_payment_sees_moved_money(self, sim):
        room = sim.room("R")
        ada = player_with_key(sim, room)
        adjust_credits(ada, 100)
        till = sim.obj("till", location=room)
        till.db.set("on_payment",
                    "if target is me: set_attr(me, 'balance_at_hook', credits(me))")
        await sim.do(ada, "pay 30 to till")
        assert get_credits(till) == 30
        assert till.db.get("balance_at_hook") == 30


class TestVetoStopsTheMiddle:

    async def test_ward_veto_prevents_the_lock(self, sim):
        room = sim.room("R")
        ada = player_with_key(sim, room)
        chest = sim.obj("chest", location=room,
                        tags=["thing", "container", "closable"])
        chest.db.set("key_id", "brass")
        chest.db.set("on_check",
                     "if atype == 'item:on_lock': block('The hasp is fused solid.')")
        chest.db.set("on_lock", "if target is me: set_attr(me, 'hook_fired', 1)")
        await sim.do(ada, "lock chest")
        assert not chest.has_tag("locked")           # effect never ran
        assert chest.db.get("hook_fired") is None    # ON_LOCK never fired
        assert any("fused solid" in m for m in sim.seen(ada))

    async def test_ward_veto_prevents_the_payment(self, sim):
        # The capability the old order silently disabled: a ward refuses
        # the coin BEFORE any money moves.
        room = sim.room("R")
        ada = player_with_key(sim, room)
        adjust_credits(ada, 100)
        judge = sim.obj("judge", location=room, tags=["npc"])
        judge.db.set("on_check",
                     "if atype == 'event:payment': block('The judge waves the bribe away.')")
        judge.db.set("on_payment", "if target is me: set_attr(me, 'took', 1)")
        await sim.do(ada, "pay 50 to judge")
        assert get_credits(ada) == 100               # money never moved
        assert get_credits(judge) == 0
        assert judge.db.get("took") is None          # ON_PAYMENT never fired
        assert any("waves the bribe away" in m for m in sim.seen(ada))

    async def test_insufficient_funds_reads_like_a_veto(self, sim):
        room = sim.room("R")
        ada = player_with_key(sim, room)
        adjust_credits(ada, 10)
        till = sim.obj("till", location=room)
        till.db.set("on_payment", "if target is me: set_attr(me, 'took', 1)")
        await sim.do(ada, "pay 500 to till")
        assert get_credits(till) == 0
        assert till.db.get("took") is None
        assert any("don't have 500" in m for m in sim.seen(ada))


class TestAppliedFlag:

    async def test_applied_is_set_between_the_passes(self, sim):
        from realm.core.propagation import Action, get_engine
        room = sim.room("R")
        witness = {}

        def apply(action):
            witness["at_apply"] = action.applied     # False while running
            room.db.set("mark", 1)

        action = Action(actor=None, target=room, action_type="event:test")
        result = await get_engine().propagate(action, apply=apply)
        assert witness["at_apply"] is False
        assert result.applied is True
        assert room.db.get("mark") == 1

    async def test_blocked_apply_marks_unapplied(self, sim):
        from realm.core.propagation import Action, get_engine

        def apply(action):
            action.block("no")

        action = Action(actor=None, target=sim.room("R"),
                        action_type="event:test")
        result = await get_engine().propagate(action, apply=apply)
        assert result.blocked and result.applied is False
