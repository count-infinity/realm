# 026. Keycard Door

> Checklist item 26 — now — *on_check wards reading carried items' attrs*

**What you'll build:** A security door whose scanner checks the
**clearance level printed on the card you're carrying** — not who you
are. A level-1 visitor badge bounces off a level-3 door; hand your
white keycard to the intern and *the intern* gets in while *you* don't.

**Concepts:** `on_check` wards on the movement path, `event:pre_enter`
(the destination's own veto), scanning `contents(actor)` for item
attributes, numeric refusal text — and how this differs from the
engine's `key_id`/`unlocks` lock, which tests *identity*, not *level*.

## How it works

**Two kinds of "keycard."** The engine already ships one: give a door
`key_id` and a card `unlocks` with the same value and `use card on
door` toggles its lock — a *physical* key that happens to be plastic.
That lock is an identity test: the card either names this lock or it
doesn't, and once the door is unlocked it's unlocked *for everyone*
until someone locks it again. A clearance scanner is different in both
ways: it compares a **number carried as data on the card** against a
number on the door, and it re-decides **at every crossing** — there is
no unlocked state to leave behind you, and any card of high enough
level works, including one issued years after the door was built.

**Where the ward lives.** A walk fires two gated actions: `event:
on_leave` targeting the origin room, then `event:pre_enter` targeting
the destination — and softcode `on_check` wards run on an action's
*participants* (the actor, the target room), not on bystanders. An
`on_check` set on the **exit itself never fires for traversal** (the
exit is only a bystander in those actions) — so the scanner goes on
the **secure room**, whose `pre_enter` it is. That placement is also
the more honest security model: `pre_enter` fires for walk-ins *and*
softcode teleports alike, so the ward guards every way in, keyed by
`atype == 'event:pre_enter'` so it never interferes with people
*leaving*.

**The scan is a read.** Ward code runs in the read-only check
namespace — it can `block()` but not mutate — and reads are open, so
it may sweep the arriving actor's inventory:

```text
max([int(get_attr(o, 'clearance', 0)) for o in contents(actor)] + [0])
```

Your *best* credential is what counts, unmarked items count as 0, and
the `+ [0]` keeps `max()` happy for the empty-handed. The refusal text
quotes the number back — a scanner that says *"your best credential
reads level 1"* teaches the player what to go looking for.

## Build it

Dig the hallway and the lab behind a paired door, and cut two cards —
`@create` leaves them in your hand, which is where the scanner looks:

```text
@dig Records Hallway
@teleport me = Records Hallway
@dig The Clean Lab = security door, security door
@create white keycard
@set white keycard/clearance = 3
@create visitor badge
@set visitor badge/clearance = 1
```

Walk in (nothing is warded yet) and arm the room. The threshold is
data on the room (`min_clearance`), the ward quotes both numbers, and
the `atype` guard makes it a one-way check — arrivals only:

```text
security door
@set here/on_check = best = max([int(get_attr(o, 'clearance', 0)) for o in contents(actor)] + [0]); block('The scanner strobes red: CLEARANCE 3 REQUIRED. Your best credential reads level ' + str(best) + '.') if atype == 'event:pre_enter' and best < int(get_attr(me, 'min_clearance', 3)) else None
@set here/min_clearance = 3
security door
```

That last `security door` walks you back out — leaving is free, and
you're holding the level-3 card anyway. The scanner has no favorites:
drop your cards and the door refuses *you*, its builder.

## Try it

Have a cardless friend try the door, then start handing cards around:

```text
(friend) security door   -> The scanner strobes red: CLEARANCE 3 REQUIRED.
                            Your best credential reads level 0.
give visitor badge to Ina
(friend) security door   -> ...reads level 1.  (still not enough)
give white keycard to Ina
(friend) security door   -> she's in.
(friend) security door   -> and back out (exits are free).
(friend) give white keycard to Bob
(friend) security door   -> ...reads level 1.  (access followed the card)
```

The whole point in two lines: the moment the white card changes hands,
so does the access. Nothing was locked or unlocked in between — the
ward re-reads the world at every crossing. Softcode teleports are
caught by the same ward (`pre_enter` fires for `move_to` too);
`teleport_obj` is the wizard tunnel that skips wards, as always.

## Engine gaps

- The capability audit phrases this as an "exit `on_check` ward", but a
  ward on the exit object never fires for traversal — the gating
  actions target the rooms, and the bystander pass runs behaviors only,
  not softcode `on_check`. The room-side ward keyed by `atype` (or
  `adata('exit')` when you need to gate one door among several) covers
  everything the audit intended; noted for the integrator.

## Going further

- **Gate one door among several** — this lab has one entrance, so the
  room-wide ward is right. For a room with public *and* secure exits,
  key the ward on the door: `adata('exit') == get('security door')`
  (movement actions carry the exit in their payload).
- **Badge-out too** — add a second clause on the *hallway* keyed to
  `adata('exit')`, and the lab needs a card in both directions. Now a
  dropped card inside is a story.
- **Audit trail** — wards can't write, but the door still propagates:
  put an `ON_ENTER` on the lab that appends `name(enactor)` to a
  `visit_log` list attribute. Decision in the ward, bookkeeping in the
  reaction — that split is the `on_check` contract.
- **Revocation** — set the stolen card's `clearance` to 0. No
  locksmith, no new door: access *is* the attribute.
