"""
Persistence manager for saving/loading game objects.

Features:
- Async SQLite support via aiosqlite
- Simple save strategies: immediate vs deferred (batched)
- JSON serialization for attributes and complex data
- Dirty tracking for efficient saves
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiosqlite

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)


# The running server's manager — the ambient identity map (same pattern as
# the propagation-engine singleton). Set by GameServer.start(), cleared on
# stop(). Behaviors and other engine-internal code resolve object IDs
# through it when no explicit manager is in reach.
_active_manager = None


def set_active_manager(manager) -> None:
    """Install (or clear, with None) the ambient PersistenceManager."""
    global _active_manager
    _active_manager = manager


def get_active_manager():
    """The running server's PersistenceManager, if any."""
    return _active_manager


# SQL Schema
SCHEMA = """
CREATE TABLE IF NOT EXISTS objects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    location_id TEXT,
    parent_id TEXT,
    owner_id TEXT,
    tags TEXT DEFAULT '[]',
    attributes TEXT DEFAULT '{}',
    behaviors TEXT DEFAULT '[]',
    locks TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_objects_location ON objects(location_id);
CREATE INDEX IF NOT EXISTS idx_objects_owner ON objects(owner_id);
CREATE INDEX IF NOT EXISTS idx_objects_name ON objects(name);
"""


