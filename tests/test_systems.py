"""
Tests for the GameSystem abstraction (the swappable GURPS/D20 rules
package), chargen steps, and password hashing.
"""

from __future__ import annotations

import pytest

from realm.core.objects import GameObject
from realm.games.d20.system import D20System
from realm.games.gurps.system import GurpsSystem
from realm.std.accounts.auth import hash_password, verify_password
from realm.std.rules.system import ChoiceStep, resolve_game_system


class TestResolveGameSystem:
    """GAME_SYSTEM is a dotted import path to a GameSystem subclass."""

    def test_resolve_builtin_paths(self):
        assert isinstance(
            resolve_game_system("realm.games.gurps.system.GurpsSystem"), GurpsSystem)
        assert isinstance(
            resolve_game_system("realm.games.d20.system.D20System"), D20System)

    def test_bad_path_raises(self):
        with pytest.raises(ValueError):
            resolve_game_system("realm.games.FateSystem")   # no such class
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
        # build_world installs the selected system's table on the world.
        from realm.std.rules.checks import checks
        from realm.testing import Simulator

        with Simulator(game_system=D20System):
            assert checks().skill_defaults["stealth"] == ("dexterity", -4)
            assert "lore" in checks().skill_defaults
        with Simulator(game_system=GurpsSystem):
            assert checks().skill_defaults["stealth"] == ("dexterity", -5)


class TestAuth:

    def test_roundtrip(self):
        stored = hash_password("hunter2")
        assert stored.startswith("scrypt$")
        assert verify_password("hunter2", stored) is True

    def test_wrong_password(self):
        stored = hash_password("hunter2")
        assert verify_password("hunter3", stored) is False

    def test_unique_salts(self):
        assert hash_password("x") != hash_password("x")

    def test_plaintext_stored_value_is_rejected(self):
        """Plaintext storage predates 2026-07-04; such a database must be
        recreated, never matched against."""
        assert verify_password("s1", "s1") is False

    def test_garbage_stored_fails_closed(self):
        assert verify_password("x", "scrypt$nothex$zzz") is False


@pytest.mark.asyncio
class TestAuthService:
    """Identity is the account's (MUD_PLAN 6.1): ``authenticate`` returns
    an account, ``create_character`` makes a character on it."""

    def _service(self, **kw):
        from realm.std.accounts.auth import AuthService
        from tests.test_olc import MockPersistence
        pers = MockPersistence()
        return AuthService(pers, **kw), pers

    async def _account(self, pers, name="Bob", password="s2"):
        from realm.std.accounts.account import new_account
        from realm.std.accounts.auth import hash_password
        account = new_account(name, hash_password(password))
        pers.add(account)
        return account

    async def test_authenticate_roundtrip(self):
        svc, pers = self._service()
        bob = await self._account(pers)
        account, err = await svc.authenticate("Bob", "s2")
        assert account is bob and err == ""

    async def test_rate_limit_locks_and_drains(self, monkeypatch):
        clock = {"t": 0.0}
        monkeypatch.setattr("realm.std.accounts.auth.now", lambda: clock["t"])
        svc, pers = self._service(max_attempts=3, window_seconds=60)
        await self._account(pers)
        for _ in range(3):
            account, err = await svc.authenticate("Bob", "wrong")
            assert account is None
        # Locked even with the RIGHT password now.
        account, err = await svc.authenticate("Bob", "s2")
        assert account is None and "Too many failed attempts" in err
        # Window drains -> works again.
        clock["t"] = 61.0
        account, err = await svc.authenticate("Bob", "s2")
        assert account is not None

    async def test_plaintext_account_cannot_log_in(self):
        svc, pers = self._service()
        old = await self._account(pers, "Old")
        old.db.password = "plain"
        account, err = await svc.authenticate("Old", "plain")
        assert account is None and err == "Invalid password."
        assert old.db.get("password") == "plain"

    async def test_create_account_rejects_duplicates(self):
        svc, pers = self._service()
        await self._account(pers)
        account, err = await svc.create_account("Bob", "xxxx")
        assert account is None and "already exists" in err

    async def test_create_character_applies_system_baseline(self):
        svc, _pers = self._service()
        account, _ = await svc.create_account("New", "pwpw")
        player, err = await svc.create_character(account, "Newt", system=GurpsSystem())
        assert player is not None
        assert player.db.get("strength") == 10
        assert player.db.get("password") is None
        assert str(account.db.get("password")).startswith("scrypt$")

    async def test_first_character_becomes_superuser(self):
        svc, _pers = self._service()
        account, _ = await svc.create_account("Founder", "pwpw")
        first, _ = await svc.create_character(account, "Hero")
        second, _ = await svc.create_character(account, "Sidekick")
        assert first.has_tag("god") and not second.has_tag("god")


@pytest.mark.asyncio
class TestSystemStamp:

    def _service(self):
        from realm.std.accounts.auth import AuthService
        from tests.test_olc import MockPersistence
        return AuthService(MockPersistence()), None

    async def test_creation_stamps_system(self):
        svc, _ = self._service()
        account, _ = await svc.create_account("Bob", "pwpw")
        player, _ = await svc.create_character(account, "Bobby", system=D20System())
        assert player.db.get("game_system") == "d20"
