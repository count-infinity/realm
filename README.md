# REALM

Real-time Event-Action Layered MUD framework in Python.

## Installation

```bash
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest
```

## Running the Space Game

The space game is a GURPS-based MUD built on REALM:

```bash
cd examples/spacegame
realm start --init    # First time: initialize world
realm start           # Subsequent runs
```

Then connect via telnet:
```bash
telnet localhost 4000
```

Commands once connected:
- `create <name> <password>` - Create a new character
- `connect <name> <password>` - Log in to existing character
- `look` - Look around
- `north`, `south`, `east`, `west` - Move through exits
- `say <message>` - Speak to the room
- `quit` - Disconnect

Stop the server with **Ctrl+C**.

### Combat Demo (Non-Interactive)

```bash
python -m examples.spacegame.game
```

This runs a combat simulation between a Marine and a Space Pirate using the GURPS 3d6 roll-under system.

## Features

- **GameObject system** - Everything is a GameObject with tags and behaviors
- **Event-driven architecture** - Two-phase validate/execute event model
- **Swappable combat rulesets** - D20 (D&D 5e) and GURPS 3d6 included
- **Softcode scripting** - PennMUSH-style $command and ^listen patterns
- **Permission system** - Role hierarchy with lock expressions
- **OLC commands** - @create, @dig, @set, @destroy, etc.
