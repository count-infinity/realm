"""
The ``look`` feature.

Looking at rooms and objects, and beyond the room (``scan``, ``exits``,
``where``). The ``autoexit`` and ``brief`` options shape how a room reads.
"""

from __future__ import annotations

from realm.features import Feature
from realm.std.look.around import cmd_exits, cmd_scan, cmd_where
from realm.std.look.commands import cmd_examine, cmd_look

feature = Feature(
    'look',
    doc='Looking at rooms and objects.',
)

feature.command(
    'look',
    cmd_look,
    aliases=['l'],
    category='looking',
    help_text='Look at your surroundings or an object',
    usage='look [target]',
)
feature.command(
    'examine',
    cmd_examine,
    aliases=['ex', 'exam'],
    category='looking',
    help_text='Examine an object in detail',
    usage='examine <target>',
)

feature.command('scan', cmd_scan, category='looking',
                help_text='See who is one room away in each direction', usage='scan')
feature.command('exits', cmd_exits, category='looking',
                help_text='List the exits here and where they lead', usage='exits')
feature.command('where', cmd_where, category='looking',
                help_text='List the players in this zone', usage='where')


@feature.on_install
def _offer_room_options(world) -> None:
    """The room renderer's two player settings (``config``)."""
    options = world.services.get("options")
    if options is not None:
        options.toggle("autoexit", "Show a room's exits when you look or arrive.", True)
        options.toggle("brief", "Leave out room descriptions as you walk "
                       "(look still shows them).", False)


@feature.on_install
def _offer_rendering(world) -> None:
    """Other features show a room through ``world.services["look"]``
    (``render_room``) when ``look`` is in the world."""
    from realm.std.look import render
    world.services["look"] = render
