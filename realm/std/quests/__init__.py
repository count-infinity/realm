"""The ``quests`` feature. Its declarations are in ``feature.py``; this
package holds its parts, which import without loading the feature.

Public: ``find_quest(name)``, ``state(player, quest)``, ``accept``,
``credit``, ``complete`` and ``fail`` (``realm.std.quests.quests``)."""

from realm._exports import exports

__all__, __getattr__, __dir__ = exports(globals(), {
    "find_quest": "realm.std.quests.quests:find_quest",
    "state": "realm.std.quests.quests:state",
    "accept": "realm.std.quests.quests:accept",
    "credit": "realm.std.quests.quests:credit",
    "complete": "realm.std.quests.quests:complete",
    "fail": "realm.std.quests.quests:fail",
})
