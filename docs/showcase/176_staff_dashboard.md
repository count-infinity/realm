# 176. Staff dashboard

> Checklist item 176 ([now]): *world-zone master console, ON_CONNECT/ON_DISCONNECT presence roster, ON_DEATH witness reading target and adata(), search_world() census, eval_attr() render helper, @stats engine boundary*

**What you'll build:** an `Ops Console` you install once and read with a
single word, `dashboard`, that prints station health at a glance: uptime,
who is online out of everyone rostered, a live world census, and a rolling
feed of recent incidents.

**Concepts:** a [world-zone master](078_pa_system.md) as a station-wide
console; an [`ON_CONNECT`/`ON_DISCONNECT`](../reference/softcode.md#lifecycle-hooks)
presence roster (the honest workaround for softcode's missing presence
query, from the [message in a bottle](083_message_in_bottle.md));
[`search_world()`](../reference/softcode.md#fn-search_world) as a census
tool; a witness that reads the action's own data
([`target`](../reference/softcode.md#guard-on-target) and
[`adata()`](../reference/softcode.md#event-data-namespace)) rather than
guessing from the enactor;
[`eval_attr()`](../reference/softcode.md#fn-eval_attr) for a tidy render
helper; staff gating by tag; and where softcode's reach ends, since the
builtin `@stats` and the server log own engine internals softcode never
sees.

## How it works

The finished console is one object standing in a control room, crowned
master of the world zone, that answers a single `dashboard` command with a
five-part report. This section explains how one object hears the whole
station, how it knows who is online when scripts have no session list, and
how one death-witness turns every kill on the grid into a feed line. It
closes with the boundary: what the console reads, and what only the engine
can report.

### How one object hears the whole station

The console is crowned master of the `zone:world` zone, so its `$dashboard`
verb answers from any room tagged into that zone, and its `ON_*` hooks
witness events happening in every room of the zone. A zone master shares its
zone tag, and REALM consults the masters of the room you stand in for both
`$`-command triggers and event witnessing, so one object listens for the
whole zone. That world zone is REALM's stand-in for a global command room
until a Master Room lands, so tag every room a staffer should read from into
it. This is the same zone-master trick the [PA system](078_pa_system.md)
uses, turned inward: instead of speaking to the station, this master listens
to it.

### How the console knows who is online

REALM has no softcode "who is online" primitive, because sessions are
invisible to scripts (the [message in a bottle](083_message_in_bottle.md)
tells the full story). So the console keeps its own roster: it hears
`event:connect` and `event:disconnect` from every world room and maintains
an `online` list of ids, de-duplicated and appended on connect, dropped on
disconnect. When it prints, it re-verifies that each id still resolves to a
live object with [`get`](../reference/softcode.md#fn-get) before counting
it, so a hard crash that strands a stale id leaves the count honest rather
than inflated.

### The census is just `search_world()`

Rooms, NPCs, and things are counted by tag on demand with
[`search_world()`](../reference/softcode.md#fn-search_world), which is
cheap, exact, and always current, so no separate tally has to be kept in
step with the world.

### How a witness reads the action, not just the actor

The console's `on_death` appends a line whenever anything dies on the world
zone, and *anything* means anything. The engine announces `combat:on_death`
from its one death path, so a mob cut down in a duel, an NPC finished off by
a poison tick or a landmine, and a player going down all reach this hook
alike, and nothing has to be polled for. An
[`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks) hook gets the same
names an `on_check` ward does, so the feed asks the death itself who fell
rather than guessing:

- [`target`](../reference/softcode.md#guard-on-target) is the victim, while
  `enactor` is the *killer*, bound to the actor as on every event, which is
  why the line reads `name(target)`. A death with no killer (a poison tick,
  a long fall) has no actor at all, so `name(enactor)` would be empty.
- [`adata('killer')`](../reference/softcode.md#event-data-namespace) is the
  killer's name, or nothing when the world did it, so the line only appends
  `(by ...)` when there is someone to blame.
- `adata('fatal')` separates a real death (an NPC, now a corpse) from a
  player merely knocked unconscious, so the board says `death:` or `down:`
  honestly instead of reporting every knockout as a fatality.

The console's three witnesses (`on_connect`, `on_disconnect`, `on_death`)
are all **global witnesses**, so none takes a
[`if target is me:` guard](../reference/softcode.md#guard-on-target): the
console is watching everyone on purpose, which is exactly the deliberate
exception to the guard rule. Point more `ON_*` hooks at the same list and
the feed grows.

### Where softcode stops and the engine begins

Softcode reads the world, not the runtime. The engine's internal tick
metrics (tick pacing, behavior load, scheduled waits, active combat) live in
the builtin `@stats`, and its Python error stream lives in the server log.
The dashboard surfaces everything softcode sees, and `@stats` is its
companion for the plumbing underneath.

## Build it

Dig a control room, tag it into the world zone, and drop in the console.
Promoting it to master crowns it with both the `zone:world` and
`zone_master` tags, so it hears the whole zone:

```text
@dig The Operations Center = ops, out
ops
@zone here = world
@create Ops Console
drop Ops Console
@desc Ops Console = A wall of glass and telemetry. DASHBOARD prints station health at a glance.
@zone/master Ops Console = world
```

Stamp the boot time so uptime has an origin. This is a one-off
[`@eval`](../reference/softcode.md#fn-now) that runs softcode as you, the
owner:

```text
@eval set_attr(get('Ops Console'), 'booted_at', now())
```

The presence roster is two single-statement witnesses. Each rewrites the
`online` list of ids: connect removes any stale copy of the enactor's id and
appends it, disconnect just removes it. Reading `V('online')` off `me` keeps
the roster on the console itself:

```text
@set Ops Console/on_connect = set_attr(me, 'online', [i for i in (V('online') or []) if i != enactor.id] + [enactor.id])
@set Ops Console/on_disconnect = set_attr(me, 'online', [i for i in (V('online') or []) if i != enactor.id])
```

The incident feed is the death-witness. It labels the line `death` or `down`
from `adata('fatal')`, names the victim with `target`, appends the killer
only when there is one, and trims the running list to its last twenty
entries. It takes no `target` guard because a zone master is a deliberate
global witness:

```text
@set Ops Console/on_death = '''
# Global zone-master witness: no `if target is me` guard, it watches every death.
kind = 'death' if adata('fatal') else 'down'
by = adata('killer')
entry = f'{kind}: {name(target)} in {name(here)}'
if by:
    entry = entry + f' (by {by})'      # only blame a named killer
incidents = (V('incidents') or []) + [entry]
set_attr(me, 'incidents', incidents[-20:])
'''
```

The render helper builds the five-part report. It computes uptime, re-counts
only the online ids that still resolve, runs the census with `search_world`,
and prints each line with [`pemit`](../reference/softcode.md#fn-pemit):

```text
@set Ops Console/render = '''
up = now() - V('booted_at', now())
online = [i for i in (V('online') or []) if get('#' + str(i))]   # drop ids that no longer resolve
incidents = V('incidents') or []
lines = ['=== STATION OPS ===',
         f'uptime: {up}s since boot',
         f'online: {len(online)} / {len(search_world(tag="player"))} characters',
         f'world: {len(search_world(tag="room"))} rooms, {len(search_world(tag="npc"))} npcs, {len(search_world(tag="thing"))} things',
         '--- recent incidents ---']
lines = lines + (incidents[-5:] if incidents else ['(none logged)'])
for ln in lines:
    pemit(enactor, ln)
'''
```

The gated verb runs the helper for staff and turns everyone else away. A
`$`-command on a world-zone master needs no `target` guard, since it fires
only for the person who typed it:

```text
@set Ops Console/cmd_dashboard = '''
$dashboard:
if has_tag(enactor, 'admin'):
    eval_attr(me, 'render')
else:
    pemit(enactor, 'The ops console stays dark for you.')
'''
```

[`eval_attr(me, 'render')`](../reference/softcode.md#fn-eval_attr) runs
`render` as a subroutine that still sees `enactor`, the same helper-call
idiom the [custom channel](074_custom_channel.md) uses for `speak`, since
`eval_attr` runs as the caller and leaves the enactor bound.

## Try it

As two players connect, Kess kills a rat and Zeke is dropped by something
nameless, a staffer reads the board:

```text
dashboard
   -> === STATION OPS ===
   -> uptime: 42s since boot
   -> online: 2 / 3 characters
   -> world: 1 rooms, 0 npcs, 0 things
   -> --- recent incidents ---
   -> death: a rat in The Operations Center (by Kess)
   -> down: Zeke in The Operations Center
```

The rat died with a name attached, while Zeke went `down` rather than
`death` because a player who drops is unconscious, not gone, and
`adata('fatal')` is what tells them apart.

A non-staff character gets nothing but `The ops console stays dark for
you.` Then reach past softcode into the engine itself:

```text
@stats
   -> Engine stats:
   ->   tick interval: ...s (scheduler resolution)
   ->   world beat: ...s (ambient/effect tempo; combat runs on each encounter's beat)
   ->   behavior owners: ...
   ->   scheduled waits: ...
   ->   active combat encounters: ...
```

That is the division of labor: `dashboard` for the game's state, `@stats`
for the engine's.

## Going further

- **Wider incidents.** Point `on_hitprcnt`, `on_attack`, or a custom
  [`act()`](../reference/softcode.md#fn-act) event at the same `incidents`
  list and the feed covers boss fights, brawls, and alarms, not just deaths.
  Each carries its own payload for `adata()` to read (`on_attack` has
  `weapon`, `attacker_hp`, `defender_hp`; `on_damage` has `damage` and
  `damage_types`), so the lines can be as detailed as you like.
- **GMCP telemetry.** A single
  [`oob(enactor, 'Ops.Health', {...})`](../reference/softcode.md#fn-oob)
  pushes the same numbers to a client-side heads-up panel (the
  [GMCP tour](193_gmcp_oob.md) walks through it).
- **Paging the on-call.** Combine with the
  [announcement system](181_announcements.md) so a red incident `pemit`s
  every staffer on the grid, not just whoever is reading the board.
- **The real presence fix.** The roster is a workaround. If your game leans
  on presence, file for an engine `online_players()` primitive (audit gap
  **G4**); the day it lands, delete the two roster hooks.

For the propagation model behind these witnesses, see
[the event architecture](../architecture/events.md) and the guided
[event bus tour](245_event_bus_tour.md).
