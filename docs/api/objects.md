# Core Objects API

!!! note "Work in Progress"
    Full API documentation coming soon.

## GameObject

The base class for all game objects.

```python
class GameObject:
    id: str              # UUID
    name: str            # display name (articles computed at render)
    description: str     # may embed [[...]] softcode blocks
    location: GameObject | None
    contents: list[GameObject]
    tags: TagSet         # has_tag/add_tag/remove_tag; "zone:castle" namespacing
    db: AttributeProxy   # persistent attrs: obj.db.hp = 10 (dirty-tracked)
    owner: GameObject | None  # authority: controls() walks this
    locks: dict          # "basic", "enter", "use", "control", ...

    def msg(text)                    # to the player's client (no-op for NPCs)
    def msg_oob(package, data)       # GMCP structured data (no-op likewise)
    def add_behavior(b) / get_behaviors()
    def get_display_name(looker)     # perception/disguise hook
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
