# REALM

**Real-time Event-Action Layered MUD framework**

REALM is a modern Python framework for building Multi-User Dungeons (MUDs), MUSHes, and other text-based multiplayer games.

## Features

- **Async-first architecture** - Built on Python's asyncio for high concurrency
- **Protocol agnostic** - Telnet, WebSocket, and extensible to custom protocols
- **Event-driven** - Flexible event bus with validation and execution phases
- **Persistent world** - SQLite-backed persistence with dirty tracking
- **Extensible commands** - Easy command registration with aliases
- **Session management** - Robust connection handling with auto-flush

## Quick Example

```python
from realm.server import GameServer

async def main():
    server = GameServer(
        telnet_port=4000,
        websocket_port=4001,
    )
    await server.run_forever()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Getting Started

- [Installation](getting-started/installation.md) - Set up your development environment
- [Quick Start](getting-started/quickstart.md) - Run your first REALM server
- [Your First Game](getting-started/first-game.md) - Build a simple game world

## Architecture

- [Overview](architecture/overview.md) - How REALM components fit together
- [Session Lifecycle](architecture/sessions.md) - Connection states and flow
- [Event System](architecture/events.md) - The event bus and handlers
- [Command Dispatch](architecture/commands.md) - How commands are processed

## For Developers

- [Adding a Protocol](protocols/adding-protocol.md) - Integrate new connection types
- [Contributing](development/contributing.md) - How to contribute to REALM

## Design Philosophy

REALM draws inspiration from three battle-tested MU* implementations:

| Framework | Inspiration |
|-----------|-------------|
| **PennMUSH** | Permission systems, softcode concepts, lock system |
| **Evennia** | Command parsing, typeclass system, Django integration patterns |
| **CoffeeMud** | Combat formulas, economy systems, area templates |

We aim to combine the best ideas from each while providing a clean, modern Python API.
