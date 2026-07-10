> **Historical document.** This is REALM's original pre-implementation
> plan, kept for provenance. It describes intentions from before the
> engine was built and is **not** kept in sync with the code. For the
> current state of the project see `BACKLOG.md` in the repository root
> and the [design notes](engine_vision.md); for how things actually work,
> the [Concepts](../concepts/character-creation.md) and
> [Architecture](../architecture/overview.md) docs are authoritative.

---

# REALM Framework Implementation Plan

## Vision

A Python MUD framework combining:
- **Combat depth** (CoffeeMud-style hack-and-slash out of the box)
- **Builder empowerment** (MUSH-style OLC + softcode scripting)
- **Low barrier to entry** (SQLite, simple setup, extensible core)
- **Reference implementation**: Space game (GURPS-based)

---

## Core Requirements

### 1. Object Model

**Philosophy**: Everything is a `GameObject` with behaviors attached. No rigid type hierarchy.

**Core Object Structure**:
```python
class GameObject:
    id: str                     # Unique identifier (dbref-like)
    name: str                   # Display name
    location: GameObject | None # Container (room, inventory, etc.)
    contents: List[GameObject]  # What's inside this object
    parent: GameObject | None   # Explicit @parent for inheritance
    owner: GameObject | None    # Who owns this object
    tags: Set[str]              # Flexible tagging (replaces rigid types)
    behaviors: List[Behavior]   # Attached behaviors
    locks: Dict[str, Lock]      # Permission locks
    _attrs: Dict[str, Any]      # Persistent attributes (.db access)
```

**Tags replace rigid types**:
- `room` - Is a location
- `exit` - Is a connection between rooms
- `player` - Is a player character
- `thing` - Is a portable object
- `zone:forest` - Belongs to forest zone
- `npc`, `shopkeeper`, `quest_giver` - Role tags

**Zones via tags**: Rooms tagged with `zone:Sherwood Forest` belong to that zone. Zone-based permissions check the tag.

**Attribute Inheritance**:
1. Check object's own attributes
2. Walk explicit `@parent` chain
3. Fall back to type-based ancestors (server-configured, optional)
4. `ORPHAN` flag or missing tag skips ancestor lookup

**Type Ancestors** (server config, not per-object):
```python
# In server settings
ANCESTORS = {
    'room': dbref_of_room_ancestor,
    'player': dbref_of_player_ancestor,
    'thing': dbref_of_thing_ancestor,
    'exit': dbref_of_exit_ancestor,
}
```

### 2. Event-Action Architecture

**Two-phase event model** (inspired by CoffeeMud):
1. **Validation phase** (`on_validate`): Any listener can veto
2. **Execution phase** (`on_execute`): Event is applied

**Event structure**:
```python
@dataclass(slots=True)
class Event:
    type: str                          # e.g., "speech", "attack", "enter"
    source: GameObject | None          # Who initiated
    target: GameObject | None          # Primary target
    location: GameObject | None        # Where it happened
    data: Dict[str, Any]               # Event-specific data
    cancelled: bool = False            # Set by validation phase
    messages: Dict[str, str] = field() # source_msg, target_msg, others_msg
```

**Core Event Types** (inspired by CoffeeMud triggers):

| Category | Events |
|----------|--------|
| **Movement** | `enter`, `leave`, `arrive`, `depart` |
| **Combat** | `attack`, `damage`, `death`, `kill`, `flee` |
| **Communication** | `speech`, `whisper`, `channel`, `emote` |
| **Items** | `get`, `drop`, `give`, `put`, `wear`, `remove`, `consume` |
| **Interaction** | `look`, `examine`, `use`, `open`, `close`, `lock`, `unlock` |
| **Commerce** | `buy`, `sell`, `bribe` |
| **Session** | `connect`, `disconnect`, `idle` |
| **Time** | `tick`, `hour`, `day` |
| **Magic** | `cast`, `affect`, `resist` |

### 3. Command System

**Command Parsing Pipeline**:
```
Input → Trim → Token Check → Alias Expand → Exit Match → Command Lookup
      → Permission Check → Switch Parse → Argument Parse → Execute
      → Softcode Fallback ($-commands)
```

