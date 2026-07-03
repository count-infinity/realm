"""Tests for the persistence layer."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from realm.core.behaviors import Behavior, BehaviorRegistry
from realm.core.objects import GameObject
from realm.persistence.manager import PersistenceManager


class PersistTestBehavior(Behavior):
    """Simple behavior for testing persistence."""

    behavior_id = "test_persist"


@pytest.fixture
def db_path():
    """Create a temporary database path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test.db"


@pytest.fixture
async def pm(db_path):
    """Create and initialize a PersistenceManager."""
    manager = PersistenceManager(db_path)
    await manager.initialize()
    yield manager
    await manager.close()


class TestPersistenceManager:
    """Test suite for PersistenceManager."""

    @pytest.mark.asyncio
    async def test_initialize_creates_database(self, db_path):
        """initialize() creates the database file."""
        pm = PersistenceManager(db_path)
        await pm.initialize()

        assert db_path.exists()
        await pm.close()

    @pytest.mark.asyncio
    async def test_save_and_load_object(self, pm):
        """Objects can be saved and loaded."""
        obj = GameObject("sword", description="A sharp blade")
        obj.db.damage = 10
        obj.add_tag('thing')
        obj.add_tag('weapon')

        await pm.save(obj)

        # Clear cache to force load from DB
        pm._object_cache.clear()

        loaded = await pm.load(obj.id)

        assert loaded is not None
        assert loaded.name == "sword"
        assert loaded.description == "A sharp blade"
        assert loaded.db.damage == 10
        assert loaded.has_tag('thing')
        assert loaded.has_tag('weapon')

    @pytest.mark.asyncio
    async def test_load_nonexistent_returns_none(self, pm):
        """Loading nonexistent object returns None."""
        loaded = await pm.load("nonexistent-id")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_exists(self, pm):
        """exists() checks if object is in database."""
        obj = GameObject("test")
        await pm.save(obj)

        assert await pm.exists(obj.id)
        assert not await pm.exists("nonexistent-id")

    @pytest.mark.asyncio
    async def test_delete(self, pm):
        """Objects can be deleted."""
        obj = GameObject("test")
        await pm.save(obj)

        await pm.delete(obj)

        assert not await pm.exists(obj.id)
        assert obj.id not in pm._object_cache

    @pytest.mark.asyncio
    async def test_load_from_cache(self, pm):
        """load() returns cached object if available."""
        obj = GameObject("test")
        await pm.save(obj)

        # Object should be in cache
        loaded = await pm.load(obj.id)
        assert loaded is obj  # Same instance

    @pytest.mark.asyncio
    async def test_register_and_unregister(self, pm):
        """Objects can be registered/unregistered from cache."""
        obj = GameObject("test")

        pm.register(obj)
        assert obj.id in pm._object_cache

        pm.unregister(obj)
        assert obj.id not in pm._object_cache

    @pytest.mark.asyncio
    async def test_save_deferred(self, pm):
        """save_deferred() queues object for batch save."""
        obj = GameObject("test")
        obj.db.value = 42

        await pm.save_deferred(obj)

        # Object should be registered
        assert obj.id in pm._object_cache

        # Manually flush the queue
        await pm._flush_queue()

        # Clear cache and load from DB
        pm._object_cache.clear()
        loaded = await pm.load(obj.id)

        assert loaded is not None
        assert loaded.db.value == 42

    @pytest.mark.asyncio
    async def test_dirty_tracking_on_save(self, pm):
        """Saving clears dirty flag."""
        obj = GameObject("test")
        obj.db.value = 1  # Makes dirty

        assert obj.is_dirty()
        await pm.save(obj)
        assert not obj.is_dirty()

    @pytest.mark.asyncio
    async def test_flush_only_saves_dirty(self, pm):
        """Flush only saves objects that are dirty."""
        obj1 = GameObject("obj1")
        obj2 = GameObject("obj2")

        # Save obj1 (clears dirty)
        await pm.save(obj1)

        # Queue both for deferred save
        await pm.save_deferred(obj1)
        await pm.save_deferred(obj2)

        # obj1 is not dirty, obj2 is dirty
        obj2.db.value = 1  # Mark dirty

        # Flush should only save obj2
        await pm._flush_queue()

        # Both should exist in DB
        assert await pm.exists(obj1.id)
        assert await pm.exists(obj2.id)

    @pytest.mark.asyncio
    async def test_load_all(self, pm):
        """load_all() loads all objects from database."""
        obj1 = GameObject("obj1")
        obj2 = GameObject("obj2")
        obj3 = GameObject("obj3")

        await pm.save(obj1)
        await pm.save(obj2)
        await pm.save(obj3)

        # Clear cache
        pm._object_cache.clear()

        objects = await pm.load_all()

        assert len(objects) == 3
        names = [o.name for o in objects]
        assert 'obj1' in names
        assert 'obj2' in names
        assert 'obj3' in names


