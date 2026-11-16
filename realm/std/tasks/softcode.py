"""
Softcode functions: timed actions. The ``tasks`` feature declares each;
the first parameter is the run's frame.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.std.tasks.tasks import BUSY, task_info

if TYPE_CHECKING:
    from realm.core.objects import GameObject


def start_task(frame, seconds: float, done_attr: str, label: str = "",
               interrupt_attr: str | None = None) -> bool:
    """
    Make the enactor busy for ``seconds``: when the time passes, this
    object's ``done_attr`` runs with the enactor bound. Moving, a fight or
    the ``stop`` command breaks it off and runs ``interrupt_attr`` instead.
    The task is stored on the character, so it survives a reboot. False
    when the enactor is already busy (or out of reach).

    Example: start_task(10, 'smelt_done', 'smelting ore', 'smelt_stop')
    """
    who = frame.enactor
    if who is None or frame.executor is None or not frame.in_reach(who):
        return False
    if who.has_tag(BUSY) or float(seconds) < 0:
        return False
    frame.command_queue.append(('task_start', who, (frame.executor, float(seconds),
                                                    str(done_attr), str(label),
                                                    interrupt_attr)))
    return True


def task_of(frame, obj: GameObject | str | None) -> dict | None:
    """
    What a character is busy with: ``{"label": ..., "left": seconds}``, or
    None.

    Example: task_of(enactor)
    """
    target = frame.resolve(obj)
    return task_info(target) if target is not None else None


def stop_task(frame, obj: GameObject | str | None) -> bool:
    """
    Break off a character's task (its interrupt script runs). The object
    that started the task may stop it, as may anything that controls the
    character.

    Example: stop_task(enactor)
    """
    target = frame.resolve(obj)
    if target is None or not target.has_tag(BUSY):
        return False
    task = target.db.get("task") or {}
    started_here = frame.executor is not None and task.get("starter") == frame.executor.id
    if not started_here and not frame.may_mutate(target):
        return False
    frame.command_queue.append(('task_stop', target, None))
    return True


__all__ = ["start_task", "task_of", "stop_task"]
