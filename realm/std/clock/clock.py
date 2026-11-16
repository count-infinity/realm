"""
Game time (MUD_PLAN 8).

Game time is derived, not counted: game seconds = (real now - the epoch)
x ``GAME_TIME_RATIO``, the epoch stored on the one ``world_clock`` object.
So the clock keeps running across restarts and while the server is down,
and nothing ticks. A new world starts at 08:00 on the first day of the
first month of year 1.

The calendar is settings: ``HOURS_PER_DAY``, ``DAYS_PER_MONTH``,
``MONTH_NAMES``, ``DAY_NAMES``. Dawn is the hour a quarter of the way
into the day (06:00 of 24), dusk the hour 19/24 of the way (19:00);
between them is day, the rest night.

Every reaper sweep the service looks for game hours that have begun since
the last one (kept on the clock object, so a reboot does not repeat them)
and fires, for each: ``time:on_hour`` (hook ``HOUR``, payload ``hour``)
and, at the four boundaries, ``time:on_dawn`` / ``on_day`` / ``on_dusk`` /
``on_night``, on each zone master and each room holding a player.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from realm.core.world import find_world

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.world import World

CLOCK_TAG = "world_clock"
START_HOUR = 8


def _hour_action(action_type: str, hour: int):
    """The action announcing an hour, written out per type so the payload
    docs check can read each type's keys from the source."""
    from realm.core.propagation import Action
    made = {
        "time:on_hour": lambda: Action(actor=None, target=None, chain=[],
                                       action_type="time:on_hour", extra={"hour": hour}),
        "time:on_dawn": lambda: Action(actor=None, target=None, chain=[],
                                       action_type="time:on_dawn", extra={"hour": hour}),
        "time:on_day": lambda: Action(actor=None, target=None, chain=[],
                                      action_type="time:on_day", extra={"hour": hour}),
        "time:on_dusk": lambda: Action(actor=None, target=None, chain=[],
                                       action_type="time:on_dusk", extra={"hour": hour}),
        "time:on_night": lambda: Action(actor=None, target=None, chain=[],
                                        action_type="time:on_night", extra={"hour": hour}),
    }
    return made[action_type]()


def now() -> float:
    """The wall clock game time derives from (tests replace it)."""
    return time.time()


