"""
Communication commands for REALM.

Handles speaking, emoting, and messaging. Each command emits an action
through the propagation engine; behaviors on actor / room / bystanders /
target can observe, modify (add modifiers), or block (e.g. a "muted"
debuff vetoes speech).
"""

from __future__ import annotations

from realm.commands import CommandContext, CommandDispatcher
from realm.commands.base import find_player
from realm.core.propagation import Action, ROOM_TARGET_CHAIN, propagate


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
    location = ctx.player.location
    if location is None:
        await ctx.session.send("You have nowhere to speak from.")
        return

    message = ctx.args
    action = Action(
        actor=ctx.player,
        target=location,
        action_type="event:speech",
        chain=ROOM_TARGET_CHAIN,
        extra={"message": message},
    )
    action.add_message("actor", f'You say, "{message}"')
    action.add_message("room", f'{{actor}} says, "{message}"')
    await propagate(action)


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
    location = ctx.player.location
    if location is None:
        return

    pose_text = ctx.args
    action = Action(
        actor=ctx.player,
        target=location,
        action_type="event:emote",
        chain=ROOM_TARGET_CHAIN,
        extra={"pose": pose_text},
    )
    action.add_message("actor", f"{{actor}} {pose_text}")
    action.add_message("room", f"{{actor}} {pose_text}")
    await propagate(action)


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
    location = ctx.player.location
    if location is None:
        return

    pose_text = ctx.args
    action = Action(
        actor=ctx.player,
        target=location,
        action_type="event:semipose",
        chain=ROOM_TARGET_CHAIN,
        extra={"pose": pose_text},
    )
    # No space between name and action — pre-format here so {actor} substitution
    # doesn't insert a leading space.
    line = f"{ctx.player.name}{pose_text}"
    action.add_message("actor", line)
    action.add_message("room", line)
    await propagate(action)


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
    location = ctx.player.location
    if location is None:
        return

    message = ctx.args
    action = Action(
        actor=ctx.player,
        target=location,
        action_type="event:emit",
        chain=ROOM_TARGET_CHAIN,
        extra={"message": message},
    )
    # @emit shows the same raw message to everyone, including the emitter.
    action.add_message("actor", message)
    action.add_message("room", message)
    await propagate(action)


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

    target = find_player(ctx, target_name)
    if not target:
        await ctx.session.send(f"You don't see '{target_name}' here.")
        return
    if target == ctx.player:
        await ctx.session.send("Talking to yourself?")
        return

    # Default chain — actor → room → bystanders → target. Bystanders see the
    # vague "X whispers something to Y" via the room audience; the target
    # gets the actual whisper via the target audience.
    action = Action(
        actor=ctx.player,
        target=target,
        action_type="event:whisper",
        extra={"message": message},
    )
    action.add_message("actor", f'You whisper to {{target}}, "{message}"')
    action.add_message("target", f'{{actor}} whispers, "{message}"')
    action.add_message("room", "{actor} whispers something to {target}.")
    await propagate(action)


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
    location = ctx.player.location
    if location is None:
        return

    message = ctx.args
    action = Action(
        actor=ctx.player,
        target=location,
        action_type="event:ooc",
        chain=ROOM_TARGET_CHAIN,
        extra={"message": message},
    )
    line = f"[OOC] {ctx.player.name}: {message}"
    action.add_message("actor", line)
    action.add_message("room", line)
    await propagate(action)


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
    location = ctx.player.location
    if location is None:
        return

    message = ctx.args
    action = Action(
        actor=ctx.player,
        target=location,
        action_type="event:shout",
        chain=ROOM_TARGET_CHAIN,
        # 'sound' tag lets behaviors react to any noisy action regardless
        # of whether it's speech, shouting, combat, etc.
        tags={"sound"},
        extra={"message": message},
    )
    action.add_message("actor", f'You shout, "{message}"')
    action.add_message("room", f'{{actor}} shouts, "{message}"')
    await propagate(action)
    # TODO: also propagate a muffled "Someone shouts in the distance..." to
    # adjacent rooms via exits — needs a multi-room chain helper.


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
