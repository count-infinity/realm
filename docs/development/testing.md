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