class TestPersistenceWithBehaviors:
    """Test persistence of behaviors."""

    @pytest.fixture(autouse=True)
    def register_behaviors(self):
        """Register test behaviors."""
        BehaviorRegistry._behaviors.clear()
        BehaviorRegistry.register(PersistTestBehavior)
        yield
        BehaviorRegistry._behaviors.clear()

    @pytest.mark.asyncio
    async def test_save_and_load_behaviors(self, pm):
        """Behaviors are persisted and restored."""
        obj = GameObject("test")
        behavior = PersistTestBehavior(damage=10, speed=5)
        obj.add_behavior(behavior)

        await pm.save(obj)
        pm._object_cache.clear()

        loaded = await pm.load(obj.id)

        assert loaded is not None
        behaviors = loaded.get_behaviors()
        assert len(behaviors) == 1
        assert behaviors[0].behavior_id == "test_persist"
        assert behaviors[0].get_param('damage') == 10
        assert behaviors[0].get_param('speed') == 5


class TestPersistenceWithReferences:
    """Test persistence of object references (location, parent, owner)."""

    @pytest.mark.asyncio
    async def test_save_and_load_location(self, pm):
        """Location references are persisted and restored."""
        room = GameObject("room", tags=['room'])
        player = GameObject("player", tags=['player'])
        player.location = room

        await pm.save(room)
        await pm.save(player)

        pm._object_cache.clear()

        # Load all to populate cache with references
        objects = await pm.load_all()

        player_loaded = next(o for o in objects if o.name == "player")
        room_loaded = next(o for o in objects if o.name == "room")

        assert player_loaded.location == room_loaded
        assert player_loaded in room_loaded.contents

    @pytest.mark.asyncio
    async def test_save_and_load_parent(self, pm):
        """Parent references are persisted and restored."""
        parent = GameObject("parent")
        child = GameObject("child", parent=parent)

        await pm.save(parent)
        await pm.save(child)

        pm._object_cache.clear()
        objects = await pm.load_all()

        child_loaded = next(o for o in objects if o.name == "child")
        parent_loaded = next(o for o in objects if o.name == "parent")

        assert child_loaded.parent == parent_loaded

    @pytest.mark.asyncio
    async def test_save_and_load_owner(self, pm):
        """Owner references are persisted and restored."""
        player = GameObject("player", tags=['player'])
        item = GameObject("sword", owner=player)

        await pm.save(player)
        await pm.save(item)

        pm._object_cache.clear()
        objects = await pm.load_all()

        item_loaded = next(o for o in objects if o.name == "sword")
        player_loaded = next(o for o in objects if o.name == "player")

        assert item_loaded.owner == player_loaded


class TestPersistenceWithLocks:
    """Test persistence of lock data."""

    @pytest.mark.asyncio
    async def test_save_and_load_locks(self, pm):
        """Lock data is persisted and restored."""
        obj = GameObject("chest")
        obj.locks = {
            'default': 'owner',
            'open': 'has_key',
            'get': 'is_admin',
        }

        await pm.save(obj)
        pm._object_cache.clear()

        loaded = await pm.load(obj.id)

        assert loaded.locks == {
            'default': 'owner',
            'open': 'has_key',
            'get': 'is_admin',
        }


