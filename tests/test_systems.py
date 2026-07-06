"""
Tests for the GameSystem abstraction (the swappable GURPS/D20 rules
package), chargen steps, and password hashing.
"""

from __future__ import annotations

from realm.core.objects import GameObject
from realm.server.auth import hash_password, verify_password
from realm.systems import D20System, GameSystemRegistry, GurpsSystem
from realm.systems.base import ChoiceStep


class TestRegistry:

    def test_builtin_systems_registered(self):
        assert set(GameSystemRegistry.list_all()) >= {"gurps", "d20"}

    def test_create_by_id(self):
        assert isinstance(GameSystemRegistry.create("gurps"), GurpsSystem)
        assert isinstance(GameSystemRegistry.create("d20"), D20System)
        assert GameSystemRegistry.create("fate") is None


class TestChoiceStep:

    def _step(self):
        picked = []
        step = ChoiceStep("class", "Pick:", {"fighter": "hits", "rogue": "sneaks"},
                          lambda p, name: picked.append(name))
        return step, picked

    def test_pick_by_number(self):
        step, picked = self._step()
        advance, _ = step.handle(GameObject("Bob"), "2")
        assert advance is True and picked == ["rogue"]

    def test_pick_by_prefix(self):
        step, picked = self._step()
        advance, _ = step.handle(GameObject("Bob"), "fig")
        assert advance is True and picked == ["fighter"]

    def test_bad_input_stays(self):
        step, picked = self._step()
        advance, feedback = step.handle(GameObject("Bob"), "paladin")
        assert advance is False and picked == []
        assert "listed options" in feedback


class TestGurpsSystem:

    def test_template_chargen_flow(self):
        system = GurpsSystem()
        bob = GameObject("Bob", tags=["player"])
        system.apply_baseline(bob)

        steps = system.chargen_steps()
        assert [s.key for s in steps] == ["template", "bonus skill"]

        advance, _ = steps[0].handle(bob, "infiltrator")
        assert advance is True
        assert bob.db.get("dexterity") == 13
        assert bob.db.get("skill_stealth") == 13

        # Bonus skill on a trained skill = +1.
        advance, _ = steps[1].handle(bob, "stealth")
        assert advance is True
        assert bob.db.get("skill_stealth") == 14

        system.finish_chargen(bob)
        assert bob.db.get("hp") == bob.db.get("strength") == 10
        assert bob.db.get("dodge") == 7 + (13 + 10) // 8

    def test_bonus_skill_untrained_starts_at_attribute(self):
        system = GurpsSystem()
        bob = GameObject("Bob")
        system.apply_baseline(bob)
        steps = system.chargen_steps()
        steps[0].handle(bob, "soldier")           # no fast_talk
        steps[1].handle(bob, "fast_talk")
        assert bob.db.get("skill_fast_talk") == bob.db.get("intelligence")

    def test_flat_improve_cost(self):
        assert GurpsSystem().improve_cost("stealth", 14) == 4


class TestD20System:

    def test_class_chargen(self):
        system = D20System()
        bob = GameObject("Bob")
        system.apply_baseline(bob)
        (step,) = system.chargen_steps()
        advance, _ = step.handle(bob, "rogue")
        assert advance and bob.db.get("skill_lockpicking") == 14
        system.finish_chargen(bob)
        assert bob.db.get("max_hp") == bob.db.get("health") == 12

    def test_escalating_improve_cost(self):
        system = D20System()
        assert system.improve_cost("stealth", 10) < system.improve_cost("stealth", 18)


class TestSkillDefaultsSwap:

    def test_system_owns_the_table(self):
        from realm.core.checks import SKILL_DEFAULTS, set_skill_defaults

        saved = dict(SKILL_DEFAULTS)
        try:
            set_skill_defaults(D20System().skill_defaults())
            assert SKILL_DEFAULTS["stealth"] == ("dexterity", -4)
            assert "lore" in SKILL_DEFAULTS
            set_skill_defaults(GurpsSystem().skill_defaults())
            assert SKILL_DEFAULTS["stealth"] == ("dexterity", -5)
        finally:
            set_skill_defaults(saved)


class TestAuth:

    def test_roundtrip(self):
        stored = hash_password("hunter2")
        assert stored.startswith("scrypt$")
        ok, rehash = verify_password("hunter2", stored)
        assert ok is True and rehash is False

    def test_wrong_password(self):
        stored = hash_password("hunter2")
        ok, _ = verify_password("hunter3", stored)
        assert ok is False

    def test_unique_salts(self):
        assert hash_password("x") != hash_password("x")

    def test_legacy_plaintext_flags_rehash(self):
        ok, rehash = verify_password("s1", "s1")
        assert ok is True and rehash is True
        ok, _ = verify_password("nope", "s1")
        assert ok is False

    def test_garbage_stored_fails_closed(self):
        ok, rehash = verify_password("x", "scrypt$nothex$zzz")
        assert ok is False and rehash is False
