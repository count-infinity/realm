"""
The composition root: ``build_world`` wires the kernel, then the features.

``GameServer.start`` and the test ``Simulator`` both call ``build_world``,
so a test cannot pass on wiring the live game lacks. The kernel part is
the same for every game: syntax settings, the store, the dispatcher, the
script engine, the game system and the world tempo. Everything else comes
from the loaded features (``FeatureSet.install_runtime``): commands,
observers, the combat manager, queue kinds, reapers.

Each registration on ambient state (module setters, propagation observers)
pushes its undo onto ``World._closers``; ``World.close`` runs them newest
first and then restores the default registries.

What stays outside: opening and loading the store (the server does that
first), the login flow, the "Huh?" wrapper around the softcode fallback,
the tick and reap loops, and the protocol servers.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field, fields
from typing import TYPE_CHECKING, Any

from realm.config.loader import Settings

if TYPE_CHECKING:
    from realm.commands.dispatcher import CommandDispatcher
    from realm.core.propagation import PropagationEngine
    from realm.features import FeatureSet
    from realm.gateway.session import SessionManager
    from realm.scripting.engine import ScriptEngine
    from realm.systems.base import GameSystem

logger = logging.getLogger(__name__)


@dataclass
class World:
    """Everything ``build_world`` wired, plus how to unwire it."""

    settings: Settings
    store: Any
    engine: PropagationEngine
    dispatcher: CommandDispatcher
    rules: GameSystem
    scripts: ScriptEngine | None
    sessions: SessionManager | None
    features: FeatureSet | None = None
    services: dict[str, Any] = field(default_factory=dict)  # features' services, e.g. "combat"
    reapers: list[Callable] = field(default_factory=list)   # async (store) sweeps
    protocols: list[tuple[str, type, dict[str, Any]]] = field(default_factory=list)
    _closers: list[Callable[[], None]] = field(default_factory=list, repr=False)

    def add_closer(self, undo: Callable[[], None]) -> None:
        """Run ``undo`` when the world closes (newest first)."""
        self._closers.append(undo)

    def observe(self, observer: Callable) -> None:
        """Add a propagation observer for the life of this world."""
        self.engine.add_observer(observer)
        self._closers.append(lambda: self.engine.remove_observer(observer))

    def setting(self, key: str) -> Any:
        """A config value by its ``config.py`` key: a kernel key from
        ``Settings``, or a key a loaded feature declared (its value from
        ``config.py``, else the declared default)."""
        for f in fields(Settings):
            if f.metadata.get("key") == key:
                return getattr(self.settings, f.name)
        declared = self.features.settings if self.features is not None else {}
        if key not in declared:
            raise KeyError(f"{key!r} is not a kernel setting and no loaded feature "
                           f"declares it")
        return self.settings.raw.get(key, declared[key][0])

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


def build_world(store, settings: Settings | None = None, *,
                sessions: SessionManager | None = None,
                defer_timers: bool = False,
                features: FeatureSet | None = None) -> World:
    """Wire the engine around an already-open ``store``.

    ``features`` must already have run ``install_registries`` (the server
    does that before loading the world). Without it, the set named by
    ``settings.features`` (default ``CLASSIC``) is loaded and installed here.

    ``defer_timers`` makes softcode ``wait()`` fire only when a test pumps
    ``engine.tick_waits()`` (the Simulator's virtual clock).
    """
    from realm.commands.dispatcher import CommandDispatcher
    from realm.core import behaviors as behaviors_module
    from realm.core.checks import set_check_resolver, set_skill_defaults
    from realm.core.markup import set_markup_marker
    from realm.core.objects import set_check_hook
    from realm.core.propagation import get_engine
    from realm.core.verbs import set_emote_sigil
    from realm.gateway.session import set_heredoc_sigils
    from realm.persistence.manager import set_active_manager
    from realm.scripting.engine import ScriptEngine, set_script_engine
    from realm.scripting.functions import set_keyid_sigil
    from realm.scripting.inline import set_inline_delimiters
    from realm.scripting.sandbox import set_interpreter_recursion_limit
    from realm.scripting.triggers import set_trigger_sigils
    from realm.systems import resolve_game_system, set_game_system

    cfg = settings or Settings()
    if features is None:
        from realm.features import load
        from realm.std import CLASSIC
        features = load(cfg.features or CLASSIC)
        features.install_registries()

    engine = get_engine()
    closers: list[Callable[[], None]] = []

    # 1. Syntax. A bad value raises here, at boot, not mid-render.
    set_inline_delimiters(cfg.inline_open, cfg.inline_close)
    closers.append(set_inline_delimiters)
    set_trigger_sigils(command=cfg.command_sigil, listen=cfg.listen_sigil)
    closers.append(set_trigger_sigils)
    set_markup_marker(cfg.markup_marker)
    closers.append(set_markup_marker)
    set_emote_sigil(cfg.emote_sigil)
    closers.append(set_emote_sigil)
    set_keyid_sigil(cfg.keyid_sigil)
    closers.append(set_keyid_sigil)
    set_heredoc_sigils(cfg.heredoc_open, cfg.heredoc_close)
    closers.append(set_heredoc_sigils)
    # Process-wide, every thread (see set_interpreter_recursion_limit).
    set_interpreter_recursion_limit(cfg.recursion_limit)
    closers.append(set_interpreter_recursion_limit)

    # 2. The store every lookup goes through.
    set_active_manager(store)
    closers.append(lambda: set_active_manager(None))

    # 3. Commands (the features fill it in).
    dispatcher = CommandDispatcher()
    dispatcher.persistence = store
    dispatcher.session_manager = sessions

    # 4. Rules resolution: skill defaults and the check resolver.
    rules = resolve_game_system(cfg.game_system)
    set_game_system(rules)
    closers.append(lambda: set_game_system(None))
    set_skill_defaults(rules.skill_defaults())
    set_check_resolver(rules.resolve_check)
    closers.append(lambda: set_check_resolver(None))

    # 5. World tempo (ambient beat, default behavior cadence).
    previous_tick = behaviors_module.WORLD_TICK
    behaviors_module.set_world_tick(cfg.world_beat)
    closers.append(lambda: behaviors_module.set_world_tick(previous_tick))

    world = World(settings=cfg, store=store, engine=engine, dispatcher=dispatcher,
                  rules=rules, scripts=None, sessions=sessions, _closers=closers)

    # 6. Softcode: $-command fallback, ^listen / ON_<EVENT> observer, on_check hook.
    if cfg.enable_scripting:
        scripts = ScriptEngine(persistence=store)
        scripts.defer_waits = defer_timers
        scripts.dispatcher = dispatcher
        scripts.session_manager = sessions
        world.observe(scripts.handle_action)
        set_script_engine(scripts)
        closers.append(lambda: set_script_engine(None))
        set_check_hook(scripts.run_check_hook)
        closers.append(lambda: set_check_hook(None))
        closers.append(scripts.shutdown_waits)
        dispatcher.set_unknown_handler(scripts.handle_unknown_command)
        world.scripts = scripts

    # 7. Everything else: the loaded features.
    features.install_runtime(world)
    return world


__all__ = ["World", "build_world"]
