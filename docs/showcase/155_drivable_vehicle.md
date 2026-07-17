# 155. Drivable vehicle

> Checklist item 155 — now — *vehicle-as-room, a moving boarding exit, relayed drive commands*

**What you'll build:** A ground rover you climb *into* — the cab is a
room. From the driver's seat you `drive north` and the whole rover
trundles across the map: onlookers watch it grind off in a cloud of
dust and roll in somewhere new, while you ride along inside. Step out
the hatch and you're wherever you parked.

**Concepts:** the **vehicle-as-room** — a cab room whose occupants are
the passengers; a **boarding exit that travels with the vehicle**
(`teleport_obj` on an ordinary exit, [tutorial 033](033_portal_pair.md));
`$drive` **relaying** the outer world's exits from inside; a
push-on-change `[[...]]` **outside view** ([tutorial 036](036_weather_system.md)).

## How it works

**The cab stays still; the doors move.** The rover's interior is a room,
`The Rover Cab`. Two exits bind it to the world: a `board` exit that
sits out *in the world* and leads into the cab, and a `hatch` exit
inside the cab that leads back out to wherever the rover is parked. The
cab tracks its own location in a `parked_at` attribute.

**Driving is relaying the outer exits.** When you `drive north` from the
seat, the dashboard looks up the room the rover is *parked in*, finds
*its* `north` exit, and reads where it goes. Then it does two writes and
two moves: `teleport_obj` the `board` exit into the new room (so people
there can climb aboard), and relink the cab's `hatch` to the new room
(so stepping out drops you there). The passengers never move — they're
in the cab, and the cab's doors now open somewhere else. That's the
whole trick: a vehicle is a room wearing a pair of relocatable doors.

**Authority makes it safe.** The dashboard is builder-owned, so it may
teleport the rover's own exits and rewrite their destinations — but it
can't drive a rover it doesn't own, and the outer exits it relays
through still enforce their own locks and guards.

**The outside view is push-on-change.** Each drive stamps a one-line
`sitrep` onto the `board` exit; `look`ing at the rover from outside
reads that single local attribute in a `[[...]]` block — cheap, shallow,
and correct, the habit from the weather system.

## Build it

A little map for the rover to cross:

```text
@dig The Motor Pool
@teleport me = The Motor Pool
@dig The Dust Flats = north, south
north
@dig The Canyon Rim = north, south
south
```

The rover itself — the cab, its two exits (`board` out in the world,
`hatch` inside), and the wiring that hands the cab handles to both plus
its starting berth:

```text
@dig The Rover Cab = board, hatch
@teleport me = The Rover Cab
@eval cab = here; hatch = [e for e in contents(cab) if has_tag(e,'exit') and name(e)=='hatch'][0]; board = [o for o in search_world(name='board') if has_tag(o,'exit')][0]; set_attr(cab, 'hatch', '#'+hatch.id); set_attr(cab, 'board', '#'+board.id); set_attr(cab, 'parked_at', str(get_attr(hatch,'destination'))); set_attr(board, 'sitrep', 'A dusty rover idles here, hatch open.'); result='rover wired'
```

The dashboard — `$drive` reads the parked room's exit, relays the rover
through it, and re-stamps the outside view:

```text
@create dashboard
@desc dashboard = A steering yoke and a throttle. DRIVE <direction> to roll.
drop dashboard
@set dashboard/cmd_drive = $drive *: way = trim(arg0).lower(); cab = here; outer = get('#' + str(get_attr(cab, 'parked_at'))); ex = [e for e in contents(outer) if has_tag(e, 'exit') and name(e) == way]; dest = get('#' + str(get_attr(ex[0], 'destination'))) if ex else None; (pemit(enactor, 'The rover cannot roll ' + way + ' from here.') if dest is None else (remit(outer, 'The rover grinds ' + way + ' and rolls out of sight.'), teleport_obj(get(get_attr(cab, 'board')), dest), set_attr(get(get_attr(cab, 'hatch')), 'destination', dest.id), set_attr(cab, 'parked_at', dest.id), set_attr(get(get_attr(cab, 'board')), 'sitrep', 'A dusty rover idles here at ' + name(dest) + ', hatch open.'), remit(dest, 'A dusty rover rolls in and settles, engine ticking.'), remit(cab, 'The cab lurches ' + way + '; the land slides past the ports.')))
```

Finally, the outside view — a `[[...]]` desc on the `board` exit that
reads the one stamped line:

```text
@teleport me = The Motor Pool
@desc board = A rugged six-wheeled rover, hatch standing open. [[result = get_attr(me, 'sitrep', '')]]
```

## Try it

```text
board               -> you climb into The Rover Cab
drive north         -> "The cab lurches north; the land slides past the ports."
hatch               -> you step out onto The Dust Flats
```

Onlookers left behind in the Motor Pool saw "The rover grinds north and
rolls out of sight"; anyone standing in the Dust Flats saw it roll in.
Climb back in and `drive north` again to reach the Canyon Rim — the
rover carries its doors with it every hop. From outside, `look board`
(before you board) shows the push-on-change sitrep naming where the
rover last parked.

## Going further

- **A driver's lock:** `@lock/use dashboard = caller.id == owner.id` (or
  a `driver` attribute you can hand off) so passengers ride but only the
  driver steers — the [pet](065_pet.md)'s ownership line, on a throttle.
- **Fuel:** the rover runs on hope until [tutorial 163](163_vehicle_fuel.md)
  gives it a tank, a low-fuel light, and a pump.
- **Bigger rigs:** dig a second interior room (a cargo bay) off the cab;
  the vehicle is still one `board`/`hatch` pair, so nothing about
  driving changes — this is the seed of the [spaceship](164_small_spaceship.md).
- **Terrain gates:** the outer exits are ordinary exits, so a
  [skill-checked ledge](034_climbing_exit.md) or a [toll](030_toll_gate.md)
  on the map applies to the rover exactly as it would to a walker.
