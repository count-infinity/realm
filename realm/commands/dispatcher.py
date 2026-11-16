"""
Command dispatcher for REALM.

Routes commands from sessions to appropriate handlers.
Implements the command parsing pipeline from the plan.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.gateway.session import Session, SessionManager
    from realm.persistence.manager import PersistenceManager

logger = logging.getLogger(__name__)


@dataclass
class CommandContext:
    """
    Context passed to command handlers.

    Contains all information about the command invocation, plus the
    dispatcher that built it — handlers reach shared services
    (``ctx.dispatcher.persistence``, ``ctx.dispatcher.session_manager``)
    through it instead of module-level globals.
    """

    session: Session
    player: GameObject | None
    raw_input: str
    command_name: str
    args: str
    switches: list[str] = field(default_factory=list)
    left_args: str = ""
    right_args: str = ""
    dispatcher: CommandDispatcher | None = None

    @property
    def persistence(self) -> PersistenceManager | None:
        """The server's persistence manager, if wired."""
        return self.dispatcher.persistence if self.dispatcher else None

    @property
    def session_manager(self) -> SessionManager | None:
        """The server's session manager, if wired."""
        return self.dispatcher.session_manager if self.dispatcher else None


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
        permission: Required permission level
        parse_equals: Whether to split args at '='
    """

    name: str
    handler: CommandHandler
    aliases: list[str] = field(default_factory=list)
    help_text: str = ""
    usage: str = ""
    permission: str = "player"  # player, builder, admin, god
    parse_equals: bool = False
    category: str = "general"  # help-screen grouping


class CommandDispatcher:
    """
    Dispatches commands to registered handlers.

    Implements the parsing pipeline:
    1. Trim input
    2. A one-character token declared by a command (``:waves`` -> pose)
    3. Split the command word, its ``/switches`` and ``left = right`` args
    4. Look up the command: exact name, alias, unique prefix
    5. Otherwise the fallbacks, in order (``feature.fallback``: the
       ``movement`` feature walks a typed exit name)
    6. Otherwise the unknown handler (softcode ``$``-commands, then "Huh?")

    The dispatcher knows no command, exit or direction by name: every one
    comes from a feature.
    """

    def __init__(self):
        self._commands: dict[str, Command] = {}
        self._aliases: dict[str, str] = {}  # alias -> command name

        # Shared services, wired by GameServer.start(). Commands reach them
        # via ctx.persistence / ctx.session_manager.
        self.persistence: PersistenceManager | None = None
        self.session_manager: SessionManager | None = None
        # monotonic() stamp taken when the server goes live; None until then.
        # `uptime` reads it through ctx.dispatcher.
        self.server_started_at: float | None = None
        # The GameServer running this world (None in a Simulator): @shutdown
        # and @reboot stop it, @stats reads its settings.
        self.server: Any = None
        # Returns the connection/welcome screen text. Wired by GameServer so
        # `logout` can drop a session back to it without reconnecting.
        self.welcome_screen: Callable[[], str] | None = None

        # Handler for unknown commands (for softcode fallback)
        self._unknown_handler: CommandHandler | None = None
        self._tokens: dict[str, str] = {}               # one-char prefix -> command
        self._fallbacks: list[Callable[[CommandContext], Awaitable[bool]]] = []

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
        permission: str = "player",
        parse_equals: bool = False,
        category: str = "general",
        tokens: tuple[str, ...] | list[str] = (),
    ) -> None:
        """Register a command handler. Each of ``tokens`` is a one-character
        prefix that runs it (``:waves``)."""
        cmd = Command(
            name=name.lower(),
            handler=handler,
            aliases=[a.lower() for a in (aliases or [])],
            help_text=help_text,
            usage=usage,
            permission=permission,
            parse_equals=parse_equals,
            category=category,
        )
        self._commands[cmd.name] = cmd

        # Register aliases
        for alias in cmd.aliases:
            self._aliases[alias] = cmd.name
        for token in tokens:
            self._tokens[token] = cmd.name

    def unregister(self, name: str) -> None:
        """Unregister a command."""
        name = name.lower()
        if name in self._commands:
            cmd = self._commands.pop(name)
            for alias in cmd.aliases:
                self._aliases.pop(alias, None)

    def add_fallback(self, fn: Callable[[CommandContext], Awaitable[bool]]) -> None:
        """Try ``fn(ctx) -> bool`` when no command matches, after those
        added before it; True means it handled the line."""
        self._fallbacks.append(fn)

    def set_unknown_handler(self, handler: CommandHandler) -> None:
        """Set handler for unknown commands (softcode fallback)."""
        self._unknown_handler = handler

    def set_login_handler(self, handler: CommandHandler) -> None:
        """Set handler for commands when not logged in."""
        self._login_handler = handler

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
                    dispatcher=self,
                )
                await self._login_handler(ctx)
            else:
                await session.send("This world has no login feature installed.")
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

        # Step 1: a command's one-character token
        if raw_input and raw_input[0] in self._tokens:
            command_name = self._tokens[raw_input[0]]
            args = raw_input[1:].lstrip()
            return CommandContext(
                session=session,
                player=player,
                raw_input=original,
                command_name=command_name,
                args=args,
                dispatcher=self,
            )

        # Step 2: Split into command and arguments
        parts = raw_input.split(None, 1)
        raw_command = parts[0] if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        # Step 3: Parse switches from command (e.g., @command/switch1/switch2)
        if '/' in raw_command:
            switch_parts = raw_command.split('/')
            raw_command = switch_parts[0]
            switches = [s.lower() for s in switch_parts[1:] if s]

        command_name = raw_command.lower()

        # Step 4: Parse left/right arguments if '=' present
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
            dispatcher=self,
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

        # The features' fallbacks (a typed exit name), in order.
        for fallback in self._fallbacks:
            if await fallback(ctx):
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

    async def _run_command(self, cmd: Command, ctx: CommandContext) -> None:
        """Run a command after finding it."""
        # The handler sees the command's own name, whichever alias, prefix
        # or token reached it ('n' runs north with command_name 'north').
        ctx.command_name = cmd.name
        # Permission check
        if not self._check_permission(ctx.player, cmd.permission):
            await ctx.session.send("Permission denied.")
            return

        from realm.core.search import AmbiguousMatchError, format_ambiguous
        try:
            await cmd.handler(ctx)
        except AmbiguousMatchError as e:
            # A name matched several objects equally well — let the player
            # narrow it down. One handler here covers every command.
            await ctx.session.send(format_ambiguous(e, ctx.player))
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


