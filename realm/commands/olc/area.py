"""
Builder area commands: @export, @import (plan), @import/apply, @areas.

Areas are zones exported to files under ``data/areas/`` — a sandbox
(names only, never paths, no escape). Import is a Terraform-style
two step: ``@import <name>`` shows a PLAN (a dry-run diff), then
``@import/apply <name>`` executes it. Matching is by stable id, gated
by controls() on every touched object; orphans are reported, never
auto-deleted.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from realm.commands import CommandContext, CommandDispatcher
from realm.persistence.worldio import (
    apply_plan,
    diff_plan,
    export_zone,
)

_SAFE_NAME = re.compile(r'^[A-Za-z0-9_-]+$')


def _areas_dir() -> Path:
    """The sandboxed area directory (created on demand)."""
    from realm.persistence.manager import get_active_manager
    manager = get_active_manager()
    root = Path(manager.db_path).parent if manager else Path("data")
    areas = root / "areas"
    areas.mkdir(parents=True, exist_ok=True)
    return areas


def _area_path(name: str) -> Path | None:
    """Resolve a bare area name to a file inside the sandbox, or None."""
    if not _SAFE_NAME.match(name):
        return None
    return _areas_dir() / f"{name}.realm"


async def cmd_areas(ctx: CommandContext) -> None:
    """
    List importable area files.

    Usage: @areas

    Example:
        @areas
    """
    files = sorted(p.stem for p in _areas_dir().glob("*.realm"))
    if not files:
        await ctx.session.send("No area files in data/areas/.")
        return
    await ctx.session.send("Areas: " + ", ".join(files))


async def cmd_export(ctx: CommandContext) -> None:
    """
    Export a zone to data/areas/<name>.realm (rooms, their contents,
    and masters). Re-export after editing to update the file.

    Usage: @export <zone>

    Example:
        @export castle
    """
    if not ctx.args:
        await ctx.session.send("Usage: @export <zone>")
        return
    zone = ctx.args.strip().lower().replace(' ', '_')
    path = _area_path(zone)
    if path is None:
        await ctx.session.send("Area names may use letters, digits, - and _ only.")
        return

    data = export_zone(zone)
    if not data['objects']:
        await ctx.session.send(
            f"Zone '{zone}' has no rooms — tag some with @zone here = {zone}.")
        return
    path.write_text(json.dumps(data, indent=2))
    await ctx.session.send(
        f"Exported {len(data['objects'])} objects to areas/{zone}.realm.")


async def cmd_import(ctx: CommandContext) -> None:
    """
    Import an area — a PLAN by default, /apply to execute. Objects are
    matched by stable id and synced in place; you must control every
    object the plan would change. Orphans (in-world, not in file) are
    reported but never deleted. @tel to the area once imported.

    Usage: @import <name>          (dry-run: show the plan)
           @import/apply <name>    (execute the plan)

    Example:
        @import castle
        @import/apply castle
    """
    if not ctx.args:
        await ctx.session.send("Usage: @import[/apply] <name>")
        return
    name = ctx.args.strip().lower().replace(' ', '_')
    path = _area_path(name)
    if path is None or not path.exists():
        await ctx.session.send(f"No area file 'areas/{name}.realm'.")
        return

    data = json.loads(path.read_text())
    persistence = ctx.dispatcher.persistence if ctx.dispatcher else None
    try:
        plan = diff_plan(data, name, persistence, actor=ctx.player)
    except ValueError as e:
        await ctx.session.send(str(e))
        return

    applying = bool(ctx.switches and ctx.switches[0].lower() == 'apply')
    if not applying:
        await ctx.session.send(plan.render())
        if not plan.is_empty() and not plan.conflict:
            await ctx.session.send(f"Run @import/apply {name} to execute.")
        return

    if plan.conflict:
        await ctx.session.send(plan.render())
        await ctx.session.send("Resolve conflicts before applying.")
        return
    if plan.is_empty():
        await ctx.session.send("Nothing to apply — the area matches the file.")
        return

    summary = await apply_plan(data, plan, persistence)
    await ctx.session.send(
        f"Applied: {summary['created']} created, {summary['updated']} updated, "
        f"{summary['orphaned']} orphaned (left in place). @tel {name} to visit.")


def register_area_commands(dispatcher: CommandDispatcher) -> None:
    from functools import partial
    register = partial(dispatcher.register, category="building",
                       permission="builder")
    register("@areas", cmd_areas, help_text="List importable area files",
             usage="@areas")
    register("@export", cmd_export,
             help_text="Export a zone to an area file",
             usage="@export <zone>")
    register("@import", cmd_import,
             help_text="Import an area (plan; /apply to execute)",
             usage="@import[/apply] <name>")
