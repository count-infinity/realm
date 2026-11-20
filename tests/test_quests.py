"""
MUD_PLAN step 15: quests as data (``quest_def``), tracked by the engine,
after tbaMUD's autoquests (``src/quest.c``) and CoffeeMud's QuestMaker
templates (``resources/quests/templates``).
"""

from __future__ import annotations

import logging

import pytest

from realm.core.behaviors import BehaviorRegistry
from realm.core.defs import all_defs
from realm.core.propagation import Action, propagate
from realm.permissions.locks import check_lock
from realm.std import CLASSIC
from realm.std.quests import quests as quest_clock
from realm.std.quests.quests import expire_all, find_quest, rebuild, state
from realm.testing import Simulator

FIDOS = [{"text": "Kill five fidos.",
          "objectives": [{"kind": "kill", "name": "fido", "count": 5}]}]


class Clock:
    """The injected wall clock quests read (``realm.std.quests.quests.now``)."""

    def __init__(self, monkeypatch, start: float = 1_000_000.0):
        self.t = start
        monkeypatch.setattr(quest_clock, "now", lambda: self.t)

    def advance(self, seconds: float) -> None:
        self.t += seconds


@pytest.fixture
def sim():
    s = Simulator()
    try:
        yield s
    finally:
        _close(s)


@pytest.fixture
def clock(monkeypatch):
    return Clock(monkeypatch)


def _close(s: Simulator) -> None:
    from realm.std.combat.combatant import clear_combatant_cache
    combat = s.world.services.get("combat")
    if combat is not None:
        combat.stop_all()
    clear_combatant_cache()
    s.close()


def _quest(sim, name, **attrs):
    return sim.obj(name, tags=["quest_def"], **attrs)


def _npc(sim, name, room, **attrs):
    return sim.obj(name, location=room, tags=["npc"], hp=10, max_hp=10, **attrs)


async def _say(sim, who, line) -> str:
    await sim.do(who, line)
    return "\n".join(sim.seen(who))


async def _eval(sim, who, code):
    """Run softcode as an administrator, with ``who`` the enactor (the
    builder functions need the HARM entitlement)."""
    wizard = sim.store.find_cached(name="Wizard")
    if not wizard:
        wizard = [sim.player("Wizard")]
        wizard[0].add_tag("admin")
    result, error = await sim.eval(wizard[0], f"result = {code}", enactor=who)
    assert error is None, error
    return result


async def _kill(sim, victim, killer):
    await sim.world.services["combat"].handle_death(victim, killer)


def _baker_quest(sim, **extra):
    """A baker who offers 'Fido trouble': five fidos, for 40 credits."""
    bakery = sim.room("Bakery")
    baker = _npc(sim, "baker", bakery)
    attrs = {"description": "The baker wants the fidos gone.", "giver": "baker",
             "stages": FIDOS, "rewards": {"credits": 40}}
    attrs.update(extra)
    _quest(sim, "Fido trouble", **attrs)
    alice = sim.player("Alice", location=bakery)
    return bakery, baker, alice


# --- 15.1 the definition -----------------------------------------------------------


async def test_a_malformed_definition_is_refused_at_load_by_name(sim, caplog):
    _quest(sim, "Broken bell", stages=[{"text": "x", "objectives": [{"kind": "dance"}]}])
    _quest(sim, "Empty stage", stages=[{"text": "x", "objectives": []}])
    _quest(sim, "Bad loot", stages=FIDOS, rewards={"items": ["no such thing"]})
    _quest(sim, "Fine", stages=FIDOS)
    with caplog.at_level(logging.WARNING):
        rebuild(sim.world)
    text = caplog.text
    assert "'Broken bell'" in text and "unknown kind 'dance'" in text
    assert "'Empty stage'" in text and "stage 1 has no objectives" in text
    assert "'Bad loot'" in text and "names no prototype" in text
    assert set(all_defs("quest")) == {"fine"}


