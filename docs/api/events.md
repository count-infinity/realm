# Events API

!!! note "Work in Progress"
    Full API documentation coming soon.

## EventBus

Central event dispatcher.

```python
from realm.core.events import EventBus, Event, EventType

bus = EventBus()

# Subscribe to events
async def handler(event: Event):
    print(f"Got {event.type}")

bus.subscribe(EventType.SPEECH, handler)

# Emit events
event = Event(
    type=EventType.SPEECH,
    source=player,
    location=room,
    data={'message': 'Hello'},
)
await bus.emit(event)
```

## Event

Event data structure.

```python
@dataclass
class Event:
    type: EventType
    source: GameObject | None
    target: GameObject | None
    location: GameObject | None
    data: dict
    source_msg: str | None
    others_msg: str | None
    canceled: bool = False
```

## EventType

Available event types:

- `CONNECT`, `DISCONNECT` - Session events
- `SPEECH`, `EMOTE` - Communication
- `MOVE`, `ENTER`, `LEAVE` - Movement
- `LOOK`, `GET`, `DROP`, `USE` - Actions
- `ATTACK`, `DAMAGE`, `DEATH` - Combat
- `TICK`, `CUSTOM` - System
