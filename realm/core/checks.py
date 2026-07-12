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

from collections.abc import Callable
from typing import TYPE_CHECKING

from realm.core.dice import CheckResult, margin_under, roll

if TYPE_CHECKING:
    from realm.core.objects import GameObject


# Skills the ENGINE itself rolls (combat flee checks, movement gates).
# Game systems layer their tables over this floor but can't drop it —
# otherwise every live server silently loses the flee default.
ENGINE_SKILL_DEFAULTS: dict[str, tuple[str, int]] = {
    "flee": ("dexterity", -2),
}


# skill -> (attribute name, default penalty). The active GameSystem
# installs its full table over this at server start (set_skill_defaults);
# the seed is the engine floor so bare library use still works.
SKILL_DEFAULTS: dict[str, tuple[str, int]] = dict(ENGINE_SKILL_DEFAULTS)


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


def skill_level(obj: GameObject, skill: str) -> int:
    """
    An object's level in a skill.

    ``db.skill_<name>`` if trained; otherwise the attribute default from
    SKILL_DEFAULTS; otherwise DEFAULT_ATTRIBUTE - 5.
    """
    trained = obj.db.get(f"skill_{skill}")
    if trained is not None:
        return int(trained)

    # Untrained: the governing attribute + penalty come from the active
    # system's table (data it owns). A skill the table doesn't list gets a
    # neutral floor — NOT a hardcoded humanoid stat, so a ship or door isn't
    # silently rated off an "intelligence" it doesn't have.
    entry = SKILL_DEFAULTS.get(skill)
    if entry is None:
        return DEFAULT_ATTRIBUTE - 5
    attr, penalty = entry
    base = obj.db.get(attr)
    base = int(base) if base is not None else DEFAULT_ATTRIBUTE
    return base + penalty


def default_resolver(obj: GameObject, skill: str, modifier: int) -> CheckResult:
    """A **neutral** zero-config fallback: 3d6 roll-under vs effective
    skill, with no game-specific policy (no criticals — those belong to a
    ruleset). It exists only so ``check()`` works before a game system is
    installed; every real game installs its own resolver (GURPS crits live
    in GurpsSystem, D20's rule in D20System, or a softcode ``resolve_rule``
    — see resolve_with_rule). The kernel does not encode a game's rules."""
    effective = skill_level(obj, skill) + modifier
    return margin_under(roll("3d6"), effective, skill=skill)


def resolve_with_rule(
    obj: GameObject, skill: str, modifier: int, rule: str
) -> CheckResult:
    """
    Resolve a check by evaluating a **softcode resolution rule** — the
    "game system as data" path. The rule is an expression over the dice
    primitives (see realm.core.dice), evaluated with the entity's data
    bound *by name* (so a ship's ``gunnery`` and a person's ``skill`` use
    the identical resolver):

        margin_under(roll('3d6'), skill() + mod)     # GURPS
        net_successes(attr('pool'), attr('tn'))      # a dice-pool system

    Names in scope: the reducers (``margin_under``/``margin_over``/
    ``net_successes``/``highest``/``band``) and ``roll``; ``skill(name=…)``
    (this skill's level, or a named one), ``attr(name)`` (a raw attribute),
    and ``mod`` (the folded modifier). The rule must return a CheckResult
    (a reducer) — or a bare number, read as a success margin.
    """
    from realm.core import dice
    from realm.core.safe_eval import eval_expression

    namespace = {
        "roll": dice.roll,
        "margin_under": dice.margin_under,
        "margin_over": dice.margin_over,
        "net_successes": dice.net_successes,
        "highest": dice.highest,
        "band": dice.band,
        "skill": lambda name=skill: skill_level(obj, name),
        "attr": lambda name: obj.db.get(name) or 0,
        "mod": modifier,
        "skill_name": skill,
    }
    result = eval_expression(rule, namespace)
    if isinstance(result, CheckResult):
        if not result.skill:
            result.skill = skill
        return result
    # A bare number is read as a margin (>0 = success by that much).
    margin = int(result)
    return CheckResult(margin > 0, margin, margin, 0, skill)


CheckResolver = Callable[["GameObject", str, int], CheckResult]

_resolver: CheckResolver = default_resolver


def set_check_resolver(resolver: CheckResolver | None) -> None:
    """Replace how checks resolve (None restores the 3d6 default)."""
    global _resolver
    _resolver = resolver or default_resolver


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
    result = _resolver(obj, skill, modifier + condition_modifier(obj, skill))
    # Roll visibility (@rolls on): echo the dice to a curious builder.
    if obj.db.get('show_rolls'):
        obj.msg(f"[roll {result.skill}: {result.roll} vs {result.effective} "
                f"-> {'success' if result.success else 'failure'} "
                f"(margin {result.margin:+d})]")
    return result


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
    "default_resolver",
    "resolve_with_rule",
    "skill_level",
    "check",
    "contest",
    "set_check_resolver",
]
