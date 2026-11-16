# Time and Weather

The `clock` feature gives the world a time of day, a calendar, events at
the turn of each hour, darkness at night, and weather per zone. Builders
react to all of it in softcode; nothing in the rules changes by itself.

## Game time

Game time runs at `GAME_TIME_RATIO` game seconds per real second (default
30, so a game day lasts 48 real minutes). It is derived, not counted: the
world stores one epoch, on an object tagged `world_clock`, and the time is
always "how long since then, sped up". So it keeps running across
restarts, and while the server is down. A new world starts at 08:00 on the
first day of the first month of year 1.

The calendar is settings:

| Key | Default |
|---|---|
| `GAME_TIME_RATIO` | 30 |
| `HOURS_PER_DAY` | 24 |
| `DAYS_PER_MONTH` | 30 |
| `MONTH_NAMES` | Deepwinter, Thaw, Seedtime, Rains, Blossom, Highsun, Midsummer, Harvest, Leaffall, Frost, Darkening, Longnight |
| `DAY_NAMES` | Moonday, Tiwday, Wodensday, Thunderday, Freyday, Starday, Sunday |

Dawn is the hour a quarter of the way into the day (06:00 of 24) and dusk
the hour 19/24 of the way (19:00); between them is day, the rest night.

`time` shows the game time first and the server's clock after. In
softcode, `game_time()` returns `hour`, `minute`, `day`, `month`, `year`,
`month_name`, `day_name` and `time_of_day`, and `time_of_day()` returns
`dawn`, `day`, `dusk` or `night`:

```text
@desc inn sign = The Gilded Goose. [[ result = 'Lamplight spills from the windows.' if time_of_day() == 'night' else 'The shutters stand open.' ]]
```

## The hour

At the start of each game hour, every zone master and every room holding
a player hears `ON_HOUR` (`adata('hour')`), and at the four turns of the
day `ON_DAWN`, `ON_DAY` (the hour after dawn), `ON_DUSK` and `ON_NIGHT`
(the hour after dusk). One master hears each event once, however many of
its rooms hold players. So a shop can open and a lamplighter walk his
round without a ticker on every object:

```text
@set Market Zone/on_dawn = remit(get('#market_square'), 'Stallholders throw back their awnings.')
@set Market Zone/on_night = set_attr(get('#bakery'), 'open', 0)
```

Hours missed while the server was down, or between two sweeps, fire in
order when it next looks (every `REAP_INTERVAL` seconds), and never
twice: the last hour fired is kept on the clock object.

## Night

A room tagged `outdoor` is dark at night, exactly like a room tagged
`dark`: a light source in the room, or wielded by someone in it, lights
it, and `nightvision` sees anyway. A room also tagged `lamplit` stays lit
(city streets). This needs the `sight` feature; without it, night changes
nothing.

```text
@tag here = outdoor
@tag The High Street = lamplit
```

The ROM importer tags every non-interior room `outdoor` and city streets
`lamplit`, as ROM does.

## Weather

A zone master with a `weather` attribute gets a state rolled each game
hour, kept in its `weather_now`. The attribute is a list of
`[state, weight]` pairs, or a softcode expression (the `rule` profile,
with `hour` and `current` bound, and the read-only functions such as
`time_of_day()`) returning the state:

```text
@set Vale Zone/weather = [["clear", 5], ["cloudy", 3], ["rain", 2]]
@set Vale Zone/weather_messages = {"rain": "Rain begins to patter on the leaves."}
@set Moor Zone/weather = 'fog' if time_of_day() in ('dawn', 'night') else 'drizzle'
```

When the state changes, the zone's `outdoor` rooms are told: the master's
`weather_messages` line for it, else "The weather turns <state>.". Indoor
rooms hear nothing. `weather` shows it outdoors ("You can't see the sky
from in here." indoors), and softcode reads it with `weather(here)`.
Weather has no effect on the rules: a fishing pond that bites more in the
rain asks `weather(here)` itself.

See also [Time, Ticks & Beats](../design/time-and-beats.md) for the
engine's other two clocks.
