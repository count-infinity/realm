"""
Integration tests for the wired ScriptEngine.

The engine has two entry points:
- handle_unknown_command: the dispatcher's softcode $-command fallback
- handle_action: a propagation observer firing ^listen and ON_<EVENT>
  triggers on the same action stream behaviors see

Scripted output (say/pose/emit/whisper) is emitted back through the
propagation engine as real actions, so these tests assert on what lands in
player session queues — the player-visible truth.
"""

from __future__ import annotations

import re

import pytest

from realm.core.movement import move_through_exit
from realm.core.objects import GameObject
from realm.core.propagation import get_engine, reset_engine
from realm.gateway.session import Session
from realm.scripting.engine import ScriptEngine
from realm.server.dispatcher import CommandContext

# --- Helpers ---------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_propagation_engine():
    """Each test gets a fresh propagation singleton (observers reset)."""
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


def make_ctx(sess: Session, raw_input: str) -> CommandContext:
    parts = raw_input.split(None, 1)
    return CommandContext(
        session=sess,
        player=sess.player,
        raw_input=raw_input,
        command_name=parts[0].lower() if parts else "",
        args=parts[1] if len(parts) > 1 else "",
    )


def wired_engine() -> ScriptEngine:
    """A ScriptEngine observing the (fresh) propagation singleton."""
    engine = ScriptEngine()
    get_engine().add_observer(engine.handle_action)
    return engine


# --- $-command fallback -----------------------------------------------------


@pytest.mark.asyncio
class TestCommandFallback:

    async def test_dollar_command_fires_npc_response(self):
        room = GameObject("Cantina", tags=["room"])
        npc = GameObject("Zeke", location=room)
        npc.db.cmd_greet = "$greet*:say Welcome to The Void's Edge."
        alice, sess = make_player("Alice", location=room)

        engine = wired_engine()
        handled = await engine.handle_unknown_command(make_ctx(sess, "greet"))

        assert handled is True
        assert 'Zeke says, "Welcome to The Void\'s Edge."' in drain(sess)

    async def test_wildcard_capture_substitution(self):
        room = GameObject("Cantina", tags=["room"])
        npc = GameObject("Zeke", location=room)
        npc.db.cmd_buy = "$buy *:say That'll be 5 credits for a %0."
        alice, sess = make_player("Alice", location=room)

        engine = wired_engine()
        handled = await engine.handle_unknown_command(make_ctx(sess, "buy beer"))

        assert handled is True
        assert 'Zeke says, "That\'ll be 5 credits for a beer."' in drain(sess)

    async def test_no_match_returns_false(self):
        room = GameObject("Cantina", tags=["room"])
        alice, sess = make_player("Alice", location=room)

        engine = wired_engine()
        handled = await engine.handle_unknown_command(make_ctx(sess, "frobnicate"))

        assert handled is False
        assert drain(sess) == []

    async def test_halt_tag_suppresses_triggers(self):
        room = GameObject("Cantina", tags=["room"])
        npc = GameObject("Zeke", location=room)
        npc.db.cmd_greet = "$greet*:say Welcome!"
        npc.add_tag("halt")
        alice, sess = make_player("Alice", location=room)

        engine = wired_engine()
        handled = await engine.handle_unknown_command(make_ctx(sess, "greet"))

        assert handled is False

    async def test_halted_owner_freezes_owned_object(self):
        """A halted owner freezes its objects' softcode (the fail-safe) —
        even though the object itself carries no halt tag."""
        room = GameObject("Cantina", tags=["room"])
        builder = GameObject("Bilda", tags=["builder"])
        gadget = GameObject("Zeke", location=room, owner=builder)
        gadget.db.cmd_greet = "$greet*:say Welcome!"
        alice, sess = make_player("Alice", location=room)
        engine = wired_engine()

        # Baseline: neither halted -> the $-command fires.
        assert gadget.is_halted is False
        assert await engine.handle_unknown_command(make_ctx(sess, "greet")) is True

        # Halt the OWNER (not the gadget) -> the gadget goes inert.
        builder.add_tag("halt")
        assert gadget.is_halted is True
        assert gadget.has_tag("halt") is False  # inherited, not direct
        assert await engine.handle_unknown_command(make_ctx(sess, "greet")) is False


