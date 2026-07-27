# 155. Drivable vehicle

> Checklist item 155 ([now]): *vehicle-as-container-room, $drive relays the map's exits, push-on-change [[...]] outside view*

**What you'll build:** A ground rover you climb *into*, because the cab is a
room. From the driver's seat you `drive north` and the whole rover trundles
across the map: onlookers watch it grind off in a cloud of dust and roll in
somewhere new, while you ride along inside. Step out the hatch and you are
wherever you parked.

**Concepts:** the **vehicle-as-room**, a cab room whose occupants are the
passengers; a **boarding exit that travels with the vehicle**
([`teleport_obj`](../reference/softcode.md#fn-teleport_obj) on an ordinary exit,
[tutorial 033](033_portal_pair.md)); a `$drive` **command that reads the outer
world's exits** from inside the cab; and a push-on-change
[`[[...]]`](036_weather_system.md) **outside view** ([tutorial 036](036_weather_system.md)).

## How it works

The finished shape is a room that pretends to be a thing. The rover's interior
is a room named `The Rover Cab`, and two exits tie it to the world: a `board`
exit that stands out *in the world* and leads into the cab, and a `hatch` exit
inside the cab that leads back out to wherever the rover is parked. Driving never
moves the passengers; it moves those two doors. This section answers where the
passengers actually are, what `drive` does under the hood, who is allowed to
steer, and how the view from outside stays cheap.

**The cab stays still; the doors move.** The cab tracks its own parking spot in
a `parked_at` attribute. When you `drive north`, the dashboard looks up the room
the rover is parked in, finds *its* `north` exit, and reads where that exit
goes. Then it makes two writes and one move:
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj) carries the `board`
exit into the new room, so people there can climb aboard, and
[`set_attr`](../reference/softcode.md#fn-set_attr) relinks the cab's `hatch` to
that same room, so stepping out drops you there. The passengers never move,
since they are standing in the cab and it is the cab's doors that now open
somewhere else. That is the whole trick: a vehicle is a room wearing a pair of
relocatable doors.

**Driving reads the map, it does not walk it.** The dashboard finds the outer
`north` exit only to read its `destination`, then relocates the doors straight
there. It never traverses that exit, which means the outer exit's own locks and
wards do not gate a drive. This keeps the mechanic simple, and the "Going
further" section shows how to put a terrain check back on the drive itself when
you want one.

**Who may steer.** The dashboard is builder-owned, so its
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj) and
[`set_attr`](../reference/softcode.md#fn-set_attr) calls succeed for the exits
and cab its owner built; that owner authority is what lets the command move the
doors at all. The `drive` command itself is a `$`-command, so it runs with the
dashboard's authority rather than the typist's, which means as built *any*
passenger riding in the cab may steer. To reserve the wheel for one driver, put
a use-lock on the dashboard (see "Going further").

**The outside view is push-on-change.** Each drive stamps a one-line `sitrep`
onto the `board` exit, and `look`ing at the rover from outside reads that single
local attribute in a [`[[...]]`](036_weather_system.md) block: cheap, shallow,
and correct, the habit from the [weather system](036_weather_system.md).

## Build it

First a little map for the rover to cross, three rooms in a line, with the
builder standing in the first:

```text
@dig The Motor Pool
@teleport me = The Motor Pool
@dig The Dust Flats = north, south
north
@dig The Canyon Rim = north, south
south
```

Now the rover itself. `@dig The Rover Cab = board, hatch` makes the cab room
plus its two doors in one stroke: `board` stands out in the Motor Pool leading
in, and `hatch` sits inside the cab leading back out. Step inside to configure
it:

```text
@dig The Rover Cab = board, hatch
@teleport me = The Rover Cab
```

The wiring step hands the cab a handle to each of its doors and records its
starting berth. It resolves the `hatch` from the cab's own contents and the
`board` from the world, stores each door's id under a named attribute so the
`$drive` command can fetch them later, reads the cab's opening parking spot off
wherever the hatch already leads, and seeds the outside `sitrep`:

```text
@eval '''
cab = here
hatch = [e for e in contents(cab) if has_tag(e, 'exit') and name(e) == 'hatch'][0]
board = [o for o in search_world(name='board') if has_tag(o, 'exit')][0]
set_attr(cab, 'hatch', '#' + hatch.id)   # keep each door's id so $drive can fetch it
set_attr(cab, 'board', '#' + board.id)
set_attr(cab, 'parked_at', str(get_attr(hatch, 'destination')))   # the cab starts parked where the hatch leads
set_attr(board, 'sitrep', 'A dusty rover idles here, hatch open.')
result = 'rover wired'
'''
```

Next the dashboard, an ordinary object dropped in the cab:

```text
@create dashboard
@desc dashboard = A steering yoke and a throttle. DRIVE <direction> to roll.
drop dashboard
```

The `$drive` command is the engine of the rover. It normalizes the direction,
finds the matching exit in the room the rover is parked in, and reads that
exit's destination. If there is no such exit it says so, and otherwise it
announces the departure to the old room, carries the `board` door to the new
room, relinks the `hatch` and updates `parked_at`, re-stamps the outside sitrep,
and narrates the arrival to the new room and the lurch to the riders:

```text
@set dashboard/cmd_drive = '''
$drive *:
way = trim(arg0).lower()
cab = here                 # the dashboard rides in the cab, so here is the cab room
outer = get('#' + str(get_attr(cab, 'parked_at')))
ex = [e for e in contents(outer) if has_tag(e, 'exit') and name(e) == way]
dest = get('#' + str(get_attr(ex[0], 'destination'))) if ex else None
if dest is None:
    pemit(enactor, 'The rover cannot roll ' + way + ' from here.')
else:
    board = get(get_attr(cab, 'board'))
    hatch = get(get_attr(cab, 'hatch'))
    remit(outer, 'The rover grinds ' + way + ' and rolls out of sight.')
    teleport_obj(board, dest)               # the boarding door travels to the new room
    set_attr(hatch, 'destination', dest.id)  # stepping out of the cab now drops you there
    set_attr(cab, 'parked_at', dest.id)
    set_attr(board, 'sitrep', 'A dusty rover idles here at ' + name(dest) + ', hatch open.')
    remit(dest, 'A dusty rover rolls in and settles, engine ticking.')
    remit(cab, 'The cab lurches ' + way + '; the land slides past the ports.')
'''
```

Finally the outside view. Standing back in the Motor Pool with the `board` exit,
give it a description whose [`[[...]]`](036_weather_system.md) tail reads the one
stamped `sitrep` line off the exit itself:

```text
@teleport me = The Motor Pool
@desc board = A rugged six-wheeled rover, hatch standing open. [[result = V('sitrep', '')]]
```

## Try it

Board, drive, and step out the far side:

```text
> board
You leave board.
The Rover Cab
Exits: hatch

> drive north
The cab lurches north; the land slides past the ports.

> hatch
You step out onto The Dust Flats.
```

Onlookers left behind in the Motor Pool saw "The rover grinds north and rolls
out of sight", and anyone standing in the Dust Flats saw it roll in. Climb back
in and `drive north` again to reach the Canyon Rim, since the rover carries its
doors with it every hop. From outside, `look board` before you board shows the
push-on-change sitrep naming where the rover last parked:

```text
> look board
A rugged six-wheeled rover, hatch standing open. A dusty rover idles here at The Dust Flats, hatch open.
```

## Going further

- **A driver's lock:** `@lock/use dashboard = caller.id == owner.id` (or a
  `driver` attribute you hand off) so passengers ride but only the driver steers.
  A `$`-command honors the object's use-lock, so this is what actually reserves
  the wheel; it is the [pet](065_pet.md)'s ownership line, put on a throttle.
- **Fuel:** the rover runs on hope until [tutorial 163](163_vehicle_fuel.md)
  gives it a tank, a low-fuel light, and a pump.
- **Bigger rigs:** dig a second interior room (a cargo bay) off the cab. The
  vehicle is still one `board`/`hatch` pair, so nothing about driving changes;
  this is the seed of the [spaceship](164_small_spaceship.md).
- **Terrain gates:** because `$drive` reads an exit's destination rather than
  walking the exit, a [skill-checked ledge](034_climbing_exit.md) or a
  [toll](030_toll_gate.md) on the outer exit stays silent during a drive. To
  make one bite, have `$drive` consult the outer exit's lock with
  [`test_lock`](../reference/softcode.md#fn-test_lock) before it relocates the
  doors, so the rover faces the same gate a walker would.
