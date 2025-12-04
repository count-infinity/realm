"""Tests for the Event system."""

import pytest
from realm.core.events import Event, EventType, EventBus, emit
from realm.core.objects import GameObject
from realm.core.behaviors import Behavior, BehaviorRegistry


class TestEvent:
    """Test suite for Event dataclass."""

    def test_creation_minimal(self):
        """Event can be created with just type."""
        event = Event(type=EventType.ENTER)
        assert event.type == EventType.ENTER
        assert event.source is None
        assert event.target is None
        assert event.cancelled is False

    def test_creation_full(self):
        """Event can be created with all fields."""
        source = GameObject("player")
        target = GameObject("door")
        location = GameObject("room")

        event = Event(
            type=EventType.OPEN,
            source=source,
            target=target,
            location=location,
            data={'key_used': 'golden_key'},
            source_msg="You open the door.",
            target_msg="The door opens.",
            others_msg="Player opens the door."
        )

        assert event.source == source
        assert event.target == target
        assert event.location == location
        assert event.data['key_used'] == 'golden_key'
        assert event.source_msg == "You open the door."

    def test_cancel(self):
        """Event can be cancelled with a reason."""
        event = Event(type=EventType.ATTACK)
        event.cancel("Target is protected")

        assert event.cancelled is True
        assert event.cancel_reason == "Target is protected"

    def test_cancel_without_reason(self):
        """Event can be cancelled without a reason."""
        event = Event(type=EventType.ATTACK)
        event.cancel()

        assert event.cancelled is True
        assert event.cancel_reason is None

    def test_custom_event_type(self):
        """Event can use custom string type."""
        event = Event(type="MY_CUSTOM_EVENT")
        assert event.type == "MY_CUSTOM_EVENT"

    def test_repr(self):
        """__repr__ returns useful information."""
        player = GameObject("Player")
        door = GameObject("Door")
        event = Event(type=EventType.OPEN, source=player, target=door)

        repr_str = repr(event)
        assert "OPEN" in repr_str
        assert "Player" in repr_str
        assert "Door" in repr_str


class VetoBehavior(Behavior):
    """Test behavior that vetoes events."""

    behavior_id = "veto"

    async def validate_event(self, obj, event):
        if self.get_param('veto', False):
            event.cancel("Vetoed by VetoBehavior")
            return False
        return True


class TrackingBehavior(Behavior):
    """Test behavior that tracks events received."""

    behavior_id = "tracking"

    def __init__(self, **params):
        super().__init__(**params)
        self.validated_events = []
        self.handled_events = []

    async def validate_event(self, obj, event):
        self.validated_events.append(event)
        return True

    async def handle_event(self, obj, event):
        self.handled_events.append(event)


