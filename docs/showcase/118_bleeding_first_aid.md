# 118. Bleeding & first aid

> Checklist item 118 ([now]): *damage_over_time behavior, the firstaid command*

**What you'll build:** A battleground where wounds keep bleeding after the blow
lands. A triage post standing in the room applies a beat-driven
`damage_over_time` effect to whoever is hurt, and a field satchel's `$bandage`
(a First Aid roll) stops the bleeding. Both halves are engine primitives, so the
softcode is one room hook and one command.

**Concepts:** [`apply_effect`](../reference/softcode.md#fn-apply_effect) with
`damage_over_time` and `kind='bleeding'`, its beat clock,
[`remove_effect`](../reference/softcode.md#fn-remove_effect) as the cure, an
`ON_DAMAGE` room witness under proximity authority, the native `firstaid`
command and how it differs from `$bandage`, and the mercy rule.

## How it works

The finished yard has one object doing the wounding bookkeeping: a triage post
that hears every blow and afflicts the wounded with a bleeding effect that ticks
on its own until it clots. A separate satchel carries the cure. This section
answers four questions: how a wound becomes an ongoing condition, how one object
starts everyone in the room bleeding, why treatment takes two different verbs,
and why a downed fighter does not bleed out.

### How a wound becomes an ongoing condition

Bleeding is a registered effect behavior, not a script loop.
[`apply_effect`](../reference/softcode.md#fn-apply_effect)`(victim,
'damage_over_time', kind='bleeding', ...)` attaches it, and three things follow
for free, the same three the [poison dart trap](052_poison_dart_trap.md) relies
on. The effect mirrors its `kind` as a tag on the victim for exactly as long as
it runs, so [`has_tag(x, 'bleeding')`](../reference/softcode.md#fn-has_tag) is
readable by perception, locks, and other softcode. It persists across a reboot,
because behaviors serialize with their remaining beats intact, so a bleeding
character is still bleeding after a restart. And a pulse that reaches 0 HP routes
through the real defeat path.

Its clock is the **beat**, the game's round-clock: the encounter's adjustable
round while its owner is fighting, and the ambient world tick otherwise. Slow
the fight with `pace` and the bleeding slows in lockstep, because a beat is a
beat whichever clock is driving it. With `duration=8` and `interval=1` the effect
lands seven damaging pulses and clots on the eighth beat, the same arithmetic as
the dart trap's `duration=6` (five pulses, breaks on the sixth).

### How one object starts everyone in the room bleeding

Every wounding swing propagates `combat:on_damage`, and that event fires the
[`ON_DAMAGE`](../reference/softcode.md#lifecycle-hooks) hook of every object in
the room, not only the defender's. A triage post standing there hears it and
sweeps the room's [`contents`](../reference/softcode.md#fn-contents), reading
each occupant's HP with
[`get_attr`](../reference/softcode.md#fn-get_attr) and starting a bleed on any
fighter who is hurt and not already bleeding. The post applies the effect under **proximity** authority: like the
[dart trap](052_poison_dart_trap.md)'s venom, an effect reaches from where the
applying object stands, so the post can afflict whoever shares its room with no
ownership needed.

The hook could read `target`, which names the defender of this particular swing,
but the post sweeps the whole room instead, so that a running fight that wounds
several people sets all of them bleeding rather than only the last one hit.
Because the post reacts to every wounding rather than to its own business, it is
a room-wide witness and takes no `target` guard, the deliberate exception to the
[guard on `target`](../reference/softcode.md#guard-on-target) rule; the check
that a fighter is not already bleeding keeps the repeated sweep idempotent.

One consequence of the timing is honest to call out. `combat:on_damage`
propagates *before* the swing's HP loss is applied (see the
[before/apply/after trio](../design/action-phases.md)), so on the very first
blow of a fight the defender still reads full HP and the sweep passes them over.
They start bleeding on the next combat event instead, once the earlier wound is
on the books. The battlefield notices you a beat late.

### Why treatment takes two verbs

The native `firstaid` command runs a First Aid roll, heals by the margin,
revives an unconscious patient, reports an unhurt one "unhurt" and stops, and
refuses while *you* are fighting. It restores HP, but it knows nothing about
effects, so a bandaged wound keeps bleeding. The satchel's `$bandage` is the
missing half: a [`skill_check`](../reference/softcode.md#fn-skill_check)`(enactor,
'first_aid')` and, on success,
[`remove_effect`](../reference/softcode.md#fn-remove_effect)`(t, 'bleeding')`,
which strips the effect, tag and all. Field doctrine: bandage stops the loss,
firstaid restores it. Unlike `firstaid`, `$bandage` is a plain room command with
no combat gate, so a ringside medic can work on a patient mid-fight.

### Why the downed do not bleed out

The `damage_over_time` pulse skips an owner tagged `unconscious`, so a fighter
who has already gone down does not bleed out while helpless. This is the same
mercy the [tranquilizer](059_tranquilizer.md) leans on, that the engine treats
`unconscious` as a real state other systems respect. A bleed pulse that would
itself take a player to 0 HP drops them unconscious rather than killing them
(players never die), and the effect ends there. The engine is on the medic's
side.

## Build it

Dig the yard, step in, then stand up the triage post and give it a face:

```text
@dig The Red Yard = yard, out
yard
@create triage post
drop triage post
@desc triage post = A leaning pole flying a faded red cross. It has seen worse days than yours.
```

The post's `on_damage` hook sweeps the room on every wounding: for each living
fighter who is hurt and not already bleeding, it applies a bleeding effect that
pulses one point a beat for eight beats. It reacts to every wounding, not to its
own business, so it takes no `target` guard, and the already-bleeding check keeps
the repeated sweep from stacking:

```text
@set triage post/on_damage = '''
# ON_DAMAGE fires on every object in the room, so this post sweeps all the wounded
for o in contents(here):
    if (has_tag(o, 'player') or has_tag(o, 'npc')) and get_attr(o, 'hp', 0) > 0 and get_attr(o, 'hp', 0) < get_attr(o, 'max_hp', 0) and not has_tag(o, 'bleeding') and not has_tag(o, 'unconscious'):
        apply_effect(o, 'damage_over_time', kind='bleeding', damage=1, interval=1, duration=8, tick_msg='Your wound runs red; the blood keeps coming.', room_msg='{name} is losing blood.', expire_msg='The wound finally clots.')
'''
```

Create the satchel and set it down so it shares the room with its patients:

```text
@create field satchel
drop field satchel
@desc field satchel = Rolled dressings, a bone needle, gut thread. BANDAGE <name> to stop a bleed.
```

The `bandage` command finds the named patient with
[`get`](../reference/softcode.md#fn-get) and
[`trim`](../reference/softcode.md#fn-trim), refuses a name that is not in the
room or a patient who is not bleeding, then rolls the medic's First Aid. A
success strips the bleeding with `remove_effect`, presses in one point with
[`heal`](../reference/softcode.md#fn-heal), and announces it with
[`remit`](../reference/softcode.md#fn-remit) to the medic's room,
[`loc`](../reference/softcode.md#fn-loc)`(enactor)`, naming both parties with
[`name`](../reference/softcode.md#fn-name); a failure reports privately with
[`pemit`](../reference/softcode.md#fn-pemit) and just soaks the dressing.
`first_aid` is a native skill, so no `skill_def` setup is needed:

```text
@set field satchel/cmd_bandage = '''
$bandage *:
t = get(trim(arg0))
if not (t and loc(t) is loc(enactor)):
    pemit(enactor, 'No patient by that name here.')
elif not has_tag(t, 'bleeding'):
    pemit(enactor, 'They are not bleeding.')
elif skill_check(enactor, 'first_aid'):
    remove_effect(t, 'bleeding')
    heal(t, 1)  # the dressing itself is worth a point
    remit(loc(enactor), name(enactor) + ' ties off ' + name(t) + "'s wound. The bleeding stops.")
else:
    pemit(enactor, 'The dressing soaks through. It will not hold.')
'''
```

Both `heal` and `remove_effect` are proximity verbs, so any bystander medic can
work on any patient in the room.

## Try it

Start a fight in the yard. The first blow lands clean, because the hook fires
before that blow's HP loss and the defender still reads full health. From the
second combat event on, the hurt fighter is tagged `bleeding`, and each
following beat opens with the tick:

```text
Your wound runs red; the blood keeps coming.        (-1 HP)
```

A medic in the room can bandage even mid-fight, since `$bandage` is a plain room
command. Whether the dressing holds is the medic's First Aid roll, so the first
two lines vary with the medic:

```text
> bandage Bruce         (weak First Aid)
The dressing soaks through. It will not hold.

> bandage Bruce         (strong First Aid)
Mara ties off Bruce's wound. The bleeding stops.
```

On the success the tag lifts, the per-beat loss stops, and the patient is one HP
better for the dressing. Left alone instead, the wound clots on its own after
seven pulses, on the eighth beat: bleeding is pressure, not a death sentence,
unless those seven points were points the fighter did not have. HP restoration
afterwards is the native command, `firstaid Bruce`, which also revives him if he
went down (and which he must be out of a fight to perform).

## Going further

- **Bleed from big hits only.** Gate the sweep on
  `get_attr(o, 'hp', 0) < get_attr(o, 'max_hp', 0) // 2`, so flesh wounds seal
  and only deep ones run.
- **Cutting weapons cut.** Put the sweep on a zone master instead, and check the
  room for a fighter wielding a `serrated`-tagged weapon before applying, a whole
  battlefield of wound rules in one master.
- **Field medicine consumes.** Give the satchel `charges` and burn one per
  successful bandage, restocking at item 63's shopkeeper.
- **Infection.** A `$bandage` failure could `apply_effect` a slow `poison`
  damage-over-time with a long interval, so untreated wounds worsen, and item
  52's antidote pattern cures it.
```
