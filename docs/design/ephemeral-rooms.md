# Ephemeral Rooms — On-Demand Instances & Wilderness

**Status:** both stages **shipped**. Stage 1 (**per-PC instances**) —
`realm/core/instances.py`, the `ephemeral` transient flag in persistence,
the softcode `enter_instance()` surface, and the idle reaper on the world
tick. Stage 2 (**wilderness**) — `realm/core/wilderness.py` over the same
machinery, keyed by coordinate; see `wilderness-requirements.md` (the
executable spec) for what shipped. This document is the shared design.

**What's shipped (Stage 1):**

- **Transient flag** (kernel #1) — any object tagged `ephemeral` is
  registered in the live cache but never written to SQLite
  (`PersistenceManager._save_object` early-returns on it), so an instance
  copy can't resurrect on reboot.
- **Evacuation guard** (kernel #2) — destroying a room relocates any player
  standing in it (to their home in the general path; to the instance's
  `return_room` else home in `destroy_instance`) — never orphaned.
- **The convention layer** — `instance_template` opt-in tag, `ephemeral` +
  `instance:<template>:<owner>` identity tags, an instance-master object,
  the materializer (`import_objects`), per-PC / shared-follower keying, and
  the idle reaper — all in `realm/core/instances.py`.
- **Softcode surface** — `enter_instance(player, template, mode=,
  return_room=, idle_ttl=)`, authority-gated (`_may_relocate` or a
  consenting enactor, + the template opt-in and the entry room's ENTER
  lock), mirroring `act()`/`teleport_obj`.

**Portal migration (2026-07-14):** instance portals are now *real exits*
with `dest_resolver = "instance"` (attrs: `instance_template`,
`instance_mode`, `instance_return` — default the portal's own room —
and `instance_ttl`), resolved through the same deferred-destination hook
as wilderness. Walking one is a normal `move_through_exit`, so wards,
locks, `on_enter`, and the follower cascade apply; the softcode
`enter_instance()` remains the scripted API (game events opening
portals), and the old `ON_FAIL` dead-end pattern still works but is no
longer the recommended portal shape.

**Closed gap (fixed with Stage 2):** teardown used to be *player-only* —
a foreign persistent object (a dropped item, a wandering NPC) in a
destroyed copy was orphaned with a dangling `location_id`, reloading
silently at `location=None`. The shared teardown (`realm/core/teardown.py`,
used by both reapers) now applies the R9 disposition — players evacuated,
player-owned property to its owner's refuge, everything else destroyed
loudly — and load-time reconcile covers non-players (see
`wilderness-requirements.md` R9).

**Still design-only:** pooling instead of recreate (a later optimization,
only if cell churn gets hot).

Two features that look different are the *same primitive*: a per-party
**instance** (a private copy of an authored area, so puzzles and loot
aren't griefed) and a **wilderness** (procgen space too vast to hand-build).
Both want the same thing — a real room **materialized on demand** from a
template, private, **transient** (never persisted), and **reaped when
idle**. The two differ only in what *keys* the copy: a party, or a
coordinate.

This is **opt-in**. Persistent rooms and areas stay the default and the
common case; a room becomes a template only by carrying a tag. Nothing
about a normal world changes.

## Why not "one room, per-viewer descriptions"

The tempting shortcut — one wilderness room whose `[[...]]` description
renders per looker from their coordinate — **only handles `look`**.
Everything else in REALM is scoped to the **room object and its
`contents`**, with no notion of a sub-coordinate:

- speech / `remit` / `act(targeting='room')` deliver to `room.contents` —
  a player at (0,0) hears one at (500,500);
- `room_is_lit` reads dark/light **tags on the room object** — one cell
  can't be a dark cave while another is a lit meadow;
- there is one combat encounter per room; two unrelated fights collide;
- stealth, zone events, and perception all key on the room / its contents.

So the moment two players share one virtual room at different cells, they
wrongly share audience, flags, combat, and stealth. **Cells must be real
rooms.** (This is exactly why Evennia's wilderness pools real room objects
and merges/splits them — to reuse the room-scoped machinery unchanged. The
pooling isn't overhead it failed to avoid; it's the reason the design
works.) So we make real rooms on demand — and the per-viewer `[[...]]`
description becomes a nice procgen-flavor layer *on top* of real rooms, not
a replacement for them.

## The primitive: materialize → occupy → reap

```
 [template]  --(enter / step)-->  materialize a private, transient copy
    tag                              tag: ephemeral + instance:<t>:<key>
     |                                   |
     |                              occupy (bump last_active)
     |                                   |
     +<---- reaped when idle+empty ----- idle
             (evacuate stragglers first, then destroy)
```

## Three small kernel pieces

Everything else is convention (below); the kernel only needs:

1. **A transient / "do-not-persist" flag.** REALM's in-memory store
   dirty-syncs to SQLite and reloads on boot — an instance would be
   persisted and *resurrect* on reboot. An `ephemeral` tag must (a) exclude
   the object from the sync and (b) never be reloaded. This was the one
   thing the persistence model couldn't express (now the `ephemeral`
   early-return in `_save_object`; CoffeeMud's whole ephemerality is one
   predicate: `isSavable()==false` for instance children).
2. **An evacuation guard in `destroy_obj`.** Destroying a room that still
   holds a player must relocate them first — to the instance's
   `return_room` if it set one, else the player's **home** — never orphan
   them.
3. **Formula-resolved exit destinations** (wilderness variant only). An
   exit's `destination` was a fixed object; it can now be resolved by
   softcode at traverse time, so a direction exit can *get-or-create the
   room for the neighbor cell* and land you in a **real** room (not a
   self-loop). *Final form:* a **deferred exit destination** — a named
   resolver the movement kernel consults after the origin-side gates pass,
   so the traversal stays a normal `move_through_exit` (wards, locks,
   `on_enter`, followers all unchanged). The `on_fail` dead-end idea was
   considered and retired for movement (see `wilderness-requirements.md`
   §4.3).

## The convention layer (data + behaviors, no new subsystem)

| Piece | What | Built from |
|---|---|---|
| **Template tag** | opt-in mark on a source room/area (e.g. `instance_template`) | a tag |
| **`ephemeral` tag** | on materialized copies — transient (kernel #1), reapable | a tag |
| **Identity tag** | `instance:<template>:<owner-id>` — extends the `zone:` scheme | a tag |
| **Instance-master** | one object per live copy holding `{template, owner, mode, return_room, idle_ttl, entry, last_active}` | a GameObject (mirrors zone-master) |
| **Portal-router** | on trigger: the owner → their copy; a follower/party-member of an owner (if `shared`) → that owner's copy; a follower of a `solo` owner → bounced at the threshold; else materialize a new copy | **shipped** — `dest_resolver="instance"` portal exits (`instances.resolve_instance_exit`) over the deferred-destination hook; `bring_followers` re-resolves each follower individually, so the routing applies per walker |
| **Reaper** | idle + empty → R9 evacuation (`release_contents`) → delete the copy + master | **shipped** — `instances.reap_idle` / `wilderness.reap_wilderness`, called from the world tick |
| **Materializer** | clone the template's rooms/contents with fresh ids | `import_objects` (already exists) |
| **Population** | mobs/items in the copy | `SpawnerBehavior` in cloned instance templates; the provider's `cell_populate` prototypes for wilderness cells |
| **Map-provider** (wilderness) | `is_valid`, `cell_name`, `cell_desc`, `cell_terrain`, `cell_populate` attrs on the region object | a softcode/pack library |

## Two keying strategies

| | **Per-player instance** | **Per-coordinate wilderness** |
|---|---|---|
| Key | the PC who triggers it (one copy per player) | `(x,y)` cell |
| Trigger | first through a portal exit, *or* a game event opens a portal (a solved puzzle) | a formula exit that get-or-creates the neighbor cell |
| Source | a hand-authored template area | a map-provider (procgen) |
| Content | authored rooms, spawners, scripted encounters | computed per coordinate |
| Reaped | when the owner leaves and it's idle | when a cell empties |
| For | solo dungeons, puzzle missions, story beats | overworld, ocean, frontier, star-field |

Each PC who triggers a portal owns a *private* copy. Whether **others may
enter it** is a create-time setting on the template — `instance_mode`:

- **solo** — only the owner; a follower who tries to enter is bounced at
  the threshold.
- **shared** — the owner's **followers/party** route into the owner's copy
  instead of their own. A follower already cascades through the portal with
  the leader, so the router just recognizes "this PC is following someone
  who owns a copy of this template" and sends them there — CoffeeMud's
  party-cohesion, over REALM's existing follow/party system.

A non-following stranger who walks the same portal always gets their own
copy (or is bounced, per the template's rules).

Rule of thumb: content **authored and stateful** → instance; content
**computed from position** → wilderness. And they compose — a wilderness
whose landmark coordinates are doorways into per-player instanced dungeons.

## Templates: authored or generated (one format)

A template is just **worldio area-data** — the same format `@export`,
`realm export`, and content packs already produce. It comes from any of:

- **OLC** — build the area in-game (`@dig` / `@create` / `@set`), then
  `@export` it to a template;
- a **hand-written data template** — author the JSON directly;
- a **generator** — softcode (or a data spec) that *emits* area-data at
  materialize time, optionally seeded (party level, a random seed).

All three produce the same thing — an area-data string — and feed the one
materializer (`import_objects`). A fixed dungeon clones a static template;
a procgen dungeon or a wilderness cell calls a generator that returns the
data. The materializer doesn't care which: "procgen vs. authored" is just
*who produced the string*.

**Half of this authoring flow already exists.** Building an area in OLC,
`@export`-ing it, and cloning it with fresh ids is exactly what `@export` +
`import_objects` do today (it's how the spacegame station and content packs
work). The instancing wrapper around that clone —
the `instance_template` tag, the portal-router that materializes on demand
*per PC*, the `ephemeral` flag so copies aren't persisted, and the reaper —
is now shipped in `realm/core/instances.py`. So "build → export → use as an
instanced area" is exactly the path: the same export that once produced a
single *persistent* copy now backs a repeatable, transient, self-reaping
instance.

## Persistence & reboot

Ephemeral copies are **not saved and do not survive a reboot** — only
templates persist (CoffeeMud makes the same call). A player mid-dungeon at
reboot is returned to their home (else the start room) by the load-time
reconcile — the instance's `return_room` only applies to live reaps, since
the master recording it is itself ephemeral; progress inside a single
instance is intentionally not durable. If a game needs durable instances
(a persistent player housing plot, say), that's a *different* feature —
model it as a real, persistent per-owner area, not an ephemeral copy.

## What reuses what (the payoff)

The genuinely hard part of all this — deep-copy a populated area with fresh
ids and remap every internal reference so the copy is self-consistent and
isolated — REALM **already does** in `import_objects`. Instancing and
wilderness collapse into one primitive (materialize-on-demand + reap +
transient) over machinery that already exists: `import_objects`, zones,
`SpawnerBehavior`, the tick loop, `move_through_exit`, and per-viewer
`[[...]]` descriptions. The *only* net-new kernel concepts are the three
small pieces above — and notice the deep "spatial primitive" (continuous
coordinates for free-flight ships) is **not** among them: discrete cells
are just rooms, so it stays reserved for genuinely continuous space.

## Decided

- **Tag names** — `instance_template` / `ephemeral` / `instance:<t>:<owner>`.
- **Owned by whoever triggers it** (first through a portal, or a game event
  that opens one), with a create-time **`instance_mode` = solo | shared** —
  shared lets the owner's followers/party enter the owner's copy.
- **Recreate, don't pool.** Destroy an empty copy and rebuild it next time;
  pooling is a later optimization only if cell churn gets hot.
- **Evacuate** to the instance's `return_room` if set, else the player's
  **home**.
- **One template format** — worldio area-data, produced by OLC-export, a
  hand-written template, or a generator; all feed `import_objects`.
- **Idle TTL is an attribute, not a design question** — `idle_ttl` on the
  instance-master (module default 900 s = 15 min, overridable per
  `enter_instance` call or per portal via `instance_ttl`), checked by the
  reaper each tick against `now - last_active`.

This shipped as designed: a thin convention layer over `import_objects`
plus the three small kernel bits above — `realm/core/instances.py`,
`realm/core/wilderness.py`, the `ephemeral` skip in persistence, the
evacuation guard, and the deferred-destination hook in
`realm/core/movement.py`.
