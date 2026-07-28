"""ScriptedBehavior — behavior logic defined in-world as behavior_def objects.

The contract under test: an object tagged ``behavior_def`` carries hook
softcode (on_check / on_react / on_tick); attaching it by name via the
registry's fallback gives any object that logic; hooks resolve the def
BY NAME AT FIRE TIME (live edits propagate, a missing def is inert); and
``param(key, default)`` reads the attachment's own parameters so one def
serves many differently-tuned carriers.
"""

from __future__ import annotations

import asyncio

import pytest

from realm.behaviors.scripted import ScriptedBehavior, find_behavior_def
from realm.core.behaviors import BehaviorRegistry
from realm.testing import Simulator


async def feed(sim, who, text):
    """Submit a possibly multi-line block one real input line at a time."""
    for line in text.strip("\n").splitlines():
        await sim.submit_line(who, line)


@pytest.fixture
def world():
    sim = Simulator()
    bay = sim.room("Reactor Control")
    bob = sim.player("Bob", location=bay)
    bob.add_tag("builder")
    bob.add_tag("admin")
    yield sim, bay, bob
    sim.close()


async def build_breach_rig(sim, bob, bay):
    """A console that fires event:breach (severity 8, tag hazard) and a
    monitor that records the severity it witnesses."""
    console = sim.obj("console", location=bay)
    console.owner = bob
    await feed(sim, bob, """@set console/cmd_purge = '''
$purge:
act(me, 'Klaxon!', targeting='room', action_type='event:breach', extra={'severity': 8}, tags=['hazard'])
'''""")
    monitor = sim.obj("monitor", location=bay)
    monitor.owner = bob
    await feed(sim, bob, """@set monitor/on_breach = '''
set_attr(me, 'heard', adata('severity', -1))
'''""")
    return monitor


async def build_filter_def(sim, bob):
    await feed(sim, bob, """@create hazard_filter
@tag hazard_filter = behavior_def""")
    await feed(sim, bob, """@set hazard_filter/on_check = '''
if has_atag('hazard') and V('online') and adata('severity', 0) > param('cut_to', 2):
    set_adata('severity', param('cut_to', 2))
'''""")


async def purge(sim, bob, monitor):
    monitor.db.set("heard", None)
    await sim.submit_line(bob, "purge")
    await asyncio.sleep(0.05)
    return monitor.db.get("heard")


@pytest.mark.asyncio
class TestScriptedOnCheck:

    async def test_bystander_object_intercepts_via_attached_def(self, world):
        """The headline: a plain object in the room, carrying a def-based
        behavior, edits the payload before the reactor reads it."""
        sim, bay, bob = world
        monitor = await build_breach_rig(sim, bob, bay)
        await build_filter_def(sim, bob)
        filt = sim.obj("carbon filter", location=bay)
        filt.owner = bob
        await sim.submit_line(bob, "@set carbon filter/online = 1")
        await sim.submit_line(bob, "@behavior carbon filter = hazard_filter, cut_to:2")

        assert await purge(sim, bob, monitor) == 2

    async def test_params_tune_each_attachment(self, world):
        sim, bay, bob = world
        monitor = await build_breach_rig(sim, bob, bay)
        await build_filter_def(sim, bob)
        vent = sim.obj("air vent", location=bay)
        vent.owner = bob
        await sim.submit_line(bob, "@set air vent/online = 1")
        await sim.submit_line(bob, "@behavior air vent = hazard_filter, cut_to:5")

        assert await purge(sim, bob, monitor) == 5

    async def test_def_state_gates_the_hook(self, world):
        """V() inside the hook reads the ATTACHED object, so its own
        attributes (online) gate the logic."""
        sim, bay, bob = world
        monitor = await build_breach_rig(sim, bob, bay)
        await build_filter_def(sim, bob)
        filt = sim.obj("carbon filter", location=bay)
        filt.owner = bob
        await sim.submit_line(bob, "@behavior carbon filter = hazard_filter")

        assert await purge(sim, bob, monitor) == 8   # online unset -> inert
        await sim.submit_line(bob, "@set carbon filter/online = 1")
        assert await purge(sim, bob, monitor) == 2

    async def test_live_edit_of_the_def_changes_every_attachment(self, world):
        sim, bay, bob = world
        monitor = await build_breach_rig(sim, bob, bay)
        await build_filter_def(sim, bob)
        filt = sim.obj("carbon filter", location=bay)
        filt.owner = bob
        await sim.submit_line(bob, "@set carbon filter/online = 1")
        await sim.submit_line(bob, "@behavior carbon filter = hazard_filter")
        assert await purge(sim, bob, monitor) == 2

        await feed(sim, bob, """@set hazard_filter/on_check = '''
if has_atag('hazard'):
    set_adata('severity', 0)
'''""")
        assert await purge(sim, bob, monitor) == 0

    async def test_missing_def_is_inert_not_an_error(self, world):
        sim, bay, bob = world
        monitor = await build_breach_rig(sim, bob, bay)
        await build_filter_def(sim, bob)
        filt = sim.obj("carbon filter", location=bay)
        filt.owner = bob
        await sim.submit_line(bob, "@set carbon filter/online = 1")
        await sim.submit_line(bob, "@behavior carbon filter = hazard_filter")

        target = find_behavior_def("hazard_filter")
        await sim.submit_line(bob, f"@destroy #{target.id}")
        await asyncio.sleep(0.05)
        assert find_behavior_def("hazard_filter") is None
        assert await purge(sim, bob, monitor) == 8   # inert, no crash


