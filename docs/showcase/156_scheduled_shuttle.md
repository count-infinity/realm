# 156. Scheduled shuttle

> Checklist item 156 ([now]): *on_tick timetables, boarding windows*

**What you'll build:** An automated shuttle that runs a loop of three
platforms on its own clock. It pulls in and opens for boarding, then on the
next beat glides to the next stop, carrying whoever climbed aboard. There is no
driver: the timetable is a [`script_ticker`](036_weather_system.md) firing the
cabin's [`on_tick`](../reference/softcode.md#lifecycle-hooks).

**Concepts:** the [drivable vehicle](155_drivable_vehicle.md)'s moving cabin and
travelling boarding exit made **autonomous** by an
[`on_tick`](../reference/softcode.md#lifecycle-hooks) heartbeat; a **route** as
an ordered list of stop ids the cabin walks in a loop; a **boarding window**
enforced by where the boarding exit is, since it travels with the shuttle.

## How it works

The finished shuttle is one room, `The Shuttle Cabin`, plus three platform
rooms it visits in turn. A ticker fires the cabin's `on_tick` on a fixed
cadence, and each firing relocates one exit and rewrites one destination. This
section answers three questions: who drives the cabin, how the route advances,
and why a latecomer cannot board a shuttle that has already left.

### Who drives, now that nobody is at the wheel?

Like the [rover](155_drivable_vehicle.md), the shuttle is a cabin room with a
`shuttle` boarding exit out in the world and a `hatch` exit inside that leads
back to the current stop. The rover moved because a player typed `drive`; the
shuttle moves because a [`script_ticker`](036_weather_system.md) behavior fires
the cabin's [`on_tick`](../reference/softcode.md#lifecycle-hooks) attribute on a
cadence, and that script performs the departure. The ticker only supplies the
clock, since the departure logic lives entirely in the `on_tick` attribute a
builder can [`@set`](../guides/world-management.md#multi-line-input-heredocs).

### How does the route advance?

The cabin holds an ordered `stops` list of platform ids and an `idx` cursor into
it. Each tick reads the platform the shuttle is leaving, advances `idx` around
the loop with `% len(stops)` so it wraps from the last stop back to the first,
then uses [`teleport_obj`](../reference/softcode.md#fn-teleport_obj) to move the
boarding exit to the platform `idx` now names. It also rewrites the `hatch`
exit's `destination` to that same platform, so a rider who steps out lands at
the new stop. Riders sit in the cabin room the entire time and never move
themselves, which is why the shuttle carries them for free.

### Why can a latecomer not board once it has left?

The boarding window is simply the location of the `shuttle` exit. While the
shuttle is parked, that exit stands at the current platform and anyone there can
board. When the tick relocates the exit to the next stop, the platform it left
is bare: there is no `shuttle` exit there for a latecomer to take, so they wait
for the loop to bring the shuttle around again. To widen or narrow the window,
change the ticker's `interval`, because the whole timetable is that one number.

## Build it

Dig the three platforms and the cabin, then open the two exits that bind them:
a `hatch` inside the cabin leading to Platform One, and a `shuttle` boarding
exit at Platform One leading into the cabin.

```text
@dig Platform One
@teleport me = Platform One
@dig Platform Two
@teleport me = Platform One
@dig Platform Three
@teleport me = Platform One
@dig The Shuttle Cabin
@teleport me = The Shuttle Cabin
@open hatch = Platform One
@teleport me = Platform One
@open shuttle = The Shuttle Cabin
```

Wire the cabin. This one [`@eval`](../guides/world-management.md) stores the
route (the three platform ids), sets the `idx` cursor to the first stop, and
hands the cabin stable handles to its two exits by
[`search_world`](../reference/softcode.md#fn-search_world) and
[`contents`](../reference/softcode.md#fn-contents). The `stops` value is a plain
data list, so it stays a single-line [`set_attr`](../reference/softcode.md#fn-set_attr):

```text
@teleport me = The Shuttle Cabin
@eval cab=here; p1=get('Platform One'); p2=get('Platform Two'); p3=get('Platform Three'); set_attr(cab,'stops',[p1.id,p2.id,p3.id]); set_attr(cab,'idx',0); hatch=[e for e in contents(cab) if has_tag(e,'exit') and name(e)=='hatch'][0]; board=[o for o in search_world(name='shuttle') if has_tag(o,'exit')][0]; set_attr(cab,'hatch','#'+hatch.id); set_attr(cab,'board','#'+board.id); result='shuttle wired'
```

The timetable is the cabin's `on_tick`. Each firing announces the departure,
advances the cursor, moves the boarding exit and relinks the hatch to the next
stop, then announces the arrival. It is a stored script with several statements,
so it is written as a [`'''` block](../guides/world-management.md#multi-line-input-heredocs)
of ordinary softcode. An `on_tick` heartbeat runs on the object itself, so it
takes no [`target` guard](../reference/softcode.md#guard-on-target):

```text
@set The Shuttle Cabin/on_tick = '''
cab = me
stops = get_attr(cab, 'stops')
depart = get('#' + str(stops[get_attr(cab, 'idx')]))
board = get(get_attr(cab, 'board'))
remit(depart, 'The shuttle doors seal; it slides out of the station.')
nxt = (get_attr(cab, 'idx') + 1) % len(stops)  # wrap from the last stop back to the first
set_attr(cab, 'idx', nxt)
dest = get('#' + str(stops[nxt]))
teleport_obj(board, dest)  # the boarding exit itself travels, so the platform it leaves has no 'shuttle' exit until the loop returns
set_attr(get(get_attr(cab, 'hatch')), 'destination', dest.id)  # relink the hatch so riders step out at the new stop
remit(dest, 'The shuttle glides in; the doors open. Now boarding.')
remit(cab, 'The cabin sways as the shuttle changes track.')
'''
```

Attach the heartbeat that runs it. `interval:15` is fifteen world beats between
departures, and it is the only number in the timetable. The final teleport
leaves you standing on Platform One to watch:

```text
@behavior The Shuttle Cabin = script_ticker, interval:15
@teleport me = Platform One
```

## Try it

Board at Platform One while the shuttle is parked there:

```text
> shuttle
you board The Shuttle Cabin
```

Wait for the beat, or force one with `@tr The Shuttle Cabin/on_tick`, then step
out onto the next platform:

```text
> @tr The Shuttle Cabin/on_tick
The cabin sways as the shuttle changes track.

> hatch
you step out onto Platform Two
```

Watch a platform without boarding and the loop breathes past you: "The shuttle
doors seal; it slides out of the station." here, then one stop down "The shuttle
glides in; the doors open. Now boarding." A latecomer who types `shuttle` at the
platform the shuttle just left finds no boarding exit there and waits for the
loop to return it. [`@examine`](../guides/world-management.md) The Shuttle Cabin
shows the `idx` cursor stepping 0, 1, 2, 0 around the route.

## Going further

- **A boarding countdown:** give the cabin a second `script_ticker` on a
  different `attr` (the behavior takes an `attr` param, see
  [tutorial 036](036_weather_system.md)) that only warns "doors closing!" one
  beat before departure, for a real timetable feel.
- **Express vs local:** store a second `stops` list and an `express` flag the
  `on_tick` picks between, so a rush-hour run skips Platform Two.
- **Fares:** gate the `shuttle` boarding exit with a [toll](030_toll_gate.md) so
  you tap a fare to board, or sell passes an NPC checks.
- **A visible arrivals board:** stamp the next stop onto a sign at each platform
  (push-on-change) and read it with a `[[...]]` desc, so riders see
  "Next: Platform Three" without asking.
```
