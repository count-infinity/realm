"""
Followers and parties: one attribute, room-local cascade, CP splits,
and the escort quest (an NPC agreeing to follow via softcode).
"""

from __future__ import annotations

import pytest

from realm.core.movement import move_through_exit
from realm.core.objects import GameObject
from realm.core.party import (
    followers_of,
    party_members,
    set_following,
)
from realm.core.propagation import reset_engine
from tests.test_olc import MockPersistence, make_context, use_persistence


@pytest.fixture(autouse=True)
def fresh_engine():
    reset_engine()
    yield
    reset_engine()


def two_rooms():
    west = GameObject("West", tags=["room"])
    east = GameObject("East", tags=["room"])
    door = GameObject("east", tags=["exit"], location=west)
    door.db.destination_obj = east
    return west, east, door


@pytest.mark.asyncio
class TestFollowing:

    async def test_follower_walks_after_leader(self):
        west, east, door = two_rooms()
        alice = GameObject("Alice", tags=["player"], location=west)
        bob = GameObject("Bob", tags=["player"], location=west)
        set_following(bob, alice)

        assert await move_through_exit(alice, east, exit_obj=door)
        assert bob.location is east

    async def test_chain_cascades(self):
        west, east, door = two_rooms()
        alice = GameObject("Alice", tags=["player"], location=west)
        bob = GameObject("Bob", tags=["player"], location=west)
        carol = GameObject("Carol", tags=["player"], location=west)
        set_following(bob, alice)
        set_following(carol, bob)

        await move_through_exit(alice, east, exit_obj=door)
        assert bob.location is east and carol.location is east

    async def test_cycle_is_safe(self):
        west, east, door = two_rooms()
        alice = GameObject("Alice", tags=["player"], location=west)
        bob = GameObject("Bob", tags=["player"], location=west)
        set_following(bob, alice)
        set_following(alice, bob)  # mutual — must not recurse forever

        await move_through_exit(alice, east, exit_obj=door)
        assert alice.location is east and bob.location is east

    async def test_locked_exit_leaves_follower_behind(self):
        west, east, door = two_rooms()
        alice = GameObject("Alice", tags=["player"], location=west)
        bob = GameObject("Bob", tags=["player"], location=west)
        set_following(bob, alice)
        door.locks["basic"] = "caller.has_tag('keyholder')"
        alice.add_tag("keyholder")

        await move_through_exit(alice, east, exit_obj=door)
        assert alice.location is east
        assert bob.location is west  # the lock judged Bob on his own merits

    async def test_unconscious_stays(self):
        west, east, door = two_rooms()
        alice = GameObject("Alice", tags=["player"], location=west)
        bob = GameObject("Bob", tags=["player", "unconscious"], location=west)
        set_following(bob, alice)

        await move_through_exit(alice, east, exit_obj=door)
        assert bob.location is west

    async def test_npc_escort_via_softcode(self):
        """The B2 rescue: a prisoner agrees to follow via $-command."""
        from realm.gateway.session import Session
        from realm.scripting.engine import ScriptEngine
        from realm.server.dispatcher import CommandContext

        west, east, door = two_rooms()
        alice = GameObject("Alice", tags=["player"], location=west)
        sess = Session(protocol="test", address="1.1.1.1")
        sess.link_player(alice)
        prisoner = GameObject("prisoner", tags=["npc"], location=west)
        prisoner.db.cmd_rescue = (
            "$rescue prisoner:set_attr(me, 'following', '%#')\n"
            "say('Bless you! Lead the way.')"
        )

        engine = ScriptEngine()
        from realm.core.propagation import get_engine
        get_engine().add_observer(engine.handle_action)
        ctx = CommandContext(session=sess, player=alice,
                             raw_input="rescue prisoner",
                             command_name="rescue", args="prisoner")
        handled = await engine.handle_unknown_command(ctx)
        assert handled is True
        assert prisoner.db.get("following") == alice.id

        await move_through_exit(alice, east, exit_obj=door)
        assert prisoner.location is east  # the escort walks out with you


