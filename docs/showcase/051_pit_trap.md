# 051. Pit Trap

> Checklist item 51 ([now]): *trap state attrs, teleport_obj, escape contests*

**What you'll build:** A rigged flagstone that drops unwary walkers into
an oubliette below, plus the hard way back out: a climbable shaft that
rolls your Climbing skill on every attempt.

**Concepts:** a witnessed `ON_ENTER` trap, `teleport_obj()` as the fall,
room-owner relocation authority (why a trap may move a victim at all), a
skill-gated exit (`check_skill` / `check_difficulty` / `check_fail_msg`)
as the escape, and the enactor-in-room guard that keeps two co-located
traps from double-firing.

## How it works

A pit trap is two moves the engine already knows how to make. The floor
drops a walker into a cell one room below, and a skill-gated exit lets
them climb back out on their own dice. Everything below is either the
drop, the authority that permits it, or the guard that makes it fire
exactly once. There is no polling loop and no `$`-command anywhere.

### Why the fall is a `teleport_obj`, and why the trap may do it

Movement in REALM is one primitive with two doors: walking, gated by
wards, locks, and skill checks, and *placement*,
[`teleport_obj()`](../reference/softcode.md#fn-teleport_obj), which
relocates straight to a destination. A trapdoor is placement, so no exit
is traversed; the floor simply stops being under you. `teleport_obj` is
forced movement (a thin alias for `move_to(force=True)`): it tunnels past
the destination's on_check wards, because you do not get a *choice* about
falling, while still honoring the destination's locks. The same forced
relocation drives the cliff in [falling between rooms](047_falling.md).

The authority is the part worth understanding. Softcode may normally
mutate only what it controls, but relocation is deliberately weaker than
full control: **a room's owner may move whatever is standing in that
room** (PennMUSH's `tport_control_ok`). The flagstone runs with its
owner's authority, the owner dug and therefore owns the gallery, and the
victim is standing in the gallery, so the drop is legal for *any* victim.
Put the same trap in a stranger's room and the teleport fizzles, which is
why traps belong on home turf.

### How the plate fires for the walker and for no one else

When anything enters the room, the arrival propagates as `event:on_enter`
and **every object in the room witnesses it**, with the arriver bound as
`enactor`. The hook sees post-state: by the time it runs the walker has
already arrived (see [action phases](../design/action-phases.md)). A pit
lying on the floor therefore hears about every arrival for free, the same
proximity pattern as the [landmine](049_landmine.md).

Because the *room* is the target of `on_enter`, not the plate, the pit
cannot guard with `target is me` the way the
[poison dart trap](052_poison_dart_trap.md) guards its `ON_GET`. It reads
the mover off `enactor` instead and filters, in one `if` on the first
line of the body:

- the plate is `armed`,
- the arriver is a player or an npc (a dropped crate keeps its footing),
- the arriver is not the [`owner`](../reference/softcode.md#fn-owner) (so
  a builder decorating the gallery does not drop through it), and
- the arriver is *still standing on this plate*: `loc(x) is loc(me)`.

That last clause earns its keep. Put two armed plates in one gallery and
both witness the same arrival, but the first plate's fall relocates the
victim before the second plate's hook runs, so the second reads
[`loc(x)`](../reference/softcode.md#fn-loc) as the cell below, not the
gallery, and stays inert. I confirmed this with two plates in one room:
the victim falls once and the second plate is never sprung. Drop the
clause and the victim reads the fall twice and both plates disarm. Write
`is`, not `==`, since it is an identity check; and there is no `return` in
a script body, so the guard is a plain `if` wrapping the reaction.

### What happens on a hit, and why the plate disarms itself

A sharp-eyed walker gets one out:
[`skill_check(x, 'observation', -3)`](../reference/softcode.md#fn-skill_check)
rolls their Observation at a penalty, and on success they step around the
plate, which stays armed. On a failure the `else` branch drops the floor,
and its statement order is deliberate. Queued softcode actions run in
order after the script finishes, so the script disarms the plate,
[`remit`](../reference/softcode.md#fn-remit)s the gallery its
third-person line,
[`pemit`](../reference/softcode.md#fn-pemit)s the victim "The floor drops
away", teleports them, then pemits the landing. The victim reads the
sequence in the order it happened to them.

The disarm is load-bearing, not flavor.
[`set_attr(me, 'armed', 0)`](../reference/softcode.md#fn-set_attr) springs
the trap so the doors hang open until the owner resets them, because a
climber emerging from the cell *arrives back in the gallery* and would
land on a still-armed plate and fall forever. State on the trap is what
makes the loop escapable.

### The way out is a skill-gated exit, with no softcode at all

Any exit can carry `check_skill` and `check_difficulty`: the engine rolls
the walker's skill at that penalty on *every* traversal and turns
failures back with `check_fail_msg`. Name the exit `climb` and the escape
reads like a verb. Type `climb`, roll Climbing at -2, and either make it
or slide back down for another try. Failure keeps you in the cell, so a
weak climber is late, not trapped, and none of it needs a `$`-command.

## Build it

The gallery, and the cell below it, dug unlinked so the only honest way
in is through the floor:

```text
@dig The Dusty Gallery = gallery, out
@dig The Oubliette
gallery
```

The flagstone, with `armed` as its one switch:

```text
@create rigged flagstone
drop rigged flagstone
@desc rigged flagstone = One flagstone sits a shade lower than its brothers.
@set rigged flagstone/armed = 1
```

The trigger. The guard on the first line decides whether this plate is
the one that should react to the arriving walker; the body then either
lets a sharp eye sidestep or drops the floor:

```text
@set rigged flagstone/on_enter = '''
x = enactor
# fire only for a living walker who isn't the owner and is still on THIS plate
if V('armed', 0) and (has_tag(x, 'player') or has_tag(x, 'npc')) and x is not owner(me) and loc(x) is loc(me):
    if skill_check(x, 'observation', -3):
        pemit(x, 'A flagstone shifts under your toe -- you step around it just in time.')
    else:
        set_attr(me, 'armed', 0)  # the fall springs the trap: doors stay open until reset
        remit(loc(me), f'{name(x)} vanishes through the floor with a crash!')
        pemit(x, 'The floor drops away beneath you!')
        teleport_obj(x, 'The Oubliette')
        pemit(x, 'You land hard on cold stone, far below.')
'''
```

The climb out, an exit with the skill gate on it, built from inside the
cell:

```text
@teleport me = The Oubliette
@desc here = A stone box that smells of old rain. The only light is a grey coin of sky at the top of a rough shaft.
@open climb = The Dusty Gallery
@desc climb = A rough shaft, half handholds, half wishful thinking.
@set climb/check_skill = climbing
@set climb/check_difficulty = 2
@set climb/check_fail_msg = You claw halfway up the slick stone and slide back down.
@teleport me = The Dusty Gallery
```

## Try it

Send in two walkers with different eyes:

```text
> gallery      (Scout, Observation 13)
A flagstone shifts under your toe -- you step around it just in time.

> gallery      (Mook, Observation 6)
The floor drops away beneath you!
You land hard on cold stone, far below.
  (in the gallery) Mook vanishes through the floor with a crash!
```

Scout rolls Observation 13 - 3 = 10 and steps around it, and the plate
stays armed for the next group. Mook rolls 6 - 3 = 3, drops through, and
the fall springs the doors. Now climb out of the cell:

```text
> climb        (untrained, Climbing defaults to DX-5 = 5)
You claw halfway up the slick stone and slide back down.

> climb        (Climbing 12)
The Dusty Gallery
```

Every `climb` is a fresh roll (5 - 2 = 3 slides back, 12 - 2 = 10 makes
it), so a weak climber is late, not stuck forever. The climber surfaces
safely because their own fall already sprang the doors; re-arm the plate
for the next group with `@set rigged flagstone/armed = 1`.

## Going further

- **Self-resetting doors:** end the fall branch with
  [`wait`](../reference/softcode.md#fn-wait)`(60, 'trigger me/rearm')`
  and a one-line `rearm` attribute (`set_attr(me, 'armed', 1)`), for a
  dungeon that resets itself. Mind any climber still below when it fires.
- **Fall damage:** the flagstone cannot hurt someone a room below, since
  [`damage`](../reference/softcode.md#fn-damage) reaches only its own
  room, so put an `on_enter` on the Oubliette itself:
  `damage(enactor, roll('1d6'))` catches trapdoor victims and careless
  teleporters alike.
- **A rope changes the odds:** an inline `[[...]]` block in the shaft's
  description can report whether a rope is in the cell,
  `[o for o in contents(here) if has_tag(o, 'rope')]`, and a
  `$tie rope` verb can lower `check_difficulty` when one is present.
- **Oubliette with company:** a
  [wandering rat](060_wandering_npc.md) zone-leashed to the cell makes
  waiting for rescue worse.
