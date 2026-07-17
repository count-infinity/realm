# 164. Small spaceship

> Checklist item 164 — now — *CAPSTONE: vehicle-as-room + airlock cycle + fuel + launch/fly/dock*

**What you'll build:** A little ship you can fly between docking bays. It
has an interior — a cockpit and an airlock — with a proper cycle: the
airlock never lets both doors stand open at once, because the outer one
faces vacuum in flight. Cycle through, seal up, `launch`, `fly` to
another berth, and the whole ship — hull, doors, and crew — arrives and
docks. It's every pattern in this chapter, bolted together.

**Concepts:** the composition. The [vehicle-as-room](155_drivable_vehicle.md)
gives the moving hull and a gangway that travels with it; the
[airlock](032_airlock.md)'s **cycle choreography** gives the two-door
interlock; [fuel](163_vehicle_fuel.md) gives launch a cost; and exit
relinking ([tutorial 033](033_portal_pair.md)) docks the ship at each new
site.

## How it works

**The ship is a two-room vehicle.** Interior: `The Cockpit` and `The
Airlock`, joined by an inner `hatch` (a two-faced door). The airlock's
outer `ramp` leads out to the current berth, and a matching `ramp` sits
in the berth leading aboard — the [rover's](155_drivable_vehicle.md)
travelling gangway, now the ship's boarding ramp. The cockpit holds the
ship's `state` (docked / flying), its `site`, its `fuel`, and handles to
the gangway; the airlock holds the two **door-face lists**.

**The airlock is a cycle, not four mirrored doors.** Here's the trick
the [airlock tutorial](032_airlock.md) teaches and this capstone *needs*:
a ship's airlock has both its doors in one room, and event-mirror hooks
would cross-fire between them. So the airlock is driven the same way 032
runs its real choreography — **raw writes**. `cycle in` seals all four
faces, then unseals the two inner ones; `cycle out` seals all four, then
unseals the two outer. Both-closed is always a legal instant, so the "never
both open" invariant holds at every step — by construction, with no wards
to dodge. And because the airlock structurally forbids reaching the
cockpit while the outer door gapes, you *can't* fly with the hull open —
the safety is the geometry.

**Flying is fuel + relink.** `launch` refuses without a sealed outer door
(belt-and-suspenders on the geometry) or fuel, then marks the ship
`flying`. `fly <berth>` spends a unit, `teleport_obj`s the gangway to the
target berth, relinks the outer ramp's destination, and marks the ship
`docked` there. The crew, in the cockpit, ride the whole way — the hull
moved, they didn't. Then they cycle the airlock out and step onto a new
world.

**Authority ties it together.** The console and the airlock are
builder-owned, so they may move the ship's own exits, rewrite their
destinations, and seal their own doors — but nothing here touches a player
except the exits they choose to walk.

## Build it

The two berths and the ship's interior — the inner `hatch` pair comes
free from `@dig`, and both `ramp` faces open the gangway:

```text
@dig Docking Bay Alpha
@teleport me = Docking Bay Alpha
@dig Docking Bay Beta
@teleport me = Docking Bay Alpha
@dig The Cockpit
@teleport me = The Cockpit
@dig The Airlock = hatch, hatch
@teleport me = The Airlock
@open ramp = Docking Bay Alpha
@teleport me = Docking Bay Alpha
@open ramp = The Airlock
```

Wire it: the airlock learns its two door-face lists; the cockpit learns
the gangway, the outer ramp to relink, and its flight state:

```text
@teleport me = The Cockpit
@eval cock=here; air=get('The Airlock'); alpha=get('Docking Bay Alpha'); ih=[e for e in contents(cock) if has_tag(e,'exit') and name(e)=='hatch'][0]; ih2=[e for e in contents(air) if has_tag(e,'exit') and name(e)=='hatch'][0]; orr=[e for e in contents(air) if has_tag(e,'exit') and name(e)=='ramp'][0]; sr=[e for e in contents(alpha) if has_tag(e,'exit') and name(e)=='ramp'][0]; set_attr(air,'inner_faces',['#'+ih.id,'#'+ih2.id]); set_attr(air,'outer_faces',['#'+orr.id,'#'+sr.id]); set_attr(cock,'airlock',air.id); set_attr(cock,'outer_ramp','#'+orr.id); set_attr(cock,'board','#'+sr.id); set_attr(cock,'site', alpha.id); set_attr(cock,'state','docked'); set_attr(cock,'fuel',3); result='ship wired'
```

The airlock cycle — raw-seal all four faces, then unseal the requested
pair (the [032](032_airlock.md) choreography):

```text
@set The Airlock/cmd_cycle = $cycle *: way = trim(arg0).lower(); doors = V('inner_faces') + V('outer_faces'); (pemit(enactor, 'Which way? CYCLE IN or CYCLE OUT.') if way not in ('in','out') else ([add_tag(get(d),'closed') for d in doors], [remove_tag(get(d),'closed') for d in (V('inner_faces') if way=='in' else V('outer_faces'))], remit(here, 'Pumps roar; the ' + ('inner' if way=='in' else 'outer') + ' door unseals with a hiss.')))
```

The flight console in the cockpit — status, launch (sealed + fuel gate),
and fly (fuel + relink + dock):

```text
@create flight console
@desc flight console = A crash-couch and a board of switches: STATUS, LAUNCH, FLY <berth>. (The airlock cycles from the lock itself: CYCLE IN / CYCLE OUT.)
drop flight console
@set flight console/cmd_status = $status: cock = here; air = get('#'+str(get_attr(cock,'airlock'))); ish = 'SHUT' if all(has_tag(get(f),'closed') for f in get_attr(air,'inner_faces')) else 'OPEN'; osh = 'SHUT' if all(has_tag(get(f),'closed') for f in get_attr(air,'outer_faces')) else 'OPEN'; pemit(enactor, f'STATUS: {get_attr(cock,"state","?")} | fuel {get_attr(cock,"fuel",0)} | berth {name(get("#"+str(get_attr(cock,"site"))))} | inner {ish}, outer {osh}')
@set flight console/cmd_launch = $launch: cock = here; air = get('#'+str(get_attr(cock,'airlock'))); osealed = all(has_tag(get(f),'closed') for f in get_attr(air,'outer_faces')); (pemit(enactor,'Refused: an outer door is open. CYCLE IN first.') if not osealed else (pemit(enactor,'Refused: fuel empty.') if get_attr(cock,'fuel',0) <= 0 else (set_attr(cock,'state','flying'), remit(cock,'Engines light; the ship lifts off the pad and climbs into the black.'), remit(get('#'+str(get_attr(cock,'site'))),'The ship boosts off the pad in a wash of flame.'))))
@set flight console/cmd_fly = $fly *: cock = here; goal = trim(arg0); dests = [r for r in search_world(name=goal) if has_tag(r,'room')]; site = dests[0] if dests else None; (pemit(enactor,'Not flying — LAUNCH first.') if get_attr(cock,'state') != 'flying' else (pemit(enactor,'No such berth: ' + goal + '.') if site is None else (pemit(enactor,'Refused: fuel empty.') if get_attr(cock,'fuel',0) <= 0 else (set_attr(cock,'fuel', get_attr(cock,'fuel',0)-1), teleport_obj(get(get_attr(cock,'board')), site), set_attr(get(get_attr(cock,'outer_ramp')),'destination', site.id), set_attr(cock,'site', site.id), set_attr(cock,'state','docked'), remit(cock,'The ship settles onto the pad at ' + name(site) + ' with a clang.'), remit(site,'A ship drops out of the sky and docks.')))))
```

Set the starting state — docked at Alpha with the inner hatch sealed and
the outer ramp open for boarding:

```text
@teleport me = The Cockpit
@eval air=get('The Airlock'); [add_tag(get(f),'closed') for f in get_attr(air,'inner_faces')]; result='inner sealed'
@teleport me = Docking Bay Alpha
```

## Try it

Board — the outer ramp is open, so walk aboard, then cycle to the inside:

```text
ramp                -> into The Airlock
cycle in            -> "Pumps roar; the inner door unseals." (outer seals)
hatch               -> into The Cockpit
status              -> STATUS: docked | fuel 3 | berth Docking Bay Alpha | inner OPEN, outer SHUT
```

Fly:

```text
launch              -> "Engines light; the ship... climbs into the black."
fly Docking Bay Beta-> "The ship settles onto the pad at Docking Bay Beta with a clang."
```

Disembark on the new world:

```text
hatch               -> back into The Airlock
cycle out           -> "...the outer door unseals." (inner seals)
ramp                -> you stand on Docking Bay Beta
```

`@examine` the door faces at any instant of a cycle: they are *never*
both open — seal-all-then-open-one guarantees it. And notice you could
never `launch` with the outer ramp open, because you can't reach the
cockpit past a sealed inner hatch while the outer gapes — the airlock's
geometry *is* the flight safety. `fly` on an empty tank won't leave the
pad; every subsystem in the chapter is doing its job at once.

## Going further

- **A pilot's seat:** `@lock/use flight console = ...` so only the pilot
  flies, while passengers ride ([tutorial 155](155_drivable_vehicle.md)'s
  driver lock).
- **Refuel at the pad:** drop [tutorial 163](163_vehicle_fuel.md)'s pump
  in a docking bay; `pay` it while docked to top the tank — trade routes
  become a fuel economy.
- **Cargo and crew:** dig a hold off the cockpit; it's still one gangway
  and one airlock, so flight is unchanged — the ship scales by adding
  rooms.
- **A real starmap:** give each berth coordinates and charge `fly` fuel
  by distance; gate a berth behind a [keycard](026_keycard_door.md)
  clearance and you've a fast-travel network with locked ports.
- **Depressurization with teeth:** an emergency `$vent` that raw-opens
  the outer ramp in flight and `apply_effect`s vacuum exposure to
  everyone in the airlock — the [airlock](032_airlock.md)'s vacuum
  variation, made lethal, and a reason the cycle exists.
