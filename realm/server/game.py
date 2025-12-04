"""
Game server for REALM.

Orchestrates all components:
- Gateway layer (telnet, websocket)
- Session management
- Command dispatching
- Event bus
- Persistence
"""

from __future__ import annotations

import asyncio
import logging
import signal
from pathlib import Path
from typing import Any, Callable, Awaitable

from realm.core.events import EventBus, Event, EventType
from realm.core.objects import GameObject
from realm.gateway.session import Session, SessionManager
from realm.gateway.telnet import TelnetServer
from realm.persistence.manager import PersistenceManager
from realm.server.dispatcher import CommandDispatcher, CommandContext

logger = logging.getLogger(__name__)


class GameServer:
    """
    Main game server that coordinates all components.

    Usage:
        server = GameServer(db_path="game.db")
        await server.start()
        # ... runs until stopped
        await server.stop()
    """

    def __init__(
        self,
        db_path: str | Path = "game.db",
        telnet_port: int = 4000,
        websocket_port: int = 4001,
        telnet_host: str = "0.0.0.0",
        websocket_host: str = "0.0.0.0",
        enable_telnet: bool = True,
        enable_websocket: bool = False,  # Requires aiohttp
        flush_interval: float = 30.0,
    ):
        self.db_path = Path(db_path)
        self.telnet_port = telnet_port
        self.websocket_port = websocket_port
        self.telnet_host = telnet_host
        self.websocket_host = websocket_host
        self.enable_telnet = enable_telnet
        self.enable_websocket = enable_websocket
        self.flush_interval = flush_interval

        # Core components
        self.session_manager = SessionManager()
        self.event_bus = EventBus()
        self.dispatcher = CommandDispatcher()
        self.persistence: PersistenceManager | None = None

        # Protocol servers
        self._telnet_server: TelnetServer | None = None
        self._websocket_server: Any = None  # WebSocketServer if enabled

        # State
        self._running = False
        self._startup_room: GameObject | None = None

        # Callbacks
        self._on_start: list[Callable[[], Awaitable[None]]] = []
        self._on_stop: list[Callable[[], Awaitable[None]]] = []

    def on_start(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Register a callback to run after server starts."""
        self._on_start.append(callback)

    def on_stop(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Register a callback to run before server stops."""
        self._on_stop.append(callback)

    async def start(self) -> None:
        """Start the game server."""
        logger.info("Starting REALM game server...")

        # Initialize persistence
        self.persistence = PersistenceManager(
            self.db_path,
            flush_interval=self.flush_interval,
        )
        await self.persistence.initialize()
        await self.persistence.start_flush_loop()

        # Load world
        await self._load_world()

        # Set up session callbacks
        self.session_manager.on_connect(self._on_session_connect)
        self.session_manager.on_disconnect(self._on_session_disconnect)

        # Set up dispatcher handlers
        self.dispatcher.set_login_handler(self._handle_login)
        self.dispatcher.set_unknown_handler(self._handle_unknown)
        self.dispatcher._persistence = self.persistence  # For room lookups
        self._register_builtin_commands()

        # Start protocol servers
        if self.enable_telnet:
            self._telnet_server = TelnetServer(
                self.session_manager,
                self._on_command,
                host=self.telnet_host,
                port=self.telnet_port,
            )
            await self._telnet_server.start()

        if self.enable_websocket:
            try:
                from realm.gateway.websocket import WebSocketServer
                self._websocket_server = WebSocketServer(
                    self.session_manager,
                    self._on_command,
                    host=self.websocket_host,
                    port=self.websocket_port,
                )
                await self._websocket_server.start()
            except Exception as e:
                logger.warning(f"Could not start WebSocket server: {e}")

        self._running = True

        # Run startup callbacks
        for callback in self._on_start:
            try:
                await callback()
            except Exception as e:
                logger.error(f"Error in startup callback: {e}")

        logger.info("REALM game server started")

    async def stop(self) -> None:
        """Stop the game server."""
        logger.info("Stopping REALM game server...")

        self._running = False

        # Run stop callbacks
        for callback in self._on_stop:
            try:
                await callback()
            except Exception as e:
                logger.error(f"Error in stop callback: {e}")

        # Stop protocol servers
        if self._telnet_server:
            await self._telnet_server.stop()

        if self._websocket_server:
            await self._websocket_server.stop()

        # Disconnect all sessions
        for session in self.session_manager.all_sessions():
            await session.send("Server shutting down. Goodbye!")
            await self.session_manager.destroy_session(session)

        # Save and close persistence
        if self.persistence:
            await self.persistence.close()

        logger.info("REALM game server stopped")

    async def run_forever(self) -> None:
        """Run the server until interrupted."""
        await self.start()

        # Set up signal handlers
        loop = asyncio.get_event_loop()

        def handle_signal():
            logger.info("Received shutdown signal")
            asyncio.create_task(self.stop())

        try:
            loop.add_signal_handler(signal.SIGINT, handle_signal)
            loop.add_signal_handler(signal.SIGTERM, handle_signal)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

        # Wait until stopped
        while self._running:
            await asyncio.sleep(1)

    async def _load_world(self) -> None:
        """Load the game world from persistence."""
        if not self.persistence:
            return

        objects = await self.persistence.load_all()
        logger.info(f"Loaded {len(objects)} objects from database")

        # Find or create startup room
        for obj in objects:
            if obj.has_tag('start_room'):
                self._startup_room = obj
                break

        if not self._startup_room:
            # Create a default startup room
            self._startup_room = GameObject(
                name="The Void",
                description="You are floating in an empty void. This is the default starting location.",
                tags=['room', 'start_room'],
            )
            await self.persistence.save(self._startup_room)
            logger.info("Created default startup room")

    async def _on_session_connect(self, session: Session) -> None:
        """Called when a new session connects."""
        await session.send("\n")
        await session.send("=" * 60)
        await session.send("  Welcome to REALM")
        await session.send("  Real-time Event-Action Layered MUD")
        await session.send("=" * 60)
        await session.send("\n")
        await session.send("Enter 'connect <name> <password>' to log in")
        await session.send("Enter 'create <name> <password>' to create a new character")
        await session.send("")

    async def _on_session_disconnect(self, session: Session) -> None:
        """Called when a session disconnects."""
        if session.player:
            # Emit disconnect event
            event = Event(
                type=EventType.DISCONNECT,
                source=session.player,
                location=session.player.location,
            )
            await self.event_bus.emit(event)

            # Save player state
            if self.persistence:
                await self.persistence.save(session.player)

    async def _on_command(self, session: Session, command: str) -> None:
        """Called when a command is received from a session."""
        await self.dispatcher.dispatch(session, command)

        # Flush output to client
        await session.flush_output()

    async def _handle_login(self, ctx: CommandContext) -> None:
        """Handle commands when not logged in."""
        args = ctx.args.split()

        if not args:
            return

        cmd = args[0].lower()

        if cmd == 'connect' and len(args) >= 3:
            name = args[1]
            password = args[2]
            await self._do_connect(ctx.session, name, password)

        elif cmd == 'create' and len(args) >= 3:
            name = args[1]
            password = args[2]
            await self._do_create(ctx.session, name, password)

        elif cmd == 'quit':
            await ctx.session.send("Goodbye!")
            await self.session_manager.destroy_session(ctx.session)

        elif cmd == 'who':
            await self._do_who(ctx.session)

        else:
            await ctx.session.send(
                "Commands: connect <name> <password>, create <name> <password>, who, quit"
            )

    async def _do_connect(self, session: Session, name: str, password: str) -> None:
        """Handle the connect command."""
        if not self.persistence:
            await session.send("Server not ready.")
            return

        # TODO: Proper password verification
        # For now, just find the player by name

        # Search for existing player
        player = None
        for obj in self.persistence._object_cache.values():
            if obj.has_tag('player') and obj.name.lower() == name.lower():
                player = obj
                break

        if not player:
            await session.send(f"Character '{name}' not found. Use 'create' to make one.")
            return

        # Check password (stored in attribute for now - should use proper hashing)
        stored_password = player.db.get('password', '')
        if stored_password != password:
            await session.send("Invalid password.")
            return

        # Link player to session
        self.session_manager.link_player_to_session(session, player)

        # Emit connect event
        event = Event(
            type=EventType.CONNECT,
            source=player,
            location=player.location,
        )
        await self.event_bus.emit(event)

        await session.send(f"\nWelcome back, {player.name}!\n")

        # Show room
        await self._show_room(session, player)

    async def _do_create(self, session: Session, name: str, password: str) -> None:
        """Handle the create command."""
        if not self.persistence:
            await session.send("Server not ready.")
            return

        # Check if name is taken
        for obj in self.persistence._object_cache.values():
            if obj.has_tag('player') and obj.name.lower() == name.lower():
                await session.send(f"Character '{name}' already exists.")
                return

        # Create new player
        player = GameObject(
            name=name,
            description=f"This is {name}.",
            location=self._startup_room,
            tags=['player'],
        )
        player.db.password = password  # TODO: Hash this!

        await self.persistence.save(player)

        # Link player to session
        self.session_manager.link_player_to_session(session, player)

        # Emit connect event
        event = Event(
            type=EventType.CONNECT,
            source=player,
            location=player.location,
        )
        await self.event_bus.emit(event)

        await session.send(f"\nCharacter '{name}' created. Welcome to REALM!\n")

        # Show room
        await self._show_room(session, player)

    async def _do_who(self, session: Session) -> None:
        """Show who is online."""
        playing = self.session_manager.playing_sessions()
        await session.send(f"\n{len(playing)} player(s) online:")
        for s in playing:
            if s.player:
                idle = int(s.idle_time)
                await session.send(f"  {s.player.name} (idle {idle}s)")
        await session.send("")

    async def _show_room(self, session: Session, player: GameObject) -> None:
        """Show the current room to a player."""
        room = player.location
        if not room:
            await session.send("You are nowhere.")
            return

        await session.send(f"\n{room.name}")
        await session.send("-" * len(room.name))
        await session.send(room.description)

        # Show contents
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

    async def _handle_unknown(self, ctx: CommandContext) -> None:
        """Handle unknown commands (softcode fallback)."""
        # TODO: Search for $-commands on nearby objects
        await ctx.session.send(f"Huh? (Type 'help' for commands)")

    def _register_builtin_commands(self) -> None:
        """Register built-in commands."""

        async def cmd_look(ctx: CommandContext) -> None:
            if ctx.player:
                session = self.session_manager.get_session_by_player(ctx.player)
                if session:
                    await self._show_room(session, ctx.player)

        self.dispatcher.register("look", cmd_look, aliases=["l"])

        async def cmd_say(ctx: CommandContext) -> None:
            if not ctx.player or not ctx.args:
                return
            message = ctx.args
            await ctx.session.send(f'You say, "{message}"')

            # Notify others in room
            if ctx.player.location:
                event = Event(
                    type=EventType.SPEECH,
                    source=ctx.player,
                    location=ctx.player.location,
                    data={'message': message},
                    source_msg=f'You say, "{message}"',
                    others_msg=f'{ctx.player.name} says, "{message}"',
                )
                await self.event_bus.emit(event)

        self.dispatcher.register("say", cmd_say, aliases=["'"])

        async def cmd_pose(ctx: CommandContext) -> None:
            if not ctx.player or not ctx.args:
                return
            action = ctx.args
            await ctx.session.send(f"{ctx.player.name} {action}")

            if ctx.player.location:
                event = Event(
                    type=EventType.EMOTE,
                    source=ctx.player,
                    location=ctx.player.location,
                    data={'action': action},
                    others_msg=f"{ctx.player.name} {action}",
                )
                await self.event_bus.emit(event)

        self.dispatcher.register("pose", cmd_pose, aliases=[":"])

        async def cmd_who(ctx: CommandContext) -> None:
            await self._do_who(ctx.session)

        self.dispatcher.register("who", cmd_who)

        async def cmd_quit(ctx: CommandContext) -> None:
            await ctx.session.send("Goodbye!")
            await self.session_manager.destroy_session(ctx.session)

        self.dispatcher.register("quit", cmd_quit, aliases=["QUIT"])

        async def cmd_help(ctx: CommandContext) -> None:
            commands = self.dispatcher.list_commands()
            await ctx.session.send("\nAvailable commands:")
            await ctx.session.send(", ".join(commands))
            await ctx.session.send("")

        self.dispatcher.register("help", cmd_help, aliases=["?"])

        async def cmd_inventory(ctx: CommandContext) -> None:
            if not ctx.player:
                return
            items = [obj for obj in ctx.player.contents if obj.has_tag('thing')]
            if items:
                await ctx.session.send("\nYou are carrying:")
                for item in items:
                    await ctx.session.send(f"  {item.name}")
            else:
                await ctx.session.send("You aren't carrying anything.")
            await ctx.session.send("")

        self.dispatcher.register("inventory", cmd_inventory, aliases=["i", "inv"])

    @property
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self._running
