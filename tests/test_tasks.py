"""
MUD_PLAN step 5.5: timed actions (the ``tasks`` feature).

Softcode ``start_task(seconds, done_attr, label, interrupt_attr)`` makes
the enactor busy; when the time passes the reaper runs ``done_attr`` on
the object that started it, with the enactor bound. Moving, a fight or
``stop`` interrupts it. A task is stored on the character, so it survives a
reboot.
"""

from __future__ import annotations

import pytest

from realm.core.action_tags import HOSTILE
from realm.core.propagation import Action, propagate
from realm.testing import Simulator


@pytest.fixture
def clock(monkeypatch):
    now = [5_000_000.0]
    monkeypatch.setattr("realm.std.tasks.tasks.now", lambda: now[0])
    return now


def _forge(sim, room):
    forge = sim.obj("a forge", location=room)
    forge.db.cmd_smelt = ("$smelt: pemit(enactor, 'You start smelting.') if "
                          "start_task(10, 'smelt_done', 'smelting ore', 'smelt_stop') "
                          "else pemit(enactor, 'You are busy.')")
    forge.db.smelt_done = "pemit(enactor, 'An ingot cools on the anvil.')"
    forge.db.smelt_stop = "pemit(enactor, 'You leave the ore half-smelted.')"
    return forge


def _world(sim):
    room = sim.room("Smithy")
    yard = sim.room("Yard")
    door = sim.obj("out", location=room, tags=["exit"])
    door.db.set("destination", yard.id)
    pat = sim.player("Pat", location=room)
    return room, yard, pat, _forge(sim, room)


async def _sweep(sim):
    from realm.std.tasks.tasks import task_sweep
    await task_sweep(sim.store)


@pytest.fixture
def sim():
    s = Simulator()
    try:
        yield s
    finally:
        s.close()


async def test_a_task_completes_and_runs_its_script(sim, clock):
    room, _yard, pat, _forge_obj = _world(sim)
    await sim.do(pat, "smelt")
    assert pat.has_tag("busy")
    assert "You start smelting." in sim.seen(pat)
    clock[0] += 5
    await _sweep(sim)
    assert pat.has_tag("busy")
    clock[0] += 5
    await _sweep(sim)
    assert not pat.has_tag("busy") and pat.db.task is None
    assert "An ingot cools on the anvil." in sim.seen(pat)


async def test_a_second_task_is_refused(sim, clock):
    _room, _yard, pat, _forge_obj = _world(sim)
    await sim.do(pat, "smelt")
    sim.seen(pat)
    await sim.do(pat, "smelt")
    assert "You are busy." in sim.seen(pat)


async def test_moving_interrupts_it(sim, clock):
    _room, yard, pat, _forge_obj = _world(sim)
    await sim.do(pat, "smelt")
    await sim.do(pat, "out")
    assert pat.location is yard
    assert not pat.has_tag("busy")
    assert "You leave the ore half-smelted." in sim.seen(pat)
    clock[0] += 60
    await _sweep(sim)
    assert "An ingot cools on the anvil." not in sim.seen(pat)


async def test_a_fight_interrupts_it(sim, clock):
    room, _yard, pat, _forge_obj = _world(sim)
    wolf = sim.obj("wolf", location=room, tags=["npc"])
    await sim.do(pat, "smelt")
    await propagate(Action(actor=wolf, target=pat, action_type="combat:on_attack",
                           tags={HOSTILE}))
    assert not pat.has_tag("busy")
    assert "You leave the ore half-smelted." in sim.seen(pat)


async def test_stop_interrupts_it(sim, clock):
    _room, _yard, pat, _forge_obj = _world(sim)
    await sim.do(pat, "stop")
    assert "You aren't doing anything." in sim.seen(pat)
    await sim.do(pat, "smelt")
    await sim.do(pat, "stop")
    assert not pat.has_tag("busy")
    assert "You leave the ore half-smelted." in sim.seen(pat)


async def test_busy_is_marked_and_task_of_reads_it(sim, clock):
    room, _yard, pat, forge = _world(sim)
    sam = sim.player("Sam", location=room)
    await sim.do(pat, "smelt")
    await sim.do(sam, "look")
    assert any("Pat (busy)" in line for line in sim.seen(sam))
    clock[0] += 3
    result, err = await sim.eval(forge, "result = task_of(get('Pat'))")
    assert err is None and result == {"label": "smelting ore", "left": 7}
    result, _err = await sim.eval(forge, "result = task_of(me)")
    assert result is None


async def test_stop_task_from_softcode(sim, clock):
    _room, _yard, pat, forge = _world(sim)
    await sim.do(pat, "smelt")
    _result, err = await sim.eval(forge, "stop_task(get('Pat'))")
    assert err is None
    assert not pat.has_tag("busy")


async def test_a_task_survives_a_reload_of_the_character(clock):
    from realm.persistence.worldio import export_objects, import_objects
    first = Simulator()
    try:
        room, _yard, pat, forge = _world(first)
        await first.do(pat, "smelt")
        saved = export_objects([room, forge, pat])         # what a save keeps
    finally:
        first.close()

    second = Simulator()
    try:
        await import_objects(saved, second.store, preserve_ids=True)
        pat = second.store.get_cached(pat.id)
        assert pat.has_tag("busy")
        clock[0] += 10
        ran = []
        engine = second.world.scripts
        original = engine.run_object_script

        async def spy(obj, attr, *, enactor=None):
            ran.append((obj.name, attr, enactor.name if enactor else None))
            return await original(obj, attr, enactor=enactor)

        engine.run_object_script = spy
        await _sweep(second)
        assert ran == [("a forge", "smelt_done", "Pat")]
        assert not pat.has_tag("busy")
    finally:
        second.close()
