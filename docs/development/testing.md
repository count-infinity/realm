# Testing

REALM uses pytest with pytest-asyncio for testing.

## Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_session.py

# Run specific test
pytest tests/test_session.py::test_session_creation
```

## Test Structure

```
tests/                        # 800+ tests, ~2s total
├── test_propagation.py       # the action pipeline
├── test_objects.py / test_tags.py
├── test_dispatcher.py / test_commands.py / test_builtin_commands.py
├── test_scripting.py / test_script_engine.py / test_softcode_builders.py
├── test_combat*.py / test_ranged_combat.py
├── test_behaviors.py / test_disposition.py / test_economy.py / test_party.py
├── test_systems.py           # GameSystem, chargen, auth
├── test_query_zones.py / test_help_and_details.py / test_oob.py
├── test_persistence.py / test_session.py / test_permissions.py
└── test_olc.py / test_infiltration.py / test_spacegame.py
```

Live end-to-end drives (telnet scripts that boot a real server) live
outside the repo during development and verify each feature package;
the tutorial's command sequence is one of them.

## Writing Tests

```python
import pytest
from realm.gateway.session import Session, SessionManager

@pytest.mark.asyncio
async def test_session_creation():
    """Test that sessions are created with correct defaults."""
    manager = SessionManager()

    messages = []
    async def mock_writer(msg):
        messages.append(msg)

    session = await manager.create_session(
        protocol="test",
        address="127.0.0.1:1234",
        writer=mock_writer,
    )

    assert session.protocol == "test"
    assert session.address == "127.0.0.1:1234"
```

## Mocking Sessions

```python
from unittest.mock import AsyncMock

# Create a mock session for testing commands
session = AsyncMock(spec=Session)
session.player = mock_player
session.send = AsyncMock()
```

## Integration testing with the Simulator

For "run this and see what a player would see," `realm.testing.Simulator`
wires the *real* engine in-process — propagation, softcode, the command
dispatcher, and a game system — so you drive a mini-world exactly as a
live server would, with no sockets or database file.

```python
import pytest
from realm.testing import Simulator

@pytest.fixture
def sim():
    s = Simulator()               # defaults to the GURPS system
    try:
        yield s
    finally:
        s.close()                 # restores ambient singletons

@pytest.mark.asyncio
async def test_npc_greets(sim):
    room  = sim.room("Cantina")
    zeke  = sim.obj("Zeke", location=room)
    alice = sim.player("Alice", location=room)   # gets a live Session

    # Run softcode AS zeke (the @eval path):
    await sim.eval(zeke, "pemit(enactor, 'Welcome, ' + name(enactor))",
                   enactor=alice)
    assert "Welcome, Alice" in sim.seen(alice)   # what Alice received

    # Or run a real player command through the dispatcher:
    sim.obj("sword", location=room, tags=["thing"])
    await sim.do(alice, "get sword")
    assert "You pick up a sword." in sim.seen(alice)
```

- `sim.room / obj / player` build the world (`player` returns an object
  with a live session reachable via `seen()`).
- `sim.eval(obj, code, enactor=…)` runs softcode as `obj`; returns
  `(result, error)`.
- `await sim.do(player, "command")` runs a real command through the
  dispatcher.
- `sim.seen(player)` drains and returns that player's messages.
- Choose the ruleset with `Simulator(game_system="realm.systems.D20System")`.

Because both paths go through the real engine, the transcript is exactly
what happens live — which makes it the natural way to test data-driven
content (a `class_def`, a `skill_def`, a scripted NPC) end-to-end.
