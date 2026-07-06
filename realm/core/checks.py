"""
Skill checks and opposed contests.

The default resolver is GURPS-shaped — roll 3d6, succeed on <= effective
skill — because that's REALM's reference ruleset, but games swap the
whole resolution function with :func:`set_check_resolver` (same
extension pattern as the render group formatter).

Skill levels are lean data, no classes: ``db.skill_<name>`` on the
actor. An unskilled actor falls back to an attribute default from
SKILL_DEFAULTS ("you can always try"), mirroring GURPS defaults —
e.g. stealth defaults to DX-5.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject


# skill -> (attribute name, default penalty). Games extend or replace.
SKILL_DEFAULTS: dict[str, tuple[str, int]] = {
    "stealth": ("dexterity", -5),
    "climbing": ("dexterity", -5),
    "jumping": ("dexterity", -4),
    "lockpicking": ("dexterity", -5),
    "observation": ("intelligence", -5),
    "electronics": ("intelligence", -5),
    "computer_operation": ("intelligence", -4),
    "traps": ("intelligence", -5),
    "fast_talk": ("intelligence", -5),
    "flee": ("dexterity", -2),
    "first_aid": ("intelligence", -5),
    "detect_lies": ("intelligence", -6),
    "disguise": ("intelligence", -5),
    "acting": ("intelligence", -5),
}


# Skills the ENGINE itself rolls (combat flee checks, movement gates).
# Game systems layer their tables over this floor but can't drop it —
# otherwise every live server silently loses the flee default.
ENGINE_SKILL_DEFAULTS: dict[str, tuple[str, int]] = {
    "flee": ("dexterity", -2),
}


def set_skill_defaults(defaults: dict[str, tuple[str, int]]) -> None:
    """
    Install the active GameSystem's untrained-skill table, merged over
    the engine floor (ENGINE_SKILL_DEFAULTS) — the rules package owns
    the skill list; the engine keeps the skills it rolls itself.
    """
    SKILL_DEFAULTS.clear()
    SKILL_DEFAULTS.update(ENGINE_SKILL_DEFAULTS)
    SKILL_DEFAULTS.update(defaults)


DEFAULT_ATTRIBUTE = 10


@dataclass
class CheckResult:
    """Outcome of a skill check."""

    success: bool
    margin: int        # effective - roll; positive = succeeded by that much
    roll: int
    effective: int     # skill level after modifiers
    skill: str

    def __bool__(self) -> bool:
        return self.success


def skill_level(obj: GameObject, skill: str) -> int:
    """
    An object's level in a skill.

    ``db.skill_<name>`` if trained; otherwise the attribute default from
    SKILL_DEFAULTS; otherwise DEFAULT_ATTRIBUTE - 5.
    """
    trained = obj.db.get(f"skill_{skill}")
    if trained is not None:
        return int(trained)

    attr, penalty = SKILL_DEFAULTS.get(skill, ("intelligence", -5))
    base = obj.db.get(attr)
    base = int(base) if base is not None else DEFAULT_ATTRIBUTE
    return base + penalty


def _default_resolver(obj: GameObject, skill: str, modifier: int) -> CheckResult:
    """3d6 roll-under vs effective skill (GURPS-style)."""
    effective = skill_level(obj, skill) + modifier
    roll = sum(random.randint(1, 6) for _ in range(3))
    # Criticals: 3-4 always succeed, 17-18 always fail.
    if roll <= 4:
        success = True
    elif roll >= 17:
        success = False
    else:
        success = roll <= effective
    return CheckResult(
        success=success,
        margin=effective - roll,
        roll=roll,
        effective=effective,
        skill=skill,
    )


CheckResolver = Callable[["GameObject", str, int], CheckResult]

_resolver: CheckResolver = _default_resolver


def set_check_resolver(resolver: CheckResolver | None) -> None:
    """Replace how checks resolve (None restores the 3d6 default)."""
    global _resolver
    _resolver = resolver or _default_resolver


# --- Condition modifiers (the banshee-wail pipeline) --------------------------
#
# Effects, gear, and environment change rolls WITHOUT every caller
# remembering to ask: check() sums registered providers into the
# modifier before the resolver sees it, so fear really is "-2 to
# everything" no matter who rolls or which ruleset resolves.
#
# The built-in provider reads ``db.check_mods`` — one dict, keyed by
# condition kind, entirely softcode-writable:
#
#     db.check_mods = {"fear": {"all": -2}, "blinded": {"observation": -6}}
#
# An entry may also be a bare int (applies to all checks). Effect
# behaviors (ModifierEffectBehavior, or any TimedEffectBehavior with a
# ``check_mods`` param) maintain their own entry and remove it on expiry.

ModifierProvider = Callable[["GameObject", str], int]


def _attr_modifier_provider(obj: GameObject, skill: str) -> int:
    mods = obj.db.get('check_mods')
    if not isinstance(mods, dict):
        return 0
    total = 0
    for entry in mods.values():
        if isinstance(entry, dict):
            total += int(entry.get('all', 0)) + int(entry.get(skill, 0))
        else:
            try:
                total += int(entry)
            except (TypeError, ValueError):
                continue
    return total


_modifier_providers: list[ModifierProvider] = [_attr_modifier_provider]


def add_modifier_provider(provider: ModifierProvider) -> None:
    """Register an extra condition-modifier source (darkness, encumbrance...)."""
    if provider not in _modifier_providers:
        _modifier_providers.append(provider)


def remove_modifier_provider(provider: ModifierProvider) -> None:
    _modifier_providers[:] = [p for p in _modifier_providers if p is not provider]


def condition_modifier(obj: GameObject, skill: str) -> int:
    """Sum every provider's modifier for this check; errors count as 0."""
    total = 0
    for provider in _modifier_providers:
        try:
            total += int(provider(obj, skill))
        except Exception:
            continue
    return total


def check(obj: GameObject, skill: str, modifier: int = 0) -> CheckResult:
    """
    Roll a skill check for an object.

    Condition modifiers (fear, blindness, buffs — see condition_modifier)
    are folded in here, upstream of the resolver, so every ruleset and
    injected test resolver inherits them.
    """
    return _resolver(obj, skill, modifier + condition_modifier(obj, skill))


def contest(
    actor: GameObject,
    actor_skill: str,
    opponent: GameObject,
    opponent_skill: str,
    actor_mod: int = 0,
    opponent_mod: int = 0,
) -> bool:
    """
    Opposed quick contest: both roll; the better margin of success wins.

    Returns True if the ACTOR wins. Ties and mutual failure go to the
    opponent (the status quo holds — the hider stays hidden when the
    spotter contests, the liar is caught when margins tie).
    """
    a = check(actor, actor_skill, actor_mod)
    b = check(opponent, opponent_skill, opponent_mod)
    if a.success and not b.success:
        return True
    if not a.success:
        return False
    return a.margin > b.margin


__all__ = [
    "SKILL_DEFAULTS",
    "CheckResult",
    "skill_level",
    "check",
    "contest",
    "set_check_resolver",
]
