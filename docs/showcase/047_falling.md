# 047. Falling between rooms

> Checklist item 47 ([now]): *skill gates, teleport_obj, forced movement*

**What you'll build:** A cliffside ledge that demands a Climbing roll from
everyone who steps onto it. Fail, and you drop to the gully below, taking 2d6
from the landing, with a guard so one bad step cannot cascade into an infinite
ping-pong.

**Concepts:** [`ON_ENTER`](../reference/softcode.md#lifecycle-hooks) as a skill
gate, [`teleport_obj`](../reference/softcode.md#fn-teleport_obj) forced movement
and room-owner relocation authority,
[`damage`](../reference/softcode.md#fn-damage) timing, message and move queue
ordering, and a time-keyed reentrancy guard.

## How it works

The finished ledge is a room whose arrival hook rolls a skill check against
everyone who walks in. A trained climber reads one line and stays; an untrained
one is dropped into the gully below, hurt by the landing, while the ledge
narrates the fall to whoever is left standing on it. A stamp on the room keeps
a climber who scrambles straight back up from being re-rolled and dropped again.
This section answers four questions: where the gate lives and who it tests, what
actually moves the faller, why the messages and the move come out in the right
order, and how the reentrancy guard stops a loop.

### Where the gate lives and who it tests

The gate is the ledge's own [`ON_ENTER`](../reference/softcode.md#lifecycle-hooks)
hook. A room's `ON_ENTER` fires for *every* arrival, with the room as the hook's
target and the mover as `enactor` (this is the room case of the
[`target` guard](../reference/softcode.md#guard-on-target): a room's own hook is
already scoped to the room, so the filter you write is on the *enactor*, not
`if target is me`). The hook rolls
[`skill_check`](../reference/softcode.md#fn-skill_check)`(enactor, 'climbing', -2)`.
Climbing is a built-in GURPS skill (DX-based, defaulting to dexterity minus 5),
so no `skill_def` object is needed. A
[`has_tag`](../reference/softcode.md#fn-has_tag)`(enactor, 'player')` filter keeps
the test on players, so a shoved crate or a wandering NPC crosses the ledge
without losing its footing.

### What moves the faller

The fall is a [`teleport_obj`](../reference/softcode.md#fn-teleport_obj) call.
`teleport_obj` is the forced form of
[`move_to`](../reference/softcode.md#fn-move_to) (it is exactly
`move_to(force=True)`): the force flag tunnels past `on_check` wards, because you
do not get a *choice* about falling, while still honoring the destination's
locks. The room is allowed to relocate the faller because of room-owner
relocation authority, which is Penn's `tport_control_ok`: whoever owns a room may
move what stands in it, a weaker power than full control, which is why the fall
works without an admin owner. It also means falls only work in *owned* rooms,
which is true of anything you dug.

### Why the messages and the move land in order

Softcode world operations and messages are queued and run after the script, in
the order the script queued them. This hook queues, in sequence: the victim's
"you are falling" line (a private
[`pemit`](../reference/softcode.md#fn-pemit)), the teleport, the ledge-wide
third-person line, and the landing line. By the time the
[`remit`](../reference/softcode.md#fn-remit) delivers, the faller has already
left the ledge, so the bystanders on the ledge
read the fall while the faller does not get their own third-person echo (a move
is two events across two rooms; see
[action phases](../design/action-phases.md) and the
[one-way exit](028_one_way_exit.md) for the leave-then-arrive split).

[`damage`](../reference/softcode.md#fn-damage) needs no such care. It must be
*called* while the victim is still in reach (the same room), and it is: the
teleport only queues, so at the moment `damage` runs the faller is still on the
ledge. The hp change is applied immediately and the death check rides the queue,
so a lethal drop still routes through the real death path, with the dice supplied
by [`roll`](../reference/softcode.md#fn-roll)`('2d6')` (the
[poison dart trap](052_poison_dart_trap.md) leans on the same proximity
authority for its venom).

### How the reentrancy guard stops a loop

The teleport fires the gully's own `ON_ENTER` mid-cascade, which is harmless here
because the gully has no gate. But an `ON_ENTER` that itself calls a move chains
the actor onward (that is the mechanism behind the chained-fall variation below),
so if a miswired drop room pointed back at the ledge, the gate would re-roll
forever. To close that, a fall uses [`set_attr`](../reference/softcode.md#fn-set_attr) to
stamp `fall_<id> = `[`now()`](../reference/softcode.md#fn-now) on the ledge, and
the gate reads that stamp back with
[`V`](../reference/softcode.md#fn-v) to wave through anyone who fell within the
last 5 seconds. There is no re-roll
and no loop, and the stamp expires on its own with no cleanup tick.

## Build it

Dig the ledge with an entry exit and a way back, step onto it, then dig the gully
downward from the ledge so `down` and `up` connect the two levels. Describe the
shelf while you stand on it:

```text
@dig Cliffside Ledge = ledge, back
ledge
@dig Scree Gully = down, up
@desc here = A boot-wide shelf hugs the cliff face. Pebbles you dislodge take a long time to land.
```

Now set the ledge's `ON_ENTER`. It filters to players, waves through anyone who
fell here in the last 5 seconds, and otherwise rolls Climbing at -2: a made roll
is a line of flavor, a failed one stamps the fall time, drops the faller, hurts
them, and tells the ledge:

```text
@set here/on_enter = '''
if has_tag(enactor, 'player'):
    k = 'fall_' + enactor.id
    recent = now() - V(k, 0) < 5          # fell here in the last 5 seconds?
    if not recent:
        if skill_check(enactor, 'climbing', -2):
            pemit(enactor, 'Scree shifts under your boots. You hug the rock and find your footing.')
        else:
            set_attr(me, k, now())        # stamp the fall so the return trip is not re-rolled
            pemit(enactor, 'The lip crumbles under your boot. You are falling.')
            teleport_obj(enactor, 'Scree Gully')
            damage(enactor, roll('2d6'))  # called while still on the ledge, before the teleport drains
            remit(me, name(enactor) + ' misses a step and pitches over the edge!')
            pemit(enactor, 'You slam into the scree below. Everything hurts.')
'''
```

Finally, step back off the ledge so you are clear of your own trap:

```text
back
```

## Try it

Give yourself a body, then test both outcomes:

```text
@set me/hp = 14
@set me/max_hp = 14
@set me/skill_climbing = 14
ledge
  Scree shifts under your boots. You hug the rock and find your footing.
back
@set me/skill_climbing = 4
ledge
  The lip crumbles under your boot. You are falling.
  You slam into the scree below. Everything hurts.
```

You are now in Scree Gully, several hp lighter, and anyone on the ledge read
"...misses a step and pitches over the edge!" Climb `up` right away and the
5-second stamp lets you regain the shelf without a fresh roll, winded but not
looping. Wait it out, and the ledge is dangerous again.

## Going further

- **Margin-scaled damage:** swap the boolean `skill_check` for the
  [`margin_under`](../reference/softcode.md#fn-margin_under) primitive and size
  the dice by how badly the roll missed, so a slip costs less than a plummet.
- **Catch yourself:** on failure, offer one `prompt()` ("grab for the root?
  (yes/no)"), a second Climbing roll at -4 before the drop
  ([tutorial 067](067_dialogue_tree_npc.md) chains prompts).
- **Chained falls:** give the gully floor its own weaker gate onto a lower cave.
  Because each fall stamps its own room, even a chain of ledges stays loop-safe.
- **Push people off:** a `$shove <target>` verb cannot relocate a bystander
  (no consent, no ownership), but it *can* `force` a contested roll and let the
  *ledge* do the dropping when they fail, so route hostile pushes through the
  room that owns the fall.
