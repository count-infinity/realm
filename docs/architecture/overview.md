# Architecture Overview

REALM uses a layered architecture that separates concerns cleanly:

```
┌─────────────────────────────────────────────────────────────┐
│                      Client Connections                      │
│                  (Telnet, WebSocket, Godot)                  │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                     Gateway Layer                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │   Telnet    │  │  WebSocket  │  │   Custom    │          │
│  │  Protocol   │  │  Protocol   │  │  Protocol   │          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
│         └────────────────┼────────────────┘                  │
│                          │                                   │
│              ┌───────────▼───────────┐                       │
│              │   SessionManager      │                       │
│              │   (Protocol Agnostic) │                       │
│              └───────────┬───────────┘                       │
└──────────────────────────┼──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                      Server Layer                            │
│  ┌─────────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │  GameServer     │  │  Dispatcher │  │   EventBus      │  │
│  │  (Orchestrator) │  │  (Commands) │  │   (Events)      │  │
│  └─────────────────┘  └─────────────┘  └─────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                       Core Layer                             │
│  ┌─────────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │   GameObject    │  │  Behaviors  │  │   Attributes    │  │
│  │   (All things)  │  │  (Scripts)  │  │   (db.*)        │  │
│  └─────────────────┘  └─────────────┘  └─────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   Persistence Layer                          │
│              ┌─────────────────────────┐                     │
│              │  PersistenceManager     │                     │
│              │  (SQLite / PostgreSQL)  │                     │
│              └─────────────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### Gateway Layer

The gateway layer handles all network protocols. Each protocol (telnet, websocket, etc.) is responsible for:

1. Accepting connections
2. Creating a writer function for output
3. Calling `SessionManager.create_session(writer=...)`
4. Translating protocol-specific input to commands
5. Handling disconnections

The **SessionManager** is protocol-agnostic and manages all sessions uniformly.

### Server Layer

The server layer contains the game logic:

- **GameServer** - Orchestrates all components, handles startup/shutdown
- **CommandDispatcher** - Routes commands to handlers
- **EventBus** - Publishes and delivers events to subscribers

### Core Layer

The core layer defines the game world:

- **GameObject** - Everything is a GameObject (rooms, players, items, exits)
- **Behaviors** - Scripts attached to objects that respond to events
- **Attributes** - Persistent data stored on objects via `obj.db.attribute`

### Persistence Layer

The persistence layer handles saving and loading:

- Dirty tracking for efficient saves
- Periodic flush to database
- Support for SQLite (default) and PostgreSQL

## Data Flow: Command Execution

```
1. Client sends "say hello"
        │
        ▼
2. Protocol receives data, calls on_command(session, "say hello")
        │
        ▼
3. Dispatcher.dispatch(session, "say hello")
        │
        ├─► Command found? Execute handler
        │           │
        │           ▼
        │   4. Handler sends messages: session.send("You say...")
        │           │
        │           ▼
        │   5. Handler emits event: event_bus.emit(SPEECH event)
        │           │
        │           ▼
        │   6. Event delivered to room occupants
        │
        └─► Command not found? Call unknown_handler (softcode search)

7. After handler completes: session.flush_output()
        │
        ▼
8. All queued messages sent to client via writer callback
```

## Design Decisions

### Why Single-Process?

Unlike Evennia's Portal/Server split, REALM uses a single async process:

- **Simpler deployment** - One process to manage
- **Lower latency** - No IPC overhead
- **Easier debugging** - Single stack trace
- **Hot reload via behaviors** - Game logic in behaviors can be reloaded

### Why Protocol-Agnostic Sessions?

Sessions don't know about telnet vs websocket:

- **Uniform API** - `session.send()` works the same everywhere
- **Easy testing** - Mock sessions without network code
- **Future-proof** - Add new protocols without changing game code

### Why Event Bus?

Events decouple game actions from their effects:

- **Extensible** - Behaviors can subscribe to any event
- **Cancelable** - Validation phase can prevent actions
- **Observable** - Easy to add logging, achievements, etc.

## Next Steps

- [Session Lifecycle](sessions.md) - Deep dive into connection handling
- [Event System](events.md) - How events flow through the system
- [Command Dispatch](commands.md) - Command registration and routing
