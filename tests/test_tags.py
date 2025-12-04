"""Tests for the TagSet class."""

import pytest
from realm.core.tags import TagSet


class TestTagSet:
    """Test suite for TagSet."""

    def test_empty_init(self):
        """TagSet can be initialized empty."""
        tags = TagSet()
        assert len(tags) == 0

    def test_init_with_list(self):
        """TagSet can be initialized with a list."""
        tags = TagSet(['room', 'indoor', 'dark'])
        assert len(tags) == 3
        assert 'room' in tags
        assert 'indoor' in tags
        assert 'dark' in tags

    def test_init_with_set(self):
        """TagSet can be initialized with a set."""
        tags = TagSet({'room', 'outdoor'})
        assert len(tags) == 2
        assert 'room' in tags
        assert 'outdoor' in tags

    def test_add_tag(self):
        """Tags can be added."""
        tags = TagSet()
        tags.add('room')
        assert 'room' in tags

    def test_remove_tag(self):
        """Tags can be removed."""
        tags = TagSet(['room', 'indoor'])
        tags.remove('indoor')
        assert 'indoor' not in tags
        assert 'room' in tags

    def test_remove_nonexistent_tag(self):
        """Removing a nonexistent tag doesn't raise."""
        tags = TagSet(['room'])
        tags.remove('nonexistent')  # Should not raise
        assert len(tags) == 1

    def test_case_insensitive(self):
        """Tags are case-insensitive."""
        tags = TagSet()
        tags.add('ROOM')
        assert 'room' in tags
        assert 'Room' in tags
        assert 'ROOM' in tags

    def test_whitespace_stripped(self):
        """Whitespace is stripped from tags."""
        tags = TagSet()
        tags.add('  room  ')
        assert 'room' in tags

    def test_has_method(self):
        """The has() method works correctly."""
        tags = TagSet(['room', 'zone:forest'])
        assert tags.has('room')
        assert tags.has('zone:forest')
        assert not tags.has('player')

    def test_has_prefix(self):
        """has_prefix() finds namespaced tags."""
        tags = TagSet(['room', 'zone:forest', 'zone:dark'])
        assert tags.has_prefix('zone')
        assert tags.has_prefix('zone:')
        assert not tags.has_prefix('type')

    def test_get_value(self):
        """get_value() extracts value from namespaced tag."""
        tags = TagSet(['room', 'zone:forest'])
        assert tags.get_value('zone') == 'forest'
        assert tags.get_value('zone:') == 'forest'
        assert tags.get_value('type') is None

    def test_get_all_values(self):
        """get_all_values() extracts all values for a prefix."""
        tags = TagSet(['zone:forest', 'zone:dark', 'zone:magical', 'room'])
        values = tags.get_all_values('zone')
        assert len(values) == 3
        assert 'forest' in values
        assert 'dark' in values
        assert 'magical' in values

    def test_clear(self):
        """clear() removes all tags."""
        tags = TagSet(['room', 'indoor', 'dark'])
        tags.clear()
        assert len(tags) == 0

    def test_copy(self):
        """copy() creates an independent copy."""
        original = TagSet(['room', 'indoor'])
        copy = original.copy()
        copy.add('dark')
        assert 'dark' in copy
        assert 'dark' not in original

    def test_iteration(self):
        """TagSet is iterable."""
        tags = TagSet(['a', 'b', 'c'])
        tag_list = list(tags)
        assert len(tag_list) == 3

    def test_equality(self):
        """TagSet equality comparison works."""
        tags1 = TagSet(['room', 'indoor'])
        tags2 = TagSet(['room', 'indoor'])
        tags3 = TagSet(['room', 'outdoor'])
        assert tags1 == tags2
        assert tags1 != tags3

    def test_to_list(self):
        """to_list() returns sorted list."""
        tags = TagSet(['c', 'a', 'b'])
        result = tags.to_list()
        assert result == ['a', 'b', 'c']

    def test_from_list(self):
        """from_list() creates TagSet from list."""
        tags = TagSet.from_list(['room', 'indoor'])
        assert 'room' in tags
        assert 'indoor' in tags

    def test_repr(self):
        """__repr__ returns readable string."""
        tags = TagSet(['room'])
        assert 'room' in repr(tags)
        assert 'TagSet' in repr(tags)
