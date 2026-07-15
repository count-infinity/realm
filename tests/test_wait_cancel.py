"""
Cancelable ``wait()`` — the scheduler handle (LDMud ``call_out`` /
``remove_call_out``, MOO ``fork`` / ``kill_task``). ``wait()`` returns an
opaque handle id; ``cancel_wait(id)`` calls the pending wait off before it
fires (a defuse), gated so only a controller of the scheduling object may
cancel it.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.testing import Simulator


@pytest.fixture
def world():
    sim = Simulator()
    room = sim.room("Hall")
    clock = sim.obj("clock", location=room)
    clock.db.set("boom", "set_attr(me, 'fired', 1)")   # what a wait will run
    alice = sim.player("Alice", location=room)
    alice.db.set("boom", "set_attr(me, 'fired', 1)")
    try:
        yield SimpleNamespace(sim=sim, room=room, clock=clock, alice=alice)
    finally:
        sim.close()


@pytest.mark.asyncio
class TestCancelableWait:

    async def test_wait_returns_a_handle(self, world):
        w = world
        res, err = await w.sim.eval(w.clock, "result = wait(5, 'say tick')")
        assert err is None
        assert isinstance(res, str) and res       # a non-empty handle id

    async def test_uncancelled_wait_fires(self, world):
        w = world
        await w.sim.eval(w.clock, "wait(0, 'trigger me/boom')")
        await w.sim.engine.tick_waits()
        assert w.clock.db.get("fired") == 1

    async def test_cancel_prevents_firing(self, world):
        w = world
        # Schedule and cancel in one script — the handle round-trips.
        await w.sim.eval(
            w.clock, "t = wait(0, 'trigger me/boom'); cancel_wait(t)")
        await w.sim.engine.tick_waits()
        assert w.clock.db.get("fired") is None      # defused

    async def test_cancel_across_scripts_via_stored_handle(self, world):
        w = world
        res, _ = await w.sim.eval(
            w.clock, "result = wait(0, 'trigger me/boom')")
        await w.sim.eval(w.clock, f"cancel_wait('{res}')")
        await w.sim.engine.tick_waits()
        assert w.clock.db.get("fired") is None

    async def test_cancel_requires_control_of_the_scheduler(self, world):
        w = world
        # Alice (a player) schedules a wait; an unowned gremlin can't cancel
        # it — the id is not authority (rule: control the scheduling object).
        res, _ = await w.sim.eval(
            w.alice, "result = wait(0, 'trigger me/boom')", enactor=w.alice)
        gremlin = w.sim.obj("gremlin", location=w.room)
        await w.sim.eval(gremlin, f"cancel_wait('{res}')", enactor=gremlin)

        await w.sim.engine.tick_waits()
        assert w.alice.db.get("fired") == 1         # cancel denied, wait fired

    async def test_cancel_unknown_handle_is_harmless(self, world):
        w = world
        res, err = await w.sim.eval(w.clock, "result = cancel_wait('nope')")
        assert err is None
        assert res is True                          # queued (no-op at drain)
