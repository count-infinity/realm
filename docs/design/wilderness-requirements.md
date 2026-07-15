# Wilderness — Requirements & Build Plan (Ephemeral Stage 2)

**Status:** **shipped** — `realm/core/wilderness.py`, the
deferred-destination hook in `realm/core/movement.py`, the shared R9
teardown in `realm/core/teardown.py` (instances adopted it), the
`enter_wilderness` softcode surface, the tick reaper, the load-time
dangling-location reconcile, `tests/test_wilderness.py` +
`tests/test_wilderness_demo.py`, and the `frontier` example region
(`examples/wilderness/`). This document remains the spec the
implementation answers to. Wilderness is Stage 1's sibling over the same
machinery, keyed by **coordinate** instead of by **player**.

---

## 1. Goal

A **wilderness** is a region of procedurally-described space too vast to
hand-build — an overworld, an ocean, a starfield, a frontier. The player
walks `north` / `south` / `east` / `west` and the cell they arrive in is
**materialized on demand** from a map-provider, **shared** by everyone at
that coordinate, **transient** (never persisted), and **reaped** when it
empties. Two players who walk to the same `(x, y)` stand in the *same* cell.

Rule of thumb (from `ephemeral-rooms.md`): content **authored and stateful**
→ *instance* (Stage 1, per-player); content **computed from position** →
*wilderness* (Stage 2, per-coordinate). They compose — a wilderness whose
landmark coordinates are doorways into per-player instanced dungeons.

## 2. What's already shipped (build ON this)

Wilderness is a thin convention layer over primitives that already exist and
are tested. Do **not** reinvent these:

| Primitive | Where | Use for wilderness |
|---|---|---|
| `ephemeral` tag → never persisted | `realm/persistence/manager.py` (`_save_object` guard + dirty-sweep filter) | cells are ephemeral; excluded from SQLite + reboot |
| `import_objects(data, persistence)` | `realm/persistence/worldio.py` | not strictly needed if cells are built directly, but available |
| `event:on_fail` dead-end hook | `realm/core/movement.py:fire_exit_fail` — a null-destination exit fires it; if a handler relocates the actor, the "leads nowhere" line is suppressed | authored `@afail` reactions on true dead-ends (R4) — **no longer** the movement trigger (§4.3) |
| `move_to(actor, dest, *, force, mover)` | `realm/core/movement.py` | move the walker into the materialized cell (checked or forced) |
| evacuation guard + reboot reconcile | `engine.py` `destroy` op; `game.py:_reconcile_orphaned_players` | a player mid-wilderness at reboot lands home, never "nowhere" |
| idle reaper on the world tick | `game.py:_tick_loop` → `instances.reap_idle` | mirror it: `reap_wilderness` on the same pulse |
| the instances module (the pattern to mirror) | `realm/core/instances.py` — `EPHEMERAL_TAG`, `materialize`, `enter`, `reap_idle`, `destroy_instance`, `evacuation_room` | **copy the shape**; wilderness is `instances.py` keyed by coord not owner |
| `eval_attr` (Penn `u()`) | softcode | run the map-provider's per-coordinate softcode — the kernel binds `x`/`y` as named globals (`ScriptContext.extra`, the established kernel pattern); softcode-side `eval_attr` passes them as positional `arg0`/`arg1` strings |

The genuinely hard part — a transient, self-reaping, evacuation-safe room
materialized on demand — is **done**. Wilderness adds: coordinate keying, a
map-provider convention, and directional get-or-create movement.

## 3. Functional requirements

- **R1 — Coordinate-keyed, shared cells.** A cell is identified by
  `(region, x, y)`. Everyone who walks to that coordinate shares one cell
  (contrast instances: one copy per player). `cell_for(region, x, y)`
  returns the live cell or `None`.
