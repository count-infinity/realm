# Contributing

Thank you for your interest in contributing to REALM!

## Development Setup

```bash
# Clone and install
git clone https://github.com/realm-mud/realm.git
cd realm
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest

# Run type checking
mypy realm

# Run linter
ruff check realm
```

## Code Style

- Follow PEP 8
- Use type hints for all function signatures
- Use `ruff` for linting
- Maximum line length: 100 characters

## Pull Request Process

1. Create a feature branch
2. Write tests for new functionality
3. Ensure all tests pass
4. Update documentation if needed
5. Submit PR with clear description

## Architecture Guidelines

- Keep protocols in `gateway/`
- Keep game logic in `server/`
- Keep core abstractions in `core/`
- Events for decoupled communication
- Behaviors for extensible object logic
