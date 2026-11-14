"""
The ``building`` feature.

The @-commands for building and administering the world.
"""

from __future__ import annotations

from realm.features import Feature
from realm.std.building.admin import (
    cmd_boot,
    cmd_chown,
    cmd_destroy,
    cmd_examine_full,
    cmd_find,
    cmd_nuke,
    cmd_teleport,
)
from realm.std.building.area import (
    cmd_areas,
    cmd_export,
    cmd_import,
    cmd_pack,
)
from realm.std.building.create import (
    cmd_create,
    cmd_dig,
    cmd_link,
    cmd_open,
    cmd_pair,
    cmd_unlink,
)
from realm.std.building.debug import (
    cmd_eval,
    cmd_events,
    cmd_foreach,
    cmd_quell,
    cmd_reload,
    cmd_rolls,
    cmd_stats,
)
from realm.std.building.modify import (
    cmd_attr,
    cmd_desc,
    cmd_detail,
    cmd_keyid,
    cmd_lock,
    cmd_name,
    cmd_parent,
    cmd_set,
    cmd_tag,
    cmd_unlock,
    cmd_untag,
    cmd_wipe,
)
from realm.std.building.scripting import (
    cmd_behavior,
    cmd_clone,
    cmd_force,
    cmd_trigger,
    cmd_zone,
)

feature = Feature(
    'building',
    requires=['look'],
    doc='The @-commands for building and administering the world.',
)

