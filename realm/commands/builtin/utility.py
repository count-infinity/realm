"""
Utility commands for REALM.

General-purpose commands like who, quit, help.
"""

from __future__ import annotations

from realm.commands import CommandContext, CommandDispatcher


async def cmd_who(ctx: CommandContext) -> None:
    """
    Show who is online.

    Usage: who
    """
    if not ctx.session_manager:
        await ctx.session.send("Who list unavailable.")
        return

    playing = ctx.session_manager.playing_sessions()

    await ctx.session.send(f"\n{'=' * 40}")
    await ctx.session.send(f"  {len(playing)} player(s) online")
    await ctx.session.send(f"{'=' * 40}")

    if playing:
        await ctx.session.send("")
        for session in playing:
            if session.player:
                name = session.player.name
                idle = int(session.idle_time)

                # Format idle time
                if idle < 60:
                    idle_str = f"{idle}s"
                elif idle < 3600:
                    idle_str = f"{idle // 60}m"
                else:
                    idle_str = f"{idle // 3600}h"

                # Get location if visible
                loc = ""
                if session.player.location:
                    loc = f" in {session.player.location.name}"

                await ctx.session.send(f"  {name} (idle {idle_str}){loc}")

    await ctx.session.send("")


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


async def cmd_help(ctx: CommandContext) -> None:
    """
    Show help on commands.

    Usage: help [command]

    Example:
        help combat
        help fasttalk
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

    await ctx.session.send("\n" + "=" * 40)
    await ctx.session.send("  Available Commands")
    await ctx.session.send("=" * 40)
    for category in sorted(categories):
        await ctx.session.send(f"\n{category.title()}:")
        await ctx.session.send(f"  {', '.join(sorted(categories[category]))}")
    await ctx.session.send(
        "\nhelp <command> for details; help <word> searches help text.")


async def _show_command_help(ctx: CommandContext, topic: str) -> None:
    """Detail one command, or search help text when nothing matches."""
    dispatcher = ctx.dispatcher
    cmd = dispatcher.get_command(topic.lower())
    if cmd is not None:
        lines = [f"\n{cmd.name}"]
        if cmd.aliases:
            lines.append(f"  aliases: {', '.join(cmd.aliases)}")
        if cmd.usage:
            lines.append(f"  usage: {cmd.usage}")
        if cmd.help_text:
            lines.append(f"  {cmd.help_text}")
        doc = (cmd.handler.__doc__ or "").strip()
        if doc:
            lines.append("")
            lines.extend("  " + ln.strip() for ln in doc.split("\n"))
        await ctx.session.send("\n".join(lines))
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
    Show the current game time.

    Usage: time
    """
    # TODO: Implement game time system
    import datetime
    now = datetime.datetime.now()
    await ctx.session.send(f"Server time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    # await ctx.session.send(f"Game time: Day 1, Hour 12")


async def cmd_uptime(ctx: CommandContext) -> None:
    """
    Show server uptime.

    Usage: uptime
    """
    # TODO: Track server start time
    await ctx.session.send("Server uptime information unavailable.")


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
    Return to your home location.

    Usage: recall
    """
    # Get home location
    home = ctx.player.db.get('home')
    if not home:
        await ctx.session.send("You don't have a home set.")
        return

    # TODO: Implement actual recall with movement events
    await ctx.session.send("Recall not yet implemented.")


async def cmd_color(ctx: CommandContext) -> None:
    """
    Toggle color output for your client.

    Usage: color on | color off

    Example:
        color off
    """
    want = (ctx.args or "").strip().lower()
    if want not in ("on", "off"):
        state = "off" if ctx.player.db.get("color") is False else "on"
        await ctx.session.send(f"Color is {state}. Usage: color on|off")
        return
    ctx.player.db.set("color", want == "on")
    from realm.core.markup import wrap
    await ctx.session.send(
        f"Color {want}." + (" " + wrap('g', 'Like this.')
                            if want == "on" else ""))


def register_utility_commands(dispatcher: CommandDispatcher) -> None:
    """Register utility commands with the dispatcher."""
    from functools import partial
    register = partial(dispatcher.register, category="utility")

    register(
        "color",
        cmd_color,
        help_text="Toggle color output",
        usage="color on|off",
    )

    register(
        "who",
        cmd_who,
        help_text="Show who is online",
    )

    register(
        "quit",
        cmd_quit,
        aliases=["QUIT"],
        help_text="Disconnect from the game",
    )

    register(
        "help",
        cmd_help,
        aliases=["?"],
        help_text="Show help on commands",
        usage="help [command]",
    )

    register(
        "commands",
        cmd_commands,
        help_text="List all available commands",
    )

    register(
        "time",
        cmd_time,
        help_text="Show the current time",
    )

    register(
        "uptime",
        cmd_uptime,
        help_text="Show server uptime",
        permission="builder",
    )

    register(
        "think",
        cmd_think,
        help_text="Think to yourself",
        usage="think <thought>",
    )

    register(
        "recall",
        cmd_recall,
        help_text="Return to your home",
    )
