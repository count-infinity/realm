# Star Wars Reality (SWR) space system vs REALM

A reference comparison against the **space/starship system** of **Star Wars
Reality** (SWRFUSS — a SMAUG-derived C codebase, `~/SWRFUSS/src/`, ~40
`.c` files). Almost the entire subsystem lives in one 7,000-line file,
`space.c`, plus the `ship_data` / `space_data` / `missile_data` structs in
`mud.h`. It maps what SWR does onto REALM's **vehicle model** and its
**reserved "spatial primitive"** (the coordinate sidecar in the
[features roadmap](features-roadmap.md), line 21), and flags what's worth
stealing.

SWR matters here because it is a *shipped, played* answer to the exact
question REALM has deferred: how do you run continuous free-flight space —
ranges, headings, homing weapons — in a MUD that is otherwise a graph of
rooms? SWR's answer is the reusable insight, and it is more modest than the
roadmap fears.

## The one deep difference — SWR runs a room graph AND a coordinate sidecar at once

**SWR does not choose between "space is rooms" and "space is coordinates."
It runs both simultaneously, and a starship has two identities at once.** A
ship is a `SHIP_DATA` struct (`mud.h:848`) that always owns a contiguous
block of ordinary room vnums — `firstroom`..`lastroom`, with named role
rooms `cockpit`, `pilotseat`, `coseat`, `navseat`, `gunseat`, `turret1/2`,
`engineroom`, `entrance`, `hanger`, `location` (`mud.h:895-916`). Those
interior rooms are normal rooms in the normal room graph and exist whether
the ship is parked or in deep space. *On top of that*, the same struct
carries nine floats — position `vx,vy,vz`, heading `hx,hy,hz`, jump-target
`jx,jy,jz` (`mud.h:889-891`) — plus a `starsystem` pointer. Those exist only
while the ship is flying.

So SWR draws the line in a very specific place:

- **Inside a ship, and between star systems: room graph.** You walk around
  the cockpit; you `board` through a hatch; a hyperspace jump moves the ship
  from one star-system container to another. All discrete.
- **Within a single star system: continuous coordinates.** Two ships in the
  same system have a real, changing `sqrt(dx²+dy²+dz²)` distance between
  them. This is the *only* place SWR needs floats, and it is the only place
  a room graph genuinely cannot express (two objects in one room have no
  distance).

That is exactly REALM's reserved split: discrete cells = rooms; continuous
free-flight = a coordinate sidecar beside the graph. SWR proves the sidecar
is small — nine floats and one Euler-integration step, not a physics engine.

## 1. The space model

| | SWR (space.c / mud.h) | REALM today |
|---|---|---|
| Within-system space | **Continuous 3D coordinates.** Ship has float `vx,vy,vz` position (`mud.h:889`) | room graph only; no intra-room distance |
| Movement | **Euler vector integration.** Each `move_ships` tick: normalize heading, `vx += (hx/|h|)·currspeed/5` (`space.c:432-441`) | `move_through_exit` traversal — discrete hops, no velocity |
| Heading / turning | `do_trajectory x y z` sets heading = target − position: `hx = vx_target − vx` (`space.c:5233-5235`); big ships take N ticks to come about (`SHIP_BUSY` states, `space.c:5246-5251`) | n/a — exits, not vectors |
| Speed | scalar `currspeed`, clamped to `realspeed`; `do_accelerate` burns fuel (`space.c:5122-5124`) | n/a |
| Star system | `SPACE_DATA` = a **container** (linked list of ships, missiles, planets) with fixed named points: stars `s1x/y/z`, planets `p1x/y/z`, gravity wells, dock-room vnums `doc1a..doc3c` (`mud.h:698-760`) | a room / zone |
| Galaxy | coarse **integer graph**: each system has `xpos,ypos` (`mud.h:721-722`) used only to price jumps: `(|Δx|+|Δy|)/2` (`space.c:6757`) | room graph + exits (the natural fit) |
| Hyperspace (between systems) | **discrete jump.** `do_calculate` stores dest system + entry `jx,jy,jz` (`space.c:6775-6778`); `do_hyperspace` removes ship from system, sets `vx=jx` (`space.c:6010-6012`); tick counts `hyperdistance` down then re-inserts into dest system (`space.c:707-730`) | exit traversal is the exact analogue |
| Planets / stars | **named coordinate points**, not places. Flying within 10 units of a star = death (`space.c:516-537`); within 10 of a planet = auto-orbit, `currspeed=0` (`space.c:541-576`); gravity-well pull code exists but is commented out (`space.c:448-500`) | planets are rooms; "surface" is ordinary rooms |
| Tick cadence | `move_ships` (integrate position) ~1/sec; `update_space` (state machine, telemetry, energy, shields) every 10 sec (`mud.h:235`, `update.c:2153-2168`) | one global heartbeat |

