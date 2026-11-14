"""
Modification OLC commands for REALM.

Commands for modifying existing objects.
"""

from __future__ import annotations

import json

from realm.commands import CommandContext
from realm.commands.base import (
    find_object_global,
    require_control,
    resolve_target,
    run_op,
    save_object,
)
from realm.core import ops
from realm.core.attrflags import VALID_FLAGS, attr_flags, set_attr_flags
from realm.core.safe_eval import validate_code
from realm.core.world import setting
from realm.permissions.locks import LockType
from realm.persistence.keyid import KEYID_ATTR
from realm.std.look.describe import DETAILS_ATTR


async def cmd_desc(ctx: CommandContext) -> None:
    """
    Set an object's description.

    Usage: @desc <object> = <description>
           @desc here = <description>
           @desc me = <description>

    Use multi-line by ending with \\ and continuing on next line.

    Example:
        @desc here = Salt-bleached steps spiral up the cliff face.
    """
    if not ctx.left_args:
        await ctx.session.send("Usage: @desc <object> = <description>")
        return

    target_name = ctx.left_args.strip()
    description = ctx.right_args if ctx.right_args else ""

    # Find target
    target = resolve_target(ctx, target_name)
    if not target:
        await ctx.session.send(f"Object '{target_name}' not found.")
        return

    if await run_op(ctx, ops.describe, target, description) is None:
        return
    if description:
        await ctx.session.send(f"Description set for {target.name}.")
    else:
        await ctx.session.send(f"Description cleared for {target.name}.")


async def cmd_name(ctx: CommandContext) -> None:
    """
    Rename an object.

    Usage: @name <object> = <new name>

    Example:
        @name rock = moon rock
    """
    if not ctx.left_args or not ctx.right_args:
        await ctx.session.send("Usage: @name <object> = <new name>")
        return

    target_name = ctx.left_args.strip()
    new_name = ctx.right_args.strip()

    # Find target
    target = resolve_target(ctx, target_name)
    if not target:
        await ctx.session.send(f"Object '{target_name}' not found.")
        return

    result = await run_op(ctx, ops.rename, target, new_name)
    if result is None:
        return
    await ctx.session.send(f"Renamed '{result.value}' to '{target.name}'.")


async def cmd_keyid(ctx: CommandContext) -> None:
    """
    Give an object a unique, friendly handle — a *keyid* — so scripts can
    reference it as ``get('$<keyid>')`` instead of a collision-prone name or
    an opaque id. Ideal for well-known singletons (a bank core, a weather
    master). The uuid stays the canonical id; a keyid is an optional, stable,
    globally-unique alias on top of it, and only one object may hold a given
    keyid at a time.

    Usage: @keyid <object>              (show the current keyid)
           @keyid <object> = <keyid>    (set — refused if another object holds it)
           @keyid <object> =            (clear)

    Example:
        @keyid BankNet Core = banknet_core
        @eval get('$banknet_core')
    """

    spec = (ctx.left_args or "").strip()
    if not spec:
        await ctx.session.send("Usage: @keyid <object> [= <keyid>]")
        return
    target = resolve_target(ctx, spec)
    if not target:
        await ctx.session.send(f"Object '{spec}' not found.")
        return
    if not await require_control(ctx, target):
        return

    sigil = setting("KEYID_SIGIL")
    persistence = ctx.persistence

    # No '=' anywhere → show the current keyid.
    if '=' not in (ctx.args or ""):
        current = target.db.get(KEYID_ATTR)
        if current:
            await ctx.session.send(f"{target.name} keyid: {sigil}{current}")
        else:
            await ctx.session.send(
                f"{target.name} has no keyid. Give it one with "
                f"'@keyid {spec} = <handle>'.")
        return

    new = (ctx.right_args or "").strip()

    # '=' with an empty value → clear.
    if not new:
        result = await run_op(ctx, ops.clear_keyid, target, persistence)
        if result is not None:
            await ctx.session.send(f"Cleared {target.name}'s keyid ('{result.value}').")
        return

    # Set — validate the handle, then claim it (conflict, never merge).
    if await run_op(ctx, ops.set_keyid, target, new, persistence) is None:
        return
    await ctx.session.send(f"{target.name} is now reachable as {sigil}{new}.")


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
    target = resolve_target(ctx, target_name)
    if not target:
        await ctx.session.send(f"Object '{target_name}' not found.")
        return

    if ctx.right_args:
        value = _parse_value(ctx.right_args)
        if await run_op(ctx, ops.set_attr, target, attr_name, value) is None:
            return
        await ctx.session.send(f"Set {target.name}/{attr_name} = {value!r}")
    else:
        if await run_op(ctx, ops.del_attr, target, attr_name) is None:
            return
        await ctx.session.send(f"Cleared {target.name}/{attr_name}")


