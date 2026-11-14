"""
Combat rulesets as feature declarations (KERNEL_PLAN 1.6, then 4.1).

The shipped rulesets come from the ``gurps``, ``d20`` and ``merc``
features. A second declaration of a taken name is a collision unless it
says ``replace=True``; ``RulesetRegistry.register`` is the low-level call.
"""

from __future__ import annotations

import pytest

from realm.features import Feature, FeatureError, FeatureSet, install_default, load
from realm.games.d20.ruleset import D20Ruleset
from realm.std.combat.ruleset import Ruleset
from realm.std.combat.system import RulesetRegistry


class HouseGurps(Ruleset):
    """Stands in for a game's own ruleset."""


@pytest.fixture(autouse=True)
def restore_default():
    yield
    install_default()


def _house(replace: bool) -> Feature:
    house = Feature("house", requires=["rules"])
    house.ruleset("gurps", HouseGurps, replace=replace)
    return house


class TestDefault:

    def test_shipped_rulesets_and_aliases(self):
        assert RulesetRegistry.get("d20") is D20Ruleset
        assert RulesetRegistry.get("dnd") is D20Ruleset
        assert {"gurps", "3d6", "merc", "diku"} <= set(RulesetRegistry.list_all())


class TestFeatureDeclarations:

    def test_redeclaring_a_shipped_name_is_a_collision(self):
        shipped = load(["rules", "items", "combat", "gurps"]).features
        with pytest.raises(FeatureError, match="'gurps'.*'house'"):
            FeatureSet([*shipped, _house(replace=False)])

    def test_replace_overrides_and_keeps_the_others(self):
        shipped = load(["rules", "items", "combat", "gurps", "d20", "merc"]).features
        FeatureSet([*shipped, _house(replace=True)]).install_registries()
        assert RulesetRegistry.get("gurps") is HouseGurps
        assert RulesetRegistry.get("d20") is D20Ruleset
        assert RulesetRegistry.get("merc") is not None


class TestLowLevelRegister:

    def test_taken_name_raises(self):
        with pytest.raises(ValueError, match="gurps"):
            RulesetRegistry.register("gurps", HouseGurps)

    def test_replace_true_replaces(self):
        RulesetRegistry.register("gurps", HouseGurps, replace=True)
        assert RulesetRegistry.get("gurps") is HouseGurps

    def test_same_class_again_is_allowed(self):
        RulesetRegistry.register("house", HouseGurps)
        RulesetRegistry.register("HOUSE", HouseGurps)
        assert RulesetRegistry.get("house") is HouseGurps
