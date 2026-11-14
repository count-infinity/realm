"""
Softcode functions: the dice and resolution primitives (``realm.core.dice``),
the pieces a game system's resolution rule composes from.
"""

from __future__ import annotations

from realm.scripting.registry import softcode_function


# The dice and resolution primitives (realm.core.dice): the pieces a game
# system's resolution rule composes from.
def _register_dice() -> None:
    from realm.core import dice
    for fn in (dice.roll, dice.margin_under, dice.margin_over,
               dice.net_successes, dice.highest, dice.band):
        softcode_function(group="Dice & skill checks", readonly=True)(fn)


_register_dice()
