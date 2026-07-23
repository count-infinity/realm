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


# Heredoc (multi-line input) delimiters — game settings (HEREDOC_OPEN /
# HEREDOC_CLOSE in config.py). A command line ending in the OPEN sigil starts
# collecting; a line that is exactly the CLOSE sigil ends it, and the whole
# block is dispatched as ONE command with its newlines and indentation intact
# (so a builder can @set a readable multi-line script instead of a `;`
# one-liner). Open and close default to the same ''' but may be distinct
# (<<< ... >>>) for worlds whose scripts use ''' internally. Ambient module
# state, wired at server construction like the other sigils.
DEFAULT_HEREDOC_OPEN = "'''"
DEFAULT_HEREDOC_CLOSE = "'''"
_heredoc_open = DEFAULT_HEREDOC_OPEN
_heredoc_close = DEFAULT_HEREDOC_CLOSE

#: Discards a runaway/mistyped block instead of dispatching it.
HEREDOC_ABORT = "@abort"
#: Backstop against an unterminated block growing without bound.
HEREDOC_MAX_LINES = 1000


def set_heredoc_sigils(open_sigil: str = DEFAULT_HEREDOC_OPEN,
                       close_sigil: str = DEFAULT_HEREDOC_CLOSE) -> None:
    """Install the multi-line-input delimiters (game config). Each is 1-16
    non-alphanumeric, non-space characters (an alnum sigil would swallow
    ordinary commands ending in that word). Open and close may be equal
    (``''' ... '''``) or distinct (``<<< ... >>>``). A bad value raises at
    boot, not mid-input."""
    global _heredoc_open, _heredoc_close
    for name, sig in (("open", str(open_sigil)), ("close", str(close_sigil))):
        if (not sig or len(sig) > 16
                or any(c.isalnum() or c.isspace() for c in sig)):
            raise ValueError(
                f"heredoc {name} sigil must be 1-16 non-alphanumeric, "
                f"non-space characters (got {sig!r})")
    _heredoc_open = str(open_sigil)
    _heredoc_close = str(close_sigil)


