"""
Look and examine commands for REALM.

Handles viewing rooms, objects, and players.
"""

from __future__ import annotations

from realm.commands import CommandContext, CommandDispatcher
from realm.commands.base import find_exit, find_object
from realm.core.action_tags import VISUAL
from realm.core.movement import resolve_exit_destination
from realm.core.propagation import ROOM_TARGET_CHAIN, Action, propagate
from realm.core.render import render_room


async def cmd_look(ctx: CommandContext) -> None:
    """
    Look at the room or an object.

    Usage: look [target]
           l [target]

    Example:
        look
        look statue
    """
    if not ctx.args:
        # Look at the room
        await _show_room(ctx)
        return

    target_name = ctx.args.strip()

    # Try to find an object
    target = find_object(ctx, target_name, search_exits=True)

    if target:
        await _show_object(ctx, target)
        return

    # Try as an exit
    exit_obj = find_exit(ctx, target_name)
    if exit_obj:
        await _show_exit(ctx, exit_obj)
        return

    # Check for special targets
    if target_name.lower() in ('me', 'self'):
        await _show_object(ctx, ctx.player)
        return

    if target_name.lower() == 'here' and ctx.player.location:
        await _show_room(ctx)
        return

    await ctx.session.send(f"You don't see '{target_name}' here.")


async def cmd_examine(ctx: CommandContext) -> None:
    """
    Examine an object in detail.

    Shows more information than look, including attributes.

    Usage: examine <target>
           ex <target>

    Example:
        examine statue         (visual-flagged attributes show here)
    """
    if not ctx.args:
        await ctx.session.send("Examine what?")
        return

    target_name = ctx.args.strip()

    # Special cases
    if target_name.lower() in ('me', 'self'):
        target = ctx.player
    elif target_name.lower() == 'here':
        target = ctx.player.location
    else:
        target = find_object(ctx, target_name, search_exits=True)

    if not target:
        await ctx.session.send(f"You don't see '{target_name}' here.")
        return

    # Show detailed information
    await ctx.session.send(f"\n{target.name}")
    await ctx.session.send("=" * len(target.name))

    if target.description:
        desc = target.description
        if '[[' in desc:
            from realm.scripting.inline import eval_inline
            desc = eval_inline(desc, target, ctx.player).strip()
        if desc:
            await ctx.session.send(desc)
    from realm.core.describe import detail_lines
    for line in detail_lines(target, ctx.player):
        await ctx.session.send(line)

    await ctx.session.send("")

    # Attributes the builder flagged visual are public lore.
    from realm.core.attrflags import visual_attrs
    for attr_name in visual_attrs(target):
        value = target.db.get(attr_name)
        if value is not None:
            await ctx.session.send(f"{attr_name}: {value}")

    # Show tags
    if target.tags:
        tags_str = ", ".join(sorted(target.tags.to_list()))
        await ctx.session.send(f"Tags: {tags_str}")

    # Show ID (for builders)
    # TODO: Check if player has builder permission
    await ctx.session.send(f"ID: {target.id}")

    # Show owner
    if target.owner:
        await ctx.session.send(f"Owner: {target.owner.name}")

    # Show parent
    if target.parent:
        await ctx.session.send(f"Parent: {target.parent.name}")

    # Show location
    if target.location:
        await ctx.session.send(f"Location: {target.location.name}")

    # Show contents count
    if target.contents:
        await ctx.session.send(f"Contents: {len(target.contents)} object(s)")

    # Show behaviors
    behaviors = target.get_behaviors()
    if behaviors:
        behavior_names = [b.behavior_id for b in behaviors]
        await ctx.session.send(f"Behaviors: {', '.join(behavior_names)}")

    # Show custom attributes
    attrs = target.db.all()
    if attrs:
        await ctx.session.send("\nAttributes:")
        for key, value in sorted(attrs.items()):
            # Skip internal attributes
            if not key.startswith('_'):
                await ctx.session.send(f"  {key}: {value}")

    await ctx.session.send("")


async def _show_room(ctx: CommandContext) -> None:
    """Display the current room to the player."""
    room = ctx.player.location
    if not room:
        await ctx.session.send("You are nowhere.")
        return

    # Propagate a look action so observers can react (mirrors, paintings,
    # NPCs that notice scrutiny, audit logs). The actual display output
    # below is the answer to a query, not a propagated message.
    look = Action(
        actor=ctx.player,
        target=room,
        action_type="event:look",
        chain=ROOM_TARGET_CHAIN,
        tags={VISUAL},
    )
    await propagate(look)

    await ctx.session.send(render_room(room, ctx.player))


async def _show_object(ctx: CommandContext, target) -> None:
    """Display an object to the player."""
    # Looking AT an object: target is the object, default chain visits
    # actor → room → bystanders → target. The object's behaviors get a
    # chance to react ("the box rattles when you look at it").
    if ctx.player is not None:
        look = Action(
            actor=ctx.player,
            target=target,
            action_type="event:look",
            tags={VISUAL},
        )
        await propagate(look)

    # Play-facing look: name the target as the looker knows them (a
    # disguise or an unintroduced stranger reads by their assumed name).
    # `@examine` deliberately does NOT — it shows the truth.
    await ctx.session.send(f"\n{target.get_display_name(ctx.player)}")

    # "You see nothing special." is the fallback for an object that shows
    # the looker NOTHING — no description and no perceptible details. It
    # must not follow a description that did render.
    described = False

    if target.description:
        desc = target.description
        if '[[' in desc:
            from realm.scripting.inline import eval_inline
            desc = eval_inline(desc, target, ctx.player).strip()
        if desc:
            await ctx.session.send(desc)
            described = True
    from realm.core.describe import detail_lines
    for line in detail_lines(target, ctx.player):
        await ctx.session.send(line)
        described = True
    if not described:
        await ctx.session.send("You see nothing special.")

    # If it's a container with visible contents
    if target.has_tag('closed'):
        await ctx.session.send("It is closed.")
    elif target.contents and not target.has_tag('player'):
        visible = [obj for obj in target.contents if not obj.has_tag('exit')]
        if visible:
            await ctx.session.send("\nContains:")
            for obj in visible:
                await ctx.session.send(f"  {obj.name}")

    await ctx.session.send("")


async def _show_exit(ctx: CommandContext, exit_obj) -> None:
    """Display an exit to the player."""
    await ctx.session.send(f"\n{exit_obj.name}")

    if exit_obj.description:
        await ctx.session.send(exit_obj.description)

    dest = resolve_exit_destination(exit_obj, ctx.persistence)
    if dest:
        await ctx.session.send(f"Leads to: {dest.name}")

    await ctx.session.send("")


def register_look_commands(dispatcher: CommandDispatcher) -> None:
    """Register look commands with the dispatcher."""
    from functools import partial
    register = partial(dispatcher.register, category="looking")

    register(
        "look",
        cmd_look,
        aliases=["l"],
        help_text="Look at your surroundings or an object",
        usage="look [target]",
    )

    register(
        "examine",
        cmd_examine,
        aliases=["ex", "exam"],
        help_text="Examine an object in detail",
        usage="examine <target>",
    )
