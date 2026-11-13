"""
Configuration for REALM: the ``Settings`` dataclass and ``load_config``.

``Settings`` is the only place a config key and its default are declared.
Each field made with :func:`setting` is also an UPPERCASE ``config.py`` key;
``load_config`` reads exactly those keys, ``KNOWN_CONFIG_KEYS`` is derived
from them, and ``scripts/gen_config_docs.py`` writes the reference page from
their docs. Adding a config key is one line here.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.server.game import GameServer

logger = logging.getLogger(__name__)


def setting(default: Any, key: str, doc: str, *, path: bool = False) -> Any:
    """A ``Settings`` field that is also a ``config.py`` key.

    ``path=True`` marks a filesystem path: ``load_config`` resolves a relative
    value against the game directory.
    """
    return field(default=default, metadata={"key": key, "doc": doc, "path": path})


def callback(doc: str) -> Any:
    """A ``Settings`` field filled from a same-named function in ``config.py``."""
    return field(default=None, metadata={"callback": True, "doc": doc})


@dataclass
class Settings:
    """Every setting a game can make in its ``config.py``, with its default."""

    # --- Game ---
    game_name: str = setting(
        "REALM", "GAME_NAME", "Name shown on the welcome screen and in logs.")
    debug: bool = setting(
        False, "DEBUG", "Log at DEBUG level (same as `realm start --debug`).")
    game_system: Any = setting(
        "realm.systems.GurpsSystem", "GAME_SYSTEM",
        "Dotted import path to the GameSystem subclass that holds the rules "
        "(chargen, checks, advancement, combat pairing, currency). Choose it "
        "once, before the first character is created.")
    encoding: str = setting(
        "utf-8", "ENCODING",
        "Text encoding for telnet input and output (`latin-1` or `cp437` "
        "only for legacy clients).")

    # --- Network ---
    telnet_host: str = setting("0.0.0.0", "TELNET_HOST", "Telnet listen address.")
    telnet_port: int = setting(4000, "TELNET_PORT", "Telnet listen port.")
    websocket_host: str = setting("0.0.0.0", "WEBSOCKET_HOST", "WebSocket listen address.")
    websocket_port: int = setting(4001, "WEBSOCKET_PORT", "WebSocket listen port.")
    enable_telnet: bool = setting(True, "ENABLE_TELNET", "Run the telnet server.")
    enable_websocket: bool = setting(
        False, "ENABLE_WEBSOCKET", "Run the WebSocket server (needs aiohttp).")

    # --- Softcode ---
    enable_scripting: bool = setting(
        True, "ENABLE_SCRIPTING",
        "Run softcode: `$`-commands, `^`-listens, `ON_<EVENT>` hooks, inline blocks.")
    inline_open: str = setting(
        "[[", "INLINE_OPEN",
        "Opening delimiter of an inline softcode block in text.")
    inline_close: str = setting(
        "]]", "INLINE_CLOSE",
        "Closing delimiter of an inline softcode block in text.")
    command_sigil: str = setting(
        "$", "COMMAND_SIGIL",
        "Prefix of a softcode command attribute (`$greet *:...`).")
    listen_sigil: str = setting(
        "^", "LISTEN_SIGIL",
        "Prefix of a softcode listen attribute (`^*hello*:...`).")
    markup_marker: str = setting(
        "|", "MARKUP_MARKER",
        "Color-markup marker (`|r` red, `|n` reset).")
    emote_sigil: str = setting(
        "/", "EMOTE_SIGIL",
        "Reference sigil in rich emotes (`pose waves at /Bob`).")
    keyid_sigil: str = setting(
        "$", "KEYID_SIGIL",
        "Prefix of a friendly keyid reference (`get('$banknet_core')`). May not start with `#`.")
    heredoc_open: str = setting(
        "'''", "HEREDOC_OPEN",
        "A line ending in this starts a multi-line block.")
    heredoc_close: str = setting(
        "'''", "HEREDOC_CLOSE",
        "A line equal to this ends a multi-line block.")
    recursion_limit: int = setting(
        1000, "RECURSION_LIMIT",
        "Process-wide Python recursion limit (every thread, not per script). "
        "Rejected below 100 or above 100000.")

    # --- Files ---
    db_path: Path = setting(
        Path("data/game.db"), "DB_PATH", "SQLite database file.", path=True)
    welcome_file: Path = setting(
        Path("data/welcome.txt"), "WELCOME_FILE", "Text shown on connection.", path=True)
    welcome_banner: str | None = setting(
        None, "WELCOME_BANNER", "Inline welcome text. When set, it wins over WELCOME_FILE.")

    # --- Time ---
    tick_interval: float = setting(
        0.1, "TICK_INTERVAL",
        "Seconds between server pulses (0 disables). Waits, one-shots and "
        "reapers land on it; behaviors keep their own cadence.")
    world_beat: float = setting(
        4.0, "WORLD_BEAT",
        "Seconds in one out-of-combat round (poison, regen) and the default "
        "cadence of pulse-counting behaviors.")
    reap_interval: float = setting(
        5.0, "REAP_INTERVAL",
        "Seconds between housekeeping sweeps (idle instances, wilderness cells, expired objects).")
    flush_interval: float = setting(
        30.0, "FLUSH_INTERVAL", "Seconds between saves of changed objects to the database.")

    # --- Combat ---
    combat_ruleset: str | None = setting(
        None, "COMBAT_RULESET",
        "Combat ruleset name. Unset, the game system picks its own; set it "
        "only to mix systems on purpose.")
    show_rolls: bool = setting(
        False, "SHOW_ROLLS",
        "Show dice detail on combat messages. Players override with `showrolls on|off`.")
    combat_beat_min: float = setting(4.0, "COMBAT_BEAT_MIN", "Shortest combat round, in seconds.")
    combat_beat_max: float = setting(120.0, "COMBAT_BEAT_MAX", "Longest combat round, in seconds.")
    combat_beat_default: float = setting(
        15.0, "COMBAT_BEAT_DEFAULT",
        "Default combat round, in seconds.")

    # --- Callbacks: functions of the same name in config.py ---
    init_world: Callable[[GameServer], Awaitable[None]] | None = callback(
        "`async def init_world(server)`: runs once, when the database is empty.")
    on_start: Callable[[GameServer], Awaitable[None]] | None = callback(
        "`async def on_start(server)`: runs after the server has started.")
    on_stop: Callable[[GameServer], Awaitable[None]] | None = callback(
        "`async def on_stop(server)`: runs when the server stops.")
    register_commands: Callable[[GameServer], None] | None = callback(
        "`def register_commands(server)`: add the game's own commands.")
    register_protocols: Callable[[GameServer], None] | None = callback(
        "`def register_protocols(server)`: add custom network protocols.")

    # --- Set by load_config, not config keys ---
    game_dir: Path = field(default_factory=Path.cwd)
    _raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        # A path given as a string (GameServer(db_path=":memory:")) is a Path.
        for f in fields(self):
            if f.metadata.get("path"):
                value = getattr(self, f.name)
                if value is not None and not isinstance(value, Path):
                    setattr(self, f.name, Path(value))

    def get(self, key: str, default: Any = None) -> Any:
        """A raw ``config.py`` value by name, including the game's own constants."""
        return self._raw.get(key, default)


