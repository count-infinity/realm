"""
The ``stealth`` feature.

Hiding, searching and lockpicking.
"""

from __future__ import annotations

from realm.features import Feature
from realm.std.stealth.commands import cmd_hide, cmd_pick, cmd_search
from realm.std.stealth.hiding import hidden_from_sight, hidden_marker, stealth_observer

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

# A hidden thing is out of sight, and an admin sees it marked (hidden).
feature.sight_rule(hidden_from_sight)
feature.marker(hidden_marker)

# Loud actions break stealth, whoever performs them.
feature.observer(stealth_observer)