async def test_objectives_parse_with_their_defaults(sim):
    _quest(sim, "Errands", stages=[
        {"text": "Do things.", "objectives": [
            {"kind": "collect", "name": "apple", "count": 3, "consume": True},
            {"kind": "deliver", "name": "letter", "to": "#abc"},
            {"kind": "custom", "key": "Oath"}]}])
    quest = find_quest("errands")
    first, second, third = quest.stages[0].objectives
    assert (first.key, first.count, first.consume) == ("collect", 3, True)
    assert second.to.id == "abc" and second.match.name == "letter"
    assert third.key == "oath" and third.match is None


# --- 15.2 tracking: each objective kind ------------------------------------------------


async def test_kill_counts_toward_the_stage_and_a_giverless_quest_completes(sim):
    room = sim.room("Square")
    alice = sim.player("Alice", location=room)
    _quest(sim, "Cull", stages=[{"text": "Thin the fidos.",
                                 "objectives": [{"kind": "kill", "tag": "race:fido",
                                                 "count": 2}]}],
           rewards={"credits": 5})
    assert "Quest accepted: Cull." in await _say(sim, alice, "quest accept cull")
    for _ in range(2):
        await _kill(sim, sim.obj("fido", location=room, tags=["npc", "race:fido"]), alice)
    out = "\n".join(sim.seen(alice))
    assert "[Cull] kill anything tagged race:fido: 1/2" in out
    assert "Quest complete: Cull!" in out
    assert state(alice, find_quest("cull")) == "done"
    assert alice.db.get("credits") == 5


async def test_a_kill_of_something_else_counts_nothing(sim):
    bakery, baker, alice = _baker_quest(sim)
    await sim.do(alice, "quest accept fido")
    await _kill(sim, _npc(sim, "cat", bakery), alice)
    assert "kill fido" not in "\n".join(sim.seen(alice))
    assert alice.db.quests["fido trouble"]["counts"] == {}


async def test_collect_counts_what_is_held_and_consume_takes_it_at_the_hand_in(sim):
    bakery, baker, alice = _baker_quest(sim, stages=[
        {"text": "Bring three apples.",
         "objectives": [{"kind": "collect", "name": "apple", "count": 3,
                         "consume": True}]}])
    sim.obj("apple", location=alice)                 # one held before accepting
    await sim.do(alice, "quest accept fido")
    for _ in range(2):
        sim.obj("apple", location=bakery)
    await sim.do(alice, "get apple")
    assert "[Fido trouble] collect apple: 2/3" in "\n".join(sim.seen(alice))
    await sim.do(alice, "quests")
    assert "collect apple: 2/3" in "\n".join(sim.seen(alice))
    await sim.do(alice, "get apple")
    assert "Return to baker" in "\n".join(sim.seen(alice))
    assert state(alice, find_quest("fido")) == "ready"
    await sim.do(alice, "drop apple")
    assert "still asks for: collect apple" in await _say(sim, alice, "quest complete")
    await sim.do(alice, "get apple")
    assert "Quest complete: Fido trouble!" in await _say(sim, alice, "quest complete")
    assert not [o for o in alice.contents if o.name == "apple"]


async def test_consumed_gear_is_taken_off_first(sim):
    # A worn thing a collect objective consumes comes off as ROM's
    # extract_obj takes it off: what it granted goes with it (2026-11-17).
    bakery, baker, alice = _baker_quest(sim, stages=[
        {"text": "Bring the goggles.",
         "objectives": [{"kind": "collect", "name": "goggles", "count": 1,
                         "consume": True}]}])
    sim.obj("goggles", location=alice, tags=["thing", "wearable"], slot="eyes",
            grants_tags=["nightvision"])
    await sim.do(alice, "wear goggles")
    assert alice.has_tag("nightvision")
    await sim.do(alice, "quest accept fido")
    assert "Quest complete: Fido trouble!" in await _say(sim, alice, "quest complete")
    assert not [o for o in alice.contents if o.name == "goggles"]
    assert not alice.has_tag("nightvision")


