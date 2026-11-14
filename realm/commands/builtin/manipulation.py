"""
Object manipulation: doors and containers, keys, wearables. (Hiding,
searching and lockpicking are the ``stealth`` feature's:
``realm/std/stealth/commands.py``.)

Everything is lean state on ordinary objects — capability and state are
**tags**, values are attributes:

- ``container`` tag — this object can be opened/closed and holds contents
  (``get from`` / ``put in`` / ``open`` / ``close``). ``closable`` tags a
  non-container that can still be closed.
- ``closed`` tag — a shut door (exit) or container. One mechanism for
  both: movement refuses closed exits, ``get from``/``put in`` refuse
  closed containers.
- ``locked`` tag + ``db.key_id`` — physically locked; opened by a
  carried key/keycard whose ``db.unlocks`` matches, by ``stealth``'s
  ``pick`` (``db.lock_difficulty``, ``db.lock_skill`` for electronic
  locks), or by admins. Distinct from permission locks:
  locks/@lock decide who MAY, ``locked`` is what IS.
- ``wearable`` tag + ``db.slot`` + ``db.grants_tags`` — worn gear can
  grant perception tags (nightvision goggles).
"""

from __future__ import annotations

from realm.commands import CommandContext
from realm.commands.base import find_object
from realm.core.objects import GameObject
from realm.core.propagation import Action, deliver_messages, gate_action
from realm.std.items.actions import ItemAction


def _find_thing_or_exit(ctx: CommandContext, name: str) -> GameObject | None:
    return find_object(ctx, name, search_exits=True)


async def _gated(
    ctx: CommandContext,
    action_type: str,
    target: GameObject,
    *,
    tool: GameObject | None = None,
    data: dict | None = None,
    fail_msg: str,
    apply=None,
) -> Action | None:
    """Propagate a manipulation action with its engine effect as ``apply``
    (run between the passes — reaction hooks see POST-state); behaviors/
    locks may veto, in which case the effect never runs."""
    action = Action(
        actor=ctx.player,
        target=target,
        action_type=action_type,
        tool=tool,
    )
    for key, value in (data or {}).items():
        action.add_data(key, value)
    if not await gate_action(action, fail_msg=fail_msg, apply=apply):
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
    from realm.std.items.verbs import do_open
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
    from realm.std.items.verbs import do_close
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
    if target.has_tag('locked'):
        await ctx.session.send("It's already locked.")
        return
    if not target.db.get('key_id'):
        await ctx.session.send("There's no lock on it.")
        return
    key = _find_key(ctx.player, target)
    if key is None:
        await ctx.session.send("You don't have the key.")
        return
    if await _gated(ctx, ItemAction.ON_LOCK, target, tool=key,
                    fail_msg="The lock won't catch.",
                    apply=lambda _a: target.add_tag('locked')) is None:
        return
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
    if not target.has_tag('locked'):
        await ctx.session.send("It isn't locked.")
        return
    key = _find_key(ctx.player, target)
    if key is None:
        await ctx.session.send("You don't have the key.")
        return
    if await _gated(ctx, ItemAction.ON_UNLOCK, target, tool=key,
                    fail_msg="The lock holds fast.",
                    apply=lambda _a: target.remove_tag('locked')) is None:
        return
    ctx.player.msg(f"You unlock {target.name} with {key.name}.")


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

    # Keycard on its lock — the same gated lock/unlock events the `lock`/
    # `unlock` commands fire, so wards apply and ON_LOCK/ON_UNLOCK mirrors
    # hear a swipe exactly like a turned key.
    if item is not None and item.db.get('unlocks') and \
            item.db.get('unlocks') == target.db.get('key_id'):
        now_locked = not target.has_tag('locked')
        atype = ItemAction.ON_LOCK if now_locked else ItemAction.ON_UNLOCK
        fail = "The lock won't catch." if now_locked else "The lock holds fast."

        def _flip(_a):
            if now_locked:
                target.add_tag('locked')
            else:
                target.remove_tag('locked')

        if await _gated(ctx, atype, target, tool=item, fail_msg=fail,
                        apply=_flip) is None:
            return
        state = "locks" if now_locked else "unlocks"
        ctx.player.msg(f"You swipe {item.name}: {target.name} {state}.")
        return

    action = await _gated(
        ctx, ItemAction.ON_USE, target, tool=item,
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

    def _don(_a):
        item.add_tag('worn')
        granted = []
        for tag in item.db.get('grants_tags') or []:
            if not ctx.player.has_tag(tag):
                ctx.player.add_tag(tag)
                granted.append(tag)
        item.db.granted_active = granted

    action = await _gated(ctx, ItemAction.ON_WEAR, item,
                          fail_msg=f"You can't wear {item.name}.",
                          apply=_don)
    if action is None:
        return

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

    # ON_REMOVE — gated, the mirror of item:on_wear: a cursed item's on_check
    # can refuse (block) removal.
    def _doff(_a):
        item.remove_tag('worn')
        for tag in item.db.get('granted_active') or []:
            ctx.player.remove_tag(tag)
        item.db.granted_active = []

    removing = await _gated(
        ctx, ItemAction.ON_REMOVE, item,
        fail_msg="You can't seem to take it off.",
        apply=_doff)
    if removing is None:
        return

    ctx.player.msg(f"You take off {item.name}.")
    if ctx.player.location:
        ctx.player.location.msg_contents(
            f"{ctx.player.get_display_name(None)} takes off {item.name}.",
            exclude=[ctx.player],
        )
