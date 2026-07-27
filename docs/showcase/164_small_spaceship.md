# 164. Small spaceship

> Checklist item 164 ([now]): *multi-room vehicle-as-room, airlock interlock cycle, fuel-gated launch, docking by exit relink; the chapter capstone*

**What you'll build:** A little ship you can fly between docking bays. It
has an interior, a cockpit and an airlock, with a proper cycle: the airlock
never lets both doors stand open at once, because the outer one faces vacuum
in flight. Cycle through, seal up, `launch`, `fly` to another berth, and the
ship docks at the new site with its crew aboard. This capstone composes every
pattern the chapter has taught.

**Concepts:** the composition. The [vehicle-as-room](155_drivable_vehicle.md)
gives the moving boarding gangway; the [airlock](032_airlock.md)'s
**cycle choreography** gives the two-door interlock; [fuel](163_vehicle_fuel.md)
gives launch a cost; and exit relinking ([tutorial 033](033_portal_pair.md))
docks the ship at each new site.

## How it works

The ship is two interior rooms, a cockpit and an airlock, joined by an inner
`hatch`. The airlock's outer `ramp` leads to whatever berth the ship is at, and
a matching `ramp` in that berth leads aboard. Flying does not move the interior
rooms at all: it teleports the boarding gangway to the destination berth and
relinks the outer ramp to point there, exactly as the
[rover](155_drivable_vehicle.md) carries its doors while its cab stays still.
This section answers four questions: how the interior is laid out, how the
airlock guarantees its one door is never open alongside the other, how flying
relocates the ship without moving a room, and where the authority comes from.

### What holds the ship's state

