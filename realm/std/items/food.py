"""
Eating and drinking (MUD_PLAN 3.4, and 12.4 for food and drink).

A line these commands cannot use (nothing named, nothing edible) goes to
the world's softcode ``$``-commands before it is refused, so a builder's
``$eat``, ``$drink`` or ``$fill`` still works.

``eat`` takes something tagged ``food`` from your inventory; ``drink``
takes something tagged ``drink`` from your inventory or the room. Each
fires a gated ``item:on_eat`` / ``item:on_drink`` (hooks ``EAT`` and
``DRINK``, so the item's softcode runs and may refuse), mends the pools
named in the item's ``restores`` attribute (``{"hp": 5}``; a pool the
eater lacks is skipped), then:

- food moves one ``bite`` (default: all of it) of its ``nourishment`` into
  the eater's ``food`` pool, scaled by ``FOOD_GAIN`` percent, and is gone
  when its nourishment is. A full stomach refuses more;
- a drink with ``liquid_remaining`` (a container) moves one ``sip``
  (default 50) of its ``liquid`` into ``water``, scaled by ``WATER_GAIN``,
  and lowers what remains; one tagged ``fountain`` never runs dry. A full
  stomach refuses more. ``drink`` alone drinks from a fountain here, or
  from the room itself when it is tagged ``water_source`` (a river, a
  well);
- a drink without a liquid (a potion-like flask) loses one of its
  ``charges`` (none means it never runs dry).

``fill <container> [<source>]`` refills a container (one with
``liquid_held``) from a fountain, or from a ``water_source`` room.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.commands.base import find_object
from realm.core.pools import has_pool, is_spent, mend, pool_get, pool_max, settle
from realm.core.propagation import Action, deliver_messages
from realm.core.world import get_world
from realm.std.items.actions import ItemAction

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject

#: How much one ``drink`` takes from a container without its own ``sip``.
DEFAULT_SIP = 50


async def _restore(player: GameObject, item: GameObject) -> None:
    restores = item.db.get('restores')
    if not isinstance(restores, dict):
        return
    for pool, amount in restores.items():
        if has_pool(player, str(pool)) and int(amount) > 0:
            await settle(mend(player, str(pool), int(amount)), source=item)


def _full(player: GameObject, pool: str) -> bool:
    """``player`` has the pool and it is at its max."""
    value, maximum = pool_get(player, pool), pool_max(player, pool)
    return value is not None and maximum is not None and value >= maximum


def _empty(player: GameObject, pool: str) -> bool:
    return has_pool(player, pool) and is_spent(player, pool)


async def _take_in(player: GameObject, pool: str, amount: int, setting: str,
                   source: GameObject) -> None:
    """Mend ``pool`` by ``amount`` scaled by the ``setting`` percent."""
    gain = round(int(amount) * float(get_world().setting(setting, 100)) / 100)
    if gain > 0 and has_pool(player, pool):
        await settle(mend(player, pool, gain), source=source)


def _satiation(player: GameObject, pool: str, was_empty: bool,
               relieved: str, brimming: str) -> None:
    """CoffeeMud's lines after a meal or a drink."""
    if was_empty and not _empty(player, pool):
        player.msg(relieved)
    elif _full(player, pool):
        player.msg(brimming)


async def world_verb(ctx: CommandContext) -> bool:
    """Offer the line to the world's softcode ``$``-commands (a builder's
    ``$eat`` on a buffet, ``$drink`` on a bar), as ``cast`` does: a built-in
    must not shadow a verb the world defines. True when one took it."""
    engine = get_world().scripts
    return engine is not None and await engine.handle_unknown_command(ctx)


async def _use_up(item: GameObject) -> None:
    store = get_world().store
    item.location = None
    if store is not None:
        await store.delete(item)


async def _gated(ctx: CommandContext, action_type: str, target: GameObject,
                 verb: str, apply) -> Action | None:
    from realm.std.items.commands import gated_item_action
    return await gated_item_action(ctx.player, action_type, target,
                                   fail_msg=f"You can't {verb} {target.name}.",
                                   apply=apply)