async def cmd_wipe(ctx: CommandContext) -> None:
    """
    Clear all attributes from an object.

    Usage: @wipe <object>

    Example:
        @wipe scratch pad      (safe-flagged attributes survive)
    """
    if not ctx.args:
        await ctx.session.send("Usage: @wipe <object>")
        return

    target = resolve_target(ctx, ctx.args.strip())
    if not target:
        await ctx.session.send(f"Object '{ctx.args}' not found.")
        return

    if not await require_control(ctx, target):
        return

    # Delete every attribute the del_attr op allows: safe attrs always
    # survive, system attrs survive unless the wiper is admin+ (so a
    # builder's @wipe can't strip a character's stats), protected ones stay.
    count = 0
    for key in list(target.db.all()):
        try:
            result = ops.del_attr(ctx.player, target, key)
        except ops.OpError:
            continue
        count += bool(result.value)

    await save_object(ctx, target)
    await ctx.session.send(f"Wiped {count} attribute(s) from {target.name}.")


async def cmd_parent(ctx: CommandContext) -> None:
    """
    Set an object's parent — the child inherits the template's db
    attributes (defaults, ON_* hooks, $-commands) wherever it lacks its
    own. Child's own attribute shadows the template's; writes land on
    the child; tags/behaviors/fields never inherit. You must control
    BOTH objects. See docs/design/templates.md.

    Usage: @parent <object> = <parent>
           @parent <object> =             (clear parent)

    Example:
        @parent red apple = apple template
    """
    if not ctx.left_args:
        await ctx.session.send("Usage: @parent <object> = <parent>")
        return

    target_name = ctx.left_args.strip()
    parent_name = ctx.right_args.strip() if ctx.right_args else ""

    # Find target
    target = resolve_target(ctx, target_name)
    if not target:
        await ctx.session.send(f"Object '{target_name}' not found.")
        return

    if not await require_control(ctx, target):
        return

    if parent_name:
        # Find parent
        parent = find_object_global(ctx, parent_name)
        if not parent:
            await ctx.session.send(f"Parent '{parent_name}' not found.")
            return

        # Adopting a template runs its code with YOUR object's authority,
        # so you must control the template too. (A Penn-style @lock/parent
        # opt-in for shared templates is backlogged.)
        if not await require_control(ctx, parent):
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

    await save_object(ctx, target)


async def cmd_tag(ctx: CommandContext) -> None:
    """
    Add a tag to an object.

    Usage: @tag <object> = <tag>

    Examples:
        @tag chest = container
        @tag npc = zone:tavern
    """
    if not ctx.left_args or not ctx.right_args:
        await ctx.session.send("Usage: @tag <object> = <tag>")
        return

    target_name = ctx.left_args.strip()
    tag = ctx.right_args.strip().lower()

    # Find target
    target = resolve_target(ctx, target_name)
    if not target:
        await ctx.session.send(f"Object '{target_name}' not found.")
        return

    result = await run_op(ctx, ops.tag, target, tag)
    if result is None:
        return
    if not result.value:
        await ctx.session.send(f"{target.name} already has tag '{tag}'.")
        return
    await ctx.session.send(f"Added tag '{tag}' to {target.name}.")


async def cmd_untag(ctx: CommandContext) -> None:
    """
    Remove a tag from an object.

    Usage: @untag <object> = <tag>

    Example:
        @untag rat = hostile
    """
    if not ctx.left_args or not ctx.right_args:
        await ctx.session.send("Usage: @untag <object> = <tag>")
        return

    target_name = ctx.left_args.strip()
    tag = ctx.right_args.strip().lower()

    # Find target
    target = resolve_target(ctx, target_name)
    if not target:
        await ctx.session.send(f"Object '{target_name}' not found.")
        return

    result = await run_op(ctx, ops.untag, target, tag)
    if result is None:
        return
    if not result.value:
        await ctx.session.send(f"{target.name} doesn't have tag '{tag}'.")
        return
    await ctx.session.send(f"Removed tag '{tag}' from {target.name}.")


