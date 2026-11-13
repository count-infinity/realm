"""
Softcode functions: Dice, numbers and conditionals.

Each function is registered with ``@softfn``; one that takes the run's
``ScriptFrame`` as ``frame`` reads the executor, enactor, store and queue
from it. See ``realm/scripting/registry.py`` for the flags.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from realm.scripting.registry import softfn

if TYPE_CHECKING:
    pass

@softfn(takes_frame=False, group='Dice & skill checks', readonly=True)
def rand(low: int = 0, high: int = 100) -> int:
    """Random integer between low and high (inclusive).

    Example: rand(1, 100)
    """
    return random.randint(int(low), int(high))

@softfn(takes_frame=False, group='Dice & skill checks', readonly=True)
def dice(num: int = 1, sides: int = 6, modifier: int = 0) -> int:
    """
    Roll dice: NdS+M

    Args:
        num: Number of dice
        sides: Sides per die
        modifier: Added to total

    Example: dice(3, 6)   # 3d6
    """
    num = max(1, min(num, 100))  # Limit dice count
    sides = max(1, min(sides, 1000))  # Limit sides
    total = sum(random.randint(1, sides) for _ in range(num))
    return total + modifier

@softfn(takes_frame=False, group='Math & logic', readonly=True)
def clamp(value: int | float, low: int | float, high: int | float) -> int | float:
    """Clamp value between low and high.

    Example: clamp(damage, 1, 10)
    """
    return max(low, min(value, high))

@softfn(takes_frame=False, group='Math & logic', readonly=True)
def floor(value: float) -> int:
    """Round down to integer.

    Example: floor(7.9)                # 7
    """
    import math
    return math.floor(value)

@softfn(takes_frame=False, group='Math & logic', readonly=True)
def ceil(value: float) -> int:
    """Round up to integer.

    Example: ceil(7.1)                 # 8
    """
    import math
    return math.ceil(value)

@softfn(takes_frame=False, group='Math & logic', readonly=True)
def if_else(condition: bool, true_val: Any, false_val: Any) -> Any:
    """Conditional expression.

    Example: if_else(credits(enactor) >= 10, 'Welcome!', 'No coin, no entry.')
    """
    return true_val if condition else false_val

@softfn(takes_frame=False, group='Math & logic', readonly=True)
def switch(value: Any, *cases: Any) -> Any:
    """
    Switch statement.

    Args: value, case1, result1, case2, result2, ..., default

    Example: switch(tag_value(here, 'zone'), 'castle', 'Halt!',
             'forest', 'Rustle...', 'Silence.')
    """
    i = 0
    while i < len(cases) - 1:
        if cases[i] == value:
            return cases[i + 1]
        i += 2
    # Return default if odd number of args
    if len(cases) % 2 == 1:
        return cases[-1]
    return None
