"""
Tests for lock ENFORCEMENT — locks stopping real actions.

The lock module itself (expressions, validation, bypass) is covered in
test_permissions.py. These tests prove the wiring: locks checked in the
propagation check pass (get/drop/give/put/speech), in the movement gate
(exit traversal, room entry), and by the @lock command's write-time
validation.
"""

from __future__ import annotations

import pytest

from realm.commands.builtin.communication import cmd_say
from realm.commands.builtin.inventory import cmd_drop, cmd_get, cmd_give, cmd_put
from realm.core.movement import move_through_exit
from realm.core.objects import GameObject
from realm.core.propagation import reset_engine
from realm.gateway.session import Session
from realm.server.dispatcher import CommandContext


@pytest.fixture(autouse=True)
def fresh_propagation_engine():
    reset_engine()
    yield
    reset_engine()


def make_player(name: str, location: GameObject | None = None) -> tuple[GameObject, Session]:
    player = GameObject(name=name, location=location)
    player.add_tag("player")
    sess = Session(protocol="test", address="127.0.0.1")
    sess.link_player(player)
    return player, sess


def drain(sess: Session) -> list[str]:
    out: list[str] = []
    while not sess._output_queue.empty():
        out.append(sess._output_queue.get_nowait())
    return out


def make_ctx(sess: Session, *, args: str = "", left_args: str = "",
             right_args: str = "") -> CommandContext:
    return CommandContext(
        session=sess,
        player=sess.player,
        raw_input=args,
        command_name="test",
        args=args,
        left_args=left_args or args,
        right_args=right_args,
    )


# --- Item locks (propagation check pass) ------------------------------------


@pytest.mark.asyncio
class TestItemLocks:

    async def test_basic_lock_blocks_get(self):
        room = GameObject("Vault", tags=["room"])
        gem = GameObject("gem", location=room, tags=["thing"])
        gem.locks["basic"] = "False"
        alice, sess = make_player("Alice", location=room)

        await cmd_get(make_ctx(sess, args="gem"))

        assert gem.location is room
        assert drain(sess) == ["You can't pick up gem."]

    async def test_basic_lock_expression_grants_by_tag(self):
        room = GameObject("Vault", tags=["room"])
        gem = GameObject("gem", location=room, tags=["thing"])
        gem.locks["basic"] = "caller.has_tag('key_holder')"
        alice, sess = make_player("Alice", location=room)

        await cmd_get(make_ctx(sess, args="gem"))
        assert gem.location is room  # not a key holder

        alice.add_tag("key_holder")
        await cmd_get(make_ctx(sess, args="gem"))
        assert gem.location is alice

    async def test_admin_bypasses_lock(self):
        room = GameObject("Vault", tags=["room"])
        gem = GameObject("gem", location=room, tags=["thing"])
        gem.locks["basic"] = "False"
        admin, sess = make_player("Odin", location=room)
        admin.add_tag("admin")

        await cmd_get(make_ctx(sess, args="gem"))

        assert gem.location is admin

    async def test_erroring_expression_fails_closed(self):
        room = GameObject("Vault", tags=["room"])
        gem = GameObject("gem", location=room, tags=["thing"])
        gem.locks["basic"] = "caller.db.level >= 10"  # level is None -> error
        alice, sess = make_player("Alice", location=room)

        await cmd_get(make_ctx(sess, args="gem"))

        assert gem.location is room

    async def test_drop_lock_blocks_drop(self):
        room = GameObject("Room", tags=["room"])
        alice, sess = make_player("Alice", location=room)
        ring = GameObject("ring", location=alice, tags=["thing"])
        ring.locks["drop"] = "False"

        await cmd_drop(make_ctx(sess, args="ring"))

        assert ring.location is alice
        assert drain(sess) == ["You can't drop ring."]

    async def test_give_lock_on_item_blocks_give(self):
        room = GameObject("Room", tags=["room"])
        alice, sess_a = make_player("Alice", location=room)
        bob, _sess_b = make_player("Bob", location=room)
        heirloom = GameObject("heirloom", location=alice, tags=["thing"])
        heirloom.locks["give"] = "False"

        await cmd_give(make_ctx(sess_a, args="heirloom to Bob"))

        assert heirloom.location is alice
        assert drain(sess_a) == ["You can't give heirloom away."]

    async def test_enter_lock_blocks_put(self):
        room = GameObject("Room", tags=["room"])
        alice, sess = make_player("Alice", location=room)
        coin = GameObject("coin", location=alice, tags=["thing"])
        chest = GameObject("chest", location=room, tags=["thing"])
        chest.locks["enter"] = "False"

        await cmd_put(make_ctx(sess, args="coin in chest"))

        assert coin.location is alice
        assert drain(sess) == ["You can't put things in chest."]

    async def test_custom_failure_message(self):
        room = GameObject("Vault", tags=["room"])
        gem = GameObject("gem", location=room, tags=["thing"])
        gem.locks["basic"] = "False"
        gem.db.lock_fail_basic = "The gem crackles with warding energy."
        alice, sess = make_player("Alice", location=room)

        await cmd_get(make_ctx(sess, args="gem"))

        assert drain(sess) == ["The gem crackles with warding energy."]

    async def test_get_all_honors_per_item_locks(self):
        room = GameObject("Room", tags=["room"])
        free = GameObject("apple", location=room, tags=["thing"])
        locked = GameObject("anvil", location=room, tags=["thing"])
        locked.locks["basic"] = "False"
        alice, sess = make_player("Alice", location=room)

        await cmd_get(make_ctx(sess, args="all"))

        assert free.location is alice
        assert locked.location is room
        out = drain(sess)
        assert "You can't pick up anvil." in out
        assert any("You pick up an apple." in line for line in out)


