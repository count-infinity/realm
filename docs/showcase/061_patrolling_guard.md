# 061. Patrolling guard

> Checklist item 61 ([now]): *patrol behavior, waypoint routes, ON_OPEN/ON_ARRIVE reactions*

**What you'll build:** Sergeant Yara, who walks a fixed round (gatehouse, wall,
battlements and back) pausing at each post. Open the armory door in front of her
and she challenges you on the spot; leave it open behind her back and she pulls
it shut, muttering, on her next round.
**Concepts:** the built-in `patrol` behavior (its `route` and `pause` params),
doors as `closed`-tagged paired exits, `ON_OPEN` as a witnessed reaction,
`ON_ARRIVE` as the mover's own arrival hook, and a `now()` cooldown attribute.

## How it works

Yara is one object carrying three brains: a `patrol` behavior that walks her
route on the world tick, and two lifecycle hooks that react to doors. This
section answers how the route drives her feet, why an open door reaches her when
she is standing there, and why she finds a door left open behind her back.

### How the route drives her feet

Where item 60's [wandering NPC](060_wandering_npc.md) rolls dice for its next
step, `patrol` follows orders. The `route` param is a list of exit *names*, and
the behavior walks them in order, looping forever, waiting `pause` ticks between
steps. With `pause:2` she takes one step, waits two ticks, then steps again, so
she moves on every third world tick. Two properties matter:

- **The route is topology, not coordinates.** Each step goes through the real
  movement pathway (`move_through_exit`), so locks, wards, and closed doors stop
  the guard exactly as they would stop you. A blocked step is not skipped: she
  stands and retries after the pause, which reads as a guard waiting at an
  obstacle. Close a door on her route and you have stalled the patrol.
- **State is two attributes** (`patrol_index`, her place in the route, and
  `patrol_wait`, the countdown) written on Yara. `@examine Sergeant Yara` shows
  them, and because they are ordinary attributes a restart does not lose them.

### How an open door reaches her

`ON_OPEN` fires on every *witness* of an open: the room, its contents, and the
door itself. It does not fire on the actor who did the opening. So when you open
a door in Yara's room, her [`ON_OPEN`](../reference/softcode.md#lifecycle-hooks)
runs with you as `enactor`. She is a witness reacting to the door's event, never
the thing that was opened, so her hook takes no `target is me` guard; a
[witness reaction](../reference/softcode.md#guard-on-target) that added one would
never fire, because the target is the door. A
[`now()`](../reference/softcode.md#fn-now) cooldown attribute is what keeps her
from barking once per hinge creak.

### How she catches a door left open behind her

`ON_ARRIVE` is the mover's own hook: it fires only on the object that just
entered a room, and only for that object's own move. Yara's runs on her each
time she completes a step of the round, and it sweeps the room she landed in for
door-flagged exits that lost their `closed` tag, shutting each with a scripted
`close` command. That routes through the same close verb players use, so the
whole room hears her do it and the door's own `ON_CLOSE` mirror (item 25's
[lockable door](025_lockable_door.md)) still fires. Because the hook only ever
runs for her own arrival, it needs no guard either.

We flag which exits count as "doors she cares about" with a plain `door`
attribute; the sweep reads it and nothing else does. Convention stored as data.

## Build it

The round is three rooms off your workroom, plus the armory behind a
paired-exit door (both faces named `armory door`, the pattern from item 25's
[lockable door](025_lockable_door.md)). Dig the rooms, walking as you go so you
end standing on the North Wall:

```text
@dig The Gatehouse = gatehouse, back
gatehouse
@dig The North Wall = wall, gatehouse
wall
@dig The Battlements = battlements, wall
@dig The Armory = armory door, armory door
```

Mark both faces of the door with the `door` attribute the sweep reads, then shut
it, since exits are dug open. Set the near face, step through to set the far
face, step back, and close it:

```text
@set armory door/door = 1
armory door
@set armory door/door = 1
armory door
close armory door
```

Now the sergeant herself, built standing on the North Wall:

```text
@create Sergeant Yara
@tag Sergeant Yara = npc
drop Sergeant Yara
@desc Sergeant Yara = Boots you could shave in. She walks the same round she has walked for nine years.
```

Her challenge is an `ON_OPEN` hook. It speaks and stamps the current time onto a
`challenged` attribute, but only when more than 20 seconds have passed since the
last challenge, so a flurry of opens gets one line:

```text
@set Sergeant Yara/on_open = '''
if now() - V('challenged', 0) > 20:  # witness, not target: no target-is-me guard, the cooldown gates repeats
    say('Who goes into the armory? State your business.')
    set_attr(me, 'challenged', now())
'''
```

Her arrival sweep is an `ON_ARRIVE` hook. It loops the exits in the room she
just entered and, for any that carry the `door` attribute yet have lost their
`closed` tag, mutters and shuts it through the ordinary `close` verb:

```text
@set Sergeant Yara/on_arrive = '''
for o in contents(here):  # her own arrival hook, fires only on her own move
    if has_tag(o, 'exit') and get_attr(o, 'door', 0) and not has_tag(o, 'closed'):
        pose('mutters about lax discipline.')
        cmd(f'close {name(o)}')
'''
```

Finally attach the patrol brain and set its route in one line. Read the route
from where she stands on the North Wall: out to the battlements, back to the
wall, down to the gatehouse, back to the wall, then loop:

```text
@behavior Sergeant Yara = patrol, route:["battlements", "wall", "gatehouse", "wall"], pause:2
```

The armory door is not on her route: it is the thing she guards, not the way she
walks.

## Try it

Stand on the North Wall and let a few ticks pass. She strides off to the
battlements, waits a beat, comes back through, then heads for the gatehouse. The
round never varies, and `@examine Sergeant Yara` shows `patrol_index` as her
place in it.

Open the door while she is present, then open it again inside the cooldown
window:

```text
open armory door
  -> Sergeant Yara says, "Who goes into the armory? State your business."
close armory door
open armory door
  -> (silence: within ~20s the cooldown attribute holds her tongue)
```

Now the crime she cannot see. Wait until she is away, open the armory door, and
stand back. On her next pass through the North Wall her arrival sweep finds it:

```text
open armory door        (with Yara off at the battlements)
  -> (nothing yet)
                        (on her next step back onto the North Wall)
  -> Sergeant Yara mutters about lax discipline.
     Sergeant Yara closes the armory door.
```

And the patrol is physical. The armory door is not on her route, so to see the
movement gate stop her, stand a locked door or a second guard on her path and
watch her wait at it, retrying each pause, until it clears.

## Going further

- **Waypoint speeches:** add a branch to `ON_ARRIVE` keyed on `name(here)`, a
  word at the gatehouse and a long stare from the battlements, with one
  [`switch()`](../reference/softcode.md#fn-switch) on the room name.
- **Shift changes:** wrap
  [`attach_behavior`](../reference/softcode.md#fn-attach_behavior) and
  [`detach_behavior`](../reference/softcode.md#fn-detach_behavior) in item 68's
  [clock states](068_npc_schedule.md) so Yara patrols only at night and sleeps
  in the gatehouse by day.
- **Alarm integration:** her `ON_OPEN` could
  [`act()`](../reference/softcode.md#fn-act) a custom event to a zone master
  (item 71's [guard response](071_guard_response.md)) instead of just speaking,
  a patrol that summons the cavalry.
- **Keyed patrols:** give her the armory key (an `unlocks` attribute) and an
  `ON_ARRIVE` that runs `unlock` and `lock` through their verbs, a guard who
  locks up properly behind herself with the same key items players use (item
  25).
