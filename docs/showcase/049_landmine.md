# 049. Landmine

> Checklist item 49 ([now]): *ON_ENTER triggers, contest() detection, concealment tags*

**What you'll build:** A buried mine that detonates when someone walks
into the room, unless they win a Perception contest against its
concealment, already know it is there, or planted it themselves. It is
part of the [Heist arc](arc_heist.md), and it goes in the Vault
Antechamber from [item 27](027_secret_door.md).

**Concepts:** a witnessed [`ON_ENTER`](../reference/softcode.md#lifecycle-hooks)
used as a proximity trigger, a [`contest()`](../reference/softcode.md#fn-contest)
whose opposing skill lives *on the object*, an
[`on_check`](../reference/softcode.md#guard-on-target) ward that vetoes a
pickup, [`eval_attr()`](../reference/softcode.md#fn-eval_attr) for splitting
a long script, the proximity authority behind
[`damage()`](../reference/softcode.md#fn-damage), and the `invisible` plus
`conceal_difficulty` concealment kit shared with the secret door.

## How it works

The finished mine is a single object lying on the floor of the
antechamber. It never polls, and the room needs no code of its own: when
anything walks in, the mine hears about it, rolls one contest, and either
warns the walker or blows up. This section answers three questions in the
order a builder asks them. How does a passive object hear a footstep? How
does it decide? And why can a dropped object legally hurt the person who
just stepped on it?

### How a passive mine hears a footstep

Movement in REALM propagates as an action. When a walker arrives, the
engine fires an `event:on_enter` whose **target is the room**, and every
object sitting in that room witnesses the reaction pass. So a mine on the
floor gets its [`ON_ENTER`](../reference/softcode.md#lifecycle-hooks) hook
run for free on every arrival, with the walker bound as `enactor` (one of
the names in the
[event data namespace](../reference/softcode.md#event-data-namespace)).
That is the whole proximity-trigger pattern, and the same shape powers
pressure plates, welcome mats, and shop doorbells.

Because the reaction pass runs *after* the move applies (the
[trio](../design/action-phases.md): check before, apply, react after), the
walker is already standing in the room when the hook fires. The mine and
the walker now share a room, which is exactly why the mine can reach out
and touch them in the next step.

The mine reacts to the *walker*, not to itself, so the guard here is not
the usual `target is me`: for an entry event the target is the room, and
the mine is a bystander to it. Instead the mine reads `enactor`, filters
to living arrivals with
[`has_tag()`](../reference/softcode.md#fn-has_tag), and exempts its own
[`owner()`](../reference/softcode.md#fn-owner). Each mine also checks its
*own* [`V('armed', 0)`](../reference/softcode.md#fn-v), so a disarmed mine
lying next to an armed one stays quiet while the live one goes off.

### How the mine decides: a contest with the skill on the object

Detection is a [`contest()`](../reference/softcode.md#fn-contest), and the
pleasing part is that the opposing skill lives on the *mine*.
`skill_concealment = 13` is the minelayer's craftsmanship, read by the
same skill machinery as any character skill, so
`contest(x, 'observation', me, 'concealment')` needs no special case. The
walker must *exceed* the mine to win: an equal roll is a tie, and ties go
to the status quo, which is the armed mine. The branches, in the order a
minefield actually plays:

1. Not armed, not a living thing, or the arriver **owns the mine**, so do
   nothing. The owner exemption matters, because softcode fires for
   everyone, and a builder who steps on their own mine while decorating
   will not make that mistake twice.
2. The mine is already visible (someone found it earlier), so the walker
   steps around it. Knowledge is safety.
3. Contest won, so the walker freezes mid-step: reveal the mine to the
   world, and no boom.
4. Contest lost, so run `eval_attr(me, 'boom')`.

The detonation lives in its own `boom` attribute.
[`eval_attr()`](../reference/softcode.md#fn-eval_attr) runs another
attribute as a subroutine under the same authority and message queue,
which keeps the trigger readable and makes `boom` independently testable
with `@trigger` and reusable (the [combination safe](016_combination_safe.md)'s
trapped-dial variant wires its mismatch branch to this same attribute).

### Why a dropped mine may hurt the walker

[`damage()`](../reference/softcode.md#fn-damage) carries **proximity
authority**: a script may hurt whatever stands in its own room, with no
ownership needed. That is the license a trap requires and no more, and it
is available precisely because the entry already placed the walker in the
mine's room. Lethal damage routes through the real death path.

Last is the [`on_check`](../reference/softcode.md#guard-on-target) ward,
because mines are not loot. The check pass runs *before* a gated action
commits, in a read-only namespace where a script can only decide, and
`block(reason)` vetoes the pickup. Here the ward is the deliberate case
for `target is me`: a softcode ward runs only when its object is a
*participant* in the gated action (the actor, the target, or the room),
never for a mere bystander, so the mine's ward fires only when the mine
itself is the thing being picked up. (Python behaviors, by contrast, do
get a bystander check pass. See [053_snare.md](053_snare.md) for the
participant-only rule in practice.)

## Build it

Stand in the antechamber, create the mine, and drop it so it lies on the
floor:

```text
@teleport me = Vault Antechamber
@create anti-personnel mine
drop anti-personnel mine
```

Arm it and set its concealment skill. `armed` is the trap's one switch,
and `skill_concealment` is the number the walker's Observation must beat:

```text
@set anti-personnel mine/armed = 1
@set anti-personnel mine/skill_concealment = 13
```

Add the concealment kit, which is identical to the secret door's, so the
built-in `search` finds mines too. `conceal_difficulty` is the search
penalty, while the contest above is the mid-step check:

```text
@set anti-personnel mine/conceal_difficulty = 3
@set anti-personnel mine/reveal_msg = Dust brushed aside -- a pressure plate, wired and live!
```

The ward keeps the mine from being pocketed. It is a single conditional,
so it stays on one line, and it guards on `target is me` because the mine
is the *target* of a pickup:

```text
@set anti-personnel mine/on_check = block('It is wedged into the floor -- and armed.') if atype == 'item:on_get' and target is me else None
```

The trigger has real branches, so it is a `'''` block. It binds the
arriver, guards on that arriver, then walks the four cases in order:
already exposed, then the contest, then the boom.

```text
@set anti-personnel mine/on_enter = '''
x = enactor
# entry's target is the ROOM, so guard on the arriver, not target is me
if V('armed', 0) and (has_tag(x, 'player') or has_tag(x, 'npc')) and x is not owner(me):
    if not has_tag(me, 'invisible'):
        pemit(x, 'You step around the exposed mine.')
    elif contest(x, 'observation', me, 'concealment'):
        remove_tag(me, 'invisible')
        pemit(x, 'You freeze mid-step -- a pressure plate, right under your boot!')
    else:
        eval_attr(me, 'boom')
'''
```

The bang is its own block. It reveals the mine, disarms it, tells the
victim and the room, and then deals the damage:

```text
@set anti-personnel mine/boom = '''
remove_tag(me, 'invisible')
set_attr(me, 'armed', 0)  # a spent, scorched casing is neither hidden nor live
pemit(enactor, 'KA-WHUMP! The floor erupts under you.')
oemit(enactor, f'{name(enactor)} sets off a buried mine!')
damage(enactor, roll('2d6'))
'''
```

Bury it last, so you can see what you are doing while you work:

```text
@tag anti-personnel mine = invisible
```

Note what `boom` does besides hurt: it un-hides the mine and disarms it,
because a spent casing is not hidden from anyone.

## Try it

Walk in from the corridor by the `loose grate`, with different eyes:

```text
(Observation 14)         -> You freeze mid-step -- a pressure plate, right under your boot!
get anti-personnel mine  -> It is wedged into the floor -- and armed.
duct, loose grate        -> You step around the exposed mine.

(Observation 6)          -> KA-WHUMP! The floor erupts under you.   (2d6, for real)
```

An Observation of 14 beats the concealment of 13 and freezes the walker,
so the mine is now exposed but still armed, and the `on_check` ward still
refuses to let it be pocketed. Walking back out and in again just steps
around the visible mine. An Observation of 6 loses the contest and takes
the full 2d6.

The cautious route is `search`: if you are *already* in the room, it rolls
Observation at -3 (`conceal_difficulty`) and reveals the mine with `Dust
brushed aside -- a pressure plate, wired and live!`. The catch is that you
must be in the room first, and getting in is the dangerous part. That is
what makes it a minefield.

## Going further

- **Disarming.** Add a `$disarm mine: ...` command with a `traps` skill
  check, where success sets `armed = 0` and failure runs
  `eval_attr(me, 'boom')` at the disarmer's feet.
- **Area blast.** Loop the room's contents in `boom` and
  [`damage()`](../reference/softcode.md#fn-damage) bystanders for half.
  Proximity authority already covers the whole room.
- **Alarm plate.** Replace the damage in `boom` with a zone-wide
  `act(..., targeting='zone')`, and the same trigger becomes a silent
  alarm. Compare the reveal-only [pit trap](051_pit_trap.md) and the
  venomous [poison dart trap](052_poison_dart_trap.md) for two other
  payloads on the same trigger shape.
- **Mob casualties.** The trigger already fires for `npc`-tagged
  arrivals, so route a patrol through the minefield at your own
  conscience.
