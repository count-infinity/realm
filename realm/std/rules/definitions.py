"""
Skills and classes as *data*, not hardcoded Python.

A game system's mechanics stay in code (how dice resolve), but its
*content* — which skills exist, which classes chargen offers — lives in
the world as ordinary tagged objects a builder can `@create` and edit,
or an area file can `@import`. This is the first step of the data-driven
rules kernel: the system reads these definitions instead of a fixed dict.

Conventions:

    a **skill** is an object tagged ``skill_def``
        name   = the skill's name (e.g. "piloting")
        attrs  = { stat: <governing attribute>, penalty: <untrained default> }

    a **class** is an object tagged ``class_def``
        name   = the class/background name (e.g. "pilot")
        attrs  = { blurb: <one-line description>,
                   stats:  { strength: 10, ... },     # applied at chargen
                   skills: { piloting: 13, ... } }

A system **merges** ``skill_def`` and ``class_def`` objects over its
built-in tables — data wins by name, so defining one adds (or overrides)
it rather than replacing the set. A world with no definitions runs on the
built-ins unchanged. (Suppressing a specific built-in is a future explicit
opt-out, not an emergent side effect of adding one.)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.attrflags import mark_system
from realm.core.objects import GameObject

if TYPE_CHECKING:
    from realm.core.objects import GameObject

SKILL_DEF_TAG = "skill_def"
CLASS_DEF_TAG = "class_def"


# --- Reading definitions from the world --------------------------------------

def parse_skill_def(obj: GameObject) -> tuple[str, int] | None:
    """A ``skill_def`` as ``(stat, penalty)``; None (skipped) when incomplete."""
    stat = obj.db.get("stat")
    penalty = obj.db.get("penalty")
    if stat is None or penalty is None:
        return None
    return (str(stat), int(penalty))


def parse_class_def(obj: GameObject) -> tuple[str, dict, dict] | None:
    """A ``class_def`` as ``(blurb, stats, skills)``; None when malformed."""
    blurb = obj.db.get("blurb") or obj.description or ""
    stats = obj.db.get("stats") or {}
    skills = obj.db.get("skills") or {}
    if not isinstance(stats, dict) or not isinstance(skills, dict):
        return None
    return (str(blurb), dict(stats), dict(skills))


# --- Creating definitions (for seeding, OLC, and tests) ----------------------

def define_skill(name: str, stat: str, penalty: int) -> GameObject:
    """Build a ``skill_def`` object (caller adds it to the world)."""

    obj = GameObject(name=name, tags=[SKILL_DEF_TAG])
    obj.db.set("stat", str(stat))
    obj.db.set("penalty", int(penalty))
    return obj


def define_class(
    name: str, blurb: str, stats: dict, skills: dict
) -> GameObject:
    """Build a ``class_def`` object (caller adds it to the world)."""

    obj = GameObject(name=name, description=str(blurb), tags=[CLASS_DEF_TAG])
    obj.db.set("blurb", str(blurb))
    obj.db.set("stats", dict(stats))
    obj.db.set("skills", dict(skills))
    return obj


def apply_class(player: GameObject, blurb_stats_skills: tuple[str, dict, dict],
                name: str, *, marker: str = "template") -> None:
    """Write a class definition's stats and skills onto a character; record
    the chosen class under ``marker`` (GURPS uses ``template``, D20
    ``character_class``)."""
    _blurb, stats, skills = blurb_stats_skills
    for stat, value in stats.items():
        player.db.set(stat, value)
    for skill, level in skills.items():
        player.db.set(f"skill_{skill}", level)
    player.db.set(marker, name)
    # A class's stats are the character's characteristics — system-owned, so
    # neither the player nor a plain builder can rewrite them after creation.
    # Skills stay writable: they are earned and spent through the CP economy.
    if stats:
        mark_system(player, *stats.keys())


__all__ = [
    "SKILL_DEF_TAG",
    "CLASS_DEF_TAG",
    "parse_skill_def",
    "parse_class_def",
    "define_skill",
    "define_class",
    "apply_class",
]
