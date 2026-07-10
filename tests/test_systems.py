"""
Tests for the GameSystem abstraction (the swappable GURPS/D20 rules
package), chargen steps, and password hashing.
"""

from __future__ import annotations

import pytest

from realm.core.objects import GameObject
from realm.server.auth import hash_password, verify_password
from realm.systems import D20System, GurpsSystem
from realm.systems.base import ChoiceStep, resolve_game_system


class TestResolveGameSystem:
    """GAME_SYSTEM is a dotted import path to a GameSystem subclass."""

    def test_resolve_builtin_paths(self):
        assert isinstance(
            resolve_game_system("realm.systems.GurpsSystem"), GurpsSystem)
        assert isinstance(
            resolve_game_system("realm.systems.D20System"), D20System)

    def test_bad_path_raises(self):
        with pytest.raises(ValueError):
            resolve_game_system("realm.systems.FateSystem")   # no such class
        with pytest.raises(ValueError):
            resolve_game_system("gurps")                      # not dotted


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


@pytest.mark.asyncio
class TestAuthService:

    def _service(self, **kw):
        from realm.server.auth import AuthService
        from tests.test_olc import MockPersistence
        pers = MockPersistence()
        return AuthService(pers, **kw), pers

    async def _account(self, pers, name="Bob", password="s2"):
        from realm.core.objects import GameObject
        from realm.server.auth import hash_password
        p = GameObject(name, tags=["player"])
        p.db.password = hash_password(password)
        pers.add(p)
        return p

    async def test_authenticate_roundtrip(self):
        svc, pers = self._service()
        bob = await self._account(pers)
        player, err = await svc.authenticate("Bob", "s2")
        assert player is bob and err == ""

    async def test_rate_limit_locks_and_drains(self):
        clock = {"t": 0.0}
        svc, pers = self._service(max_attempts=3, window_seconds=60,
                                  clock=lambda: clock["t"])
        await self._account(pers)
        for _ in range(3):
            player, err = await svc.authenticate("Bob", "wrong")
            assert player is None
        # Locked even with the RIGHT password now.
        player, err = await svc.authenticate("Bob", "s2")
        assert player is None and "Too many failed attempts" in err
        # Window drains -> works again.
        clock["t"] = 61.0
        player, err = await svc.authenticate("Bob", "s2")
        assert player is not None

    async def test_legacy_plaintext_upgraded(self):
        from realm.core.objects import GameObject
        svc, pers = self._service()
        old = GameObject("Old", tags=["player"])
        old.db.password = "plain"
        pers.add(old)
        player, err = await svc.authenticate("Old", "plain")
        assert player is old
        assert str(old.db.get("password")).startswith("scrypt$")

    async def test_create_account_rejects_duplicates(self):
        svc, pers = self._service()
        await self._account(pers)
        player, err = await svc.create_account("Bob", "x")
        assert player is None and "already exists" in err

    async def test_create_applies_system_baseline(self):
        svc, _pers = self._service()
        player, err = await svc.create_account("New", "pw",
                                               system=GurpsSystem())
        assert player is not None
        assert player.db.get("strength") == 10
        assert str(player.db.get("password")).startswith("scrypt$")

    async def test_first_character_becomes_superuser(self):
        svc, _pers = self._service()
        first, _ = await svc.create_account("Founder", "pw")
        assert first.has_tag("god")
        second, _ = await svc.create_account("Guest2", "pw")
        assert not second.has_tag("god")


class TestCheckResolution:
    """Each GameSystem owns non-combat skill resolution, not just combat."""

    def test_gurps_rolls_3d6_under(self):
        # A high skill almost always succeeds; a low one almost never —
        # over many rolls, roll-under behaviour.
        sys = GurpsSystem()
        pro = GameObject("Pro")
        pro.db.skill_stealth = 16
        oaf = GameObject("Oaf")
        oaf.db.skill_stealth = 4
        pro_wins = sum(sys.resolve_check(pro, "stealth", 0).success for _ in range(200))
        oaf_wins = sum(sys.resolve_check(oaf, "stealth", 0).success for _ in range(200))
        assert pro_wins > 180 and oaf_wins < 20

    def test_d20_rolls_high_vs_dc(self):
        sys = D20System()
        # skill "level" is a BONUS under d20: +10 clears DC 15 most rolls,
        # +0 rarely does.
        ace = GameObject("Ace")
        ace.db.skill_stealth = 10
        joe = GameObject("Joe")
        joe.db.skill_stealth = 0
        ace_wins = sum(sys.resolve_check(ace, "stealth", 0).success for _ in range(200))
        joe_wins = sum(sys.resolve_check(joe, "stealth", 0).success for _ in range(200))
        assert ace_wins > joe_wins
        # roll-high, not roll-under: the higher bonus wins, opposite of GURPS
        assert ace_wins > 100

    def test_server_installs_system_resolver(self):
        # Selecting d20 makes check() itself roll d20 (roll-high), proving
        # the resolver is wired to the GameSystem not just combat.
        from realm.core.checks import check, set_check_resolver
        try:
            set_check_resolver(D20System().resolve_check)
            hero = GameObject("Hero")
            hero.db.skill_stealth = 30  # auto-clears DC
            assert check(hero, "stealth").success is True
            assert check(hero, "stealth").roll <= 20  # a d20, not 3d6
        finally:
            set_check_resolver(None)

    def test_d20_chargen_sets_armor_class(self):
        sys = D20System()
        rogue = GameObject("Rogue")
        sys.apply_baseline(rogue)
        (step,) = sys.chargen_steps()
        step.handle(rogue, "rogue")      # DEX 16
        sys.finish_chargen(rogue)
        assert rogue.db.get("armor_class") == 13  # 10 + (16-10)//2


@pytest.mark.asyncio
class TestSystemStamp:

    def _service(self):
        from realm.server.auth import AuthService
        from tests.test_olc import MockPersistence
        return AuthService(MockPersistence()), None

    async def test_creation_stamps_system(self):
        svc, _ = self._service()
        player, _ = await svc.create_account("Bob", "pw", system=D20System())
        assert player.db.get("game_system") == "d20"
