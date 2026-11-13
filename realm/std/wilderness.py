"""
The ``wilderness`` feature.

Procedural wilderness cells behind map-provider regions.
"""

from __future__ import annotations

from realm.core import wilderness
from realm.features import Feature

feature = Feature(
    'wilderness',
    requires=['spawning'],
    doc='Procedural wilderness cells behind map-provider regions.',
)

feature.dest_resolver(wilderness.RESOLVER_NAME, wilderness.resolve_wilderness_exit)
feature.reaper(wilderness.reap_wilderness)


async def _enter(engine, frame, obj, payload) -> None:
    """Queued by softcode enter_wilderness()."""
    import logging
    store = engine.store
    if store is None:
        return
    region, x, y = payload
    if await wilderness.enter_cell(obj, region, x, y, store) is None:
        logging.getLogger(__name__).warning(
            f"enter_wilderness({region!r}, {x}, {y}) for {obj.name}: no cell "
            f"materialized; move dropped")


feature.queue_kind("wilderness", _enter)
