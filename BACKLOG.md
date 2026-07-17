# REALM Development Backlog

Prioritized list of improvements, features, and technical debt items.

**NORTH STAR: VISION.md** (root — the durable invariants) + the
capability tracker **docs/design/engine_vision.md** — REALM is the Godot of
MU*s: the engine obfuscates MU* complexity, games are softcode.
Almost all functionality reachable from softcode, with permissions on
softcode (`controls()` authority model). Every feature ships in two
layers — hardcoded mechanism + softcode surface; a feature without its
softcode surface is half-shipped and its other half belongs here.
The vision doc's capability matrix is the coverage tracker.
**docs/design/adventure_coverage.md** grades the engine against nine
published one-shots (B2, Tomb of Horrors, Death House, Caravan to Ein
Arris, The Haunting, Death Station, Food Fight, Ypsilon 14...) — its
gap clusters (check-modifier providers, ranged combat, disposition
states, economy kit, followers, @force) are the demand signal for
prioritizing below.

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

### Entitlement-based security: roles carry granular grants (requested 2026-07-16)

Today privilege is a five-rung `IntEnum` ladder (GUEST < PLAYER <
BUILDER < ADMIN < GOD, assigned by player tags) and every privileged
code path is a rung comparison. That conflates capabilities: `>=
Role.ADMIN` simultaneously means see-through-darkness, bypass-locks,
teleport-anywhere, and control-everything — you cannot grant one
without the rest. The AWS policy model (documents, conditions,
resources) is more than we need; the right middle is one hop simpler:
**players have roles; a role is a named set of granular entitlements;
call sites ask for the entitlement they actually mean** —
`has_entitlement(actor, 'FORCE_ALL')` — and never compare rungs.

Design sketch:

- **Entitlement** = a namespaced string constant from a small registry
  (typo-guarded at boot, like behavior ids). **Role** = a named
  entitlement set. Role *assignment* stays exactly as it is (tags on
  the player; multiple role tags = union of their entitlements).
- **Built-in roles reproduce today's ladder verbatim** (guest ⊂ player
  ⊂ builder ⊂ admin ⊂ god as nested grant sets), so the cut-over has
  zero behavior change and the ladder remains the zero-config default.
- **Roles as data**, like `skill_def`: a `role_def` object (name +
  entitlement list) merges over the builtins at `@reload`, so a game
  mints custom staff ranks in-world — a "warden" who can
  `TELEPORT_ANY` but not `CONTROL_ALL`, an "architect" who builds
  without seeing invisible. This is the whole payoff of the refactor.
- **`controls()` keeps its ownership/delegation model** (self, owner,
  world-trusts-world, Penn delegation, control lock) — only its role
  rungs become entitlement checks. Same for lock evaluation.
- **Quell** already resolves to PLAYER; under entitlements, quelled =
  "resolve with the player role's set". Unchanged semantics.
- **Two layers, per the vision**: engine mechanism + softcode surface
  (`has_entitlement(obj, 'X')` read-only in scripts; lock DSL grows
  `caller.has_entitlement('x')`).

Call-site inventory — the entire ladder surface today (small, which is
what makes this cheap):

- [ ] `permissions/locks.py:178` — GOD bypasses all locks →
      `LOCK_BYPASS_ALL`
- [ ] `permissions/locks.py:182` — ADMIN bypasses locks, except
      CONTROL of god-owned objects → `LOCK_BYPASS` (keep the
      rival-authority carve-out: a bypass entitlement never beats an
      owner holding `LOCK_BYPASS_ALL`)
- [ ] `permissions/locks.py:254` — ADMIN controls everything →
      `CONTROL_ALL` (this is the `FORCE_ALL` example: @force,
      possession, and mutation all ride `controls()`)
- [ ] `permissions/locks.py:256` — BUILDER controls unowned non-player
      objects → `CONTROL_UNOWNED`
- [ ] `core/movement.py:271` — ADMIN tunnels destination locks →
      `TELEPORT_ANY`
- [ ] `core/perception.py:48` — ADMIN sees in darkness / through
      invisibility → `SEE_ALL`
- [ ] `server/dispatcher.py` — `Command.permission` tier strings
      (`"player"/"builder"/"admin"/"god"`) become a required
      entitlement per command (`BUILD` for OLC, `ADMIN_TOOLS`, ...);
      `has_permission()` / `PERMISSION_LEVELS` retire with it
- [ ] Migration tests: (a) ladder-equivalence — every existing
      permission test passes unmodified with the default role table;
      (b) decoupling proof — a custom `role_def` granting exactly one
      entitlement gets that capability and no other

Open questions (product pass before building):

- Deny/negative grants? Lean **no** — additive-only sets keep
  reasoning and the union rule trivial; AWS-style deny is where the
  complexity we're avoiding lives.
- Per-player one-off grants without a role? Lean **no** — mint a role;
  it keeps the audit surface ("who can force players?") one query.
- Entitlement naming: `FORCE_ALL` flat constants vs `force.all`
  namespacing — decide once, registry-enforced either way.
- NPCs rank as PLAYER today (possession work, 2026-07-05) — keep, via
  the player role's set.

### Maintainability review findings (2026-07-02) — not yet fixed

Full-codebase review (3 subsystem passes). The structural tier was fixed the
same day (see Completed); these remain, roughly by impact:

- [ ] **Scripting follow-ups** (engine wired 2026-07-02; actuators +
  builder loop 2026-07-04, see Completed): the global Master Room is still
  unimplemented in `get_search_objects` (docs/design/original_plan.md
  search order step 5; zone masters — step 4 — shipped, see Completed);
  scripts can emit communication commands plus
  `move`/`trigger` — `get`/`drop`/`open` and full dispatcher access
  (`@force`) remain; listen triggers hear `extra["message"]` actions
  (say/shout/ooc/emit) but not poses.
- [ ] **Spacegame content:** the doctor's `$help` softcode is shadowed by
  the builtin `help` command (softcode only sees *unknown* commands) —
  rename the trigger or document the precedence.
- [x] ~~**Rewrite or delete `examples/spacegame/commands.py`.**~~ DONE
  2026-07-05: deleted with the legacy set/get_combat_system globals (see
  Completed TIER 2/3 entry).
- [x] ~~**Extract auth from GameServer**~~ DONE 2026-07-05:
  AuthService(persistence) with rate limiting; see Completed.
- [x] ~~**Unify the AST validators.**~~ DONE 2026-07-04:
  `realm/core/safe_eval.py` is the one policy module; sandbox, locks,
  and strategy conditions all consume it (locks got strictly stronger —
  `getattr` and private names are now rejected there too).
- [ ] **Fix the flag namespace.** `flags.py` docstring claims a `flag:` prefix
  but `_flag_tag` returns bare values — `set_flag(obj, Flag.WIZARD)` silently
  grants ADMIN via the role check on the `wizard` tag.
- [ ] **Lock follow-ups** (core enforcement 2026-07-02; use/listen/
  command + controls() landed 2026-07-04, see Completed): `teleport`
  lock now checked by scripted `teleport_obj` but still not by
  `@teleport` (admin-gated anyway), `examine` lock not consulted by
  look/examine, `page`/`mail` have no systems yet. The gated-broadcast
  pattern drops trailing-action messages (pre-existing movement trade-off,
  now shared by `gate_action`).
- [ ] **Softcode platform remaining** (engine_vision.md matrix; the
  2026-07-04 tranche shipped locks/combat/verbs/waits — see Completed):
  ~~@force~~ (DONE 2026-07-05); persistent waits (current one-shots
  are in-memory like MUSH @waits); `put <thing> in <container>` script
  verb.
- [ ] **Script-thread vs event-loop trade-off** (documented in
  engine_vision.md): sandbox mutations run in the worker thread and rely
  on the GIL; session/persistence work is queued and drained on-loop.
  If a race ever bites, queue mutations wholesale or run scripts
  on-loop with an instruction budget.
- [ ] **Inventory action boilerplate + bulk gap.** The ~18-line
  propagate/block/move/deliver ritual repeats 4× in `inventory.py`, and
  `get all`/`drop all` skip propagation entirely — behaviors fire for
  `get sword` but not `get all`. Extract one item-transfer helper.
- [ ] **Combat ruleset duplication.** Weapon-prop access ×5, DamageType
  coercion ×2, two dice parsers; base `Ruleset.roll_dice`/`get_modifier`
  have zero callers. Shared helpers on the base class.
- [ ] **Two examine implementations** (`look.py` vs `admin.py`) and a
  ~~hand-maintained help category map~~ (DONE 2026-07-05: Command.category).
- [ ] **Persistence follow-ups:** N+1 query in `load_all` (per-object
  reference SELECT), no schema versioning (`PRAGMA user_version` +
  migrations), `repository.py` interface incompatible with `manager.py`.
  Consider SQLite WAL mode for crash-robustness. (FIXED 2026-07-03: the
  flush loop now sweeps ALL dirty objects in one transaction — pure
  gameplay mutations previously never persisted unless something
  incidentally called save(); crash-loss is now genuinely bounded by
  FLUSH_INTERVAL. Verified by unit tests + a live SIGKILL drive.)
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
  - Location: new `docs/decisions/`
  - Reason: Python 3.14 compatibility rationale should be recorded

### Testing
- [ ] Add tests for welcome screen auto-flush functionality
- [ ] Add integration tests for protocol connection lifecycle
- [x] ~~Add tests for websocket welcome screen parity~~ DONE 2026-07-16:
  `make_ws_writer` renders markup segments from the first byte (the old
  pre-handler writer leaked raw pipe markup on the welcome screen);
  pinned in tests/test_gateway_funnel.py.

## Priority 2 - Nice to Have

### Configuration
- [x] ~~Make welcome file path configurable~~ DONE: `WELCOME_FILE` in
  config.py (realm/config/loader.py; default `data/welcome.txt`).

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

- [x] ~~Protocol-agnostic structured data API (Option 1)~~ DONE
  2026-07-16: `Session.send_oob(package, data)` is the protocol-blind
  call — telnet ships it as GMCP, websocket as `{'type': 'oob'}` JSON
  frames (the websocket half was missing; web clients silently got no
  Room.Info/vitals). Inbound is symmetric: GMCP subnegotiation and
  `{'type': 'oob'}` messages both land in `session.oob_supports`. The
  same pass unified INPUT: protocols decode bytes →
  `session.submit_input()` → a per-session pump drains the one input
  funnel (`_on_command`) in arrival order — no more per-line tasks
  (telnet) vs awaited-inline (websocket) divergence, and the dead
  double-write to the input queue is gone. Telnet NAWS now feeds the
  same `terminal_width/height` session data as websocket `resize`.
  AresMUSH steal-list #1 (aresmush-comparison.md). Tests:
  tests/test_gateway_funnel.py.

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

### Builder Tools
- [ ] **In-game multiline text editor** (Evennia `EvEditor` analog)
  - A stateful line-editor input mode for editing multiline text in-game:
    room/object descriptions, `[[...]]`/softcode attr bodies, mail, notes,
    boards. Enter with e.g. `@edit here/desc`; edit over multiple lines;
    `:w` save, `:q` quit, `:wq`, plus line ops (list `:`, insert, delete,
    replace/search, undo). Also seen as `ed`/`wedit`/`beginedit` in
    LDMud/DikuMUD3 and CoffeeMud's genEd prompt-editor — a near-universal
    builder QoL tool the catalog surfaced (docs/design/command-catalog.md).
  - **Build on what exists**: the session input-capture already powering
    `prompt()` (`session.input_handler` / `_prompt_future`, single-line);
    an editor is a richer, persistent input mode over the same choke point —
    it intercepts each line, maintains a text buffer + cursor, and commits
    the buffer back to the target attr on `:w`. Reboot-safety like chargen
    (persist the buffer + re-install on reconnect) is a nice-to-have.
  - **Authority**: gate writes through the same path as `@set`/`@desc`
    (`controls()` / attribute permissions) — the editor is just an input UI
    over an authorized attribute write, no new permission surface.
  - Softcode surface: a way to open the editor on an attr from softcode
    (mirrors how `prompt()` is exposed), so builders can wire "edit this"
    affordances.

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

- [x] **LIGHTHOUSE-TUTORIAL FEEDBACK: 19 fixes (2026-07-09).** 892
  tests (16 new). From playtesting the tutorial:
  - **Bugs**: @dig/@open reject a duplicate exit name in a room;
    `search` finds concealed OBJECTS via a flat Observation check vs
    `conceal_difficulty` (was a nonsense Stealth contest against a
    statless item — you could never find the key); @behavior tolerates
    commas inside param values (a taunt with a comma no longer breaks).
  - **Builder tools**: `@eval <code>` (arbitrary softcode, the Penn
    think<<>> — via new ScriptEngine.run_code); `@foreach <search> =
    <cmd>` (bulk ops, %o = each #id); `@stats` (tick interval, behavior
    load, waits, encounters — lag visibility); `@rolls on/off` (echo
    check dice); `quell`/`unquell` (drop to mortal perception+authority
    for honest testing — get_role returns PLAYER when `quelled`);
    `@detail/remove <obj> = <n>`; `@behavior/set` (edit params in
    place, e.g. a new ticker interval); exit prefix matching
    (`trapd`→`trapdoor`, dispatcher `_find_exit` now uses the tiered
    matcher).
  - **Design**: a CARRIED light must be `wielded` to illuminate (a
    lantern in the pack no longer lights); CoffeeMud-style perception
    markers `(glowing)`/`(magic)`/`(hidden)` in room listings via
    `display_markers` (gated by looker capability; kept OUT of message
    substitution so speech stays clean).
  - Answered: `detect_lies` exists (IQ-6); `@examine` already shows raw
    description + attrs; multiple `script_ticker`s work via distinct
    `attr`+`interval`. Tutorial corrected (down not down/south, conceal
    the key, quell to test) and docs updated.
  - Deferred (documented): ON_ENTER script output arrives before the
    room render — use `wait 0` to defer an effect a beat; a proper
    render-ordering pass is future work.
