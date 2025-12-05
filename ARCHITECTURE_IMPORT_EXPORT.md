# Architecture Decision: Import/Export System for REALM

## Context

REALM needs a portable world specification system that allows builders to:
1. Define world content (rooms, objects, NPCs, scripts) in files outside the database
2. Import the same spec multiple times with different namespaces (e.g., casino.realm imported as "vegas-casino" and "atlantic-casino")
3. Detect drift between spec files and live database (Terraform/Helm-like workflow)
4. Transfer specs between different REALM game instances

This system must align with REALM's philosophy: it's a library, not an application to fork. Users should be able to manage world content through configuration and declarative specs without modifying REALM source code.

## Reference Implementation Analysis

### PennMUSH Approach
**Files examined**: `/home/realm-dev/realm/_reference/pennmush/src/create.c`

**How they solve it**:
- Objects created with `@create`, `@dig`, rooms linked with `@open`
- Each object gets a dbref (database reference number) that's permanent
- Parent objects via `@parent` provide attribute inheritance
- No formal export/import system - world exists only in database
- Manual reconstruction via textdumps or examining individual objects

**Strengths**:
- dbref system provides stable references
- Parent-based inheritance is simple and battle-tested
- Lock system on objects handles permissions cleanly

**Weaknesses**:
- No declarative world definition format
- No namespace isolation for imported content
- World content tightly coupled to database
- No built-in diff/drift detection

### CoffeeMud Approach
**Files examined**:
- `/home/realm-dev/realm/_reference/CoffeeMud/com/planet_ink/coffee_mud/Commands/Export.java`
- `/home/realm-dev/realm/_reference/CoffeeMud/com/planet_ink/coffee_mud/Commands/Import.java`
- `/home/realm-dev/realm/_reference/CoffeeMud/resources/examples/deities.cmare`

**How they solve it**:
- XML-based `.cmare` (CoffeeMud Area) files containing complete area definitions
- EXPORT command serializes areas/rooms/mobs to XML
- IMPORT command loads XML and creates objects in database
- Areas have unique IDs and can be loaded/unloaded at runtime
- Template-based mob/item definitions with instance spawning

**Strengths**:
- Complete export/import workflow
- XML format is verbose but self-documenting
- Areas are first-class entities with lifecycle management
- Template system separates prototypes from instances
- Dynamic loading/unloading of content

**Weaknesses**:
- XML is verbose and not builder-friendly
- No namespace concept for multiple imports of same area
- No drift detection between file and database
- Tight coupling to Java serialization patterns

### Evennia Approach
**Files examined**:
- `/home/realm-dev/realm/_reference/evennia/evennia/prototypes/README.md`
- `/home/realm-dev/realm/_reference/evennia/evennia/prototypes/spawner.py`
- `/home/realm-dev/realm/_reference/evennia/docs/source/Components/Prototypes.md`

**How they solve it**:
- Prototype system: Python dicts describing object templates
- Prototypes can be defined in modules (`settings.PROTOTYPE_MODULES`) or stored in database
- `spawn` command creates objects from prototypes
- Prototype inheritance via `prototype_parent` key
- Batch processors for running sequences of commands or Python code
- **Diff system**: `prototype_diff_from_object()` compares prototype to spawned object
- `batch_update_objects_with_prototype()` applies diffs to update spawned objects
- Tags track which objects were spawned from which prototype

**Strengths**:
- Dictionary format is Pythonic and easy to write
- Prototype inheritance is powerful and flexible
- **Drift detection already implemented** via diff system
- Protfuncs allow randomization and scripting
- Can update all instances of a prototype after changes
- Clear separation between prototype (template) and instance

**Weaknesses**:
- No namespace concept for multiple imports
- Prototypes are global by `prototype_key`
- No concept of "modules" that group related content
- Batch processors are either imperative (batchcommand) or code-based (batchcode)
- Module-based prototypes are read-only in-game

