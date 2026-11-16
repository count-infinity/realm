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
    deliver_messages,
    propagate,
)
from realm.core.world import World
from realm.gateway.session import LINK_LOST, Session, SessionManager
from realm.gateway.telnet import TelnetServer
from realm.persistence.manager import PersistenceManager
from realm.scripting.engine import ScriptEngine
from realm.server.world import DISPATCHED, INTERCEPTED, build_world, prepare_world, route_input

logger = logging.getLogger(__name__)

#: ``realm start``'s exit status after ``@reboot``: a supervisor (systemd's
#: ``Restart=on-failure``, a shell loop) starts the server again on it.
REBOOT_EXIT_CODE = 3


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
        # game_system reads it.
        self.world: World | None = None

        # Core components
        self.session_manager = SessionManager()
        # The one input funnel: every protocol adapter's submit_input()
        # drains through _on_command via a per-session pump — prompts,
        # chargen, and dispatch see identical input from any protocol.
        self.session_manager.set_input_sink(self._on_command)
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
        self._tick_task: asyncio.Task[None] | None = None
        self._reap_task: asyncio.Task[None] | None = None
        #: what ``realm start`` exits with: 0, or REBOOT_EXIT_CODE after @reboot
        self.exit_code = 0
        # A countdown in progress (@shutdown / @reboot), and the stop it ends in.
        self._shutdown_task: asyncio.Task[None] | None = None
        self._stop_task: asyncio.Task[None] | None = None
        # When the last automatic backup was taken (session clock).
        self._last_backup: float | None = None

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
    def game_system(self) -> Any | None:
        return self.world.rules if self.world is not None else None

    async def start(self) -> None:
        """Start the game server."""
        logger.info(f"Starting {self.settings.game_name} game server...")

        # The game's features. Their registries (behaviors, rulesets,
        # destination resolvers, softcode functions) install BEFORE the world
        # loads, so a saved behavior always finds its class.
        from realm.features import load
        features = load(self.settings.features)
        features.install_registries()

        # Initialize persistence
        self.persistence = PersistenceManager(
            self.settings.db_path,
            flush_interval=self.settings.flush_interval,
        )
        await self.persistence.initialize()
        await self.persistence.start_flush_loop()
        if self._db_file() is not None:
            from realm.persistence.pidfile import write_pid_file
            write_pid_file(self._db_file())

        # Wire the world (the same build_world the Simulator uses) before it
        # loads, so loading and init_world find the store through it.
        # Feature on_boot hooks run once it is loaded, below.
        self.world = build_world(self.persistence, self.settings,
                                 sessions=self.session_manager, features=features)

        # Load world
        loaded_count = await self._load_world()

        # init_world on first boot (empty database) only — running it on
        # every start would recreate world objects over the loaded ones —
        # then role_def ranks and a default start room (shared with the
        # Simulator).
        await prepare_world(self.world, self, empty=loaded_count == 0)

        # Relocate any player whose saved location vanished (e.g. an instance
        # room that was never persisted) — the reboot half of the evacuation
        # guard, so nobody logs in to "nowhere".
        await self._reconcile_orphaned_players()

        # A character left link-dead when the server last stopped (a crash)
        # has no wait running: it is simply offline.
        for player in self.persistence.find_cached(tag='linkdead'):
            player.remove_tag('linkdead')

        # Set up session callbacks
        self.session_manager.on_connect(self._on_session_connect)
        self.session_manager.on_disconnect(self._on_session_disconnect)

        await features.boot(self.world)

        # Server-only wiring around the shared world. (The login handler and
        # the welcome screen are the login feature's: `accounts`.)
        self.dispatcher.server = self  # @stats reads settings
        self.dispatcher.set_unknown_handler(self._handle_unknown)

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
                    web_client=self.settings.web_client,
                    game_name=self.settings.game_name,
                )
                await self._websocket_server.start()
            except Exception as e:
                logger.warning(f"Could not start WebSocket server: {e}")
        elif self.settings.web_client:
            logger.warning("WEB_CLIENT is set but the WebSocket server is off, so the "
                           "browser client is not served: set ENABLE_WEBSOCKET = True "
                           "in config.py.")

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
        for key, value in self.world.changed_settings().items():
            logger.info(f"setting {key} = {value!r}")

    def _db_file(self):
        """The database file, or None for an in-memory database."""
        path = self.settings.db_path
        return None if str(path) == ":memory:" else path

    async def stop(self) -> None:
        """Stop the game server."""
        logger.info(f"Stopping {self.settings.game_name} game server...")

        self._running = False
        if self._shutdown_task is not None and self._shutdown_task is not asyncio.current_task():
            self._shutdown_task.cancel()
        self._shutdown_task = None

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

        # Disconnect all sessions BEFORE stopping protocol servers:
        # Server.wait_closed() (Python 3.12.1+) waits for client connections,
        # so lingering sessions would stall shutdown until clients hang up.
        # And before closing the world: a player still in play is announced
        # as disconnected and saved, which needs the world.
        for session in self.session_manager.all_sessions():
            await session.send("Server shutting down. Goodbye!")
            await self.session_manager.destroy_session(session)

        # Undo every ambient registration build_world made (observers,
        # setters, the active store) so a later server starts clean.
        if self.world is not None:
            self.world.close()

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
            if self._db_file() is not None:
                from realm.persistence.pidfile import remove_pid_file
                remove_pid_file(self._db_file())

        logger.info(f"{self.settings.game_name} game server stopped")

    async def run_forever(self) -> None:
        """Run the server until interrupted."""
        await self.start()

        # Set up signal handlers
        loop = asyncio.get_running_loop()

        def handle_signal():
            logger.info("Received shutdown signal")
            self.request_stop()

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
        if self._stop_task is not None:
            await self._stop_task

    def request_stop(self) -> None:
        """Stop the server from inside its own loop (a signal, the end of a
        countdown): ``run_forever`` waits for the stop to finish."""
        if self._stop_task is None:
            self._stop_task = asyncio.create_task(self.stop())

    # --- @shutdown / @reboot ---

    @property
    def shutdown_pending(self) -> bool:
        return self._shutdown_task is not None and not self._shutdown_task.done()

    async def schedule_shutdown(self, seconds: int, reason: str = "", *,
                                reboot: bool = False) -> None:
        """Announce a countdown of ``seconds`` to every session, then (in
        the background) repeat it at the minute marks and 30, 10 and 5
        seconds out, save everything, and stop; ``reboot`` exits with
        REBOOT_EXIT_CODE. One countdown at a time (``cancel_shutdown``)."""
        if self.shutdown_pending:
            raise RuntimeError("A shutdown is already counting down.")
        seconds = max(0, int(seconds))
        if seconds > 0:
            await self.wall(self._countdown_line(seconds, reason, reboot))
        self._shutdown_task = asyncio.create_task(self._count_down(seconds, reason, reboot))

    @staticmethod
    def _countdown_line(remaining: int, reason: str, reboot: bool) -> str:
        what = "rebooting" if reboot else "shutting down"
        why = f" ({reason})" if reason else ""
        if remaining <= 0:
            return f"*** The server is {what} now{why}. ***"
        unit = "second" if remaining == 1 else "seconds"
        return f"*** The server is {what} in {remaining} {unit}{why}. ***"

    def cancel_shutdown(self) -> bool:
        """Stop a countdown; False when none is running."""
        if not self.shutdown_pending:
            return False
        self._shutdown_task.cancel()
        self._shutdown_task = None
        return True

    async def wall(self, text: str) -> None:
        """Send ``text`` to every connected session now."""
        for session in self.session_manager.all_sessions():
            await session.send(text)
            await session.flush_output()

    async def _count_down(self, seconds: int, reason: str, reboot: bool) -> None:
        remaining = seconds
        while remaining > 0:
            marks = [m for m in (*range(60, remaining, 60), 30, 10, 5) if m < remaining]
            nxt = max(marks) if marks else 0
            await asyncio.sleep(remaining - nxt)
            remaining = nxt
            if remaining > 0:
                await self.wall(self._countdown_line(remaining, reason, reboot))
        await self.wall(self._countdown_line(0, reason, reboot))
        self.exit_code = REBOOT_EXIT_CODE if reboot else 0
        if self.persistence is not None:
            await self.persistence.flush()
        self._shutdown_task = None
        self.request_stop()

    async def _load_world(self) -> int:
        """Load the game world from persistence. Returns the object count."""
        if not self.persistence:
            return 0

        objects = await self.persistence.load_all()
        logger.info(f"Loaded {len(objects)} objects from database")

        for obj in objects:
            if obj.has_tag('start_room'):
                self.world.startup_room = obj
                break

        from realm.scripting.scripted_behavior import report_unresolved
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
            dest = home or self.world.startup_room
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
                          or self.world.startup_room)
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
                    obj.location = self.world.startup_room
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

    async def _on_session_connect(self, session: Session) -> None:
        """Greet a new connection with the login feature's welcome screen."""
        if self.dispatcher.welcome_screen is None:
            await session.send("This world has no login feature installed.")
            return
        await session.send(self.dispatcher.welcome_screen())

    async def _on_session_disconnect(self, session: Session) -> None:
        """Called when a session disconnects. A connection that dropped
        under a character in play (no ``quit``) leaves it waiting in the
        room, link-dead, for ``LINKDEAD_SECONDS``; otherwise it leaves
        play now."""
        if session.player:
            player = session.player
            location = player.location
            if (session.close_reason == LINK_LOST and location is not None
                    and self.settings.linkdead_seconds > 0
                    and player.db.get('chargen_step') is None):
                self.session_manager.mark_linkdead(player)
                action = Action(actor=player, target=location,
                                action_type=ActionType.DISCONNECT, chain=ROOM_TARGET_CHAIN)
                action.add_message("room", "{actor} has lost their link.")
                deliver_messages(action)        # a line only: it has not left yet
            elif location is not None:
                await self._announce_departure(player)

            if self.persistence:
                await self.persistence.save(player)

    async def _announce_departure(self, player: GameObject) -> None:
        """The character leaves play: the room hears it, and ``ON_DISCONNECT``."""
        action = Action(
            actor=player,
            target=player.location,
            action_type=ActionType.DISCONNECT,
            chain=ROOM_TARGET_CHAIN,
        )
        action.add_message("room", "{actor} has disconnected.")
        await propagate(action)

    async def _on_command(self, session: Session, command: str) -> None:
        """Called when a command is received from a session."""
        outcome = await route_input(self.world, session, command)
        if outcome != DISPATCHED:
            # A prompt or the editor asks its own question; the pager and an
            # interceptor end with the prompt.
            await session.flush_output(prompt=outcome == INTERCEPTED)
            return

        # Flush every session, not just the actor's — actions propagated by
        # this command can queue messages on bystanders' output queues. If we
        # only flushed the actor, bystanders wouldn't see anything until they
        # typed a command of their own. The typist always gets a prompt;
        # a bystander gets one after the output it was sent.
        for s in self.session_manager.all_sessions():
            await s.flush_output(prompt=s is session)

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

        from realm.core.beats import ambient_beat_targets, deliver_beat
        from realm.core.behaviors import behavior_owners

        world_beat = self.world.setting("WORLD_BEAT")

        last_ticked: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
        next_pulse = _time.monotonic()
        # Start the ambient-beat clock now, so the first beat lands one
        # WORLD_BEAT after boot rather than immediately on pulse one.
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
            # Each fires on its own tick_interval (default WORLD_BEAT), so the
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
            # WORLD_BEAT. Combatants are driven by their encounter instead
            # (the double-tick guard), so they're skipped here. ---
            if now - last_world_beat >= world_beat:
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
        (idle instances, wilderness cells), the kernel's expiry sweep, idle
        and link-dead sessions, and the automatic backup."""
        from realm.core.events import reap_expired
        reapers = [*(self.world.reapers if self.world is not None else []), reap_expired]
        for fn in reapers:
            try:
                await fn(self.persistence)
            except Exception:
                logger.exception(f"Reap error in {fn.__module__}.{fn.__qualname__}")
        for step in (self._reap_idle, self._reap_linkdead, self._backup_if_due):
            try:
                await step()
            except Exception:
                logger.exception(f"Reap error in {step.__name__}")

    async def _reap_idle(self) -> None:
        """Close every connection idle for ``IDLE_TIMEOUT`` minutes; admins
        are exempt."""
        minutes = self.settings.idle_timeout
        if minutes <= 0:
            return
        from realm.permissions.roles import has_permission
        for session in self.session_manager.all_sessions():
            if session.idle_time < minutes * 60:
                continue
            if session.player is not None and has_permission(session.player, 'admin'):
                continue
            await session.send(f"You have been idle for {int(minutes)} minutes. Goodbye.")
            await self.session_manager.destroy_session(session)

    async def _reap_linkdead(self) -> None:
        """A link-dead character whose wait ran out leaves play."""
        limit = self.settings.linkdead_seconds
        from realm.gateway import session as session_clock
        now = session_clock.clock()
        for player, since in self.session_manager.linkdead():
            if now - since < limit:
                continue
            self.session_manager.clear_linkdead(player)
            if player.location is not None:
                await self._announce_departure(player)
            if self.persistence:
                await self.persistence.save(player)

    async def _backup_if_due(self) -> None:
        """Every ``BACKUP_INTERVAL_HOURS``, a backup to ``data/backups/``,
        then prune to the newest ``BACKUP_KEEP``."""
        hours = self.settings.backup_interval_hours
        db = self._db_file()
        if hours <= 0 or db is None or self.persistence is None:
            return
        from realm.gateway import session as session_clock
        now = session_clock.clock()
        if self._last_backup is None:
            self._last_backup = now                  # the first one, an interval after boot
            return
        if now - self._last_backup < hours * 3600:
            return
        self._last_backup = now
        from realm.persistence.backup import backup_database, prune_backups
        await self.persistence.flush()
        path = await asyncio.to_thread(backup_database, db)
        logger.info(f"Backup written to {path}")
        if self.settings.backup_keep > 0:
            await asyncio.to_thread(prune_backups, db, self.settings.backup_keep)

    async def _handle_unknown(self, ctx: CommandContext) -> None:
        """Handle unknown commands: softcode $-command fallback."""
        if self.script_engine is not None:
            if await self.script_engine.handle_unknown_command(ctx):
                return
        await ctx.session.send("Huh? (Type 'help' for commands)")

    @property
    def startup_room(self) -> GameObject | None:
        """The room new characters and roomless players start in
        (``world.startup_room``)."""
        return self.world.startup_room if self.world is not None else None

    @startup_room.setter
    def startup_room(self, room: GameObject | None) -> None:
        self.world.startup_room = room
