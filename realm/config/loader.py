"""
Configuration loader for REALM.

Finds and loads user's config.py, merging with defaults.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from realm.config.defaults import get_default_settings

if TYPE_CHECKING:
    from realm.server.game import GameServer

logger = logging.getLogger(__name__)


@dataclass
class Settings:
    """
    Loaded configuration settings.

    Contains all settings plus any callbacks defined in user's config.
    """

    # Server settings
    game_name: str = "REALM"
    debug: bool = False

    # Network settings
    telnet_host: str = "0.0.0.0"
    telnet_port: int = 4000
    websocket_host: str = "0.0.0.0"
    websocket_port: int = 4001

    # Protocol toggles
    enable_telnet: bool = True
    enable_websocket: bool = False

    # Softcode scripting ($commands, ^listens, ON_EVENT triggers)
    enable_scripting: bool = True

    # Paths (resolved to absolute)
    db_path: Path = field(default_factory=lambda: Path("data/game.db"))
    welcome_file: Path = field(default_factory=lambda: Path("data/welcome.txt"))
    game_dir: Path = field(default_factory=Path.cwd)

    # Persistence
    flush_interval: float = 30.0

    # Callbacks (optional, from user config)
    init_world: Callable[[GameServer], Awaitable[None]] | None = None
    on_start: Callable[[GameServer], Awaitable[None]] | None = None
    on_stop: Callable[[GameServer], Awaitable[None]] | None = None
    register_commands: Callable[[GameServer], None] | None = None
    register_protocols: Callable[[GameServer], None] | None = None

    # Raw config dict for advanced access
    _raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a raw config value by key."""
        return self._raw.get(key, default)


def load_config(game_dir: Path | None = None) -> Settings:
    """
    Load configuration from a game directory.

    Looks for config.py in the game directory (or current directory).
    Merges user settings with defaults.

    Args:
        game_dir: Path to game directory. Defaults to current working directory.

    Returns:
        Settings object with all configuration.

    Raises:
        FileNotFoundError: If game_dir doesn't exist.
    """
    if game_dir is None:
        game_dir = Path.cwd()
    else:
        game_dir = Path(game_dir).resolve()

    if not game_dir.exists():
        raise FileNotFoundError(f"Game directory not found: {game_dir}")

    # Start with defaults
    config = get_default_settings()

    # Try to load config.py
    config_file = game_dir / "config.py"
    user_config: dict[str, Any] = {}

    if config_file.exists():
        user_config = _load_config_file(config_file, game_dir)
        # Merge user config over defaults
        config.update(user_config)
        logger.info(f"Loaded config from {config_file}")
    else:
        # Also check for legacy realm_config.py
        legacy_config = game_dir / "realm_config.py"
        if legacy_config.exists():
            user_config = _load_config_file(legacy_config, game_dir)
            config.update(user_config)
            logger.warning(
                f"Using legacy {legacy_config.name}. "
                "Consider renaming to config.py"
            )

    # Build Settings object
    settings = Settings(
        game_name=config.get('GAME_NAME', 'REALM'),
        debug=config.get('DEBUG', False),
        telnet_host=config.get('TELNET_HOST', '0.0.0.0'),
        telnet_port=config.get('TELNET_PORT', 4000),
        websocket_host=config.get('WEBSOCKET_HOST', '0.0.0.0'),
        websocket_port=config.get('WEBSOCKET_PORT', 4001),
        enable_telnet=config.get('ENABLE_TELNET', True),
        enable_websocket=config.get('ENABLE_WEBSOCKET', False),
        enable_scripting=config.get('ENABLE_SCRIPTING', True),
        db_path=_resolve_path(game_dir, config.get('DB_PATH', 'data/game.db')),
        welcome_file=_resolve_path(game_dir, config.get('WELCOME_FILE', 'data/welcome.txt')),
        game_dir=game_dir,
        flush_interval=config.get('FLUSH_INTERVAL', 30.0),
        init_world=config.get('init_world'),
        on_start=config.get('on_start'),
        on_stop=config.get('on_stop'),
        register_commands=config.get('register_commands'),
        register_protocols=config.get('register_protocols'),
        _raw=config,
    )

    return settings


def _load_config_file(config_file: Path, game_dir: Path) -> dict[str, Any]:
    """
    Load a Python config file and extract its settings.

    Args:
        config_file: Path to config.py
        game_dir: Game directory (added to sys.path for imports)

    Returns:
        Dictionary of settings from the config file.
    """
    spec = importlib.util.spec_from_file_location("game_config", config_file)
    if not spec or not spec.loader:
        logger.error(f"Could not load config from {config_file}")
        return {}

    module = importlib.util.module_from_spec(spec)

    # Add game_dir to sys.path so config can import from game
    # Keep it permanently - callbacks like init_world need to import game modules
    if str(game_dir) not in sys.path:
        sys.path.insert(0, str(game_dir))
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        logger.error(f"Error loading {config_file}: {e}")
        raise

    # Extract public attributes
    config: dict[str, Any] = {}
    for key in dir(module):
        if not key.startswith('_'):
            config[key] = getattr(module, key)

    return config


def _resolve_path(game_dir: Path, path_str: str) -> Path:
    """
    Resolve a path relative to the game directory.

    Absolute paths are returned unchanged.
    Relative paths are resolved from game_dir.
    """
    path = Path(path_str)
    if path.is_absolute():
        return path
    return game_dir / path
