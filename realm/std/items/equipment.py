"""
Wearing things: slots, ``wear``, ``remove`` and ``equipment`` (MUD_PLAN 3.1).

An item tagged ``wearable`` names where it goes in ``db.slot``. The game
system says which slots exist and how many items each holds
(``GameSystem.wear_slots``: Merc has two fingers, two necks and two wrists).
A system with no list (the neutral default) takes any slot name, one item
each. A full slot refuses the next item unless asked to ``replace``, which
takes off the one worn longest, through the same gated ``item:on_remove``
as ``remove`` (a cursed ring stays on).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from realm.commands.base import find_object
from realm.core.world import get_world
from realm.std.items.actions import ItemAction

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject
    from realm.core.world import World

_log = logging.getLogger(__name__)

#: Before 2026-11-17 the ROM importer left a mob's E-reset gear in its pack
#: with a ``worn`` attribute naming ROM's wear location; ``hold`` is Merc's
#: ``held`` slot.
_OLD_WEAR_LOC_SLOT = {"hold": "held"}


def wear_slots() -> list[tuple[str, int]]:
    """The game system's slots, or ``[]`` with no rules feature."""
    rules = get_world().rules
    return list(rules.wear_slots()) if rules is not None else []


def worn_in(player: GameObject, slot: str) -> list[GameObject]:
    """What ``player`` wears in ``slot``, longest worn first."""
    worn = [o for o in player.contents
            if o.has_tag('worn') and o.db.get('slot') == slot]
    return sorted(worn, key=lambda o: int(o.db.get('worn_seq') or 0))


def _bare_name(item: GameObject) -> str:
    """"an iron ring" -> "iron ring", for a command line to type."""
    name = item.name
    for article in ("a ", "an ", "the "):
        if name.lower().startswith(article):
            return name[len(article):]
    return name


def equipped(item: GameObject) -> bool:
    """Is ``item`` worn or wielded (not merely carried)?"""
    return item.has_tag('worn') or item.has_tag('wielded')


def take_it_off_first(item: GameObject) -> str | None:
    """Why ``item`` cannot leave its holder's hands as it is: ROM's "You must
    remove it first." for worn gear ("unwield" for a weapon in hand, which
    ``remove`` does not take); None when it is only carried. ``drop``,
    ``give``, ``put``, ``sell`` and ``eat`` ask (``drop all`` skips it)."""
    if item.has_tag('wielded'):
        return "You must unwield it first."
    if item.has_tag('worn'):
        return "You must remove it first."
    return None


def unequip(wearer: GameObject, item: GameObject) -> None:
    """Take ``item`` off ``wearer`` silently, with no event: what ROM's
    ``obj_from_char`` does to equipment leaving its owner (a death's
    corpse). The tags it granted go with it."""
    item.remove_tag('worn')
    item.remove_tag('wielded')
    for tag in item.db.get('granted_active') or []:
        wearer.remove_tag(tag)
    if item.db.get('granted_active'):
        item.db.granted_active = []


async def take_off(player: GameObject, item: GameObject) -> bool:
    """Remove a worn item through the gated ``item:on_remove``; its granted
    tags go with it. False when something refused."""
    from realm.std.items.commands import gated_item_action

    def _doff(_a):
        item.remove_tag('worn')
        for tag in item.db.get('granted_active') or []:
            player.remove_tag(tag)
        item.db.granted_active = []

    removing = await gated_item_action(
        player, ItemAction.ON_REMOVE, item,
        fail_msg="You can't seem to take it off.", apply=_doff)
    if removing is None:
        return False
    player.msg(f"You take off {item.name}.")
    if player.location:
        player.location.msg_contents(
            f"{player.get_display_name(None)} takes off {item.name}.",
            exclude=[player])
    return True


def may_use(player: GameObject, item: GameObject) -> bool:
    """The game system's word before ``item`` is worn or wielded: a
    refusal (Merc: the item's level is above the character's) is said and
    stops it; an item that ``repels`` the character zaps off to the floor.
    True when nothing stood in the way."""
    rules = get_world().rules
    if rules is None:
        return True
    refusal = rules.wear_refusal(player, item)
    if refusal:
        player.msg(refusal)
        return False
    if rules.repels(player, item):
        rules.zap(player, item)
        return False
    return True


async def cmd_wear(ctx: CommandContext) -> None:
    """
    Wear a carried item. Worn gear can grant abilities via
    db.grants_tags (e.g. nightvision goggles). A full slot takes the new
    item only with `replace`, which takes off the one worn longest.

    Usage: wear <item> [replace]
           wear all

    Example:
        wear nightvision goggles
        wear iron ring replace
        wear all               (everything carried that has a free slot)
    """
    args = (ctx.args or "").strip()
    replace = False
    if args.lower().endswith(" replace"):
        args, replace = args[:-len(" replace")].strip(), True
    if not ctx.player or not args:
        await ctx.session.send("Wear what?")
        return
    player = ctx.player
    if args.lower() == "all":
        await _wear_all(ctx, player)
        return
    item = find_object(ctx, args, search_room=False, search_inventory=True)
    if not item:
        await ctx.session.send(f"You aren't carrying '{args}'.")
        return
    if not item.has_tag('wearable'):
        await ctx.session.send(f"You can't wear {item.name}.")
        return
    if item.has_tag('worn'):
        await ctx.session.send("You're already wearing that.")
        return
    await _wear(ctx, player, item, replace=replace)


