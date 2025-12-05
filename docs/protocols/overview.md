# Protocol Overview

REALM supports multiple connection protocols through a clean abstraction layer.

## Supported Protocols

| Protocol | Port | Status | Use Case |
|----------|------|--------|----------|
| Telnet | 4000 | Stable | Traditional MUD clients |
| WebSocket | 4001 | Stable | Web clients, modern apps |
| Custom | - | Guide | Godot, Unity, etc. |

## Protocol Architecture

All protocols follow the same pattern:

```
Client ──► Protocol Handler ──► SessionManager ──► Game Logic
                │                      │
                │                      ▼
                │               Session Object
                │                      │
                └──── writer ──────────┘
```

1. Protocol receives connection
2. Protocol creates a **writer function**
3. Protocol calls `session_manager.create_session(writer=...)`
4. SessionManager creates session, runs callbacks, auto-flushes
5. Protocol handles input loop, calling `on_command()`
6. On disconnect, protocol calls `destroy_session()`

## Key Principle: Writer First

The writer function must be passed to `create_session()` before callbacks run:

```python
# Correct: writer passed to create_session
session = await session_manager.create_session(
    protocol="myprotocol",
    writer=my_writer,  # <-- Available for welcome screen flush
)

# Incorrect: writer set after
session = await session_manager.create_session(protocol="myprotocol")
session.set_writer(my_writer)  # <-- Too late! Welcome screen lost
```

## Protocol Files

```
realm/gateway/
├── session.py    # Session and SessionManager (protocol-agnostic)
├── telnet.py     # Telnet protocol implementation
└── websocket.py  # WebSocket protocol implementation
```

## Next Steps

- [Adding a Protocol](adding-protocol.md) - Step-by-step guide
- [Session Lifecycle](../architecture/sessions.md) - How sessions work
