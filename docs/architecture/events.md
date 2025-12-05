# Event System

REALM uses an event-driven architecture where game actions emit events that can be observed, modified, or canceled.

!!! note "Work in Progress"
    This documentation is being expanded.

## Event Types

```python
class EventType(Enum):
    # Connection events
    CONNECT = auto()
    DISCONNECT = auto()

    # Communication
    SPEECH = auto()      # Player says something
    EMOTE = auto()       # Player emotes/poses

    # Movement
    MOVE = auto()        # Object moves between locations
    ENTER = auto()       # Object enters a location
    LEAVE = auto()       # Object leaves a location

    # Actions
    LOOK = auto()        # Player looks at something
    GET = auto()         # Player picks up item
    DROP = auto()        # Player drops item
    USE = auto()         # Player uses an item

    # Combat (planned)
    ATTACK = auto()
    DAMAGE = auto()
    DEATH = auto()

    # System
    TICK = auto()        # Periodic game tick
    CUSTOM = auto()      # User-defined events
```

## Event Structure

```python
@dataclass
class Event:
    type: EventType
    source: GameObject | None      # Who/what caused the event
    target: GameObject | None      # Target of the event
    location: GameObject | None    # Where the event occurred
    data: dict                     # Event-specific data
    source_msg: str | None         # Message for the source
    others_msg: str | None         # Message for observers
    canceled: bool = False         # Set to True to cancel
```

## Emitting Events

```python
from realm.core.events import Event, EventType

# Emit a speech event
event = Event(
    type=EventType.SPEECH,
    source=player,
    location=player.location,
    data={'message': 'Hello everyone!'},
    source_msg='You say, "Hello everyone!"',
    others_msg=f'{player.name} says, "Hello everyone!"',
)
await event_bus.emit(event)
```

## Subscribing to Events

```python
# Subscribe to all speech events
async def on_speech(event: Event) -> None:
    print(f"{event.source.name} said: {event.data['message']}")

event_bus.subscribe(EventType.SPEECH, on_speech)
```

## Two-Phase Processing

Events are processed in two phases:

1. **Validation Phase** - Handlers can set `event.canceled = True`
2. **Execution Phase** - Only runs if not canceled

This allows behaviors to prevent actions (e.g., a locked door preventing movement).

## Next Steps

- [Command Dispatch](commands.md) - How commands trigger events
- [Architecture Overview](overview.md) - How events fit in the system