async def test_deliver_counts_an_item_given_to_the_named_npc(sim):
    bakery, baker, alice = _baker_quest(sim, stages=[
        {"text": "Take the parcel to the miller.",
         "objectives": [{"kind": "deliver", "name": "parcel", "to": "miller"}]}],
        giver=None)
    miller = _npc(sim, "miller", bakery)
    sim.obj("parcel", location=alice)
    sim.obj("parcel", location=alice)
    await sim.do(alice, "quest accept fido")
    await sim.do(alice, "give parcel to baker")
    assert state(alice, find_quest("fido")) == 1
    await sim.do(alice, "give parcel to miller")
    assert state(alice, find_quest("fido")) == "done"
    assert any(o.name == "parcel" for o in miller.contents)


async def test_visit_talk_and_use_objectives_across_stages(sim):
    road = sim.room("Road")
    shrine = sim.room("Shrine")
    shrine.add_tag("holy")
    sim.obj("north", location=road, tags=["exit"], destination=shrine.id)
    sim.obj("south", location=shrine, tags=["exit"], destination=road.id)
    hermit = _npc(sim, "hermit", shrine)
    bell = sim.obj("bell", location=shrine)
    alice = sim.player("Alice", location=road)
    _quest(sim, "Pilgrim", stages=[
        {"text": "Walk to the shrine.", "objectives": [{"kind": "visit", "tag": "holy"}]},
        {"text": "Speak with the hermit.",
         "objectives": [{"kind": "talk", "name": "hermit"}]},
        {"text": "Ring the bell.", "objectives": [{"kind": "use", "id": bell.id}]}],
           on_stage="pemit(enactor, 'Onward to stage ' + str(adata('stage')) + '.')")
    hermit.db.on_talk = "pemit(enactor, 'The hermit nods slowly.')"
    await sim.do(alice, "quest accept pilgrim")
    await sim.do(alice, "north")
    out = "\n".join(sim.seen(alice))
    assert "[Pilgrim] Stage 2: Speak with the hermit." in out and "Onward to stage 2." in out
    out = await _say(sim, alice, "talk hermit")
    assert "You talk with the hermit." in out and "The hermit nods slowly." in out
    assert "[Pilgrim] Stage 3: Ring the bell." in out
    out = await _say(sim, alice, "use bell")
    assert "Quest complete: Pilgrim!" in out


async def test_custom_objectives_advance_from_softcode(sim):
    room = sim.room("Hall")
    alice = sim.player("Alice", location=room)
    _quest(sim, "Oath", stages=[{"text": "Swear twice.",
                                 "objectives": [{"kind": "custom", "key": "sworn",
                                                 "count": 2, "text": "oaths sworn"}]}])
    altar = sim.obj("altar", location=room)
    altar.db.on_use = ("if target is me:\n"
                       "    quest_advance(enactor, 'Oath', 'sworn')")
    await sim.do(alice, "quest accept oath")
    assert await _eval(sim, alice, "quest_count(enactor, 'Oath', 'sworn')") == 0
    await sim.do(alice, "use altar")
    assert "[Oath] oaths sworn: 1/2" in "\n".join(sim.seen(alice))
    assert await _eval(sim, alice, "quest_count(enactor, 'Oath', 'sworn')") == 1
    await sim.do(alice, "use altar")
    assert await _eval(sim, alice, "quest_state(enactor, 'Oath')") == "done"


