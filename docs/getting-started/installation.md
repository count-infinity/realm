# Installation

## Requirements

- Python 3.11 or higher (tested up to Python 3.14)
- pip or uv for package management

## Quick Install

```bash
# Clone the repository
git clone https://github.com/realm-mud/realm.git
cd realm

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"
```

## Optional Dependencies

### WebSocket Support

```bash
pip install -e ".[websocket]"
```

### PostgreSQL Support

```bash
pip install -e ".[postgres]"
```

### All Optional Dependencies

```bash
pip install -e ".[dev,websocket,postgres]"
```

## Verify Installation

```bash
# Run the test suite
pytest

# Start a test server
realm start
```

Then connect with telnet:

```bash
telnet localhost 4000
```

You should see the welcome screen immediately.

## Next Steps

- [Quick Start](quickstart.md) - Run your first server
- [Your First Game](first-game.md) - Build a simple world
