"""
Tests for the infiltration mechanics: skill checks, door/container
state, keys and lockpicking, wearables, stealth, search, and the
Watchful/Patrol NPC behaviors.

Dice are removed via the pluggable check resolver: a check succeeds iff
effective skill >= 10, margin = effective - 10. Contests therefore go
to the higher skill, deterministically.
"""

from __future__ import annotations

import pytest

from realm.behaviors import PatrolBehavior, WatchfulBehavior
from realm.commands.builtin.communication import cmd_say
from realm.commands.builtin.inventory import cmd_get
from realm.commands.builtin.manipulation import (
    cmd_hide,
    cmd_open,
    cmd_pick,
    cmd_search,
    cmd_unwear,
    cmd_use,
    cmd_wear,
)
from realm.core.checks import CheckResult, check, contest, set_check_resolver, skill_level
from realm.core.movement import move_through_exit
from realm.core.objects import GameObject
from realm.core.perception import can_see, can_see_room
from realm.core.propagation import get_engine as get_propagation_engine
from realm.core.propagation import reset_engine
from realm.gateway.session import Session
from realm.server.dispatcher import CommandContext, CommandDispatcher


def level_resolver(obj, skill, modifier):
    effective = skill_level(obj, skill) + modifier
    return CheckResult(
        success=effective >= 10,
        margin=effective - 10,
        roll=10,
        effective=effective,
        skill=skill,
    )


@pytest.fixture(autouse=True)
def deterministic_checks():
    reset_engine()
    set_check_resolver(level_resolver)
    yield
    set_check_resolver(None)
    reset_engine()


def make_player(name, location=None, **skills):
    player = GameObject(name=name, location=location)
    player.add_tag("player")
    for key, value in skills.items():
        player.db.set(key, value)
    sess = Session(protocol="test", address="127.0.0.1")
    sess.link_player(player)
    return player, sess


def drain(sess):
    out = []
    while not sess._output_queue.empty():
        out.append(sess._output_queue.get_nowait())
    return out


def make_ctx(sess, args=""):
    return CommandContext(
        session=sess,
        player=sess.player,
        raw_input=args,
        command_name="test",
        args=args,
        dispatcher=CommandDispatcher(),
    )


# --- Checks -------------------------------------------------------------------


class TestChecks:

    def test_trained_skill_level(self):
        obj = GameObject("Raven")
        obj.db.skill_stealth = 14
        assert skill_level(obj, "stealth") == 14

    def test_attribute_default(self):
        obj = GameObject("Rube")
        obj.db.dexterity = 12
        assert skill_level(obj, "stealth") == 7  # DX-5

    def test_check_uses_resolver(self):
        skilled = GameObject("Pro")
        skilled.db.skill_stealth = 14
        clumsy = GameObject("Oaf")
        clumsy.db.skill_stealth = 5
        assert check(skilled, "stealth").success
        assert not check(clumsy, "stealth").success

    def test_contest_higher_skill_wins(self):
        sneak = GameObject("Sneak")
        sneak.db.skill_stealth = 15
        guard = GameObject("Guard")
        guard.db.skill_observation = 12
        assert not contest(guard, "observation", sneak, "stealth")
        guard.db.skill_observation = 18
        assert contest(guard, "observation", sneak, "stealth")


# --- Doors ----------------------------------------------------------------------


