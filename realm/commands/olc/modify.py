"""
Modification OLC commands for REALM.

Commands for modifying existing objects.
"""

from __future__ import annotations

import json

from realm.commands import CommandContext, CommandDispatcher
from realm.commands.base import find_object
from realm.commands.olc.create import _find_object_global, _persistence


async def cmd_desc(ctx: CommandContext) -> None:
    """
    Set an object's description.

    Usage: @desc <object> = <description>
           @desc here = <description>
           @desc me = <description>

    Use multi-line by ending with \\ and continuing on next line.
    """
    if not ctx.player:
        return

    if not ctx.left_args:
        await ctx.session.send("Usage: @desc <object> = <description>")
        return

    target_name = ctx.left_args.strip()
    description = ctx.right_args if ctx.right_args else ""

    # Find target
    target = _resolve_target(ctx, target_name)
    if not target:
        await ctx.session.send(f"Object '{target_name}' not found.")
        return

    # Set description
    target.description = description

    if _persistence:
        await _persistence.save(target)

    if description:
        await ctx.session.send(f"Description set for {target.name}.")
    else:
        await ctx.session.send(f"Description cleared for {target.name}.")


async def cmd_name(ctx: CommandContext) -> None:
    """
    Rename an object.

    Usage: @name <object> = <new name>
    """
    if not ctx.player:
        return

    if not ctx.left_args or not ctx.right_args:
        await ctx.session.send("Usage: @name <object> = <new name>")
        return

    target_name = ctx.left_args.strip()
    new_name = ctx.right_args.strip()

    # Find target
    target = _resolve_target(ctx, target_name)
    if not target:
        await ctx.session.send(f"Object '{target_name}' not found.")
        return

    old_name = target.name
    target.name = new_name

    if _persistence:
        await _persistence.save(target)

    await ctx.session.send(f"Renamed '{old_name}' to '{new_name}'.")


async def cmd_set(ctx: CommandContext) -> None:
    """
    Set an attribute on an object.

    Usage: @set <object>/<attribute> = <value>
           @set <object>/<attribute>           (clear attribute)

    Values are parsed as JSON if possible, otherwise stored as strings.

    Examples:
        @set sword/damage = 10
        @set chest/capacity = 100
        @set npc/dialogue = ["Hello", "Goodbye"]
        @set room/hidden = true
    """
    if not ctx.player:
        return

    if not ctx.left_args:
        await ctx.session.send("Usage: @set <object>/<attribute> = <value>")
        return

    # Parse object/attribute
    if '/' not in ctx.left_args:
        await ctx.session.send("Usage: @set <object>/<attribute> = <value>")
        return

    parts = ctx.left_args.split('/', 1)
    target_name = parts[0].strip()
    attr_name = parts[1].strip()

    if not attr_name:
        await ctx.session.send("Attribute name required.")
        return

    # Find target
    target = _resolve_target(ctx, target_name)
    if not target:
        await ctx.session.send(f"Object '{target_name}' not found.")
        return

    # Set or clear the attribute
    if ctx.right_args:
        value = _parse_value(ctx.right_args)
        target.db.set(attr_name, value)
        await ctx.session.send(f"Set {target.name}/{attr_name} = {value!r}")
    else:
        target.db.delete(attr_name)
        await ctx.session.send(f"Cleared {target.name}/{attr_name}")

    if _persistence:
        await _persistence.save(target)


async def cmd_wipe(ctx: CommandContext) -> None:
    """
    Clear all attributes from an object.

    Usage: @wipe <object>
    """
    if not ctx.player:
        return

    if not ctx.args:
        await ctx.session.send("Usage: @wipe <object>")
        return

    target = _resolve_target(ctx, ctx.args.strip())
    if not target:
        await ctx.session.send(f"Object '{ctx.args}' not found.")
        return

    # Clear all attributes
    attrs = target.db.all()
    count = len(attrs)

    for key in list(attrs.keys()):
        target.db.delete(key)

    if _persistence:
        await _persistence.save(target)

    await ctx.session.send(f"Wiped {count} attribute(s) from {target.name}.")


