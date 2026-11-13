"""
The ``items`` feature.

Carrying, giving, wearing and using objects; doors and locks.
"""

from __future__ import annotations

from realm.commands.builtin.combat import cmd_unwield, cmd_wield
from realm.commands.builtin.inventory import (
    cmd_drop,
    cmd_get,
    cmd_give,
    cmd_inventory,
    cmd_put,
)
from realm.commands.builtin.manipulation import (
    cmd_close,
    cmd_lock_item,
    cmd_open,
    cmd_unlock_item,
    cmd_unwear,
    cmd_use,
    cmd_wear,
)
from realm.features import Feature

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
    usage='wear <item>',
)
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