- **R2 — Materialize from a map-provider.** A new cell's name, description,
  terrain, and open exit directions come from the region's **map-provider**
  — softcode evaluated with the coordinate bound. Authoring the provider is
  how a builder defines a wilderness; the engine never hardcodes terrain.
  **The provider is a contract: `is_valid` and `cell_exits` must be pure
  functions of `(region, x, y)`** — cells reap and re-materialize constantly
  (R6), and nondeterminism there mutates topology (an open pass is closed on
  the walk back). `cell_name`/`cell_desc` should be stable too; per-look
  variation belongs in `[[...]]` viewer flavor, and wanted noise derives
  from a stable hash of the coordinate, never `rand()`.
- **R3 — Directional get-or-create movement.** Walking a direction from a
  cell computes the neighbor coordinate, get-or-creates that cell, and moves
  the walker in — a *real* `move_through_exit` traversal over a **deferred
  destination** (§4.3): the destination is materialized after the
  origin-side gates pass, then locks, wards, `on_enter`, and the follower
  cascade all run unchanged. Not a self-loop, not a per-viewer description,
  not a failure-hook side effect.
- **R4 — Bounds are true dead-ends.** If the map-provider says a neighbor
  coordinate is invalid (ocean edge, cliff, map bound), the exit stays a
  genuine dead-end with an authored message ("The sea blocks your way.") —
  no cell is created.
- **R5 — Enter and leave the persistent world.** A persistent room has an
  exit *into* the wilderness at a start coordinate; designated wilderness
  cells have exits *back out* to persistent rooms (a town gate). Crossing
  either boundary is seamless.
- **R6 — Reap empty cells.** A cell sat empty past its idle TTL is
  destroyed (recreate-on-demand; do not pool). **Empty means: contains no
  player.** NPCs and items never hold a cell open. Teardown still
  defensively evacuates any player found at destroy time (the
  check-to-teardown race guard) via the shared `evacuation_room` ladder;
  every other occupant follows the R9 contents policy.
- **R7 — Never persisted; reboot-safe.** Cells are `ephemeral` — not saved,
  not reloaded. A player standing in the wilderness at reboot is reconciled
  home/return by the existing guard. Progress inside a cell is intentionally
  not durable.
- **R8 — Softcode surface.** The whole thing is reachable and authorable
  from softcode: define a region + provider in-game, and the movement hook
  is softcode on the cells' exits (set by the materializer, not the
  builder). Authority-gated like every relocation.
- **R9 — Teardown never orphans an object.** The pre-Stage-2 teardown was
  player-only at every layer: `destroy_instance` evacuated only
  `player`-tagged occupants, the engine `destroy` op likewise, and reboot
  reconcile iterated only players. A persistent item dropped in an ephemeral
  room was neither evacuated nor deleted — it kept a location pointing
  at a dead room and its row was *saved with a dangling `location_id`*,
  reloading silently at `location=None`. Wilderness makes dropping things on
  the ground an everyday path, so this was a blocker, not a nit — closed by
  the shared helper (`realm/core/teardown.py`: `release_contents` applies
  the disposition below; instances adopted it). Policy:
  - **ownership decides** (one rule for items and NPCs alike): an object
    whose `.owner` is a player is delivered to that player's `home` (else
    the start-room floor), logged; an object with no owner — or a
    non-player owner — is **deliberately destroyed** with the cell
    (`persistence.delete` + a log line) — R7's non-durability applied to
    contents; loud deletion, never silent limbo;
  - **reboot reconcile extends beyond players** (the crash-path backstop):
    any persistent object reloading with a dangled location gets the same
    ownership disposition — player-owned → the owner's home (else the
    start room); anything else is emptied (the R9 recursion) and deleted,
    logged — never `location=None` silently.
  Implemented in the **shared reap+evacuate helper** (`realm/core/teardown.py`)
  so instances inherit the fix — this closed a gap that was live in shipped
  Stage 1.