- [x] **CONFIGURABLE TEXT ENCODING (2026-07-09).** 877 tests (3 new).
  User saw garbled glyphs (em-dash in the chargen menu) on a non-UTF-8
  client. The server was ALWAYS sending correct UTF-8; the garble is
  client-side charset. Per user direction (keep UTF-8, don't dumb
  output down to ASCII): telnet output encode + input decode now use a
  config `ENCODING` setting, **default "utf-8"**, threaded config →
  GameServer → TelnetServer → TelnetProtocol (GMCP stays UTF-8 per
  spec; errors='replace' so a bad byte never crashes the writer).
  config.py.template documents it (set your client to UTF-8; latin-1/
  cp437 only for legacy playerbases). Live-verified the em-dash
  round-trips as its 3 UTF-8 bytes.
- [x] **AREAS SYNC LIKE TERRAFORM + two real flakes killed
  (2026-07-07).** 874 tests (8 new); 20 consecutive clean full-suite
  runs.
  - **In-game area workflow**: `@export <zone>` /
    `@import <name>` (PLAN) / `@import/apply` / `@areas`, all over a
    sandboxed `data/areas/` (name-only, path-escape rejected).
  - **Stable-id sync** (worldio `diff_plan` → `apply_plan`): re-import
    updates the area IN PLACE, matched by UUID — idempotent, no
    duplicate castles (fresh-id `import_objects` kept as the CLI clone
    path). Terraform-shaped plan (create / ~update with field diffs /
    orphan / conflict). Every touched object control-gated; orphans
    reported never deleted; membership computed (zone rooms + contents
    by location, NOT tagged — no area:/zone: conflation).
  - **REAL BUG caught by a flaky test**: `apply_plan` resolved
    intra-batch references via the persistence cache, so an exit's
    location came out None when its room saved later in set-iteration
    order. Fixed: references resolve against the apply batch first
    (as import_objects already did). This is why the test flaked.
  - **Two timing flakes eliminated at the source**:
    test_session's idle_time / touch tests asserted on wall-clock
    jitter (`new <= old` on microsecond gaps) — rewritten with a
    frozen `time.monotonic` (monkeypatch) to assert the real contract
    deterministically. No more coin-flip tests.
- [x] **D20 IS A REAL SYSTEM: whole-package swap (2026-07-07).** 866
  tests (5 new) + a 4-check live drive of GAME_SYSTEM=\"d20\".
  - Closed the half-wiring: `GameSystem.resolve_check` owns NON-combat
    skill resolution, and the server installs it via set_check_resolver
    at startup (cleared on stop). GURPS = 3d6 roll-under (default);
    D20 = d20 + skill-bonus vs DC 15 roll-HIGH. Before this, `d20`
    combat rolled d20 but stealth/persuade still rolled 3d6 — now the
    ENTIRE package swaps. checks._default_resolver → public
    default_resolver so systems can delegate.
  - D20 chargen sets `armor_class` (10 + DEX mod) — the ruleset's
    required stat that chargen never wrote.
  - Config is boot-fixed: characters stamped `db.game_system` at
    creation; login WARNS on mismatch ("created under 'gurps', server
    now runs 'd20'"); the generated config.py.template documents
    GAME_SYSTEM as a once-only deployment choice; new
    docs/guides/game-systems.md (comparison table, the swap warning,
    a write-your-own subclass).
- [x] **THE DIE ROLLS: Penn-parity gaps closed (2026-07-07).** 861
  tests (9 new, incl. the user's PennMUSH die ported verbatim as the
  regression).
  - **eval_attr(obj, 'attr', *args)** — Penn's u(): evaluate an
    attribute as a FUNCTION and return its `result`; args bind as
    arg0../%0..; runs with the CALLER's authority (executor unchanged,
    like Penn — borrowed code can't steal the target's powers); secret
    attrs refuse; recursion capped at 8.
  - **|v reverse video** (SGR 7) in markup + Style + encoder;
    `ansi()`'s 'i' now Penn-faithfully maps to inverse (|i stays
    italic).
  - **|/ newline markup** — multiline values writable from plain @set
    one-liners.
  - Verified: the full die ($roll trigger → rand → eval_attr face art
    with inverse-video blocks → pemit → real SGR at the edge) + the
    custom lock-failure message path.
- [x] **EVERY HELP ENTRY HAS AN EXAMPLE (2026-07-07).** 852 tests.
  - In-game `help <command>`: all 57 argument-taking commands gained a
    concise Example block in their docstrings (copy-pasteable real
    invocations — `pay 25 to ogre`, `@attr vault/gm_notes = secret`,
    `queue shoot thug`); the 18 no-argument commands' usage lines ARE
    their examples.
  - Softcode reference: all 87 functions carry an `Example:` docstring
    line; the generator surfaces it as a fourth table column, so
    examples regenerate with the API (scripts/gen_softcode_docs.py).
- [x] **COLOR AT THE EDGE (2026-07-07).** 852 tests (16 new); docs
  shipped with it (guides/color.md + regenerated softcode reference).
  - **No ANSIString class** — the deliberate anti-Evennia decision:
    color is |-markup inside ordinary str; the whole pipeline is
    markup-blind; rendering happens ONCE per protocol at write time.
    realm/core/markup.py owns semantics: parse→(Style, text) segments,
    strip/visible_len/pad/truncate (the only raw-vs-visible code),
    escape, to_ansi.
  - **Minimal SGR**: codes only on style change (adjacent same-style
    fragments coalesce — tested: '|rab|rcd|ref' = ONE escape), combined
    params, single trailing reset (no prompt bleed). Split-safety
    regression-tested: marked-up text split at EVERY index still
    parses/renders.
  - **Edges**: telnet renders ANSI (or strips for db.color=False —
    `color on|off` player command); WebSocket ships structured
    segments {text, segments:[[stylekey, text]...]} — no ANSI→HTML
    parsing ever. Extension path: parser reads one char after '|',
    so |#F00 truecolor slots in later.
  - **Softcode**: Penn-style `ansi('rh', text)` (h=bright,
    UPPER=background) + `escape()`; raw pipes work in @desc/say/
    [[...]] today. Room render colorized (|c title, |g exits) as the
    adoption starter.
- [x] **AREAS AS FILES + ATTRIBUTE FLAGS (2026-07-07).** 836 tests
  (12 new); docs shipped WITH the features.
  - **World import/export** (realm/persistence/worldio.py + `realm
    export/import` CLI): JSON area files carrying attrs (softcode
    travels free), tags, locks, behaviors, references. Import mints
    FRESH ids with deep reference remapping (location/owner/parent AND
    id-bearing attribute values — exit destinations, spawner lists);
    external refs resolve against the live world or drop cleanly;
    passwords always stripped; `--zone castle` exports an area
    (rooms + contents + masters) — zones are shippable. Newer-format
    guard. Closes the old ".realm import/export" backlog item.
  - **Attribute flags** (realm/core/attrflags.py + `@attr` command):
    the four load-bearing Penn flags — `secret` (controllers-only
    reads, enforced in get_attr/has_attr/search_world/@examine-path),
    `visual` (shown on plain player examine), `safe` (@set/@wipe/
    set_attr refuse; @wipe spares them), `no_clone` (skipped by
    @clone). One dict (`db.attr_flags`) in the house style. REALM
    keeps open-reads as the DEFAULT (mechanics depend on it) — the
    deliberate inversion of Penn's model, documented. Penn's full
    ~30-flag inventory (verified against attrib.h/atr_tab.c) recorded
    for the deferred items: trees, per-attr ownership, NEARBY,
    enum/rlimit.
  - **Docs**: NEW guides/world-management.md (search, zones, flags,
    import/export, safety valves) + reference/softcode.md
    AUTO-GENERATED from the live API (75 functions;
    scripts/gen_softcode_docs.py regenerates) — new capabilities and
    everything prior now covered; nav + index updated.
