"""
Dispositions: NPCs remember how they feel about you.

The missing state behind reaction rolls, persuasion, and fast-talk:
an NPC's attitude toward a specific character, stored lean on the NPC
(``db.dispositions = {char_id: int}``) and consulted by behaviors
(guards let friends pass, aggressives spare them), commands
(greet/persuade/fasttalk), and softcode.

The scale is GURPS-flavored, centered on 0:

    <= -3  hostile      attacks / refuses on sight
    -2..-1 unfriendly   suspicious, obstructive
     0     neutral      by the book
    +1..+2 friendly     helpful, talkative
    >= +3  devoted      goes out of their way

``reaction_roll`` is the classic first-meeting mechanic — 3d6 high-good,
mapped onto the scale — and it MEMOIZES: the first impression sticks
until something (persuasion, betrayal, softcode) changes it.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject

DISPOSITION_ATTR = "dispositions"



def disposition_band(value: int) -> str:
    """Name the attitude a numeric disposition represents."""
    value = int(value)
    if value <= -3:
        return "hostile"
    if value <= -1:
        return "unfriendly"
    if value == 0:
        return "neutral"
    if value <= 2:
        return "friendly"
    return "devoted"


def get_disposition(npc: GameObject, other: GameObject) -> int:
    """
    How ``npc`` feels about ``other``.

    Falls back to ``db.default_disposition`` (a grumpy guard can default
    to -1), else 0. A ``hostile``-tagged NPC never reports above -3.
    """
    dispositions = npc.db.get(DISPOSITION_ATTR) or {}
    value = dispositions.get(other.id)
    if value is None:
        value = npc.db.get('default_disposition') or 0
    value = int(value)
    if npc.has_tag('hostile'):
        return min(value, -3)
    return value


def set_disposition(npc: GameObject, other: GameObject, value: int) -> int:
    """Set (clamped to -5..+5) and return npc's disposition toward other."""
    value = max(-5, min(5, int(value)))
    dispositions = dict(npc.db.get(DISPOSITION_ATTR) or {})
    dispositions[other.id] = value
    npc.db.set(DISPOSITION_ATTR, dispositions)
    return value


def adjust_disposition(npc: GameObject, other: GameObject, delta: int) -> int:
    """Shift npc's disposition toward other by delta; returns the new value."""
    return set_disposition(npc, other, get_disposition(npc, other) + int(delta))


def has_met(npc: GameObject, other: GameObject) -> bool:
    """Has this NPC formed an opinion (rolled or set) about other?"""
    return other.id in (npc.db.get(DISPOSITION_ATTR) or {})


def reaction_roll(
    npc: GameObject,
    other: GameObject,
    modifier: int = 0,
    *,
    dice: int | None = None,
) -> int:
    """
    First-impression roll (3d6 high-good + modifier), MEMOIZED: if the
    NPC already has an opinion it's returned unchanged. ``dice`` injects
    a fixed roll for tests/softcode-determined outcomes.

    Mapping (GURPS reaction table, compressed):
        <= 6  -> -2    7..9  -> -1    10..12 -> 0
        13..15 -> +1   >= 16 -> +2
    """
    if has_met(npc, other):
        return get_disposition(npc, other)

    roll = int(dice) if dice is not None else sum(
        random.randint(1, 6) for _ in range(3))
    roll += int(modifier)
    if roll <= 6:
        value = -2
    elif roll <= 9:
        value = -1
    elif roll <= 12:
        value = 0
    elif roll <= 15:
        value = 1
    else:
        value = 2
    # Layer the roll on top of the NPC's baseline temperament.
    value += int(npc.db.get('default_disposition') or 0)
    return set_disposition(npc, other, value)


__all__ = [
    "disposition_band",
    "get_disposition",
    "set_disposition",
    "adjust_disposition",
    "has_met",
    "reaction_roll",
]
