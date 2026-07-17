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
from realm.core.action_tags import SOUND
from realm.core.propagation import ROOM_TARGET_CHAIN, Action, propagate


async def cmd_say(ctx: CommandContext) -> None:
    """
    Say something to the room.

    Usage: say <message>
           "<message>

    Example:
        say Meet me at the jetty.
    """
    if not ctx.args:
        await ctx.session.send("Say what?")
        return
    if ctx.player.location is None:
        await ctx.session.send("You have nowhere to speak from.")
        return

    from realm.core.verbs import do_say
    action = await do_say(ctx.player, ctx.args)
    if action and action.blocked:
        ctx.player.msg(action.block_reason or "You can't speak here.")


async def cmd_pose(ctx: CommandContext) -> None:
    """
    Emote/pose an action.

    Usage: pose <action>
           :<action>

    Example: pose waves hello.
             -> "YourName waves hello."

    Reference someone with /name — they read "you", everyone else reads
    the name they know them by:
        pose slides the datapad to /Kade.
             -> Kade reads "Ada slides the datapad to you."
             -> others read "Ada slides the datapad to Kade."
    A /word that matches no one in the room is left as typed.
    """
    if not ctx.args:
        await ctx.session.send("Pose what?")
        return
    if ctx.player.location is None:
        return

    from realm.core.verbs import do_pose
    action = await do_pose(ctx.player, ctx.args)
    if action and action.blocked:
        ctx.player.msg(action.block_reason or "You can't emote here.")



async def cmd_semipose(ctx: CommandContext) -> None:
    """
    Emote with name attached directly (no space).

    Usage: semipose <action>
           ;<action>

    Example: semipose 's dog barks.
             -> "YourName's dog barks."
    """
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
    # No space between name and action — the name is pre-formatted here so
    # {actor} substitution doesn't insert a leading space. The pose text
    # stays a {speech} token: it is player input, so it must not be
    # token-substituted, and renderers need a handle on it.
    line = f"{ctx.player.name}{{speech}}"
    action.add_message("actor", line, success_only=True)
    action.add_message("room", line, success_only=True)
    await propagate(action)
    if action.blocked:
        ctx.player.msg(action.block_reason or "You can't emote here.")


async def cmd_emit(ctx: CommandContext) -> None:
    """
    Emit a message to the room without your name.

    Usage: emit <message>
           \\<message>

    Example: emit A cold wind blows through the room.
    """
    if not ctx.args:
        await ctx.session.send("Emit what?")
        return
    if ctx.player.location is None:
        return

    from realm.core.verbs import do_emit
    action = await do_emit(ctx.player, ctx.args)
    if action and action.blocked:
        ctx.player.msg(action.block_reason or "You can't emit here.")


async def cmd_whisper(ctx: CommandContext) -> None:
    """
    Whisper privately to someone in the room.

    Usage: whisper <player> = <message>

    Example:
        whisper Bob = the key is under the third step
    """
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

    # do_whisper builds the actor/target/room lines and propagates; the
    # bystander room audience sees the vague "X whispers something to Y".
    from realm.core.verbs import do_whisper
    action = await do_whisper(ctx.player, target, message)
    if action and action.blocked:
        ctx.player.msg(action.block_reason or "You can't whisper here.")


async def cmd_ooc(ctx: CommandContext) -> None:
    """
    Out-of-character speech (clearly marked).

    Usage: ooc <message>

    Example:
        ooc anyone up for the lighthouse run?
    """
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
    # The body is a token like every other speech-family action, so player
    # text is never token-substituted. Renderers still see it — and a
    # language garbler should check `atype` and leave `event:ooc` alone:
    # out-of-character talk is the player speaking, not the character, so
    # it has no language and takes no accent.
    line = f"[OOC] {ctx.player.name}: {{speech}}"
    action.add_message("actor", line, success_only=True)
    action.add_message("room", line, success_only=True)
    await propagate(action)
    if action.blocked:
        ctx.player.msg(action.block_reason or "You can't speak here.")


async def cmd_shout(ctx: CommandContext) -> None:
    """
    Shout something loudly (heard in adjacent rooms).

    Usage: shout <message>

    Example:
        shout Fire on the promenade!
    """
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
        tags={SOUND},
        extra={"message": message},
    )
    action.add_message("actor", 'You shout, "{speech}"', success_only=True)
    action.add_message("room", '{actor} shouts, "{speech}"', success_only=True)
    await propagate(action)
    if action.blocked:
        ctx.player.msg(action.block_reason or "You can't speak here.")
    # TODO: also propagate a muffled "Someone shouts in the distance..." to
    # adjacent rooms via exits — needs a multi-room chain helper.


def register_communication_commands(dispatcher: CommandDispatcher) -> None:
    """Register communication commands with the dispatcher."""
    from functools import partial
    register = partial(dispatcher.register, category="communication")

    register(
        "say",
        cmd_say,
        aliases=["'"],
        help_text="Say something to the room",
        usage='say <message> or "<message>',
    )

    register(
        "pose",
        cmd_pose,
        aliases=["emote"],
        help_text="Emote an action",
        usage="pose <action> or :<action>",
    )

    register(
        "semipose",
        cmd_semipose,
        help_text="Emote with name attached",
        usage="semipose <action> or ;<action>",
    )

    register(
        "emit",
        cmd_emit,
        help_text="Emit a message to the room",
        usage="emit <message> or \\<message>",
        permission="builder",
    )

    register(
        "whisper",
        cmd_whisper,
        aliases=["w"],
        help_text="Whisper privately to someone",
        usage="whisper <player> = <message>",
        parse_equals=True,
    )

    register(
        "ooc",
        cmd_ooc,
        help_text="Out-of-character speech",
        usage="ooc <message>",
    )

    register(
        "shout",
        cmd_shout,
        help_text="Shout to the room (and nearby)",
        usage="shout <message>",
    )