async def test_party_and_companion_kills_count(sim):
    from realm.std.companions.companions import set_master
    from realm.std.social.party import set_following
    room = sim.room("Square")
    alice = sim.player("Alice", location=room)
    bob = sim.player("Bob", location=room)
    cass = sim.player("Cass", location=room)          # not in the party
    set_following(bob, alice)
    _quest(sim, "Cull", stages=[{"text": "x", "objectives": [
        {"kind": "kill", "name": "fido", "count": 3}]}])
    for who in (alice, bob, cass):
        await sim.do(who, "quest accept cull")
    kitten = sim.obj("kitten", location=room, tags=["npc"], hp=5, max_hp=5)
    await set_master(kitten, alice)
    await _kill(sim, _npc(sim, "fido", room), alice)
    await _kill(sim, _npc(sim, "fido", room), bob)
    await _kill(sim, _npc(sim, "fido", room), kitten)
    assert alice.db.get("quests") is None and bob.db.get("quests") is None
    assert state(alice, find_quest("cull")) == "done" == state(bob, find_quest("cull"))
    assert cass.db.quests["cull"]["counts"] == {}


async def test_an_action_nobody_waits_on_returns_at_once(sim, monkeypatch):
    room = sim.room("Square")
    alice = sim.player("Alice", location=room)
    _quest(sim, "Pilgrim", stages=[{"text": "x", "objectives": [
        {"kind": "visit", "tag": "holy"}]}])

    looked = []

    async def count(player, kind, test):
        looked.append(kind)
    monkeypatch.setattr(quest_clock, "_count", count)
    await sim.do(alice, "quest accept pilgrim")
    await _kill(sim, _npc(sim, "fido", room), alice)      # nobody has a kill objective
    sim.obj("apple", location=room)
    await sim.do(alice, "get apple")                        # nor collect
    assert looked == []                                     # the index answered
    sim.room("Shrine").add_tag("holy")
    await propagate(Action(actor=alice, target=room, action_type="event:on_enter"))
    assert looked == ["visit"]                              # a visit is awaited


# --- 15.3 the giver, the lock and the hand-in ------------------------------------------


async def test_the_giver_offers_marks_and_takes_back(sim):
    bakery, baker, alice = _baker_quest(sim)
    assert "baker (!)" in await _say(sim, alice, "look")
    out = await _say(sim, alice, "quest list")
    assert "The baker offers:" in out and "Fido trouble - The baker wants" in out
    await sim.do(alice, "quest accept fido")
    assert "baker (!)" not in await _say(sim, alice, "look")
    for _ in range(5):
        await _kill(sim, _npc(sim, "fido", bakery), alice)
    out = "\n".join(sim.seen(alice))
    assert "Return to baker (quest complete Fido trouble)." in out
    assert "baker (?)" in await _say(sim, alice, "look")
    out = await _say(sim, alice, "quests")
    assert "Fido trouble (ready: return to baker)" in out
    out = await _say(sim, alice, "talk baker")
    assert "The baker is waiting for you to hand in Fido trouble" in out
    out = await _say(sim, alice, "quest complete fido")
    assert "Quest complete: Fido trouble!" in out and "You receive 40 credits." in out
    assert "(" not in (await _say(sim, alice, "look")).split("baker")[1].split("\n")[0]
    assert "You have already done Fido trouble." in await _say(sim, alice,
                                                                "quest accept fido")
    assert "Fido trouble" in await _say(sim, alice, "quests done")


async def test_hand_in_only_at_the_giver(sim):
    bakery, baker, alice = _baker_quest(sim)
    await sim.do(alice, "quest accept fido")
    for _ in range(5):
        await _kill(sim, _npc(sim, "fido", bakery), alice)
    street = sim.room("Street")
    clerk = _npc(sim, "clerk", street)
    clerk.add_behavior(BehaviorRegistry.create("quest_giver", quests=["Fido trouble"]))
    alice.location = street
    sim.seen(alice)
    assert "Hand Fido trouble in to baker." in await _say(sim, alice,
                                                         "quest complete fido")
    assert "Nobody here takes back" in await _say(sim, alice, "quest complete")
    assert state(alice, find_quest("fido")) == "ready"