- [x] **THE WORLD ANSWERS: queries + zones (2026-07-07).** 823 tests
  (9 new).
  - **Query engine** (realm/core/query.py): `find_objects(tag/tags/
    attr[=value]/name_like/limit)` over the identity map (whole world
    in RAM; ~15ms per 100K scan). Surfaces: `@find/attr key[=value]`
    joins /tag and /owner; softcode `search_world(...)` capped at 500.
  - **Protected attributes**: softcode can no longer read `password`
    (get_attr/has_attr/search_world all refuse) — closed the
    hash-disclosure hole flagged in the design discussion.
  - **Zones** (realm/core/zones.py): rooms carry `zone:<name>` tags;
    any `zone_master`-tagged object sharing the tag is the area brain.
    THREE seams wired: trigger search step 4 (zone-wide $-commands and
    ^listens — the Penn Zone Master Room, finally implemented from
    docs/design/original_plan.md), event witnessing (the master's
    ON_ENTER/ON_DEATH fire for events in member rooms), and
    `zone_property(room, name)` —
    numeric policy where overlapping zones take max; the death award
    consults `xp_multiplier` (`@set Castle Zone/xp_multiplier = 1.2`
    is the user's +20% XP zone, one attribute, no scripts per kill).
  - `@zone` builder command (add/remove/master/rooms/inspect);
    softcode `zone_rooms('castle')` / `zones_of(here)`.
- [x] **THE TUTORIAL IS TRUE: Getting Started docs (2026-07-06).**
  814 tests; 14-check live drive runs the tutorial's command sequence
  near-verbatim against a fresh default game. MkDocs Material was
  already wired — docs stay plain Markdown (readable on GitHub),
  `mkdocs serve`/`build` for HTML.
  - Rewrote getting-started/ (installation from git with the
    pip-install-later note, quickstart, first-game) and added the
    5-part **Abandoned Lighthouse** tutorial (public-domain premise):
    rooms/details → locked trapdoor + hidden key → NPCs/behaviors/
    clone → softcode ($cmd, ^listen, ON_ENTER trap, inline [[...]]
    cached-roll description) → banshee (fear wail), combat/loot,
    ferryman ON_PAYMENT bribe. Each part ends with a Learn-more box.
  - **First character on a fresh database becomes SUPERUSER**
    (god tag, announced at creation) — no more sqlite surgery;
    AuthService owns the save.
  - Writing the docs found a REAL bug: `@dig room = a, b` created BOTH
    names as outbound exits (even `= north, south` made a wrong-way
    south). Fixed to Evennia semantics: first name out, second name
    (or compass opposite) back, in the new room.
- [x] **SPEAKING CLIENT: GMCP / out-of-band channel (2026-07-06).**
  813 tests (9 new). The gateway now speaks structured data:
  - **Session OOB channel**: `session.send_oob(package, dict)` +
    `set_oob_writer` (protocol installs it); GameObject mirror
    `msg_oob`/`set_oob_handler` wired by link_player — engine code
    emits unconditionally, NPCs/plain clients no-op.
  - **Telnet GMCP** (option 201): offered at connect (IAC WILL GMCP);
    client DO wires the channel; outbound frames IAC SB GMCP
    "Package.Sub {json}" IAC SE with IAC-escaping; the byte machine
    grew real subnegotiation parsing (IAC SB ... IAC SE, escaped-255
    aware); inbound Core.Hello/Core.Supports stored in
    session.oob_supports.
  - **WebSocket**: {"type": "oob", "package", "data"} JSON envelope.
  - **Engine emissions**: Room.Info (id/name/exits) on every
    move_through_exit; Char.Vitals (hp/max_hp/round) each combat
    round for players.
  - **Softcode**: `oob(target, 'My.Package', {...})` — custom client
    UI panels from builder scripts (queued like pemit).
  Remaining protocol flavor for later: MSSP (crawler status), NAWS
  payload use, MXP — the SB parser and option table now make each a
  small add.
- [x] **THE LIST IS DONE: hardening + persistence + tail (2026-07-05,
  final sweep).** 804 tests (5 new).
  - **AuthService** (realm/server/auth.py): identity extracted from
    GameServer — authenticate (verify + legacy-plaintext upgrade) and
    create_account (hash + system baseline), plus **login rate
    limiting** (5 fails/60s per name locks the name until the window
    drains; injectable clock, tested). Chargen flow deliberately stays
    in the composition root (cohesive, uses server-owned resources).
  - **Persistence**: WAL journal mode + synchronous=NORMAL (crash
    robustness), PRAGMA user_version schema versioning (SCHEMA_VERSION
    constant, newer-db guard, migration hook point), and the load_all
    N+1 fixed — reference ids captured during the single world scan
    (one query total, was one per object).
  - **Cosmetic tail**: LockEvaluator dead cache + throwaway-Lock in
    check() removed (eval_bool direct); AttributeProxy per-attribute
    dirty set → the object-level bool that was actually consumed;
    cmd_pose consumes the canonical pose_action; spacegame doctor's
    shadowed $help renamed $treatment with a comment.
  - Remaining accepted-as-is items (resolve_or_report sweep, ooc/shout
    one-off shapes, put-in-container script verb, persistent waits)
    stay documented in simplicity_review.md / BACKLOG.
- [x] **TIER-3 FINISH: the consolidation tail (2026-07-05).** 799
  tests. The correctness headliner: **GURPS combat now uses the one
  skill ladder** — get_skill passes checks.skill_level as get_stat's
  default (trained/untrained × modified/unmodified all correct; an
  untrained DX-13 fighter attacks at DX-4, not flat 10); the drifted
  checks.py seed table trimmed to the engine floor. Also: canonical
  speech_action/pose_action shapes in core/verbs.py consumed by
  cmd_say, the script engine, AND _npc_say (narration drift now
  impossible); GameSystem.death_award(victim) hook (CP policy belongs
  to the rules package); RulesetRegistry (register custom rulesets, no
  engine edits — same shape as Behavior/GameSystem registries);
  Behavior.countdown(obj, key, ticks) base helper (ticker + wanderer
  converted); DispositionBoost applied-flag moved from params to
  owner.db (behaviors are stateless logic). Remaining cosmetic items
  (resolve_or_report, remaining communication commands, locks class
  flattening, AttributeProxy dirty-set) stay listed in the review doc.
- [x] **YOUR OBJECTS ARE YOU: Penn owner delegation (2026-07-05,
  follow-on to the bracket).** 799 tests (6 new). `controls()` gained
  rule 6: an owned object controls whatever its owner controls
  (owner-chain walk, depth/cycle-guarded) — Bob's gadget reads AND
  writes Bob's stash; a builder's tool reaches world props; strangers
  still denied. Sound because only the owner can script the object.
  The Penn-faithful valve: `@chown` HALTS objects carrying
  CMD_/LISTEN_/ON_ scripts (old code must not run with the new
  owner's authority) and says so. Inline [[...]] blocks now reach
  sibling state — tested (room description reads + audits a ledger
  the same owner holds).
- [x] **THE BRACKET LIVES: inline softcode in descriptions
  (2026-07-05, twelfth package).** 793 tests (7 new). The PennMUSH
  ``[...]`` capability, REALM-style: any description may embed
  ``[[ ... ]]`` blocks executed PER VIEWER through the script sandbox
  at render time (realm/scripting/inline.py; wired into render_room +
  look-at-object; zero cost when no '[[' present).
  - Full ScriptFunctions namespace (get_attr/set_attr/rand/now()/...)
    plus viewer, check_roll(skill, mod) (rolls AS the viewer,
    condition modifiers apply), skill(name). Block runs AS the
    described object (its authority); assigns ``result`` for the
    substitution; ';' separates statements; blocks capped at 8;
    errors/forbidden code fail closed to '' (logged).
  - State in ordinary attributes = builders code caching/expiry
    themselves — the memoized passive-detection idiom is tested
    near-verbatim from the user's pseudocode (roll once per viewer,
    cache PASS/FAIL on the room, stable across looks). ``now()``
    added for time-based cache expiry.
  - Mutations persist via the dirty sweep; pemit/remit deliver
    immediately; loop-bound ops (combat/force/wait) are rejected with
    a log — use ON_LOOK scripts for those.
  - desc_extras/@detail (11th package) remains as the cheap,
    validated declarative form; [[...]] is the full-power form.
- [x] **EYES THAT SEE: help system + per-viewer details (2026-07-05,
  eleventh package).** 786 tests (10 new).
  - **Help, registry-derived**: `Command.category` field (set per
    module via a registration partial — movement/communication/looking/
    items/combat/social/economy/utility/building); `help` groups the
    commands YOU can see by category (builders see Building, players
    don't); `help <cmd>` shows aliases/usage/help + docstring;
    `help <word>` substring-searches names, aliases, and help text
    ("Related: buy, sell..."). Deleted the hand-maintained category
    map (closes that backlog item).
  - **Per-viewer conditional descriptions** (`realm/core/describe.py`):
    `db.desc_extras = [[condition, text], ...]` evaluated PER VIEWER at
    render time through the unified safe-eval — namespace: viewer,
    skill(name) (stable threshold), check(name, mod) (fresh roll),
    has_tag(name). Wired into render_room AND look-at-object. Builder
    command: `@detail here = check('observation', -2) -> You notice a
    small hole in the wall.` (validated at write time; @detail/clear;
    bare text = shown to all). The thief's passive detection, softcode
    all the way down.
- [x] **THE GHOST RIDES: @force / possession (2026-07-05, final
  matrix gap).** 776 tests (6 new); coverage 53 YES / 5 NO — Death
  House possession and CoC compelled actions flipped.
  - `realm/server/puppet.py`: PuppetSession (the minimal .player/.send
    surface) + `force_command` through the REAL dispatcher — parsing,
    permissions, and propagation all apply to forced commands; output
    forwards to the forcer prefixed `[puppet]`. Chains depth-capped.
  - Authority is `controls()` — so PLAYER possession is admin-only by
    default and OPT-IN otherwise (`@lock/control me =
    caller.has_tag('ghost')`): the Death House mechanic falls out of
    the existing model with zero new concepts.
  - `@force <target> = <command>` builder command; softcode
    `force(target, cmd)` (queued, drained through the dispatcher).
  - Two real fixes surfaced by tests: NPCs now rank as PLAYER role in
    the command layer (a forced imp can `say` but never `@set`), and
    `controls()` rule 4 no longer lets builders control unowned
    PLAYERS.
- [x] **THE SAGA HOLDS: consolidated live drive (2026-07-05).**
  12-check continuous telnet playthrough on the post-cleanup engine:
  chargen (soldier) → shopkeeper built in-game (@behavior + @teleport
  stock) → list/buy/credits → ON_PAYMENT bribe judged by softcode →
  consider → wield blaster → queue shoot kills in beat combat →
  softcode-hired porter follows through an exit + party listing.
  Dispositions/ranged/economy/followers verified live for the first
  time, together. Driver: scratchpad e2e_saga.py (port 4805).
- [x] **SIMPLICITY REVIEW + TIER-1 FIXES (2026-07-05, tenth package).**
  Three independent review passes; full findings + verdicts in
  docs/design/simplicity_review.md. Verdict: bones are right (layering
  clean, singletons right-sized, _resolve_action chain and core layout
  KEEP). Fixed same day (789 tests): @teleport/@destroy/@link/@unlink
  now require_control (builder commands were LOOSER than scripts);
  set_skill_defaults merges over ENGINE_SKILL_DEFAULTS floor (flee
  default was silently lost on every live server); COMBAT_RULESET now
  defaults to the GameSystem's ruleset (GAME_SYSTEM=d20 no longer gets
  GURPS combat); create_obj location gated; roles.py rival authority
  layer (can_control/can_examine + dead helpers) DELETED — locks.controls
  is the one predicate; flags.can_set_flag rewired to it.
  TIER 2/3 EXECUTED same day (770 tests, ~900 lines removed):
  DELETED flags.py (dead PennMUSH lexicon + its tests), legacy
  set/get_combat_system + unimportable examples/spacegame/commands.py,
  eq/gt/lt MUSH comparisons + output_callback from ScriptFunctions,
  dead Ruleset surface (roll_saving_throw/get_attack_range/roll_dice/
  get_modifier; calculate_healing kept — one real caller), TagSet
  namespace API, dispatcher @command decorator + register_commands +
  min_args, disposition BANDS, LockType PAGE/MAIL/ZONE, resolve_attr,
  has_msg_handler, 53 unreachable ctx.player guards. CONSOLIDATED
  functions.py to one resolution idiom (_resolve) + _controlled/_touch
  mutate helpers (del_attr now queues its save). Still pending (review
  doc Tier 3): resolve_or_report helper, communication.py helper +
  speech-shape builders, Behavior.countdown, GURPS skill ladder
  unification, RulesetRegistry, death_award hook, locks class
  flattening, AttributeProxy dirty-set.
- [x] **NOBODY LEFT BEHIND: followers & parties (2026-07-05, ninth
  package).** 801 tests (12 new); coverage 51 YES / 6 NO — B2's
  rescue-the-prisoners escort flipped.
  - `realm/core/party.py`: `db.following = <leader id>` is the entire
    state. `bring_followers` hooks move_through_exit: followers in the
    origin room walk the same exit after their leader — chains cascade
    naturally, cycles self-resolve (scans are room-local; movers have
    left the room being scanned), locks/skill gates judge each
    follower on their own merits, unconscious/in-combat stay, FLEEING
    breaks the chain (you escape alone).
  - Party = the connected component of follow edges in one room — no
    party object, no invitations. `follow`/`unfollow`/`party` commands.
  - **CP awards split** across the killer's party members present
    (max(1, award // n) each; solo unchanged) — closes the
    long-standing party-CP-split backlog item.
  - Escort quests are pure softcode: the prisoner's
    `$rescue prisoner: set_attr(me, 'following', '%#')` — enactor id
    via %-substitution — tested through the real trigger path.
- [x] **MONEY TALKS: the economy kit (2026-07-05, eighth package).**
  789 tests (14 new); coverage 50 YES / 9 PARTIAL — B2's keep shops,
  the bribed ogre, caravan wages, and Death Station salvage all
  flipped.
  - `realm/core/economy.py`: `db.credits`, never-negative
    adjust/transfer; the active GameSystem names the currency
    (`currency_name` — credits for GURPS-space, gold for D20).
  - **ShopkeeperBehavior**: stock IS the keeper's inventory
    (restocking = spawner/softcode drops goods on them); price =
    item `db.value` × markup × DISPOSITION factor (±5%/point, cap
    ±15%) — persuade the merchant, get a discount: the systems
    compose. `no_sell`/`wielded` items withheld; buyback with
    `no_buy` opt-out.
  - Commands: `credits`/`money`, `list`/`wares`, `buy`, `sell`,
    `pay <amount> to <target>`. **`pay` propagates `event:payment`**
    → ON_PAYMENT softcode: the B2 ogre judges the bribe and drops
    its `hostile` tag (tested end-to-end through the trigger path).
  - Softcode: `credits()` read; `adjust_credits` (minting requires
    control); `transfer_credits` (executor must control the SOURCE —
    a banker pays from its own pocket, can't script money out of a
    player).
- [x] **GUNS WORK: ranged combat (2026-07-05, seventh package).**
  775 tests (11 new); coverage 46 YES / 7 NO — Shadowrun's Food Fight
  and Harkwood's archery contest flipped from NO.
  - **Range bands** on Participant (0 = engaged, 1 = at range; int so
    more bands can come later). Melee requires both at band 0
    ("'close' the distance or 'shoot'"); shoot works at any band.
  - **Base maneuvers** (engine vocabulary, every ruleset gets them):
    shoot (-2 close quarters, -2 vs cover), aim (+weapon Acc on next
    shot at that target, +1/extra round, cap Acc+2, consumed on fire),
    close/withdraw (band moves, drop cover), cover (needs a
    `cover`-tagged room object; -2 to ranged attacks against you).
  - **Wielded weapons**: `wield`/`unwield` commands ('wielded' tag,
    one at a time), `find_wielded()`; melee attack won't club with a
    ranged weapon (goes unarmed); GURPS `get_skill` honors the
    weapon's `skill_type` (skill_guns) before broad fallbacks.
  - Modifier dicts flow through the existing `roll_attack(modifiers=)`
    seam — verified by a recording-ruleset test. NPC snipers are just
    `combat_strategy = [["", "shoot"]]`.
  - Remaining flavor (backlogged): ammo/reload, bursts, cross-room
    sniping (encounters stay per-room by design).
- [x] **NPCS HOLD GRUDGES: disposition states (2026-07-04, sixth
  package).** 764 tests (15 new). Adventure matrix gap #3 closed:
  44 YES / 12 PARTIAL now.
  - `realm/core/disposition.py`: `db.dispositions = {char_id: -5..+5}`
    on the NPC; GURPS bands (hostile/unfriendly/neutral/friendly/
    devoted); `db.default_disposition` temperament baseline; `hostile`
    tag caps at -3; `reaction_roll` = 3d6 high-good MEMOIZED (first
    impressions stick until something changes them).
  - Commands: `consider` (NOT `greet` — that name is left free for
    softcode $-commands; builtins shadow the fallback), `persuade`
    (persuasion vs will, +1 permanent, per-person cooldown),
    `fasttalk` (fast_talk vs detect_lies; +2 via
    DispositionBoostBehavior that EXPIRES and reverses; caught = -1
    permanent).
  - Consumers: GuardBehavior waves through disposition >= 
    allow_disposition (default 2) — the fast-talked guard literally
    lets you past, then wonders why two minutes later; Aggressive
    spares targets >= spare_at (default 2, None disables).
  - Softcode: disposition()/adjust_disposition() (authority: an NPC
    owns its own opinions)/reaction_roll() (proximity).
  - GURPS system grows will/detect_lies defaults.
- [x] **THE BANSHEE WAILS: condition-modifier pipeline (2026-07-04,
  fifth package).** 749 tests (8 new). The adventure matrix's #1 gap
  cluster closed; coverage 38→42 YES, 17→14 PARTIAL.
  - `check()` folds `condition_modifier(obj, skill)` in UPSTREAM of the
    resolver — every ruleset and injected resolver inherits it (Chain
    of Responsibility on the check pipeline). Providers registerable
    (`add_modifier_provider`); built-in provider reads `db.check_mods`
    ({kind: {'all': -2, 'observation': -6}} or bare int) — one dict,
    softcode-writable, reboot-safe.
  - Any `TimedEffectBehavior` can carry `check_mods` — its entry lives
    exactly as long as the effect (blinding poison = DoT + observation
    penalty). `ModifierEffectBehavior` (behavior_id `modifier_effect`)
    is the pure-condition shape: kind/duration/check_mods/apply_msg.
  - Softcode: `apply_effect(target, effect_id, **params)` and
    `remove_effect(target, kind)` with proximity authority (a banshee
    frightens whoever hears the wail; a cleric cures who's present).
    The user's original example is now literal:
    `@set banshee/on_wail = apply_effect(enactor, 'modifier_effect',
    kind='fear', duration=8, check_mods={'all': -2})`.
- [x] **THE FRONT DOOR OPENS: GameSystem + chargen + hashed auth
  (2026-07-04, fourth package).** 741 tests (16 new) + a 9-check live
  drive of the full new-player journey: create → GURPS template
  chargen (input captured, quit/reconnect safe) → derived stats →
  world; scrypt-hashed password verified across a reboot, plaintext
  never stored.
  - **GameSystem** (`realm/systems/`): the swappable rules package —
    Abstract Factory + Registry (config `GAME_SYSTEM = "gurps"`),
    Strategy for advancement (`improve_cost`), Template Method for
    chargen (server owns the prompt→answer→advance loop, state in
    `db.chargen_step`; systems supply `ChargenStep`s; `ChoiceStep`
    covers menus, point-buy steps are future subclasses). Owns: combat
    ruleset name, skill defaults (`set_skill_defaults` — checks.py
    table now comes from the system), baselines, derived stats.
  - **GurpsSystem**: 4 templates (soldier/infiltrator/face/technician)
    + bonus-skill step; HP from ST, dodge from DX/HT; flat 4 CP/level.
    **D20System** proves the swap: class pick, HP from HT-analog,
    escalating improve costs. `improve` command asks the system.
  - **Auth** (`realm/server/auth.py`): salted scrypt
    (`scrypt$salt$hash`), constant-time compare, legacy plaintext
    accounts upgraded in place on first successful login.
  - Chargen flow edge cases: stray world commands captured, `quit`
    mid-chargen works, disconnect/reconnect resumes at the same step.
- [x] **THE ENGINE SPEAKS SOFTCODE: combat, locks, verbs, waits
  (2026-07-04, third package).** 725 tests (17 new) + an 8-check live
  drive authored entirely with @set: a fetch-imp (scripted get/give), a
  script-sealed lock, a dart-trap room (`damage(enactor, 3)` on
  ON_ENTER — "HP now 7"), a rat killed by script leaving a real corpse,
  and a `wait 2 say KABOOM!` fuse firing off the heartbeat.
  - **Combat channels**: `damage`/`heal` with PROXIMITY authority (same
    room as the executor, or inside it — room traps work); lethal
    damage queues a death_check drained on-loop through
    `CombatManager.handle_death`, so corpses/CP/unconsciousness hold.
    `start_combat(attacker, target)` — executor must control the
    attacker (no puppeting players into fights), same-room, queued into
    `CombatManager.initiate`.
  - **Locks from scripts**: `set_lock` (validated by the unified
    safe-eval, authority-gated), `clear_lock`, `test_lock`.
  - **Manipulation verbs**: get/take/drop/give/open/close as script
    commands, backed by NEW `realm/core/verbs.py` — the single
    implementation player commands now delegate to (cmd_get/cmd_drop/
    cmd_give/cmd_open/cmd_close refactored; message templates exist
    once). Scripted gets pass the same locks and behavior gates.
    Sandbox got a generic `cmd(line)` escape hatch.
  - **`wait`**: `wait(seconds, command)` function + `wait <sec> <cmd>`
    script command; one-shots ride the server heartbeat
    (`ScriptEngine.tick_waits`), clamp 0–3600s, honor `halt`,
    in-memory like MUSH @waits (persistent waits backlogged).
  - Script `get()` name resolution is now LOCAL-FIRST (executor's room
    + inventory, then world) and works without persistence.
- [x] **PERMISSIONS ON SOFTCODE + the engine API (2026-07-04, same day,
  second package).** 708 tests (18 new); the 13-check MUSH-loop live
  drive re-passed under the new authority layer. North star written:
  docs/design/engine_vision.md (Godot-of-MU*s; capability matrix is
  the coverage tracker).
  - **`controls(actor, obj)`** (permissions/locks.py) — the one
    authority predicate: self, owner, ADMIN+, builder-over-unowned,
    world-trusts-world (unowned non-player ↔ unowned non-player),
    else the `control` lock. `may_trigger` adds the trigger_ok analog:
    controllers, or an explicit `command` lock grant.
  - **Builder commands gated**: @desc/@name/@set/@wipe/@parent/@tag/
    @untag/@lock/@unlock/@behavior/@clone all `require_control`;
    @tr uses `may_trigger`. @clone now sets `clone.owner = cloner`.
  - **Trigger locks enforced**: `use` gates who fires an object's
    $-commands; `listen` gates whose speech its ^patterns overhear;
    cross-object `trigger` from scripts needs may_trigger. Defaults
    are True/True/controllers — unset locks change nothing.
  - **Script mutations authority-gated**: set_attr/del_attr/add_tag/
    remove_tag now require the EXECUTOR to control the target (scripts
    run as their object, never as the enactor; self-modification always
    works). An imp's `set_attr('Alice','hp',0)` is a no-op.
  - **Engine API for softcode**: `create_obj` (owned by executor's
    owner, saved via queue), `destroy_obj` (never players),
    `teleport_obj` (checks destination teleport lock), `exits`,
    `behaviors`/`attach_behavior`/`detach_behavior`, `controls`.
    Script mutations queue persistence saves — deduped, drained
    on-loop after execution alongside pemit/remit/oemit.
- [x] **SOFTCODE MACHINES LIVE: the MUSH builder loop (2026-07-04).**
  690 tests (34 new) + a 13-check live drive: a builder assembles a
  living NPC entirely in-game and it survives a reboot untouched —
  `@create parrot` → `@behavior parrot = script_ticker, interval:2` →
  `@set parrot/on_tick = say Awk!` → `@clone parrot = polly` →
  `@tr polly/on_tick` → a softcode-only wanderer walking real exits.
  - **One safe-eval engine** (`realm/core/safe_eval.py`): locks,
    strategy conditions, and the script sandbox all validate against
    the same rules (compiled expressions LRU-cached; `eval_bool` is the
    fail-closed gate). Locks got strictly stronger — `getattr` and
    private names now rejected there too. Closed the "unify the AST
    validators" hardening item.
  - **Script actuators**: `move <exit>` (and sandbox `move()`) routes
    through `move_through_exit` — locks, closed doors, and guard
    behaviors apply to scripted movement exactly as to players;
    `trigger <obj>/<attr>` chains named scripts, depth-capped.
  - **`ScriptTickerBehavior`** (behavior_id `script_ticker`): runs the
    owner's `on_tick` attribute as softcode on the one heartbeat —
    scheduling stays native, logic is builder-authored. Deliberate
    divergence from MUSH `@wait` chains (no per-mob queue machines);
    halting = `halt` tag or detach, no `@halt` wars.
  - **Builder commands**: `@behavior` (attach/detach/list, @set-style
    param parsing), `@clone` (attrs+tags+behaviors+locks via the
    spawner's prototype path; spawn-bookkeeping tags stripped;
    players/rooms refused), `@tr obj/attr` (run a named script,
    executor=obj, enactor=you; reports halt).
  - `ScriptEngine.run_object_script` + `set_script_engine/get_script_engine`
    ambient accessor (same pattern as combat/persistence managers).
  - Fixed a second test-registry landmine: test_persistence.py cleared
    `BehaviorRegistry._behaviors` in teardown without restoring,
    unregistering every import-time behavior for the rest of the
    session (same bug as test_behaviors.py, fixed same way).
- [x] **THE KILL LOOP CLOSES: spawners, progression, real NPC brains
  (2026-07-04).** 656 tests (10 new) + a 9-check live drive: kill the
  spawner-staffed lobby guard → earn 6 CP → `improve stealth` → corpse
  remains → the relief guard walks in on the respawn timer.
  - `SpawnerBehavior` (`realm/behaviors/spawner.py`): rooms keep N
    copies of a prototype (plain data: name/tags/attrs/behaviors)
    alive. Liveness via the identity map — killed NPCs are deleted
    from the cache, so a dead spawn's ID stops resolving; no scanning.
    Respawn countdown + tracked IDs live in room.db (reboot-safe).
    First spawn immediate. Nexagen's two guards are now spawner
    prototypes — the tower re-staffs itself.
  - **Progression**: NPC kills award character points
    (`victim.db.points // 10`, min 1) to player killers via the shared
    death path; `points`/`score` shows the ledger + trained skills;
    `improve <skill>` spends 4 CP per +1 level (untrained skills start
    from their attribute default). Party split awaits a group system.
  - **Combat behaviors de-stubbed** (all five "Would ..." stubs are
    real): Aggressive engages through the CombatManager with a spoken
    taunt (perception-gated — it can't aggro what it can't see);
    Defensive/Fleeing write `!`-override flee strategy rules (the same
    engine players' wimpy uses); Healer heals with a db cooldown;
    Combatant delivers last words on combat:on_death; Wandering
    actually walks random open exits with zone confinement
    (stay_in_zone) and avoid_tags. Fixed integration bug: behaviors
    called `get_combat_system()`, a global the server never set (now
    set alongside the manager).
  - `Behavior.tick_interval` is honored (was silently ignored): the
    heartbeat tracks per-instance last-tick in a WeakKeyDictionary;
    default 0 = every pulse.
  - Removed the superseded `StatusEffect` machinery from combatant.py
    (effects.py behaviors replaced it); lint baseline dropped 14→8.
- [x] **Timed effects + tick-sweep registry (2026-07-03).** 648 tests.
  - Effects ARE tickable behaviors (`realm/behaviors/effects.py`):
    `TimedEffectBehavior` base (interval/duration countdowns in
    owner.db — a poisoned character is still poisoned after a reboot;
    the effect kind mirrors as a tag for perception/softcode/strategy
    visibility), `DamageOverTimeBehavior` (bleeding/poison/burning;
    lethal pulses route through the new shared
    `CombatManager.handle_death` — players fall unconscious, NPCs die
    into corpses, same as a sword), `RegenerationBehavior` (capped,
    optionally innate with duration=0).
  - Tick loop no longer scans the whole world: objects register in a
    WeakSet on first behavior attach (`behavior_owners()` in
    core/behaviors.py). Measured: 100K-object sweep went from 15.08ms
    to 0.070ms per pulse (215×), now O(objects-with-behaviors).
  - Fixed a latent test-hygiene bug: test_behaviors cleared the global
    BehaviorRegistry without restoring it, silently unregistering all
    import-time behaviors for the rest of the session.
  - Follow-up: `StatusEffect` in combat/combatant.py is now superseded
    dead code (never driven) — remove alongside the combat-behaviors
    de-stubbing; `cure`/antidote surface for removing effects.
- [x] **BEAT-DRIVEN COMBAT (2026-07-03).** The full design in
  docs/design/combat.md, all five phases, shipped in one pass.
  Verified: 642 unit tests (24 combat) + a 24-check live telnet drive
  (PvP duel on real beats, PvE guard kill with lootable corpse, and the
  heist failure path: spotted → hostile guard opens combat → flee →
  re-hide).
  - **Encounter engine** (`realm/combat/encounter.py`): one fight per
    room, its own async beat timer (no per-fight polling). The beat is
    the decision window — the slowest player's `db.combat_beat` wins,
    clamped to `COMBAT_BEAT_MIN/MAX` (4s–120s), `pace` command sets it.
    Queued actions are freely replaceable until the beat fires; then
    everything resolves in initiative order (fixed per encounter).
    Round prompts show what will fire and when.
  - **Ruleset-agnostic scheduling, data-driven vocabulary**:
    `Ruleset.maneuvers()` publishes what can be queued (base:
    attack/defend/flee/wait); GURPS adds All-Out Attack (+4/no
    defense), All-Out Defense (+4), and Feint (contest; opens the
    target's guard NEXT round via deferred modifiers) purely through
    the `resolve_special_maneuver` seam — D20 keeps the base verbs,
    proving swappability.
  - **Commands**: attack/kill, queue (+ defend shortcut), flee
    (random-exit fallback, failed flee wastes the beat, success moves
    with the `fleeing` flag through the movement gate — leaving a room
    mid-combat otherwise refuses), combat (status with HP bars), pace,
    combatdefault (attack|defend|repeat|nothing), wimpy, firstaid.
  - **Strategies** (`realm/combat/strategy.py`): ordered
    condition→action rules in `db.combat_strategy`, lock-style safe
    expressions over `me/target/round/enemies/chance(pct)` views.
    Plain rules fire only when nothing is queued; `!`-flagged
    OVERRIDE rules preempt even manual intent — `wimpy 30` is sugar
    writing `["!me.hp_percent < 30", "flee"]`. NPC combat AI is the
    same engine: a guard's brain is a strategy list, @examine-able.
  - **Hostile-tag auto-combat** (propagation observer): any successful
    action tagged `hostile` between combat-capable parties starts the
    fight, crediting the initiator (`already_acted` — the fireball WAS
    your turn). Defender auto-joins targeting the attacker.
  - **Defeat asymmetry**: players fall unconscious in place
    (`unconscious` tag; firstaid revives); NPCs die into lootable
    corpse containers that spill-and-crumble via DecayBehavior.
    Nexagen's executive guard is now `hostile=True` — stealth failure
    on floor 46 has real teeth.
  - **Messaging** rides `deliver_messages` (perception applies — an
    unseen attacker narrates as "Someone"); new characters get baseline
    GURPS-style stats at creation so combat works out of the box.
  - Follow-ups (docs/design/combat.md): full narration interception via
    react-pass propagation, Aim/ranged, action-point economy for
    attacks-per-beat, GURPS death spirals at -HP, group formations,
    strategy editor command (today: @set combat_strategy).
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
- [x] Configurable welcome screen via `data/welcome.txt` (`WELCOME_FILE`
  setting)
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

- [x] Interactive prompts / wizards (EvMenu-analog: stop-and-ask dialogues)
  - Hardcode: `session.prompt(text, *, choices, allow, allow_abort)` awaits the
    player's next line (deadlock-free — telnet runs each line as its own task);
    `confirm()` (yes/no bool) and `choose()` (numbered menu) built on it.
    Single `session.input_handler` intercepts the next line before dispatch;
    `_prompt_future` resolves the await. `DEFAULT_ALLOW={help,quit,exit}` pass
    through mid-prompt; `abort` always cancels (unless `allow_abort=False`).
    `destroy_session` cancels pending prompts (await returns None).
  - Softcode: `prompt(target, text, callback, persistent=False)` — queues a
    `('prompt', ...)` op drained in the engine (mirrors `wait`), installs the
    session handler; the player's next line runs the `callback` attribute
    with the answer bound as `arg0`/`%0`. Runs AS the executor (builder's
    authority — can't rewrite the player; that's the security boundary), so
    NPC dialogue trees chain by prompting again inside the callback.
  - `persistent=True` writes `db.input_prompt` (callback+executor) — reboot-safe
    like chargen; `_do_connect` re-installs the handler on reconnect.
  - Docs: docs/guides/wizards.md (both layers, escape hatch, authority rule);
    softcode reference regenerated. Tests: tests/test_prompts.py (10 passing —
    await/abort/help-passthrough/choices/confirm/choose/disconnect-cancel +
    softcode callback + persistent marker). Full suite 901.

## Showcase-discovered engine gaps (filed 2026-07-16)

Found while implementing the showcase arcs (`docs/showcase/`); each verified
against source by the implementing session. Workarounds are documented in the
named tutorials, so none of these block showcase progress.

- [ ] **Sandbox: call-free loops escape the time budget.** The 1500 ms limit is
  enforced in `ScriptSandbox._wrap_function`, so `while True: pass` (no
  function calls) is never interrupted and pins its worker thread. An
  instruction-count guard or tracing hook would close it.
  (`docs/showcase/250_player_scripting.md`)
- [x] **`ON_<EVENT>` scripts get no action payload — RESOLVED 2026-07-17.** Was: — e.g. `ON_PAYMENT` cannot
  read the amount; witnessed events also fire on every bystander with the hook,
  indistinguishably. Three arcs independently re-derived the balance-delta
  "ledger/till" idiom (001, 002, 064, 067). A bound payload
  (amount/actor/target) would remove the workaround.
- [ ] **`SpawnerBehavior` liveness is deletion-based** (`persistence.get_cached(id)`)
  — a sold/relocated item still counts as alive, so a spawner can never restock
  a shop; only destroyed populations repopulate. Audit had recommended spawner
  for shop restock — correction: use `script_ticker` meanwhile.
  (`docs/showcase/063_shopkeeper.md`)
- [ ] **Things have no softcode-visible description fallback** — `look` reads
  only the engine description field for things
  (`realm/commands/builtin/look.py:94-96,195-196`); rooms fall back to
  `db.description` (`realm/core/render.py:86`) but things don't, so
  `create_obj()` goods are name-only. (`docs/showcase/002_vending_machine.md`)
- [ ] **Keycard fast-path and `pick` mutate `locked` without propagating**
  (`realm/commands/builtin/manipulation.py:256-261, 205`) — `ON_LOCK`/`ON_UNLOCK`
  hooks can't observe those paths; `lock`/`unlock` propagate fine.
  (`docs/showcase/025_lockable_door.md`)
- [ ] **`start_combat()` same-room check runs at call time while moves are still
  queued** — teleport-then-fight silently fails; `force(npc, 'attack …')` works
  because it executes after the queued teleport. (`docs/showcase/071_guard_response.md`)
- [ ] **`exits()` documented as "open exits" but returns closed exits too**
  (`realm/scripting/functions.py:298`) — fix the docstring and regenerate
  softcode docs, or add an `only_open` flag. (`docs/showcase/048_gas_bomb.md`
  filters `closed` explicitly.)
- [ ] **Simulator doesn't wire the `prompt()` seam** (`engine.session_manager` /
  `player._session`) — tests using `prompt()` re-wire it by hand; a Simulator
  convenience would help test authors. (`tests/showcase/test_heist.py`)
- [ ] **Master Room** for global `$`-commands is a live TODO
  (`get_search_objects`) — ~10 showcase items use the `zone:world` master
  workaround meanwhile. (`docs/showcase/capability_audit.md`)

## Showcase wave-2 engine gaps (filed 2026-07-16, categories 1-5)

- [ ] **Softcode `on_check` wards are participant-only — exits and bystanders
  never run them.** `visit_observe_check` (realm/core/objects.py:313-317) runs
  behaviors only; the softcode `_check_hook` runs solely in `visit_check`
  (actor/target/room-as-target). Two consequences, both verified: (a) an exit's
  ward never fires for traversal — movement gates on the rooms, so per-exit
  access logic must be a room ward keyed by `adata('exit')` (026, 030, 034,
  035); (b) a bystander object cannot veto actions it merely witnesses (053).
  Possible fix: run the check hook for the exit named in a movement action's
  extra, and/or give softcode wards an opt-in observe pass.
- [ ] **`eval_attr` absent from the check-pass allowlist** (`ScriptFunctions.
  _READONLY`) though read-only — wards can't honor computed conventions (e.g.
  a weight function); only plain data attrs. (017_bag_of_holding.md)
- [ ] **`create_obj(..., location=<other player>)` silently returns `None`**
  (deliberate no-seeding rule) and downstream `set_attr(None, ...)` swallows it
  — fails invisibly. Suggest: raise a script error naming the rule. Workaround:
  create at self, `teleport_obj` to recipient. (022_coat_check.md)
- [ ] **No per-exit movement message overrides** — stock leave/arrive lines
  always print; `leave_msg`/`arrive_msg` attrs don't exist, and room
  ON_ENTER/ON_LEAVE can't see which exit carried the mover. (028_one_way_exit.md)
- [~] **`ON_FAIL` can't read the failure reason** — PARTIALLY resolved 2026-07-17: `adata()` is now bound, so the moment `extra['reason']` is populated this works with no further engine change. Was: (`extra['reason']` not bound)
  — e.g. fall damage on a lockable climbing exit would also fire when bounced
  off the lock. (034_climbing_exit.md)
- [ ] **`look <name>` has no fallback to named `desc_extras` details** — builtin
  look resolves objects only and dispatches before `$`-triggers, so named
  details need a `$study *` verb. A small cmd_look fallback would make item 42
  fully native. (042_room_details.md)
- [ ] **`oemit()` silently no-ops for room executors** — `_deliver_queued` reads
  `functions.executor.location`, `None` for rooms. Workaround: queue the move
  first, then `remit`. (040_zero_g_room.md, 047_falling.md)
- [ ] **`eval_attr()` stringifies its args** (`captures=[str(a) for a in args]`)
  — GameObjects can't be passed; callers pass `o.id` and re-resolve. Doc nit or
  enhancement. (039_underwater_room.md)
- [ ] **`zone_property()`/`zone_masters()` not exposed to softcode** though the
  audit names them — worked around via `get_attr('<master>', ...)`.
  (043_hazard_room.md)
- [ ] **DX note: builtin unique-prefix matching silently shadows `$`-verbs**
  (`$read` can never fire — prefix-matches builtin `ready`). Suggest a builder
  diagnostic (warn on shadowed trigger registration). (010_typewriter.md)
- [x] **Addendum to the payload-binding gap — RESOLVED 2026-07-17** (`item:on_get`'s item is the action `target`, now readable; give/receive carry it in `extra`). Was: a moved item is not a
  witness to its own `item:on_put`/`item:on_get` (witnesses = room + contents +
  zone masters + target), so no hook can name the item involved even indirectly.
  (018_refrigerator.md, 019_trash_incinerator.md)

Audit corrections recorded by implementers (no engine change): row 53's
victim-tag recipe must route through `apply_effect` kind-tags; rows 39/43 need a
`skill_def` (stat=health), bare `skill_check(o,'health')` gets the unlisted-skill
floor; row 63's spawner-restock recipe superseded (see wave-1 spawner gap).

- [ ] **Engine defect: inline `[[...]]` blocks inherit the caller's stack, making
  the sandbox recursion cap depth-dependent.** `ScriptSandbox.execute` sets an
  absolute `sys.setrecursionlimit(min(max_recursion+10, 100))` = 60 frames
  (realm/scripting/sandbox.py:294); every other consumer enters via
  `execute_async` on a ~7-frame worker stack, but `eval_inline`
  (realm/scripting/inline.py) runs synchronously on the render call stack
  (~47-49 frames under pytest, plausibly deeper in production). Result: an
  inline block's survival depends on where `look` was dispatched from — the
  same block can render in one context and fail closed in another. Fix: make
  the guard relative to entry depth (`entry_depth + max_recursion`), or route
  eval_inline through the worker thread like everything else. Measured
  headroom per block class and the interim "push-on-change" idiom are
  documented in docs/showcase/036_weather_system.md (also 037, 043).

## Showcase wave-3 engine gaps (filed 2026-07-16, categories 6-11)

The dominant theme this wave: **event-trigger namespaces are too thin.** Many
findings below are facets of one fix — bind the action's target + payload into
`ON_<EVENT>` script namespaces the way `on_check` wards already receive `adata`.

- [ ] **`combat:on_death` only propagates from the combat-swing path**
  (`CombatSystem._propagate_death`); `CombatManager.handle_death` — reached by
  softcode `damage()` / `damage_over_time` kills — makes the corpse WITHOUT
  firing the event. So `ON_DEATH` witnesses can't verify poison/grenade/trap
  kills (breaks bounty verification, arena recorders, replay logs).
  (114_bounty_board, 111_grenades, 115_arena_spectators, 120_combat_replay)
- [x] **`ON_<EVENT>` triggers expose only `enactor` — RESOLVED 2026-07-17** (see the resolution note at the end of this file). Was: — no target, amount, or
  hit/miss (unlike `on_check`'s `adata`/target). Reconfirmed from many angles:
  armor wear can't be booked defender-side (117), damage narration can't name
  the defender (115, 120), emote/wield reactions can't read content (072),
  ON_PAYMENT can't read the amount (all economy). This is the single
  highest-leverage engine fix for softcode expressiveness.
- [ ] **`^listen` never hears poses/emotes** — `LISTENABLE_ACTIONS = {speech,
  shout, ooc, emit}` excludes `event:emote`, so content-keyed reactions to poses
  are impossible. (072_npc_reactions)
- [ ] **`eval_attr` discards a called routine's `say`/`pose`/`emit` output**
  (functions.py:1059 returns `result`, drops `_output`) — only queued emitters
  (`remit`/`pemit`) reach the caller. (094_job_board)
- [ ] **No graded, condition-modified check in softcode.** `skill_check()` /
  `contest()` return bare bools; the full-pipeline `CheckResult` (with margin,
  crit bands, and `check_mods` folded in) is unreachable. The `margin_under(
  roll('3d6'), get_attr(actor,'skill_X',8))` idiom recovers margin but reads the
  trained level RAW — buffs/debuffs (fear, meal buffs, darkness) silently don't
  apply to hand-rolled margins. A `check_roll(obj, skill, mod) -> CheckResult`
  surface would close it. Affects crafting quality, dice roller, darts,
  arm-wrestling. (125_quality_tiers, 129_cooking_buffs, 098_dice_roller, 107_dart_board)
- [ ] **Sandbox comprehension-scoping defect.** Scripts run `exec(code, globals,
  locals)` with separate dicts. Under PEP 709 (Py 3.12+; env is 3.13) list/set/
  dict comprehensions are inlined and see script-locals, but **generator
  expressions and lambdas are NOT** — their bodies `LOAD_GLOBAL` and NameError
  on any script-local. Silently breaks `set(x for x in ...)`, `sorted(g for
  ...)`, `lambda v: local[v]`. A single-namespace exec would erase the
  distinction. Interim idioms (wrap genexprs as `[...]`, use bound methods)
  documented on 100_poker_table. (also 101, 102, 105)
- [ ] **No presence query in softcode** — nothing answers "who is online"
  (`who` is builtin-only; sessions invisible to the sandbox). Blocks
  deliver-to-random-online-player and channel/PA rosters. Worked around with an
  `ON_CONNECT`/`ON_DISCONNECT` roster master. Suggest a `connected()` primitive
  or engine-maintained online tag. (083_message_in_bottle; also the [small]
  presence-surface gap group 180/188/197)
- [ ] **Softcode cannot set the `description` slot** — `.description` is written
  only by `@desc`; `set_attr(obj,'description',…)` writes an unrelated attr and
  doesn't render. Softcode's only description surface is `desc_extras`. A
  `set_desc()` (or routing that attr to the slot) would remove the sharp edge
  behind the wave-1 "spawned things are name-only" gap. (082_newspaper, 008_camera)
- [ ] **No enactor-consent path for `set_attr` on a player** — `move_to` honors
  `enactor_consent` but attribute writes require `controls()`, so a self-service
  blueprint/trainer can't sign its own reader's sheet; must use an admin-owned
  master. (126_blueprints, 131_chemistry_poisons)
- [ ] **No native yield/`stop_combat`, `throw`, or forgiving `roll()`** — small
  ergonomic gaps: an NPC can behave surrendered (strategy=wait) but can't be
  removed from an encounter (119); thrown weapons are a softcode pattern with no
  native `throw` to tie them into range bands (111); `roll()` raises on
  malformed notation instead of offering a `valid_roll()` predicate (098).

## Showcase wave-4 findings (filed 2026-07-16, categories 12-22 — all 223 [now] items done)

Wave 4 added no new *blocking* gaps — every [now] item builds on existing
primitives. Findings reinforce the wave-3 theme (thin event namespaces) and add a
few precise engine facts:

- [ ] **No player death event.** `CombatManager.handle_death` tags a player
  `unconscious` and emits nothing — no `combat:on_death`. Combined with the
  wave-3 finding that softcode `damage()`/DoT kills also skip the event, there is
  no reliable "X died/fell" hook for softcode. Clone bays, bounty boards, and
  recorders must poll. (140_death_cloning, 114_bounty_board)
- [ ] **Airlock mirror pattern cross-fires for co-located door faces** — a direct
  consequence of `ON_<EVENT>` carrying no target: two doors in one room both run
  their mirror on any open. 032_airlock now documents the limit; the fix for
  co-located faces is the single-panel raw-write cycle (used by 164_small_spaceship).
- [ ] **No attribute-enumeration function in softcode** (no `lattr()`-equivalent)
  — objects can't scan their own `skill_*`/`topic_*` attrs, so index-carrying
  objects (a `skills`/`topics` list attr) are the idiom. Affects score screens,
  help/guide boards, snapshot/restore. (190_score_screen, 182_snapshot_restore)
- [ ] **`@parent` does not propagate attribute reads** — the link is stored and
  shown in `@examine`, but `get_attr(child,x)` never falls through to the parent.
  Blocks native prototype/room-template inheritance; worked around with dict-merge
  and `@clone`. `@clone` additionally refuses rooms (use a `$stamp` minting verb).
  (165_prototype_library, 168_room_templates)
- [ ] **Sandbox forbids `isinstance`/`type`** and disallows `_` as a loop var —
  world-audit/auto-map idioms use `len(str(v))` and named vars instead.
  (172_world_audit, 174_auto_map)
- [ ] **Test-harness convenience:** `realm.testing.Simulator` doesn't wire
  `engine.session_manager`, so every `prompt()`-based showcase test hand-shims it
  (heist, gadgets, quests, character-systems, scripting-extras all do). Wiring a
  default into the Simulator would remove ~repeated boilerplate. (Not an engine
  gap — a DX improvement for game authors writing tests.)

**Latent risk, not currently failing:** the absolute-recursion-cap defect (filed
above) produced *non-deterministic* RecursionError across the showcase suite while
10 agents wrote files concurrently (stack depth varies with collection). With the
tree settled, `pytest tests/showcase/` and the full suite are deterministic (570
and 1734 passed, repeatably). But deeper production call stacks could resurface it
for any inline `[[...]]` block — the depth-relative-guard fix remains worthwhile.

Also worth folding into softcode docs (recurring builder footguns, taught across
tutorials, not gaps): builtins (and their unique-prefix abbreviations, and
n/s/e/w/diagonal direction aliases) dispatch before `$`-triggers, so custom verbs
must dodge builtin names/prefixes; `get('<bare-id>')` returns None (use `#id`);
`eval_attr` stringifies args and keeps the caller's executor (re-resolve the home
master by name); `:` breaks `^listen`/`$` pattern splitting.

## Softcode ergonomics & builder-experience backlog (filed 2026-07-17)

User-requested batch (deferred — capture only). Current state verified against
source. Two turned out to already work; the rest split absent / partial. Grouped by
the user's numbering.

### 1. Making the one-line Python pattern readable

- [x] **1b. `%#` enactor substitution — ALREADY WORKS.** `ScriptSandbox.
  expand_substitutions` (realm/scripting/sandbox.py:151-178, dup at :378-398)
  supports the full Penn table: `%#`=enactor id, `%!`=executor id, `%n`=enactor
  name, `%l`=location id, `%0`-`%9`=captures. `arg0..argN`, `me`, `here`,
  `enactor`, `viewer` are also namespace vars. → **DOCS task:** teach `%#` in the
  softcode reference; showcase tutorials wrote the longer `enactor.id`. Caveat:
  `%#` is raw text-substituted, so it must land in a string/valid-token position.
- [x] **1c. Python f-strings — ALREADY WORK.** The sandbox validator is a DENYLIST
  (`FORBIDDEN_NODES` = Import/ImportFrom/Global/Nonlocal only; realm/core/
  safe_eval.py:30-70), so `JoinedStr`/`FormattedValue` compile and run;
  `say(f"...")` is explicitly fine. → **DOCS task:** f-strings are the single
  biggest readability win available *today* — teach them; tutorials avoided them
  by idiom (favoring concatenation/`ansi()`), not because of a ban.
- [x] **1a. `V('cost', 10)` alias — DONE 2026-07-17.** Was absent; The
  most-repeated call in every tutorial. Sketch: register `V` in `ScriptFunctions`
  as `lambda name, default=None: get_attr(me, name, default)` bound to the
  executor's `me`. (PennMUSH `v()` parity; pairs naturally with 1d.)
- [x] **1d. increment sugar — DONE 2026-07-17** (shipped as `incr(k, by=1)`/`decr`, returning the new value; `++(k)` isn't valid Python syntax so a named fn it is). Formerly: for `set_attr(me, k, get_attr(me,k,0)+1)`.
  Absent. Also very frequent (ledgers, cooldowns, tallies). Sketch: `incr(name,
  by=1)` / `decr(...)` functions returning the new value; optionally target-aware
  `incr(obj, name, by)`.
- [ ] **1e. Multi-line attribute editor (`@edit obj/attr`).** ABSENT — no
  EvEditor analog. `@set obj/attr = value` is single-line (`_parse_value`,
  realm/commands/olc/modify.py:407-434); the `@desc` `\`-continuation is
  documented but unimplemented. Newlines only survive as JSON `"\n"` literals.
  Sketch: a session line-buffer state machine (accumulate until a `.` terminator),
  store joined text with `\n`. Solves the telnet newline=command limit.

### 2. Friendlier object ids

- [ ] **Human-friendly id (`name#<shorthash>`) alongside uuid.** Currently
  `id = str(uuid.uuid4())` (realm/core/objects.py:148); `get('#<id>')` needs the
  FULL uuid (exact cache-key lookup, persistence/manager.py:220). Sketch: keep
  uuid as canonical, add a short-prefix index (first 6-8 hex) + a `#name~shorthash`
  parse branch in `get()`/`get_cached`; collisions fall back to full-uuid or
  disambiguation. Keeps uuid uniqueness, adds legibility.

### 3. `get()` collision handling + filters

- [ ] **Refine `get()` candidates by tag/attr.** Today `get('name')` is
  first-match, local-first, never raises on ambiguity (`functions.py:69-110`);
  `search_world(tag=,attr=,value=,name=,limit=)` has filters but **equality only**
  (`core/query.py:20-62`). `get('name', tag='armor', ...)` refinement is absent
  (and `'ac'>=5` isn't valid kwarg syntax). Sketch: add `tag=`/`attr=` kwargs to
  `get()` that pre-filter candidates before the matcher; add operator support to
  `find_objects` via tuple form `value=('>=', 5)`. Would also let `get` optionally
  raise/disambiguate on ambiguity like the command-path `match_one`.

### 4. Regex trigger/command patterns

- [ ] **Opt-in regex patterns.** Currently glob-only: `*`→`(.*)`, `?`→`(.)`, rest
  escaped/anchored (realm/scripting/triggers.py:117-127, 161-167). No Penn-style
  `@set attr = regex` facility. Sketch: a prefix (e.g. pattern starting `~`)
  compiles the remainder as a real `re` with numbered groups → the same `%0..%9`
  captures. Opt-in keeps existing glob patterns intact.

### 5. Attribute locks / system attributes

- [ ] **A `system`/read-only attribute tier for core stats.** PARTIAL today: a
  flag system exists (`secret`/`visual`/`safe`/`no_clone`; realm/core/attrflags.py)
  and `password` is hard-protected (`PROTECTED_ATTRS`). BUT core stats
  (hp/str/dex/con) live in the same `db` namespace as ordinary attrs with NO
  default protection — softcode `set_attr`/`@set` can write them unless a builder
  flags each `safe`. Enforcement: `functions.py:200-223`, `modify.py:134-137`.
  Sketch: either seed default `attr_flags` marking core stats `safe`, or add a
  `system` tier that even controllers can't `@set` (only ruleset code writes).
  Directly strengthens the sandbox-safety story (see showcase 250).

### 6. NO_SPOOF flag

- [ ] **`no_spoof` source-reveal.** ABSENT. Attribution today is visibility-based
  (`perceived_name`, realm/core/perception.py:129-140) — real name if visible else
  "Someone"; no "really from X" reveal, and softcode `pemit`/`remit`/`oemit`
  deliver plain untagged text. (Confirms showcase 084 voice-disguise gap.) Sketch:
  a `no_spoof` viewer tag that appends `[from <realname>]` when message source ≠
  perceived name, threaded through the propagation message builder. Pairs with the
  deferred speech-pipeline gap (items 79/80/84).

### 7. `hold` vs `wield`

- [ ] **A `held`/off-hand slot distinct from `wielded`.** Today `wield` is a single
  `wielded` tag; a new wield strips it from all other items (one active weapon, no
  slots). Light sources REUSE `wielded` (why flashlight 006 "wields" a torch).
  Worn armor is separate (`wearable` + `db.slot`). Refs: combat.py:335-386,
  manipulation.py:304-311, perception.py:51-66. Sketch: add a `held`/`offhand`
  slot (own tag + `item:on_hold` event) for shields/torches/tools, and split
  light-source readiness off the weapon `wielded` tag so you can hold a torch
  without it being your weapon.

### 8. Customizable dark-room message

- [x] **Per-room dark message — DONE 2026-07-17** (`db.dark_msg` read at render.py, falling back to the default). Formerly HARDCODED: "It is pitch black here. You can't see
  a thing." (realm/core/render.py:108; gate perception.py:69-75). Sketch: read an
  optional `db.dark_msg` on the room (fallback to the constant) at render.py:108,
  or expose a `set_dark_message()` hook mirroring the existing `set_group_formatter`
  pattern. Trivial, improves every dark-area build (showcase 038).

### 9. Expression-valued behavior params

- [ ] **`interval:[[expr]]` in `@behavior`.** ABSENT — params are literal-only
  (`_parse_value`: JSON→bool→numeric→str; olc/softcode.py:118-124). Sketch: in the
  value-coercion step, detect an inline `[[...]]` wrapper and run it through
  `eval_inline`, coercing the result to int; or accept a `key:=expr` form.
  Lets tick rates/counts derive from object state.

### 10. `@amhear`-style self-listen

- [ ] **Opt-in self-hearing.** ABSENT by design: `handle_speech` skips any match
  where `match.obj == speaker` (realm/scripting/engine.py:202-205), confirmed by
  showcase 007. Sketch: an opt-in `^^`/`AMHEAR_` prefix (or a `self_hear` tag) that
  removes the speaker-skip for those patterns, kept depth-guarded to avoid feedback
  loops. Lets an object react to its own emissions (PennMUSH `@amhear` parity).

## ~~URGENT~~ RESOLVED 2026-07-17: the sandbox recursion guard was process-global

Sharpens the earlier "inline blocks inherit the caller's stack" entry — same
root cause, **higher severity than first filed**, now reproduced against the
engine suite (not just showcase).

**Root cause:** `ScriptSandbox.execute` guards recursion with
`sys.setrecursionlimit(min(max_recursion + 10, 100))` (= 60) around its `exec`
(realm/scripting/sandbox.py:291-299). `sys.setrecursionlimit` is **interpreter-
global — it applies to every thread**, not just the caller. But `execute_async`
runs `execute` on a worker thread (`run_in_executor`). So for the duration of
ANY softcode execution, the whole process is capped at 60 frames.

**Two consequences, both observed:**
1. *Cross-thread crashes (new, production-severity).* While a worker runs a
   script, the main thread — asyncio event loop + dispatcher + engine, routinely
   deeper than 60 frames — raises `RecursionError` on its next call, in code
   that has nothing to do with softcode. Captured traceback bottoms out in
   `threading.py:368` (lock wait) during a normal test. In a live game this
   means any softcode execution can randomly crash concurrent main-loop work.
   Reproduces as a ~20-40% flake: `pytest tests/showcase/test_containers.py`
   (TestLootCrate::test_first_open_seeds_from_the_table_tail) fails
   intermittently *in isolation*, timing-dependent.
2. *Depth-dependent inline blocks (already filed).* `eval_inline` additionally
   runs `execute` synchronously on the render call stack, so a `[[...]]` block's
   survival depends on how deep `look` was dispatched.

**Correction to an earlier claim:** I previously reported the showcase suite as
"deterministic, 1734 passed, repeatably" on the strength of five clean runs.
That was wrong — the wave-2/3/4 implementer agents reported this flake
repeatedly and they were right. It is a real, pre-existing race; clean runs are
luck.

**Fix (needs a design call — do not paper over):** stop using
`sys.setrecursionlimit` as a per-script guard; it is global state and cannot be
made thread-safe. Options, roughly in order of preference:
- Enforce recursion at the AST/compile layer (reject unbounded self-recursion)
  and rely on the existing per-script **call-count** budget
  (`max_function_calls`) + timeout for runaway depth — no global state at all.
- Use a per-thread `sys.settrace`/`threading.setprofile` depth counter scoped to
  the executing thread.
- If a global limit must be kept, serialize sandbox executions behind a lock AND
  set the limit relative to the executing thread's entry depth
  (`entry_depth + max_recursion`) — still cross-thread unsafe, so weakest option.

Note the interaction with the separate "call-free loops escape the time budget"
entry: whatever replaces this guard should close both (a `while True: pass` with
no calls is currently uninterruptible).

## i18n: route hardcoded system messages through a translation layer (filed 2026-07-17)

Every engine-authored player-facing string is a hardcoded literal today —
`T('It is pitch black here.')`-style marking would make the engine
translatable/rebrandable.

**Scope (surveyed 2026-07-17):** ~175 literal `return`/`send`/`msg`/`pemit`
strings + ~145 f-string variants ≈ **320 sites**, no existing gettext/locale
infrastructure anywhere. Densest: `commands/builtin/manipulation.py` (21),
`builtin/combat.py` (18), `olc/modify.py` (15), `olc/admin.py` (14),
`combat/encounter.py` (14), `olc/softcode.py` (11), `builtin/social.py` (10),
then a long tail across olc/*, builtin/*, core/render.py, core/perception.py,
server/game.py.

**Design notes (the non-obvious parts):**

- **Translate the template, never the interpolated result.** ~145 sites are
  f-strings (`f"You put {item} in {container}."`). Naively wrapping them
  (`T(f"...")`) produces one catalog entry per runtime value and is useless.
  They must become `T("You put {item} in {container}.").format(item=…, …)` —
  i.e. mark the template, interpolate after lookup. That refactor is the bulk
  of the work, not the T() function itself.
- **Engine strings vs game content — draw the line explicitly.** `T()` covers
  strings the *engine* authors. It must NOT touch builder/player-authored
  content: room descs, `desc_extras`, softcode `say`/`pemit` output, and the
  new per-room `db.dark_msg` override (see the 2026-07-17 ergonomics batch).
  Precedent worth stating in the docs: `dark_msg` is *content customization*
  (this room reads differently); `T()` is *locale* (this player reads a
  different language). A room that sets `dark_msg` opts out of the translated
  default by design.
- **Per-recipient rendering is the crux — and it's shared.** A string returned
  from a command has one recipient, so call-time locale resolution works. But
  `remit`/`act` deliver one message to a room of players who may not share a
  locale, so the message must stay *unrendered* until delivery (a lazy/deferred
  `T` object resolved per-session, or a render hook in the propagation
  delivery step). **This is the same seam the already-filed speech-pipeline
  gap needs** (showcase items 79 languages / 80 whispers / 84 voice disguise,
  which want per-listener message transforms). Build the per-recipient
  rendering hook ONCE and both land — worth sequencing them together.
- **Session locale:** needs a `locale` on the session/player (default from
  config), settable in-game, and honored by the delivery hook.

**Sketch (incremental, each step shippable):**
1. Add `T(msg, **kwargs)` as an identity/format passthrough + a `locale` config
   default. Zero behavior change, but it *marks* strings.
2. Mechanically wrap the ~320 sites (template-then-format for the f-strings).
   Mostly rote; do it module-by-module against the density list above.
3. Add catalog extraction (a script scanning `T(...)` call sites → a `.po`/JSON
   catalog) + `scripts/gen_*`-style regeneration, wired like
   `gen_softcode_docs.py`.
4. Add the per-recipient deferred-render hook in propagation delivery (jointly
   with the speech-pipeline gap), then per-session locale resolution.
5. Ship one non-English catalog as the proof + a test asserting a translated
   session sees translated engine strings while content strings pass through.

### Resolution (2026-07-17)

**Fixed.** `ScriptSandbox.execute` no longer touches the recursion limit. The
limit is now a **process-wide game setting** applied once at boot, in the same
place as the other ambient singletons (sigils/markup), where its scope is
self-evident:

- `set_interpreter_recursion_limit(limit)` (realm/scripting/sandbox.py) — the
  only caller-facing entry, with a docstring stating it is interpreter-global,
  affects every thread, and must never be called per execution. Validates and
  raises at boot: floor `MIN_RECURSION_LIMIT = 100` (below it the engine's own
  main thread bricks — the old effective value was 60, i.e. the bug), ceiling
  `MAX_RECURSION_LIMIT = 100_000` (above it CPython segfaults instead of
  raising).
- `RECURSION_LIMIT = 1000` in config (Settings.recursion_limit, documented in
  the config template under SOFTCODE LIMITS), threaded through
  `GameServer.__init__`.
- `ScriptLimits.max_recursion` **removed** — it advertised a per-script depth
  limit the engine cannot actually enforce (user scripts recurse in real
  CPython frames the engine never sees). Its docstring now points here.
  Runaway recursion still surfaces as `ScriptRecursionError`: the interpreter
  raises `RecursionError` inside `exec` and it is converted as before.

**Verification:** the flake is gone by construction (the global mutation no
longer exists), and empirically: `tests/showcase/test_containers.py` 15/15 clean
(was ~20% failing in isolation), full suite 6/6 clean at 1759 passed (was ~30%
failing). Regression test pinned:
`test_execute_does_not_touch_the_global_recursion_limit` asserts
`sys.getrecursionlimit()` is unchanged across both a normal and an exploding
script.

**Still open (see next entry):** a *true per-script* depth limit. The floor/
ceiling only bound the process; one script can still nest to 1000.

## Per-execution recursion counting via AST injection (filed 2026-07-17)

The way to get a real per-script depth limit back — Penn's model, adapted.
Penn counts its own interpreter's recursion in per-execution state
(`pe_info->fun_recursions`, incremented/decremented around `process_expression`,
checked at parse.c:2843) because *all* Penn softcode recursion flows through
Penn's evaluator. REALM can't do that directly: scripts are real Python, so
user recursion happens in CPython frames the engine never sees — which is why
it reached for the (global, broken) recursion limit.

**Idea:** instrument the AST before compile. Walk the tree with an
`ast.NodeTransformer` and rewrite every `FunctionDef` body from `<body>` to
roughly:

    __ctx.enter()          # increments; raises ScriptRecursionError over limit
    try:
        <body>
    finally:
        __ctx.exit()       # decrements

with `__ctx` injected into the script globals (a per-execution counter object,
like `pe_info`) and `ast.fix_missing_locations()` after the rewrite. That gives
Penn's exact semantics: per-execution, no global state, thread-safe, and it can
carry Penn's dual counter (per-script + a global ceiling at N×) and Penn's
graceful degradation.

**Viable — with caveats worth knowing before starting:**
- **Lambdas can't be instrumented** (a lambda body is an expression, not
  statements). The self-passing-lambda recursion idiom the showcase teaches
  (`f = lambda self, n: ...`; see 017/024) would slip straight through. So the
  process-wide limit must REMAIN as the backstop — this is defense in depth,
  not a replacement.
- Comprehensions/generators/async defs each need their own handling.
- Only counts user-defined function calls, which is exactly the blind spot —
  engine-mediated re-entry is already counted Penn-style at
  functions.py:1033 (`_eval_depth >= 8`).
- Cost is one counter call per user function call: far cheaper than
  `sys.settrace`, which is the only other per-thread-safe option.
- Doesn't bound C-level recursion (deep `repr`, etc.) — again, the process
  limit backstops.

Sequence it with the "call-free loops escape the time budget" entry: the same
`__ctx` object could carry an instruction/loop-iteration counter (Penn's
`call_limit` per queue cycle is the precedent), closing both holes with one
mechanism.

### Decided 2026-07-17: do NOT ban lambdas to make injection airtight

The question came up: since lambdas can't be instrumented, ban them and get
complete coverage? **Technically it would work** — with lambdas gone every user
callable is a `def` the transformer can wrap, and there is no other route to an
anonymous callable (dunder names and imports are already blocked). It is a cost
question, not a correctness one. The cost is too high:

- **Lambdas are the only local-function mechanism at a live prompt.** Scripts
  are entered one line at a time (no `@edit` — see item 1e). `def f(n): return
  n+1` fits on one line but cannot be *called* on that line, so at the prompt a
  lambda is the only way to make a helper at all. Multi-line `def` does work via
  pack files / JSON-escaped `\n` values, but that pushes helper code out of the
  live prompt — against REALM's whole thesis.
- **Load-bearing in shipped content:** 12 tutorials, 25 test sites (017, 020,
  024, 100, 101, 102, 104, 105, 130, 161, 162, 250). The dominant use is not the
  exotic recursion trick — it is `sorted(x, key=lambda o: ...)` (bookshelf by
  title 020, leaderboards 104, race odds 105, poker scoring 100, trivia 102).
  None have a one-line replacement. Self-passing recursion (017, 024) is the
  minority use.
- **The payoff is small:** the process-wide limit already converts runaway
  recursion into a clean `ScriptRecursionError` — script dies, server lives. A
  per-script counter only buys failing at depth 50 instead of 1000. Actual DoS
  is bounded by the time (1500ms) and call-count (25,000) budgets, which
  lambdas do not evade.

**Therefore:** instrument the `def`s, keep the process-wide limit as the
backstop for lambda-recursion, accept partial coverage. The residual gap is "a
lambda can recurse to 1000 and die cleanly", not "a lambda can hurt the server".

**Narrower option if the self-passing idiom specifically is the worry:** ban
*recursive lambdas*, not lambdas. The AST can flag a lambda assigned to a name
that appears in its own body (`f = lambda: f()`) and the self-passing form (a
lambda whose first parameter is called within its body, `w(w, ...)`). That kills
the uninstrumentable-recursion case and leaves every `key=lambda` untouched.
Still needs the process-limit backstop for anything cleverer.

**If a ban were ever revisited:** it can only follow 1e (multi-line editing), it
permanently loses `key=lambda` at the prompt, and it requires rewriting the 12
tutorials above.

## `@function`: builder-registered softcode functions (filed 2026-07-17)

Penn's `&MYFN obj = <code>` + `@function myfn = obj/MYFN`, so softcode calls
`myfn(x)` instead of `eval_attr(get('Library'), 'myfn', x)`. Wanted; design
settled below.

**What already exists:** `eval_attr(obj, 'attr', *args)` is the execution half
(args as `arg0..argN`/`%0..%9`, `_eval_depth >= 8` recursion guard, secret-attr
read gates, fail-closed to None). Missing is only the *registry* — a
name → (obj, attr) mapping merged into the script namespace.

**Semantics: follow Penn — the executor swaps to the function object.**
Verified in source: `call_ufun_int` (pennmush src/utils.c:363) and `do_userfn`
(src/funufun.c) both call
`process_expression(..., ufun->thing, caller, enactor, ...)`, and the prototype
(hdrs/parse.h:268) is `(..., dbref executor, dbref caller, dbref enactor, ...)`
— so `ufun->thing`, the object holding the attribute, IS the executor. Inside
the function, `v(attr)` reads the *function object's* data; the caller drops to
`%@`. That is what makes a function object (5 routines + their shared data
attrs) work as a unit, and it is exactly what we want.

**This is not a new security model for REALM — it is the existing one.** A
`$deposit` verb on an admin-owned bank already runs *as the bank* with the
bank's authority; the showcase does this everywhere (bank 087, trainer 069,
jail 177, warden, mint 086). `@function` is that same arrangement reached by
name instead of by typed command.

**Therefore registration is privileged** (Builder/Admin). Penn gates it behind a
named power — `if (!Global_Funcs(player)) { notify(player, T("Permission
denied.")); }` (src/function.c:1658) — precisely because publishing a function
hands its object's authority to every caller. Same reasoning applies here.

**The two mechanisms are complementary — document them as a pair:**

| | Runs as | Purpose |
|---|---|---|
| `eval_attr(me,'helper',x)` | the **caller** (unchanged) | *subroutine* — split up your own object's code |
| `myfn(x)` (`@function`) | the **function object** | *library call* — shared service with its own data |

**Design decisions to make:**
- **Collisions.** `registered_bindings()` currently *may override* the
  vocabulary (functions.py `to_dict()`). `@function get = ...` must not silently
  shadow a builtin — reject at registration with a clear error, matching the
  "bad value raises at boot" habit. Decide precedence vs native bindings
  (suggest: builtins < native bindings < @function, all collisions rejected).
- **Args.** `eval_attr` stringifies args (`captures=[str(a) for a in args]` —
  already filed as a gap). Fix it here so library functions can take objects,
  not just strings.
- **First-class callables.** If the registry injects a real callable into the
  namespace (a wrapper around the eval_attr path), then
  `sorted(items, key=my_sort_key)` works — which erodes the strongest argument
  for keeping lambdas (see the lambda decision above). Worth doing for that
  reason alone.
- **Discovery/lifecycle:** `@function` with no args lists; `/delete`,
  `/disable` (Penn has ALIAS/BUILTIN/CLONE/DELETE/ENABLE/DISABLE/PRESERVE/
  RESTORE/RESTRICT — we need a fraction of that).
- Recursion is already handled (`_eval_depth >= 8`, Penn's `fun_recursions`).

**Companion (separate, trivial):** `&attr obj = value` as shorthand for
`@set obj/attr = value` — pure MUSH muscle memory. Note Penn requires the
object; `&myfn1 = ...` with no target would be a REALM divergence (would have
to default to `me`).

## RESOLVED 2026-07-17: event payload binding (Theme A, the #1 showcase gap)

**Shipped.** `ON_<EVENT>` and `^listen` scripts can now read what happened,
not just who did it.

**The finding that made it small:** the engine already populated every payload —
`event:payment` carried `amount`, `combat:on_damage` carried `damage`/
`damage_types` (with `target` = the defender), `combat:on_attack` carried
`weapon`, give/receive carried `item`/`giver`, poses carried `pose`,
`on_hitprcnt` carried `percent`. The data was never missing; only the namespace
binding was. `on_check` wards already had it via `_check_namespace`;
`_execute_trigger` simply never received the `Action`.

**Change** (realm/scripting/engine.py):
- Extracted `_event_namespace(action)` — the read-only subset: `atype`,
  `actor`, `target`, `adata(key, default)`, `has_atag(tag)`.
- `_check_namespace` now layers the decision verbs (`block`, `mod`,
  `is_blocked`, `set_adata`) on top of it, so both passes share one definition
  and the apply pass is read-only **by construction**: once an `ON_<EVENT>`
  runs the decision is already made, so a witness gets no veto and cannot
  rewrite an in-flight action.
- Threaded an optional `action` through `_execute_trigger`, passed from all
  three observe sites: event witnesses, `ON_ARRIVE`, and `^listen` (which also
  gives listeners `target` — the seam item 80's overheard-whispers wants).
  `$`-commands and `@tr` have no action and pass None, leaving the names
  unbound.

**Tests:** `tests/test_event_payload.py` — 10 tests driving real commands
(`pay 25 to ogre` → `adata('amount') == 25`; two NPCs distinguishing "I was
paid" from "someone was paid" via `target`; `ON_RECEIVE` reading `item`/`giver`;
`^listen` reading `message`; guards that `block`/`set_adata` are absent on the
apply pass; existing ward behavior unchanged). Full suite 1769 green.
**Docs:** an "Event data" section in the softcode reference (via the generator
HEADER) with the payload table per action type.

**Learned while testing (worth knowing):** `do_get` passes no `extra` — for
`get gem` the item IS the action's `target`. The `{"item": ...}` payloads exist
only where the target is a *person* (give/receive). So "which item?" is
answered by `target` on get/drop and by `adata('item')` on give/receive.

**Downstream now unblocked** (previously forced onto the ledger/till workaround):
armor wear booked defender-side (117), honest damage narration (115, 120),
emote/wield content reactions (072), `ON_PAYMENT` amounts everywhere (001, 002,
013, 030, 064, 067, 082, 091, 105, 106), item identity on decay/incinerator
(018, 019) and collection counters (200). The ledger idiom still works — those
tutorials are correct, just no longer the only way.

## Ledger/till idiom → `adata()` rewrites (filed 2026-07-17, deferred)

The 2026-07-17 idiom sweep modernized *syntax* only (`V()`, `incr()`,
f-strings). It deliberately did NOT rewrite tutorials whose **logic** works
around the old payload gap, because that changes what the build does, not just
how it reads:

- **Ledger/till idiom** (reconstruct a payment by diffing your own balance
  before/after): 001, 002, 013, 030, 064, 067, 082, 091, 105, 106. Now
  expressible as `adata('amount')`.
- **Unstamped-item idiom** (find the arrival by elimination): 022, 094, 096,
  097. Now expressible as `adata('item')` / `adata('giver')`.
- **Inventory-diff counters**: 200 (deferred `wait(0)` + inventory read). Now
  expressible via `target` / `adata('item')`.
- **Pose-order-only logging**: 205. Now `adata('pose')`.

**Keep the idioms documented somewhere** — they remain the correct answer for
any action that genuinely carries no payload, and the till pattern is the
general "reconstruct state you can't observe" technique. Suggested: one
reference page (or a section in 245_event_bus_tour) that teaches them once, and
the individual tutorials switch to `adata()` and link to it. That is strictly
better than the status quo, where a dozen tutorials each re-derive the
workaround as though it were the only way.

Each rewrite touches the build transcript AND its test constants (doc↔test sync
enforces the pair), so it is real work, not a regex — hence deferred rather than
bundled into the syntax sweep.

## ~~SECURITY~~ RESOLVED 2026-07-17: `on_check` wards failed OPEN on script error

Found while probing during the idiom sweep, not by reading code: an agent put a
deliberately-broken call in a ward that also called `block()`. The script raised
(NameError), `_run_check` caught `ScriptError`, logged a warning — and **the
action proceeded**. The item was picked up. The ward silently did nothing.

    try:
        await self.sandbox.execute_async(code, ctx, functions=namespace)
    except ScriptError as exc:
        logger.warning(f"on_check error on {obj.name}: {exc}")   # ...and continue

**Why it matters:** `on_check` is the *veto* surface — cursed items refusing
removal, landmines refusing pickup, capacity limits, clearance gates, escrow
protection, the jail door. A typo in any of those silently disables the
protection, and the only trace is a log line nobody reads. "Your ward has a
syntax error" and "your ward decided to allow it" are indistinguishable to the
world.

**Options (needs a design call):**
- **Fail closed** — an erroring ward blocks with a generic reason. Safest for
  security-shaped wards; risks a typo bricking a busy room until fixed.
- **Fail closed only if the ward *would* have blocked** — undecidable; discard.
- **Fail open but LOUD** — surface the error to the object's owner and/or the
  actor ("this ward is broken"), not just the log. Keeps a typo from bricking
  the game but ends the silence.
- **Per-ward opt-in** — `@set obj/on_check_failsafe = block`, defaulting to
  loud-open. Most flexible, more surface.

Recommend at minimum the LOUD variant; consider fail-closed as the default for
wards on `item:on_get`/`event:pre_enter`-style gates. Note Penn's precedent:
softcode errors return a visible `#-1 ...` string into the output rather than
vanishing — the error is *seen*.

Related: this is why the sweep brief forbade `incr`/`decr` inside wards (they
are correctly absent from the `_READONLY` namespace) — but "correctly absent"
plus "fails open" equals a security hole, not a guardrail.

## `incr()`/`decr()` need a `default` parameter (filed 2026-07-17)

`incr(name, by=1)` hardcodes a 0 baseline for a missing attribute. Real scripts
routinely read with a *different* default, and four separate sweep agents
independently hit this and correctly refused the conversion:

| Tutorial | Attr | Reads with default | `incr` would give |
|---|---|---|---|
| 029 timed door | `pending` | 1 | wrong slam count |
| 089 auction | `next_lot` | 1 | lot numbering starts at 1 not 2 |
| 058 spreading fire | `stage` | 1 | fire stages silently broken |
| 018 refrigerator | `freshness` | 6 | `0 - rate` instead of `6 - rate` |

Three of those four are *silent* breakage — tests wouldn't catch them because
the builds pre-set the attribute; only a reader copying the tutorial without
that line gets bitten. Fix: `incr(name, by=1, default=0)` / `decr(...)`.

Also worth considering (same reports): `incr` writes unconditionally, so it
can't replace a *guarded* write (082 newspaper bumps the issue number on empty
ticks; 056 countdown writes only when `n > 0`; 216 escape-room writes only in
the `else` branch). And it coerces non-numeric to 0, which would have destroyed
list attrs (099 `table`, 104 `champions`). A `default` param fixes the first
class; the rest are correctly out of scope for the sugar.

## Showcase test harness: migrate to read-from-docs (filed 2026-07-17)

The 223 tutorials are verified by 26 suites using **two different designs**, and
only one of them is sound.

**Design A — mirror + sync test (12 suites).** Build lines are duplicated as
Python literals in the test; a sync test asserts each appears in the doc. Two
holes, both hit for real during the idiom sweep:
- *Substring matching lets truncation pass.* An f-string's `"` inside a `"`
  literal ends the string early and `#` comments out the rest — the line is
  silently truncated, and `assert line in doc_text` still passes because a
  truncated line IS a substring. Caught only by a behavioral assertion.
- *A corrupted rewrite can delete tests outright and the count still looks fine.*
  One agent's script deleted 170 lines of `test_puzzles.py`; the run reported
  "93 passed" because the deleted tests simply ceased to exist.

**Design B — read from the doc (`test_social.py`).**

    def build_lines(doc_name):
        """Every command line in the tutorial's "Build it" fenced blocks."""
        body = (DOCS / doc_name).read_text()
        match = re.search(r"^## Build it$(.*?)^## ", body, re.M | re.S)
        ...

The test *executes what the doc says*. Drift is **structurally impossible** —
edit the doc and the test runs the new lines. No mirror, no sync test, nothing
to keep in step. (It is also why `test_social.py` needed zero edits during the
sweep while every other suite needed lockstep changes.)

**Recommendation:** migrate all suites to Design B. Concretely: lift
`build_lines()` into a shared `tests/showcase/conftest.py` helper and rewrite
each suite's setup to call it. Benefits beyond drift-proofing: the sweep would
have been ~half the work (docs only), and future idiom passes become docs-only.

**Suites still on Design A / with no guard at all** (12): combat_ext, comms,
doors_exits, economy_arc, economy_more, heist, living_npcs, npcs_ai, social*,
softcode, transport, traps_devices. (*social already reads from docs; it just
lacks a *named* sync test, which under Design B it does not need.)

Interim state as of this filing: all 26 suites verified in sync by hand/scripts,
full suite 1769 green — but 12 have no automated guard, and this tree has been
demonstrated to revert uncommitted docs.

### Resolution (2026-07-17)

**Fixed, both halves.** Reproduced first: every failure mode failed open — a
typo'd name, a wrong-namespace call, a runtime error, even a *syntax error* —
all logged a warning and let the action through.

**1. Runtime: fail CLOSED when the ward could have denied.**
`ScriptEngine._ward_failed` now logs at ERROR, messages the object's owner, and
blocks the action if `_ward_can_deny(code, known)` says the ward guards
something. The classifier is deliberately conservative — a ward is treated as
*provably advisory* only when it parses AND every function it calls is a name
it could actually have (check namespace + SAFE_BUILTINS) AND none is `block`:

- `block(...)` → guards → **closed**
- `blok(...)` → an *unknown callable* → **closed**. This case decided the
  design: a misspelled `block` is the likeliest ward bug there is, and a naive
  "does the AST contain a block() call?" check fails open on exactly it. My
  first implementation had that bug; the probe caught it.
- unparseable → can't tell what it guards → **closed**
- `mod(-2)`, `set_adata('damage', ...)` → provably advisory → **open** (loud).
  An armour calculation that raises must not veto the swing —
  `tests/test_on_check.py` has real `mod()`-only wards, so blanket fail-closed
  would have been a regression.

The invariant was already written down: `_run_check`'s own docstring says "a
ward must not silently *fail open*" — it's why there's no shared depth guard
there. The error path just didn't honor it.

**2. Authoring: `@set` warns when a script won't run.** `@set` stored
`block('warded'` (missing paren) with a cheerful "Set relic/on_check = ..." —
the ward was dead from birth and nothing ever said so. `script_code_of()`
(realm/scripting/triggers.py) recognises script attributes the way the engine
does — by value sigil (`$`/`^`, code after the first `:`) or attribute name
(`on_check`, `on_tick`, `ON_<EVENT>`) — and `@set` now validates and warns.
Warns rather than refuses: placeholders and `@import` are legitimate, and the
runtime fails safe on its own now. Data attributes are untouched (a `desc`
with an unbalanced paren is prose, not code).

**Tests:** `tests/test_ward_failure.py` — 29 tests covering every failure mode,
the advisory/deny classifier, the `@set` warnings, and the "healthy world
unaffected" cases. Full suite **1798 green**; none of the 25 existing showcase
wards changed behavior.

**Gotcha found while implementing:** `script_code_of` must `.strip()` the code
after the sigil split — builders write `$fetch *: force(...)` with a space, and
a leading space is an `IndentationError` to `ast.parse` even though the engine
runs it fine. That produced 72 false warnings before I caught it (the showcase
suites assert no error markers in build output — the harness earned its keep).