## Conflicts and Tradeoffs

### File Format: YAML vs Python Dict vs XML
**Conflict**: CoffeeMud uses XML, Evennia uses Python dicts, modern tools prefer YAML

**Analysis**:
- XML is too verbose for human editing
- Python dicts require valid Python syntax, harder for non-programmers
- YAML is human-friendly, supports comments, widely adopted (Kubernetes, Ansible, etc.)

**Decision**: Use YAML as primary format
- REALM can parse YAML to Python dicts internally (Evennia-style processing)
- YAML supports comments for documentation
- Familiar to modern devops users who understand Terraform/Kubernetes

### Namespacing: Global vs Scoped
**Conflict**: All three frameworks use global object spaces

**Analysis**:
- PennMUSH: dbrefs are global, no isolation
- CoffeeMud: Areas have IDs but can't have multiple instances of same area
- Evennia: prototype_key is global identifier
- **User requirement**: Same casino.realm imported as "vegas-casino" and "atlantic-casino"

**Decision**: Implement module namespacing
- Module = collection of related objects (like CoffeeMud's Area + Evennia's prototype grouping)
- Import command takes `--as <namespace>` flag
- Object IDs within module are scoped: `<namespace>:<local_id>`
- Database tracks module instances separately
- Allows same spec file to be imported multiple times

### Drift Detection: Evennia's Approach vs Terraform
**Conflict**: How to represent state differences?

**Analysis**:
- Evennia has `prototype_diff_from_object()` - compares prototype dict to object attrs
- Terraform has plan/apply workflow showing intended changes before execution
- User wants: see what changed between spec and database

**Decision**: Adopt Terraform-like workflow with Evennia's diff engine
- `realm plan spec.realm --as name` shows what would change (dry run)
- `realm apply spec.realm --as name` applies changes (creates/updates objects)
- `realm diff name` shows drift between spec and live objects
- Use Evennia's diff format internally, present as human-readable text

### Object References: Dbrefs vs Local IDs
**Conflict**: How do objects reference each other within a module?

**Analysis**:
- PennMUSH: #1234 dbrefs hardcoded everywhere
- CoffeeMud: Uses object names and area context
- Evennia: Prototypes resolve references at spawn time
- **Problem**: If same module imported twice, references must resolve correctly

**Decision**: Local IDs within module + resolution at import time
- Spec file uses local IDs like `room:lobby`, `npc:dealer`, `exit:front_door`
- On import, these become `<namespace>:lobby`, `<namespace>:dealer`, `<namespace>:front_door`
- Database stores actual UUID references
- Reverse mapping for export: UUID -> local ID

## Recommended Architecture

### File Format: REALM Module Spec (YAML)

```yaml
# casino.realm - Example module specification
module:
  key: casino
  version: "1.0"
  description: "A gambling casino with poker tables and slot machines"
  author: "builder1"

# Prototypes define reusable templates (Evennia-style)
prototypes:
  poker_table:
    tags: [thing, furniture]
    attributes:
      desc: "A green felt poker table with cup holders"
      seats: 8

  slot_machine:
    tags: [thing, interactive]
    attributes:
      desc: "A flashy slot machine with spinning reels"
      jackpot: 1000

# Objects are actual instances in the world
objects:
  - id: lobby
    name: "Casino Lobby"
    tags: [room]
    attributes:
      desc: |
        A glittering casino lobby with crystal chandeliers.
        Slot machines line the walls, their lights flashing.

  - id: poker_room
    name: "High Stakes Poker Room"
    tags: [room]
    attributes:
      desc: "A hushed room with several poker tables"

  - id: table_1
    name: "Poker Table #1"
    prototype: poker_table
    location: poker_room

  - id: slots_1
    name: "Lucky Seven Slot Machine"
    prototype: slot_machine
    location: lobby
    attributes:
      jackpot: 5000  # Override prototype value

# Exits connect rooms
exits:
  - id: lobby_to_poker
    name: "north"
    aliases: [n]
    source: lobby
    destination: poker_room

  - id: poker_to_lobby
    name: "south"
    aliases: [s]
    source: poker_room
    destination: lobby

# NPCs (future: could reference behavior scripts)
npcs:
  - id: dealer
    name: "Casino Dealer"
    location: poker_room
    tags: [npc]
    attributes:
      desc: "A professional dealer in a black vest"
      greeting: "Welcome to the high stakes table!"

# Scripts (future: softcode/Python behaviors)
scripts:
  - id: jackpot_timer
    type: ticker
    interval: 300  # 5 minutes
    target: slots_1
    code: |
      # Increase jackpot over time
      target.db.jackpot += 100
```

