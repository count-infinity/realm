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

### Action Propagation

The propagation engine, `GameObject.msg()` wiring, the EventBus retirement, the
builtin command migration, and unified movement events are all done. The action
framework is fully in place.

### Maintainability review findings (2026-07-02) — not yet fixed

Full-codebase review (3 subsystem passes). The structural tier was fixed the
same day (see Completed); these remain, roughly by impact:

- [ ] **Scripting follow-ups** (engine is wired as of 2026-07-02, see
  Completed): zone objects and the Master Room are still unimplemented in
  `get_search_objects` (plan.md search order steps 4–5); scripts can only
  emit communication commands (say/pose/emit/whisper) — anything else is
  logged and dropped until scripted objects can drive the dispatcher
  (ties into `@force`); listen triggers hear `extra["message"]` actions
  (say/shout/ooc/emit) but not poses.
- [ ] **Spacegame content:** the doctor's `$help` softcode is shadowed by
  the builtin `help` command (softcode only sees *unknown* commands) —
  rename the trigger or document the precedence.
- [ ] **Rewrite or delete `examples/spacegame/commands.py`.** It imports a
  command API that doesn't exist (`realm.commands.registry`, `context`,
  `Command`) — cannot be imported. Add an import smoke-test for examples.
- [ ] **Extract auth from GameServer.** `_do_connect`/`_do_create` compare
  plaintext passwords (`# TODO: Hash this!`), are untested, and live on the
  server object. Extract an `AuthService(persistence)` with salted hashing.
