# 053. Snare

> Checklist item 53 ([now]): *restraint tags, movement wards, $struggle contest loops*

**What you'll build:** A hunting snare that whips tight around an ankle and
holds its victim in the room until they tear free with a Strength contest, each
failed struggle loosening the wire a little.

**Concepts:** what actually blocks movement in softcode: an `on_check` ward
vetoing a departure, the effect machinery's kind-tag used as a restraint flag
([`apply_effect`](../reference/softcode.md#fn-apply_effect) with `duration=0`),
a [`contest`](../reference/softcode.md#fn-contest) against a skill stored on the
trap, Strength-as-a-skill through a `skill_def`, and degrading trap state as a
mercy rule.

## How it works

A snare is a room that refuses to let you leave while a tag is on you, plus a
trap that hangs that tag and a `struggle` command that removes it. Nothing owns
the victim and nothing edits their sheet, so the whole restraint is one ward
reading one tag. This section answers three questions: how softcode stops
someone from leaving a room, where the `snared` tag comes from, and how a victim
breaks out.

### How does softcode stop someone from leaving a room?

Not by owning the walker, and not by editing their sheet, but by vetoing the
move as it happens. Walking out fires an `event:on_leave` action through the
propagation engine's [check pass](../design/action-phases.md) *before* the actor
relocates. On that pass the mover and the origin room each get to run their
`on_check` ward against the in-flight action, while bystanders witness the
attempt but their softcode never runs on the check pass. A ward is
decision-only softcode: it reads a restricted namespace plus `block()`, and it
sees the action's own fields, where `atype` is the action type and `actor` is
who is moving.

So the ward goes on the room, and it is one line: if this is a departure and
the actor carries the `snared` tag, `block()` with a reason. The engine shows
the walker the reason and the move never happens. Notice what this ward does
*not* need: any code on the victim, and no knowledge of which exit they tried.

### Where does the "snared" tag come from?

The snare cannot [`add_tag`](../reference/softcode.md#fn-add_tag) on the victim,
because mutating a stranger requires control of them. But `apply_effect` runs on
*proximity* authority (the same license as damage: you may affect whoever stands
next to you), and every timed effect mirrors its `kind` as a tag on its host for
exactly as long as it is active. So
`apply_effect(x, 'modifier_effect', kind='snared', duration=0)` is the legal way
to hang a restraint flag on someone else: `duration=0` means "until removed", the
tag `snared` appears for the ward to read, and
[`remove_effect`](../reference/softcode.md#fn-remove_effect)`(x, 'snared')` takes
the flag and the effect away in one motion. The status machinery keeps the tag;
the ward only reads it. This is the same effect machinery the
[poison dart trap](052_poison_dart_trap.md) uses for venom, run with
`duration=0` so it never expires on its own.

### How does a victim break out?

Breaking out is a quick contest, and the opposing skill lives on the trap.
`contest(enactor, 'might', me, 'hold')` rolls the victim's Strength against
`skill_hold` on the snare (the trapper's craftsmanship), the same shape as the
[landmine's](049_landmine.md) concealment contest. Strength-as-a-skill is one
more `skill_def` object named `might` (`stat = strength`, penalty 0): untrained,
everyone rolls their raw Strength, and `@reload` teaches the skill table the new
row. Ties go to the snare, because REALM contests favor the status quo, and the
status quo has you by the ankle.

### Why the wire loosens

Each failed struggle decrements `skill_hold` with
[`decr`](../reference/softcode.md#fn-decr). The snare's skill is just an
attribute, so the trap itself degrades: a weak character is delayed, not
imprisoned, and the contest loop always terminates. That is trap design as much
as engine fact.

One honest note: the ward gates *walking* and a scripted
[`move_to`](../reference/softcode.md#fn-move_to). A `teleport_obj` or
`@teleport` is a forced placement and tunnels past wards by design, so an admin
can always yank a victim free.

## Build it

First the trail you will stand in to build, and Strength as a rollable skill. A
`skill_def` object is data the rules read, so `@reload` picks up the new row:

```text
@dig The Game Trail = trail, out
trail
@create might
@tag might = skill_def
@set might/stat = strength
@set might/penalty = 0
@reload
```

Now the snare itself, with its two switches. `armed` spends itself on the first
victim (it is *holding* them now), and `skill_hold` is the trapper's craft:

```text
@create hunting snare
drop hunting snare
@desc hunting snare = A whippy sapling, a loop of ground wire, and patience.
@set hunting snare/armed = 1
@set hunting snare/skill_hold = 12
```

The trigger springs the snare on arrival. It reacts only to an armed snare
catching a real character who is not the owner, then spends the trap, announces
to the room with [`remit`](../reference/softcode.md#fn-remit), and hangs the
`snared` effect on the victim:

```text
@set hunting snare/on_enter = '''
x = enactor
# ON_ENTER fires on every object in the room, so react only to an armed
# snare catching a real character; V('armed', 0) reads THIS snare, and
# `is not` is an identity check, not equality.
if V('armed', 0) and (has_tag(x, 'player') or has_tag(x, 'npc')) and x is not owner(me):
    set_attr(me, 'armed', 0)
    remit(loc(me), f"A wire loop snaps tight around {name(x)}'s ankle!")
    apply_effect(x, 'modifier_effect', kind='snared', duration=0, apply_msg='The world jerks sideways -- you are caught fast!')
'''
```

The ward is the whole restraint in one decision, and it goes on the room. It
vetoes a departure only while the mover carries the `snared` tag:

```text
@set here/on_check = block('The snare around your ankle jerks taut! (STRUGGLE to break free)') if atype == 'event:on_leave' and has_tag(actor, 'snared') else None
```

And the way out, a `$struggle` command on the snare. Win the contest and shed the
effect; lose it and the wire gives a point of `hold`:

```text
@set hunting snare/cmd_struggle = '''
$struggle:
if not has_tag(enactor, 'snared'):
    pemit(enactor, 'You are not caught in anything.')
elif contest(enactor, 'might', me, 'hold'):
    remove_effect(enactor, 'snared')
    remit(loc(me), f'{name(enactor)} tears free of the snare!')
else:
    decr('skill_hold')          # the wire stretches a little each failed pull
    pemit(enactor, 'You strain against the wire. It gives a little -- and holds.')
'''
```

## Try it

Walk someone in (Strength 12, against `hold` 12). The struggle result depends on
the roll, so the middle lines here are one representative run:

```text
> trail
The world jerks sideways -- you are caught fast!
(the room sees: A wire loop snaps tight around Zeke's ankle!)

> out
The snare around your ankle jerks taut! (STRUGGLE to break free)

> struggle
You strain against the wire. It gives a little -- and holds.
(Strength 12 vs hold 12 is a tie, ties go to the snare, and hold is now 11)

> struggle
Zeke tears free of the snare!

> out
(gone)
```

While held, *every* exit refuses them, because the ward does not know or care
which way they tried. A sprung snare (`armed = 0`) ignores the next walker;
`@set hunting snare/armed = 1` resets the trap, though the wire keeps its
stretched `skill_hold` unless you re-set that too.

## Going further

- **Hobbled, not just held.** Add `check_mods={'melee': -2, 'stealth': -4}` to
  the `apply_effect` call so fighting and sneaking from inside a snare are
  worse, and every check reads the modifier automatically.
- **A friend with a knife.** Add a `$cut snare` command on the snare that calls
  `remove_effect(V('victim'), 'snared')` when the enactor is not the one caught
  (store the victim's id when the snare springs). Rescue beats brute force.
- **Timeout mercy.** Give the effect `duration=30` instead of 0 and captivity
  expires on its own: a poacher's snare, not a dungeon.
- **The trapper's page.** Splice in the [tripwire alarm's](050_tripwire_alarm.md)
  line, `pemit(owner(me), '[snare] Something is thrashing on the Game Trail.')`,
  when it springs. Traps compose, as the [pit trap](051_pit_trap.md) shows.
```
