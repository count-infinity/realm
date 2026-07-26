# 044. Instanced room

> Checklist item 44 ([now]): *enter_instance(), ephemeral areas, idle reaping*

**What you'll build:** A motel suite that every guest gets a private copy of.
Walk the same door and you arrive in your own rooms. Instancing is native, so
this tutorial is the builder workflow, not a mechanism you assemble by hand.

**Concepts:** template zones (the `instance_template` and `instance_entry`
tags), portal exits with a deferred destination (`dest_resolver = instance`),
solo versus shared mode, an idle time-to-live (TTL) and the reaper, the scripted
[`enter_instance`](../reference/softcode.md#fn-enter_instance) entry point, and
the `ephemeral` tag that keeps copies out of the database.

## How it works

The finished shape is one authored suite that nobody visits directly plus one
doorway that, on each walk, hands the walker a fresh private copy of that suite
(or reuses the copy they already have). This section answers what a template is,
what the doorway actually does, why the copies never pile up, and how a script
can send someone in without a portal at all.

REALM collapses instancing into a single primitive. It materializes a real copy
of a template area on demand, tags every piece of the copy `ephemeral` so it
never persists, and reaps the copy once it has sat empty past its TTL. The
builder's whole job is authoring the template and one doorway.

### What makes a zone instantiable

The template is an ordinary zone. You dig its rooms and group them with `@zone`,
then add two opt-in tags. The `instance_template` tag on a room marks the whole
zone as instantiable, so nothing is ever copied by accident, and `instance_entry`
marks the room arrivals land in. Keep the template unlinked from the street so
that only copies are ever visited. A static exit inside the template (the `lobby`
door back to the real world) is safe to author, because a destination that points
at a room outside the zone resolves against the live world in every copy, so each
instance's `lobby` leads home.

### What the doorway does when you walk it

The doorway is a real exit, the same kind of tagged object that a
[portal pair](033_portal_pair.md) builds by hand. Instead of a fixed
`destination` it carries `dest_resolver = instance` and
`instance_template = <zone>`, which defers its destination to the instance
resolver. Walking it is a normal traversal, so locks, wards, `on_enter`, and the
follower cascade all run unchanged. The resolver materializes your copy on the
first walk and reuses it on the next.

Mode decides what happens to a party. With `instance_mode = shared`, anyone
following you through the door is routed into your copy, which is how you build a
party dungeon. With the default `instance_mode = solo`, a follower is refused at
the threshold and left behind rather than handed a copy, so a solo instance stays
solo. Someone who walks the door on their own always gets their own copy.

### Why the copies never pile up

Every cloned room and prop is tagged `ephemeral`. It is registered live but never
written to the database, so no copy survives a reboot, and anyone still inside one
at world-load is relocated home. When a copy has sat empty past its `instance_ttl`
seconds, the reaper destroys it and evacuates any straggler to the return room
(the portal's own room by default, or a room you name). Reaped means gone, so
re-walking the door builds a fresh copy rather than reopening your old one.

### Sending someone in without a portal

The same machinery is callable from softcode as
[`enter_instance`](../reference/softcode.md#fn-enter_instance)`(player, template,
...)`, which places the player the way [`move_to`](../reference/softcode.md#fn-move_to)
does. It is gated by consent: a player is sent in only when the executor controls
them or the player is the enactor who typed the command. That is what lets a
front-desk clerk check a guest in without owning the guest, since typing the
clerk's `$check in` command is the guest's own consent.

## Build it

Author the template first. Dig the suite, stand in it, group it into the `suite`
zone, and opt it in with the two tags. The same room is both the entry room and
the template-marked room, so it takes both tags:

```text
@dig Dust Motel Suite
@teleport me = Dust Motel Suite
@zone here = suite
@tag here = instance_template
@tag here = instance_entry
```

Give it a description, then open a static exit back to the real world. The
`lobby` exit points at The Workshop, a room outside the `suite` zone, so it keeps
leading there in every copy:

```text
@desc here = Bed, basin, and a window painted shut. Not much, but tonight it is yours alone.
@open lobby = The Workshop
```

Add the second room. `@dig <name> = <there>, <back>` digs the washroom and links
it both ways, then walk in to zone it into `suite` and walk back out, so the whole
suite is one zone the copy can carry along:

```text
@dig Suite Washroom = washroom, out
washroom
@zone here = suite
out
```

Now the doorway, back in the lobby. An exit is just an exit-tagged object, so
create one, tag it `exit`, and drop it into the room:

```text
@teleport me = The Workshop
@create suite door
@tag suite door = exit
drop suite door
```

Configure the door to defer its destination to the instance resolver. Setting
`dest_resolver = instance` is what turns an ordinary exit into a portal, and
`instance_template` names the zone to copy. The `solo` mode keeps each guest
private, and the TTL sets the empty-idle seconds before the reaper collects a
copy:

```text
@set suite door/dest_resolver = instance
@set suite door/instance_template = suite
@set suite door/instance_mode = solo
@set suite door/instance_ttl = 600
```

Finally the scripted alternative, a clerk whose `$check in` command does the same
job from softcode. The body is more than one statement, so it is a `'''` heredoc
block: it sends the enactor into their suite and then confirms with a private
[`pemit`](../reference/softcode.md#fn-pemit):

```text
@create desk clerk
drop desk clerk
@set desk clerk/cmd_checkin = '''
$check in:
# reuses the guest's copy if they have one, else materializes it
enter_instance(enactor, 'suite', mode='solo', return_room=here, idle_ttl=600)
pemit(enactor, 'The clerk slides a brass key across the desk.')
'''
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

Have a friend walk `suite door` and they arrive in a different Dust Motel Suite:
same text, separate rooms, and you never see each other. Typing `check in` at the
clerk lands you in your copy too, and it reuses rather than duplicates. Inside,
`@examine here` lists the copy's tags, including `ephemeral` and an
`instance:suite:<your id>` tag that literally carries your id. Leave it empty for
ten minutes and the reaper removes it, so your next visit is freshly made.

## Going further

- **A party dungeon:** set `@set suite door/instance_mode = shared` and have the
  group `follow` the leader through. One copy is made, the whole party is routed
  in, and non-followers are bounced.
- **Gate the door:** the template entry room's `enter` lock is checked before
  anything is copied, so an `@lock`-style key or role check on that room gates the
  instance.
- **Persistent-feeling props:** copies are disposable by design, so to let a guest
  keep something, add a checkout `$`-command that moves it into their inventory
  before the reaper's evacuation.
- **Story rooms:** call
  [`enter_instance`](../reference/softcode.md#fn-enter_instance) from a dialogue
  tree ([tutorial 067](067_dialogue_tree_npc.md)) to drop a player into a private
  flashback scene, an instance used as a cutscene and reaped when the scene ends.
```
