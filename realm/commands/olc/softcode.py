"""
Builder tools for live composition: @behavior, @clone, @tr.

Together with @set (script attributes) and the script_ticker behavior,
these close the MUSH softcode loop — a builder can assemble, duplicate,
and animate NPCs entirely in-game:

    @clone door guard
    @behavior guard-2 = script_ticker, interval:4
    @set guard-2/on_tick = say Move along, citizen.
    @tr guard-2/on_tick
"""

from __future__ import annotations

import json

from realm.commands import CommandContext, CommandDispatcher
from realm.commands.base import require_control, resolve_target, save_object
from realm.commands.olc.modify import _parse_value
from realm.core.attrflags import cloneable_attrs
from realm.core.behaviors import BehaviorRegistry


async def cmd_behavior(ctx: CommandContext) -> None:
    """
    Attach, detach, or list behaviors on an object.

    Usage: @behavior <object>                       (list attached)
           @behavior <object> = <id>[, key:value...]  (attach)
           @behavior/set <object> = <id>, key:value    (edit params in place)
           @behavior/remove <object> = <id>           (detach)
           @behavior/list                             (all registered ids)

    Multiple tickers are fine — give each its own attr and interval:
        @behavior bell = script_ticker, interval:2, attr:on_fast
        @behavior bell = script_ticker, interval:20, attr:on_slow

    Parameter values parse like @set values (numbers, booleans, JSON).

    Examples:
        @behavior parrot = script_ticker, interval:8
        @behavior guard = wandering, pause:5, stay_in_zone:true
        @behavior/remove guard = wandering
    """
    if ctx.switches and ctx.switches[0].lower() == 'list':
        ids = sorted(BehaviorRegistry.list_all())
        await ctx.session.send("Registered behaviors: " + ", ".join(ids))
        return

    if not ctx.left_args:
        await ctx.session.send(
            "Usage: @behavior <object> [= <behavior_id>, key:value, ...]"
        )
        return

    target = resolve_target(ctx, ctx.left_args.strip())
    if not target:
        await ctx.session.send(f"Object '{ctx.left_args.strip()}' not found.")
        return

    if ctx.right_args and not await require_control(ctx, target):
        return

    switch = ctx.switches[0].lower() if ctx.switches else ""
    removing = switch in ('remove', 'del')
    setting = switch == 'set'   # edit an attached behavior's params in place

    if not ctx.right_args:
        if removing:
            await ctx.session.send("Usage: @behavior/remove <object> = <behavior_id>")
            return
        # List attached behaviors.
        behaviors = target.get_behaviors()
        if not behaviors:
            await ctx.session.send(f"{target.name} has no behaviors.")
            return
        lines = [f"Behaviors on {target.name}:"]
        for behavior in behaviors:
            params = behavior.params
            suffix = f"  {json.dumps(params)}" if params else ""
            lines.append(f"  {behavior.behavior_id}{suffix}")
        await ctx.session.send("\n".join(lines))
        return

    # Split on commas, but a comma INSIDE a value (a taunt with a comma)
    # shouldn't start a new param — only a "key:" prefix does.
    import re as _re
    raw_segs = ctx.right_args.split(',')
    behavior_id = raw_segs[0].strip()
    param_segs: list[str] = []
    for seg in raw_segs[1:]:
        if _re.match(r'\s*\w+\s*:', seg):
            param_segs.append(seg)
        elif param_segs:
            param_segs[-1] += ',' + seg
    parts = [behavior_id, *param_segs]

    if removing:
        for behavior in target.get_behaviors():
            if behavior.behavior_id == behavior_id:
                target.remove_behavior(behavior)
                await save_object(ctx, target)
                await ctx.session.send(
                    f"Removed behavior '{behavior_id}' from {target.name}."
                )
                return
        await ctx.session.send(f"{target.name} has no '{behavior_id}' behavior.")
        return

    if BehaviorRegistry.get(behavior_id) is None:
        known = ", ".join(sorted(BehaviorRegistry.list_all()))
        await ctx.session.send(
            f"Unknown behavior '{behavior_id}'. Registered: {known}"
        )
        return

    params = {}
    for part in parts[1:]:
        if ':' not in part:
            await ctx.session.send(f"Bad parameter '{part}' — use key:value.")
            return
        key, value = part.split(':', 1)
        params[key.strip()] = _parse_value(value.strip())

    if setting:
        # Update an already-attached behavior's params (e.g. a new
        # ticker interval) without detach/reattach losing its db state.
        for behavior in target.get_behaviors():
            if behavior.behavior_id == behavior_id:
                behavior.params.update(params)
                await save_object(ctx, target)
                await ctx.session.send(
                    f"Updated '{behavior_id}' on {target.name}: "
                    f"{json.dumps(behavior.params)}.")
                return
        await ctx.session.send(
            f"{target.name} has no '{behavior_id}' to set — attach it first.")
        return

    behavior = BehaviorRegistry.create(behavior_id, **params)
    target.add_behavior(behavior)
    await save_object(ctx, target)

    suffix = f" with {json.dumps(params)}" if params else ""
    await ctx.session.send(f"Attached '{behavior_id}' to {target.name}{suffix}.")


