"""
Abilities typed as commands (MUD_PLAN 4.1).

``kick fido``: when no command matches, a verb that names an
``ability_def`` (by name or one of its ``aliases``) the player may invoke
runs it, with the rest of the line as the target. Spells (``spell_def``)
keep ``cast``. An ability the player may not invoke is not a command for
them, and the line goes on to softcode ``$``-commands and "Huh?" as any
unknown verb does. ``abilities`` lists what a character can invoke.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from realm.commands.base import find_object
from realm.core.defs import all_defs
from realm.std.abilities.abilities import (
    _cooldown_seconds,
    _cost_of,
    can_invoke,
    invoke_ability,
    ready_at,
)

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject


def ability_for_verb(player: GameObject, verb: str) -> GameObject | None:
    """The ability_def ``verb`` names (its name or an alias, exactly) that
    ``player`` may invoke."""
    want = verb.strip().lower()
    if not want:
        return None
    for adef in sorted(all_defs("ability").values(), key=lambda o: o.id):
        names = [adef.name.lower(), *(str(a).lower() for a in adef.db.get("aliases") or [])]
        if want in names and can_invoke(player, adef):
            return adef
    return None


async def ability_fallback(ctx: CommandContext) -> bool:
    """``feature.fallback``: run a typed ability. False when the verb names none."""
    player = ctx.player
    if player is None:
        return False
    adef = ability_for_verb(player, ctx.command_name)
    if adef is None:
        return False
    target = None
    words = (ctx.args or "").strip()
    if words:
        target = find_object(ctx, words, search_room=True, search_inventory=False)
        if target is None:
            await ctx.session.send(f"You don't see '{words}' here.")
            return True
    await invoke_ability(player, adef, target, verb=adef.name)
    return True


def cost_text(adef: GameObject) -> str:
    """"8 mana, 2 beats" — what invoking ``adef`` costs."""
    cost = _cost_of(adef) or {}
    parts = []
    if cost.get("pool"):
        parts.append(f"{int(cost.get('n') or 0)} {cost['pool']}")
    if cost.get("per_day"):
        parts.append(f"{int(cost['per_day'])} a day")
    if cost.get("cooldown"):
        beats = int(cost["cooldown"])
        parts.append(f"{beats} beat{'s' if beats != 1 else ''}")
    return ", ".join(parts) or "free"


async def cmd_abilities(ctx: CommandContext) -> None:
    """
    List the abilities you can use (type an ability's name to use it),
    what each costs, and whether it is ready.

    Usage: abilities
    """
    player = ctx.player
    usable = sorted((a for a in all_defs("ability").values() if can_invoke(player, a)),
                    key=lambda o: o.name)
    if not usable:
        await ctx.session.send("You have no abilities.")
        return
    lines = ["Abilities you can use:"]
    now = time.time()
    for adef in usable:
        waiting = ready_at(player, adef.name) - now
        state = f"  (ready in {int(waiting) + 1}s)" if _cooldown_seconds(_cost_of(adef)) \
            and waiting > 0 else ""
        lines.append(f"  {adef.name:<16} {cost_text(adef)}{state}")
    await ctx.session.send("\n".join(lines))


__all__ = ["ability_for_verb", "ability_fallback", "cost_text", "cmd_abilities"]
