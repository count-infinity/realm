# 046. Room capacity

> Checklist item 46 — [now] — *ENTER wards counting occupants*

**What you'll build:** A maintenance closet with room for two: the
third person who tries to squeeze in is refused at the threshold, with
the count done live at the moment they try.

**Concepts:** `on_check` wards on the destination (`event:pre_enter`),
counting occupants with `contents()` in the decision pass, wards vs
locks, `[[...]]` descs reporting occupancy.

## How it works

Movement into a room fires an `event:pre_enter` check at the
destination *before* the mover relocates — the destination's own
event-veto. A one-line `on_check` on the room counts its player-tagged
contents and `block()`s when the closet is full; the block reason is
what the refused walker reads. This is the container capacity ward
([tutorial 014](014_basic_container.md)) lifted from `item:on_put` to
room entry — same primitive, bigger box.

Why a ward and not a lock? A **lock** is a static predicate about the
*walker* (has the key, has the role). Occupancy is a fact about the
*room right now* — it needs a count at decision time, which is exactly
what the check pass exists for. The division of labor: locks say *who
may ever*, wards say *whether right now*.

Details that matter:

- The ward triggers only on `atype == 'event:pre_enter'`, so looks,
  says, and other actions targeting the room sail past it.
- It counts and blocks **players** (`has_tag(actor, 'player')`); NPCs,
  spawned props, and dropped junk neither fill the closet nor get
  bounced. Widen or narrow deliberately — counting `npc` too makes
  guard-stuffing a tactic.
- At `pre_enter` time the mover hasn't arrived, so `contents(me)` is
  the *current* occupancy — a capacity of 2 blocks the third body.
- `on_check` runs in a read-only namespace (it decides, it can't act),
  and it fires for *every* way in that respects wards — walking and
  scripted `move_to` alike. `teleport_obj` / `@teleport` are the
  deliberate force-past (wards yield to the wizard path; locks
  wouldn't).

## Build it

```text
@dig Maintenance Closet = closet, out
closet
@set here/capacity = 2
@set here/on_check = block(f'There is no room. {name(me)} is packed shoulder to shoulder.') if atype == 'event:pre_enter' and has_atag('movement') and has_tag(actor, 'player') and len([o for o in contents(me) if has_tag(o, 'player')]) >= V('capacity', 2) else None
@desc here = Mop, bucket, fuse panel. Space for two people and one grudge. [[n = len([o for o in contents(me) if has_tag(o, 'player')]); result = f"{n} of {V('capacity', 2)} spots are taken."]]
out
```

Capacity is an attribute, so `@set here/capacity = 6` re-rates the
room without touching the ward — and the same ward line works on every
room that carries a `capacity`.

## Try it

You and a friend fit; the third bounces:

```text
closet                       (you)
closet                       (Kess)
closet                       (Tam, from outside)
  There is no room. Maintenance Closet is packed shoulder to shoulder.
```

Tam is still in the corridor. The moment Kess steps `out`, Tam's next
try walks right in — the count is live, no bookkeeping to go stale.
Inside, `look` reads the meter: `2 of 2 spots are taken.`

## Going further

- **Squeeze checks:** instead of a flat refusal, let the ward pass and
  have the room's `on_enter` charge a cost when it's crowded — or
  keep the ward but exempt `has_tag(actor, 'slippery')`.
- **Weight, not heads:** sum `get_attr(o, 'weight', 0)` over contents
  instead of counting players — a rope bridge with a load limit
  (fail it with [tutorial 047](047_falling.md)'s drop).
- **Queues:** when the ward blocks, it could also note the hopeful in
  a `waiting` list attribute that the room's `on_leave` pages when a
  spot opens — a nightclub door in three attributes.
- **Vehicles and elevators:** capacity plus a movement schedule (the
  ferry of tutorial 07) is a working elevator car.
