# REALM Development Backlog

Prioritized list of improvements, features, and technical debt items.

**NORTH STAR: docs/design/engine_vision.md** — REALM is the Godot of
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

### Maintainability review findings (2026-07-02) — not yet fixed

Full-codebase review (3 subsystem passes). The structural tier was fixed the
same day (see Completed); these remain, roughly by impact:

- [ ] **Scripting follow-ups** (engine wired 2026-07-02; actuators +
  builder loop 2026-07-04, see Completed): zone objects and the Master
  Room are still unimplemented in `get_search_objects` (plan.md search
  order steps 4–5); scripts can emit communication commands plus
  `move`/`trigger` — `get`/`drop`/`open` and full dispatcher access
  (`@force`) remain; listen triggers hear `extra["message"]` actions
  (say/shout/ooc/emit) but not poses.
- [ ] **Spacegame content:** the doctor's `$help` softcode is shadowed by
  the builtin `help` command (softcode only sees *unknown* commands) —
  rename the trigger or document the precedence.
- [ ] **Rewrite or delete `examples/spacegame/commands.py`.** It imports a
  command API that doesn't exist (`realm.commands.registry`, `context`,
  `Command`) — cannot be imported. Add an import smoke-test for examples.
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
- [ ] **Spacegame duplicates Combatant.** `SpaceCharacter.heal/take_damage`
  vs `Combatant` both write `db.hp` through different paths. Pick one owner.
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
    plan.md), event witnessing (the master's ON_ENTER/ON_DEATH fire
    for events in member rooms), and `zone_property(room, name)` —
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
