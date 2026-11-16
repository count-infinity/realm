"""
MUD_PLAN step 4.1: an ``ability_def`` is a command.

When no command matches, a typed verb that names an ability_def (or one of
its ``aliases``) the player may invoke runs it, with the rest of the line
as the target. Spells keep ``cast``. A cost may carry a ``cooldown`` in
world beats; an effect of type ``check`` rolls a skill and stops the
effects after it on a failure.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.testing import Simulator


@pytest.fixture
def sim():
    s = Simulator()
    try:
        yield s
    finally:
        s.world.services["combat"].stop_all()
        s.close()


def _ability(sim, name, **attrs):
    attrs.setdefault("target", "victim")
    attrs.setdefault("effects", [{"type": "damage", "dice": "3", "damage_type": "bludgeoning",
                                  "magical": False}])
    return sim.obj(name, tags=["ability_def"], **attrs)


def _arena(sim):
    room = sim.room("Yard")
    pat = sim.player("Pat", location=room, hp=20, max_hp=20, level=1)
    rat = sim.obj("rat", location=room, tags=["npc"], hp=20, max_hp=20)
    return room, pat, rat


def _always(success: bool):
    from realm.std.rules.checks import checks
    checks().resolver = lambda actor, skill, mod=0, **kw: SimpleNamespace(
        success=success, margin=1 if success else -1, critical=False, roll=10)


class TestAbilitiesAsCommands:

    async def test_kick_rat_runs_the_kick_ability(self, sim):
        _ability(sim, "kick")
        _room, pat, rat = _arena(sim)
        await sim.do(pat, "kick rat")
        assert rat.db.hp == 17
        assert any("kick" in line for line in sim.seen(pat))

    async def test_an_alias_names_it_too(self, sim):
        _ability(sim, "headbutt", aliases=["butt"])
        _room, pat, rat = _arena(sim)
        await sim.do(pat, "butt rat")
        assert rat.db.hp == 17

    async def test_without_a_target_it_uses_the_spells_rule(self, sim):
        _ability(sim, "kick")
        _room, pat, _rat = _arena(sim)
        await sim.do(pat, "kick")
        assert any("at whom" in line for line in sim.seen(pat))

    async def test_an_unseen_target_is_said_so(self, sim):
        _ability(sim, "kick")
        _room, pat, _rat = _arena(sim)
        await sim.do(pat, "kick dragon")
        assert "You don't see 'dragon' here." in sim.seen(pat)

    async def test_a_victim_is_a_creature_not_its_corpse(self, sim):
        # MUD_PLAN step 17: `kick fido` beside "the corpse of fido dog"
        # kicks the fido; with only the corpse there, nothing is kicked.
        _ability(sim, "kick")
        room, pat, _rat = _arena(sim)
        corpse = sim.obj("corpse of fido dog", location=room, tags=["thing", "container"])
        fido = sim.obj("fido dog", location=room, tags=["npc"], hp=20, max_hp=20)
        await sim.do(pat, "kick fido")
        assert fido.db.hp == 17
        await sim.do(pat, "kill fido")                  # and `kill` the same
        assert "You will attack fido dog" in "\n".join(sim.seen(pat))
        sim.world.services["combat"].stop_all()
        fido.location = None
        sim.seen(pat)
        await sim.do(pat, "kick fido")
        assert "You don't see 'fido' here." in sim.seen(pat)
        assert corpse.location is room

    async def test_spells_are_not_commands(self, sim):
        sim.obj("zot", tags=["spell_def"], target="victim", damage_dice="3")
        _room, pat, rat = _arena(sim)
        await sim.do(pat, "zot rat")
        assert rat.db.hp == 20

    async def test_a_class_ability_is_not_a_command_for_other_classes(self, sim):
        _ability(sim, "kick", classes=["warrior"])
        _room, pat, rat = _arena(sim)
        pat.db.character_class = "mage"
        await sim.do(pat, "kick rat")
        assert rat.db.hp == 20
        pat.db.character_class = "warrior"
        await sim.do(pat, "kick rat")
        assert rat.db.hp == 17

    async def test_an_unknown_verb_still_reaches_softcode(self, sim):
        _ability(sim, "kick")
        room, pat, _rat = _arena(sim)
        drum = sim.obj("drum", location=room)
        drum.db.cmd_dance = "$dance: pemit(enactor, 'You dance to the drum.')"
        await sim.do(pat, "dance")
        assert "You dance to the drum." in sim.seen(pat)

    async def test_abilities_lists_what_you_can_use_with_cost(self, sim):
        _ability(sim, "kick", classes=["warrior"], cost={"cooldown": 2})
        _ability(sim, "smite", classes=["paladin"])
        _ability(sim, "roar", cost={"pool": "hp", "n": 2})
        sim.obj("zot", tags=["spell_def"], damage_dice="3")
        _room, pat, _rat = _arena(sim)
        pat.db.character_class = "warrior"
        await sim.do(pat, "ab")
        out = "\n".join(sim.seen(pat))
        assert "kick" in out and "2 beats" in out
        assert "roar" in out and "2 hp" in out
        assert "smite" not in out and "zot" not in out


class TestCooldown:

    async def test_a_cooldown_refuses_the_second_use_and_allows_the_third(self, sim, monkeypatch):
        clock = [1000.0]
        monkeypatch.setattr("realm.std.abilities.abilities.time.time", lambda: clock[0])
        _ability(sim, "kick", cost={"cooldown": 2})
        _room, pat, rat = _arena(sim)
        await sim.do(pat, "kick rat")
        assert rat.db.hp == 17
        sim.seen(pat)
        await sim.do(pat, "kick rat")
        assert rat.db.hp == 17
        assert "You are not ready to kick again yet." in sim.seen(pat)
        clock[0] += 2 * sim.world.setting("WORLD_BEAT")
        await sim.do(pat, "kick rat")
        assert rat.db.hp == 14

    async def test_a_cooldown_beside_a_pool_cost(self, sim, monkeypatch):
        monkeypatch.setattr("realm.std.abilities.abilities.time.time", lambda: 1000.0)
        _ability(sim, "roar", cost={"pool": "mana", "n": 3, "cooldown": 1})
        _room, pat, rat = _arena(sim)
        pat.db.mana, pat.db.max_mana = 10, 10
        await sim.do(pat, "roar rat")
        await sim.do(pat, "roar rat")
        assert pat.db.mana == 7                     # the refused second use cost nothing
        assert pat.db.ability_ready["roar"] > 1000.0


class TestCheckEffect:

    async def test_a_failed_check_deals_no_damage(self, sim):
        _ability(sim, "kick", fail_msg="Your kick misses.",
                 effects=[{"type": "check", "skill": "kick", "on_fail": "stop"},
                          {"type": "damage", "dice": "3", "damage_type": "bludgeoning",
                           "magical": False}])
        _room, pat, rat = _arena(sim)
        _always(False)
        await sim.do(pat, "kick rat")
        assert rat.db.hp == 20
        seen = sim.seen(pat)
        assert "Your kick misses." in seen
        assert not any(line.startswith("You kick") for line in seen)

    async def test_a_passed_check_goes_on(self, sim):
        _ability(sim, "kick", effects=[
            {"type": "check", "skill": "kick", "on_fail": "stop"},
            {"type": "damage", "dice": "3", "damage_type": "bludgeoning", "magical": False}])
        _room, pat, rat = _arena(sim)
        _always(True)
        await sim.do(pat, "kick rat")
        assert rat.db.hp == 17

    async def test_effects_before_the_check_still_apply(self, sim):
        _ability(sim, "lunge", effects=[
            {"type": "damage", "dice": "2", "damage_type": "piercing", "magical": False},
            {"type": "check", "skill": "lunge"},
            {"type": "damage", "dice": "5", "damage_type": "piercing", "magical": False}])
        _room, pat, rat = _arena(sim)
        _always(False)
        await sim.do(pat, "lunge rat")
        assert rat.db.hp == 18

    async def test_damage_dice_may_scale_with_level(self, sim):
        _ability(sim, "kick", effects=[
            {"type": "damage", "dice": "{level}", "damage_type": "bludgeoning",
             "magical": False}])
        _room, pat, rat = _arena(sim)
        pat.db.level = 6
        await sim.do(pat, "kick rat")
        assert rat.db.hp == 14