### Database Schema Additions

```sql
-- Track module instances
CREATE TABLE IF NOT EXISTS module_instances (
    namespace TEXT PRIMARY KEY,          -- e.g. "vegas-casino", "atlantic-casino"
    module_key TEXT NOT NULL,             -- e.g. "casino" (from spec file)
    spec_file TEXT NOT NULL,              -- Path to .realm file
    spec_hash TEXT NOT NULL,              -- SHA256 of file content for drift detection
    version TEXT,                         -- Module version from spec
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Track which objects belong to which module instance
CREATE TABLE IF NOT EXISTS module_objects (
    namespace TEXT NOT NULL,              -- e.g. "vegas-casino"
    local_id TEXT NOT NULL,               -- e.g. "lobby", "dealer"
    object_id TEXT NOT NULL,              -- UUID of actual GameObject
    object_type TEXT NOT NULL,            -- "room", "thing", "npc", "exit"
    PRIMARY KEY (namespace, local_id),
    FOREIGN KEY (object_id) REFERENCES objects(id) ON DELETE CASCADE,
    FOREIGN KEY (namespace) REFERENCES module_instances(namespace) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_module_objects_namespace ON module_objects(namespace);
CREATE INDEX IF NOT EXISTS idx_module_objects_object_id ON module_objects(object_id);

-- Track object attributes from spec (for drift detection)
CREATE TABLE IF NOT EXISTS module_object_spec (
    namespace TEXT NOT NULL,
    local_id TEXT NOT NULL,
    spec_data TEXT NOT NULL,              -- JSON of original spec for this object
    PRIMARY KEY (namespace, local_id),
    FOREIGN KEY (namespace, local_id) REFERENCES module_objects(namespace, local_id) ON DELETE CASCADE
);
```

### CLI Commands

```bash
# Import a module (creates new namespace)
realm import casino.realm --as vegas-casino

# Plan mode: show what would change (dry run)
realm plan casino.realm --as vegas-casino

# Apply changes to existing module instance
realm apply casino.realm --as vegas-casino

# Show drift between spec and database
realm diff vegas-casino

# Export module instance to file
realm export vegas-casino > exported_casino.realm

# List all imported modules
realm modules list

# Remove a module instance (deletes all objects)
realm modules remove vegas-casino

# Update module from modified spec
realm modules update vegas-casino --from casino.realm
```

### Design Rationale

#### Why YAML over Python dicts?
- **Accessibility**: Non-programmers can edit YAML without Python knowledge
- **Comments**: YAML supports inline documentation
- **Industry standard**: Kubernetes, Ansible, Docker Compose use YAML
- **Evennia compatibility**: YAML parses to Python dicts, can use same internal processing

#### Why namespace scoping?
- **Multiple instances**: User explicitly wants to import same spec multiple times
- **Isolation**: Changes to one instance don't affect others
- **Clean removal**: Deleting a namespace removes all its objects
- **No global pollution**: Doesn't conflict with other modules or hand-crafted objects

#### Why local IDs within modules?
- **Readability**: `room:lobby` is clearer than UUID or dbref
- **Portability**: Spec file isn't tied to specific database UUIDs
- **References work**: Exit from `lobby` to `poker_room` resolves correctly within namespace
- **Export preserves structure**: Exported file has same local IDs as original

