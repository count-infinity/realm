"""
MUD_PLAN step 8: the world clock (the ``clock`` feature).

Game time is derived from real time since an epoch on a ``world_clock``
object, so it keeps running across restarts. The hour fires ``time:on_hour``
(and dawn, day, dusk, night) on zone masters and rooms holding players;
``outdoor`` rooms are dark at night; zones with a ``weather`` table roll
their weather each game hour.
"""

from __future__ import annotations

import pytest

from realm.config.loader import Settings
from realm.testing import Simulator

HOUR = 3600 / 30          # real seconds in a game hour at the default ratio


@pytest.fixture
def clock(monkeypatch):
    now = [10_000_000.0]
    monkeypatch.setattr("realm.std.clock.clock.now", lambda: now[0])
    return now


@pytest.fixture
def sim(clock):
    s = Simulator()
    try:
        yield s
    finally:
        s.close()


def _service(sim):
    return sim.world.services["clock"]


async def _sweep(sim):
    from realm.std.clock.clock import clock_sweep
    await clock_sweep(sim.store)


def _text(sim, who):
    return "\n".join(sim.seen(who))


class TestTheCalendar:

    def test_a_new_world_starts_at_eight_on_the_first_day(self, sim):
        t = _service(sim).game_time()
        assert (t["hour"], t["day"], t["month"], t["year"]) == (8, 1, 1, 1)
        assert t["time_of_day"] == "day"

    def test_time_runs_at_the_ratio_and_rolls_the_calendar(self, sim, clock):
        service = _service(sim)
        service.game_time()                        # the clock starts on first use (or boot)
        clock[0] += 4 * HOUR
        assert service.game_time()["hour"] == 12
        clock[0] += 24 * HOUR
        t = service.game_time()
        assert (t["hour"], t["day"]) == (12, 2)
        assert t["day_name"] == sim.world.setting("DAY_NAMES")[1]
        clock[0] += 30 * 24 * HOUR
        t = service.game_time()
        assert (t["day"], t["month"]) == (2, 2)
        assert t["month_name"] == sim.world.setting("MONTH_NAMES")[1]

    def test_the_calendar_comes_from_settings(self, clock):
        sim = Simulator(settings=Settings(raw={
            "HOURS_PER_DAY": 10, "DAYS_PER_MONTH": 3, "MONTH_NAMES": ["Ice", "Mud"],
            "DAY_NAMES": ["Odd", "Even"], "GAME_TIME_RATIO": 60}))
        try:
            service = _service(sim)
            assert service.game_time()["hour"] == 8
            clock[0] += 2 * 60                     # 2 game hours at 60x
            t = service.game_time()
            assert (t["hour"], t["day"], t["day_name"]) == (0, 2, "Even")
            clock[0] += 10 * 60 * 3                # three more days: next month
            t = service.game_time()
            assert (t["month_name"], t["day"]) == ("Mud", 2)
        finally:
            sim.close()

    def test_time_of_day(self, sim, clock):
        service = _service(sim)
        seen = []
        for _ in range(24):
            seen.append((service.game_time()["hour"], service.time_of_day()))
            clock[0] += HOUR
        by_hour = dict(seen)
        assert by_hour[6] == "dawn" and by_hour[12] == "day"
        assert by_hour[19] == "dusk" and by_hour[23] == "night" and by_hour[2] == "night"

    async def test_softcode_reads_it(self, sim):
        obj = sim.obj("sundial", location=sim.room("Garden"))
        result, err = await sim.eval(obj, "result = (game_time()['hour'], time_of_day())")
        assert err is None and result == (8, "day")

    async def test_the_time_command(self, sim):
        pat = sim.player("Pat", location=sim.room("Garden"))
        await sim.do(pat, "time")
        out = _text(sim, pat)
        lines = out.splitlines()
        assert "8:00" in lines[0] and "day" in lines[0]
        assert "Server time" in out


async def test_a_restart_keeps_the_time(clock):
    """The epoch is saved on the clock object; a new world loading it is
    later in the day by however long it was down."""
    from realm.persistence.worldio import export_objects, import_objects
    first = Simulator()
    try:
        _service(first).game_time()
        saved = export_objects(first.store.find_cached(tag="world_clock"))
    finally:
        first.close()
    clock[0] += 3 * HOUR
    second = Simulator()
    try:
        await import_objects(saved, second.store, preserve_ids=True)
        assert _service(second).game_time()["hour"] == 11
    finally:
        second.close()


