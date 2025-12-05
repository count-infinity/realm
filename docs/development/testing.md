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
tests/
├── test_session.py      # Session and SessionManager tests
├── test_objects.py      # GameObject tests
├── test_events.py       # EventBus tests
├── test_dispatcher.py   # Command dispatcher tests
└── test_persistence.py  # Database tests
```

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
