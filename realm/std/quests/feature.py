"""
The ``quests`` feature.

Quests as data (``quest_def``), tracked by the engine: who has which, how
far along they are, and what they get (MUD_PLAN step 15). See
docs/guides/quests.md.

It requires nothing: the game system's award (``rules``), money
(``economy``), achievements, companions (a pet's kill is its master's)
and parties (``social``) are reached through their services, and a
reward whose feature is absent is skipped with a WARNING.
"""

from __future__ import annotations

from realm.features import Feature
from realm.std.quests import softcode
from realm.std.quests.behaviors import QuestGiverBehavior
from realm.std.quests.commands import cmd_quest, cmd_quests, cmd_talk
from realm.std.quests.definitions import parse_quest
from realm.std.quests.quests import (
    ACCEPT,
    ADVANCE,
    COMPLETE,
    FAIL,
    TALK,
    clear_index,
    expire_all,
    quest_marker,
    quest_observer,
    rebuild,
)

feature = Feature(
    'quests',
    doc='Quests as data: stages, objectives tracked by the engine, rewards.',
)

feature.def_kind("quest", "quest_def", parse_quest)

feature.command('quests', cmd_quests, aliases=['journal'], category='quests',
                help_text='Your quest journal', usage='quests [done]')
feature.command('quest', cmd_quest, category='quests',
                help_text='Take, follow and hand in quests',
                usage='quest [list | <name> | accept <name> | complete [<name>] | '
                      'abandon <name>]')
feature.command('talk', cmd_talk, category='quests', help_text='Talk to someone here',
                usage='talk <someone>')

feature.behavior(QuestGiverBehavior)
feature.marker(quest_marker)
feature.observer(quest_observer)
feature.reaper(expire_all)
feature.on_reload(rebuild)
feature.on_close(clear_index)


@feature.on_install
def _fresh_index(world) -> None:
    clear_index()


@feature.on_boot
async def _read_definitions(world) -> None:
    """A malformed quest is reported, by name, at boot."""
    rebuild(world)


for _type, _hook, _doc, _payload in (
        (ACCEPT, "QUESTACCEPT", "a character took a quest (`enactor`; the target is the "
         "giver, or the quest's definition)", {"quest": "the quest's name"}),
        (ADVANCE, "QUESTADVANCE", "a character finished a stage of a quest (`enactor`)",
         {"quest": "the quest's name",
          "stage": "the new stage number, or 'ready' when it waits to be handed in"}),
        (COMPLETE, "QUESTCOMPLETE", "a character completed a quest (`enactor`; the target "
         "is the giver it was handed in to, or the quest's definition)",
         {"quest": "the quest's name"}),
        (FAIL, "QUESTFAIL", "a character's quest ended unfinished (`enactor`)",
         {"quest": "the quest's name", "reason": "expired, abandoned or failed"}),
        (TALK, "TALK", "a character talks to this object (`talk <npc>`)", {})):
    feature.event(_type, hook=_hook, doc=_doc, payload=_payload)

for _fn in (softcode.quest_state, softcode.quest_count):
    feature.softfn(_fn, group='Quests', readonly=True)
for _fn in (softcode.quest_offer, softcode.quest_advance, softcode.quest_complete,
            softcode.quest_fail):
    feature.softfn(_fn, group='Quests', harm=True)
feature.queue_kind("quest_offer", softcode.queued_offer)
feature.queue_kind("quest_advance", softcode.queued_advance)
feature.queue_kind("quest_complete", softcode.queued_complete)
feature.queue_kind("quest_fail", softcode.queued_fail)
