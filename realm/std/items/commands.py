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
from realm.core.events import fire_event
from realm.core.objects import GameObject
from realm.core.propagation import Action, deliver_messages, gate_action
from realm.std.items.actions import ItemAction
from realm.std.items.verbs import do_close, do_open


async def gated_item_action(actor: GameObject, action_type: str, target: GameObject, *,
                            fail_msg: str, apply=None) -> Action | None:
    """``_gated`` for code that has a player but no command context."""
    action = Action(actor=actor, target=target, action_type=action_type)
    if not await gate_action(action, fail_msg=fail_msg, apply=apply):
        return None
    return action


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


# ``wear`` and ``remove`` live in ``realm.std.items.equipment``.


# --- Weapons ----------------------------------------------------------------


async def cmd_wield(ctx: CommandContext) -> None:
    """
    Ready a carried weapon (one at a time).

    Usage: wield <weapon>

    Example:
        wield laser pistol
    """

    if not ctx.player or not ctx.args:
        await ctx.session.send("Wield what?")
        return
    weapon = find_object(ctx, ctx.args.strip(),
                         search_room=False, search_inventory=True)
    if weapon is None:
        await ctx.session.send(f"You aren't carrying '{ctx.args.strip()}'.")
        return
    from realm.std.items.equipment import may_use
    if not weapon.has_tag("wielded") and not may_use(ctx.player, weapon):
        return

    wielding = await fire_event(ctx.player, weapon, ItemAction.ON_WIELD, gated=True)
    if wielding.blocked:
        ctx.player.msg(wielding.block_reason or f"You can't ready {weapon.name}.")
        return
    for item in ctx.player.contents:
        if item.has_tag('wielded') and item is not weapon:
            item.remove_tag('wielded')
            ctx.player.msg(f"You lower {item.name}.")
    weapon.add_tag('wielded')
    ctx.player.msg(f"You ready {weapon.name}.")
    if ctx.player.location:
        ctx.player.location.msg_contents(
            f"{ctx.player.name} readies {weapon.name}.", exclude=[ctx.player])


async def cmd_unwield(ctx: CommandContext) -> None:
    """
    Lower your readied weapon.

    Usage: unwield
    """
    for item in ctx.player.contents:
        if item.has_tag('wielded'):
            lowering = await fire_event(ctx.player, item, ItemAction.ON_UNWIELD,
                                        gated=True)
            if lowering.blocked:
                ctx.player.msg(
                    lowering.block_reason or f"You can't lower {item.name}.")
                return
            item.remove_tag('wielded')
            await ctx.session.send(f"You lower {item.name}.")
            return
    await ctx.session.send("You have nothing readied.")