**Special Tokens** (single-character shortcuts):
| Token | Expands To | Example |
|-------|------------|---------|
| `"` | `say` | `"hello` → `say hello` |
| `:` | `pose` | `:waves` → `pose waves` |
| `;` | `semipose` | `;'s dog` → `semipose 's dog` |
| `\` | `@emit` | `\A ghost appears!` → `@emit A ghost appears!` |
| `+` | Channel prefix | `+ooc hi` → `channel ooc=hi` |
| `@` | Builder command prefix | `@dig North` |

**Command Abbreviations**:
- Unique prefix matching: `l` → `look`, `i` → `inventory`
- Ambiguous prefixes show options: `"lo" matches: look, lock, logout`
- Reserved aliases for directions: `n`, `s`, `e`, `w`, `u`, `d`, `ne`, `nw`, `se`, `sw`

**Switch and Argument Parsing**:
```
@command/switch1/switch2 left_args = right_args
```
- Switches: `/switch` modifiers before the space
- Left/Right split at `=`
- Comma or space splitting configurable per command

**Softcode Command Fallback** (`$pattern:action`):
When no built-in command matches, search nearby objects for `$pattern` attributes:
1. Contents of current room
2. The room itself
3. Player's inventory
4. Zone objects (tagged with matching zone)
5. Global command room (Master Room)

### 4. Scripting System

**Syntax**: PennMUSH-style attribute patterns
```
&CMD_GREET obj = $greet *: say Hello, %0! Welcome to the realm.
&LISTEN_MAGIC obj = ^*casts*: say I sense magical energies!
&ON_ENTER obj = say Someone just arrived.
```

**Trigger Types** (from CoffeeMud research):

| Trigger | Fires When |
|---------|------------|
| `$pattern` | Player input matches pattern |
| `^pattern` | Overheard speech matches pattern |
| `ON_ENTER` | Something enters this location |
| `ON_LEAVE` | Something leaves this location |
| `ON_ARRIVE` | This object arrives somewhere new |
| `ON_LOOK` | This object is looked at |
| `ON_GET` | This object is picked up |
| `ON_DROP` | This object is dropped |
| `ON_GIVE` | This object is given away |
| `ON_RECEIVE` | This object receives something |
| `ON_ATTACK` | This object attacks or is attacked |
| `ON_DAMAGE` | This object takes damage |
| `ON_DEATH` | This object dies |
| `ON_KILL` | This object kills something |
| `ON_CONNECT` | Player connects (on player, room, zone) |
| `ON_DISCONNECT` | Player disconnects |
| `ON_TICK` | Periodic timer fires |
| `ON_USE` | This object is used |

**Softcode Substitutions**:
| Code | Meaning |
|------|---------|
| `%#` | Enactor (who triggered) |
| `%!` | Executor (this object) |
| `%n` | Enactor's name |
| `%0-%9` | Captured wildcard groups |
| `%l` | Enactor's location |

**Sandboxing & Quotas**:
- **Recursion limit**: 50 nested calls
- **Function limit**: 25,000 invocations per command
- **CPU time limit**: 1500ms per script execution
- **Memory limit**: TBD (RestrictedPython handles)
- **Object quota**: Configurable per-player limit (default 20)

### 5. Permission System

**Privilege Hierarchy**:
```
God (superuser) → bypasses everything
  ↓
Admin (wizard) → bypasses most locks, can modify any object
  ↓
Builder (staff) → can build, limited lock bypass
  ↓
Player → subject to all locks
  ↓
Guest → restricted, no building, limited commands
```

**Wizards bypass MOST locks** (recommendation based on PennMUSH patterns).
Exceptions: God-owned objects, certain hardcoded protections.

**Lock Types**:
| Lock | Controls |
|------|----------|
| `basic` | Who can pick up / traverse |
| `enter` | Who can enter this container |
| `use` | Who can trigger $-commands on this |
| `control` | Who can modify this object (delegation) |
| `zone` | Who controls objects in this zone |
| `speech` | Who can speak here |
| `teleport` | Who can teleport to this room |
| `examine` | Who can examine this VISUAL object |
| `give` | Who can give this away |
| `drop` | Who can drop this |
| `command` | Who can trigger commands on this |
| `listen` | Who can trigger listen patterns |

**Lock Syntax** (Python expressions for V1):
```
@lock obj = caller.has_tag('admin') or caller.db.karma > 100
@lock/enter room = caller.db.level >= 10
@lock/use vending = caller.db.coins >= 5
```

**Object Flags**:
| Flag | Effect |
|------|--------|
| `HALT` | Cannot execute any scripts/commands |
| `GAGGED` | Cannot communicate (say, pose, etc.) |
| `DARK` | Hidden from normal view |
| `QUIET` | Suppresses action feedback |
| `VISUAL` | Can be examined by anyone |
| `SAFE` | Protected from destruction |
| `ORPHAN` | Skips ancestor inheritance |

### 6. World Building (OLC)

**Core Commands**:
| Command | Purpose |
|---------|---------|
| `@create <name>` | Create a new object |
| `@dig <name> [= exits]` | Create a room with optional exits |
| `@open <exit> = <destination>` | Create an exit |
| `@link <exit> = <destination>` | Link exit to destination |
| `@desc <obj> = <description>` | Set description |
| `@name <obj> = <newname>` | Rename object |
| `@set <obj>/<attr> = <value>` | Set attribute |
| `@parent <obj> = <parent>` | Set inheritance parent |
| `@tag <obj> = <tag>` | Add tag |
| `@untag <obj> = <tag>` | Remove tag |
| `@lock[/<type>] <obj> = <expr>` | Set lock |
| `@destroy <obj>` | Destroy object |
| `@teleport <obj> = <dest>` | Move object |
| `@chown <obj> = <newowner>` | Change ownership |

