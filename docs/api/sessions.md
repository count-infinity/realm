# Sessions API

!!! note "Work in Progress"
    Full API documentation coming soon.

## Session

Represents a player connection.

```python
class Session:
    id: str                    # Unique session ID
    state: SessionState        # CONNECTED, AUTHENTICATING, PLAYING, DISCONNECTING
    player: GameObject | None  # Linked player object
    protocol: str              # "telnet", "websocket", etc.
    address: str               # Remote address
    idle_time: float           # Seconds since last activity
    connected_time: float      # Seconds since connection
```

### Sending Messages

```python
# Queue a message (async)
await session.send("Hello!")

# Queue without waiting (sync contexts)
session.send_nowait("Hello!")

# Flush all queued messages to client
await session.flush_output()
```

### Session Data

```python
# Store arbitrary data
session.set_data('terminal_width', 80)

# Retrieve data
width = session.get_data('terminal_width', default=80)
```

## SessionManager

Manages all active sessions.

```python
# Get sessions
session = manager.get_session(session_id)
session = manager.get_session_by_player(player)
all_sessions = manager.all_sessions()
playing = manager.playing_sessions()

# Broadcast
await manager.broadcast("Server message!")
await manager.broadcast_to_room(room, "A noise echoes.", exclude=source)

# Counts
total = manager.session_count()
players = manager.player_count()
```

## Out-of-band data (GMCP)

```python
session.send_oob("Char.Vitals", {"hp": 9, "max_hp": 12})
session.set_oob_writer(fn)     # installed by the protocol
session.oob_supports           # what the client announced (Core.Hello...)
```

No-op for clients that never negotiated an OOB channel. Telnet uses
GMCP (option 201); WebSocket wraps the same data as
`{"type": "oob", "package": ..., "data": ...}`.
