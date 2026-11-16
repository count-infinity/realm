"""
Positions: standing, resting, sleeping (MUD_PLAN 2.2).

A position is a tag: ``resting`` or ``sleeping`` (standing is neither).
Resting and sleeping multiply regeneration by ``REST_REGEN`` and
``SLEEP_REGEN``. Neither walks. A hostile act against either stands it up.
A sleeper sees nothing but itself, hears nothing said to the room (Decision
D4: what is addressed to it, the action's target, still arrives), and every
line it types but a few is answered "You are asleep."
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.action_tags import HOSTILE
from realm.core.propagation import Action, deliver_messages

if TYPE_CHECKING:
    from realm.commands.dispatcher import CommandContext
    from realm.core.objects import GameObject
    from realm.core.world import World
    from realm.gateway.session import Session

RESTING = "resting"
SLEEPING = "sleeping"

#: What a sleeper may still type: these names, and any alias of them
#: (``score`` is itself an alias of ``points``).
AWAKE_COMMANDS = frozenset({"stand", "wake", "help", "who", "score", "quit",
                            "tell", "reply"})


def _tell_room(actor: GameObject, line: str) -> None:
    """``line`` (with ``{actor}``) to everyone else in the room, through
    delivery, so perception and the deaf rules apply."""
    action = Action(actor=actor, target=None, action_type="vitals:position")
    action.add_message("room", line)
    deliver_messages(action)


async def _refused(ctx: CommandContext, doing: str) -> bool:
    player = ctx.player
    if player.has_tag("unconscious"):
        await ctx.session.send("You are unconscious.")
        return True
    if player.has_tag("in_combat") and doing:
        await ctx.session.send(f"You can't {doing} while fighting!")
        return True
    return False


async def cmd_rest(ctx: CommandContext) -> None:
    """
    Sit down and rest: you recover faster, but cannot walk.

    Usage: rest
    """
    player = ctx.player
    if await _refused(ctx, "rest"):
        return
    if player.has_tag(RESTING):
        await ctx.session.send("You are already resting.")
        return
    if player.has_tag(SLEEPING):
        player.remove_tag(SLEEPING)
        player.add_tag(RESTING)
        await ctx.session.send("You wake and sit up.")
        _tell_room(player, "{actor} wakes and sits up.")
        return
    player.add_tag(RESTING)
    await ctx.session.send("You sit down and rest.")
    _tell_room(player, "{actor} sits down and rests.")


async def cmd_sleep(ctx: CommandContext) -> None:
    """
    Lie down and sleep: you recover fastest, but see and hear nothing
    around you. Wake with `wake` (or `stand`).

    Usage: sleep
    """
    player = ctx.player
    if await _refused(ctx, "sleep"):
        return
    if player.has_tag(SLEEPING):
        await ctx.session.send("You are already asleep.")
        return
    player.remove_tag(RESTING)
    player.add_tag(SLEEPING)
    await ctx.session.send("You lie down and go to sleep.")
    _tell_room(player, "{actor} lies down and goes to sleep.")


async def cmd_stand(ctx: CommandContext) -> None:
    """
    Get up from resting, or wake from sleep.

    Usage: stand   (or: wake)
    """
    player = ctx.player
    if await _refused(ctx, ""):
        return
    if player.has_tag(SLEEPING):
        player.remove_tag(SLEEPING)
        player.remove_tag(RESTING)
        await ctx.session.send("You wake and stand up.")
        _tell_room(player, "{actor} wakes and stands up.")
    elif player.has_tag(RESTING):
        player.remove_tag(RESTING)
        await ctx.session.send("You stand up.")
        _tell_room(player, "{actor} stands up.")
    else:
        await ctx.session.send("You are already standing.")


def position_multiplier(obj: GameObject, pool_name: str) -> float:
    """The first of the vitals multipliers: ``REST_REGEN`` resting,
    ``SLEEP_REGEN`` asleep, else 1."""
    from realm.core.world import get_world
    if obj.has_tag(SLEEPING):
        return float(get_world().setting("SLEEP_REGEN"))
    if obj.has_tag(RESTING):
        return float(get_world().setting("REST_REGEN"))
    return 1.0


async def position_gate(actor: GameObject, exit_obj: GameObject | None,
                        direction: str, *, fleeing: bool) -> str | None:
    """Resting and sleeping characters do not walk."""
    if actor.has_tag(RESTING) or actor.has_tag(SLEEPING):
        return "You need to stand up first."
    return None


async def roused_observer(action: Action) -> None:
    """A hostile act against a resting or sleeping character stands it up."""
    if action.blocked or HOSTILE not in action.tags:
        return
    target = action.target
    if target is None or target is action.actor:
        return
    if not (target.has_tag(RESTING) or target.has_tag(SLEEPING)):
        return
    target.remove_tag(RESTING)
    target.remove_tag(SLEEPING)
    target.msg("You are jolted to your feet!")
    _tell_room(target, "{actor} scrambles to their feet.")


async def asleep_interceptor(world: World, session: Session, line: str) -> bool:
    """A sleeping player's input: anything but ``AWAKE_COMMANDS`` is
    answered "You are asleep." and goes no further."""
    player = session.player
    if player is None or not player.has_tag(SLEEPING):
        return False
    words = line.split(maxsplit=1)
    if not words:
        return False
    typed = words[0].lower()
    command = world.dispatcher.get_command(typed)
    if typed in AWAKE_COMMANDS or (command is not None and command.name in AWAKE_COMMANDS):
        return False
    await session.send("You are asleep.")
    return True


def asleep_sight(viewer: GameObject, obj: GameObject) -> bool | None:
    """A sleeper sees nothing (the kernel already lets it see itself)."""
    return False if viewer.has_tag(SLEEPING) else None


def asleep_deaf(recipient: GameObject, action: Action) -> bool:
    """A sleeper hears nothing it is not party to: messages for the room
    and other audiences stop, what is addressed to it (it is the action's
    target, as with a tell) arrives."""
    return (recipient.has_tag(SLEEPING) and recipient is not action.actor
            and recipient is not action.target)


def position_marker(obj: GameObject, looker: GameObject | None) -> str | None:
    """``Pat (sleeping)``, ``Pat (resting)`` in room listings."""
    if obj.has_tag(SLEEPING):
        return "sleeping"
    if obj.has_tag(RESTING):
        return "resting"
    return None


__all__ = ["RESTING", "SLEEPING", "AWAKE_COMMANDS", "cmd_rest", "cmd_sleep",
           "cmd_stand", "position_multiplier", "position_gate", "roused_observer",
           "asleep_interceptor", "asleep_sight", "asleep_deaf", "position_marker"]
