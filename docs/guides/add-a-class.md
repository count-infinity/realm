# How-To: Add a Character Class

**Goal:** add a new selectable background (a "class") to character
creation without touching the engine.

If you haven't yet, skim [How a Character Is Born](../concepts/character-creation.md)
first — it explains why a "class" is just a dict entry.

## GURPS: add a template

Classes for the GURPS system are entries in the `TEMPLATES` dict in
`realm/systems/gurps.py`. Each is `name → (blurb, stats, skills)`:

```python
TEMPLATES = {
    "soldier": ( … ),
    "infiltrator": ( … ),

    # your new class:
    "pilot": (
        "sharp reflexes, ice nerves (DX 12; piloting, gunnery)",
        {'strength': 10, 'dexterity': 12, 'intelligence': 11, 'health': 10},
        {'piloting': 13, 'gunnery': 12, 'electronics': 11},
    ),
}
```

That's the whole change. `chargen_steps()` builds the creation menu from
this dict, so `pilot` now appears as an option and its stats/skills are
applied when chosen. Any skill you name (`piloting`, `gunnery`) should
also have an entry in `skill_defaults()` so untrained checks have a
sensible fallback — otherwise it defaults to DX-5.

Restart the server and create a character to see it:

```text
create Maverick topgun
Pick your background:
  1. soldier — tough and dangerous …
  2. infiltrator — quick and quiet …
  3. face — silver-tongued …
  4. technician — gadget-minded …
  5. pilot — sharp reflexes, ice nerves …     ← your new class
```

## D20: add a class

Identical shape in `realm/systems/d20.py`, the `CLASSES` dict:

```python
CLASSES = {
    "fighter": ( … ),
    "rogue":   ( … ),
    "ranger": (
        "a hunter of the wilds",
        {'strength': 13, 'dexterity': 14, 'constitution': 12},
        {'survival': 4, 'stealth': 2, 'perception': 3},
    ),
}
```

## Doing it without editing `realm/`

Editing the in-box dict is fine for your own deployment, but the clean
way — the one that survives upgrading REALM — is to **subclass the
system** and override its options from your own `config.py`. You get the
in-box classes plus yours, and you never patch the package:

```python
# mygame/mysystem.py
from realm.systems.gurps import GurpsSystem, TEMPLATES
from realm.systems.base import GameSystemRegistry, ChoiceStep

MY_TEMPLATES = {
    **TEMPLATES,
    "pilot": ("sharp reflexes …", {'dexterity': 12, …}, {'piloting': 13, …}),
}


def _apply(player, name):
    """Write the chosen template's stats and skills onto the character."""
    _blurb, stats, skills = MY_TEMPLATES[name]
    for stat, value in stats.items():
        player.db.set(stat, value)
    for skill, level in skills.items():
        player.db.set(f"skill_{skill}", level)
    player.db.template = name


@GameSystemRegistry.register
class MyGurps(GurpsSystem):
    system_id = "mygurps"

    def chargen_steps(self):
        steps = super().chargen_steps()
        # Replace the template step's options with our expanded set.
        steps[0] = ChoiceStep(
            "template", "Pick your background:",
            {name: blurb for name, (blurb, _s, _k) in MY_TEMPLATES.items()},
            _apply,
        )
        return steps
```

```python
# mygame/config.py
import mysystem            # registers MyGurps at import
GAME_SYSTEM = "mygurps"
```

Because the engine imports `config.py` at boot, importing your module
there is enough to register the system. See
[Game Systems](game-systems.md) for the full custom-system reference.

## Verifying

```bash
realm start
# telnet in, create a character, confirm your class appears and its
# stats land on the sheet:
create Test pw
# … pick your class …
score        # or: points   — check the skills were applied
```
