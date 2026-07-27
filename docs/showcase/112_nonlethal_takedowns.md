# 112. Non-lethal takedowns

> Checklist item 112 ([now]): *engine unconsciousness, restraint wards, captives*

**What you'll build:** a cosh that puts people down without killing them, iron
binders that keep a captive put, and a clear map of the engine's two ways to end
up on the floor: the HP-zero death path versus the softcode knockout.

**Concepts:** the `unconscious` kind-tag (the [tranquilizer](059_tranquilizer.md)
sets it with a dart, here by blunt force), a
[`contest`](../reference/softcode.md#fn-contest) for the opposed takedown, a
permanent [`modifier_effect`](../reference/softcode.md#fn-apply_effect) as a
restraint, the room `on_check` ward from the [snare](053_snare.md), and what the
one native defeat path does for players versus NPCs.

## How it works

There is no engine "subdue" maneuver: nothing in combat tracks fatigue or
non-lethal damage, and no swing ever ends in a captive. So a takedown is built
entirely in softcode, out of two pieces you already have, a
[`contest`](../reference/softcode.md#fn-contest) and an effect. This section
answers three questions: why beating a foe to zero HP cannot capture them, how a
cosh drops someone without touching their HP, and why the binders are a ward on
the room rather than a rope on the prisoner.

### Why zero HP is the wrong path for a capture

When combat drives anything to 0 HP, one death path fires, and it is asymmetric
by design:

| | Players | NPCs |
|---|---|---|
| At 0 HP | fall unconscious in place, tagged `unconscious` | die into a lootable `corpse of X`, which decays |
| Comes back via | `firstaid`, which lifts the tag once it heals HP above zero | nothing: a fresh spawn is a new creature |

So you cannot capture an NPC by beating it down, because zero HP is a corpse and
a corpse cannot be interrogated. A player at zero is at least still on the floor,
but you never chose that: it is combat running its course. Capturing on purpose
needs the second path.

### How a cosh drops someone without touching their HP

The [tranquilizer](059_tranquilizer.md)'s dart established the trick, and the
cosh reuses it. An effect applied with kind `unconscious` mirrors that kind as a
**tag** on the victim for as long as it runs, and the engine's own gates key on
the tag, so no HP is harmed. While the tag holds, the engine reads it
everywhere: [`has_tag`](../reference/softcode.md#fn-has_tag) checks gate movement
(`You are unconscious.`) and combat (the same line), and the combat gate
`is_combat_capable` refuses a tagged target, which is why `attack` a captive
answers `... is not something you can fight`. Downed means
out of the fight in both directions: nobody can start combat against a captive,
and the [poison dart trap](052_poison_dart_trap.md)'s bleed effects skip the
downed as a mercy rule. Unlike HP-zero, this effect expires on its own beats, so
a sapped guard wakes up with a headache instead of a gravestone.

The cosh resolves as a quick [`contest`](../reference/softcode.md#fn-contest),
the attacker's Melee against the victim's Fortitude, and a
[`contest`](../reference/softcode.md#fn-contest) gives ties to the defender, so a
hardy target shrugs it off. That is the same opposed-check shape as the
[snare](053_snare.md)'s struggle. Fortitude is one `skill_def` object named
`fortitude` (`stat = health`) plus `@reload`, the same data trick the
[tranquilizer](059_tranquilizer.md) and [poison dart trap](052_poison_dart_trap.md)
use, so the roll is the target's own health.

### Why the binders are a ward, not a rope

The binders attach a permanent (`duration=0`) `modifier_effect` with kind
`restrained`, again just a kind-tag, and the room's `on_check` ward vetoes any
`event:on_leave` by a `restrained` actor. That is the [snare](053_snare.md)'s
pattern with the tag renamed: walking out fires an `event:on_leave` action on the
[check pass](../design/action-phases.md) before the mover relocates, the room
runs its ward against it, and its `block()` call stops the move. Binding requires the target already unconscious, because you do not
handcuff someone mid-swing, and `$release` strips the effect. Because the
restraint is permanent while the knockout expires, your captive wakes up still
bound, and that is the capture.

The ward takes the guard a ward needs: it acts only when the action is a
departure by a restrained actor, testing `atype` and `actor` rather than reacting
blindly. The `$sap`, `$bind`, and `$release` verbs take no guard at all, because
a `$`-command only ever runs on the object whose name matched, never on a
bystander.

## Build it

Start with a room for the brig, then teach the skill table the resistance roll.
The `skill_def` tag plus `@reload` is what makes `fortitude` a real skill the
contest can roll:

```text
@dig The Brig = brig, out
brig
@create fortitude
@tag fortitude = skill_def
@set fortitude/stat = health
@set fortitude/penalty = 0
@reload
```

Create the cosh, set it down, and give it a face:

```text
@create leather cosh
drop leather cosh
@desc leather cosh = A sand-filled sock of a weapon. SAP someone with it -- quietly.
```

The `sap` command finds the named target, confirms it is a living thing in
reach, refuses a target that is already out, then runs the Melee-versus-Fortitude
[`contest`](../reference/softcode.md#fn-contest). A win announces the takedown to
the room and hangs the `unconscious` effect for eight beats; a loss is a clean
miss:

```text
@set leather cosh/cmd_sap = '''
$sap *:
t = get(trim(arg0))
if not (t and loc(t) is loc(enactor) and (has_tag(t, 'player') or has_tag(t, 'npc'))):
    pemit(enactor, 'No sign of them in reach.')
elif has_tag(t, 'unconscious'):
    pemit(enactor, 'They are already out cold.')
elif contest(enactor, 'melee', t, 'fortitude'):  # ties go to the target, so a hardy foe resists
    remit(loc(enactor), f"{name(enactor)} saps {name(t)} behind the ear -- they fold up like wet paper.")
    apply_effect(t, 'modifier_effect', kind='unconscious', duration=8, apply_msg='A starburst of white -- then nothing.', expire_msg='You come to with a skull full of gravel.')
else:
    remit(loc(enactor), f"{name(t)} twists away from {name(enactor)}'s cosh!")
'''
```

Create the binders and set them down too:

```text
@create iron binders
drop iron binders
@desc iron binders = Rimed iron cuffs on a short chain. BIND the unconscious; RELEASE the forgiven.
```

The `bind` command refuses anyone still awake or already in irons, then attaches
the permanent `restrained` effect. `duration=0` is what makes it outlast the
knockout, so the prisoner is still bound when they come to:

```text
@set iron binders/cmd_bind = '''
$bind *:
t = get(trim(arg0))
if not (t and loc(t) is loc(enactor)):
    pemit(enactor, 'No sign of them in reach.')
elif not has_tag(t, 'unconscious'):
    pemit(enactor, 'They are wide awake -- put them down first.')
elif has_tag(t, 'restrained'):
    pemit(enactor, 'They are already in irons.')
else:
    apply_effect(t, 'modifier_effect', kind='restrained', duration=0)  # duration=0: permanent, never expires on its own
    remit(loc(enactor), f"{name(enactor)} snaps iron binders around {name(t)}'s wrists.")
'''
```

The `release` command is the mirror: it confirms the target is in reach and
actually carries the `restrained` tag, then strips the effect, which lifts the
tag and reopens the exits:

```text
@set iron binders/cmd_release = '''
$release *:
t = get(trim(arg0))
if t and loc(t) is loc(enactor) and has_tag(t, 'restrained'):
    remove_effect(t, 'restrained')
    remit(loc(enactor), f'{name(enactor)} unlocks the binders.')
else:
    pemit(enactor, 'They are not in your irons.')
'''
```

Finally the ward that makes the binders real. It goes on the room and vetoes a
departure only while the mover carries the `restrained` tag:

```text
@set here/on_check = block('The binders hold -- you are going nowhere.') if atype == 'event:on_leave' and has_tag(actor, 'restrained') else None
```

## Try it

Sap a hardy target and a soft one. Fortitude is the target's raw health, so
Melee 14 ties Fortitude 14 (the tie goes to the target) but beats Fortitude 8:

```text
> sap Brick          (Fortitude 14)
Brick twists away from Mara's cosh!

> sap Zeke           (Fortitude 8)
Mara saps Zeke behind the ear -- they fold up like wet paper.
(Zeke) A starburst of white -- then nothing.
```

Zeke is tagged `unconscious` with no HP lost, so the engine's own gates do the
lockout you never wrote, from both sides:

```text
> attack Zeke
Zeke is not something you can fight.
```

Put him in irons. Binding refuses the still-awake, so it works only because he
is down:

```text
> bind Brick
Brick is wide awake -- put them down first.

> bind Zeke
Mara snaps iron binders around Zeke's wrists.
```

Eight beats later the knockout expires on its own, but the restraint does not, so
Zeke wakes up still bound and every exit refuses him:

```text
(Zeke) You come to with a skull full of gravel.

(Zeke) > out
The binders hold -- you are going nowhere.
```

`release Zeke` strips the `restrained` effect and the door works again.
Meanwhile the death path, for contrast: knock a **thug NPC** to 0 HP in combat
and you get `corpse of thug`, with no captive and no interrogation. Beat a
**player** to 0 and they collapse where they stand (`Everything goes black...`)
until someone kneels down with `firstaid`, which lifts the tag once it heals HP
back above zero.

## Going further

- **Drag the captive.** A `$drag *` on the binders that `move_to`s a restrained
  target along with you needs relocation authority: it works on your own
  prisoners (your NPCs), or through an admin-owned paddy wagon, the same
  authority rule the [snare](053_snare.md)'s rescue note describes.
- **Struggle out.** Give the binders a hold rating and copy the
  [snare](053_snare.md)'s `$struggle` contest verbatim (`might` versus `hold`,
  the rating eroding per attempt), so a strong captive can fight the irons.
- **Turn them in.** A [bounty office](114_bounty_board.md) that pays for
  `restrained` captives delivered alive: the `$claim` checks `has_tag(t,
  'restrained')` instead of listening for deaths.
- **Sap from stealth only.** Require `has_tag(enactor, 'hidden')` and drop the
  contest to a flat Fortitude roll at a penalty: assassin rules, with the
  sneaking as the setup.
