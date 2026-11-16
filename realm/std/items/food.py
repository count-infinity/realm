"""
Eating and drinking (MUD_PLAN 3.4).

A line these commands cannot use (nothing named, nothing edible) goes to
the world's softcode ``$``-commands before it is refused, so a builder's
``$eat`` or ``$drink`` still works.

``eat`` takes something tagged ``food`` from your inventory; ``drink``
takes something tagged ``drink`` from your inventory or the room (a
fountain). Each fires a gated ``item:on_eat`` / ``item:on_drink`` (hooks
``EAT`` and ``DRINK``, so the item's softcode runs and may refuse), mends
the pools named in the item's ``restores`` attribute (``{"hp": 5}``; a pool
the eater lacks is skipped), then uses the item up: food is gone, a drink
loses one of its ``charges`` (none means it never runs dry).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.commands.base import find_object
from realm.core.pools import has_pool, mend, settle
from realm.core.propagation import deliver_messages
from realm.core.world import get_world
from realm.std.items.actions import ItemAction

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject


async def _restore(player: GameObject, item: GameObject) -> None:
    restores = item.db.get('restores')
    if not isinstance(restores, dict):
        return
    for pool, amount in restores.items():
        if has_pool(player, str(pool)) and int(amount) > 0:
            await settle(mend(player, str(pool), int(amount)), source=item)


async def world_verb(ctx: CommandContext) -> bool:
    """Offer the line to the world's softcode ``$``-commands (a builder's
    ``$eat`` on a buffet, ``$drink`` on a bar), as ``cast`` does: a built-in
    must not shadow a verb the world defines. True when one took it."""
    engine = get_world().scripts
    return engine is not None and await engine.handle_unknown_command(ctx)


async def _consume(ctx: CommandContext, *, verb: str, tag: str, action_type: str,
                   in_room: bool, refusal: str) -> None:
    from realm.std.items.commands import gated_item_action

    name = (ctx.args or "").strip()
    item = find_object(ctx, name, search_room=in_room, search_inventory=True) \
        if name else None
    if item is None or not item.has_tag(tag):
        if await world_verb(ctx):
            return
        if not name:
            await ctx.session.send(f"{verb.capitalize()} what?")
        elif item is None:
            await ctx.session.send(f"You don't have '{name}'.")
        else:
            await ctx.session.send(refusal)
        return
    charges = item.db.get('charges')
    if charges is not None and int(charges) <= 0:
        await ctx.session.send(f"{item.name} is empty.")
        return

    async def _apply(_a) -> None:
        await _restore(ctx.player, item)

    action = await gated_item_action(ctx.player, action_type, item,
                                     fail_msg=f"You can't {verb} {item.name}.",
                                     apply=_apply)
    if action is None:
        return
    action.add_message("actor", f"You {verb} " + "{target:a}.")
    action.add_message("room", "{actor} " + f"{verb}s " + "{target:a}.")
    deliver_messages(action)

    if charges is not None:
        item.db.charges = int(charges) - 1
    elif tag == 'food':
        store = get_world().store
        item.location = None
        if store is not None:
            await store.delete(item)


async def cmd_eat(ctx: CommandContext) -> None:
    """
    Eat something you carry.

    Usage: eat <food>
    """
    await _consume(ctx, verb="eat", tag="food", action_type=ItemAction.ON_EAT,
                   in_room=False, refusal="That's not edible.")


async def cmd_drink(ctx: CommandContext) -> None:
    """
    Drink from something you carry, or a fountain where you stand.

    Usage: drink <container>
    """
    await _consume(ctx, verb="drink", tag="drink", action_type=ItemAction.ON_DRINK,
                   in_room=True, refusal="You can't drink from that.")


__all__ = ["cmd_eat", "cmd_drink", "world_verb"]
