"""
Utility commands for REALM.

General-purpose commands like quit, help, time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.commands import CommandContext
from realm.commands.base import save_object
from realm.core.action_types import ActionType
from realm.core.markup import escape, wrap
from realm.core.movement import move_to
from realm.core.options import get_option, set_option
from realm.core.teardown import start_room_floor
from realm.core.world import find_world

if TYPE_CHECKING:
    from realm.core.objects import GameObject


async def cmd_quit(ctx: CommandContext) -> None:
    """
    Disconnect from the game.

    Usage: quit
           QUIT
    """
    await ctx.session.send("Goodbye! Come back soon.")

    if ctx.session_manager:
        # destroy_session flushes the farewell, then hangs up the connection.
        await ctx.session_manager.destroy_session(ctx.session)


async def cmd_logout(ctx: CommandContext) -> None:
    """
    Leave your character and return to the connection screen.

    Usage: logout

    Unlike `quit`, your connection stays open: the character leaves play
    exactly as if you had disconnected, and you land back at the welcome
    screen where you can `connect` again — as the same character or another.
    """
    player = ctx.player
    if player is None:
        await ctx.session.send("You aren't logged in.")
        return

    # A half-finished prompt/wizard must not leak into the login screen.
    ctx.session.cancel_prompt()

    # Tell the room, as a real disconnect does, so ON_DISCONNECT hooks fire
    # and onlookers see the character go.
    location = player.location
    if location is not None:
        from realm.core.propagation import (
            ROOM_TARGET_CHAIN,
            Action,
            propagate,
        )
        action = Action(
            actor=player,
            target=location,
            action_type=ActionType.DISCONNECT,
            chain=ROOM_TARGET_CHAIN,
        )
        action.add_message("room", "{actor} logs out.")
        await propagate(action)

    if ctx.persistence:
        await ctx.persistence.save(player)

    await ctx.session.send("You leave your character behind.\n")

    # Drop the player↔session link but KEEP the connection: with no player,
    # the dispatcher routes input to the login handler again. The account
    # goes too: logout returns to the welcome screen, not the character menu.
    ctx.session.account = None
    if ctx.session_manager:
        ctx.session_manager.unlink_player_from_session(ctx.session)
    else:
        ctx.session.unlink_player()

    if ctx.dispatcher is not None and ctx.dispatcher.welcome_screen:
        await ctx.session.send(ctx.dispatcher.welcome_screen())


async def cmd_help(ctx: CommandContext) -> None:
    """
    Show help on commands, and the game's own help topics.

    Usage: help [command or topic]

    Example:
        help combat
        help newbie
    """
    if not ctx.dispatcher:
        await ctx.session.send("Help unavailable.")
        return

    if not ctx.args:
        # Show list of commands
        await _show_command_list(ctx)
    else:
        # Show help for specific command
        await _show_command_help(ctx, ctx.args.strip())


async def _show_command_list(ctx: CommandContext) -> None:
    """List available commands, grouped by their registered category."""
    dispatcher = ctx.dispatcher
    visible = set(dispatcher.list_commands(ctx.player))

    categories: dict[str, list[str]] = {}
    for name, cmd in dispatcher._commands.items():
        if name in visible:
            categories.setdefault(cmd.category, []).append(name)

    lines = ["", "=" * 40, "  Available Commands", "=" * 40]
    for category in sorted(categories):
        lines.extend(["", f"{category.title()}:",
                      f"  {', '.join(sorted(categories[category]))}"])
    lines.extend(["", "help <command> for details; help <word> searches help text."])
    ctx.session.send_paged("\n".join(lines))


def help_topic(topic: str) -> GameObject | None:
    """The game's ``help_def`` (a help topic written as data, ROM's help
    file entry) whose name, or one of whose ``keywords``, is ``topic``."""
    from realm.core.defs import def_kinds, def_objects
    if "help" not in def_kinds():
        return None
    want = topic.strip().lower()
    for name, entry in def_objects("help").items():
        words = entry.db.get("keywords") or []
        if want == name or want in [str(word).lower() for word in words]:
            return entry
    return None


async def _show_command_help(ctx: CommandContext, topic: str) -> None:
    """A help topic of that name, else detail one command, or search help
    text when nothing matches."""
    entry = help_topic(topic)
    if entry is not None:
        ctx.session.send_paged(str(entry.db.get("text") or ""))
        return
    dispatcher = ctx.dispatcher
    cmd = dispatcher.get_command(topic.lower())
    if cmd is not None:
        # Help is plain text: a pipe in it (`on|off|history`) is a pipe,
        # not color markup.
        lines = [f"\n{cmd.name}"]
        if cmd.aliases:
            lines.append(f"  aliases: {', '.join(cmd.aliases)}")
        if cmd.usage:
            lines.append(f"  usage: {escape(cmd.usage)}")
        if cmd.help_text:
            lines.append(f"  {escape(cmd.help_text)}")
        doc = (cmd.handler.__doc__ or "").strip()
        if doc:
            lines.append("")
            lines.extend("  " + escape(ln.strip()) for ln in doc.split("\n"))
        ctx.session.send_paged("\n".join(lines))
        return

    # Search: substring over names, aliases, and help text.
    want = topic.lower()
    visible = set(dispatcher.list_commands(ctx.player))
    hits = sorted({
        name for name, c in dispatcher._commands.items()
        if name in visible and (
            want in name
            or any(want in a for a in c.aliases)
            or want in c.help_text.lower())
    })
    if hits:
        await ctx.session.send(
            f"No command '{topic}'. Related: {', '.join(hits)}")
    else:
        await ctx.session.send(f"No help found for '{topic}'.")



async def cmd_commands(ctx: CommandContext) -> None:
    """
    List all available commands (alias for help).

    Usage: commands
    """
    await cmd_help(ctx)


async def cmd_time(ctx: CommandContext) -> None:
    """
    Show the current server time.

    Usage: time
    """
    import datetime
    now = datetime.datetime.now()
    await ctx.session.send(f"Server time: {now.strftime('%Y-%m-%d %H:%M:%S')}")


def _format_duration(seconds: int) -> str:
    """Render a second count as a compact "1d 2h 3m 4s" string."""
    days, rem = divmod(max(0, seconds), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


async def cmd_uptime(ctx: CommandContext) -> None:
    """
    Show how long the server has been running.

    Usage: uptime
    """
    started = ctx.dispatcher.server_started_at if ctx.dispatcher else None
    if started is None:
        await ctx.session.send("Server uptime information unavailable.")
        return
    import time
    await ctx.session.send(
        f"Server uptime: {_format_duration(int(time.monotonic() - started))}.")


async def cmd_think(ctx: CommandContext) -> None:
    """
    Think to yourself (only you see it).

    Usage: think <thought>

    Example:
        think Note to self: the ferryman takes bribes.
    """
    if not ctx.args:
        await ctx.session.send("Think what?")
        return

    await ctx.session.send(f"You think: {ctx.args}")


async def cmd_recall(ctx: CommandContext) -> None:
    """
    Pray your way back to safety: your home, else where new characters
    start. Some places hold you (a room tagged ``no_recall``); in a fight
    it takes a check, and the game system may charge for it (under Merc,
    half your movement).

    Usage: recall
    """
    player = ctx.player
    world = find_world()
    if player.location is not None and player.location.has_tag('no_recall'):
        await ctx.session.send("You cannot recall from here.")
        return
    home_id = player.db.get('home')
    if home_id:
        dest = ctx.persistence.get_cached(str(home_id)) if ctx.persistence else None
        if dest is None:
            await ctx.session.send("Your home no longer exists.")
            return
    else:
        dest = (world.startup_room if world is not None else None) or start_room_floor()
        if dest is None:
            await ctx.session.send("You don't have a home to recall to.")
            return
    await recall_to(player, dest, ctx.session)


async def recall_to(player: GameObject, dest: GameObject, session) -> bool:
    """Recall ``player`` to ``dest`` under ``recall``'s rules: not from a
    ``no_recall`` room, a check in a fight (``GameSystem.recall_refusal``)
    and its cost (``after_recall``), through ``dest``'s locks. Tells the
    player why not; True when they arrived. The move carries the ``recall``
    service's ``tags`` (``companions`` adds ``accompanied``, so a pet beside
    the player and the mount under it come too). The ``recall`` service
    offers it (``clan recall`` goes to the clan's home with it)."""
    world = find_world()
    here = player.location
    if here is not None and here.has_tag('no_recall'):
        await session.send("You cannot recall from here.")
        return False
    if here is dest:
        await session.send("You are already home.")
        return False

    from_combat = player.has_tag('in_combat')
    rules = world.rules if world is not None else None
    refusal = (rules.recall_refusal(player) if rules is not None
               else "You can't recall in the middle of a fight." if from_combat else None)
    if refusal:
        await session.send(refusal)
        return False

    # Move through the one relocation core (not forced — recall is voluntary,
    # so home's ENTER/TELEPORT locks and movement wards still apply), with
    # whatever tags other features asked a recall to carry (the player's
    # company comes too when the world has companions: ROM's do_recall takes
    # the pet).
    service = world.services.get("recall") if world is not None else None
    tags = list(service.tags) if service is not None else []
    if not await move_to(player, dest, mover=player, extra_tags=tags):
        await session.send("Something prevents you from recalling home.")
        return False
    # Out of any fight it was in: ``combat`` takes whoever is placed out of
    # a fight's room out of it.
    if rules is not None:
        rules.after_recall(player, from_combat=from_combat)
    if here is not None:
        here.msg_contents(f"{player.name} disappears.", exclude=[player])
    dest.msg_contents(f"{player.name} appears in the room.", exclude=[player])

    store = world.store if world is not None else None
    if store is not None:
        await store.save(player)
    await session.send(f"You recall to {dest.name}.")
    look = world.services.get("look") if world is not None else None
    if look is not None:
        await session.send(look.render_room(dest, player, arrival=True))
    return True


async def cmd_color(ctx: CommandContext) -> None:
    """
    Toggle color output for your client.

    Usage: color on | color off

    Example:
        color off
    """
    want = (ctx.args or "").strip().lower()
    if want not in ("on", "off"):
        state = "off" if get_option(ctx.player, "color") is False else "on"
        await ctx.session.send(f"Color is {state}. Usage: color on|off")
        return
    await save_object(ctx, set_option(ctx.player, "color", want == "on"))
    await ctx.session.send(
        f"Color {want}." + (" " + wrap('g', 'Like this.')
                            if want == "on" else ""))


