"""
End-to-end tests for the migrated realm/commands/builtin/* commands.

Each test sets up a minimal world (room + actor + bystander, items as needed),
drives the command via its CommandContext, and asserts on what landed in the
relevant session output queues. The point is to verify the propagation
pipeline — actions emitted, behaviors observable, blocking honored, messages
delivered to the right audiences — not to re-test the propagation engine.
"""

from __future__ import annotations

import pytest

from realm.commands.base import find_object  # noqa: F401  # ensure the module imports cleanly
from realm.commands.builtin.communication import (
    cmd_emit,
    cmd_ooc,
    cmd_pose,
    cmd_say,
    cmd_semipose,
    cmd_shout,
    cmd_whisper,
)
from realm.commands.builtin.inventory import cmd_drop, cmd_get, cmd_give, cmd_put
from realm.commands.builtin.look import cmd_look
from realm.commands.builtin.movement import cmd_go
from realm.core.behaviors import Behavior
from realm.core.objects import GameObject
from realm.gateway.session import Session
from realm.server.dispatcher import CommandContext

# --- Helpers --------------------------------------------------------------


def make_session() -> Session:
    return Session(protocol="test", address="127.0.0.1")


def make_player(name: str, location: GameObject | None = None) -> tuple[GameObject, Session]:
    player = GameObject(name=name, location=location)
    player.add_tag("player")
    sess = make_session()
    sess.link_player(player)
    return player, sess


def drain(sess: Session) -> list[str]:
    out: list[str] = []
    while not sess._output_queue.empty():
        out.append(sess._output_queue.get_nowait())
    return out


def make_ctx(
    sess: Session,
    *,
    args: str = "",
    left_args: str = "",
    right_args: str = "",
    command_name: str = "test",
) -> CommandContext:
    return CommandContext(
        session=sess,
        player=sess.player,
        raw_input=f"{command_name} {args}".strip(),
        command_name=command_name,
        args=args,
        left_args=left_args or args,
        right_args=right_args,
    )


# --- Communication --------------------------------------------------------


@pytest.mark.asyncio
class TestCommunicationCommands:

    async def test_say_delivers_to_actor_and_room(self):
        room = GameObject("Tavern", tags=["room"])
        alice, sess_a = make_player("Alice", location=room)
        bob, sess_b = make_player("Bob", location=room)

        await cmd_say(make_ctx(sess_a, args="hello world"))

        assert drain(sess_a) == ['You say, "hello world"']
        assert drain(sess_b) == ['Alice says, "hello world"']

    async def test_say_with_no_args_prompts(self):
        room = GameObject("Room", tags=["room"])
        alice, sess = make_player("Alice", location=room)
        await cmd_say(make_ctx(sess, args=""))
        assert drain(sess) == ["Say what?"]

    async def test_say_with_no_location(self):
        alice, sess = make_player("Alice")  # no location
        await cmd_say(make_ctx(sess, args="hello"))
        out = drain(sess)
        assert out == ["You have nowhere to speak from."]

    async def test_pose_shows_same_line_to_actor_and_room(self):
        room = GameObject("Room", tags=["room"])
        alice, sess_a = make_player("Alice", location=room)
        bob, sess_b = make_player("Bob", location=room)

        await cmd_pose(make_ctx(sess_a, args="waves"))

        assert drain(sess_a) == ["Alice waves"]
        assert drain(sess_b) == ["Alice waves"]

    async def test_semipose_no_space_between_name_and_action(self):
        room = GameObject("Room", tags=["room"])
        alice, sess_a = make_player("Alice", location=room)
        bob, sess_b = make_player("Bob", location=room)

        await cmd_semipose(make_ctx(sess_a, args="'s dog barks."))

        # Actor and bystander both see the no-space form.
        assert drain(sess_a) == ["Alice's dog barks."]
        assert drain(sess_b) == ["Alice's dog barks."]

    async def test_emit_shows_raw_message_to_everyone(self):
        room = GameObject("Room", tags=["room"])
        alice, sess_a = make_player("Alice", location=room)
        bob, sess_b = make_player("Bob", location=room)

        await cmd_emit(make_ctx(sess_a, args="A cold wind blows."))

        assert drain(sess_a) == ["A cold wind blows."]
        assert drain(sess_b) == ["A cold wind blows."]

    async def test_whisper_three_audiences(self):
        room = GameObject("Room", tags=["room"])
        alice, sess_a = make_player("Alice", location=room)
        bob, sess_b = make_player("Bob", location=room)
        charlie, sess_c = make_player("Charlie", location=room)

        await cmd_whisper(make_ctx(
            sess_a, left_args="Bob", right_args="meet me at midnight",
        ))

        assert drain(sess_a) == ['You whisper to Bob, "meet me at midnight"']
        assert drain(sess_b) == ['Alice whispers, "meet me at midnight"']
        assert drain(sess_c) == ["Alice whispers something to Bob."]

    async def test_whisper_to_self_rejected(self):
        room = GameObject("Room", tags=["room"])
        alice, sess = make_player("Alice", location=room)
        await cmd_whisper(make_ctx(
            sess, left_args="Alice", right_args="hi me",
        ))
        assert drain(sess) == ["Talking to yourself?"]

    async def test_ooc_marker(self):
        room = GameObject("Room", tags=["room"])
        alice, sess_a = make_player("Alice", location=room)
        bob, sess_b = make_player("Bob", location=room)

        await cmd_ooc(make_ctx(sess_a, args="brb"))

        assert drain(sess_a) == ["[OOC] Alice: brb"]
        assert drain(sess_b) == ["[OOC] Alice: brb"]

    async def test_shout_carries_sound_tag(self):
        """Behaviors filtering on the 'sound' tag react to shout."""
        room = GameObject("Room", tags=["room"])
        alice, sess_a = make_player("Alice", location=room)
        bob, sess_b = make_player("Bob", location=room)

        observed: list[str] = []

        class SoundWatcher(Behavior):
            behavior_id = "soundwatcher"

            async def on_check(self, obj, action):
                if "sound" in action.tags:
                    observed.append(action.action_type)

        bob.add_behavior(SoundWatcher())

        await cmd_shout(make_ctx(sess_a, args="HELP"))

        # bob's behavior saw the shout via the sound tag, not a specific
        # action_type filter — that's the cross-cutting tag system at work.
        assert observed == ["event:shout"]
        assert drain(sess_a) == ['You shout, "HELP"']
        assert drain(sess_b) == ['Alice shouts, "HELP"']


