# 040. Zero-G compartment

> Checklist item 40 ([now]): *movement wards by action tag, custom $-verbs, themed remit*

**What you'll build:** A cargo bay in freefall, where ordinary walking
fails with drift flavor, leaving takes a `push <hatch>` off a bulkhead (a
Free Fall roll), and the room grows its own weightless verbs.

**Concepts:** `on_check` movement wards keyed on `has_atag('movement')`,
letting your own verbs through the ward with a custom action tag,
`move_to(enactor, ...)` with `$`-command consent, `$`-verbs hung on the
room itself, and an honest account of what softcode can and cannot
rewrite.

## How it works

A zero-G bay is a normal room with two softcode seams bolted around the
engine's own movement: a ward that refuses an ordinary walk out, and a
`push` verb that grants a tagged exception to anyone who rolls well. This
section explains where those seams sit, why walking cannot simply be
re-skinned, and how a room comes to own verbs the engine never shipped.

**Why you cannot just rewrite walking.** Builtin commands dispatch before
softcode `$`-triggers, so a room cannot shadow `go`, `say`, or `pose`, and
it cannot rewrite the engine's own movement text. What softcode owns
instead are the two seams around the builtin: the ward, an
[`on_check`](../design/action-phases.md) that vetoes the move before it
happens with any refusal text you like, and new vocabulary, verbs such as
`$push` and `$flail` that the engine does not have, so the room is free to
define them. Freefall play is therefore additive, because you add themed
verbs rather than re-skinning the ones that already exist.

The pieces:

1. **The ward.** Every move fires an `event:on_leave` check at the origin
   room, tagged `movement`, before anyone actually leaves. An `on_check`
   on the room turns that into a veto for players, and the
   [`block`](../reference/softcode.md#event-data-namespace) reason is the
   drift text the walker reads. Because wards match by action category,
   this one clause catches walking, fleeing, and following at once without
   naming any of them, since `flee` and a follower's cascade both travel
   the same movement path.

2. **The pass-through.** The `$push` verb relocates people with
   [`move_to`](../reference/softcode.md#fn-move_to)`(enactor, dest,
   tags=['zerog'])`. The extra `zerog` tag rides the same movement action,
   and the ward waves any tagged move past with its
   [`not has_atag('zerog')`](../reference/softcode.md#event-data-namespace)
   clause: your ward, your tag, your tunnel.
   ([`teleport_obj`](../reference/softcode.md#fn-teleport_obj) and the
   builder's `@teleport` force past wards anyway, so nobody strands
   themselves in the bay.)

3. **Consent.** A room script cannot normally relocate a player it does
   not own, but typing an object's `$`-command is deliberate interaction,
   and the engine grants exactly that: the enactor of a `$push` may be
   moved by it. A bystander cannot be shoved, because the pusher only ever
   pushes themselves.

4. **The roll.** Moving in freefall is a skill. A `freefall` `skill_def`
   (DX-based, untrained at -5) makes
   [`skill_check`](../reference/softcode.md#fn-skill_check)`(enactor,
   'freefall')` the gate between sailing cleanly and tumbling in place.

5. **Room-scoped verbs.** A `cmd_*` attribute on the room itself sits in
   every occupant's trigger search path, so no gadget object is needed and
   the room itself speaks freefall.

## Build it

The freefall skill comes first, as data the check engine reads once you
`@reload`. `stat = dexterity` and `penalty = -5` make it a DX-based skill
that untrained characters roll at DX minus five:

```text
@create freefall
@tag freefall = skill_def
@set freefall/stat = dexterity
@set freefall/penalty = -5
@reload
```

Now dig the bay off your workshop and step inside. The build ends in the
bay on purpose, because once the ward is live you leave the way everyone
does, by pushing:

```text
@dig Cargo Bay Zero-G = bay, aft
bay
@desc here = Cargo nets sag from every bulkhead and nothing agrees on which way is down.
```

The ward vetoes a walk out unless the move carries our tag. It gates on
`event:on_leave` deliberately, because this same `on_check` also runs for
arrivals, and blocking those would trap people out of the bay:

```text
@set here/on_check = '''
# on_leave only: this on_check also fires for arrivals, which must stay free
if atype == 'event:on_leave' and has_atag('movement') and not has_atag('zerog') and has_tag(actor, 'player'):
    block('You kick against nothing and drift in place. Grab a handhold and push <exit> instead.')
'''
```

The `$push` verb reads the wildcard with
[`trim`](../reference/softcode.md#fn-trim), finds the named hatch among
[`contents`](../reference/softcode.md#fn-contents)`(me)` by
[`has_tag`](../reference/softcode.md#fn-has_tag) and
[`name`](../reference/softcode.md#fn-name), rolls Free Fall, and then
either sails on a success or tumbles in place on a failure. The private
line goes to the pusher with
[`pemit`](../reference/softcode.md#fn-pemit), while
[`remit`](../reference/softcode.md#fn-remit) runs after the queued
[`move_to`](../reference/softcode.md#fn-move_to), so the launch line lands
in the bay once the pusher has already left it and only those still present
read it:

```text
@set here/cmd_push = '''
$push *:
nm = trim(arg0).lower()
ex = [e for e in contents(me) if has_tag(e, 'exit') and name(e) == nm]
if not ex:
    pemit(enactor, 'No handhold faces that way.')
elif skill_check(enactor, 'freefall'):
    move_to(enactor, get('#' + str(get_attr(ex[0], 'destination', ''))), tags=['zerog'])  # the zerog tag rides this move so the ward waves it through
    pemit(enactor, f'You coil, kick off, and sail through the {nm} hatch.')
    remit(me, f'{name(enactor)} kicks off a bulkhead and sails out through the {nm} hatch.')
else:
    pemit(enactor, 'You misjudge the kick and tumble; the hatch drifts past your fingers.')
    remit(me, name(enactor) + ' tumbles slowly in midair, pawing at nothing.')
'''
```

And one purely thematic verb, because a zero-G room without one is a waste
of a ceiling:

```text
@set here/cmd_flail = '''
$flail:
pemit(enactor, 'You windmill your arms. It achieves nothing, beautifully.')
remit(me, name(enactor) + ' windmills in place, going exactly nowhere.')
'''
```

## Try it

```text
aft
  You kick against nothing and drift in place. Grab a handhold and push <exit> instead.
flail
  You windmill your arms. It achieves nothing, beautifully.
push aft            (trained first: @set me/skill_freefall = 14)
  You coil, kick off, and sail through the aft hatch.
bay                 (walking IN is fine: you drift in through the hatch)
push aft            (untrained, on a bad roll)
  You misjudge the kick and tumble; the hatch drifts past your fingers.
```

Anyone else in the bay reads the third-person lines: the sail on a
success, the slow tumble on a failure. And `push mainmast` gets
`No handhold faces that way.`

## Going further

- **Magboots:** a wearable that `grants_tags` `magboots`, plus a ward
  clause `and not has_tag(actor, 'magboots')`, is gear that restores plain
  walking, the goggles pattern from the
  [dark room](038_dark_room.md).
- **Drift on failure:** on a tumble, `move_to` the pusher through a
  *random* exit instead of nowhere, since Newton does not care which hatch
  you meant.
- **Thrown things:** a `$toss <item> <exit>` verb using the same tagged
  pass-through for objects, zero-G cargo handling as a minigame.
- **A whole deck:** the ward and verbs are plain attributes, so `@clone`
  the pattern onto each compartment, or hang the `cmd_push` on a zone
  master so one copy serves the entire hulk (this room's ward stays
  per-room, so only these compartments are in freefall).
```