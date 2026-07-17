# 158. Mounts

> Checklist item 158 — now — *rider/mount pairing by containment, steering relayed through the mount, a view relay*

**What you'll build:** Rusty, a dun mare you can ride. `mount Rusty`
puts you in the saddle; `ride north` and she carries you off — you go
where you steer her, not the other way round. `dismount` sets you back
on your feet. Only one rider at a time.

**Concepts:** riding as **containment** — the rider *enters* the mount,
so the mount's moves carry them automatically; **consenting** `move_to`
to seat and unseat; **steering relayed** through the mount's own scripted
`move`; and an `ON_ARRIVE` **view relay** so the rider sees where they
land.

## How it works

**The saddle is containment.** The engine already carries an object's
contents when it moves — so the simplest true "carry" is to put the
rider *inside* the mount. `mount Rusty` runs `move_to(enactor, me)`:
you consented by typing the command, so the mount may seat you, and now
you're in Rusty's contents. When Rusty walks a room, you're still inside
her — carried, for free, no follow bookkeeping. (Compare the
[pet](065_pet.md), which *follows* you via `db.following`; a mount is the
inverse — you ride *it*.)

**Steering is a relayed move.** From the saddle, `ride north` runs *as
Rusty*: she scripted-`move`s north through the real movement pathway
(so locked and guarded exits judge the mare, and a rider can cross what
they'd steer a horse across). You came along inside her.

**Why the mount can't just write you.** An NPC can't set attributes on a
player or force them around — authority forbids it. Containment sidesteps
that entirely: the only player-touching op is the *consented* `move_to`,
which the rider authorized. Everything else Rusty does to herself.

**The rider needs eyes.** Tucked inside the mount, you don't hear the
room's messages — so Rusty's `ON_ARRIVE` (which fires on her, in the new
room) `pemit`s her rider the arrival line. One relay, and riding reads
right.

## Build it

A paddock and a trail to ride between:

```text
@dig The Paddock = paddock, out
paddock
@dig The Trail = trail, back
back
```

Rusty, and her four behaviors — mount, ride, the arrival relay, and
dismount:

```text
@create Rusty
@tag Rusty = npc
@desc Rusty = A patient dun mare, saddled and waiting.
drop Rusty
@set Rusty/cmd_mount = $mount *: (pemit(enactor, 'That is not Rusty.') if trim(arg0).lower() not in name(me).lower() else (pemit(enactor, 'Someone is already astride.') if V('rider') else (oemit(enactor, name(enactor) + ' swings up onto ' + name(me) + '.'), move_to(enactor, me), set_attr(me,'rider', '#'+enactor.id), pemit(enactor, 'You settle into the saddle. RIDE <direction> to go.'))))
@set Rusty/cmd_ride = $ride *: way = trim(arg0).lower(); (pemit(enactor, 'You are not riding ' + name(me) + '.') if V('rider') != '#'+enactor.id else (pose('bears ' + name(enactor) + ' ' + way + '.'), move(way)))
@set Rusty/on_arrive = (pemit(get(V('rider')), name(me) + ' bears you into ' + name(here) + '.') if V('rider') else None)
@set Rusty/cmd_dismount = $dismount: (pemit(enactor, 'You are not mounted.') if V('rider') != '#'+enactor.id else (del_attr(me,'rider'), move_to(enactor, loc(me)), oemit(enactor, name(enactor) + ' swings down off ' + name(me) + '.'), pemit(enactor, 'You dismount.')))
```

## Try it

```text
mount Rusty         -> You settle into the saddle. RIDE <direction> to go.
ride trail          -> "Rusty bears you into The Trail."
dismount            -> You dismount.   (you're standing on The Trail)
```

`@examine Rusty` shows her `rider` set while you're aboard and gone once
you drop down. A second person who tries `mount Rusty` while you ride
gets "Someone is already astride." Onlookers watch her leave and arrive
by her own name — she's a mount, but she's still a creature moving
through rooms.

## Going further

- **Whose horse:** `@lock/use Rusty = caller.id == owner.id` (or a
  `tamed_by` attribute) so only her handler may `mount` — the
  [pet](065_pet.md)'s ownership line.
- **Voice, not verbs:** add `^*whoa*` / `^*walk on*` [listen
  triggers](065_pet.md) so you can rein her with speech as well as
  `ride`.
- **A led mount:** for a pack animal that *follows* instead of carrying,
  set `following` on the mount (the [pet](065_pet.md) pattern) — the two
  models compose; a mule you lead until you climb on.
- **Fuller vision:** the relay sends a line; to give the rider the whole
  room, have `ON_ARRIVE` also `oob` the room's exits to their client,
  or relay the mount's room description attribute.
- **Mounted combat:** the rider is *in* Rusty, so a foe must target the
  mount first — the seed of a mount that soaks hits (compose with
  [tutorial 073](073_boss_phases.md)'s targeting).
