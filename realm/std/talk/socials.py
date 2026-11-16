"""
Socials (MUD_PLAN 7.3): ``smile``, ``bow bob``.

A social is a ``social_def`` object with up to five lines, in the usual
``{actor}`` / ``{target}`` formatting (so an unseen actor reads
"Someone"):

    actor         what the actor sees, with no target
    room          what the room sees, with no target
    actor_at      what the actor sees, with a target
    target        what the target sees
    room_at       what everyone else sees, with a target

Its name is a command only when no command, exit or world ``$``-command
answers to the word, so a social never shadows anything. The
``socials-classic`` pack ships the common Diku socials.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.commands.base import find_object
from realm.core.propagation import Action, propagate
from realm.core.world import find_world

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject


def socials() -> dict[str, GameObject]:
    from realm.core.defs import def_objects
    return def_objects("social")


async def social_fallback(ctx: CommandContext) -> bool:
    """``feature.fallback``: run the social the typed word names."""
    player = ctx.player
    social = socials().get(ctx.command_name.lower()) if player is not None else None
    if social is None:
        return False
    world = find_world()
    if world is not None and world.scripts is not None \
            and await world.scripts.handle_unknown_command(ctx):
        return True                       # a world verb of the same word comes first
    words = (ctx.args or "").strip()
    action = Action(actor=player, target=None, action_type="event:social",
                    extra={"social": social.name})
    if words:
        if not social.db.get("actor_at"):
            await ctx.session.send(f"You can't {social.name} at someone.")
            return True
        target = find_object(ctx, words, search_room=True, search_inventory=False)
        if target is None:
            await ctx.session.send("They aren't here.")
            return True
        action.target = target
        action.add_message("actor", str(social.db.actor_at))
        if social.db.get("target"):
            action.add_message("target", str(social.db.target))
        if social.db.get("room_at"):
            action.add_message("room", str(social.db.room_at))
    else:
        action.add_message("actor", str(social.db.get("actor") or f"You {social.name}."))
        if social.db.get("room"):
            action.add_message("room", str(social.db.room))
    await propagate(action)
    return True


async def cmd_socials(ctx: CommandContext) -> None:
    """
    List the socials: type one (with a name after it, for most) to use it.

    Usage: socials
    """
    names = sorted(socials())
    if not names:
        await ctx.session.send("This game has no socials.")
        return
    rows = [", ".join(names[i:i + 10]) for i in range(0, len(names), 10)]
    ctx.session.send_paged("Socials:\n  " + "\n  ".join(rows))


__all__ = ["socials", "social_fallback", "cmd_socials"]
