"""The ``quest_giver`` behavior (MUD_PLAN 15.3)."""

from __future__ import annotations

from realm.core.behaviors import Behavior


class QuestGiverBehavior(Behavior):
    """Offers quests: ``quest list`` shows them to the players in the room,
    and a ``(!)`` beside the NPC's name says it has one for the looker."""

    behavior_id = "quest_giver"
    param_spec = {
        'quests': ([], "the names of the quests this NPC offers (a quest whose "
                       "`giver` is this NPC needs no entry)"),
    }


__all__ = ["QuestGiverBehavior"]
