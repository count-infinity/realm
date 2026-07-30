"""The generic ability mechanism (systems.abilities) under spells/skills/shouts.

The thesis under test: a spell and a "rally cry" are the SAME object with
different data. Both are ability_defs invoked through one pipeline —
gate -> propagate -> pay a cost spec -> apply an effect-spec list, with
damage effects firing the shared, interceptable combat:on_damage event.
Nothing here is genre-specific: cost is a spec (not hardcoded mana),
targeting includes the room, effects parameterize engine behaviors.
"""

from __future__ import annotations

import pytest

from realm.combat.manager import CombatManager, set_combat_manager
from realm.combat.rulesets.merc import MercRuleset
from realm.combat.system import CombatSystem
from realm.core.behaviors import Behavior
from realm.core.objects import GameObject
from realm.systems import MercSystem, set_game_system
from realm.systems.abilities import (
    can_invoke,
    find_ability_def,
    invoke_ability,
    list_ability_defs,
)
from realm.testing import Simulator


def _ability(sim, name, **attrs):
    obj = GameObject(name=name, tags=["ability_def"])
    for k, v in attrs.items():
        obj.db.set(k, v)
    sim.add(obj)
    return obj


def _char(sim, room, name, **attrs):
    p = sim.player(name, location=room)
    for k, v in attrs.items():
        p.db.set(k, v)
    return p


@pytest.fixture
def arena():
    sim = Simulator()
    mgr = CombatManager(CombatSystem(ruleset=MercRuleset()),
                        beat_min=4.0, beat_max=120.0, beat_default=15.0)
    set_combat_manager(mgr)
    set_game_system(MercSystem())
    room = sim.room("Field")
    yield sim, room
    mgr.stop_all()
    set_combat_manager(None)
    set_game_system(None)
    sim.close()


# --- spell and skill are the same mechanism ---------------------------------

@pytest.mark.asyncio
class TestSpellEqualsSkill:

    async def test_rally_cry_is_a_spell_with_different_data(self, arena):
        # A "rally cry" SKILL: no mana, a per-day limit, a room target, and
        # a +2 modifier effect. Same invoke_ability a fireball uses.
        sim, room = arena
        rally = _ability(
            sim, "rally cry",
            cost={"per_day": 2},
            target="room",
            effects=[{"type": "behavior", "behavior_id": "modifier_effect",
                      "params": {"kind": "rallied", "duration": 30,
                                 "check_mods": {"all": 2}}}])
        captain = _char(sim, room, "Captain")
        ally = _char(sim, room, "Grunt")

        action = await invoke_ability(captain, rally, verb="shout")
        assert action is not None and action.applied
        # Everyone in the room (captain + ally) is rallied.
        for who in (captain, ally):
            assert any(getattr(b, "kind", None) == "rallied"
                       for b in who.get_behaviors())
        # The room-wide message reads as a shout, not a cast.
        assert any("shout" in m.lower() for m in sim.seen(captain))

    async def test_per_day_limit_refuses_the_third_use(self, arena):
        sim, room = arena
        rally = _ability(sim, "rally cry", cost={"per_day": 2},
                         target="room",
                         effects=[{"type": "behavior",
                                   "behavior_id": "modifier_effect",
                                   "params": {"kind": "rallied"}}])
        captain = _char(sim, room, "Captain")
        assert await invoke_ability(captain, rally, verb="shout") is not None
        assert await invoke_ability(captain, rally, verb="shout") is not None
        # Third use today is refused (counter hit the cap).
        assert await invoke_ability(captain, rally, verb="shout") is None
        assert captain.db.get("used_ability_rally_cry") == 2


# --- cost specs -------------------------------------------------------------

@pytest.mark.asyncio
class TestCostSpecs:

    async def test_mana_pool_spec_and_legacy_mana_are_equivalent(self, arena):
        sim, room = arena
        spec = _ability(sim, "spark", cost={"pool": "mana", "n": 10},
                        target="self",
                        effects=[{"type": "heal", "dice": "1d1"}])
        legacy = _ability(sim, "glow", mana=10, target="self",
                          effects=[{"type": "heal", "dice": "1d1"}])
        mage = _char(sim, room, "Mage", mana=100, max_hp=50, hp=40,
                     character_class="mage", level=20)
        await invoke_ability(mage, spec, verb="use")
        assert mage.db.get("mana") == 90
        await invoke_ability(mage, legacy, verb="use")
        assert mage.db.get("mana") == 80          # both charge the mana pool

    async def test_stamina_pool_names_its_own_cost_key(self, arena):
        sim, room = arena
        kick = _ability(sim, "power kick", cost={"pool": "stamina", "n": 5},
                        target="self", effects=[{"type": "heal", "dice": "1d1"}])
        monk = _char(sim, room, "Monk", stamina=8, hp=10, max_hp=10)
        action = await invoke_ability(monk, kick, verb="use")
        assert action is not None
        assert monk.db.get("stamina") == 3
        assert action.extra.get("stamina_cost") == 5    # per-pool ward hook


# --- eligibility ------------------------------------------------------------

class TestEligibility:

    def test_skill_requirement_gates_a_maneuver(self):
        sim = Simulator()
        try:
            disarm = _ability(sim, "disarm",
                              skill_req={"skill": "melee", "min": 12})
            room = sim.room("Yard")
            novice = _char(sim, room, "Novice", skill_melee=8)
            veteran = _char(sim, room, "Vet", skill_melee=15)
            assert not can_invoke(novice, disarm)
            assert can_invoke(veteran, disarm)
        finally:
            sim.close()


# --- damage abilities fire the interceptable damage event -------------------

@pytest.mark.asyncio
class TestDamageIsInterceptable:

    async def test_a_room_ward_nerfs_an_ability_fireball(self, arena, monkeypatch):
        # The headline: spell/ability damage funnels through combat:on_damage,
        # so a room's "sanctuary" behavior halves it exactly as it would a
        # melee swing. (Proves the damage event is unified, not combat-only.)
        sim, room = arena

        class Sanctuary(Behavior):
            behavior_id = "sanctuary"

            async def on_check(self, obj, action):
                if action.action_type == "combat:on_damage":
                    action.add_data("damage", action.extra.get("damage", 0) // 2)

        room.add_behavior(Sanctuary())
        fireball = _ability(sim, "fireball", mana=0, target="victim",
                            effects=[{"type": "damage", "dice": "6d6",
                                      "damage_type": "fire"}])
        mage = _char(sim, room, "Mage", mana=100, character_class="mage",
                     level=20)
        target = sim.obj("dummy", location=room)
        target.db.set("hp", 100)
        monkeypatch.setattr("realm.systems.abilities.random.randint",
                            lambda a, b: 4)               # 6d6 -> 24
        action = await invoke_ability(mage, fireball, target, verb="cast",
                                      domain="spell")
        assert action.extra["dealt"] == 12                # halved by the room
        assert target.db.get("hp") == 88


# --- the def registry sees both flavors -------------------------------------

class TestRegistry:

    def test_find_ability_spans_spell_and_ability_tags(self):
        sim = Simulator()
        try:
            _ability(sim, "war cry")                       # ability_def
            spell = GameObject(name="fireball", tags=["spell_def"])
            sim.add(spell)
            assert find_ability_def("war cry") is not None
            assert find_ability_def("fireball") is spell   # spell_def counts
            names = {o.name for o in list_ability_defs()}
            assert {"war cry", "fireball"} <= names
        finally:
            sim.close()
