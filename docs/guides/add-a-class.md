# How-To: Add a Character Class

**Goal:** add a new selectable background (a "class") to character
creation — defined in *your* game, without touching the `realm` package.

If you haven't yet, skim [How a Character Is Born](../concepts/character-creation.md)
first — it explains why a "class" is just an entry a chargen step offers.

## You already have the file: `rules.py`

`realm init` created a **`rules.py`** in your project — a `GameRules`
class that subclasses the built-in GURPS system, already registered and
already selected by `config.py`. Out of the box it behaves exactly like
GURPS; adding a class means filling in a couple of its hooks. You never
touch the `realm` package, and a REALM upgrade can't overwrite your work.

The scaffolded file has this exact edit stubbed out in comments — the
snippet below is what it looks like uncommented and filled in.

### GURPS

A GURPS class is a `name → (blurb, stats, skills)` entry, the same shape
as the in-box `TEMPLATES`. In your `rules.py`:

```python
# rules.py  (created by `realm init` — already imported & selected)
from realm.systems.gurps import GurpsSystem, TEMPLATES
from realm.systems.base import GameSystemRegistry, ChoiceStep

MY_TEMPLATES = {
    **TEMPLATES,                       # keep the in-box classes (optional)
    "pilot": (
        "sharp reflexes, ice nerves (DX 12; piloting, gunnery)",
        {'strength': 10, 'dexterity': 12, 'intelligence': 11, 'health': 10},
        {'piloting': 13, 'gunnery': 12, 'electronics': 11},
    ),
}


def _apply(player, name):
    """Write the chosen class's stats and skills onto the character."""
    _blurb, stats, skills = MY_TEMPLATES[name]
    for stat, value in stats.items():
        player.db.set(stat, value)
    for skill, level in skills.items():
        player.db.set(f"skill_{skill}", level)
    player.db.template = name


@GameSystemRegistry.register           # already present in the scaffold
class GameRules(GurpsSystem):          # your game's system (id from config)
    system_id = "mygame"

    def chargen_steps(self):
        steps = super().chargen_steps()          # template + bonus skill
        # Swap the template step's options for our expanded set.
        steps[0] = ChoiceStep(
            "template", "Pick your background:",
            {name: blurb for name, (blurb, _s, _k) in MY_TEMPLATES.items()},
            _apply,
        )
        return steps
```

Nothing else to wire — `config.py` already `import rules` and sets
`GAME_SYSTEM` to your game's id. (If you *didn't* use `realm init`, that
one-time wiring is: `import rules` in `config.py`, then
`GAME_SYSTEM = "your_id"`.) Restart and create a character to see it:

```text
create Maverick topgun
Pick your background:
  1. soldier — tough and dangerous …
  2. infiltrator — quick and quiet …
  3. face — silver-tongued …
  4. technician — gadget-minded …
  5. pilot — sharp reflexes, ice nerves …     ← your new class
```

Any skill you name (`piloting`, `gunnery`) should also appear in
`skill_defaults()` so untrained checks have a sensible fallback —
override that method too, spreading the parent's defaults:

```python
    def skill_defaults(self):
        return {**super().skill_defaults(),
                "piloting": ("dexterity", -4),
                "gunnery":  ("dexterity", -4)}
```

### D20

Identical shape — D20 classes are `CLASSES` entries. Subclass
`D20System`, spread `CLASSES`, add your own, and override `chargen_steps()`
the same way.

## Why not just edit `realm/systems/gurps.py`?

Because REALM is a library you build *on*, not an application you fork.
Editing the in-box dict works until you `pip install -U realm` and your
change vanishes — and it entangles your game with engine internals. The
subclass above lives entirely in your game directory, survives upgrades,
and is the same mechanism used to ship a whole new rules package (see
[Game Systems](game-systems.md)).

## Verifying

```bash
realm start
# telnet in, create a character, confirm your class appears and its
# stats land on the sheet:
create Test pw
# … pick your class …
points        # (alias: score) — check the skills were applied
```
