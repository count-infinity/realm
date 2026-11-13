"""
RulesetRegistry (realm/combat/system.py): built-ins always load, a game's
earlier registration of a built-in name wins, and a name is never silently
replaced (KERNEL_PLAN step 1.6).
"""

from __future__ import annotations

import pytest

from realm.combat.ruleset import Ruleset
from realm.combat.system import RulesetRegistry


@pytest.fixture(autouse=True)
def fresh_registry(monkeypatch):
    """Each test starts with an empty registry that has not loaded built-ins."""
    monkeypatch.setattr(RulesetRegistry, "_rulesets", {})
    monkeypatch.setattr(RulesetRegistry, "_builtins_loaded", False)


class HouseGurps(Ruleset):
    """Stands in for a game's own ruleset."""


class TestBuiltins:

    def test_game_registering_gurps_first_keeps_the_other_builtins(self):
        RulesetRegistry.register("gurps", HouseGurps)

        assert RulesetRegistry.get("gurps") is HouseGurps
        assert RulesetRegistry.get("d20") is not None
        assert RulesetRegistry.get("merc") is not None


class TestRegister:

    def test_taken_name_raises(self):
        RulesetRegistry.get("gurps")          # loads the built-ins
        with pytest.raises(ValueError, match="gurps"):
            RulesetRegistry.register("gurps", HouseGurps)

    def test_replace_true_replaces(self):
        RulesetRegistry.get("gurps")
        RulesetRegistry.register("gurps", HouseGurps, replace=True)
        assert RulesetRegistry.get("gurps") is HouseGurps

    def test_same_class_again_is_allowed(self):
        RulesetRegistry.register("house", HouseGurps)
        RulesetRegistry.register("HOUSE", HouseGurps)
        assert RulesetRegistry.get("house") is HouseGurps
