"""
The ``stealth`` feature.

Hiding, searching and lockpicking.
"""

from __future__ import annotations

from realm.commands.builtin.manipulation import cmd_hide, cmd_pick, cmd_search
from realm.core.perception import stealth_observer
from realm.features import Feature

feature = Feature(
    'stealth',
    requires=['rules', 'items'],
    doc='Hiding, searching and lockpicking.',
)

feature.command('hide', cmd_hide, category='items', help_text='Hide (Stealth check)', usage='hide')
feature.command(
    'search',
    cmd_search,
    category='items',
    help_text='Search for the hidden (Observation check)',
    usage='search',
)
feature.command(
    'pick',
    cmd_pick,
    category='items',
    help_text='Pick a lock with skill',
    usage='pick <target>',
)

# Loud actions break stealth, whoever performs them.
feature.observer(stealth_observer)
