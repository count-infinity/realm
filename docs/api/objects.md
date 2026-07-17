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

### The display-name seam (recognition & disguise)

`get_display_name(looker)` → `perceived_name` is the one place "who does
this person appear to be?" is decided. Register overrides with
`realm.core.perception.register_name_resolver(fn)`:

```python
from realm.core.perception import register_name_resolver

def recognition(obj, looker, current):
    """Strangers read by their sdesc until introduced."""
    sdesc = obj.db.get('sdesc')
    if sdesc and looker and looker is not obj \
            and looker.id not in (obj.db.get('recognized_by') or []):
        return sdesc
    return current

register_name_resolver(recognition)
```

`fn(obj, looker, current) -> str` runs only when `looker` can see `obj`
(an unseen actor is always "Someone"), composes in registration order,
and must not raise (a broken one is logged and skipped). With none
registered, names are unchanged.

Every **narration and listing** surface routes through it — speech
attribution (`{actor}` in a message), the room's "Players here" list,
and `look <player>` — so a disguise or an unintroduced stranger is named
consistently everywhere in play, *including their voice* (item 84 falls
out of the same seam). Deliberately **not** routed: `@examine`, owner /
parent / location readouts, and logs, which show the truth — a disguise
that fooled `@examine` would be a grief tool.

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
