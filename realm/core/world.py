"""
The running world: one handle instead of module-global setters.

``build_world`` (``realm/server/world.py``) builds a :class:`World` and
installs it with :func:`set_world`. Code that needs the store, the
propagation engine, the script engine, the rules system or a feature's
service asks the current world:

    get_world().store
    get_world().services.get("combat")
    setting("EMOTE_SIGIL")

``_current`` is the one mutable module global the kernel keeps for this.
Two worlds in one process (a test that boots a second server on the same
file) switch with :func:`use_world`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, fields
from functools import cache
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.commands.dispatcher import CommandDispatcher
    from realm.config.loader import Settings
    from realm.core.propagation import PropagationEngine
    from realm.features import FeatureSet
    from realm.gateway.session import SessionManager
    from realm.scripting.engine import ScriptEngine

logger = logging.getLogger(__name__)

_MISSING: Any = object()


@cache
def _kernel_keys() -> dict[str, tuple[str, Any]]:
    """config key -> (Settings field name, class default)."""
    from realm.config.loader import Settings
    return {f.metadata["key"]: (f.name, f.default)
            for f in fields(Settings) if "key" in f.metadata}


@dataclass
class World:
    """Everything ``build_world`` wired, plus how to unwire it."""

    settings: Settings
    store: Any
    engine: PropagationEngine
    dispatcher: CommandDispatcher
    rules: Any | None                            # the game system (the rules feature's)
    scripts: ScriptEngine | None
    sessions: SessionManager | None
    features: FeatureSet | None = None
    #: Where new characters and roomless players are placed (the server
    #: sets it from a ``start_room``-tagged room, or makes one).
    startup_room: Any = None
    #: (order, async (world, session, line) -> bool): input a feature
    #: consumes before the dispatcher sees it (character creation).
    input_interceptors: list[tuple[int, Callable]] = field(default_factory=list)
    services: dict[str, Any] = field(default_factory=dict)  # e.g. "combat", "checks"
    reapers: list[Callable] = field(default_factory=list)   # async (store) sweeps
    protocols: list[tuple[str, type, dict[str, Any]]] = field(default_factory=list)
    #: exit destination resolvers by name: (async fn, shared_destination)
    dest_resolvers: dict[str, tuple[Callable, bool]] = field(default_factory=dict)
    #: (obj, skill) -> int condition modifiers (``feature.check_modifier``);
    #: the ``rules`` feature folds them into every check.
    check_modifiers: list[Callable] = field(default_factory=list)
    #: (async (actor, exit_obj, direction) -> str | None, on_fail reason)
    traversal_gates: list[tuple[Callable, str]] = field(default_factory=list)
    #: async (actor, origin, destination, exit_obj, *, fleeing)
    after_traverse: list[Callable] = field(default_factory=list)
    sight_rules: list[Callable] = field(default_factory=list)   # (viewer, obj) -> bool | None
    markers: list[Callable] = field(default_factory=list)       # (obj, looker) -> str | None
    name_resolvers: list[Callable] = field(default_factory=list)      # perception
    speech_renderers: list[Callable] = field(default_factory=list)    # per listener
    group_formatter: Callable | None = None                           # contents lines
    _closers: list[Callable[[], None]] = field(default_factory=list, repr=False)

    def add_closer(self, undo: Callable[[], None]) -> None:
        """Run ``undo`` when the world closes (newest first)."""
        self._closers.append(undo)

    def observe(self, observer: Callable) -> None:
        """Add a propagation observer for the life of this world."""
        self.engine.add_observer(observer)
        self._closers.append(lambda: self.engine.remove_observer(observer))

    def setting(self, key: str, default: Any = _MISSING) -> Any:
        """A config value by its ``config.py`` key: a kernel key from
        ``Settings``, or a key a loaded feature declared (its value from
        ``config.py``, else the declared default). A key neither knows is
        ``default`` when given, else KeyError."""
        kernel = _kernel_keys().get(key)
        if kernel is not None:
            return getattr(self.settings, kernel[0])
        declared = self.features.settings if self.features is not None else {}
        if key not in declared:
            if default is not _MISSING:
                return default
            raise KeyError(f"{key!r} is not a kernel setting and no loaded feature "
                           f"declares it")
        return self.settings.raw.get(key, declared[key][0])

    def changed_settings(self) -> dict[str, Any]:
        """Every config key whose value differs from its default: kernel
        keys from ``Settings``, and feature-declared keys ``config.py`` set."""
        out: dict[str, Any] = {}
        for key, (name, default) in _kernel_keys().items():
            value = getattr(self.settings, name)
            if value != default:
                out[key] = value
        declared = self.features.settings if self.features is not None else {}
        for key, (default, *_rest) in declared.items():
            if key in self.settings.raw and self.settings.raw[key] != default:
                out[key] = self.settings.raw[key]
        return out

    def close(self) -> None:
        """Undo every ambient registration, newest first, then restore the
        default registries. Safe to call twice."""
        while self._closers:
            undo = self._closers.pop()
            try:
                undo()
            except Exception:
                logger.exception("World.close: an undo step failed")
        if self.features is not None:
            features, self.features = self.features, None
            features.close(self)


_current: World | None = None


def get_world() -> World:
    """The running world. Raises RuntimeError when none is installed."""
    if _current is None:
        raise RuntimeError("No world is installed (build_world, a Simulator, or the "
                           "`world` test fixture installs one).")
    return _current


def find_world() -> World | None:
    """The running world or None, for code that legitimately runs without one."""
    return _current


def set_world(world: World | None) -> World | None:
    """Install ``world`` (or clear with None); return the previous one."""
    global _current
    previous, _current = _current, world
    return previous


@contextmanager
def use_world(world: World) -> Iterator[World]:
    """Install ``world`` for the block, then restore the previous one."""
    previous = set_world(world)
    try:
        yield world
    finally:
        set_world(previous)


def setting(key: str, default: Any = _MISSING) -> Any:
    """The current world's setting by its config key, or the ``Settings``
    class default when no world is installed, so pure helpers (markup,
    inline blocks) work in a unit test that builds nothing. A feature's key
    with no world (or one its feature isn't loaded in) is ``default`` when
    given, else KeyError."""
    world = _current
    if world is not None:
        return world.setting(key, default)
    kernel = _kernel_keys().get(key)
    if kernel is not None:
        return kernel[1]
    if default is not _MISSING:
        return default
    raise KeyError(f"{key!r} is not a kernel setting (no world is installed to "
                   f"ask its features)")


__all__ = ["World", "get_world", "find_world", "set_world", "use_world", "setting"]