**Export/Import** (for version control):
```yaml
# room_tavern.yaml
id: tavern_001
name: "The Rusty Sword Tavern"
tags: [room, zone:town, indoor]
desc: |
  A cozy tavern with a roaring fireplace...
attributes:
  capacity: 50
  music: "bard_tune_3"
exits:
  north: town_square_001
  out: town_square_001
```

### 7. Persistence

**Strategy**: Simple "save now" vs "save on interval"
- Player changes: Save immediately
- World changes: Batch save every 30 seconds
- Shutdown: Full save

**Database**: SQLite (dev), PostgreSQL (production option)

**Scale Target**: 10s of concurrent players, ~100K objects

### 8. Process Architecture

**Single Process with Gateway/Server Split**:
```
┌─────────────────────────────────────────────────────┐
│              REALM Process (asyncio)                │
├─────────────────────────────────────────────────────┤
│  Gateway Layer                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │  Telnet  │  │WebSocket │  │   SSH    │         │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘         │
│       └─────────────┼─────────────┘                 │
│                     ↓                                │
│  ┌────────────────────────────────────────────────┐│
│  │  Message Queue (asyncio.Queue)                 ││
│  │  - Buffers during server reload                ││
│  └────────────────────────────────────────────────┘│
│                     ↓                                │
├─────────────────────────────────────────────────────┤
│  Server Layer                                       │
│  ┌────────────────────────────────────────────────┐│
│  │  Command Dispatcher → Event Bus → Persistence  ││
│  └────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

**Hot Reload Strategy** (if not too complex):
1. Signal handler catches reload request
2. Server layer saves state, stops processing
3. Gateway layer queues incoming messages
4. Reload Python modules
5. Server layer restarts, resumes from queue
6. Brief pause (~1-2 seconds), no disconnects

**V1 Fallback**: Simple restart, players reconnect.

---

## Architectural Insights from Reference Frameworks

### From Evennia
- **Portal/Server split**: Two-process model for hot reload
- **Attribute system**: `obj.db.attr = value` pattern
- **Tags**: Flexible categorization system
- **Typeclass inheritance**: Useful but can be over-engineered

### From CoffeeMud
- **CMMsg**: Two-phase event model (validate → execute)
- **Behaviors**: Composable, runtime-attachable
- **50+ trigger types**: Comprehensive scripting hooks
- **Scriptable.html**: Rich scripting documentation

### From PennMUSH
- **Softcode**: `$command:action` pattern matching
- **Locks**: Boolean expression evaluation
- **32+ lock types**: Fine-grained permissions
- **Ancestors**: Type-based default parents
- **Command parsing**: Token replacement, prefix matching

---

## Implementation Plan

### Step 1: Foundation
- `realm/core/objects.py` - GameObject, AttributeProxy
- `realm/core/events.py` - Event, EventBus (two-phase)
- `realm/core/behaviors.py` - Behavior base class
- `realm/core/tags.py` - Tag system
- `realm/persistence/` - SQLite storage

### Step 2: Gateway/Server
- `realm/gateway/session.py` - Session management
- `realm/gateway/telnet.py` - Telnet protocol
- `realm/gateway/websocket.py` - WebSocket protocol
- `realm/server/dispatcher.py` - Command routing

### Step 3: Command System
- `realm/commands/parser.py` - Tokenizer, prefix matching, aliases
- `realm/commands/base.py` - Command decorator/class
- `realm/commands/builtin/` - look, say, move, inventory, etc.

### Step 4: OLC Commands
- `realm/commands/olc/` - @create, @dig, @desc, @set, @parent, @tag, @lock

### Step 5: Scripting
- `realm/scripting/sandbox.py` - RestrictedPython wrapper
- `realm/scripting/triggers.py` - $command and ^listen matching
- `realm/scripting/functions.py` - Built-in script functions

### Step 6: Permissions
- `realm/permissions/locks.py` - Lock types and evaluation
- `realm/permissions/flags.py` - HALT, GAGGED, DARK, etc.
- `realm/permissions/roles.py` - God, Admin, Builder, Player, Guest

### Step 7: Combat & Behaviors
- `realm/combat/` - Attack, damage, death events
- `realm/behaviors/` - Aggressive, Wandering, Shopkeeper

### Step 8: Reference Game
- `examples/spacegame/` - GURPS space game demo

---

## Open Questions

1. **Alias storage**: Per-player aliases in attributes, or separate system?
2. **Channel system**: How should chat channels work?
3. **Mail system**: In-game mail between players?
4. **Help system**: How to organize and display help?
5. **Logging**: What to log and where?

---

## Implementation Status

- [x] Clean up CLAUDE.md
- [x] Fix .gitignore paths
- [x] Explored reference implementations
- [x] Refined requirements with PM review
- [x] Create foundation: GameObject, Event, Behavior
- [x] Build gateway/server with asyncio
- [x] Implement command system
- [x] Add OLC commands
- [x] Build scripting with sandboxing
- [x] Add permission/lock system
- [x] Implement combat and behaviors
- [x] Create reference space game
