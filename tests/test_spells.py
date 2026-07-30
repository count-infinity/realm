"""Spells as data: spell_def objects, the cast pipeline, CasterBehavior,
the importer's spec_cast mapping, and the merc-classic pack.

The design under test: a spell is ONE propagated ``spell:<name>`` action.
Requirements are announced in the payload, the check pass (wards,
softcode) may block or modify them, and the apply step enforces the FINAL
values — mana spend, saving throw, typed damage through the ruleset (so
the ``resistances`` layer fires), heals, and effect-behavior attachment.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from realm.behaviors.caster import CasterBehavior
from realm.core.behaviors import Behavior
from realm.core.objects import GameObject
from realm.systems import GurpsSystem, MercSystem, set_game_system
from realm.systems.spells import (
    cast_spell,
    find_spell_def,
    knows_spell,
)
from realm.testing import Simulator


def _spell(sim, name, **attrs):
    obj = GameObject(name=name, tags=["spell_def"])
    for k, v in attrs.items():
        obj.db.set(k, v)
    sim.add(obj)
    return obj


def _mage(sim, room, name="Merlin", mana=100, level=20):
    p = sim.player(name, location=room)
    p.db.character_class = "mage"
    p.db.level = level
    p.db.mana = mana
    return p


def _dummy(sim, room, hp=100, **attrs):
    d = sim.obj("dummy", location=room)
    d.db.set("hp", hp)
    d.db.set("max_hp", hp)
    for k, v in attrs.items():
        d.db.set(k, v)
    return d


@pytest.fixture
def world():
    sim = Simulator()
    room = sim.room("Tower")
    yield sim, room
    set_game_system(None)
    sim.close()


# --- lookup & knowledge ------------------------------------------------------

class TestSpellDefs:

    def test_exact_and_unique_prefix(self, world):
        sim, room = world
        fireball = _spell(sim, "fireball")
        _spell(sim, "fire breath")
        assert find_spell_def("FIREBALL") is fireball
        assert find_spell_def("fireb") is fireball      # unique prefix
        assert find_spell_def("fire") is None           # ambiguous
        assert find_spell_def("meteor swarm") is None

    def test_knows_spell_gates_class_and_level(self, world):
        sim, room = world
        fireball = _spell(sim, "fireball", classes=["mage"], level=15)
        mage = _mage(sim, room, level=20)
        assert knows_spell(mage, fireball)
        mage.db.level = 3
        assert not knows_spell(mage, fireball)          # too low
        mage.db.level = 20
        mage.db.character_class = "cleric"
        assert not knows_spell(mage, fireball)          # wrong class

    def test_npc_bypasses_class_gate(self, world):
        sim, room = world
        fireball = _spell(sim, "fireball", classes=["mage"], level=15)
        mob = sim.obj("dragon", location=room)
        mob.add_tag("npc")
        assert knows_spell(mob, fireball)


# --- the cast pipeline -------------------------------------------------------

@pytest.mark.asyncio
class TestCasting:

    async def test_cast_spends_mana_and_deals_typed_damage(self, world,
                                                           monkeypatch):
        sim, room = world
        spell = _spell(sim, "fireball", mana=15, level=15,
                       damage_dice="6d6", damage_type="fire", save="half")
        mage = _mage(sim, room)
        target = _dummy(sim, room)
        monkeypatch.setattr("realm.systems.abilities.random.randint",
                            lambda a, b: 4)             # 6d6 all 4s = 24
        action = await cast_spell(mage, spell, target)
        assert action is not None and action.applied
        assert "hostile" in action.tags and "magic" in action.tags
        assert mage.db.get("mana") == 85                # 100 - 15
        assert target.db.get("hp") == 76                # 100 - 24
        assert action.extra["dealt"] == 24

    async def test_insufficient_mana_refuses_like_a_veto(self, world):
        sim, room = world
        spell = _spell(sim, "fireball", mana=15, damage_dice="6d6",
                       damage_type="fire")
        mage = _mage(sim, room, mana=3)
        target = _dummy(sim, room)
        action = await cast_spell(mage, spell, target)
        assert action is None
        assert mage.db.get("mana") == 3                 # nothing spent
        assert target.db.get("hp") == 100               # nothing dealt

    async def test_no_mana_pool_cannot_channel_unless_npc(self, world):
        sim, room = world
        spell = _spell(sim, "fireball", mana=15, damage_dice="2d6",
                       damage_type="fire")
        rube = sim.player("Rube", location=room)        # no mana attr at all
        target = _dummy(sim, room)
        assert await cast_spell(rube, spell, target) is None
        mob = sim.obj("dragon", location=room)
        mob.add_tag("npc")                              # spec mobs cast free
        assert (await cast_spell(mob, spell, target)) is not None

    async def test_fire_immune_target_takes_nothing(self, world, monkeypatch):
        sim, room = world
        spell = _spell(sim, "fireball", mana=15, damage_dice="6d6",
                       damage_type="fire")
        mage = _mage(sim, room)
        target = _dummy(sim, room, resistances={"fire": 0.0})
        monkeypatch.setattr("realm.systems.abilities.random.randint",
                            lambda a, b: 4)
        action = await cast_spell(mage, spell, target)
        assert action.extra["dealt"] == 0
        assert target.db.get("hp") == 100

    async def test_save_halves_damage(self, world, monkeypatch):
        sim, room = world
        set_game_system(MercSystem())
        spell = _spell(sim, "fireball", mana=15, level=15,
                       damage_dice="6d6", damage_type="fire", save="half")
        mage = _mage(sim, room)
        target = _dummy(sim, room)
        monkeypatch.setattr("realm.systems.abilities.random.randint",
                            lambda a, b: 4)             # 24 rolled
        monkeypatch.setattr(MercSystem, "saving_throw",
                            lambda self, t, level: True)
        action = await cast_spell(mage, spell, target)
        assert action.extra["saved"] is True
        assert action.extra["dealt"] == 12              # halved
        assert target.db.get("hp") == 88

    async def test_default_system_has_no_save(self, world, monkeypatch):
        sim, room = world
        set_game_system(GurpsSystem())
        spell = _spell(sim, "fireball", mana=15, damage_dice="6d6",
                       damage_type="fire", save="half")
        mage = _mage(sim, room)
        target = _dummy(sim, room)
        monkeypatch.setattr("realm.systems.abilities.random.randint",
                            lambda a, b: 4)
        action = await cast_spell(mage, spell, target)
        assert action.extra["dealt"] == 24              # full: no save concept

    async def test_ward_blocks_in_check_pass_nothing_spent(self, world):
        sim, room = world

        class NullField(Behavior):
            behavior_id = "null_field"

            async def on_check(self, obj, action):
                if action.domain == "spell":
                    action.block("The spell unravels into sparks.")

        spell = _spell(sim, "fireball", mana=15, damage_dice="6d6",
                       damage_type="fire")
        mage = _mage(sim, room)
        target = _dummy(sim, room)
        target.add_behavior(NullField())
        action = await cast_spell(mage, spell, target)
        assert action is None
        assert mage.db.get("mana") == 100               # apply never ran
        assert target.db.get("hp") == 100

    async def test_check_pass_modifies_cost_apply_enforces_final(self, world):
        sim, room = world

        class ManaWell(Behavior):
            """A room feature that makes all magic free."""
            behavior_id = "mana_well"

            async def on_check(self, obj, action):
                if action.domain == "spell":
                    action.extra["mana_cost"] = 0

        spell = _spell(sim, "fireball", mana=50, damage_dice="1d6",
                       damage_type="fire")
        mage = _mage(sim, room, mana=5)                 # can't afford 50
        target = _dummy(sim, room)
        room.add_behavior(ManaWell())
        action = await cast_spell(mage, spell, target)
        assert action is not None and action.applied    # final cost 0
        assert mage.db.get("mana") == 5

    async def test_heal_targets_ally_and_caps(self, world, monkeypatch):
        sim, room = world
        spell = _spell(sim, "cure light", mana=10, target="ally",
                       heal_dice="1d8+2")
        cleric = _mage(sim, room, name="Friar")
        wounded = sim.player("Conan", location=room)
        wounded.db.hp = 95
        wounded.db.max_hp = 100
        monkeypatch.setattr("realm.systems.abilities.random.randint",
                            lambda a, b: 8)             # 8+2 = 10 healed
        action = await cast_spell(cleric, spell, wounded)
        assert wounded.db.get("hp") == 100              # capped at max
        assert action.extra["healed"] == 10
        # With no target given, an ally spell falls back to the caster.
        cleric.db.hp = 1
        cleric.db.max_hp = 20
        await cast_spell(cleric, spell)
        assert cleric.db.get("hp") == 11

    async def test_effect_spell_attaches_behavior(self, world):
        sim, room = world
        spell = _spell(sim, "bless", mana=5, target="ally",
                       effect={"behavior_id": "modifier_effect",
                               "params": {"kind": "blessed", "duration": 60,
                                          "check_mods": {"all": 1}}})
        cleric = _mage(sim, room, name="Friar")
        ally = sim.player("Conan", location=room)
        await cast_spell(cleric, spell, ally)
        kinds = [b.kind for b in ally.get_behaviors()
                 if hasattr(b, "kind")]
        assert "blessed" in kinds

    async def test_negated_save_shrugs_off_the_effect(self, world,
                                                      monkeypatch):
        sim, room = world
        set_game_system(MercSystem())
        spell = _spell(sim, "curse", mana=5, target="victim", hostile=True,
                       save="negates",
                       effect={"behavior_id": "modifier_effect",
                               "params": {"kind": "cursed", "duration": 60,
                                          "check_mods": {"all": -1}}})
        cleric = _mage(sim, room, name="Friar")
        target = _dummy(sim, room)
        monkeypatch.setattr(MercSystem, "saving_throw",
                            lambda self, t, level: True)
        action = await cast_spell(cleric, spell, target)
        assert action is not None and action.applied
        assert not any(getattr(b, "kind", None) == "cursed"
                       for b in target.get_behaviors())

    async def test_on_cast_softcode_runs_as_the_spell_def(self, world):
        sim, room = world
        spell = _spell(sim, "mark", mana=0, target="victim")
        spell.db.on_cast = "set_attr(target, 'marked', adata('spell'))"
        # The spell_def must control the target for set_attr to land.
        mage = _mage(sim, room)
        target = _dummy(sim, room)
        spell.db.set("owner", None)
        target.owner = spell
        await cast_spell(mage, spell, target)
        assert target.db.get("marked") == "mark"


# --- the cast command --------------------------------------------------------

@pytest.mark.asyncio
class TestCastCommand:

    async def test_cast_by_name_with_target(self, world, monkeypatch):
        sim, room = world
        _spell(sim, "magic missile", mana=8, level=1, classes=["mage"],
               damage_dice="1d4+1", damage_type="force")
        mage = _mage(sim, room, level=5)
        _dummy(sim, room)
        monkeypatch.setattr("realm.systems.abilities.random.randint",
                            lambda a, b: 3)
        await sim.do(mage, "cast 'magic missile' dummy")
        out = "\n".join(sim.seen(mage))
        assert "You cast magic missile at" in out
        # unquoted multiword also parses (longest leading match)
        await sim.do(mage, "cast magic missile dummy")
        assert "You cast magic missile at" in "\n".join(sim.seen(mage))

    async def test_unknown_spell_and_class_gate(self, world):
        sim, room = world
        _spell(sim, "fireball", mana=15, level=15, classes=["mage"])
        rogue = sim.player("Sly", location=room)
        rogue.db.character_class = "thief"
        rogue.db.level = 20
        await sim.do(rogue, "cast fireball")
        assert any("don't know how" in m for m in sim.seen(rogue))
        await sim.do(rogue, "cast meteorswarm")
        assert any("know no spell" in m for m in sim.seen(rogue))

    async def test_spells_lists_castable(self, world):
        sim, room = world
        _spell(sim, "fireball", mana=15, level=15, classes=["mage"])
        _spell(sim, "harm", mana=35, level=19, classes=["cleric"])
        mage = _mage(sim, room, level=20)
        await sim.do(mage, "spells")
        out = "\n".join(sim.seen(mage))
        assert "fireball" in out and "harm" not in out


# --- CasterBehavior ----------------------------------------------------------

class _FakeEncounter:
    def __init__(self, me, opponent):
        self._parts = {p.obj.id: p for p in (me, opponent)}
        self.participants = self._parts

    def get(self, oid):
        return self._parts.get(oid)


class _FakePart:
    def __init__(self, obj, target_id=None):
        self.obj = obj
        self.target_id = target_id
        self.combatant = type("C", (), {"is_alive": True})()


class _FakeManager:
    def __init__(self, encounter):
        self._enc = encounter

    def encounter_in(self, room):
        return self._enc


@pytest.mark.asyncio
class TestCasterBehavior:

    async def test_ticks_only_in_combat_and_casts_via_pipeline(
            self, world, monkeypatch):
        sim, room = world
        fireball = _spell(sim, "fireball", mana=0, damage_dice="1d6",
                          damage_type="fire")
        mob = sim.obj("mage guard", location=room)
        mob.add_tag("npc")
        hero = sim.player("Conan", location=room)
        casts = []

        async def fake_cast(caster, spell, target=None):
            casts.append((caster.name, spell.name,
                          target.name if target else None))

        monkeypatch.setattr("realm.systems.spells.cast_spell", fake_cast)
        monkeypatch.setattr("realm.behaviors.caster.random.random",
                            lambda: 0.0, raising=False)
        behavior = CasterBehavior(spells=["fireball", "undefined spell"],
                                  chance=1.0)
        # Out of combat (no manager): no cast.
        monkeypatch.setattr("realm.combat.manager.get_combat_manager",
                            lambda: None)
        await behavior.tick(mob, 4.0)
        assert casts == []
        # In combat: casts the defined spell at the opponent.
        enc = _FakeEncounter(_FakePart(mob, target_id=hero.id),
                             _FakePart(hero))
        monkeypatch.setattr("realm.combat.manager.get_combat_manager",
                            lambda: _FakeManager(enc))
        await behavior.tick(mob, 4.0)
        assert casts == [("mage guard", "fireball", "Conan")]
        assert fireball is not None

    async def test_chance_gates_the_attempt(self, world, monkeypatch):
        sim, room = world
        _spell(sim, "fireball", mana=0, damage_dice="1d6",
               damage_type="fire")
        mob = sim.obj("mage guard", location=room)
        hero = sim.player("Conan", location=room)
        casts = []

        async def fake_cast(caster, spell, target=None):
            casts.append(spell.name)

        monkeypatch.setattr("realm.systems.spells.cast_spell", fake_cast)
        enc = _FakeEncounter(_FakePart(mob, target_id=hero.id),
                             _FakePart(hero))
        monkeypatch.setattr("realm.combat.manager.get_combat_manager",
                            lambda: _FakeManager(enc))
        monkeypatch.setattr("random.random", lambda: 0.9)
        await CasterBehavior(spells=["fireball"], chance=0.5).tick(mob, 4.0)
        assert casts == []                               # 0.9 > 0.5: no cast


# --- importer mapping --------------------------------------------------------

_ROM_SPEC_ARE = """\
#AREA
guild.are~
Guild~
{ All } Test    Guild~
100 199
#MOBILES
#100
guildmaster mage~
the mage guildmaster~
A guildmaster studies you coolly.
~
He crackles with restrained power.
~
human~
AB D 900 0
23 0 1d1+499 1d1+499 1d8+10 magic
-10 -10 -10 -10
0 0 0 0
stand stand male 5000
0 0 medium 0
#0
#ROOMS
#101
The Guild Hall~
A quiet hall.
~
0 0 0
S
#0
#RESETS
M 0 100 1 101 1
S
#SPECIALS
M 100 spec_cast_mage
S
#$
"""


class TestImporterCasterMapping:

    def _module(self):
        spec = importlib.util.spec_from_file_location(
            "rom_import",
            Path(__file__).resolve().parents[1] / "scripts" / "rom_import.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["rom_import"] = mod
        spec.loader.exec_module(mod)
        return mod

    def test_spec_cast_becomes_caster_behavior(self):
        rom_import = self._module()
        area = rom_import.convert(_ROM_SPEC_ARE)
        proto = area.mob_protos[100]
        assert "rom_spec:spec_cast_mage" in proto["tags"]
        casters = [b for b in proto["behaviors"]
                   if b["behavior_id"] == "caster"]
        assert len(casters) == 1
        assert "fireball" in casters[0]["params"]["spells"]
        # The reset-placed instance is patched too, like #SHOPS keepers.
        placed = [o for o in area.objects
                  if o["attrs"].get("prototype_vnum") == 100]
        assert placed and any(b["behavior_id"] == "caster"
                              for b in placed[0]["behaviors"])


# --- the merc-classic pack ---------------------------------------------------

@pytest.mark.asyncio
class TestMercClassicPack:

    async def test_pack_imports_and_casts(self, world, monkeypatch):
        sim, room = world
        from realm.packs import import_pack
        created = await import_pack("merc-classic", sim.store)
        assert len(created) == 23
        fireball = find_spell_def("fireball")
        assert fireball is not None
        assert fireball.db.get("damage_type") == "fire"
        mage = _mage(sim, room)
        target = _dummy(sim, room)
        monkeypatch.setattr("realm.systems.abilities.random.randint",
                            lambda a, b: 4)
        action = await cast_spell(mage, fireball, target)
        assert action is not None and action.applied
        assert target.db.get("hp") == 76                # 6d6 all 4s

    async def test_breaths_have_no_class_gate_but_high_level(self, world):
        sim, room = world
        from realm.packs import import_pack
        await import_pack("merc-classic", sim.store)
        breath = find_spell_def("fire breath")
        mob = sim.obj("dragon", location=room)
        mob.add_tag("npc")
        assert knows_spell(mob, breath)                 # spec mobs cast it
        rube = sim.player("Rube", location=room)
        rube.db.level = 3
        assert not knows_spell(rube, breath)            # level 20 spell
