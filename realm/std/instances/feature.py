"""
The ``instances`` feature.

Instanced copies of template areas.
"""

from __future__ import annotations

from realm.core import instances
from realm.features import Feature
from realm.std.instances import softcode

feature = Feature(
    'instances',
    doc='Instanced copies of template areas.',
)

# Private space: every walker may land in a different copy, so flee refuses
# these exits.
feature.dest_resolver(instances.RESOLVER_NAME, instances.resolve_instance_exit,
                      shared_destination=False)
feature.reaper(instances.reap_idle)


async def _enter(engine, frame, obj, payload) -> None:
    """Queued by softcode enter_instance()."""
    import logging
    store = engine.store
    if store is None:
        return
    template, mode, return_room_id, ttl = payload
    return_room = store.get_cached(return_room_id) if return_room_id else None
    kwargs = {'mode': mode, 'return_room': return_room}
    if ttl is not None:
        kwargs['idle_ttl'] = ttl
    if await instances.enter(template, obj, store, **kwargs) is None:
        logging.getLogger(__name__).warning(
            f"enter_instance({template!r}) for {obj.name}: no entry room "
            f"materialized; move dropped")


feature.queue_kind("enter_instance", _enter)


# --- softcode ------------------------------------------------------------------

feature.softfn(softcode.enter_instance, group='Movement & travel')
