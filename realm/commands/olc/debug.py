"""
Builder tooling: @eval, @foreach, @stats, @rolls, quell.

The introspection-and-power kit — arbitrary softcode execution, bulk
operations over world searches, live metrics, roll visibility, and
dropping to mortal perception for honest testing.
"""

from __future__ import annotations

from realm.commands import CommandContext


async def cmd_eval(ctx: CommandContext) -> None:
    """
    Run arbitrary softcode as yourself and report the result — the
    PennMUSH think<<...>> primitive. Side effects (pemit/say/force/
    set_attr...) apply; a ``result`` value is echoed back.

    Usage: @eval <code>

    Example:
        @eval [force('#' + r.id, 'move The Cellar') for r in search_world(tag='rat')]
        @eval result = len(search_world(tag='npc'))
    """
    from realm.scripting.engine import get_script_engine

    if not ctx.args:
        await ctx.session.send("Usage: @eval <code>")
        return
    engine = get_script_engine()
    if engine is None:
        await ctx.session.send("Scripting is not enabled.")
        return
    result, error = await engine.run_code(ctx.player, ctx.args)
    if error:
        await ctx.session.send(f"Eval error: {error}")
    elif result is not None:
        await ctx.session.send(f"=> {result!r}")
    else:
        await ctx.session.send("Done.")


async def cmd_reload(ctx: CommandContext) -> None:
    """
    Re-read the rules from the world. Skills and classes are data
    (``skill_def`` / ``class_def`` objects); after you @create or edit
    one, @reload re-installs the skill table so checks pick it up. (New
    classes appear at the next character creation without a reload.)

    Usage: @reload
    """
    from realm.core.defs import all_defs, def_kinds, invalidate
    from realm.permissions.entitlements import reload_role_defs
    from realm.systems import reload_rules
    invalidate()                    # every in-world definition is re-read
    reload_rules()
    problems = reload_role_defs()   # custom role_def ranks take effect immediately
    counts = ", ".join(f"{len(all_defs(kind))} {kind}" for kind in sorted(def_kinds()))
    await ctx.session.send("Rules reloaded from the world.")
    await ctx.session.send(f"Definitions: {counts}.")
    for problem in problems:
        await ctx.session.send(f"Warning: {problem}")


async def cmd_foreach(ctx: CommandContext) -> None:
    """
    Run a command for every object matching a search — bulk building.
    ``%o`` in the command is replaced by each object's #id.

    Usage: @foreach <search> = <command>
           search: name / tag:<tag> / attr:<name>

    Example:
        @foreach tag:npc = @tag %o = halt
        @foreach tag:rat = @teleport %o = The Cellar
        @foreach attr:xp_multiplier = @set %o/xp_multiplier = 1.5
    """
    from realm.core.query import find_objects

    if not ctx.left_args or not ctx.right_args:
        await ctx.session.send("Usage: @foreach <search> = <command>  (use %o for each #id)")
        return

    spec = ctx.left_args.strip()
    kwargs = {}
    if spec.startswith('tag:'):
        kwargs['tag'] = spec[4:].strip()
    elif spec.startswith('attr:'):
        kwargs['attr'] = spec[5:].strip()
    else:
        kwargs['name_like'] = spec
    matches = find_objects(limit=200, **kwargs)
    if not matches:
        await ctx.session.send(f"Nothing matched '{spec}'.")
        return

    command = ctx.right_args.strip()
    count = 0
    for obj in matches:
        line = command.replace('%o', f"#{obj.id}")
        await ctx.dispatcher.dispatch(ctx.session, line)
        count += 1
    await ctx.session.send(f"Ran '{command}' for {count} object(s).")


async def cmd_stats(ctx: CommandContext) -> None:
    """
    Live engine metrics — tick pacing, behavior load, scheduled work,
    active combat. Use it when the game feels laggy.

    Usage: @stats

    Example:
        @stats
    """
    from realm.combat.manager import get_combat_manager
    from realm.core.behaviors import behavior_owners
    from realm.scripting.engine import get_script_engine

    lines = ["Engine stats:"]
    server = getattr(ctx.dispatcher, 'server', None)
    tick = server.settings.tick_interval if server is not None else None
    beat = server.settings.world_beat if server is not None else None
    lines.append(f"  tick interval: {tick if tick is not None else '?'}s "
                 f"(scheduler resolution)")
    lines.append(f"  world beat: {beat if beat is not None else '?'}s "
                 f"(ambient/effect tempo; combat runs on each encounter's beat)")

    owners = behavior_owners()
    total_behaviors = sum(len(o.get_behaviors()) for o in owners)
    tickers = [(o, b) for o in owners
               for b in o.get_behaviors() if b.should_tick]
    lines.append(f"  behavior owners: {len(owners)}  "
                 f"(behaviors: {total_behaviors}, ticking: {len(tickers)})")
    # Name what's ticking, so an admin can find (and @destroy) a runaway or a
    # forgotten gadget by name or #id rather than guessing.
    for obj, behavior in tickers[:12]:
        lines.append(f"    - {obj.name} (#{obj.id[:8]}): {behavior.behavior_id}")
    if len(tickers) > 12:
        lines.append(f"    ... and {len(tickers) - 12} more")

    engine = get_script_engine()
    if engine is not None:
        lines.append(f"  scheduled waits: {len(engine._waits)}")

    manager = get_combat_manager()
    if manager is not None:
        n = len(getattr(manager, '_encounters', {}) or {})
        lines.append(f"  active combat encounters: {n}")

    if ctx.persistence:
        lines.append(f"  cached objects: {len(ctx.persistence.all_cached())}")
    await ctx.session.send("\n".join(lines))


async def cmd_rolls(ctx: CommandContext) -> None:
    """
    Toggle roll visibility — echo each skill check's dice to you.

    Usage: @rolls          (toggle)
           @rolls on|off

    Example:
        @rolls on
    """
    arg = (ctx.args or "").strip().lower()
    current = bool(ctx.player.db.get('show_rolls'))
    new = {'on': True, 'off': False}.get(arg, not current)
    ctx.player.db.show_rolls = new
    await ctx.session.send(f"Roll visibility {'ON' if new else 'OFF'}.")


async def cmd_quell(ctx: CommandContext) -> None:
    """
    Drop to mortal perception and authority for honest testing — you
    stop bypassing dark/hidden/invisible and lose admin powers until
    you unquell. Evennia-style.

    Usage: quell / unquell

    Example:
        quell
    """
    from realm.commands.base import run_op
    from realm.core import ops
    if ctx.command_name == 'unquell' or ctx.player.has_tag('quelled'):
        if await run_op(ctx, ops.untag, ctx.player, 'quelled') is not None:
            await ctx.session.send("You resume your full powers.")
    elif await run_op(ctx, ops.tag, ctx.player, 'quelled') is not None:
        await ctx.session.send(
            "You quell your powers — you now see and act as a mortal. "
            "'unquell' to restore.")




async def cmd_events(ctx: CommandContext) -> None:
    """
    List the event hooks this world fires: each ON_<HOOK> attribute an
    object can carry, the feature that declares it, and when it fires.

    Usage: @events

    Example:
        @events
    """
    from realm.core.eventdefs import installed
    hooks = installed().hooks()
    lines = [f"Event hooks ({len(hooks)}): set ON_<HOOK> on an object to react."]
    for name, event in hooks.items():
        lines.append(f"  ON_{name:<11} [{event.owner}] {event.doc}")
    await ctx.session.send("\n".join(lines))
