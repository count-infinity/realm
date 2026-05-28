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

### Action Propagation — Remaining Work

The propagation engine, `GameObject.msg()` wiring, and the EventBus retirement are done. What's left:

- [ ] Migrate the parallel `realm/commands/builtin/` command set to `propagate(Action(...))`
  - These commands aren't wired by the default game (game.py has its own inline say/pose/look/etc.) but are exposed via `register_all_commands` for game authors who want the richer set
  - Currently each command iterates `obj.location.contents` and calls `.msg()` directly — TODO markers are in place at every spot
  - Affected: `communication.py` (say/pose/semipose/emit/whisper/ooc/shout), `movement.py` (go/direction), `look.py` (look/examine), `inventory.py` (get/drop/give/put), `olc/admin.py` if it grows event-emitting commands
  - Pattern reference: `cmd_say` in `realm/server/game.py`

- [ ] Wire movement events (`event:on_leave` / `event:on_enter`)
  - Today `_handle_exit` in `realm/server/dispatcher.py` and the builtin `cmd_go` mutate `player.location` directly
  - `GuardBehavior` already listens for these via `on_check` and is ready to block — it just needs something to fire them
  - Without these, mob behaviors (AggressiveBehavior, GuardBehavior, FleeingBehavior) sit dormant

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

### Session Output
- [ ] Out-of-band flush for messages emitted outside command processing
  - Today, `game._on_command` awaits `session.flush_output()` after each command, so command-driven output flushes correctly
  - Messages emitted from a tick, NPC AI, or scheduled task without an in-flight command sit on the session output queue until something else triggers a flush
  - Two viable approaches:
    1. Flush-on-enqueue hook: schedule a flush task whenever `Session.send_nowait` puts on a non-empty queue
    2. Periodic flush task in the protocol/server layer (configurable interval)
  - Required before NPCs, scripts, or world ticks can speak to players without being driven by a player command

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

1. **OOB flush strategy**: Command-time flush works (dispatcher awaits `flush_output` after each command). For messages emitted without an in-flight command (ticks, NPC AI, scripts), should we use flush-on-enqueue (lower latency, more wakeups) or a periodic flush task (simpler, configurable interval)? See Priority 2 → Session Output.
2. **Multiple connections**: What message should old session receive when player connects from new location?
3. **Config paths**: How should relative paths work when running from subdirectories?

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
- [x] Lift propagation engine from solar_frontiers into `realm/core/propagation.py`
  - `Action`, four `Step` classes (Actor/Room/RoomContents/Target), `PropagationEngine`
  - Permission pass + reaction pass both run to completion (block does NOT short-circuit)
  - Trailing actions depth-limited to `MAX_TRAILING_DEPTH` (3)
  - `visit_check`/`visit_react`/`visit_observe_check`/`visit_observe_react` on `GameObject`
  - `on_check`/`on_react` on `Behavior` (alongside legacy `validate_event`/`handle_event`)
- [x] Implement `GameObject.msg()` to bridge actions to session output
  - `_msg_handler` slot + `set_msg_handler` / `clear_msg_handler` / `msg_contents(text, exclude=...)`
  - `Session.link_player`/`unlink_player` wires/clears handler via `session.send_nowait`
  - `deliver_messages(action)` routes accumulated messages by audience (`actor`/`target`/`room`)
  - `propagate(action, deliver=True)` convenience function drives the full pipeline

- [x] Refactor `cmd_say` and `cmd_pose` end-to-end as canonical examples
  - Added `ROOM_TARGET_CHAIN` for broadcast actions (speech/emote/connect/disconnect)
  - Inline registrations in `realm/server/game.py` rewritten

- [x] Migrate connect / disconnect / create lifecycle in `realm/server/game.py`
  - `_on_session_disconnect`, `_do_connect`, `_do_create` use `propagate(Action(...))`
  - New `_announce_connect(player, returning=)` helper

- [x] Migrate `realm/combat/system.py` to `propagate(action, deliver=False)`
  - Three `_emit_*_event` methods replaced with `_propagate_attack`/`_propagate_damage`/`_propagate_death`
  - Cancel-checks rewritten as `action.blocked` checks
  - `event_bus` parameter removed from `CombatSystem.__init__` and `create_combat_system`

- [x] Migrate `realm/combat/behaviors.py` to `on_check`/`on_react`
  - Five behaviors converted (Aggressive, Defensive, Guard, Fleeing, Combatant)
  - `EventType.X` → `action.action_type` string match
  - `GuardBehavior`'s veto becomes `action.block(reason)`

- [x] Clean up `realm/scripting/`
  - Deleted dead `ScriptEngine.handle_event` (no callers)
  - `EventTrigger.matches_event` now takes an `Action` and matches against `action_type` suffix

- [x] Retire `realm/core/events.py`
  - Deleted `Event` / `EventBus` / `EventType`
  - Removed legacy `validate_event`/`handle_event` from `Behavior` and `on_event_validate`/`on_event_execute` from `GameObject`
  - Deleted `tests/test_events.py`; updated `test_behaviors.py`, `test_persistence.py`, `test_spacegame.py`, `test_scripting.py`
