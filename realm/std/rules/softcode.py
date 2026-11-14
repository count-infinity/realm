"""
Softcode functions: Skill checks and the subject helpers.

The ``rules`` feature declares each (``feature.py``, with its group and
flags); the first parameter is the run's ``ScriptFrame``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

def skill_check(frame, obj, skill: str, modifier: int = 0) -> bool:
    """Roll a skill check for an object (name/#id or object).

    Example: skill_check(enactor, 'stealth', -2)
    """
    from realm.std.rules.checks import check as _check
    target = frame.resolve(obj)
    if target is None:
        return False
    return bool(_check(target, str(skill), int(modifier)))

def check_roll(frame, obj, skill: str, modifier: int = 0):
    """Roll a skill check and return the GRADED, condition-modified result.

    Like :meth:`skill_check`, but hands back the whole ``CheckResult``
    instead of just pass/fail — read ``.success``, ``.margin`` (degree
    of success), ``.roll`` and ``.effective`` off it. And unlike the
    hand-rolled ``margin_under(roll('3d6'), get_attr(me, 'skill', 8))``
    idiom, this goes through the real ``check()`` pipeline, so
    ``check_mods`` (fear, darkness, a meal buff, encumbrance) are folded
    in. That idiom reads the *trained* level raw and silently ignores
    every condition — a fear-struck crafter rolled as if calm.

    Returns a failing result (margin 0) for an unresolvable object.

    Example: r = check_roll(enactor, 'cooking'); quality = r.margin // 2
    """
    from realm.core.dice import CheckResult
    from realm.std.rules.checks import check as _check
    target = frame.resolve(obj)
    if target is None:
        return CheckResult(False, 0, 0, 0, str(skill))
    return _check(target, str(skill), int(modifier))

def contest(frame, actor, actor_skill: str, opponent, opponent_skill: str) -> bool:
    """Opposed quick contest; True if the actor wins.

    Example: contest(enactor, 'fast_talk', me, 'detect_lies')
    """
    from realm.std.rules.checks import contest as _contest
    a = frame.resolve(actor)
    b = frame.resolve(opponent)
    if a is None or b is None:
        return False
    return _contest(a, str(actor_skill), b, str(opponent_skill))

def skill(frame, name: str) -> int:
    """The subject's effective level in a skill (trained, else its default).

    The subject is the enactor in a script, the viewer in an inline block
    or ``@detail`` condition, the caller in a lock, the roller in a rule.

    Example: [[result = 'You read the runes.' if skill('runes') >= 12 else '']]
    """
    from realm.std.rules.checks import skill_level
    if frame.subject is None:
        return 0
    return skill_level(frame.subject, str(name))

def check(frame, name: str, mod: int = 0) -> bool:
    """Roll a skill check AS the subject; True on success.

    The subject is the enactor in a script, the viewer in an inline block
    or ``@detail`` condition, the caller in a lock, the roller in a rule.
    For the graded result use ``check_roll(obj, skill, mod)``.

    Example: [[result = ' A loose flagstone.' if check('observation') else '']]
    """
    from realm.std.rules.checks import check as _check
    if frame.subject is None:
        return False
    return bool(_check(frame.subject, str(name), int(mod)))
