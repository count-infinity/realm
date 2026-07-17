# 032. Airlock

> Checklist item 32 — now — *interlocked on_check wards across objects, $cycle wait sequence*

**What you'll build:** A ship airlock: an inner door to the crew deck,
an outer door to the hull, and an iron rule — **both doors are never
open at once**. Try to `open` the wrong one and the interlock refuses;
the chamber's `CYCLE IN` / `CYCLE OUT` panel seals everything, runs the
pumps, and unseals the far side.

**Concepts:** a **cross-object invariant** held by `on_check` wards
(each door reads the *other* door's state and vetoes its own opening),
the mirror pattern from [tutorial 025](025_lockable_door.md) keeping
each door's two faces agreed, and a `$cycle` sequence that changes
state safely *because* raw writes bypass wards — automation as the
sanctioned path through your own interlock.

## How it works

**Why the ward CAN sit on the door this time.** Traversal wards live on
rooms (the walk's actions target rooms) — but `open` is different: it
propagates `item:on_open` **targeting the door itself**, and gated
events run the target's own `on_check` before the state changes. So
each door face carries a ward that reads the opposite door and
`block()`s the open while it stands open. The invariant is enforced at
the *command* level, symmetric from every side, with a reason the
player reads off the interlock light.

**Four faces, two doors, one truth.** Each door is a pair of exit
objects (one face per room), kept in lockstep by the 025 mirror:
`ON_OPEN`/`ON_CLOSE` hooks copy the `closed` tag onto the partner face
with raw writes (which don't re-propagate — recursion-proof). Because
the faces mirror, the interlock only needs to check **one** canonical
face of the other door; a one-line `@eval` wires every face's
`partner` (its twin) and `other` (the opposite door), plus the panel's
face lists, so no ids are copied by hand.

**The cycle is a raw-write choreography.** The panel's `$cycle in|out`
seals *all four faces* first (`add_tag` — raw writes don't fire the
mirrors and don't consult the wards, and both-closed is a legal state,
so the invariant holds at every instant), narrates the pumps, then a
`wait()` later unseals the requested door's two faces. A `cycling`
latch keeps overlapping cycles from interleaving. This is the same
lesson as the mirror itself, scaled up: **commands** are gated by
wards; **your own automation** writes state directly and is responsible
for stepping through legal states only.

## Build it

Geometry — deck, chamber, hull, both doors paired, and the panel in
the chamber:

```text
@dig Crew Deck
@teleport me = Crew Deck
@dig Airlock Chamber = inner door, inner door
inner door
@dig Hull Exterior = outer door, outer door
@create airlock panel
drop airlock panel
```

Wire everything from the chamber in one `@eval`: find both local faces,
follow their `destination`s to find the far faces, then hand out
`partner` (mirror twin), `other` (the opposite door's chamber face),
and the panel's door lists:

```text
@eval ch = here; inn = [o for o in contents(ch) if has_tag(o, 'exit') and name(o) == 'inner door'][0]; out = [o for o in contents(ch) if has_tag(o, 'exit') and name(o) == 'outer door'][0]; deck = get('#' + str(get_attr(inn, 'destination'))); hull = get('#' + str(get_attr(out, 'destination'))); inn2 = [o for o in contents(deck) if has_tag(o, 'exit') and name(o) == 'inner door'][0]; out2 = [o for o in contents(hull) if has_tag(o, 'exit') and name(o) == 'outer door'][0]; [set_attr(a, 'partner', '#' + p.id) for a, p in [(inn, inn2), (inn2, inn), (out, out2), (out2, out)]]; [set_attr(f, 'other', '#' + g.id) for f, g in [(inn, out), (inn2, out), (out, inn), (out2, inn)]]; panel = get('airlock panel'); set_attr(panel, 'inner_doors', ['#' + inn.id, '#' + inn2.id]); set_attr(panel, 'outer_doors', ['#' + out.id, '#' + out2.id]); result = 'airlock wired'
```

Every face gets the same three lines — two mirror hooks and the
interlock ward. `@set` resolves names locally, so the identical stanza
configures whichever face you're standing at; walk the loop and apply
it to all four (here: both chamber faces, then the deck face, then the
hull face):

```text
@set inner door/on_open = remove_tag(get_attr(me, 'partner'), 'closed')
@set inner door/on_close = add_tag(get_attr(me, 'partner'), 'closed')
@set inner door/on_check = block('The interlock light burns red: the other door is open.') if atype == 'item:on_open' and target == me and not has_tag(get(get_attr(me, 'other', '')), 'closed') else None
@set outer door/on_open = remove_tag(get_attr(me, 'partner'), 'closed')
@set outer door/on_close = add_tag(get_attr(me, 'partner'), 'closed')
@set outer door/on_check = block('The interlock light burns red: the other door is open.') if atype == 'item:on_open' and target == me and not has_tag(get(get_attr(me, 'other', '')), 'closed') else None
inner door
@set inner door/on_open = remove_tag(get_attr(me, 'partner'), 'closed')
@set inner door/on_close = add_tag(get_attr(me, 'partner'), 'closed')
@set inner door/on_check = block('The interlock light burns red: the other door is open.') if atype == 'item:on_open' and target == me and not has_tag(get(get_attr(me, 'other', '')), 'closed') else None
inner door
outer door
@set outer door/on_open = remove_tag(get_attr(me, 'partner'), 'closed')
@set outer door/on_close = add_tag(get_attr(me, 'partner'), 'closed')
@set outer door/on_check = block('The interlock light burns red: the other door is open.') if atype == 'item:on_open' and target == me and not has_tag(get(get_attr(me, 'other', '')), 'closed') else None
outer door
```

The panel: `cycle_time` is data; `$cycle` latches, seals all faces,
narrates, and schedules the unseal; `finish_cycle` opens the requested
door and releases the latch:

```text
@set airlock panel/cycle_time = 5
@set airlock panel/cmd_cycle = $cycle *: side = trim(arg0).lower(); pemit(enactor, 'Cycle which way? CYCLE IN or CYCLE OUT.') if side not in ('in', 'out') else (pemit(enactor, 'The pumps are already running.') if get_attr(me, 'cycling', 0) else (set_attr(me, 'cycling', 1), set_attr(me, 'goal', side), [add_tag(get(d), 'closed') for d in get_attr(me, 'inner_doors', []) + get_attr(me, 'outer_doors', [])], remit(loc(me), 'Bolts thud home; both doors seal. The pumps roar.'), wait(get_attr(me, 'cycle_time', 5), 'trigger me/finish_cycle')))
@set airlock panel/finish_cycle = doors = get_attr(me, 'inner_doors', []) if get_attr(me, 'goal') == 'in' else get_attr(me, 'outer_doors', []); [remove_tag(get(d), 'closed') for d in doors]; set_attr(me, 'cycling', 0); remit(loc(me), 'The pumps fall silent. The ' + ('inner' if get_attr(me, 'goal') == 'in' else 'outer') + ' door unseals with a hiss.')
```

Finally, put the airlock in a legal starting state — seal both from
the chamber (the mirrors close the far faces for you):

```text
close inner door
close outer door
```

## Try it

From the crew deck:

```text
open inner door     -> You open the inner door.       (outer is shut: allowed)
inner door          -> you're in the chamber
open outer door     -> The interlock light burns red: the other door is open.
cycle out           -> Bolts thud home; both doors seal. The pumps roar.
                       ...The pumps fall silent. The outer door unseals
                       with a hiss.
outer door          -> you're on the hull
```

Try `open inner door` from the deck while the outer door stands open —
red light, from a room away, because the deck face's ward reads the
same mirrored truth. Cycle back with `cycle in` from the chamber.
`@examine` any face mid-sequence: at no instant are both doors ever
untagged `closed`.

> **Caveat — co-located door faces.** The mirror hooks here copy `closed`
> onto a *named* partner. If two doors share one room (e.g. a ship airlock
> where both hatches open into the same chamber), an `ON_OPEN` fires for
> *every* door in the room and — because `ON_<EVENT>` hooks can't read the
> action's target — each door's mirror runs on every open, cross-firing.
> This demo is safe only because the two faces live in different rooms.
> For co-located faces, drive the state from a single panel with the
> **raw-write cycle** idiom (seal-all-then-open-one), which needs no target
> info; the [spaceship](164_small_spaceship.md) capstone does exactly this.

## Going further

- **Vacuum consequences** — put an `ON_ENTER` on the hull that
  `apply_effect`s suffocation on anyone without a `sealed_suit` tag;
  the [gas bomb](048_gas_bomb.md)'s exposure pattern in reverse.
- **Emergency override** — a `$override` on the panel that raw-writes
  both doors open *is* writable — the invariant is yours, so breaking
  it is a design decision with a klaxon attached (`remit` + an `act()`
  to the bridge).
- **Auto-close** — fold in the [timed door](029_timed_door.md) ticket
  pattern so an opened door seals itself after 30 seconds; airlocks
  and banks love it.
- **One-button cycle** — a `$cycle` with no argument that opens
  whichever door is currently sealed (read both states, pick the
  closed one): the panel already owns all four faces.
