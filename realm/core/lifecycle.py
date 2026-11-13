"""
One destroy path.

Every way an object leaves the world — ``@destroy``, ``@nuke``, softcode
``destroy_obj()``, expiry reaping, the load-time orphan sweep — goes through
``destroy_object`` so the rules cannot drift between them:

- a **player** is never destroyed unless the caller says so (``@nuke``);
- a ``safe``-tagged object is never destroyed;
- a destroyed **exit** dissolves its pairing, so the far side is not left
  pointing at a deleted door;
- **contents** get the R9 disposition of ``core.teardown`` (players
  evacuated, player-owned property sent to its owner's refuge, everything
  else destroyed), or with ``contents="destroy"`` every non-player object in
  the subtree dies with it (players are still evacuated).

Batch teardowns with their own doomed sets (``instances.destroy_instance``,
the wilderness cell reaper) call ``teardown.release_contents`` directly.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from realm.core.teardown import release_contents

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)

SAFE_TAG = "safe"


class DestroyRefused(Exception):  # noqa: N818 — a refusal, not an error
    """Raised when an object may not be destroyed. ``.reason`` is shown to the actor."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def check_destroy(obj: GameObject, *, allow_player: bool = False) -> None:
    """Raise DestroyRefused for a player (unless ``allow_player``) or a
    ``safe``-tagged object."""
    if obj.is_player and not allow_player:
        raise DestroyRefused(f"{obj.name} is a player. Use @nuke to destroy player objects.")
    if obj.has_tag(SAFE_TAG):
        raise DestroyRefused(f"{obj.name} is protected from destruction.")


def _subtree(root: GameObject) -> list[GameObject]:
    """Every object inside ``root``, parents before children."""
    out: list[GameObject] = []
    seen = {root.id}
    stack = list(root.contents)
    while stack:
        obj = stack.pop()
        if obj.id in seen:
            continue
        seen.add(obj.id)
        out.append(obj)
        stack.extend(obj.contents)
    return out


async def destroy_object(obj: GameObject, store, *, allow_player: bool = False,
                         contents: str = "release") -> int:
    """Destroy ``obj``. Returns how many contained objects were destroyed with it.

    ``contents="release"`` applies the R9 disposition to what ``obj`` holds;
    ``contents="destroy"`` destroys every non-player object inside it.
    Raises DestroyRefused (see ``check_destroy``) before touching anything.
    """
    if contents not in ("release", "destroy"):
        raise ValueError(f"contents must be 'release' or 'destroy', not {contents!r}")
    check_destroy(obj, allow_player=allow_player)

    if obj.is_exit:
        from realm.core.pairing import dissolve_pairing
        former = dissolve_pairing(obj)
        if former is not None and store is not None:
            await store.save(former)

    if contents == "release":
        destroyed = await release_contents(obj, store)
    else:
        doomed = [o for o in _subtree(obj) if not o.is_player]
        doomed_ids = {o.id for o in doomed}
        destroyed = await release_contents(obj, store, doomed_ids=doomed_ids)
        for victim in reversed(doomed):       # deepest first
            victim.location = None
            if store is not None:
                await store.delete(victim)
        destroyed += len(doomed)

    obj.location = None
    if store is not None:
        await store.delete(obj)
    logger.info(f"Destroyed {obj.name} ({obj.id}) and {destroyed} contained object(s)")
    return destroyed


__all__ = ["DestroyRefused", "check_destroy", "destroy_object"]