#: Every UPPERCASE key ``load_config`` consumes. A config.py may define other
#: constants for its own use; an unknown key that is a near miss of one of
#: these (WELCOME_BANER) warns at boot.
KNOWN_CONFIG_KEYS = frozenset(
    f.metadata["key"] for f in fields(Settings) if "key" in f.metadata)


def _warn_near_miss_keys(user_config: dict[str, Any]) -> None:
    """Warn about probable typos of real config keys.

    A misspelled key (``TELNET_PROT``) is otherwise ignored without a
    trace and the default silently wins — the config-file cousin of a
    typo'd action type. Only close matches warn; arbitrary user constants
    stay legal and silent.
    """
    import difflib
    for key in user_config:
        if not key.isupper() or key in KNOWN_CONFIG_KEYS:
            continue
        close = difflib.get_close_matches(key, KNOWN_CONFIG_KEYS, n=1,
                                          cutoff=0.8)
        if close:
            logger.warning(
                f"config: unknown key {key!r} looks like a typo of "
                f"{close[0]!r} — it is being IGNORED"
            )


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

    config_file = game_dir / "config.py"
    user_config: dict[str, Any] = {}
    if config_file.exists():
        user_config = _load_config_file(config_file, game_dir)
        _warn_near_miss_keys(user_config)
        logger.info(f"Loaded config from {config_file}")
    else:
        logger.warning(f"No config.py in {game_dir}; running on built-in defaults")

    values: dict[str, Any] = {}
    for f in fields(Settings):
        if "key" in f.metadata:
            value = user_config.get(f.metadata["key"], f.default)
            if f.metadata["path"] and value is not None:
                value = _resolve_path(game_dir, value)
            values[f.name] = value
        elif f.metadata.get("callback") and f.name in user_config:
            values[f.name] = user_config[f.name]
    return Settings(**values, game_dir=game_dir, _raw=user_config)


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


def _resolve_path(game_dir: Path, path_str: str | Path) -> Path:
    """
    Resolve a path relative to the game directory.

    Absolute paths are returned unchanged.
    Relative paths are resolved from game_dir.
    """
    path = Path(path_str)
    if path.is_absolute():
        return path
    return game_dir / path
