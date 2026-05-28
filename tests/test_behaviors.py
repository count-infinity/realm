"""Tests for the Behavior system."""

import pytest

from realm.core.behaviors import Behavior, BehaviorRegistry
from realm.core.objects import GameObject


class SimpleBehavior(Behavior):
    """Simple test behavior."""

    behavior_id = "simple"


class TickingBehavior(Behavior):
    """Behavior that ticks."""

    behavior_id = "ticking"

    def __init__(self, **params):
        super().__init__(**params)
        self.tick_count = 0

    @property
    def should_tick(self) -> bool:
        return True

    @property
    def tick_interval(self) -> float:
        return self.get_param('interval', 1.0)

    async def tick(self, obj, delta):
        self.tick_count += 1


class CountingBehavior(Behavior):
    """Behavior that counts on_check / on_react calls."""

    behavior_id = "counting"

    def __init__(self, **params):
        super().__init__(**params)
        self.check_count = 0
        self.react_count = 0

    async def on_check(self, obj, action):
        self.check_count += 1

    async def on_react(self, obj, action):
        self.react_count += 1


class TestBehavior:
    """Test suite for Behavior base class."""

    def test_behavior_creation(self):
        b = SimpleBehavior(damage=10, speed=5)
        assert b.get_param('damage') == 10
        assert b.get_param('speed') == 5
        assert b.get_param('missing') is None
        assert b.get_param('missing', 'default') == 'default'

    def test_owner_initially_none(self):
        b = SimpleBehavior()
        assert b.owner is None

    def test_attach_sets_owner(self):
        obj = GameObject("test")
        b = SimpleBehavior()
        b.attach(obj)
        assert b.owner == obj

    def test_detach_clears_owner(self):
        obj = GameObject("test")
        b = SimpleBehavior()
        b.attach(obj)
        b.detach(obj)
        assert b.owner is None

    def test_default_should_tick_false(self):
        b = SimpleBehavior()
        assert b.should_tick is False

    def test_default_tick_interval(self):
        b = SimpleBehavior()
        assert b.tick_interval == 1.0

    def test_ticking_behavior(self):
        b = TickingBehavior(interval=0.5)
        assert b.should_tick is True
        assert b.tick_interval == 0.5

    @pytest.mark.asyncio
    async def test_tick_called(self):
        b = TickingBehavior()
        obj = GameObject("test")
        await b.tick(obj, 0.1)
        assert b.tick_count == 1

    def test_to_dict(self):
        b = SimpleBehavior(damage=10, name="test")
        data = b.to_dict()
        assert data['behavior_id'] == 'simple'
        assert data['params']['damage'] == 10
        assert data['params']['name'] == 'test'

    def test_from_dict(self):
        data = {'behavior_id': 'simple', 'params': {'damage': 10}}
        b = SimpleBehavior.from_dict(data)
        assert b.get_param('damage') == 10

    def test_repr(self):
        obj = GameObject("test")
        b = SimpleBehavior()
        obj.add_behavior(b)
        repr_str = repr(b)
        assert 'SimpleBehavior' in repr_str
        assert 'test' in repr_str


class TestBehaviorRegistry:
    """Test suite for BehaviorRegistry."""

    def setup_method(self):
        BehaviorRegistry._behaviors.clear()

    def test_register_behavior(self):
        BehaviorRegistry.register(SimpleBehavior)
        assert 'simple' in BehaviorRegistry.list_all()

    def test_register_as_decorator(self):
        @BehaviorRegistry.register
        class DecoratedBehavior(Behavior):
            behavior_id = "decorated"

        assert 'decorated' in BehaviorRegistry.list_all()

    def test_get_behavior(self):
        BehaviorRegistry.register(SimpleBehavior)
        cls = BehaviorRegistry.get('simple')
        assert cls == SimpleBehavior

    def test_get_nonexistent(self):
        assert BehaviorRegistry.get('nonexistent') is None

    def test_create_behavior(self):
        BehaviorRegistry.register(SimpleBehavior)
        b = BehaviorRegistry.create('simple', damage=10)
        assert isinstance(b, SimpleBehavior)
        assert b.get_param('damage') == 10

    def test_create_nonexistent(self):
        assert BehaviorRegistry.create('nonexistent') is None

    def test_from_dict(self):
        BehaviorRegistry.register(SimpleBehavior)
        data = {'behavior_id': 'simple', 'params': {'damage': 10}}
        b = BehaviorRegistry.from_dict(data)
        assert isinstance(b, SimpleBehavior)
        assert b.get_param('damage') == 10

    def test_from_dict_missing_id(self):
        assert BehaviorRegistry.from_dict({}) is None

    def test_from_dict_unknown_id(self):
        data = {'behavior_id': 'unknown', 'params': {}}
        assert BehaviorRegistry.from_dict(data) is None

    def test_list_all(self):
        BehaviorRegistry.register(SimpleBehavior)
        BehaviorRegistry.register(CountingBehavior)
        all_ids = BehaviorRegistry.list_all()
        assert 'simple' in all_ids
        assert 'counting' in all_ids


class TestGameObjectBehaviors:
    """Test behavior integration with GameObject (no propagation —
    that's covered in test_propagation.py)."""

    def test_add_behavior(self):
        obj = GameObject("test")
        b = SimpleBehavior()
        obj.add_behavior(b)
        assert b in obj.get_behaviors()
        assert b.owner == obj

    def test_remove_behavior(self):
        obj = GameObject("test")
        b = SimpleBehavior()
        obj.add_behavior(b)
        obj.remove_behavior(b)
        assert b not in obj.get_behaviors()
        assert b.owner is None

    def test_get_behavior_by_type(self):
        obj = GameObject("test")
        simple = SimpleBehavior()
        counting = CountingBehavior()
        obj.add_behavior(simple)
        obj.add_behavior(counting)
        found = obj.get_behavior(CountingBehavior)
        assert found == counting

    def test_get_behavior_not_found(self):
        obj = GameObject("test")
        obj.add_behavior(SimpleBehavior())
        found = obj.get_behavior(CountingBehavior)
        assert found is None

    def test_no_duplicate_behaviors(self):
        obj = GameObject("test")
        b = SimpleBehavior()
        obj.add_behavior(b)
        obj.add_behavior(b)
        assert len(obj.get_behaviors()) == 1

    def test_adding_behavior_marks_dirty(self):
        obj = GameObject("test")
        obj.clear_dirty()
        obj.add_behavior(SimpleBehavior())
        assert obj.is_dirty()

    def test_removing_behavior_marks_dirty(self):
        obj = GameObject("test")
        b = SimpleBehavior()
        obj.add_behavior(b)
        obj.clear_dirty()
        obj.remove_behavior(b)
        assert obj.is_dirty()
