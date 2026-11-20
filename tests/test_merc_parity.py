"""
MUD_PLAN step 11: Merc parity, the remaining Diku pieces.

Special procedures (the peacekeeper's two ROM modes), the player toggles
(``autoloot``, ``autogold``, ``autosplit``, ``autoexit``, ``brief``), group
play (experience split by level, ``split``, ``report``), looking around
(``scan``, ``exits``, ``where``, ``consider``), alignment and the
``anti_*`` items, the level cap and class titles, and ``recall``. The
importer's half is in ``TestImporter``; the shipped Midgaard area in
``tests/test_midgaard_playable.py``.
"""

from __future__ import annotations

import pytest

from realm.core.options import get_option
from realm.testing import Simulator

MERC = "realm.games.merc.system.MercSystem"


@pytest.fixture
def merc():
    sim = Simulator(game_system=MERC)
    try:
        yield sim
    finally:
        sim.close()


def text(sim, player) -> str:
    return "\n".join(sim.seen(player))


def _room(sim, name="Square", **attrs):
    return sim.room(name, **attrs)


def _link(sim, here, there, name, back):
    door = sim.obj(name, location=here, tags=["exit"])
    door.db.set("destination", there.id)
    ret = sim.obj(back, location=there, tags=["exit"])
    ret.db.set("destination", here.id)
    return door


def _hero(sim, name="Pat", room=None, **attrs):
    attrs.setdefault("level", 1)
    attrs.setdefault("character_class", "warrior")
    attrs.setdefault("hp", 20)
    attrs.setdefault("max_hp", 20)
    return sim.player(name, location=room, **attrs)


def _mob(sim, name, room, **attrs):
    attrs.setdefault("level", 1)
    attrs.setdefault("hp", 5)
    attrs.setdefault("max_hp", 5)
    return sim.obj(name, location=room, tags=["npc"], **attrs)


async def _kill(sim, victim, killer):
    await sim.world.services["combat"].handle_death(victim, killer=killer)


# --- 11.1 special procedures --------------------------------------------------------


class TestPeacekeeperModes:

    async def _fight(self, sim, room, a, b):
        await sim.world.services["combat"].initiate(a, b)

    async def test_spec_guard_attacks_the_most_evil_fighter(self, merc):
        from realm.core.behaviors import BehaviorRegistry
        room = _room(merc)
        guard = _mob(merc, "cityguard", room, alignment=1000)
        guard.add_behavior(BehaviorRegistry.create("peacekeeper", protect="evil"))
        pat = _hero(merc, room=room, alignment=500)
        orc = _mob(merc, "orc", room, alignment=-800)
        await self._fight(merc, room, pat, orc)
        behavior = next(b for b in guard.get_behaviors() if b.behavior_id == "peacekeeper")
        await behavior.tick(guard, 1.0)
        assert merc.world.services["combat"].target_of(guard) is orc

    async def test_spec_guard_leaves_a_fight_of_the_good_alone(self, merc):
        from realm.core.behaviors import BehaviorRegistry
        room = _room(merc)
        guard = _mob(merc, "cityguard", room, alignment=1000)
        guard.add_behavior(BehaviorRegistry.create("peacekeeper", protect="evil"))
        pat = _hero(merc, room=room, alignment=500)
        sparrer = _mob(merc, "monk", room, alignment=900)
        await self._fight(merc, room, pat, sparrer)
        behavior = next(b for b in guard.get_behaviors() if b.behavior_id == "peacekeeper")
        await behavior.tick(guard, 1.0)
        assert not guard.has_tag("in_combat")

    async def test_a_plain_peacekeeper_only_arrests(self, merc):
        from realm.core.behaviors import BehaviorRegistry
        room = _room(merc)
        guard = _mob(merc, "cityguard", room)
        guard.add_behavior(BehaviorRegistry.create("peacekeeper"))
        pat = _hero(merc, room=room)
        orc = _mob(merc, "orc", room, alignment=-1000)
        await self._fight(merc, room, pat, orc)
        behavior = next(b for b in guard.get_behaviors() if b.behavior_id == "peacekeeper")
        await behavior.tick(guard, 1.0)
        assert not guard.has_tag("in_combat")

    async def test_spec_patrolman_breaks_up_a_fight_on_the_stronger_side(self, merc):
        from realm.core.behaviors import BehaviorRegistry
        room = _room(merc)
        cop = _mob(merc, "patrolman", room)
        cop.add_behavior(BehaviorRegistry.create("peacekeeper", protect="fights"))
        pat = _hero(merc, room=room, level=9)
        rat = _mob(merc, "rat", room, level=2)
        await self._fight(merc, room, rat, pat)
        behavior = next(b for b in cop.get_behaviors() if b.behavior_id == "peacekeeper")
        await behavior.tick(cop, 1.0)
        assert merc.world.services["combat"].target_of(cop) is pat
        assert "Break it up!" in text(merc, pat)


