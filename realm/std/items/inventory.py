"""
Inventory and item commands for REALM.

Handles getting, dropping, and managing items.
"""

from __future__ import annotations

from realm.commands import CommandContext
from realm.commands.base import find_object, find_player, format_list
from realm.core.language import group_contents, numbered_name
from realm.core.objects import GameObject
from realm.core.propagation import deliver_messages
from realm.core.world import find_world, get_world
from realm.std.items.actions import ItemAction
from realm.std.items.verbs import do_drop, do_get, do_give, gate_item_action


def _summarize(items: list[GameObject]) -> str:
    """Grouped, articled phrasing for bulk results: "2 apples and a sword"."""
    return format_list(
        [numbered_name(rep, count) for rep, count in group_contents(items)],
        conjunction="and",
    )


async def cmd_inventory(ctx: CommandContext) -> None:
    """
    Show your inventory.

    Usage: inventory
           i
           inv
    """
    # What is worn or wielded is listed by `equipment`, not here.
    items = [obj for obj in ctx.player.contents if not obj.is_exit
             and not obj.has_tag('worn') and not obj.has_tag('wielded')]
    # Money is a balance, not an object — the economy feature keeps it and
    # the active GameSystem names it (credits / gold / shillings), so shops
    # and inventory always agree. No economy, no purse line.
    economy = get_world().services.get("economy")
    purse = (f"You have {economy.get_credits(ctx.player)} {economy.currency_name()}."
             if economy is not None else None)

    if not items:
        await ctx.session.send("You aren't carrying anything.")
        if purse:
            await ctx.session.send(purse)
        return

    await ctx.session.send("\nYou are carrying:")
    for item in items:
        await ctx.session.send(f"  {item.name}")
    if purse:
        await ctx.session.send(purse)
    await ctx.session.send("")


async def cmd_get(ctx: CommandContext) -> None:
    """
    Pick up an object.

    Usage: get <object>
           get <object> from <container>

    Example:
        get coin
        get key from chest
    """
    if not ctx.args:
        await ctx.session.send("Get what?")
        return

    # Check for "from" syntax
    args = ctx.args
    from_container = None

    if ' from ' in args.lower():
        parts = args.lower().split(' from ', 1)
        item_name = ctx.args[:len(parts[0])]
        container_name = ctx.args[len(parts[0]) + 6:]  # Skip " from "

        from_container = find_object(ctx, container_name.strip())
        if not from_container:
            await ctx.session.send(f"You don't see '{container_name.strip()}' here.")
            return
        if from_container.has_tag('closed'):
            await ctx.session.send(f"{from_container.name} is closed.")
            return
    else:
        item_name = args

    # Handle "all"
    if item_name.lower() == 'all':
        await _get_all(ctx, from_container)
        return

    # Money is a balance, not an object: "get gold from corpse".
    if from_container is not None and item_name.strip().lower() in money_words():
        if not take_money(ctx.player, from_container):
            await ctx.session.send(f"There is no money in {from_container.name}.")
        return

    # Find the item
    if from_container:
        # Search in container
        from realm.core.search import match_one
        target = match_one(item_name, from_container.contents)
        if not target:
            await ctx.session.send(
                f"You don't see '{item_name}' in {from_container.name}."
            )
            return
    else:
        # Search in room
        target = find_object(
            ctx, item_name,
            search_room=True,
            search_inventory=False,
        )
        if not target:
            await ctx.session.send(f"You don't see '{item_name}' here.")
            return

    # One verb core for typed and scripted gets (locks, behavior gates,
    # and messages all live in realm.std.items.verbs.do_get).
    await do_get(ctx.player, target)


def _economy():
    world = find_world()
    return world.services.get("economy") if world is not None else None


def money_words() -> set[str]:
    """What ``get <word> from <container>`` takes as the money in it: the
    currency's name, ``coins`` and ``money``. None without ``economy``."""
    economy = _economy()
    if economy is None:
        return set()
    return {economy.currency_name().lower(), "coins", "coin", "money"}


def take_money(player: GameObject, source: GameObject) -> int:
    """Move the money a container (a corpse) holds to ``player``, saying so.
    Returns how much; 0 when there is none or the world has no
    ``economy``."""
    economy = _economy()
    if economy is None or source.is_player:
        return 0
    amount = economy.get_credits(source)
    if amount <= 0 or not economy.transfer_credits(source, player, amount):
        return 0
    player.msg(f"You get {amount} {economy.currency_name()} from {source.name}.")
    return amount


async def take_all(player: GameObject, source: GameObject) -> tuple[list[GameObject], int]:
    """Everything ``player`` may pick up from ``source`` (a room or a
    container), each through the same gate as a single ``get``, and from a
    container its money too. Returns what was taken and how much money."""
    items = [obj for obj in source.contents
             if not obj.is_player and not obj.is_exit and obj is not player]
    gotten = []
    for item in items:
        # Same gate as single-item get: locks and behaviors apply per item.
        def _take(_a, item=item):
            item.location = player
        action = await gate_item_action(
            player, ItemAction.ON_GET, item,
            fail_msg=f"You can't pick up {item.name}.",
            apply=_take,
        )
        if action is None:
            continue
        deliver_messages(action)
        gotten.append(item)
    if gotten:
        player.msg(f"You pick up {_summarize(gotten)}.")
    money = take_money(player, source) if source is not player.location else 0
    return gotten, money


