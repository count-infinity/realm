"""
WebSocket protocol handler for REALM.

Provides a WebSocket interface for web clients using aiohttp.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

try:
    from aiohttp import WSMsgType, web
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    web = None  # type: ignore
    WSMsgType = None  # type: ignore

if TYPE_CHECKING:
    from realm.gateway.session import Session, SessionManager

logger = logging.getLogger(__name__)


def make_ws_writer(ws: Any) -> callable:
    """The one text writer for a WebSocket client, used from the very
    first byte (the welcome screen included). Markup ships as structured
    segments — the client styles them (no ANSI-to-HTML archaeology);
    plain text stays plain."""

    async def write_to_client(message: str) -> None:
        if ws.closed:
            return
        from realm.core.markup import MARKER, parse, strip
        try:
            if MARKER in message:
                try:
                    segments = [[style.key(), seg]
                                for style, seg in parse(message)]
                    await ws.send_json({'type': 'text',
                                        'text': strip(message),
                                        'segments': segments})
                    return
                except Exception:
                    message = strip(message)
            await ws.send_str(message)
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
            await self.session_manager.destroy_session(self.session)

    async def _handle_text(self, text: str) -> None:
        """Handle a text message from the client."""
        text = text.strip()
        if not text:
            return

        # Try to parse as JSON first
        if text.startswith('{'):
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
    """

    def __init__(
        self,
        session_manager: SessionManager,
        on_command: callable,
        host: str = "0.0.0.0",
        port: int = 4001,
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

        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None

    async def start(self) -> None:
        """Start the WebSocket server."""
        self._app = web.Application()
        self._app.router.add_get('/ws', self._handle_websocket)
        self._app.router.add_get('/health', self._handle_health)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()

        logger.info(f"WebSocket server listening on {self.host}:{self.port}")

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
        peername = request.transport.get_extra_info('peername') if request.transport else None
        address = f"{peername[0]}:{peername[1]}" if peername else "unknown"

        # The one writer, installed BEFORE create_session() so the
        # welcome screen flushes immediately — with the same markup
        # rendering every later message gets (no raw-pipe leak window).
        session = await self.session_manager.create_session(
            protocol="websocket",
            address=address,
            writer=make_ws_writer(ws),
        )
        # ws.close() returns an awaitable; close_connection awaits it.
        session.set_closer(ws.close)

        logger.info(f"WebSocket connection from {address}")

        # Run the handler
        handler = WebSocketHandler(ws, session, self.session_manager, self.on_command)
        await handler.run()

        return ws

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