- **R10 — Provider failures are loud, not oceanic.** `eval_attr` returns
  `None` on *any* script error, and `materialize_cell` returns `None` for
  invalid coordinates — naively a syntax error in the provider renders the
  whole region as the R4 bounds message ("The sea blocks your way",
  everywhere, forever, no log). The materializer must distinguish *evaluated
  false* from *failed to evaluate*: a provider error emits a structured,
  builder-visible error plus a walker-facing message distinct from the
  authored dead-end; `cell_name`/`cell_desc` erroring mid-build fall back to
  terse defaults + log rather than half-building the cell.

## 4. Recommended design

Mirror `instances.py` in a new `realm/core/wilderness.py`. The movement
trigger is a **deferred exit destination**: wilderness exits are *real,
normal exits* whose destination doesn't exist yet — a small kernel hook in
`move_through_exit` resolves it *after the origin-side gates pass*
(materializing the neighbor cell), then the traversal proceeds exactly like
any door: destination gates, relocate, `on_enter`, follower cascade. This
is `ephemeral-rooms.md` kernel bit #3 in its final form. The earlier
`on_fail` dead-end idea is retired for movement — it bypassed the whole
normal-move pipeline, which is precisely where followers, wards, and
consent live; `on_fail` remains what it always was, the authored `@afail`
reaction hook. Instances' portal entry can migrate onto the same hook
later — one mechanism, two keyings.

### 4.1 Data model

- **Region master** — a *persistent* object (built in-game or shipped in a
  pack), tags `wilderness_region`, name = the region id (e.g. `wilds`).
  Attributes:
  - map-provider softcode (on the master, or a referenced object),
    evaluated per coordinate with `x`/`y` bound — the kernel builds the
    `ScriptContext` itself with `extra={'x': x, 'y': y}` (named globals, the
    established kernel pattern; no `eval_attr` change needed):
    - `is_valid` → bool (bounds / water / walls)
    - `cell_name` → str
    - `cell_desc` → str (may itself contain `[[...]]` for per-looker flavor)
    - `cell_exits` → list of open directions (default the 4/8 compass)
    - `cell_terrain` → str tag(s) applied to the cell (optional)
  - `edge_msg` — authored bounds line (R4; a plain string, not softcode),
    stamped as `fail_msg` on the cells' directional exits
  - `cell_populate` (Stage 3) → list of **prototype dicts** — the exact
    shape `SpawnerBehavior` already speaks (`name`, `tags`, `attrs`,
    `behaviors`) — spawned into the cell at materialize time via
    `spawn_from_prototype`. The kernel injects `ephemeral` + the region
    zone tag (so spawns die with the cell, R9) and strips
    identity-bearing tags a spawn must never carry (`player`, `room`,
    `exit`, `start_room`, …), loudly. Unlike `is_valid`/`cell_exits`,
    this attr **may** be random — a re-materialized cell re-rolling its
    encounter table is the genre, not a bug. Errors follow the R10
    flavor rule: logged, cell still builds, unpopulated.
  - `idle_ttl` — default **120s**, *not* `instances.DEFAULT_IDLE_TTL`
    (900s). An instance TTL amortizes a full zone import; a cell re-derives
    from a few provider evals, so its TTL is only a walk-back-rejoin grace.
    At 900s a sprinter (one cell per ~2s) trails ~450 live cells — ~2–4k
    ephemeral objects sitting in the cache that the 5s flush sweep and every
    `find_objects` call scan linearly; at 120s the trail caps near 60.
  - `start_coord` — `(x, y)` where the world-entry exit drops you
- **Cell** — an `ephemeral` room tagged `room` + `ephemeral` +
  `zone:wilderness:<region>` (the per-region zone tag — see `_region_zone`
  in §4.2 — so a region's cells are one zone and don't collide with
  instances or other regions) + identity tag
  `wildcell:<region>:<x>,<y>`. Attrs: `wild_region`, `wild_x`, `wild_y`,
  `last_active`.
- **Cell exit** — one `ephemeral` exit object per open direction, a *real*
  exit with a **deferred destination**: no `destination` stored; instead
  `dest_resolver = "wilderness"` plus `wild_dx`/`wild_dy` (the step
  offset), and `fail_msg` stamped from the region's `edge_msg`. The
  movement kernel materializes the neighbor at traverse time (§4.3).
  (Exits *back to the persistent world* are ordinary exits with a real
  `destination`, set from `cell_exits` when the provider names one.)

