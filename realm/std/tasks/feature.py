"""
The ``tasks`` feature.

Timed actions at a place: crafting, gathering, anything that takes time
and can be broken off (MUD_PLAN 5.5; docs/guides/progression.md).
"""

from __future__ import annotations

from realm.features import Feature
from realm.std.tasks import softcode
from realm.std.tasks.tasks import (
    begin,
    busy_marker,
    cmd_stop,
    fight_observer,
    interrupt,
    moved,
    task_sweep,
)

feature = Feature(
    'tasks',
    doc='Timed actions (crafting, gathering) that a move, a fight or `stop` breaks off.',
)

feature.command('stop', cmd_stop, category='general',
                help_text='Stop what you are doing', usage='stop')
feature.reaper(task_sweep)
feature.after_traverse(moved)
feature.observer(fight_observer)
feature.marker(busy_marker)

feature.softfn(softcode.start_task, group='Time & scheduling')
feature.softfn(softcode.task_of, group='Time & scheduling', readonly=True)
feature.softfn(softcode.stop_task, group='Time & scheduling')


async def _start(engine, frame, obj, payload) -> None:
    """Queued by softcode start_task()."""
    starter, seconds, done, label, interrupt_attr = payload
    begin(obj, starter, seconds, done, label, interrupt_attr)


async def _stop(engine, frame, obj, _payload) -> None:
    """Queued by softcode stop_task()."""
    await interrupt(obj)


feature.queue_kind("task_start", _start)
feature.queue_kind("task_stop", _stop)
