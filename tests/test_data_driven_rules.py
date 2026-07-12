"""
Stage A of the data-driven rules kernel: skills and classes are DATA
(``skill_def`` / ``class_def`` objects) the game system reads, with the
built-in tables as the default/fallback. Proven end-to-end in-game via
the Simulator harness.
"""

from __future__ import annotations

import pytest

from realm.core.checks import skill_level
from realm.systems import GurpsSystem, reload_rules, set_game_system
from realm.systems.definitions import define_class, define_skill
from realm.testing import Simulator


@pytest.fixture
def sim():
    s = Simulator()
    try:
        yield s
    finally:
        s.close()


class TestBuiltinFallback:
    """A world with no definitions behaves exactly as before."""

    def test_builtin_skills_present(self, sim):
        defaults = sim.game_system.skill_defaults()
        assert defaults["stealth"] == ("dexterity", -5)   # GURPS built-in

    def test_builtin_classes_used_when_no_class_defs(self, sim):
        classes = sim.game_system._class_options()
        assert set(classes) == {"soldier", "infiltrator", "face", "technician"}


class TestSkillsAsData:

    def test_skill_def_extends_the_table(self, sim):
        # A world can add a skill with no code — just an object.
        sim.add(define_skill("piloting", "dexterity", -4))
        reload_rules()                              # re-read cached table
        defaults = sim.game_system.skill_defaults()
        assert defaults["piloting"] == ("dexterity", -4)

    def test_skill_def_overrides_builtin(self, sim):
        sim.add(define_skill("stealth", "dexterity", -2))   # easier than built-in -5
        reload_rules()
        assert sim.game_system.skill_defaults()["stealth"] == ("dexterity", -2)

    def test_data_skill_drives_an_actual_check(self, sim):
        # The untrained default of a data-defined skill flows into checks.
        sim.add(define_skill("piloting", "dexterity", -4))
        reload_rules()
        ace = sim.obj("Ace", dexterity=14)
        # skill_level: untrained = governing attr + penalty = 14 - 4 = 10
        assert skill_level(ace, "piloting") == 10


class TestClassesAsData:

    def test_class_defs_merge_with_builtins(self, sim):
        # Adding a class ADDS it — it does not wipe the built-in roster
        # (same merge rule as skills; no silent replace-cliff).
        sim.add(define_class("pilot", "ace flyer",
                             {"dexterity": 13}, {"piloting": 14}))
        classes = sim.game_system._class_options()
        assert "pilot" in classes                     # the new one
        assert "soldier" in classes                   # built-ins still there
        assert classes["pilot"][0] == "ace flyer"

    def test_class_def_overrides_builtin_by_name(self, sim):
        sim.add(define_class("soldier", "cyber-augmented shock trooper",
                             {"strength": 14}, {"guns": 15}))
        classes = sim.game_system._class_options()
        assert classes["soldier"][0] == "cyber-augmented shock trooper"

    def test_class_def_appears_in_chargen_and_applies(self, sim):
        sim.add(define_class("pilot", "ace flyer",
                             {"dexterity": 13, "intelligence": 11},
                             {"piloting": 14, "sensors": 11}))
        steps = sim.game_system.chargen_steps()
        template_step = steps[0]
        assert "pilot" in template_step.options

        hero = sim.obj("Hero")
        advance, _ = template_step.handle(hero, "pilot")
        assert advance is True
        assert hero.db.get("dexterity") == 13
        assert hero.db.get("skill_piloting") == 14
        assert hero.db.get("template") == "pilot"


@pytest.mark.asyncio
class TestOLCEditableInGame:
    """The whole point: a builder creates a class as an object in-game,
    and it's immediately live — no restart, no code."""

    async def test_softcode_creates_a_class_then_chargen_uses_it(self, sim):
        builder = sim.player("Builder", location=sim.room("Workshop"))
        # Build a class_def entirely from softcode (as an OLC builder would).
        code = (
            "c = create_obj('scout')\n"
            "add_tag(c, 'class_def')\n"
            "set_attr(c, 'blurb', 'eyes in the dark')\n"
            "set_attr(c, 'stats', {'dexterity': 12})\n"
            "set_attr(c, 'skills', {'stealth': 13, 'observation': 14})"
        )
        _res, err = await sim.eval(builder, code)
        assert err is None, err

        # Now chargen offers it and applies it — proven live.
        classes = sim.game_system._class_options()
        assert "scout" in classes
        recruit = sim.obj("Recruit")
        step = sim.game_system.chargen_steps()[0]
        step.handle(recruit, "scout")
        assert recruit.db.get("skill_observation") == 14
        assert recruit.db.get("dexterity") == 12


def test_builtins_restored_after_sim_close():
    """Simulator.close() must not leave a stale game system installed."""
    sim = Simulator()
    sim.add(define_skill("piloting", "dexterity", -4))
    reload_rules()
    sim.close()
    # A fresh built-in system has no 'piloting' (the data world is gone).
    set_game_system(GurpsSystem())
    assert "piloting" not in GurpsSystem().skill_defaults()