async def test_the_accept_lock_and_a_quest_offered_elsewhere(sim):
    bakery, baker, alice = _baker_quest(sim, accept_lock="get_attr(caller, 'level', 1) >= 3")
    assert "baker (!)" not in await _say(sim, alice, "look")
    assert "Nobody here has a quest for you." in await _say(sim, alice, "quest list")
    assert "Fido trouble is not for you." in await _say(sim, alice, "quest accept fido")
    alice.db.level = 3
    assert "Quest accepted" in await _say(sim, alice, "quest accept fido")
    bob = sim.player("Bob", location=sim.room("Street"), level=5)
    assert "Nobody here offers that quest." in await _say(sim, bob, "quest accept fido")


async def test_a_quest_giver_behavior_offers_quests_handed_in_elsewhere(sim):
    room = sim.room("Post office")
    clerk = _npc(sim, "clerk", room)
    clerk.add_behavior(BehaviorRegistry.create("quest_giver", quests=["Letters"]))
    _quest(sim, "Letters", giver="postmaster", stages=[{"text": "x", "objectives": [
        {"kind": "custom", "key": "k"}]}])
    alice = sim.player("Alice", location=room)
    assert "clerk (!)" in await _say(sim, alice, "look")
    await sim.do(alice, "quest accept letters")
    assert state(alice, find_quest("letters")) == 1


async def test_abandon_and_the_journal(sim):
    bakery, baker, alice = _baker_quest(sim)
    assert "Your journal is empty." in await _say(sim, alice, "journal")
    await sim.do(alice, "quest accept fido")
    await _kill(sim, _npc(sim, "fido", bakery), alice)
    sim.seen(alice)
    out = await _say(sim, alice, "journal")
    assert "Fido trouble (stage 1 of 1)" in out and "kill fido: 1/5" in out
    out = await _say(sim, alice, "quest fido")
    assert "The baker wants the fidos gone." in out and "Rewards: 40 credits" in out
    assert "You abandon Fido trouble." in await _say(sim, alice, "quest abandon fido")
    assert state(alice, find_quest("fido")) is None
    assert "Quest accepted" in await _say(sim, alice, "quest accept fido")


# --- rewards ----------------------------------------------------------------------------


async def test_rewards_award_items_achievement_and_tags(sim):
    room = sim.room("Hall")
    alice = sim.player("Alice", location=room)
    sim.obj("bread", tags=["thing", "prototype", "food"])
    sim.obj("Dogcatcher", tags=["achievement_def"], description="Rid the town of fidos.")
    _quest(sim, "Cull", stages=[{"text": "x", "objectives": [{"kind": "custom",
                                                              "key": "k"}]}],
           rewards={"award": 7, "items": ["bread"], "achievement": "Dogcatcher",
                    "tags": ["fido_slayer"]})
    await sim.do(alice, "quest accept cull")
    await _eval(sim, alice, "quest_advance(enactor, 'Cull', 'k')")
    out = "\n".join(sim.seen(alice))
    assert "You gain 7 character points." in out
    assert "You receive bread." in out and "Achievement earned: Dogcatcher!" in out
    bread = [o for o in alice.contents if o.name == "bread"]
    assert bread and not bread[0].has_tag("prototype")
    assert alice.has_tag("fido_slayer")