async def cmd_parent(ctx: CommandContext) -> None:
    """
    Set an object's parent for attribute inheritance.

    Usage: @parent <object> = <parent>
           @parent <object> =             (clear parent)
    """
    if not ctx.player:
        return

    if not ctx.left_args:
        await ctx.session.send("Usage: @parent <object> = <parent>")
        return

    target_name = ctx.left_args.strip()
    parent_name = ctx.right_args.strip() if ctx.right_args else ""

    # Find target
    target = _resolve_target(ctx, target_name)
    if not target:
        await ctx.session.send(f"Object '{target_name}' not found.")
        return

    if parent_name:
        # Find parent
        parent = _find_object_global(parent_name)
        if not parent:
            await ctx.session.send(f"Parent '{parent_name}' not found.")
            return

        # Prevent circular inheritance
        if _would_create_cycle(target, parent):
            await ctx.session.send("That would create a circular inheritance chain.")
            return

        target.parent = parent
        await ctx.session.send(f"{target.name} now inherits from {parent.name}.")
    else:
        target.parent = None
        await ctx.session.send(f"{target.name} no longer has a parent.")

    if _persistence:
        await _persistence.save(target)


async def cmd_tag(ctx: CommandContext) -> None:
    """
    Add a tag to an object.

    Usage: @tag <object> = <tag>

    Examples:
        @tag chest = container
        @tag npc = zone:tavern
    """
    if not ctx.player:
        return

    if not ctx.left_args or not ctx.right_args:
        await ctx.session.send("Usage: @tag <object> = <tag>")
        return

    target_name = ctx.left_args.strip()
    tag = ctx.right_args.strip().lower()

    # Find target
    target = _resolve_target(ctx, target_name)
    if not target:
        await ctx.session.send(f"Object '{target_name}' not found.")
        return

    if target.has_tag(tag):
        await ctx.session.send(f"{target.name} already has tag '{tag}'.")
        return

    target.add_tag(tag)

    if _persistence:
        await _persistence.save(target)

    await ctx.session.send(f"Added tag '{tag}' to {target.name}.")


async def cmd_untag(ctx: CommandContext) -> None:
    """
    Remove a tag from an object.

    Usage: @untag <object> = <tag>
    """
    if not ctx.player:
        return

    if not ctx.left_args or not ctx.right_args:
        await ctx.session.send("Usage: @untag <object> = <tag>")
        return

    target_name = ctx.left_args.strip()
    tag = ctx.right_args.strip().lower()

    # Find target
    target = _resolve_target(ctx, target_name)
    if not target:
        await ctx.session.send(f"Object '{target_name}' not found.")
        return

    if not target.has_tag(tag):
        await ctx.session.send(f"{target.name} doesn't have tag '{tag}'.")
        return

    target.remove_tag(tag)

    if _persistence:
        await _persistence.save(target)

    await ctx.session.send(f"Removed tag '{tag}' from {target.name}.")


async def cmd_lock(ctx: CommandContext) -> None:
    """
    Set a lock on an object.

    Usage: @lock <object> = <lock expression>
           @lock/<type> <object> = <lock expression>

    Lock types: default, enter, use, get, drop, give, control

    Lock expressions are Python boolean expressions with access to:
    - caller: The object trying to pass the lock
    - target: The object with the lock (self)

    Examples:
        @lock door = caller.has_tag('key_holder')
        @lock/enter room = caller.db.level >= 10
        @lock chest = caller == target.owner
    """
    if not ctx.player:
        return

    if not ctx.left_args:
        await ctx.session.send("Usage: @lock[/<type>] <object> = <expression>")
        return

    # Determine lock type from switches
    lock_type = 'default'
    if ctx.switches:
        lock_type = ctx.switches[0]

    target_name = ctx.left_args.strip()
    lock_expr = ctx.right_args if ctx.right_args else ""

    # Find target
    target = _resolve_target(ctx, target_name)
    if not target:
        await ctx.session.send(f"Object '{target_name}' not found.")
        return

    if lock_expr:
        # Set the lock
        target.locks[lock_type] = lock_expr
        await ctx.session.send(f"Lock/{lock_type} set on {target.name}.")
    else:
        # Clear the lock
        if lock_type in target.locks:
            del target.locks[lock_type]
            await ctx.session.send(f"Lock/{lock_type} cleared from {target.name}.")
        else:
            await ctx.session.send(f"{target.name} has no {lock_type} lock.")

    if _persistence:
        await _persistence.save(target)