def test_is_halted_is_single_level():
    """Own tag or the immediate owner's — not a full owner-chain walk."""
    grandowner = GameObject("Root")
    owner = GameObject("Mid", owner=grandowner)
    obj = GameObject("Leaf", owner=owner)

    assert obj.is_halted is False
    grandowner.add_tag("halt")
    assert obj.is_halted is False   # grand-owner does not propagate
    owner.add_tag("halt")
    assert obj.is_halted is True    # immediate owner does
    owner.remove_tag("halt")
    obj.add_tag("halt")
    assert obj.is_halted is True    # own tag still works


# --- ^listen triggers via propagation ---------------------------------------


@pytest.mark.asyncio
class TestListenTriggers:

    async def test_speech_triggers_listen(self):
        from realm.commands.builtin.communication import cmd_say

        room = GameObject("Cantina", tags=["room"])
        npc = GameObject("Zeke", location=room)
        npc.db.listen_trouble = "^*trouble*:say We don't want any trouble here."
        alice, sess_a = make_player("Alice", location=room)
        bob, sess_b = make_player("Bob", location=room)

        wired_engine()
        await cmd_say(make_ctx(sess_a, "say I'm looking for trouble"))

        a_out = drain(sess_a)
        b_out = drain(sess_b)
        # Alice hears her own say, then the NPC's scripted response.
        assert a_out[0] == 'You say, "I\'m looking for trouble"'
        assert 'Zeke says, "We don\'t want any trouble here."' in a_out
        # The bystander hears both the speech and the response.
        assert 'Alice says, "I\'m looking for trouble"' in b_out
        assert 'Zeke says, "We don\'t want any trouble here."' in b_out

    async def test_speaker_does_not_trigger_own_listen(self):
        from realm.commands.builtin.communication import cmd_say

        room = GameObject("Cantina", tags=["room"])
        alice, sess = make_player("Alice", location=room)
        alice.db.listen_echo = "^*hello*:say I heard myself?!"

        wired_engine()
        await cmd_say(make_ctx(sess, "say hello there"))

        out = drain(sess)
        assert out == ['You say, "hello there"']

    async def test_whisper_is_not_overheard(self):
        from realm.commands.builtin.communication import cmd_whisper

        room = GameObject("Cantina", tags=["room"])
        npc = GameObject("Zeke", location=room)
        npc.db.listen_secret = "^*secret*:say I know your secret!"
        alice, sess_a = make_player("Alice", location=room)
        bob, sess_b = make_player("Bob", location=room)

        wired_engine()
        ctx = make_ctx(sess_a, "whisper Bob = a secret for you")
        ctx.left_args = "Bob"
        ctx.right_args = "a secret for you"
        await cmd_whisper(ctx)

        combined = drain(sess_a) + drain(sess_b)
        assert not any("I know your secret" in line for line in combined)

    async def test_scripted_whisper_resolves_target_by_partial_name(self):
        """A scripted whisper shares cmd_whisper's pathway (do_whisper) and
        resolves its target perception-aware — so a partial name works,
        where the old exact-match actuator required the full name."""
        room = GameObject("Cantina", tags=["room"])
        npc = GameObject("Zeke", location=room)
        # $tip triggers a scripted whisper to a partial name.
        npc.db.cmd_tip = "$tip:whisper Alic = the vault code is 1234"
        alice, sess_a = make_player("Alice", location=room)
        _bob, sess_b = make_player("Bob", location=room)

        engine = wired_engine()
        handled = await engine.handle_unknown_command(make_ctx(sess_a, "tip"))

        assert handled is True
        a_out = drain(sess_a)
        assert any("Zeke whispers" in line and "1234" in line for line in a_out)
        # Bob only sees the vague room line, never the secret.
        b_out = drain(sess_b)
        assert not any("1234" in line for line in b_out)
        assert any("whispers something to Alice" in line for line in b_out)

    async def test_scripted_whisper_to_unseen_target_is_noop(self):
        """No perceivable target by that name → the whisper is dropped, no
        crash (the guarded match replaces the old bare exact-match loop)."""
        room = GameObject("Cantina", tags=["room"])
        npc = GameObject("Zeke", location=room)
        npc.db.cmd_tip = "$tip:whisper Ghost = nobody home"
        alice, sess_a = make_player("Alice", location=room)

        engine = wired_engine()
        handled = await engine.handle_unknown_command(make_ctx(sess_a, "tip"))

        assert handled is True
        assert not any("nobody home" in line for line in drain(sess_a))

    async def test_listen_recursion_is_depth_limited(self):
        """Two NPCs whose listens answer each other must not loop forever."""
        from realm.commands.builtin.communication import cmd_say

        room = GameObject("Cantina", tags=["room"])
        npc_a = GameObject("Alpha", location=room)
        npc_a.db.listen_echo = "^*echo*:say echo alpha"
        npc_b = GameObject("Beta", location=room)
        npc_b.db.listen_echo = "^*echo*:say echo beta"
        alice, sess = make_player("Alice", location=room)

        wired_engine()
        await cmd_say(make_ctx(sess, "say echo start"))

        out = drain(sess)
        # The guard bounds each response CHAIN to MAX_SCRIPT_DEPTH; with two
        # listeners the total is bounded by breadth**depth, not depth. What
        # matters: it terminated, and stayed within that envelope.
        assert out[0] == 'You say, "echo start"'
        assert 2 <= len(out) <= 1 + 2 ** ScriptEngine.MAX_SCRIPT_DEPTH


