"""Merc/Diku-lineage rules package: MercSystem + MercRuleset.

Covers the four things that make it Diku rather than the shipped GURPS/D20
packages: THAC0 descending-AC to-hit, weapon dice + damroll with no armor
mitigation, percentile skills, and XP-and-level advancement through the
shared ``grant_award`` seam (which the default still routes to character
points).
"""

from __future__ import annotations

import pytest

from realm.games.merc.system import MercSystem
from realm.std.combat.combatant import Combatant
from realm.std.combat.system import RulesetRegistry
from realm.std.rules.definitions import apply_class
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
        monkeypatch.setattr("realm.games.merc.ruleset.random.randint",
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
        monkeypatch.setattr("realm.games.merc.ruleset.random.randint",
                            lambda a, b: 20)
        assert atk_hits(atk, wall) is True
        weak = sim.obj("weak", location=room)
        weak.db.set("armor_class", 50)       # trivially hit
        weak.db.set("hp", 20)
        monkeypatch.setattr("realm.games.merc.ruleset.random.randint",
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
        monkeypatch.setattr("realm.games.merc.ruleset.random.randint",
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
        # ROM's and Merc's new_char: every class starts with 20 hit points;
        # the hit die tells from level 2 (a 4-hp mage died to one fido).
        assert warrior.db.get("hp") == warrior.db.get("max_hp") == 20
        assert warrior.db.get("strength") == 16
        assert warrior.db.get("thac0") == 20
        mage = _make(system, sim, room, "Merlin", "mage")
        assert mage.db.get("hp") == 20
        assert mage.db.get("max_mana") > 100       # casters get mana
        # ROM's nanny: 5 practices and 3 training sessions to start with.
        assert (mage.db.practices, mage.db.trains) == (5, 3)

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
        monkeypatch.setattr("realm.games.merc.system.random.randint",
                            lambda a, b: 35)
        assert system.resolve_check(hero, "melee", 0).success       # 35 <= 40
        monkeypatch.setattr("realm.games.merc.system.random.randint",
                            lambda a, b: 55)
        assert not system.resolve_check(hero, "melee", 0).success   # 55 > 40

    def test_untrained_skill_almost_always_fails(self, arena, monkeypatch):
        sim, room, system = arena
        hero = _make(system, sim, room, "Conan", "warrior")   # no lockpicking
        monkeypatch.setattr("realm.games.merc.system.random.randint",
                            lambda a, b: 10)
        # dexterity 13 - 80 penalty, clamped to 0 -> nothing beats it
        assert not system.resolve_check(hero, "lockpicking", 0).success


# --- Advancement: the shared grant_award seam -------------------------------

class TestAdvancement:

    def test_award_banks_xp_and_levels_up(self, arena):
        sim, room, system = arena
        hero = _make(system, sim, room, "Conan", "warrior")
        hp0 = hero.db.get("hp")
        sim.seen(hero)
        system.grant_award(hero, 1000)             # exactly one level
        seen = sim.seen(hero)
        assert hero.db.get("level") == 2
        assert hero.db.get("xp") == 0
        assert hero.db.get("hp") == hp0 + 6        # d10 expected roll = 6
        assert hero.db.get("thac0") == 19          # warrior: -1 per level
        assert hero.db.get("practices") == 5 + 1   # ROM's 5 at creation, 1 a level
        # What happened, said plainly (ROM's "You raise a level!!" and what
        # it gained).
        assert seen == ["You gain 1000 experience.",
                        "You raise a level!!  You are now level 2.",
                        "You gain 6 hit points, 1 practice and 1 training session. "
                        "Your THAC0 is now 19."]

    def test_score_shows_practices_and_training_sessions(self, arena):
        # What a level brought, where the player looks (ROM's score: "You
        # have 1 practices and 1 training sessions.").
        sim, room, system = arena
        hero = _make(system, sim, room, "Conan", "warrior")
        assert "Practices: 5   Training sessions: 3" in system.score_lines(hero)
        system.grant_award(hero, 1000)
        assert "Practices: 6   Training sessions: 4" in system.score_lines(hero)

    def test_a_caster_hears_its_mana(self, arena):
        sim, room, system = arena
        mage = _make(system, sim, room, "Merlin", "mage")
        sim.seen(mage)
        system.grant_award(mage, 1000)
        assert sim.seen(mage)[-1] == \
            "You gain 2 hit points, 10 mana, 2 practices and 1 training session."

    def test_low_levels_earn_more_as_in_rom(self, arena):
        # ROM's xp_compute, for each member: below level 6,
        # xp = 10 * xp / (level + 4). The kill's worth is unchanged.
        sim, room, system = arena
        hero = _make(system, sim, room, "Conan", "warrior")
        fido = sim.obj("fido", location=room, tags=["npc"])
        fido.db.level, fido.db.points = 0, 100
        assert system.death_award(fido, hero) == 85
        assert system.share_award(85, [hero]) == [(hero, 170)]   # doubled at level 1
        hero.db.level = 2
        assert system.share_award(70, [hero]) == [(hero, 116)]   # 70 * 10 / 6
        hero.db.level = 6
        assert system.share_award(100, [hero]) == [(hero, 100)]  # no bonus from 6

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
        from realm.games.gurps.system import GurpsSystem
        mage = sim.player("Merlin", location=room)
        GurpsSystem().grant_award(mage, 7)
        assert mage.db.get("character_points") == 7
        assert mage.db.get("xp") is None
