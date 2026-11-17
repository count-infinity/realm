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
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from realm.core.options import get_option
from realm.core.pools import damage_pool, declared_pools, pool_get, pool_max, vital_pool
from realm.core.world import setting

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)

#: The session clock (seconds, monotonic): idle time, link-dead waits and
#: the flood bucket read it, so a test can move time by replacing it.
clock = time.monotonic

#: Why a session closed (``Session.close_reason``): on purpose (quit, boot,
#: idle timeout, shutdown), or because the connection dropped under it.
CLOSED = "closed"
LINK_LOST = "link_lost"

FLOOD_WARNING = "You are sending commands too fast; the extra ones were dropped."

#: The prompt while long output is held (``Session.send_paged``).
PAGER_PROMPT = "[more: enter, b back, q quit]"


# Heredoc (multi-line input) delimiters — game settings (HEREDOC_OPEN /
# HEREDOC_CLOSE in config.py). A command line ending in the OPEN sigil starts
# collecting; a line that is exactly the CLOSE sigil ends it, and the whole
# block is dispatched as ONE command with its newlines and indentation intact
# (so a builder can @set a readable multi-line script instead of a `;`
# one-liner). Open and close default to the same ''' but may be distinct
# (<<< ... >>>) for worlds whose scripts use ''' internally.

#: Discards a runaway/mistyped block instead of dispatching it.
HEREDOC_ABORT = "@abort"
#: Backstop against an unterminated block growing without bound.
HEREDOC_MAX_LINES = 1000


