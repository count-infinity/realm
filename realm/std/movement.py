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


@feature.script_verb("move", aliases=["go"], sugar=True,
                     doc="move <exit>: walk through an exit of the object's room")
async def _move(engine, executor, rest):
    """The full movement pathway: exit locks, closed doors, guards and
    on_leave/on_enter all apply. A blocked move is a silent no-op for the
    script; the world already told whoever should know."""
    import logging

    from realm.core.movement import (
        has_dest_resolver,
        move_through_exit,
        resolve_exit_destination,
    )
    from realm.core.search import AmbiguousMatchError, match_one
    direction = rest.strip()
    if not direction or executor.location is None:
        return
    exits = [obj for obj in executor.location.contents if obj.is_exit]
    try:
        exit_obj = match_one(direction, exits)
    except AmbiguousMatchError:
        exit_obj = None
    if exit_obj is None:
        logging.getLogger(__name__).warning(
            f"Script on {executor.name} tried to move through unknown exit {direction!r}")
        return
    destination = resolve_exit_destination(exit_obj)
    if destination is None and not has_dest_resolver(exit_obj):
        return
    await move_through_exit(executor, destination, exit_obj=exit_obj)