async def cmd_unlock(ctx: CommandContext) -> None:
    """
    Remove all locks from an object.

    Usage: @unlock <object>
    """
    if not ctx.player:
        return

    if not ctx.args:
        await ctx.session.send("Usage: @unlock <object>")
        return

    target = _resolve_target(ctx, ctx.args.strip())
    if not target:
        await ctx.session.send(f"Object '{ctx.args}' not found.")
        return

    count = len(target.locks)
    target.locks.clear()

    if _persistence:
        await _persistence.save(target)

    await ctx.session.send(f"Removed {count} lock(s) from {target.name}.")


def _resolve_target(ctx: CommandContext, name: str):
    """Resolve a target by name, with special handling for 'me' and 'here'."""
    name_lower = name.lower()

    if name_lower in ('me', 'self'):
        return ctx.player
    if name_lower == 'here':
        return ctx.player.location if ctx.player else None

    # Try local first
    target = find_object(ctx, name, search_exits=True)
    if target:
        return target

    # Try global lookup
    return _find_object_global(name)


def _parse_value(value_str: str):
    """Parse a value string, attempting JSON first."""
    value_str = value_str.strip()

    # Try JSON parsing
    try:
        return json.loads(value_str)
    except json.JSONDecodeError:
        pass

    # Handle boolean strings
    if value_str.lower() == 'true':
        return True
    if value_str.lower() == 'false':
        return False
    if value_str.lower() in ('none', 'null'):
        return None

    # Try numeric
    try:
        if '.' in value_str:
            return float(value_str)
        return int(value_str)
    except ValueError:
        pass

    # Return as string
    return value_str


def _would_create_cycle(target, new_parent) -> bool:
    """Check if setting new_parent would create a circular chain."""
    visited = {target.id}
    current = new_parent

    while current is not None:
        if current.id in visited:
            return True
        visited.add(current.id)
        current = current.parent

    return False


def register_modify_commands(dispatcher: CommandDispatcher) -> None:
    """Register modification OLC commands with the dispatcher."""

    dispatcher.register(
        "@desc",
        cmd_desc,
        aliases=["@describe"],
        help_text="Set an object's description",
        usage="@desc <object> = <description>",
        permission="builder",
        parse_equals=True,
    )

    dispatcher.register(
        "@name",
        cmd_name,
        help_text="Rename an object",
        usage="@name <object> = <new name>",
        permission="builder",
        parse_equals=True,
    )

    dispatcher.register(
        "@set",
        cmd_set,
        help_text="Set an attribute on an object",
        usage="@set <object>/<attr> = <value>",
        permission="builder",
        parse_equals=True,
    )

    dispatcher.register(
        "@wipe",
        cmd_wipe,
        help_text="Clear all attributes from an object",
        usage="@wipe <object>",
        permission="builder",
    )

    dispatcher.register(
        "@parent",
        cmd_parent,
        help_text="Set an object's parent",
        usage="@parent <object> = <parent>",
        permission="builder",
        parse_equals=True,
    )

    dispatcher.register(
        "@tag",
        cmd_tag,
        help_text="Add a tag to an object",
        usage="@tag <object> = <tag>",
        permission="builder",
        parse_equals=True,
    )

    dispatcher.register(
        "@untag",
        cmd_untag,
        help_text="Remove a tag from an object",
        usage="@untag <object> = <tag>",
        permission="builder",
        parse_equals=True,
    )

    dispatcher.register(
        "@lock",
        cmd_lock,
        help_text="Set a lock on an object",
        usage="@lock[/<type>] <object> = <expression>",
        permission="builder",
        parse_equals=True,
    )

    dispatcher.register(
        "@unlock",
        cmd_unlock,
        help_text="Remove all locks from an object",
        usage="@unlock <object>",
        permission="builder",
    )
