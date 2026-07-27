# 059. Tranquilizer Mechanics

> Checklist item 59 ([now]): *engine unconscious tag, command lockout, recovery waits*

**What you'll build:** A tranquilizer pistol whose dart drops a target into
real unconsciousness, the same state the combat engine uses when a fighter's HP
runs out, for six beats, plus a stim injector that jolts them awake early.

**Concepts:** the engine's `unconscious` tag and the gates it closes (movement
and combat), inducing that tag legally from softcode with
[`apply_effect`](../reference/softcode.md#fn-apply_effect)'s kind-tag under
proximity authority, HT resistance as a `skill_def`, and
[`remove_effect`](../reference/softcode.md#fn-remove_effect) as the wake-up.

## How it works

The finished device is a dart that sets one engine tag on whoever it hits.
Because the combat engine already treats that tag as "out cold", every lockout
you might want comes for free, and the effect machinery lifts the tag on its own
when the sedation runs out. This section answers four questions: why setting one
tag is the whole knockout, how softcode may sedate someone it does not control,
how the target wakes, and how resistance is rolled.

### Why setting one tag is the whole knockout

When combat drops a player to 0 HP, the engine tags them `unconscious`, and that
tag is read all over the engine. Walking any exit answers `You are
unconscious.`, `attack` refuses with the same line, and an unconscious follower
is left behind rather than trailing its leader. A tranquilizer therefore needs
no lockout code of its own. It only has to set that tag, and every gate the
engine already built closes.

### How softcode sedates someone it does not control

Softcode cannot call `add_tag(victim, 'unconscious')`, because tagging an object
requires control of it and you do not control other players. The legal path is
an effect. [`apply_effect`](../reference/softcode.md#fn-apply_effect) runs under
proximity authority, since a dart may drug whoever it can reach, and every timed
effect mirrors its `kind` as a tag on the victim for exactly as long as it runs.
So `apply_effect(t, 'modifier_effect', kind='unconscious', duration=6, ...)` is
the entire knockout: the engine tag appears, the gates close, and the effect
owns the bookkeeping. It is the same kind-tag mechanism the [poison dart
trap](052_poison_dart_trap.md) uses for its venom, pointed this time at a tag
the engine itself respects.

Proximity means the gadget's own room. Effects and damage reach from where the
object stands, which is why this pistol sits on a swivel mount inside the Med
Bay and the stim rests in a wall cradle there, the same reason the [poison dart
trap](052_poison_dart_trap.md)'s idol darts from its bracket and the [gas
bomb](048_gas_bomb.md) refuses to arm in your hands. A held gadget's room is
your own inventory, which reaches only its carrier, so sedation gear is placed
in the room it is meant to cover.

### How the target wakes

`duration` counts beats, the game's round-clock (combat rounds inside a fight,
the world tick outside one). When the count reaches zero the effect detaches
itself: the tag lifts, the `expire_msg` is delivered, and the gates open.
Because effects serialize with their owner, the sedation survives a reboot with
its remaining beats intact, so there is no in-memory timer to orphan. The
counterplay is the mirror of the knockout:
[`remove_effect`](../reference/softcode.md#fn-remove_effect)`(t, 'unconscious')`
strips the effect early, tag and all, which is exactly what the stim injector
does. The built-in `firstaid` also revives the unconscious, but only a wounded
one: it reports an unhurt target "unhurt" and stops, and a tranq victim takes no
HP damage, so chemistry is the only way back for them.

### Resistance is the same HT roll as every toxin

GURPS resists a sedative with HT, so one `skill_def` object named `fortitude`
(`stat = health`) plus `@reload` teaches the skill table a new row, the same
data trick the [gas bomb](048_gas_bomb.md) and [poison dart
trap](052_poison_dart_trap.md) build.
[`skill_check`](../reference/softcode.md#fn-skill_check)`(t, 'fortitude', -3)`
then rolls the target's own health. Tranq darts are meant to put a target down,
which is the reason for the -3, but a hardy target shakes it off.

One design note: the dart deals no HP damage. A tranquilizer is useful precisely
because it routes around the death path, so a game can hand players a knockout
without handing them a kill.

## Build it

Start with a room for the device and teach the skill table the resistance roll.
The `skill_def` tag plus `@reload` is what makes `fortitude` a real skill the
check machinery can roll:

```text
@dig The Med Bay = medbay, out
medbay
@create fortitude
@tag fortitude = skill_def
@set fortitude/stat = health
@set fortitude/penalty = 0
@reload
```

Create the pistol, set it down so it shares the room with its targets, and give
it a face:

```text
@create tranq pistol
drop tranq pistol
@desc tranq pistol = A snub-nosed gas pistol on a swivel mount by the door, its rotary drum full of red-feathered darts. SHOOT someone with it.
```

The `shoot` command finds the named target with
[`get`](../reference/softcode.md#fn-get) and
[`trim`](../reference/softcode.md#fn-trim), confirms with
[`has_tag`](../reference/softcode.md#fn-has_tag) that it is a living thing in the
same room, announces the dart with [`remit`](../reference/softcode.md#fn-remit)
to [`loc`](../reference/softcode.md#fn-loc)`(enactor)`, then rolls fortitude. A
success is a numb wobble; a failure attaches the `unconscious` modifier effect
for six beats and drops them where they stand:

```text
@set tranq pistol/cmd_shoot = '''
$shoot *:
t = get(trim(arg0))
if not (t and loc(t) is loc(enactor) and (has_tag(t, 'player') or has_tag(t, 'npc'))):
    pemit(enactor, 'No sign of them in reach.')
else:
    remit(loc(enactor), f"{name(enactor)} plants a red-feathered dart in {name(t)}'s neck!")
    if skill_check(t, 'fortitude', -3):  # a hardy target shakes it off
        pemit(t, 'Your vision swims... then steadies. Your neck is numb.')
    else:
        # kind mirrors as the engine 'unconscious' tag for exactly duration beats
        apply_effect(t, 'modifier_effect', kind='unconscious', duration=6, apply_msg='The room smears sideways. Then nothing.', expire_msg='You come to, cheek on the cold deck.')
        remit(loc(enactor), f'{name(t)} crumples bonelessly to the floor.')
'''
```

The `$shoot *` pattern binds whatever follows `shoot` as `arg0`, and
[`pemit`](../reference/softcode.md#fn-pemit) to `enactor` reports the clean miss
when the name resolves to nobody in reach.

Create the stim injector and set it in its own cradle in the same room:

```text
@create stim injector
drop stim injector
@desc stim injector = An emergency stim injector in a wall cradle. JAB the sedated with it.
```

The `jab` command is the early wake-up. It confirms the target is in reach and
actually carries the `unconscious` tag, then calls
[`remove_effect`](../reference/softcode.md#fn-remove_effect) to strip the effect,
which lifts the tag and reopens the gates:

```text
@set stim injector/cmd_jab = '''
$jab *:
t = get(trim(arg0))
if t and loc(t) is loc(enactor) and has_tag(t, 'unconscious'):
    remove_effect(t, 'unconscious')  # strips the effect early: tag lifts, gates reopen
    remit(loc(enactor), f"{name(enactor)} slams a stim injector against {name(t)}'s arm. They jolt awake.")
else:
    pemit(enactor, 'They are not sedated.')
'''
```

## Try it

Dart two targets, one hardy and one not (fortitude is `health - 3`, so HT 13
resists at 10 and HT 8 fails at 5):

```text
> shoot Brick        (HT 13)
Your vision swims... then steadies. Your neck is numb.

> shoot Zeke         (HT 8)
Bob plants a red-feathered dart in Zeke's neck!
(Zeke) The room smears sideways. Then nothing.
Zeke crumples bonelessly to the floor.
```

Now the engine's own gates do the lockout you never wrote:

```text
(Zeke) > out
You are unconscious.

(Zeke) > attack Brick
You are unconscious.
```

Six beats later, on its own, Zeke reads `You come to, cheek on the cold deck.`
and the exits work again. Or skip the wait with the stim:

```text
> jab Zeke
Bob slams a stim injector against Zeke's arm. They jolt awake.
```

## Going further

- **Groggy aftermath.** Chain a second effect onto the wake-up: a
  `modifier_effect` with `kind='groggy', duration=10, check_mods={'all': -2}`
  applied alongside, one beat longer, so the target wakes before their reflexes
  recover.
- **A gag ward too.** The unconscious can still speak, since only movement and
  combat are engine-gated. A ward on the room closes that: `@set here/on_check =
  ...` with a body of `block('Only a soft snore emerges.') if atype ==
  'event:speech' and has_tag(actor, 'unconscious') else None`. A room, as a
  participant in the action, may veto what happens in it, the
  [snare](053_snare.md)'s lesson.
- **Drag the body.** The sleeper cannot be picked up, since players never can,
  but a `$drag *` command using `teleport_obj` works in rooms you own, a
  kidnapping mechanic with the same authority rules as the [pit
  trap](051_pit_trap.md).
- **Dosage policy.** A second dart on an already-sedated target refreshes the
  effect to full duration, because effects are singletons per kind, so
  re-applying renews rather than stacks. Raise `duration` on the second dart for
  a deepening dose, or check the tag and refuse for a one-dose rule.