class SessionState(Enum):
    """States a session can be in."""

    CONNECTED = auto()      # Just connected, not authenticated
    AUTHENTICATING = auto() # In login/character select flow
    PLAYING = auto()        # In-game, has a player object
    DISCONNECTING = auto()  # Being cleaned up


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
        'account',
        '_data',
        'input_handler',
        '_prompt_future',
        '_prompt_writer',
        '_prompt_shown',
        '_heredoc',
        '_flush_tasks',
        'close_reason',
        'snoopers',
        '_bucket',
        '_on_flood',
        '_pager',
        'raw_lines',
        '_vitals_sent',
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
        #: True while the input handler wants every line as typed: blank
        #: lines and leading spaces kept (the line editor).
        self.raw_lines = False
        # Long output being shown a page at a time (send_paged), or None.
        self._pager: _Pager | None = None
        # Where the game's prompt goes (the protocol's own framing: telnet
        # ends it with EOR/GA). None: this connection shows no prompt.
        self._prompt_writer: Callable[[str], None] | None = None
        # True while the prompt is the last thing this connection was
        # written and no line of input has come in since: a command that
        # flushed its own output (an announcement) already ended with it.
        self._prompt_shown = False
        # The last Char.Vitals sent with a prompt (write_prompt sends it again
        # only when a pool changed).
        self._vitals_sent: dict[str, int] | None = None
        # Multi-line (heredoc) accumulation state: None in normal mode, else
        # {'head': <command prefix>, 'body': [<raw lines>]} while collecting.
        self._heredoc: dict[str, Any] | None = None
        # Fire-and-forget flush tasks (see _flush_soon) kept referenced until
        # done so they aren't GC'd mid-flight.
        self._flush_tasks: set[asyncio.Task] = set()

        self._protocol = protocol
        self._address = address
        self._created_at = clock()
        self._last_activity = self._created_at
        #: set by ``SessionManager.destroy_session``: CLOSED or LINK_LOST
        self.close_reason: str | None = None
        #: sessions that see everything this one is sent (``@snoop``)
        self.snoopers: list[Session] = []
        # The flood limiter: a session a protocol connected
        # (``SessionManager.create_session``) gets one; a test harness's
        # adopted session does not.
        self._bucket: TokenBucket | None = None
        self._on_flood: Callable[[], None] | None = None
        #: the account logged in on this connection (the ``accounts``
        #: feature): set at ``connect``, kept while the player picks or
        #: switches characters, cleared at ``logout``
        self.account: GameObject | None = None
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
        return clock() - self._last_activity

    @property
    def connected_time(self) -> float:
        """Seconds since connection."""
        return clock() - self._created_at

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

    def set_prompt_writer(self, writer: Callable[[str], None] | None) -> None:
        """Where the game's prompt is written (sync; the protocol frames it)."""
        self._prompt_writer = writer

    def write_prompt(self) -> None:
        """Write the game's prompt for this session's player, unless there
        is no player yet, a softcode prompt or wizard is waiting for an
        answer (its own question is the prompt), or the game shows none.
        While long output is held, the prompt is the pager's.

        A client with an out-of-band channel is sent ``Char.Vitals`` (every
        pool the player has, ``name`` and ``max_name``) beside the prompt,
        whenever it differs from the last one sent: the browser client's
        bars, and any GMCP client's."""
        if self.player is not None and self._oob_writer is not None:
            self._send_vitals(self.player)
        if self._prompt_writer is not None and self._pager is not None:
            self._prompt_writer(PAGER_PROMPT)
            self._prompt_shown = True
            return
        if (self._prompt_writer is None or self.player is None
                or self.input_handler is not None or self._prompt_future is not None):
            return
        from realm.core.world import find_world
        world = find_world()
        renderer = world.prompt_renderer if world is not None else None
        if renderer is None:
            return
        try:
            text = renderer(self.player)
        except Exception:
            logger.exception(f"Session {self.id}: prompt renderer failed")
            return
        if text:
            self._prompt_writer(str(text))
            self._prompt_shown = True

    def input_arrived(self) -> None:
        """A line of input came in: the prompt on the screen is answered,
        so the end of the command it runs writes a fresh one."""
        self._prompt_shown = False

    def _send_vitals(self, player: GameObject) -> None:
        vitals = vitals_of(player)
        if vitals and vitals != self._vitals_sent:
            self._vitals_sent = vitals
            self.send_oob("Char.Vitals", dict(vitals))

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
        self._last_activity = clock()

    async def send(self, message: str) -> None:
        """Send a message to the player."""
        await self._output_queue.put(message)
        self._echo(message)

    def send_nowait(self, message: str) -> None:
        """Send a message without waiting (for sync contexts)."""
        try:
            self._output_queue.put_nowait(message)
        except asyncio.QueueFull:
            logger.warning(f"Session {self.id}: output queue full, dropping message")
        self._echo(message)

    def _echo(self, message: str) -> None:
        """Copy what this session is sent to its snoopers, each line marked
        with whose it is."""
        if not self.snoopers:
            return
        who = self.player.name if self.player is not None else self.address
        marked = "\n".join(f"[{who}] {line}" for line in str(message).split("\n"))
        for snooper in self.snoopers:
            snooper.send_nowait(marked)

    def reaches(self, other: Session) -> bool:
        """Whether what this session is sent ends up at ``other``, directly
        or through a chain of snoopers (a snoop that would loop is refused)."""
        seen: set[str] = set()
        todo = [self]
        while todo:
            session = todo.pop()
            if session is other:
                return True
            if session.id in seen:
                continue
            seen.add(session.id)
            todo.extend(session.snoopers)
        return False

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
            if marker == setting("HEREDOC_CLOSE"):
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

        # The line editor takes every line as typed: a blank line is a
        # blank line of text, and leading spaces are indentation.
        if self.raw_lines:
            self.touch()
            self._queue_input(raw.rstrip("\r\n"))
            return

        line = raw.strip()
        if not line:
            # A bare enter turns the pager's page; otherwise it is nothing.
            if self._pager is not None:
                self.touch()
                self._queue_input("")
            return

        # Open a heredoc? A single command line ending in the OPEN sigil, and
        # only in normal command mode (a pending prompt/wizard or login owns
        # the input instead). The '\n' guard skips a whole multi-line paste
        # arriving as one websocket message.
        opener = setting("HEREDOC_OPEN")
        if (self.player is not None and self._pager is None
                and self._prompt_future is None and self.input_handler is None
                and "\n" not in line and line.endswith(opener)):
            self._heredoc = {'head': line[:-len(opener)], 'body': []}
            self.touch()
            self.send_nowait(
                f"Multi-line input — end with a line of {setting('HEREDOC_CLOSE')}, "
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

    def limit_input(self, on_flood: Callable[[], None] | None) -> None:
        """Rate-limit this session's input (``COMMAND_RATE``,
        ``COMMAND_BURST``); ``on_flood`` runs once it has stayed over the
        limit for ``FLOOD_DISCONNECT_SECONDS``."""
        self._bucket = TokenBucket()
        self._on_flood = on_flood

    def _admit(self) -> bool:
        """The flood check on one line of input: True to queue it."""
        if self._bucket is None:
            return True
        verdict = self._bucket.take(clock())
        if verdict is TokenBucket.WARN:
            self.send_nowait(FLOOD_WARNING)
            self._flush_soon()
        elif verdict is TokenBucket.CLOSE and self._on_flood is not None:
            on_flood, self._on_flood = self._on_flood, None
            on_flood()
        return verdict is TokenBucket.OK

    def _queue_input(self, line: str) -> None:
        if not self._admit():
            return
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
        """Stop the input pump (session teardown). Called from inside the
        pump (``quit`` destroys its own session), it is not cancelled, which
        would cancel the teardown it is running: it ends after that line."""
        task, self._input_task = self._input_task, None
        if task is not None and task is not asyncio.current_task():
            task.cancel()

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
            if self._input_task is not asyncio.current_task():
                return                            # stopped by the line it ran

    async def flush_output(self, *, prompt: bool = False) -> None:
        """Flush all pending output to the writer, then the prompt: after
        any output, or with ``prompt`` (a command that printed nothing still
        ends with one) unless the prompt is already the last thing written
        since the input (a command whose output was flushed as it went,
        such as an announcement to everyone, ends with one prompt)."""
        if self._writer is None:
            return

        wrote = False
        while not self._output_queue.empty():
            try:
                message = self._output_queue.get_nowait()
                await self._writer(message)
                wrote = True
                self._prompt_shown = False
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                logger.error(f"Session {self.id}: error writing: {e}")
                break
        if wrote or (prompt and not self._prompt_shown):
            self.write_prompt()

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
        """Drop any active input capture (a prompt, the line editor, held
        pages) and unblock its task (disconnect, logout)."""
        self._end_prompt(None)
        self.raw_lines = False
        self._pager = None

    # --- The pager (MUD_PLAN 10.1) ---

    def page_length(self) -> int:
        """Lines on one screen: the player's ``pagelength`` option, else the
        height the client reported (NAWS, a web client's resize), else
        ``PAGE_LENGTH``. 0 means output is never held."""
        if self.player is not None:
            own = get_option(self.player, "pagelength")
            if own is not None:
                return max(0, int(own))
        height = self.get_data("terminal_height")
        if height:
            return max(0, int(height))
        return max(0, int(setting("PAGE_LENGTH")))

    @property
    def paging(self) -> bool:
        """Whether long output is being held a page at a time."""
        return self._pager is not None

    def send_paged(self, text: str) -> None:
        """Send ``text``, a screenful at a time when it is longer than one
        screen (``page_length``): the rest is held, the prompt becomes
        ``PAGER_PROMPT``, and the next line of input turns the page (enter),
        goes back (``b``) or stops (``q``); anything else stops paging and is
        an ordinary command."""
        lines = str(text).split("\n")
        height = self.page_length()
        if height <= 0 or len(lines) <= height:
            self.send_nowait(str(text))
            return
        # One line of the screen is the pager's prompt.
        self._pager = _Pager(lines, max(1, height - 1))
        self._show_page()

    def _show_page(self) -> None:
        pager = self._pager
        if pager is None:
            return
        self.send_nowait("\n".join(pager.lines[pager.top:pager.top + pager.size]))
        if pager.top + pager.size >= len(pager.lines):
            self._pager = None                  # that was the last page
        elif self._prompt_writer is None:
            # A connection with no prompt line (a test session, a bare
            # protocol): the pager's prompt is a line of output.
            self.send_nowait(PAGER_PROMPT)

    def page_input(self, line: str) -> bool:
        """A line of input while paging: True when the pager used it (enter,
        ``b``, ``q``); False when paging stopped and the line is a command."""
        pager = self._pager
        if pager is None:
            return False
        word = line.strip().lower()
        if word == "":
            pager.top += pager.size
        elif word == "b":
            pager.top = max(0, pager.top - pager.size)
        elif word == "q":
            self._pager = None
            return True
        else:
            self._pager = None
            return False
        self._show_page()
        return True

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


class _Pager:
    """Long output held by ``Session.send_paged``: its lines, the page size,
    and the first line of the page on screen."""

    __slots__ = ("lines", "size", "top")

    def __init__(self, lines: list[str], size: int) -> None:
        self.lines = lines
        self.size = size
        self.top = 0


class TokenBucket:
    """Flood control for one session (capability audit G13).

    The bucket holds up to ``COMMAND_BURST`` tokens and refills at
    ``COMMAND_RATE`` a second; each line of input takes one. A line that
    finds the bucket empty is dropped. The first drop of a flood warns; a
    flood lasts until the bucket is full again, and one that lasts
    ``FLOOD_DISCONNECT_SECONDS`` (0: never) closes the session.
    ``COMMAND_RATE`` 0 turns the limit off.
    """

    OK, DROP, WARN, CLOSE = "ok", "drop", "warn", "close"

    __slots__ = ("tokens", "updated", "flooding_since")

    def __init__(self) -> None:
        self.tokens: float | None = None
        self.updated = 0.0
        self.flooding_since: float | None = None

    def take(self, now: float) -> str:
        rate = float(setting("COMMAND_RATE"))
        if rate <= 0:
            return self.OK
        burst = float(setting("COMMAND_BURST"))
        if self.tokens is None:
            self.tokens = burst
        else:
            self.tokens = min(burst, self.tokens + (now - self.updated) * rate)
        self.updated = now
        if self.tokens >= burst:
            self.flooding_since = None                  # slowed down: the flood is over
        if self.tokens >= 1:
            self.tokens -= 1
            verdict = self.OK
        elif self.flooding_since is None:
            self.flooding_since = now
            return self.WARN
        else:
            verdict = self.DROP
        limit = float(setting("FLOOD_DISCONNECT_SECONDS"))
        if self.flooding_since is not None and limit > 0 and now - self.flooding_since >= limit:
            return self.CLOSE
        return verdict


def vitals_of(player: GameObject) -> dict[str, int]:
    """``Char.Vitals`` for ``player``: each pool it has (its declared pools,
    then its damage and vital pools) as ``name``, and ``max_name`` when the
    pool has a maximum."""
    names = list(declared_pools(player))
    for name in (damage_pool(player), vital_pool(player)):
        if name is not None and name not in names:
            names.append(name)
    vitals: dict[str, int] = {}
    for name in names:
        value = pool_get(player, name)
        if value is None:
            continue
        vitals[name] = value
        maximum = pool_max(player, name)
        if maximum is not None:
            vitals[f"max_{name}"] = maximum
    return vitals


def format_peer_address(peername: Any) -> str:
    """``host:port`` from a transport's peername tuple, or ``unknown``."""
    return f"{peername[0]}:{peername[1]}" if peername else "unknown"


async def connect_session(
    session_manager: SessionManager,
    *,
    protocol: str,
    address: str,
    writer: Callable[[str], Awaitable[None]],
    closer: Callable[[], Any],
) -> Session:
    """The one connect ritual every protocol adapter performs.

    ``writer`` being a REQUIRED argument is the point: the writer must
    exist before the session does, because ``create_session`` fires
    connect callbacks that send the welcome screen and auto-flush — a
    session created without its writer silently swallows those first
    bytes. Routing adapters through here makes that ordering structural
    instead of a comment each adapter has to repeat.
    """
    session = await session_manager.create_session(
        protocol=protocol,
        address=address,
        writer=writer,
    )
    session.set_closer(closer)
    logger.info(f"{protocol} connection from {address}")
    return session


class SessionManager:
    """
    Manages all active sessions.

    Provides lookup by session ID, player, and address.
    Handles session lifecycle events.
    """

    __slots__ = (
        '_sessions', '_by_player', '_by_address',
        '_on_connect', '_on_disconnect', '_pending_destroys',
        '_input_sink', '_linkdead',
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

        # Characters whose connection dropped and who wait in the room for
        # it to come back: player id -> (player, when the link was lost).
        self._linkdead: dict[str, tuple[GameObject, float]] = {}

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
        session.limit_input(lambda: self._flooded(session))

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

    def _flooded(self, session: Session) -> None:
        """A session that stayed over the input limit: logged and closed."""
        logger.warning(f"Flood: closing session {session.id} from {session.address}"
                       + (f" ({session.player.name})" if session.player is not None else ""))
        session.send_nowait("You sent too many commands too fast. Goodbye.")
        self.destroy_session_soon(session)

    async def connection_lost(self, session: Session) -> None:
        """The client's connection dropped (no ``quit``): what protocol
        adapters call. The session closes with ``close_reason`` LINK_LOST,
        so its character may wait in the room as link-dead."""
        await self.destroy_session(session, reason=LINK_LOST)

    async def destroy_session(self, session: Session, *, reason: str = CLOSED) -> None:
        """Clean up a session and hang up its connection. Idempotent.
        ``reason`` is CLOSED (on purpose) or LINK_LOST (see
        ``connection_lost``); disconnect callbacks read it as
        ``session.close_reason``."""
        if session.id not in self._sessions:
            return
        session.close_reason = reason
        session.state = SessionState.DISCONNECTING
        session.stop_input_pump()
        session.cancel_prompt()  # resolve any awaiting wizard so its task ends

        # Notify callbacks
        for callback in self._on_disconnect:
            try:
                await callback(session)
            except Exception as e:
                logger.error(f"Error in disconnect callback: {e}")

        # Nobody snoops a closed session, and it snoops nobody.
        for other in self._sessions.values():
            if session in other.snoopers:
                other.snoopers.remove(session)
        if session.snoopers:
            who = session.player.name if session.player is not None else session.address
            for snooper in session.snoopers:
                snooper.send_nowait(f"[Snoop ended: {who} disconnected.]")
            session.snoopers.clear()

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

    def destroy_session_soon(self, session: Session, *, reason: str = CLOSED) -> None:
        """
        Schedule a session for destruction from sync code (protocol
        callbacks). Holds a reference to the task so it can't be
        garbage-collected before running.
        """
        task = asyncio.create_task(self.destroy_session(session, reason=reason))
        self._pending_destroys.add(task)
        task.add_done_callback(self._pending_destroys.discard)

    def adopt(self, session: Session) -> Session:
        """Register a session made elsewhere (an in-process test harness),
        with no connection callbacks or input pump: it is then found by
        ``all_sessions`` and, once linked, ``get_session_by_player``."""
        self._sessions[session.id] = session
        self._by_address.setdefault(session.address, []).append(session)
        return session

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
        self.clear_linkdead(player)

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

    # --- link-dead characters ---

    def mark_linkdead(self, player: GameObject) -> None:
        """``player``'s connection dropped: it waits in the room, tagged
        ``linkdead``, until it reconnects or the wait runs out."""
        player.add_tag("linkdead")
        self._linkdead[player.id] = (player, clock())

    def clear_linkdead(self, player: GameObject) -> None:
        """``player`` is no longer waiting (reconnected, or the wait ended)."""
        if self._linkdead.pop(player.id, None) is not None or player.has_tag("linkdead"):
            player.remove_tag("linkdead")

    def linkdead(self) -> list[tuple[GameObject, float]]:
        """Every link-dead character, with the clock time its link was lost."""
        return list(self._linkdead.values())

    def online_players(self) -> list[GameObject]:
        """Every character in play, in connection order."""
        return [s.player for s in self._sessions.values() if s.player is not None]

    def is_online(self, player: GameObject) -> bool:
        return player.id in self._by_player

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
            if obj != exclude and obj.is_player:
                session = self.get_session_by_player(obj)
                if session:
                    await session.send(message)


def online_players() -> list[GameObject]:
    """The current world's characters in play (none without a world)."""
    from realm.core.world import find_world
    world = find_world()
    return world.sessions.online_players() if world is not None and world.sessions else []


def is_online(player: GameObject) -> bool:
    """Whether ``player`` is in play in the current world."""
    from realm.core.world import find_world
    world = find_world()
    return world is not None and world.sessions is not None and world.sessions.is_online(player)