feature.command(
    '@create',
    cmd_create,
    permission='builder',
    category='building',
    help_text='Create a new object',
    usage='@create <name> [= <parent>]',
    parse_equals=True,
)
feature.command(
    '@dig',
    cmd_dig,
    permission='builder',
    category='building',
    help_text='Create a new room with exits',
    usage='@dig <room name> [= <exit1>, <exit2>]',
    parse_equals=True,
)
feature.command(
    '@open',
    cmd_open,
    permission='builder',
    category='building',
    help_text='Create an exit to a room',
    usage='@open <exit name> = <destination>',
    parse_equals=True,
)
feature.command(
    '@pair',
    cmd_pair,
    permission='builder',
    category='building',
    help_text='Marry two exits as the faces of one door',
    usage='@pair <exit> [= <far exit>]',
    parse_equals=True,
)
feature.command(
    '@link',
    cmd_link,
    permission='builder',
    category='building',
    help_text='Link an exit to a destination',
    usage='@link <exit> = <destination>',
    parse_equals=True,
)
feature.command(
    '@unlink',
    cmd_unlink,
    permission='builder',
    category='building',
    help_text='Unlink an exit',
    usage='@unlink <exit>',
)
feature.command(
    '@desc',
    cmd_desc,
    aliases=['@describe'],
    permission='builder',
    category='building',
    help_text="Set an object's description",
    usage='@desc <object> = <description>',
    parse_equals=True,
)
feature.command(
    '@name',
    cmd_name,
    permission='builder',
    category='building',
    help_text='Rename an object',
    usage='@name <object> = <new name>',
    parse_equals=True,
)
feature.command(
    '@set',
    cmd_set,
    permission='builder',
    category='building',
    help_text='Set an attribute on an object',
    usage='@set <object>/<attr> = <value>',
    parse_equals=True,
)
feature.command(
    '@keyid',
    cmd_keyid,
    permission='builder',
    category='building',
    help_text='Give an object a unique friendly handle ($keyid)',
    usage='@keyid <object> [= <keyid>]',
    parse_equals=True,
)
feature.command(
    '@wipe',
    cmd_wipe,
    permission='builder',
    category='building',
    help_text='Clear all attributes from an object',
    usage='@wipe <object>',
)
feature.command(
    '@parent',
    cmd_parent,
    permission='builder',
    category='building',
    help_text="Set an object's parent",
    usage='@parent <object> = <parent>',
    parse_equals=True,
)
feature.command(
    '@tag',
    cmd_tag,
    permission='builder',
    category='building',
    help_text='Add a tag to an object',
    usage='@tag <object> = <tag>',
    parse_equals=True,
)
feature.command(
    '@untag',
    cmd_untag,
    permission='builder',
    category='building',
    help_text='Remove a tag from an object',
    usage='@untag <object> = <tag>',
    parse_equals=True,
)
feature.command(
    '@attr',
    cmd_attr,
    permission='builder',
    category='building',
    help_text='Flag attributes: secret, visual, safe, no_clone, public',
    usage='@attr <object>/<attr> = <flag>[, ...]',
    parse_equals=True,
)
feature.command(
    '@detail',
    cmd_detail,
    permission='builder',
    category='building',
    help_text='Add a per-viewer conditional description line',
    usage='@detail <object> = [<condition> ->] <text>',
    parse_equals=True,
)
feature.command(
    '@lock',
    cmd_lock,
    permission='builder',
    category='building',
    help_text='Set a lock on an object',
    usage='@lock[/<type>] <object> = <expression>',
    parse_equals=True,
)
feature.command(
    '@unlock',
    cmd_unlock,
    permission='builder',
    category='building',
    help_text='Remove all locks from an object',
    usage='@unlock <object>',
)
feature.command(
    '@teleport',
    cmd_teleport,
    aliases=['@tel'],
    permission='builder',
    category='building',
    help_text='Teleport to a location',
    usage='@teleport [<object> =] <destination>',
    parse_equals=True,
)
feature.command(
    '@chown',
    cmd_chown,
    permission='admin',
    category='building',
    help_text='Change ownership of an object',
    usage='@chown <object> = <new owner>',
    parse_equals=True,
)
feature.command(
    '@destroy',
    cmd_destroy,
    aliases=['@recycle'],
    permission='builder',
    category='building',
    help_text='Destroy an object',
    usage='@destroy <object>',
)
feature.command(
    '@nuke',
    cmd_nuke,
    permission='admin',
    category='building',
    help_text='Destroy a player object',
    usage='@nuke <player>',
)
feature.command(
    '@find',
    cmd_find,
    aliases=['@search'],
    permission='builder',
    category='building',
    help_text='Search for objects',
    usage='@find[/tag|/owner] <search>',
)
feature.command(
    '@examine',
    cmd_examine_full,
    aliases=['@ex'],
    permission='builder',
    category='building',
    help_text='Show detailed object information',
    usage='@examine <object>',
)
feature.command(
    '@boot',
    cmd_boot,
    permission='admin',
    category='building',
    help_text='Disconnect a player',
    usage='@boot <player>',
)
feature.command(
    '@behavior',
    cmd_behavior,
    aliases=['@behaviors'],
    permission='builder',
    category='building',
    help_text='Attach, detach, or list behaviors on an object',
    usage='@behavior <object> [= <behavior_id>, key:value, ...]',
    parse_equals=True,
)
feature.command(
    '@clone',
    cmd_clone,
    permission='builder',
    category='building',
    help_text='Duplicate an object with its attributes, tags, and behaviors',
    usage='@clone <object> [= <new name>]',
    parse_equals=True,
)
feature.command(
    '@zone',
    cmd_zone,
    permission='builder',
    category='building',
    help_text='Manage zones: membership, masters, room lists',
    usage='@zone <object> [= <zone>]',
    parse_equals=True,
)
feature.command(
    '@force',
    cmd_force,
    permission='builder',
    category='building',
    help_text='Make something you control execute a command',
    usage='@force <target> = <command>',
    parse_equals=True,
)
feature.command(
    '@tr',
    cmd_trigger,
    aliases=['@trigger'],
    permission='builder',
    category='building',
    help_text="Run the script stored in an object's attribute",
    usage='@tr <object>/<attribute>',
)
feature.command(
    '@areas',
    cmd_areas,
    permission='builder',
    category='building',
    help_text='List importable area files',
    usage='@areas',
)
feature.command(
    '@pack',
    cmd_pack,
    permission='builder',
    category='building',
    help_text='List or import built-in content packs (classes/skills/gear)',
    usage='@pack [<name>]',
)
feature.command(
    '@export',
    cmd_export,
    permission='builder',
    category='building',
    help_text='Export a zone to an area file',
    usage='@export <zone>',
)
feature.command(
    '@import',
    cmd_import,
    permission='builder',
    category='building',
    help_text='Import an area (plan; /apply to execute)',
    usage='@import[/apply] <name>',
)
feature.command(
    '@eval',
    cmd_eval,
    aliases=['@ev'],
    permission='builder',
    category='building',
    help_text='Run arbitrary softcode and report the result',
    usage='@eval <code>',
)
feature.command(
    '@reload',
    cmd_reload,
    permission='builder',
    category='building',
    help_text='Re-read data-driven rules (skill_def/class_def) from the world',
    usage='@reload',
)
feature.command(
    '@foreach',
    cmd_foreach,
    permission='builder',
    category='building',
    help_text='Run a command for every matching object (%o = #id)',
    usage='@foreach <search> = <command>',
    parse_equals=True,
)
feature.command(
    '@stats',
    cmd_stats,
    aliases=['@metrics'],
    permission='builder',
    category='building',
    help_text='Live engine metrics (tick, behaviors, combat)',
    usage='@stats',
)
feature.command(
    '@rolls',
    cmd_rolls,
    permission='builder',
    category='building',
    help_text='Toggle skill-roll visibility for yourself',
    usage='@rolls [on|off]',
)
feature.command(
    'quell',
    cmd_quell,
    category='utility',
    help_text='Drop to mortal perception/authority',
    usage='quell',
)
feature.command(
    'unquell',
    cmd_quell,
    category='utility',
    help_text='Restore full powers after quell',
    usage='unquell',
)
feature.command(
    '@events',
    cmd_events,
    permission='builder',
    category='building',
    help_text='List the event hooks this world fires',
    usage='@events',
)
