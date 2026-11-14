"""Tests for the CommandDispatcher class."""

import pytest

from realm.commands.dispatcher import (
    CommandContext,
    CommandDispatcher,
)
from realm.core.objects import GameObject
from realm.gateway.session import Session


class TestCommandContext:
    """Test suite for CommandContext."""

    def test_context_creation(self):
        """CommandContext can be created with required fields."""
        session = Session()
        player = GameObject("Player", tags=['player'])

        ctx = CommandContext(
            session=session,
            player=player,
            raw_input="look here",
            command_name="look",
            args="here",
        )

        assert ctx.session == session
        assert ctx.player == player
        assert ctx.raw_input == "look here"
        assert ctx.command_name == "look"
        assert ctx.args == "here"

    def test_context_without_player(self):
        """CommandContext works without a player."""
        session = Session()

        ctx = CommandContext(
            session=session,
            player=None,
            raw_input="connect name pass",
            command_name="connect",
            args="name pass",
        )

        assert ctx.player is None

    def test_context_with_switches(self):
        """CommandContext stores switches."""
        session = Session()

        ctx = CommandContext(
            session=session,
            player=None,
            raw_input="@set/quiet obj=value",
            command_name="set",
            args="obj=value",
            switches=["quiet"],
        )

        assert ctx.switches == ["quiet"]

    def test_context_left_right_args(self):
        """CommandContext stores left/right split."""
        session = Session()

        ctx = CommandContext(
            session=session,
            player=None,
            raw_input="@set obj=value",
            command_name="set",
            args="obj=value",
            left_args="obj",
            right_args="value",
        )

        assert ctx.left_args == "obj"
        assert ctx.right_args == "value"


class TestCommandDispatcher:
    """Test suite for CommandDispatcher."""

    @pytest.mark.asyncio
    async def test_register_command(self):
        """Commands can be registered."""
        dispatcher = CommandDispatcher()
        called = []

        async def handler(ctx):
            called.append(ctx.command_name)

        dispatcher.register("test", handler)

        # Command should be findable
        cmd = dispatcher.get_command("test")
        assert cmd is not None
        assert cmd.name == "test"

    @pytest.mark.asyncio
    async def test_dispatch_simple_command(self):
        """Simple commands are dispatched correctly."""
        dispatcher = CommandDispatcher()
        called = []

        async def handler(ctx):
            called.append(ctx.args)

        dispatcher.register("echo", handler)

        session = Session()
        player = GameObject("Player", tags=['player'])
        session.link_player(player)

        await dispatcher.dispatch(session, "echo hello world")

        assert called == ["hello world"]

    @pytest.mark.asyncio
    async def test_dispatch_with_alias(self):
        """Commands can be called by alias."""
        dispatcher = CommandDispatcher()
        called = []

        async def handler(ctx):
            # ctx.command_name reflects what user typed, handler is called
            called.append("handler_called")

        dispatcher.register("look", handler, aliases=["l", "lo"])

        session = Session()
        player = GameObject("Player", tags=['player'])
        session.link_player(player)

        await dispatcher.dispatch(session, "l")
        await dispatcher.dispatch(session, "lo")
        await dispatcher.dispatch(session, "look")

        # All three invocations should call the handler
        assert len(called) == 3

    @pytest.mark.asyncio
    async def test_dispatch_prefix_match(self):
        """Unique prefixes match commands."""
        dispatcher = CommandDispatcher()
        called = []

        async def handler(ctx):
            called.append(ctx.command_name)

        dispatcher.register("inventory", handler)

        session = Session()
        player = GameObject("Player", tags=['player'])
        session.link_player(player)

        await dispatcher.dispatch(session, "inv")
        await dispatcher.dispatch(session, "inve")
        await dispatcher.dispatch(session, "inventory")

        assert len(called) == 3

    @pytest.mark.asyncio
    async def test_dispatch_ambiguous_prefix(self):
        """Ambiguous prefixes show error."""
        dispatcher = CommandDispatcher()

        async def handler(ctx):
            pass

        dispatcher.register("look", handler)
        dispatcher.register("lock", handler)

        session = Session()
        player = GameObject("Player", tags=['player'])
        session.link_player(player)

        await dispatcher.dispatch(session, "lo")

        # Should have error message in output
        msg = session._output_queue.get_nowait()
        assert "Ambiguous" in msg
        assert "look" in msg
        assert "lock" in msg

    @pytest.mark.asyncio
    async def test_token_expansion(self):
        """Special tokens expand to commands."""
        dispatcher = CommandDispatcher()
        called = []

        async def say_handler(ctx):
            called.append(('say', ctx.args))

        async def pose_handler(ctx):
            called.append(('pose', ctx.args))

        dispatcher.register("say", say_handler, tokens=['"'])
        dispatcher.register("pose", pose_handler, tokens=[':'])

        session = Session()
        player = GameObject("Player", tags=['player'])
        session.link_player(player)

        await dispatcher.dispatch(session, '"Hello!')
        await dispatcher.dispatch(session, ":waves")

        assert ('say', 'Hello!') in called
        assert ('pose', 'waves') in called

    @pytest.mark.asyncio
    async def test_switch_parsing(self):
        """Switches are parsed from command."""
        dispatcher = CommandDispatcher()
        captured = []

        async def handler(ctx):
            captured.append(ctx.switches)

        dispatcher.register("set", handler)

        session = Session()
        player = GameObject("Player", tags=['player'])
        session.link_player(player)

        await dispatcher.dispatch(session, "set/quiet/force obj=val")

        assert captured == [["quiet", "force"]]

    @pytest.mark.asyncio
    async def test_equals_splitting(self):
        """Arguments are split at '='."""
        dispatcher = CommandDispatcher()
        captured = []

        async def handler(ctx):
            captured.append((ctx.left_args, ctx.right_args))

        dispatcher.register("set", handler)

        session = Session()
        player = GameObject("Player", tags=['player'])
        session.link_player(player)

        await dispatcher.dispatch(session, "set foo = bar baz")

        assert captured == [("foo", "bar baz")]

    @pytest.mark.asyncio
    async def test_an_alias_reaches_the_command_by_its_own_name(self):
        """'n' runs north, and the handler sees command_name 'north'."""
        dispatcher = CommandDispatcher()
        called = []

        async def handler(ctx):
            called.append(ctx.command_name)

        dispatcher.register("north", handler, aliases=["n"])
        dispatcher.register("south", handler, aliases=["s"])

        session = Session()
        player = GameObject("Player", tags=['player'])
        session.link_player(player)

        await dispatcher.dispatch(session, "n")
        await dispatcher.dispatch(session, "s")

        assert "north" in called
        assert "south" in called

    @pytest.mark.asyncio
    async def test_login_handler(self):
        """Login handler is called when not logged in."""
        dispatcher = CommandDispatcher()
        login_calls = []

        async def login_handler(ctx):
            login_calls.append(ctx.args)

        dispatcher.set_login_handler(login_handler)

        session = Session()  # No player

        await dispatcher.dispatch(session, "connect user pass")

        assert login_calls == ["connect user pass"]

    @pytest.mark.asyncio
    async def test_unknown_handler(self):
        """Unknown handler is called for unrecognized commands."""
        dispatcher = CommandDispatcher()
        unknown_calls = []

        async def unknown_handler(ctx):
            unknown_calls.append(ctx.command_name)

        dispatcher.set_unknown_handler(unknown_handler)

        session = Session()
        player = GameObject("Player", tags=['player'])
        session.link_player(player)

        await dispatcher.dispatch(session, "xyzzy")

        assert "xyzzy" in unknown_calls

    @pytest.mark.asyncio
    async def test_unregister_command(self):
        """Commands can be unregistered."""
        dispatcher = CommandDispatcher()

        async def handler(ctx):
            pass

        dispatcher.register("test", handler, aliases=["t"])
        dispatcher.unregister("test")

        assert dispatcher.get_command("test") is None
        assert dispatcher.get_command("t") is None

    @pytest.mark.asyncio
    async def test_plus_command_receives_its_arguments(self):
        """A Python command named with a leading + is an ordinary command."""
        dispatcher = CommandDispatcher()
        called = []

        async def handler(ctx):
            called.append((ctx.command_name, ctx.args))

        dispatcher.register("+finger", handler)

        session = Session()
        player = GameObject("Player", tags=['player'])
        session.link_player(player)

        await dispatcher.dispatch(session, "+finger Alice")

        assert called == [("+finger", "Alice")]