# --- Speech locks -------------------------------------------------------------


@pytest.mark.asyncio
class TestSpeechLocks:

    async def test_speech_lock_silences_say(self):
        room = GameObject("Library", tags=["room"])
        room.locks["speech"] = "False"
        alice, sess_a = make_player("Alice", location=room)
        bob, sess_b = make_player("Bob", location=room)

        await cmd_say(make_ctx(sess_a, args="hello?"))

        assert drain(sess_a) == ["You can't speak here."]
        assert drain(sess_b) == []  # success messages suppressed

    async def test_speech_lock_custom_message(self):
        room = GameObject("Library", tags=["room"])
        room.locks["speech"] = "False"
        room.db.lock_fail_speech = "A librarian glares you into silence."
        alice, sess = make_player("Alice", location=room)

        await cmd_say(make_ctx(sess, args="hello?"))

        assert drain(sess) == ["A librarian glares you into silence."]

    async def test_unlocked_room_speech_unaffected(self):
        room = GameObject("Plaza", tags=["room"])
        alice, sess_a = make_player("Alice", location=room)
        bob, sess_b = make_player("Bob", location=room)

        await cmd_say(make_ctx(sess_a, args="hello"))

        assert drain(sess_a) == ['You say, "hello"']
        assert drain(sess_b) == ['Alice says, "hello"']


# --- Movement locks -----------------------------------------------------------


