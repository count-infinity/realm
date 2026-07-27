# 161. Travel time

> Checklist item 161 ([now]): *dead-end exit launches a timed journey, wait() progress sweep, teleport on arrival, turn-back interruption*

**What you'll build:** A long road where walking is not instant. Step onto
it and you are "on the road": progress lines tick past, and only after the
journey elapses do you arrive at the far end. Change your mind and `turn back`
to abandon the trek.

**Concepts:** a **dead-end exit** whose [`ON_FAIL`](../reference/softcode.md#lifecycle-hooks)
launches a journey (the portal pattern, [tutorial 033](033_portal_pair.md));
**journey tokens**, small owned objects that hold each traveller's clock; a
[`wait()`](../reference/softcode.md#fn-wait) **sweep** that delivers progress and
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj)s arrivals; and
interruption as leaving the road.

## How it works

The finished shape is three rooms and one clever exit. The trailhead holds a
`road` exit that leads nowhere; walking it drops you into a transit room, `The
Long Road`, alongside a small object that clocks your trip. A repeating sweep
reads those objects, nudges everyone still walking with a progress line, and
delivers anyone whose time is up to the destination. This section answers four
questions: why a dead-end exit can move you, why the clock lives on a separate
object, how one sweep serves every traveller, and how leaving the road ends the
trip.

### Why a dead-end exit can move you

Walking the `road` exit finds no room beyond it, so the engine fires the exit's
[`ON_FAIL`](../reference/softcode.md#lifecycle-hooks) hook, the same post-move
reaction a locked or dead-end exit gives any builder to work with. The road owns
both the trailhead and the transit room, so it is allowed to relocate anyone
standing in either: this is room-owner relocation, the authority a room's owner
has to move what stands in their room even without full control of it. The hook
uses that authority to [`move_to`](../reference/softcode.md#fn-move_to) the
walker into `The Long Road`.

One guard is essential. An `ON_<EVENT>` hook fires on *every* object in the
room, not only on the exit that failed, so the road's `ON_FAIL` opens with
`if target is me:` (an identity check, see
[Guard on `target`](../reference/softcode.md#guard-on-target)). For an
`event:on_fail` action, `target` is the exit that was walked, so the guard lets
the road launch a journey only when the road itself was the thwarted step. A
second dead-end exit in the same room would otherwise send its walker up the
road too.

### Why the clock lives on a separate object

A road script may not write attributes onto a player, because it does not
control one. So the hook mints a **journey token** instead: a tiny object the
road owns via [`create_obj`](../reference/softcode.md#fn-create_obj), created in
the transit room and stamped with the traveller's id, their destination, their
home, and an `eta` ([`now()`](../reference/softcode.md#fn-now) plus the travel
time). The road controls anything it owns, so it stamps the token freely with
[`set_attr`](../reference/softcode.md#fn-set_attr) and reads it back later. One
token per traveller means each person carries their own clock.

### How one sweep serves every traveller

The road schedules a [`wait()`](../reference/softcode.md#fn-wait) that runs its
`sweep` script. Each pass walks the tokens in transit: anyone whose `eta` has
arrived is [`teleport_obj`](../reference/softcode.md#fn-teleport_obj)'d to their
destination and their token destroyed, while everyone still walking gets a
progress line. The road owns the transit room, so room-owner relocation lets it
teleport a traveller standing there. If travellers remain, the sweep re-arms
another `wait()`; when the road empties, it stops by clearing its `sweeping`
flag. `sweep` runs by name off a timer, so no action is behind it and it needs
no `target` guard.

### How turn back ends the trip

`turn back` is a `$`-command on the transit room itself. It finds the token
whose `traveler` is you, moves you back to its stored home, and destroys it, so
the next sweep no longer sees you. Any other way off the road does the same: no
token, no arrival.

### The reboot caveat

These timers are in-memory, so a restart mid-journey leaves travellers on the
road with their tokens intact but the `wait` chain gone. For journeys that must
survive a reboot, drive the sweep from a `script_ticker` behavior instead (see
[tutorial 152](152_persistent_timers.md)); the tokens are already persistent.

## Build it

Dig the trailhead, the destination, and the transit room between them, stand in
the trailhead, and open the `road` exit as a dead end by unlinking it. Give the
transit room a description that points at the escape command:

```text
@dig The Trailhead
@dig The Hillfort
@dig The Long Road
@teleport me = The Trailhead
@open road = The Trailhead
@unlink road
@desc The Long Road = A rutted track winding through gorse, going on and on. TURN BACK to abandon the journey.
```

The road's data is plain single-line attributes: the failure line a bare walk
would show, the destination, the transit room, home, and the two timings. The
`goal`, `transit`, and `home` values are room names, which
[`get`](../reference/softcode.md#fn-get) resolves anywhere in the world:

```text
@set road/fail_msg = The road is long; better to set out properly.
@set road/goal = The Hillfort
@set road/transit = The Long Road
@set road/home = The Trailhead
@set road/travel_time = 6
@set road/step = 2
```

`ON_FAIL` launches the journey: move the walker into transit, mint their token
and stamp it, announce the departure, and start the sweep if it is not already
running. The `if target is me:` guard is the first line, because the hook fires
on every object in the room:

```text
@set road/on_fail = '''
if target is me:  # ON_FAIL fires on every object in the room; only the road launches
    trans = get(V('transit'))
    move_to(enactor, trans)
    tok = create_obj('travel token', tags=['journeying'], location=trans)
    set_attr(tok, 'traveler', '#' + enactor.id)
    set_attr(tok, 'goal', V('goal'))
    set_attr(tok, 'home', V('home'))
    set_attr(tok, 'eta', now() + int(V('travel_time', 6)))
    pemit(enactor, 'You shoulder your pack and set out. The fort is a long walk off.')
    remit(get(V('home')), name(enactor) + ' sets off up the road.')
    if not V('sweeping'):
        wait(int(V('step', 2)), 'trigger me/sweep')
        set_attr(me, 'sweeping', 1)
'''
```

The sweep visits every token in transit. A traveller who left the road by some
other door has their token dropped; one whose `eta` has passed is teleported to
the goal and their token destroyed; everyone else gets a progress line. It
re-arms while anyone remains and clears `sweeping` when the road empties:

```text
@set road/sweep = '''
trans = get(V('transit'))
for tok in [o for o in contents(trans) if has_tag(o, 'journeying')]:
    traveler = get(get_attr(tok, 'traveler'))
    if traveler is None or loc(traveler) is not trans:
        destroy_obj(tok)
    elif now() >= get_attr(tok, 'eta', now() + 999):
        teleport_obj(traveler, get(get_attr(tok, 'goal')))
        pemit(traveler, 'The walls of the Hillfort rise at last; you have arrived.')
        remit(get(get_attr(tok, 'goal')), name(traveler) + ' trudges in through the gate, road-dusty.')
        destroy_obj(tok)
    else:
        pemit(traveler, 'The road unrolls on beneath your boots...')
if [o for o in contents(trans) if has_tag(o, 'journeying')]:
    wait(int(V('step', 2)), 'trigger me/sweep')
else:
    set_attr(me, 'sweeping', 0)
'''
```

The escape hatch is a `$turn back` command on the transit room. It matches the
token stamped with your id, walks you back to its stored home, and destroys it:

```text
@set The Long Road/cmd_turnback = '''
$turn back:
mine = [o for o in contents(here) if has_tag(o, 'journeying') and get_attr(o, 'traveler') == '#' + enactor.id]
if not mine:
    pemit(enactor, 'You are not on the road.')
else:
    move_to(enactor, get(get_attr(mine[0], 'home')))
    destroy_obj(mine[0])
    pemit(enactor, 'You give it up and trudge back the way you came.')
'''
```

## Try it

```text
> road
You shoulder your pack and set out. The fort is a long walk off.

The Long Road
-------------
A rutted track winding through gorse, going on and on. TURN BACK to abandon the journey.
```

You are on `The Long Road` now, and a `travel token` clocks your trip. Each
sweep beat, while the `eta` is still in the future, nudges you along:

```text
(a sweep beat)
The road unrolls on beneath your boots...

(the beat your eta passes)
The walls of the Hillfort rise at last; you have arrived.
```

Walk it again and `turn back` before the timer elapses, and you trudge home to
the trailhead while the sweep forgets you:

```text
> turn back
You give it up and trudge back the way you came.
```

Send two people up the road at once and one sweep serves both, each on their own
token clock. `@examine` a token mid-journey to watch its `eta` count down.

## Going further

- **Distance as data:** `travel_time` already lives on the exit, so a long road
  and a short lane share every line of this code at different speeds.
- **Perils on the way:** the sweep visits everyone in transit, so roll an ambush
  ([tutorial 043](043_hazard_room.md)) on a bad beat, or a chance to find
  something in the ditch.
- **Reboot-proof journeys:** swap the `wait()` chain for a `script_ticker` on
  the transit room ([tutorial 152](152_persistent_timers.md)); the tokens
  persist, so travel survives a restart.
- **Faster on a mount:** a [mounted](158_mounts.md) traveller could carry a
  shorter `travel_time`, read from a `mounted` marker when the token is minted.
