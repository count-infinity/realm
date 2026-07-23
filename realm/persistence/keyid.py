"""
Keyid index — the friendly, unique, opt-in handle layer over the canonical
uuid (docs/design/object-identity.md).

Most objects have no keyid and never touch this index; a handful of
well-known singletons (a bank core, a weather master, a zone controller)
carry one so builders can reference them as ``get('$banknet_core')`` instead
of by a collision-prone name or an opaque uuid. The keyid lives in the
object's ``keyid`` db attribute (so it persists like any other), and this
class is the ``{keyid -> obj_id}`` map that makes lookup O(1).

Design invariants:

- **Cache-validated reads.** ``holder()`` resolves the stored id through the
  live cache and re-checks the object still carries that keyid, so a stale
  entry left by a delete or a re-key self-heals to "no holder" — no separate
  release bookkeeping is required for correctness.
- **Conflict, never merge.** ``claim()`` binds a keyid only if no *different*
  live object already holds it; a genuine two-objects-one-keyid clash is
  reported, never silently overwritten. Re-claiming the same keyid on the same
  object is idempotent (the re-import / re-save case).
- **First-wins on load.** ``index()`` (the load/register path) records a
  keyid unless a live object already holds it, so reloading a well-formed
  world is a no-op and pre-corrupted duplicates don't crash the boot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from realm.core.objects import GameObject

#: The db attribute every keyid lives in. Protected from `@set`/`set_attr`
#: (only `@keyid` writes it) and never copied by `@clone`.
KEYID_ATTR = "keyid"


class KeyidIndex:
    """A ``{keyid -> obj_id}`` map validated against a live object cache.

    Constructed with a ``resolve`` callable (``obj_id -> GameObject | None``,
    i.e. the store's ``get_cached``) so it can validate holders without owning
    the cache itself.
    """

    def __init__(self, resolve: Callable[[str], "GameObject | None"]) -> None:
        self._map: dict[str, str] = {}
        self._resolve = resolve

    def index(self, obj: "GameObject") -> None:
        """Record obj's current keyid (load/register path, first-wins).

        A no-op if obj has no keyid or a *different* live object already holds
        it — the write paths (`claim`) are what enforce uniqueness; this only
        rebuilds the map as objects enter the cache.
        """
        kid = obj.db.get(KEYID_ATTR)
        if not kid:
            return
        existing = self._map.get(kid)
        if existing and existing != obj.id and self._resolve(existing) is not None:
            return
        self._map[kid] = obj.id

    def holder(self, keyid: str) -> "GameObject | None":
        """The live object holding ``keyid``, or None.

        Self-healing: a stored id that no longer resolves, or resolves to an
        object that has since been re-keyed, counts as no holder.
        """
        if not keyid:
            return None
        oid = self._map.get(keyid)
        obj = self._resolve(oid) if oid else None
        if obj is not None and obj.db.get(KEYID_ATTR) == keyid:
            return obj
        return None

    def claim(self, obj: "GameObject", keyid: str) -> tuple[bool, str]:
        """Bind ``keyid`` to ``obj``. Returns ``(ok, reason)``.

        Conflict (``ok=False``) iff a *different* live object already holds the
        keyid — reported, never merged. Re-claiming the same object's own keyid
        is idempotent. Updates the map only; the caller writes the db attribute.
        """
        holder = self.holder(keyid)
        if holder is not None and holder.id != obj.id:
            return False, (f"keyid '{keyid}' already belongs to "
                           f"{holder.name} (#{holder.id[:8]})")
        prev = obj.db.get(KEYID_ATTR)
        if prev and prev != keyid:
            self._map.pop(prev, None)
        self._map[keyid] = obj.id
        return True, ""

    def release(self, obj: "GameObject") -> None:
        """Drop obj's keyid from the map (the `@keyid <obj> =` clear path)."""
        kid = obj.db.get(KEYID_ATTR)
        if kid and self._map.get(kid) == obj.id:
            self._map.pop(kid, None)


__all__ = ["KeyidIndex", "KEYID_ATTR"]