async def cmd_clone(ctx: CommandContext) -> None:
    """
    Duplicate an object — attributes, tags, behaviors, and locks.

    Usage: @clone <object>
           @clone <object> = <new name>

    The copy appears in your location. Players and rooms can't be cloned.
    A unique @keyid handle is NOT copied (a copy can't share a unique
    identity, like a uuid) — the clone lands keyless; re-key it with @keyid
    if it should be a singleton.

    Example:
        @clone harbor rat
        @clone parrot = polly
    """
    from realm.behaviors.spawner import spawn_from_prototype

    if not ctx.player or ctx.player.location is None:
        return

    spec = (ctx.left_args or ctx.args or "").strip()
    if not spec:
        await ctx.session.send("Usage: @clone <object> [= <new name>]")
        return

    original = resolve_target(ctx, spec)
    if not original:
        await ctx.session.send(f"Object '{spec}' not found.")
        return
    if original.has_tag('player') or original.has_tag('room'):
        await ctx.session.send("You can't clone players or rooms.")
        return
    if not await require_control(ctx, original):
        return

    new_name = ctx.right_args.strip() if ctx.right_args else original.name

    # Deep-copy db attrs via JSON (they're JSON-serializable by design);
    # strip spawner bookkeeping tags so the copy isn't mistaken for a
    # tracked spawn.
    tags = [t for t in original.tags.to_list() if not t.startswith('spawned:')]
    prototype = {
        'name': new_name,
        'description': original.description,
        'tags': tags,
        'attrs': json.loads(json.dumps(cloneable_attrs(
            original.db.all(), original.db.get('attr_flags')))),
        'behaviors': [b.to_dict() for b in original.get_behaviors()],
    }
    clone = spawn_from_prototype(prototype, ctx.player.location)
    clone.locks.update(original.locks)
    clone.owner = ctx.player

    await save_object(ctx, clone)
    await ctx.session.send(f"Cloned {original.name} → {clone.name} (#{clone.id[:8]}).")


async def cmd_trigger(ctx: CommandContext) -> None:
    """
    Run the script stored in an object's attribute.

    Usage: @tr <object>/<attribute>

    The object becomes the script's executor; you are the enactor (%#).

    Example:
        @set parrot/battle_cry = say To arms!
        @tr parrot/battle_cry
    """
    from realm.scripting.engine import get_script_engine

    spec = (ctx.args or "").strip()
    if '/' not in spec:
        await ctx.session.send("Usage: @tr <object>/<attribute>")
        return

    obj_spec, attr_name = spec.split('/', 1)
    obj_spec = obj_spec.strip()
    attr_name = attr_name.strip()
    if not obj_spec or not attr_name:
        await ctx.session.send("Usage: @tr <object>/<attribute>")
        return

    target = resolve_target(ctx, obj_spec)
    if not target:
        await ctx.session.send(f"Object '{obj_spec}' not found.")
        return

    from realm.permissions.locks import may_trigger
    if not may_trigger(ctx.player, target):
        await ctx.session.send(f"You don't control {target.name}.")
        return

    engine = get_script_engine()
    if engine is None:
        await ctx.session.send("Scripting is not enabled.")
        return

    fired = await engine.run_object_script(target, attr_name, enactor=ctx.player)
    if fired:
        await ctx.session.send(f"Triggered {target.name}/{attr_name}.")
    elif target.is_halted:
        await ctx.session.send(f"{target.name} is halted.")
    else:
        await ctx.session.send(f"{target.name} has no script in '{attr_name}'.")