### 4.2 Core module — `realm/core/wilderness.py`

```
WILDERNESS_REGION_TAG = "wilderness_region"
def _cell_tag(region, x, y): return f"wildcell:{region}:{x},{y}"
def _region_zone(region):    return f"zone:wilderness:{region}"

_cells: dict[tuple[str, int, int], GameObject]
    # THE lookup — cell_for runs on every step (the hottest path) and
    # find_objects is a linear scan of the whole cache; the identity tags
    # stay for debugging/zone tooling, never for lookup.

def cell_for(region, x, y) -> GameObject | None          # index lookup
async def materialize_cell(region, x, y, persistence) -> GameObject | None
    # None iff is_valid(x,y) evaluated false; a provider *error* raises
    # ProviderError instead (R10) — never masquerades as "invalid". Else
    # build the ephemeral cell + directional dead-end exits from the
    # map-provider, tag + attr + index it. Concurrent callers for one
    # coordinate share a single in-flight build (a _pending task map) —
    # never two cells for one coord.
async def resolve_wilderness_exit(exit_obj, actor) -> GameObject | None
    # the registered dest_resolver: region+coord from the exit (dx/dy step
    # off its cell, or absolute wild_x/wild_y — the world-entry seam);
    # is_valid gate; cell_for or materialize_cell; ProviderError -> log,
    # then DestinationUnavailableError (distinct walker message, R10).
async def enter_cell(player, region, x, y, persistence) -> GameObject | None
    # the scripted-entry arm: cell_for or materialize_cell; catches
    # ProviderError (log + walker message, no move); move_to(player, cell)
    # — a placement, teleport semantics; bump last_active.
async def reap_wilderness(persistence, *, now=None) -> int
    # iterate the index: every cell empty past its region idle_ttl ->
    # tear down per R9 (players evacuated via evacuation_room, items
    # destroyed+logged, NPCs home-or-destroyed), drop from the index.
```

The shared reap+evacuate helper was extracted to `realm/core/teardown.py`
(`evacuation_room`, `release_contents`, `subtree_has_player`); both
`instances.py` and `wilderness.py` import it, so the R9 policy cannot drift
between them.

### 4.3 The movement trigger — deferred exit destinations

- **Kernel hook (small, generic):** `movement.py` gains a resolver registry
  — `register_dest_resolver(name, fn)` — and `move_through_exit` accepts a
  `None` destination when the exit carries `db.dest_resolver`. Order:
  origin-side gates first (combat/unconscious, BASIC lock, closed, skill)
  — **only then** is the resolver awaited to materialize the destination;
  then the rest of the normal pipeline untouched (destination ENTER lock,
  `on_leave` gate, `pre_enter` ward, relocate, `on_enter`, follower
  cascade). Nothing is created for a walker whose move the origin would
  have refused anyway.
- **The wilderness resolver** reads the traversed exit: its cell's
  `wild_region`/`wild_x`/`wild_y` plus the exit's `wild_dx`/`wild_dy` (or
  the exit's own absolute `wild_region`+`wild_x`/`wild_y` — the world-entry
  seam), checks `is_valid`, and returns `cell_for(...) or
  materialize_cell(...)`:
  - invalid coordinate → resolver returns `None`; the walker sees the
    exit's authored `fail_msg` (stamped from the region's `edge_msg`) or
    the default dead-end line, and `on_fail` fires as for any dead-end
    (R4);
  - `ProviderError` → logged, walker sees a *distinct* "strange force"
    message (R10), no move, no cell.
- **World-entry exit**: a persistent room's exit with
  `dest_resolver = "wilderness"`, `wild_region`, and absolute
  `wild_x`/`wild_y` — same resolver, absolute-coord arm. Exits back out are
  ordinary exits (R5).