# --- Movement --------------------------------------------------------------


@pytest.mark.asyncio
class TestMovementCommand:

    async def _setup_two_rooms(self):
        """Two rooms connected by a 'north' exit (one-way for the test)."""
        room_a = GameObject("Plaza", tags=["room"], description="A wide plaza.")
        room_b = GameObject("Alley", tags=["room"], description="A narrow alley.")

        exit_north = GameObject("north", location=room_a)
        exit_north.add_tag("exit")
        exit_north.db.destination = room_b.id
        exit_north.db.destination_obj = room_b

        return room_a, room_b, exit_north

    async def test_go_moves_player_and_shows_destination(self):
        room_a, room_b, _ = await self._setup_two_rooms()
        alice, sess = make_player("Alice", location=room_a)

        await cmd_go(make_ctx(sess, args="north"))

        assert alice.location is room_b
        out = drain(sess)
        # Both leave message and arrival display land on the actor.
        assert "You leave north." in out
        assert "Alley" in "\n".join(out)  # destination room name shown

    async def test_go_emits_room_messages_to_bystanders(self):
        room_a, room_b, _ = await self._setup_two_rooms()
        alice, sess_a = make_player("Alice", location=room_a)
        bob, sess_b = make_player("Bob", location=room_a)
        carol, sess_c = make_player("Carol", location=room_b)

        await cmd_go(make_ctx(sess_a, args="north"))

        # Bystander in old room sees leave; bystander in new room sees arrive.
        assert any("Alice leaves north" in m for m in drain(sess_b))
        assert any("Alice arrives" in m for m in drain(sess_c))

    async def test_guard_at_old_location_blocks_movement(self):
        """A behavior that blocks event:on_leave aborts the move."""
        room_a, room_b, _ = await self._setup_two_rooms()
        alice, sess = make_player("Alice", location=room_a)

        class Lockdown(Behavior):
            behavior_id = "lockdown"

            async def on_check(self, obj, action):
                if action.action_type == "event:on_leave":
                    action.block("The doors are sealed.")

        room_a.add_behavior(Lockdown())

        await cmd_go(make_ctx(sess, args="north"))

        assert alice.location is room_a, "should not have moved"
        out = drain(sess)
        assert out == ["The doors are sealed."]

    async def test_unknown_direction(self):
        room_a, _, _ = await self._setup_two_rooms()
        alice, sess = make_player("Alice", location=room_a)

        await cmd_go(make_ctx(sess, args="south"))

        assert drain(sess) == ["You can't go south."]

    async def test_dispatcher_exit_name_fires_movement_events(self):
        """Typing a bare exit name (default-game path) fires on_enter to bystanders."""
        from realm.server.dispatcher import CommandDispatcher

        room_a, room_b, _ = await self._setup_two_rooms()
        alice, sess_a = make_player("Alice", location=room_a)
        carol, sess_c = make_player("Carol", location=room_b)

        dispatcher = CommandDispatcher()
        await dispatcher.dispatch(sess_a, "north")

        assert alice.location is room_b
        assert any("Alice arrives" in m for m in drain(sess_c))

    async def test_dispatcher_exit_name_honors_block(self):
        """A behavior blocking on_leave stops movement via the dispatcher path too."""
        from realm.server.dispatcher import CommandDispatcher

        room_a, room_b, _ = await self._setup_two_rooms()
        alice, sess = make_player("Alice", location=room_a)

        class Lockdown(Behavior):
            behavior_id = "lockdown"

            async def on_check(self, obj, action):
                if action.action_type == "event:on_leave":
                    action.block("The doors are sealed.")

        room_a.add_behavior(Lockdown())

        dispatcher = CommandDispatcher()
        await dispatcher.dispatch(sess, "north")

        assert alice.location is room_a, "should not have moved"
        assert "The doors are sealed." in drain(sess)


