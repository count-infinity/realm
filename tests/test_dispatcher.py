"""Tests for the CommandDispatcher class."""

import pytest

from realm.commands.dispatcher import (
    DIRECTION_ALIASES,
    TOKEN_MAP,
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

        dispatcher.register("say", say_handler)
        dispatcher.register("pose", pose_handler)

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
    async def test_direction_aliases(self):
        """Direction aliases are expanded."""
        dispatcher = CommandDispatcher()
        called = []

        async def handler(ctx):
            called.append(ctx.command_name)

        dispatcher.register("north", handler)
        dispatcher.register("south", handler)

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


class TestTokenMap:
    """Test that TOKEN_MAP contains expected tokens."""

    def test_say_tokens(self):
        """Say tokens are defined."""
        assert TOKEN_MAP.get('"') == 'say'
        assert TOKEN_MAP.get("'") == 'say'

    def test_pose_token(self):
        """Pose token is defined."""
        assert TOKEN_MAP.get(':') == 'pose'

    def test_semipose_token(self):
        """Semipose token is defined."""
        assert TOKEN_MAP.get(';') == 'semipose'

    def test_emit_token(self):
        """Emit token is defined."""
        assert TOKEN_MAP.get('\\') == 'emit'


class TestDirectionAliases:
    """Test that direction aliases are defined."""

    def test_cardinal_directions(self):
        """Cardinal directions are aliased."""
        assert DIRECTION_ALIASES['n'] == 'north'
        assert DIRECTION_ALIASES['s'] == 'south'
        assert DIRECTION_ALIASES['e'] == 'east'
        assert DIRECTION_ALIASES['w'] == 'west'

    def test_vertical_directions(self):
        """Up/down are aliased."""
        assert DIRECTION_ALIASES['u'] == 'up'
        assert DIRECTION_ALIASES['d'] == 'down'

    def test_diagonal_directions(self):
        """Diagonal directions are aliased."""
        assert DIRECTION_ALIASES['ne'] == 'northeast'
        assert DIRECTION_ALIASES['nw'] == 'northwest'
        assert DIRECTION_ALIASES['se'] == 'southeast'
        assert DIRECTION_ALIASES['sw'] == 'southwest'
