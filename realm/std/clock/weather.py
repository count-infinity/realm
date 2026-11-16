"""
Weather per zone (MUD_PLAN 8).

A zone master with a ``weather`` attribute gets a current state rolled
each game hour, kept in ``weather_now``. ``weather`` is a list of
``[state, weight]`` pairs (a dict of state to weight works too), or a
softcode expression in the ``rule`` profile with ``hour`` and ``current``
bound (and every read-only function, ``time_of_day()`` among them),
returning the state. A change is
announced to the zone's outdoor rooms: the master's ``weather_messages``
line for the new state, else "The weather turns <state>." Weather has no
effect on rules; builders hook ``weather(here)``.
"""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Any

from realm.core.zones import MASTER_TAG, zone_masters, zone_rooms, zone_tags

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.std.clock.clock import WorldClock

logger = logging.getLogger(__name__)


def roll_weather(table: Any) -> str | None:
    """A state from a ``[[state, weight], ...]`` list or a ``{state: weight}``."""
    pairs = list(table.items()) if isinstance(table, dict) else [tuple(p) for p in table]
    pairs = [(str(s), float(w)) for s, w in pairs if float(w) > 0]
    if not pairs:
        return None
    return random.choices([s for s, _ in pairs], weights=[w for _, w in pairs])[0]


def _from_rule(master: GameObject, rule: str, hour: int) -> str | None:
    from realm.core.safe_eval import eval_expression
    from realm.scripting.namespace import build_namespace
    namespace, _frame = build_namespace(
        'rule', executor=master, enactor=master, location=master.location, subject=master,
        extra={"hour": hour, "current": master.db.get("weather_now")})
    try:
        state = eval_expression(rule, namespace)
    except Exception as exc:
        logger.warning(f"{master.name}: weather rule failed ({exc}); weather unchanged")
        return None
    return str(state) if state else None


async def roll_zones(clock: WorldClock, hour: int) -> None:
    """Roll each weather-bearing zone master's state; announce changes."""
    from realm.core.query import find_objects
    for master in find_objects(tag=MASTER_TAG):
        table = master.db.get("weather")
        if not table:
            continue
        state = (_from_rule(master, table, hour) if isinstance(table, str)
                 else roll_weather(table))
        if state is None or state == master.db.get("weather_now"):
            continue
        master.db.weather_now = state
        messages = master.db.get("weather_messages") or {}
        line = messages.get(state) or f"The weather turns {state}."
        for zone in zone_tags(master):
            for room in zone_rooms(zone):
                if room.has_tag("outdoor"):
                    room.msg_contents(line)


def weather_at(room: GameObject | None) -> str | None:
    """The weather in ``room``'s zone, or None."""
    for master in zone_masters(room):
        state = master.db.get("weather_now")
        if state:
            return str(state)
    return None


__all__ = ["roll_weather", "roll_zones", "weather_at"]
