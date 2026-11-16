"""
Tells, ignore and afk (MUD_PLAN 7.1).

``tell <player> <message>`` reaches an online player anywhere: one
``comm:on_tell`` action with the recipient as target and no room audience,
so the recipient's softcode hears it (``ON_TELL``) and a ward on the
teller's room may refuse it. ``reply`` answers the last teller. ``ignore``
keeps a list of names a player will not hear from, and ``afk`` leaves a
message tellers are shown.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.propagation import Action, ActorStep, TargetStep, deliver_messages, gate_action
from realm.gateway.session import is_online
from realm.std.channels.common import find_character

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject


class _BothRooms:
    """The teller's room and the recipient's, as rooms only: a ward in
    either may refuse the tell, and nobody standing there overhears it."""

    @staticmethod
    def _rooms(action: Action) -> list:
        rooms = []
        for party in (action.actor, action.target):
            room = party.location if party is not None else None
            if room is not None and room not in rooms:
                rooms.append(room)
        return rooms

    async def on_check(self, action: Action) -> None:
        for room in self._rooms(action):
            await room.visit_check(action)

    async def on_react(self, action: Action) -> None:
        for room in self._rooms(action):
            await room.visit_react(action)


#: Who a tell passes through: the teller, both rooms, the recipient.
TELL_CHAIN = [ActorStep(), _BothRooms(), TargetStep()]


def ignores(recipient: GameObject, teller: GameObject) -> bool:
    return teller.name.lower() in [str(n).lower() for n in recipient.db.get("ignore") or []]


async def send_tell(ctx: CommandContext, recipient: GameObject, message: str) -> None:
    teller = ctx.player
    if recipient is teller:
        await ctx.session.send("You mutter to yourself.")
        return
    if not is_online(recipient):
        await ctx.session.send(f"{recipient.name} is not online. Leave them a message "
                               f"with mail.")
        return
    if ignores(recipient, teller):
        await ctx.session.send(f"{recipient.name} is not listening to you.")
        return
    action = Action(actor=teller, target=recipient, action_type="comm:on_tell",
                    chain=TELL_CHAIN, extra={"message": message})
    if not await gate_action(action, fail_msg="Your words do not carry."):
        return
    # Names are written out, not perceived: a tell is not seen across rooms.
    action.add_message("actor", f"You tell {recipient.name}, '" + "{speech}'")
    action.add_message("target", f"{teller.name} tells you, '" + "{speech}'")
    deliver_messages(action)
    recipient.db.last_teller = teller.id
    if recipient.has_tag("afk"):
        away = recipient.db.get("afk_message") or "away from the keyboard"
        await ctx.session.send(f"{recipient.name} is away: {away}")


async def cmd_tell(ctx: CommandContext) -> None:
    """
    Say something privately to a player anywhere in the game.

    Usage: tell <player> <message>
    """
    words = (ctx.args or "").split(maxsplit=1)
    if len(words) < 2:
        await ctx.session.send("Tell whom what?")
        return
    recipient = find_character(words[0])
    if recipient is None:
        await ctx.session.send(f"No one called '{words[0]}' plays here.")
        return
    await send_tell(ctx, recipient, words[1])


async def cmd_reply(ctx: CommandContext) -> None:
    """
    Answer the last person who told you something.

    Usage: reply <message>
    """
    message = (ctx.args or "").strip()
    last = ctx.player.db.get("last_teller")
    recipient = ctx.persistence.get_cached(str(last)) if last and ctx.persistence else None
    if recipient is None:
        await ctx.session.send("Nobody has told you anything to reply to.")
        return
    if not message:
        await ctx.session.send(f"Reply what to {recipient.name}?")
        return
    await send_tell(ctx, recipient, message)


async def cmd_ignore(ctx: CommandContext) -> None:
    """
    Stop hearing tells from a player, or list whom you ignore.

    Usage: ignore [player]
    """
    player = ctx.player
    names = list(player.db.get("ignore") or [])
    who = (ctx.args or "").strip()
    if not who:
        await ctx.session.send("You are ignoring: " + ", ".join(names) if names
                               else "You are ignoring no one.")
        return
    other = find_character(who)
    name = other.name if other is not None else who
    if name.lower() not in [n.lower() for n in names]:
        names.append(name)
        player.db.ignore = names
    await ctx.session.send(f"You are ignoring {name}.")


async def cmd_unignore(ctx: CommandContext) -> None:
    """
    Hear tells from a player you were ignoring.

    Usage: unignore <player>
    """
    player = ctx.player
    who = (ctx.args or "").strip().lower()
    names = [n for n in (player.db.get("ignore") or []) if str(n).lower() != who]
    player.db.ignore = names
    await ctx.session.send(f"You are no longer ignoring {ctx.args.strip()}.")


async def cmd_afk(ctx: CommandContext) -> None:
    """
    Mark yourself away (anyone who tells you something is shown your
    message), or back.

    Usage: afk [message]
    """
    player = ctx.player
    message = (ctx.args or "").strip()
    if player.has_tag("afk") and not message:
        player.remove_tag("afk")
        player.db.delete("afk_message")
        await ctx.session.send("You are back.")
        return
    player.add_tag("afk")
    player.db.afk_message = message or "away from the keyboard"
    await ctx.session.send(f"You are away: {player.db.afk_message}")


def afk_field(viewer: GameObject | None, player: GameObject) -> str | None:
    """A ``who`` field: ``afk`` beside a player who is away."""
    return "afk" if player.has_tag("afk") else None


__all__ = ["ignores", "send_tell", "cmd_tell", "cmd_reply", "cmd_ignore", "cmd_unignore",
           "cmd_afk", "afk_field"]