async def cmd_force(ctx: CommandContext) -> None:
    """
    Make something you control execute a command.

    Usage: @force <target> = <command>

    Runs through the real dispatcher — the target's own permissions
    apply (an NPC can't run builder commands). Forcing a player needs
    control of them: admin, or their explicit control-lock grant
    (possession is opt-in: @lock/control me = <expression>).

    Example:
        @force imp = say Obey!
    """
    from realm.permissions.locks import controls
    from realm.server.puppet import force_command

    if not ctx.left_args or not ctx.right_args:
        await ctx.session.send("Usage: @force <target> = <command>")
        return

    target = resolve_target(ctx, ctx.left_args.strip())
    if not target:
        await ctx.session.send(f"Object '{ctx.left_args.strip()}' not found.")
        return
    if not controls(ctx.player, target):
        await ctx.session.send(f"You don't control {target.name}.")
        return

    ok = await force_command(ctx.dispatcher, target, ctx.right_args.strip(),
                             watcher=ctx.session)
    if not ok:
        await ctx.session.send("Puppet chain too deep.")


async def cmd_zone(ctx: CommandContext) -> None:
    """
    Manage zones (areas): tag rooms in, inspect membership, crown masters.

    Usage: @zone here = castle             (add room to zone)
           @zone/remove here = castle
           @zone/master <object> = castle  (make it the zone's master)
           @zone here                      (list zones + masters)
           @zone/rooms castle              (list member rooms)

    Example:
        @zone here = castle
        @zone/master Castle Brain = castle
        @zone/rooms castle
    """
    from realm.core.zones import MASTER_TAG, ZONE_PREFIX, zone_masters, zone_rooms, zone_tags

    switch = ctx.switches[0].lower() if ctx.switches else ""

    if switch == 'rooms':
        zone = (ctx.args or "").strip()
        if not zone:
            await ctx.session.send("Usage: @zone/rooms <zone>")
            return
        rooms = zone_rooms(zone)
        if not rooms:
            await ctx.session.send(f"No rooms in zone '{zone}'.")
            return
        await ctx.session.send(
            f"Zone '{zone}' ({len(rooms)} rooms): "
            + ", ".join(r.name for r in rooms[:50]))
        return

    if not ctx.left_args:
        await ctx.session.send("Usage: @zone <object> [= <zone>]")
        return
    target = resolve_target(ctx, ctx.left_args.strip())
    if not target:
        await ctx.session.send(f"Object '{ctx.left_args.strip()}' not found.")
        return

    if not ctx.right_args:
        zones = [t.split(':', 1)[1] for t in zone_tags(target)]
        masters = zone_masters(target)
        await ctx.session.send(
            f"{target.name}: zones {zones or 'none'}"
            + (f"; masters: {', '.join(m.name for m in masters)}"
               if masters else ""))
        return

    if not await require_control(ctx, target):
        return
    zone = ctx.right_args.strip().lower().replace(' ', '_')
    tag = ZONE_PREFIX + zone

    if switch in ('remove', 'del'):
        target.remove_tag(tag)
        await save_object(ctx, target)
        await ctx.session.send(f"{target.name} removed from zone '{zone}'.")
        return

    target.add_tag(tag)
    if switch == 'master':
        target.add_tag(MASTER_TAG)
    await save_object(ctx, target)
    role = "MASTER of" if switch == 'master' else "added to"
    await ctx.session.send(f"{target.name} {role} zone '{zone}'.")


def register_softcode_commands(dispatcher: CommandDispatcher) -> None:
    """Register live-composition builder commands."""
    from functools import partial
    register = partial(dispatcher.register, category="building")

    register(
        "@behavior",
        cmd_behavior,
        aliases=["@behaviors"],
        help_text="Attach, detach, or list behaviors on an object",
        usage="@behavior <object> [= <behavior_id>, key:value, ...]",
        permission="builder",
        parse_equals=True,
    )

    register(
        "@clone",
        cmd_clone,
        help_text="Duplicate an object with its attributes, tags, and behaviors",
        usage="@clone <object> [= <new name>]",
        permission="builder",
        parse_equals=True,
    )

    register(
        "@zone",
        cmd_zone,
        help_text="Manage zones: membership, masters, room lists",
        usage="@zone <object> [= <zone>]",
        permission="builder",
        parse_equals=True,
    )

    register(
        "@force",
        cmd_force,
        help_text="Make something you control execute a command",
        usage="@force <target> = <command>",
        permission="builder",
        parse_equals=True,
    )

    register(
        "@tr",
        cmd_trigger,
        aliases=["@trigger"],
        help_text="Run the script stored in an object's attribute",
        usage="@tr <object>/<attribute>",
        permission="builder",
    )
