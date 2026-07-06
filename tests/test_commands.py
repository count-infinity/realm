"""Tests for the command system."""

import pytest

from realm.commands import CommandContext, CommandDispatcher
from realm.commands.base import find_exit, find_object, format_list
from realm.commands.builtin import register_all_commands
from realm.core.objects import GameObject
from realm.gateway.session import Session


class TestCommandBase:
    """Test suite for command base utilities."""

    def test_format_list_empty(self):
        """format_list handles empty list."""
        assert format_list([]) == ""

    def test_format_list_single(self):
        """format_list handles single item."""
        assert format_list(["apple"]) == "apple"

    def test_format_list_two(self):
        """format_list handles two items."""
        assert format_list(["apple", "banana"]) == "apple and banana"

    def test_format_list_three(self):
        """format_list handles three+ items."""
        result = format_list(["apple", "banana", "cherry"])
        assert result == "apple, banana, and cherry"

    def test_format_list_custom_conjunction(self):
        """format_list supports custom conjunction."""
        result = format_list(["apple", "banana"], conjunction="or")
        assert result == "apple or banana"


class TestFindObject:
    """Test suite for find_object utility."""

    def setup_method(self):
        """Set up test environment."""
        self.room = GameObject("Test Room", tags=['room'])
        self.player = GameObject("Player", tags=['player'], location=self.room)
        self.sword = GameObject("sword", tags=['thing'], location=self.room)
        self.shield = GameObject("shield", tags=['thing'], location=self.player)

        self.session = Session()
        self.session.link_player(self.player)

        self.ctx = CommandContext(
            session=self.session,
            player=self.player,
            raw_input="",
            command_name="",
            args="",
        )

    def test_find_in_room(self):
        """find_object finds objects in room."""
        result = find_object(self.ctx, "sword", search_room=True)
        assert result == self.sword

    def test_find_in_inventory(self):
        """find_object finds objects in inventory."""
        result = find_object(self.ctx, "shield", search_inventory=True)
        assert result == self.shield

    def test_find_not_found(self):
        """find_object returns None when not found."""
        result = find_object(self.ctx, "nonexistent")
        assert result is None

    def test_find_case_insensitive(self):
        """find_object is case insensitive."""
        result = find_object(self.ctx, "SWORD")
        assert result == self.sword

    def test_find_by_alias(self):
        """find_object finds by alias."""
        self.sword.db.aliases = ["blade", "weapon"]
        result = find_object(self.ctx, "blade")
        assert result == self.sword


class TestFindExit:
    """Test suite for find_exit utility."""

    def setup_method(self):
        """Set up test environment."""
        self.room = GameObject("Test Room", tags=['room'])
        self.player = GameObject("Player", tags=['player'], location=self.room)
        self.north_exit = GameObject("north", tags=['exit'], location=self.room)

        self.session = Session()
        self.session.link_player(self.player)

        self.ctx = CommandContext(
            session=self.session,
            player=self.player,
            raw_input="",
            command_name="",
            args="",
        )

    def test_find_exit_by_name(self):
        """find_exit finds exit by name."""
        result = find_exit(self.ctx, "north")
        assert result == self.north_exit

    def test_find_exit_by_alias(self):
        """find_exit finds exit by alias."""
        self.north_exit.db.aliases = ["n"]
        result = find_exit(self.ctx, "n")
        assert result == self.north_exit

    def test_find_exit_not_found(self):
        """find_exit returns None when not found."""
        result = find_exit(self.ctx, "south")
        assert result is None