The shape: **a coarse discrete graph of star systems, each of which opens
into a small continuous coordinate volume.** Hyperspace is graph traversal;
sublight flight is vector integration. Planets and stars are just *tagged
points* inside the volume with proximity rules bolted on.

## 2. Ships as entities — a hybrid, resolved by room-vnum matching

| | SWR | REALM today |
|---|---|---|
| What a ship *is* | **hybrid**: a `SHIP_DATA` sidecar that owns a block of interior room vnums *and* (while flying) a coordinate + system membership (`mud.h:848-928`) | a `GameObject` that is a container-room you board |
| Interior | ordinary rooms (`firstroom`..`lastroom`), always present in the room graph | ordinary rooms, via containment |
| "Which ship am I in?" | **reverse lookup by vnum**: `ship_from_pilotseat(ch->in_room->vnum)`, `ship_from_cockpit`, `ship_from_turret`… scan every ship matching the player's room (`space.c:2227-2311`) | direct containment: the vehicle *is* your `location`'s parent |
| Ship ↔ coordinate binding | `ship_to_starsystem` links the struct into a system's ship list and sets `vx/vy/vz` (`space.c:3931-3951`); `ship_from_starsystem` unlinks it | the reserved sidecar would tag coordinates onto the GameObject |
| Roles | control rooms are *typed by which vnum field they occupy* — pilot seat can `launch`/`accelerate`/`trajectory`; nav seat can `calculate`; gun seat/turret can `target`/`fire` (`space.c:5045,6718,6035`) | any room + lock/behavior could gate commands |
| Command gating | every space command re-derives the ship from the room and checks seat + state (`SHIP_DOCKED`/`READY`/`HYPERSPACE`…) | command availability by location + locks |

The crucial mechanic: SWR has **no pointer from a player to their ship**. It
matches the player's current room vnum against the ship's stored seat vnums
every command. REALM's containment graph gives this for free and more
cleanly — the vehicle is literally an ancestor of the pilot's location.

## 3. Passenger / riding model

| | SWR | REALM today |
|---|---|---|
| How you board | `do_board`: `char_from_room` → `char_to_room(entrance)` through an open hatch (`space.c:4299-4357`) | `enter` the vehicle container (movement + `on_enter`) |
| How passengers ride | **they don't move with the ship — the ship's coordinate changes, the interior rooms are static.** A passenger is simply a `CHAR_DATA` standing in an interior room; only `SHIP_DATA.vx/vy/vz` updates each tick | occupants ride via **containment**: they are inside the container that moves |
| Riding relationship | *implicit* — "in an interior room of a struct that has coordinates" | *explicit* — containment edge |
| Crew coordination | multiple players in different seat rooms (pilot flies, gunner fires, nav plots) — genuine multi-crew | same, and follower/party cascade already carries occupants |
| Leaving in flight | `do_leaveship` blocked unless docked/landed (`space.c:4380`) | movement locks |

SWR and REALM reach the *same* passenger model — "you're inside a thing that
moves, so you go where it goes" — but SWR fakes it (the interior never
actually moves; only the sidecar coordinate does) while REALM does it
literally (the container moves and containment carries you). For a
room-graph ship these are indistinguishable to the player.

## 4. Space combat

