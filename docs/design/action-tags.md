# Action Category Tags & Movement Semantics

Two related pieces of the kernel: the **category-tag vocabulary** every
propagated action carries, and the **movement primitives** that are the
biggest consumer of it. Canonical source: `realm/core/action_tags.py`.

## Category tags — the flag-mask vocabulary

Every `Action` carries a set of **category** tags. A ward blocks by
category, never by enumerating specific action types:

```
@set here/on_check = block('The binding holds you.') if has_atag('movement') else None
```

That one line stops walking, fleeing, following, **and** a cast-teleport —
none of which the ward names. It's CoffeeMUD's `CMMsg` flag-mask model
(`MASK_MOVE`, `MASK_MAGIC`…) in REALM's string-tag form; `has_atag(cat)` is
`msg.sourceMajor(MASK_…)`.

Two tiers, honestly separated (`realm/core/action_tags.py`):

**Kernel-guaranteed** (`CORE_CATEGORIES`) — every one of these IS emitted by
engine-fired events, so a ward can rely on them:

| Tag | Meaning | Typical ward |
|---|---|---|
| `movement` | any relocation of a body | a Bound / rooted effect |
| `hostile` | an aggressive act | a peace / sanctuary ward |
| `visual` | perceived by sight | blindness, darkness |
| `sound` | perceived by hearing | silence, deafness |
| `scripted` | originated in softcode | loop/depth accounting |
| `failure` | a thwarted attempt (paired with its base category) | — |

**Reserved game-layer names** (`RESERVED_CATEGORIES`) — conventional
spellings the kernel itself never emits (a hard-SF game has no "magic";
that's genre, not engine). They exist so packs converge on one spelling:

| Tag | Meaning | Typical ward |
|---|---|---|
| `magic` | magical/supernatural causation | an anti-magic field |
| `forced` | against the target's will | knockback, compel |

A **game adds its own** categories freely (`fire`, `holy`, `poison`…) —
`has_atag()` reads them identically. Keep the *core* set small and
universal; game-specific categories belong in a content pack, not here.

**Sub-kinds live in `adata`, not in more tags.** A movement action with an
`exit` in its `adata` is a **traversal** (a walk); its absence means
**direct placement** (teleport/summon/knockback). So "block teleports but
allow walking" is `has_atag('movement') and not adata('exit')` — no bespoke
`teleport` tag.

Category tags are distinct from **object** tags (`room`/`exit`/`player`):
same `has_tag` plumbing, different vocabulary — object tags say *what a
thing is*, category tags say *what an action is*.

## Movement primitives — two orthogonal axes

Movement is where locks + events + terrain + followers + messaging all
converge (it's the complex part of every MUD). REALM keeps it composable by
splitting it along **two orthogonal axes**, not a pile of ad-hoc functions:

| | **Checked** (wards / locks / events fire) | **Forced** (bypass gates) |
|---|---|---|
| **Traversal** (via an exit) | `move_through_exit` — walk, flee, a train/vehicle | shove through a locked exit |
| **Direct placement** (no exit) | `move_to` — teleport, summon, knockback | `teleport_obj` (wizard/admin) |

- **`move_to`** is *direct placement with checks* — not "a teleport" per se
  (teleport is just its commonest use). Its baked-in sequence is the
  `move_and_slide` of REALM: a `movement`-tagged **leave** veto (origin/mover
  may block) → destination **ENTER + TELEPORT locks** → a `movement`-tagged
  **pre-enter** veto (the *destination's* event-veto, which a static lock
  can't express, mirroring Evennia's `at_pre_object_receive` / CoffeeMUD's
  destination `okMessage`) → relocate → informational `on_enter`.
- **`move_through_exit`** is traversal — the same core movement plus an exit
  preamble (exit lock, closed-door, skill-gate, direction) and the follower
  cascade. Its `destination` may be deferred — an exit with a registered
  `dest_resolver` materializes the room beyond (a wilderness cell, an
  instance copy) only after the origin-side gates pass; see
  ephemeral-rooms.md.
- **`teleport_obj`** is now a thin alias for `move_to(force=True)` — the
  wizard/admin path.

### Who may relocate whom — `may_relocate`

Relocation authority is *broader* than control, matching PennMUSH's
`tport_control_ok`: a room's **owner** may teleport/shove around what stands
in their room, without being able to `@set` or `@destroy` it. So movement
gates on `may_relocate(mover, target)` (not `controls`):

1. `controls(mover, target)` — you own the target, or you're admin.
2. You own the room the target is in *and* it isn't **`anchored`** (Penn's
   `HEAVY` opt-out; the object's own controller and admins still move it).

The rule-2 check requires the room to be **owned** — for an unowned world
room, `controls` would fire the world-trusts-world rule and let any
co-located object move occupants (a confused-deputy hole). Requiring
`loc.owner` means only genuine ownership / admin / owner-delegation counts.
This reaches both the softcode surface (`move_to`/`teleport_obj`/
`enter_instance`/`enter_wilderness`) and the OLC `@teleport` command.

**The destination side** (Penn's `tport_dest_ok`) is symmetric: `move_to`'s
optional `mover` names who's performing a third-party relocation, and its
ENTER/TELEPORT locks **yield** when the mover is ADMIN+ or genuinely
controls an *owned* destination — you can stuff things into your own locked
room, but not someone else's. `@teleport` now routes through
`move_to(force=True, mover=you)`, so it honors those locks (and fires
`on_enter`) instead of the old raw `location =` set — one relocation core,
no bypass path.

### `force` — what it does and doesn't bypass (unified)

`move_to` is the single relocation verb; `force` is a flag on it. It is
carefully *not* an all-powerful override — three distinct layers, and
`force` only touches one:

| Layer | What it is | Bypassed by `force`? |
|---|---|---|
| **Authority** | you must *control* the target (or, unforced, be the enactor) | **never** |
| **Locks** (ENTER, TELEPORT) | the destination's static gates | **no** — only elevated roles bypass a lock (GOD bypasses all; ADMIN all but CONTROL on god-owned objects), in `check_lock` |
| **Wards** (on_check leave / pre-enter vetoes) | category blocks like a Bound field | **yes** — this is the whole point |

So a wizard's `teleport_obj` tunnels past a Bound ward but **still honors a
destination's teleport lock** — the "no teleporting in here" capability is
preserved, because it lives on the *lock* layer, not the *ward* layer. A
forced arrival still fires the informational `on_enter` (skip the gates,
keep the notification).

This also *fixed an inversion*: before the merge, only the raw
`teleport_obj` checked the teleport lock while the game `move_to` didn't.
Now the game path (`move_to`, a cast-teleport) honors it and `force` is the
explicit override — the right way round.

**Both paths run the destination ward.** `move_through_exit` and `move_to`
fire the same `event:pre_enter` on the destination before relocating (via a
shared helper), so a warded sanctum stops walk-ins and teleports alike — one
choke point, like Evennia's `at_pre_object_receive`. A ward can still
distinguish them: a walk carries `adata('exit')`, a teleport doesn't.

**Deliberate remaining asymmetries** (traversal vs placement, documented in
each docstring): the in_combat/unconscious gates and the follower cascade
apply only to traversal — walking is embodied travel; a teleport is the
spell's problem — and the TELEPORT lock applies only to direct placement.
The full exit preamble (exit-lock / closed / skill-gate) is traversal-only
by construction.
