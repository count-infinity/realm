"""Tests for the Behavior system."""

import pytest
from realm.core.behaviors import Behavior, BehaviorRegistry
from realm.core.objects import GameObject
from realm.core.events import Event, EventType


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
    """Behavior that counts events."""

    behavior_id = "counting"

    def __init__(self, **params):
        super().__init__(**params)
        self.validate_count = 0
        self.handle_count = 0

    async def validate_event(self, obj, event):
        self.validate_count += 1
        return True

    async def handle_event(self, obj, event):
        self.handle_count += 1


class VetoingBehavior(Behavior):
    """Behavior that vetoes certain events."""

    behavior_id = "vetoing"

    async def validate_event(self, obj, event):
        if event.type == EventType.ATTACK:
            event.cancel("No fighting allowed!")
            return False
        return True


class TestBehavior:
    """Test suite for Behavior base class."""

    def test_behavior_creation(self):
        """Behavior can be created with parameters."""
        b = SimpleBehavior(damage=10, speed=5)
        assert b.get_param('damage') == 10
        assert b.get_param('speed') == 5
        assert b.get_param('missing') is None
        assert b.get_param('missing', 'default') == 'default'

    def test_owner_initially_none(self):
        """Behavior owner is None before attachment."""
        b = SimpleBehavior()
        assert b.owner is None

    def test_attach_sets_owner(self):
        """attach() sets the owner reference."""
        obj = GameObject("test")
        b = SimpleBehavior()
        b.attach(obj)
        assert b.owner == obj

    def test_detach_clears_owner(self):
        """detach() clears the owner reference."""
        obj = GameObject("test")
        b = SimpleBehavior()
        b.attach(obj)
        b.detach(obj)
        assert b.owner is None

    @pytest.mark.asyncio
    async def test_default_validation_allows(self):
        """Default validate_event returns True."""
        b = SimpleBehavior()
        obj = GameObject("test")
        event = Event(type=EventType.LOOK)

        result = await b.validate_event(obj, event)
        assert result is True

    def test_default_should_tick_false(self):
        """Default should_tick is False."""
        b = SimpleBehavior()
        assert b.should_tick is False

    def test_default_tick_interval(self):
        """Default tick_interval is 1.0."""
        b = SimpleBehavior()
        assert b.tick_interval == 1.0

    def test_ticking_behavior(self):
        """TickingBehavior has correct tick properties."""
        b = TickingBehavior(interval=0.5)
        assert b.should_tick is True
        assert b.tick_interval == 0.5

    @pytest.mark.asyncio
    async def test_tick_called(self):
        """tick() can be called."""
        b = TickingBehavior()
        obj = GameObject("test")
        await b.tick(obj, 0.1)
        assert b.tick_count == 1

    @pytest.mark.asyncio
    async def test_validation_can_veto(self):
        """validate_event can return False to veto."""
        b = VetoingBehavior()
        obj = GameObject("test")
        event = Event(type=EventType.ATTACK)

        result = await b.validate_event(obj, event)
        assert result is False
        assert event.cancelled is True
        assert event.cancel_reason == "No fighting allowed!"

    @pytest.mark.asyncio
    async def test_handle_event_called(self):
        """handle_event receives events."""
        b = CountingBehavior()
        obj = GameObject("test")
        event = Event(type=EventType.LOOK)

        await b.handle_event(obj, event)
        assert b.handle_count == 1

    def test_to_dict(self):
        """Behavior can be serialized to dict."""
        b = SimpleBehavior(damage=10, name="test")
        data = b.to_dict()

        assert data['behavior_id'] == 'simple'
        assert data['params']['damage'] == 10
        assert data['params']['name'] == 'test'

    def test_from_dict(self):
        """Behavior can be created from dict."""
        data = {'behavior_id': 'simple', 'params': {'damage': 10}}
        b = SimpleBehavior.from_dict(data)

        assert b.get_param('damage') == 10

    def test_repr(self):
        """__repr__ returns useful information."""
        obj = GameObject("test")
        b = SimpleBehavior()
        obj.add_behavior(b)

        repr_str = repr(b)
        assert 'SimpleBehavior' in repr_str
        assert 'test' in repr_str