# --- ON_<EVENT> triggers ----------------------------------------------------


@pytest.mark.asyncio
class TestEventTriggers:

    async def test_on_enter_fires_room_greeter(self):
        room_a = GameObject("Plaza", tags=["room"])
        room_b = GameObject("Shop", tags=["room"])
        exit_obj = GameObject("east", location=room_a, tags=["exit"])
        exit_obj.db.destination_obj = room_b

        greeter = GameObject("Shopkeeper", location=room_b)
        greeter.db.on_enter = "say Welcome to my shop!"

        alice, sess = make_player("Alice", location=room_a)

        wired_engine()
        moved = await move_through_exit(alice, room_b, exit_obj=exit_obj)

        assert moved is True
        assert 'Shopkeeper says, "Welcome to my shop!"' in drain(sess)

    async def test_on_arrive_fires_on_the_mover(self):
        room_a = GameObject("Plaza", tags=["room"])
        room_b = GameObject("Shop", tags=["room"])

        alice, sess = make_player("Alice", location=room_a)
        alice.db.on_arrive = "pose stretches after the trip."
        bob, sess_b = make_player("Bob", location=room_b)

        wired_engine()
        await move_through_exit(alice, room_b)

        assert "Alice stretches after the trip." in drain(sess_b)

    async def test_blocked_action_fires_no_triggers(self):
        from realm.core.propagation import ROOM_TARGET_CHAIN, Action

        room = GameObject("Cantina", tags=["room"])
        npc = GameObject("Zeke", location=room)
        npc.db.listen_any = "^*:say I hear everything."
        alice, sess = make_player("Alice", location=room)

        engine = wired_engine()
        action = Action(
            actor=alice,
            target=room,
            action_type="event:speech",
            chain=ROOM_TARGET_CHAIN,
            extra={"message": "can you hear me?"},
        )
        action.block("gagged")
        await engine.handle_action(action)

        assert drain(sess) == []


# --- Python scripts with injected functions ---------------------------------


