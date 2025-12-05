# Your First Game

This tutorial walks through creating a simple game world with rooms, items, and basic interactions.

!!! note "Work in Progress"
    This documentation is being developed. Check back soon for the full tutorial.

## Overview

You'll learn to:

1. Create rooms and connect them with exits
2. Add items players can pick up
3. Create simple NPCs
4. Add custom commands

## Creating Rooms

```python
from realm.core.objects import GameObject

# Create a starting room
tavern = GameObject(
    name="The Rusty Tankard",
    description="A cozy tavern with a crackling fireplace. The smell of ale fills the air.",
    tags=['room', 'start_room'],
)

# Create another room
street = GameObject(
    name="Main Street",
    description="A cobblestone street runs through the center of town.",
    tags=['room'],
)
```

## Connecting Rooms with Exits

```python
# Create an exit from tavern to street
exit_out = GameObject(
    name="out",
    description="The door leads to Main Street.",
    tags=['exit'],
    location=tavern,
)
exit_out.db.destination = street.id

# Create return exit
exit_tavern = GameObject(
    name="tavern",
    description="The door to The Rusty Tankard.",
    tags=['exit'],
    location=street,
)
exit_tavern.db.destination = tavern.id
```

## Adding Items

```python
# A simple item
sword = GameObject(
    name="rusty sword",
    description="An old sword, pitted with rust but still sharp.",
    tags=['thing', 'weapon'],
    location=tavern,
)
sword.db.damage = 5
```

## Next Steps

- Add behaviors to make objects interactive
- Create NPCs with AI behaviors
- Implement a combat system

See the [Architecture Overview](../architecture/overview.md) to understand how these pieces fit together.
