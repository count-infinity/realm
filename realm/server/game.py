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
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Importing the behavior kit registers its behaviors with the
# BehaviorRegistry so persisted worlds can rehydrate them.
import realm.behaviors  # noqa: F401
import realm.combat.behaviors  # noqa: F401
from realm.combat.manager import CombatManager, set_combat_manager
from realm.combat.system import create_combat_system
from realm.core.objects import GameObject
from realm.core.perception import stealth_observer
from realm.core.propagation import (
    ROOM_TARGET_CHAIN,
    Action,
    propagate,
)
from realm.core.propagation import (
    get_engine as get_propagation_engine,
)
from realm.core.render import render_room
from realm.gateway.session import Session, SessionManager
from realm.gateway.telnet import TelnetServer
from realm.persistence.manager import PersistenceManager, set_active_manager
from realm.scripting.engine import ScriptEngine, set_script_engine
from realm.server.auth import AuthService
from realm.server.dispatcher import CommandContext, CommandDispatcher
from realm.systems import GameSystemRegistry, GurpsSystem, set_game_system

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
        enable_scripting: bool = True,
        flush_interval: float = 30.0,
        tick_interval: float = 4.0,
        encoding: str = "utf-8",
        combat_ruleset: str | None = None,
        game_system: str = "gurps",
        combat_beat_min: float = 4.0,
        combat_beat_max: float = 120.0,
        combat_beat_default: float = 15.0,
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
        self.enable_scripting = enable_scripting
        self.flush_interval = flush_interval
        self.tick_interval = tick_interval
        self.encoding = encoding
        self.combat_ruleset = combat_ruleset
        self.game_system_name = game_system
        self.game_system = None
        self.combat_beat_min = combat_beat_min
        self.combat_beat_max = combat_beat_max
        self.combat_beat_default = combat_beat_default
        self.game_name = game_name
        self.welcome_file = Path(welcome_file) if welcome_file else None

        # Core components
        self.session_manager = SessionManager()
        self.dispatcher = CommandDispatcher()
        self.persistence: PersistenceManager | None = None
        self.auth: AuthService | None = None
        self.script_engine: ScriptEngine | None = None
        self.combat_manager: CombatManager | None = None

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
        self._tick_task: asyncio.Task[None] | None = None
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
            enable_scripting=settings.enable_scripting,
            flush_interval=settings.flush_interval,
            tick_interval=settings.tick_interval,
            encoding=getattr(settings, 'encoding', 'utf-8'),
            combat_ruleset=settings.combat_ruleset,
            game_system=getattr(settings, 'game_system', 'gurps'),
            combat_beat_min=settings.combat_beat_min,
            combat_beat_max=settings.combat_beat_max,
            combat_beat_default=settings.combat_beat_default,
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
        set_active_manager(self.persistence)
        self.auth = AuthService(self.persistence)

        # Load world
        loaded_count = await self._load_world()

        # Call init_world only on first boot (empty database) — its documented
        # contract. Running it on every start would recreate world objects
        # over the loaded ones, leaving players in stale duplicate rooms.
        if loaded_count == 0 and self._settings and self._settings.init_world:
            try:
                await self._settings.init_world(self)
            except Exception as e:
                logger.error(f"Error in init_world callback: {e}")
                raise

        # Fall back to a default startup room if the world still lacks one.
        await self._ensure_startup_room()

        # Set up session callbacks
        self.session_manager.on_connect(self._on_session_connect)
        self.session_manager.on_disconnect(self._on_session_disconnect)

        # Set up dispatcher handlers and services
        self.dispatcher.set_login_handler(self._handle_login)
        self.dispatcher.server = self  # @stats reads tick_interval etc.
        self.dispatcher.set_unknown_handler(self._handle_unknown)
        self.dispatcher.persistence = self.persistence
        self.dispatcher.session_manager = self.session_manager

        # Softcode scripting: $-command fallback via _handle_unknown, and an
        # action observer so ^listen and ON_<EVENT> triggers fire on the
        # same propagated actions behaviors see.
        if self.enable_scripting:
            self.script_engine = ScriptEngine(persistence=self.persistence)
            get_propagation_engine().add_observer(self.script_engine.handle_action)
            set_script_engine(self.script_engine)
            self.script_engine.dispatcher = self.dispatcher

        # Loud actions break stealth, whoever performs them.
        get_propagation_engine().add_observer(stealth_observer)

        # Combat: beat-driven encounters; hostile-tagged actions between
        # combat-capable parties auto-initiate (the fireball WAS your turn).
        # The game system is the swappable rules package (GURPS/D20/...):
        # it supplies skill defaults, chargen, advancement, and the combat
        # ruleset (explicit COMBAT_RULESET config overrides it).
        self.game_system = (GameSystemRegistry.create(self.game_system_name)
                            or GurpsSystem())
        set_game_system(self.game_system)
        from realm.core.checks import set_check_resolver, set_skill_defaults
        set_skill_defaults(self.game_system.skill_defaults())
        set_check_resolver(self.game_system.resolve_check)

        combat_system = create_combat_system(
            self.combat_ruleset or self.game_system.ruleset_name)
        self.combat_manager = CombatManager(
            combat_system,
            beat_min=self.combat_beat_min,
            beat_max=self.combat_beat_max,
            beat_default=self.combat_beat_default,
            session_manager=self.session_manager,
        )
        set_combat_manager(self.combat_manager)
        get_propagation_engine().add_observer(self.combat_manager.hostile_observer)

        # The world's heartbeat: drives tickable behaviors (patrols, AI)
        # and flushes sessions so NPC-initiated output reaches players
        # without waiting for them to type something.
        if self.tick_interval > 0:
            self._tick_task = asyncio.create_task(self._tick_loop())

        # Imported here, not at module top: realm.commands re-exports from
        # realm.server.dispatcher, so a top-level import would be circular.
        from realm.commands.builtin import register_all_commands
        register_all_commands(self.dispatcher)

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
                encoding=self.encoding,
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

        # Stop the heartbeat before tearing anything else down.
        if self._tick_task is not None:
            self._tick_task.cancel()
            try:
                await self._tick_task
            except asyncio.CancelledError:
                pass
            self._tick_task = None

        # Detach observers from the (module-singleton) propagation engine
        # so a later server instance doesn't double-fire.
        if self.script_engine is not None:
            get_propagation_engine().remove_observer(self.script_engine.handle_action)
            self.script_engine = None
            set_script_engine(None)
        get_propagation_engine().remove_observer(stealth_observer)
        if self.combat_manager is not None:
            get_propagation_engine().remove_observer(self.combat_manager.hostile_observer)
            self.combat_manager.stop_all()
            self.combat_manager = None
            set_combat_manager(None)
        set_active_manager(None)
        from realm.core.checks import set_check_resolver
        set_check_resolver(None)
        set_game_system(None)
        self.game_system = None

        # Disconnect all sessions BEFORE stopping protocol servers:
        # Server.wait_closed() (Python 3.12.1+) waits for client connections,
        # so lingering sessions would stall shutdown until clients hang up.
        for session in self.session_manager.all_sessions():
            await session.send("Server shutting down. Goodbye!")
            await self.session_manager.destroy_session(session)

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

        # Save and close persistence
        if self.persistence:
            await self.persistence.close()

        logger.info(f"{self.game_name} game server stopped")

    async def run_forever(self) -> None:
        """Run the server until interrupted."""
        await self.start()

        # Set up signal handlers
        loop = asyncio.get_running_loop()
        stop_task: asyncio.Task[None] | None = None

        def handle_signal():
            nonlocal stop_task
            logger.info("Received shutdown signal")
            if stop_task is None:
                stop_task = asyncio.create_task(self.stop())

        try:
            loop.add_signal_handler(signal.SIGINT, handle_signal)
            loop.add_signal_handler(signal.SIGTERM, handle_signal)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

        # Wait until stopped
        while self._running:
            await asyncio.sleep(1)

        # stop() flips _running immediately, which ends the wait loop above.
        # Await the full shutdown here — returning early would let
        # asyncio.run() cancel it mid-flight (unflushed saves, a stranded
        # aiosqlite thread that keeps the process alive).
        if stop_task is not None:
            await stop_task

    async def _load_world(self) -> int:
        """Load the game world from persistence. Returns the object count."""
        if not self.persistence:
            return 0

        objects = await self.persistence.load_all()
        logger.info(f"Loaded {len(objects)} objects from database")

        for obj in objects:
            if obj.has_tag('start_room'):
                self._startup_room = obj
                break

        return len(objects)

    async def _ensure_startup_room(self) -> None:
        """Create a default startup room when neither the database nor
        init_world provided one."""
        if self._startup_room or not self.persistence:
            return

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
            player = session.player
            location = player.location
            if location is not None:
                action = Action(
                    actor=player,
                    target=location,
                    action_type="event:disconnect",
                    chain=ROOM_TARGET_CHAIN,
                )
                action.add_message("room", "{actor} has disconnected.")
                await propagate(action)

            if self.persistence:
                await self.persistence.save(player)

    async def _on_command(self, session: Session, command: str) -> None:
        """Called when a command is received from a session."""
        # Mid-chargen input goes to the chargen flow, not the dispatcher.
        if (session.player is not None
                and session.player.db.get('chargen_step') is not None):
            await self._handle_chargen(session, command)
            await session.flush_output()
            return

        await self.dispatcher.dispatch(session, command)

        # Flush every session, not just the actor's — actions propagated by
        # this command can queue messages on bystanders' output queues. If we
        # only flushed the actor, bystanders wouldn't see anything until they
        # typed a command of their own.
        for s in self.session_manager.all_sessions():
            await s.flush_output()

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
        """Handle the connect command (identity via AuthService)."""
        if not self.persistence or not self.auth:
            await session.send("Server not ready.")
            return

        player, error = await self.auth.authenticate(name, password)
        if player is None:
            await session.send(error)
            return

        # Link player to session
        self.session_manager.link_player_to_session(session, player)

        # Warn if the character was made under a different rules package
        # (config is boot-time-fixed; a mid-life swap leaves old sheets
        # authored under the wrong rules).
        made_under = player.db.get('game_system')
        if (made_under and self.game_system
                and made_under != self.game_system.system_id):
            await session.send(
                f"[!] {player.name} was created under the '{made_under}' "
                f"rules but this server now runs '{self.game_system.system_id}'. "
                "Your character sheet may not match the current rules.")

        # Unfinished chargen resumes where it left off.
        if player.db.get('chargen_step') is not None and self.game_system:
            steps = self.game_system.chargen_steps()
            index = min(int(player.db.get('chargen_step') or 0),
                        max(0, len(steps) - 1))
            await session.send("\nWelcome back — let's finish your character.\n")
            if steps:
                await session.send(steps[index].prompt(player))
            return

        await self._announce_connect(player, returning=True)

        # Show room
        await session.send(render_room(player.location, player))

    async def _do_create(self, session: Session, name: str, password: str) -> None:
        """Handle the create command (identity via AuthService)."""
        if not self.persistence or not self.auth:
            await session.send("Server not ready.")
            return

        player, error = await self.auth.create_account(
            name, password, system=self.game_system)
        if player is None:
            await session.send(error)
            return

        self.session_manager.link_player_to_session(session, player)
        await session.send(f"\nCharacter '{name}' created.")
        if player.has_tag('god'):
            await session.send(
                "As the first character on this server you have SUPERUSER "
                "powers (builder and admin commands — see 'help').")

        steps = self.game_system.chargen_steps()
        if steps:
            player.db.chargen_step = 0
            await self.persistence.save(player)
            await session.send("")
            await session.send(steps[0].prompt(player))
            return

        await self._enter_world(session, player)

    async def _handle_chargen(self, session: Session, response: str) -> None:
        """
        Drive the game system's chargen flow (Template Method: the loop
        lives here, the steps come from the system). State is
        ``db.chargen_step`` — reboot-safe mid-creation.
        """
        player = session.player
        if response.strip().lower() in ('quit', 'logout'):
            await session.send("Goodbye! Your unfinished character will wait.")
            await self.session_manager.destroy_session(session)
            return
        steps = self.game_system.chargen_steps() if self.game_system else []
        index = int(player.db.get('chargen_step') or 0)

        if not steps or index >= len(steps):
            player.db.delete('chargen_step')
            await self._enter_world(session, player)
            return

        if response.strip():
            advance, feedback = steps[index].handle(player, response)
            await session.send(feedback)
            if advance:
                index += 1
        if index >= len(steps):
            player.db.delete('chargen_step')
            welcome = self.game_system.finish_chargen(player)
            if self.persistence:
                await self.persistence.save(player)
            await session.send(welcome)
            await self._enter_world(session, player)
        else:
            player.db.chargen_step = index
            await session.send("")
            await session.send(steps[index].prompt(player))

    async def _enter_world(self, session: Session, player: GameObject) -> None:
        """Place a finished character in the world and announce them."""
        if player.location is None:
            player.location = self._startup_room
        if self.persistence:
            await self.persistence.save(player)
        await session.send(f"\nWelcome to the world, {player.name}!\n")
        await self._announce_connect(player, returning=False)
        await session.send(render_room(player.location, player))

    async def _announce_connect(self, player: GameObject, *, returning: bool) -> None:
        """Tell the player and bystanders that the player has connected."""
        location = player.location
        if location is None:
            return
        verb = "has reconnected" if returning else "arrives"
        action = Action(
            actor=player,
            target=location,
            action_type="event:connect",
            chain=ROOM_TARGET_CHAIN,
            extra={"returning": returning},
        )
        if returning:
            action.add_message("actor", f"\nWelcome back, {player.name}!\n")
        action.add_message("room", f"{{actor}} {verb}.")
        await propagate(action)

    async def _do_who(self, session: Session) -> None:
        """Show who is online."""
        playing = self.session_manager.playing_sessions()
        await session.send(f"\n{len(playing)} player(s) online:")
        for s in playing:
            if s.player:
                idle = int(s.idle_time)
                await session.send(f"  {s.player.name} (idle {idle}s)")
        await session.send("")

    async def _tick_loop(self) -> None:
        """
        Periodic world pulse.

        Every tick_interval seconds, run tick() on every behavior that
        opts in (should_tick), then flush all session output — NPC
        actions must reach players without a player command in flight.
        A failing behavior is logged and skipped; the pulse survives.
        """
        import time as _time
        import weakref

        from realm.core.behaviors import behavior_owners
        last_ticked: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
        while True:
            await asyncio.sleep(self.tick_interval)
            now = _time.monotonic()
            for obj in behavior_owners():
                for behavior in obj.get_behaviors():
                    if not behavior.should_tick:
                        continue
                    interval = behavior.tick_interval
                    previous = last_ticked.get(behavior)
                    if interval > 0 and previous is not None \
                            and now - previous < interval:
                        continue
                    last_ticked[behavior] = now
                    try:
                        await behavior.tick(
                            obj, now - previous if previous else self.tick_interval,
                        )
                    except Exception:
                        logger.exception(
                            f"Tick error in {behavior.behavior_id} on {obj.name}"
                        )
            # One-shot softcode waits ride the same heartbeat.
            if self.script_engine is not None:
                try:
                    await self.script_engine.tick_waits()
                except Exception:
                    logger.exception("Tick wait error")
            for session in self.session_manager.all_sessions():
                try:
                    await session.flush_output()
                except Exception:
                    logger.exception("Tick flush error")

    async def _handle_unknown(self, ctx: CommandContext) -> None:
        """Handle unknown commands: softcode $-command fallback."""
        if self.script_engine is not None:
            if await self.script_engine.handle_unknown_command(ctx):
                return
        await ctx.session.send("Huh? (Type 'help' for commands)")

    @property
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self._running

    @property
    def startup_room(self) -> GameObject | None:
        """The room new characters and roomless players start in."""
        return self._startup_room

    @startup_room.setter
    def startup_room(self, room: GameObject | None) -> None:
        self._startup_room = room