async def cmd_lock(ctx: CommandContext) -> None:
    """
    Set a lock on an object.

    Usage: @lock <object> = <lock expression>
           @lock/<type> <object> = <lock expression>

    Without a type, sets the 'basic' lock (pick up / traverse).
    Types: basic, enter, use, control, zone, speech, teleport, examine,
    give, drop, command, listen, page, mail.

    The 'examine' lock hides the DETAIL sections of examine/look (detail
    lines, visual attributes, tags) from viewers who fail it; the name
    and base description always show. Open by default:
        @lock/examine relic = caller.has_tag('scholar')

    Lock expressions are Python boolean expressions with access to:
    - caller: The object trying to pass the lock
    - target: The object with the lock (self)
    - owner: The lock owner

    Examples:
        @lock door = caller.has_tag('key_holder')
        @lock/enter room = caller.db.level >= 10
        @lock chest = caller == target.owner
    """

    if not ctx.left_args:
        await ctx.session.send("Usage: @lock[/<type>] <object> = <expression>")
        return

    lock_type = ctx.switches[0].lower() if ctx.switches else LockType.BASIC
    target_name = ctx.left_args.strip()
    lock_expr = ctx.right_args if ctx.right_args else ""

    target = resolve_target(ctx, target_name)
    if not target:
        await ctx.session.send(f"Object '{target_name}' not found.")
        return

    if lock_expr:
        # Validated at write time, so a builder learns about a bad expression
        # now, not from a lock that silently never passes.
        if await run_op(ctx, ops.set_lock, target, lock_type, lock_expr) is None:
            return
        await ctx.session.send(f"Lock/{lock_type} set on {target.name}.")
        return
    result = await run_op(ctx, ops.clear_lock, target, lock_type)
    if result is None:
        return
    if result.value:
        await ctx.session.send(f"Lock/{lock_type} cleared from {target.name}.")
    else:
        await ctx.session.send(f"{target.name} has no {lock_type} lock.")


async def cmd_unlock(ctx: CommandContext) -> None:
    """
    Remove all locks from an object.

    Usage: @unlock <object>

    Example:
        @unlock old door
    """
    if not ctx.args:
        await ctx.session.send("Usage: @unlock <object>")
        return

    target = resolve_target(ctx, ctx.args.strip())
    if not target:
        await ctx.session.send(f"Object '{ctx.args}' not found.")
        return

    result = await run_op(ctx, ops.clear_lock, target)
    if result is None:
        return
    await ctx.session.send(f"Removed {result.value} lock(s) from {target.name}.")


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


