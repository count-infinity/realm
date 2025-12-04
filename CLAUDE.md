# REALM Project

Real-time Event-Action Layered MUD framework in Python.

## Reference Implementations (Git-ignored)

These folders contain existing MU* frameworks for reference. They are not part of REALM itself.
```
realm/
└── _reference/
    ├── CoffeeMud/           # Java MUD - combat, economy, crafting
    ├── evennia/             # Python MUD - Django-based, modern
    └── pennmush/            # C MUSH - softcode, permissions
```

**Do not modify files in these directories.** These are read-only study material.

When working in these reference framework folders, you may be a subagent focused on extracting patterns from that codebase.

## Notes for Subagents

### If working in _reference/CoffeeMud/
Focus: combat formulas, area/mob templates, economy systems, event-driven behavior system
CoffeeMud is verbose Java. Look for patterns, not code to copy.

### If working in _reference/evennia/
Focus: command parsing, typeclass system, how they handle inheritance, Portal/Server split architecture
Note what works well and what's over-engineered.

### If working in _reference/pennmush/
Focus: permission systems, softcode concepts, flag-based attributes, lock system
The C is old but the design concepts are battle-tested.