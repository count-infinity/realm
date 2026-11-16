"""
How skills improve (MUD_PLAN step 5; docs/guides/progression.md).

Four models, chosen per skill by the skill definition's ``progression``
attribute, else the game system's ``default_progression``:

- ``points``: bought with character points (``improve``);
- ``practice``: raised at a trainer (``practice``), up to the trainer's floor;
- ``use``: every check of the skill, and every swing with a weapon of it,
  earns ``skill_xp_<name>`` toward the next level;
- ``idle``: ``study`` it, and it accrues from the wall clock, online or not.

Whatever the model, it writes the plain ``skill_<name>`` level, so
``skill_level()`` stays an attribute read and no ruleset knows.

The use model runs from ``GameSystem.on_skill_used``, which ``check()``
calls at its end and ``CombatSystem.attack`` calls after each attack roll.
It is synchronous, like ``check()``: it changes attributes and messages the
character, and never propagates an action.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from realm.core.action_types import ActionType
from realm.core.world import find_world

if TYPE_CHECKING:
    from realm.core.dice import CheckResult
    from realm.core.objects import GameObject
    from realm.core.propagation import Action
    from realm.std.rules.system import GameSystem

logger = logging.getLogger(__name__)

MODELS = ("points", "practice", "use", "idle")


def now() -> float:
    """The wall clock idle training runs on (tests replace it)."""
    return time.time()


def skill_key(name: str) -> str:
    """"Second Attack" -> "second_attack", the attribute spelling."""
    return "_".join(str(name).strip().lower().split())


def skill_def(skill: str) -> GameObject | None:
    """The ``skill_def`` object for ``skill``, if the world has one."""
    from realm.core.defs import def_kinds, def_objects
    if "skill" not in def_kinds():
        return None
    defs = def_objects("skill")
    key = skill_key(skill)
    return defs.get(key) or defs.get(key.replace("_", " "))


def _rules() -> GameSystem | None:
    world = find_world()
    return world.rules if world is not None else None


def progression_of(obj: GameObject, skill: str) -> str | None:
    """How ``skill`` improves for ``obj``: its definition's
    ``progression``, else the game system's ``default_progression``.
    None: it does not improve."""
    sdef = skill_def(skill)
    chosen = sdef.db.get("progression") if sdef is not None else None
    if chosen:
        return str(chosen).strip().lower()
    rules = _rules()
    return rules.default_progression if rules is not None else None


def trained(obj: GameObject, skill: str) -> int | None:
    """The character's own ``skill_<name>``, or None when never taught."""
    value = obj.db.get(f"skill_{skill_key(skill)}")
    return int(value) if value is not None else None


def starting_level(obj: GameObject, skill: str) -> int:
    """Where a model starts counting: the trained level, else the skill's
    untrained default (an attribute default a GURPS character already has),
    never below 0. Writing 1 over a default of 5 would lower the skill."""
    level = trained(obj, skill)
    if level is not None:
        return level
    from realm.std.rules.checks import skill_level
    return max(0, int(skill_level(obj, skill_key(skill))))


# --- learn by use -------------------------------------------------------------------


def _rule_gain(sdef: GameObject, obj: GameObject, level: int, success: bool,
               xp: int) -> int:
    """A builder's ``progress_rule``: an expression in the ``rule``
    profile with ``level``, ``success`` and ``xp`` bound, returning the
    experience to add (it mirrors ``resolve_rule``)."""
    from realm.core.safe_eval import eval_expression
    from realm.scripting.namespace import build_namespace
    namespace, _frame = build_namespace(
        'rule', executor=obj, enactor=obj, location=obj.location, subject=obj,
        extra={"level": level, "success": success, "xp": xp})
    try:
        return int(eval_expression(str(sdef.db.get("progress_rule")), namespace) or 0)
    except Exception as exc:
        logger.warning(f"skill_def {sdef.name!r}: progress_rule failed ({exc}); "
                       f"no experience awarded")
        return 0


def record_use(system: GameSystem, obj: GameObject, result: CheckResult) -> None:
    """The ``use`` model: a check or swing of a ``use`` skill earns
    experience (more for a success), nothing when the roll could not go
    either way, at or above the cap, or for a skill never taught (unless
    the definition says ``untrained_use``). Players only."""
    # A stand-in resolver (a test's, a game's) may return a bare result
    # without a skill name; there is then nothing to credit.
    skill = skill_key(getattr(result, "skill", "") or "")
    if not skill or not obj.is_player or progression_of(obj, skill) != "use":
        return
    if not system.check_was_open(result):
        return
    sdef = skill_def(skill)
    level = trained(obj, skill)
    if not level:
        if sdef is None or not sdef.db.get("untrained_use"):
            return
        level = starting_level(obj, skill) if level is None else 0
    cap = system.skill_cap(obj, skill)
    if cap is not None and level >= cap:
        return
    xp = int(obj.db.get(f"skill_xp_{skill}") or 0)
    if sdef is not None and sdef.db.get("progress_rule"):
        gain = _rule_gain(sdef, obj, level, bool(result.success), xp)
    else:
        gain = system.use_xp_gain(bool(result.success))
    if gain <= 0:
        return
    xp += gain
    if xp >= system.use_xp_needed(level):
        obj.db.set(f"skill_{skill}", level + 1)
        xp = 0
        obj.msg(f"You have become better at {skill.replace('_', ' ')}!")
    obj.db.set(f"skill_xp_{skill}", xp)


