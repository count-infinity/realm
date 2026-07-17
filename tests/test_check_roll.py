"""`check_roll` — a graded, condition-modified check for softcode.

`skill_check()` calls the real `check()` pipeline (which grades the roll
AND folds in `check_mods`) but throws all but the bool away. So softcode
that wanted a *margin* reached for
`margin_under(roll('3d6'), get_attr(me, 'skill', 8))` — which reads the
TRAINED level raw and silently ignores every condition modifier. A
fear-struck or well-fed crafter rolled as if neither applied: item 129's
meal buff never reached item 125's craft roll.

`check_roll(obj, skill, mod)` returns the whole `CheckResult` from the
real pipeline, so `.margin` is available AND `check_mods` count.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.core.checks import set_check_resolver
from realm.core.dice import CheckResult
from realm.testing import Simulator


@pytest.fixture
def world():
    sim = Simulator()
    room = sim.room("Kitchen")
    cook = sim.player("Cook", location=room)
    cook.db.set('skill_cooking', 12)
    # Deterministic: 3d6 always totals 10, so margin = effective - 10.
    set_check_resolver(
        lambda obj, skill, mod: CheckResult(
            (obj.db.get(f'skill_{skill}', 8) + mod) >= 10,
            (obj.db.get(f'skill_{skill}', 8) + mod) - 10,
            10,
            obj.db.get(f'skill_{skill}', 8) + mod,
            skill,
        ))
    try:
        yield SimpleNamespace(sim=sim, room=room, cook=cook)
    finally:
        set_check_resolver(None)
        sim.close()


@pytest.mark.asyncio
class TestCheckRoll:
    async def test_returns_a_graded_result(self, world):
        w = world
        r, _ = await w.sim.eval(
            w.cook, "r = check_roll(me, 'cooking'); result = [r.success, r.margin]")
        # 12 vs 10 -> success, margin +2.
        assert r == [True, 2]

    async def test_folds_in_check_mods(self, world):
        """The headline: a +3 buff in check_mods reaches the roll."""
        w = world
        w.cook.db.set('check_mods', {'inspired': {'all': 3}})
        eff, _ = await w.sim.eval(w.cook, "result = check_roll(me, 'cooking').effective")
        assert eff == 15                    # 12 trained + 3 buff

    async def test_a_penalty_condition_lowers_the_roll(self, world):
        w = world
        w.cook.db.set('check_mods', {'fear': {'all': -4}})
        r, _ = await w.sim.eval(
            w.cook, "r = check_roll(me, 'cooking'); result = [r.effective, r.success]")
        # 12 - 4 = 8, below the 10 the resolver needs -> failure.
        assert r == [8, False]

    async def test_the_old_idiom_ignores_check_mods(self, world):
        """Contrast, pinned: the margin_under workaround reads the trained
        level and never sees the buff. This is the bug check_roll fixes."""
        w = world
        w.cook.db.set('check_mods', {'inspired': {'all': 3}})
        old, _ = await w.sim.eval(
            w.cook,
            "result = margin_under(roll('3d6'), get_attr(me, 'skill_cooking', 8)).effective")
        assert old == 12                    # buff invisible to the old way

    async def test_explicit_modifier_stacks_with_conditions(self, world):
        w = world
        w.cook.db.set('check_mods', {'inspired': {'all': 3}})
        eff, _ = await w.sim.eval(w.cook, "result = check_roll(me, 'cooking', -1).effective")
        assert eff == 14                    # 12 + 3 buff - 1 explicit

    async def test_unresolvable_object_fails_safely(self, world):
        w = world
        r, _ = await w.sim.eval(
            w.cook, "r = check_roll(get('nobody'), 'x'); result = [r.success, r.margin]")
        assert r == [False, 0]

    async def test_usable_in_an_on_check_ward(self, world):
        """check_roll is read-only, so it belongs in the ward namespace."""
        from realm.scripting.functions import ScriptFunctions
        assert 'check_roll' in ScriptFunctions(
            executor=world.cook).readonly_dict()
