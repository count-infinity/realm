"""
World queries: one function, three surfaces.

``find_objects`` filters the in-memory identity map (the whole world is
cached — a scan is ~15ms per 100K objects, fine for command-frequency
use). Filters compose with AND. Surfaces: the builder's ``@find``
switches, softcode's ``search_world``, and direct engine use.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.objects import GameObject

_UNSET = object()


def find_objects(
    objects: list[GameObject] | None = None,
    *,
    tag: str | None = None,
    tags: list[str] | None = None,
    attr: str | None = None,
    value: Any = _UNSET,
    name_like: str | None = None,
    limit: int | None = None,
) -> list[GameObject]:
    """
    Filter the world (or a provided list). All given filters must match:

        tag / tags   object carries the tag(s)
        attr         object has the attribute; with ``value``, it must equal
        name_like    case-insensitive substring of the name
        limit        cap the result count
    """
    if objects is None:
        from realm.persistence.manager import get_active_manager
        manager = get_active_manager()
        objects = manager.all_cached() if manager else []

    wanted_tags = list(tags or [])
    if tag:
        wanted_tags.append(tag)
    needle = name_like.lower() if name_like else None

    results: list[GameObject] = []
    for obj in objects:
        if wanted_tags and not all(obj.has_tag(t) for t in wanted_tags):
            continue
        if attr is not None:
            if attr not in obj.db:
                continue
            if value is not _UNSET and obj.db.get(attr) != value:
                continue
        if needle is not None and needle not in obj.name.lower():
            continue
        results.append(obj)
        if limit is not None and len(results) >= limit:
            break
    return results


__all__ = ["find_objects"]
