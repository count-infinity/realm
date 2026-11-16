"""The ``clock`` feature's commands and softcode."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

from realm.core.world import get_world
from realm.std.clock.weather import weather_at

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject


async def cmd_time(ctx: CommandContext) -> None:
    """
    Show the time in the game, then the server's own clock.

    Usage: time
    """
    clock = get_world().services["clock"]
    server = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    await ctx.session.send(f"{clock.describe()}\nServer time: {server}")


async def cmd_weather(ctx: CommandContext) -> None:
    """
    Look at the sky.

    Usage: weather
    """
    room = ctx.player.location
    if room is None or not room.has_tag("outdoor"):
        await ctx.session.send("You can't see the sky from in here.")
        return
    state = weather_at(room)
    clock = get_world().services["clock"]
    sky = f"The weather is {state}" if state else "The sky is unremarkable"
    await ctx.session.send(f"{sky}, and it is {clock.time_of_day()}.")


def game_time(frame) -> dict[str, Any]:
    """
    The game's time and date: ``{'hour', 'minute', 'day', 'month', 'year',
    'month_name', 'day_name', 'time_of_day'}``.

    Example: game_time()['hour']
    """
    return get_world().services["clock"].game_time()


def time_of_day(frame) -> str:
    """
    ``dawn``, ``day``, ``dusk`` or ``night``.

    Example: if time_of_day() == 'night': pemit(enactor, 'The owls are out.')
    """
    return get_world().services["clock"].time_of_day()


def weather(frame, room: GameObject | str | None = None) -> str | None:
    """
    The weather in a room's zone (rolled hourly by its zone master), or
    None.

    Example: weather(here)
    """
    target = frame.resolve(room) if room is not None else frame.location
    return weather_at(target)


__all__ = ["cmd_time", "cmd_weather", "game_time", "time_of_day", "weather"]
