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
    """Show list of available commands."""
    commands = ctx.dispatcher.list_commands(ctx.player)

    await ctx.session.send("\n" + "=" * 40)
    await ctx.session.send("  Available Commands")
    await ctx.session.send("=" * 40)

    # Group commands by category
    categories = {
        'movement': ['go', 'north', 'south', 'east', 'west', 'up', 'down',
                     'northeast', 'northwest', 'southeast', 'southwest', 'in', 'out'],
        'communication': ['say', 'pose', 'semipose', 'emit', 'whisper', 'ooc', 'shout'],
        'looking': ['look', 'examine'],
        'inventory': ['inventory', 'get', 'drop', 'give', 'put'],
        'utility': ['who', 'quit', 'help', 'commands', 'time', 'uptime'],
    }

    shown = set()

    for category, cat_commands in categories.items():
        matching = [c for c in cat_commands if c in commands]
        if matching:
            await ctx.session.send(f"\n{category.title()}:")
            await ctx.session.send(f"  {', '.join(sorted(matching))}")
            shown.update(matching)

    # Show any remaining commands
    remaining = [c for c in commands if c not in shown]
    if remaining:
        await ctx.session.send("\nOther:")
        await ctx.session.send(f"  {', '.join(sorted(remaining))}")

    await ctx.session.send("\nType 'help <command>' for more information.")
    await ctx.session.send("")


async def _show_command_help(ctx: CommandContext, command_name: str) -> None:
    """Show help for a specific command."""
    cmd = ctx.dispatcher.get_command(command_name.lower())

    if not cmd:
        await ctx.session.send(f"Unknown command: {command_name}")
        await ctx.session.send("Type 'help' for a list of commands.")
        return

    await ctx.session.send(f"\n{cmd.name.upper()}")
    await ctx.session.send("-" * len(cmd.name))

    if cmd.help_text:
        await ctx.session.send(cmd.help_text)

    if cmd.usage:
        await ctx.session.send(f"\nUsage: {cmd.usage}")

    if cmd.aliases:
        await ctx.session.send(f"Aliases: {', '.join(cmd.aliases)}")

    await ctx.session.send("")


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


def register_utility_commands(dispatcher: CommandDispatcher) -> None:
    """Register utility commands with the dispatcher."""

    dispatcher.register(
        "who",
        cmd_who,
        help_text="Show who is online",
    )

    dispatcher.register(
        "quit",
        cmd_quit,
        aliases=["QUIT"],
        help_text="Disconnect from the game",
    )

    dispatcher.register(
        "help",
        cmd_help,
        aliases=["?"],
        help_text="Show help on commands",
        usage="help [command]",
    )

    dispatcher.register(
        "commands",
        cmd_commands,
        help_text="List all available commands",
    )

    dispatcher.register(
        "time",
        cmd_time,
        help_text="Show the current time",
    )

    dispatcher.register(
        "uptime",
        cmd_uptime,
        help_text="Show server uptime",
        permission="builder",
    )

    dispatcher.register(
        "think",
        cmd_think,
        help_text="Think to yourself",
        usage="think <thought>",
    )

    dispatcher.register(
        "recall",
        cmd_recall,
        help_text="Return to your home",
    )