@pytest.mark.asyncio
class TestDoors:

    def _door_between(self, room_a, room_b, **attrs):
        door = GameObject("steel door", location=room_a, tags=["exit"])
        door.db.destination_obj = room_b
        for key, value in attrs.items():
            door.db.set(key, value)
        return door

    async def test_closed_exit_blocks_movement(self):
        a = GameObject("Hall", tags=["room"])
        b = GameObject("Vault", tags=["room"])
        door = self._door_between(a, b)
        door.add_tag("closed")
        raven, sess = make_player("Raven", location=a)

        moved = await move_through_exit(raven, b, exit_obj=door)

        assert moved is False
        assert raven.location is a
        assert drain(sess) == ["The steel door is closed."]

    async def test_open_then_traverse(self):
        a = GameObject("Hall", tags=["room"])
        b = GameObject("Vault", tags=["room"])
        door = self._door_between(a, b)
        door.add_tag("closed")
        raven, sess = make_player("Raven", location=a)

        await cmd_open(make_ctx(sess, "steel door"))
        assert not door.has_tag("closed")

        moved = await move_through_exit(raven, b, exit_obj=door)
        assert moved is True

    async def test_locked_door_wont_open(self):
        a = GameObject("Hall", tags=["room"])
        b = GameObject("Vault", tags=["room"])
        door = self._door_between(a, b, locked=True, key_id="vault")
        door.add_tag("closed")
        raven, sess = make_player("Raven", location=a)

        await cmd_open(make_ctx(sess, "door"))

        assert door.has_tag("closed")
        assert any("locked" in line.lower() for line in drain(sess))

    async def test_key_unlocks(self):
        a = GameObject("Hall", tags=["room"])
        b = GameObject("Vault", tags=["room"])
        door = self._door_between(a, b, locked=True, key_id="vault")
        door.add_tag("closed")
        raven, sess = make_player("Raven", location=a)
        key = GameObject("brass key", location=raven, tags=["thing"])
        key.db.unlocks = "vault"

        from realm.commands.builtin.manipulation import cmd_unlock_item
        await cmd_unlock_item(make_ctx(sess, "door"))

        assert door.db.get("locked") is False
        await cmd_open(make_ctx(sess, "door"))
        assert not door.has_tag("closed")

    async def test_keycard_via_use(self):
        a = GameObject("Hall", tags=["room"])
        b = GameObject("Vault", tags=["room"])
        door = self._door_between(a, b, locked=True, key_id="vault")
        raven, sess = make_player("Raven", location=a)
        card = GameObject("keycard", location=raven, tags=["thing"])
        card.db.unlocks = "vault"

        await cmd_use(make_ctx(sess, "keycard on steel door"))

        assert door.db.get("locked") is False

    async def test_pick_lock_with_skill_and_tools(self):
        a = GameObject("Hall", tags=["room"])
        b = GameObject("Vault", tags=["room"])
        door = self._door_between(a, b, locked=True, key_id="vault",
                                  lock_difficulty=2)
        raven, sess = make_player("Raven", location=a, skill_lockpicking=14)
        GameObject("lockpick set", location=raven, tags=["thing", "lockpicks"])

        await cmd_pick(make_ctx(sess, "door"))
        assert door.db.get("locked") is False  # 14 - 2 = 12 >= 10

    async def test_pick_without_tools_penalized(self):
        a = GameObject("Hall", tags=["room"])
        b = GameObject("Vault", tags=["room"])
        door = self._door_between(a, b, locked=True, key_id="vault",
                                  lock_difficulty=2)
        raven, sess = make_player("Raven", location=a, skill_lockpicking=14)

        await cmd_pick(make_ctx(sess, "door"))
        assert door.db.get("locked") is True  # 14 - 2 - 5 = 7 < 10

    async def test_electronic_lock_uses_other_skill(self):
        a = GameObject("Hall", tags=["room"])
        b = GameObject("Vault", tags=["room"])
        door = self._door_between(a, b, locked=True, key_id="vault",
                                  lock_skill="electronics", lock_difficulty=1)
        raven, sess = make_player("Raven", location=a, skill_electronics=12)

        await cmd_pick(make_ctx(sess, "door"))
        assert door.db.get("locked") is False  # no lockpicks penalty

    async def test_skill_gated_exit(self):
        alley = GameObject("Alley", tags=["room"])
        landing = GameObject("Landing", tags=["room"])
        fire = GameObject("fire escape", location=alley, tags=["exit"])
        fire.db.destination_obj = landing
        fire.db.check_skill = "climbing"
        fire.db.check_difficulty = 2

        climber, _ = make_player("Ape", location=alley, skill_climbing=13)
        clumsy, sess2 = make_player("Oaf", location=alley, skill_climbing=9)

        assert await move_through_exit(climber, landing, exit_obj=fire) is True
        assert await move_through_exit(clumsy, landing, exit_obj=fire) is False
        assert clumsy.location is alley


# --- Containers -------------------------------------------------------------------