# --- Look ------------------------------------------------------------------


@pytest.mark.asyncio
class TestLookCommand:

    async def test_look_at_room_propagates_event_look(self):
        """A behavior on the room sees event:look fire and can react to it."""
        room = GameObject("Mirror Hall", tags=["room"], description="Mirrors line the walls.")
        alice, sess = make_player("Alice", location=room)

        observed: list[str] = []

        class WatcherMirror(Behavior):
            behavior_id = "mirror"

            async def on_react(self, obj, action):
                if action.action_type == "event:look":
                    observed.append("looked")
                    action.add_message("actor", "The mirrors shimmer faintly.")

        room.add_behavior(WatcherMirror())

        await cmd_look(make_ctx(sess, args=""))

        assert observed == ["looked"]
        out = "\n".join(drain(sess))
        # Behavior's actor message was delivered, plus the display content.
        assert "The mirrors shimmer faintly." in out
        assert "Mirror Hall" in out
        assert "Mirrors line the walls." in out

    async def test_look_at_object_propagates_with_object_as_target(self):
        room = GameObject("Vault", tags=["room"])
        alice, sess = make_player("Alice", location=room)
        chest = GameObject("chest", location=room, description="A wooden chest.")

        observed: list[str] = []

        class Watcher(Behavior):
            behavior_id = "watcher"

            async def on_react(self, obj, action):
                if action.action_type == "event:look":
                    observed.append(action.target.name if action.target else "?")

        chest.add_behavior(Watcher())

        await cmd_look(make_ctx(sess, args="chest"))

        assert observed == ["chest"]
        out = "\n".join(drain(sess))
        assert "chest" in out


# --- Inventory -------------------------------------------------------------


