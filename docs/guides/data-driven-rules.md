# How-To: Skills & Classes as Data

Skills and classes aren't hardcoded in Python — they're **data**. A skill
or a class is just a tagged object in the world, so you can add or edit
one in-game with OLC, or ship one in an importable area, with **no code
change**. The game system reads these definitions and falls back to its
built-ins when the world has none.

This is Stage A of the [data-driven rules kernel](../design/rules-kernel.md).

## The conventions

A **skill** is an object tagged `skill_def`:

| field | meaning |
|---|---|
| name | the skill's name (e.g. `piloting`) |
| `stat` | governing attribute (`dexterity`, `intelligence`, …) |
| `penalty` | untrained default penalty (e.g. `-4`) |

A **class** is an object tagged `class_def`:

| field | meaning |
|---|---|
| name | the class / background name (e.g. `pilot`) |
| `blurb` | one-line description shown in the chargen menu |
| `stats` | dict of attributes set at creation — `{"dexterity": 13}` |
| `skills` | dict of skills granted — `{"piloting": 14}` |

**Both merge** over the built-ins — data wins by name. Define `piloting`
and it's added; define a `soldier` `class_def` and it overrides the
built-in soldier; make `stealth` easier by redefining it. Adding one
definition *adds* it — it never silently wipes the built-in set.
(Suppressing a specific built-in is a future explicit opt-out.)

## Add one from softcode / OLC

A class is an ordinary object, so you build it the way you build anything:

```text
@create pilot
@tag pilot = class_def
@set pilot/blurb = sharp reflexes, ice nerves
@set pilot/stats  = {"dexterity": 12, "intelligence": 11}
@set pilot/skills = {"piloting": 13, "gunnery": 12}
```

It appears at the next character creation immediately — classes are read
live. A **skill** is the same shape:

```text
@create piloting
@tag piloting = skill_def
@set piloting/stat = dexterity
@set piloting/penalty = -4
@reload
```

The `@reload` matters for **skills only**: the skill table is cached for
speed, so after you create or edit a `skill_def`, `@reload` re-reads it so
checks pick it up. (Classes need no reload.)

## Add one from Python

For seeding or tests, `realm.systems.definitions` has builders:

```python
from realm.systems.definitions import define_skill, define_class

await persistence.save(define_skill("piloting", "dexterity", -4))
await persistence.save(define_class(
    "pilot", "sharp reflexes",
    stats={"dexterity": 12}, skills={"piloting": 13, "gunnery": 12}))
```

## Ship them in an area — or a pack

Because they're just objects, `@export` / `realm export` serialize them
into an area file like any room or NPC, and `@import` brings them in — so
"the sci-fi class set" or "one hacker class" is a normal importable unit.
Bundle skills, classes, and gear into a **[content pack](content-packs.md)**
(`@pack`, `realm pack import`) to ship a whole game's worth at once — the
built-in `gurps-scifi` pack does exactly this. See also
[World Management](world-management.md).

## Where the built-ins live

The default tables are `BUILTIN_SKILL_DEFAULTS` and `TEMPLATES` (GURPS) /
`CLASSES` (D20) in `realm/systems/`. They're the fallback and the seed to
mirror — not files to patch (see [Add a Character Class](add-a-class.md)
for customizing in your own `rules.py`). Defining `skill_def`/`class_def`
objects is the *content* path; a `rules.py` subclass is the *mechanics*
path. Both compose.