async def cmd_detail(ctx: CommandContext) -> None:
    """
    Add a per-viewer conditional description line.

    Usage: @detail <object> = <condition> -> <text>
           @detail <object> = <text>            (shown to everyone)
           @detail <object>                     (list, numbered)
           @detail/remove <object> = <n>        (remove one by number)
           @detail/clear <object>

    Conditions are safe expressions over the VIEWER:
    skill('observation'), check('observation', -2), has_tag('ghost'),
    viewer. Example:

        @detail here = check('observation', -2) -> You notice a
            small hole in the wall.
    """

    if not ctx.left_args:
        await ctx.session.send("Usage: @detail <object> = [<condition> ->] <text>")
        return

    target = resolve_target(ctx, ctx.left_args.strip())
    if not target:
        await ctx.session.send(f"Object '{ctx.left_args.strip()}' not found.")
        return

    if not await require_control(ctx, target):
        return

    if ctx.switches and ctx.switches[0].lower() == 'clear':
        target.db.delete(DETAILS_ATTR)
        await save_object(ctx, target)
        await ctx.session.send(f"Details cleared from {target.name}.")
        return

    if ctx.switches and ctx.switches[0].lower() in ('remove', 'del'):
        extras = list(target.db.get(DETAILS_ATTR) or [])
        try:
            idx = int((ctx.right_args or ctx.args or "").strip())
        except ValueError:
            await ctx.session.send("Usage: @detail/remove <object> = <number>")
            return
        if not (1 <= idx <= len(extras)):
            await ctx.session.send(
                f"No detail #{idx} (there are {len(extras)}). "
                f"'@detail {target.name}' lists them.")
            return
        removed = extras.pop(idx - 1)
        op = (ops.set_attr, target, DETAILS_ATTR, extras) if extras else (
            ops.del_attr, target, DETAILS_ATTR)
        if await run_op(ctx, *op) is None:
            return
        await ctx.session.send(f"Removed detail #{idx}: {removed[1]}")
        return

    if not ctx.right_args:
        extras = target.db.get(DETAILS_ATTR) or []
        if not extras:
            await ctx.session.send(f"{target.name} has no details.")
            return
        lines = [f"Details on {target.name}:"]
        for i, entry in enumerate(extras, 1):
            cond = entry[0] or "(always)"
            lines.append(f"  {i}. [{cond}] {entry[1]}")
        await ctx.session.send("\n".join(lines))
        return

    spec = ctx.right_args.strip()
    if '->' in spec:
        condition, text = spec.split('->', 1)
        condition, text = condition.strip(), text.strip()
        errors = validate_code(condition, mode='eval')
        if errors:
            await ctx.session.send(f"Bad condition: {'; '.join(errors)}")
            return
    else:
        condition, text = "", spec

    extras = list(target.db.get(DETAILS_ATTR) or [])
    extras.append([condition, text])
    if await run_op(ctx, ops.set_attr, target, DETAILS_ATTR, extras) is None:
        return
    await ctx.session.send(
        f"Detail added to {target.name}"
        f"{f' (when {condition})' if condition else ''}.")


async def cmd_attr(ctx: CommandContext) -> None:
    """
    Flag attributes: secret (controllers-only read), visual (shown on
    examine), safe (writes refused for everyone), system (writes refused
    below admin+ — stats are stamped this at creation), no_clone (skipped
    by @clone), public (callable AS this object via call() by
    non-controllers).

    Usage: @attr <object>/<attribute> = <flag>[, <flag>...]
           @attr <object>/<attribute> = !<flag>     (remove a flag)
           @attr <object>/<attribute> =             (clear all flags)
           @attr <object>                           (list flagged attrs)

    Example:
        @attr vault/gm_notes = secret
        @attr shrine/on_pray = safe
        @attr vault/gm_notes = !secret
    """

    if not ctx.left_args:
        await ctx.session.send("Usage: @attr <object>[/<attribute>] [= flags]")
        return

    spec = ctx.left_args.strip()
    obj_spec, _, attr_name = spec.partition('/')
    target = resolve_target(ctx, obj_spec.strip())
    if not target:
        await ctx.session.send(f"Object '{obj_spec.strip()}' not found.")
        return

    if not attr_name:
        table = target.db.get('attr_flags') or {}
        if not table:
            await ctx.session.send(f"{target.name} has no flagged attributes.")
            return
        lines = [f"Attribute flags on {target.name}:"]
        for name in sorted(table):
            lines.append(f"  {name}: {', '.join(table[name])}")
        await ctx.session.send("\n".join(lines))
        return

    if not await require_control(ctx, target):
        return

    attr_name = attr_name.strip()
    current = attr_flags(target, attr_name)
    if ctx.right_args is None or not ctx.right_args.strip():
        set_attr_flags(target, attr_name, [])
        await save_object(ctx, target)
        await ctx.session.send(f"Flags cleared from {target.name}/{attr_name}.")
        return

    for token in (t.strip().lower() for t in ctx.right_args.split(',')):
        removing = token.startswith('!')
        flag = token.lstrip('!')
        if flag not in VALID_FLAGS:
            await ctx.session.send(
                f"Unknown flag '{flag}'. Valid: {', '.join(VALID_FLAGS)}")
            return
        (current.discard if removing else current.add)(flag)
    set_attr_flags(target, attr_name, sorted(current))
    await save_object(ctx, target)
    await ctx.session.send(
        f"{target.name}/{attr_name}: {', '.join(sorted(current)) or 'no flags'}.")


