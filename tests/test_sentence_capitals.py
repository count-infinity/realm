"""
Sentence-initial names: capitalized when the game asks for it, as ROM's
``act()`` does (BACKLOG 2026-11-16: "the beastly fido hits you", "the
cityguard arrives.").

ROM capitalizes the first letter of what ``act()`` sends and leaves
``send_to_char`` as written. That is ROM's presentation, not every game's:
the kernel sends lines exactly as written and offers the
``feature.line_formatter`` seam; ``basics``' ``CAPITALIZE_LINES`` setting
(off by default, on in the Merc scaffold and Midgaard) installs ROM's rule
on the two ``act()``-like paths, ``deliver_messages`` (every templated
message: movement, combat, verbs, socials) and a room broadcast
(``msg_contents``: softcode ``remit``/``oemit``, a death, a scavenger). A
line sent straight to one object (``obj.msg``, softcode ``pemit``, command
output) is ``send_to_char``: left as written either way.
"""

from __future__ import annotations

from realm.config.loader import Settings
from realm.core.markup import capitalize
from realm.core.movement import move_through_exit
from realm.core.propagation import Action, deliver_messages
from realm.core.world import format_line
from realm.testing import Simulator


def _capitalizing() -> Simulator:
    """A world whose config.py says ``CAPITALIZE_LINES = True``."""
    return Simulator(settings=Settings(raw={"CAPITALIZE_LINES": True}))


class TestCapitalize:

    def test_the_first_letter(self):
        assert capitalize("the cityguard arrives.") == "The cityguard arrives."
        assert capitalize("You hit it.") == "You hit it."

    def test_markup_is_stepped_over(self):
        assert capitalize("|ythe cityguard|n arrives.") == "|yThe cityguard|n arrives."
        assert capitalize("|[r|hthe fire|n roars.") == "|[r|hThe fire|n roars."

    def test_only_the_first_character_of_the_message(self):
        # Not every line: a wrapped description's second line is prose.
        assert capitalize("the fido\naround its teeth.") == "The fido\naround its teeth."
        assert capitalize("  a leather cap") == "  a leather cap"
        assert capitalize("<10hp 100m 100mv>") == "<10hp 100m 100mv>"
        assert capitalize("||literal pipe") == "||literal pipe"
        assert capitalize("") == ""
        assert capitalize("|n") == "|n"


async def test_a_game_without_the_rule_sends_lines_as_written():
    # A MUSH, a GURPS game: "the cityguard" stays lowercase wherever it falls.
    sim = Simulator()
    try:
        here, there = sim.room("Gate"), sim.room("Square")
        door = sim.obj("north", location=here, tags=["exit"], destination=there.id)
        guard = sim.obj("the cityguard", location=here, tags=["npc"])
        pat = sim.player("Pat", location=there)
        action = Action(actor=guard, target=pat, action_type="event:test")
        action.add_message("target", "{actor} hits you!")
        deliver_messages(action)
        assert sim.seen(pat) == ["the cityguard hits you!"]
        assert await move_through_exit(guard, there, exit_obj=door)
        assert "the cityguard arrives." in sim.seen(pat)
        there.msg_contents("the beastly fido falls dead!")
        assert sim.seen(pat) == ["the beastly fido falls dead!"]
        assert format_line("the guildmaster teaches:") == "the guildmaster teaches:"
    finally:
        sim.close()


async def test_a_templated_message_starts_capitalized():
    sim = _capitalizing()
    try:
        room = sim.room("Square")
        guard = sim.obj("the cityguard", location=room, tags=["npc"])
        pat = sim.player("Pat", location=room)
        action = Action(actor=guard, target=pat, action_type="event:test")
        action.add_message("room", "{actor} arrives.")
        action.add_message("target", "{actor} hits you!")
        deliver_messages(action)
        assert sim.seen(pat) == ["The cityguard hits you!"]     # the room line is others'
        sam = sim.player("Sam", location=room)
        action = Action(actor=guard, target=pat, action_type="event:test")
        action.add_message("room", "{actor} arrives.")
        deliver_messages(action)
        assert sim.seen(sam) == ["The cityguard arrives."]
    finally:
        sim.close()


async def test_walking_in_and_a_room_broadcast_are_capitalized():
    sim = _capitalizing()
    try:
        here, there = sim.room("Gate"), sim.room("Square")
        door = sim.obj("north", location=here, tags=["exit"], destination=there.id)
        guard = sim.obj("the cityguard", location=here, tags=["npc"])
        pat = sim.player("Pat", location=there)
        assert await move_through_exit(guard, there, exit_obj=door)
        assert "The cityguard arrives." in sim.seen(pat)
        there.msg_contents("the beastly fido falls dead!")
        assert sim.seen(pat) == ["The beastly fido falls dead!"]
    finally:
        sim.close()


async def test_a_line_to_one_player_is_left_as_written():
    # send_to_char: a builder's deliberately lowercase pemit stays so.
    sim = _capitalizing()
    try:
        room = sim.room("Loft")
        pat = sim.player("Pat", location=room)
        pat.msg("the wind whispers your name.")
        assert sim.seen(pat) == ["the wind whispers your name."]
        sack = sim.obj("sack", location=room, tags=["thing"])
        sack.db.cmd_sniff = "$sniff sack: pemit(enactor, 'it smells of bread.')"
        await sim.do(pat, "sniff sack")
        assert "it smells of bread." in sim.seen(pat)
    finally:
        sim.close()


def test_a_line_formatter_is_a_seam_any_feature_declares(world):
    # The kernel applies whatever formatters the loaded features declare,
    # in feature order; one that raises is logged and skipped.
    from realm.core.objects import GameObject
    from realm.features import Feature, FeatureSet
    shout, broken = Feature("shout"), Feature("broken")
    shout.line_formatter(lambda text: text.upper())
    broken.line_formatter(lambda text: 1 / 0)
    FeatureSet([shout, broken]).install_runtime(world)
    room = GameObject(name="Hall", tags=["room"])
    heard: list[str] = []
    listener = GameObject(name="Pat", tags=["player"], location=room)
    listener.set_msg_handler(heard.append)
    room.msg_contents("the bell rings.")
    assert heard == ["THE BELL RINGS."]
    assert format_line("a line") == "A LINE"