class TestTheHour:

    async def test_the_hour_fires_once_on_masters_and_player_rooms(self, sim, clock):
        field = sim.room("Field")
        empty = sim.room("Empty Barn")
        field.add_tag("zone:vale")
        sim.player("Pat", location=field)
        master = sim.obj("vale master", location=sim.room("Vale Office"))
        master.add_tag("zone_master")
        master.add_tag("zone:vale")
        for obj in (field, empty, master):
            obj.db.on_hour = ("set_attr(me, 'hours', "
                              "(get_attr(me, 'hours') or []) + [adata('hour')])")
        await _sweep(sim)                          # starts tracking: nothing fires
        clock[0] += HOUR / 2
        await _sweep(sim)
        assert field.db.get("hours") is None
        clock[0] += HOUR / 2
        await _sweep(sim)
        await _sweep(sim)                          # the same hour: not again
        assert field.db.hours == [9] and master.db.hours == [9]
        assert empty.db.get("hours") is None       # no player there
        clock[0] += 3 * HOUR                       # missed hours fire in order
        await _sweep(sim)
        assert field.db.hours == [9, 10, 11, 12]

    async def test_dawn_and_dusk_fire_at_their_boundaries(self, sim, clock):
        room = sim.room("Hill")
        sim.player("Pat", location=room)
        room.db.on_dusk = "set_attr(me, 'dusk', 1)"
        room.db.on_night = "set_attr(me, 'night', 1)"
        room.db.on_dawn = "set_attr(me, 'dawn', 1)"
        await _sweep(sim)
        clock[0] += 11 * HOUR                      # 8 -> 19: dusk
        await _sweep(sim)
        assert room.db.dusk == 1 and room.db.get("night") is None
        clock[0] += HOUR
        await _sweep(sim)
        assert room.db.night == 1 and room.db.get("dawn") is None
        clock[0] += 10 * HOUR                      # -> 6: dawn
        await _sweep(sim)
        assert room.db.dawn == 1


class TestNight:

    async def test_an_outdoor_room_is_dark_at_night_and_a_torch_lights_it(self, sim, clock):
        from realm.std.sight.sight import room_is_lit
        field = sim.room("Field")
        field.add_tag("outdoor")
        street = sim.room("Street")
        street.add_tag("outdoor")
        street.add_tag("lamplit")
        hall = sim.room("Hall")
        assert room_is_lit(field)
        clock[0] += 14 * HOUR                      # 22:00
        assert not room_is_lit(field)
        assert room_is_lit(street) and room_is_lit(hall)
        pat = sim.player("Pat", location=field)
        sim.obj("a torch", location=pat, tags=["thing", "light", "wielded"])
        assert room_is_lit(field)

    async def test_night_without_sight_changes_nothing(self, clock):
        sim = Simulator(features=["basics", "look", "clock"])
        try:
            field = sim.room("Field")
            field.add_tag("outdoor")
            pat = sim.player("Pat", location=field)
            clock[0] += 14 * HOUR
            await sim.do(pat, "look")
            assert any("Field" in line for line in sim.seen(pat))
        finally:
            sim.close()


class TestWeather:

    def _vale(self, sim):
        field = sim.room("Field")
        field.add_tag("outdoor")
        field.add_tag("zone:vale")
        hall = sim.room("Hall")
        hall.add_tag("zone:vale")
        master = sim.obj("vale master", location=sim.room("Vale Office"))
        master.add_tag("zone_master")
        master.add_tag("zone:vale")
        out = sim.player("Out", location=field)
        inside = sim.player("In", location=hall)
        return field, hall, master, out, inside

    async def test_a_change_is_announced_outdoors_and_not_indoors(self, sim, clock, monkeypatch):
        field, hall, master, out, inside = self._vale(sim)
        master.db.weather = [["clear", 1], ["rain", 1]]
        master.db.weather_messages = {"rain": "Rain begins to fall."}
        rolls = iter(["clear", "rain", "rain"])
        monkeypatch.setattr("realm.std.clock.weather.roll_weather",
                            lambda table: next(rolls))
        await _sweep(sim)
        for _ in range(3):
            clock[0] += HOUR
            await _sweep(sim)
        assert master.db.weather_now == "rain"
        assert _text(sim, out).count("Rain begins to fall.") == 1
        assert "Rain" not in _text(sim, inside)

    async def test_weather_readable_from_softcode_and_the_command(self, sim, clock):
        field, hall, master, out, inside = self._vale(sim)
        master.db.weather = [["fog", 1]]
        await _sweep(sim)
        clock[0] += HOUR
        await _sweep(sim)
        vane = sim.obj("weather vane", location=field)
        result, _e = await sim.eval(vane, "result = weather(here)")
        assert result == "fog"
        sim.seen(out)
        await sim.do(out, "weather")
        assert "fog" in _text(sim, out)
        await sim.do(inside, "weather")
        assert "can't see the sky" in _text(sim, inside)

    async def test_a_softcode_weather_rule(self, sim, clock):
        field, hall, master, out, inside = self._vale(sim)
        master.db.weather = "'storm' if hour >= 12 else 'calm'"
        await _sweep(sim)
        clock[0] += HOUR
        await _sweep(sim)
        assert master.db.weather_now == "calm"
        clock[0] += 4 * HOUR
        await _sweep(sim)
        assert master.db.weather_now == "storm"
