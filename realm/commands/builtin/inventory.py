"""
Inventory and item commands for REALM.

Handles getting, dropping, and managing items.
"""

from __future__ import annotations

from realm.commands import CommandContext, CommandDispatcher
from realm.commands.base import find_object, find_player, format_list
from realm.core.language import numbered_name
from realm.core.objects import GameObject
from realm.core.propagation import Action, deliver_messages, gate_action
from realm.core.render import group_contents


def _summarize(items: list[GameObject]) -> str:
    """Grouped, articled phrasing for bulk results: "2 apples and a sword"."""
    return format_list(
        [numbered_name(rep, count) for rep, count in group_contents(items)],
        conjunction="and",
    )


async def _gate_item_action(
    actor: GameObject,
    action_type: str,
    target: GameObject,
    *,
    tool: GameObject | None = None,
    extra: dict | None = None,
    fail_msg: str,
) -> Action | None:
    """
    Run an item action's permission pass through propagation.

    Locks (via the check-pass lock guard) and behaviors both get a chance
    to block. Returns the action on success, None on a block (the actor
    has been messaged). Every item transfer — single or bulk — goes
    through this one gate.
    """
    action = Action(
        actor=actor,
        target=target,
        action_type=action_type,
        tool=tool,
        extra=extra or {},
    )
    if not await gate_action(action, fail_msg=fail_msg):
        return None
    return action


async def cmd_inventory(ctx: CommandContext) -> None:
    """
    Show your inventory.

    Usage: inventory
           i
           inv
    """
    if not ctx.player:
        return

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
    """
    if not ctx.player:
        return

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

    # Check if it's gettable (has 'thing' tag or similar)
    if target.has_tag('player'):
        await ctx.session.send("You can't pick up players!")
        return

    # Locks and behaviors can both block (locked-down item, cursed item
    # glued to the floor, weight limits); observers can react either way.
    action = await _gate_item_action(
        ctx.player, "item:on_get", target,
        fail_msg=f"You can't pick up {target.name}.",
    )
    if action is None:
        return

    # Mutate state
    target.location = ctx.player

    # Bake in success messages and deliver everything (including any behavior
    # messages added during the propagation passes).
    action.add_message("actor", "You pick up {target:a}.")
    action.add_message("room", "{actor} picks up {target:a}.")
    deliver_messages(action)


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
        action = await _gate_item_action(
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
    """
    if not ctx.player:
        return

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

    action = await _gate_item_action(
        ctx.player, "item:on_drop", target,
        fail_msg=f"You can't drop {target.name}.",
    )
    if action is None:
        return

    target.location = ctx.player.location

    action.add_message("actor", "You drop {target:a}.")
    action.add_message("room", "{actor} drops {target:a}.")
    deliver_messages(action)


async def _drop_all(ctx: CommandContext) -> None:
    """Drop all items in inventory."""
    items = [obj for obj in ctx.player.contents if not obj.has_tag('exit')]

    if not items:
        await ctx.session.send("You aren't carrying anything.")
        return

    dropped = []
    for item in items:
        # Same gate as single-item drop: locks and behaviors apply per item.
        action = await _gate_item_action(
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
    """
    if not ctx.player:
        return

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

    if target == ctx.player:
        await ctx.session.send("Give it to yourself? That doesn't make sense.")
        return

    # For 'give', the target is the recipient and the item travels via extra.
    # The 'tool' field carries the item so {tool} substitution works in
    # messages and the actor-side give-lock check can find it.
    action = await _gate_item_action(
        ctx.player, "item:on_give", target,
        tool=item,
        extra={"item": item},
        fail_msg=f"You can't give {item.name} to {target.name}.",
    )
    if action is None:
        return

    item.location = target

    action.add_message("actor", "You give {tool:a} to {target}.")
    action.add_message("target", "{actor} gives you {tool:a}.")
    action.add_message("room", "{actor} gives {tool:a} to {target}.")
    deliver_messages(action)


async def cmd_put(ctx: CommandContext) -> None:
    """
    Put an object in a container.

    Usage: put <object> in <container>
    """
    if not ctx.player:
        return

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

    # For 'put', the target is the container and the item travels via tool/extra.
    action = await _gate_item_action(
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

    dispatcher.register(
        "inventory",
        cmd_inventory,
        aliases=["i", "inv"],
        help_text="Show your inventory",
    )

    dispatcher.register(
        "get",
        cmd_get,
        aliases=["take", "grab"],
        help_text="Pick up an object",
        usage="get <object> [from <container>]",
    )

    dispatcher.register(
        "drop",
        cmd_drop,
        help_text="Drop an object",
        usage="drop <object>",
    )

    dispatcher.register(
        "give",
        cmd_give,
        help_text="Give an object to someone",
        usage="give <object> to <player>",
        parse_equals=True,
    )

    dispatcher.register(
        "put",
        cmd_put,
        aliases=["place"],
        help_text="Put an object in a container",
        usage="put <object> in <container>",
    )
