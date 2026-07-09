"""
Inventory and item commands for REALM.

Handles getting, dropping, and managing items.
"""

from __future__ import annotations

from realm.commands import CommandContext, CommandDispatcher
from realm.commands.base import find_object, find_player, format_list
from realm.core.language import numbered_name
from realm.core.objects import GameObject
from realm.core.propagation import deliver_messages
from realm.core.render import group_contents
from realm.core.verbs import do_drop, do_get, do_give, gate_item_action


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
    items = [obj for obj in ctx.player.contents if not obj.has_tag('exit')]

    if not items:
        await ctx.session.send("You aren't carrying anything.")
        return

    await ctx.session.send("\nYou are carrying:")
    for item in items:
        await ctx.session.send(f"  {item.name}")
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
    # and messages all live in realm.core.verbs.do_get).
    await do_get(ctx.player, target)


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

    items = [
        obj for obj in source.contents
        if not obj.has_tag('player') and not obj.has_tag('exit') and obj != ctx.player
    ]

    if not items:
        await ctx.session.send(f"There's nothing to get {source_name}.")
        return

    gotten = []
    for item in items:
        # Same gate as single-item get: locks and behaviors apply per item.
        action = await gate_item_action(
            ctx.player, "item:on_get", item,
            fail_msg=f"You can't pick up {item.name}.",
        )
        if action is None:
            continue
        item.location = ctx.player
        deliver_messages(action)
        gotten.append(item)

    if gotten:
        await ctx.session.send(f"You pick up {_summarize(gotten)}.")


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
    items = [obj for obj in ctx.player.contents if not obj.has_tag('exit')]

    if not items:
        await ctx.session.send("You aren't carrying anything.")
        return

    dropped = []
    for item in items:
        # Same gate as single-item drop: locks and behaviors apply per item.
        action = await gate_item_action(
            ctx.player, "item:on_drop", item,
            fail_msg=f"You can't drop {item.name}.",
        )
        if action is None:
            continue
        item.location = ctx.player.location
        deliver_messages(action)
        dropped.append(item)

    if dropped:
        await ctx.session.send(f"You drop {_summarize(dropped)}.")


async def cmd_give(ctx: CommandContext) -> None:
    """
    Give an object to someone.

    Usage: give <object> to <player>
           give <object> = <player>

    Example:
        give medkit to Alice
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

    # Find the target player
    target = find_player(ctx, target_name)
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
    action = await gate_item_action(
        ctx.player, "item:on_put", container,
        tool=item,
        extra={"item": item},
        fail_msg=f"You can't put {item.name} in {container.name}.",
    )
    if action is None:
        return

    item.location = container

    action.add_message("actor", "You put {tool:a} in {target:the}.")
    action.add_message("room", "{actor} puts {tool:a} in {target:the}.")
    deliver_messages(action)


def register_inventory_commands(dispatcher: CommandDispatcher) -> None:
    """Register inventory commands with the dispatcher."""
    from functools import partial
    register = partial(dispatcher.register, category="items")

    register(
        "inventory",
        cmd_inventory,
        aliases=["i", "inv"],
        help_text="Show your inventory",
    )

    register(
        "get",
        cmd_get,
        aliases=["take", "grab"],
        help_text="Pick up an object",
        usage="get <object> [from <container>]",
    )

    register(
        "drop",
        cmd_drop,
        help_text="Drop an object",
        usage="drop <object>",
    )

    register(
        "give",
        cmd_give,
        help_text="Give an object to someone",
        usage="give <object> to <player>",
        parse_equals=True,
    )

    register(
        "put",
        cmd_put,
        aliases=["place"],
        help_text="Put an object in a container",
        usage="put <object> in <container>",
    )