@pytest.mark.asyncio
class TestInventoryCommands:

    async def test_get_moves_item_and_messages(self):
        room = GameObject("Room", tags=["room"])
        alice, sess_a = make_player("Alice", location=room)
        bob, sess_b = make_player("Bob", location=room)
        sword = GameObject("sword", location=room)

        await cmd_get(make_ctx(sess_a, args="sword"))

        assert sword.location is alice
        assert drain(sess_a) == ["You pick up a sword."]
        assert drain(sess_b) == ["Alice picks up a sword."]

    async def test_get_blocked_by_behavior(self):
        """A behavior on the item can block 'item:on_get' (cursed item)."""
        room = GameObject("Room", tags=["room"])
        alice, sess = make_player("Alice", location=room)
        cursed = GameObject("idol", location=room)

        class Glued(Behavior):
            behavior_id = "glued"

            async def on_check(self, obj, action):
                if action.action_type == "item:on_get":
                    action.block("The idol is fixed to the floor.")

        cursed.add_behavior(Glued())

        await cmd_get(make_ctx(sess, args="idol"))

        assert cursed.location is room, "blocked get should not move item"
        assert drain(sess) == ["The idol is fixed to the floor."]

    async def test_drop_moves_item_to_room(self):
        room = GameObject("Room", tags=["room"])
        alice, sess_a = make_player("Alice", location=room)
        bob, sess_b = make_player("Bob", location=room)
        sword = GameObject("sword", location=alice)

        await cmd_drop(make_ctx(sess_a, args="sword"))

        assert sword.location is room
        assert drain(sess_a) == ["You drop a sword."]
        assert drain(sess_b) == ["Alice drops a sword."]

    async def test_give_three_audiences(self):
        room = GameObject("Room", tags=["room"])
        alice, sess_a = make_player("Alice", location=room)
        bob, sess_b = make_player("Bob", location=room)
        charlie, sess_c = make_player("Charlie", location=room)
        coin = GameObject("coin", location=alice)

        await cmd_give(make_ctx(
            sess_a, args="coin to Bob", left_args="coin", right_args="Bob",
        ))

        assert coin.location is bob
        assert drain(sess_a) == ["You give a coin to Bob."]
        assert drain(sess_b) == ["Alice gives you a coin."]
        assert drain(sess_c) == ["Alice gives a coin to Bob."]

    async def test_put_moves_item_into_container(self):
        room = GameObject("Room", tags=["room"])
        alice, sess = make_player("Alice", location=room)
        bag = GameObject("bag", location=room)
        coin = GameObject("coin", location=alice)

        await cmd_put(make_ctx(sess, args="coin in bag"))

        assert coin.location is bag
        assert drain(sess) == ["You put a coin in the bag."]

    async def test_drop_blocked_by_cursed_behavior(self):
        room = GameObject("Room", tags=["room"])
        alice, sess = make_player("Alice", location=room)
        cursed = GameObject("ring", location=alice)

        class CantDrop(Behavior):
            behavior_id = "cant_drop"

            async def on_check(self, obj, action):
                if action.action_type == "item:on_drop":
                    action.block("The ring won't come off your finger.")

        cursed.add_behavior(CantDrop())

        await cmd_drop(make_ctx(sess, args="ring"))

        assert cursed.location is alice, "blocked drop should not move item"
        assert drain(sess) == ["The ring won't come off your finger."]


# --- Bystander flush regression -----------------------------------------


@pytest.mark.asyncio
class TestOnCommandFlushesAllSessions:
    """
    GameServer._on_command must flush every session after dispatch, not just
    the actor's. Otherwise bystanders see nothing until they type a command of
    their own. This was reported during live Mudlet testing.
    """

    async def test_bystander_writer_called_after_actor_command(self):
        from realm.commands.builtin import register_all_commands
        from realm.server.game import GameServer

        server = GameServer(db_path=":memory:", enable_telnet=False)
        register_all_commands(server.dispatcher)

        room = GameObject("Tavern", tags=["room"])
        alice = GameObject("Alice", location=room); alice.add_tag("player")
        bob = GameObject("Bob", location=room); bob.add_tag("player")

        sess_a = Session(protocol="test", address="1.1.1.1")
        sess_b = Session(protocol="test", address="2.2.2.2")

        # Capture what each session's WRITER (the network layer) actually sees.
        a_written: list[str] = []
        b_written: list[str] = []

        async def write_a(text: str) -> None: a_written.append(text)
        async def write_b(text: str) -> None: b_written.append(text)

        sess_a.set_writer(write_a)
        sess_b.set_writer(write_b)

        # Register sessions with the manager so _on_command can iterate them.
        server.session_manager._sessions[sess_a.id] = sess_a
        server.session_manager._sessions[sess_b.id] = sess_b
        sess_a.link_player(alice)
        sess_b.link_player(bob)

        # Alice issues a say command. Bob's writer must receive the broadcast
        # WITHOUT Bob having to type anything himself.
        await server._on_command(sess_a, 'say hello')

        assert any('hello' in w for w in a_written), f"actor writer empty: {a_written}"
        assert any('Alice says, "hello"' in w for w in b_written), \
            f"bystander writer empty: {b_written}"
