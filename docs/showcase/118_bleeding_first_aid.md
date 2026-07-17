# 118. Bleeding & first aid

> Checklist item 118 — [now] — *damage_over_time behavior, the firstaid command*

**What you'll build:** A battleground where wounds keep bleeding after
the blow — a beat-driven `damage_over_time` effect applied by a triage
witness — and a field satchel whose `$bandage` (a First Aid roll) stops
the bleeding. Both halves of the item are engine primitives; the
softcode is one hook and one command.

**Concepts:** `apply_effect(..., 'damage_over_time', kind='bleeding')`
and its beat clock, `remove_effect()` as the cure verb, an `ON_DAMAGE`
room witness with proximity authority, the native `firstaid` command
(and how it differs from `$bandage`), and the mercy rule.

## How it works

1. **Bleeding is built in.** `damage_over_time` is a registered effect
   behavior: `kind='bleeding'` tags the victim `bleeding` while active,
   pulses `damage` every `interval` beats, expires after `duration`
   beats (the wound clots on its own), and it *persists* — a bleeding
   character is still bleeding after a reboot. Its clock is the
   **beat**: the encounter's adjustable round while its owner fights,
   the ambient world tick otherwise — slow the fight (`pace`) and the
   bleeding slows in lockstep, and never double-ticks (the engine's
   one-clock-one-owner rule).

2. **Wounds start bleeding via a witness.** Every wounding swing
   propagates `combat:on_damage`; a triage-post object standing in the
   room hears it on `ON_DAMAGE` and sweeps the room: any fighter below
   full HP who is not already bleeding starts. `apply_effect` is
   **proximity** authority — the post can afflict whoever shares its
   room, no ownership needed (the same rule that lets item 52's dart
   poison strangers). Two honest notes: the hook fires *before* the
   damage lands, so the very first wound of a fight starts bleeding on
   the **next** combat event (the battlefield notices you a beat late);
   and a witness cannot tell who was hit, so the sweep is the honest
   read — *the wounded bleed*, whoever they are.

3. **Treatment is two different verbs.** The native `firstaid`
   command (First Aid skill, margin-based healing, revives the
   unconscious, refused while *you* are fighting) restores HP — but it
   knows nothing about effects, so the wound keeps bleeding. The
   satchel's `$bandage` is the missing half: a `skill_check(enactor,
   'first_aid')` and `remove_effect(t, 'bleeding')` — stabilization.
   Field doctrine: **bandage stops the loss, firstaid restores it.**

4. **The mercy rule.** `damage_over_time` skips owners tagged
   `unconscious` — the downed do not bleed out in v1. So dropping to
   zero pauses the clock rather than deleting the patient; the engine
   is on the medic's side.

## Build it

The yard and the triage witness:

```text
@dig The Red Yard = yard, out
yard
@create triage post
drop triage post
@desc triage post = A leaning pole flying a faded red cross. It has seen worse days than yours.
@set triage post/on_damage = [apply_effect(o, 'damage_over_time', kind='bleeding', damage=1, interval=1, duration=8, tick_msg='Your wound runs red -- the blood keeps coming.', room_msg='{name} is losing blood.', expire_msg='The wound finally clots.') for o in contents(here) if (has_tag(o, 'player') or has_tag(o, 'npc')) and not has_tag(o, 'bleeding') and not has_tag(o, 'unconscious') and get_attr(o, 'hp', 0) > 0 and get_attr(o, 'hp', 0) < get_attr(o, 'max_hp', 0)]
```

The satchel:

```text
@create field satchel
drop field satchel
@desc field satchel = Rolled dressings, a bone needle, gut thread. BANDAGE <name> to stop a bleed.
@set field satchel/cmd_bandage = $bandage *: t = get(trim(arg0)); (pemit(enactor, 'No patient by that name here.') if not (t and loc(t) == loc(enactor)) else (pemit(enactor, 'They are not bleeding.') if not has_tag(t, 'bleeding') else ((remove_effect(t, 'bleeding'), heal(t, 1), remit(loc(enactor), name(enactor) + ' ties off ' + name(t) + "'s wound. The bleeding stops.")) if skill_check(enactor, 'first_aid') else pemit(enactor, 'The dressing soaks through. It will not hold.'))))
```

`heal()` and `remove_effect()` are both proximity verbs — any bystander
medic can work on any patient in the room.

## Try it

Start a fight in the yard. The first blow lands clean; from the second
combat event on, the hurt fighter is tagged `bleeding`, and each
following beat opens with:

```text
Your wound runs red -- the blood keeps coming.        (-1 HP)
```

A medic standing ringside (not fighting — the fight is not theirs):

```text
bandage Bruce         -> (bad roll) The dressing soaks through. It will not hold.
bandage Bruce         -> ... ties off Bruce's wound. The bleeding stops.
```

The tag lifts, the per-beat loss stops, and the patient is 1 HP better
for the dressing. Left alone instead, the wound clots by itself after
8 beats — bleeding is pressure, not a death sentence — unless those 8
points were points the fighter did not have. HP restoration afterwards
is the native command: `firstaid Bruce` (and it also revives him if he
went down).

## Going further

- **Bleed from big hits only** — gate the sweep on
  `get_attr(o, 'hp', 0) < get_attr(o, 'max_hp', 0) // 2`: flesh wounds
  seal, deep ones run.
- **Cutting weapons cut** — put the sweep on a zone master instead and
  check the room for a fighter wielding a `serrated`-tagged weapon
  before applying — a whole battlefield of wound rules in one master.
- **Field medicine consumes** — give the satchel `charges` and burn
  one per successful bandage; restock at item 63's shopkeeper.
- **Infection** — `$bandage` failures could `apply_effect` a slow
  `poison` DoT with a long interval: untreated wounds get worse, item
  52's antidote pattern cures it.