# --- 11.2 player toggles ------------------------------------------------------------


class TestToggles:

    async def test_config_lists_the_merc_toggles(self, merc):
        pat = _hero(merc, room=_room(merc))
        await merc.do(pat, "config")
        listing = text(merc, pat)
        for name in ("autoloot", "autogold", "autosplit", "autoexit", "brief"):
            assert name in listing
        assert get_option(pat, "autoexit") is None          # a default, not a setting

    async def test_without_autoloot_the_corpse_keeps_the_loot_and_money(self, merc):
        room = _room(merc)
        pat = _hero(merc, room=room)
        rat = _mob(merc, "rat", room, credits=7)
        merc.obj("a rat tail", location=rat, tags=["thing"])
        await _kill(merc, rat, pat)
        corpse = next(o for o in room.contents if o.name == "corpse of rat")
        assert [o.name for o in corpse.contents] == ["a rat tail"]
        assert corpse.db.credits == 7
        assert not pat.db.credits
        merc.seen(pat)
        await merc.do(pat, "look corpse")
        assert "7 gold" in text(merc, pat)
        await merc.do(pat, "get all from corpse")
        assert pat.db.credits == 7 and not corpse.db.credits
        assert any(o.name == "a rat tail" for o in pat.contents)

    async def test_autoloot_takes_everything(self, merc):
        room = _room(merc)
        pat = _hero(merc, room=room)
        await merc.do(pat, "config autoloot on")
        rat = _mob(merc, "rat", room, credits=7)
        merc.obj("a rat tail", location=rat, tags=["thing"])
        merc.seen(pat)
        await _kill(merc, rat, pat)
        assert any(o.name == "a rat tail" for o in pat.contents)
        assert pat.db.credits == 7
        seen = text(merc, pat)
        assert "a rat tail" in seen and "7 gold" in seen

    async def test_autogold_takes_only_the_money(self, merc):
        room = _room(merc)
        pat = _hero(merc, room=room)
        await merc.do(pat, "config autogold on")
        rat = _mob(merc, "rat", room, credits=7)
        merc.obj("a rat tail", location=rat, tags=["thing"])
        await _kill(merc, rat, pat)
        assert pat.db.credits == 7
        assert not any(o.name == "a rat tail" for o in pat.contents)

    async def test_get_gold_from_a_corpse(self, merc):
        room = _room(merc)
        pat = _hero(merc, room=room)
        rat = _mob(merc, "rat", room, credits=4)
        await _kill(merc, rat, pat)
        await merc.do(pat, "get gold from corpse")
        assert pat.db.credits == 4

    async def test_autosplit_shares_the_money_with_the_party(self, merc):
        room = _room(merc)
        pat = _hero(merc, room=room)
        sam = _hero(merc, "Sam", room=room)
        sam.db.following = pat.id
        await merc.do(pat, "config autogold on")
        await merc.do(pat, "config autosplit on")
        rat = _mob(merc, "rat", room, credits=9)
        await _kill(merc, rat, pat)
        assert (pat.db.credits, sam.db.credits) == (5, 4)

    async def test_autoexit_off_hides_the_exits_line(self, merc):
        here, there = _room(merc, "Road"), _room(merc, "Field")
        _link(merc, here, there, "north", "south")
        pat = _hero(merc, room=here)
        await merc.do(pat, "look")
        assert "Exits: |gnorth|n" in text(merc, pat)
        await merc.do(pat, "config autoexit off")
        merc.seen(pat)
        await merc.do(pat, "look")
        assert "Exits:" not in text(merc, pat)

    async def test_brief_leaves_out_descriptions_while_walking(self, merc):
        here = _room(merc, "Road")
        there = _room(merc, "Field")
        there.description = "Tall grass sways in the wind."
        _link(merc, here, there, "north", "south")
        pat = _hero(merc, room=here, move=100, max_move=100)
        await merc.do(pat, "config brief on")
        merc.seen(pat)
        await merc.do(pat, "north")
        walked = text(merc, pat)
        assert "Field" in walked and "Tall grass" not in walked
        await merc.do(pat, "look")
        assert "Tall grass" in text(merc, pat)


