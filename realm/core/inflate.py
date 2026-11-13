"""
One way to build a GameObject from data.

A *spec* is a plain dict: ``name``, ``description``, ``tags``, ``attrs``,
``locks`` and ``behaviors`` (each ``{"behavior_id": ..., "params": ...}``).
Prototypes, area files, database rows, clones and wilderness cells all
become objects through :func:`inflate`, so they agree on what an unknown
behavior means.

References between objects (location, owner, parent) are not part of a
spec: they need the world to resolve, so the caller sets them.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)


def inflate(spec: dict[str, Any], *, obj_id: str | None = None,
            strict_behaviors: bool = False) -> GameObject:
    """Build a GameObject from ``spec``.

    ``strict_behaviors=False`` (loading saved data) keeps a behavior whose
    id has no class as an inert placeholder, because its ``behavior_def``
    may load later; ``report_unresolved`` reports it after the load.
    ``strict_behaviors=True`` (spawning, cloning, creating) drops such a
    behavior; every dropped id is reported in one WARNING.
    """
    from realm.core.behaviors import BehaviorRegistry
    from realm.core.objects import GameObject

    kwargs: dict[str, Any] = {}
    if obj_id is not None:
        kwargs['id'] = obj_id
    obj = GameObject(
        name=str(spec.get('name', 'thing')),
        description=str(spec.get('description', '') or ''),
        tags=[str(t) for t in (spec.get('tags') or [])],
        **kwargs,
    )
    for key, value in (spec.get('attrs') or {}).items():
        obj.db.set(str(key), value)
    for lock_type, expression in (spec.get('locks') or {}).items():
        obj.locks[str(lock_type)] = str(expression)

    unknown: list[str] = []
    for entry in spec.get('behaviors') or []:
        behavior_id = entry.get('behavior_id')
        params = dict(entry.get('params') or {})
        if not behavior_id:
            continue
        if strict_behaviors:
            behavior = BehaviorRegistry.create(str(behavior_id), **params)
        else:
            behavior = BehaviorRegistry.from_dict(
                {'behavior_id': behavior_id, 'params': params})
        if behavior is None:
            unknown.append(str(behavior_id))
            continue
        obj.add_behavior(behavior)
    if unknown:
        logger.warning(
            f"{obj.name}: dropped unknown behavior(s) {', '.join(sorted(set(unknown)))} "
            f"(no registered class and no behavior_def). Is the feature that "
            f"declares them in FEATURES?")
    return obj


__all__ = ["inflate"]