| | SWR | REALM today |
|---|---|---|
| Targeting | `do_target` sets `ship->target0/1/2` (one per turret) to another `SHIP_DATA`; **range-gated**: `|Δv| > 5000` = "too far to target" (`space.c:6101-6107`) | dice primitives + attrs; **no range** without the sidecar |
| Facing | forward weapons need `is_facing`: dot(heading, bearing)/… > 0.75 cos (`space.c:2025-2044, 6253`) | needs heading vectors — sidecar only |
| Hit chance | skill − target `manuever`/10 − `currspeed`/20 − coordinate distance/70, clamped 10–90 (`space.c:6259-6265`) | dice + modifiers, but distance term needs coords |
| Weapons | lasers (forward, instant), missiles/torpedos/rockets (homing), tractor beam, chaff (missile defense) | softcode weapon defs |
| Missiles | **independent `MISSILE_DATA` entities** with own `mx,my,mz`, home toward target coords at `speed/5`/tick, detonate within 20 units, age out at 50 ticks (`space.c:351-423`, `mud.h:930`) | a homing projectile with a position is a *pure* sidecar object |
| Damage model | scalar pools: `shield` (decays/tick, autorecharge from `energy`), `hull`, `energy` (`space.c:765-784`, `damage_ship`) | scalar attrs + dice — **works on a room graph today** |
| Proximity broadcast | `echo_to_system` pushes to every *other* ship's cockpit in the same system; `echo_to_cockpit` to all control rooms of one ship (`space.c:2010-2023`) | per-viewer `[[...]]` messaging + two-pass propagation |

Two clean layers: **the damage/shield/energy economy is scalar and needs no
geometry** (REALM does this today with dice + attrs), while **targeting,
facing, range-to-hit, and homing missiles all reduce to coordinate
comparisons** and cannot exist on a bare room graph.

## 5. Space ↔ ground transition

| | SWR | REALM today |
|---|---|---|
| Docked state | ship interior rooms live in the graph; `ship->location` = a docking-bay room vnum; **not** in any star system (`space.c:4990-4993`) | vehicle parked in a "dock" room |
| Launch | `do_land`/`do_launch` set a state; the `update_space` tick runs a **state machine** `LAUNCH→LAUNCH_2→READY` (`space.c:759-762`); `launchship` calls `ship_to_starsystem`, extracts from room, seeds `vx/vy/vz` at the planet's dock coordinates + random heading (`space.c:4603-4708`) | vehicle traverses an exit from dock room → "space" room |
| Land | `do_land` requires a destination **within 200 coordinate units** (`space.c:4874-4910`); `landship` calls `ship_to_room(dock_vnum)` + `ship_from_starsystem` (`space.c:4946-4994`) | traverse an exit space → surface dock |
| The bridge | **a docking bay is a room vnum that is *also* a coordinate point in a system** (`doc1a`↔`p1x/y/z`). Landing = leave the coordinate world, bind interior to that room | an exit whose two ends are (space room) ↔ (surface room) |
| Ship-in-ship | land in a capital ship's `hanger` if within 200 units and bay open (`space.c:4859-4880`) | nested containment |

The transition is the whole trick: **the dock is the one object that lives in
both worlds** — a room you can stand in *and* a coordinate you can fly to.
Cross the 200-unit proximity threshold and the ship pops out of the
coordinate sidecar and re-attaches to the room graph.

## Mapping onto REALM — what's already softcode, what needs the sidecar

REALM's roadmap already asserts (line 21) that discrete space is rooms and
only continuous free-flight needs coordinates. SWR is a working existence
proof of exactly that split, and it lets us draw the line precisely.

**Buildable in REALM *today*, no kernel change (room-graph ships):**

- **Ship interiors you board and ride** — REALM's vehicle model already *is*
  SWR's interior-rooms + `do_board`, done better: true containment instead
  of vnum-matching, so "which ship am I in?" and "passengers ride along" are
  free rather than a per-command reverse scan.
- **The entire between-system layer.** SWR's galaxy is a coarse discrete
  graph and hyperspace is graph traversal. Model each **star system as a
  room** (or zone) and each **hyperspace lane as an exit**; "jump" is
  `move_through_exit` on the vehicle object. Jump-cost/`calculate` is
  softcode arithmetic over exit metadata.
- **Docking and landing** — the vehicle object traverses an exit from a
  "system"/"orbit" room to a surface dock room. Space↔ground is just a
  two-ended exit; nested hangars are nested containment.
- **The damage economy** — shields/hull/energy as scalar attrs, shield decay
  and autorecharge as `on_tick`, hit resolution via the dice primitives.
  Combat *without geometry* runs today.
- **Scanner readouts, telemetry, proximity chatter** — `do_radar`/`do_status`
  are command-driven text dumps; `echo_to_system`/`echo_to_cockpit` are
  per-viewer proximity messaging. REALM's `[[...]]` per-viewer render and
  two-pass propagation cover all of it. A "see outside" cockpit view is a
  per-viewer description reading the vehicle's current *room* — exactly the
  roadmap's line-19 note.

That already yields a complete **discrete** space game: fly between systems
by exits, dock at planets, crew multi-seat ships, fight with dice — all
softcode.

