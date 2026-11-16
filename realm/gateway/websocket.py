"""
WebSocket protocol handler for REALM.

Provides a WebSocket interface for web clients using aiohttp, and, with
``WEB_CLIENT``, serves the browser client (``realm/web/index.html``) at ``/``.
"""

from __future__ import annotations

import asyncio
import html
import importlib.resources
import json
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from realm.core.markup import marker, parse, recolor, strip, undecorate
from realm.core.options import display_for

try:
    from aiohttp import WSMsgType, web
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    web = None  # type: ignore
    WSMsgType = None  # type: ignore

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.gateway.session import Session, SessionManager

logger = logging.getLogger(__name__)

#: Where the browser client's page is kept inside the ``realm`` package.
CLIENT_PAGE = ("web", "index.html")

#: The placeholder in the page that ``WebSocketServer`` fills with GAME_NAME.
GAME_NAME_MARK = "{{GAME_NAME}}"


def client_page() -> str:
    """The browser client: one HTML page, its CSS and JavaScript inline."""
    return importlib.resources.files("realm").joinpath(*CLIENT_PAGE).read_text(encoding="utf-8")


def styled_for(player: GameObject | None, message: str) -> tuple[str, list[list[str]] | None]:
    """``message`` as one player's web client gets it, by their display
    options (``realm.core.options.display_for``): the plain text, and the
    styled segments ``[[style key, text], ...]`` for the client to draw, or
    None when the text is to be shown plain (no markup, ``color`` off, or
    ``screenreader``, which also drops lines drawn only for looks)."""
    display = display_for(player)
    if display.undecorate:
        message = undecorate(message)
    if display.plain or marker() not in message:
        return strip(message), None
    segments = [[recolor(style, display.palette).key(), seg] for style, seg in parse(message)]
    return "".join(seg for _key, seg in segments), segments


def make_ws_writer(ws: Any, player: Callable[[], GameObject | None]) -> callable:
    """The one text writer for a WebSocket client, used from the very
    first byte (the welcome screen included). Markup ships as structured
    segments — the client styles them (no ANSI-to-HTML archaeology);
    plain text stays plain (a ``{'type': 'text'}`` frame when it starts
    with ``{``, which only JSON frames do). ``player()`` is whoever the connection is
    playing now (None before login), whose display options apply."""

    async def write_to_client(message: str) -> None:
        if ws.closed:
            return
        try:
            text, segments = styled_for(player(), message)
            if message and not text:
                return                      # nothing left once decoration went
            if segments is None and not text.startswith('{'):
                await ws.send_str(text)
            elif segments is None:
                # A string frame starting with '{' is always JSON, so text
                # cannot pass for a frame (a prompt, vitals) in the client.
                await ws.send_json({'type': 'text', 'text': text})
            else:
                await ws.send_json({'type': 'text', 'text': text, 'segments': segments})
        except Exception as e:
            logger.error(f"Error writing to WebSocket: {e}")

    return write_to_client


class WebSocketHandler:
    """
    Handles a single WebSocket connection.

    Messages can be plain text (commands) or JSON for structured data.
    Every command line — plain or JSON-wrapped — lands in the session's
    input funnel (``submit_input``), the same common representation the
    telnet adapter produces. There is no parallel dispatch path.
    """

    def __init__(
        self,
        ws: Any,  # aiohttp WebSocketResponse
        session: Session,
        session_manager: SessionManager,
        on_command: callable,
    ):
        self.ws = ws
        self.session = session
        self.session_manager = session_manager
        self.on_command = on_command  # unused by the pump path; kept for
        #                               custom-protocol API symmetry
        self._oob_tasks: set = set()

    async def run(self) -> None:
        """Run the WebSocket handler loop."""
        # Structured push parity with telnet+GMCP: msg_oob() events
        # (Room.Info, vitals) reach web clients as {'type': 'oob'} frames.
        self.session.set_oob_writer(self._send_oob)
        # The game's prompt arrives as its own frame, so a web client can
        # show it apart from the scrollback.
        self.session.set_prompt_writer(self._send_prompt)

        try:
            async for msg in self.ws:
                if msg.type == WSMsgType.TEXT:
                    await self._handle_text(msg.data)
                elif msg.type == WSMsgType.BINARY:
                    # Treat binary as UTF-8 text
                    try:
                        text = msg.data.decode('utf-8')
                        await self._handle_text(text)
                    except Exception:
                        pass
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {self.ws.exception()}")
                    break
        finally:
            await self.session_manager.connection_lost(self.session)

    async def _handle_text(self, text: str) -> None:
        """Handle a text message from the client. The line goes to the
        session as typed: a blank one turns the pager's page, and the line
        editor keeps leading spaces (``submit_input`` trims the rest)."""
        # Try to parse as JSON first
        if text.strip().startswith('{'):
            try:
                data = json.loads(text)
                await self._handle_json(data)
                return
            except json.JSONDecodeError:
                pass

        # Plain text command → the common input representation.
        self.session.submit_input(text)

    async def _handle_json(self, data: dict[str, Any]) -> None:
        """Handle a JSON message from the client."""
        msg_type = data.get('type', 'command')

        if msg_type == 'command':
            self.session.submit_input(str(data.get('command', '')))

        elif msg_type == 'oob':
            # Inbound structured data — the websocket twin of inbound
            # GMCP (Core.Supports etc.): remember what the client told us.
            package = data.get('package')
            if package:
                self.session.oob_supports[str(package)] = data.get('data')

        elif msg_type == 'ping':
            await self._send_json({'type': 'pong'})

        elif msg_type == 'resize':
            # Window size update — same session data telnet NAWS sets.
            self.session.set_data('terminal_width', data.get('width', 80))
            self.session.set_data('terminal_height', data.get('height', 24))

    def _send_prompt(self, text: str) -> None:
        """The game's prompt as a ``{'type': 'prompt'}`` frame (scheduled),
        styled like text: ``text`` plain, plus ``segments`` when colored."""
        if self.ws.closed:
            return
        plain, segments = styled_for(self.session.player, text)
        frame: dict[str, Any] = {'type': 'prompt', 'text': plain}
        if segments is not None:
            frame['segments'] = segments
        task = asyncio.create_task(self._send_json(frame))
        self._oob_tasks.add(task)
        task.add_done_callback(self._oob_tasks.discard)

    def _send_oob(self, package: str, data: dict) -> None:
        """Outbound structured event (session.send_oob → here). Sync
        signature per the oob-writer contract; the send is scheduled."""
        if self.ws.closed:
            return
        task = asyncio.create_task(
            self._send_json({'type': 'oob', 'package': package,
                             'data': data}))
        self._oob_tasks.add(task)
        task.add_done_callback(self._oob_tasks.discard)

    async def _send_json(self, data: dict[str, Any]) -> None:
        """Send a JSON message to the client."""
        if self.ws.closed:
            return

        try:
            await self.ws.send_json(data)
        except Exception as e:
            logger.error(f"Error sending JSON to WebSocket: {e}")


