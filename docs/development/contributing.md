# Contributing

Thank you for your interest in contributing to REALM!

## Development Setup

```bash
# Clone and install
git clone https://github.com/count-infinity/realm.git
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

## Where new code goes

`tests/test_boundaries.py` is the rule; it runs with the suite (there is no
separate CI workflow). In short:

- **Game meaning goes in a feature.** A command, a behavior, a softcode
  function, an action type, a setting: put it in the feature that owns it
  (`realm/std/<name>/`, declared in its `feature.py`) or a new one. A game
  system and its combat ruleset go in `realm/games/<name>/`.
- **The kernel holds mechanisms only.** `realm/core`, `scripting`,
  `commands`, `permissions`, `persistence`, `gateway`, `server`, `config`,
  `packs` and `realm/features.py` import nothing from `realm/std` or
  `realm/games` (`test_kernel_imports_nothing_above_it`). When kernel code
  needs a feature to take part (a fallback for unknown input, a gate on
  walking, a renderer), add a seam: a `Feature` declaration the kernel calls
  through `World`.
- **A feature imports another only when it requires it**
  (`test_feature_requires_match_imports`). For an optional integration, use
  the other feature's service: `world.services.get("social")` is None in a
  world without it. Naming another feature's action types
  (`realm.std.<x>.actions`) is allowed.
- **`std` does not import `games`** (`test_std_features_do_not_import_games`).
- **No module-global setters.** Put state on `World`, its `services`, or a
  `Settings` key.

`test_bare_kernel_boots` and `test_stock_game_is_only_a_feature_list` keep
the kernel usable on its own: a world of no features boots, scripts, saves
and loads, and loads no feature module.

- Keep protocols in `gateway/`.
- Events (propagation) for decoupled communication; behaviors for object logic.
