"""
Softcode functions: Locks and entitlements.

Each function is registered with ``@softfn``; one that takes the run's
``ScriptFrame`` as ``frame`` reads the executor, enactor, store and queue
from it. See ``realm/scripting/registry.py`` for the flags.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.scripting.registry import softfn

if TYPE_CHECKING:
    from realm.core.objects import GameObject

@softfn(group='Locks & permissions', readonly=True)
def has_entitlement(frame, obj: GameObject | str | None,
                    entitlement: str) -> bool:
    """Whether an object holds a permission entitlement (read-only).

    The capability layer under roles: instead of asking "is this an
    admin?", ask what you actually mean. Built-in roles grant the classic
    sets; a game's own `role_def` ranks may grant them too, including names
    the game invents for its own checks.

    Example: has_entitlement(enactor, 'SEE_ALL') or has_entitlement(enactor, 'SMUGGLE')
    """
    from realm.permissions.roles import has_entitlement
    target = frame.resolve(obj)
    return has_entitlement(target, str(entitlement)) if target else False

@softfn(group='Locks & permissions')
def set_lock(
    frame,
    obj: GameObject | str | None,
    lock_type: str,
    expression: str,
) -> bool:
    """Set a lock on an object the executor controls (validated).

    Example: set_lock(me, 'basic', "caller.has_tag('keyholder')")
    """
    from realm.core import ops
    target = frame.resolve(obj)
    return target is not None and frame.apply(
        ops.set_lock, target, str(lock_type), str(expression)) is not None


@softfn(group='Locks & permissions')
def clear_lock(frame, obj: GameObject | str | None, lock_type: str) -> bool:
    """Clear a lock from an object the executor controls.

    Example: clear_lock(me, 'basic')
    """
    from realm.core import ops
    target = frame.resolve(obj)
    if target is None:
        return False
    result = frame.apply(ops.clear_lock, target, str(lock_type))
    return bool(result is not None and result.value)


@softfn(group='Locks & permissions', readonly=True)
def test_lock(
    frame,
    obj: GameObject | str | None,
    lock_type: str,
    caller: GameObject | str | None = None,
) -> bool:
    """Would ``caller`` (default: the executor) pass this lock?

    Example: test_lock('vault door', 'enter')
    """
    from realm.permissions.locks import check_lock as _check_lock

    target = frame.resolve(obj)
    who = frame.resolve(caller) if caller is not None else frame.executor
    if target is None or who is None:
        return False
    try:
        return _check_lock(target, str(lock_type), who)
    except ValueError:
        return False
