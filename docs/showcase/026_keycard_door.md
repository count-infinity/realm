# 026. Keycard Door

> Checklist item 26 ([now]): *on_check wards reading carried items' attrs*

**What you'll build:** A security door whose scanner checks the clearance
level printed on the card you are carrying, not who you are. A level-1
visitor badge bounces off a level-3 door, but hand your white keycard to
the intern and the intern walks in while you do not.

**Concepts:** an [`on_check`](../design/action-phases.md) ward on the
movement path (the destination's own `event:pre_enter` veto), scanning
[`contents(actor)`](../reference/softcode.md#fn-contents) for item
attributes, numeric refusal text, and how this differs from the engine's
`key_id`/`unlocks` lock (the [lockable door](025_lockable_door.md)), which
tests identity, not level.

## How it works

A clearance scanner is a ward that reads the arriving player's pockets.
When someone tries to enter the lab, the door sweeps whatever they carry,
takes the highest `clearance` number printed on any of it, and refuses the
crossing when that number falls short. Nothing is ever locked or unlocked,
because the ward re-decides at every crossing from data it reads live. This
section answers three questions: how a clearance scanner differs from a
plastic key, where the ward has to live to fire at all, and what the scan
itself is allowed to do.

### How a clearance scanner differs from a plastic key

The engine already ships a plastic key. Give a door a `key_id`, give a card
an `unlocks` set to the same value, and `use card on door` toggles the
door's `locked` tag, exactly the [lockable door](025_lockable_door.md)'s
brass key in card form. That is an identity test: the card either names
this one lock or it does not, and once the door is unlocked it stays
unlocked for everyone until someone locks it again. A clearance scanner is
different in two ways. It compares a number carried as data on the card
against a number on the door, so any card of high enough level works,
including one minted years after the door was built. And it re-decides at
every crossing, so there is no unlocked state left behind for the next
person to walk through.

### Where the ward has to live

A walk fires two gated actions: `event:on_leave` targeting the room you are
leaving, then `event:pre_enter` targeting the room you are entering.
Softcode `on_check` wards run only on an action's participants, the actor
and the target room, never on bystanders.
An `on_check` set on the exit object itself therefore never fires for a
traversal, because the exit is only a bystander in those actions. So the
scanner goes on the secure room, whose `pre_enter` it is. That placement is
also the more honest security model, because `pre_enter` fires for walk-ins
and softcode teleports alike, so the ward guards every way in. Key it to
`atype == 'event:pre_enter'` so it scans arrivals only and never traps
anyone trying to leave.

### What the scan is allowed to do

An `on_check` ward runs in a read-only namespace, so it can `block()` but
never mutate. Reads are open, though, so it may sweep the arriving actor's
inventory. The one expression that does the work is:

```text
max([int(get_attr(o, 'clearance', 0)) for o in contents(actor)] + [0])
```

[`contents(actor)`](../reference/softcode.md#fn-contents) is everything the
walker carries, [`get_attr(o, 'clearance', 0)`](../reference/softcode.md#fn-get_attr)
reads each item's printed level (unmarked items count as 0), and the
trailing `+ [0]` gives `max()` a floor to return when the walker is
empty-handed. Your best credential is what counts, and the refusal quotes
the number back, because a scanner that says your best credential reads
level 1 tells the player exactly what to go and find.

## Build it

Dig the hallway and the lab, joined by a paired door, and stand in the
hallway. A two-way `@dig` stamps each face as the other's partner, so the
return trip is already wired:

```text
@dig Records Hallway
@teleport me = Records Hallway
@dig The Clean Lab = security door, security door
```

Cut two cards. `@create` leaves each one in your hand, which is exactly
where the scanner will look, and the printed clearance level is just an
attribute:

```text
@create white keycard
@set white keycard/clearance = 3
@create visitor badge
@set visitor badge/clearance = 1
```

Walk in while nothing is warded yet, then arm the room. The ward is a
[multi-line block](../guides/world-management.md#multi-line-input-heredocs)
read top to bottom: take the walker's best clearance, read the room's
threshold with [`V`](../reference/softcode.md#fn-v), and `block()` the
crossing when the best falls short, naming both numbers. The
`atype == 'event:pre_enter'` guard scans arrivals only, so nobody is ever
trapped inside, and `min_clearance` keeps the threshold as plain data the
refusal reads back. The last `security door` walks you home to the hallway:

```text
security door
@set here/on_check = '''
best = max([int(get_attr(o, 'clearance', 0)) for o in contents(actor)] + [0])
need = int(V('min_clearance', 3))
if atype == 'event:pre_enter' and best < need:  # gate arrivals only; on_leave targets this room too and must stay free
    block(f'The scanner strobes red: CLEARANCE {need} REQUIRED. Your best credential reads level {best}.')
'''
@set here/min_clearance = 3
security door
```

The scanner has no favorites: drop your cards and the door refuses you, its
own builder.

## Try it

Have a cardless friend, Ina, try the door, then start handing cards around.
Ina's commands are marked; the `give` lines are yours:

```text
> security door                     (Ina, empty-handed)
  The scanner strobes red: CLEARANCE 3 REQUIRED. Your best credential reads level 0.

> give visitor badge to Ina
> security door                     (Ina, level-1 badge)
  The scanner strobes red: CLEARANCE 3 REQUIRED. Your best credential reads level 1.

> give white keycard to Ina
> security door                     (Ina, now carrying level 3)
  The Clean Lab
```

Now walk her back out and take the card away again:

```text
> security door                     (Ina, leaving is free)
  Records Hallway

> give white keycard to Bob
> security door                     (Ina, down to the badge again)
  The scanner strobes red: CLEARANCE 3 REQUIRED. Your best credential reads level 1.
```

The whole point is in those last two lines: the moment the white card
changes hands, so does the access. Nothing was locked or unlocked in
between, because the ward re-reads the world at every crossing. A softcode
teleport is caught by the same ward, since
[`move_to`](../reference/softcode.md#fn-move_to) fires `pre_enter` too;
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj) is the wizard
tunnel that skips wards, as always.

## Engine gaps

- The capability audit phrases this as an exit `on_check` ward, but a ward
  on the exit object never fires for a traversal: the gating actions target
  the rooms, and the bystander pass runs behaviors only, not softcode
  `on_check`. The room-side ward keyed by `atype` (or by `adata('exit')`
  when you need to single out one door among several) covers everything the
  audit intended. Noted for the integrator.

## Going further

- **Gate one door among several.** This lab has a single entrance, so the
  room-wide ward is right. For a room with public and secure exits, key the
  ward on the door instead with `adata('exit') == get('security door')`,
  because a walk carries the exit it used in its
  [event data](../reference/softcode.md#event-data-namespace).
- **Badge out too.** Add a second clause on the hallway keyed to
  `adata('exit')`, so the lab demands a card in both directions. Now a card
  dropped inside is a real problem.
- **Audit trail.** A ward cannot write, but the door still propagates, so
  put an [`ON_ENTER`](../reference/softcode.md#lifecycle-hooks) on the lab
  that records each visitor:
  `set_attr(me, 'visit_log', V('visit_log', []) + [name(enactor)])`. The
  decision lives in the ward and the bookkeeping in the reaction, which is
  the whole `on_check` contract. (Writes go through
  [`set_attr`](../reference/softcode.md#fn-set_attr) and
  [`name`](../reference/softcode.md#fn-name); a ward could not do this even
  if it wanted to.)
- **Revocation.** Set a stolen card's `clearance` to 0 with one `@set`. No
  locksmith and no new door, because access is the attribute.
