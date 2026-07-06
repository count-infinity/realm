"""
Dispositions: NPCs remember attitudes. Reaction rolls memoize,
persuasion sticks, fast-talk wears off, guards and monsters consult
the state.
"""

from __future__ import annotations

import pytest

from realm.behaviors.effects import DispositionBoostBehavior
from realm.combat.behaviors import AggressiveBehavior, GuardBehavior
from realm.core.checks import set_check_resolver
from realm.core.disposition import (
    adjust_disposition,
    disposition_band,
    get_disposition,
    has_met,
    reaction_roll,
    set_disposition,
)
from realm.core.objects import GameObject
from realm.core.propagation import Action, reset_engine


@pytest.fixture(autouse=True)
def fresh_engine():
    reset_engine()
    yield
    reset_engine()


def level_resolver(win: bool):
    """Actor-independent forced outcome for contests isn't needed here —
    tests inject per-object skill levels instead."""


class TestDispositionCore:

    def test_default_and_bands(self):
        npc = GameObject("guard")
        bob = GameObject("Bob", tags=["player"])
        assert get_disposition(npc, bob) == 0
        assert disposition_band(0) == "neutral"
        assert disposition_band(-3) == "hostile"
        assert disposition_band(2) == "friendly"
        assert disposition_band(4) == "devoted"

    def test_default_disposition_baseline(self):
        npc = GameObject("grump")
        npc.db.default_disposition = -1
        bob = GameObject("Bob")
        assert get_disposition(npc, bob) == -1

    def test_hostile_tag_caps(self):
        npc = GameObject("raider", tags=["hostile"])
        bob = GameObject("Bob")
        set_disposition(npc, bob, 3)
        assert get_disposition(npc, bob) == -3

    def test_set_clamps_and_adjust(self):
        npc = GameObject("guard")
        bob = GameObject("Bob")
        assert set_disposition(npc, bob, 99) == 5
        assert adjust_disposition(npc, bob, -20) == -5

    def test_reaction_roll_memoizes(self):
        npc = GameObject("merchant")
        bob = GameObject("Bob")
        assert not has_met(npc, bob)
        first = reaction_roll(npc, bob, dice=16)   # -> +2
        assert first == 2
        # A terrible second roll changes nothing: first impressions stick.
        assert reaction_roll(npc, bob, dice=3) == 2
        assert has_met(npc, bob)

    def test_reaction_roll_layers_temperament(self):
        npc = GameObject("grump")
        npc.db.default_disposition = -1
        bob = GameObject("Bob")
        assert reaction_roll(npc, bob, dice=11) == -1  # neutral roll + grump


@pytest.mark.asyncio
class TestDispositionConsumers:

    async def test_guard_waves_friends_through(self):
        room = GameObject("Gate", tags=["room"])
        guard = GameObject("guard", location=room)
        guard.add_behavior(GuardBehavior(challenge_message="Halt!"))
        bob = GameObject("Bob", tags=["player"], location=room)

        action = Action(actor=bob, target=room, action_type="event:on_leave")
        await guard.get_behaviors()[0].on_check(guard, action)
        assert action.blocked  # stranger stopped

        set_disposition(guard, bob, 2)
        action2 = Action(actor=bob, target=room, action_type="event:on_leave")
        await guard.get_behaviors()[0].on_check(guard, action2)
        assert not action2.blocked  # friend passes

    async def test_aggressive_spares_the_devoted(self):
        from realm.combat.manager import set_combat_manager

        class FakeManager:
            def __init__(self):
                self.fights = []

            async def initiate(self, a, b):
                self.fights.append((a, b))

        manager = FakeManager()
        set_combat_manager(manager)
        try:
            room = GameObject("Lair", tags=["room"])
            wolf = GameObject("wolf", location=room)
            behavior = AggressiveBehavior()
            wolf.add_behavior(behavior)
            bob = GameObject("Bob", tags=["player"], location=room)

            set_disposition(wolf, bob, 3)
            await behavior._maybe_engage(wolf, bob)
            assert manager.fights == []

            set_disposition(wolf, bob, 0)
            await behavior._maybe_engage(wolf, bob)
            assert manager.fights == [(wolf, bob)]
        finally:
            set_combat_manager(None)

    async def test_fasttalk_boost_wears_off(self):
        room = GameObject("Gate", tags=["room"])
        guard = GameObject("guard", location=room)
        bob = GameObject("Bob", tags=["player"], location=room)

        boost = DispositionBoostBehavior(target_id=bob.id, delta=2, duration=2)
        guard.add_behavior(boost)
        assert get_disposition(guard, bob) == 2

        await boost.tick(guard, 4.0)
        await boost.tick(guard, 4.0)  # expires, reverses
        assert get_disposition(guard, bob) == 0
        assert guard.get_behaviors() == []