class TestBehaviorRegistry:
    """Test suite for BehaviorRegistry."""

    def setup_method(self):
        """Clear registry before each test."""
        BehaviorRegistry._behaviors.clear()

    def test_register_behavior(self):
        """Behaviors can be registered."""
        BehaviorRegistry.register(SimpleBehavior)
        assert 'simple' in BehaviorRegistry.list_all()

    def test_register_as_decorator(self):
        """register() can be used as decorator."""

        @BehaviorRegistry.register
        class DecoratedBehavior(Behavior):
            behavior_id = "decorated"

        assert 'decorated' in BehaviorRegistry.list_all()

    def test_get_behavior(self):
        """Registered behaviors can be retrieved."""
        BehaviorRegistry.register(SimpleBehavior)
        cls = BehaviorRegistry.get('simple')
        assert cls == SimpleBehavior

    def test_get_nonexistent(self):
        """Getting nonexistent behavior returns None."""
        assert BehaviorRegistry.get('nonexistent') is None

    def test_create_behavior(self):
        """Behaviors can be created by ID."""
        BehaviorRegistry.register(SimpleBehavior)
        b = BehaviorRegistry.create('simple', damage=10)

        assert isinstance(b, SimpleBehavior)
        assert b.get_param('damage') == 10

    def test_create_nonexistent(self):
        """Creating nonexistent behavior returns None."""
        assert BehaviorRegistry.create('nonexistent') is None

    def test_from_dict(self):
        """Behaviors can be created from serialized data."""
        BehaviorRegistry.register(SimpleBehavior)

        data = {'behavior_id': 'simple', 'params': {'damage': 10}}
        b = BehaviorRegistry.from_dict(data)

        assert isinstance(b, SimpleBehavior)
        assert b.get_param('damage') == 10

    def test_from_dict_missing_id(self):
        """from_dict with missing behavior_id returns None."""
        assert BehaviorRegistry.from_dict({}) is None

    def test_from_dict_unknown_id(self):
        """from_dict with unknown behavior_id returns None."""
        data = {'behavior_id': 'unknown', 'params': {}}
        assert BehaviorRegistry.from_dict(data) is None

    def test_list_all(self):
        """list_all returns all registered behavior IDs."""
        BehaviorRegistry.register(SimpleBehavior)
        BehaviorRegistry.register(CountingBehavior)
        BehaviorRegistry.register(VetoingBehavior)

        all_ids = BehaviorRegistry.list_all()
        assert 'simple' in all_ids
        assert 'counting' in all_ids
        assert 'vetoing' in all_ids


class TestGameObjectBehaviors:
    """Test behavior integration with GameObject."""

    def test_add_behavior(self):
        """Behaviors can be added to objects."""
        obj = GameObject("test")
        b = SimpleBehavior()

        obj.add_behavior(b)

        assert b in obj.get_behaviors()
        assert b.owner == obj

    def test_remove_behavior(self):
        """Behaviors can be removed from objects."""
        obj = GameObject("test")
        b = SimpleBehavior()
        obj.add_behavior(b)

        obj.remove_behavior(b)

        assert b not in obj.get_behaviors()
        assert b.owner is None

    def test_get_behavior_by_type(self):
        """Behaviors can be retrieved by type."""
        obj = GameObject("test")
        simple = SimpleBehavior()
        counting = CountingBehavior()
        obj.add_behavior(simple)
        obj.add_behavior(counting)

        found = obj.get_behavior(CountingBehavior)
        assert found == counting

    def test_get_behavior_not_found(self):
        """get_behavior returns None if type not attached."""
        obj = GameObject("test")
        obj.add_behavior(SimpleBehavior())

        found = obj.get_behavior(CountingBehavior)
        assert found is None

    def test_no_duplicate_behaviors(self):
        """Same behavior instance isn't added twice."""
        obj = GameObject("test")
        b = SimpleBehavior()

        obj.add_behavior(b)
        obj.add_behavior(b)

        assert len(obj.get_behaviors()) == 1

    def test_adding_behavior_marks_dirty(self):
        """Adding a behavior marks object as dirty."""
        obj = GameObject("test")
        obj.clear_dirty()

        obj.add_behavior(SimpleBehavior())
        assert obj.is_dirty()

    def test_removing_behavior_marks_dirty(self):
        """Removing a behavior marks object as dirty."""
        obj = GameObject("test")
        b = SimpleBehavior()
        obj.add_behavior(b)
        obj.clear_dirty()

        obj.remove_behavior(b)
        assert obj.is_dirty()

    @pytest.mark.asyncio
    async def test_event_validation_through_behaviors(self):
        """on_event_validate calls all behaviors."""
        obj = GameObject("test")
        c1 = CountingBehavior()
        c2 = CountingBehavior()
        obj.add_behavior(c1)
        obj.add_behavior(c2)

        event = Event(type=EventType.LOOK)
        result = await obj.on_event_validate(event)

        assert result is True
        assert c1.validate_count == 1
        assert c2.validate_count == 1

    @pytest.mark.asyncio
    async def test_event_validation_stops_on_veto(self):
        """Validation stops when a behavior vetoes."""
        obj = GameObject("test")
        veto = VetoingBehavior()
        counting = CountingBehavior()
        obj.add_behavior(veto)
        obj.add_behavior(counting)

        event = Event(type=EventType.ATTACK)
        result = await obj.on_event_validate(event)

        assert result is False
        assert counting.validate_count == 0  # Never called

    @pytest.mark.asyncio
    async def test_event_execution_through_behaviors(self):
        """on_event_execute calls all behaviors."""
        obj = GameObject("test")
        c1 = CountingBehavior()
        c2 = CountingBehavior()
        obj.add_behavior(c1)
        obj.add_behavior(c2)

        event = Event(type=EventType.LOOK)
        await obj.on_event_execute(event)

        assert c1.handle_count == 1
        assert c2.handle_count == 1