@pytest.mark.asyncio
class TestPythonScripts:

    async def test_script_functions_available(self):
        room = GameObject("Cantina", tags=["room"])
        npc = GameObject("Croupier", location=room)
        npc.db.cmd_roll = (
            "$roll:total = dice(2, 6)\n"
            'say(f"You rolled {total}!")'
        )
        alice, sess = make_player("Alice", location=room)

        engine = wired_engine()
        handled = await engine.handle_unknown_command(make_ctx(sess, "roll"))

        assert handled is True
        out = drain(sess)
        rolled = [line for line in out if re.search(r'Croupier says, "You rolled \d+!"', line)]
        assert rolled, f"no roll output in {out}"
        value = int(re.search(r"rolled (\d+)!", rolled[0]).group(1))
        assert 2 <= value <= 12

    async def test_script_can_mutate_attributes(self):
        room = GameObject("Cantina", tags=["room"])
        npc = GameObject("Counter", location=room)
        npc.db.visits = 0
        npc.db.cmd_visit = (
            "$visit:count = get_attr(me, 'visits', 0) + 1\n"
            "set_attr(me, 'visits', count)\n"
            'say(f"Visitor number {count}.")'
        )
        alice, sess = make_player("Alice", location=room)

        engine = wired_engine()
        await engine.handle_unknown_command(make_ctx(sess, "visit"))
        await engine.handle_unknown_command(make_ctx(sess, "visit"))

        assert npc.db.visits == 2
        out = drain(sess)
        assert 'Counter says, "Visitor number 2."' in out

    async def test_pemit_delivers_privately(self):
        room = GameObject("Cantina", tags=["room"])
        npc = GameObject("Oracle", location=room)
        npc.db.cmd_fortune = (
            "$fortune:pemit(enactor, 'The stars whisper only to you.')"
        )
        alice, sess_a = make_player("Alice", location=room)
        bob, sess_b = make_player("Bob", location=room)

        engine = wired_engine()
        handled = await engine.handle_unknown_command(make_ctx(sess_a, "fortune"))

        assert handled is True
        assert "The stars whisper only to you." in drain(sess_a)
        assert drain(sess_b) == []

    async def test_script_error_reported_to_invoker(self):
        room = GameObject("Cantina", tags=["room"])
        npc = GameObject("Buggy", location=room)
        npc.db.cmd_break = "$break:import os\nsay('never runs')"
        alice, sess = make_player("Alice", location=room)

        engine = wired_engine()
        handled = await engine.handle_unknown_command(make_ctx(sess, "break"))

        assert handled is True
        out = drain(sess)
        assert any("Script error" in line for line in out)
        assert not any("never runs" in line for line in out)


# --- GameServer wiring -------------------------------------------------------


@pytest.mark.asyncio
class TestServerWiring:

    async def test_server_dispatch_reaches_softcode(self):
        from realm.server.game import GameServer

        server = GameServer(db_path=":memory:", enable_telnet=False)
        await server.start()
        try:
            room = GameObject("Cantina", tags=["room"])
            npc = GameObject("Zeke", location=room)
            npc.db.cmd_greet = "$greet*:say Welcome, traveler."

            alice, sess = make_player("Alice", location=room)
            server.session_manager._sessions[sess.id] = sess

            await server.dispatcher.dispatch(sess, "greet")

            assert 'Zeke says, "Welcome, traveler."' in drain(sess)
        finally:
            await server.stop()

    async def test_unknown_command_still_says_huh(self):
        from realm.server.game import GameServer

        server = GameServer(db_path=":memory:", enable_telnet=False)
        await server.start()
        try:
            room = GameObject("Void", tags=["room"])
            alice, sess = make_player("Alice", location=room)
            server.session_manager._sessions[sess.id] = sess

            await server.dispatcher.dispatch(sess, "frobnicate")

            out = drain(sess)
            assert any("Huh?" in line for line in out)
        finally:
            await server.stop()

    async def test_enable_scripting_false_disables_fallback(self):
        from realm.server.game import GameServer

        server = GameServer(
            db_path=":memory:", enable_telnet=False, enable_scripting=False,
        )
        await server.start()
        try:
            assert server.script_engine is None

            room = GameObject("Cantina", tags=["room"])
            npc = GameObject("Zeke", location=room)
            npc.db.cmd_greet = "$greet*:say Welcome, traveler."
            alice, sess = make_player("Alice", location=room)
            server.session_manager._sessions[sess.id] = sess

            await server.dispatcher.dispatch(sess, "greet")

            out = drain(sess)
            assert any("Huh?" in line for line in out)
            assert not any("Welcome, traveler" in line for line in out)
        finally:
            await server.stop()

    async def test_stop_detaches_observer(self):
        from realm.server.game import GameServer

        server = GameServer(db_path=":memory:", enable_telnet=False)
        await server.start()
        engine_ref = server.script_engine
        assert engine_ref is not None
        assert engine_ref.handle_action in get_engine()._observers
        await server.stop()
        assert engine_ref.handle_action not in get_engine()._observers
