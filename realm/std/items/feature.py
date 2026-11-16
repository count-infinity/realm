"""
The ``items`` feature.

Carrying, giving, wearing and using objects; doors and locks.
"""

from __future__ import annotations

from realm.features import Feature
from realm.std.items.actions import ItemAction
from realm.std.items.commands import (
    cmd_close,
    cmd_lock_item,
    cmd_open,
    cmd_unlock_item,
    cmd_unwield,
    cmd_use,
    cmd_wield,
)
from realm.std.items.equipment import cmd_equipment, cmd_unwear, cmd_wear
from realm.std.items.food import cmd_drink, cmd_eat
from realm.std.items.inventory import (
    cmd_drop,
    cmd_get,
    cmd_give,
    cmd_inventory,
    cmd_put,
)

feature = Feature(
    'items',
    doc='Carrying, giving, wearing and using objects; doors and locks.',
)

feature.command(
    'get',
    cmd_get,
    aliases=['take', 'grab'],
    category='items',
    help_text='Pick up an object',
    usage='get <object> [from <container>]',
)
feature.command(
    'drop',
    cmd_drop,
    category='items',
    help_text='Drop an object',
    usage='drop <object>',
)
feature.command(
    'give',
    cmd_give,
    category='items',
    help_text='Give an object to someone',
    usage='give <object> to <player>',
    parse_equals=True,
)
feature.command(
    'put',
    cmd_put,
    aliases=['place'],
    category='items',
    help_text='Put an object in a container',
    usage='put <object> in <container>',
)
feature.command(
    'inventory',
    cmd_inventory,
    aliases=['i', 'inv'],
    category='items',
    help_text='Show your inventory',
)
feature.command(
    'open',
    cmd_open,
    category='items',
    help_text='Open a door or container',
    usage='open <target>',
)
feature.command(
    'close',
    cmd_close,
    category='items',
    help_text='Close a door or container',
    usage='close <target>',
)
feature.command(
    'lock',
    cmd_lock_item,
    category='items',
    help_text='Lock with a carried key',
    usage='lock <target>',
)
feature.command(
    'unlock',
    cmd_unlock_item,
    category='items',
    help_text='Unlock with a carried key',
    usage='unlock <target>',
)
feature.command(
    'use',
    cmd_use,
    category='items',
    help_text='Use an object, or an item on a target',
    usage='use <target> | use <item> on <target>',
)
feature.command(
    'wear',
    cmd_wear,
    category='items',
    help_text='Wear a carried item',
    usage='wear <item> [replace]',
)
feature.command(
    'equipment',
    cmd_equipment,
    aliases=['eq'],
    category='items',
    help_text='Show what you wear and wield',
)
feature.command('eat', cmd_eat, category='items', help_text='Eat something you carry',
                usage='eat <food>')
feature.command('drink', cmd_drink, category='items',
                help_text='Drink from a container or fountain', usage='drink <container>')
feature.command(
    'remove',
    cmd_unwear,
    aliases=['unwear'],
    category='items',
    help_text='Take off a worn item',
    usage='remove <item>',
)
feature.command(
    'wield',
    cmd_wield,
    aliases=['ready', 'draw'],
    category='combat',
    help_text='Ready a carried weapon',
    usage='wield <weapon>',
)
feature.command(
    'unwield',
    cmd_unwield,
    aliases=['lower', 'sheathe'],
    category='combat',
    help_text='Lower your readied weapon',
    usage='unwield',
)


# --- script verbs: the same manipulation cores the commands use -------------

def _find(candidates, spec):
    from realm.core.search import AmbiguousMatchError, match_one
    try:
        return match_one(spec, candidates)
    except AmbiguousMatchError:
        return None


def _around(executor):
    room = list(executor.location.contents) if executor.location else []
    return [o for o in room if o is not executor]


@feature.script_verb("get", aliases=["take"], doc="get <item>: pick up from the room")
async def _get(engine, executor, rest):
    from realm.std.items.verbs import do_get
    target = _find(_around(executor), rest.strip())
    if target is not None:
        await do_get(executor, target)


@feature.script_verb("drop", doc="drop <item>: put down something carried")
async def _drop(engine, executor, rest):
    from realm.std.items.verbs import do_drop
    target = _find(list(executor.contents), rest.strip())
    if target is not None:
        await do_drop(executor, target)


@feature.script_verb("give", doc="give <item> = <who> (or: give <item> to <who>)")
async def _give(engine, executor, rest):
    from realm.std.items.verbs import do_give
    if '=' in rest:
        item_spec, target_spec = rest.split('=', 1)
    elif ' to ' in rest.lower():
        idx = rest.lower().index(' to ')
        item_spec, target_spec = rest[:idx], rest[idx + 4:]
    else:
        return
    item = _find(list(executor.contents), item_spec.strip())
    target = _find(_around(executor), target_spec.strip())
    if item is not None and target is not None:
        await do_give(executor, item, target)


@feature.script_verb("open", doc="open <door or container>")
async def _open(engine, executor, rest):
    from realm.std.items.verbs import do_open
    target = _find(_around(executor), rest.strip())
    if target is not None:
        await do_open(executor, target)


@feature.script_verb("close", doc="close <door or container>")
async def _close(engine, executor, rest):
    from realm.std.items.verbs import do_close
    target = _find(_around(executor), rest.strip())
    if target is not None:
        await do_close(executor, target)


# --- events -------------------------------------------------------------------


feature.event(ItemAction.ON_GET, hook="GET", doc="this object is picked up",
              target_lock=("basic", "You can't pick up {name}."))
feature.event(ItemAction.ON_DROP, hook="DROP", doc="this object is dropped",
              target_lock=("drop", "You can't drop {name}."))
feature.event(ItemAction.ON_GIVE, hook="GIVE", doc="this object is given away",
              payload={"item": "what was given (also the action's tool); target is "
                               "the recipient"},
              tool_lock=("give", "You can't give {name} away."))
feature.event(ItemAction.ON_PUT, hook="PUT", doc="this object is put in a container",
              payload={"item": "what was put in; target is the container"},
              target_lock=("enter", "You can't put things in {name}."))
feature.event(ItemAction.ON_WEAR, hook="WEAR", doc="this object is worn")
feature.event(ItemAction.ON_REMOVE, hook="REMOVE",
              doc="this object is taken off (gated: cursed gear can refuse)")
feature.event(ItemAction.ON_WIELD, hook="WIELD", doc="this weapon is readied (gated)")
feature.event(ItemAction.ON_UNWIELD, hook="UNWIELD", doc="this weapon is lowered (gated)")
feature.event(ItemAction.ON_USE, hook="USE", doc="this object is used")
feature.event(ItemAction.ON_EAT, hook="EAT", doc="this food is eaten (gated)")
feature.event(ItemAction.ON_DRINK, hook="DRINK", doc="this is drunk from (gated)")
feature.event(ItemAction.ON_OPEN, hook="OPEN", doc="this door/container is opened")
feature.event(ItemAction.ON_CLOSE, hook="CLOSE", doc="this door/container is closed")
feature.event(ItemAction.ON_LOCK, hook="LOCK", doc="this is locked (gated)")
feature.event(ItemAction.ON_UNLOCK, hook="UNLOCK",
              doc="this is unlocked (gated: a sealed door can refuse)",
              payload={"picked": "True when a lockpick, not a key, opened it"})
feature.event(None, hook="PUSH", doc="this object is pushed (button, lever)")
