"""Merc/Diku-lineage rules package: MercSystem + MercRuleset.

Covers the four things that make it Diku rather than the shipped GURPS/D20
packages: THAC0 descending-AC to-hit, weapon dice + damroll with no armor
mitigation, percentile skills, and XP-and-level advancement through the
shared ``grant_award`` seam (which the default still routes to character
points).
"""

from __future__ import annotations

import pytest

from realm.combat.combatant import Combatant
from realm.combat.system import RulesetRegistry
from realm.systems.definitions import apply_class
from realm.systems.merc import MercSystem
from realm.testing import Simulator


@pytest.fixture
def arena():
    sim = Simulator()
    room = sim.room("Arena")
    system = MercSystem()
    yield sim, room, system
    sim.close()


def _make(system, sim, room, name, cls):
    p = sim.player(name, location=room)
    system.apply_baseline(p)
    spec = system._classes()[cls]
    apply_class(p, (spec["blurb"], spec["stats"], spec["skills"]), cls,
                marker="character_class")
    system.finish_chargen(p)
    return p


def _merc_ruleset():
    RulesetRegistry._ensure_builtins()
    return RulesetRegistry.get("merc")()


# --- Ruleset: THAC0 / AC / damage -------------------------------------------

class TestMercRuleset:

    def test_registered_under_merc_and_diku(self):
        assert RulesetRegistry.get("merc").__name__ == "MercRuleset"
        assert RulesetRegistry.get("diku").__name__ == "MercRuleset"

    def test_lower_ac_is_harder_to_hit(self, arena, monkeypatch):
        sim, room, system = arena
        atk = Combatant(_make(system, sim, room, "Conan", "warrior"))
        soft = sim.obj("soft", location=room)
        soft.db.set("armor_class", 10)
        soft.db.set("hp", 20)
        hard = sim.obj("hard", location=room)
        hard.db.set("armor_class", 2)
        hard.db.set("hp", 20)
        # Force a mid d20 so the need formula decides, not a nat 1/20.
        monkeypatch.setattr("realm.combat.rulesets.merc.random.randint",
                            lambda a, b: 12)
        # need = thac0(20) - ac. Soft: 10 -> hit on 12>=10. Hard: 18 -> 12<18 miss.
        assert atk_hits(atk, soft) is True
        assert atk_hits(atk, hard) is False

    def test_natural_20_always_hits_1_always_misses(self, arena, monkeypatch):
        sim, room, system = arena
        atk = Combatant(_make(system, sim, room, "Conan", "warrior"))
        wall = sim.obj("wall", location=room)
        wall.db.set("armor_class", -50)      # unhittable
        wall.db.set("hp", 20)
        monkeypatch.setattr("realm.combat.rulesets.merc.random.randint",
                            lambda a, b: 20)
        assert atk_hits(atk, wall) is True
        weak = sim.obj("weak", location=room)
        weak.db.set("armor_class", 50)       # trivially hit
        weak.db.set("hp", 20)
        monkeypatch.setattr("realm.combat.rulesets.merc.random.randint",
                            lambda a, b: 1)
        assert atk_hits(atk, weak) is False

    def test_damage_is_dice_plus_damroll_no_armor_mitigation(self, arena,
                                                             monkeypatch):
        sim, room, system = arena
        hero = _make(system, sim, room, "Conan", "warrior")   # str 16 -> +1
        atk = Combatant(hero)
        target = sim.obj("dummy", location=room)
        target.db.set("hp", 100)
        target.db.set("armor_class", -30)
        weapon = sim.obj("axe", location=room)
        weapon.db.set("damage_dice", "2d6")
        monkeypatch.setattr("realm.combat.rulesets.merc.random.randint",
                            lambda a, b: 4)                     # each die -> 4
        ruleset = _merc_ruleset()
        atkres = ruleset.roll_attack(atk, Combatant(target), weapon)
        dmg = ruleset.roll_damage(atk, Combatant(target), atkres, weapon)
        # 2d6 all 4s = 8, + str damroll ((16-14)//2 = 1) = 9. Armor irrelevant.
        assert dmg.total == 9
        before = target.db.get("hp")
        dealt = ruleset.apply_damage(Combatant(target), dmg)
        assert dealt == 9
        assert target.db.get("hp") == before - 9