async def _get_all(ctx: CommandContext, from_container=None) -> None:
    """Pick up all items from room or container."""
    if from_container:
        source = from_container
        source_name = from_container.name
    elif ctx.player.location:
        source = ctx.player.location
        source_name = "here"
    else:
        return
    gotten, money = await take_all(ctx.player, source)
    if not gotten and not money and not [
            obj for obj in source.contents
            if not obj.is_player and not obj.is_exit and obj != ctx.player]:
        await ctx.session.send(f"There's nothing to get {source_name}.")


async def cmd_drop(ctx: CommandContext) -> None:
    """
    Drop an object.

    Usage: drop <object>
           drop all

    Example:
        drop coin
        drop all
    """
    if not ctx.args:
        await ctx.session.send("Drop what?")
        return

    if not ctx.player.location:
        await ctx.session.send("You can't drop things here.")
        return

    item_name = ctx.args.strip()

    # Handle "all"
    if item_name.lower() == 'all':
        await _drop_all(ctx)
        return

    # Find the item in inventory
    target = find_object(
        ctx, item_name,
        search_room=False,
        search_inventory=True,
    )

    if not target:
        await ctx.session.send(f"You aren't carrying '{item_name}'.")
        return

    await do_drop(ctx.player, target)


async def _drop_all(ctx: CommandContext) -> None:
    """Drop all items in inventory."""
    items = [obj for obj in ctx.player.contents if not obj.is_exit]

    if not items:
        await ctx.session.send("You aren't carrying anything.")
        return

    dropped = []
    for item in items:
        # Same gate as single-item drop: locks and behaviors apply per item.
        def _release(_a, item=item):
            item.location = ctx.player.location
        action = await gate_item_action(
            ctx.player, ItemAction.ON_DROP, item,
            fail_msg=f"You can't drop {item.name}.",
            apply=_release,
        )
        if action is None:
            continue
        deliver_messages(action)
        dropped.append(item)

    if dropped:
        await ctx.session.send(f"You drop {_summarize(dropped)}.")


async def cmd_give(ctx: CommandContext) -> None:
    """
    Give an object to someone — a player or an NPC. The recipient's
    ON_RECEIVE softcode fires (a shopkeeper taking stock, a bribe
    pressed into a guard's hands).

    Usage: give <object> to <someone>
           give <object> = <someone>

    Example:
        give medkit to Alice
        give smoked herring to Mother Salt
    """
    # Parse arguments
    item_name = ""
    target_name = ""

    if ' to ' in ctx.args.lower():
        parts = ctx.args.lower().split(' to ', 1)
        item_name = ctx.args[:len(parts[0])].strip()
        target_name = ctx.args[len(parts[0]) + 4:].strip()
    elif ctx.left_args and ctx.right_args:
        item_name = ctx.left_args.strip()
        target_name = ctx.right_args.strip()
    else:
        await ctx.session.send("Usage: give <object> to <player>")
        return

    # Find the item
    item = find_object(
        ctx, item_name,
        search_room=False,
        search_inventory=True,
    )
    if not item:
        await ctx.session.send(f"You aren't carrying '{item_name}'.")
        return

    # Find the recipient: a player, or a visible NPC (do_give and
    # ON_RECEIVE are recipient-agnostic; only this lookup ever was not).
    target = find_player(ctx, target_name)
    if not target and ctx.player.location:
        from realm.core.perception import can_see
        from realm.core.search import match_one
        npcs = [obj for obj in ctx.player.location.contents
                if obj.is_npc and can_see(ctx.player, obj)]
        target = match_one(target_name, npcs)
    if not target:
        await ctx.session.send(f"You don't see '{target_name}' here.")
        return

    await do_give(ctx.player, item, target)


async def cmd_put(ctx: CommandContext) -> None:
    """
    Put an object in a container.

    Usage: put <object> in <container>

    Example:
        put gem in chest
    """
    if ' in ' not in ctx.args.lower():
        await ctx.session.send("Usage: put <object> in <container>")
        return

    parts = ctx.args.lower().split(' in ', 1)
    item_name = ctx.args[:len(parts[0])].strip()
    container_name = ctx.args[len(parts[0]) + 4:].strip()

    # Find the item
    item = find_object(
        ctx, item_name,
        search_room=False,
        search_inventory=True,
    )
    if not item:
        await ctx.session.send(f"You aren't carrying '{item_name}'.")
        return

    # Find the container
    container = find_object(ctx, container_name)
    if not container:
        await ctx.session.send(f"You don't see '{container_name}' here.")
        return

    if container == item:
        await ctx.session.send("You can't put something inside itself!")
        return

    if container.has_tag('closed'):
        await ctx.session.send(f"{container.name} is closed.")
        return

    # For 'put', the target is the container and the item travels via tool/extra.
    def _stow(_a):
        item.location = container

    action = await gate_item_action(
        ctx.player, ItemAction.ON_PUT, container,
        tool=item,
        extra={"item": item},
        fail_msg=f"You can't put {item.name} in {container.name}.",
        apply=_stow,
    )
    if action is None:
        return

    action.add_message("actor", "You put {tool:a} in {target:the}.")
    action.add_message("room", "{actor} puts {tool:a} in {target:the}.")
    deliver_messages(action)