@pytest.mark.asyncio
class TestSocialCommands:

    def setup_method(self):
        from tests.test_olc import MockPersistence, use_persistence
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

    def teardown_method(self):
        set_check_resolver(None)

    def _scene(self):
        room = GameObject("Gate", tags=["room"])
        npc = GameObject("guard", tags=["npc"], location=room)
        bob = GameObject("Bob", tags=["player"], location=room)
        return room, npc, bob

    async def test_consider_shows_band(self):
        from realm.commands.builtin.social import cmd_greet
        from tests.test_olc import make_context

        _room, npc, bob = self._scene()
        set_disposition(npc, bob, -2)
        ctx = make_context(bob, args="guard")
        await cmd_greet(ctx)
        assert any("suspicion" in m for m in ctx.session.messages)

    async def test_persuade_success_sticks_and_cools_down(self):
        from realm.commands.builtin.social import cmd_persuade
        from realm.core.checks import CheckResult
        from tests.test_olc import make_context

        _room, npc, bob = self._scene()
        set_disposition(npc, bob, 0)

        def rigged(obj, skill, modifier):
            # Bob always wins, guard always loses.
            return CheckResult(obj is bob, 5 if obj is bob else -5, 8,
                               10, skill)
        set_check_resolver(rigged)

        ctx = make_context(bob, args="guard")
        await cmd_persuade(ctx)
        assert get_disposition(npc, bob) == 1
        assert any("goodwill" in m for m in ctx.session.messages)

        ctx2 = make_context(bob, args="guard")
        await cmd_persuade(ctx2)
        assert any("Give it a rest" in m for m in ctx2.session.messages)
        assert get_disposition(npc, bob) == 1  # unchanged

    async def test_fasttalk_failure_costs_standing(self):
        from realm.commands.builtin.social import cmd_fasttalk
        from realm.core.checks import CheckResult
        from tests.test_olc import make_context

        _room, npc, bob = self._scene()
        set_disposition(npc, bob, 0)

        def rigged(obj, skill, modifier):
            return CheckResult(obj is npc, 5 if obj is npc else -5, 8,
                               10, skill)
        set_check_resolver(rigged)

        ctx = make_context(bob, args="guard")
        await cmd_fasttalk(ctx)
        assert get_disposition(npc, bob) == -1
        assert any("sees right through you" in m for m in ctx.session.messages)


@pytest.mark.asyncio
class TestDispositionSoftcode:

    async def test_script_reads_and_reacts(self):

        room = GameObject("Gate", tags=["room"])
        npc = GameObject("innkeeper", location=room)
        bob = GameObject("Bob", tags=["player"], location=room)
        set_disposition(npc, bob, 2)
        npc.db.cmd_room = (
            "$room*:\n"
            "if disposition(me, enactor) >= 2: pemit(enactor, 'The best room, friend!')\n"
            "else: pemit(enactor, 'No vacancy.')"
        )
        # Direct function check (the trigger path is covered elsewhere).
        from realm.scripting.functions import ScriptFunctions
        funcs = ScriptFunctions(enactor=bob, executor=npc)
        assert funcs.disposition(npc) == 2

    async def test_adjust_needs_authority(self):
        from realm.scripting.functions import ScriptFunctions

        room = GameObject("Gate", tags=["room"])
        imp = GameObject("imp", location=room)
        guard = GameObject("guard", location=room,
                           owner=GameObject("Owner", tags=["player"]))
        bob = GameObject("Bob", tags=["player"], location=room)

        funcs = ScriptFunctions(executor=imp)
        # imp doesn't control someone else's guard...
        assert funcs.adjust_disposition(guard, bob, 5) is False
        # ...but owns its own opinions.
        assert funcs.adjust_disposition(imp, bob, -2) is True
        assert get_disposition(imp, bob) == -2

    async def test_reaction_roll_from_script(self):
        from realm.scripting.functions import ScriptFunctions

        room = GameObject("Gate", tags=["room"])
        npc = GameObject("merchant", location=room)
        bob = GameObject("Bob", tags=["player"], location=room)

        funcs = ScriptFunctions(enactor=bob, executor=npc)
        value = funcs.reaction_roll(npc)
        assert -2 <= value <= 2
        assert has_met(npc, bob)
