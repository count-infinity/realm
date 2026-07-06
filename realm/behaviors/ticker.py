"""
ScriptTickerBehavior: a heartbeat for softcode.

The escape hatch that makes behaviors builder-authorable: attach this to
any object and its ``on_tick`` attribute runs as softcode on a cadence —
scheduling stays on the server's one heartbeat, the *logic* lives
entirely in a db attribute the builder can @set.

    @behavior parrot = script_ticker, interval:8
    @set parrot/on_tick = say Pieces of eight!

A softcode-only wanderer (the MUSH ``&wander`` pattern, minus the @wait
chains):

    @set critter/on_tick = exits = [e for e in contents(here) if has_tag(e, 'exit')]
        if exits: move(name(exits[rand(0, len(exits) - 1)]))

Scripted ``move`` routes through the real movement pathway, so locks,
closed doors, and guard behaviors apply. Runaway machines halt like any
other softcode: ``@tag <obj> = halt``, or detach the behavior.

Parameters:
    interval: ticks between runs (default 4; at TICK_INTERVAL=4s that's
        ~16 seconds). Countdown persists in ``db.script_tick_wait``.
    attr: the attribute holding the script (default ``on_tick``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.behaviors import Behavior, BehaviorRegistry

if TYPE_CHECKING:
    from realm.core.objects import GameObject


@BehaviorRegistry.register
class ScriptTickerBehavior(Behavior):
    """Runs the owner's ``on_tick`` softcode attribute periodically."""

    behavior_id = "script_ticker"

    @property
    def should_tick(self) -> bool:
        return True

    async def tick(self, obj: GameObject, delta: float) -> None:
        from realm.scripting.engine import get_script_engine

        wait = int(obj.db.get('script_tick_wait') or 0)
        if wait > 0:
            obj.db.script_tick_wait = wait - 1
            return
        obj.db.script_tick_wait = max(0, int(self.get_param('interval', 4)) - 1)

        engine = get_script_engine()
        if engine is None:
            return
        attr = str(self.get_param('attr', 'on_tick'))
        await engine.run_object_script(obj, attr)


__all__ = ["ScriptTickerBehavior"]
