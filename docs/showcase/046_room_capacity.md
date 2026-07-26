# 046. Room capacity

> Checklist item 46 ([now]): *ENTER wards counting occupants*

**What you'll build:** A maintenance closet with room for two, where the
third person who tries to squeeze in is refused at the threshold, and the
count is taken live at the moment they try.

**Concepts:** an [`on_check`](../design/action-phases.md) ward on a
destination room (the `event:pre_enter` action), counting occupants with
[`contents()`](../reference/softcode.md#fn-contents) in the decision pass,
wards versus locks, and a `[[...]]` description that reports occupancy.

## How it works

The finished closet is one data attribute and one ward. Movement into a
room fires an `event:pre_enter` check on the destination *before* the mover
relocates, and that check is the room's own veto over arrivals. The ward
counts the closet's player-tagged contents and calls
[`block()`](../reference/softcode.md#event-data-namespace) once it is
already full, and the block reason is exactly what the refused walker
reads. This is the container capacity ward of the
[basic container](014_basic_container.md) lifted from `item:on_put` to room
entry: the same primitive on a bigger box.

### Why a ward and not a lock?

A lock is a static predicate about the *walker*: has the key, has the
role. Occupancy is a fact about the *room right now*, so it needs a count
taken at decision time, which is exactly what the check pass is for. The
division of labor is that locks say who may ever, and wards say whether
right now.

### What the ward keys on

The action arrives as `atype == 'event:pre_enter'` with the closet as
[`target`](../reference/softcode.md#event-data-namespace), so the ward
filters to exactly that case. It counts and blocks players only, using
[`has_tag(actor, 'player')`](../reference/softcode.md#fn-has_tag), so NPCs,
spawned props, and dropped junk neither fill the closet nor get bounced.
(Widen or narrow that deliberately: counting `npc` too would make
guard-stuffing a tactic.) At `pre_enter` time the mover has not arrived
yet, so [`contents(me)`](../reference/softcode.md#fn-contents) is the
*current* occupancy, which means a capacity of 2 blocks the third body.

### Why the atype filter is the load-bearing guard

A room hears both ends of a move: entering fires `event:pre_enter` with the
room as target, and leaving fires `event:on_leave` with that same room as
target. Both are movement actions. A ward that keyed only on "this is a
movement action" would also fire when a full closet's own occupant tries to
step *out*, and would block them, trapping everyone inside the instant the
room fills. Keying on `atype == 'event:pre_enter'` (and, defensively, on
`target is me`) is what confines the ward to arrivals and lets departures
pass untouched. Write `is`, not `==`, for that identity check.

The ward runs in the check pass, so it decides and cannot act: the
namespace has no `set_attr` and no `say`. Reactions belong in
[`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks) hooks that see the
world after the effect, which is the before/apply/after
[trio](../design/action-phases.md). The ward fires for *every* way in that
respects wards, walking and a scripted
[`move_to`](../reference/softcode.md#fn-move_to) alike, while
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj) and `@teleport`
are the deliberate force-past, since wards yield to the wizard path where a
lock would not.

## Build it

First the shell: dig the closet off the workshop, where `closet` walks in
and `out` walks back, then step inside so `here` resolves to the closet.

```text
@dig Maintenance Closet = closet, out
closet
```

The capacity is plain data, so a bigger closet is a `@set`, not a script
edit:

```text
@set here/capacity = 2
```

The ward is a `'''` heredoc block. Its steps in order: filter to an arrival
into this room, count the players already inside, then block when that
count has reached capacity. [`V('capacity', 2)`](../reference/softcode.md#fn-v)
reads the attribute (defaulting to 2), and
[`name(me)`](../reference/softcode.md#fn-name) keeps the message honest on a
renamed room:

```text
@set here/on_check = '''
if atype == 'event:pre_enter' and target is me:  # only arrivals INTO me, never a departure (event:on_leave)
    taken = len([o for o in contents(me) if has_tag(o, 'player')])  # mover hasn't arrived yet, so this is current occupancy
    if taken >= V('capacity', 2):
        block(f'There is no room. {name(me)} is packed shoulder to shoulder.')
'''
```

A living face: the `[[...]]` block in the description runs per look and
counts the players fresh each time, so it always reads the true occupancy.
The trailing `out` then walks you back to the workshop:

```text
@desc here = Mop, bucket, fuse panel. Space for two people and one grudge. [[n = len([o for o in contents(me) if has_tag(o, 'player')]); result = f"{n} of {V('capacity', 2)} spots are taken."]]
out
```

The same ward line works on every room that carries a `capacity`, so
`@set here/capacity = 6` re-rates this one without touching the ward.

## Try it

You and a friend fit, and the third bounces:

```text
> closet                       (you)
> closet                       (Kess)
> closet                       (Tam, from outside)
There is no room. Maintenance Closet is packed shoulder to shoulder.
```

Tam is still in the corridor. The moment Kess steps `out`, Tam's next try
walks right in, because the count is live and there is no bookkeeping to go
stale. A full closet never traps the people already inside: stepping `out`
fires `event:on_leave`, which the ward ignores. Inside, `look` reads the
meter:

```text
> look
Maintenance Closet
Mop, bucket, fuse panel. Space for two people and one grudge. 2 of 2 spots are taken.
```

## Going further

- **Squeeze checks:** instead of a flat refusal, let the ward pass and have
  the room's [`on_enter`](../reference/softcode.md#lifecycle-hooks) reaction
  charge a cost when it is crowded, or keep the ward but exempt anyone
  tagged `slippery`.
- **Weight, not heads:** sum
  [`get_attr(o, 'weight', 0)`](../reference/softcode.md#fn-get_attr) over the
  contents instead of counting players, for a rope bridge with a load limit
  (fail it with the [falling](047_falling.md) drop).
- **Queues:** the ward only reads, so a queue lives in the reactions around
  it. The room's `on_fail` hook fires when an arrival is bounced and can
  append the hopeful to a `waiting` list attribute, and its `on_leave`
  reaction pages the next in line when a spot opens: a nightclub door in a
  couple of attributes.
- **Vehicles and elevators:** a capacity plus a movement schedule is a
  working elevator car.
