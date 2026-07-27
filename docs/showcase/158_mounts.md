# 158. Mounts

> Checklist item 158 ([now]): *rider/mount pairing by containment, relayed steering, a view relay, dismount rules*

**What you'll build:** Rusty, a dun mare you can ride. `mount Rusty` puts
you in the saddle, `ride north` carries you off in the direction you steer
her, and `dismount` sets you back on your feet. Only one rider sits her at a
time.

**Concepts:** riding as **containment**, where the rider enters the mount so
the mount's own moves carry them; a **consented** [`move_to`](../reference/softcode.md#fn-move_to)
to seat and unseat; **steering relayed** through the mount's scripted
[`move`](../reference/softcode.md#script-commands-simple-scripts-cmd-output-lines);
and an [`ON_ARRIVE`](../reference/softcode.md#lifecycle-hooks) **view relay**
so the rider sees where they land.

## How it works

A mount is a creature you climb inside. Seating a rider puts them in the
mount's contents, so every room the mount walks takes the rider along, and
steering is just the mount moving itself while you sit within it. This
section answers four questions: where the rider actually stands, how one
command steers the mount, why the mount reaches only itself, and how the
rider still watches the world go by.

### Where does the rider stand?

Inside the mount. The engine already carries an object's contents when that
object moves, so the simplest true carry is to put the rider in the mount's
contents. `mount Rusty` runs [`move_to`](../reference/softcode.md#fn-move_to)`(enactor, me)`:
you consented by typing the command, which lets the mount seat you, and now
you are in Rusty's contents. When Rusty walks a room you ride along, with no
follow bookkeeping. Compare the [pet](065_pet.md), which *follows* you
through its `following` attribute; a mount is the inverse, since you ride
inside it.

### How does one command steer the mount?

From the saddle, `ride north` runs *as Rusty*: her script calls
[`move`](../reference/softcode.md#script-commands-simple-scripts-cmd-output-lines)`(way)`,
so she walks north through the real movement pathway. Locked and guarded
exits judge the mare, and you travel wherever she goes because you are inside
her.

### Why does the mount touch only itself?

An NPC has no authority to write a player's attributes or shove a player
around, so a mount that tried to relocate its rider by force would be
refused. Containment sidesteps that entirely: the one player-touching
operation is the *consented* `move_to` the rider authorized by typing
`mount`. Everything after that, Rusty does to herself.

### How does the rider still see the room?

Tucked inside the mount, the rider misses the room's own arrival lines, so
Rusty relays them. Her [`ON_ARRIVE`](../reference/softcode.md#lifecycle-hooks)
hook fires on her when she reaches a new room, and it forwards the arrival
line to whoever is riding with [`pemit`](../reference/softcode.md#fn-pemit).
`ON_ARRIVE` is the mover's own hook, firing on the object that moved rather
than on every object in the destination, so it needs no `target` guard and a
second mare standing by stays silent.

## Build it

A paddock and a trail to ride between, then Rusty herself, tagged and
dropped where a rider will find her:

```text
@dig The Paddock = paddock, out
paddock
@dig The Trail = trail, back
back
@create Rusty
@tag Rusty = npc
@desc Rusty = A patient dun mare, saddled and waiting.
drop Rusty
```

`mount` seats a consenting rider. It rejects a name that is not hers, refuses
a second rider while one is up, then announces the mount, moves the rider
inside her, and records who is aboard:

```text
@set Rusty/cmd_mount = '''
$mount *:
if trim(arg0).lower() not in name(me).lower():
    pemit(enactor, 'That is not Rusty.')
elif V('rider'):
    pemit(enactor, 'Someone is already astride.')
else:
    oemit(enactor, name(enactor) + ' swings up onto ' + name(me) + '.')
    move_to(enactor, me)                       # consented: the rider typed this command, so the mount may seat them
    set_attr(me, 'rider', '#' + enactor.id)
    pemit(enactor, 'You settle into the saddle. RIDE <direction> to go.')
'''
```

`ride` steers from the saddle. It confirms the enactor is the current rider,
then poses the mare's stride and walks her the given way, carrying the rider
inside her:

```text
@set Rusty/cmd_ride = '''
$ride *:
way = trim(arg0).lower()
if V('rider') != '#' + enactor.id:
    pemit(enactor, 'You are not riding ' + name(me) + '.')
else:
    pose('bears ' + name(enactor) + ' ' + way + '.')
    move(way)
'''
```

`ON_ARRIVE` is the view relay. It fires on Rusty in each new room and
forwards the arrival line to her rider, so the person in her contents learns
where they landed:

```text
@set Rusty/on_arrive = '''
if V('rider'):
    pemit(get(V('rider')), name(me) + ' bears you into ' + name(here) + '.')
'''
```

`dismount` unseats the rider. It confirms the enactor is aboard, clears the
rider mark, sets them down in Rusty's own room with a consented `move_to`,
and announces the dismount:

```text
@set Rusty/cmd_dismount = '''
$dismount:
if V('rider') != '#' + enactor.id:
    pemit(enactor, 'You are not mounted.')
else:
    del_attr(me, 'rider')
    move_to(enactor, loc(me))                  # set the rider down in the room Rusty stands in
    oemit(enactor, name(enactor) + ' swings down off ' + name(me) + '.')
    pemit(enactor, 'You dismount.')
'''
```

## Try it

```text
mount Rusty         -> You settle into the saddle. RIDE <direction> to go.
ride trail          -> "Rusty bears you into The Trail."
dismount            -> You dismount.   (you are standing on The Trail)
```

`@examine Rusty` shows her `rider` set while you are aboard and gone once you
drop down. A second person who tries `mount Rusty` while you ride gets
"Someone is already astride." Onlookers watch her leave and arrive by her
own name, because she is a mount yet still a creature moving through rooms.

## Going further

- **Whose horse:** `@lock/use Rusty = caller.id == owner.id` (or a
  `tamed_by` attribute) so only her handler may `mount`, since the `use`
  lock gates a `$`-command. This is the [pet](065_pet.md)'s ownership line.
- **Voice, not verbs:** add `^*whoa*` and `^*walk on*`
  [listen triggers](065_pet.md) so you rein her with speech as well as
  `ride`.
- **A led mount:** for a pack animal that *follows* instead of carrying, set
  `following` on the mount (the [pet](065_pet.md) pattern). The two models
  compose into a mule you lead until you climb on.
- **Fuller vision:** the relay sends one line; to give the rider the whole
  room, have `ON_ARRIVE` also [`oob`](../reference/softcode.md#fn-oob) the
  room's exits to their client, or relay the mount's room description.
- **Mounted combat:** the rider sits inside Rusty, so a foe in the room
  faces the mount, not the person in the saddle. Compose with
  [tutorial 073](073_boss_phases.md)'s targeting for a mount that takes the
  hits.