class TestBuiltinCommands:
    """Test suite for built-in commands."""

    def setup_method(self):
        """Set up test environment."""
        self.dispatcher = CommandDispatcher()
        register_all_commands(self.dispatcher)

        self.room = GameObject("Test Room", tags=['room'])
        self.room.description = "A test room."

        self.player = GameObject("TestPlayer", tags=['player'], location=self.room)

        self.session = Session()
        self.session.link_player(self.player)

    @pytest.mark.asyncio
    async def test_say_command(self):
        """say command sends message to room."""
        await self.dispatcher.dispatch(self.session, "say Hello everyone!")

        # Check output was sent
        msg = self.session._output_queue.get_nowait()
        assert 'You say, "Hello everyone!"' in msg

    @pytest.mark.asyncio
    async def test_say_shortcut(self):
        """" shortcut works for say."""
        await self.dispatcher.dispatch(self.session, '"Hello!')

        msg = self.session._output_queue.get_nowait()
        assert 'You say, "Hello!"' in msg

    @pytest.mark.asyncio
    async def test_pose_command(self):
        """pose command emotes action."""
        await self.dispatcher.dispatch(self.session, "pose waves hello.")

        msg = self.session._output_queue.get_nowait()
        assert "TestPlayer waves hello." in msg

    @pytest.mark.asyncio
    async def test_pose_shortcut(self):
        """: shortcut works for pose."""
        await self.dispatcher.dispatch(self.session, ":waves")

        msg = self.session._output_queue.get_nowait()
        assert "TestPlayer waves" in msg

    @pytest.mark.asyncio
    async def test_look_command(self):
        """look command shows room."""
        await self.dispatcher.dispatch(self.session, "look")

        # Collect output
        output = []
        while not self.session._output_queue.empty():
            output.append(self.session._output_queue.get_nowait())

        full_output = "\n".join(output)
        assert "Test Room" in full_output

    @pytest.mark.asyncio
    async def test_look_at_self(self):
        """look at self works."""
        self.player.description = "A brave adventurer."
        await self.dispatcher.dispatch(self.session, "look me")

        output = []
        while not self.session._output_queue.empty():
            output.append(self.session._output_queue.get_nowait())

        full_output = "\n".join(output)
        assert "TestPlayer" in full_output

    @pytest.mark.asyncio
    async def test_inventory_empty(self):
        """inventory shows empty message."""
        await self.dispatcher.dispatch(self.session, "inventory")

        msg = self.session._output_queue.get_nowait()
        assert "aren't carrying" in msg

    @pytest.mark.asyncio
    async def test_inventory_with_items(self):
        """inventory shows items."""
        sword = GameObject("sword", tags=['thing'], location=self.player)

        await self.dispatcher.dispatch(self.session, "i")

        output = []
        while not self.session._output_queue.empty():
            output.append(self.session._output_queue.get_nowait())

        full_output = "\n".join(output)
        assert "sword" in full_output

    @pytest.mark.asyncio
    async def test_get_command(self):
        """get command picks up items."""
        sword = GameObject("sword", tags=['thing'], location=self.room)

        await self.dispatcher.dispatch(self.session, "get sword")

        # Check item moved
        assert sword.location == self.player

        # Check message
        msg = self.session._output_queue.get_nowait()
        assert "pick up" in msg.lower()

    @pytest.mark.asyncio
    async def test_drop_command(self):
        """drop command drops items."""
        sword = GameObject("sword", tags=['thing'], location=self.player)

        await self.dispatcher.dispatch(self.session, "drop sword")

        # Check item moved
        assert sword.location == self.room

        # Check message
        msg = self.session._output_queue.get_nowait()
        assert "drop" in msg.lower()

    @pytest.mark.asyncio
    async def test_give_command(self):
        """give command gives items."""
        other = GameObject("OtherPlayer", tags=['player'], location=self.room)
        sword = GameObject("sword", tags=['thing'], location=self.player)

        await self.dispatcher.dispatch(self.session, "give sword to OtherPlayer")

        # Check item moved
        assert sword.location == other

    @pytest.mark.asyncio
    async def test_examine_command(self):
        """examine command shows details."""
        sword = GameObject("sword", tags=['thing'], location=self.room)
        sword.description = "A sharp blade."
        sword.db.damage = 10

        await self.dispatcher.dispatch(self.session, "examine sword")

        output = []
        while not self.session._output_queue.empty():
            output.append(self.session._output_queue.get_nowait())

        full_output = "\n".join(output)
        assert "sword" in full_output
        assert "sharp blade" in full_output

    @pytest.mark.asyncio
    async def test_whisper_command(self):
        """whisper command sends private message."""
        other = GameObject("OtherPlayer", tags=['player'], location=self.room)

        await self.dispatcher.dispatch(self.session, "whisper OtherPlayer = secret")

        msg = self.session._output_queue.get_nowait()
        assert "whisper to OtherPlayer" in msg

    @pytest.mark.asyncio
    async def test_ooc_command(self):
        """ooc command sends OOC message."""
        await self.dispatcher.dispatch(self.session, "ooc testing")

        msg = self.session._output_queue.get_nowait()
        assert "[OOC]" in msg
        assert "testing" in msg

    @pytest.mark.asyncio
    async def test_help_command(self):
        """help command shows help."""
        await self.dispatcher.dispatch(self.session, "help")

        output = []
        while not self.session._output_queue.empty():
            output.append(self.session._output_queue.get_nowait())

        full_output = "\n".join(output)
        assert "Available Commands" in full_output

    @pytest.mark.asyncio
    async def test_help_specific_command(self):
        """help shows specific command info."""
        await self.dispatcher.dispatch(self.session, "help look")

        output = []
        while not self.session._output_queue.empty():
            output.append(self.session._output_queue.get_nowait())

        full_output = "\n".join(output)
        assert "look" in full_output

    @pytest.mark.asyncio
    async def test_think_command(self):
        """think command shows thought."""
        await self.dispatcher.dispatch(self.session, "think deep thoughts")

        msg = self.session._output_queue.get_nowait()
        assert "You think:" in msg
        assert "deep thoughts" in msg


class TestCommandRegistration:
    """Test that all commands are properly registered."""

    def test_all_commands_registered(self):
        """All expected commands are registered."""
        dispatcher = CommandDispatcher()
        register_all_commands(dispatcher)

        expected = [
            # Movement
            'go', 'north', 'south', 'east', 'west', 'up', 'down',
            # Communication
            'say', 'pose', 'whisper', 'ooc', 'shout',
            # Look
            'look', 'examine',
            # Inventory
            'inventory', 'get', 'drop', 'give', 'put',
            # Utility
            'who', 'quit', 'help', 'think',
        ]

        for cmd in expected:
            assert dispatcher.get_command(cmd) is not None, f"Command {cmd} not registered"

    def test_aliases_registered(self):
        """Command aliases are registered."""
        dispatcher = CommandDispatcher()
        register_all_commands(dispatcher)

        # Check some aliases
        assert dispatcher.get_command("l") is not None  # look
        assert dispatcher.get_command("i") is not None  # inventory
        assert dispatcher.get_command("?") is not None  # help
