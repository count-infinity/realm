"""
Timed actions (MUD_PLAN 5.5): crafting, gathering, anything that takes
time at a place.

``start_task(seconds, done_attr, label, interrupt_attr)`` makes the
enactor busy: tagged ``busy``, with a ``task`` attribute holding the label,
the finish time and what to run. When the time passes, the reaper clears it
and runs ``done_attr`` on the object that started it, with the character as
enactor. Moving, being drawn into a fight, or typing ``stop`` interrupts
it and runs ``interrupt_attr`` instead. Unlike ``wait()``, a task is stored
on the character, so it survives a reboot, and it belongs to one character.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from realm.core.action_tags import HOSTILE
from realm.core.world import find_world

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.propagation import Action

BUSY = "busy"


def now() -> float:
    """The wall clock tasks finish on (tests replace it)."""
    return time.time()


def task_info(obj: GameObject) -> dict | None:
    """``{"label", "left"}`` for a busy object (whole seconds left), else None."""
    task = obj.db.get("task")
    if not obj.has_tag(BUSY) or not isinstance(task, dict):
        return None
    return {"label": str(task.get("label") or ""),
            "left": max(0, int(float(task.get("until") or 0) - now()))}


def begin(obj: GameObject, starter: GameObject, seconds: float, done_attr: str,
          label: str = "", interrupt_attr: str | None = None) -> bool:
    """Make ``obj`` busy for ``seconds``. False when it already is."""
    if obj.has_tag(BUSY):
        return False
    obj.add_tag(BUSY)
    obj.db.task = {"label": str(label), "until": now() + float(seconds),
                   "starter": starter.id, "done": str(done_attr),
                   "interrupt": str(interrupt_attr) if interrupt_attr else None}
    return True


def _clear(obj: GameObject) -> dict | None:
    task = obj.db.get("task")
    obj.remove_tag(BUSY)
    obj.db.delete("task")
    return task if isinstance(task, dict) else None


async def _run(task: dict, which: str, obj: GameObject) -> None:
    world = find_world()
    attr = task.get(which)
    if world is None or not attr or world.scripts is None:
        return
    starter = world.store.get_cached(str(task.get("starter"))) if world.store else None
    if starter is not None:
        await world.scripts.run_object_script(starter, str(attr), enactor=obj)


async def finish(obj: GameObject) -> None:
    """The task is done: clear it and run its ``done`` script."""
    task = _clear(obj)
    if task is not None:
        await _run(task, "done", obj)


async def interrupt(obj: GameObject) -> bool:
    """Break off ``obj``'s task, running its ``interrupt`` script. False
    when it had none."""
    if not obj.has_tag(BUSY):
        return False
    task = _clear(obj)
    if task is not None:
        await _run(task, "interrupt", obj)
    return True


async def task_sweep(store: Any) -> None:
    """The ``tasks`` reaper: finish every task whose time has come."""
    if store is None:
        return
    moment = now()
    for obj in list(store.find_cached(tag=BUSY)):
        task = obj.db.get("task")
        if not isinstance(task, dict) or moment >= float(task.get("until") or 0):
            await finish(obj)
            await store.save(obj)


async def moved(actor: GameObject, origin, destination, exit_obj, *, fleeing: bool) -> None:
    """``feature.after_traverse``: walking away breaks off the task."""
    await interrupt(actor)


async def fight_observer(action: Action) -> None:
    """Being drawn into a fight (either side of a hostile act) breaks it off."""
    if action.blocked or HOSTILE not in action.tags:
        return
    for party in (action.actor, action.target):
        if party is not None and party.has_tag(BUSY):
            await interrupt(party)


def busy_marker(obj: GameObject, looker: GameObject | None) -> str | None:
    return "busy" if obj.has_tag(BUSY) else None


async def cmd_stop(ctx) -> None:
    """
    Stop what you are doing (a craft, a harvest).

    Usage: stop
    """
    if await interrupt(ctx.player):
        return
    from realm.core.world import get_world
    engine = get_world().scripts
    # Not busy: the line may be a world verb (a recorder's $stop).
    if engine is None or not await engine.handle_unknown_command(ctx):
        await ctx.session.send("You aren't doing anything.")


__all__ = ["BUSY", "now", "task_info", "begin", "finish", "interrupt", "task_sweep",
           "moved", "fight_observer", "busy_marker", "cmd_stop"]
