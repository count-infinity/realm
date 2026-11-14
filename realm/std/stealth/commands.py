"""
The ``stealth`` feature's commands: hide, search, pick.

- ``hidden`` tag — granted by the ``hide`` skill check, broken by loud
  actions or a winning ``search``/Watchful contest (``hiding.py``).
- ``invisible`` + ``db.conceal_difficulty`` — concealed scenery
  (a safe behind a painting) revealed by ``search``.
- ``locked`` tag — ``pick`` defeats it with a skill check
  (``db.lock_difficulty``; ``db.lock_skill`` for electronic locks).
"""

from __future__ import annotations

from realm.commands import CommandContext
from realm.commands.base import find_object
from realm.core.perception import room_is_lit
from realm.std.items.actions import ItemAction
from realm.std.items.verbs import gate_item_action
from realm.std.rules.checks import check, contest
from realm.std.stealth.hiding import HIDDEN_TAG


async def cmd_pick(ctx: CommandContext) -> None:
    """
    Pick a lock with skill (lockpicking by default; a lock may demand
    another skill via db.lock_skill — e.g. electronics).

    Usage: pick <target>

    Example:
        pick chest             (lockpicking check; carry lockpicks)
    """
    if not ctx.player or not ctx.args:
        await ctx.session.send("Pick what?")
        return
    target = find_object(ctx, ctx.args.strip(), search_exits=True)
    if not target:
        await ctx.session.send(f"You don't see '{ctx.args.strip()}' here.")
        return
    if not target.has_tag('locked'):
        await ctx.session.send("It isn't locked.")
        return

    skill = target.db.get('lock_skill') or 'lockpicking'
    modifier = -int(target.db.get('lock_difficulty') or 0)
    # Proper tools matter: without lockpicks you're improvising.
    if skill == 'lockpicking':
        has_tools = any(item.has_tag('lockpicks') for item in ctx.player.contents)
        if not has_tools:
            modifier -= 5

    result = check(ctx.player, skill, modifier)
    if result.success:
        # The same gated unlock event the `unlock` command fires — wards may
        # veto a picked lock too, and ON_UNLOCK mirrors/alarms hear it.
        # `picked` in the action data lets scripts tell a jimmy from a key.
        if await gate_item_action(
                ctx.player, ItemAction.ON_UNLOCK, target, extra={'picked': True},
                fail_msg=f"The lock on {target.name} defies your tools.",
                apply=lambda _a: target.remove_tag('locked')) is None:
            return
        ctx.player.msg(f"Click. You defeat the lock on {target.name}.")
        if ctx.player.location:
            ctx.player.location.msg_contents(
                f"{ctx.player.get_display_name(None)} fiddles with {target.name}.",
                exclude=[ctx.player],
            )
    else:
        ctx.player.msg(f"The lock on {target.name} resists your attempt.")


async def cmd_hide(ctx: CommandContext) -> None:
    """
    Slip out of sight (Stealth check; darkness helps).

    Staying hidden lasts until you act loudly or someone spots you.

    Usage: hide
    """
    if ctx.player.has_tag(HIDDEN_TAG):
        await ctx.session.send("You are already hidden.")
        return
    room = ctx.player.location
    modifier = 3 if (room is not None and not room_is_lit(room)) else 0

    result = check(ctx.player, 'stealth', modifier)
    if result.success:
        ctx.player.add_tag(HIDDEN_TAG)
        await ctx.session.send("You slip out of sight.")
    else:
        await ctx.session.send("You can't find anywhere to hide.")


async def cmd_search(ctx: CommandContext) -> None:
    """
    Search the room (Observation check): reveals concealed objects and
    contests hidden characters' Stealth.

    Usage: search
    """
    if not ctx.player or not ctx.player.location:
        return
    room = ctx.player.location
    found: list[str] = []

    for obj in list(room.contents):
        if obj is ctx.player:
            continue
        if obj.has_tag(HIDDEN_TAG):
            is_character = obj.is_player or obj.is_npc
            if is_character:
                # A hidden PERSON opposes with their Stealth.
                won = contest(ctx.player, 'observation', obj, 'stealth')
            else:
                # A concealed OBJECT has no Stealth — a flat Observation
                # check against its conceal_difficulty (default 0).
                diff = int(obj.db.get('conceal_difficulty') or 0)
                won = check(ctx.player, 'observation', -diff).success
            if won:
                obj.remove_tag(HIDDEN_TAG)
                found.append(obj.get_display_name(ctx.player))
                if is_character:
                    obj.msg(f"{ctx.player.name} spots you!")
                    room.msg_contents(
                        f"{ctx.player.name} spots {obj.name} hiding!",
                        exclude=[ctx.player, obj],
                    )
        elif obj.has_tag('invisible') and obj.db.get('conceal_difficulty') is not None:
            result = check(ctx.player, 'observation',
                           -int(obj.db.get('conceal_difficulty') or 0))
            if result.success:
                obj.remove_tag('invisible')
                reveal = obj.db.get('reveal_msg') or f"{ctx.player.name} uncovers {obj.name}!"
                found.append(obj.name)
                room.msg_contents(reveal, exclude=[ctx.player])
                ctx.player.msg(reveal)

    if found:
        await ctx.session.send(f"Your search turns up: {', '.join(found)}.")
    else:
        await ctx.session.send("You find nothing unusual.")


__all__ = ["cmd_hide", "cmd_search", "cmd_pick"]
