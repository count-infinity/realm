"""
Softcode functions: Attribute reads and writes.

Each function is registered with ``@softfn``; one that takes the run's
``ScriptFrame`` as ``frame`` reads the executor, enactor, store and queue
from it. See ``realm/scripting/registry.py`` for the flags.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from realm.core.attrflags import PROTECTED_ATTRS
from realm.scripting.registry import softfn

if TYPE_CHECKING:
    from realm.core.objects import GameObject

@softfn(group='Objects & attributes', readonly=True)
def get_attr(
    frame,
    obj: GameObject | str | None,
    attr_name: str,
    default: Any = None,
) -> Any:
    """Get an attribute from an object.

    Example: get_attr(enactor, 'hp', 0)
    """
    if str(attr_name) in PROTECTED_ATTRS:
        return default
    target = frame.resolve(obj)
    if target is None:
        return default
    from realm.core.attrflags import readable_attr
    if not readable_attr(target, str(attr_name), frame.executor):
        return default
    return target.db.get(attr_name, default)

@softfn(group='Objects & attributes')
def set_attr(
    frame,
    obj: GameObject | str | None,
    attr_name: str,
    value: Any,
) -> bool:
    """
    Set an attribute on an object the executor controls.

    Returns True on success, False on failure (including no
    authority — see docs/design/engine_vision.md).

    Example: set_attr(me, 'visits', get_attr(me, 'visits', 0) + 1)
    """
    from realm.core import ops
    target = frame.resolve(obj)
    return target is not None and frame.apply(
        ops.set_attr, target, str(attr_name), value) is not None


@softfn(group='Objects & attributes', readonly=True)
def has_attr(frame, obj: GameObject | str | None, attr_name: str) -> bool:
    """Check if an object has an attribute.

    Example: has_attr(me, 'charged')
    """
    if str(attr_name) in PROTECTED_ATTRS:
        return False
    target = frame.resolve(obj)
    if target is None:
        return False
    from realm.core.attrflags import readable_attr
    if not readable_attr(target, str(attr_name), frame.executor):
        return False
    return attr_name in target.db

@softfn(group='Objects & attributes')
def del_attr(frame, obj: GameObject | str | None, attr_name: str) -> bool:
    """Delete an attribute from an object the executor controls.

    Example: del_attr(me, 'charged')
    """
    from realm.core import ops
    target = frame.resolve(obj)
    if target is None:
        return False
    result = frame.apply(ops.del_attr, target, str(attr_name))
    return bool(result is not None and result.value)


@softfn(group='Objects & attributes', readonly=True)
def V(frame, attr_name: str, default: Any = None) -> Any:
    """Read an attribute off ``me`` (the executor) — the common case.

    Shorthand for ``get_attr(me, attr_name, default)`` (PennMUSH ``v()``
    parity). Honors the same read flags as get_attr.

    Example: V('cost', 10)   # == get_attr(me, 'cost', 10)
    """
    return frame.get_attr(frame.executor, attr_name, default)

@softfn(group='Objects & attributes')
def incr(frame, attr_name: str, by: Any = 1, default: Any = 0) -> Any:
    """Increment a numeric attribute on ``me`` and return the new value.

    Shorthand for ``set_attr(me, k, get_attr(me, k, default) + by)`` that
    also hands back the result. Returns None if the write is refused (no
    authority or the attribute is not writable). Non-numeric current
    values fall back to ``default``.

    ``default`` is what an *unset* attribute counts as — and it matters
    more than it looks. Plenty of counters don't start at 0: a lot number
    whose first lot is #1, a freshness meter that starts full at 6. Pass
    the same default the read would have used, or the first bump silently
    lands one short:

        incr('next_lot', default=1)      # first lot is 2, not 1
        decr('freshness', default=6)     # an unset meter is full

    Get this backwards and you break things quietly in the other
    direction too: a counter of things *in flight* (pending timers, open
    sessions) means **zero** when unset, and giving it `default=1` leaves
    a phantom that never drains. Match the read; don't guess.

    Example: incr('visits')             # +1 from 0, returns the new count
             incr('charge', 5)
             incr('next_lot', default=1)
    """
    current = frame.get_attr(frame.executor, attr_name, default)
    if not isinstance(current, (int, float)) or isinstance(current, bool):
        current = default
    new_value = current + by
    if frame.set_attr(frame.executor, attr_name, new_value):
        return new_value
    return None

@softfn(group='Objects & attributes')
def decr(frame, attr_name: str, by: Any = 1, default: Any = 0) -> Any:
    """Decrement a numeric attribute on ``me`` and return the new value.

    The mirror of :meth:`incr`, including its ``default`` (what an unset
    attribute counts as). Returns None if the write is refused.

    Example: decr('ammo')                  # -1 from 0
             decr('breath', default=3)     # an unset meter starts full
    """
    return frame.incr(attr_name, -by, default=default)
