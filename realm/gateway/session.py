"""
Session management for player connections.

Sessions represent the connection between a player and the game.
They handle input/output buffering and map to player objects.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """States a session can be in."""

    CONNECTED = auto()      # Just connected, not authenticated
    AUTHENTICATING = auto() # In login/character select flow
    PLAYING = auto()        # In-game, has a player object
    DISCONNECTING = auto()  # Being cleaned up


@dataclass
class SessionMessage:
    """A message in the session queue."""

    session_id: str
    content: str
    timestamp: float = field(default_factory=time.monotonic)


class Session:
    """
    Represents a single player connection.

    Each session has:
    - A unique ID
    - An input queue (commands from player)
    - An output queue (messages to player)
    - An optional linked player object
    - Connection metadata (IP, protocol, etc.)
    """

    __slots__ = (
        'id',
        'state',
        'player',
        '_input_queue',
        '_output_queue',
        '_writer',
        '_closer',
        '_protocol',
        '_address',
        '_created_at',
        '_last_activity',
        '_account_name',
        '_data',
    )

    def __init__(
        self,
        session_id: str | None = None,
        protocol: str = "unknown",
        address: str = "unknown",
    ):
        self.id = session_id or str(uuid.uuid4())
        self.state = SessionState.CONNECTED
        self.player: GameObject | None = None

        self._input_queue: asyncio.Queue[str] = asyncio.Queue()
        self._output_queue: asyncio.Queue[str] = asyncio.Queue()
        self._writer: Callable[[str], Awaitable[None]] | None = None
        self._closer: Callable[[], Any] | None = None

        self._protocol = protocol
        self._address = address
        self._created_at = time.monotonic()
        self._last_activity = self._created_at
        self._account_name: str | None = None
        self._data: dict[str, Any] = {}  # Extra session data

    @property
    def protocol(self) -> str:
        """The protocol this session uses (telnet, websocket, etc.)."""
        return self._protocol

    @property
    def address(self) -> str:
        """The remote address of this session."""
        return self._address

    @property
    def idle_time(self) -> float:
        """Seconds since last activity."""
        return time.monotonic() - self._last_activity

    @property
    def connected_time(self) -> float:
        """Seconds since connection."""
        return time.monotonic() - self._created_at

    @property
    def account_name(self) -> str | None:
        """The account name if authenticated."""
        return self._account_name

    def set_writer(self, writer: Callable[[str], Awaitable[None]]) -> None:
        """Set the function used to write data to the client."""
        self._writer = writer

    def set_closer(self, closer: Callable[[], Any] | None) -> None:
        """
        Set the function that closes the underlying connection.

        Wired by the protocol layer so the server can hang up (quit command,
        shutdown) instead of waiting for the client to disconnect. May be a
        plain callable or one returning an awaitable.
        """
        self._closer = closer

    async def close_connection(self) -> None:
        """Close the underlying network connection, if a closer is wired."""
        if self._closer is None:
            return
        try:
            result = self._closer()
            if result is not None and hasattr(result, '__await__'):
                await result
        except Exception as e:
            logger.warning(f"Session {self.id}: error closing connection: {e}")

    def touch(self) -> None:
        """Update last activity timestamp."""
        self._last_activity = time.monotonic()

    async def send(self, message: str) -> None:
        """Send a message to the player."""
        await self._output_queue.put(message)

    def send_nowait(self, message: str) -> None:
        """Send a message without waiting (for sync contexts)."""
        try:
            self._output_queue.put_nowait(message)
        except asyncio.QueueFull:
            logger.warning(f"Session {self.id}: output queue full, dropping message")

    async def receive(self) -> str:
        """Receive a command from the player."""
        return await self._input_queue.get()

    def receive_nowait(self) -> str | None:
        """Try to receive a command without waiting."""
        try:
            return self._input_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def push_input(self, command: str) -> None:
        """Push a command into the input queue (called by protocol handlers)."""
        self.touch()
        await self._input_queue.put(command)

    def push_input_nowait(self, command: str) -> None:
        """Push a command without waiting."""
        self.touch()
        try:
            self._input_queue.put_nowait(command)
        except asyncio.QueueFull:
            logger.warning(f"Session {self.id}: input queue full, dropping command")

    async def flush_output(self) -> None:
        """Flush all pending output to the writer."""
        if self._writer is None:
            return

        while not self._output_queue.empty():
            try:
                message = self._output_queue.get_nowait()
                await self._writer(message)
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                logger.error(f"Session {self.id}: error writing: {e}")
                break

    def get_data(self, key: str, default: Any = None) -> Any:
        """Get session-specific data."""
        return self._data.get(key, default)

    def set_data(self, key: str, value: Any) -> None:
        """Set session-specific data."""
        self._data[key] = value

    def link_player(self, player: GameObject) -> None:
        """Link this session to a player object and wire output delivery."""
        self.player = player
        self.state = SessionState.PLAYING
        # Route player.msg() text through this session's output queue.
        player.set_msg_handler(self.send_nowait)

    def unlink_player(self) -> None:
        """Unlink this session from its player object."""
        if self.player:
            self.player.clear_msg_handler()
            self.player = None
        self.state = SessionState.CONNECTED

    def __repr__(self) -> str:
        player_name = self.player.name if self.player else "None"
        return f"<Session {self.id[:8]}... state={self.state.name} player={player_name}>"


class SessionManager:
    """
    Manages all active sessions.

    Provides lookup by session ID, player, and address.
    Handles session lifecycle events.
    """

    __slots__ = (
        '_sessions', '_by_player', '_by_address',
        '_on_connect', '_on_disconnect', '_pending_destroys',
    )

    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._by_player: dict[str, Session] = {}  # player.id -> session
        self._by_address: dict[str, list[Session]] = {}  # address -> sessions

        # Callbacks
        self._on_connect: list[Callable[[Session], Awaitable[None]]] = []
        self._on_disconnect: list[Callable[[Session], Awaitable[None]]] = []

        # Strong refs to in-flight destroy tasks — a bare create_task() can
        # be garbage-collected before it runs.
        self._pending_destroys: set[asyncio.Task] = set()

    def on_connect(self, callback: Callable[[Session], Awaitable[None]]) -> None:
        """Register a callback for new connections."""
        self._on_connect.append(callback)

    def on_disconnect(self, callback: Callable[[Session], Awaitable[None]]) -> None:
        """Register a callback for disconnections."""
        self._on_disconnect.append(callback)

    async def _auto_flush(self, session: Session) -> None:
        """
        Flush session output with error logging.

        Called automatically after connection callbacks to ensure welcome
        messages are sent immediately. Protocol-agnostic - works with any
        session that has a writer configured.
        """
        try:
            await session.flush_output()
        except Exception as e:
            logger.error(
                f"Failed to flush output for session {session.id} "
                f"({session.protocol} from {session.address}): {e}"
            )

    async def create_session(
        self,
        protocol: str = "unknown",
        address: str = "unknown",
        writer: Callable[[str], Awaitable[None]] | None = None,
    ) -> Session:
        """
        Create and register a new session.

        Args:
            protocol: The protocol name (telnet, websocket, etc.)
            address: The remote address string
            writer: Optional writer callback. If provided, it's set before
                    connection callbacks run, ensuring welcome messages can
                    be flushed immediately.
        """
        session = Session(protocol=protocol, address=address)

        # Set writer BEFORE callbacks so auto-flush works
        if writer is not None:
            session.set_writer(writer)

        self._sessions[session.id] = session

        # Track by address
        if address not in self._by_address:
            self._by_address[address] = []
        self._by_address[address].append(session)

        logger.info(f"Session created: {session.id} from {address} via {protocol}")

        # Notify callbacks
        for callback in self._on_connect:
            try:
                await callback(session)
            except Exception as e:
                logger.error(f"Error in connect callback: {e}")

        # Auto-flush output after connection callbacks complete.
        # This ensures welcome messages are sent immediately without
        # waiting for user input. Protocol-agnostic.
        await self._auto_flush(session)

        return session

    async def destroy_session(self, session: Session) -> None:
        """Clean up a session and hang up its connection. Idempotent."""
        if session.id not in self._sessions:
            return
        session.state = SessionState.DISCONNECTING

        # Notify callbacks
        for callback in self._on_disconnect:
            try:
                await callback(session)
            except Exception as e:
                logger.error(f"Error in disconnect callback: {e}")

        # Unlink player if any
        if session.player:
            player_id = session.player.id
            session.unlink_player()
            self._by_player.pop(player_id, None)

        # Remove from address tracking
        if session._address in self._by_address:
            sessions = self._by_address[session._address]
            if session in sessions:
                sessions.remove(session)
            if not sessions:
                del self._by_address[session._address]

        # Remove from main registry
        self._sessions.pop(session.id, None)

        # Deliver anything still queued (farewells), then hang up. Without
        # this the server depends on the client closing the socket.
        await self._auto_flush(session)
        await session.close_connection()

        logger.info(f"Session destroyed: {session.id}")

    def destroy_session_soon(self, session: Session) -> None:
        """
        Schedule a session for destruction from sync code (protocol
        callbacks). Holds a reference to the task so it can't be
        garbage-collected before running.
        """
        task = asyncio.create_task(self.destroy_session(session))
        self._pending_destroys.add(task)
        task.add_done_callback(self._pending_destroys.discard)

    def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def get_session_by_player(self, player: GameObject) -> Session | None:
        """Get the session for a player object."""
        return self._by_player.get(player.id)

    def get_sessions_by_address(self, address: str) -> list[Session]:
        """Get all sessions from an address."""
        return self._by_address.get(address, []).copy()

    def link_player_to_session(self, session: Session, player: GameObject) -> None:
        """Link a player to a session, handling any existing session."""
        # Check if player already has a session
        old_session = self._by_player.get(player.id)
        if old_session and old_session != session:
            # Disconnect old session
            old_session.unlink_player()

        session.link_player(player)
        self._by_player[player.id] = session

    def all_sessions(self) -> list[Session]:
        """Get all active sessions."""
        return list(self._sessions.values())

    def playing_sessions(self) -> list[Session]:
        """Get all sessions with linked players."""
        return [s for s in self._sessions.values() if s.state == SessionState.PLAYING]

    def session_count(self) -> int:
        """Get the number of active sessions."""
        return len(self._sessions)

    def player_count(self) -> int:
        """Get the number of sessions with linked players."""
        return len(self._by_player)

    async def broadcast(self, message: str, exclude: Session | None = None) -> None:
        """Send a message to all playing sessions."""
        for session in self.playing_sessions():
            if session != exclude:
                await session.send(message)

    async def broadcast_to_room(
        self,
        room: GameObject,
        message: str,
        exclude: GameObject | None = None,
    ) -> None:
        """Send a message to all players in a room."""
        for obj in room.contents:
            if obj != exclude and obj.has_tag('player'):
                session = self.get_session_by_player(obj)
                if session:
                    await session.send(message)
