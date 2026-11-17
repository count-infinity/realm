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

    async def test_the_fido_is_aggressive(self):
        # ACT_AGGRESSIVE: the fido pounces when a mortal enters its room
        # (the shipped `aggressive` behavior reacts to event:on_enter).
        sim, system, mgr = await _world()
        try:
            from realm.core.propagation import Action
            square = sim.store.get_cached(COMMON_SQUARE)
            fido = [o for o in square.contents
                    if "npc" in o.tags and "fido" in o.name][0]
            grog = await _barbarian(sim, system)          # a mortal walks in
            aggro = next(b for b in fido.get_behaviors()
                         if b.behavior_id == "aggressive")
            arrival = Action(actor=grog, target=square,
                             action_type="event:on_enter")
            await aggro.on_react(fido, arrival)
            assert fido.has_tag("in_combat")              # it attacked
            assert grog.has_tag("in_combat")
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
            assert int(grog.db.get("xp") or 0) == 100      # a level-0 fido's 100 points
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


@pytest.mark.asyncio
class TestTheTownAsROMHasIt:

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
            assert "the guildmaster teaches:" in out, cls
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
        assert "baker" in _seen(sim, pat)
    finally:
        _teardown(sim)
        sys.modules.pop("rules", None)
        sys.modules.pop("game", None)
        sys.path[:] = before
        install_default()
