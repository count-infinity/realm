"""
MUD_PLAN step 4.2: the Merc class skills.

The merc-classic pack ships kick, bash, backstab, rescue, disarm and trip
as ability_defs (each a ``check`` on the skill of the same name and a
cooldown); MercRuleset turns hits aside with dodge, parry and shield
block, and gives warriors second and third attacks.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.testing import Simulator

MERC = "realm.games.merc.system.MercSystem"


@pytest.fixture
async def sim(monkeypatch):
    from realm.packs import import_pack
    s = Simulator(game_system=MERC)
    await import_pack("merc-classic", s.store)
    monkeypatch.setattr("realm.std.abilities.abilities.random.randint", lambda a, b: b)
    try:
        yield s
    finally:
        s.world.services["combat"].stop_all()
        s.close()


def _checks(passing: set[str] | bool):
    """Every check passes (True), fails (False), or passes for the named skills."""
    from realm.std.rules.checks import checks

    def resolve(actor, skill, mod=0, **kw):
        ok = passing if isinstance(passing, bool) else skill in passing
        return SimpleNamespace(success=ok, margin=1 if ok else -1, critical=False,
                               roll=10, effective=50, skill=skill)
    checks().resolver = resolve


async def _made(sim, name, cls, room, **attrs):
    rules = sim.game_system
    player = sim.player(name, location=room)
    rules.apply_baseline(player)
    rules.chargen_steps()[0].handle(player, cls)
    rules.finish_chargen(player)
    await rules.outfit_new_character(player, sim.store)
    for key, value in attrs.items():
        player.db.set(key, value)
    return player


def _rat(sim, room, name="rat", **attrs):
    stats = dict(hp=60, max_hp=60, level=1, thac0=20, armor_class=10)
    stats.update(attrs)
    return sim.obj(name, location=room, tags=["npc"], **stats)


def _text(sim, player):
    return "\n".join(sim.seen(player))


class TestKickAndBash:

    async def test_a_warrior_kicks(self, sim):
        room = sim.room("Yard")
        pat = await _made(sim, "Pat", "warrior", room, level=4)
        rat = _rat(sim, room)
        _checks(True)
        await sim.do(pat, "kick rat")
        assert rat.db.hp == 56                       # 1d{level}, rolled high
        assert pat.has_tag("in_combat")              # a kick starts the fight

    async def test_a_missed_kick_does_nothing(self, sim):
        room = sim.room("Yard")
        pat = await _made(sim, "Pat", "warrior", room)
        rat = _rat(sim, room)
        _checks(False)
        await sim.do(pat, "kick rat")
        assert rat.db.hp == 60
        assert "Your kick misses" in _text(sim, pat)

    async def test_a_mage_cannot_kick(self, sim):
        room = sim.room("Yard")
        pat = await _made(sim, "Pat", "mage", room)
        rat = _rat(sim, room)
        _checks(True)
        await sim.do(pat, "kick rat")
        assert rat.db.hp == 60

    async def test_bash_stuns(self, sim):
        room = sim.room("Yard")
        pat = await _made(sim, "Pat", "warrior", room)
        rat = _rat(sim, room)
        _checks(True)
        await sim.do(pat, "bash rat")
        assert rat.db.hp < 60
        assert rat.has_tag("stunned")


class TestBackstab:

    async def test_a_thief_backstabs_an_unaware_target(self, sim):
        room = sim.room("Alley")
        pat = await _made(sim, "Pat", "thief", room)
        rat = _rat(sim, room)
        _checks(True)
        await sim.do(pat, "backstab rat")
        assert rat.db.hp <= 60 - 8                    # 1d4 dagger, doubled and more

    async def test_backstab_needs_a_piercing_weapon(self, sim):
        room = sim.room("Alley")
        pat = await _made(sim, "Pat", "thief", room)
        dagger = next(o for o in pat.contents if o.has_tag("wielded"))
        dagger.db.damage_type = "bludgeoning"
        rat = _rat(sim, room)
        _checks(True)
        await sim.do(pat, "backstab rat")
        assert rat.db.hp == 60
        assert "You need to wield a piercing weapon to backstab." in _text(sim, pat)

    async def test_backstab_needs_a_target_not_fighting(self, sim):
        room = sim.room("Alley")
        pat = await _made(sim, "Pat", "thief", room)
        rat = _rat(sim, room)
        rat.add_tag("in_combat")
        _checks(True)
        await sim.do(pat, "backstab rat")
        assert rat.db.hp == 60
        assert "rat is too alert" in _text(sim, pat)


class TestRescueDisarmTrip:

    async def test_rescue_takes_the_attacker_off_an_ally(self, sim):
        room = sim.room("Yard")
        pat = await _made(sim, "Pat", "warrior", room)
        sam = await _made(sim, "Sam", "mage", room)
        rat = _rat(sim, room)
        combat = sim.world.services["combat"]
        encounter = await combat.initiate(rat, sam)
        assert encounter.get(rat.id).target_id == sam.id
        _checks(True)
        await sim.do(pat, "rescue sam")
        assert encounter.get(rat.id).target_id == pat.id
        assert encounter.get(pat.id).target_id == rat.id
        assert "You rescue Sam" in _text(sim, pat)

    async def test_a_failed_rescue_changes_nothing(self, sim):
        room = sim.room("Yard")
        pat = await _made(sim, "Pat", "warrior", room)
        sam = await _made(sim, "Sam", "mage", room)
        rat = _rat(sim, room)
        combat = sim.world.services["combat"]
        encounter = await combat.initiate(rat, sam)
        _checks(False)
        await sim.do(pat, "rescue sam")
        assert encounter.get(rat.id).target_id == sam.id

    async def test_disarm_drops_the_weapon(self, sim):
        room = sim.room("Yard")
        pat = await _made(sim, "Pat", "warrior", room, level=10)
        rat = _rat(sim, room, name="bandit")
        sword = sim.obj("a rusty sword", location=rat, tags=["thing", "weapon", "wielded"])
        _checks(True)
        await sim.do(pat, "disarm bandit")
        assert sword.location is room and not sword.has_tag("wielded")

    async def test_trip_puts_the_victim_down(self, sim):
        room = sim.room("Yard")
        pat = await _made(sim, "Pat", "thief", room)
        rat = _rat(sim, room)
        _checks(True)
        await sim.do(pat, "trip rat")
        assert rat.has_tag("resting")


class TestPassiveDefenses:

    async def _swing(self, sim, defender_skills, wear=()):
        from realm.std.combat.combatant import clear_combatant_cache
        clear_combatant_cache()
        room = sim.room("Pit")
        attacker = _rat(sim, room, name="ogre", thac0=1)
        target = await _made(sim, "Pat", "warrior", room)
        for skill, level in defender_skills.items():
            target.db.set(f"skill_{skill}", level)
        for slot in wear:
            sim.obj(f"a {slot}", location=target, tags=["thing", "wearable", "worn"], slot=slot)
        combat = sim.world.services["combat"]
        return await combat.combat_system.attack(attacker, target), target

    async def test_a_dodge_turns_a_hit_into_a_miss(self, sim, monkeypatch):
        monkeypatch.setattr("realm.games.merc.ruleset.random.randint", lambda a, b: 15)
        _checks({"dodge"})
        result, target = await self._swing(sim, {"dodge": 50, "parry": 0, "shield_block": 0})
        assert not result.success
        assert "dodge" in result.messages["defender_msg"]
        assert target.db.hp == target.db.max_hp

    async def test_parry_needs_a_weapon_and_shield_block_a_shield(self, sim, monkeypatch):
        monkeypatch.setattr("realm.games.merc.ruleset.random.randint", lambda a, b: 15)
        _checks({"parry", "shield_block"})
        result, _t = await self._swing(sim, {"dodge": 0, "parry": 50, "shield_block": 50})
        assert not result.success and "parry" in result.messages["defender_msg"]
        _checks({"shield_block"})
        result, _t = await self._swing(sim, {"dodge": 0, "parry": 50, "shield_block": 50},
                                       wear=("shield",))
        assert not result.success and "block" in result.messages["defender_msg"]
        result, _t = await self._swing(sim, {"dodge": 0, "parry": 50, "shield_block": 50})
        assert result.success                        # no shield worn: no block

    async def test_untrained_defenders_do_not_defend(self, sim, monkeypatch):
        monkeypatch.setattr("realm.games.merc.ruleset.random.randint", lambda a, b: 15)
        _checks(True)
        result, _t = await self._swing(sim, {"dodge": 0, "parry": 0, "shield_block": 0})
        assert result.success


class TestExtraAttacks:

    async def test_a_warrior_gets_a_second_attack(self, sim):
        room = sim.room("Pit")
        pat = await _made(sim, "Pat", "warrior", room)
        rules = sim.world.services["combat"].combat_system.ruleset
        _checks({"second_attack"})
        assert rules.extra_attacks(pat) == 1
        pat.db.skill_third_attack = 40
        _checks({"second_attack", "third_attack"})
        assert rules.extra_attacks(pat) == 2
        _checks(set())
        assert rules.extra_attacks(pat) == 0

    async def test_the_encounter_swings_again(self, sim, monkeypatch):
        monkeypatch.setattr("realm.games.merc.ruleset.random.randint", lambda a, b: 15)
        room = sim.room("Pit")
        pat = await _made(sim, "Pat", "warrior", room)
        rat = _rat(sim, room, hp=500, max_hp=500)
        swings = []
        system = sim.world.services["combat"].combat_system
        original = system.attack

        async def counting(attacker, defender, **kw):
            if attacker is pat:
                swings.append(1)
            return await original(attacker, defender, **kw)

        monkeypatch.setattr(system, "attack", counting)
        _checks({"second_attack"})
        encounter = await sim.world.services["combat"].initiate(pat, rat)
        from realm.std.combat.maneuver import QueuedAction
        encounter.queue(pat, QueuedAction("attack", target_id=rat.id))
        await encounter.resolve_round()
        assert len(swings) == 2


class TestTheList:

    @pytest.mark.parametrize("cls,expected", [
        ("warrior", {"kick", "bash", "rescue"}),
        ("barbarian", {"kick"}),
        ("thief", {"backstab", "trip"}),
        ("cleric", set()),
    ])
    async def test_abilities_lists_what_the_class_can_use_at_level_one(self, sim, cls, expected):
        room = sim.room("Hall")
        pat = await _made(sim, "Pat", cls, room)
        await sim.do(pat, "abilities")
        out = _text(sim, pat)
        for name in {"kick", "bash", "backstab", "rescue", "disarm", "trip"}:
            assert (f"  {name} " in out) == (name in expected), (cls, name, out)

    def test_class_skills_match_the_pack(self):
        from realm.games.merc import MERC_CLASSES
        assert {"kick", "bash", "rescue", "disarm", "second_attack"} <= set(
            MERC_CLASSES["warrior"]["skills"])
        assert {"backstab", "trip", "disarm"} <= set(MERC_CLASSES["thief"]["skills"])
        assert "kick" in MERC_CLASSES["barbarian"]["skills"]
