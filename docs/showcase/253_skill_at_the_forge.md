# 253. A skill learned at the forge

> Checklist item 253 ([now]): *progression per skill: learn by use, idle study, timed tasks*

**What you'll build:** a forge that teaches the smith who works it. Every
nail you hammer out is a use of `smithing`, and the skill rises with the
work. Beside it you study `metallurgy` from a book, and that skill rises
over real time, even while you are logged out. The more metallurgy you
know, the better your smithing rolls. Two skills, two ways of
improving, one game.

**Concepts:** a skill definition's `progression` (`use` for smithing,
`idle` for metallurgy), `untrained_use` so a beginner can start learning,
`study`, the timed job from [122](122_recipe_crafting.md)
([`start_task`](../reference/softcode.md#fn-start_task)), and
[`check_roll`](../reference/softcode.md#fn-check_roll), which goes
through the real check pipeline and so feeds learning by use.

## How it works

How a skill improves is a property of the skill, not of the game. A
`skill_def` names its model in `progression`, and the game system's own
default covers every skill that says nothing (GURPS buys skills with
points; Merc learns them by use). So the forge needs no code of its own
for learning: it only has to roll the skill the honest way.

### Smithing learns by use

`smithing/progression = use` means every check of smithing earns
experience toward the next level: more for a success than a failure,
nothing for a roll that could not have gone either way. When enough has
built up the level goes up and the smith is told "You have become better
at smithing!" The level is the plain `skill_smithing` attribute, so
anything that reads the skill (a detail, a shop, a door) sees the new
level at once.

A character who was never taught smithing would normally learn nothing
by using it. `untrained_use = True` lets a beginner start from their
untrained default (dexterity minus 5), which is the point of a forge in a
starting town.

The forge rolls with `check_roll`, not a hand-rolled
`margin_under(roll('3d6'), ...)`. Only a real check reports the use; a
hand-rolled one teaches nothing.

### Metallurgy is studied

`metallurgy/progression = idle` means it improves by `study`: type
`study metallurgy` and it accrues from the wall clock, a little faster
for a clever, wise character (intelligence plus half of wisdom, a
minute). Nothing runs while you are away; the time is counted when you
next look (`skills`, `score`), log in, or roll the skill. One skill is in
study at a time.

### The two meet at the anvil

`nail_done` adds a quarter of your metallurgy to the smithing roll, so
the study you did overnight makes tomorrow's work go better, and the
better work teaches smithing faster.

## Build it

Dig the smithy and step in.

```text
@dig Smithy = smithy, out
smithy
```

Define the two skills. Each is an ordinary `skill_def` object; the
`progression` attribute is the whole difference between them.

```text
@create smithing
@tag smithing = skill_def
@set smithing/stat = dexterity
@set smithing/penalty = -5
@set smithing/progression = use
@set smithing/untrained_use = True
@create metallurgy
@tag metallurgy = skill_def
@set metallurgy/stat = intelligence
@set metallurgy/penalty = -5
@set metallurgy/progression = idle
@set metallurgy/attributes = ["intelligence", "wisdom"]
@reload
```

The forge. `forge nail` starts a six-second job; when it is done the
forge rolls smithing, with a quarter of your metallurgy added, and makes
a nail or cracks the rod.

```text
@create forge
drop forge
@desc forge = A squat brick forge, its coals banked and glowing. FORGE NAIL to work a rod of iron.
@set forge/cmd_forge = $forge nail: pemit(enactor, 'You heat a rod of iron in the coals.') if start_task(6, 'nail_done', 'forging a nail', 'nail_stop') else pemit(enactor, 'You are already busy.')
@set forge/nail_done = '''
bonus = get_attr(enactor, 'skill_metallurgy', 0) // 4
r = check_roll(enactor, 'smithing', bonus)
if r.success:
    create_obj('an iron nail', ['thing', 'nail'], here)
    remit(here, f'{name(enactor)} hammers out an iron nail.')
else:
    pemit(enactor, 'The rod cracks in the quench.')
'''
@set forge/nail_stop = pemit(enactor, 'You let the iron cool, unworked.')
```

## Try it

```text
> forge nail
  You heat a rod of iron in the coals.
  (six seconds later)
  Bob hammers out an iron nail.
> forge nail
  ...
  You have become better at smithing!
> skills
  Your skills:
    smithing             6   (use: 0/3)
> study metallurgy
  You begin studying metallurgy.
  (log out; come back eight hours later)
> skills
  You have finished training metallurgy to level 17.
  Your skills:
    metallurgy           17   (training)
    smithing             6   (use: 0/3)
  Training metallurgy: the next level in 11 minute(s).
```

Those numbers are for a smith with dexterity 10, intelligence 12 and
wisdom 11 in a GURPS game, where untrained metallurgy starts at 7;
yours depend on your characteristics. The use counter (`0/3`)
shows how far smithing is from its next level; the study line shows
when metallurgy gains its next.

## Going further

- **Mastery:** give smithing a `progress_rule` that pays nothing on a
  failure past level 15, so only good work teaches a journeyman.
- **A cap per class:** in a Merc game, `smithing/class_caps =
  {"warrior": 50}` keeps a warrior from out-smithing the guild.
- **Prerequisites:** `metallurgy/requires = {"smithing": 8}` makes study
  wait until the smith has worked the anvil.
- **Practice:** put a `trainer` behavior on the master smith
  (`@behavior master smith = trainer, teaches:smithing`) to teach
  smithing up to a floor, after which it improves only by use.
