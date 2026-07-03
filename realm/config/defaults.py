"""
Default settings for REALM.

Users override these in their game's config.py file.
"""

from typing import Any

# Server settings
GAME_NAME: str = "REALM"
DEBUG: bool = False

# Network settings
TELNET_HOST: str = "0.0.0.0"
TELNET_PORT: int = 4000
WEBSOCKET_HOST: str = "0.0.0.0"
WEBSOCKET_PORT: int = 4001

# Protocol toggles
ENABLE_TELNET: bool = True
ENABLE_WEBSOCKET: bool = False

# Softcode scripting ($commands, ^listens, ON_EVENT triggers)
ENABLE_SCRIPTING: bool = True

# Database settings
# Relative paths are resolved from the game directory
DB_PATH: str = "data/game.db"

# Welcome screen
# Relative paths are resolved from the game directory
WELCOME_FILE: str = "data/welcome.txt"

# Persistence settings
FLUSH_INTERVAL: float = 30.0  # Seconds between auto-saves

# World heartbeat: seconds between behavior ticks (0 disables)
TICK_INTERVAL: float = 4.0


def get_default_settings() -> dict[str, Any]:
    """
    Return all default settings as a dictionary.

    This is used by the config loader to provide defaults
    that can be overridden by user config.
    """
    return {
        'GAME_NAME': GAME_NAME,
        'DEBUG': DEBUG,
        'TELNET_HOST': TELNET_HOST,
        'TELNET_PORT': TELNET_PORT,
        'WEBSOCKET_HOST': WEBSOCKET_HOST,
        'WEBSOCKET_PORT': WEBSOCKET_PORT,
        'ENABLE_TELNET': ENABLE_TELNET,
        'ENABLE_WEBSOCKET': ENABLE_WEBSOCKET,
        'ENABLE_SCRIPTING': ENABLE_SCRIPTING,
        'DB_PATH': DB_PATH,
        'WELCOME_FILE': WELCOME_FILE,
        'FLUSH_INTERVAL': FLUSH_INTERVAL,
        'TICK_INTERVAL': TICK_INTERVAL,
    }


# For convenient import
DEFAULT_SETTINGS = get_default_settings()
