"""
``@edit`` (MUD_PLAN 10.2): an attribute or a description in the line editor
(``realm.gateway.editor``). Saving goes through the same ops as ``@set``
and ``@desc``: the same control and attribute-flag checks, and a softcode
attribute that will not run is saved with ``@set``'s warning, the editor
staying open to fix it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.commands.base import resolve_target, run_op
from realm.core import ops
from realm.gateway.editor import open_editor

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject


async def edit_description(ctx: CommandContext, target: GameObject) -> None:
    """Open the editor on ``target``'s description (``@edit obj``, ``@desc obj``)."""
    try:
        ops.check_describe(ctx.player, target)
    except ops.OpError as err:
        await ctx.session.send(err.reason)
        return

    async def save(text: str) -> bool | None:
        if await run_op(ctx, ops.describe, target, text.rstrip("\n")) is None:
            return None
        await ctx.session.send(f"Description saved for {target.name}.")
        return True

    open_editor(ctx.session, target.description or "",
                title=f"the description of {target.name}", on_save=save)


async def edit_attribute(ctx: CommandContext, target: GameObject, name: str) -> None:
    """Open the editor on ``target``'s attribute ``name`` (``@edit obj/attr``)."""
    try:
        ops.check_set_attr(ctx.player, target, name)
    except ops.OpError as err:
        await ctx.session.send(err.reason)
        return
    current = target.db.get(name)
    if current is not None and not isinstance(current, str):
        await ctx.session.send(
            f"{target.name}/{name} holds {type(current).__name__} {current!r}, not text; "
            f"change it with @set.")
        return

    async def save(text: str) -> bool | None:
        text = text.rstrip("\n")
        if not text:
            if await run_op(ctx, ops.del_attr, target, name) is None:
                return None
            await ctx.session.send(f"Cleared {target.name}/{name}.")
            return True
        result = await run_op(ctx, ops.set_attr, target, name, text)
        if result is None:
            return None
        if result.warnings:
            await ctx.session.send("Saved, but it will not run as it is. Fix it and .s "
                                   "again, or .q to leave it.")
            return False
        await ctx.session.send(f"Saved {target.name}/{name}.")
        return True

    open_editor(ctx.session, current or "", title=f"{target.name}/{name}", on_save=save)


async def cmd_edit(ctx: CommandContext) -> None:
    """
    Edit an attribute, or a description, a line at a time.

    Usage: @edit <object>/<attribute>
           @edit <object>              (its description)

    Every line you type is added; .l lists the text, .d N deletes line N,
    .i N text inserts before line N, .r N text replaces line N, .s saves,
    .q quits without saving, .h helps. Lines keep their indentation, so
    softcode is written as it reads; it is checked on save as @set checks
    it.

    Example:
        @edit here
        @edit fountain/CMD_DRINK
    """
    spec = (ctx.args or "").strip()
    if not spec:
        await ctx.session.send("Usage: @edit <object>[/<attribute>]")
        return
    target_name, _, attr = spec.partition("/")
    target = resolve_target(ctx, target_name.strip())
    if target is None:
        await ctx.session.send(f"Object '{target_name.strip()}' not found.")
        return
    if "/" in spec:
        if not attr.strip():
            await ctx.session.send("Attribute name required.")
            return
        await edit_attribute(ctx, target, attr.strip())
    else:
        await edit_description(ctx, target)


__all__ = ["edit_description", "edit_attribute", "cmd_edit"]
