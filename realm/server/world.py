"""
The composition root: ``build_world`` wires every engine subsystem.

``GameServer.start`` and the test ``Simulator`` both call ``build_world``,
so a test cannot pass on wiring the live game lacks. Each registration it
makes on ambient state (module setters, propagation observers) pushes its
undo onto ``World._closers``; ``World.close`` runs them newest first.

What stays outside: opening and loading the store (the server does that
before calling ``build_world``), the login flow, the "Huh?" wrapper around
the softcode fallback, the tick and reap loops, and the protocol servers.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from realm.config.loader import Settings

if TYPE_CHECKING:
    from realm.commands.dispatcher import CommandDispatcher
    from realm.core.propagation import PropagationEngine
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
    services: dict[str, Any] = field(default_factory=dict)
    _closers: list[Callable[[], None]] = field(default_factory=list, repr=False)

    def close(self) -> None:
        """Undo every ambient registration, newest first. Safe to call twice."""
        while self._closers:
            undo = self._closers.pop()
            try:
                undo()
            except Exception:
                logger.exception("World.close: an undo step failed")


def build_world(store, settings: Settings | None = None, *,
                sessions: SessionManager | None = None,
                defer_timers: bool = False) -> World:
    """Wire the engine around an already-open ``store``.

    ``defer_timers`` makes softcode ``wait()`` fire only when a test pumps
    ``engine.tick_waits()`` (the Simulator's virtual clock).
    """
    from realm.combat.manager import CombatManager, set_combat_manager
    from realm.combat.system import create_combat_system, set_show_rolls_default
    from realm.commands.builtin import register_all_commands
    from realm.commands.dispatcher import CommandDispatcher
    from realm.core import behaviors as behaviors_module
    from realm.core.checks import set_check_resolver, set_skill_defaults
    from realm.core.markup import set_markup_marker
    from realm.core.objects import set_check_hook
    from realm.core.perception import stealth_observer
    from realm.core.propagation import get_engine
    from realm.core.verbs import set_emote_sigil
    from realm.gateway.session import set_heredoc_sigils
    from realm.persistence.manager import set_active_manager
    from realm.scripting.engine import ScriptEngine, set_script_engine
    from realm.scripting.functions import set_keyid_sigil
    from realm.scripting.inline import set_inline_delimiters
    from realm.scripting.sandbox import set_interpreter_recursion_limit
    from realm.scripting.triggers import set_trigger_sigils
    from realm.systems import equipment_observer, resolve_game_system, set_game_system
    from realm.systems.crime import crime_observer

    cfg = settings or Settings()
    engine = get_engine()
    closers: list[Callable[[], None]] = []

    def observe(observer) -> None:
        engine.add_observer(observer)
        closers.append(lambda: engine.remove_observer(observer))

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

    # 3. Commands.
    dispatcher = CommandDispatcher()
    dispatcher.persistence = store
    dispatcher.session_manager = sessions

    # 4. Softcode: $-command fallback, ^listen / ON_<EVENT> observer, on_check hook.
    scripts: ScriptEngine | None = None
    if cfg.enable_scripting:
        scripts = ScriptEngine(persistence=store)
        scripts.defer_waits = defer_timers
        scripts.dispatcher = dispatcher
        scripts.session_manager = sessions
        observe(scripts.handle_action)
        set_script_engine(scripts)
        closers.append(lambda: set_script_engine(None))
        set_check_hook(scripts.run_check_hook)
        closers.append(lambda: set_check_hook(None))
        closers.append(scripts.shutdown_waits)
        dispatcher.set_unknown_handler(scripts.handle_unknown_command)

    # 5. Loud actions break stealth, whoever performs them.
    observe(stealth_observer)

    # 6. Rules: skill defaults, check resolver, gear changes.
    rules = resolve_game_system(cfg.game_system)
    set_game_system(rules)
    closers.append(lambda: set_game_system(None))
    observe(equipment_observer)
    set_skill_defaults(rules.skill_defaults())
    set_check_resolver(rules.resolve_check)
    closers.append(lambda: set_check_resolver(None))

    # 7. Combat. COMBAT_RULESET overrides the system's own pairing.
    combat = CombatManager(
        create_combat_system(cfg.combat_ruleset or rules.ruleset_name),
        beat_min=cfg.combat_beat_min,
        beat_max=cfg.combat_beat_max,
        beat_default=cfg.combat_beat_default,
        session_manager=sessions,
    )
    set_combat_manager(combat)
    closers.append(lambda: set_combat_manager(None))
    closers.append(combat.stop_all)
    set_show_rolls_default(cfg.show_rolls)
    closers.append(lambda: set_show_rolls_default(False))
    observe(combat.hostile_observer)

    # 8. Crime: assaulting a player flags the attacker wanted.
    observe(crime_observer)

    # 9. World tempo (ambient beat, default behavior cadence).
    previous_tick = behaviors_module.WORLD_TICK
    behaviors_module.set_world_tick(cfg.world_beat)
    closers.append(lambda: behaviors_module.set_world_tick(previous_tick))

    # 10. The stock command set.
    register_all_commands(dispatcher)

    return World(
        settings=cfg,
        store=store,
        engine=engine,
        dispatcher=dispatcher,
        rules=rules,
        scripts=scripts,
        sessions=sessions,
        services={"combat": combat},
        _closers=closers,
    )


__all__ = ["World", "build_world"]
