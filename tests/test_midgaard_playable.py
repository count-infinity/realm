"""End-to-end: the Midgaard example game is actually playable on merc.

Loads the shipped ``examples/midgaard`` area on the ``merc`` game system and
walks the scenario the game promises: a level-1 barbarian starts in the
Common Square kitted with a club, kills a fido for XP, the fido respawns,
and the shops trade. This is the integration proof that merc + the ROM
importer (--repop) + chargen + combat + XP + spells hang together.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from realm.combat.manager import CombatManager, set_combat_manager
from realm.combat.maneuver import QueuedAction
from realm.combat.rulesets.merc import MercRuleset
from realm.combat.system import CombatSystem
from realm.persistence.worldio import import_objects
from realm.systems import MercSystem, reload_rules, set_game_system
from realm.systems.definitions import apply_class
from realm.testing import Simulator

AREA = Path(__file__).resolve().parents[1] / "examples" / "midgaard" / \
    "data" / "areas" / "midgaard.json"
COMMON_SQUARE = "rom_3025"


async def _world():
    """Boot the Midgaard area on merc, the way config.init_world would."""
    sim = Simulator()
    await import_objects(json.loads(AREA.read_text()), sim.store,
                         preserve_ids=True)
    system = MercSystem()
    set_game_system(system)
    reload_rules()
    mgr = CombatManager(CombatSystem(ruleset=MercRuleset()),
                        beat_min=4.0, beat_max=120.0, beat_default=15.0)
    set_combat_manager(mgr)
    return sim, system, mgr


async def _barbarian(sim, system, name="Grog"):
    """Create + fully generate a barbarian, as connecting would."""
    square = sim.store.get_cached(COMMON_SQUARE)
    p = sim.player(name, location=square)
    system.apply_baseline(p)
    spec = system._classes()["barbarian"]
    apply_class(p, (spec["blurb"], spec["stats"], spec["skills"]),
                "barbarian", marker="character_class")
    system.finish_chargen(p)
    await system.outfit_new_character(p, sim.store)
    return p


def _teardown(sim):
    set_combat_manager(None)
    set_game_system(None)
    sim.close()


@pytest.mark.asyncio
class TestMidgaardPlayable:

    async def test_barbarian_starts_kitted_in_the_square(self):
        sim, system, mgr = await _world()
        try:
            grog = await _barbarian(sim, system)
            assert grog.db.get("character_class") == "barbarian"
            assert grog.db.get("level") == 1
            assert grog.db.get("hp") == 13               # d12 (12) + con-16 (+1)
            assert grog.location.id == COMMON_SQUARE
            assert grog.location.name == "The Common Square"
            club = [o for o in grog.contents if o.has_tag("wielded")]
            assert len(club) == 1
            assert "club" in club[0].name
            assert club[0].db.get("damage_dice") == "1d8"
        finally:
            _teardown(sim)

    async def test_a_fido_waits_in_the_square(self):
        sim, system, mgr = await _world()
        try:
            square = sim.store.get_cached(COMMON_SQUARE)
            fidos = [o for o in square.contents
                     if "npc" in o.tags and "fido" in o.name]
            assert fidos, "the Common Square should be stocked with a fido"
            assert fidos[0].db.get("hp") == 8
        finally:
            _teardown(sim)

    async def test_kill_a_fido_for_xp(self, monkeypatch):
        sim, system, mgr = await _world()
        try:
            grog = await _barbarian(sim, system)
            square = grog.location
            fido = [o for o in square.contents
                    if "npc" in o.tags and "fido" in o.name][0]
            # Deterministic: every die rolls maximum, so the club connects
            # and the fido (hp 8) drops in the first round.
            monkeypatch.setattr("realm.combat.rulesets.merc.random.randint",
                                lambda a, b: b)
            encounter = await mgr.initiate(grog, fido)
            encounter.queue(grog, QueuedAction("attack", target_id=fido.id))
            for _ in range(3):
                await encounter.resolve_round()
                if sim.store.get_cached(fido.id) is None or \
                        int(fido.db.get("hp") or 0) <= 0:
                    break
                encounter.queue(grog, QueuedAction("attack", target_id=fido.id))
            assert int(fido.db.get("hp") or 0) <= 0        # fido is dead
            assert int(grog.db.get("xp") or 0) >= 50       # fido lvl5 -> 50 xp
        finally:
            _teardown(sim)

    async def test_the_fido_respawns_after_death(self, monkeypatch):
        sim, system, mgr = await _world()
        try:
            square = sim.store.get_cached(COMMON_SQUARE)
            fido = [o for o in square.contents
                    if "npc" in o.tags and "fido" in o.name][0]
            # Kill it outright (the death path deletes it from the cache).
            await mgr.handle_death(fido, killer=None)
            assert not [o for o in square.contents
                        if "npc" in o.tags and "fido" in o.name]
            # The square's spawner adopted the original; after its respawn
            # window it repopulates. Tick past respawn_ticks (20).
            spawner = next(b for b in square.get_behaviors()
                           if b.behavior_id == "spawner")
            for _ in range(25):
                await spawner.tick(square, 4.0)
            reborn = [o for o in square.contents
                      if "npc" in o.tags and "fido" in o.name]
            assert reborn, "the fido should respawn on the spawner's timer"
            assert reborn[0].db.get("hp") == 8             # fresh, full HP
        finally:
            _teardown(sim)

    async def test_trade_at_a_shop(self):
        sim, system, mgr = await _world()
        try:
            grog = await _barbarian(sim, system)
            # Find a stocked keeper and step into their shop.
            from realm.behaviors.shop import find_shopkeeper
            shop_room = keeper = None
            for room in sim.store.all_cached():
                if not room.has_tag("room"):
                    continue
                found = find_shopkeeper(room)
                if found and found[1].wares(found[0]):
                    shop_room, keeper = room, found[0]
                    break
            assert keeper is not None, "Midgaard should have a stocked shop"
            grog.location = shop_room
            grog.db.credits = 1000
            ware = [w for w in keeper.contents if w.has_tag("thing")][0]
            before = get_credits_of(grog)
            await sim.do(grog, f"buy {ware.name}")
            bought = [o for o in grog.contents if o.name == ware.name]
            assert bought, f"should have bought {ware.name!r}"
            assert get_credits_of(grog) < before          # gold was spent
        finally:
            _teardown(sim)

    async def test_a_mage_can_cast_from_the_pack(self, monkeypatch):
        # Spells "shake out" too: import the pack, a mage burns a fido.
        sim, system, mgr = await _world()
        try:
            from realm.packs import import_pack
            from realm.systems.spells import cast_spell, find_spell_def
            await import_pack("merc-classic", sim.store)
            square = sim.store.get_cached(COMMON_SQUARE)
            merlin = sim.player("Merlin", location=square)
            system.apply_baseline(merlin)
            merlin.db.character_class = "mage"
            merlin.db.level = 20
            merlin.db.mana = 100
            fido = [o for o in square.contents
                    if "npc" in o.tags and "fido" in o.name][0]
            monkeypatch.setattr("realm.systems.abilities.random.randint",
                                lambda a, b: b)
            fireball = find_spell_def("fireball")
            action = await cast_spell(merlin, fireball, fido)
            assert action is not None and action.applied
            assert merlin.db.get("mana") < 100             # spent
            assert int(action.extra.get("dealt") or 0) > 0  # fido burned
        finally:
            _teardown(sim)


def get_credits_of(obj):
    from realm.core.economy import get_credits
    return get_credits(obj)
