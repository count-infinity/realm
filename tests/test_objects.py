"""Tests for GameObject and AttributeProxy."""

import pytest

from realm.core.objects import GameObject


class TestAttributeProxy:
    """Test suite for AttributeProxy (obj.db.* access)."""

    def test_set_and_get_attribute(self):
        """Attributes can be set and retrieved."""
        obj = GameObject("test")
        obj.db.health = 100
        assert obj.db.health == 100

    def test_get_nonexistent_returns_none(self):
        """Getting a nonexistent attribute returns None."""
        obj = GameObject("test")
        assert obj.db.nonexistent is None

    def test_get_with_default(self):
        """get() method supports default values."""
        obj = GameObject("test")
        assert obj.db.get('missing', 42) == 42
        obj.db.health = 100
        assert obj.db.get('health', 0) == 100

    def test_set_method(self):
        """set() method works as alternative to dot notation."""
        obj = GameObject("test")
        obj.db.set('health', 100)
        assert obj.db.health == 100

    def test_delete_attribute(self):
        """Attributes can be deleted."""
        obj = GameObject("test")
        obj.db.health = 100
        del obj.db.health
        assert obj.db.health is None

    def test_delete_method(self):
        """delete() method works as alternative to del."""
        obj = GameObject("test")
        obj.db.health = 100
        obj.db.delete('health')
        assert obj.db.health is None

    def test_contains(self):
        """'in' operator works for checking attributes."""
        obj = GameObject("test")
        obj.db.health = 100
        assert 'health' in obj.db
        assert 'missing' not in obj.db

    def test_all_returns_dict(self):
        """all() returns all attributes as dictionary."""
        obj = GameObject("test")
        obj.db.health = 100
        obj.db.mana = 50
        all_attrs = obj.db.all()
        assert all_attrs == {'health': 100, 'mana': 50}

    def test_underscore_prefix_rejected(self):
        """Attribute names starting with underscore are rejected."""
        obj = GameObject("test")
        with pytest.raises(AttributeError):
            obj.db._private = 42
        with pytest.raises(AttributeError):
            _ = obj.db._private

    def test_dirty_tracking(self):
        """Setting attributes marks object as dirty."""
        obj = GameObject("test")
        obj.clear_dirty()
        assert not obj.is_dirty()
        obj.db.health = 100
        assert obj.is_dirty()


class TestGameObject:
    """Test suite for GameObject."""

    def test_creation_with_defaults(self):
        """GameObject can be created with minimal arguments."""
        obj = GameObject("sword")
        assert obj.name == "sword"
        assert obj.description == ""
        assert obj.location is None
        assert len(obj.contents) == 0
        assert obj.parent is None
        assert obj.owner is None

    def test_creation_with_all_args(self):
        """GameObject can be created with all arguments."""
        room = GameObject("room", tags=['room'])
        player = GameObject("player", tags=['player'])
        parent = GameObject("parent template")

        obj = GameObject(
            "sword",
            description="A sharp blade",
            location=room,
            parent=parent,
            owner=player,
            tags=['thing', 'weapon']
        )

        assert obj.name == "sword"
        assert obj.description == "A sharp blade"
        assert obj.location == room
        assert obj.parent == parent
        assert obj.owner == player
        assert obj.has_tag('thing')
        assert obj.has_tag('weapon')

    def test_unique_id(self):
        """Each GameObject gets a unique ID."""
        obj1 = GameObject("test1")
        obj2 = GameObject("test2")
        assert obj1.id != obj2.id

    def test_custom_id(self):
        """Custom ID can be provided."""
        obj = GameObject("test", id="custom-id-123")
        assert obj.id == "custom-id-123"

    def test_location_property(self):
        """Setting location updates contents lists."""
        room = GameObject("room")
        player = GameObject("player")

        player.location = room

        assert player.location == room
        assert player in room.contents

    def test_location_change(self):
        """Changing location updates both old and new contents."""
        room1 = GameObject("room1")
        room2 = GameObject("room2")
        player = GameObject("player")

        player.location = room1
        assert player in room1.contents

        player.location = room2
        assert player not in room1.contents
        assert player in room2.contents

    def test_location_set_none(self):
        """Setting location to None removes from contents."""
        room = GameObject("room")
        player = GameObject("player", location=room)

        player.location = None
        assert player not in room.contents
        assert player.location is None

    def test_contents_is_copy(self):
        """contents property returns a copy, not the internal list."""
        room = GameObject("room")
        player = GameObject("player", location=room)

        contents = room.contents
        contents.clear()

        # Internal list should be unchanged
        assert player in room.contents

    def test_tag_shortcuts(self):
        """Tag shortcut methods work correctly."""
        obj = GameObject("test")

        obj.add_tag('room')
        assert obj.has_tag('room')
        assert obj.is_room

        obj.remove_tag('room')
        obj.add_tag('player')
        assert obj.is_player

        obj.remove_tag('player')
        obj.add_tag('exit')
        assert obj.is_exit

        obj.remove_tag('exit')
        obj.add_tag('thing')
        assert obj.is_thing

    def test_dirty_tracking(self):
        """Changes mark object as dirty."""
        obj = GameObject("test")
        obj.clear_dirty()

        obj.name = "new name"  # Doesn't trigger dirty
        obj.add_tag('room')
        assert obj.is_dirty()

        obj.clear_dirty()
        assert not obj.is_dirty()

    def test_equality_by_id(self):
        """GameObjects are equal if they have the same ID."""
        obj1 = GameObject("test", id="same-id")
        obj2 = GameObject("different name", id="same-id")
        obj3 = GameObject("test", id="different-id")

        assert obj1 == obj2
        assert obj1 != obj3

    def test_hashable(self):
        """GameObjects can be used in sets and as dict keys."""
        obj1 = GameObject("test1")
        obj2 = GameObject("test2")

        obj_set = {obj1, obj2}
        assert len(obj_set) == 2
        assert obj1 in obj_set


