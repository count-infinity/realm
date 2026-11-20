"""End-to-end: the Midgaard example game is actually playable on merc.

Loads the shipped ``realm/examples/midgaard`` area on the ``merc`` game system and
walks the scenario the game promises: a level-1 barbarian starts in the
Common Square kitted with a club, kills a fido for XP, the fido respawns,
and the shops trade. This is the integration proof that merc + the ROM
importer (--repop) + chargen + combat + XP + spells hang together.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from realm.core.world import get_world
from realm.games.merc.ruleset import MercRuleset
from realm.games.merc.system import MercSystem
from realm.persistence.worldio import import_objects
from realm.std.combat.manager import CombatManager
from realm.std.combat.maneuver import QueuedAction
from realm.std.combat.system import CombatSystem
from realm.std.rules.definitions import apply_class
from realm.std.rules.system import reload_rules
from realm.testing import Simulator

AREA = Path(__file__).resolve().parents[1] / "realm" / "examples" / "midgaard" / \
    "data" / "areas" / "midgaard.json"
COMMON_SQUARE = "rom_3025"


async def _world():
    """Boot the Midgaard area on merc, the way config.init_world would."""
    sim = Simulator()
    await import_objects(json.loads(AREA.read_text()), sim.store,
                         preserve_ids=True)
    system = MercSystem()
    get_world().rules = system
    reload_rules()
    mgr = CombatManager(CombatSystem(ruleset=MercRuleset()),
                        beat_min=4.0, beat_max=120.0, beat_default=15.0)
    get_world().services["combat"] = mgr
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
    from realm.std.combat.combatant import clear_combatant_cache
    # These tests import with preserve_ids, so the same mob id recurs across
    # sims; drop the id-keyed combatant cache so a later test never wraps a
    # stale, closed-sim object.
    clear_combatant_cache()
    sim.close()


@pytest.mark.asyncio
class TestMidgaardPlayable:

    async def test_barbarian_starts_kitted_in_the_square(self):
        sim, system, mgr = await _world()
        try:
            grog = await _barbarian(sim, system)
            assert grog.db.get("character_class") == "barbarian"
            assert grog.db.get("level") == 1
            assert grog.db.get("hp") == 20               # ROM's new_char, every class
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

    async def test_the_beastly_fido_wanders(self, monkeypatch):
        sim, system, mgr = await _world()
        try:
            square = sim.store.get_cached(COMMON_SQUARE)
            fido = [o for o in square.contents
                    if "npc" in o.tags and "fido" in o.name][0]
            wander = next((b for b in fido.get_behaviors()
                           if b.behavior_id == "wandering"), None)
            assert wander is not None, "the beastly fido should wander"
            # Force a step every tick, first exit each time.
            monkeypatch.setattr("realm.std.combat.behaviors.random.random",
                                lambda: 0.0)
            monkeypatch.setattr("realm.std.combat.behaviors.random.choice",
                                lambda seq: seq[0])
            start = fido.location.id
            moved = False
            for _ in range(6):
                await wander.tick(fido, 4.0)
                if fido.location is not None and fido.location.id != start:
                    moved = True
                    break
            assert moved, "the fido should roam to an adjacent room"
            # ACT_STAY_AREA: it stays inside Midgaard.
            assert "zone:midgaard" in fido.location.tags
        finally:
            _teardown(sim)

    async def test_the_fido_lets_the_awake_walk_by(self):
        # ROM's fido is ACT_AGGRESSIVE and ACT_WIMPY: aggr_update leaves an
        # awake player alone (it would bite a sleeper). Before 2026-11-17
        # it jumped every newcomer, two at a time.
        sim, system, mgr = await _world()
        try:
            square = sim.store.get_cached(COMMON_SQUARE)
            fido = [o for o in square.contents
                    if "npc" in o.tags and "fido" in o.name][0]
            assert "aggressive" not in [b.behavior_id for b in fido.get_behaviors()]
            assert "F" in fido.db.rom_act and "H" in fido.db.rom_act
        finally:
            _teardown(sim)

    async def test_the_fido_eats_a_corpse(self):
        # spec_fido -> scavenger: the fido devours a corpse left in its room.
        sim, system, mgr = await _world()
        try:
            square = sim.store.get_cached(COMMON_SQUARE)
            fido = [o for o in square.contents
                    if "npc" in o.tags and "fido" in o.name][0]
            corpse = sim.obj("corpse of a rat", location=square,
                             tags=["thing", "container"])
            scav = next(b for b in fido.get_behaviors()
                        if b.behavior_id == "scavenger")
            # chance defaults to 0.5; force it to act.
            import random
            random.seed(1)
            for _ in range(10):
                await scav.tick(fido, 4.0)
                if sim.store.get_cached(corpse.id) is None:
                    break
            assert sim.store.get_cached(corpse.id) is None  # devoured
        finally:
            _teardown(sim)

    async def test_shop_wares_restock(self):
        # A bought ware comes back: the keeper's restock re-mints it.
        sim, system, mgr = await _world()
        try:
            from realm.std.economy.shop import find_shopkeeper
            keeper = None
            for room in sim.store.all_cached():
                found = room.has_tag("room") and find_shopkeeper(room)
                if found and found[1].wares(found[0]):
                    keeper, shop = found[0], found[1]
                    break
            assert keeper is not None
            restock = next(b for b in keeper.get_behaviors()
                           if b.behavior_id == "restock")
            await restock.tick(keeper, 4.0)               # snapshot the stock
            ware = shop.wares(keeper)[0]
            name = ware.name
            ware.location = None                          # someone bought it
            assert name not in [w.name for w in shop.wares(keeper)]
            for _ in range(40):                           # wait out the timer
                await restock.tick(keeper, 4.0)
                if name in [w.name for w in shop.wares(keeper)]:
                    break
            assert name in [w.name for w in shop.wares(keeper)]  # re-minted
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
            monkeypatch.setattr("realm.games.merc.ruleset.random.randint",
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
            # A level-0 fido is a level below level-1 Grog: its 100 points, bent 15% down.
            assert int(grog.db.get("xp") or 0) == 170   # 85, doubled at level 1 (ROM)
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
            from realm.std.economy.shop import find_shopkeeper
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
            from realm.std.abilities.spells import cast_spell, find_spell_def
            await import_pack("merc-classic", sim.store)
            square = sim.store.get_cached(COMMON_SQUARE)
            merlin = sim.player("Merlin", location=square)
            system.apply_baseline(merlin)
            merlin.db.character_class = "mage"
            merlin.db.level = 20
            merlin.db.mana = 100
            fido = [o for o in square.contents
                    if "npc" in o.tags and "fido" in o.name][0]
            monkeypatch.setattr("realm.std.abilities.abilities.random.randint",
                                lambda a, b: b)
            fireball = find_spell_def("fireball")
            action = await cast_spell(merlin, fireball, fido)
            assert action is not None and action.applied
            assert merlin.db.get("mana") < 100             # spent
            assert int(action.extra.get("dealt") or 0) > 0  # fido burned
        finally:
            _teardown(sim)

    # --- MUD_PLAN step 11: Merc parity ----------------------------------------------

    async def test_the_watch_protects_the_innocent(self):
        # spec_guard -> a peacekeeper that also takes on the most evil
        # fighter in a brawl (protect="evil").
        sim, system, mgr = await _world()
        try:
            guards = [o for o in sim.store.all_cached()
                      if o.has_tag("rom_spec:spec_guard") and not o.has_tag("prototype")]
            assert guards
            for guard in guards:
                keeper = next(b for b in guard.get_behaviors()
                              if b.behavior_id == "peacekeeper")
                assert keeper.get_param("protect") == "evil"
        finally:
            _teardown(sim)

    async def test_the_watch_does_not_eat_the_dead(self):
        # MUD_PLAN step 17: ACT_SCAVENGER picks things up; only spec_fido
        # eats corpses (the shipped area was refreshed).
        sim, system, mgr = await _world()
        try:
            scavengers = [b for o in sim.store.all_cached()
                          if o.has_tag("rom_spec:spec_guard") and o.has_tag("npc")
                          for b in o.get_behaviors() if b.behavior_id == "scavenger"]
            assert scavengers
            assert all(b.get_param("eat_corpses") is False for b in scavengers)
        finally:
            _teardown(sim)

    async def test_a_kill_pays_the_victims_money(self):
        # ROM wealth became money; autogold takes it from the corpse.
        sim, system, mgr = await _world()
        try:
            grog = await _barbarian(sim, system)
            guard = next(o for o in sim.store.all_cached()
                         if o.has_tag("rom_spec:spec_guard") and not o.has_tag("prototype"))
            purse = get_credits_of(guard)
            assert purse > 0
            guard.location = grog.location
            await sim.do(grog, "config autogold on")
            await mgr.handle_death(guard, killer=grog)
            assert get_credits_of(grog) == purse
            assert int(grog.db.alignment) < 0            # a good guard: Grog darkens
        finally:
            _teardown(sim)

    async def test_consider_a_fido_and_who_is_on(self):
        sim, system, mgr = await _world()
        try:
            grog = await _barbarian(sim, system)
            await sim.do(grog, "consider fido")          # ROM's fido is level 0
            assert "The perfect match!" in "\n".join(sim.seen(grog))
            await sim.do(grog, "who")
            assert "Grog the Brute (1 barbarian)" in "\n".join(sim.seen(grog))
        finally:
            _teardown(sim)


def get_credits_of(obj):
    from realm.std.economy.credits import get_credits
    return get_credits(obj)


# --- the town as ROM has it (after the MUD plan, 2026-11-16) -----------------------
#
# The shipped area is converted from ROM 2.4's own midgaard.are: the baker
# keeps the Bakery, the four guildmasters their guilds, and everything is
# called by its short description while answering to its keywords.

MIDGAARD_GAME = AREA.parents[2]
GUILDMASTERS = {3020: ("rom_3019", "mage"), 3021: ("rom_3002", "cleric"),
                3022: ("rom_3029", "thief"), 3023: ("rom_3023", "warrior")}
BARS = {"rom_3018": "mage", "rom_3003": "cleric", "rom_3028": "thief",
        "rom_3022": "warrior"}


@pytest.fixture
async def town():
    """The Midgaard game booted from its config.py (init_world and all)."""
    import sys

    from realm.features import install_default
    before = list(sys.path)
    sim = Simulator.from_game(MIDGAARD_GAME)
    await sim.start()
    try:
        yield sim
    finally:
        _teardown(sim)
        sys.modules.pop("rules", None)
        sys.modules.pop("game", None)
        sys.path[:] = before
        install_default()


def _character(sim, name, cls, room):
    rules = get_world().rules
    player = sim.player(name, location=room)
    rules.apply_baseline(player)
    rules.chargen_steps()[0].handle(player, cls)
    rules.finish_chargen(player)
    return player


def _seen(sim, player) -> str:
    return "\n".join(sim.seen(player))


async def _seen_after(sim, player, line) -> str:
    sim.seen(player)
    await sim.do(player, line)
    return _seen(sim, player)


@pytest.mark.asyncio
class TestTheTownAsROMHasIt:

    async def test_the_mud_school_is_up_from_the_temple(self, town):
        # ROM's newbie area (school.are, vnums 3700-3799), converted the way
        # Midgaard is: the Temple's `up` (ROM 3001 D4) leads into it, its
        # exit `down` back, and it has ROM's trainer (the adept of Furey,
        # ACT_TRAIN) and the leashed monsters to practise on.
        temple, entrance = town.store.get_cached("rom_3001"), town.store.get_cached("rom_3700")
        assert entrance is not None and entrance.name == "Entrance to Mud School"
        pat = _character(town, "Pat", "warrior", temple)
        await town.do(pat, "up")
        assert pat.location is entrance
        assert "This is the entrance to the Merc Mud School." in _seen(town, pat)
        await town.do(pat, "down")
        assert pat.location is temple
        furey = next(o for o in town.store.find_cached(tag="npc")
                     if o.db.get("prototype_vnum") == 3718)
        trainer = next(b for b in furey.get_behaviors() if b.behavior_id == "trainer")
        assert trainer.get_param("trains_stats") is True
        pat.location, pat.db.trains = furey.location, 1        # a level's session
        strength = pat.db.strength
        out = await _seen_after(town, pat, "train strength")
        assert f"Your strength rises to {strength + 1}." in out and pat.db.trains == 0
        monsters = [o for o in town.store.find_cached(tag="npc")
                    if o.db.get("prototype_vnum") == 3702]
        assert monsters and all(o.location.has_tag("zone:mud_school") for o in monsters)

    async def test_help_newbie_tells_a_new_character_what_to_do(self, town):
        # ROM shows a new character its "newbie info" help; the banner here
        # points to it.
        pat = _character(town, "Pat", "mage", town.store.get_cached(COMMON_SQUARE))
        out = await _seen_after(town, pat, "help newbie")
        assert "NEWBIE INFO" in out and "where fido" in out and "kill fido" in out
        assert "NEWBIE INFO" in await _seen_after(town, pat, "help newbie info")
        assert "help newbie" in town.world.setting("WELCOME_BANNER")

    async def test_a_new_character_is_outfitted_as_rom_does(self, town):
        # ROM's do_outfit: the class weapon, and the Mud School's vest,
        # shield and war banner, worn, worth nothing at a shop (cost 0).
        rules = get_world().rules
        pat = _character(town, "Pat", "mage", town.store.get_cached(COMMON_SQUARE))
        await rules.outfit_new_character(pat, town.store)
        worn = {o.db.get("slot"): o for o in pat.contents if o.has_tag("worn")}
        assert {slot: o.name for slot, o in worn.items()} == {
            "body": "a sub issue vest", "shield": "a sub issue shield",
            "light": "a war banner"}
        assert all(not o.has_tag("prototype") and o.db.get("value") == 0
                   for o in worn.values())
        assert [o.name for o in pat.contents if o.has_tag("wielded")] == ["a gnarled dagger"]
        assert pat.db.armor_class == 8
        out = await _seen_after(town, pat, "equipment")
        assert "<body>    a sub issue vest" in out and "<light>   a war banner" in out

    async def test_a_locked_door_opens_with_its_key_from_both_sides(self, town):
        # midgaard.are: room 3110's `D3` is a `door` with key 3120 (an iron
        # key; the cityguard in room 3111 carries one, `G 0 3120`) to room
        # 3142, whose `D1` door leads back (BACKLOG 2026-11-17).
        inside, beyond = town.store.get_cached("rom_3110"), town.store.get_cached("rom_3142")
        west = next(o for o in inside.contents if o.is_exit and o.name == "west")
        east = next(o for o in beyond.contents if o.is_exit and o.name == "east")
        assert west.db.get("key_id") == east.db.get("key_id") == "rom_obj_3120"
        assert town.store.get_cached("rom_3120").db.get("unlocks") is None   # a room
        key = next(o for o in town.store.find_cached(tag="key")
                   if o.db.get("rom_vnum") == 3120 and not o.has_tag("prototype"))
        assert key.location.db.get("prototype_vnum") == 3060      # the cityguard's
        pat = _character(town, "Pat", "warrior", inside)
        sam = _character(town, "Sam", "warrior", beyond)
        key.location = pat
        # Locked at boot, both sides: ROM's `D 0 3110 3 2` and `D 0 3142 1 2`.
        assert west.has_tag("locked") and east.has_tag("locked")
        await town.do(sam, "open east")
        assert "locked" in _seen(town, sam).lower() and east.has_tag("closed")
        await town.do(pat, "unlock west")
        assert not west.has_tag("locked") and not east.has_tag("locked")
        await town.do(pat, "lock west")
        assert "You lock the door with a key." in _seen(town, pat)     # its short description
        assert west.has_tag("locked") and east.has_tag("locked")
        await town.do(pat, "unlock west")
        await town.do(pat, "open west")
        assert not west.has_tag("closed") and not east.has_tag("closed")
        assert "The door opens." in _seen(town, sam)
        await town.do(sam, "east")
        assert sam.location is inside

    async def test_the_baker_keeps_the_bakery_and_sells_bread(self, town):
        bakery = town.store.get_cached("rom_3009")
        bakers = [o for o in bakery.contents if o.db.get("prototype_vnum") == 3001]
        assert [b.name for b in bakers] == ["the baker"]           # one, the real one
        pat = _character(town, "Pat", "warrior", bakery)
        pat.db.credits = 100
        await town.do(pat, "list")
        listing = _seen(town, pat)
        assert "The baker's wares:" in listing and "a bread — " in listing
        assert "a big pot pie — " in listing
        await town.do(pat, "buy bread")
        assert "You buy a bread for " in _seen(town, pat)
        await town.do(pat, "buy potpie")                            # a ROM keyword
        assert "You buy a big pot pie for " in _seen(town, pat)
        await town.do(pat, "inventory")
        held = _seen(town, pat)
        assert "  a bread" in held and "  a big pot pie" in held

    async def test_the_fido_quest_is_the_real_bakers(self, town):
        bakery = town.store.get_cached("rom_3009")
        pat = _character(town, "Pat", "warrior", bakery)
        await town.do(pat, "look")
        assert "the baker (!)" in _seen(town, pat)
        await town.do(pat, "quest list")
        assert "Fido trouble" in _seen(town, pat)
        elsewhere = town.obj("the baker", location=bakery, tags=["npc"])
        from realm.std.quests.quests import offered_by
        assert offered_by(elsewhere) == []                          # a namesake is not him

    async def test_each_guildmaster_is_in_their_guild(self, town):
        for vnum, (room_id, _cls) in GUILDMASTERS.items():
            room = town.store.get_cached(room_id)
            masters = [o for o in room.contents if o.db.get("prototype_vnum") == vnum]
            assert [m.name for m in masters] == ["the guildmaster"], room.name
            assert any(b.behavior_id == "trainer" for b in masters[0].get_behaviors())

    async def test_each_class_practises_at_its_own_guild(self, town):
        for vnum, (room_id, cls) in GUILDMASTERS.items():
            room = town.store.get_cached(room_id)
            student = _character(town, f"Student{vnum}", cls, room)
            student.db.practices = 1
            await town.do(student, "practice")
            out = _seen(town, student)
            assert "The guildmaster teaches:" in out, cls
            taught = get_world().rules.class_skills(student)
            assert taught and all(s.replace("_", " ") in out for s in taught), cls

    async def test_a_guilds_bar_turns_the_other_classes_away(self, town):
        rooms = [o for o in town.store.all_cached() if o.has_tag("room")]
        for bar_id, cls in BARS.items():
            way_in = next(e for r in rooms for e in r.contents
                          if e.has_tag("exit") and e.db.get("destination") == bar_id)
            outside = way_in.location
            member = _character(town, f"Member{cls}", cls, outside)
            other = _character(town, f"Other{cls}", "mage" if cls != "mage" else "thief",
                               outside)
            await town.do(other, way_in.name)
            assert "You aren't allowed in there." in _seen(town, other)
            assert other.location is outside
            await town.do(member, way_in.name)
            assert member.location.id == bar_id, cls
        swordsmen = town.store.get_cached("rom_3022")
        way_in = next(e for r in rooms for e in r.contents
                      if e.has_tag("exit") and e.db.get("destination") == "rom_3022")
        brute = _character(town, "Brute", "barbarian", way_in.location)
        await town.do(brute, way_in.name)                           # barbarians drink here
        assert brute.location is swordsmen

    async def test_a_cityguard_fights_with_his_sword(self, town):
        # ROM's E reset equips: the guard wields his sword and wears his vest
        # (BACKLOG 2026-11-16: the gear sat in his pack and he punched).
        from realm.std.combat.system import find_wielded
        guard = next(o for o in town.store.find_cached(tag="npc")
                     if o.name == "the cityguard" and not o.has_tag("prototype"))
        sword = find_wielded(guard)
        assert sword is not None and sword.name == "a standard issue sword"
        vest = next(o for o in guard.contents if o.name == "a standard issue vest")
        assert vest.has_tag("worn") and vest.db.get("slot") == "body"
        assert vest.db.get("worn") is None
        pat = _character(town, "Pat", "warrior", guard.location)
        await town.do(pat, "look cityguard")
        seen = _seen(town, pat)
        assert "The cityguard is using:" in seen and "<wielded> a standard issue sword" in seen
        # A fight passes the wielded weapon to the ruleset (the encounter's
        # find_wielded), whose dice are the sword's 3d5, not his own 2d4+4.
        assert MercRuleset().weapon_prop(sword, "damage_dice", None) == "3d5"

    async def test_a_dead_guards_gear_is_loot_not_still_worn(self, town):
        # ROM's make_corpse takes everything off: what a looter picks up is
        # carried, never worn or wielded on arrival.
        guard = next(o for o in town.store.find_cached(tag="npc")
                     if o.name == "the cityguard" and not o.has_tag("prototype"))
        room = guard.location
        gear = list(guard.contents)
        assert any(o.has_tag("wielded") for o in gear)
        await town.world.services["combat"].handle_death(guard)
        corpse = next(o for o in room.contents if o.name == "corpse of the cityguard")
        assert set(gear) == set(corpse.contents)
        assert not any(o.has_tag("worn") or o.has_tag("wielded") for o in gear)

    async def test_a_keeper_sells_nothing_he_wields(self, town):
        bakery = town.store.get_cached("rom_3009")
        baker = next(o for o in bakery.contents if o.db.get("prototype_vnum") == 3001)
        sword = next(o for o in baker.contents if o.name == "a long sword")
        assert sword.has_tag("wielded")
        pat = _character(town, "Pat", "warrior", bakery)
        await town.do(pat, "list")
        assert "long sword" not in _seen(town, pat)

    async def test_names_read_as_rom_does(self, town):
        square = town.store.get_cached(COMMON_SQUARE)
        pat = _character(town, "Pat", "warrior", square)
        await town.do(pat, "look")
        assert "the beastly fido" in _seen(town, pat)
        assert "fido dog" not in _seen(town, pat)
        await town.do(pat, "consider fido")                         # the keyword answers
        assert "The beastly fido " in _seen(town, pat)
        await town.do(pat, "kill fido")
        assert "You square off against the beastly fido!" in _seen(town, pat)


async def test_a_world_made_from_the_old_conversion_still_boots():
    """A Midgaard database made before the re-conversion: things named by
    their ROM keywords (the short description unused in ``short_desc``),
    the baker the old template cloned. It boots under the new template as
    it was (``init_world`` runs only on an empty database): nothing is
    renamed, no guild bar is locked, and its things still answer to what
    they are called."""
    import sys

    from realm.features import install_default
    old = [
        {"id": "rom_3009", "name": "The Bakery", "tags": ["room"],
         "attrs": {"rom_vnum": 3009, "sector": "inside"}},
        {"id": "rom_3018", "name": "Mage's Bar", "tags": ["room"],
         "attrs": {"rom_vnum": 3018, "sector": "inside"}},
        {"id": "cloned_baker", "name": "baker", "tags": ["npc"], "location": "rom_3009",
         "attrs": {"rom_vnum": 3001, "short_desc": "the baker", "prototype_vnum": 3001}},
        {"id": "cloned_loaf", "name": "bread", "tags": ["thing", "food"],
         "location": "cloned_baker", "attrs": {"rom_vnum": 3011, "short_desc": "a bread"}},
        # Gear an E reset gave before 2026-11-17: a `worn` attribute naming
        # its ROM wear location, never the tags a wearer's gear has.
        {"id": "old_sword", "name": "sword long", "tags": ["thing", "weapon", "wieldable"],
         "location": "cloned_baker", "attrs": {"rom_vnum": 3021, "worn": "wield"}},
        {"id": "old_apron", "name": "apron", "tags": ["thing", "wearable"],
         "location": "cloned_baker", "attrs": {"rom_vnum": 3999, "worn": "about",
                                               "slot": "about"}},
        {"id": "old_lamp", "name": "lamp", "tags": ["thing", "light"],
         "location": "cloned_baker", "attrs": {"rom_vnum": 3998, "worn": "hold"}},
        # A door and its key as the importer wrote them before 2026-11-17:
        # the key's vnum in the exit's `key`, nothing on the key.
        {"id": "old_door", "name": "north", "tags": ["exit", "door", "closed"],
         "location": "rom_3018",
         "attrs": {"destination": "rom_3009", "keywords": "door", "key": "rom_obj_3120"}},
        {"id": "old_key", "name": "an iron key", "tags": ["thing", "key"],
         "location": "rom_3018", "attrs": {"rom_vnum": 3120, "item_type": "key",
                                           "aliases": ["key", "iron"]}},
    ]
    before = list(sys.path)
    sim = Simulator.from_game(MIDGAARD_GAME)
    await import_objects({"realm_format": 1, "objects": old}, sim.store, preserve_ids=True)
    await sim.start()
    try:
        bakery = sim.store.get_cached("rom_3009")
        assert [o.name for o in bakery.contents] == ["baker"]
        assert sim.store.get_cached("rom_3018").locks.get("enter") is None
        pat = sim.player("Pat", location=bakery)
        await sim.do(pat, "look baker")
        assert "Baker" in _seen(sim, pat)
        # The old gear is equipped at boot (the `items` feature's on_boot):
        # wielded, and worn where ROM put it (ROM's "hold" is Merc's "held").
        sword, apron, lamp = (sim.store.get_cached(i) for i in ("old_sword", "old_apron",
                                                               "old_lamp"))
        assert sword.has_tag("wielded") and sword.db.get("worn") is None
        assert apron.has_tag("worn") and apron.db.get("slot") == "about"
        assert lamp.has_tag("worn") and lamp.db.get("slot") == "held"
        assert not any(o.db.get("worn") for o in (sword, apron, lamp))
        # The old door and key are mended at boot: `key_id` and `unlocks`.
        door, key = sim.store.get_cached("old_door"), sim.store.get_cached("old_key")
        assert door.db.get("key_id") == "rom_obj_3120" and door.db.get("key") is None
        assert key.db.get("unlocks") == "rom_obj_3120"
        mo = sim.player("Mo", location=sim.store.get_cached("rom_3018"))
        await sim.do(mo, "get key")
        await sim.do(mo, "lock door")
        assert door.has_tag("locked")
    finally:
        _teardown(sim)
        sys.modules.pop("rules", None)
        sys.modules.pop("game", None)
        sys.path[:] = before
        install_default()

