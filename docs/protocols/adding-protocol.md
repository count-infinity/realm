# Adding a Protocol

This guide explains how to add a new connection protocol to REALM, such as a custom Godot client, SSH, or any other transport.

!!! important "REALM is a Library"
    You should **never need to modify REALM's source code** to add a protocol.
    Protocols are registered through your game's configuration or entry points.

## Overview

Adding a protocol requires:

1. A **protocol server class** in your game's code
2. **Registration** via config or entry points
3. A **writer function** that sends data to clients

## Quick Start: Register via Configuration

In your game's `config/settings.yaml`:

```yaml
# config/settings.yaml
server:
  protocols:
    telnet:
      enabled: true
      port: 4000
    websocket:
      enabled: true
      port: 4001
    # Custom protocol from your game code
    godot:
      enabled: true
      port: 4002
      class: "mygame.protocols.GodotServer"
```

REALM will import and instantiate your protocol class automatically.

## Quick Start: Register via Python

In your game's entry point:

```python
# mygame/server.py
from realm import GameServer
from mygame.protocols import GodotServer

async def main():
    server = GameServer()

    # Register your custom protocol
    server.register_protocol(
        "godot",
        GodotServer,
        port=4002,
    )

    await server.run_forever()
```

## Protocol Server Interface

Your protocol server must implement this interface:

```python
"""
mygame/protocols/godot.py - Custom protocol in YOUR game, not in REALM.
"""

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.gateway.session import SessionManager

logger = logging.getLogger(__name__)


class GodotServer:
    """
    Custom protocol server for Godot clients.

    This class lives in YOUR game code, not in REALM.
    """

    def __init__(
        self,
        session_manager: SessionManager,
        on_command: callable,
        host: str = "0.0.0.0",
        port: int = 4002,
    ):
        self.session_manager = session_manager
        self.on_command = on_command
        self.host = host
        self.port = port
        self._server = None

    async def start(self) -> None:
        """Start accepting connections."""
        # Your server setup here
        logger.info(f"Godot server listening on {self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    @property
    def is_serving(self) -> bool:
        """Check if server is running."""
        return self._server is not None
```

## Connection Handling

When a client connects, create a session with a writer:

```python
async def _handle_connection(self, connection) -> None:
    """Handle a new connection."""
    address = self._get_client_address(connection)

    # Create writer FIRST - this is critical!
    # The writer must exist before create_session() so the
    # welcome screen can be flushed immediately.
    async def write_to_client(message: str) -> None:
        if not connection.closed:
            await connection.send(message.encode('utf-8'))

    # Create session with writer
    session = await self.session_manager.create_session(
        protocol="godot",
        address=address,
        writer=write_to_client,  # <-- Must pass writer here!
    )

    logger.info(f"Godot connection from {address}")

    # Handle input loop
    try:
        await self._input_loop(connection, session)
    finally:
        await self.session_manager.destroy_session(session)
```

!!! warning "Writer Timing is Critical"
    The writer MUST be passed to `create_session()` so it's available
    before connection callbacks run. This ensures the welcome screen
    is sent immediately when the client connects.

## Input Loop

Process incoming data and dispatch commands:

```python
async def _input_loop(self, connection, session) -> None:
    """Read input and dispatch commands."""
    async for data in connection:
        command = self._parse_command(data)
        if command:
            session.push_input_nowait(command)
            await self.on_command(session, command)
```

## Complete Example: Godot WebSocket Protocol

Here's a complete example for a Godot client using JSON over WebSocket:

```python
"""
mygame/protocols/godot.py

A WebSocket protocol for Godot game clients.
Place this in YOUR game code, not in REALM.
"""

import json
import logging
from aiohttp import web, WSMsgType

logger = logging.getLogger(__name__)


class GodotServer:
    """WebSocket server for Godot clients with JSON messages."""

    def __init__(
        self,
        session_manager,
        on_command,
        host: str = "0.0.0.0",
        port: int = 4002,
    ):
        self.session_manager = session_manager
        self.on_command = on_command
        self.host = host
        self.port = port
        self._app = None
        self._runner = None
        self._site = None

    async def start(self) -> None:
        """Start the WebSocket server."""
        self._app = web.Application()
        self._app.router.add_get('/ws', self._handle_websocket)
        self._app.router.add_get('/health', self._handle_health)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()

        logger.info(f"Godot server listening on {self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the server."""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
            self._site = None
            self._app = None

    async def _handle_websocket(self, request) -> web.WebSocketResponse:
        """Handle a WebSocket connection."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        # Get client address
        peername = request.transport.get_extra_info('peername')
        address = f"{peername[0]}:{peername[1]}" if peername else "unknown"

        # Create writer that sends JSON messages
        async def write_to_client(message: str) -> None:
            if not ws.closed:
                try:
                    await ws.send_json({
                        "type": "message",
                        "text": message,
                    })
                except Exception as e:
                    logger.error(f"Error writing to Godot client: {e}")

        # Create session with writer
        session = await self.session_manager.create_session(
            protocol="godot",
            address=address,
            writer=write_to_client,
        )

        logger.info(f"Godot connection from {address}")

        # Handle messages
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self._handle_message(session, msg.data)
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
                    break
        finally:
            await self.session_manager.destroy_session(session)

        return ws

    async def _handle_message(self, session, raw_data: str) -> None:
        """Handle a JSON message from the client."""
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            return

        msg_type = data.get("type", "command")

        if msg_type == "command":
            command = data.get("text", "").strip()
            if command:
                session.push_input_nowait(command)
                await self.on_command(session, command)

        elif msg_type == "ping":
            # Respond to ping
            await session.send('{"type": "pong"}')
            await session.flush_output()

    async def _handle_health(self, request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({"status": "ok"})

    @property
    def is_serving(self) -> bool:
        return self._site is not None
```

## Using Your Protocol

### Option 1: Configuration (Recommended)

```yaml
# config/settings.yaml
server:
  protocols:
    godot:
      enabled: true
      port: 4002
      class: "mygame.protocols.GodotServer"
```

### Option 2: Python Registration

```python
# mygame/server.py
from realm import GameServer
from mygame.protocols import GodotServer

server = GameServer()
server.register_protocol("godot", GodotServer, port=4002)
await server.run_forever()
```

### Option 3: Entry Points (for pip-installable plugins)

```toml
# In your plugin's pyproject.toml
[project.entry-points."realm.protocols"]
godot = "mygame.protocols:GodotServer"
```

## Checklist

When creating a protocol, verify:

- [ ] Protocol class is in YOUR game code, not REALM
- [ ] Writer function created BEFORE `create_session()`
- [ ] Writer passed to `create_session(writer=...)`
- [ ] Session destroyed on disconnect
- [ ] Input pushed to session queue
- [ ] `on_command()` called for each command
- [ ] Errors logged appropriately
- [ ] Server has `start()` and `stop()` methods
- [ ] `is_serving` property implemented

## Testing Your Protocol

```python
import pytest

@pytest.mark.asyncio
async def test_godot_welcome_screen():
    """Verify welcome screen is sent on connect."""
    from realm.gateway.session import SessionManager

    manager = SessionManager()
    messages_sent = []

    async def mock_writer(msg):
        messages_sent.append(msg)

    # Add a connection callback that sends welcome
    async def on_connect(session):
        await session.send("Welcome to my game!")

    manager.on_connect(on_connect)

    # Simulate connection
    session = await manager.create_session(
        protocol="godot",
        address="test:1234",
        writer=mock_writer,
    )

    # Welcome should be sent immediately
    assert len(messages_sent) > 0
    assert "Welcome" in messages_sent[0]
```