async def cmd_eat(ctx: CommandContext) -> None:
    """
    Eat something you carry, a bite at a time when it is a big meal.

    Usage: eat <food>
    """
    player = ctx.player
    name = (ctx.args or "").strip()
    item = find_object(ctx, name, search_room=False, search_inventory=True) \
        if name else None
    if item is None or not item.has_tag('food'):
        if await world_verb(ctx):
            return
        if not name:
            await ctx.session.send("Eat what?")
        elif item is None:
            await ctx.session.send(f"You don't have '{name}'.")
        else:
            await ctx.session.send("That's not edible.")
        return
    charges = item.db.get('charges')
    if charges is not None and int(charges) <= 0:
        await ctx.session.send(f"{item.name} is empty.")
        return
    nourishment = max(0, int(item.db.get('nourishment') or 0))
    if nourishment and _full(player, 'food'):
        await ctx.session.send("You are too full to eat more.")
        return
    bite = int(item.db.get('bite') or 0)
    amount = nourishment if bite <= 0 or bite >= nourishment else bite
    whole = amount >= nourishment
    was_hungry = _empty(player, 'food')

    async def _apply(_a) -> None:
        await _restore(player, item)
        if amount:
            await _take_in(player, 'food', amount, "FOOD_GAIN", item)

    action = await _gated(ctx, ItemAction.ON_EAT, item, "eat", _apply)
    if action is None:
        return
    if whole:
        action.add_message("actor", "You eat {target:a}.")
        action.add_message("room", "{actor} eats {target:a}.")
    else:
        action.add_message("actor", "You take a bite of {target:a}.")
        action.add_message("room", "{actor} takes a bite of {target:a}.")
    deliver_messages(action)
    if amount:
        _satiation(player, 'food', was_hungry, "You are no longer hungry.", "You are full.")

    if charges is not None and not nourishment:
        item.db.charges = int(charges) - 1
    elif whole:
        await _use_up(item)
    else:
        item.db.nourishment = nourishment - amount


def _fountain_here(room: GameObject | None) -> GameObject | None:
    if room is None:
        return None
    return next((o for o in room.contents
                 if o.has_tag('fountain') and o.has_tag('drink')), None)


def _holds_liquid(item: GameObject) -> bool:
    return item.has_tag('fountain') or item.db.get('liquid_remaining') is not None


def _liquid(source: GameObject) -> str:
    return str(source.db.get('liquid') or 'water')


async def _drink_liquid(ctx: CommandContext, source: GameObject, *, room: bool) -> None:
    """One sip from a container, a fountain, or a ``water_source`` room."""
    player = ctx.player
    endless = room or source.has_tag('fountain')
    remaining = None if endless else int(source.db.get('liquid_remaining') or 0)
    if remaining is not None and remaining <= 0:
        await ctx.session.send(f"{source.name} is empty.")
        return
    sip = max(1, int(source.db.get('sip') or DEFAULT_SIP))
    if remaining is not None:
        sip = min(sip, remaining)
    if _full(player, 'water'):
        await ctx.session.send("You are too full to drink more.")
        return
    liquid = _liquid(source)
    was_thirsty = _empty(player, 'water')

    async def _apply(_a) -> None:
        if not room:
            await _restore(player, source)
        await _take_in(player, 'water', sip, "WATER_GAIN", source)

    action = await _gated(ctx, ItemAction.ON_DRINK, source, "drink from", _apply)
    if action is None:
        return
    if room:
        action.add_message("actor", f"You drink {liquid} here.")
        action.add_message("room", "{actor} " + f"drinks {liquid} here.")
    else:
        action.add_message("actor", f"You drink {liquid} from " + "{target:a}.")
        action.add_message("room", "{actor} " + f"drinks {liquid} from " + "{target:a}.")
    deliver_messages(action)
    _satiation(player, 'water', was_thirsty, "You are no longer thirsty.",
               "You have drunk all you can.")
    if remaining is not None:
        source.db.liquid_remaining = remaining - sip


