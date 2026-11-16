# 158. Mounts

> Checklist item 158 ([now]): *the `companions` feature's mounts: a bond, `mount`/`dismount`, riding lines, riding gates*

**What you'll build:** Rusty, a dun mare you can claim and ride. `claim
rusty` makes her yours, `mount Rusty` puts you in the saddle, every exit
you take carries you both ("Tam rides trail on Rusty."), and `dismount`
sets you back on your feet. Only her owner rides her, and only one rider
sits her at a time.

**Concepts:** a mount is a [companion](../guides/companions.md) tagged
`mount`; [`set_master`](../reference/softcode.md#fn-set_master) bonds her
from softcode; the engine's `mount`, `ride` and `dismount` commands do the
riding; and a `no_mount` tag closes a room to riders.

## How it works

A mount is a creature that follows you and that you can sit on. The
`companions` feature (MUD_PLAN step 13) already knows both halves, so the
build is a mare, one tag and one softcode line that makes her yours. This
section answers three questions: what makes a creature rideable, how
riding moves, and where a rider cannot go.

### What makes a creature rideable?

Two things: it is your companion (its `master` attribute holds your id),
and it carries the `mount` tag. `claim rusty` is a `$`-command on Rusty
that calls [`set_master`](../reference/softcode.md#fn-set_master)`(me,
enactor)`: she becomes your companion, which also makes her follow you
(the `following` attribute) and counts her against your companion limit.
`mount Rusty` then writes one attribute each way: `riding` on you and
`ridden_by` on her. Someone else's mare answers "Rusty isn't yours to
ride.", and a mare with a rider already up answers "Rusty already has a
rider."

### How does riding move?

You walk as always. Rusty follows you through the exit because she is
your companion, and the movement lines say you rode: the room you leave
sees "Tam rides trail on Rusty.", the room you reach "Tam arrives, riding
Rusty.", and Rusty's own steps print nothing. In a room, you are listed as
"Tam (riding Rusty)" and she is not listed on her own. In a game that
charges movement (Merc), each step is paid from her `move` pool, not
yours, and an exhausted mare refuses to go on.

### Where can a rider not go?

Anywhere tagged `no_mount`, and indoors (`sector:inside`) unless the game
sets `MOUNTS_INDOORS = True`: "You can't ride in there." Dismount and walk
in, and Rusty follows on foot. Nobody mounts in the middle of a fight, and
a rider who sleeps, is knocked out or dies comes off.

## Build it

A paddock and a trail to ride between, then Rusty herself, tagged as a
creature and a mount and dropped where a rider will find her:

```text
@dig The Paddock = paddock, out
paddock
@dig The Trail = trail, back
back
@create Rusty
@tag Rusty = npc
@tag Rusty = mount
@desc Rusty = A patient dun mare, saddled and waiting.
drop Rusty
```

`claim rusty` makes her yours. It refuses when she already has a master;
otherwise [`set_master`](../reference/softcode.md#fn-set_master) bonds her
to whoever typed it (after the script, so the line is shown first):

```text
@set Rusty/cmd_claim = '''
$claim rusty:
if master(me):
    pemit(enactor, name(me) + ' already answers to ' + name(master(me)) + '.')
elif set_master(me, enactor):
    pemit(enactor, name(me) + ' nuzzles your hand. She is yours to ride.')
else:
    pemit(enactor, 'You have too many followers to keep her.')
'''
```

A stable door you can lead her through but not ride through:

```text
@dig The Stable = stable, yard
stable
@tag here = no_mount
yard
```

## Try it

```text
claim rusty         -> Rusty nuzzles your hand. She is yours to ride.
mount Rusty         -> You mount Rusty.
trail               -> You ride trail on Rusty.   (the Paddock sees
                       "Tam rides trail on Rusty."; Rusty is on the Trail)
back                -> back in the Paddock, still riding
stable              -> You can't ride in there.
dismount            -> You dismount Rusty.
stable              -> you walk in; Rusty follows you on foot
companions          -> Rusty (mount)   here
                       You have 1 of 2 followers.
```

A second person who tries `mount Rusty` is told "Rusty isn't yours to
ride.", and their `claim rusty` "Rusty already answers to Tam."
`@examine Rusty` shows `master` and `following`, and `ridden_by` while you
are up.

## Going further

- **A paying mount:** under the Merc rules (`--system merc`), give her a
  `move` pool (`@set Rusty/move = 40`, `@set Rusty/max_move = 40`) and
  every step is paid from it; she regains it resting like anyone.
- **A stable that sells them:** a pet shop whose stock is tagged `mount`
  is a mount shop: put Rusty in a back room and give a shopkeeper
  `sells_pets` and `pet_stock` ([the guide](../guides/companions.md#pet-shops)).
- **Voice, not verbs:** a mount is a companion, so `order Rusty pose
  stamps and snorts.` works from the saddle, and [the pet](065_pet.md)'s
  `^listen` tricks work on her too.
- **Mounted combat:** a game system's `mounted_modifiers(rider, mount)`
  returns `{"attack": n, "defense": n}` to change a rider's rolls; the
  neutral system and Merc return nothing.
