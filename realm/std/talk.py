"""
The ``talk`` feature.

Speech: say, pose, emit, shout, whisper.
"""

from __future__ import annotations

from realm.commands.builtin.communication import (
    cmd_emit,
    cmd_ooc,
    cmd_pose,
    cmd_say,
    cmd_semipose,
    cmd_shout,
    cmd_whisper,
)
from realm.features import Feature

feature = Feature(
    'talk',
    doc='Speech: say, pose, emit, shout, whisper.',
)

feature.command(
    'say',
    cmd_say,
    aliases=["'"],
    category='communication',
    help_text='Say something to the room',
    usage='say <message> or "<message>',
)
feature.command(
    'pose',
    cmd_pose,
    aliases=['emote'],
    category='communication',
    help_text='Emote an action',
    usage='pose <action> or :<action>',
)
feature.command(
    'semipose',
    cmd_semipose,
    category='communication',
    help_text='Emote with name attached',
    usage='semipose <action> or ;<action>',
)
feature.command(
    'emit',
    cmd_emit,
    permission='builder',
    category='communication',
    help_text='Emit a message to the room',
    usage='emit <message> or \\<message>',
)
feature.command(
    'ooc',
    cmd_ooc,
    category='communication',
    help_text='Out-of-character speech',
    usage='ooc <message>',
)
feature.command(
    'shout',
    cmd_shout,
    category='communication',
    help_text='Shout to the room (and nearby)',
    usage='shout <message>',
)
feature.command(
    'whisper',
    cmd_whisper,
    aliases=['w'],
    category='communication',
    help_text='Whisper privately to someone',
    usage='whisper <player> = <message>',
    parse_equals=True,
)
