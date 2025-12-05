# REALM Development Backlog

Prioritized list of improvements, features, and technical debt items.

## Priority 0 - Core Architecture (Library Design)

REALM must be usable as a library, not an application to fork.

### CLI & Project Scaffolding
- [x] Implement `realm init <gamename>` command
  - Creates project structure with `config.py` and `data/` directory
  - Generates `config.py` with sensible defaults (Python-based config)
  - Generates starter `data/welcome.txt`

- [ ] Implement `realm migrate` command
  - Creates/updates database schema
  - Handles schema versioning

- [x] Implement `realm start` that loads from config
  - Reads `config.py` for ports, protocols, database
  - Supports callbacks: `init_world`, `register_commands`, `register_protocols`

### Protocol Registration System
- [x] Implement `GameServer.register_protocol(name, class, **kwargs)`
  - Allows users to register custom protocols without modifying REALM
  - Protocol classes instantiated with session_manager, on_command, host, port

- [ ] Implement config-based protocol loading (YAML)
  ```yaml
  protocols:
    godot:
      enabled: true
      port: 4002
      class: "mygame.protocols.GodotServer"
  ```
  - REALM imports and instantiates the class automatically

- [ ] Implement entry point protocol discovery
  - `[project.entry-points."realm.protocols"]`
  - Allows pip-installable protocol plugins

### Configuration System
- [x] Create settings loader (`realm/config/loader.py`)
  - Loads from `config.py` in current directory
  - Falls back to defaults
  - Python-based config for maximum flexibility

- [x] Define Settings dataclass with all config options
  - Server settings (ports, hosts, game_name)
  - Database settings (db_path, flush_interval)
  - Callbacks (init_world, on_start, on_stop, register_commands, register_protocols)

### Command Registration
- [ ] Implement decorator-based command registration
  ```python
  from realm import command

  @command("wave", aliases=["wav"])
  async def cmd_wave(ctx):
      await ctx.send("You wave.")
  ```

- [ ] Auto-discover commands from user's `commands/` directory

## Priority 1 - Should Address Soon

### Code Quality
- [ ] Add explicit encoding to welcome file read: `read_text(encoding='utf-8')`
  - Location: `realm/server/game.py:242`
  - Reason: Cross-platform safety

- [ ] Document `time.monotonic()` migration decision
  - Location: `PLAN.md` or new `docs/decisions/`
  - Reason: Python 3.14 compatibility rationale should be recorded

### Testing
- [ ] Add tests for welcome screen auto-flush functionality
- [ ] Add integration tests for protocol connection lifecycle
- [ ] Add tests for websocket welcome screen parity

## Priority 2 - Nice to Have

### Configuration
- [ ] Make welcome file path configurable via settings
  - Current: Hardcoded to `config/welcome.txt`
  - Should come from settings.yaml

### Logging & Debugging
- [ ] Add debug log when flush is called without a writer set
  - Location: `realm/gateway/session.py` in `flush_output()`
  - Helps diagnose protocol integration issues

### Session Management
- [ ] Use `AUTHENTICATING` session state during login flow
  - Currently goes directly from `CONNECTED` to `PLAYING`
  - The state exists but is never used

### Code Clarity
- [ ] Create `SessionWriter` type alias for readability
  - `SessionWriter = Callable[[str], Awaitable[None]]`

- [ ] Enhance telnet `_setup_session()` comment to explain negotiation timing

## Priority 3 - Future Enhancements

### GMCP (Generic MUD Communication Protocol)
- [ ] Add GMCP support to telnet protocol
  - Telnet sub-negotiation for structured data (JSON)
  - Negotiate GMCP capability with client (IAC WILL/DO GMCP)
  - `TelnetProtocol.send_gmcp(package, data)` method
  - Track `gmcp_enabled` per connection

- [ ] Protocol-agnostic structured data API (Option 1)
  - `Session.send_structured(package, data)` method
  - Telnet: sends via GMCP
  - WebSocket: sends as JSON message with type field
  - Allows game code to send data without knowing protocol

- [ ] Common GMCP packages
  - `Char.Vitals` - HP, mana, stamina updates
  - `Char.Status` - level, class, position
  - `Room.Info` - room name, exits, area
  - Hook into EventBus for automatic updates

### Welcome Screen
- [ ] Add ANSI color support to default welcome screen
- [ ] Add max file size check for welcome.txt (prevent memory issues)
- [ ] Handle empty welcome.txt explicitly (use default or send nothing?)

### Event System
- [ ] Implement `GameObject.msg()` to bridge events to session output
  - Currently a no-op placeholder
  - Needed for events to automatically message players

### Softcode / Player Scripting
- [ ] Implement $-command search on nearby objects
  - Location: `realm/server/game.py:408-411` (TODO comment exists)
  - Enables player-defined commands on objects

### Import/Export System (Module Specs)
- [ ] Portable world specs (`.realm` YAML files)
  - Define rooms, objects, NPCs, exits, scripts in declarative YAML
  - Terraform/Helm-like workflow: `plan` → `apply` → `diff`
  - Multiple instances with namespacing: `realm import casino.realm --as vegas-casino`
  - Drift detection between spec files and live database
  - **Full architecture spec**: `ARCHITECTURE_IMPORT_EXPORT.md`
  - **Implementation phases**:
    1. MVP: Basic import/export without drift detection
    2. Namespacing and `--as` flag for multiple instances
    3. Drift detection and plan/apply workflow
    4. Prototypes and templates
    5. Scripts, dependencies, advanced features
  - **Open questions** (see architecture doc):
    - Cross-module references
    - Prototype visibility scope
    - Version conflict handling
    - Object ownership
    - Default locks
    - Scripting approach (Python entry points vs inline)

## Questions for Product Manager

These items need clarification before implementation:

1. **Flush lifecycle**: Should there be background/periodic flushing, or only after commands?
2. **Event-to-message bridge**: How should `GameObject.msg()` connect to session output?
3. **Multiple connections**: What message should old session receive when player connects from new location?
4. **Config paths**: How should relative paths work when running from subdirectories?

## Completed

- [x] Auto-flush welcome screen on connection (telnet)
- [x] Auto-flush welcome screen on connection (websocket)
- [x] Configurable welcome screen via `config/welcome.txt`
- [x] Python 3.14 asyncio compatibility (`time.monotonic()`)
- [x] Pass writer to `create_session()` for protocol-agnostic flush
- [x] Update venv instructions in `CLAUDE.md`
- [x] Document REALM-as-library philosophy in `CLAUDE.md`
- [x] Update protocol docs to show registration patterns (not REALM modification)
- [x] Set up MkDocs documentation framework
