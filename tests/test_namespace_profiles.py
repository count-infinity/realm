"""
One namespace builder (KERNEL_PLAN 3.3).

A registered function is visible in every evaluation context its flags
allow: a ``readonly`` function in all six profiles, any other only where
the world may change (``script`` and ``inline``).
"""

from __future__ import annotations

import pytest

from realm.core.action_types import ActionType
from realm.core.checks import resolve_with_rule
from realm.core.describe import DETAILS_ATTR, detail_lines
from realm.core.propagation import Action
from realm.permissions.locks import LockType, check_lock, set_lock
from realm.scripting.inline import eval_inline
from realm.scripting.registry import softcode_function, unregister
from realm.testing import Simulator


@pytest.fixture
def world():
    @softcode_function("ro_probe", readonly=True)
    def ro_probe():
        return 7

    @softcode_function("rw_probe")
    def rw_probe():
        return 7

    sim = Simulator()
    room = sim.room("Hall")
    viewer = sim.player("Alice", location=room)
    thing = sim.obj("statue", location=room)
    try:
        yield sim, room, viewer, thing
    finally:
        sim.close()
        unregister("ro_probe")
        unregister("rw_probe")


async def _script(sim, thing, fn):
    result, err = await sim.eval(thing, f"result = {fn}()")
    return result if err is None else err


async def _ward(sim, thing, viewer, fn):
    action = Action(actor=viewer, target=thing, action_type=ActionType.ON_GET)
    await sim.engine.run_check_code(thing, action, f"set_adata('seen', {fn}())")
    return action


def _lock(thing, viewer, fn):
    set_lock(thing, LockType.USE, f"{fn}() == 7")
    return check_lock(thing, LockType.USE, viewer)


def _detail(thing, viewer, fn):
    thing.db.set(DETAILS_ATTR, [[f"{fn}() == 7", "SEEN"]])
    return detail_lines(thing, viewer)


def _inline(thing, viewer, fn):
    return eval_inline(f"[[result = {fn}()]]", thing, viewer)


class TestReadonlyFunctionEverywhere:

    async def test_script(self, world):
        sim, _room, _viewer, thing = world
        assert await _script(sim, thing, "ro_probe") == 7

    async def test_check_ward(self, world):
        sim, _room, viewer, thing = world
        action = await _ward(sim, thing, viewer, "ro_probe")
        assert action.extra.get("seen") == 7 and not action.blocked

    def test_lock(self, world):
        _sim, _room, viewer, thing = world
        assert _lock(thing, viewer, "ro_probe") is True

    def test_detail(self, world):
        _sim, _room, viewer, thing = world
        assert _detail(thing, viewer, "ro_probe") == ["SEEN"]

    def test_inline(self, world):
        _sim, _room, viewer, thing = world
        assert _inline(thing, viewer, "ro_probe") == "7"

    def test_rule(self, world):
        _sim, _room, _viewer, thing = world
        assert resolve_with_rule(thing, "x", 0, "ro_probe()").margin == 7


class TestMutatingFunctionOnlyWhereTheWorldMayChange:

    async def test_script(self, world):
        sim, _room, _viewer, thing = world
        assert await _script(sim, thing, "rw_probe") == 7

    def test_inline(self, world):
        _sim, _room, viewer, thing = world
        assert _inline(thing, viewer, "rw_probe") == "7"

    async def test_check_ward_fails_closed(self, world):
        sim, _room, viewer, thing = world
        action = await _ward(sim, thing, viewer, "rw_probe")
        assert "seen" not in action.extra and action.blocked

    def test_lock_fails_closed(self, world):
        _sim, _room, viewer, thing = world
        assert _lock(thing, viewer, "rw_probe") is False

    def test_detail_hidden(self, world):
        _sim, _room, viewer, thing = world
        assert _detail(thing, viewer, "rw_probe") == []

    def test_rule_raises(self, world):
        _sim, _room, _viewer, thing = world
        with pytest.raises(NameError):
            resolve_with_rule(thing, "x", 0, "rw_probe()")


class TestSubjectHelpers:
    """``skill(name)`` and ``check(name, mod)`` are the subject's, in every profile."""

    def test_inline_skill_is_the_viewers(self, world):
        _sim, _room, viewer, thing = world
        viewer.db.set("skill_observation", 17)
        assert eval_inline("[[result = skill('observation')]]", thing, viewer) == "17"

    def test_detail_skill_and_two_argument_has_tag(self, world):
        _sim, _room, viewer, thing = world
        viewer.db.set("skill_observation", 17)
        viewer.add_tag("elf")
        thing.db.set(DETAILS_ATTR, [
            ["skill('observation') >= 15", "SHARP"],
            ["has_tag(viewer, 'elf')", "ELVISH"],
            ["viewer.has_tag('elf')", "ALSO ELVISH"],
        ])
        assert detail_lines(thing, viewer) == ["SHARP", "ELVISH", "ALSO ELVISH"]

    def test_lock_subject_is_the_caller(self, world):
        _sim, _room, viewer, thing = world
        viewer.db.set("skill_lockpicking", 15)
        set_lock(thing, LockType.USE, "skill('lockpicking') >= 15")
        assert check_lock(thing, LockType.USE, viewer) is True

    def test_inline_check_roll_is_the_standard_three_argument_form(self, world):
        """No inline-only override: check_roll(obj, skill) returns the graded
        CheckResult here as in every other profile."""
        _sim, _room, viewer, thing = world
        code = "[[r = check_roll(viewer, 'observation'); result = r.skill]]"
        assert eval_inline(code, thing, viewer) == "observation"


class TestWardExplainsAMissingFunction:

    async def test_log_names_the_readonly_rule(self, world, caplog):
        sim, _room, viewer, thing = world
        with caplog.at_level("ERROR", logger="realm.scripting.engine"):
            await _ward(sim, thing, viewer, "rw_probe")
        assert any("rw_probe() exists but changes the world" in r.getMessage()
                   for r in caplog.records)
