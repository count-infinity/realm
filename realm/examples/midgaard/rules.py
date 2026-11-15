"""
Midgaard — your game's rules package.

This is YOUR copy of the game system, and the blessed place to shape how
characters are made and how skills work. Out of the box it behaves
*exactly* like the built-in Merc rules — it just subclasses them. You
customize by uncommenting the hooks below; you never edit the `realm`
package itself, so upgrading REALM can't clobber your game.

`config.py` selects this class with `GAME_SYSTEM = "rules.GameRules"` (a
dotted import path), so THIS file is the single place your rules are
decided. The base class GameRules subclasses is the choice: swap it
for another built-in system (GurpsSystem, D20System, MercSystem) and the
same world runs those rules.

Learn the model:
  - Concepts → "How a Character Is Born"
  - How-To   → "Add a Character Class"
  - How-To   → "Customize Character Creation"

Prefer a built-in with no changes? Delete this file and set
`GAME_SYSTEM = "realm.games.merc.system.MercSystem"` in config.py.
"""

from __future__ import annotations

from realm.games.merc import MercSystem


class GameRules(MercSystem):
    """Your game's rules. Inherits Merc; override the hooks to customize."""

    # system_id stays "merc": characters are stamped with it, and a
    # Midgaard database made before this file existed keeps matching.

    # --- Add or change character classes -----------------------------------
    #
    # A Merc class is a dict: its blurb, hit die (hit points gained per
    # level), thac0_rate (levels per point of THAC0; lower fights better),
    # mana per level, starting stats, starting skill percentages and the
    # weapon it starts with. Uncomment to offer your own alongside (or
    # instead of) the built-ins:
    #
    # from realm.games.merc import MERC_CLASSES
    #
    # MY_CLASSES = {
    #     **MERC_CLASSES,                    # keep the stock classes (optional)
    #     "ranger": {
    #         "blurb": "a woodland scout: a good hit die, stealth and tracking",
    #         "hit_die": 8, "thac0_rate": 1, "mana_per_level": 2,
    #         "stats": {"dexterity": 16, "wisdom": 14},
    #         "skills": {"melee": 35, "stealth": 30, "tracking": 40},
    #         "starting_weapon": {"name": "a hunting knife", "damage_dice": "1d4"},
    #     },
    # }
    #
    # def _classes(self):
    #     # Chargen, the first-level hit points and the starting weapon all
    #     # read the class from here.
    #     return self.MY_CLASSES

    # --- Skills your classes reference -------------------------------------
    #
    # Skills are percentages. Give any new skill an untrained default:
    # (attribute, penalty), so an untaught character rolls near zero.
    #
    # def skill_defaults(self):
    #     return {**super().skill_defaults(),
    #             "tracking": ("wisdom", -50)}

    # --- No creation menu: instant characters ------------------------------
    #
    # Return [] to skip chargen entirely (e.g. drop players into an in-world
    # training school instead). See the "Customize Character Creation"
    # how-to.
    #
    # def chargen_steps(self):
    #     return []
