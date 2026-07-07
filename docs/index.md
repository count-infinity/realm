# REALM

**Real-time Event-Action Layered MUD framework**

REALM is a modern Python framework for building Multi-User Dungeons (MUDs), MUSHes, and other text-based multiplayer games.

## Features

- **Async-first** - one asyncio process; SQLite (WAL) persistence with dirty-sweep saves
- **Action propagation** - every game action flows through one two-pass, vetoable pipeline
- **Softcode** - a Turing-complete, sandboxed scripting layer builders use *in-game*
  (`$`-commands, triggers, tickers, inline `[[...]]` in descriptions), with a real authority model
- **Swappable rules** - GameSystem packages (GURPS and D20 ship in-box): chargen,
  skills, advancement, combat rulesets
- **Playable out of the box** - beat combat (melee + ranged), NPCs with brains,
  shops, dispositions, followers, zones
- **Protocol agnostic** - telnet (with GMCP), WebSocket, custom protocols

## Quick Example

```bash
pip install -e .          # from a git clone, for now
realm init mygame && cd mygame
realm start               # telnet localhost 4000; first character = superuser
```

Then build from inside the game:

```text
@dig The Garden = north, south
@detail here = check('observation') -> A glint of metal in the roses.
@create parrot
@behavior parrot = script_ticker, interval:8
@set parrot/on_tick = say Pieces of eight!
```

## Getting Started

- [Installation](getting-started/installation.md) - Set up your development environment
- [Quick Start](getting-started/quickstart.md) - Run your first REALM server
- [Your First Game](getting-started/first-game.md) - Build a simple game world
- [Tutorial: The Abandoned Lighthouse](tutorial/index.md) - a complete adventure, built in-game
- [World Management](guides/world-management.md) - search, zones, attribute flags, import/export
- [Softcode Reference](reference/softcode.md) - every function, trigger, and script command

## Architecture

- [Overview](architecture/overview.md) - How REALM components fit together
- [Session Lifecycle](architecture/sessions.md) - Connection states and flow
- [Action Propagation](architecture/events.md) - the engine's one message pathway
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