@pytest.mark.asyncio
class TestScriptedReactAndTick:

    async def test_on_react_observes_the_action(self, world):
        sim, bay, bob = world
        monitor = await build_breach_rig(sim, bob, bay)
        await feed(sim, bob, """@create siren_logic
@tag siren_logic = behavior_def""")
        await feed(sim, bob, """@set siren_logic/on_react = '''
if atype == 'event:breach':
    set_attr(me, 'reacted_to', adata('severity', 0))
'''""")
        siren = sim.obj("siren", location=bay)
        siren.owner = bob
        await sim.submit_line(bob, "@behavior siren = siren_logic")

        await purge(sim, bob, monitor)
        assert siren.db.get("reacted_to") == 8

    async def test_on_tick_runs_as_the_attached_object(self, world):
        sim, bay, bob = world
        await feed(sim, bob, """@create pulse_logic
@tag pulse_logic = behavior_def
@set pulse_logic/on_tick = incr('pulses')""")
        beacon = sim.obj("beacon", location=bay)
        beacon.owner = bob
        await sim.submit_line(bob, "@behavior beacon = pulse_logic, interval:1")

        behavior = beacon.get_behaviors()[0]
        assert behavior.should_tick
        for _ in range(3):
            await behavior.tick(beacon, 0.1)
        assert beacon.db.get("pulses") == 3

    async def test_def_without_on_tick_declines_ticking(self, world):
        sim, bay, bob = world
        await build_filter_def(sim, bob)
        filt = sim.obj("carbon filter", location=bay)
        filt.owner = bob
        await sim.submit_line(bob, "@behavior carbon filter = hazard_filter")
        assert not filt.get_behaviors()[0].should_tick


@pytest.mark.asyncio
class TestRegistryAndCommand:

    async def test_attach_with_a_typo_errors(self, world):
        sim, bay, bob = world
        await build_filter_def(sim, bob)
        filt = sim.obj("carbon filter", location=bay)
        filt.owner = bob
        sim.seen(bob)
        await sim.submit_line(bob, "@behavior carbon filter = hazrd_filter")
        assert any("Unknown behavior" in s for s in sim.seen(bob))
        assert not filt.get_behaviors()

    async def test_listing_and_removal_speak_the_def_name(self, world):
        sim, bay, bob = world
        await build_filter_def(sim, bob)
        filt = sim.obj("carbon filter", location=bay)
        filt.owner = bob
        await sim.submit_line(bob, "@behavior carbon filter = hazard_filter")

        sim.seen(bob)
        await sim.submit_line(bob, "@behavior carbon filter")
        assert any("hazard_filter" in s for s in sim.seen(bob))

        sim.seen(bob)
        await sim.submit_line(bob, "@behavior/list")
        assert any("World behavior defs: hazard_filter" in s
                   for s in sim.seen(bob))

        await sim.submit_line(bob, "@behavior/remove carbon filter = hazard_filter")
        assert not filt.get_behaviors()

    async def test_serialization_round_trips_by_def_name(self, world):
        sim, bay, bob = world
        await build_filter_def(sim, bob)
        filt = sim.obj("carbon filter", location=bay)
        filt.owner = bob
        await sim.submit_line(bob, "@behavior carbon filter = hazard_filter, cut_to:3")

        data = filt.get_behaviors()[0].to_dict()
        assert data["behavior_id"] == "hazard_filter"

        restored = BehaviorRegistry.from_dict(data)
        assert isinstance(restored, ScriptedBehavior)
        assert restored.behavior_id == "hazard_filter"
        assert restored.get_param("cut_to") == 3

    async def test_info_describes_a_registered_behavior(self, world):
        sim, bay, bob = world
        sim.seen(bob)
        await sim.submit_line(bob, "@behavior/info guard")
        out = "\n".join(sim.seen(bob))
        assert "Blocks movement" in out
        assert "challenge_message" in out
        assert "tags marking who passes" in out

    async def test_info_describes_a_behavior_def(self, world):
        sim, bay, bob = world
        await build_filter_def(sim, bob)
        await feed(sim, bob, """@set hazard_filter/blurb = cuts hazard severity while its carrier is online
@set hazard_filter/param_spec = {"cut_to": [2, "severity ceiling while online"]}""")
        sim.seen(bob)
        await sim.submit_line(bob, "@behavior/info hazard_filter")
        out = "\n".join(sim.seen(bob))
        assert "behavior_def object" in out
        assert "cuts hazard severity" in out
        assert "hooks: on_check" in out
        assert "severity ceiling while online" in out

    async def test_info_unknown_name_errors(self, world):
        sim, bay, bob = world
        sim.seen(bob)
        await sim.submit_line(bob, "@behavior/info nonsense")
        assert any("No behavior or behavior_def" in s for s in sim.seen(bob))

    async def test_load_path_survives_a_not_yet_loaded_def(self, world):
        """Non-strict fallback: restoring a saved behavior must not depend
        on its def object having loaded first."""
        sim, bay, bob = world
        restored = BehaviorRegistry.from_dict(
            {"behavior_id": "ghost_def", "params": {"def_name": "ghost_def"}})
        assert isinstance(restored, ScriptedBehavior)
        assert restored.behavior_id == "ghost_def"
        assert not restored.should_tick   # inert until the def exists