@pytest.mark.asyncio
class TestContainers:

    async def test_closed_container_blocks_get_from(self):
        room = GameObject("Office", tags=["room"])
        safe = GameObject("wall safe", location=room, tags=["thing", "closed"])
        safe.db.container = True
        GameObject("documents", location=safe, tags=["thing"])
        raven, sess = make_player("Raven", location=room)

        await cmd_get(make_ctx(sess, "documents from safe"))

        assert any("closed" in line for line in drain(sess))

    async def test_open_then_loot(self):
        room = GameObject("Office", tags=["room"])
        safe = GameObject("wall safe", location=room, tags=["thing", "closed"])
        safe.db.container = True
        docs = GameObject("documents", location=safe, tags=["thing"])
        raven, sess = make_player("Raven", location=room)

        await cmd_open(make_ctx(sess, "safe"))
        await cmd_get(make_ctx(sess, "documents from safe"))

        assert docs.location is raven


# --- Wearables ---------------------------------------------------------------------


@pytest.mark.asyncio
class TestWearables:

    async def test_wear_grants_tags_remove_revokes(self):
        room = GameObject("Room", tags=["room"])
        raven, sess = make_player("Raven", location=room)
        goggles = GameObject("goggles", location=raven, tags=["thing", "wearable"])
        goggles.db.slot = "eyes"
        goggles.db.grants_tags = ["nightvision"]

        cellar = GameObject("Cellar", tags=["room", "dark"])
        assert not can_see_room(raven, cellar)

        await cmd_wear(make_ctx(sess, "goggles"))
        assert raven.has_tag("nightvision")
        assert can_see_room(raven, cellar)

        await cmd_unwear(make_ctx(sess, "goggles"))
        assert not raven.has_tag("nightvision")

    async def test_slot_conflict(self):
        room = GameObject("Room", tags=["room"])
        raven, sess = make_player("Raven", location=room)
        goggles = GameObject("goggles", location=raven, tags=["thing", "wearable"])
        goggles.db.slot = "eyes"
        monocle = GameObject("monocle", location=raven, tags=["thing", "wearable"])
        monocle.db.slot = "eyes"

        await cmd_wear(make_ctx(sess, "goggles"))
        await cmd_wear(make_ctx(sess, "monocle"))

        assert goggles.has_tag("worn")
        assert not monocle.has_tag("worn")

    async def test_innate_tag_survives_remove(self):
        room = GameObject("Room", tags=["room"])
        raven, sess = make_player("Raven", location=room)
        raven.add_tag("nightvision")  # innate
        goggles = GameObject("goggles", location=raven, tags=["thing", "wearable"])
        goggles.db.grants_tags = ["nightvision"]

        await cmd_wear(make_ctx(sess, "goggles"))
        await cmd_unwear(make_ctx(sess, "goggles"))

        assert raven.has_tag("nightvision")


# --- Stealth ----------------------------------------------------------------------


@pytest.mark.asyncio
class TestStealth:

    async def test_hide_needs_skill(self):
        room = GameObject("Room", tags=["room"])
        pro, sess_a = make_player("Pro", location=room, skill_stealth=13)
        oaf, sess_b = make_player("Oaf", location=room, skill_stealth=6)

        await cmd_hide(make_ctx(sess_a))
        await cmd_hide(make_ctx(sess_b))

        assert pro.has_tag("hidden")
        assert not oaf.has_tag("hidden")

    async def test_darkness_helps_hiding(self):
        cellar = GameObject("Cellar", tags=["room", "dark"])
        mid, sess = make_player("Mid", location=cellar, skill_stealth=8)

        await cmd_hide(make_ctx(sess))  # 8 + 3 (dark) = 11 >= 10

        assert mid.has_tag("hidden")

    async def test_hidden_invisible_to_others(self):
        room = GameObject("Room", tags=["room"])
        pro, sess_a = make_player("Pro", location=room, skill_stealth=13)
        bob, _ = make_player("Bob", location=room)

        await cmd_hide(make_ctx(sess_a))

        assert not can_see(bob, pro)

    async def test_loud_action_breaks_stealth(self):
        get_propagation_engine().add_observer(
            __import__("realm.core.perception", fromlist=["stealth_observer"]).stealth_observer
        )
        room = GameObject("Room", tags=["room"])
        pro, sess = make_player("Pro", location=room, skill_stealth=13)
        await cmd_hide(make_ctx(sess))
        assert pro.has_tag("hidden")

        await cmd_say(make_ctx(sess, "boo"))

        assert not pro.has_tag("hidden")

    async def test_search_contest_reveals_hider(self):
        room = GameObject("Room", tags=["room"])
        sneak, sess_a = make_player("Sneak", location=room, skill_stealth=11)
        hawk, sess_b = make_player("Hawk", location=room, skill_observation=15)

        await cmd_hide(make_ctx(sess_a))
        assert sneak.has_tag("hidden")

        await cmd_search(make_ctx(sess_b))

        assert not sneak.has_tag("hidden")

    async def test_search_reveals_concealed_object(self):
        room = GameObject("Office", tags=["room"])
        safe = GameObject("wall safe", location=room, tags=["thing", "invisible"])
        safe.db.conceal_difficulty = 2
        safe.db.reveal_msg = "The painting swings aside, revealing a wall safe!"
        hawk, sess = make_player("Hawk", location=room, skill_observation=13)

        assert not can_see(hawk, safe)
        await cmd_search(make_ctx(sess))

        assert not safe.has_tag("invisible")
        assert any("revealing a wall safe" in line for line in drain(sess))


