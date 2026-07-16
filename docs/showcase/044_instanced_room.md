# 044. Instanced room

> Checklist item 44 — [now] — *enter_instance(), ephemeral areas, idle reaping*

**What you'll build:** A motel suite that every guest gets a private
copy of — walk the same door, arrive in your own rooms. Instancing is
**native**: this tutorial is the builder workflow, not a mechanism you
construct.

**Concepts:** template zones (`instance_template` / `instance_entry`
tags), portal exits with deferred destinations (`dest_resolver =
instance`), solo vs shared mode, idle TTL and reaping, the
`enter_instance()` softcode seam, `ephemeral` (copies never persist).

## How it works

REALM collapses instancing into one primitive: *materialize a real copy
of a template area on demand, tag every piece `ephemeral` so it never
persists, and reap it once it's sat empty past its TTL.* The builder's
whole job is authoring the template and one doorway:

1. **The template is a normal zone** — dig rooms, `@zone` them
   together — plus two opt-in tags: `instance_template` on a room
   marks the zone as instantiable (nothing instances by accident), and
   `instance_entry` marks where arrivals land. Keep the template
   unlinked from the street so only copies are ever visited.

2. **The doorway is a real exit with a deferred destination.** Instead
   of `destination`, give it `dest_resolver = instance` and
   `instance_template = <zone>`. Walking it is a *normal traversal* —
   locks, wards, and follower cascades all apply — that materializes
   your copy on first walk and **reuses it** on the next. `instance_mode
   = shared` routes your followers into *your* copy (a party
   dungeon); the default `solo` bounces them to get their own.

3. **Copies are ephemeral and reaped.** Every cloned room and prop is
   tagged `ephemeral` — registered live, never written to the
   database, so no copy survives a reboot (players left inside are
   relocated on world-load). When a copy has sat *empty* past
   `instance_ttl` seconds, the reaper destroys it; stragglers are
   evacuated to the portal room (or an explicit return room). Reaped
   means *gone* — re-walking materializes a fresh copy, not your old
   mess.

4. **The scripted seam** is `enter_instance(player, template, ...)` —
   same machinery, callable from any trigger. A `$`-command's enactor
   consents by typing it, so a front-desk clerk can check guests in
   without owning them.

## Build it

Author the template — a two-room suite, zoned, opted in, with a static
exit back to the lobby (static destinations copy as-is, so every
instance's `lobby` leads home):

```text
@dig Dust Motel Suite
@teleport me = Dust Motel Suite
@zone here = suite
@tag here = instance_template
@tag here = instance_entry
@desc here = Bed, basin, and a window painted shut. Not much - but tonight, it is yours alone.
@open lobby = The Workshop
@dig Suite Washroom = washroom, out
washroom
@zone here = suite
out
```

Back in the lobby, the portal exit (an exit is just an exit-tagged
object; `@dig`'s exits are the same thing made for you):

```text
@teleport me = The Workshop
@create suite door
@tag suite door = exit
drop suite door
@set suite door/dest_resolver = instance
@set suite door/instance_template = suite
@set suite door/instance_mode = solo
@set suite door/instance_ttl = 600
```

And the scripted alternative — a clerk whose `$check in` does the same
thing from softcode:

```text
@create desk clerk
drop desk clerk
@set desk clerk/cmd_checkin = $check in: enter_instance(enactor, 'suite', mode='solo', return_room=here, idle_ttl=600); pemit(enactor, 'The clerk slides a brass key across the desk.')
```

## Try it

```text
suite door
  Dust Motel Suite
  Bed, basin, and a window painted shut. ...
washroom            <- the whole zone was copied, connections intact
out
lobby               <- the authored exit leads back to the real world
suite door          <- ...and the SAME copy is waiting for you
```

Have a friend walk `suite door`: they arrive in a *different* Dust
Motel Suite — same text, separate rooms; you'll never see each other.
`check in` at the clerk lands you in your copy too (it reuses rather
than duplicates). `@examine here` inside shows the `ephemeral` tag and
an `instance:suite:<your id>` tag — the copy literally has your name
on it. Leave it empty for ten minutes and the reaper quietly removes
it; your next visit is freshly made.

## Going further

- **A party dungeon:** `@set suite door/instance_mode = shared` and
  have the group `follow` the leader through — one copy, whole party
  routed in, stragglers bounced.
- **Gate the door:** the template entry room's `enter` lock is checked
  *before* anything materializes — `@lock`-style key or role gating on
  the room gates the instance.
- **Persistent-feeling props:** copies are disposable by design; to
  let guests keep something, have a checkout `$`-command move it to
  their inventory before the reap does its evacuation.
- **Story rooms:** `enter_instance` from a dialogue tree
  ([tutorial 067](067_dialogue_tree_npc.md)) drops a player into a
  private flashback scene — instances as cutscenes, reaped when the
  scene ends.
