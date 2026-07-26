# 052. Poison Dart Trap

> Checklist item 52 ([now]): *ON_GET/ON_USE traps, apply_effect damage_over_time*

**What you'll build:** A jade idol that answers a touch (or a grab) with a
dart and a lingering venom. The venom ticks damage for six beats unless the
victim's constitution shakes it off, and an antidote vial cures it.

**Concepts:** a `$`-command and [`ON_GET`](../reference/softcode.md#lifecycle-hooks)
as two triggers on one trap, [`eval_attr`](../reference/softcode.md#fn-eval_attr)
as the shared payload, the engine's effect machinery
([`apply_effect`](../reference/softcode.md#fn-apply_effect) with
`damage_over_time`: a ticking condition that persists, tags its victim, and
expires on its own), resistance as a `skill_def`, and
[`remove_effect`](../reference/softcode.md#fn-remove_effect) as counterplay.

## How it works

The finished trap is one idol carrying a single `dart` payload that two
different triggers reach: the explicit verb `touch idol`, and the greedy
`get idol`. A poisoned victim then carries an engine effect that ticks damage
on its own clock until it expires, and an antidote strips that effect early.
This section answers three questions: how one payload serves both triggers,
why the poison is an engine effect rather than a script loop, and how the trap
avoids darting an innocent bystander.

### Two triggers, one payload

Touching the wrong object arrives through two doors. The first is the explicit
verb `touch idol`, a `$`-command matched only against the idol you named. The
second is the greedy `get idol`: when someone picks the idol up, the engine
fires the idol's [`ON_GET`](../reference/softcode.md#lifecycle-hooks) hook. Both
triggers call one shared `dart` attribute through
[`eval_attr`](../reference/softcode.md#fn-eval_attr), the same shared-subroutine
shape as the [security camera](054_security_camera.md)'s relay, so you fix the
dart once and both triggers sharpen.

`eval_attr` runs another attribute as a subroutine, keeping the same
`enactor` and the same message queue, so inside `dart` the `enactor` is
whoever touched or grabbed the idol. The dart announces to the room with
[`remit`](../reference/softcode.md#fn-remit) to
[`loc(enactor)`](../reference/softcode.md#fn-loc), scratches for
real with [`damage`](../reference/softcode.md#fn-damage), then rolls the
victim's resistance to decide whether venom takes hold.

### Why the venom is an engine effect, not a script loop

REALM's status machinery is [`apply_effect`](../reference/softcode.md#fn-apply_effect),
which attaches a registered effect behavior to the victim. The
`damage_over_time` effect pulses damage each **beat** (the game's round-clock:
combat rounds in a fight, the world tick outside one) for `duration` beats,
narrating with `tick_msg` and `room_msg`, then removes itself with
`expire_msg`. With `duration=6` and `interval=1` it lands five damaging pulses
and breaks on the sixth beat.

Three things come free that a hand-rolled `wait()` loop would not give you.
The effect persists across a reboot, because behaviors serialize with the
remaining beats intact, so a poisoned character is still poisoned after a
restart. It tags the victim, so [`has_tag(x, 'poison')`](../reference/softcode.md#fn-has_tag)
is readable by locks, perception, and other softcode while it runs. And a
lethal pulse routes through the real death path.

The authority to poison is proximity, not control, the same license as
[`damage`](../reference/softcode.md#fn-damage): a trap may hurt or poison
whoever is in reach of it. That is why the *idol* applies the effect. It works
for a grab as well as a touch because [reach includes your
carrier](../design/action-phases.md): an object can act on the one carrying it,
so an idol already in the taker's hands is still in reach of that taker.

### How the trap knows the grab was for it

An [`ON_GET`](../reference/softcode.md#lifecycle-hooks) hook fires **after** the
item has moved, so by the time the hook runs the idol is already in the taker's
inventory, not on the floor. That post-move timing is why the dart announces
with `loc(enactor)`, the taker's room, rather than `loc(me)`, which is now the
taker's own inventory. See the [before/apply/after trio](../design/action-phases.md).

The post-move timing carries a second consequence that a trap must respect:
`ON_GET`, like every `ON_<EVENT>` hook, is witnessed by every object in the
room, not only by the one that was picked up. So the hook opens with
`if target is me:`, because otherwise a second idol sharing the room would
fire its own dart whenever the *first* idol was grabbed, and dart the taker
twice. `target` is the object that was actually taken and `me` is the
witnessing idol, so the guard fires the dart only when this idol is the one in
hand. Write `is`, not `==`: it is an identity check. See
[Guard on `target`](../reference/softcode.md#guard-on-target). The `touch`
verb needs no such guard, because a `$`-command only ever runs on the object
whose name matched.

### Resistance is data, and the cure is one call

GURPS resists poison with HT, so one `skill_def` object named `fortitude`
(`stat = health`) plus `@reload` teaches the skill table a new row, the same
trick as the [gas bomb](048_gas_bomb.md)'s fortitude roll.
[`skill_check(enactor, 'fortitude', -2)`](../reference/softcode.md#fn-skill_check)
then rolls the toucher's own health attribute, and a success shrugs the venom
off. The antidote is the mirror image: a `$drink` command that confirms the
victim actually carries the `poison` tag, calls
[`remove_effect`](../reference/softcode.md#fn-remove_effect) to strip the
effect by kind, and [destroys itself](../reference/softcode.md#fn-destroy_obj).

## Build it

Start with a room for the shrine, then the resistance skill as data. The
`skill_def` tag plus `@reload` is what makes `fortitude` a real skill the
check machinery can roll:

```text
@dig The Reliquary = reliquary, out
reliquary
@create fortitude
@tag fortitude = skill_def
@set fortitude/stat = health
@set fortitude/penalty = 0
@reload
```

Create the idol and give it a face:

```text
@create jade idol
drop jade idol
@desc jade idol = A grinning green figurine on a wall bracket. Its eyes follow you.
```

The `dart` payload is the shared subroutine both triggers call. It announces
to the room, deals the scratch, then rolls fortitude: a success is a harmless
scratch, a failure spreads venom by attaching a `damage_over_time` effect that
pulses for six beats:

```text
@set jade idol/dart = '''
remit(loc(enactor), 'A hidden nozzle spits a needle-thin dart!')
damage(enactor, roll('1d2'))
if skill_check(enactor, 'fortitude', -2):
    pemit(enactor, 'Your head swims for a moment, then clears. Only a scratch.')
else:
    pemit(enactor, 'A cold numbness spreads from the scratch.')
    apply_effect(enactor, 'damage_over_time', kind='poison', damage=1, interval=1, duration=6, tick_msg='Venom burns through your veins!', room_msg='{name} shivers, grey-faced and sweating.', expire_msg='The fever finally breaks.')
'''
```

Now the two triggers. `touch` is a `$`-command that only ever runs on the idol
you named, so it calls the payload directly on one line:

```text
@set jade idol/cmd_touch = $touch idol: eval_attr(me, 'dart')
```

`on_get` needs a guard, because the engine fires it on every object in the room
when anything is picked up. Without `if target is me:` a neighbouring idol
would dart you whenever you grabbed a different one:

```text
@set jade idol/on_get = '''
if target is me:  # ON_GET fires on EVERY object in the room, so guard it
    eval_attr(me, 'dart')
'''
```

Last, the counterplay. The antidote's `$drink` command checks the drinker
actually carries the effect's own `poison` tag, cures them, and spends the
vial; drinking it unpoisoned wastes nothing:

```text
@create antidote vial
drop antidote vial
@desc antidote vial = A stoppered vial of milky liquid, labeled in a careful hand: AFTER THE IDOL.
@set antidote vial/cmd_drink = '''
$drink antidote:
if has_tag(enactor, 'poison'):
    remove_effect(enactor, 'poison')
    pemit(enactor, 'Bitter warmth washes the numbness out of your blood.')
    destroy_obj(me)
else:
    pemit(enactor, 'You are not poisoned. Save it.')
'''
```

## Try it

A touch, with a strong constitution and then a weak one (fortitude is
`health - 2`, so HT 13 resists and HT 8 does not):

```text
> touch idol        (HT 13)
A hidden nozzle spits a needle-thin dart!
Your head swims for a moment, then clears. Only a scratch.

> touch idol        (HT 8)
A hidden nozzle spits a needle-thin dart!
A cold numbness spreads from the scratch.
```

The dart damage is `1d2`, so the HP lost to the scratch varies by a point.
After a failed resist, each beat the poisoned one reads `Venom burns through
your veins!` and loses 1 HP while the room watches them shiver. Five pulses
later, on the sixth beat, `The fever finally breaks.` on its own.

Grabbing the idol runs the same payload, and the grab still succeeds, so you
are left holding a live trap:

```text
> get jade idol
A hidden nozzle spits a needle-thin dart!
```

The cure, any time before the fever runs its course:

```text
> drink antidote
Bitter warmth washes the numbness out of your blood.
```

[`remove_effect`](../reference/softcode.md#fn-remove_effect) detaches the
behavior mid-run, so the tag lifts, the ticking stops, and the vial is gone.

## Going further

- **Blinding venom.** Effects carry check modifiers, so adding
  `check_mods={'observation': -4}` to the `apply_effect` call leaves the
  poisoned barely able to see straight until it lifts, the same
  `modifier_effect` plumbing a fear spell uses.
- **One dart only.** Gate `dart` on a `loaded` attribute and zero it after
  firing with `set_attr`; a `$reload idol` command for the owner re-arms it.
- **Trapped chest instead.** The payload is portable: put `eval_attr(me,
  'dart')` behind a container's `ON_OPEN` (guarded the same way) and the venom
  guards loot.
- **Slow rot.** `interval=3, duration=30` turns a nuisance into a
  journey-length problem that outlives a server restart, and the antidote
  trade gets interesting.
