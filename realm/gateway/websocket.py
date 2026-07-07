"""
WebSocket protocol handler for REALM.

Provides a WebSocket interface for web clients using aiohttp.
"""

from __future__ import annotations

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


class WebSocketHandler:
    """
    Handles a single WebSocket connection.

    Messages can be plain text (commands) or JSON for structured data.
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
        self.on_command = on_command
        self._running = False

    async def run(self) -> None:
        """Run the WebSocket handler loop."""
        self._running = True

        # Note: Writer is now set in _handle_websocket before create_session()
        # to ensure welcome screen flushes immediately. We update it here to
        # use the handler's method which checks self._running for cleaner shutdown.
        self.session.set_writer(self._write_to_client)

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
            self._running = False
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

        # Plain text command
        self.session.push_input_nowait(text)
        await self.on_command(self.session, text)

    async def _handle_json(self, data: dict[str, Any]) -> None:
        """Handle a JSON message from the client."""
        msg_type = data.get('type', 'command')

        if msg_type == 'command':
            command = data.get('command', '').strip()
            if command:
                self.session.push_input_nowait(command)
                await self.on_command(self.session, command)

        elif msg_type == 'ping':
            await self._send_json({'type': 'pong'})

        elif msg_type == 'resize':
            # Window size update
            width = data.get('width', 80)
            height = data.get('height', 24)
            self.session.set_data('terminal_width', width)
            self.session.set_data('terminal_height', height)

    async def _write_to_client(self, message: str) -> None:
        """Write a message to the WebSocket client.

        Markup ships as structured segments — the client styles them
        (no ANSI-to-HTML archaeology); plain text stays plain.
        """
        if not self._running or self.ws.closed:
            return

        from realm.core.markup import MARKER, parse, strip
        if MARKER in message:
            try:
                segments = [[style.key(), seg] for style, seg in parse(message)]
                await self._send_json({'type': 'text',
                                       'text': strip(message),
                                       'segments': segments})
                return
            except Exception:
                message = strip(message)

        try:
            await self.ws.send_str(message)
        except Exception as e:
            logger.error(f"Error writing to WebSocket: {e}")

    async def _send_json(self, data: dict[str, Any]) -> None:
        """Send a JSON message to the client."""
        if not self._running or self.ws.closed:
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

        # Create writer function that captures the ws object.
        # This must be created BEFORE create_session() so the welcome
        # screen can be flushed immediately (same pattern as telnet).
        async def write_to_client(message: str) -> None:
            if not ws.closed:
                try:
                    await ws.send_str(message)
                except Exception as e:
                    logger.error(f"Error writing to WebSocket: {e}")

        # Create session with writer so welcome screen flushes immediately
        session = await self.session_manager.create_session(
            protocol="websocket",
            address=address,
            writer=write_to_client,
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