class TestTheKernelKnowsNoVocabulary:
    """Tokens, directions and exits come from features (KERNEL_PLAN 7.3)."""

    def _session(self):
        session = Session()
        session.link_player(GameObject("Player", tags=['player']))
        return session

    @pytest.mark.asyncio
    async def test_a_bare_dispatcher_has_no_tokens_or_directions(self):
        dispatcher = CommandDispatcher()
        unknown = []

        async def on_unknown(ctx):
            unknown.append(ctx.command_name)

        dispatcher.set_unknown_handler(on_unknown)
        session = self._session()
        await dispatcher.dispatch(session, '"hello')
        await dispatcher.dispatch(session, "n")
        assert unknown == ['"hello', "n"]

    def test_classic_declares_the_talk_tokens_and_direction_aliases(self):
        from realm.features import load
        from realm.std import CLASSIC
        dispatcher = CommandDispatcher()
        load(CLASSIC).install_commands(dispatcher)
        assert dispatcher._tokens == {'"': 'say', "'": 'say', ':': 'pose',
                                      ';': 'semipose', '\\': 'emit'}
        for short, name in [('n', 'north'), ('s', 'south'), ('e', 'east'),
                            ('w', 'west'), ('u', 'up'), ('d', 'down'),
                            ('ne', 'northeast'), ('nw', 'northwest'),
                            ('se', 'southeast'), ('sw', 'southwest')]:
            assert dispatcher.get_command(short).name == name

    @pytest.mark.asyncio
    async def test_fallbacks_run_in_order_before_the_unknown_handler(self):
        dispatcher = CommandDispatcher()
        seen = []

        async def first(ctx):
            seen.append("first")
            return ctx.command_name == "one"

        async def second(ctx):
            seen.append("second")
            return ctx.command_name == "two"

        async def on_unknown(ctx):
            seen.append("unknown")

        dispatcher.add_fallback(first)
        dispatcher.add_fallback(second)
        dispatcher.set_unknown_handler(on_unknown)
        session = self._session()
        await dispatcher.dispatch(session, "one")
        await dispatcher.dispatch(session, "two")
        await dispatcher.dispatch(session, "three")
        assert seen == ["first", "first", "second",
                        "first", "second", "unknown"]