@pytest.mark.asyncio
class TestMovementLocks:

    def _rooms_with_exit(self):
        room_a = GameObject("Hall", tags=["room"])
        room_b = GameObject("Sanctum", tags=["room"])
        door = GameObject("north", location=room_a, tags=["exit"])
        door.db.destination_obj = room_b
        return room_a, room_b, door

    async def test_exit_basic_lock_blocks_traversal(self):
        room_a, room_b, door = self._rooms_with_exit()
        door.locks["basic"] = "False"
        alice, sess = make_player("Alice", location=room_a)

        moved = await move_through_exit(alice, room_b, exit_obj=door)

        assert moved is False
        assert alice.location is room_a
        assert drain(sess) == ["You can't go north — it's locked."]

    async def test_exit_lock_expression_grants_by_tag(self):
        room_a, room_b, door = self._rooms_with_exit()
        door.locks["basic"] = "caller.has_tag('key_holder')"
        alice, sess = make_player("Alice", location=room_a)
        alice.add_tag("key_holder")

        moved = await move_through_exit(alice, room_b, exit_obj=door)

        assert moved is True
        assert alice.location is room_b

    async def test_destination_enter_lock_blocks_entry(self):
        room_a, room_b, door = self._rooms_with_exit()
        room_b.locks["enter"] = "False"
        alice, sess = make_player("Alice", location=room_a)

        moved = await move_through_exit(alice, room_b, exit_obj=door)

        assert moved is False
        assert alice.location is room_a
        assert drain(sess) == ["You can't enter Sanctum."]

    async def test_exit_custom_failure_message(self):
        room_a, room_b, door = self._rooms_with_exit()
        door.locks["basic"] = "False"
        door.db.lock_fail_basic = "The door is sealed by an ancient ward."
        alice, sess = make_player("Alice", location=room_a)

        await move_through_exit(alice, room_b, exit_obj=door)

        assert drain(sess) == ["The door is sealed by an ancient ward."]

    async def test_admin_bypasses_movement_locks(self):
        room_a, room_b, door = self._rooms_with_exit()
        door.locks["basic"] = "False"
        room_b.locks["enter"] = "False"
        admin, sess = make_player("Odin", location=room_a)
        admin.add_tag("admin")

        moved = await move_through_exit(admin, room_b, exit_obj=door)

        assert moved is True
        assert admin.location is room_b


# --- @lock command ------------------------------------------------------------


@pytest.mark.asyncio
class TestLockCommand:

    def _builder_ctx(self, **kwargs):
        from tests.test_olc import MockPersistence, make_context, use_persistence
        self.persistence = MockPersistence()
        use_persistence(self.persistence)
        self.room = GameObject("Workshop", tags=["room"])
        self.builder = GameObject("Bob", tags=["player", "builder"], location=self.room)
        self.thing = GameObject("box", location=self.room, tags=["thing"])
        self.persistence.add(self.room)
        self.persistence.add(self.builder)
        self.persistence.add(self.thing)
        return make_context(self.builder, **kwargs)

    async def test_bare_lock_sets_basic(self):
        from realm.commands.olc.modify import cmd_lock
        ctx = self._builder_ctx(
            args="box = caller.has_tag('vip')",
            left_args="box",
            right_args="caller.has_tag('vip')",
        )
        await cmd_lock(ctx)

        assert self.thing.locks["basic"] == "caller.has_tag('vip')"
        assert "Lock/basic set on box." in ctx.session.messages

    async def test_invalid_expression_rejected_not_stored(self):
        from realm.commands.olc.modify import cmd_lock
        ctx = self._builder_ctx(
            args="box = import os",
            left_args="box",
            right_args="import os",
        )
        await cmd_lock(ctx)

        assert "basic" not in self.thing.locks
        assert any("Invalid lock expression" in m for m in ctx.session.messages)

    async def test_unknown_lock_type_rejected(self):
        from realm.commands.olc.modify import cmd_lock
        ctx = self._builder_ctx(
            args="box = True",
            left_args="box",
            right_args="True",
        )
        ctx.switches = ["frobnicate"]
        await cmd_lock(ctx)

        assert self.thing.locks == {}
        assert any("Unknown lock type" in m for m in ctx.session.messages)

    async def test_lock_set_then_enforced_end_to_end(self):
        """A lock set via @lock actually stops the action."""
        from realm.commands.olc.modify import cmd_lock
        ctx = self._builder_ctx(
            args="box = False",
            left_args="box",
            right_args="False",
        )
        await cmd_lock(ctx)

        alice, sess = make_player("Alice", location=self.room)
        await cmd_get(make_ctx(sess, args="box"))

        assert self.thing.location is self.room
        assert drain(sess) == ["You can't pick up box."]