class TestEventBus:
    """Test suite for EventBus."""

    @pytest.mark.asyncio
    async def test_emit_returns_true(self):
        """emit() returns True when event is not cancelled."""
        bus = EventBus()
        event = Event(type=EventType.LOOK)
        result = await bus.emit(event)
        assert result is True
        assert not event.cancelled

    @pytest.mark.asyncio
    async def test_emit_with_source(self):
        """Event is sent to source object."""
        bus = EventBus()
        player = GameObject("player")
        tracking = TrackingBehavior()
        player.add_behavior(tracking)

        event = Event(type=EventType.LOOK, source=player)
        await bus.emit(event)

        assert len(tracking.validated_events) == 1
        assert len(tracking.handled_events) == 1

    @pytest.mark.asyncio
    async def test_emit_with_target(self):
        """Event is sent to target object."""
        bus = EventBus()
        door = GameObject("door")
        tracking = TrackingBehavior()
        door.add_behavior(tracking)

        event = Event(type=EventType.OPEN, target=door)
        await bus.emit(event)

        assert len(tracking.handled_events) == 1

    @pytest.mark.asyncio
    async def test_emit_with_location_contents(self):
        """Event is sent to location and its contents."""
        bus = EventBus()
        room = GameObject("room", tags=['room'])
        npc = GameObject("npc", location=room)

        room_tracking = TrackingBehavior()
        npc_tracking = TrackingBehavior()
        room.add_behavior(room_tracking)
        npc.add_behavior(npc_tracking)

        player = GameObject("player")
        event = Event(type=EventType.SPEECH, source=player, location=room)
        await bus.emit(event)

        assert len(room_tracking.handled_events) == 1
        assert len(npc_tracking.handled_events) == 1

    @pytest.mark.asyncio
    async def test_validation_can_cancel(self):
        """Behavior can cancel event during validation."""
        bus = EventBus()
        guard = GameObject("guard")
        veto = VetoBehavior(veto=True)
        guard.add_behavior(veto)

        event = Event(type=EventType.ENTER, source=guard)
        result = await bus.emit(event)

        assert result is False
        assert event.cancelled is True

    @pytest.mark.asyncio
    async def test_cancelled_event_not_executed(self):
        """Cancelled events don't trigger handle_event."""
        bus = EventBus()
        obj = GameObject("test")
        veto = VetoBehavior(veto=True)
        tracking = TrackingBehavior()
        obj.add_behavior(veto)
        obj.add_behavior(tracking)

        event = Event(type=EventType.ENTER, source=obj)
        await bus.emit(event)

        assert len(tracking.validated_events) == 0  # Veto first, stops there
        assert len(tracking.handled_events) == 0

    @pytest.mark.asyncio
    async def test_global_handler_receives_events(self):
        """Global handlers receive all events."""

        class GlobalTracker:
            def __init__(self):
                self.events = []

            async def on_event_validate(self, event):
                return True

            async def on_event_execute(self, event):
                self.events.append(event)

        bus = EventBus()
        tracker = GlobalTracker()
        bus.add_global_handler(tracker)

        event = Event(type=EventType.TICK)
        await bus.emit(event)

        assert len(tracker.events) == 1

    @pytest.mark.asyncio
    async def test_global_handler_can_veto(self):
        """Global handlers can veto events."""

        class GlobalVeto:
            async def on_event_validate(self, event):
                return False

        bus = EventBus()
        bus.add_global_handler(GlobalVeto())

        event = Event(type=EventType.ATTACK)
        result = await bus.emit(event)

        assert result is False
        assert event.cancelled is True

    @pytest.mark.asyncio
    async def test_remove_global_handler(self):
        """Global handlers can be removed."""

        class GlobalTracker:
            def __init__(self):
                self.count = 0

            async def on_event_execute(self, event):
                self.count += 1

        bus = EventBus()
        tracker = GlobalTracker()
        bus.add_global_handler(tracker)
        bus.remove_global_handler(tracker)

        await bus.emit(Event(type=EventType.TICK))
        assert tracker.count == 0

    @pytest.mark.asyncio
    async def test_no_duplicate_listeners(self):
        """Same object doesn't receive event twice."""
        bus = EventBus()
        player = GameObject("player")
        room = GameObject("room")
        player.location = room

        tracking = TrackingBehavior()
        player.add_behavior(tracking)

        # Player is both source and in location contents
        event = Event(type=EventType.SPEECH, source=player, location=room)
        await bus.emit(event)

        # Should only receive once
        assert len(tracking.handled_events) == 1


class TestEmitFunction:
    """Test the convenience emit() function."""

    @pytest.mark.asyncio
    async def test_emit_with_bus(self):
        """emit() works with provided EventBus."""
        bus = EventBus()
        event = Event(type=EventType.TICK)
        result = await emit(event, bus)
        assert result is True

    @pytest.mark.asyncio
    async def test_emit_without_bus(self):
        """emit() works without EventBus (local dispatch)."""
        player = GameObject("player")
        tracking = TrackingBehavior()
        player.add_behavior(tracking)

        event = Event(type=EventType.LOOK, source=player)
        result = await emit(event)

        assert result is True
        assert len(tracking.handled_events) == 1

    @pytest.mark.asyncio
    async def test_emit_without_bus_can_cancel(self):
        """emit() without bus respects cancellation."""
        player = GameObject("player")
        player.add_behavior(VetoBehavior(veto=True))

        event = Event(type=EventType.ATTACK, source=player)
        result = await emit(event)

        assert result is False
        assert event.cancelled is True


class TestEventTypes:
    """Test that all EventTypes are defined correctly."""

    def test_event_type_values(self):
        """All expected event types exist."""
        # Movement
        assert EventType.ENTER
        assert EventType.LEAVE
        assert EventType.ARRIVE
        assert EventType.DEPART

        # Combat
        assert EventType.ATTACK
        assert EventType.DAMAGE
        assert EventType.DEATH
        assert EventType.KILL
        assert EventType.FLEE

        # Communication
        assert EventType.SPEECH
        assert EventType.WHISPER
        assert EventType.CHANNEL
        assert EventType.EMOTE

        # Items
        assert EventType.GET
        assert EventType.DROP
        assert EventType.GIVE
        assert EventType.PUT
        assert EventType.WEAR
        assert EventType.REMOVE
        assert EventType.CONSUME

        # Interaction
        assert EventType.LOOK
        assert EventType.EXAMINE
        assert EventType.USE
        assert EventType.OPEN
        assert EventType.CLOSE
        assert EventType.LOCK
        assert EventType.UNLOCK

        # Commerce
        assert EventType.BUY
        assert EventType.SELL
        assert EventType.BRIBE

        # Session
        assert EventType.CONNECT
        assert EventType.DISCONNECT
        assert EventType.IDLE

        # Time
        assert EventType.TICK
        assert EventType.HOUR
        assert EventType.DAY

        # Magic
        assert EventType.CAST
        assert EventType.AFFECT
        assert EventType.RESIST

        # Custom
        assert EventType.CUSTOM
