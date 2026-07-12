"""
Dice and resolution primitives — the genre-neutral kernel mechanics a
game system's resolution rule composes from.

There is deliberately no "resolution mode" enum and no descriptor of
flags. A rule is an *expression* over small primitives:

    GURPS       margin_under(roll("3d6"), skill() + mod)
    D20         margin_over(roll("d20") + skill(), 15)
    Shadowrun   net_successes(attr("pool"), attr("tn"))     # graded: net hits
    PbtA        band(roll("2d6") + attr("cool"), 7, 10)     # miss / 7-9 / 10+
    Blades      highest(attr("pool"))                       # 6 / 4-5 / 1-3

Every reducer returns a :class:`CheckResult` — a *graded* outcome
(``margin`` carries the degree: margin of success, net successes, or
tier), never a bare bool. The primitives take numbers, not objects, so
they are entity-agnostic: a ship's ``gunnery`` and a person's ``skill``
flow through the identical machinery.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass


@dataclass
class CheckResult:
    """A graded resolution outcome (the one result type)."""

    success: bool
    margin: int        # degree: margin of success / net successes / tier
    roll: int          # the salient rolled value (total, top die, or count)
    effective: int     # the target / TN this was resolved against
    skill: str = ""

    def __bool__(self) -> bool:
        return self.success


# --- Rolling -----------------------------------------------------------------

# NdS, dS, dF (Fudge); optional ! (explode on max), kh/kl N (keep), +/- mod.
_DICE_RE = re.compile(
    r"^\s*(\d*)d(F|\d+)(!)?(?:k([hl])(\d+))?\s*([+-]\s*\d+)?\s*$", re.I
)


def roll_dice(n: int, sides: int, *, explode: bool = False,
              _cap: int = 100) -> list[int]:
    """Roll ``n`` dice of ``sides``; with ``explode`` a max face rerolls
    and adds (rule-of-six). Returns the individual dice (a *pool*)."""
    out: list[int] = []
    for _ in range(max(0, int(n))):
        v = random.randint(1, sides)
        total = v
        iters = 0
        while explode and v == sides and iters < _cap:
            v = random.randint(1, sides)
            total += v
            iters += 1
        out.append(total)
    return out


def roll(expr: str | int) -> int:
    """
    Roll a dice expression to a total. Supports ``NdS`` / ``dS``, Fudge
    ``NdF`` (each die -1/0/+1), ``!`` explode, ``khK`` / ``klK`` keep
    highest/lowest, and a trailing ``+K`` / ``-K`` modifier. A bare int
    passes through.
    """
    if isinstance(expr, int):
        return expr
    m = _DICE_RE.match(str(expr))
    if not m:
        raise ValueError(f"bad dice expression: {expr!r}")
    n = int(m.group(1)) if m.group(1) else 1
    face = m.group(2)
    explode = bool(m.group(3))
    keep_dir, keep_n = m.group(4), m.group(5)
    mod = int(m.group(6).replace(" ", "")) if m.group(6) else 0

    if face.lower() == "f":
        dice = [random.randint(-1, 1) for _ in range(n)]
    else:
        dice = roll_dice(n, int(face), explode=explode)
    if keep_n is not None:
        dice = sorted(dice, reverse=(keep_dir.lower() == "h"))[: int(keep_n)]
    return sum(dice) + mod


# --- Reducers (each returns a graded CheckResult) ----------------------------

def margin_under(rolled: int, target: int, *, skill: str = "") -> CheckResult:
    """Roll-under (GURPS, CoC): success if ``rolled <= target``; margin is
    how far under."""
    return CheckResult(rolled <= target, target - rolled, rolled, target, skill)


def margin_over(rolled: int, target: int, *, skill: str = "") -> CheckResult:
    """Roll-over (D20): success if ``rolled >= target``; margin is how far
    over."""
    return CheckResult(rolled >= target, rolled - target, rolled, target, skill)


def net_successes(pool: int, tn: int, *, sides: int = 6, explode: bool = True,
                  skill: str = "") -> CheckResult:
    """Dice-pool success-counting (Shadowrun, WoD): roll ``pool`` dice,
    count those ``>= tn``. Graded by the count of successes."""
    dice = roll_dice(pool, sides, explode=explode)
    count = sum(1 for d in dice if d >= tn)
    return CheckResult(count >= 1, count, count, tn, skill)


def highest(pool: int, *, sides: int = 6, skill: str = "") -> CheckResult:
    """Highest-die tiers (Blades): 6 -> full (2), 4-5 -> partial (1),
    else miss (0)."""
    dice = roll_dice(pool, sides)
    top = max(dice) if dice else 0
    tier = 2 if top >= 6 else (1 if top >= 4 else 0)
    return CheckResult(tier >= 1, tier, top, sides, skill)


def band(value: int, *thresholds: int, skill: str = "") -> CheckResult:
    """Tiered outcome (PbtA): tier = how many ascending thresholds
    ``value`` clears. ``band(2d6+stat, 7, 10)`` -> 0 miss / 1 partial /
    2 full."""
    tier = sum(1 for t in sorted(thresholds) if value >= t)
    floor = min(thresholds) if thresholds else 0
    return CheckResult(tier >= 1, tier, value, floor, skill)


__all__ = [
    "CheckResult",
    "roll",
    "roll_dice",
    "margin_under",
    "margin_over",
    "net_successes",
    "highest",
    "band",
]
