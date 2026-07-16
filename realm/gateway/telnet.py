"""
Telnet protocol handler for REALM.

Implements a basic telnet server with:
- Line-based input
- ANSI color support
- Basic telnet negotiation
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.gateway.session import Session, SessionManager

logger = logging.getLogger(__name__)

# Telnet protocol bytes
IAC = bytes([255])   # Interpret As Command
WILL = bytes([251])
WONT = bytes([252])
DO = bytes([253])
DONT = bytes([254])
SB = bytes([250])    # Sub-negotiation Begin
SE = bytes([240])    # Sub-negotiation End
GMCP = bytes([201])  # Generic MUD Communication Protocol (option 201)
SE = bytes([240])    # Sub-negotiation End

# Common telnet options
ECHO = bytes([1])
SGA = bytes([3])     # Suppress Go Ahead
NAWS = bytes([31])   # Negotiate About Window Size
LINEMODE = bytes([34])


class TelnetProtocol(asyncio.Protocol):
    """
    Asyncio protocol handler for telnet connections.

    Handles:
    - Basic telnet negotiation
    - Line buffering
    - Session lifecycle
    """

    encoding: str = "utf-8"   # default for __new__-based construction

    def __init__(
        self,
        session_manager: SessionManager,
        on_command: callable,
        encoding: str = "utf-8",
    ):
        self.session_manager = session_manager
        self.on_command = on_command  # Callback for received commands
        self.encoding = encoding      # text codec (config ENCODING)

        self.transport: asyncio.Transport | None = None
        self.session: Session | None = None
        self._buffer = bytearray()
        self._in_iac = False
        self._iac_command = bytearray()

    def connection_made(self, transport: asyncio.Transport) -> None:
        """Called when a connection is established."""
        self.transport = transport
        peername = transport.get_extra_info('peername')
        address = f"{peername[0]}:{peername[1]}" if peername else "unknown"

        # Create session asynchronously
        asyncio.create_task(self._setup_session(address))

    async def _setup_session(self, address: str) -> None:
        """Set up the session and send initial negotiation."""
        # Send initial telnet negotiation first
        self._send_negotiation()

        # Create session with writer already configured.
        # The writer must be set BEFORE create_session() because
        # create_session() triggers connection callbacks that send
        # the welcome screen and then auto-flush. Without the writer,
        # flush does nothing.
        self.session = await self.session_manager.create_session(
            protocol="telnet",
            address=address,
            writer=self._write_to_client,
        )
        self.session.set_closer(self._close_transport)

        logger.info(f"Telnet connection from {address}")

    def _close_transport(self) -> None:
        """Close the client connection (session closer hook)."""
        if self.transport is not None and not self.transport.is_closing():
            self.transport.close()

    def _send_negotiation(self) -> None:
        """Send initial telnet option negotiation."""
        if self.transport is None:
            return

        # Tell client we will echo (password hiding)
        self.transport.write(IAC + WILL + ECHO)
        # Tell client to suppress go-ahead
        self.transport.write(IAC + WILL + SGA)
        # Ask client to suppress go-ahead
        self.transport.write(IAC + DO + SGA)
        # Offer GMCP (structured out-of-band data for modern clients)
        self.transport.write(IAC + WILL + GMCP)

    def data_received(self, data: bytes) -> None:
        """Called when data is received from the client."""
        if self.session is None:
            return

        for byte in data:
            if getattr(self, '_in_sb', False):
                self._handle_sb_byte(byte)
            elif self._in_iac:
                self._handle_iac(byte)
            elif byte == 255:  # IAC
                self._in_iac = True
                self._iac_command = bytearray([byte])
            elif byte == 13:  # CR
                # Line complete, process it
                self._process_line()
            elif byte == 10:  # LF
                # Ignore LF (usually follows CR)
                pass
            elif byte == 8 or byte == 127:  # Backspace or DEL
                if self._buffer:
                    self._buffer.pop()
            elif 32 <= byte < 127 or byte >= 128:  # Printable or extended
                self._buffer.append(byte)

    def _handle_iac(self, byte: int) -> None:
        """Handle telnet IAC sequences."""
        self._iac_command.append(byte)

        if len(self._iac_command) == 2:
            # Check if this is a 2-byte or 3-byte command
            if byte in (251, 252, 253, 254):  # WILL, WONT, DO, DONT
                return  # Wait for option byte
            elif byte == 250:  # SB — collect until IAC SE
                self._in_iac = False
                self._in_sb = True
                self._sb_buffer = bytearray()
            else:
                # 2-byte command complete
                self._in_iac = False
        elif len(self._iac_command) == 3:
            # 3-byte command complete
            cmd = self._iac_command[1]
            option = self._iac_command[2]

            # Handle the negotiation
            if cmd == 253:  # DO
                # Client asks us to do something
                if option == 1:  # ECHO
                    pass  # We already said WILL ECHO
                elif option == 3:  # SGA
                    pass  # We already said WILL SGA
                elif option == 201:  # GMCP accepted — wire the channel
                    if self.session is not None:
                        self.session.set_oob_writer(self._send_gmcp)
                else:
                    # Refuse unknown options
                    if self.transport:
                        self.transport.write(IAC + WONT + bytes([option]))

            elif cmd == 251:  # WILL
                # Client offers to do something
                if option == 31:  # NAWS
                    # Accept window size negotiation
                    if self.transport:
                        self.transport.write(IAC + DO + NAWS)
                else:
                    # Refuse unknown options
                    if self.transport:
                        self.transport.write(IAC + DONT + bytes([option]))

            self._in_iac = False

    def _handle_sb_byte(self, byte: int) -> None:
        """Collect a subnegotiation until IAC SE (IAC IAC = literal 255)."""
        buf = self._sb_buffer
        if buf and buf[-1] == 255:
            if byte == 240:  # SE — complete
                self._in_sb = False
                self._handle_subnegotiation(bytes(buf[:-1]))
                return
            if byte == 255:  # escaped IAC
                return  # keep the single 255 already in the buffer
        buf.append(byte)

    def _handle_subnegotiation(self, payload: bytes) -> None:
        """Dispatch a completed IAC SB ... IAC SE block."""
        if not payload:
            return
        if payload[0] == 201:  # GMCP: "Package.Sub JSON"
            self._handle_gmcp(payload[1:])
        elif payload[0] == 31 and len(payload) >= 5:  # NAWS: w16 h16
            # Same session data the websocket 'resize' message sets —
            # window size is protocol-agnostic once it's in the session.
            if self.session is not None:
                self.session.set_data(
                    'terminal_width', (payload[1] << 8) | payload[2])
                self.session.set_data(
                    'terminal_height', (payload[3] << 8) | payload[4])

    def _handle_gmcp(self, payload: bytes) -> None:
        """Inbound GMCP from the client (Core.Hello, Core.Supports...)."""
        import json
        try:
            text = payload.decode('utf-8', errors='replace').strip()
            package, _, body = text.partition(' ')
            data = json.loads(body) if body else None
        except (ValueError, json.JSONDecodeError):
            return
        if self.session is None:
            return
        # Remember what the client told us (client name, supported
        # packages); softcode/UI code can consult session.oob_supports.
        self.session.oob_supports[package] = data

    def _send_gmcp(self, package: str, data: dict) -> None:
        """Outbound GMCP frame."""
        import json
        if self.transport is None:
            return
        payload = f"{package} {json.dumps(data)}".encode()
        payload = payload.replace(IAC, IAC + IAC)  # escape literal 255s
        self.transport.write(IAC + SB + GMCP + payload + IAC + SE)

    def _process_line(self) -> None:
        """Process a complete line of input."""
        if self.session is None:
            return

        try:
            line = self._buffer.decode(self.encoding, errors='replace')
        except Exception:
            line = ""

        self._buffer.clear()

        # The adapter's whole input job ends here: decoded text into the
        # session's common input representation. The per-session pump
        # delivers it to the server funnel in order — no per-line tasks,
        # no protocol-specific dispatch semantics.
        self.session.submit_input(line)

    async def _write_to_client(self, message: str) -> None:
        """Write a message to the client (markup renders HERE)."""
        if self.transport is None or self.transport.is_closing():
            return

        # Color markup renders at the protocol edge: ANSI for clients,
        # stripped for players who set color off.
        from realm.core.markup import strip, to_ansi
        player = self.session.player if self.session else None
        if player is not None and player.db.get('color') is False:
            message = strip(message)
        else:
            message = to_ansi(message)

        # Ensure lines end with CRLF for telnet
        if not message.endswith('\n'):
            message += '\n'
        message = message.replace('\n', '\r\n')

        try:
            self.transport.write(message.encode(self.encoding, errors='replace'))
        except Exception as e:
            logger.error(f"Error writing to telnet client: {e}")

    def connection_lost(self, exc: Exception | None) -> None:
        """Called when the connection is lost."""
        if self.session:
            self.session_manager.destroy_session_soon(self.session)
        self.transport = None
        self.session = None


class TelnetServer:
    """
    Telnet server wrapper.

    Manages the asyncio server and provides start/stop methods.
    """

    def __init__(
        self,
        session_manager: SessionManager,
        on_command: callable,
        host: str = "0.0.0.0",
        port: int = 4000,
        encoding: str = "utf-8",
    ):
        self.session_manager = session_manager
        self.on_command = on_command
        self.host = host
        self.port = port
        self.encoding = encoding
        self._server: asyncio.Server | None = None

    async def start(self) -> None:
        """Start the telnet server."""
        loop = asyncio.get_running_loop()

        def protocol_factory():
            return TelnetProtocol(self.session_manager, self.on_command,
                                  encoding=self.encoding)

        self._server = await loop.create_server(
            protocol_factory,
            self.host,
            self.port,
        )

        logger.info(f"Telnet server listening on {self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the telnet server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            logger.info("Telnet server stopped")

    @property
    def is_serving(self) -> bool:
        """Check if the server is currently serving."""
        return self._server is not None and self._server.is_serving()
