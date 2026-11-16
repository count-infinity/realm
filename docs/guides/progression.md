# Progression: How Skills Improve

A skill in REALM improves in one of four ways, and a game may use all four
at once, skill by skill:

| Model | How it improves | Spent / earned | Works offline |
|---|---|---|---|
| `points` | `improve <skill>` | character points, from kills and awards | n/a |
| `practice` | `practice <skill>` at a trainer | practice sessions, from levels | n/a |
| `use` | by being used: every check of it, every swing of a weapon of it | experience per skill, earned automatically | no |
| `idle` | `study <skill>`, over real time | time itself | yes |

Whatever the model, it writes the same thing: the plain `skill_<name>`
attribute. Every check, ruleset, softcode `skill()` call and character
sheet reads that, so none of them knows or cares how the level was
reached.

## Choosing a model per skill

A skill's model is its `skill_def`'s `progression` attribute. A skill that
does not say gets the game system's `default_progression`:

| System | Default |
|---|---|
| GURPS, D20 (`PointBuyMixin`) | `points` |
| Merc | `use`, after practice to a floor (Decision D5: the SMAUG hybrid) |
| a neutral `GameSystem` | `None`: skills do not improve |

```text
@set smithing/progression = use          # grind it
@set metallurgy/progression = idle       # study it
@set tactics/progression = points        # buy it
```

The skill must exist as a `skill_def` to carry the attribute
([Skills & Classes as Data](data-driven-rules.md)).

## Caps

`use`, `practice` and `idle` stop at the game system's
`skill_cap(character, skill)`. Point-buy limits itself (points are scarce)
and ignores it.

| System | Cap |
|---|---|
| neutral | none |
| Merc | the skill definition's `class_caps` for the character's class (`{"warrior": 50}`); else 95 for a skill of the character's class once they reach the level its ability unlocks at, 75 before that, and 75 for any skill outside their class |

## Learn by use

Every `check()` and every attack roll reports to the game system's
`on_skill_used(character, result)`. For a `use` skill:

- a success earns 2 experience and a failure 1 (`use_xp_gain`), kept in
  `skill_xp_<name>`;
- a roll that could not have gone either way earns nothing
  (`check_was_open`: under Merc, a 0% or 100% chance);
- at `use_xp_needed(level)` (`2 + level ÷ 5` by default) the level rises
  by one, the counter resets, and the character is told "You have become
  better at <skill>!";
- nothing is earned at or above the cap;
- a skill the character was never taught does not improve by use, unless
  its definition says `untrained_use = True`. Then it starts from its
  untrained default (under GURPS, its attribute minus its penalty), so
  learning never lowers it;
- only player characters learn.

An attack roll counts as a use of the weapon's skill: its `skill`
attribute, else `skill_type`, else `melee`.

`skills` shows how far a `use` skill is from its next level:
`melee  40%   (use: 6/10)`.

### A curve of your own

A `progress_rule` on the skill definition replaces the experience award.
It is a softcode expression in the `rule` profile, like a game system's
`resolve_rule`, with `level`, `success` and `xp` bound, and returns the
experience to add:

```text
@set smithing/progress_rule = (3 if success else 1) if level < 15 else (1 if success else 0)
```

`on_skill_used` is synchronous, because `check()` is: it may change
attributes and message the character, and never propagates an action.
Learning by use cannot be an `ON_<EVENT>` hook.

## Practice

An NPC with the `trainer` behavior teaches:

| Param | Default | Meaning |
|---|---|---|
| `teaches` | `"class"` | a list of skill names, or `"class"` for the character's class skills |
| `max_level` | a third of the skill's cap | how far practice carries a skill |
| `trains_stats` | `False` | whether `train <stat>` works here |

```text
@behavior guildmaster = trainer, trains_stats:true
@behavior master smith = trainer, teaches:smithing, max_level:30
```

- `practice` lists what the trainer teaches and your levels.
- `practice <skill>` spends one of your `practices` and raises the skill
  by a third of your intelligence, up to the trainer's `max_level`. Past
  that, the skill improves only by use. A skill whose model is `points` or
  `idle` is not practiced.
- `train <stat>` spends one of your `trains` and raises a characteristic
  by one, up to the game system's `stat_max` (Merc: 18, or 20 for the
  class's prime characteristics).

Merc characters earn practices and one train each level. The ROM importer
gives mobs with ROM's practice and train flags the `trainer` behavior.

## Idle training

`study <skill>` starts training an `idle` skill; `study stop` ends it,
`study` alone says what you are studying. One skill at a time; switching
banks what the first earned. A definition's `requires`
(`{"herbalism": 5}`) must be met first.

Training accrues skill points a minute from the definition's two
`attributes` (default intelligence and wisdom): the first plus half the
second. A level costs `idle_cost(level)` (`60 × (level + 1)` by default)
times the definition's `rank`. Nothing runs while the player is away: the
time is counted whenever it is next needed, at login, by `skills` and
`score`, before any check of that skill, and by a sweep over online
characters that tells them "You have finished training <skill> to level
N." The setting `IDLE_TRAINING_MAX_HOURS` caps how much time away is
banked at once (0, the default, for no cap).

## Timed tasks

The `tasks` feature is for anything that takes time at a place: crafting,
gathering, a ritual.

```text
@set forge/cmd_forge = $forge nail: start_task(6, 'nail_done', 'forging a nail', 'nail_stop')
@set forge/nail_done = create_obj('an iron nail', ['thing', 'nail'], here)
@set forge/nail_stop = pemit(enactor, 'You let the iron cool.')
```

`start_task(seconds, done_attr, label, interrupt_attr)` makes the enactor
busy (tagged `busy`, shown as `Pat (busy)`). When the time passes, the
object that started it runs `done_attr` with the character as enactor.
Moving, being drawn into a fight, or typing `stop` breaks it off and runs
`interrupt_attr` instead. A second task while busy is refused
(`start_task` returns False). Unlike `wait()`, a task is stored on the
character, so it survives a reboot. `task_of(obj)` returns `{"label",
"left"}` or None; `stop_task(obj)` breaks one off.

A task that rolls a skill with `check_roll` or `skill_check` teaches it
by use, which is how a crafting skill grinds: see the worked example,
[a skill learned at the forge](../showcase/253_skill_at_the_forge.md).

## For a game system's author

The hooks, all on `GameSystem` ([Creating Your Own
System](creating-your-own-system.md)):

| Hook | Default |
|---|---|
| `default_progression` | `None` (`"points"` on `PointBuyMixin`, `"use"` on Merc) |
| `on_skill_used(obj, result)` | runs the `use` model |
| `skill_cap(obj, skill)` | `None` |
| `check_was_open(result)` | `True` |
| `use_xp_gain(success)` | 2 for a success, 1 for a failure |
| `use_xp_needed(level)` | `2 + level // 5` |
| `idle_cost(level)` | `60 * (level + 1)` |
| `class_skills(obj)` | `[]` (what a `"class"` trainer teaches) |
| `stat_max(obj, stat)` | `None` |

A use or idle curve must land on the game's own scale: under GURPS skill
14 is an expert, so a GURPS game that learns by use wants a steep, short
curve (override `use_xp_needed`).
