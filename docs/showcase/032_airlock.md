# 032. Airlock

> Checklist item 32 ([now]): *interlocked on_check wards across objects, $cycle wait sequence*

**What you'll build:** A ship airlock with an inner door to the crew deck, an
outer door to the hull, and one iron rule: the two doors are never open at
once. Try to `open` the wrong one and the interlock refuses; the chamber's
`CYCLE IN` / `CYCLE OUT` panel seals everything, runs the pumps, and unseals
the far side for you.

**Concepts:** a cross-object invariant held by two `on_check` wards that each
read the *other* door's state and veto their own opening, the mirror pattern
from the [lockable door](025_lockable_door.md) keeping each door's two faces
in agreement, and a `$cycle` command whose [`wait()`](../reference/softcode.md#fn-wait)
sequence is allowed to change state directly because its raw writes bypass the
wards.

## How it works

An airlock is two paired doors plus a panel, wired so a plain `open` can never
leave both doors open at the same instant, while the panel's `cycle` command
is allowed to seal both and then open one. This section answers three
questions: how one door refuses to open while the other stands open, how a
door's two faces stay in agreement, and why the cycle may do what a player's
`open` may not.

### How one door vetoes the other

Opening a door propagates an `item:on_open` action that targets the door
itself, and a gated action runs the target's own `on_check` during the
permission pass, before the `closed` tag is cleared
([action phases](../design/action-phases.md)). That is the
[gift box](012_gift_box.md)'s interception point, aimed at a sibling object
instead of at the opener: each door face carries a ward that reads the
*opposite* door and calls [`block()`](../reference/softcode.md#event-data-namespace)
while that door is open. The refusal is symmetric from every side, and the
player reads the reason off the interlock light.

### How a door's two faces stay agreed

Each door is a pair of exit objects, one face in each room, and a two-way
`@dig` pairs them at creation exactly as the
[lockable door](025_lockable_door.md) describes. The mirror keeps that pair in
lockstep: [`ON_OPEN`/`ON_CLOSE`](../reference/softcode.md#lifecycle-hooks)
hooks copy the `closed` tag onto the partner face with a raw
[`add_tag`](../reference/softcode.md#fn-add_tag)/[`remove_tag`](../reference/softcode.md#fn-remove_tag)
write, which does not re-propagate, so the mirror cannot echo back and forth.
Because the two faces always agree, each ward needs to read only *one*
canonical face of the other door. A single `@eval` at build time stamps every
face's `partner` (its twin) and `other` (a chamber face of the opposite door)
and fills the panel's two face lists, so no ids are copied by hand.

### Why a hook must check its target

An [`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks) hook fires for
every object in the room, not only the one the action targeted, and the
chamber holds a face of *both* doors. So `open inner door`, typed in the
chamber, runs the outer door's `ON_OPEN` too. Each hook is handed the action's
`target`, so it mirrors only when it *is* the target:
[`if target is me:`](../reference/softcode.md#guard-on-target), an identity
check written with `is`, never `==`. Drop that guard and opening either door
from the chamber quietly unseals the far face of the *other* door, breaking
the invariant with the very hook meant to preserve it. The two wards test
`target is me` for the same reason: a witness must first establish that an
event is about *it*.

### Why the cycle may do what open may not

The panel's `$cycle in|out` seals *all four faces* first with a raw
`add_tag`, which neither fires the mirrors nor consults the wards, and
both-closed is a legal state, so the invariant holds at every instant. It
narrates the pumps, then schedules the unseal with
[`wait()`](../reference/softcode.md#fn-wait); when that fires, `finish_cycle`
clears the `closed` tag from the requested door's two faces. A `cycling` latch
keeps a second `cycle` from interleaving while the pumps run. This is the same
division the mirror draws, scaled up: a player's *commands* are gated by the
wards, while your *own automation* writes state directly and is responsible
for stepping through legal states only. Because `wait()` is in-memory, a
scheduled unseal does not survive a server reboot; a timer that must survive
uses [`expire()`](../reference/softcode.md#fn-expire) instead, as the
[gas bomb](048_gas_bomb.md) shows.

## Build it

Dig the geometry from the crew deck: the inner door pairs the deck to the
chamber, the outer door pairs the chamber to the hull, and the panel is
dropped in the chamber between them. Each two-way `@dig` names the same door on
both faces, so it creates the pair and marries them:

```text
@dig Crew Deck
@teleport me = Crew Deck
@dig Airlock Chamber = inner door, inner door
inner door
@dig Hull Exterior = outer door, outer door
@create airlock panel
drop airlock panel
```

Standing in the chamber, wire everything in one `@eval`: find the two local
faces by name, follow each `destination` to its far face, then stamp `partner`
(the mirror twin) and `other` (a chamber face of the opposite door) on all
four, and hand the panel its two face lists. `.id` is already a string, so
only the numeric `destination` needs `str()`:

```text
@eval '''
ch = here
inn = [o for o in contents(ch) if has_tag(o, 'exit') and name(o) == 'inner door'][0]
out = [o for o in contents(ch) if has_tag(o, 'exit') and name(o) == 'outer door'][0]
deck = get('#' + str(get_attr(inn, 'destination')))
hull = get('#' + str(get_attr(out, 'destination')))
inn2 = [o for o in contents(deck) if has_tag(o, 'exit') and name(o) == 'inner door'][0]
out2 = [o for o in contents(hull) if has_tag(o, 'exit') and name(o) == 'outer door'][0]
for face, twin in [(inn, inn2), (inn2, inn), (out, out2), (out2, out)]:
    set_attr(face, 'partner', '#' + twin.id)
for face, opposite in [(inn, out), (inn2, out), (out, inn), (out2, inn)]:
    set_attr(face, 'other', '#' + opposite.id)
panel = get('airlock panel')
set_attr(panel, 'inner_doors', ['#' + inn.id, '#' + inn2.id])
set_attr(panel, 'outer_doors', ['#' + out.id, '#' + out2.id])
result = 'airlock wired'
'''
```

Every face gets the same three lines: two mirror hooks that copy the `closed`
tag onto the twin, and the interlock ward that blocks an open while the other
door is not `closed`. `@set` resolves the door name locally, so configure the
two faces you are standing among first, in the chamber:

```text
@set inner door/on_open = if target is me: remove_tag(V('partner'), 'closed')
@set inner door/on_close = if target is me: add_tag(V('partner'), 'closed')
@set inner door/on_check = if atype == 'item:on_open' and target is me and not has_tag(get(V('other', '')), 'closed'): block('The interlock light burns red: the other door is open.')
@set outer door/on_open = if target is me: remove_tag(V('partner'), 'closed')
@set outer door/on_close = if target is me: add_tag(V('partner'), 'closed')
@set outer door/on_check = if atype == 'item:on_open' and target is me and not has_tag(get(V('other', '')), 'closed'): block('The interlock light burns red: the other door is open.')
```

Now walk out to each far face and apply the identical stanza: through the inner
door to the deck face, back, then out the outer door to the hull face, and
back to the chamber where you started:

```text
inner door
@set inner door/on_open = if target is me: remove_tag(V('partner'), 'closed')
@set inner door/on_close = if target is me: add_tag(V('partner'), 'closed')
@set inner door/on_check = if atype == 'item:on_open' and target is me and not has_tag(get(V('other', '')), 'closed'): block('The interlock light burns red: the other door is open.')
inner door
outer door
@set outer door/on_open = if target is me: remove_tag(V('partner'), 'closed')
@set outer door/on_close = if target is me: add_tag(V('partner'), 'closed')
@set outer door/on_check = if atype == 'item:on_open' and target is me and not has_tag(get(V('other', '')), 'closed'): block('The interlock light burns red: the other door is open.')
outer door
```

The panel keeps its delay as data, so you can retune it with `@set`:

```text
@set airlock panel/cycle_time = 5
```

The `$cycle *` command reads the direction, refuses a bad word or an already
running cycle, then latches, seals every face with a raw `add_tag`, narrates,
and schedules the unseal:

```text
@set airlock panel/cmd_cycle = '''
$cycle *:
side = trim(arg0).lower()
if side not in ('in', 'out'):
    pemit(enactor, 'Cycle which way? CYCLE IN or CYCLE OUT.')
elif V('cycling', 0):
    pemit(enactor, 'The pumps are already running.')
else:
    set_attr(me, 'cycling', 1)
    set_attr(me, 'goal', side)
    for d in V('inner_doors', []) + V('outer_doors', []):
        add_tag(get(d), 'closed')  # raw write: seals every face without firing the mirrors or consulting the wards
    remit(loc(me), 'Bolts thud home; both doors seal. The pumps roar.')
    wait(V('cycle_time', 5), 'trigger me/finish_cycle')  # schedule the unseal; the latch stays set until it runs
'''
```

When the wait fires, `finish_cycle` unseals only the requested door's two
faces (again a raw `remove_tag`) and releases the latch:

```text
@set airlock panel/finish_cycle = '''
doors = V('inner_doors', []) if V('goal') == 'in' else V('outer_doors', [])
for d in doors:
    remove_tag(get(d), 'closed')
set_attr(me, 'cycling', 0)
side = 'inner' if V('goal') == 'in' else 'outer'
remit(loc(me), f"The pumps fall silent. The {side} door unseals with a hiss.")
'''
```

Finally, seal both doors from the chamber to reach a legal starting state; the
mirror closes each far face for you, so all four end `closed`:

```text
close inner door
close outer door
```

## Try it

From the crew deck, the inner door opens because the outer is sealed, but the
chamber will not let you open the outer while the inner still stands open:

```text
> open inner door
You open the inner door.

> inner door
Airlock Chamber

> open outer door
The interlock light burns red: the other door is open.
```

The cycle is the sanctioned way across. It seals both doors, runs the pumps,
and unseals the far side after `cycle_time` seconds (the middle line arrives on
the timer):

```text
> cycle out
Bolts thud home; both doors seal. The pumps roar.
The pumps fall silent. The outer door unseals with a hiss.

> outer door
Hull Exterior
```

The invariant holds a room away, too: with the outer door open, `open inner
door` from the deck gets the same red light, because the deck face's ward reads
the same mirrored truth. Cycle back with `cycle in` from the chamber, and
`@examine` any face mid-sequence to confirm that at no instant are both doors
untagged `closed`. A face of *both* doors sits in the chamber, so opening the
inner door there also fires the outer door's `ON_OPEN`; the `target is me`
guard on each mirror is what stops that stray fire from unsealing the far side
of the untouched door.

## Going further

- **Vacuum consequences:** put an `ON_ENTER` on the hull that
  [`apply_effect`](../reference/softcode.md#fn-apply_effect)s suffocation on
  anyone without a `sealed_suit` tag, the [gas bomb](048_gas_bomb.md)'s
  exposure pattern in reverse.
- **Emergency override:** a `$override` on the panel that raw-writes both
  doors open is entirely writable, because the invariant is yours to break; do
  it with a klaxon attached ([`remit`](../reference/softcode.md#fn-remit) plus
  an [`act()`](../reference/softcode.md#fn-act) to the bridge).
- **Auto-close:** fold in the [timed door](029_timed_door.md)'s countdown so an
  opened door seals itself after thirty seconds; airlocks and banks both like
  it.
- **One-button cycle:** a `$cycle` with no argument that opens whichever door
  is currently sealed (read both states, pick the closed one), since the panel
  already owns all four faces. The [spaceship](164_small_spaceship.md) capstone
  runs a whole hull on this seal-all-then-open-one idiom.
