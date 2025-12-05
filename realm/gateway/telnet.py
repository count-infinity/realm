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

    def __init__(
        self,
        session_manager: SessionManager,
        on_command: callable,
    ):
        self.session_manager = session_manager
        self.on_command = on_command  # Callback for received commands

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

        logger.info(f"Telnet connection from {address}")

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

    def data_received(self, data: bytes) -> None:
        """Called when data is received from the client."""
        if self.session is None:
            return

        for byte in data:
            if self._in_iac:
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

    def _process_line(self) -> None:
        """Process a complete line of input."""
        if self.session is None:
            return

        try:
            line = self._buffer.decode('utf-8', errors='replace').strip()
        except Exception:
            line = ""

        self._buffer.clear()

        if line:
            # Push to session input queue
            self.session.push_input_nowait(line)

            # Notify command handler
            asyncio.create_task(self.on_command(self.session, line))

    async def _write_to_client(self, message: str) -> None:
        """Write a message to the client."""
        if self.transport is None or self.transport.is_closing():
            return

        # Ensure lines end with CRLF for telnet
        if not message.endswith('\n'):
            message += '\n'
        message = message.replace('\n', '\r\n')

        try:
            self.transport.write(message.encode('utf-8'))
        except Exception as e:
            logger.error(f"Error writing to telnet client: {e}")

    def connection_lost(self, exc: Exception | None) -> None:
        """Called when the connection is lost."""
        if self.session:
            asyncio.create_task(
                self.session_manager.destroy_session(self.session)
            )
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
    ):
        self.session_manager = session_manager
        self.on_command = on_command
        self.host = host
        self.port = port
        self._server: asyncio.Server | None = None

    async def start(self) -> None:
        """Start the telnet server."""
        loop = asyncio.get_running_loop()

        def protocol_factory():
            return TelnetProtocol(self.session_manager, self.on_command)

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
