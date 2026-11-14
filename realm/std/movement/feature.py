"""
The ``movement`` feature.

Walking through exits: go, the directions and their abbreviations, and a
typed exit name.
"""

from __future__ import annotations

from realm.features import Feature
from realm.std.movement.commands import cmd_direction, cmd_go, walk_typed_exit

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
# The directions and their abbreviations ('n' is north).
_DIRECTIONS = [
    ('north', 'n'), ('south', 's'), ('east', 'e'), ('west', 'w'),
    ('up', 'u'), ('down', 'd'),
    ('northeast', 'ne'), ('northwest', 'nw'),
    ('southeast', 'se'), ('southwest', 'sw'),
]
for _name, _short in _DIRECTIONS:
    feature.command(_name, cmd_direction, aliases=[_short], category='general',
                    help_text=f'Go {_name}')
feature.command('in', cmd_direction, category='movement', help_text='Go in')
feature.command('out', cmd_direction, category='movement', help_text='Go out')

# A line that names an exit of the room walks through it ("vault",
# "fire escape"), after every command and before softcode $-commands.
feature.fallback(walk_typed_exit)


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