def get_heredoc_sigils() -> tuple[str, str]:
    return _heredoc_open, _heredoc_close


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
        '_input_task',
        '_output_queue',
        '_writer',
        '_oob_writer',
        'oob_supports',
        '_closer',
        '_protocol',
        '_address',
        '_created_at',
        '_last_activity',
        '_account_name',
        '_data',
        'input_handler',
        '_prompt_future',
        '_heredoc',
        '_flush_tasks',
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
        self._input_task: asyncio.Task | None = None
        self._output_queue: asyncio.Queue[str] = asyncio.Queue()
        self._writer: Callable[[str], Awaitable[None]] | None = None
        # Out-of-band channel (GMCP on telnet, JSON envelope on
        # websocket). None = client never negotiated structured data.
        self._oob_writer: Callable[[str, dict], None] | None = None
        self.oob_supports: dict = {}
        self._closer: Callable[[], Any] | None = None

        # Active input capture: an async (session, line) -> bool handler.
        # When set, incoming lines route here (a prompt/wizard) instead of
        # the command dispatcher. None = normal command mode.
        self.input_handler: Callable[..., Awaitable[bool]] | None = None
        self._prompt_future: Any = None
        # Multi-line (heredoc) accumulation state: None in normal mode, else
        # {'head': <command prefix>, 'body': [<raw lines>]} while collecting.
        self._heredoc: dict[str, Any] | None = None
        # Fire-and-forget flush tasks (see _flush_soon) kept referenced until
        # done so they aren't GC'd mid-flight.
        self._flush_tasks: set[asyncio.Task] = set()

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

    def set_oob_writer(self, writer: Callable[[str, dict], None] | None) -> None:
        """Install the protocol's structured-data sender (GMCP etc.)."""
        self._oob_writer = writer

    def send_oob(self, package: str, data: dict) -> None:
        """
        Send a structured out-of-band message (fire-and-forget). A
        no-op for clients that never negotiated an OOB channel.
        """
        if self._oob_writer is not None:
            try:
                self._oob_writer(package, data)
            except Exception:
                pass  # a client hiccup must never break game flow

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
        """Receive a command from the player. (For pump-less custom
        protocols that drain the queue themselves — never mix with
        ``start_input_pump``.)"""
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

    # --- The protocol-agnostic input funnel ---
    #
    # A protocol adapter's whole input job is: decode bytes however its
    # wire format demands, then call submit_input() with a text line —
    # the COMMON REPRESENTATION every layer above this one sees. A
    # per-session pump drains the queue through the server's input sink
    # (prompt capture → chargen → dispatcher), one line at a time, so
    # every protocol gets identical ordering and backpressure semantics.

    def submit_input(self, raw: str) -> None:
        """Normalize a decoded line of client input and queue it for the
        pump. The single entry point protocol adapters should use.

        Multi-line input: a command line ending in the heredoc OPEN sigil
        (``'''`` by default) starts collecting; the lines that follow
        accumulate **with their indentation intact** until a line that is
        exactly the CLOSE sigil, at which point the whole block is emitted as
        ONE command — so a builder can ``@set`` a readable multi-line script
        instead of a semicolon one-liner. ``@abort`` on its own line cancels
        the block. Only active in normal command mode (never during a
        prompt/wizard or login).
        """
        # Collecting a heredoc body: preserve each line verbatim (no strip,
        # so Python indentation survives). Only the terminators are matched.
        if self._heredoc is not None:
            body_line = raw.rstrip("\r\n")
            marker = body_line.strip()
            if marker == _heredoc_close:
                head, body = self._heredoc['head'], self._heredoc['body']
                self._heredoc = None
                self.touch()
                self._queue_input(head + "\n".join(body))
                return
            if marker == HEREDOC_ABORT:
                self._heredoc = None
                self.send_nowait("Multi-line input aborted.")
                self._flush_soon()
                return
            if len(self._heredoc['body']) >= HEREDOC_MAX_LINES:
                self._heredoc = None
                self.send_nowait(
                    f"Multi-line input exceeded {HEREDOC_MAX_LINES} lines "
                    "— aborted.")
                self._flush_soon()
                return
            self._heredoc['body'].append(body_line)
            self.touch()
            return

        line = raw.strip()
        if not line:
            return

        # Open a heredoc? A single command line ending in the OPEN sigil, and
        # only in normal command mode (a pending prompt/wizard or login owns
        # the input instead). The '\n' guard skips a whole multi-line paste
        # arriving as one websocket message.
        if (_heredoc_open and self.player is not None
                and self._prompt_future is None and self.input_handler is None
                and "\n" not in line and line.endswith(_heredoc_open)):
            self._heredoc = {'head': line[:-len(_heredoc_open)], 'body': []}
            self.touch()
            self.send_nowait(
                f"Multi-line input — end with a line of {_heredoc_close}, "
                f"or {HEREDOC_ABORT} to cancel.")
            self._flush_soon()
            return

        self.touch()
        self._queue_input(line)

    def _flush_soon(self) -> None:
        """Flush queued output now, from a sync context, if we're inside the
        event loop. Used for messages emitted mid-heredoc — a collecting line
        dispatches nothing, so the normal post-command flush never runs and
        the notice would otherwise sit in the queue until the block closes."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # no loop (e.g. a direct unit-test call) — nothing to do
        task = loop.create_task(self.flush_output())
        self._flush_tasks.add(task)
        task.add_done_callback(self._flush_tasks.discard)

    def _queue_input(self, line: str) -> None:
        try:
            self._input_queue.put_nowait(line)
        except asyncio.QueueFull:
            logger.warning(f"Session {self.id}: input queue full, dropping command")

    def start_input_pump(
        self, sink: Callable[[Session, str], Awaitable[None]],
    ) -> None:
        """Start the pump draining this session's input through ``sink``
        — one line at a time, in arrival order. Idempotent."""
        if self._input_task is not None and not self._input_task.done():
            return
        self._input_task = asyncio.create_task(self._pump_input(sink))

    def stop_input_pump(self) -> None:
        """Cancel the input pump (session teardown)."""
        if self._input_task is not None:
            self._input_task.cancel()
            self._input_task = None

    async def _pump_input(
        self, sink: Callable[[Session, str], Awaitable[None]],
    ) -> None:
        while True:
            line = await self._input_queue.get()
            try:
                await sink(self, line)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    f"Session {self.id}: error processing input {line!r}")

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

    # --- Interactive prompts (wizards) ---

    #: commands that still work while a prompt is pending (escape hatches).
    DEFAULT_ALLOW = frozenset({'help', 'quit', 'exit'})

    async def prompt(
        self,
        text: str,
        *,
        choices: list[str] | None = None,
        allow: frozenset[str] | None = None,
        allow_abort: bool = True,
    ) -> str | None:
        """
        Ask the player a question and await their next line — the async
        wizard primitive. Returns the line, or None if aborted.

        ``choices`` re-prompts until the answer is one of them (prefix
        match). ``allow`` names commands that still pass through to the
        dispatcher while pending (default help/quit/exit); ``abort``
        always cancels unless ``allow_abort=False``.
        """
        import asyncio as _asyncio

        allowed = self.DEFAULT_ALLOW if allow is None else allow
        future: _asyncio.Future = _asyncio.get_event_loop().create_future()
        self._prompt_future = future

        async def handler(_session, line: str) -> bool:
            word = line.split()[0].lower() if line.split() else ""
            if allow_abort and word == 'abort':
                self._end_prompt(None)
                return True
            if word in allowed:
                return False  # pass through to the dispatcher; prompt stays
            if choices is not None:
                matches = [c for c in choices if c.lower().startswith(line.lower())]
                if len(matches) != 1:
                    await self.send(
                        f"Please answer one of: {', '.join(choices)} "
                        f"(or 'abort').")
                    return True
                line = matches[0]
            self._end_prompt(line)
            return True

        self.input_handler = handler
        await self.send(text)
        return await future

    def _end_prompt(self, value) -> None:
        """Resolve the pending prompt future and release capture."""
        self.input_handler = None
        fut, self._prompt_future = self._prompt_future, None
        if fut is not None and not fut.done():
            fut.set_result(value)

    async def confirm(self, text: str) -> bool:
        """Yes/no prompt. 'abort' counts as no."""
        answer = await self.prompt(f"{text} (yes/no)", choices=["yes", "no"])
        return answer == "yes"

    async def choose(self, text: str, options: list[str]) -> str | None:
        """Numbered menu; returns the chosen option (or None if aborted)."""
        menu = [text] + [f"  {i}. {o}" for i, o in enumerate(options, 1)]
        while True:
            raw = await self.prompt("\n".join(menu))
            if raw is None:
                return None
            raw = raw.strip()
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                return options[int(raw) - 1]
            hits = [o for o in options if o.lower().startswith(raw.lower())]
            if len(hits) == 1:
                return hits[0]
            await self.send("Pick a number or name from the list (or 'abort').")

    def cancel_prompt(self) -> None:
        """Drop any active input capture and unblock its task (disconnect)."""
        self._end_prompt(None)

    def link_player(self, player: GameObject) -> None:
        """Link this session to a player object and wire output delivery."""
        self.player = player
        self.state = SessionState.PLAYING
        # Route player.msg() text through this session's output queue.
        player.set_msg_handler(self.send_nowait)
        player.set_oob_handler(self.send_oob)

    def unlink_player(self) -> None:
        """Unlink this session from its player object."""
        if self.player:
            self.player.clear_msg_handler()
            self.player.clear_oob_handler()
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
        '_input_sink',
    )

    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._by_player: dict[str, Session] = {}  # player.id -> session
        self._by_address: dict[str, list[Session]] = {}  # address -> sessions

        # The server's one input funnel (prompt capture → chargen →
        # dispatcher). When set, every created session gets an input
        # pump draining submit_input() lines through it.
        self._input_sink: Callable[[Session, str], Awaitable[None]] | None = None

        # Callbacks
        self._on_connect: list[Callable[[Session], Awaitable[None]]] = []
        self._on_disconnect: list[Callable[[Session], Awaitable[None]]] = []

        # Strong refs to in-flight destroy tasks — a bare create_task() can
        # be garbage-collected before it runs.
        self._pending_destroys: set[asyncio.Task] = set()

    def set_input_sink(
        self, sink: Callable[[Session, str], Awaitable[None]] | None,
    ) -> None:
        """Install the server's input funnel. Sessions created after
        this get a pump routing ``submit_input`` lines through it."""
        self._input_sink = sink

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

        if self._input_sink is not None:
            session.start_input_pump(self._input_sink)

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
        session.stop_input_pump()
        session.cancel_prompt()  # resolve any awaiting wizard so its task ends

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

    def unlink_player_from_session(self, session: Session) -> None:
        """
        Return a session to the pre-login state, dropping the player↔session
        mapping as well as the link itself.

        The exact inverse of :meth:`link_player_to_session`, and distinct from
        :meth:`destroy_session`: the **connection stays open**, so the client
        lands back on the connection screen and may ``connect`` again. Used by
        the ``logout`` command. Leaving the ``_by_player`` entry behind would
        strand a stale session — ``get_session_by_player`` would hand it to
        ``@boot``, and a later re-login would unlink the wrong session.
        """
        player = session.player
        if player is not None:
            self._by_player.pop(player.id, None)
        session.unlink_player()

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
