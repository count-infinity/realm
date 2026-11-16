"""
The ``clock`` feature.

Game time, a calendar, the hour's events, night darkness for outdoor rooms
and weather per zone (MUD_PLAN step 8; docs/guides/time-and-weather.md).
"""

from __future__ import annotations

from realm.features import Feature
from realm.std.clock import commands
from realm.std.clock.clock import WorldClock, clock_sweep, night_darkness

feature = Feature(
    'clock',
    doc='Game time and calendar, hourly events, night, weather per zone.',
)

feature.setting("GAME_TIME_RATIO", 30,
                "Game seconds per real second (30: a game day is 48 real minutes).")
feature.setting("HOURS_PER_DAY", 24, "Hours in a game day.")
feature.setting("DAYS_PER_MONTH", 30, "Days in a game month.")
feature.setting("MONTH_NAMES",
                ["Deepwinter", "Thaw", "Seedtime", "Rains", "Blossom", "Highsun",
                 "Midsummer", "Harvest", "Leaffall", "Frost", "Darkening", "Longnight"],
                "The months of the game year, in order.")
feature.setting("DAY_NAMES",
                ["Moonday", "Tiwday", "Wodensday", "Thunderday", "Freyday", "Starday",
                 "Sunday"],
                "The days of the game week, in order.")

feature.command('time', commands.cmd_time, category='utility', replace=True,
                help_text='Show the game time')
feature.command('weather', commands.cmd_weather, category='utility',
                help_text='Look at the sky')
feature.reaper(clock_sweep)

for _type, _hook, _doc in (
        ("time:on_hour", "HOUR", "a game hour begins (zone masters, rooms holding players)"),
        ("time:on_dawn", "DAWN", "dawn breaks"), ("time:on_day", "DAY", "full day begins"),
        ("time:on_dusk", "DUSK", "dusk falls"), ("time:on_night", "NIGHT", "night falls")):
    feature.event(_type, hook=_hook, doc=_doc, payload={"hour": "the hour of the day"})

feature.softfn(commands.game_time, group='Time & scheduling', readonly=True)
feature.softfn(commands.time_of_day, group='Time & scheduling', readonly=True)
feature.softfn(commands.weather, group='Time & scheduling', readonly=True)


@feature.on_boot
async def _start_the_clock(world) -> None:
    """A new world's clock starts at boot (08:00 on the first day); a
    saved one carries on from its epoch."""
    clock = world.services["clock"]
    await world.store.save(clock.clock_object())


@feature.on_install
def _offer_clock(world) -> None:
    """``world.services["clock"]``; and with ``sight``, outdoor rooms go
    dark at night (a darkness test on the sight service)."""
    world.services["clock"] = WorldClock(world)
    sight = world.services.get("sight")
    if sight is not None:
        world.add_closer(sight.add_darkness_test(night_darkness))