#### Why Terraform-like workflow?
- **Safety**: Plan before apply prevents mistakes
- **Transparency**: User sees exactly what will change
- **Familiar**: Developers already know Terraform/Helm patterns
- **Drift detection**: Catches manual edits to imported objects

### Python/REALM Adaptations

1. **YAML to GameObject mapping**:
```python
# realm/modules/loader.py
def load_module_spec(filepath: Path) -> dict:
    """Load and validate a REALM module spec from YAML."""
    with open(filepath) as f:
        spec = yaml.safe_load(f)

    # Validate required fields
    if 'module' not in spec:
        raise ValueError("Missing 'module' section")

    return spec

def create_objects_from_spec(
    spec: dict,
    namespace: str,
    pm: PersistenceManager
) -> list[GameObject]:
    """Create GameObjects from spec, tracking in module tables."""
    objects = []
    id_map = {}  # local_id -> GameObject

    # Create prototypes first (stored as template objects)
    for proto_id, proto_data in spec.get('prototypes', {}).items():
        # Store prototype for later reference
        pass

    # Create rooms
    for obj_spec in spec.get('objects', []):
        obj = GameObject(
            name=obj_spec['name'],
            tags=obj_spec.get('tags', [])
        )

        # Set attributes
        for key, value in obj_spec.get('attributes', {}).items():
            obj.db.set(key, value)

        # Track in module system
        local_id = obj_spec['id']
        id_map[local_id] = obj
        objects.append(obj)

    # Resolve references (location, exits)
    for obj_spec in spec.get('objects', []):
        if 'location' in obj_spec:
            local_id = obj_spec['id']
            location_id = obj_spec['location']
            id_map[local_id].location = id_map[location_id]

    return objects
```

2. **Diff engine (adapted from Evennia)**:
```python
# realm/modules/diff.py
def compute_module_diff(
    spec: dict,
    namespace: str,
    pm: PersistenceManager
) -> dict:
    """
    Compare spec file to live database objects.

    Returns:
        diff dict with structure:
        {
            'objects': {
                'lobby': {'attributes': {'desc': ('old', 'new')}},
                'dealer': {'location': ('old_room_id', 'new_room_id')}
            },
            'added': ['new_object_id'],
            'removed': ['deleted_object_id']
        }
    """
    # Load current state from module_objects table
    # Compare to spec
    # Return structured diff
    pass

def format_diff_output(diff: dict) -> str:
    """Format diff as human-readable text (Terraform-style)."""
    lines = []

    for local_id, changes in diff.get('objects', {}).items():
        lines.append(f"~ {local_id}")
        for field, (old, new) in changes.items():
            lines.append(f"    {field}: {old} -> {new}")

    for local_id in diff.get('added', []):
        lines.append(f"+ {local_id}")

    for local_id in diff.get('removed', []):
        lines.append(f"- {local_id}")

    return "\n".join(lines)
```

3. **Export preserves local IDs**:
```python
# realm/modules/exporter.py
def export_module(
    namespace: str,
    pm: PersistenceManager
) -> dict:
    """
    Export module instance to spec dict.

    Preserves local IDs from original import.
    """
    # Query module_objects to get local_id -> object_id mapping
    # Load all objects
    # Reconstruct spec dict with local IDs
    # Convert object references back to local IDs
    pass
```

## Integration Points

### GameObject/Room/Player Hierarchy
- **No changes needed**: Existing GameObject class works perfectly
- Module system adds metadata layer on top
- Objects don't need to "know" they're part of a module
- Module tracking is in separate tables

### Persistence Layer (SQLite)
- **Addition**: New tables for module tracking
- **No breaking changes**: Existing objects table unchanged
- **Migration**: Add module tables via alembic or manual SQL
- **Performance**: Indexes on namespace and object_id for fast lookups

