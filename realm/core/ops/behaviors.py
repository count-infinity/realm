"""
Ops that attach, detach and configure behaviors.

Control of the object is not enough: a behavior is code that runs as the
object forever, so the actor's responsible principal must also hold BUILD
(see :func:`realm.core.ops.may_build`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from realm.core.ops import Invalid, NotAllowed, OpResult, may_build, require_control

if TYPE_CHECKING:
    from realm.core.behaviors import Behavior
    from realm.core.objects import GameObject


def _require_build(actor: GameObject | None, obj: GameObject) -> None:
    require_control(actor, obj)
    if not may_build(actor):
        raise NotAllowed("Attaching behaviors needs builder authority (BUILD).")


def _attached(obj: GameObject, behavior_id: str) -> Behavior | None:
    for behavior in obj.get_behaviors():
        if behavior.behavior_id == behavior_id:
            return behavior
    return None


def check_attach_behavior(actor: GameObject | None, obj: GameObject,
                          behavior_id: str) -> None:
    from realm.core.behaviors import BehaviorRegistry
    from realm.scripting.scripted_behavior import find_behavior_def
    _require_build(actor, obj)
    if (BehaviorRegistry.get(str(behavior_id)) is None
            and find_behavior_def(str(behavior_id)) is None):
        known = ", ".join(sorted(BehaviorRegistry.list_all()))
        raise Invalid(f"Unknown behavior '{behavior_id}' (no registered behavior or "
                      f"behavior_def object by that name). Registered: {known}")


def attach_behavior(actor: GameObject | None, obj: GameObject, behavior_id: str,
                    params: dict[str, Any] | None = None) -> OpResult:
    """Attach a behavior by id. ``value`` is the new behavior."""
    from realm.core.behaviors import BehaviorRegistry
    check_attach_behavior(actor, obj, behavior_id)
    behavior = BehaviorRegistry.create(str(behavior_id), **(params or {}))
    if behavior is None:                 # defensive: the check found it
        raise Invalid(f"Unknown behavior '{behavior_id}'.")
    obj.add_behavior(behavior)
    return OpResult(value=behavior, touched=[obj])


def check_detach_behavior(actor: GameObject | None, obj: GameObject,
                          behavior_id: str) -> None:
    _require_build(actor, obj)
    if _attached(obj, str(behavior_id)) is None:
        raise Invalid(f"{obj.name} has no '{behavior_id}' behavior.")


def detach_behavior(actor: GameObject | None, obj: GameObject, behavior_id: str) -> OpResult:
    """Detach the first behavior with this id."""
    check_detach_behavior(actor, obj, behavior_id)
    obj.remove_behavior(_attached(obj, str(behavior_id)))
    return OpResult(value=True, touched=[obj])


def check_configure_behavior(actor: GameObject | None, obj: GameObject,
                             behavior_id: str) -> None:
    _require_build(actor, obj)
    if _attached(obj, str(behavior_id)) is None:
        raise Invalid(f"{obj.name} has no '{behavior_id}' to set — attach it first.")


def configure_behavior(actor: GameObject | None, obj: GameObject, behavior_id: str,
                       params: dict[str, Any]) -> OpResult:
    """Update an attached behavior's params in place (its object state is
    kept, unlike detach and attach). ``value`` is the merged params."""
    check_configure_behavior(actor, obj, behavior_id)
    behavior = _attached(obj, str(behavior_id))
    behavior.params.update(params)
    return OpResult(value=dict(behavior.params), touched=[obj])