# --- idle training ------------------------------------------------------------------


def _rate(obj: GameObject, sdef: GameObject | None) -> float:
    """Skill points a minute: the primary attribute plus half the
    secondary (EVE's shape), from the definition's ``attributes``."""
    attrs = (sdef.db.get("attributes") if sdef is not None else None) \
        or ["intelligence", "wisdom"]
    primary = float(obj.db.get(str(attrs[0])) or 10)
    secondary = float(obj.db.get(str(attrs[1])) or 10) if len(attrs) > 1 else 0.0
    return primary + secondary / 2


def _max_offline() -> float:
    world = find_world()
    hours = float(world.setting("IDLE_TRAINING_MAX_HOURS", 0) or 0) if world else 0.0
    return hours * 3600 if hours > 0 else 0.0


def accrue_training(obj: GameObject) -> int:
    """Bank the time since ``training_since`` into the skill in
    ``training``, buying levels at ``idle_cost(level)`` × the definition's
    ``rank``, to the cap. Returns the levels gained (and tells the
    character). Lazy: nothing runs while the character is away, and this
    catches up whenever it is called."""
    skill = obj.db.get("training")
    since = obj.db.get("training_since")
    rules = _rules()
    if not skill or since is None or rules is None:
        return 0
    skill = skill_key(skill)
    moment = now()
    elapsed = max(0.0, moment - float(since))
    limit = _max_offline()
    if limit:
        elapsed = min(elapsed, limit)
    sdef = skill_def(skill)
    rank = float((sdef.db.get("rank") if sdef is not None else None) or 1)
    sp = float(obj.db.get(f"sp_{skill}") or 0) + _rate(obj, sdef) * elapsed / 60
    level = starting_level(obj, skill)
    cap = rules.skill_cap(obj, skill)
    gained = 0
    while (cap is None or level < cap) and sp >= rules.idle_cost(level) * rank:
        sp -= rules.idle_cost(level) * rank
        level += 1
        gained += 1
    if gained:
        obj.db.set(f"skill_{skill}", level)
        obj.msg(f"You have finished training {skill.replace('_', ' ')} to level {level}.")
    obj.db.set(f"sp_{skill}", sp)
    obj.db.training_since = moment
    return gained


def next_level_in(obj: GameObject) -> float | None:
    """Seconds until the skill in training gains its next level, or None."""
    skill = obj.db.get("training")
    rules = _rules()
    if not skill or rules is None:
        return None
    skill = skill_key(skill)
    sdef = skill_def(skill)
    rank = float((sdef.db.get("rank") if sdef is not None else None) or 1)
    left = rules.idle_cost(starting_level(obj, skill)) * rank - float(
        obj.db.get(f"sp_{skill}") or 0)
    return max(0.0, left) / _rate(obj, sdef) * 60


def prerequisites_unmet(obj: GameObject, skill: str) -> list[str]:
    """``["herbalism 5"]``: the definition's ``requires`` not yet met."""
    sdef = skill_def(skill)
    needs = sdef.db.get("requires") if sdef is not None else None
    if not isinstance(needs, dict):
        return []
    return [f"{name} {int(level)}" for name, level in needs.items()
            if (trained(obj, name) or 0) < int(level)]


def _online_players(store: Any) -> list[GameObject]:
    world = find_world()
    sessions = world.sessions if world is not None else None
    if sessions is not None:
        return [s.player for s in sessions.all_sessions() if s.player is not None]
    return list(store.find_cached(tag="player")) if store is not None else []


async def training_sweep(store: Any) -> None:
    """The ``rules`` reaper: catch up every online character in training,
    so "You have finished training ..." arrives while they play."""
    for player in _online_players(store):
        if player.db.get("training"):
            accrue_training(player)


async def login_observer(action: Action) -> None:
    """Catch up a character's training when it connects, and give it the
    ``food`` and ``water`` its game system declares if it was made before
    them (``GameSystem.fill_stomach``, MUD_PLAN 12.1)."""
    if action.action_type == ActionType.CONNECT and action.actor is not None:
        accrue_training(action.actor)
        rules = _rules()
        if rules is not None and action.actor.is_player:
            rules.fill_stomach(action.actor)


__all__ = ["MODELS", "now", "skill_key", "skill_def", "progression_of", "trained",
           "starting_level",
           "record_use", "accrue_training", "next_level_in", "prerequisites_unmet",
           "training_sweep", "login_observer"]