async def _wear_all(ctx: CommandContext, player: GameObject) -> None:
    """ROM's ``wear all``: each carried wearable that has a free slot, in
    the order carried; a full slot is passed over, never replaced."""
    slots = dict(wear_slots())
    wore = False
    for item in list(player.contents):
        if not item.has_tag('wearable') or item.has_tag('worn') or item.has_tag('wielded'):
            continue
        slot = item.db.get('slot')
        if slot and (slots and slot not in slots
                     or len(worn_in(player, slot)) >= slots.get(slot, 1)):
            continue
        wore = await _wear(ctx, player, item, replace=False) or wore
    if not wore:
        await ctx.session.send("You have nothing more to wear.")


async def _wear(ctx: CommandContext, player: GameObject, item: GameObject, *,
                replace: bool) -> bool:
    """Put ``item`` on, taking off the oldest in a full slot when
    ``replace``. Says why not, and returns whether it was put on."""
    from realm.std.items.commands import gated_item_action

    if not may_use(player, item):
        return False

    slot = item.db.get('slot')
    if slot:
        slots = dict(wear_slots())
        if slots and slot not in slots:
            await ctx.session.send(
                f"You can't wear {item.name}: this game has no {slot} to wear it on.")
            return False
        there = worn_in(player, slot)
        if len(there) >= slots.get(slot, 1):
            if not replace:
                names = " and ".join(o.name for o in there)
                await ctx.session.send(f"You're already wearing {names} there.")
                await ctx.session.send(
                    f"(Type 'wear {_bare_name(item)} replace' to take off "
                    f"{there[0].name} instead.)")
                return False
            if not await take_off(player, there[0]):
                return False

    def _don(_a):
        item.add_tag('worn')
        seq = int(player.db.get('wear_seq') or 0) + 1
        player.db.wear_seq = seq
        item.db.worn_seq = seq
        granted = []
        for tag in item.db.get('grants_tags') or []:
            if not player.has_tag(tag):
                player.add_tag(tag)
                granted.append(tag)
        item.db.granted_active = granted

    action = await gated_item_action(player, ItemAction.ON_WEAR, item,
                                     fail_msg=f"You can't wear {item.name}.",
                                     apply=_don)
    if action is None:
        return False
    from realm.core.propagation import deliver_messages
    action.add_message("actor", "You put on {target:the}.")
    action.add_message("room", "{actor} puts on {target:a}.")
    deliver_messages(action)
    return True


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
    await take_off(ctx.player, item)


async def equip_old_gear(world: World) -> None:
    """``feature.on_boot``: an item carrying the ROM importer's old ``worn``
    attribute (a saved world converted before 2026-11-17) is equipped as a
    wearer's gear is: ``wield`` tags it ``wielded``, any other place tags it
    ``worn`` in that ``slot``. A place the game has no slot for leaves it
    carried, with a WARNING. A no-op once done."""
    store = world.store
    slots = {name for name, _count in wear_slots()}
    for item in list(store.all_cached()):
        place = item.db.get("worn")
        if not isinstance(place, str):
            continue
        item.db.delete("worn")
        if place == "wield":
            item.add_tag("wielded")
        else:
            slot = _OLD_WEAR_LOC_SLOT.get(place, place)
            if slots and slot not in slots:
                _log.warning(f"{item.name} ({item.id}) was worn at {place!r}, which this "
                             f"game has no slot for; it is carried, not worn. Give it a "
                             f"'slot' and the 'worn' tag to wear it.")
            else:
                item.add_tag("worn")
                item.db.slot = slot
        await store.save(item)


def equipment_lines(player: GameObject) -> list[str]:
    """The ``equipment`` listing: every slot in the system's order with
    what fills it, then anything worn elsewhere, then the wielded weapon."""
    slots = wear_slots()
    rows: list[tuple[str, str]] = []
    listed: set[str] = set()
    for slot, count in slots:
        there = worn_in(player, slot)
        for i in range(count):
            item = there[i] if i < len(there) else None
            rows.append((slot, item.name if item is not None else "nothing"))
            if item is not None:
                listed.add(item.id)
    for item in player.contents:
        if item.has_tag('worn') and item.id not in listed:
            rows.append((str(item.db.get('slot') or 'worn'), item.name))
    wielded = next((o for o in player.contents if o.has_tag('wielded')), None)
    if wielded is not None or slots:
        rows.append(("wielded", wielded.name if wielded is not None else "nothing"))
    if not rows:
        return ["You are using nothing."]
    width = max(len(slot) for slot, _ in rows) + 2
    return ["You are using:"] + [f"  {f'<{slot}>':{width}} {what}" for slot, what in rows]


async def cmd_equipment(ctx: CommandContext) -> None:
    """
    Show what you are wearing and wielding, slot by slot.

    Usage: equipment
    """
    await ctx.session.send("\n".join(equipment_lines(ctx.player)))


__all__ = ["wear_slots", "worn_in", "unequip", "take_off", "may_use", "cmd_wear", "cmd_unwear",
           "equip_old_gear", "equipment_lines", "cmd_equipment"]