class TestFlushLoop:
    """Test the background flush loop."""

    @pytest.mark.asyncio
    async def test_start_and_stop_flush_loop(self, pm):
        """Flush loop can be started and stopped."""
        pm.flush_interval = 0.1  # Short interval for testing

        await pm.start_flush_loop()
        assert pm._running is True
        assert pm._flush_task is not None

        await pm.close()
        assert pm._running is False

    @pytest.mark.asyncio
    async def test_flush_loop_saves_queued_objects(self, pm):
        """Flush loop saves queued objects periodically."""
        pm.flush_interval = 0.1

        obj = GameObject("test")
        obj.db.value = 42
        await pm.save_deferred(obj)

        await pm.start_flush_loop()

        # Wait for flush to occur
        await asyncio.sleep(0.2)

        # Clear cache and verify saved
        pm._object_cache.clear()
        loaded = await pm.load(obj.id)

        assert loaded is not None
        assert loaded.db.value == 42

        await pm.close()


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_save_object_with_none_description(self, pm):
        """Objects with None description save correctly."""
        obj = GameObject("test")
        obj.description = ""

        await pm.save(obj)
        pm._object_cache.clear()

        loaded = await pm.load(obj.id)
        assert loaded.description == ""

    @pytest.mark.asyncio
    async def test_save_object_with_empty_tags(self, pm):
        """Objects with no tags save correctly."""
        obj = GameObject("test")

        await pm.save(obj)
        pm._object_cache.clear()

        loaded = await pm.load(obj.id)
        assert len(loaded.tags) == 0

    @pytest.mark.asyncio
    async def test_save_object_with_empty_attributes(self, pm):
        """Objects with no attributes save correctly."""
        obj = GameObject("test")

        await pm.save(obj)
        pm._object_cache.clear()

        loaded = await pm.load(obj.id)
        assert len(loaded.db.all()) == 0

    @pytest.mark.asyncio
    async def test_update_existing_object(self, pm):
        """Saving an existing object updates it."""
        obj = GameObject("test")
        obj.db.version = 1
        await pm.save(obj)

        obj.db.version = 2
        await pm.save(obj)

        pm._object_cache.clear()
        loaded = await pm.load(obj.id)

        assert loaded.db.version == 2

    @pytest.mark.asyncio
    async def test_complex_attribute_types(self, pm):
        """Complex attribute types are preserved."""
        obj = GameObject("test")
        obj.db.numbers = [1, 2, 3]
        obj.db.nested = {'a': {'b': 'c'}}
        obj.db.boolean = True
        obj.db.null_val = None

        await pm.save(obj)
        pm._object_cache.clear()

        loaded = await pm.load(obj.id)

        assert loaded.db.numbers == [1, 2, 3]
        assert loaded.db.nested == {'a': {'b': 'c'}}
        assert loaded.db.boolean is True
        assert loaded.db.null_val is None


class TestDirtySweep:
    """
    The durability contract: ANY dirty object is persisted by the
    periodic flush — gameplay code never has to call save(). A crash
    loses at most flush_interval seconds.
    """

    @pytest.mark.asyncio
    async def test_unqueued_attribute_mutation_survives_flush(self, tmp_path):
        db = tmp_path / "sweep.db"
        pm = PersistenceManager(db)
        await pm.initialize()
        obj = GameObject("safe", tags=['thing'])
        await pm.save(obj)

        # Pure gameplay mutation: no save(), no save_deferred().
        obj.db.locked = False
        obj.add_tag('closed')
        assert obj.is_dirty()

        await pm._flush_queue()  # what the background loop runs
        await pm.close()

        pm2 = PersistenceManager(db)
        await pm2.initialize()
        loaded = await pm2.load(obj.id)
        assert loaded.db.locked is False
        assert loaded.has_tag('closed')
        await pm2.close()

    @pytest.mark.asyncio
    async def test_location_move_survives_flush(self, tmp_path):
        db = tmp_path / "sweep2.db"
        pm = PersistenceManager(db)
        await pm.initialize()
        room = GameObject("Vault", tags=['room'])
        player = GameObject("Raven", tags=['player'], location=room)
        docs = GameObject("documents", tags=['thing'], location=room)
        for o in (room, player, docs):
            await pm.save(o)

        docs.location = player  # a 'get' — nobody calls save
        await pm._flush_queue()
        await pm.close()

        pm2 = PersistenceManager(db)
        await pm2.initialize()
        objs = {o.name: o for o in await pm2.load_all()}
        assert objs["documents"].location is objs["Raven"]
        await pm2.close()

    @pytest.mark.asyncio
    async def test_clean_objects_not_rewritten(self, tmp_path):
        db = tmp_path / "sweep3.db"
        pm = PersistenceManager(db)
        await pm.initialize()
        obj = GameObject("statue", tags=['thing'])
        await pm.save(obj)
        assert not obj.is_dirty()

        writes = []
        original = pm._save_object

        async def counting(o, commit=True):
            writes.append(o.id)
            await original(o, commit=commit)

        pm._save_object = counting
        await pm._flush_queue()
        assert writes == []  # nothing dirty, nothing written
        await pm.close()