The cockpit is the flight deck and carries the ship's own attributes: its
`state` (`docked` or `flying`), its `site` (the id of the current berth), its
`fuel`, plus handles to the two exits flight has to move, namely the boarding
gangway (`board`) and the outer `ramp` (`outer_ramp`). The airlock carries the
two **door-face lists** the cycle drives: `inner_faces` (the two hatch faces)
and `outer_faces` (the two ramp faces). Every id is written with a leading `#`
so [`get`](../reference/softcode.md#fn-get) can resolve it straight back to the
object.

### How the airlock keeps one door shut

A ship's airlock has both of its doors in a single room, so this build keeps no
reactive hooks on the doors at all: they are plain exits whose `closed` tag the
engine already honours, since [movement refuses a closed
exit](155_drivable_vehicle.md). One `$cycle` command on the airlock room owns
all four faces and drives them with raw
[`add_tag`](../reference/softcode.md#fn-add_tag) and
[`remove_tag`](../reference/softcode.md#fn-remove_tag) writes, the same
choreography the [airlock tutorial](032_airlock.md) uses for its own cycle.
`cycle in` seals all four faces, then unseals the two inner ones; `cycle out`
seals all four, then unseals the two outer. Both-closed is always a legal
instant, so the "never both open" invariant holds at every step by
construction, with no wards to consult. Because a sealed inner hatch keeps the
cockpit out of reach while the outer door gapes, the geometry itself is the
flight safety.

### How flying relocates the ship without moving a room

`launch` refuses unless the outer door is sealed and there is fuel, then marks
the ship `flying`. `fly <berth>` spends one unit of fuel,
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj)s the boarding
gangway to the target berth, relinks the outer ramp's `destination` to that
berth with [`set_attr`](../reference/softcode.md#fn-set_attr), records the new
`site`, and marks the ship `docked`. The interior rooms and the crew inside
them never move: the gangway travels and the outer ramp relinks, and stepping
out the ramp now lands on a new world. That is the vehicle-as-room trick from
[tutorial 155](155_drivable_vehicle.md), scaled to a hull with two rooms and an
airlock.

### Where the authority comes from

The console and the airlock are builder-owned, so they may move the ship's own
exits, rewrite those exits' destinations, and seal their own doors. Nothing
here touches a player except the exits they choose to walk. The airlock's
`cycle` and the console's `status`, `launch`, and `fly` are all
[`$`-commands](../reference/softcode.md#fn-pemit), which react to a typed verb
in the room rather than to an action aimed at an object, so they need no
`target` guard.

## Build it

First dig the two berths and the ship's interior. The inner `hatch` pair comes
free from the two-way `@dig`, and each `@open` adds one face of the boarding
ramp, so the outer door is a pair of one-way ramps that the cycle will drive
together:

```text
@dig Docking Bay Alpha
@teleport me = Docking Bay Alpha
@dig Docking Bay Beta
@dig The Cockpit
@teleport me = The Cockpit
@dig The Airlock = hatch, hatch
@teleport me = The Airlock
@open ramp = Docking Bay Alpha
@teleport me = Docking Bay Alpha
@open ramp = The Airlock
```

Standing in the cockpit, wire the ship in one `@eval`: find each face by name
with [`contents`](../reference/softcode.md#fn-contents)
and [`has_tag`](../reference/softcode.md#fn-has_tag), hand the airlock its two
face lists, and stamp the cockpit with the gangway handle, the outer ramp to
relink, the current site, the flight state, and a full tank:

```text
@teleport me = The Cockpit
@eval '''
cock = here
air = get('The Airlock')
alpha = get('Docking Bay Alpha')
ih = [e for e in contents(cock) if has_tag(e, 'exit') and name(e) == 'hatch'][0]
ih2 = [e for e in contents(air) if has_tag(e, 'exit') and name(e) == 'hatch'][0]
orr = [e for e in contents(air) if has_tag(e, 'exit') and name(e) == 'ramp'][0]
sr = [e for e in contents(alpha) if has_tag(e, 'exit') and name(e) == 'ramp'][0]
set_attr(air, 'inner_faces', ['#' + ih.id, '#' + ih2.id])
set_attr(air, 'outer_faces', ['#' + orr.id, '#' + sr.id])
set_attr(cock, 'airlock', air.id)
set_attr(cock, 'outer_ramp', '#' + orr.id)
set_attr(cock, 'board', '#' + sr.id)
set_attr(cock, 'site', alpha.id)
set_attr(cock, 'state', 'docked')
set_attr(cock, 'fuel', 3)
result = 'ship wired'
'''
```

The airlock cycle seals all four faces with raw writes, then unseals the
requested pair. [`V`](../reference/softcode.md#fn-v) reads the face lists off
the airlock room (the executor), and `here` is the airlock the cycler is
standing in:

```text
@set The Airlock/cmd_cycle = '''
$cycle *:
way = trim(arg0).lower()
if way not in ('in', 'out'):
    pemit(enactor, 'Which way? CYCLE IN or CYCLE OUT.')
else:
    for d in V('inner_faces') + V('outer_faces'):
        add_tag(get(d), 'closed')  # seal every face first, so both-closed is the passing state
    for d in (V('inner_faces') if way == 'in' else V('outer_faces')):
        remove_tag(get(d), 'closed')
    remit(here, 'Pumps roar; the ' + ('inner' if way == 'in' else 'outer') + ' door unseals with a hiss.')
'''
```

Now build the flight console. Create it and drop it in the cockpit, then give
it its three commands:

```text
@teleport me = The Cockpit
@create flight console
@desc flight console = A crash-couch and a board of switches: STATUS, LAUNCH, FLY <berth>. (The airlock cycles from the lock itself: CYCLE IN / CYCLE OUT.)
drop flight console
```

`status` reads the cockpit and reports the state, fuel, berth, and each door's
seal in one line. `here` is the cockpit, so it reads the ship's attributes off
it and follows the stored `airlock` id to read the two door lists:

```text
@set flight console/cmd_status = '''
$status:
cock = here
air = get('#' + str(get_attr(cock, 'airlock')))
ish = 'SHUT' if all(has_tag(get(f), 'closed') for f in get_attr(air, 'inner_faces')) else 'OPEN'
osh = 'SHUT' if all(has_tag(get(f), 'closed') for f in get_attr(air, 'outer_faces')) else 'OPEN'
pemit(enactor, f'STATUS: {get_attr(cock, "state", "?")} | fuel {get_attr(cock, "fuel", 0)} | berth {name(get("#" + str(get_attr(cock, "site"))))} | inner {ish}, outer {osh}')
'''
```

`launch` gates on a sealed outer door and on fuel before it lifts off. The
seal-check repeats the airlock's guarantee as a direct precondition, so flight
refuses even if a door were forced open by other means:

```text
@set flight console/cmd_launch = '''
$launch:
cock = here
air = get('#' + str(get_attr(cock, 'airlock')))
osealed = all(has_tag(get(f), 'closed') for f in get_attr(air, 'outer_faces'))
if not osealed:
    pemit(enactor, 'Refused: an outer door is open. CYCLE IN first.')
elif get_attr(cock, 'fuel', 0) <= 0:
    pemit(enactor, 'Refused: fuel empty.')
else:
    set_attr(cock, 'state', 'flying')
    remit(cock, 'Engines light; the ship lifts off the pad and climbs into the black.')
    remit(get('#' + str(get_attr(cock, 'site'))), 'The ship boosts off the pad in a wash of flame.')
'''
```

`fly <berth>` finds the destination room by name with
[`search_world`](../reference/softcode.md#fn-search_world), refuses if the ship
is not flying, the berth is unknown, or the tank is empty, then spends a unit,
teleports the gangway, relinks the outer ramp, and docks:

```text
@set flight console/cmd_fly = '''
$fly *:
cock = here
goal = trim(arg0)
dests = [r for r in search_world(name=goal) if has_tag(r, 'room')]
site = dests[0] if dests else None
if get_attr(cock, 'state') != 'flying':
    pemit(enactor, 'Not flying yet: LAUNCH first.')
elif site is None:
    pemit(enactor, 'No such berth: ' + goal + '.')
elif get_attr(cock, 'fuel', 0) <= 0:
    pemit(enactor, 'Refused: fuel empty.')
else:
    set_attr(cock, 'fuel', get_attr(cock, 'fuel', 0) - 1)
    teleport_obj(get(get_attr(cock, 'board')), site)          # the boarding gangway travels to the new berth
    set_attr(get(get_attr(cock, 'outer_ramp')), 'destination', site.id)  # the outer ramp now opens onto it
    set_attr(cock, 'site', site.id)
    set_attr(cock, 'state', 'docked')
    remit(cock, 'The ship settles onto the pad at ' + name(site) + ' with a clang.')
    remit(site, 'A ship drops out of the sky and docks.')
'''
```

Finally set the starting state: docked at Alpha with the inner hatch sealed and
the outer ramp open for boarding:

```text
@teleport me = The Cockpit
@eval '''
air = get('The Airlock')
for f in get_attr(air, 'inner_faces'):
    add_tag(get(f), 'closed')
result = 'inner sealed'
'''
@teleport me = Docking Bay Alpha
```

## Try it

Board: the outer ramp is open, so walk aboard, then cycle to the inside:

```text
> ramp
The Airlock

> cycle in
Pumps roar; the inner door unseals with a hiss.

> hatch
The Cockpit

> status
STATUS: docked | fuel 3 | berth Docking Bay Alpha | inner OPEN, outer SHUT
```

Fly:

```text
> launch
Engines light; the ship lifts off the pad and climbs into the black.

> fly Docking Bay Beta
The ship settles onto the pad at Docking Bay Beta with a clang.
```

Disembark on the new world:

```text
> hatch
The Airlock

> cycle out
Pumps roar; the outer door unseals with a hiss.

> ramp
Docking Bay Beta
```

`@examine` the door faces at any instant of a cycle and they are never both
open, because seal-all-then-open-one guarantees it. A `launch` with the outer
ramp open is refused, and in any case reaching the cockpit means passing a
sealed inner hatch while the outer stands open, which the geometry forbids: the
airlock's layout is itself the flight safety. `fly` on an empty tank stays on
the pad. Every subsystem in the chapter is doing its job at once.

## Going further

- **A pilot's seat:** `@lock/use flight console = ...` so only the pilot flies
  while passengers ride, reusing [tutorial 155](155_drivable_vehicle.md)'s
  driver lock.
- **Refuel at the pad:** drop [tutorial 163](163_vehicle_fuel.md)'s pump in a
  docking bay and `pay` it while docked to top the tank, so trade routes become
  a fuel economy.
- **Cargo and crew:** dig a hold off the cockpit. It is still one gangway and
  one airlock, so flight is unchanged, and the ship scales by adding rooms.
- **A real starmap:** give each berth coordinates and charge `fly` fuel by
  distance, then gate a berth behind a [keycard](026_keycard_door.md) clearance
  for a fast-travel network with locked ports.
- **Depressurization with teeth:** an emergency `$vent` that raw-opens the
  outer ramp in flight and [`apply_effect`](../reference/softcode.md#fn-apply_effect)s
  vacuum exposure to everyone in the airlock, the
  [airlock](032_airlock.md)'s vacuum variation made lethal and a reason the
  cycle exists.
```