- [ ] **Unify the two AST validators.** `sandbox.py` and `locks.py` each
  hand-roll eval/exec validation with diverged blocklists. One shared
  safe-eval policy module; both consume it. (No RestrictedPython anywhere —
  plan.md's sandboxing claim is aspirational.)
- [ ] **Fix the flag namespace.** `flags.py` docstring claims a `flag:` prefix
  but `_flag_tag` returns bare values — `set_flag(obj, Flag.WIZARD)` silently
  grants ADMIN via the role check on the `wizard` tag.
- [ ] **Lock follow-ups** (core enforcement landed 2026-07-02, see
  Completed): `use` lock not yet checked on softcode $-command triggers,
  `command`/`listen` locks unenforced, `teleport` lock not checked by
  `@teleport` (admin-gated anyway), `examine` lock not consulted by
  look/examine, `page`/`mail` have no systems yet. The gated-broadcast
  pattern drops trailing-action messages (pre-existing movement trade-off,
  now shared by `gate_action`).
- [ ] **Inventory action boilerplate + bulk gap.** The ~18-line
  propagate/block/move/deliver ritual repeats 4× in `inventory.py`, and
  `get all`/`drop all` skip propagation entirely — behaviors fire for
  `get sword` but not `get all`. Extract one item-transfer helper.
- [ ] **Combat ruleset duplication.** Weapon-prop access ×5, DamageType
  coercion ×2, two dice parsers; base `Ruleset.roll_dice`/`get_modifier`
  have zero callers. Shared helpers on the base class.
- [ ] **Spacegame duplicates Combatant.** `SpaceCharacter.heal/take_damage`
  vs `Combatant` both write `db.hp` through different paths. Pick one owner.
- [ ] **Two examine implementations** (`look.py` vs `admin.py`) and a
  hand-maintained help category map in `utility.py` that must be edited for
  every new command — derive categories from a `Command.category` field.
- [ ] **Persistence follow-ups:** N+1 query in `load_all` (per-object
  reference SELECT), per-object commits in `_flush_queue` (batch in one
  transaction), no schema versioning (`PRAGMA user_version` + migrations),
  `repository.py` interface incompatible with `manager.py`.
- [ ] **Gateway duplication:** telnet/websocket repeat the server-wrapper
  shape; websocket defines its writer twice (handler swaps mid-connection).
  Extract a small base or shared `connect_session` helper.
- [ ] **Stub commands registered as real:** `@force`, `@boot`, `recall`,
  `uptime`, `time` print "not implemented"; `@nuke` doesn't disconnect its
  target's session. Implement or stop registering.
- [ ] **Half-implemented combat behaviors** silently no-op (attack_delay,
  taunt, flee movement, wander movement — ruff F841 flags the dead locals).
- [ ] **Config drift:** spacegame `WELCOME_BANNER` key is ignored by the
  loader (only `welcome_file` is supported); README says `realm start --init`
  but the flag is `--reset-db`; `world.py` calls `room.contents.append(...)`
  which is a no-op (contents returns a copy — API footgun worth a docstring
  or a real mutator).
- [ ] **Layering:** `realm.commands` re-exports from `realm.server.dispatcher`
  (server → commands → server cycle, currently dodged with a deferred import
  in `game.py`). Consider moving CommandContext/CommandDispatcher into
  `realm.commands` proper.
- [ ] **Action-type constants.** `"event:on_enter"` etc. are magic strings
  across behaviors/combat/movement — a typo silently disables a behavior.
- [ ] Remaining ruff findings (~20): stub-related unused variables, long
  lines, `str`-enum modernization. `ruff check` is clean-ish; consider a
  `[tool.ruff]` config + CI gate.

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

## Priority 2 — Designed, not yet built

### Perception follow-ups (core shipped 2026-07-02, see Completed)

- Recognition/introduction systems: strangers see "a tall woman"
  instead of "Alice" — override point is
  `GameObject.get_display_name(looker)`; needs per-looker knowledge
  state ("who have I been introduced to").
- Observation-reveals-concealed: a skill check that makes an
  `invisible` secret door visible TO THAT LOOKER (per-looker reveal
  state, not tag removal).
- Wearable gear granting perception tags (nightvision goggles) — needs
  the equipment/wear system.
- Sound in darkness: "Someone says" leaks that speech happened (by
  design — you HEAR the unseen); consider a `silent` action variant and
  language garbling on the same per-looker path.
- Stealth vs Perception contests (infiltration stories): active hiding
  as opposed to flat `invisible` — skill-check-driven visibility.

### True item stacks (`stackable` tag + quantity)

Display grouping (shipped 2026-07-02, see Completed) is presentation
only — three apples are still three GameObjects. True stacks are the
data-layer complement for commodities (credits, ammo, rations) where
quantity semantics and scale matter (10,000 coins should be ONE object,
not 10,000 rows and 10,000 propagation-chain bystanders).

Design sketch:
- Opt-in via `stackable` tag; `db.quantity` (default 1). Non-stackable
  items never merge — per-unit identity is the default.
- **Merge rule**: on drop/put/give, merge into an existing stack only if
  same name AND same prototype/parent AND no differing db attributes
  (strict equality of `db.all()` minus quantity) — "close enough" merging
  corrupts enchanted-coin cases.
- **Split rule**: `get 5 coins` splits: clone the stack object with
  quantity=5 (fresh id), decrement source; delete source at 0.
  Count-aware syntax extends the matcher's `name-N` parsing
  (`get 5 coins` vs `get coins-5` — the former is a count, the latter a
  pick; disambiguate by stackable tag).
- **Propagation**: actions target the stack object; `extra["quantity"]`
  carries how many are involved. Behaviors see one visit per stack, not
  per unit (that's the point).
- **Display**: falls out of the existing grouping formatter —
  `numbered_name(stack, stack.db.quantity)`.
- **Persistence**: quantity is an ordinary attribute; no schema change.
- Follow-ups it unlocks: `get all coins`, `give 100 credits to Bob`,
  currency-aware shops.

## Completed

- [x] **THE NEXAGEN HEIST: infiltration gameplay complete (2026-07-03).**
  Story 1 (Stealth & B&E) from the infiltration user stories is fully
  playable end to end. Verified: 615 unit tests (29 new) + a 24-check
  full playthrough over telnet — challenge at the lobby, dark-alley
  fire-escape climb, looted toolkit, nightvision stairwell crossing,
  hide, sneaking past a live patrolling guard, electronic suite lock
  defeated by skill, concealed safe found behind the painting, safe
  cracked, documents taken, clean exfiltration — plus the Story 6
  softcode blackout epilogue. All lean objects + tags + attributes +
  behaviors, per the architecture goal:
  - `realm/core/checks.py`: 3d6 roll-under skill checks vs
    `db.skill_<name>` with GURPS-style attribute defaults
    (SKILL_DEFAULTS), margins, opposed `contest()`, and a pluggable
    resolver (`set_check_resolver` — tests inject a deterministic one).
    Softcode gets `skill_check()`/`contest()` functions.
  - Physical state vs permission: `closed` tag + `db.locked`/`key_id`
    on exits AND containers — one mechanism for doors and safes.
    Commands: `open/close/lock/unlock` (carried key via `db.unlocks`),
    `pick` (skill vs `db.lock_difficulty`; `db.lock_skill` for
    electronic locks; -5 without a `lockpicks`-tagged tool),
    `use <item> on <target>` (keycards toggle their lock; everything
    else propagates `item:on_use` for behaviors/ON_USE softcode).
  - Skill-gated exits: `db.check_skill`/`check_difficulty`/
    `check_fail_msg` on an exit (the fire escape) — generalizes to any
    athletic obstacle.
  - Wearables: `wearable` tag, `db.slot` conflicts, `db.grants_tags`
    applied while worn (nightvision goggles); innate tags survive
    removal.
  - Stealth: `hide` (darkness +3) grants `hidden`; loud actions break
    it via a propagation observer; `search` runs Observation contests
    against hiders and reveals `conceal_difficulty` scenery with
    custom `reveal_msg`.
  - NPC kit (`realm/behaviors/`): WatchfulBehavior (challenges visible
    arrivals, contests sneaks, bumps own `db.alert_level` on a spot)
    and PatrolBehavior (walks a route of EXIT NAMES through the real
    movement gate — closed doors stop patrols; state in owner.db so it
    persists). Registered with BehaviorRegistry → survives save/load.
  - Server tick loop (`TICK_INTERVAL`, default 4s): drives
    `should_tick` behaviors and flushes all sessions — closes the
    long-standing OOB-flush backlog item (NPCs act without waiting for
    player input).
  - Ambient persistence accessor (`set_active_manager`/
    `get_active_manager`, same pattern as the propagation singleton) so
    behaviors resolve exit-destination IDs after a restart.
  - Dispatcher: multi-word exit names ("fire escape") walkable by
    typing them (full raw input tried in exit fallthrough).
  - `examples/spacegame/nexagen.py`: the tower zone — 10 rooms, tram
    link from the Promenade, guards, locker/goggles/lockpicks, badge
    door, concealed wall safe, PROJECT LONGSHADOW documents, and a
    pure-softcode ON_USE power panel that toggles the floor-46
    blackout.
  Remaining story gaps → still-open items: social contests as commands
  (Fast-Talk NPC conviction states), building alert zones, guard
  combat response/backup, disguises, timed effects, `open` for
  revealable paintings vs search (search chosen), Observation-based
  per-looker reveals.
- [x] **Perception: per-looker rendering + darkness/invisibility
  (2026-07-02).** Verified: 586 unit tests (23 new) + an 18-check live
  telnet drive. Extends solar_frontiers infiltration user stories
  (Story 6: Blackout Infiltration, added to that doc's addendum).
  - `realm/core/perception.py`, tag-driven: `dark` rooms are pitch
    black unless lit (`light`-tagged object present — including carried:
    a held torch lights the room for everyone) or the viewer has
    `nightvision`; `invisible` beats sight unless the viewer has
    `see_invisible`; admins see all; you always see yourself.
  - Per-looker delivery: `deliver_messages` formats every message per
    recipient (`format_message(msg, looker)`); participants are named
    via the `GameObject.get_display_name(looker)` hook (the override
    point for future recognition/disguise systems). Two bystanders in
    one room can read different lines: "Someone says" vs "Alice says".
    Unseen participants render as "Someone"/"something" with no
    article.
  - One rule set, every surface: unseen objects are absent from
    `render_room` (dark rooms render "It is pitch black here."),
    untargetable (`get gem` in the dark: "You don't see 'gem' here" —
    own inventory stays usable), and masked in messages. Secret exits
    (`invisible` on an exit) vanish from the Exits line but stay
    traversable by name — classic secret doors.
- [x] **Article-aware message tokens (2026-07-02).** The per-audience
  system (actor/target/room templates on Action, routed by
  deliver_messages with exclusion) already gave "You pick up X" vs
  "Bob picks up X"; now the sentences read right too.
  `format_message` supports `{target:a}` ("an apple", honoring
  db.article and proper nouns) and `{target:the}` ("the apple") for
  actor/target/tool. Builtin get/drop/give/put use them; bulk
  summaries speak naturally ("You pick up 2 apples and a rusty
  sword."). Verified: 563 tests + 13-check live drive incl. actor
  vs bystander perspectives. Per-looker perception rendering is
  designed under Priority 2.
- [x] **Display grouping + dynamic articles/plurals (2026-07-02).**
  Verified: 558 unit tests (28 new) + a 10-check live telnet drive.
  - `realm/core/language.py`: articles and plurals computed at display
    time, never stored (deliberately unlike Evennia, whose
    `get_numbered_name` writes "an apple"/"three foos" into DB aliases
    from the render path). Bare-noun names; capitalized = proper noun =
    no article; `db.article` / `db.plural` overrides for English's
    exceptions ("some sand", "staves").
  - `render_room` groups identical things — "3 apples", "a rusty
    sword" — by lowercased name, first-seen order, `no_group` tag
    opt-out. O(n) hash pass: benchmarked 0.04ms for a 100-object room,
    1.3ms for 10,000. Style overridable per game via
    `set_group_formatter` (e.g. "apple (x3)").
  - Matcher: computed plural is a searchable name (`get apples` works,
    nothing persisted), leading articles in queries forgiven
    ("get an apple") with exact-match-first safety ("The End" still
    wins over stripping), and identical twins auto-pick the first
    instead of prompting "apple-1 or apple-2?" (name-N still available;
    differing names still prompt).
- [x] **Lock enforcement (2026-07-02).** Locks are live, not write-only.
  Verified: 530 unit tests (21 enforcement + 23 search) + a 26-check
  telnet drive (builder locking items/rooms/exits live, custom fail
  messages, clears, restart persistence, admin bypass).
  - Locks are first-class in the propagation check pass:
    `GameObject.visit_check` calls `enforce_lock_on_action` (locks.py)
    before behaviors, mapping action types to lock types — `item:on_get`
    → basic, `on_drop` → drop, `on_put` → enter (container), all
    room-directed communication → speech; `item:on_give` checks the
    TOOL's give lock from the actor (the tool isn't chain-visited).
  - Movement gate: `move_through_exit` checks the exit's `basic` lock
    and the destination's `enter` lock before any events fire.
  - `Action.add_message(..., success_only=True)` staging: blocked
    actions suppress their own outcome lines while behavior-added
    messages still deliver — communication commands bake success lines,
    propagate once (observer/script ordering preserved), then report
    `block_reason`. Shared `gate_action` helper for gate-then-mutate
    flows; `get all`/`drop all` now gate per item (they bypassed
    locks AND behaviors entirely).
  - `@lock` validates at write time (bad expressions rejected with the
    error), defaults to `basic` (was the unreadable `'default'` type),
    rejects unknown types; failure text overridable per object via
    `lock_fail_<type>` attributes.
- [x] **Intuitive name targeting (2026-07-02).** One tiered matcher
  (`realm/core/search.py`) behind every `find_*` helper, global lookups,
  container/exit resolution, and scripting `get()`. Informed by a review
  of Evennia's search internals (no Solr there — Django ORM iexact/iregex
  + one scored in-Python word-prefix matcher, which we adopted):
  - Tiers: exact (name+aliases, ci) → scored word-prefix (every query
    word must prefix-match a name word left-to-right; top-scoring bucket
    only — `prom` finds "Station Promenade", `big sw` prefers "Big
    Sword") → substring (off for exits).
  - Ambiguity is surfaced, never guessed: helpers raise
    `AmbiguousMatchError`; the dispatcher renders "Which 'red' do you
    mean? red crystal-1 (here), red sphere-2 (carried)" with `name-N`
    picking, context via `describe_match`.
  - Typo/edit-distance deliberately kept OUT of targeting (Evennia's
    boundary too); candidate for a "did you mean?" suggestion tier.
  - Follow-ups: search-visibility lock (hide objects from targeting),
    stacking ("get 3 coins"), nickname/personal-alias layer,
    did-you-mean suggestions on no-match.
  - **Full-text search decision (2026-07-02, benchmarked):** Evennia's
    in-game help uses `lunr.py` (evennia/help/utils.py — boosted fields
    key>aliases>category>tags, stemming, stop-word exceptions for
    command-like words, `query*` wildcard retry, exact-match promotion;
    index rebuilt per query). lunr.py benchmarks (pure Python,
    worst-case corpus): 500 docs ≈ 0.15s build / 6ms query; 5K ≈ 1.7s /
    51ms; 25K ≈ 7.7s / 400ms. Verdict: adopt the Evennia lunr pattern
    when REALM grows a prose help system (hundreds of docs — perfect
    fit; add `lunr` as an optional extra then). For world-content
    search (`@find` over 10K+ objects) prefer SQLite FTS5 (already
    shipped, C-speed, incremental updates) over a cached lunr index.
    Keep both OUT of targeting — targeting stays deterministic tiered
    matching.
- [x] **Softcode script engine wired into the server (2026-07-02).** The
  MUSH pillar is live. Verified: 486 unit tests (19 new) + an 18-check
  telnet drive (shipped NPC softcode, live `@set`-authored triggers,
  restart persistence).
  - `GameServer` owns `script_engine` (config: `ENABLE_SCRIPTING`, default
    on). The dispatcher's unknown handler now does the `$`-command
    fallback over `get_search_objects` (room contents → room → inventory).
  - New `PropagationEngine.add_observer/remove_observer`: the script
    engine observes every propagated action, so `^listen` triggers
    overhear speech (say/shout/ooc/emit — not whispers) and `ON_<EVENT>`
    attribute triggers fire on the same stream behaviors see (`ON_ENTER`
    on the room/witnesses, `ON_ARRIVE` on the mover). Blocked actions
    fire nothing. Observer registered on start, removed on stop.
  - Script output goes back through propagation as real actions —
    players hear NPC responses, behaviors can react, and other NPCs'
    listens can chain, bounded by `MAX_SCRIPT_DEPTH` (3).
  - `ScriptFunctions` (50+ functions) finally injected into sandbox
    execution, wrapped by the call/time limiters (`_wrap_function` had
    zero callers). `pemit`/`remit`/`oemit` queue typed deliveries drained
    on the event loop after execution (scripts run in a worker thread);
    `oemit` actually excludes now; `get()` uses the public persistence
    lookups.
  - `is_simple_script` is prefix-based (a simple script starts with a
    script command); Python one-liners like `say(f"{dice(2,6)}")` now
    route to the sandbox instead of dying in the command parser.
  - `get_event_triggers` matches attribute keys case-insensitively
    (`db.on_enter` and `db.ON_ENTER` both work, consistent with
    CMD_/LISTEN_ parsing).
  - Deleted the engine's dead `_emit_*` log-stubs and the
    `get_engine`/`set_engine`/`softcode_fallback` module globals.
- [x] **Clean-code baseline (2026-07-02).** Verified live: 467 unit tests +
  a 30-check telnet drive (fresh world, two players, two restarts, OLC).
  - One canonical room renderer: `realm/core/render.py:render_room(room,
    viewer)` replaced five divergent copies (movement.py, look.py,
    dispatcher.py, game.py, olc/admin.py). `look` now honors
    `db.description` fallback everywhere.
  - Command split-brain fixed: `GameServer.start()` registers
    `realm/commands/builtin` (incl. OLC, permission-gated); the weaker
    inline game.py command set is deleted. Tested code == running code.
  - Services flow through context: `CommandDispatcher.persistence` /
    `.session_manager` are declared and wired at startup;
    `ctx.persistence` / `ctx.session_manager` / `ctx.dispatcher`
    replace module-global `set_persistence`/`set_session_manager`
    service locators. Fixed latent bug: modify.py imported the
    `_persistence` *value* at import time (always None) — `@desc`/`@name`/
    `@set`/`@lock` changes were never saved.
  - OLC exits persist: `@dig`/`@open`/`@link` stored a live GameObject in
    `db.destination_obj`, which `json.dumps` cannot serialize — every OLC
    exit command crashed against the real database. Now only the string ID
    is stored; `resolve_exit_destination` (core/movement.py) resolves it
    via the persistence cache on every movement path (fixes `go <exit>`
    for string-destination exits too). Regression test added against real
    SQLite.
  - Public persistence lookups: `get_cached`/`all_cached`/`find_cached`
    replace `_object_cache` reaches in game.py, dispatcher, OLC.
  - Shared command helpers in `commands/base.py`: `resolve_target` (was
    duplicated byte-for-byte in modify.py and admin.py),
    `find_object_global`, `save_object`; deleted dead `send`/`send_to_room`.
  - `init_world` now runs only when the database is empty (its documented
    contract) — rerunning it every boot recreated world objects over the
    loaded ones, stranding players in stale duplicate rooms.
  - Clean shutdown: `run_forever` awaits the signal-triggered stop task
    (asyncio.run was cancelling it mid-flight, stranding the aiosqlite
    thread); `stop()` destroys sessions before `wait_closed()` (3.12.1+
    waits on client connections); sessions now own a `closer` so the
    server can hang up (quit/shutdown no longer wait for the client);
    `destroy_session` is idempotent, flushes farewells, and
    `destroy_session_soon` keeps strong task refs (bare `create_task` was
    being GC'd before running).
  - Flush loop survives exceptions; `GameServer.startup_room` is public
    (spacegame config no longer pokes `_startup_room`); deleted dead
    `find_event_triggers` (referenced the retired `Event` type); ruff
    autofixes (130: import order, unused imports, f-strings) + pytest green.
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

- [x] Migrate the builtin command set (`realm/commands/builtin/`) to `propagate(Action(...))`
  - `communication.py` (say/pose/semipose/emit/whisper/ooc/shout), `look.py` (look/examine),
    `inventory.py` (get/drop/give/put), `movement.py` (go/direction) all propagate actions
    instead of iterating `location.contents` and calling `.msg()` directly

- [x] Wire `event:on_leave` / `event:on_enter` into builtin `cmd_go`
  - on_leave runs `deliver=False` and gates the move (block aborts before location mutates)
  - on_enter is informational (fires after arrival; block is advisory)
  - both use `ROOM_TARGET_CHAIN` since the target IS the room

- [x] Unify the two movement paths so movement events fire everywhere
  - New `move_through_exit()` in `realm/core/movement.py` owns the on_leave/on_enter
    sequence; both builtin `cmd_go` and the dispatcher's `_handle_exit` (exit-name
    dispatch — the default-game path) call it, so `GuardBehavior` et al. now fire on
    both paths and can't drift apart
  - `_handle_exit` resolves the destination via new `_resolve_destination` (prefers the
    in-memory `destination_obj`, falls back to the string `destination` ID via cache)
  - Added dispatcher-path tests in `tests/test_builtin_commands.py` (event fires +
    block honored)

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