- **Followers need nothing**: the traversal *is* `move_through_exit`, so
  `bring_followers` cascades the party exactly as through any door — the
  earlier explicit-replay design is retired along with `on_fail`.
- **Scripted entry** (R8): softcode `enter_wilderness(player, region, x,
  y)` mirrors `enter_instance` — authority-gated, queues a `('wilderness',
  …)` op, drained to `wilderness.enter_cell` (a `move_to` placement, so
  teleport semantics apply).
- **Only players materialize** (Stage 3): the resolver get-or-creates a
  missing neighbor only for a `player`-tagged walker. A spawned mob may
  pursue into an *existing* cell, but a missing one is a dead-end for it
  — otherwise one wandering wolf generates terrain forever.

### 4.4 Authority & consent (do not regress the audit)

Relocation into a wilderness cell rides the same authority model just
hardened:
- Walking a wilderness exit is a **normal `move_through_exit` traversal** —
  the walker moves themself through a real exit; no witness-consent
  subtlety exists on this path at all (that was the retired `on_fail`
  design's burden). The scripted surface (`enter_wilderness`) rides the
  same `may_relocate`-or-consenting-enactor gate as `enter_instance`.
- A wilderness cell must **not** grant its occupants relocation authority
  over each other. Cells are `ephemeral` and typically unowned → the
  `may_relocate` `loc.owner is not None` guard already denies co-located
  objects. Add a security test proving a scripted object in a wilderness
  cell can't teleport a co-occupant.

## 5. Kernel vs convention (keep the kernel minimal)

- **Kernel (already exists):** ephemeral persistence exclusion,
  `move_through_exit` / `move_to`, evacuation + reboot reconcile, the tick
  reaper hook.
- **New kernel (one small bit):** deferred exit destinations in
  `movement.py` — a named-resolver registry consulted by
  `move_through_exit` when an exit has `dest_resolver` and no
  `destination`, invoked after the origin-side gates (kernel bit #3 of
  `ephemeral-rooms.md`, final form; generic — instance portals can adopt
  it later).
- **New kernel-ish (small, game-agnostic):** `realm/core/wilderness.py`
  orchestration (coordinate keying, get-or-create, reap) — mirrors
  `instances.py`; must carry **no genre/terrain logic** (that's the
  provider's job). Register `reap_wilderness` on the tick next to
  `reap_idle`. Two shared-machinery fixes ride along: the extracted
  reap+evacuate helper gains the R9 non-player contents policy (instances
  inherit it), and reboot reconcile extends beyond players (R9 backstop).
- **Convention/softcode (the game):** the map-provider (terrain, names,
  validity, exits), the region master, `[[...]]` per-looker cell flavor.
  A pack ships an example region.

## 6. Edge cases to handle (and test)

1. **Shared occupancy** — two players walk to the same coord → one cell;
   both present; walking apart materializes distinct neighbors.
2. **Invalid neighbor** — `is_valid` false → no cell, authored dead-end
   message, walker stays.
3. **Return exit into the wilderness** — walking back to a coord you left
   (still occupied by someone) rejoins the *same* cell, not a fresh one.
4. **Reap while adjacent occupied** — an empty cell next to an occupied one
   still reaps; re-materializes on demand when re-entered.
5. **Reboot mid-wilderness** — cell gone on reload → player reconciled to
   home/return (existing guard); no orphan, no resurrected cell.
6. **Evacuation on reap with a straggler** — a player still in a reaped cell
   → `evacuation_room` ladder (return → home → start_room).
7. **Followers** — a party walking the wilderness cascades into the same
   neighbor cell for free: the traversal *is* `move_through_exit`, the one
   place the cascade lives (§4.3).
8. **Leaving to the persistent world** — a cell's real-destination exit to a
   town works and the wilderness cell reaps behind them.
9. **Consent/authority** — an authored `on_fail` portal on a true dead-end
   may relocate the walker (the fail line suppressed, R4); a co-located
   scripted object cannot move a co-occupant (guarded).
10. **Contents of a reaped cell** — an unowned object is destroyed
    deliberately and logged; a player-owned object lands in its owner's
    home (R9); nothing is left pointing at the dead cell, and after a
    reboot no persistent object sits silently at `location=None`.
11. **Broken provider** — `is_valid` raising → error logged, walker stays,
    and the message is *distinct* from the authored R4 bounds message.
12. **Reap → re-materialize stability** — a cell reaped and re-entered has
    identical validity and open exits (R2 determinism); only `[[...]]`
    viewer flavor may vary.
13. **Spawned mob lifecycle** — a `cell_populate` spawn is present when
    the walker arrives, never holds the cell open alone, and dies with
    the cell at reap; a broken or wrong-shaped `cell_populate` logs and
    leaves the cell unpopulated (never half-built).
14. **Mob at the frontier of the materialized world** — a mob walking a
    direction whose cell doesn't exist gets a dead-end; the same walk by
    a player materializes it. A mob may follow a fleeing player into a
    cell that already exists.
15. **Spawn tag hygiene** — a prototype claiming `player` / `room` /
    `exit` / `start_room` etc. has those tags stripped with a logged
    warning; a spawn can't impersonate an evacuation floor or hold cells
    open.

## 7. Test plan (`tests/test_wilderness.py`, Simulator-driven)

- `cell_for`/`materialize_cell` unit: valid coord builds a tagged ephemeral
  cell with directional dead-end exits; invalid coord → None.
- `enter_cell` moves the player in; second player to the same coord shares
  the cell (`is` identity); to a different coord gets a different cell.
- Walk N then S returns to the origin cell while it's still occupied.
- E2e: `sim.do(player, "north")` from a wilderness cell materializes the
  neighbor and moves (normal traversal, normal room render); an invalid
  direction shows the authored edge message and doesn't move.
- Gate order: a walker the origin refuses (locked exit, in_combat)
  materializes **no** cell.
- World seam: a persistent room's wilderness-entry exit drops the player at
  `start_coord`; a cell's back-exit returns them to the town.
- Reap: empty cell past TTL is destroyed; occupied survives; straggler
  evacuated; re-enter after reap makes a *fresh* cell.
- Persistence: a real `:memory:` `PersistenceManager` never writes a
  wilderness cell (mirror `test_instances.test_ephemeral_objects_are_never_persisted`).
- Security: co-located scripted object can't relocate a co-occupant.
- R9 contents: drop an unowned item in a cell, force-reap → deleted +
  logged, nothing dangling anywhere; a player-owned item lands in the
  owner's home; an unowned NPC dies with the cell.
  Reload test: no persistent object comes back at silent `location=None`
  (dangled locations are reconciled or reaped at load).
- Followers: leader + follower walk `north` → both stand in the same new
  cell; the follower's arrival doesn't trigger a second materialization.
- Concurrency: two walkers resolving the same unmaterialized coord in one
  window share one build (one cell, one encounter roll).
- R10: a provider whose `is_valid` raises → structured error logged, walker
  doesn't move, message differs from the authored bounds message;
  `cell_name`/`cell_desc` erroring → cell still builds with terse defaults
  + a logged error.
- Determinism: materialize → reap → re-materialize the same coord → same
  validity and open exits.
- Population: a populated cell has its spawns on arrival (ephemeral +
  zone-tagged, denylisted tags stripped); spawns die with the reap; a
  mob-only cell still reaps; a mob can't materialize a neighbor but can
  enter an existing one; broken/wrong-shaped `cell_populate` → logged,
  cell unpopulated.

## 8. Decisions for the implementer (with recommendations)

- **Coordinate space:** 2D `(x, y)` only. 3D free-flight (continuous space,
  vectors) is the separate **spatial primitive** — explicitly out of scope;
  discrete cells are rooms. (See `features-roadmap.md`.)
- **Compass:** support 8 directions (incl. diagonals) via `wild_dx/dy`; the
  provider's `cell_exits` decides which are open. Default 4-way if unset.
- **One cell reaper or two?** Recommend a *shared* reap+evacuate helper used
  by both `instances.reap_idle` and `wilderness.reap_wilderness`, keyed
  differently (owner vs coord). Extract during this work.
- **Region master vs pure tags:** a master object is cleaner (holds provider
  + ttl + start), mirrors the instance-master. Recommend the master.
- **Map-provider location:** softcode attrs on the master, evaluated per
  coordinate with `x`/`y` bound (kernel-built `ScriptContext`, §4.1). A
  generator that emits full worldio
  area-data per cell is a *possible* alternative (composes with
  `import_objects`) but heavier; start with per-attr softcode.
- **Landmarks → instanced dungeons:** composition (a cell coord whose exit
  `enter_instance`s) — design for it, defer building it.
- **Population (Stage 3 — shipped).** The `cell_populate` provider attr
  (§4.1) is the `at_prepare_room` analog: prototype dicts spawned at
  materialize via `spawn_from_prototype` — one vocabulary shared with
  `SpawnerBehavior`, no parallel spawn system. Spawns are born
  `ephemeral` + zone-tagged: they never hold a cell open, die with it at
  teardown (R9; a *player-owned* pet still follows the ownership rule),
  and there is deliberately no in-cell respawn timer — a cell's whole
  life is ~one visit, and the reap/re-materialize cycle *is* the respawn
  (the encounter table re-rolls). Mobs never materialize cells (§4.3).
- **Non-player contents on teardown:** ownership decides — unowned →
  destroyed loudly; player-owned → the owner's home (R9) — in the *shared*
  helper, so instances get the same fix; this closes a live Stage 1 gap,
  not just a wilderness requirement. (Forbidding `drop` in ephemeral rooms
  was considered and rejected — dropping mid-fight is normal play.)
- **The deferred-destination hook is generic:** registered by name
  (`dest_resolver = "wilderness"`). Instance portals migrated onto it
  2026-07-14 (`dest_resolver = "instance"`,
  `instances.resolve_instance_exit`) — the portal-router of
  `ephemeral-rooms.md`: followers re-resolve individually, so `shared`
  routes into the owner's copy and `solo` bounces at the threshold.

## 9. References

- `docs/design/ephemeral-rooms.md` — the parent design (instances +
  wilderness = one primitive); this doc is its Stage 2.
- `docs/design/action-tags.md` — movement wards, `move_to`, relocation
  authority (`may_relocate` / `_mover_owns_destination`).
- `docs/design/pennmush-inventory.md` — the `@afail`/`event:on_fail` hook.
- `docs/design/features-roadmap.md` — where wilderness sits; the spatial
  primitive that is *not* part of this.
- Code: `realm/core/instances.py` (mirror), `realm/core/movement.py`
  (`fire_exit_fail`, `move_to`), `realm/persistence/manager.py` (ephemeral
  guard), `realm/server/game.py` (reaper hook + reboot reconcile).

## 10. Definition of done

- `realm/core/wilderness.py` with `cell_for` / `materialize_cell` /
  `enter_cell` / `reap_wilderness` (index-backed, R10 error split) + the
  registered wilderness resolver; the deferred-destination hook in
  `movement.py`; the `enter_wilderness` softcode fn + drain op; the tick
  reaper wired.
- The shared reap+evacuate helper extracted with the R9 contents policy,
  `instances.py` switched onto it, and reboot reconcile covering
  non-players.
- An example region shipped as data (a small pack or a builder script) so
  `sim.do(player, "north")` walks procedurally generated cells.
- `tests/test_wilderness.py` green (all of §7); full suite green; lint clean.
- `ephemeral-rooms.md` updated (Stage 2 shipped; kernel bit #3 landed as
  the deferred-destination hook, the `on_fail` movement trigger retired);
  `features-roadmap.md` wilderness row → shipped.
- Vision-keeper audit clean (esp. kernel purity — no terrain/genre in
  `wilderness.py` — and the consent/authority checks of §4.4).
