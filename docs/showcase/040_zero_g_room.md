# 040. Zero-G compartment

> Checklist item 40 — [now] — *movement wards by action tag, custom $-verbs, themed remit*

**What you'll build:** A cargo bay in freefall: ordinary walking fails
with drift flavor, leaving takes a `push <hatch>` off a bulkhead (a
Free Fall roll), and the room grows its own weightless verbs.

**Concepts:** `on_check` movement wards (`has_atag('movement')`),
letting your own verbs through the ward with a custom action tag,
`move_to(enactor, ...)` and $-command consent, `$`-verbs on the room
itself — and an honest look at what softcode can and can't rewrite.

## How it works

**The boundary first.** Builtin commands dispatch *before* softcode
`$`-triggers, so a zero-G room cannot shadow `go`, `say`, or `pose`, and
it cannot rewrite the engine's movement messages. What softcode *does*
own is the two seams around the builtin: the **ward** (an `on_check`
that vetoes the move before it happens, with any refusal text you like)
and **new vocabulary** (`$push`, `$flail` — verbs the engine doesn't
have, so the room gets them). Freefall emotes are *additive*: you add
themed verbs rather than re-skinning `pose`.

The pieces:

1. **The ward.** Movement fires an `event:on_leave` check at the origin
   room, tagged `movement`, before anyone moves. A one-line `on_check`
   on the room blocks it for players — the block *reason* is the drift
   flavor the walker reads. Wards block by category, so this catches
   walking, fleeing, and following without naming any of them.

2. **The pass-through.** The `$push` verb moves people with
   `move_to(enactor, dest, tags=['zerog'])` — the extra tag rides the
   same movement action, and the ward deliberately waves tagged moves
   past: `not has_atag('zerog')`. Your ward, your tag, your tunnel.
   (`teleport_obj` and the builder's `@teleport` force past wards
   anyway, so nobody bricks themselves into the bay.)

3. **Consent.** A room script can't normally relocate a player it
   doesn't own — but typing an object's `$`-command is deliberate
   interaction, and the engine grants exactly that: the *enactor* of a
   `$push` may be moved by it. Bystanders can't be shoved; the pusher
   pushes themselves.

4. **The roll.** Moving in freefall is a skill: a `freefall`
   `skill_def` (DX-based, untrained -5) makes `skill_check(enactor,
   'freefall')` the gate between sailing gracefully and tumbling in
   place.

5. **Room-scoped verbs.** `cmd_*` attributes on the room itself are in
   every occupant's trigger search path — no gadget object needed; the
   *room* speaks freefall.

## Build it

The skill, then the bay. (Note: the build ends *inside* the bay —
once the ward is set, you leave by pushing, like everyone else.)

```text
@create freefall
@tag freefall = skill_def
@set freefall/stat = dexterity
@set freefall/penalty = -5
@reload
@dig Cargo Bay Zero-G = bay, aft
bay
@desc here = Cargo nets sag from every bulkhead and nothing agrees on which way is down.
```

The ward — walking out is vetoed unless the move carries our tag:

```text
@set here/on_check = block('You kick against nothing and drift in place. Grab a handhold and push <exit> instead.') if atype == 'event:on_leave' and has_atag('movement') and not has_atag('zerog') and has_tag(actor, 'player') else None
```

The push verb: find the named hatch among the room's exits, roll Free
Fall, and either sail (a tagged `move_to`) or tumble. `remit` is queued
after the move, so the launch line lands in the bay after the pusher
has already left it:

```text
@set here/cmd_push = $push *: nm = trim(arg0).lower(); ex = [e for e in contents(me) if has_tag(e, 'exit') and name(e) == nm]; pemit(enactor, 'No handhold faces that way.') if not ex else ((move_to(enactor, get('#' + str(get_attr(ex[0], 'destination', ''))), tags=['zerog']), pemit(enactor, 'You coil, kick off, and sail through the ' + nm + ' hatch.'), remit(me, name(enactor) + ' kicks off a bulkhead and sails out through the ' + nm + ' hatch.')) if skill_check(enactor, 'freefall') else (pemit(enactor, 'You misjudge the kick and tumble; the hatch drifts past your fingers.'), remit(me, name(enactor) + ' tumbles slowly in midair, pawing at nothing.')))
```

And one purely thematic verb, because a zero-G room without one is a
waste of a ceiling:

```text
@set here/cmd_flail = $flail: pemit(enactor, 'You windmill your arms. It achieves nothing, beautifully.'); remit(me, name(enactor) + ' windmills in place, going exactly nowhere.')
```

## Try it

```text
aft
  You kick against nothing and drift in place. Grab a handhold and push <exit> instead.
flail
  You windmill your arms. It achieves nothing, beautifully.
push aft            (trained: @set me/skill_freefall = 14)
  You coil, kick off, and sail through the aft hatch.
bay                 (walking IN is fine - you drift in through the hatch)
push aft            (untrained, on a bad roll)
  You misjudge the kick and tumble; the hatch drifts past your fingers.
```

Anyone else in the bay reads the third-person lines — the sail on a
success, the slow tumble on a failure. And `push mainmast` gets
`No handhold faces that way.`

## Going further

- **Magboots:** a wearable that `grants_tags` `magboots`, and a ward
  clause `and not has_tag(actor, 'magboots')` — gear that restores
  plain walking, item 38's goggles pattern.
- **Drift on failure:** on a tumble, `move_to` the pusher through a
  *random* exit instead of nowhere — Newton doesn't care which hatch
  you meant.
- **Thrown things:** a `$toss <item> <exit>` verb using the same
  tagged pass-through for objects — zero-G cargo handling as a
  minigame.
- **A whole deck:** the ward and verbs are plain attributes — `@clone`
  the pattern onto each compartment, or hang the `cmd_push` on a
  zone master so one copy serves the entire hulk (this room's ward
  stays per-room: only *these* compartments are in freefall).