class WorldClock:
    """The ``clock`` service: what time it is in the game."""

    def __init__(self, world: World):
        self.world = world

    # --- the calendar -----------------------------------------------------------

    def calendar(self) -> dict[str, Any]:
        setting = self.world.setting
        return {"hours": int(setting("HOURS_PER_DAY")),
                "days": int(setting("DAYS_PER_MONTH")),
                "months": list(setting("MONTH_NAMES")),
                "weekdays": list(setting("DAY_NAMES")),
                "ratio": float(setting("GAME_TIME_RATIO"))}

    def clock_object(self) -> GameObject:
        """The ``world_clock`` object, made (epoch: now, at 08:00) on first use."""
        store = self.world.store
        found = store.find_cached(tag=CLOCK_TAG)
        if found:
            return found[0]
        from realm.core.objects import GameObject
        obj = GameObject(name="world clock", tags=[CLOCK_TAG], location=None)
        store.register(obj)
        # Set after registering, so the store saves it like any change.
        obj.db.epoch = now() - START_HOUR * 3600 / self.calendar()["ratio"]
        return obj

    def game_seconds(self) -> float:
        cal = self.calendar()
        return max(0.0, (now() - float(self.clock_object().db.epoch)) * cal["ratio"])

    def hour_count(self) -> int:
        """Whole game hours since the epoch."""
        return int(self.game_seconds() // 3600)

    def dawn_hour(self) -> int:
        return self.calendar()["hours"] // 4

    def dusk_hour(self) -> int:
        return self.calendar()["hours"] * 19 // 24

    def phase(self, hour: int) -> str:
        """dawn, day, dusk or night for an hour of the day."""
        dawn, dusk = self.dawn_hour(), self.dusk_hour()
        if hour == dawn:
            return "dawn"
        if dawn < hour < dusk:
            return "day"
        if hour == dusk:
            return "dusk"
        return "night"

    def game_time(self) -> dict[str, Any]:
        """``{hour, minute, day, month, year, month_name, day_name,
        time_of_day}`` (day and month from 1)."""
        cal = self.calendar()
        seconds = self.game_seconds()
        hours_total = int(seconds // 3600)
        hour = hours_total % cal["hours"]
        days_total = hours_total // cal["hours"]
        months = cal["months"] or ["Month"]
        weekdays = cal["weekdays"] or ["Day"]
        month_index = (days_total // cal["days"]) % len(months)
        return {
            "hour": hour, "minute": int(seconds % 3600 // 60),
            "day": days_total % cal["days"] + 1, "month": month_index + 1,
            "year": days_total // (cal["days"] * len(months)) + 1,
            "month_name": months[month_index], "day_name": weekdays[days_total % len(weekdays)],
            "time_of_day": self.phase(hour),
        }

    def time_of_day(self) -> str:
        return self.game_time()["time_of_day"]

    def describe(self) -> str:
        """"8:00 in the day, Moonday the 1st of Deepwinter, year 1"."""
        t = self.game_time()
        return (f"It is {t['hour']}:{t['minute']:02d}, {t['time_of_day']}, on "
                f"{t['day_name']}, day {t['day']} of {t['month_name']}, year {t['year']}.")

    def is_night(self) -> bool:
        return self.time_of_day() == "night"

    # --- the hour ---------------------------------------------------------------

    async def advance(self) -> None:
        """Fire the events of every game hour begun since the last sweep."""
        obj = self.clock_object()
        current = self.hour_count()
        last = obj.db.get("last_hour")
        if last is None:
            obj.db.last_hour = current               # start counting from here
            return
        hours = self.calendar()["hours"]
        for count in range(int(last) + 1, current + 1):
            obj.db.last_hour = count
            await self.fire_hour(count % hours)

    async def fire_hour(self, hour: int) -> None:
        from realm.std.clock.weather import roll_zones
        events = [("time:on_hour", "HOUR")]
        boundary = {self.dawn_hour(): ("time:on_dawn", "DAWN"),
                    self.dawn_hour() + 1: ("time:on_day", "DAY"),
                    self.dusk_hour(): ("time:on_dusk", "DUSK"),
                    self.dusk_hour() + 1: ("time:on_night", "NIGHT")}.get(hour)
        if boundary is not None:
            events.append(boundary)
        await roll_zones(self, hour)
        targets = self.hour_targets()
        for action_type, hook in events:
            await self._fire(action_type, hook, hour, targets)

    def hour_targets(self) -> list[GameObject]:
        """Each zone master and each room holding a player, once."""
        from realm.core.query import find_objects
        from realm.core.zones import MASTER_TAG
        out: dict[str, GameObject] = {m.id: m for m in find_objects(tag=MASTER_TAG)}
        for player in self.world.store.find_cached(tag="player"):
            room = player.location
            if room is not None and room.is_room:
                out.setdefault(room.id, room)
        return list(out.values())

    async def _fire(self, action_type: str, hook: str, hour: int,
                    targets: list[GameObject]) -> None:
        """One action for the world's observers, and the hook run on each
        target directly (so a zone master hears it once, not once per room)."""
        from realm.core.propagation import propagate
        action = _hour_action(action_type, hour)
        await propagate(action, deliver=False)
        engine = self.world.scripts
        if engine is None:
            return
        for obj in targets:
            for trigger in engine.trigger_manager.get_event_triggers(obj, hook):
                await engine.run_behavior_script(obj, trigger.action, action=action)


def _service() -> WorldClock | None:
    world = find_world()
    return world.services.get("clock") if world is not None else None


async def clock_sweep(store: Any) -> None:
    """The ``clock`` reaper."""
    service = _service()
    if service is not None:
        await service.advance()


def night_darkness(room: GameObject) -> bool:
    """A darkness test for ``sight``: an ``outdoor`` room, not ``lamplit``,
    is dark at night."""
    service = _service()
    return (service is not None and room.has_tag("outdoor") and not room.has_tag("lamplit")
            and service.is_night())


__all__ = ["CLOCK_TAG", "START_HOUR", "now", "WorldClock", "clock_sweep", "night_darkness"]
