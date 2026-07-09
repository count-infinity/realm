"""
Object manipulation: doors and containers, keys and lockpicks,
wearables, hiding and searching.

Everything is lean state on ordinary objects:

- ``closed`` tag — a shut door (exit) or container. One mechanism for
  both: movement refuses closed exits, ``get from``/``put in`` refuse
  closed containers.
- ``db.locked`` + ``db.key_id`` — physically locked; opened by a
  carried key/keycard whose ``db.unlocks`` matches, by the ``pick``
  skill command (``db.lock_difficulty``, ``db.lock_skill`` for
  electronic locks), or by admins. Distinct from permission locks:
  locks/@lock decide who MAY, ``locked`` is what IS.
- ``wearable`` tag + ``db.slot`` + ``db.grants_tags`` — worn gear can
  grant perception tags (nightvision goggles).
- ``hidden`` tag — granted by the ``hide`` skill check, broken by loud
  actions or a winning ``search``/Watchful contest.
- ``invisible`` + ``db.conceal_difficulty`` — concealed scenery
  (a safe behind a painting) revealed by ``search``.
"""

from __future__ import annotations

from realm.commands import CommandContext, CommandDispatcher
from realm.commands.base import find_object
from realm.core.checks import check, contest
from realm.core.objects import GameObject
from realm.core.perception import room_is_lit
from realm.core.propagation import Action, deliver_messages, gate_action


def _find_thing_or_exit(ctx: CommandContext, name: str) -> GameObject | None:
    return find_object(ctx, name, search_exits=True)


async def _gated(
    ctx: CommandContext,
    action_type: str,
    target: GameObject,
    *,
    tool: GameObject | None = None,
    fail_msg: str,
) -> Action | None:
    """Propagate a manipulation action; behaviors/locks may veto."""
    action = Action(
        actor=ctx.player,
        target=target,
        action_type=action_type,
        tool=tool,
    )
    if not await gate_action(action, fail_msg=fail_msg):
        return None
    return action


# --- Doors & containers -------------------------------------------------------


async def cmd_open(ctx: CommandContext) -> None:
    """
    Open a door or container.

    Usage: open <target>

    Example:
        open trapdoor
    """
    if not ctx.player or not ctx.args:
        await ctx.session.send("Open what?")
        return
    target = _find_thing_or_exit(ctx, ctx.args.strip())
    if not target:
        await ctx.session.send(f"You don't see '{ctx.args.strip()}' here.")
        return
    from realm.core.verbs import do_open
    await do_open(ctx.player, target)


async def cmd_close(ctx: CommandContext) -> None:
    """
    Close a door or container.

    Usage: close <target>

    Example:
        close trapdoor
    """
    if not ctx.player or not ctx.args:
        await ctx.session.send("Close what?")
        return
    target = _find_thing_or_exit(ctx, ctx.args.strip())
    if not target:
        await ctx.session.send(f"You don't see '{ctx.args.strip()}' here.")
        return
    from realm.core.verbs import do_close
    await do_close(ctx.player, target)


def _find_key(player: GameObject, target: GameObject) -> GameObject | None:
    """A carried item whose db.unlocks matches the target's key id."""
    key_id = target.db.get('key_id')
    if not key_id:
        return None
    for item in player.contents:
        if item.db.get('unlocks') == key_id:
            return item
    return None


async def cmd_lock_item(ctx: CommandContext) -> None:
    """
    Lock a door or container (requires the matching key).

    Usage: lock <target>

    Example:
        lock chest             (needs the matching key in hand)
    """
    if not ctx.player or not ctx.args:
        await ctx.session.send("Lock what?")
        return
    target = _find_thing_or_exit(ctx, ctx.args.strip())
    if not target:
        await ctx.session.send(f"You don't see '{ctx.args.strip()}' here.")
        return
    if target.db.get('locked'):
        await ctx.session.send("It's already locked.")
        return
    if not target.db.get('key_id'):
        await ctx.session.send("There's no lock on it.")
        return
    key = _find_key(ctx.player, target)
    if key is None:
        await ctx.session.send("You don't have the key.")
        return
    target.db.locked = True
    ctx.player.msg(f"You lock {target.name} with {key.name}.")


