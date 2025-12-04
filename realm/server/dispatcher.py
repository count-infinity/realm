"""
Command dispatcher for REALM.

Routes commands from sessions to appropriate handlers.
Implements the command parsing pipeline from the plan.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Awaitable

if TYPE_CHECKING:
    from realm.gateway.session import Session
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)


@dataclass
class CommandContext:
    """
    Context passed to command handlers.

    Contains all information about the command invocation.
    """

    session: Session
    player: GameObject | None
    raw_input: str
    command_name: str
    args: str
    switches: list[str] = field(default_factory=list)
    left_args: str = ""
    right_args: str = ""

    @property
    def has_player(self) -> bool:
        """Check if a player is linked to this command."""
        return self.player is not None


# Type for command handlers
CommandHandler = Callable[[CommandContext], Awaitable[None]]


@dataclass
class Command:
    """
    Represents a registered command.

    Attributes:
        name: Primary command name
        handler: Async function to execute
        aliases: Alternative names
        help_text: Short description
        usage: Usage syntax
        min_args: Minimum required arguments
        permission: Required permission level
        parse_equals: Whether to split args at '='
    """

    name: str
    handler: CommandHandler
    aliases: list[str] = field(default_factory=list)
    help_text: str = ""
    usage: str = ""
    min_args: int = 0
    permission: str = "player"  # player, builder, admin, god
    parse_equals: bool = False


# Special token mappings
TOKEN_MAP = {
    '"': 'say',
    ':': 'pose',
    ';': 'semipose',
    '\\': 'emit',
    "'": 'say',  # Alternative for say
}

# Direction aliases
DIRECTION_ALIASES = {
    'n': 'north',
    's': 'south',
    'e': 'east',
    'w': 'west',
    'u': 'up',
    'd': 'down',
    'ne': 'northeast',
    'nw': 'northwest',
    'se': 'southeast',
    'sw': 'southwest',
    'in': 'in',
    'out': 'out',
}


class CommandDispatcher:
    """
    Dispatches commands to registered handlers.

    Implements the parsing pipeline:
    1. Trim input
    2. Check for special tokens (", :, etc.)
    3. Expand aliases
    4. Match exit names (if playing)
    5. Look up command
    6. Parse switches
    7. Parse arguments
    8. Execute
    9. Fall back to softcode (future)
    """

    def __init__(self):
        self._commands: dict[str, Command] = {}
        self._aliases: dict[str, str] = {}  # alias -> command name
        self._player_aliases: dict[str, dict[str, str]] = {}  # player_id -> {alias: expansion}

        # Handler for unknown commands (for softcode fallback)
        self._unknown_handler: CommandHandler | None = None

        # Handler for login state
        self._login_handler: CommandHandler | None = None

    def register(
        self,
        name: str,
        handler: CommandHandler,
        *,
        aliases: list[str] | None = None,
        help_text: str = "",
        usage: str = "",
        min_args: int = 0,
        permission: str = "player",
        parse_equals: bool = False,
    ) -> None:
        """Register a command handler."""
        cmd = Command(
            name=name.lower(),
            handler=handler,
            aliases=[a.lower() for a in (aliases or [])],
            help_text=help_text,
            usage=usage,
            min_args=min_args,
            permission=permission,
            parse_equals=parse_equals,
        )
        self._commands[cmd.name] = cmd

        # Register aliases
        for alias in cmd.aliases:
            self._aliases[alias] = cmd.name

    def unregister(self, name: str) -> None:
        """Unregister a command."""
        name = name.lower()
        if name in self._commands:
            cmd = self._commands.pop(name)
            for alias in cmd.aliases:
                self._aliases.pop(alias, None)

    def set_unknown_handler(self, handler: CommandHandler) -> None:
        """Set handler for unknown commands (softcode fallback)."""
        self._unknown_handler = handler

    def set_login_handler(self, handler: CommandHandler) -> None:
        """Set handler for commands when not logged in."""
        self._login_handler = handler

    def set_player_alias(self, player_id: str, alias: str, expansion: str) -> None:
        """Set a player-specific alias."""
        if player_id not in self._player_aliases:
            self._player_aliases[player_id] = {}
        self._player_aliases[player_id][alias.lower()] = expansion

    def remove_player_alias(self, player_id: str, alias: str) -> None:
        """Remove a player-specific alias."""
        if player_id in self._player_aliases:
            self._player_aliases[player_id].pop(alias.lower(), None)

    async def dispatch(self, session: Session, raw_input: str) -> None:
        """
        Dispatch a command from a session.

        This is the main entry point for command processing.
        """
        raw_input = raw_input.strip()
        if not raw_input:
            return

        player = session.player

        # If not logged in, route to login handler
        if player is None:
            if self._login_handler:
                ctx = CommandContext(
                    session=session,
                    player=None,
                    raw_input=raw_input,
                    command_name="",
                    args=raw_input,
                )
                await self._login_handler(ctx)
            else:
                await session.send("You must log in first.")
            return

        # Parse the command
        ctx = self._parse_command(session, player, raw_input)

        # Try to find and execute the command
        await self._execute(ctx)

    def _parse_command(
        self,
        session: Session,
        player: GameObject,
        raw_input: str,
    ) -> CommandContext:
        """Parse raw input into a CommandContext."""
        original = raw_input
        command_name = ""
        args = ""
        switches: list[str] = []

        # Step 1: Check for special tokens
        if raw_input and raw_input[0] in TOKEN_MAP:
            command_name = TOKEN_MAP[raw_input[0]]
            args = raw_input[1:].lstrip()
            return CommandContext(
                session=session,
                player=player,
                raw_input=original,
                command_name=command_name,
                args=args,
            )

        # Step 2: Check for channel prefix (+)
        if raw_input.startswith('+'):
            # +channel message -> channel channel=message
            parts = raw_input[1:].split(None, 1)
            if parts:
                command_name = "channel"
                channel = parts[0]
                message = parts[1] if len(parts) > 1 else ""
                args = f"{channel}={message}"
                return CommandContext(
                    session=session,
                    player=player,
                    raw_input=original,
                    command_name=command_name,
                    args=args,
                    left_args=channel,
                    right_args=message,
                )

        # Step 3: Split into command and arguments
        parts = raw_input.split(None, 1)
        raw_command = parts[0] if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        # Step 4: Check for player aliases
        if player:
            player_aliases = self._player_aliases.get(player.id, {})
            if raw_command.lower() in player_aliases:
                # Expand alias and re-parse
                expansion = player_aliases[raw_command.lower()]
                if args:
                    expansion = f"{expansion} {args}"
                return self._parse_command(session, player, expansion)

        # Step 5: Parse switches from command (e.g., @command/switch1/switch2)
        if '/' in raw_command:
            switch_parts = raw_command.split('/')
            raw_command = switch_parts[0]
            switches = [s.lower() for s in switch_parts[1:] if s]

        command_name = raw_command.lower()

        # Step 6: Check for direction aliases
        if command_name in DIRECTION_ALIASES:
            command_name = DIRECTION_ALIASES[command_name]

        # Step 7: Parse left/right arguments if '=' present
        left_args = args
        right_args = ""
        if '=' in args:
            eq_pos = args.index('=')
            left_args = args[:eq_pos].strip()
            right_args = args[eq_pos + 1:].strip()

        return CommandContext(
            session=session,
            player=player,
            raw_input=original,
            command_name=command_name,
            args=args,
            switches=switches,
            left_args=left_args,
            right_args=right_args,
        )

    async def _execute(self, ctx: CommandContext) -> None:
        """Execute a parsed command."""
        name = ctx.command_name

        # Direct match
        if name in self._commands:
            await self._run_command(self._commands[name], ctx)
            return

        # Alias match
        if name in self._aliases:
            cmd_name = self._aliases[name]
            if cmd_name in self._commands:
                await self._run_command(self._commands[cmd_name], ctx)
                return

        # Prefix match (unique prefix only)
        matches = self._find_prefix_matches(name)
        if len(matches) == 1:
            await self._run_command(self._commands[matches[0]], ctx)
            return
        elif len(matches) > 1:
            await ctx.session.send(
                f"Ambiguous command '{name}'. Matches: {', '.join(sorted(matches))}"
            )
            return

        # Try exit matching (if player has location)
        if ctx.player and ctx.player.location:
            exit_obj = self._find_exit(ctx.player.location, name)
            if exit_obj:
                # Execute movement through the exit
                await self._handle_exit(ctx, exit_obj)
                return

        # Fall back to unknown handler (softcode)
        if self._unknown_handler:
            await self._unknown_handler(ctx)
        else:
            await ctx.session.send(f"Unknown command: {name}")

    def _find_prefix_matches(self, prefix: str) -> list[str]:
        """Find all commands matching a prefix."""
        matches = []
        for name in self._commands:
            if name.startswith(prefix):
                matches.append(name)
        for alias, cmd_name in self._aliases.items():
            if alias.startswith(prefix) and cmd_name not in matches:
                matches.append(cmd_name)
        return matches

    def _find_exit(self, room: GameObject, name: str) -> GameObject | None:
        """Find an exit in a room by name."""
        name_lower = name.lower()
        for obj in room.contents:
            if obj.has_tag('exit'):
                if obj.name.lower() == name_lower:
                    return obj
                # Check aliases stored on exit
                aliases = obj.db.get('aliases', [])
                if name_lower in [a.lower() for a in aliases]:
                    return obj
        return None

    async def _handle_exit(self, ctx: CommandContext, exit_obj: GameObject) -> None:
        """Handle movement through an exit."""
        if not ctx.player:
            return

        # Get destination ID (stored as string room ID)
        dest_id = exit_obj.db.get('destination')
        if not dest_id:
            await ctx.session.send("That exit doesn't lead anywhere.")
            return

        # Find destination room by ID
        destination = self._find_room_by_id(ctx, dest_id)

        if not destination:
            await ctx.session.send("That exit leads nowhere you can reach.")
            return

        # TODO: Check locks on exit

        # Move the player
        ctx.player.location = destination

        # Notify player
        await ctx.session.send(f"\nYou go {exit_obj.name}.")

        # Show new room
        await self._show_room_to_session(ctx.session, ctx.player)

    def _find_room_by_id(self, ctx: CommandContext, room_id: str) -> GameObject | None:
        """Find a room by its ID."""
        # Check if it's already an object reference
        if hasattr(room_id, 'id'):
            return room_id

        # Search persistence cache if available
        if hasattr(self, '_persistence') and self._persistence:
            return self._persistence._object_cache.get(room_id)

        # Search player's location contents (won't work for other rooms)
        if ctx.player and ctx.player.location:
            for obj in ctx.player.location.contents:
                if obj.id == room_id:
                    return obj

        return None

    async def _show_room_to_session(self, session: Session, player: GameObject) -> None:
        """Display a room to a session."""
        room = player.location
        if not room:
            await session.send("You are nowhere.")
            return

        await session.send(f"\n{room.name}")
        await session.send("-" * len(room.name))

        # Description from db.description or .description
        desc = room.db.get('description') or room.description
        if desc:
            await session.send(desc)

        # Show contents (excluding player and exits)
        others = [
            obj for obj in room.contents
            if obj != player and not obj.has_tag('exit')
        ]
        if others:
            await session.send("\nYou see:")
            for obj in others:
                await session.send(f"  {obj.name}")

        # Show exits
        exits = [obj for obj in room.contents if obj.has_tag('exit')]
        if exits:
            exit_names = ", ".join(e.name for e in exits)
            await session.send(f"\nExits: {exit_names}")

        await session.send("")

    async def _run_command(self, cmd: Command, ctx: CommandContext) -> None:
        """Run a command after finding it."""
        # Permission check
        if not self._check_permission(ctx.player, cmd.permission):
            await ctx.session.send("Permission denied.")
            return

        # TODO: Argument validation

        try:
            await cmd.handler(ctx)
        except Exception as e:
            logger.exception(f"Error executing command {cmd.name}: {e}")
            await ctx.session.send(f"An error occurred: {e}")

    def _check_permission(self, player: GameObject | None, permission: str) -> bool:
        """Check if a player has the required permission level."""
        from realm.permissions.roles import has_permission
        return has_permission(player, permission)

    def get_command(self, name: str) -> Command | None:
        """Get a command by name or alias."""
        name = name.lower()
        if name in self._commands:
            return self._commands[name]
        if name in self._aliases:
            return self._commands.get(self._aliases[name])
        return None

    def list_commands(self, player: GameObject | None = None) -> list[str]:
        """
        List all available commands for a player.

        Args:
            player: The player object (or None for guest-level)

        Returns:
            Sorted list of command names the player can use
        """
        result = []
        for name, cmd in self._commands.items():
            if self._check_permission(player, cmd.permission):
                result.append(name)

        return sorted(result)


def command(
    name: str,
    *,
    aliases: list[str] | None = None,
    help_text: str = "",
    usage: str = "",
    min_args: int = 0,
    permission: str = "player",
    parse_equals: bool = False,
):
    """
    Decorator for registering commands.

    Usage:
        @command("look", aliases=["l"], help_text="Look around")
        async def cmd_look(ctx: CommandContext):
            ...
    """
    def decorator(func: CommandHandler) -> CommandHandler:
        # Store metadata on the function for later registration
        func._command_meta = {  # type: ignore
            'name': name,
            'aliases': aliases or [],
            'help_text': help_text,
            'usage': usage,
            'min_args': min_args,
            'permission': permission,
            'parse_equals': parse_equals,
        }
        return func
    return decorator


def register_commands(dispatcher: CommandDispatcher, *handlers: CommandHandler) -> None:
    """
    Register multiple command handlers with a dispatcher.

    Usage:
        register_commands(dispatcher, cmd_look, cmd_say, cmd_quit)
    """
    for handler in handlers:
        if hasattr(handler, '_command_meta'):
            meta = handler._command_meta  # type: ignore
            dispatcher.register(
                meta['name'],
                handler,
                aliases=meta['aliases'],
                help_text=meta['help_text'],
                usage=meta['usage'],
                min_args=meta['min_args'],
                permission=meta['permission'],
                parse_equals=meta['parse_equals'],
            )
