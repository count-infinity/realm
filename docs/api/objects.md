# Core Objects API

!!! note "Work in Progress"
    Full API documentation coming soon.

## GameObject

The base class for all game objects.

```python
class GameObject:
    id: str              # Unique identifier
    name: str            # Display name
    description: str     # Long description
    location: GameObject | None  # Container/room
    contents: list[GameObject]   # Contained objects
    tags: set[str]       # Tags for categorization
    db: AttributeProxy   # Persistent attributes
```

### Creating Objects

```python
from realm.core.objects import GameObject

room = GameObject(
    name="Town Square",
    description="A bustling town square.",
    tags=['room'],
)

item = GameObject(
    name="golden key",
    description="A small golden key.",
    tags=['thing'],
    location=room,
)
```

### Tags

```python
# Check tags
if obj.has_tag('player'):
    ...

# Add/remove tags
obj.add_tag('glowing')
obj.remove_tag('hidden')
```

### Attributes

```python
# Set persistent attributes
obj.db.health = 100
obj.db.max_health = 100

# Get with default
damage = obj.db.get('damage', 0)
```
