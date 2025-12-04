"""
Communication commands for REALM.

Handles speaking, emoting, and messaging.
"""

from __future__ import annotations

from realm.commands import CommandContext, CommandDispatcher
from realm.commands.base import find_player
from realm.core.events import Event, EventType


async def cmd_say(ctx: CommandContext) -> None:
    """
    Say something to the room.

    Usage: say <message>
           "<message>
    """
    if not ctx.player:
        return

    if not ctx.args:
        await ctx.session.send("Say what?")
        return

    message = ctx.args

    # Show to speaker
    await ctx.session.send(f'You say, "{message}"')

    # Show to others in room
    if ctx.player.location:
        event = Event(
            type=EventType.SPEECH,
            source=ctx.player,
            location=ctx.player.location,
            data={'message': message},
        )

        for obj in ctx.player.location.contents:
            if obj != ctx.player and obj.has_tag('player'):
                obj.msg(f'{ctx.player.name} says, "{message}"')


async def cmd_pose(ctx: CommandContext) -> None:
    """
    Emote/pose an action.

    Usage: pose <action>
           :<action>

    Example: pose waves hello.
             -> "YourName waves hello."
    """
    if not ctx.player:
        return

    if not ctx.args:
        await ctx.session.send("Pose what?")
        return

    action = ctx.args

    # Show to self and others
    pose_msg = f"{ctx.player.name} {action}"
    await ctx.session.send(pose_msg)

    if ctx.player.location:
        event = Event(
            type=EventType.EMOTE,
            source=ctx.player,
            location=ctx.player.location,
            data={'action': action},
        )

        for obj in ctx.player.location.contents:
            if obj != ctx.player and obj.has_tag('player'):
                obj.msg(pose_msg)


async def cmd_semipose(ctx: CommandContext) -> None:
    """
    Emote with name attached directly (no space).

    Usage: semipose <action>
           ;<action>

    Example: semipose 's dog barks.
             -> "YourName's dog barks."
    """
    if not ctx.player:
        return

    if not ctx.args:
        await ctx.session.send("Pose what?")
        return

    action = ctx.args

    # No space between name and action
    pose_msg = f"{ctx.player.name}{action}"
    await ctx.session.send(pose_msg)

    if ctx.player.location:
        for obj in ctx.player.location.contents:
            if obj != ctx.player and obj.has_tag('player'):
                obj.msg(pose_msg)


async def cmd_emit(ctx: CommandContext) -> None:
    """
    Emit a message to the room without your name.

    Usage: emit <message>
           \\<message>

    Example: emit A cold wind blows through the room.
    """
    if not ctx.player:
        return

    if not ctx.args:
        await ctx.session.send("Emit what?")
        return

    message = ctx.args

    # Show to everyone including self
    await ctx.session.send(message)

    if ctx.player.location:
        for obj in ctx.player.location.contents:
            if obj != ctx.player and obj.has_tag('player'):
                obj.msg(message)


async def cmd_whisper(ctx: CommandContext) -> None:
    """
    Whisper privately to someone in the room.

    Usage: whisper <player> = <message>
    """
    if not ctx.player:
        return

    if not ctx.left_args or not ctx.right_args:
        await ctx.session.send("Usage: whisper <player> = <message>")
        return

    target_name = ctx.left_args
    message = ctx.right_args

    # Find the target player
    target = find_player(ctx, target_name)
    if not target:
        await ctx.session.send(f"You don't see '{target_name}' here.")
        return

    if target == ctx.player:
        await ctx.session.send("Talking to yourself?")
        return

    # Send whisper
    await ctx.session.send(f'You whisper to {target.name}, "{message}"')
    target.msg(f'{ctx.player.name} whispers, "{message}"')

    # Notify others that a whisper occurred (but not the content)
    if ctx.player.location:
        for obj in ctx.player.location.contents:
            if obj.has_tag('player') and obj != ctx.player and obj != target:
                obj.msg(f"{ctx.player.name} whispers something to {target.name}.")


async def cmd_ooc(ctx: CommandContext) -> None:
    """
    Out-of-character speech (clearly marked).

    Usage: ooc <message>
    """
    if not ctx.player:
        return

    if not ctx.args:
        await ctx.session.send("OOC what?")
        return

    message = ctx.args

    # Show to self and room with OOC marker
    await ctx.session.send(f'[OOC] {ctx.player.name}: {message}')

    if ctx.player.location:
        for obj in ctx.player.location.contents:
            if obj != ctx.player and obj.has_tag('player'):
                obj.msg(f'[OOC] {ctx.player.name}: {message}')


async def cmd_shout(ctx: CommandContext) -> None:
    """
    Shout something loudly (heard in adjacent rooms).

    Usage: shout <message>
    """
    if not ctx.player:
        return

    if not ctx.args:
        await ctx.session.send("Shout what?")
        return

    message = ctx.args

    # Show to self
    await ctx.session.send(f'You shout, "{message}"')

    if ctx.player.location:
        # Show to others in room
        for obj in ctx.player.location.contents:
            if obj != ctx.player and obj.has_tag('player'):
                obj.msg(f'{ctx.player.name} shouts, "{message}"')

        # TODO: Also send to adjacent rooms (through exits) as:
        # "Someone shouts in the distance..."


def register_communication_commands(dispatcher: CommandDispatcher) -> None:
    """Register communication commands with the dispatcher."""

    dispatcher.register(
        "say",
        cmd_say,
        aliases=["'"],
        help_text="Say something to the room",
        usage='say <message> or "<message>',
    )

    dispatcher.register(
        "pose",
        cmd_pose,
        aliases=["emote"],
        help_text="Emote an action",
        usage="pose <action> or :<action>",
    )

    dispatcher.register(
        "semipose",
        cmd_semipose,
        help_text="Emote with name attached",
        usage="semipose <action> or ;<action>",
    )

    dispatcher.register(
        "emit",
        cmd_emit,
        help_text="Emit a message to the room",
        usage="emit <message> or \\<message>",
        permission="builder",
    )

    dispatcher.register(
        "whisper",
        cmd_whisper,
        aliases=["w"],
        help_text="Whisper privately to someone",
        usage="whisper <player> = <message>",
        parse_equals=True,
    )

    dispatcher.register(
        "ooc",
        cmd_ooc,
        help_text="Out-of-character speech",
        usage="ooc <message>",
    )

    dispatcher.register(
        "shout",
        cmd_shout,
        help_text="Shout to the room (and nearby)",
        usage="shout <message>",
    )
