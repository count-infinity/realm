"""
Softcode functions: Behaviors and puppeting.

Each function is registered with ``@softfn``; one that takes the run's
``ScriptFrame`` as ``frame`` reads the executor, enactor, store and queue
from it. See ``realm/scripting/registry.py`` for the flags.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from realm.scripting.registry import softfn

if TYPE_CHECKING:
    from realm.core.objects import GameObject

@softfn(group='NPCs & behaviors')
def behaviors(frame, obj: GameObject | str | None) -> list[str]:
    """Behavior ids attached to an object.

    Example: 'wandering' in behaviors('rat')
    """
    target = frame.resolve(obj)
    if target is None:
        return []
    return [b.behavior_id for b in target.get_behaviors()]

@softfn(group='NPCs & behaviors')
def attach_behavior(
    frame,
    obj: GameObject | str | None,
    behavior_id: str,
    **params: Any,
) -> bool:
    """Attach a registered behavior to an object the executor controls.
    Like ``@behavior``, it also needs builder authority (BUILD) behind the
    executor: a mortal player's gadget cannot attach behaviors; unowned
    world objects and NPCs can.

    Example: attach_behavior('golem', 'script_ticker', interval=5)
    """
    from realm.core import ops
    target = frame.resolve(obj)
    return target is not None and frame.apply(
        ops.attach_behavior, target, str(behavior_id), params) is not None


@softfn(group='NPCs & behaviors')
def detach_behavior(frame, obj: GameObject | str | None, behavior_id: str) -> bool:
    """Detach a behavior (by id) from an object the executor controls (needs
    BUILD behind the executor, like ``attach_behavior``).

    Example: detach_behavior('golem', 'wandering')
    """
    from realm.core import ops
    target = frame.resolve(obj)
    return target is not None and frame.apply(
        ops.detach_behavior, target, str(behavior_id)) is not None


@softfn(group='NPCs & behaviors')
def force(frame, obj: GameObject | str | None, command: str) -> bool:
    """
    Make something the executor controls run a command (queued;
    executes through the real dispatcher after the script). The
    possession primitive — see @force.

    Example: force('minion', 'say Yes, master.')
    """
    target = frame.controlled(obj)
    if target is None:
        return False
    frame.command_queue.append(('force', target, str(command)))
    return True
