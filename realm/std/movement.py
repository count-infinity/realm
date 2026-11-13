"""
The ``movement`` feature.

Walking through exits: go and the directions.
"""

from __future__ import annotations

from realm.commands.builtin.movement import cmd_direction, cmd_go
from realm.features import Feature

feature = Feature(
    'movement',
    doc='Walking through exits: go and the directions.',
)

feature.command(
    'go',
    cmd_go,
    category='movement',
    help_text='Move in a direction',
    usage='go <direction>',
)
feature.command('north', cmd_direction, category='general', help_text='Go north')
feature.command('south', cmd_direction, category='general', help_text='Go south')
feature.command('east', cmd_direction, category='general', help_text='Go east')
feature.command('west', cmd_direction, category='general', help_text='Go west')
feature.command('up', cmd_direction, category='general', help_text='Go up')
feature.command('down', cmd_direction, category='general', help_text='Go down')
feature.command('northeast', cmd_direction, category='general', help_text='Go northeast')
feature.command('northwest', cmd_direction, category='general', help_text='Go northwest')
feature.command('southeast', cmd_direction, category='general', help_text='Go southeast')
feature.command('southwest', cmd_direction, category='general', help_text='Go southwest')
feature.command('in', cmd_direction, category='movement', help_text='Go in')
feature.command('out', cmd_direction, category='movement', help_text='Go out')