async def cmd_drink(ctx: CommandContext) -> None:
    """
    Drink from something you carry, or a fountain where you stand. Alone,
    drink from a fountain here, or the water here (a river, a well).

    Usage: drink [<container>]
    """
    name = (ctx.args or "").strip()
    room = ctx.player.location
    if not name:
        fountain = _fountain_here(room)
        if fountain is not None:
            await _drink_liquid(ctx, fountain, room=False)
            return
        if room is not None and room.has_tag('water_source'):
            await _drink_liquid(ctx, room, room=True)
            return
        if not await world_verb(ctx):
            await ctx.session.send("Drink what?")
        return
    item = find_object(ctx, name, search_room=True, search_inventory=True)
    if item is None or not item.has_tag('drink'):
        if await world_verb(ctx):
            return
        if item is None:
            await ctx.session.send(f"You don't have '{name}'.")
        else:
            await ctx.session.send("You can't drink from that.")
        return
    if _holds_liquid(item):
        await _drink_liquid(ctx, item, room=False)
        return
    charges = item.db.get('charges')
    if charges is not None and int(charges) <= 0:
        await ctx.session.send(f"{item.name} is empty.")
        return

    async def _apply(_a) -> None:
        await _restore(ctx.player, item)

    action = await _gated(ctx, ItemAction.ON_DRINK, item, "drink", _apply)
    if action is None:
        return
    action.add_message("actor", "You drink {target:a}.")
    action.add_message("room", "{actor} drinks {target:a}.")
    deliver_messages(action)
    if charges is not None:
        item.db.charges = int(charges) - 1


def _fill_parts(ctx: CommandContext, args: str) -> tuple[GameObject | None, str]:
    """The container and the source's name ("" for none): ``<container>
    from <source>``, else the whole line as the container, else its last
    word as the source."""
    if " from " in f" {args} ":
        left, _, right = args.partition(" from ")
        return find_object(ctx, left.strip(), search_room=False), right.strip()
    whole = find_object(ctx, args, search_room=False)
    if whole is not None or " " not in args:
        return whole, ""
    left, _, right = args.rpartition(" ")
    return find_object(ctx, left.strip(), search_room=False), right.strip()


async def cmd_fill(ctx: CommandContext) -> None:
    """
    Fill a container you carry from a fountain, or from the water here.

    Usage: fill <container> [<fountain>]
    """
    player = ctx.player
    args = (ctx.args or "").strip()
    container, source_name = _fill_parts(ctx, args) if args else (None, "")
    if container is None or container.db.get('liquid_held') is None:
        if await world_verb(ctx):
            return
        if not args:
            await ctx.session.send("Fill what?")
        elif container is None:
            await ctx.session.send("You don't have that.")
        else:
            await ctx.session.send("You can't fill that.")
        return
    room = player.location
    if source_name:
        source = find_object(ctx, source_name, search_room=True, search_inventory=False)
        if source is None or not source.has_tag('fountain'):
            await ctx.session.send("You can't fill it from that.")
            return
    else:
        source = _fountain_here(room)
        if source is None and room is not None and room.has_tag('water_source'):
            source = room
        if source is None:
            await ctx.session.send("There is nothing here to fill it from.")
            return
    held = int(container.db.get('liquid_held') or 0)
    remaining = int(container.db.get('liquid_remaining') or 0)
    if remaining >= held:
        await ctx.session.send(f"{container.name} is already full.")
        return
    liquid = _liquid(source)
    if remaining > 0 and str(container.db.get('liquid') or 'water') != liquid:
        await ctx.session.send("There is already another liquid in it.")
        return
    container.db.liquid = liquid
    container.db.liquid_remaining = held
    where = "here" if source is room else "from {tool:a}"
    action = Action(actor=player, target=container, action_type="items:fill",
                    tool=None if source is room else source)
    action.add_message("actor", "You fill {target:a} " + where + ".")
    action.add_message("room", "{actor} fills {target:a} " + where + ".")
    deliver_messages(action)


__all__ = ["DEFAULT_SIP", "cmd_eat", "cmd_drink", "cmd_fill", "world_verb"]
