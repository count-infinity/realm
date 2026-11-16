"""
Communication commands for REALM.

Handles speaking, emoting, and messaging. Each command emits an action
through the propagation engine; behaviors on actor / room / bystanders /
target can observe, modify (add modifiers), or block (e.g. a "muted"
debuff vetoes speech).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.commands import CommandContext
from realm.commands.base import find_player, format_list
from realm.core.action_tags import SOUND
from realm.core.pools import declared_pools, pool_def, pool_get, pool_max
from realm.core.propagation import ROOM_TARGET_CHAIN, Action, propagate
from realm.core.world import get_world
from realm.std.talk.actions import TalkAction
from realm.std.talk.verbs import do_emit, do_pose, do_say, do_semipose, do_whisper

if TYPE_CHECKING:
    from realm.core.objects import GameObject


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

    action = await do_say(ctx.player, ctx.args)
    if action and action.blocked:
        ctx.player.msg(action.block_reason or "You can't speak here.")


def report_line(player: GameObject) -> str:
    """"I have 12/20 hp, 50/100 mana and 80/100 move.": every pool the
    character has that recovers on its own, as ``report`` says it (ROM's
    hp, mana and move; a stomach is not reported)."""
    parts = []
    for name in declared_pools(player):
        pool = pool_def(player, name)
        if pool is not None and not pool.regen:
            continue
        value, maximum = pool_get(player, name), pool_max(player, name)
        parts.append(f"{value}/{maximum} {name}" if maximum is not None else f"{value} {name}")
    if not parts:
        return "I am well."
    return f"I have {format_list(parts, conjunction='and')}."


async def cmd_report(ctx: CommandContext) -> None:
    """
    Tell the room how you are: your hit points and the rest of your pools.

    Usage: report
    """
    engine = get_world().scripts
    if engine is not None and await engine.handle_unknown_command(ctx):
        return                                  # a world $report comes first
    if ctx.player.location is None:
        await ctx.session.send("You have nowhere to speak from.")
        return
    action = await do_say(ctx.player, report_line(ctx.player))
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

    action = await do_semipose(ctx.player, ctx.args)
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
        action_type=TalkAction.OOC,
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
        action_type=TalkAction.SHOUT,
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


