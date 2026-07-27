# 154. Elevator

> Checklist item 154 ([now]): *moving-room illusion, exit relinking, door-state connections, one shared eval_attr routine*

**What you'll build:** A two-floor elevator. The car is a room that never
actually moves: press a button inside, or thumb a CALL button on a landing, and
the car's door *relinks* to your floor while the far landings seal shut. A bell
dings, the doors part, and you step out somewhere new. The whole illusion is
exits changing where they point.

**Concepts:** an exit's `destination` is just data you can rewrite
([tutorial 033](033_portal_pair.md)); the **`closed` door-state tag**
([tutorial 025](025_lockable_door.md)) standing in for "the car isn't here"; and
one **shared routine** (`serve`) that both the in-car panel and the landing
buttons call with [`eval_attr`](../reference/softcode.md#fn-eval_attr), so the
moving logic lives in exactly one place.

## How it works

The finished machine is three rooms and a handful of exits, and it hangs together
on one trick: the car never leaves. This section answers three questions, which
is the order a builder meets them in: what actually moves when you "ride" the
elevator, where the move-the-car logic lives so it is written once, and how a
landing knows the car is not currently at its floor.

### What moves when you ride?

The car is a fixed room with one exit, `doors`, whose `destination` names the
floor it currently opens onto. Each landing has an `elevator` exit that always points *into* the
car. "Calling the car to floor 2" is two writes: relink `doors` to point at floor
2, and drop the `closed` tag from floor 2's `elevator` while adding it to every
other floor's. Nobody teleports; the car sits still and the doors report a
different floor from one call to the next, which is exactly what a real elevator's
doors do.

### Where does the moving logic live?

The move-the-car logic is a `serve` attribute on the car. Give it a target
floor's room id and it relinks `doors`, opens that floor, seals the rest, and
narrates. The in-car `$press N` and each landing's `$call` are thin shells that
resolve a target floor and hand it to `serve` via
[`eval_attr`](../reference/softcode.md#fn-eval_attr), so the logic is written
**once**.

`eval_attr` is a subroutine call, not Penn's `u()` (which would swap the executor
to the object holding the attribute). It runs with the caller's authority and
leaves the executor unchanged, so inside `serve` the executor is still the button
that called it. Every button is builder-owned, so through ownership it controls
the world-built car and landings and may rewrite their doors and seals. Because
the executor is the caller and never the attribute's object, a shared routine
resolves its own subjects by id from the arguments it was handed rather than from
`me`.

### How does a landing know the car is elsewhere?

A sealed `elevator` exit carries the engine's `closed` tag. Walking into a closed
exit is refused with `The elevator is closed.` before any move happens, which is
the whole "the car isn't at your floor" story. Calling the car lifts the tag on
your floor and lowers it on the others. This is door state, not a lock: no
permission is checked, the exit simply reports itself shut. See
[tutorial 025](025_lockable_door.md) for the `closed` tag on its own, and
[tutorial 032](032_airlock.md) for an interlock that never opens two doors at
once.

## Build it

Dig the two floors and the car, then wire the exits: the car's `doors` and each
landing's `elevator`. Each `@open` creates its exit in the room you are standing
in, so the teleports put you where each exit belongs before you open it.

```text
@dig The Lobby
@teleport me = The Lobby
@dig The Mezzanine
@teleport me = The Lobby
@dig The Elevator Car
@teleport me = The Elevator Car
@open doors = The Lobby
@teleport me = The Lobby
@open elevator = The Elevator Car
@teleport me = The Mezzanine
@open elevator = The Elevator Car
```

Give the car its memory: the ordered `stops` list of floor ids, and a handle to
its own `doors` exit stored as an id so `serve` can find it again. `stops` is a
plain data list, so it stays a single-line write. The `@eval` block runs once, as
you, to compute the ids while you stand in the car, storing them with
[`set_attr`](../reference/softcode.md#fn-set_attr):

```text
@teleport me = The Elevator Car
@eval '''
car = here
lob = get('The Lobby')
mez = get('The Mezzanine')
set_attr(car, 'stops', [lob.id, mez.id])
doors = [e for e in contents(car) if has_tag(e, 'exit') and name(e) == 'doors'][0]
set_attr(car, 'doors', '#' + doors.id)
'''
```

The one routine that moves the car. `arg0` is the target floor's room id and
`arg1` the car's id; it rewrites the `doors` exit's `destination`, then walks
every stop, opening the target with
[`remove_tag`](../reference/softcode.md#fn-remove_tag) and sealing the rest with
[`add_tag`](../reference/softcode.md#fn-add_tag), announcing each floor with
[`remit`](../reference/softcode.md#fn-remit):

```text
@set The Elevator Car/serve = '''
car = get('#' + str(arg1))
doors = get(get_attr(car, 'doors'))
set_attr(doors, 'destination', arg0)
for fid in get_attr(car, 'stops'):
    floor = get('#' + str(fid))
    # each landing's shaft door; there is exactly one 'elevator' exit per floor
    shaft = [e for e in contents(floor) if has_tag(e, 'exit') and name(e) == 'elevator'][0]
    if str(fid) == str(arg0):
        remove_tag(shaft, 'closed')
        remit(floor, 'A bell chimes; the elevator doors part.')
    else:
        add_tag(shaft, 'closed')
        remit(floor, 'The elevator doors slide shut and it departs.')
remit(car, 'The car glides to a stop.')
'''
```

The in-car panel. `$press N` reads the stops list, refuses a floor out of range,
and otherwise hands that stop's id to `serve`. `car = here` because the panel
rides inside the car, so the presser's room *is* the car:

```text
@create control panel
@desc control panel = Two buttons: PRESS 1 (Lobby), PRESS 2 (Mezzanine).
drop control panel
@set control panel/cmd_press = '''
$press *:
car = here
n = int(trim(arg0))
stops = get_attr(car, 'stops')
if n < 1 or n > len(stops):
    pemit(enactor, 'No such floor.')
else:
    pemit(enactor, 'You press ' + str(n) + '.')
    eval_attr(car, 'serve', str(stops[n - 1]), car.id)
'''
```

A CALL button on each landing. `here` is the landing the presser is standing in,
so "call the car here" is `serve(here.id)`. The button is a `$`-command
([`pemit`](../reference/softcode.md#fn-pemit) speaks only to the presser), and a
`$`-command fires only on the object whose pattern matched, so it needs no
`target` guard the way a room-wide `ON_<EVENT>` hook would:

```text
@teleport me = The Lobby
@create call button
@desc call button = A brass CALL button, worn bright with use.
drop call button
@set call button/cmd_call = '''
$call:
car = get('The Elevator Car')
pemit(enactor, 'You thumb the call button.')
eval_attr(car, 'serve', here.id, car.id)
'''
```

The Mezzanine gets an identical button:

```text
@teleport me = The Mezzanine
@create call button
@desc call button = A brass CALL button, worn bright with use.
drop call button
@set call button/cmd_call = '''
$call:
car = get('The Elevator Car')
pemit(enactor, 'You thumb the call button.')
eval_attr(car, 'serve', here.id, car.id)
'''
```

Park the car at the Lobby to start by sealing the Mezzanine landing. (The Lobby's
`elevator` exit was never closed, so the car begins open there.)

```text
@teleport me = The Elevator Car
@eval '''
mez = get('The Mezzanine')
ex = [e for e in contents(mez) if has_tag(e, 'exit') and name(e) == 'elevator'][0]
add_tag(ex, 'closed')
'''
@teleport me = The Lobby
```

## Try it

From the Lobby, where the car is parked:

```text
> elevator
You step into The Elevator Car.

> press 2
You press 2.
The car glides to a stop.

> doors
You step out onto The Mezzanine.
```

Now the car sits at the Mezzanine. A friend still in the Lobby finds the shaft
sealed until they call it back:

```text
> elevator
The elevator is closed.

> call
You thumb the call button.
A bell chimes; the elevator doors part.

> elevator
You step into The Elevator Car.
```

Run `@examine` on a landing's `elevator` exit mid-ride to see the state directly:
it carries the `closed` tag exactly when the car is elsewhere, and the car's
`doors` exit shows a `destination` attribute that always names the floor the car
is currently serving.

## Going further

- **More floors:** append each new landing's room id to the car's `stops` and
  give it an `elevator` exit. `serve` already walks the whole list, so nothing
  else changes.
- **A queue:** stash pressed floors in a `queue` attribute and give the car a
  `script_ticker` ([tutorial 036](036_weather_system.md)) that `serve`s the next
  one each tick, so the car visits floors in order instead of jumping between
  them.
- **Between-floors danger:** while `serve` runs, seal *all* landings for a tick
  before opening the target, and hang an [airlock](032_airlock.md) style
  interlock so `open doors` is refused while the car is moving.
- **An out-of-order light:** a `broken` tag the panel checks first, refusing
  service with a flavor line, so maintenance becomes content.