class WebSocketServer:
    """
    WebSocket server using aiohttp.

    Provides a REST-like endpoint structure:
    - /ws - Main game WebSocket
    - /health - Health check endpoint
    - / - the browser client, when ``web_client`` (the WEB_CLIENT setting)
    """

    def __init__(
        self,
        session_manager: SessionManager,
        on_command: callable,
        host: str = "0.0.0.0",
        port: int = 4001,
        *,
        web_client: bool = False,
        game_name: str = "REALM",
    ):
        if not HAS_AIOHTTP:
            raise RuntimeError(
                "aiohttp is required for WebSocket support. "
                "Install with: pip install aiohttp"
            )

        self.session_manager = session_manager
        self.on_command = on_command
        self.host = host
        self.port = port
        # The page is read once, here: a missing file fails at boot.
        self._page: str | None = (
            client_page().replace(GAME_NAME_MARK, html.escape(game_name))
            if web_client else None)

        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    def make_app(self) -> web.Application:
        """The aiohttp application: its routes, ready to run."""
        app = web.Application()
        app.router.add_get('/ws', self._handle_websocket)
        app.router.add_get('/health', self._handle_health)
        if self._page is not None:
            app.router.add_get('/', self._handle_page)
        return app

    async def start(self) -> None:
        """Start the WebSocket server."""
        self._app = self.make_app()

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()

        logger.info(f"WebSocket server listening on {self.host}:{self.port}")
        if self._page is not None:
            logger.info(f"Browser client at http://{self.host}:{self.port}/")

    async def stop(self) -> None:
        """Stop the WebSocket server."""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
            self._site = None
            self._app = None
            logger.info("WebSocket server stopped")

    async def _handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """Handle a WebSocket connection request."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        # Get client address
        from realm.gateway.session import connect_session, format_peer_address
        peername = request.transport.get_extra_info('peername') if request.transport else None
        address = format_peer_address(peername)

        # The shared connect ritual: the one writer installed before the
        # session exists (welcome-screen flush depends on it) — with the
        # same markup rendering every later message gets, by the display
        # options of whoever the session is playing once it plays.
        # ws.close() returns an awaitable; close_connection awaits it.
        connected: list[Session] = []
        session = await connect_session(
            self.session_manager,
            protocol="websocket",
            address=address,
            writer=make_ws_writer(ws, lambda: connected[0].player if connected else None),
            closer=ws.close,
        )
        connected.append(session)

        # Run the handler
        handler = WebSocketHandler(ws, session, self.session_manager, self.on_command)
        await handler.run()

        return ws

    async def _handle_page(self, request: web.Request) -> web.Response:
        """The browser client (WEB_CLIENT)."""
        return web.Response(text=self._page, content_type='text/html', charset='utf-8')

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({
            'status': 'ok',
            'sessions': self.session_manager.session_count(),
            'players': self.session_manager.player_count(),
        })

    @property
    def is_serving(self) -> bool:
        """Check if the server is currently serving."""
        return self._site is not None
