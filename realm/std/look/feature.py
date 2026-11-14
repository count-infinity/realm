"""
The ``look`` feature.

Looking at rooms and objects.
"""

from __future__ import annotations

from realm.features import Feature
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