# --- NPC behaviors -----------------------------------------------------------------


@pytest.mark.asyncio
class TestNPCBehaviors:

    async def test_watchful_spots_weak_sneak(self):
        outside = GameObject("Corridor", tags=["room"])
        post = GameObject("Lobby", tags=["room"])
        guard = GameObject("guard", location=post, tags=["npc"])
        guard.db.skill_observation = 16
        guard.add_behavior(WatchfulBehavior(spot_msg="Intruder!"))

        sneak, sess = make_player("Sneak", location=outside, skill_stealth=11)
        sneak.add_tag("hidden")

        await move_through_exit(sneak, post)

        assert not sneak.has_tag("hidden")
        assert int(guard.db.get("alert_level") or 0) == 1
        assert any("spots you" in line for line in drain(sess))

    async def test_watchful_misses_master_sneak(self):
        outside = GameObject("Corridor", tags=["room"])
        post = GameObject("Lobby", tags=["room"])
        guard = GameObject("guard", location=post, tags=["npc"])
        guard.db.skill_observation = 11
        guard.add_behavior(WatchfulBehavior())

        sneak, _ = make_player("Sneak", location=outside, skill_stealth=16)
        sneak.add_tag("hidden")

        await move_through_exit(sneak, post)

        assert sneak.has_tag("hidden")

    async def test_watchful_challenges_visible_arrival(self):
        outside = GameObject("Corridor", tags=["room"])
        post = GameObject("Lobby", tags=["room"])
        guard = GameObject("guard", location=post, tags=["npc"])
        guard.add_behavior(WatchfulBehavior(challenge="Building's closed."))

        visitor, sess = make_player("Visitor", location=outside)
        await move_through_exit(visitor, post)

        assert any('guard says, "Building\'s closed."' in line
                   for line in drain(sess))

    async def test_patrol_walks_route_and_respects_doors(self):
        a = GameObject("Post A", tags=["room"])
        b = GameObject("Post B", tags=["room"])
        east = GameObject("east", location=a, tags=["exit"])
        east.db.destination_obj = b
        west = GameObject("west", location=b, tags=["exit"])
        west.db.destination_obj = a

        guard = GameObject("guard", location=a, tags=["npc"])
        patrol = PatrolBehavior(route=["east", "west"], pause=0)
        guard.add_behavior(patrol)

        await patrol.tick(guard, 4.0)  # pause=0: steps east immediately
        assert guard.location is b

        # Close the way back: the patrol is stuck like anyone else.
        west.add_tag("closed")
        await patrol.tick(guard, 4.0)
        await patrol.tick(guard, 4.0)
        assert guard.location is b

        # Reopen: the patrol resumes.
        west.remove_tag("closed")
        await patrol.tick(guard, 4.0)
        assert guard.location is a


@pytest.mark.asyncio
class TestMultiWordExits:

    async def test_typing_full_multiword_exit_name_walks_it(self):
        from realm.gateway.session import Session as RealSession

        a = GameObject("Alley", tags=["room"])
        b = GameObject("Landing", tags=["room"])
        fire = GameObject("fire escape", location=a, tags=["exit"])
        fire.db.destination_obj = b

        raven, _sess = make_player("Raven", location=a)
        sess = RealSession(protocol="test", address="127.0.0.1")
        sess.link_player(raven)

        dispatcher = CommandDispatcher()
        await dispatcher.dispatch(sess, "fire escape")

        assert raven.location is b