**Genuinely needs the coordinate sidecar (the reserved spatial primitive):**

Everything that depends on *two ships in the same place having a distance
that changes continuously*. On a room graph, ships in one "system" room are
co-located with no range between them. The sidecar is the minimum addition
that gives them one:

- **Range** — target/fire gating, "too far," "too close to jump," the
  200-unit docking approach, out-of-range weapons.
- **Heading + facing** — `do_trajectory` steering, `is_facing` forward-arc
  weapons, turn-time for big ships.
- **Homing missiles** — free coordinate entities that chase a moving target;
  these have a *position* and nothing else, so they are pure sidecar objects.
- **Gravity wells, orbit capture, fly-into-the-sun** — proximity rules on
  fixed named points inside the volume.

And SWR shows how *little* the sidecar is: **nine floats on the vehicle
GameObject** (position, heading, jump-target), **a "star system" object
holding a membership list plus a handful of fixed named points**, and **one
slow ticker that Euler-integrates position and does threshold comparisons.**
It is not a physics engine — no forces, no real collision (SWR's is
commented out), no relativity. Position += unit-heading × speed, once a
second; everything else is `abs(Δcoord) < threshold`. That is the whole
primitive REALM has been reserving.

The coordinate volume also wants two capabilities REALM's core would supply
(the roadmap's "coordinates + neighbor/range queries beside the room graph"):
a **range query** ("ships within R of me," for radar/target lists) and a
**membership set** per volume. Both are trivial over the sidecar; SWR just
walks a linked list each tick (`space.c:6966` scans, `space.c:6239` for
radar), which is fine at MUD ship counts.

## Steal-list for REALM's vehicle/space roadmap (ranked)

1. **The dual-identity ship: room-graph interior + optional coordinate
   sidecar, bridged by the dock.** This is the headline. Build ships as
   REALM containers today (interiors, boarding, crew, riding, docking, the
   between-system exit graph). Reserve the sidecar for *within-system*
   flight only. The **docking object that lives in both worlds** (a room
   that is also a coordinate) is the exact seam — design it first, because
   it is what lets you ship a discrete game now and bolt on continuous
   flight later without reworking the interiors.

2. **Keep the sidecar tiny and Euler.** When continuous space is finally
   built, copy SWR's proportions: position/heading/jump vectors on the
   vehicle, a system object with a membership list + named fixed points, a
   ~1 Hz integrate-and-threshold ticker. Resist a physics engine — SWR
   proves range comparisons carry a full space game.

3. **Heading = target − position, with turn-time as state.** `do_trajectory`
   (`space.c:5233`) is the cleanest steering idiom: pilots name a
   destination coordinate, the kernel derives the heading, and big ships
   spend N ticks in a "coming about" state. Cheap, readable, and it makes
   maneuverability a real stat.

4. **Missiles as first-class coordinate entities.** A homing projectile is
   the purest sidecar object — a position that chases a target and detonates
   on proximity (`space.c:351-423`). This is the clean test case for the
   sidecar's "object with coordinates but no room" concept.

5. **Scalar combat economy decoupled from geometry.** Steal the
   shield/hull/energy loop (`space.c:765-784`) as attrs + `on_tick`
   *independently* of the coordinate work — it gives REALM a playable ship
   fight on the room graph before the sidecar exists, and it slots in
   unchanged afterward.

6. **Reverse-lookup avoidance.** SWR's `ship_from_pilotseat`-style scans
   exist only because C has no containment graph. REALM should *not* port
   them — the containment edge already answers "which ship, which seat."
   Note it as an anti-pattern the architecture obviates.

## Where REALM is already ahead

Containment gives REALM, for free, three things SWR hand-codes: passengers
that truly ride (no static-interior fiction), "which ship am I in?" (no
per-command vnum scan), and nested hangars (nested containers). Its exit
graph *is* SWR's hyperspace/galaxy layer, done in softcode. And its
per-viewer `[[...]]` render is a stronger "see outside" than SWR's pushed
telemetry lines. REALM only lacks the one thing SWR actually needed
coordinates for — continuous intra-system range — and the roadmap already
names it correctly.

*Status: reference comparison, no decisions taken. Confirms roadmap line 21
— discrete space = rooms today, continuous free-flight = a small
nine-float + one-integrator sidecar, bridged to the graph by the dock
object. Revisit when a REALM game commits to real space play.*