### Softcode/Script System (Future)
- **Placeholder**: `scripts` section in spec reserved for future use
- **Design**: Could reference Python entry points or inline softcode
- **Evennia pattern**: Could use callable registration system
- **PennMUSH pattern**: Could compile softcode to Python AST

## Implementation Phases

### Phase 1: MVP (Core Import/Export)
**Goal**: Get basic import/export working without drift detection

**Tasks**:
1. Define YAML schema for module specs
2. Implement YAML parser and validator
3. Add module_instances and module_objects tables
4. Implement `realm import` command
   - Parse YAML
   - Create GameObjects
   - Track in module tables
   - Resolve references
5. Implement `realm export` command
   - Query module_objects
   - Load GameObjects
   - Convert to YAML
   - Preserve local IDs
6. Basic error handling and validation

**Deliverable**: Can import casino.realm, export it back, re-import successfully

### Phase 2: Namespacing and Multiple Instances
**Goal**: Support importing same spec with different namespaces

**Tasks**:
1. Implement `--as <namespace>` flag
2. Add namespace prefix to object IDs in database
3. Update reference resolution to handle namespaces
4. Test: Import casino.realm as "vegas-casino" and "atlantic-casino"
5. Implement `realm modules list` command
6. Implement `realm modules remove <namespace>` command

**Deliverable**: Can have multiple instances of same module running

### Phase 3: Drift Detection and Plan/Apply
**Goal**: Terraform-like workflow with diff visualization

**Tasks**:
1. Add module_object_spec table to store original specs
2. Implement diff engine (based on Evennia's prototype_diff)
3. Implement `realm diff <namespace>` command
4. Implement `realm plan <spec> --as <namespace>` (dry run)
5. Implement `realm apply <spec> --as <namespace>` (update existing)
6. Hash tracking for spec files to detect external changes
7. Human-readable diff output formatting

**Deliverable**: Can see drift, plan changes, apply updates safely

### Phase 4: Prototypes and Templates
**Goal**: Reusable object templates within modules

**Tasks**:
1. Implement prototype system (Evennia-style)
2. Support `prototype:` key in object specs
3. Prototype inheritance within module
4. Prototype attribute merging
5. Export includes prototypes

**Deliverable**: Can define poker_table prototype, use for multiple instances

### Phase 5: Advanced Features
**Goal**: Polish and advanced use cases

**Tasks**:
1. Script system integration (placeholder -> implementation)
2. Validation improvements (schema validation, circular reference detection)
3. Import hooks for custom processing
4. Module dependencies (one module can reference another)
5. Incremental updates (only apply changed objects)
6. Backup/restore entire module state
7. Web UI for module management (future)

**Deliverable**: Production-ready module system

## Success Criteria

- [ ] Builder can write casino.realm in text editor
- [ ] `realm import casino.realm --as vegas` creates all objects
- [ ] Same spec can be imported as `atlantic` with separate objects
- [ ] `realm export vegas` produces YAML matching original structure
- [ ] Manual edits to vegas-casino objects show in `realm diff vegas`
- [ ] `realm plan casino.realm --as vegas` shows what would change
- [ ] `realm apply casino.realm --as vegas` updates modified objects
- [ ] Deleting vegas namespace removes all its objects cleanly
- [ ] Cross-module references work (vegas:lobby to atlantic:lobby would fail appropriately)
- [ ] System handles 1000+ objects per module performantly

## Open Questions for User

1. **Cross-module references**: Should one module be able to reference objects in another? (e.g., exit from vegas-casino to hotel-lobby in different module)

2. **Prototype visibility**: Should prototypes be global across modules or scoped to module?

3. **Version conflicts**: If spec file version changes, force re-import or allow partial updates?

4. **Ownership**: Should imported objects have an owner? If so, who?

5. **Locks**: Should module-imported objects have default locks? Can they be overridden locally?

6. **Behaviors**: For Phase 5, prefer Python entry points or inline scripting language?