def atk_hits(attacker, defender_obj):
    return _merc_ruleset().roll_attack(attacker, Combatant(defender_obj)).hit


# --- System: chargen, AC, skills --------------------------------------------

class TestMercSystem:

    def test_chargen_sets_class_hp_and_stats(self, arena):
        sim, room, system = arena
        warrior = _make(system, sim, room, "Conan", "warrior")
        assert warrior.db.get("level") == 1
        assert warrior.db.get("hp") == 10          # hit die 10 + con bonus 0
        assert warrior.db.get("strength") == 16
        assert warrior.db.get("thac0") == 20
        mage = _make(system, sim, room, "Merlin", "mage")
        assert mage.db.get("hp") == 4              # d4 class, fragile
        assert mage.db.get("max_mana") > 100       # casters get mana

    def test_worn_armor_lowers_ac(self, arena):
        sim, room, system = arena
        hero = _make(system, sim, room, "Conan", "warrior")
        base = hero.db.get("armor_class")
        plate = sim.obj("plate mail", location=hero)
        plate.add_tag("worn")
        plate.db.set("ac_apply", 8)
        system.recompute_ac(hero)
        assert hero.db.get("armor_class") == base - 8

    def test_percentile_skill_check(self, arena, monkeypatch):
        sim, room, system = arena
        hero = _make(system, sim, room, "Conan", "warrior")   # melee 40
        monkeypatch.setattr("realm.systems.merc.random.randint",
                            lambda a, b: 35)
        assert system.resolve_check(hero, "melee", 0).success       # 35 <= 40
        monkeypatch.setattr("realm.systems.merc.random.randint",
                            lambda a, b: 55)
        assert not system.resolve_check(hero, "melee", 0).success   # 55 > 40

    def test_untrained_skill_almost_always_fails(self, arena, monkeypatch):
        sim, room, system = arena
        hero = _make(system, sim, room, "Conan", "warrior")   # no lockpicking
        monkeypatch.setattr("realm.systems.merc.random.randint",
                            lambda a, b: 10)
        # dexterity 13 - 80 penalty, clamped to 0 -> nothing beats it
        assert not system.resolve_check(hero, "lockpicking", 0).success


# --- Advancement: the shared grant_award seam -------------------------------

class TestAdvancement:

    def test_award_banks_xp_and_levels_up(self, arena):
        sim, room, system = arena
        hero = _make(system, sim, room, "Conan", "warrior")
        hp0 = hero.db.get("hp")
        system.grant_award(hero, 1000)             # exactly one level
        assert hero.db.get("level") == 2
        assert hero.db.get("xp") == 0
        assert hero.db.get("hp") == hp0 + 6        # d10 expected roll = 6
        assert hero.db.get("thac0") == 19          # warrior: -1 per level
        assert hero.db.get("practices") >= 1

    def test_one_award_can_cross_several_levels(self, arena):
        sim, room, system = arena
        hero = _make(system, sim, room, "Conan", "warrior")
        # 1000 (1->2) + 2000 (2->3) = 3000, with 500 left over.
        system.grant_award(hero, 3500)
        assert hero.db.get("level") == 3
        assert hero.db.get("xp") == 500

    def test_partial_award_does_not_level(self, arena):
        sim, room, system = arena
        hero = _make(system, sim, room, "Conan", "warrior")
        system.grant_award(hero, 400)
        assert hero.db.get("level") == 1
        assert hero.db.get("xp") == 400

    def test_default_grant_award_banks_character_points(self, arena):
        """The ABC default (point-buy) is untouched: a GURPS-style system's
        kill reward is still character points, not XP."""
        sim, room, system = arena
        from realm.systems.gurps import GurpsSystem
        mage = sim.player("Merlin", location=room)
        GurpsSystem().grant_award(mage, 7)
        assert mage.db.get("character_points") == 7
        assert mage.db.get("xp") is None
