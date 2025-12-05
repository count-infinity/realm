# Session Lifecycle

Sessions represent the connection between a player and the game. They handle input/output buffering and map to player objects.

## Session States

```
CONNECTED ──────► AUTHENTICATING ──────► PLAYING
    │                   │                    │
    │                   │                    │
    └───────────────────┴────────────────────┘
                        │
                        ▼
                  DISCONNECTING
```

| State | Description |
|-------|-------------|
| `CONNECTED` | Just connected, not authenticated |
| `AUTHENTICATING` | In login/character select flow |
| `PLAYING` | In-game with a linked player object |
| `DISCONNECTING` | Being cleaned up |

## Connection Flow

When a client connects:

```python
# 1. Protocol receives connection
def connection_made(self, transport):
    asyncio.create_task(self._setup_session(address))

# 2. Protocol creates session with writer
async def _setup_session(self, address):
    self.session = await session_manager.create_session(
        protocol="telnet",
        address=address,
        writer=self._write_to_client,  # Must be set BEFORE create!
    )

# 3. SessionManager triggers callbacks
async def create_session(self, protocol, address, writer):
    session = Session(protocol=protocol, address=address)

    # Writer set BEFORE callbacks
    if writer:
        session.set_writer(writer)

    # Connection callbacks (send welcome screen)
    for callback in self._on_connect:
        await callback(session)

    # Auto-flush ensures welcome is sent immediately
    await self._auto_flush(session)

    return session
```

!!! important "Writer Order Matters"
    The writer must be passed to `create_session()` so it's set before
    connection callbacks run. Otherwise, the welcome screen is queued
    but never flushed (the auto-flush does nothing without a writer).

## Session Components

### Input Queue

Commands from the player are pushed to the input queue:

```python
# Protocol pushes input
session.push_input_nowait("look")

# Game loop can read
command = await session.receive()
# or
command = session.receive_nowait()
```

### Output Queue

Messages to the player are queued then flushed:

```python
# Queue a message
await session.send("You see a room.")

# Messages stay in queue until...
await session.flush_output()  # ...flush sends them to writer
```

!!! note "Flush Timing"
    Output is flushed:

    1. After connection callbacks complete (auto-flush for welcome screen)
    2. After each command is processed (`_on_command` calls flush)

    Messages are NOT automatically flushed. This allows batching multiple
    messages into a single network write.

### Writer Callback

The writer is a protocol-specific function that sends data to the client:

```python
async def _write_to_client(self, message: str) -> None:
    """Telnet writer - adds CRLF line endings."""
    if self.transport is None:
        return

    message = message.replace('\n', '\r\n')
    self.transport.write(message.encode('utf-8'))
```

Each protocol implements its own writer:

- **Telnet**: Adds `\r\n`, writes to transport
- **WebSocket**: Calls `ws.send_str()`
- **Custom**: Whatever your protocol needs

## Player Linking

When a player authenticates:

```python
# Link player object to session
session_manager.link_player_to_session(session, player)

# This:
# 1. Unlinks any existing session for this player
# 2. Sets session.player = player
# 3. Changes session.state to PLAYING
# 4. Tracks session in _by_player dict
```

!!! warning "One Session Per Player"
    If a player connects from a new location, their old session is
    automatically unlinked. You may want to send a message to the
    old session before this happens.

## Disconnection

When a connection is lost:

```python
# 1. Protocol detects disconnect
def connection_lost(self, exc):
    asyncio.create_task(
        session_manager.destroy_session(self.session)
    )

# 2. SessionManager cleans up
async def destroy_session(self, session):
    session.state = SessionState.DISCONNECTING

    # Notify callbacks (save player, emit event)
    for callback in self._on_disconnect:
        await callback(session)

    # Unlink player if any
    if session.player:
        session.unlink_player()

    # Remove from tracking dicts
    del self._sessions[session.id]
```

## Session Data

Sessions can store arbitrary data:

```python
# Store terminal size from NAWS negotiation
session.set_data('terminal_width', 80)
session.set_data('terminal_height', 24)

# Retrieve later
width = session.get_data('terminal_width', default=80)
```

This is useful for:

- Terminal dimensions
- Client capabilities
- Temporary state during login
- Protocol-specific metadata

## Timestamps

Sessions track timing for idle detection:

```python
session.idle_time      # Seconds since last activity
session.connected_time # Seconds since connection

session.touch()        # Update last activity (called on input)
```

!!! note "Python 3.14 Compatibility"
    Timestamps use `time.monotonic()` instead of event loop time.
    This works correctly in both sync and async contexts.

## Lookup Methods

Find sessions by various criteria:

```python
# By session ID
session = session_manager.get_session(session_id)

# By player object
session = session_manager.get_session_by_player(player)

# By IP address (returns list - multiple sessions possible)
sessions = session_manager.get_sessions_by_address("192.168.1.1:12345")

# All sessions
all_sessions = session_manager.all_sessions()

# Only sessions with linked players
playing = session_manager.playing_sessions()
```

## Broadcasting

Send messages to multiple sessions:

```python
# To all playing sessions
await session_manager.broadcast("Server restarting in 5 minutes!")

# To all players in a room
await session_manager.broadcast_to_room(
    room=some_room,
    message="A loud noise echoes.",
    exclude=source_player,  # Don't send to the player who caused it
)
```
