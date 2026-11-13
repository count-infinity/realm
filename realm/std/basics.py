"""
The ``basics`` feature.

Session and utility commands: help, who, quit, time.
"""

from __future__ import annotations

from realm.commands.builtin.utility import (
    cmd_color,
    cmd_commands,
    cmd_help,
    cmd_logout,
    cmd_quit,
    cmd_recall,
    cmd_think,
    cmd_time,
    cmd_uptime,
    cmd_who,
)
from realm.features import Feature

feature = Feature(
    'basics',
    doc='Session and utility commands: help, who, quit, time.',
)

feature.command(
    'help',
    cmd_help,
    aliases=['?'],
    category='utility',
    help_text='Show help on commands',
    usage='help [command]',
)
feature.command(
    'commands',
    cmd_commands,
    category='utility',
    help_text='List all available commands',
)
feature.command('who', cmd_who, category='utility', help_text='Show who is online')
feature.command(
    'quit',
    cmd_quit,
    aliases=['quit'],
    category='utility',
    help_text='Disconnect from the game',
)
feature.command(
    'logout',
    cmd_logout,
    category='utility',
    help_text='Leave your character, back to the connection screen',
    usage='logout',
)
feature.command(
    'color',
    cmd_color,
    category='utility',
    help_text='Toggle color output',
    usage='color on|off',
)
feature.command(
    'think',
    cmd_think,
    category='utility',
    help_text='Think to yourself',
    usage='think <thought>',
)
feature.command('time', cmd_time, category='utility', help_text='Show the current time')
feature.command(
    'uptime',
    cmd_uptime,
    permission='builder',
    category='utility',
    help_text='Show server uptime',
)
feature.command('recall', cmd_recall, category='utility', help_text='Return to your home')