async def cmd_unlock_item(ctx: CommandContext) -> None:
    """
    Unlock a door or container with a carried key.

    Usage: unlock <target>

    Example:
        unlock trapdoor
    """
    if not ctx.player or not ctx.args:
        await ctx.session.send("Unlock what?")
        return
    target = _find_thing_or_exit(ctx, ctx.args.strip())
    if not target:
        await ctx.session.send(f"You don't see '{ctx.args.strip()}' here.")
        return
    if not target.db.get('locked'):
        await ctx.session.send("It isn't locked.")
        return
    key = _find_key(ctx.player, target)
    if key is None:
        await ctx.session.send("You don't have the key.")
        return
    target.db.locked = False
    ctx.player.msg(f"You unlock {target.name} with {key.name}.")


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
    target = _find_thing_or_exit(ctx, ctx.args.strip())
    if not target:
        await ctx.session.send(f"You don't see '{ctx.args.strip()}' here.")
        return
    if not target.db.get('locked'):
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
        target.db.locked = False
        ctx.player.msg(f"Click. You defeat the lock on {target.name}.")
        if ctx.player.location:
            ctx.player.location.msg_contents(
                f"{ctx.player.get_display_name(None)} fiddles with {target.name}.",
                exclude=[ctx.player],
            )
    else:
        ctx.player.msg(f"The lock on {target.name} resists your attempt.")


async def cmd_use(ctx: CommandContext) -> None:
    """
    Use an object, or use a carried item on something.

    Usage: use <target>
           use <item> on <target>

    A keycard (db.unlocks) used on its matching lock (db.key_id)
    toggles the lock. Everything else propagates item:on_use for
    behaviors and ON_USE softcode to react to.

    Example:
        use lever
        use keycard on door
    """
    if not ctx.player or not ctx.args:
        await ctx.session.send("Use what?")
        return

    args = ctx.args
    item = None
    if ' on ' in args.lower():
        left, _, right = args.lower().partition(' on ')
        item_name = args[:len(left)].strip()
        target_name = args[len(left) + 4:].strip()
        item = find_object(ctx, item_name, search_room=False, search_inventory=True)
        if not item:
            await ctx.session.send(f"You aren't carrying '{item_name}'.")
            return
        target = _find_thing_or_exit(ctx, target_name) or (
            ctx.player if target_name.lower() in ('me', 'self') else None
        )
    else:
        target = _find_thing_or_exit(ctx, args.strip())

    if not target:
        await ctx.session.send("Use it on what?")
        return

    # Keycard on its lock
    if item is not None and item.db.get('unlocks') and \
            item.db.get('unlocks') == target.db.get('key_id'):
        target.db.locked = not bool(target.db.get('locked'))
        state = "locks" if target.db.get('locked') else "unlocks"
        ctx.player.msg(f"You swipe {item.name}: {target.name} {state}.")
        return

    action = await _gated(
        ctx, "item:on_use", target, tool=item,
        fail_msg=f"You can't use {'that on ' if item else ''}{target.name}.",
    )
    if action is None:
        return
    if item is not None:
        action.add_message("actor", "You use {tool:the} on {target:the}.")
        action.add_message("room", "{actor} uses {tool:a} on {target:the}.")
    else:
        action.add_message("actor", "You use {target:the}.")
        action.add_message("room", "{actor} uses {target:the}.")
    deliver_messages(action)


# --- Wearables ------------------------------------------------------------------