# --- 11.3 group play ----------------------------------------------------------------


class TestGroupPlay:

    async def test_experience_splits_by_level(self, merc):
        room = _room(merc)
        pat = _hero(merc, room=room, level=3)
        sam = _hero(merc, "Sam", room=room, level=1)
        sam.db.following = pat.id
        ogre = _mob(merc, "ogre", room, level=3, points=400)
        await _kill(merc, ogre, pat)
        # 300 and 100 by level, then ROM's low-level bonus: 10 / (level + 4).
        assert (pat.db.xp, sam.db.xp) == (300 * 10 // 7, 100 * 10 // 5)

    async def test_a_party_member_elsewhere_gets_nothing(self, merc):
        room, away = _room(merc), _room(merc, "Away")
        pat = _hero(merc, room=room)
        sam = _hero(merc, "Sam", room=away)
        sam.db.following = pat.id
        ogre = _mob(merc, "ogre", room, level=1, points=100)
        await _kill(merc, ogre, pat)
        assert pat.db.xp == 200 and not sam.db.xp       # 100, doubled at level 1 (ROM)

    async def test_split_shares_coins(self, merc):
        room = _room(merc)
        pat = _hero(merc, room=room, credits=10)
        sam = _hero(merc, "Sam", room=room)
        kim = _hero(merc, "Kim", room=room)
        sam.db.following = pat.id
        kim.db.following = sam.id
        await merc.do(pat, "split 10")
        assert (pat.db.credits, sam.db.credits, kim.db.credits) == (4, 3, 3)
        assert "Your share is 4 gold" in text(merc, pat)
        assert "Pat splits 10 gold. Your share is 3 gold." in text(merc, sam)

    async def test_split_refusals(self, merc):
        room = _room(merc)
        pat = _hero(merc, room=room, credits=3)
        await merc.do(pat, "split 2")
        assert "Just keep it all." in text(merc, pat)
        sam = _hero(merc, "Sam", room=room)
        sam.db.following = pat.id
        await merc.do(pat, "split 9")
        assert "You don't have that much to split." in text(merc, pat)
        await merc.do(pat, "split lots")
        assert "Split how much?" in text(merc, pat)
        await merc.do(pat, "split 1")
        assert "Don't even bother, cheapskate." in text(merc, pat)
        assert pat.db.credits == 3

    async def test_group_is_party(self, merc):
        room = _room(merc)
        pat = _hero(merc, room=room)
        sam = _hero(merc, "Sam", room=room)
        sam.db.following = pat.id
        await merc.do(pat, "group")
        assert "Your party:" in text(merc, pat)

    async def test_report_says_the_pools_aloud(self, merc):
        room = _room(merc)
        pat = _hero(merc, room=room, hp=12, max_hp=20, mana=50, max_mana=100,
                    move=80, max_move=100)
        sam = _hero(merc, "Sam", room=room)
        await merc.do(pat, "report")
        line = "I have 12/20 hp, 50/100 mana, and 80/100 move."
        assert line in text(merc, pat)
        heard = text(merc, sam)
        assert line in heard and "Pat" in heard

    async def test_a_world_report_command_comes_first(self, merc):
        room = _room(merc)
        pat = _hero(merc, room=room)
        warden = merc.obj("warden", location=room)
        warden.db.cmd_report = "$report:\n    pemit(enactor, 'Quest report.')"
        await merc.do(pat, "report")
        seen = text(merc, pat)
        assert "Quest report." in seen and "I have" not in seen


# --- 11.4 looking around ------------------------------------------------------------


class TestLookingAround:

    async def test_scan_shows_who_is_one_room_away(self, merc):
        here, north, east = _room(merc, "Road"), _room(merc, "Field"), _room(merc, "Barn")
        _link(merc, here, north, "north", "south")
        _link(merc, here, east, "east", "west")
        pat = _hero(merc, room=here)
        _mob(merc, "a goblin", north)
        _hero(merc, "Sam", room=east)
        await merc.do(pat, "scan")
        seen = text(merc, pat)
        assert "north (Field): a goblin" in seen
        assert "east (Barn): Sam" in seen

    async def test_scan_leaves_out_who_is_out_of_play(self, merc):
        # MUD_PLAN step 17: a character who quit is not in the world.
        here, north = _room(merc, "Road"), _room(merc, "Field")
        _link(merc, here, north, "north", "south")
        pat = _hero(merc, room=here)
        sam = _hero(merc, "Sam", room=north)
        merc.sessions.unlink_player_from_session(merc.session(sam))
        await merc.do(pat, "scan")
        assert "Sam" not in text(merc, pat)

    async def test_scan_respects_sight_and_doors(self, merc):
        here, north, east = _room(merc, "Road"), _room(merc, "Cave"), _room(merc, "Shed")
        _link(merc, here, north, "north", "south")
        door = _link(merc, here, east, "east", "west")
        door.add_tag("closed")
        north.add_tag("dark")
        pat = _hero(merc, room=here)
        _mob(merc, "a goblin", north)
        _mob(merc, "a farmer", east)
        await merc.do(pat, "scan")
        seen = text(merc, pat)
        assert "goblin" not in seen and "farmer" not in seen
        assert "You see no one nearby." in seen

    async def test_exits_lists_where_each_goes(self, merc):
        here, north, east, down = (_room(merc, "Road"), _room(merc, "Field"),
                                   _room(merc, "Shed"), _room(merc, "Cellar"))
        _link(merc, here, north, "north", "south")
        door = _link(merc, here, east, "east", "west")
        door.add_tag("closed")
        _link(merc, here, down, "down", "up")
        down.add_tag("dark")
        pat = _hero(merc, room=here)
        await merc.do(pat, "exits")
        seen = text(merc, pat)
        assert "Obvious exits:" in seen
        assert "north - Field" in seen
        assert "east  - (closed)" in seen
        assert "down  - Too dark to tell" in seen

    async def test_where_lists_players_in_the_zone(self, merc):
        a, b, c = _room(merc, "Gate"), _room(merc, "Market"), _room(merc, "Swamp")
        for room in (a, b):
            room.add_tag("zone:town")
        c.add_tag("zone:marsh")
        pat = _hero(merc, room=a)
        _hero(merc, "Sam", room=b)
        _hero(merc, "Kim", room=c)
        await merc.do(pat, "where")
        seen = text(merc, pat)
        assert "Players near you:" in seen
        assert "Sam" in seen and "Market" in seen
        assert "Kim" not in seen

    async def test_where_finds_someone_by_name_in_the_zone(self, merc):
        # ROM's `where <name>`: who of that name is in this area, and where;
        # how a new character finds a fido.
        a, b, c = _room(merc, "Gate"), _room(merc, "Market"), _room(merc, "Swamp")
        for room in (a, b):
            room.add_tag("zone:town")
        c.add_tag("zone:marsh")
        pat = _hero(merc, room=a)
        _mob(merc, "the beastly fido", b)
        _mob(merc, "the beastly fido", c)                # another zone
        _mob(merc, "the cityguard", b)
        await merc.do(pat, "where fido")
        seen = text(merc, pat)
        assert "the beastly fido" in seen and "Market" in seen
        assert "Swamp" not in seen and "cityguard" not in seen
        await merc.do(pat, "where dragon")
        assert "You didn't find any dragon." in text(merc, pat)

    async def test_consider_compares_levels_under_merc(self, merc):
        room = _room(merc)
        pat = _hero(merc, room=room, level=12)
        _mob(merc, "rat", room, level=1)
        _mob(merc, "goblin", room, level=5)
        _mob(merc, "dragon", room, level=30)
        peer = _mob(merc, "knight", room, level=13)
        await merc.do(pat, "consider rat")
        assert "You can kill rat naked and weaponless." in text(merc, pat)
        await merc.do(pat, "consider goblin")
        assert "Goblin is no match for you." in text(merc, pat)
        await merc.do(pat, "consider dragon")
        assert "Death will thank you for your gift." in text(merc, pat)
        await merc.do(pat, "consider knight")
        assert "The perfect match!" in text(merc, pat)
        assert peer.db.level == 13


# --- 11.5 alignment -----------------------------------------------------------------


class TestAlignment:

    async def test_killing_evil_makes_you_good_and_good_evil(self, merc):
        room = _room(merc)
        pat = _hero(merc, room=room, alignment=0)
        await _kill(merc, _mob(merc, "orc", room, alignment=-1000), pat)
        assert pat.db.alignment == 125
        sam = _hero(merc, "Sam", room=room, alignment=0)
        await _kill(merc, _mob(merc, "priest", room, alignment=1000), sam)
        assert sam.db.alignment == -125

    async def test_killing_a_peer_drifts_toward_neutral(self, merc):
        room = _room(merc)
        pat = _hero(merc, room=room, alignment=400)
        await _kill(merc, _mob(merc, "farmer", room, alignment=300), pat)
        assert pat.db.alignment == 300

    async def test_score_shows_alignment(self, merc):
        pat = _hero(merc, room=_room(merc), alignment=-400)
        await merc.do(pat, "score")
        assert "Alignment: -400 (evil)" in text(merc, pat)

    async def test_an_anti_evil_item_zaps_an_evil_wearer(self, merc):
        room = _room(merc)
        pat = _hero(merc, room=room, alignment=-500)
        ring = merc.obj("a holy ring", location=pat,
                        tags=["thing", "wearable", "anti_evil"], slot="finger")
        await merc.do(pat, "wear ring")
        assert ring.location is room and not ring.has_tag("worn")
        assert "You are zapped by a holy ring and drop it." in text(merc, pat)

    async def test_an_anti_good_weapon_will_not_be_wielded_by_the_good(self, merc):
        room = _room(merc)
        pat = _hero(merc, room=room, alignment=800)
        blade = merc.obj("a black blade", location=pat,
                         tags=["thing", "weapon", "wieldable", "anti_good"])
        await merc.do(pat, "wield blade")
        assert blade.location is room and not blade.has_tag("wielded")

    async def test_a_neutral_may_wear_what_is_anti_evil(self, merc):
        room = _room(merc)
        pat = _hero(merc, room=room, alignment=0)
        ring = merc.obj("a holy ring", location=pat,
                        tags=["thing", "wearable", "anti_evil"], slot="finger")
        await merc.do(pat, "wear ring")
        assert ring.has_tag("worn")

    async def test_turning_evil_zaps_what_is_worn(self, merc):
        room = _room(merc)
        pat = _hero(merc, room=room, alignment=-300)
        ring = merc.obj("a holy ring", location=pat,
                        tags=["thing", "wearable", "anti_evil"], slot="finger")
        await merc.do(pat, "wear ring")
        assert ring.has_tag("worn")
        await _kill(merc, _mob(merc, "saint", room, alignment=1000), pat)
        assert pat.db.alignment <= -350
        assert ring.location is room and not ring.has_tag("worn")


# --- 11.6 level limits and titles ---------------------------------------------------


class TestLevels:

    def test_the_level_cap_stops_advancement(self):
        from realm.config.loader import Settings
        with Simulator(game_system=MERC, settings=Settings(raw={"LEVEL_CAP": 3})) as sim:
            pat = _hero(sim, room=_room(sim))
            sim.world.rules.grant_award(pat, 100000)
            assert pat.db.level == 3

    def test_the_default_cap_is_fifty(self, merc):
        assert merc.world.setting("LEVEL_CAP") == 50
        pat = _hero(merc, room=_room(merc), level=50)
        merc.world.rules.grant_award(pat, 10 ** 6)
        assert pat.db.level == 50

    async def test_who_shows_the_class_title(self, merc):
        room = _room(merc)
        pat = _hero(merc, room=room, level=1, character_class="warrior")
        _hero(merc, "Sam", room=room, level=22, character_class="mage")
        await merc.do(pat, "who")
        seen = text(merc, pat)
        assert "Pat the Swordpupil (1 warrior)" in seen
        assert "Sam the Sorcerer (22 mage)" in seen

    async def test_wear_refuses_an_item_above_your_level(self, merc):
        room = _room(merc)
        pat = _hero(merc, room=room, level=3)
        helm = merc.obj("a great helm", location=pat,
                        tags=["thing", "wearable"], slot="head", level=10)
        await merc.do(pat, "wear helm")
        assert not helm.has_tag("worn")
        assert "You must be level 10 to use a great helm." in text(merc, pat)
        sword = merc.obj("a runed sword", location=pat,
                         tags=["thing", "weapon", "wieldable"], level=10)
        await merc.do(pat, "wield sword")
        assert not sword.has_tag("wielded")
        pat.db.level = 10
        await merc.do(pat, "wear helm")
        assert helm.has_tag("worn")


# --- 11.7 recall --------------------------------------------------------------------


class TestRecall:

    async def test_recall_halves_move_and_goes_to_the_start(self, merc):
        temple, road = _room(merc, "Temple"), _room(merc, "Road")
        merc.startup_room = temple
        pat = _hero(merc, room=road, move=80, max_move=100)
        await merc.do(pat, "recall")
        assert pat.location is temple
        assert pat.db.move == 40
        assert "Temple" in text(merc, pat)

    async def test_recall_goes_home_first(self, merc):
        temple, road, inn = _room(merc, "Temple"), _room(merc, "Road"), _room(merc, "Inn")
        merc.startup_room = temple
        pat = _hero(merc, room=road, move=80, max_move=100, home=inn.id)
        await merc.do(pat, "recall")
        assert pat.location is inn

    async def test_no_recall_rooms_refuse(self, merc):
        temple, pit = _room(merc, "Temple"), _room(merc, "Pit")
        pit.add_tag("no_recall")
        merc.startup_room = temple
        pat = _hero(merc, room=pit, move=80, max_move=100)
        await merc.do(pat, "recall")
        assert pat.location is pit and pat.db.move == 80
        assert "You cannot recall from here." in text(merc, pat)

    async def test_in_combat_recall_takes_a_check(self, merc, monkeypatch):
        temple, road = _room(merc, "Temple"), _room(merc, "Road")
        merc.startup_room = temple
        pat = _hero(merc, room=road, move=80, max_move=100, xp=100)
        orc = _mob(merc, "orc", road, hp=50, max_hp=50)
        await merc.world.services["combat"].initiate(orc, pat)
        monkeypatch.setattr("realm.games.merc.system.random.randint", lambda a, b: 100)
        await merc.do(pat, "recall")
        assert pat.location is road
        assert "You failed!" in text(merc, pat)
        monkeypatch.setattr("realm.games.merc.system.random.randint", lambda a, b: 1)
        await merc.do(pat, "recall")
        assert pat.location is temple
        assert not pat.has_tag("in_combat")
        assert pat.db.xp == 75                                  # ROM: 25 for fleeing
        assert merc.world.services["combat"].encounter_of(pat) is None


# --- the importer -------------------------------------------------------------------

PARITY_ARE = """\
#AREA
parity.are~
Parity~
{ All } Test    Parity~
400 499
#MOBILES
#401
patrolman~
the patrolman~
A patrolman walks his beat.
~
He looks bored.
~
human~
AB 0 600 0
10 0 1d1+99 1d1+99 1d6 punch
0 0 0 0
0 0 0 0
stand stand male 2500
0 0 medium 0
#402
mayor~
the mayor~
The mayor is here.
~
He looks important.
~
human~
AB 0 900 0
20 0 1d1+99 1d1+99 1d6 punch
0 0 0 0
0 0 0 0
stand stand male 0
0 0 medium 0
#0
#OBJECTS
#410
sword unholy~
an unholy sword~
An unholy sword lies here.~
steel~
weapon J AN
sword 2 5 slash 0
12 10 500 P
#411
ring plain~
a plain ring~
A plain ring lies here.~
iron~
jewelry KL AB
0 0 0 0 0
1 1 10 P
#0
#ROOMS
#420
The Pit~
A pit no prayer escapes.
~
0 N 0
S
#0
#SPECIALS
M 401 spec_patrolman
M 402 spec_mayor
S
#$
"""


class TestImporter:

    @pytest.fixture
    def area(self):
        from realm.tools import rom_import
        return rom_import.convert(PARITY_ARE)

    def test_spec_patrolman_breaks_up_fights(self, area):
        proto = area.mob_protos[401]
        keeper = next(b for b in proto["behaviors"] if b["behavior_id"] == "peacekeeper")
        assert keeper["params"]["protect"] == "fights"

    def test_the_guard_procedures(self):
        from realm.tools.rom_import import SPEC_BEHAVIORS
        assert SPEC_BEHAVIORS["spec_guard"] == {
            "behavior_id": "peacekeeper", "params": {"protect": "evil"}}
        assert SPEC_BEHAVIORS["spec_executioner"]["behavior_id"] == "peacekeeper"
        assert SPEC_BEHAVIORS["spec_executioner"]["params"] == {}

    def test_a_bespoke_procedure_stays_a_gap(self, area):
        assert not area.mob_protos[402]["behaviors"]
        assert any("spec_mayor" in gap for gap in area.gaps)

    def test_mobs_carry_their_wealth_as_money(self, area):
        attrs = area.mob_protos[401]["attrs"]
        assert attrs["credits"] == 25                       # 2500 silver
        assert attrs["rom_wealth"] == 2500 and "gold" not in attrs

    def test_anti_alignment_flags_become_tags(self, area):
        assert "anti_good" in area.obj_protos[410]["tags"]
        assert {"anti_evil", "anti_neutral"} <= set(area.obj_protos[411]["tags"])

    def test_no_recall_rooms(self, area):
        pit = next(o for o in area.objects if o.get("name") == "The Pit")
        assert "no_recall" in pit["tags"]

    def test_the_refresh_script_brings_an_old_area_up_to_date(self):
        import importlib.util
        from pathlib import Path
        script = Path(__file__).resolve().parents[1] / "scripts" / "dev" / "refresh_rom_items.py"
        spec = importlib.util.spec_from_file_location("refresh_rom_items", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        data = {"objects": [
            {"id": "m1", "name": "cityguard", "tags": ["npc", "rom_spec:spec_guard"],
             "attrs": {"gold": 150, "rom_act": ["A"]},
             "behaviors": [{"behavior_id": "peacekeeper", "params": {}}]},
            {"id": "o1", "name": "a ring", "tags": ["thing", "jewelry"],
             "attrs": {"item_type": "jewelry", "rom_values": [0, 0, 0, 0, 0],
                       "rom_wear": ["A", "B"], "rom_extra": ["K"]}},
            {"id": "r1", "name": "Pit", "tags": ["room"],
             "attrs": {"sector": "inside", "rom_room_flags": ["N"]}},
        ]}
        module.refresh(data)
        guard, ring, pit = data["objects"]
        assert guard["attrs"]["credits"] == 1 and guard["attrs"]["rom_wealth"] == 150
        assert "gold" not in guard["attrs"]
        assert guard["behaviors"] == [{"behavior_id": "peacekeeper",
                                       "params": {"protect": "evil"}}]
        assert "anti_evil" in ring["tags"]
        assert "no_recall" in pit["tags"]


async def test_short_forms_players_already_typed_still_work():
    """`scan`, `split` and `report` share letters with `score`, `spells`
    and `reply`; the short forms keep their old meaning."""
    sim = Simulator()
    try:
        ann = sim.player("Ann", location=sim.room("Hall"))
        for line, expected in (("rep", "reply to"), ("sp", "spells"), ("sc", "points")):
            await sim.do(ann, line)
            out = "\n".join(sim.seen(ann))
            assert "Ambiguous" not in out and expected in out, (line, out)
    finally:
        sim.close()
