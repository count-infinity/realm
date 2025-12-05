"""
Game server for REALM.

Orchestrates all components:
- Gateway layer (telnet, websocket, custom protocols)
- Session management
- Command dispatching
- Event bus
- Persistence

The GameServer can be configured either directly with parameters or
via a Settings object from the config loader.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from pathlib import Path
from typing import Any, Callable, Awaitable, TYPE_CHECKING

from realm.core.events import EventBus, Event, EventType
from realm.core.objects import GameObject
from realm.gateway.session import Session, SessionManager
from realm.gateway.telnet import TelnetServer
from realm.persistence.manager import PersistenceManager
from realm.server.dispatcher import CommandDispatcher, CommandContext

if TYPE_CHECKING:
    from realm.config.loader import Settings

logger = logging.getLogger(__name__)


class GameServer:
    """
    Main game server that coordinates all components.

    Usage via direct instantiation:
        server = GameServer(db_path="game.db")
        await server.start()
        # ... runs until stopped
        await server.stop()

    Usage via Settings (recommended):
        from realm.config.loader import load_config
        settings = load_config()
        server = GameServer.from_settings(settings)
        await server.run_forever()
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
        game_name: str = "REALM",
        welcome_file: str | Path | None = None,
    ):
        self.db_path = Path(db_path)
        self.telnet_port = telnet_port
        self.websocket_port = websocket_port
        self.telnet_host = telnet_host
        self.websocket_host = websocket_host
        self.enable_telnet = enable_telnet
        self.enable_websocket = enable_websocket
        self.flush_interval = flush_interval
        self.game_name = game_name
        self.welcome_file = Path(welcome_file) if welcome_file else None

        # Core components
        self.session_manager = SessionManager()
        self.event_bus = EventBus()
        self.dispatcher = CommandDispatcher()
        self.persistence: PersistenceManager | None = None

        # Protocol servers - built-in
        self._telnet_server: TelnetServer | None = None
        self._websocket_server: Any = None  # WebSocketServer if enabled

        # Custom protocol registrations
        # Format: {name: (class, kwargs)}
        self._custom_protocols: dict[str, tuple[type, dict[str, Any]]] = {}

        # Running custom protocol instances
        self._protocol_servers: dict[str, Any] = {}

        # State
        self._running = False
        self._startup_room: GameObject | None = None
        self._settings: Settings | None = None

        # Callbacks
        self._on_start: list[Callable[[], Awaitable[None]]] = []
        self._on_stop: list[Callable[[], Awaitable[None]]] = []

    @classmethod
    def from_settings(cls, settings: Settings) -> GameServer:
        """
        Create a GameServer from a Settings object.

        This is the recommended way to create a server when using
        realm as a library with config.py configuration.

        Args:
            settings: Settings loaded from load_config()

        Returns:
            Configured GameServer instance.
        """
        server = cls(
            db_path=settings.db_path,
            telnet_port=settings.telnet_port,
            telnet_host=settings.telnet_host,
            websocket_port=settings.websocket_port,
            websocket_host=settings.websocket_host,
            enable_telnet=settings.enable_telnet,
            enable_websocket=settings.enable_websocket,
            flush_interval=settings.flush_interval,
            game_name=settings.game_name,
            welcome_file=settings.welcome_file,
        )
        server._settings = settings

        # Register any startup callbacks from config
        if settings.on_start:
            async def config_on_start():
                await settings.on_start(server)
            server.on_start(config_on_start)

        if settings.on_stop:
            async def config_on_stop():
                await settings.on_stop(server)
            server.on_stop(config_on_stop)

        return server

    def register_protocol(
        self,
        name: str,
        protocol_class: type,
        **kwargs: Any,
    ) -> None:
        """
        Register a custom protocol server.

        The protocol class must have:
        - __init__(session_manager, on_command, host, port, **kwargs)
        - async start() -> None
        - async stop() -> None
        - is_serving property -> bool

        Args:
            name: Unique name for this protocol (e.g., "godot", "ssh")
            protocol_class: Protocol server class
            **kwargs: Additional arguments passed to protocol constructor
                      (must include 'port' at minimum)

        Example:
            from mygame.protocols import GodotServer
            server.register_protocol("godot", GodotServer, port=4002)
        """
        if name in self._custom_protocols:
            raise ValueError(f"Protocol '{name}' is already registered")

        if name in ("telnet", "websocket"):
            raise ValueError(
                f"Cannot register '{name}' - use enable_{name}=True instead"
            )

        self._custom_protocols[name] = (protocol_class, kwargs)
        logger.debug(f"Registered custom protocol: {name}")

    def on_start(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Register a callback to run after server starts."""
        self._on_start.append(callback)

    def on_stop(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Register a callback to run before server stops."""
        self._on_stop.append(callback)

    async def start(self) -> None:
        """Start the game server."""
        logger.info(f"Starting {self.game_name} game server...")

        # Initialize persistence
        self.persistence = PersistenceManager(
            self.db_path,
            flush_interval=self.flush_interval,
        )
        await self.persistence.initialize()
        await self.persistence.start_flush_loop()

        # Load world
        await self._load_world()

        # Call init_world callback if defined in settings
        if self._settings and self._settings.init_world:
            try:
                await self._settings.init_world(self)
            except Exception as e:
                logger.error(f"Error in init_world callback: {e}")
                raise

        # Set up session callbacks
        self.session_manager.on_connect(self._on_session_connect)
        self.session_manager.on_disconnect(self._on_session_disconnect)

        # Set up dispatcher handlers
        self.dispatcher.set_login_handler(self._handle_login)
        self.dispatcher.set_unknown_handler(self._handle_unknown)
        self.dispatcher._persistence = self.persistence  # For room lookups
        self._register_builtin_commands()

        # Call register_commands callback if defined in settings
        if self._settings and self._settings.register_commands:
            try:
                self._settings.register_commands(self)
            except Exception as e:
                logger.error(f"Error in register_commands callback: {e}")
                raise

        # Call register_protocols callback if defined in settings
        if self._settings and self._settings.register_protocols:
            try:
                self._settings.register_protocols(self)
            except Exception as e:
                logger.error(f"Error in register_protocols callback: {e}")
                raise

        # Start built-in protocol servers
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

        # Start custom protocol servers
        for name, (protocol_class, kwargs) in self._custom_protocols.items():
            try:
                # Protocol servers receive session_manager and on_command
                server = protocol_class(
                    self.session_manager,
                    self._on_command,
                    **kwargs,
                )
                await server.start()
                self._protocol_servers[name] = server
                logger.info(f"Started custom protocol: {name}")
            except Exception as e:
                logger.error(f"Failed to start protocol '{name}': {e}")
                raise

        self._running = True

        # Run startup callbacks
        for callback in self._on_start:
            try:
                await callback()
            except Exception as e:
                logger.error(f"Error in startup callback: {e}")

        logger.info(f"{self.game_name} game server started")

    async def stop(self) -> None:
        """Stop the game server."""
        logger.info(f"Stopping {self.game_name} game server...")

        self._running = False

        # Run stop callbacks
        for callback in self._on_stop:
            try:
                await callback()
            except Exception as e:
                logger.error(f"Error in stop callback: {e}")

        # Stop custom protocol servers
        for name, server in self._protocol_servers.items():
            try:
                await server.stop()
                logger.debug(f"Stopped custom protocol: {name}")
            except Exception as e:
                logger.error(f"Error stopping protocol '{name}': {e}")

        self._protocol_servers.clear()

        # Stop built-in protocol servers
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

        logger.info(f"{self.game_name} game server stopped")

    async def run_forever(self) -> None:
        """Run the server until interrupted."""
        await self.start()

        # Set up signal handlers
        loop = asyncio.get_running_loop()

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
        welcome_text = self._get_welcome_screen()
        await session.send(welcome_text)

    def _get_welcome_screen(self) -> str:
        """
        Get the connection welcome screen.

        Looks for welcome file in order:
        1. Configured welcome_file (from settings)
        2. data/welcome.txt (relative to working directory)
        3. Falls back to default welcome message

        Returns:
            The welcome screen text to display on connection.
        """
        # Try configured welcome file
        if self.welcome_file and self.welcome_file.exists():
            try:
                return self.welcome_file.read_text()
            except Exception as e:
                logger.warning(f"Failed to read welcome file: {e}")

        # Fallback to legacy location
        legacy_welcome = Path("data/welcome.txt")
        if legacy_welcome.exists():
            try:
                return legacy_welcome.read_text()
            except Exception as e:
                logger.warning(f"Failed to read legacy welcome file: {e}")

        return self._default_welcome_screen()

    def _default_welcome_screen(self) -> str:
        """Return the default welcome screen."""
        lines = [
            "",
            "=" * 60,
            f"  Welcome to {self.game_name}",
            "  Powered by REALM",
            "=" * 60,
            "",
            "Enter 'connect <name> <password>' to log in",
            "Enter 'create <name> <password>' to create a new character",
            "",
        ]
        return "\n".join(lines)

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
