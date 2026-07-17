# 176. Staff dashboard

> Checklist item 176 — [now] — *world-zone master, ON_CONNECT roster, ON_DEATH witness reading target/adata(), search_world() census, eval_attr() render, the honest presence/error boundary*

**What you'll build:** an `Ops Console` you install once and read with a
single word — `dashboard` — that prints station health at a glance:
uptime, who's online out of everyone rostered, a live world census, and a
rolling feed of recent incidents.

**Concepts:** the **world-zone master** as a station-wide console, an
**ON_CONNECT/ON_DISCONNECT presence roster** (the honest workaround for
softcode's missing presence query — from
[083](083_message_in_bottle.md)), `search_world()` as a census tool, a
witness that **reads the action's own data** (`target`, `adata()`) instead
of guessing from the enactor, `eval_attr()` for a tidy render helper,
staff gating by tag, and where
softcode's honest reach ends: the builtin `@stats` and the server log
own the engine internals softcode can't see.

## How it works

**One console, heard everywhere.** The console is crowned master of the
`zone:world` — so its `$dashboard` verb answers from any room on the
grid, and its `ON_*` hooks witness events happening anywhere in that
zone. That is the same Zone-Master-Room trick the
[PA system](078_pa_system.md) uses, turned inward: instead of speaking to
the station, this master *listens to* it.

**Presence is a roster the console keeps for itself.** REALM has no
softcode "who is online" primitive — sessions are invisible to scripts
(see the [message in a bottle](083_message_in_bottle.md) for the full
story). So the console does what the Harbormaster did: it hears
`event:connect` / `event:disconnect` from every world room and keeps an
`online` list of ids, move-to-front on connect, dropped on disconnect.
The dashboard re-verifies each id still resolves before counting it, so a
hard crash that strands a stale id can't inflate the number.

**The census is just `search_world()`.** Rooms, NPCs, and things are
counted by tag on demand — cheap, exact, and always current.

**Incidents are whatever you wire a hook to log.** The console's
`on_death` appends a line whenever anything dies on the world zone — and
*anything* means anything. The engine announces `combat:on_death` from
its one death path, so a mob cut down in a duel, an NPC finished off by a
poison tick or a landmine, and a player going down all reach this hook
alike; nothing has to be polled for.

**A witness reads the action, not just the actor.** An `ON_<EVENT>` hook
gets the same names an `on_check` ward has always had, so the feed asks
the death itself who fell rather than guessing:

- **`target`** is the victim. `enactor` is the *killer* — bound to the
  actor, as on every event — which is why the line reads `name(target)`.
  A death with no killer (a poison tick, a long fall) has no actor at
  all, and `name(enactor)` would be empty.
- **`adata('killer')`** is the killer's name, or nothing when the world
  did it. The line only appends `(by …)` when there is someone to blame.
- **`adata('fatal')`** separates a real death — an NPC, now a corpse —
  from a player merely knocked unconscious, so the board can say `death:`
  or `down:` honestly instead of reporting every KO as a fatality.

Point more `ON_*` hooks at the same list and the feed grows. **The honest
boundary:** softcode cannot read the engine's Python error stream or its
internal tick metrics — those live in the builtin **`@stats`** (tick
pacing, behavior load, scheduled waits, active combat) and in the server
log. The dashboard surfaces everything softcode *can* see; `@stats` is
its companion for the plumbing underneath.

## Build it

A control room on the world zone, and the console promoted to master:

```text
@dig The Operations Center = ops, out
ops
@zone here = world
@create Ops Console
drop Ops Console
@desc Ops Console = A wall of glass and telemetry. DASHBOARD prints station health at a glance.
@zone/master Ops Console = world
```

Stamp the boot time so uptime has an origin (a one-off `@eval` — it runs
softcode as you, the owner):

```text
@eval set_attr(get('Ops Console'), 'booted_at', now())
```

The presence roster and the incident feed — three witnesses:

```text
@set Ops Console/on_connect = set_attr(me, 'online', [i for i in (V('online') or []) if i != enactor.id] + [enactor.id])
@set Ops Console/on_disconnect = set_attr(me, 'online', [i for i in (V('online') or []) if i != enactor.id])
@set Ops Console/on_death = kind = 'death' if adata('fatal') else 'down'; by = adata('killer'); entry = f'{kind}: {name(target)} in {name(here)}' + (f' (by {by})' if by else ''); set_attr(me, 'incidents', ((V('incidents') or []) + [entry])[-20:])
```

The render helper and the gated verb that calls it:

```text
@set Ops Console/render = up = now() - V('booted_at', now()); on = [i for i in (V('online') or []) if get('#'+str(i))]; inc = V('incidents') or []; [pemit(enactor, ln) for ln in (['=== STATION OPS ===', f'uptime: {up}s since boot', f'online: {len(on)} / {len(search_world(tag="player"))} characters', f'world: {len(search_world(tag="room"))} rooms, {len(search_world(tag="npc"))} npcs, {len(search_world(tag="thing"))} things', '--- recent incidents ---'] + (inc[-5:] if inc else ['(none logged)']))]
@set Ops Console/cmd_dashboard = $dashboard: pemit(enactor, 'The ops console stays dark for you.') if not has_tag(enactor,'admin') else eval_attr(me, 'render')
```

`eval_attr(me, 'render')` runs `render` as a subroutine that still sees
`enactor` — the same helper-call idiom the
[custom channel](074_custom_channel.md) uses for `speak`.

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

The rat died with a name attached; Zeke went `down` rather than `death`
because a player who drops is unconscious, not gone — `adata('fatal')`
is what tells them apart.

A non-staff character gets nothing: `The ops console stays dark for
you.` Then reach past softcode into the engine itself:

```text
@stats
   -> Engine stats:
   ->   tick interval: ...s
   ->   behavior owners: ...
   ->   scheduled waits: ...
   ->   active combat encounters: ...
```

That's the division of labor: `dashboard` for the game's state, `@stats`
for the engine's.

## Going further

- **Wider incidents** — point `on_hitprcnt`, `on_attack`, or a custom
  `act()` event at the same `incidents` list and the feed covers boss
  fights, brawls, and alarms, not just deaths. Each carries its own
  payload for `adata()` to read — `on_attack` has `weapon`,
  `attacker_hp`, `defender_hp`; `on_damage` has `damage` and
  `damage_types` — so the lines can be as detailed as you like.
- **GMCP telemetry** — `oob(enactor, 'Ops.Health', {...})` pushes the
  same numbers to a client-side heads-up panel
  ([item 193](193_gmcp_oob.md) has the GMCP tour).
- **Paging the on-call** — combine with the
  [announcement system](181_announcements.md): a red incident `pemit`s
  every staffer on the grid, not just whoever is reading the board.
- **The real presence fix** — the roster is a workaround. If your game
  leans on presence, file for an engine `online_players()` primitive
  (audit gap **G4**); the day it lands, delete the two roster hooks.