async def cmd_wear(ctx: CommandContext) -> None:
    """
    Wear a carried item. Worn gear can grant abilities via
    db.grants_tags (e.g. nightvision goggles).

    Usage: wear <item>

    Example:
        wear nightvision goggles
    """
    if not ctx.player or not ctx.args:
        await ctx.session.send("Wear what?")
        return
    item = find_object(ctx, ctx.args.strip(), search_room=False, search_inventory=True)
    if not item:
        await ctx.session.send(f"You aren't carrying '{ctx.args.strip()}'.")
        return
    if not item.has_tag('wearable'):
        await ctx.session.send(f"You can't wear {item.name}.")
        return
    if item.has_tag('worn'):
        await ctx.session.send("You're already wearing that.")
        return
    slot = item.db.get('slot')
    if slot:
        for other in ctx.player.contents:
            if other.has_tag('worn') and other.db.get('slot') == slot:
                await ctx.session.send(
                    f"You're already wearing {other.name} there."
                )
                return

    action = await _gated(ctx, "item:on_wear", item,
                          fail_msg=f"You can't wear {item.name}.")
    if action is None:
        return

    item.add_tag('worn')
    granted = []
    for tag in item.db.get('grants_tags') or []:
        if not ctx.player.has_tag(tag):
            ctx.player.add_tag(tag)
            granted.append(tag)
    item.db.granted_active = granted

    action.add_message("actor", "You put on {target:the}.")
    action.add_message("room", "{actor} puts on {target:a}.")
    deliver_messages(action)


async def cmd_unwear(ctx: CommandContext) -> None:
    """
    Take off a worn item (its granted abilities go with it).

    Usage: remove <item>

    Example:
        remove goggles
    """
    if not ctx.player or not ctx.args:
        await ctx.session.send("Remove what?")
        return
    item = find_object(ctx, ctx.args.strip(), search_room=False, search_inventory=True)
    if not item or not item.has_tag('worn'):
        await ctx.session.send("You aren't wearing that.")
        return

    item.remove_tag('worn')
    for tag in item.db.get('granted_active') or []:
        ctx.player.remove_tag(tag)
    item.db.granted_active = []

    ctx.player.msg(f"You take off {item.name}.")
    if ctx.player.location:
        ctx.player.location.msg_contents(
            f"{ctx.player.get_display_name(None)} takes off {item.name}.",
            exclude=[ctx.player],
        )


# --- Stealth --------------------------------------------------------------------


async def cmd_hide(ctx: CommandContext) -> None:
    """
    Slip out of sight (Stealth check; darkness helps).

    Staying hidden lasts until you act loudly or someone spots you.

    Usage: hide
    """
    if ctx.player.has_tag('hidden'):
        await ctx.session.send("You are already hidden.")
        return
    room = ctx.player.location
    modifier = 3 if (room is not None and not room_is_lit(room)) else 0

    result = check(ctx.player, 'stealth', modifier)
    if result.success:
        ctx.player.add_tag('hidden')
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
        if obj.has_tag('hidden'):
            is_character = obj.has_tag('player') or obj.has_tag('npc')
            if is_character:
                # A hidden PERSON opposes with their Stealth.
                won = contest(ctx.player, 'observation', obj, 'stealth')
            else:
                # A concealed OBJECT has no Stealth — a flat Observation
                # check against its conceal_difficulty (default 0).
                diff = int(obj.db.get('conceal_difficulty') or 0)
                won = check(ctx.player, 'observation', -diff).success
            if won:
                obj.remove_tag('hidden')
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


def register_manipulation_commands(dispatcher: CommandDispatcher) -> None:
    """Register manipulation commands with the dispatcher."""
    from functools import partial
    register = partial(dispatcher.register, category="items")
    register("open", cmd_open,
                        help_text="Open a door or container", usage="open <target>")
    register("close", cmd_close,
                        help_text="Close a door or container", usage="close <target>")
    register("lock", cmd_lock_item,
                        help_text="Lock with a carried key", usage="lock <target>")
    register("unlock", cmd_unlock_item,
                        help_text="Unlock with a carried key", usage="unlock <target>")
    register("pick", cmd_pick,
                        help_text="Pick a lock with skill", usage="pick <target>")
    register("use", cmd_use,
                        help_text="Use an object, or an item on a target",
                        usage="use <target> | use <item> on <target>")
    register("wear", cmd_wear,
                        help_text="Wear a carried item", usage="wear <item>")
    register("remove", cmd_unwear, aliases=["unwear"],
                        help_text="Take off a worn item", usage="remove <item>")
    register("hide", cmd_hide,
                        help_text="Hide (Stealth check)", usage="hide")
    register("search", cmd_search,
                        help_text="Search for the hidden (Observation check)",
                        usage="search")
