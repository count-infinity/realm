"""
MUD_PLAN step 13: pets, charmed followers and mounts (the ``companions``
feature), after CoffeeMud's followers and ROM's pet shops and charm person.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from realm.config.loader import Settings
from realm.core.action_tags import HOSTILE
from realm.core.action_types import ActionType
from realm.core.beats import deliver_beat
from realm.core.objects import GameObject
from realm.core.propagation import ROOM_TARGET_CHAIN, Action, propagate
from realm.std.companions import companions_of, master_of, set_master
from realm.testing import Simulator

MERC = "realm.games.merc.system.MercSystem"
MIDGAARD = Path(__file__).resolve().parents[1] / "realm" / "examples" / "midgaard"


def _sim(*, merc: bool = False, **raw) -> Simulator:
    settings = Settings(raw=raw)
    return Simulator(settings=settings, game_system=MERC if merc else None)


@pytest.fixture
def sim():
    s = _sim()
    try:
        yield s
    finally:
        _close(s)


@pytest.fixture
def merc():
    s = _sim(merc=True)
    try:
        yield s
    finally:
        _close(s)


def _close(s: Simulator) -> None:
    from realm.std.combat.combatant import clear_combatant_cache
    combat = s.world.services.get("combat")
    if combat is not None:
        combat.stop_all()
    clear_combatant_cache()
    s.close()


def _creature(sim, name, room, *, level=1, hp=20, **attrs):
    return sim.obj(name, location=room, tags=["npc"], level=level, hp=hp, max_hp=hp, **attrs)


def _path(sim, *, there_tags=()):
    here = sim.room("Road")
    there = sim.room("Meadow")
    for tag in there_tags:
        there.add_tag(tag)
    north = sim.obj("north", location=here, tags=["exit"], destination=there.id)
    sim.obj("south", location=there, tags=["exit"], destination=here.id)
    return here, there, north


# --- 13.1 bonding and the limit -------------------------------------------------


async def test_a_companion_is_a_master_attribute_and_follows(sim):
    here, there, _north = _path(sim)
    alice = sim.player("Alice", location=here)
    kitten = _creature(sim, "kitten", here)
    assert await set_master(kitten, alice) is None
    assert master_of(kitten) is alice
    assert companions_of(alice) == [kitten]
    assert kitten.db.master == alice.id and kitten.db.following == alice.id
    assert kitten.owner is None                       # building authority untouched
    await sim.do(alice, "north")
    assert kitten.location is there


async def test_the_neutral_limit_is_two(sim):
    room = sim.room("Den")
    alice = sim.player("Alice", location=room)
    pets = [_creature(sim, f"pup{i}", room) for i in range(3)]
    assert await set_master(pets[0], alice) is None
    assert await set_master(pets[1], alice) is None
    assert await set_master(pets[2], alice) == "You can't accept any more followers."
    assert master_of(pets[2]) is None
    await sim.do(alice, "companions")
    assert "You have 2 of 2 followers." in "\n".join(sim.seen(alice))


async def test_the_game_system_hook_answers_merc_by_level(merc):
    room = merc.room("Den")
    alice = merc.player("Alice", location=room, level=1)
    a, b = _creature(merc, "pup", room), _creature(merc, "cub", room)
    assert await set_master(a, alice) is None
    assert await set_master(b, alice) is not None      # 1 + 1 // 10 = 1
    alice.db.level = 10
    assert await set_master(b, alice) is None          # 1 + 10 // 10 = 2


async def test_a_charisma_rule_in_config_wins():
    s = _sim(merc=True, COMPANION_LIMIT_RULE="1 + (get_attr(me, 'charisma', 10) - 6) // 3")
    try:
        room = s.room("Den")
        alice = s.player("Alice", location=room, level=1, charisma=15)
        pets = [_creature(s, f"pup{i}", room) for i in range(5)]
        for pet in pets[:4]:                           # 1 + (15 - 6) // 3 = 4
            assert await set_master(pet, alice) is None
        assert await set_master(pets[4], alice) is not None
        await s.do(alice, "companions")
        assert "You have 4 of 4 followers." in "\n".join(s.seen(alice))
    finally:
        _close(s)


async def test_a_companions_own_companions_count(sim):
    room = sim.room("Den")
    alice = sim.player("Alice", location=room)
    wolf, cub = _creature(sim, "wolf", room), _creature(sim, "cub", room)
    pup = _creature(sim, "pup", room)
    await set_master(cub, wolf)                        # the wolf has a cub
    assert await set_master(wolf, alice) is None       # 1 + the cub = 2
    assert await set_master(pup, alice) == "You can't accept any more followers."


async def test_the_level_difference_limit():
    s = _sim(COMPANION_LEVEL_DIFF=2)
    try:
        room = s.room("Den")
        alice = s.player("Alice", location=room, level=2)
        dragon = _creature(s, "dragon", room, level=5)
        assert await set_master(dragon, alice) == "The dragon is too advanced for you."
        dragon.db.level = 4
        assert await set_master(dragon, alice) is None
    finally:
        _close(s)


# --- order, dismiss ------------------------------------------------------------


async def test_order_runs_a_command_as_the_companion(sim):
    room = sim.room("Den")
    alice = sim.player("Alice", location=room)
    bob = sim.player("Bob", location=room)
    kitten = _creature(sim, "kitten", room)
    await set_master(kitten, alice)
    await sim.do(alice, "order kitten say mew")
    heard = "\n".join(sim.seen(bob))
    assert "Alice orders the kitten to 'say mew'." in heard
    assert "Kitten says" in heard and "mew" in heard


async def test_order_refuses_admin_commands_order_and_quit(sim):
    room = sim.room("Den")
    alice = sim.player("Alice", location=room)
    kitten = _creature(sim, "kitten", room)
    await set_master(kitten, alice)
    for line in ("@dig Lair", "quit", "order kitten say hi"):
        await sim.do(alice, f"order kitten {line}")
        assert f"You can't order anyone to '{line}'." in sim.seen(alice)
    assert not any(o.name == "Lair" for o in sim.store.all_cached())


async def test_order_refused_setting_narrows_it():
    s = _sim(ORDER_REFUSED=["drop"])
    try:
        room = s.room("Den")
        alice = s.player("Alice", location=room)
        kitten = _creature(s, "kitten", room)
        s.obj("ball", location=kitten)
        await set_master(kitten, alice)
        await s.do(alice, "order kitten drop ball")
        assert "You can't order anyone to 'drop ball'." in s.seen(alice)
    finally:
        _close(s)


async def test_order_only_your_own(sim):
    room = sim.room("Den")
    alice = sim.player("Alice", location=room)
    _creature(sim, "stray", room)
    await sim.do(alice, "order stray say hi")
    assert "Do it yourself!" in sim.seen(alice)


async def test_dismiss_releases(sim):
    room = sim.room("Den")
    alice = sim.player("Alice", location=room)
    kitten = _creature(sim, "kitten", room)
    await set_master(kitten, alice)
    await sim.do(alice, "dismiss kitten")
    assert master_of(kitten) is None and kitten.db.get("following") is None
    assert not kitten.has_tag("companion")
    assert companions_of(alice) == []


# --- fighting together --------------------------------------------------------


async def test_a_companion_joins_its_masters_fight_and_its_kill_pays(merc, monkeypatch):
    room = merc.room("Yard")
    alice = merc.player("Alice", location=room, level=1, hp=50, max_hp=50)
    kitten = _creature(merc, "kitten", room)
    fido = _creature(merc, "fido", room, points=100)
    await set_master(kitten, alice)
    manager = merc.world.services["combat"]
    await manager.initiate(alice, fido)
    await propagate(Action(actor=alice, target=fido, action_type="combat:on_attack",
                           tags={HOSTILE}))
    encounter = manager.encounter_of(alice)
    assert encounter.get(kitten.id) is not None
    assert encounter.get(kitten.id).target_id == fido.id
    assert encounter.get(fido.id).target_id == alice.id   # nobody else retargeted

    paid = []
    monkeypatch.setattr(merc.game_system, "grant_award",
                        lambda player, amount: paid.append((player, amount)))
    deaths = []
    fido.db.on_death = "set_attr(me, 'killer_seen', name(enactor))"
    merc.world.observe(_record(deaths))
    await manager.handle_death(fido, kitten)
    assert [p for p, _ in paid] == [alice]
    assert deaths and deaths[0].actor is kitten          # the event keeps the companion


def _record(into):
    async def observer(action):
        if action.action_type == "combat:on_death":
            into.append(action)
    return observer


async def test_a_companion_never_attacks_its_master(sim):
    room = sim.room("Den")
    alice = sim.player("Alice", location=room, hp=10, max_hp=10)
    kitten = _creature(sim, "kitten", room)
    await set_master(kitten, alice)
    swipe = await propagate(Action(actor=kitten, target=alice, action_type="combat:on_attack",
                                   tags={HOSTILE}))
    assert swipe.blocked and "You like Alice too much." in swipe.block_reason


async def test_a_master_who_attacks_its_companion_breaks_the_bond(sim):
    room = sim.room("Den")
    alice = sim.player("Alice", location=room, hp=10, max_hp=10)
    kitten = _creature(sim, "kitten", room)
    await set_master(kitten, alice)
    await propagate(Action(actor=alice, target=kitten, action_type="combat:on_attack",
                           tags={HOSTILE}))
    assert master_of(kitten) is None


async def test_a_dead_companion_leaves_the_list(merc):
    room = merc.room("Yard")
    alice = merc.player("Alice", location=room, level=1)
    kitten = _creature(merc, "kitten", room)
    await set_master(kitten, alice)
    await merc.world.services["combat"].handle_death(kitten, None)
    assert companions_of(alice) == []


# --- leaving and returning ------------------------------------------------------


async def _connection(player, kind):
    await propagate(Action(actor=player, target=player.location, action_type=kind,
                           chain=ROOM_TARGET_CHAIN))


async def test_companions_leave_and_return_with_their_master(sim):
    den = sim.room("Den")
    alice = sim.player("Alice", location=den)
    bob = sim.player("Bob", location=den)
    kitten = _creature(sim, "kitten", den)
    await set_master(kitten, alice)
    await _connection(alice, ActionType.DISCONNECT)
    assert kitten.location is None and kitten.db.companion_room == den.id
    assert "The kitten goes with Alice." in "\n".join(sim.seen(bob))
    hall = sim.room("Hall")
    alice.location = hall
    await _connection(alice, ActionType.CONNECT)
    assert kitten.location is hall and kitten.db.get("companion_room") is None
    assert master_of(kitten) is alice


async def test_a_companion_whose_master_is_deleted_is_released(sim):
    den = sim.room("Den")
    alice = sim.player("Alice", location=den)
    kitten = _creature(sim, "kitten", den)
    await set_master(kitten, alice)
    await _connection(alice, ActionType.DISCONNECT)
    await sim.store.delete(alice)
    from realm.std.companions.companions import release_orphans
    assert await release_orphans(sim.store) == 1
    assert kitten.db.get("master") is None and kitten.location is den


# --- softcode and events ------------------------------------------------------


async def test_softcode_bonds_releases_and_fires_events(sim):
    den = sim.room("Den")
    alice = sim.player("Alice", location=den)
    biscuit = _creature(sim, "Biscuit", den)
    biscuit.db.on_bond = "set_attr(me, 'bonded_by', name(enactor))"
    biscuit.db.on_release = "set_attr(me, 'freed_because', adata('reason'))"
    _r, err = await sim.eval(biscuit, "set_master(me, enactor)", enactor=alice)
    assert err is None and master_of(biscuit) is alice
    assert biscuit.db.bonded_by == "Alice"
    result, _ = await sim.eval(biscuit, "result = name(master(me)) + str(len(companions(enactor)))",
                               enactor=alice)
    assert result == "Alice1"
    await sim.eval(biscuit, "release(me)")
    assert master_of(biscuit) is None and biscuit.db.freed_because == "released"


# --- 13.2 pets from shops ------------------------------------------------------


def _pet_shop(sim):
    shop = sim.room("Pet Shop")
    kennel = sim.room("Kennel")
    kitten = _creature(sim, "kitten", kennel, value=12)
    mare = _creature(sim, "grey mare", kennel, value=40)
    mare.add_tag("mount")
    keeper = sim.obj("shopkeeper", location=shop, tags=["npc"])
    from realm.core.behaviors import BehaviorRegistry
    keeper.add_behavior(BehaviorRegistry.create(
        "shopkeeper", markup=1.0, sells_pets=True, pet_stock=[kitten.id, mare.id]))
    return shop, kitten, mare


async def test_buying_a_pet(sim):
    shop, kitten, _mare = _pet_shop(sim)
    alice = sim.player("Alice", location=shop, credits=100)
    await sim.do(alice, "list")
    listing = "\n".join(sim.seen(alice))
    assert "Pets for sale:" in listing and "kitten — 12" in listing
    assert "grey mare (mount) — 40" in listing
    await sim.do(alice, "buy kitten")
    bought = companions_of(alice)
    assert len(bought) == 1 and bought[0] is not kitten
    assert bought[0].location is shop and bought[0].name == "kitten"
    assert alice.db.credits == 88
    assert kitten.location.name == "Kennel" and master_of(kitten) is None


async def test_a_pet_past_the_limit_is_not_sold(sim):
    shop, kitten, mare = _pet_shop(sim)
    alice = sim.player("Alice", location=shop, credits=100)
    await sim.do(alice, "buy kitten")
    await sim.do(alice, "buy mare")
    sim.seen(alice)
    await sim.do(alice, "buy kitten")
    assert "You can't accept any more followers." in sim.seen(alice)
    assert alice.db.credits == 48 and len(companions_of(alice)) == 2


# --- charm ------------------------------------------------------------------------


def _charm_spell(sim, *, turns_hostile=False, per_level=0, duration=3):
    spell = GameObject(name="charm person", tags=["spell_def"])
    spell.db.set("level", 1)
    spell.db.set("target", "victim")
    spell.db.set("effects", [{"type": "charm", "duration": duration, "per_level": per_level,
                              "turns_hostile": turns_hostile, "save": "negates"}])
    sim.add(spell)
    return spell


async def _beats(obj, n):
    for _ in range(n):
        await deliver_beat(obj)


async def test_a_charm_lasts_then_expires(sim):
    room = sim.room("Glade")
    alice = sim.player("Alice", location=room, level=5)
    bear = _creature(sim, "bear", room, level=3)
    bear.db.on_release = "set_attr(me, 'why', adata('reason'))"
    _charm_spell(sim, duration=3)
    await sim.do(alice, "cast 'charm person' bear")
    assert master_of(bear) is alice and bear.has_tag("charmed")
    assert "The bear looks at you with adoring eyes." in sim.seen(alice)
    await _beats(bear, 1)
    assert master_of(bear) is alice
    await _beats(bear, 3)
    assert master_of(bear) is None and not bear.has_tag("charmed")
    assert "The bear's free will returns." in "\n".join(sim.seen(alice))
    assert bear.db.why == "charm_ended"                # companion:on_release


async def test_a_charm_that_turns_hostile_attacks_its_former_master(merc, monkeypatch):
    monkeypatch.setattr(merc.game_system, "saving_throw", lambda target, level: False)
    room = merc.room("Glade")
    alice = merc.player("Alice", location=room, level=5, hp=50, max_hp=50)
    bear = _creature(merc, "bear", room, level=3)
    _charm_spell(merc, duration=1, turns_hostile=True)
    await merc.do(alice, "cast 'charm person' bear")
    assert master_of(bear) is alice
    await _beats(bear, 2)
    encounter = merc.world.services["combat"].encounter_of(bear)
    assert master_of(bear) is None and encounter is not None
    assert encounter.get(bear.id).target_id == alice.id


async def test_a_saved_target_is_not_charmed(sim, monkeypatch):
    room = sim.room("Glade")
    alice = sim.player("Alice", location=room, level=5)
    bear = _creature(sim, "bear", room, level=3)
    _charm_spell(sim)
    monkeypatch.setattr(sim.game_system, "saving_throw", lambda target, level: True)
    await sim.do(alice, "cast 'charm person' bear")
    assert master_of(bear) is None and not bear.has_tag("charmed")


async def test_a_stronger_creature_resists_the_level_check(sim):
    room = sim.room("Glade")
    alice = sim.player("Alice", location=room, level=2)
    dragon = _creature(sim, "dragon", room, level=9)
    _charm_spell(sim)
    await sim.do(alice, "cast 'charm person' dragon")
    assert master_of(dragon) is None
    assert "The dragon is too strong-willed for you." in sim.seen(alice)


async def test_pets_and_charms_share_the_limit(sim):
    shop, _kitten, _mare = _pet_shop(sim)
    alice = sim.player("Alice", location=shop, credits=100, level=5)
    await sim.do(alice, "buy kitten")
    await sim.do(alice, "buy mare")
    bear = _creature(sim, "bear", shop, level=3)
    _charm_spell(sim)
    sim.seen(alice)
    await sim.do(alice, "cast 'charm person' bear")
    assert master_of(bear) is None
    assert "You can't accept any more followers." in sim.seen(alice)


async def test_players_are_charmed_only_where_the_zone_allows_it(sim):
    room = sim.room("Square")
    alice = sim.player("Alice", location=room, level=5)
    bob = sim.player("Bob", location=room, level=1)
    _charm_spell(sim)
    await sim.do(alice, "cast 'charm person' bob")
    assert master_of(bob) is None
    assert "Bob can't be charmed here." in sim.seen(alice)
    room.add_tag("zone:arena")
    sim.obj("Arena Rules", tags=["zone_master", "zone:arena"], pvp=True)
    await sim.do(alice, "cast 'charm person' bob")
    assert master_of(bob) is alice


async def test_merc_classic_ships_charm_person():
    import json
    pack = Path(__file__).resolve().parents[1] / "realm" / "packs" / "merc-classic"
    spells = {o["name"]: o for o in json.loads((pack / "spells.json").read_text())["objects"]}
    charm = spells["charm person"]["attrs"]
    assert charm["classes"] == ["mage"] and charm["effects"][0]["type"] == "charm"
    assert charm["effects"][0]["save"] == "negates"


# --- the ROM importer and Midgaard ------------------------------------------------


def test_the_importer_makes_a_pet_shop_from_room_pet_shop():
    from realm.tools.rom_import import convert, document
    area = document(convert(_PET_AREA))
    by_id = {o["id"]: o for o in area["objects"]}
    keeper = next(o for o in area["objects"]
                  if o.get("location") == "rom_9100" and "npc" in o["tags"])
    params = next(b for b in keeper["behaviors"] if b["behavior_id"] == "shopkeeper")["params"]
    assert params["sells_pets"] is True and params["pet_stock"] == ["rom_mob_9102"]
    assert by_id["rom_mob_9102"]["attrs"]["value"] == 1          # ROM 10 * 3 * 3 silver


_PET_AREA = """#AREA
pets.are~
Pets~
{ 1  5} Test  Pets~
9100 9199
#MOBILES
#9101
keeper~
the keeper~
The keeper waits.
~
A keeper.
~
human~
AB 0 0 0
5 0 1d1+1 1d1+0 1d4+0 none
0 0 0 0
0 0 0 0
stand stand male 0
0 0 medium 0
#9102
puppy~
the puppy~
A puppy wags.
~
A puppy.
~
dog~
AB 0 0 0
3 0 1d1+1 1d1+0 1d4+0 none
0 0 0 0
0 0 0 0
stand stand male 0
0 0 small 0
#0
#ROOMS
#9100
The Pet Shop~
Pets.
~
0 M 0
S
#9101
The Kennel~
Cages.
~
0 0 0
S
#0
#SHOPS
9101 0 0 0 0 0 100 100 0 23
0
#RESETS
M 0 9101 1 9100 1
M 0 9102 1 9101 1
S
#$
"""


@pytest.fixture
async def midgaard():
    before = list(sys.path)
    s = Simulator.from_game(MIDGAARD)
    await s.start()
    try:
        yield s
    finally:
        _close(s)
        sys.modules.pop("rules", None)
        sys.modules.pop("game", None)
        sys.path[:] = before
        from realm.features import install_default
        install_default()


async def test_midgaards_pet_shop_sells(midgaard):
    shop = next(o for o in midgaard.store.all_cached() if o.id == "rom_3031")
    pat = midgaard.player("Pat", location=shop, level=1, credits=50)
    await midgaard.do(pat, "list")
    listing = "\n".join(midgaard.seen(pat))
    assert "Pets for sale:" in listing and "kitten" in listing
    await midgaard.do(pat, "buy kitten")
    assert [p.name for p in companions_of(pat)] == ["the kitten"]


# --- 13.3 mounts --------------------------------------------------------------


async def _mare(sim, room, rider, **attrs):
    mare = _creature(sim, "grey mare", room, **attrs)
    mare.add_tag("mount")
    await set_master(mare, rider)
    return mare


async def test_mounting_rules(sim):
    room = sim.room("Paddock")
    alice = sim.player("Alice", location=room)
    bob = sim.player("Bob", location=room)
    mare = await _mare(sim, room, alice)
    ox = _creature(sim, "ox", room)
    await set_master(ox, alice)
    await sim.do(alice, "mount ox")
    assert "You can't ride the ox." in sim.seen(alice)
    await sim.do(bob, "mount mare")
    assert "The grey mare isn't yours to ride." in sim.seen(bob)
    await sim.do(alice, "ride mare")
    assert "You mount the grey mare." in sim.seen(alice)
    assert alice.db.riding == mare.id and mare.db.ridden_by == alice.id
    await sim.do(alice, "mount mare")
    assert "You're already mounted!" in sim.seen(alice)
    await sim.do(alice, "dismount")
    assert alice.db.get("riding") is None and mare.db.get("ridden_by") is None
    await sim.do(alice, "dismount")
    assert "You're not mounted." in sim.seen(alice)


async def test_nobody_mounts_in_combat(sim):
    room = sim.room("Paddock")
    alice = sim.player("Alice", location=room)
    await _mare(sim, room, alice)
    alice.add_tag("in_combat")
    await sim.do(alice, "mount mare")
    assert "Not in the middle of a fight!" in sim.seen(alice)


async def test_a_ride_shows_the_riding_line_and_drains_the_mount(merc):
    one = merc.room("Road")
    rooms = [one, merc.room("Ford"), merc.room("Hill")]
    for a, b in zip(rooms, rooms[1:], strict=False):
        merc.obj("north", location=a, tags=["exit"], destination=b.id)
        merc.obj("south", location=b, tags=["exit"], destination=a.id)
    alice = merc.player("Alice", location=one, level=1, move=20, max_move=20)
    watcher = merc.player("Wat", location=rooms[1])
    mare = await _mare(merc, one, alice, move=30, max_move=30)
    await merc.do(alice, "mount mare")
    merc.seen(alice)
    await merc.do(alice, "north")
    assert "You ride north on a grey mare." in merc.seen(alice)
    arrival = merc.seen(watcher)
    assert "Alice arrives, riding a grey mare." in arrival
    assert not any(line.startswith("grey mare") for line in arrival)   # its own steps are silent
    await merc.do(alice, "north")
    assert "Alice rides north on a grey mare." in merc.seen(watcher)
    assert alice.location is rooms[2] and mare.location is rooms[2]
    assert alice.db.move == 20 and mare.db.move == 28
    assert mare.db.ridden_by == alice.id


async def test_an_exhausted_mount_refuses(merc):
    here, there, _n = _path(merc)
    alice = merc.player("Alice", location=here, level=1, move=20, max_move=20)
    await _mare(merc, here, alice, move=0, max_move=30)
    await merc.do(alice, "mount mare")
    await merc.do(alice, "north")
    assert alice.location is here
    assert "Your mount is too exhausted." in merc.seen(alice)


async def test_the_rider_is_marked_and_the_mount_not_listed(sim):
    room = sim.room("Paddock")
    alice = sim.player("Alice", location=room)
    bob = sim.player("Bob", location=room)
    await _mare(sim, room, alice)
    await sim.do(bob, "look")
    assert "grey mare" in "\n".join(sim.seen(bob))
    await sim.do(alice, "mount mare")
    await sim.do(bob, "look")
    seen = "\n".join(sim.seen(bob))
    assert "Alice (riding a grey mare)" in seen
    assert "  a grey mare" not in seen


async def test_a_no_mount_room_refuses_a_rider(sim):
    here, there, _n = _path(sim, there_tags=["no_mount"])
    alice = sim.player("Alice", location=here)
    await _mare(sim, here, alice)
    await sim.do(alice, "mount mare")
    await sim.do(alice, "north")
    assert alice.location is here and "You can't ride in there." in sim.seen(alice)
    await sim.do(alice, "dismount")
    await sim.do(alice, "north")
    assert alice.location is there                    # led, the mare follows


async def test_indoors_is_closed_to_riders_unless_mounts_indoors():
    for allowed in (False, True):
        s = _sim(MOUNTS_INDOORS=allowed)
        try:
            here, there, _n = _path(s, there_tags=["sector:inside"])
            alice = s.player("Alice", location=here)
            await _mare(s, here, alice)
            await s.do(alice, "mount mare")
            await s.do(alice, "north")
            assert (alice.location is there) is allowed
        finally:
            _close(s)


async def test_being_knocked_out_or_sleeping_dismounts(sim):
    room = sim.room("Paddock")
    alice = sim.player("Alice", location=room, hp=10, max_hp=10)
    mare = await _mare(sim, room, alice)
    await sim.do(alice, "mount mare")
    await sim.world.services["combat"].handle_death(alice, None)   # unconscious
    assert alice.db.get("riding") is None and mare.db.get("ridden_by") is None
    assert "You fall from the grey mare!" in sim.seen(alice)
    alice.remove_tag("unconscious")
    await sim.do(alice, "mount mare")
    await sim.do(alice, "sleep")
    assert alice.db.get("riding") is None
    assert "You slide down from the grey mare." in sim.seen(alice)


async def test_mounted_modifiers_reach_the_attack_roll(merc, monkeypatch):
    room = merc.room("Field")
    alice = merc.player("Alice", location=room, level=1, hp=50, max_hp=50)
    mare = await _mare(merc, room, alice)
    fido = _creature(merc, "fido", room)
    await merc.do(alice, "mount mare")
    monkeypatch.setattr(merc.game_system, "mounted_modifiers",
                        lambda rider, mount: {"attack": 3, "defense": 2})
    seen = []
    ruleset = merc.world.services["combat"].combat_system.ruleset
    real = ruleset.roll_attack
    monkeypatch.setattr(ruleset, "roll_attack", lambda a, d, w=None, m=None: (
        seen.append((a.obj, dict(m or {}))), real(a, d, w, m))[1])
    system = merc.world.services["combat"].combat_system
    await system.attack(alice, fido)
    await system.attack(fido, alice)
    assert seen[0] == (alice, {"mounted": 3})
    assert seen[1] == (fido, {"target_mounted": -2})
    assert mare is not None


# --- the kernel seam ------------------------------------------------------------


async def test_a_move_describer_replaces_the_movement_lines(sim):
    here, there, _n = _path(sim)
    alice = sim.player("Alice", location=here)
    left_behind = sim.player("Lee", location=here)
    ahead = sim.player("Ann", location=there)

    def sneaky(actor, direction, phase):
        if actor is not alice:
            return None
        return {"own": "You slink {}.", "leave": "", "arrive": "{{actor}} slinks in."}[
            phase].format(direction)

    sim.world.move_describers.insert(0, sneaky)
    await sim.do(alice, "north")
    assert "You slink north." in sim.seen(alice)
    assert not any("Alice" in line for line in sim.seen(left_behind))
    assert "Alice slinks in." in sim.seen(ahead)


async def test_logging_out_takes_the_pet_along(sim):
    den = sim.room("Den")
    alice = sim.player("Alice", location=den)
    kitten = _creature(sim, "kitten", den)
    await set_master(kitten, alice)
    await sim.do(alice, "logout")
    assert kitten.location is None and master_of(kitten) is alice


async def test_across_a_real_logout_and_login_the_pet_comes_back():
    """Through the server: the account's character logs out (its kitten
    leaves the world with it) and connects again (the kitten is back)."""
    from realm.server.game import GameServer
    from tests.test_accounts import Instant, _client
    server = GameServer(db_path=":memory:", enable_telnet=False, tick_interval=0,
                        game_system=Instant)
    await server.start()
    try:
        c = await _client(server)
        await c.send("create Ann correcthorse")
        await c.send("Bree")
        bree = c.player
        kitten = GameObject(name="kitten", tags=["npc"], location=bree.location)
        await server.persistence.save(kitten)
        assert await set_master(kitten, bree) is None
        await c.send("logout")
        assert kitten.location is None
        out = await c.send("connect Ann correcthorse")
        assert c.player is bree and kitten.location is bree.location
        assert "kitten" in out
    finally:
        await server.stop()


async def test_a_rider_spends_no_food_walking(merc):
    here, there, _n = _path(merc)
    alice = merc.player("Alice", location=here, level=1, move=20, max_move=20,
                        food=400, max_food=500, water=900, max_water=1000)
    await merc.do(alice, "north")
    walked = alice.db.food
    assert walked < 400                                # walking costs food
    await merc.do(alice, "south")
    await _mare(merc, here, alice, move=30, max_move=30)
    before = alice.db.food
    await merc.do(alice, "mount mare")
    await merc.do(alice, "north")
    assert alice.location is there and alice.db.food == before


async def test_a_fleeing_riders_mount_bolts_with_it(sim):
    from realm.core.movement import move_through_exit
    here, there, north = _path(sim)
    alice = sim.player("Alice", location=here, hp=20, max_hp=20)
    mare = await _mare(sim, here, alice)
    fido = _creature(sim, "fido", here)
    await sim.do(alice, "mount mare")
    manager = sim.world.services["combat"]
    await manager.initiate(fido, alice)
    manager.assist(mare, fido)
    assert await move_through_exit(alice, there, exit_obj=north, fleeing=True)
    assert mare.location is there and mare.db.ridden_by == alice.id


async def test_a_rider_moved_without_its_mount_is_off_it(sim):
    from realm.core.movement import move_to
    here, there, _n = _path(sim)
    alice = sim.player("Alice", location=here)
    mare = await _mare(sim, here, alice)
    await sim.do(alice, "mount mare")
    await move_to(alice, there, force=True)                  # a recall, a teleport
    assert alice.db.get("riding") is None and not mare.has_tag("ridden")
    assert "You are parted from the grey mare." in sim.seen(alice)


# --- after the plan: companions come along on recall (BACKLOG, first hour) ----------------


async def test_a_pet_comes_along_on_recall(sim):
    """ROM's ``do_recall`` recalls the pet with its master. A companion
    beside its master goes too; one elsewhere, or out cold, stays."""
    here, there, _n = _path(sim)
    temple = sim.room("Temple")
    alice = sim.player("Alice", location=here, home=temple.id)
    bob = sim.player("Bob", location=here)
    kitten = _creature(sim, "kitten", here)
    hawk = _creature(sim, "hawk", there)
    dog = _creature(sim, "dog", here)
    for npc in (kitten, hawk, dog):
        await set_master(npc, alice)
    dog.add_tag("unconscious")
    sim.seen(bob)
    await sim.do(alice, "recall")
    assert alice.location is temple
    assert kitten.location is temple and master_of(kitten) is alice
    assert hawk.location is there and dog.location is here
    assert "kitten" in "\n".join(sim.seen(alice))          # in the room she wakes to
    seen = sim.seen(bob)
    assert "The kitten disappears with Alice." in seen and "Alice disappears." in seen


async def test_a_rider_recalls_on_its_mount(sim):
    here, _there, _n = _path(sim)
    temple = sim.room("Temple")
    alice = sim.player("Alice", location=here, home=temple.id)
    mare = await _mare(sim, here, alice)
    await sim.do(alice, "mount mare")
    sim.seen(alice)
    await sim.do(alice, "recall")
    assert alice.location is temple and mare.location is temple
    assert alice.db.riding == mare.id and mare.has_tag("ridden")
    assert not any("parted" in line for line in sim.seen(alice))


async def test_a_move_that_says_so_brings_companions_any_other_does_not(sim):
    """The seam is the ``accompanied`` action tag on a direct placement
    (recall puts it there; a softcode gate spell passes ``tags=
    ['accompanied']``). A plain teleport, ``@tel`` or a summons leaves
    them, as ROM's transfer and summon do."""
    from realm.core.movement import move_to
    here, there, _n = _path(sim)
    alice = sim.player("Alice", location=here)
    kitten = _creature(sim, "kitten", here)
    await set_master(kitten, alice)
    await move_to(alice, there, force=True)
    assert alice.location is there and kitten.location is here
    await move_to(alice, here, force=True)
    assert await move_to(alice, there, extra_tags=["accompanied"])
    assert kitten.location is there


async def test_a_ridden_mount_does_not_walk_off(sim):
    here, there, _n = _path(sim)
    alice = sim.player("Alice", location=here)
    mare = await _mare(sim, here, alice)
    await sim.do(alice, "mount mare")
    await sim.do(alice, "order mare north")
    assert mare.location is here
    assert "Grey mare tries to go north and fails." in sim.seen(alice)


async def test_a_companion_neither_wanders_nor_attacks_on_sight(sim):
    from realm.core.behaviors import BehaviorRegistry
    here, there, _n = _path(sim)
    alice = sim.player("Alice", location=here)
    wolf = _creature(sim, "wolf", here)
    wander = BehaviorRegistry.create("wandering", pause=0, wander_chance=1.0)
    wolf.add_behavior(wander)
    wolf.add_behavior(BehaviorRegistry.create("aggressive"))
    await set_master(wolf, alice)
    for _ in range(3):
        await wander.tick(wolf, 4.0)
    assert wolf.location is here
    bob = sim.player("Bob", location=there, hp=10, max_hp=10)
    await sim.do(bob, "south")                        # walks in on the wolf
    assert bob.location is here and not wolf.has_tag("in_combat")
