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
from typing import TYPE_CHECKING

from realm.config.loader import Settings
from realm.core.world import World, find_world, set_world

if TYPE_CHECKING:
    from realm.features import FeatureSet
    from realm.gateway.session import SessionManager

logger = logging.getLogger(__name__)


def build_world(store, settings: Settings | None = None, *,
                sessions: SessionManager | None = None,
                defer_timers: bool = False,
                features: FeatureSet | None = None) -> World:
    """Wire the engine around an already-open ``store``.

    ``features`` must already have run ``install_registries`` (the server
    does that before loading the world). Without it, the set named by
    ``settings.features`` (default ``CLASSIC``) is loaded and installed here.

    ``defer_timers`` makes softcode ``wait()`` fire only when a test pumps
    ``engine.waits.tick()`` (the Simulator's virtual clock).
    """
    from realm.commands.dispatcher import CommandDispatcher
    from realm.core.propagation import PropagationEngine
    from realm.scripting.engine import ScriptEngine
    from realm.scripting.sandbox import set_interpreter_recursion_limit

    cfg = settings or Settings()
    if features is None:
        from realm.features import load
        from realm.std import CLASSIC
        features = load(cfg.features or CLASSIC)
        features.install_registries()

    engine = PropagationEngine()        # a new world has a new engine
    closers: list[Callable[[], None]] = []

    # 1. Syntax settings (sigils, markers, delimiters, WORLD_BEAT) were
    # validated when ``cfg`` was built; their use sites read them through
    # ``setting()``. The recursion limit is interpreter state, not a value
    # anything reads, so it is applied here (process-wide, every thread:
    # see set_interpreter_recursion_limit) and restored on close.
    set_interpreter_recursion_limit(cfg.recursion_limit)
    closers.append(set_interpreter_recursion_limit)

    # 2. Commands (the features fill it in).
    dispatcher = CommandDispatcher()
    dispatcher.persistence = store
    dispatcher.session_manager = sessions

    # 3. The world. Install it now: everything below (a feature's
    # on_install, a game system reading its skill_def objects) reaches the
    # store through it. Closing it (the first closer, so it runs last)
    # restores the world that was current before. The ``rules`` feature
    # resolves GAME_SYSTEM into ``world.rules`` and installs the checks.
    world = World(settings=cfg, store=store, engine=engine, dispatcher=dispatcher,
                  rules=None, scripts=None, sessions=sessions, _closers=closers)
    previous = set_world(world)
    closers.insert(0, lambda: set_world(previous) if find_world() is world else None)

    # 4. Softcode: $-command fallback, ^listen / ON_<EVENT> observer, on_check hook.
    if cfg.enable_scripting:
        scripts = ScriptEngine(persistence=store)
        scripts.waits.defer = defer_timers
        scripts.dispatcher = dispatcher
        scripts.session_manager = sessions
        world.observe(scripts.handle_action)
        closers.append(scripts.waits.shutdown)
        dispatcher.set_unknown_handler(scripts.handle_unknown_command)
        world.scripts = scripts

    # 5. Everything else: the loaded features.
    features.install_runtime(world)
    return world


__all__ = ["build_world"]
