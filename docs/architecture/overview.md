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
│  │  GameServer     │  │  Dispatcher │  │  ScriptEngine   │  │
│  │  (Orchestrator) │  │  (Commands) │  │  (Softcode)     │  │
│  └─────────────────┘  └─────────────┘  └─────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                       Core Layer                             │
│  ┌─────────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │   GameObject    │  │  Behaviors  │  │  Propagation    │  │
│  │  (tags + db.*)  │  │  (brains)   │  │  (all actions)  │  │
│  └─────────────────┘  └─────────────┘  └─────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   Persistence Layer                          │
│              ┌─────────────────────────┐                     │
│              │  PersistenceManager     │                     │
│              │  (SQLite, WAL mode)     │                     │
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

- **GameServer** - The composition root: startup/shutdown, tick loop, auth, chargen
- **CommandDispatcher** - Routes commands to handlers (permissions, categories)
- **ScriptEngine** - Softcode: `$`-commands, `^listen`, `ON_<EVENT>` triggers, tickers
- **GameSystem** - The swappable rules package (GURPS/D20: chargen, skills, combat ruleset)

### Core Layer

The core layer defines the game world:

- **GameObject** - Everything is a GameObject (rooms, players, items, exits)
- **Action Propagation** - every game action flows through one two-pass pipeline ([details](events.md))
- **Behaviors** - reusable brains attached to objects (wandering, shopkeeper, effects)
- **Attributes & tags** - persistent data via `obj.db.attr`; mechanics are tag-driven

### Persistence Layer

The persistence layer handles saving and loading:

- Dirty tracking for efficient saves
- Periodic flush to database
- SQLite (WAL mode) today; the backend is a seam — Postgres is a
  planned alternative, not yet implemented

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
        │   5. Handler propagates an Action (two passes:
        │      check — locks/behaviors may block; react)
        │           │
        │           ▼
        │   6. Messages render per looker; observers
        │      (softcode, stealth, combat) see it
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

### Why Action Propagation?

One pipeline for every action decouples causes from effects:

- **Extensible** - behaviors and softcode react to any action, no registration tables
- **Vetoable** - the check pass lets locks and behaviors block before effects
- **Observable** - stealth, combat auto-initiation, and logging are just observers

## Next Steps

- [Session Lifecycle](sessions.md) - Deep dive into connection handling
- [Action Propagation](events.md) - How actions flow through the system
- [Command Dispatch](commands.md) - Command registration and routing