class TestPartyMembership:

    def test_party_connects_both_directions(self):
        room = GameObject("Camp", tags=["room"])
        alice = GameObject("Alice", tags=["player"], location=room)
        bob = GameObject("Bob", tags=["player"], location=room)
        carol = GameObject("Carol", tags=["player"], location=room)
        stranger = GameObject("Stranger", tags=["player"], location=room)
        set_following(bob, alice)
        set_following(carol, bob)

        for member in (alice, bob, carol):
            ids = {m.id for m in party_members(member)}
            assert ids == {alice.id, bob.id, carol.id}
        assert {m.id for m in party_members(stranger)} == {stranger.id}

    def test_followers_of_is_room_local(self):
        room = GameObject("Camp", tags=["room"])
        elsewhere = GameObject("Away", tags=["room"])
        alice = GameObject("Alice", tags=["player"], location=room)
        bob = GameObject("Bob", tags=["player"], location=elsewhere)
        set_following(bob, alice)
        assert followers_of(alice, room) == []
        assert followers_of(alice, elsewhere) == [bob]


@pytest.mark.asyncio
class TestFollowCommands:

    def setup_method(self):
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

    async def test_follow_and_unfollow(self):
        from realm.commands.builtin.social import cmd_follow, cmd_unfollow

        room = GameObject("Camp", tags=["room"])
        alice = GameObject("Alice", tags=["player"], location=room)
        bob = GameObject("Bob", tags=["player"], location=room)

        ctx = make_context(bob, args="Alice")
        await cmd_follow(ctx)
        assert bob.db.get("following") == alice.id

        ctx2 = make_context(bob, args="")
        await cmd_unfollow(ctx2)
        assert bob.db.get("following") is None

    async def test_party_listing(self):
        from realm.commands.builtin.social import cmd_party

        room = GameObject("Camp", tags=["room"])
        alice = GameObject("Alice", tags=["player"], location=room)
        bob = GameObject("Bob", tags=["player"], location=room)
        set_following(bob, alice)

        ctx = make_context(alice, args="")
        await cmd_party(ctx)
        text = "\n".join(ctx.session.messages)
        assert "Bob" in text and "following Alice" in text


@pytest.mark.asyncio
class TestPartyCpSplit:

    async def test_kill_award_splits_across_party(self):
        # ruff: noqa: F811
        from realm.combat.manager import CombatManager, set_combat_manager
        from realm.combat.system import CombatSystem
        from tests.test_combat_encounters import FixedRuleset, make_fighter  # noqa: F401

        mgr = CombatManager(CombatSystem(ruleset=FixedRuleset()),
                            beat_min=4, beat_max=120, beat_default=15)
        set_combat_manager(mgr)
        try:
            room = GameObject("Cave", tags=["room"])
            alice = GameObject("Alice", tags=["player"], location=room)
            bob = GameObject("Bob", tags=["player"], location=room)
            set_following(bob, alice)
            ogre = GameObject("ogre", tags=["npc"], location=room)
            ogre.db.points = 80  # award 8 → 4 each

            await mgr.handle_death(ogre, killer=alice)

            assert alice.db.get("character_points") == 4
            assert bob.db.get("character_points") == 4
        finally:
            mgr.stop_all()
            set_combat_manager(None)

    async def test_solo_killer_keeps_it_all(self):
        from realm.combat.manager import CombatManager, set_combat_manager
        from realm.combat.system import CombatSystem
        from tests.test_combat_encounters import FixedRuleset

        mgr = CombatManager(CombatSystem(ruleset=FixedRuleset()),
                            beat_min=4, beat_max=120, beat_default=15)
        set_combat_manager(mgr)
        try:
            room = GameObject("Cave", tags=["room"])
            alice = GameObject("Alice", tags=["player"], location=room)
            rat = GameObject("rat", tags=["npc"], location=room)
            rat.db.points = 40

            await mgr.handle_death(rat, killer=alice)
            assert alice.db.get("character_points") == 4
        finally:
            mgr.stop_all()
            set_combat_manager(None)
