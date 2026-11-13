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
from dataclasses import replace
from typing import Any

from realm.commands.dispatcher import CommandContext, CommandDispatcher
from realm.config.loader import Settings
from realm.core.action_types import ActionType
from realm.core.objects import GameObject
from realm.core.propagation import (
    ROOM_TARGET_CHAIN,
    Action,
    propagate,
)
from realm.core.render import render_room
from realm.gateway.session import Session, SessionManager
from realm.gateway.telnet import TelnetServer
from realm.persistence.manager import PersistenceManager, set_active_manager
from realm.scripting.engine import ScriptEngine
from realm.server.auth import AuthService
from realm.server.world import World, build_world
from realm.systems.base import GameSystem

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
        server = GameServer(load_config())
        await server.run_forever()
    """

    def __init__(self, settings: Settings | None = None, **overrides: Any):
        """Build a server from ``settings`` (default: ``Settings()``).

        Keyword ``overrides`` replace individual fields, so
        ``GameServer(db_path=":memory:", enable_telnet=False)`` works. An
        unknown name raises TypeError.
        """
        self.settings = replace(settings or Settings(), **overrides)
        cfg = self.settings
        # Built by start() (build_world); dispatcher, script_engine,
        # combat_manager and game_system read it.
        self.world: World | None = None

        # Core components
        self.session_manager = SessionManager()
        # The one input funnel: every protocol adapter's submit_input()
        # drains through _on_command via a per-session pump — prompts,
        # chargen, and dispatch see identical input from any protocol.
        self.session_manager.set_input_sink(self._on_command)
        self.persistence: PersistenceManager | None = None
        self.auth: AuthService | None = None

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
        self._reap_task: asyncio.Task[None] | None = None
        self._startup_room: GameObject | None = None

        # Callbacks
        self._on_start: list[Callable[[], Awaitable[None]]] = []
        self._on_stop: list[Callable[[], Awaitable[None]]] = []

        # config.py's on_start / on_stop callbacks.
        if cfg.on_start:
            config_on_start = cfg.on_start

            async def run_config_on_start():
                await config_on_start(self)
            self.on_start(run_config_on_start)
        if cfg.on_stop:
            config_on_stop = cfg.on_stop

            async def run_config_on_stop():
                await config_on_stop(self)
            self.on_stop(run_config_on_stop)

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

    @property
    def dispatcher(self) -> CommandDispatcher:
        if self.world is None:
            raise RuntimeError("GameServer.dispatcher exists once start() has run")
        return self.world.dispatcher

    @property
    def script_engine(self) -> ScriptEngine | None:
        return self.world.scripts if self.world is not None else None

    @property
    def combat_manager(self) -> Any:
        """The combat feature's manager (``world.services['combat']``), if installed."""
        return self.world.services.get("combat") if self.world is not None else None

    @property
    def game_system(self) -> GameSystem | None:
        return self.world.rules if self.world is not None else None

    async def start(self) -> None:
        """Start the game server."""
        logger.info(f"Starting {self.settings.game_name} game server...")

        # The game's features. Their registries (behaviors, rulesets,
        # destination resolvers, softcode functions) install BEFORE the world
        # loads, so a saved behavior always finds its class.
        from realm.features import load
        from realm.std import CLASSIC
        features = load(self.settings.features or CLASSIC)
        features.install_registries()

        # Initialize persistence
        self.persistence = PersistenceManager(
            self.settings.db_path,
            flush_interval=self.settings.flush_interval,
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
        if loaded_count == 0 and self.settings.init_world:
            try:
                await self.settings.init_world(self)
            except Exception as e:
                logger.error(f"Error in init_world callback: {e}")
                raise

        # Pick up any custom role_def ranks now the world is in the cache
        # (built-in roles work without this; this activates data-defined ranks
        # from boot — including any init_world just created — rather than
        # waiting for the first @reload).
        from realm.permissions.entitlements import reload_role_defs
        reload_role_defs()

        # Fall back to a default startup room if the world still lacks one.
        await self._ensure_startup_room()

        # Relocate any player whose saved location vanished (e.g. an instance
        # room that was never persisted) — the reboot half of the evacuation
        # guard, so nobody logs in to "nowhere".
        await self._reconcile_orphaned_players()

        # Set up session callbacks
        self.session_manager.on_connect(self._on_session_connect)
        self.session_manager.on_disconnect(self._on_session_disconnect)

        # Wire the engine: the same build_world the Simulator uses.
        self.world = build_world(self.persistence, self.settings,
                                 sessions=self.session_manager, features=features)
        await features.boot(self.world)

        # Server-only wiring around the shared world.
        self.dispatcher.set_login_handler(self._handle_login)
        self.dispatcher.server = self  # @stats reads settings
        self.dispatcher.set_unknown_handler(self._handle_unknown)
        # `logout` redisplays this without dropping the connection.
        self.dispatcher.welcome_screen = self._get_welcome_screen

        # The world's heartbeat: drives tickable behaviors (patrols, AI)
        # and flushes sessions so NPC-initiated output reaches players
        # without waiting for them to type something. Reaping runs on its own
        # coarse task so a slow sweep never stalls the heartbeat.
        if self.settings.tick_interval > 0:
            self._tick_task = asyncio.create_task(self._tick_loop())
            self._reap_task = asyncio.create_task(self._reap_loop())

        # Protocols the features declared join any registered on the server.
        for name, cls, kwargs in self.world.protocols:
            self.register_protocol(name, cls, **kwargs)

        # Start built-in protocol servers
        if self.settings.enable_telnet:
            self._telnet_server = TelnetServer(
                self.session_manager,
                self._on_command,
                host=self.settings.telnet_host,
                port=self.settings.telnet_port,
                encoding=self.settings.encoding,
            )
            await self._telnet_server.start()

        if self.settings.enable_websocket:
            try:
                from realm.gateway.websocket import WebSocketServer
                self._websocket_server = WebSocketServer(
                    self.session_manager,
                    self._on_command,
                    host=self.settings.websocket_host,
                    port=self.settings.websocket_port,
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
        import time as _time
        self.dispatcher.server_started_at = _time.monotonic()

        # Run startup callbacks
        for callback in self._on_start:
            try:
                await callback()
            except Exception as e:
                logger.error(f"Error in startup callback: {e}")

        logger.info(f"{self.settings.game_name} game server started")

    async def stop(self) -> None:
        """Stop the game server."""
        logger.info(f"Stopping {self.settings.game_name} game server...")

        self._running = False

        # Run stop callbacks
        for callback in self._on_stop:
            try:
                await callback()
            except Exception as e:
                logger.error(f"Error in stop callback: {e}")

        # Stop the heartbeat and the reap loop before tearing anything down.
        for attr in ("_tick_task", "_reap_task"):
            task = getattr(self, attr)
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                setattr(self, attr, None)

        # Undo every ambient registration build_world made (observers,
        # setters, the active store) so a later server starts clean.
        if self.world is not None:
            self.world.close()

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

        logger.info(f"{self.settings.game_name} game server stopped")

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

        from realm.behaviors.scripted import report_unresolved
        report_unresolved(objects)
        return len(objects)

    async def _reconcile_orphaned_players(self) -> None:
        """Kernel bit #2, across the reboot boundary.

        A player mid-instance/wilderness at shutdown has ``location``
        pointing at an ephemeral room. That room is never persisted, so on
        reload the reference resolves to nothing and the player's location
        is left ``None`` — they'd log in to "You are nowhere." Reconcile
        each such player down the same ladder the destroy paths use (home,
        else the start room), loudly. Active destroy/reap evacuate directly;
        this is the load-time half of the guarantee.

        Non-players whose stored location dangled get the R9 disposition
        (the crash-path backstop — a clean reap already applied it):
        player-owned property lands in its owner's refuge; everything else
        is deleted, loudly — never left silently at ``location=None``.
        """
        if not self.persistence:
            return
        for player in self.persistence.find_cached(tag='player'):
            if player.location is not None:
                continue
            home = self.persistence.get_cached(player.db.get('home'))
            dest = home or self._startup_room
            if dest is None:
                continue
            player.location = dest
            await self.persistence.save(player)
            logger.warning(
                f"Reconciled orphaned player {player.name} "
                f"(no resolvable location) -> {dest.name}"
            )

        from realm.core import ops
        from realm.core.teardown import owner_refuge
        dangling = getattr(self.persistence, '_dangling_locations', {})
        for obj_id, loc_id in list(dangling.items()):
            dangling.pop(obj_id, None)
            obj = self.persistence.get_cached(obj_id)
            if obj is None or obj.location is not None or obj.is_player:
                continue
            owner = obj.owner
            refuge = None
            if owner is not None and owner.is_player:
                refuge = (owner_refuge(self.persistence, owner)
                          or self._startup_room)
            if refuge is not None:
                obj.location = refuge
                await self.persistence.save(obj)
                logger.warning(
                    f"Reconciled {obj.name} ({obj.id}): stored location "
                    f"{loc_id} vanished -> {owner.name}'s refuge {refuge.name}"
                )
            else:
                # ops.destroy empties it first — a player or player-owned
                # property that reloaded INSIDE this dangling container must
                # not be deleted out from under (R9 recursion).
                try:
                    await ops.destroy(None, obj, self.persistence)
                except ops.OpError as refused:
                    obj.location = self._startup_room
                    await self.persistence.save(obj)
                    logger.warning(
                        f"Reconciled {obj.name} ({obj.id}): stored location "
                        f"{loc_id} vanished and it may not be destroyed "
                        f"({refused.reason}) -> start room")
                    continue
                logger.warning(
                    f"Reaped {obj.name} ({obj.id}): stored location "
                    f"{loc_id} vanished and it has no player owner"
                )

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

        Resolution order:
        1. WELCOME_BANNER (inline in config.py — the most deliberate)
        2. Configured welcome_file (WELCOME_FILE, resolved from the game
           directory; default data/welcome.txt)
        3. Falls back to default welcome message

        Returns:
            The welcome screen text to display on connection.
        """
        # An inline banner in config.py wins outright.
        if self.settings.welcome_banner:
            return self.settings.welcome_banner

        # Try configured welcome file
        if self.settings.welcome_file and self.settings.welcome_file.exists():
            try:
                return self.settings.welcome_file.read_text(encoding='utf-8')
            except Exception as e:
                logger.warning(f"Failed to read welcome file: {e}")

        return self._default_welcome_screen()

    def _default_welcome_screen(self) -> str:
        """Return the default welcome screen."""
        lines = [
            "",
            "=" * 60,
            f"  Welcome to {self.settings.game_name}",
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
                    action_type=ActionType.DISCONNECT,
                    chain=ROOM_TARGET_CHAIN,
                )
                action.add_message("room", "{actor} has disconnected.")
                await propagate(action)

            if self.persistence:
                await self.persistence.save(player)

    async def _on_command(self, session: Session, command: str) -> None:
        """Called when a command is received from a session."""
        # An active prompt/wizard captures input (unless it passes an
        # escape command like help/quit through to the dispatcher).
        if session.input_handler is not None:
            consumed = await session.input_handler(session, command)
            if consumed:
                await session.flush_output()
                return

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

        # A persistent softcode prompt outstanding from before a reboot
        # resumes: the player's next line runs its callback again.
        pending = player.db.get('input_prompt')
        if pending and self.script_engine is not None:
            self.script_engine._install_softcode_prompt(
                player, "(resuming...)", pending.get('callback'),
                pending.get('executor'), True)

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
                # Starting kit (a weapon, armor): async companion to
                # finish_chargen, since minting items needs persistence.
                await self.game_system.outfit_new_character(
                    player, self.persistence)
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
            action_type=ActionType.CONNECT,
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
        import random
        import time as _time
        import weakref

        from realm.core.beats import (
            WORLD_TICK,
            ambient_beat_targets,
            deliver_beat,
        )
        from realm.core.behaviors import behavior_owners

        last_ticked: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
        next_pulse = _time.monotonic()
        # Start the ambient-beat clock now, so the first beat lands one
        # WORLD_TICK after boot rather than immediately on pulse one.
        last_world_beat = _time.monotonic()
        while True:
            # Drift-correcting sleep: aim for a fixed grid, and if a heavy
            # pulse made us late, resync to now instead of spiralling.
            next_pulse += self.settings.tick_interval
            delay = next_pulse - _time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            else:
                next_pulse = _time.monotonic()
            now = _time.monotonic()

            # --- Real-time behaviors (spawners, decay, wander, tickers) ---
            # Each fires on its own tick_interval (default WORLD_TICK), so the
            # fast heartbeat never changes their pacing.
            for obj in behavior_owners():
                for behavior in obj.get_behaviors():
                    if not behavior.should_tick:
                        continue
                    interval = behavior.tick_interval
                    previous = last_ticked.get(behavior)
                    if previous is None:
                        # Start-phase jitter: seed a random point within the
                        # interval so simultaneous behaviors don't lockstep.
                        last_ticked[behavior] = now - random.random() * interval
                        continue
                    if interval > 0 and now - previous < interval:
                        continue
                    last_ticked[behavior] = now
                    try:
                        await behavior.tick(obj, now - previous)
                    except Exception:
                        logger.exception(
                            f"Tick error in {behavior.behavior_id} on {obj.name}"
                        )

            # --- Ambient beat: out-of-combat objects advance one beat every
            # WORLD_TICK. Combatants are driven by their encounter instead
            # (the double-tick guard), so they're skipped here. ---
            if now - last_world_beat >= WORLD_TICK:
                last_world_beat = now
                for obj in ambient_beat_targets(behavior_owners()):
                    try:
                        await deliver_beat(obj)
                    except Exception:
                        logger.exception(f"Ambient beat error on {obj.name}")

            # --- Output flush every pulse (near-real-time NPC/room output). ---
            for session in self.session_manager.all_sessions():
                try:
                    await session.flush_output()
                except Exception:
                    logger.exception("Tick flush error")

    async def _reap_loop(self) -> None:
        """Coarse housekeeping on its OWN cadence (``reap_interval``, ~5s),
        decoupled from the fast heartbeat so a slow sweep never stalls the
        pulse, the ambient beat, or output flush (like the persistence flush
        loop)."""
        import asyncio as _asyncio
        while True:
            await _asyncio.sleep(self.settings.reap_interval)
            if self.persistence is not None:
                await self._reap()

    async def _reap(self) -> None:
        """Slow housekeeping off the fast pulse: the features' reapers
        (idle instances, wilderness cells) and the kernel's expiry sweep."""
        from realm.core.events import reap_expired
        reapers = [*(self.world.reapers if self.world is not None else []), reap_expired]
        for fn in reapers:
            try:
                await fn(self.persistence)
            except Exception:
                logger.exception(f"Reap error in {fn.__module__}.{fn.__qualname__}")

    async def _handle_unknown(self, ctx: CommandContext) -> None:
        """Handle unknown commands: softcode $-command fallback."""
        if self.script_engine is not None:
            if await self.script_engine.handle_unknown_command(ctx):
                return
        await ctx.session.send("Huh? (Type 'help' for commands)")

    @property
    def startup_room(self) -> GameObject | None:
        """The room new characters and roomless players start in."""
        return self._startup_room

    @startup_room.setter
    def startup_room(self, room: GameObject | None) -> None:
        self._startup_room = room