async def test_award_passes_the_rules_filters(sim):
    room = sim.room("Hall")
    alice = sim.player("Alice", location=room)
    sim.world.services["rules"].award_filters.append(lambda player, amount: amount // 2)
    _quest(sim, "Cull", stages=[{"text": "x", "objectives": [{"kind": "custom",
                                                              "key": "k"}]}],
           rewards={"award": 10})
    await sim.do(alice, "quest accept cull")
    await _eval(sim, alice, "quest_advance(enactor, 'Cull', 'k')")
    assert alice.db.get("character_points") == 5


async def test_a_reward_whose_feature_is_absent_is_skipped_with_a_warning(caplog):
    s = Simulator(features=[f for f in CLASSIC if f not in ("economy", "crime")])
    try:
        room = s.room("Hall")
        alice = s.player("Alice", location=room)
        _quest(s, "Cull", stages=[{"text": "x", "objectives": [{"kind": "custom",
                                                                "key": "k"}]}],
               rewards={"credits": 10, "award": 3})
        await s.do(alice, "quest accept cull")
        with caplog.at_level(logging.WARNING):
            await _eval(s, alice, "quest_advance(enactor, 'Cull', 'k')")
        assert "quest 'Cull': its credits reward was not paid" in caplog.text
        assert alice.db.get("credits") is None
        assert alice.db.get("character_points") == 3          # the rest is paid
    finally:
        _close(s)


# --- repeat, time limit, account scope -------------------------------------------------


async def test_a_repeatable_quest_waits_out_its_cooldown(sim, clock):
    bakery, baker, alice = _baker_quest(sim, repeatable=3600, stages=[
        {"text": "x", "objectives": [{"kind": "talk", "name": "baker"}]}])
    await sim.do(alice, "quest accept fido")
    await sim.do(alice, "talk baker")
    await sim.do(alice, "quest complete")
    sim.seen(alice)
    clock.advance(1800)
    assert "You may take Fido trouble again in 30 minutes." in await _say(
        sim, alice, "quest accept fido")
    clock.advance(1801)
    assert "Quest accepted" in await _say(sim, alice, "quest accept fido")


async def test_the_time_limit_fails_the_quest(sim, clock):
    bakery, baker, alice = _baker_quest(sim, time_limit=600,
                                        on_fail="pemit(enactor, 'Why: ' + adata('reason'))")
    out = await _say(sim, alice, "quest accept fido")
    assert "You have 10 minutes to finish it." in out
    assert "10 minutes left" in await _say(sim, alice, "quests")
    clock.advance(300)
    assert await expire_all() == 0
    clock.advance(301)
    assert await expire_all() == 1
    out = "\n".join(sim.seen(alice))
    assert "You have run out of time: Fido trouble has failed." in out and "Why: expired" in out
    assert state(alice, find_quest("fido")) is None


async def test_an_offline_characters_quest_fails_when_they_return(sim, clock):
    bakery, baker, alice = _baker_quest(sim, time_limit=60)
    await sim.do(alice, "quest accept fido")
    await propagate(Action(actor=alice, target=None, action_type="event:disconnect"))
    clock.advance(120)
    assert state(alice, find_quest("fido")) == 1       # nobody fails it while away
    await propagate(Action(actor=alice, target=None, action_type="event:connect"))
    assert state(alice, find_quest("fido")) is None


async def test_account_scope_is_done_once_for_every_character(sim):
    bakery, baker, alice = _baker_quest(sim, scope="account", stages=[
        {"text": "x", "objectives": [{"kind": "talk", "name": "baker"}]}])
    bob = sim.player("Bob", location=bakery)
    account = sim.account("anne", alice, bob)
    await sim.do(alice, "quest accept fido")
    await sim.do(alice, "talk baker")
    await sim.do(alice, "quest complete")
    assert "fido trouble" in account.db.quests_done
    assert alice.db.get("quests_done") is None
    assert "You have already done Fido trouble." in await _say(sim, bob, "quest accept fido")
    assert state(bob, find_quest("fido")) == "done"


async def test_character_scope_lets_each_character_do_it(sim):
    bakery, baker, alice = _baker_quest(sim, stages=[
        {"text": "x", "objectives": [{"kind": "talk", "name": "baker"}]}])
    bob = sim.player("Bob", location=bakery)
    sim.account("anne", alice, bob)
    await sim.do(alice, "quest accept fido")
    await sim.do(alice, "talk baker")
    await sim.do(alice, "quest complete")
    assert "Quest accepted" in await _say(sim, bob, "quest accept fido")


# --- softcode -----------------------------------------------------------------------------


async def test_quest_state_in_a_lock_and_the_builder_functions(sim):
    bakery, baker, alice = _baker_quest(sim)
    door = sim.obj("door", location=bakery)
    door.locks["basic"] = "quest_state(caller, 'Fido trouble') == 'done'"
    assert not check_lock(door, "basic", alice)
    assert await _eval(sim, alice, "quest_offer(enactor, 'Fido trouble')") is True
    assert state(alice, find_quest("fido")) == 1
    assert await _eval(sim, alice, "quest_offer(enactor, 'Fido trouble')") is False
    assert await _eval(sim, alice, "quest_advance(enactor, 'Fido trouble', 'kill', 4)") is True
    assert await _eval(sim, alice, "quest_count(enactor, 'Fido trouble', 'kill')") == 4
    assert await _eval(sim, alice, "quest_advance(enactor, 'Fido trouble', 'nope')") is False
    assert await _eval(sim, alice, "quest_complete(enactor, 'Fido trouble')") is True
    assert check_lock(door, "basic", alice)
    assert alice.db.get("credits") == 40


async def test_quest_fail_from_softcode(sim):
    bakery, baker, alice = _baker_quest(sim)
    await sim.do(alice, "quest accept fido")
    sim.seen(alice)
    assert await _eval(sim, alice, "quest_fail(enactor, 'Fido trouble')") is True
    assert "You have failed Fido trouble." in "\n".join(sim.seen(alice))


async def test_the_quest_events_fire(sim):
    bakery, baker, alice = _baker_quest(sim, stages=[
        {"text": "x", "objectives": [{"kind": "talk", "name": "baker"}]}])
    baker.db.on_questaccept = "say('Good luck.')"
    baker.db.on_questcomplete = "say('Thank you!')"
    out = await _say(sim, alice, "quest accept fido")
    assert "Good luck." in out
    await sim.do(alice, "talk baker")
    assert "Thank you!" in await _say(sim, alice, "quest complete")


# --- talk ---------------------------------------------------------------------------------


async def test_bare_talk_goes_to_the_worlds_softcode(sim):
    room = sim.room("Flagon")
    moss = _npc(sim, "Old Moss", room)
    moss.db.cmd_talk = "$talk:\npemit(enactor, 'Sit, if you like.')"
    alice = sim.player("Alice", location=room)
    assert "Sit, if you like." in await _say(sim, alice, "talk")
    assert "You talk with Old Moss." in await _say(sim, alice, "talk moss")


async def test_ta_still_takes(sim):
    assert sim.dispatcher.resolve("ta apple").name == "get"
    assert sim.dispatcher.resolve("tal moss").name == "talk"


# --- the Midgaard template ------------------------------------------------------------------


async def test_midgaards_baker_offers_fido_trouble():
    import sys
    from pathlib import Path

    from realm.features import install_default
    midgaard = Path(__file__).resolve().parents[1] / "realm" / "examples" / "midgaard"
    before = list(sys.path)
    s = Simulator.from_game(midgaard)
    await s.start()
    try:
        bakery = s.store.get_cached("rom_3009")
        assert any(o.name == "the baker" for o in bakery.contents)
        pat = s.player("Pat", location=bakery, level=1, hp=20, max_hp=20)
        assert "baker (!)" in await _say(s, pat, "look")
        assert "Fido trouble" in await _say(s, pat, "quest list")
        assert "Quest accepted: Fido trouble." in await _say(s, pat, "quest accept fido")
        fidos = [o for o in s.store.all_cached() if o.db.get("prototype_vnum") == 3062]
        assert fidos
        for i in range(5):
            await _kill(s, fidos[i % len(fidos)] if i < len(fidos) else
                        s.obj("fido dog", location=bakery, tags=["npc"], prototype_vnum=3062),
                        pat)
        assert "fidos killed: 5/5" in "\n".join(s.seen(pat))
        xp = pat.db.get("xp") or 0
        out = await _say(s, pat, "quest complete")
        assert "Quest complete: Fido trouble!" in out and "You receive a bread." in out
        assert (pat.db.get("xp") or 0) >= xp + 250 or pat.db.get("level") > 1
    finally:
        _close(s)
        sys.modules.pop("rules", None)
        sys.modules.pop("game", None)
        sys.path[:] = before
        install_default()