class PersistenceManager:
    """
    Manages persistence of game objects to SQLite.

    Usage:
        pm = PersistenceManager("game.db")
        await pm.initialize()

        # Save immediately
        await pm.save(obj)

        # Queue for batch save
        await pm.save_deferred(obj)

        # Load an object
        obj = await pm.load("object-id")

        # Start background flush loop
        await pm.start_flush_loop()
    """

    def __init__(self, db_path: str | Path, flush_interval: float = 5.0):
        """
        Initialize the persistence manager.

        Args:
            db_path: Path to SQLite database file
            flush_interval: Seconds between batch saves (default 5)
        """
        self.db_path = Path(db_path)
        self.flush_interval = flush_interval
        self._db: aiosqlite.Connection | None = None
        self._save_queue: asyncio.Queue[str] = asyncio.Queue()
        self._flush_task: asyncio.Task[None] | None = None
        self._object_cache: dict[str, GameObject] = {}
        # Friendly-handle layer: {keyid -> obj_id}, validated against the
        # cache on read (see realm/persistence/keyid.py). Unkeyed objects
        # never touch it, so the hot creation path is unchanged.
        from realm.persistence.keyid import KeyidIndex
        self._keyids = KeyidIndex(self.get_cached)
        self._running = False
        # obj_id -> the location_id its row named but the cache couldn't
        # resolve at load (an ephemeral room that was never persisted, or
        # a deleted one). Load-time reconcile drains this — R9's backstop
        # against objects silently reloading at location None.
        self._dangling_locations: dict[str, str] = {}

    #: bump when SCHEMA changes; add a migration step below.
    SCHEMA_VERSION = 1

    async def initialize(self) -> None:
        """Initialize the database connection and create tables."""
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        # WAL survives crashes far better than the rollback journal and
        # lets reads proceed during the flush transaction.
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA synchronous=NORMAL")
        await self._db.executescript(SCHEMA)

        async with self._db.execute("PRAGMA user_version") as cursor:
            row = await cursor.fetchone()
            db_version = int(row[0]) if row else 0
        if db_version == 0:
            await self._db.execute(
                f"PRAGMA user_version = {self.SCHEMA_VERSION}")
        elif db_version > self.SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema v{db_version} is newer than this REALM "
                f"(v{self.SCHEMA_VERSION}) — upgrade the engine.")
        # db_version < SCHEMA_VERSION: run migrations here as they exist.

        await self._db.commit()
        logger.info(f"Database initialized at {self.db_path}")

    async def close(self) -> None:
        """Close the database connection and stop the flush loop."""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Final flush
        await self._flush_queue()

        if self._db:
            await self._db.close()
            self._db = None
        logger.info("Database connection closed")

    async def start_flush_loop(self) -> None:
        """Start the background task that periodically flushes the save queue."""
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def _flush_loop(self) -> None:
        """Background loop that flushes the save queue periodically."""
        while self._running:
            await asyncio.sleep(self.flush_interval)
            try:
                await self._flush_queue()
            except Exception:
                # One bad object must not kill autosave for the rest of the
                # server's lifetime — log and keep the loop alive.
                logger.exception("Error flushing save queue; autosave continues")

    async def _flush_queue(self) -> None:
        """
        Write every dirty object to the database in one transaction.

        This is the durability contract: ANY mutation — an attribute
        write, a tag change, an item changing location — marks its object
        dirty, and the periodic flush persists it. A crash loses at most
        ``flush_interval`` seconds of play; nothing depends on gameplay
        code remembering to call save().

        The explicit save queue is drained too (kept as an API for callers
        that want to hint urgency), but the dirty sweep is what guarantees
        coverage.
        """
        if not self._db:
            return

        while not self._save_queue.empty():
            try:
                self._save_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # Ephemeral objects are never written (see _save_object), so leave
        # them out of the sweep entirely — otherwise a dirty instance room
        # would be re-swept by every flush pass for its whole life and
        # inflate the flushed count below.
        dirty = [obj for obj in self._object_cache.values()
                 if obj.is_dirty() and not obj.has_tag('ephemeral')]
        if not dirty:
            return

        for obj in dirty:
            await self._save_object(obj, commit=False)
        await self._db.commit()

        logger.debug(f"Flushed {len(dirty)} dirty objects to database")

    # --- Public API ---

    def register(self, obj: GameObject) -> None:
        """Register an object in the cache for deferred saving."""
        self._object_cache[obj.id] = obj
        self._keyids.index(obj)

    def unregister(self, obj: GameObject) -> None:
        """Remove an object from the cache."""
        self._keyids.release(obj)
        self._object_cache.pop(obj.id, None)

    # --- Friendly keyid handles (see realm/persistence/keyid.py) ---

    def keyid_holder(self, keyid: str) -> GameObject | None:
        """The live object whose keyid is ``keyid``, or None."""
        return self._keyids.holder(keyid)

    def claim_keyid(self, obj: GameObject, keyid: str) -> tuple[bool, str]:
        """Bind ``keyid`` to ``obj`` (conflict, don't merge). ``(ok, reason)``."""
        return self._keyids.claim(obj, keyid)

    def release_keyid(self, obj: GameObject) -> None:
        """Free ``obj``'s keyid (the clear path)."""
        self._keyids.release(obj)

    def get_cached(self, obj_id: str) -> GameObject | None:
        """Get a loaded object by ID without touching the database."""
        return self._object_cache.get(obj_id)

    def all_cached(self) -> list[GameObject]:
        """All loaded objects. Callers filter by tag/name as needed."""
        return list(self._object_cache.values())

    def find_cached(self, *, tag: str | None = None, name: str | None = None) -> list[GameObject]:
        """
        Find loaded objects by tag and/or exact name (case-insensitive).

        The standard lookup for "the player named X" / "everything tagged
        room" style queries, replacing direct iteration of the cache.
        """
        name_lower = name.lower() if name is not None else None
        results = []
        for obj in self._object_cache.values():
            if tag is not None and not obj.has_tag(tag):
                continue
            if name_lower is not None and obj.name.lower() != name_lower:
                continue
            results.append(obj)
        return results

    async def save(self, obj: GameObject) -> None:
        """Save an object immediately."""
        self.register(obj)
        await self._save_object(obj)

    async def save_deferred(self, obj: GameObject) -> None:
        """Queue an object for batch saving."""
        self.register(obj)
        await self._save_queue.put(obj.id)

    async def load(self, obj_id: str) -> GameObject | None:
        """Load an object by ID."""
        # Check cache first
        if obj_id in self._object_cache:
            return self._object_cache[obj_id]

        return await self._load_object(obj_id)

    async def load_all(self) -> list[GameObject]:
        """Load all objects from the database."""
        if not self._db:
            return []

        objects: list[GameObject] = []
        refs: dict[str, tuple] = {}
        async with self._db.execute("SELECT * FROM objects") as cursor:
            async for row in cursor:
                data = dict(row)
                obj = self._row_to_object(data)
                if obj:
                    self._object_cache[obj.id] = obj
                    self._keyids.index(obj)
                    objects.append(obj)
                    refs[obj.id] = (data.get('location_id'),
                                    data.get('parent_id'),
                                    data.get('owner_id'))

        # Second pass: resolve references from the ids captured during
        # the scan — one query for the whole world, not one per object.
        for obj in objects:
            self._apply_references(obj, *refs[obj.id])

        return objects

    async def delete(self, obj: GameObject) -> None:
        """Delete an object from the database and retire it from live registries."""
        # Detach behaviors first, regardless of backing store. This drops the
        # object from the tick-owner registry *immediately*, so its behaviors
        # stop ticking (and vanish from @stats) rather than lingering, phantom
        # and unreachable, until Python's cyclic GC happens to collect it.
        for behavior in obj.get_behaviors():
            obj.remove_behavior(behavior)
        if not self._db:
            return

        await self._db.execute("DELETE FROM objects WHERE id = ?", (obj.id,))
        await self._db.commit()
        self.unregister(obj)
        logger.debug(f"Deleted object {obj.id}")

    async def exists(self, obj_id: str) -> bool:
        """Check if an object exists in the database."""
        if not self._db:
            return False

        async with self._db.execute(
            "SELECT 1 FROM objects WHERE id = ?", (obj_id,)
        ) as cursor:
            return await cursor.fetchone() is not None

    # --- Internal methods ---

    async def _save_object(self, obj: GameObject, commit: bool = True) -> None:
        """
        Save a single object to the database.

        ``commit=False`` lets the flush loop batch many objects into one
        transaction and commit once.
        """
        if not self._db:
            return

        # Ephemeral objects (instance / wilderness copies) live only in the
        # in-memory cache — never written to disk, so they don't survive a
        # reboot and don't accumulate. This is the transient/do-not-persist
        # flag every save path funnels through. (See realm.core.instances.)
        if obj.has_tag('ephemeral'):
            return

        # Deleted (unregistered) after being swept up by a flush pass —
        # INSERT OR REPLACE would resurrect its row as permanent limbo.
        if obj.id not in self._object_cache:
            return

        data = self._object_to_row(obj)
        await self._db.execute(
            """
            INSERT OR REPLACE INTO objects
            (id, name, description, location_id, parent_id, owner_id,
             tags, attributes, behaviors, locks, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                data['id'],
                data['name'],
                data['description'],
                data['location_id'],
                data['parent_id'],
                data['owner_id'],
                data['tags'],
                data['attributes'],
                data['behaviors'],
                data['locks'],
            ),
        )
        if commit:
            await self._db.commit()
        obj.clear_dirty()
        logger.debug(f"Saved object {obj.id} ({obj.name})")

    async def _load_object(self, obj_id: str) -> GameObject | None:
        """Load a single object from the database."""
        if not self._db:
            return None

        async with self._db.execute(
            "SELECT * FROM objects WHERE id = ?", (obj_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None

            obj = self._row_to_object(dict(row))
            if obj:
                self._object_cache[obj.id] = obj
                self._keyids.index(obj)
                await self._resolve_references(obj)
            return obj

    def _object_to_row(self, obj: GameObject) -> dict[str, Any]:
        """Convert a GameObject to database row data."""

        # Serialize behaviors
        behaviors_data = []
        for b in obj.get_behaviors():
            behaviors_data.append(b.to_dict())

        return {
            'id': obj.id,
            'name': obj.name,
            'description': obj.description,
            'location_id': obj.location.id if obj.location else None,
            'parent_id': obj.parent.id if obj.parent else None,
            'owner_id': obj.owner.id if obj.owner else None,
            'tags': json.dumps(obj.tags.to_list()),
            'attributes': json.dumps(obj.db.all()),
            'behaviors': json.dumps(behaviors_data),
            'locks': json.dumps(obj.locks),
        }

    def _row_to_object(self, row: dict[str, Any]) -> GameObject | None:
        """Convert a database row to a GameObject."""
        from realm.core.behaviors import BehaviorRegistry
        from realm.core.objects import GameObject

        try:
            obj = GameObject(
                name=row['name'],
                id=row['id'],
                description=row['description'] or "",
                tags=json.loads(row['tags'] or '[]'),
            )

            # Load attributes
            attrs = json.loads(row['attributes'] or '{}')
            for key, value in attrs.items():
                obj.db.set(key, value)

            # Load behaviors
            behaviors_data = json.loads(row['behaviors'] or '[]')
            for b_data in behaviors_data:
                behavior = BehaviorRegistry.from_dict(b_data)
                if behavior:
                    obj.add_behavior(behavior)

            # Load locks
            obj.locks = json.loads(row['locks'] or '{}')

            # Clear dirty flag since we just loaded
            obj.clear_dirty()

            return obj
        except Exception as e:
            logger.error(f"Error loading object {row.get('id')}: {e}")
            return None

    async def _resolve_references(self, obj: GameObject) -> None:
        """Resolve location, parent, and owner references after loading."""
        if not self._db:
            return

        # We need to get the raw IDs from the database since they weren't
        # set during _row_to_object (to avoid infinite recursion)
        async with self._db.execute(
            "SELECT location_id, parent_id, owner_id FROM objects WHERE id = ?",
            (obj.id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return

            location_id = row['location_id']
            parent_id = row['parent_id']
            owner_id = row['owner_id']

        self._apply_references(obj, location_id, parent_id, owner_id)

    def _apply_references(self, obj: GameObject, location_id, parent_id,
                          owner_id) -> None:
        """Point loaded references at cached objects."""
        # Resolve references from cache (objects should be loaded already)
        if location_id and location_id in self._object_cache:
            obj._location = self._object_cache[location_id]
            if obj not in obj._location._contents:
                obj._location._contents.append(obj)
        elif location_id:
            # The row named a room that didn't reload (ephemeral, or
            # deleted out from under it). Record it so load-time
            # reconcile can act — never leave a silent location=None.
            self._dangling_locations[obj.id] = location_id

        if parent_id and parent_id in self._object_cache:
            obj.parent = self._object_cache[parent_id]

        if owner_id and owner_id in self._object_cache:
            obj.owner = self._object_cache[owner_id]
