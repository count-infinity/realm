"""
Showcase category 18 — Quests & Storytelling (items 198-208).

Every test drives a real in-process world through the dispatcher with the
exact command lines from each tutorial's "Build it" transcript
(docs/showcase/198_quest_framework.md .. 208_collectible_lore.md), then
asserts the outcomes the tutorials promise. The transcripts live in the
``*_BUILD`` constants below and are checked, line for line, against the
published docs by ``test_tutorial_docs_contain_the_exact_tested_command_lines``
at the bottom — so a tutorial can never drift from what the tests prove.

Harness notes (mirrors the other showcase suites):
- The Simulator runs the same components a live server does, driven by
  ``sim.do(player, "raw input")``; ``sim.seen(player)`` drains that
  player's output.
- The builder is tagged ``admin`` because these masters write other
  players' sheets (quest stages, badges, codex flags) — owner authority
  over a player requires admin, exactly as on a live server.
- ``prompt()`` needs a session lookup the GameServer normally wires; the
  fixture supplies it (``engine.session_manager``).
- ``wait()`` runs on the Simulator's virtual clock — pump it with
  ``sim.engine.tick_waits()``; ``script_ticker`` ``on_tick`` routines are
  fired directly with ``@tr <obj>/on_tick``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from realm.testing import Simulator

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"


@pytest.fixture
def world():
    sim = Simulator()
    sim.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: list(sim._sessions.values()))
    hub = sim.room("The Nexus")
    bela = sim.player("Bela", location=hub)
    bela.add_tag("admin")
    try:
        yield sim, bela, hub
    finally:
        sim.close()


def one(sim, name):
    return sim.store.find_cached(name=name)[0]


def joined(msgs):
    return "\n".join(msgs)


async def build(sim, who, lines):
    for line in lines:
        await sim.do(who, line)


async def answer(sim, player, line):
    """Feed a line into a pending prompt() the way a live session would."""
    handler = sim.session(player).input_handler
    assert handler is not None, "prompt() should have captured the next line"
    await handler(sim.session(player), line)


# =========================================================================
# 198. Quest framework
# =========================================================================

WARDEN_BUILD = [
    "@create Quest Warden",
    "drop Quest Warden",
    '@set Quest Warden/quests = {"cinders": {"name": "The Cinder Road", "stages": ["Search the burned waystation for the toll ledger.", "Return the toll ledger to the Quest Warden.", "Complete."], "reward": 50}}',
    "@set Quest Warden/advance = q = get('#' + str(arg0)); slug = str(arg1); wd = get('Quest Warden'); defn = get_attr(wd, 'quests', {}).get(slug); cur = get_attr(q, 'q_' + slug, 0); nxt = cur + 1; last = len(defn['stages']) if defn else 0; [(set_attr(q, 'q_' + slug, nxt), pemit(q, 'Quest updated -- ' + defn['name'] + ': ' + defn['stages'][nxt - 1])) for g in [bool(defn) and 0 < cur < last - 1] if g]; [(set_attr(q, 'q_' + slug, last), adjust_credits(q, defn['reward']), pemit(q, 'Quest complete: ' + defn['name'] + '. Reward: ' + str(defn['reward']) + ' credits.')) for g in [bool(defn) and cur == last - 1] if g]; result = 1",
    "@set Quest Warden/cmd_start = $accept quest *:slug = trim(arg0); defn = V('quests', {}).get(slug); (pemit(enactor, 'No such quest.') if not defn else (pemit(enactor, 'You are already on that quest.') if get_attr(enactor, 'q_' + slug, 0) else (set_attr(enactor, 'q_' + slug, 1), pemit(enactor, 'Quest accepted -- ' + defn['name'] + ': ' + defn['stages'][0]))))",
    "@set Quest Warden/cmd_quests = $quests:defs = V('quests', {}); rows = [(d['name'] + ' [' + str(min(get_attr(enactor, 'q_' + s, 0), len(d['stages']))) + '/' + str(len(d['stages'])) + '] -- ' + d['stages'][min(get_attr(enactor, 'q_' + s, 0), len(d['stages'])) - 1]) for s, d in defs.items() if get_attr(enactor, 'q_' + s, 0)]; pemit(enactor, 'Your journal:' if rows else 'Your journal is empty.'); [pemit(enactor, '  ' + r) for r in rows]",
    "@set Quest Warden/cmd_report = $report:hits = [s for s, d in V('quests', {}).items() if get_attr(enactor, 'q_' + s, 0) == len(d['stages']) - 1]; [eval_attr(me, 'advance', enactor.id, s) for s in hits]; pemit(enactor, 'You have nothing to report.') if not hits else None",
    "@create toll ledger",
    "drop toll ledger",
    "@set toll ledger/on_use = w = get('Quest Warden'); [eval_attr(w, 'advance', enactor.id, 'cinders') for g in [w is not None and get_attr(enactor, 'q_cinders', 0) == 1] if g]",
]


@pytest.mark.asyncio
class TestQuestFramework:

    async def test_journal_stages_and_completion_hook(self, world):
        sim, bela, hub = world
        await build(sim, bela, WARDEN_BUILD)
        raven = sim.player("Raven", location=hub)

        await sim.do(raven, "quests")
        assert "Your journal is empty." in sim.seen(raven)

        await sim.do(raven, "accept quest cinders")
        assert any("Quest accepted -- The Cinder Road" in m for m in sim.seen(raven))
        assert raven.db.get("q_cinders") == 1

        await sim.do(raven, "quests")
        assert "The Cinder Road [1/3]" in joined(sim.seen(raven))

        # Completion hook #1: the waystation relic advances stage 1 -> 2.
        await sim.do(raven, "use toll ledger")
        assert any("Quest updated" in m for m in sim.seen(raven))
        assert raven.db.get("q_cinders") == 2

        # Completion hook #2: reporting in at the final stage pays out.
        await sim.do(raven, "report")
        out = joined(sim.seen(raven))
        assert "Quest complete: The Cinder Road" in out
        assert raven.db.get("q_cinders") == 3
        assert (raven.db.get("credits") or 0) == 50

    async def test_unknown_and_duplicate_accepts_are_refused(self, world):
        sim, bela, hub = world
        await build(sim, bela, WARDEN_BUILD)
        raven = sim.player("Raven", location=hub)

        await sim.do(raven, "accept quest dragons")
        assert "No such quest." in sim.seen(raven)

        await sim.do(raven, "accept quest cinders")
        sim.seen(raven)
        await sim.do(raven, "accept quest cinders")
        assert "You are already on that quest." in sim.seen(raven)

    async def test_report_with_nothing_due(self, world):
        sim, bela, hub = world
        await build(sim, bela, WARDEN_BUILD)
        raven = sim.player("Raven", location=hub)
        await sim.do(raven, "report")
        assert "You have nothing to report." in sim.seen(raven)


# =========================================================================
# 199. Delivery quest
# =========================================================================

DELIVERY_BUILD = [
    "@create Postmaster Vane",
    "@tag Postmaster Vane = npc",
    "drop Postmaster Vane",
    "@set Postmaster Vane/cmd_job = $courier job:has = get_attr(enactor, 'deliver_by', 0) > now(); pemit(enactor, 'You already carry sealed orders.') if has else [(set_attr(enactor, 'deliver_by', now() + 300), teleport_obj(o, enactor), pemit(enactor, 'Vane presses sealed orders into your hands. Deliver them to the Harbor Agent before they go stale.')) for o in [create_obj('sealed orders', ['thing', 'orders'], location=here)] if o]",
    "@dig The Harbor Office = harbor, back",
    "harbor",
    "@create Harbor Agent",
    "@tag Harbor Agent = npc",
    "drop Harbor Agent",
    "@set Harbor Agent/on_receive = it = ([o for o in contents(me) if has_tag(o, 'orders')] or [None])[0]; ontime = get_attr(enactor, 'deliver_by', 0) > now(); (None if it is None else ((set_attr(enactor, 'deliver_by', 0), destroy_obj(it), adjust_credits(enactor, 60), say('The orders, at last. Sixty credits for your trouble.')) if ontime else (set_attr(enactor, 'deliver_by', 0), teleport_obj(it, enactor), say('These orders are stale. I cannot accept them.'))))",
    "back",
]


@pytest.mark.asyncio
class TestDeliveryQuest:

    async def test_deliver_on_time_pays_out(self, world):
        sim, bela, hub = world
        await build(sim, bela, DELIVERY_BUILD)
        raven = sim.player("Raven", location=hub)

        await sim.do(raven, "courier job")
        orders = [o for o in raven.contents if o.name == "sealed orders"]
        assert orders, "Vane should have handed over sealed orders"
        assert raven.db.get("deliver_by") > 0

        # Already carrying: refused.
        await sim.do(raven, "courier job")
        assert "You already carry sealed orders." in sim.seen(raven)

        await sim.do(bela, "@teleport Raven = The Harbor Office")
        sim.seen(raven)
        await sim.do(raven, "give sealed orders to Harbor Agent")
        assert any("Sixty credits" in m for m in sim.seen(raven))
        assert (raven.db.get("credits") or 0) == 60
        assert not [o for o in raven.contents if o.name == "sealed orders"]
        assert raven.db.get("deliver_by") == 0

    async def test_stale_orders_are_refused_and_pushed_back(self, world):
        sim, bela, hub = world
        await build(sim, bela, DELIVERY_BUILD)
        raven = sim.player("Raven", location=hub)
        await sim.do(raven, "courier job")
        # Simulate the deadline lapsing (a live world would let the clock run).
        raven.db.set("deliver_by", 1)

        await sim.do(bela, "@teleport Raven = The Harbor Office")
        sim.seen(raven)
        await sim.do(raven, "give sealed orders to Harbor Agent")
        assert any("stale" in m for m in sim.seen(raven))
        assert [o for o in raven.contents if o.name == "sealed orders"], "pushed back"
        assert (raven.db.get("credits") or 0) == 0


# =========================================================================
# 200. Collection counters
# =========================================================================

COLLECTION_BUILD = [
    "@zone here = salvage",
    "@create Salvage Foreman",
    "drop Salvage Foreman",
    "@zone/master Salvage Foreman = salvage",
    "@set Salvage Foreman/goal = 5",
    "@set Salvage Foreman/on_get = set_attr(me, 'pending', (V('pending') or []) + [enactor.id]); wait(0, 'trigger me/tally')",
    "@set Salvage Foreman/tally = q = V('pending') or []; set_attr(me, 'pending', []); [eval_attr(me, 'count', pid) for pid in q]",
    "@set Salvage Foreman/count = p = get('#' + str(arg0)); fresh = [o for o in contents(p) if has_tag(o, 'objective') and not has_tag(o, 'counted')] if p else []; [add_tag(o, 'counted') for o in fresh]; n = get_attr(p, 'salvage_count', 0) + len(fresh); goal = V('goal', 5); [(set_attr(p, 'salvage_count', n), pemit(p, 'Salvage relays recovered: ' + str(min(n, goal)) + '/' + str(goal))) for g in [bool(fresh)] if g]; [(set_attr(p, 'salvage_done', 1), adjust_credits(p, 100), pemit(p, 'Objective complete! The Foreman wires you 100 credits.')) for g in [n >= goal and not get_attr(p, 'salvage_done', 0)] if g]; result = 1",
    "@eval [create_obj('salvage relay', ['thing', 'objective'], location=get('The Nexus')) for i in range(5)]",
    "@create rusty wrench",
    "@tag rusty wrench = thing",
    "drop rusty wrench",
]


@pytest.mark.asyncio
class TestCollectionCounters:

    async def test_five_relays_auto_track_to_completion(self, world):
        sim, bela, hub = world
        await build(sim, bela, COLLECTION_BUILD)
        raven = sim.player("Raven", location=hub)

        # A non-objective pickup does not move the counter.
        await sim.do(raven, "get rusty wrench")
        await sim.engine.tick_waits()
        assert raven.db.get("salvage_count") in (None, 0)

        for i in range(1, 6):
            await sim.do(raven, "get salvage relay")
            await sim.engine.tick_waits()
            assert raven.db.get("salvage_count") == i, f"after relay {i}"

        assert raven.db.get("salvage_done") == 1
        assert (raven.db.get("credits") or 0) == 100

    async def test_counted_relays_are_monotonic(self, world):
        sim, bela, hub = world
        await build(sim, bela, COLLECTION_BUILD)
        raven = sim.player("Raven", location=hub)
        for _ in range(5):
            await sim.do(raven, "get salvage relay")
            await sim.engine.tick_waits()
        assert raven.db.get("salvage_count") == 5

        # Dropping a relay never lowers the tally -- progress is monotonic,
        # tracked by the 'counted' tag stamped on each relay when first seen.
        await sim.do(raven, "drop salvage relay")
        await sim.engine.tick_waits()
        assert raven.db.get("salvage_count") == 5

        # Re-picking that same, already-counted relay does not double-count it.
        await sim.do(raven, "get salvage relay")
        await sim.engine.tick_waits()
        assert raven.db.get("salvage_count") == 5


# =========================================================================
# 201. Branching quest
# =========================================================================

BRANCHING_BUILD = [
    "@create Envoy Sable",
    "@tag Envoy Sable = npc",
    "drop Envoy Sable",
    "@set Envoy Sable/cmd_parley = $parley:(pemit(enactor, 'Your allegiance is already sworn: ' + get_attr(enactor, 'allegiance') + '.') if get_attr(enactor, 'allegiance', 0) else (pemit(enactor, 'Sable studies you. \"The Warlord or the Rebels -- whom do you serve?\"'), prompt(enactor, 'Answer warlord or rebels:', 'on_choose')))",
    "@set Envoy Sable/on_choose = pick = trim(arg0).lower(); (set_attr(enactor, 'allegiance', pick), pemit(enactor, 'So be it. You are sworn to the ' + pick + '.')) if pick in ('warlord', 'rebels') else pemit(enactor, 'Sable frowns. \"Speak plainly: warlord or rebels.\"')",
    "@set Envoy Sable/cmd_ending = $seek ending:a = get_attr(enactor, 'allegiance', 0); pemit(enactor, 'You have sworn nothing yet.') if not a else (pemit(enactor, 'The Warlord crowns you warlord of the marches. [WARLORD ENDING]') if a == 'warlord' else pemit(enactor, 'The Rebels raise you on their shoulders, the city freed. [REBEL ENDING]'))",
]


@pytest.mark.asyncio
class TestBranchingQuest:

    async def test_choice_locks_a_branch_and_gates_the_ending(self, world):
        sim, bela, hub = world
        await build(sim, bela, BRANCHING_BUILD)
        raven = sim.player("Raven", location=hub)

        # No allegiance yet: the ending is closed.
        await sim.do(raven, "seek ending")
        assert "You have sworn nothing yet." in sim.seen(raven)

        await sim.do(raven, "parley")
        assert any("whom do you serve" in m for m in sim.seen(raven))
        await answer(sim, raven, "rebels")
        assert raven.db.get("allegiance") == "rebels"

        # The other branch is now locked out.
        await sim.do(raven, "parley")
        assert "Your allegiance is already sworn: rebels." in sim.seen(raven)
        assert sim.session(raven).input_handler is None  # no new prompt

        await sim.do(raven, "seek ending")
        assert any("[REBEL ENDING]" in m for m in sim.seen(raven))

    async def test_warlord_branch_reaches_the_other_ending(self, world):
        sim, bela, hub = world
        await build(sim, bela, BRANCHING_BUILD)
        raven = sim.player("Raven", location=hub)
        await sim.do(raven, "parley")
        await answer(sim, raven, "warlord")
        await sim.do(raven, "seek ending")
        assert any("[WARLORD ENDING]" in m for m in sim.seen(raven))

    async def test_a_nonsense_answer_swears_nothing(self, world):
        sim, bela, hub = world
        await build(sim, bela, BRANCHING_BUILD)
        raven = sim.player("Raven", location=hub)
        await sim.do(raven, "parley")
        await answer(sim, raven, "maybe later")
        assert any("Speak plainly" in m for m in sim.seen(raven))
        assert not raven.db.get("allegiance")


# =========================================================================
# 202. World event: invasion
# =========================================================================

INVASION_BUILD = [
    "@zone here = citadel",
    "@dig The Keep = keep, gate",
    "keep",
    "@zone here = citadel",
    "gate",
    "@create War Drum",
    "drop War Drum",
    "@zone/master War Drum = citadel",
    "@set War Drum/phase = 0",
    "@set War Drum/on_tick = p = incr('phase'); [remit(r, 'Warhorns! Raiders mass beyond the walls.') for r in zone_rooms('citadel') if p == 1]; [(create_obj('a raider', ['npc', 'raider'], location=r), remit(r, 'Raiders pour through the gate!')) for r in zone_rooms('citadel') if p == 2]; [create_obj('a raider', ['npc', 'raider'], location=r) for r in zone_rooms('citadel') if p == 3]; [destroy_obj(o) for o in search_world(tag='raider') if p == 4]; [remit(r, 'The last raider falls. The citadel holds.') for r in zone_rooms('citadel') if p == 4]; set_attr(me, 'phase', 0) if p >= 4 else None",
    "@set War Drum/on_reset = [destroy_obj(o) for o in search_world(tag='raider')]; set_attr(me, 'phase', 0)",
    "@behavior War Drum = script_ticker, interval:20",
]


@pytest.mark.asyncio
class TestInvasion:

    async def test_phased_waves_spawn_then_clean_up(self, world):
        sim, bela, hub = world
        # The starting room becomes the citadel gate.
        await sim.do(bela, "@name here = The Citadel Gate")
        await build(sim, bela, INVASION_BUILD)
        watcher = sim.player("Watcher", location=hub)

        def raiders():
            return sim.store.find_cached(tag="raider")

        # Phase 1: the warning, no spawns yet.
        await sim.do(bela, "@tr War Drum/on_tick")
        assert any("Warhorns" in m for m in sim.seen(watcher))
        assert len(raiders()) == 0

        # Phase 2: first wave — one raider per zone room (gate + keep).
        await sim.do(bela, "@tr War Drum/on_tick")
        assert len(raiders()) == 2
        assert any("pour through the gate" in m for m in sim.seen(watcher))

        # Phase 3: reinforcements.
        await sim.do(bela, "@tr War Drum/on_tick")
        assert len(raiders()) == 4

        # Phase 4: the event ends and cleans up after itself.
        await sim.do(bela, "@tr War Drum/on_tick")
        assert len(raiders()) == 0
        assert any("citadel holds" in m for m in sim.seen(watcher))
        assert one(sim, "War Drum").db.get("phase") == 0

    async def test_on_reset_scrubs_a_stuck_invasion(self, world):
        sim, bela, hub = world
        await sim.do(bela, "@name here = The Citadel Gate")
        await build(sim, bela, INVASION_BUILD)
        # Spawn a wave, then reset mid-event.
        await sim.do(bela, "@tr War Drum/on_tick")
        await sim.do(bela, "@tr War Drum/on_tick")
        assert len(sim.store.find_cached(tag="raider")) == 2
        await sim.do(bela, "@tr War Drum/on_reset")
        assert len(sim.store.find_cached(tag="raider")) == 0
        assert one(sim, "War Drum").db.get("phase") == 0


# =========================================================================
# 203. Cutscenes
# =========================================================================

CUTSCENE_BUILD = [
    "@create holoprojector",
    "drop holoprojector",
    '@set holoprojector/scenes = ["The lights dim. A star map flickers to life.", "A red world turns slowly, ringed with debris.", "A voice whispers: this is Kepler\'s Rest, your target.", "The map collapses into darkness."]',
    "@set holoprojector/cmd_play = $play briefing:(pemit(enactor, 'The projector is already running. Type skip to cut it short.') if V('pending') else (set_attr(me, 'step', 0), set_attr(me, 'pending', wait(0, 'trigger me/scene_step'))))",
    "@set holoprojector/pace = 6",
    "@set holoprojector/scene_step = lines = V('scenes', []); n = V('step', 0); (del_attr(me, 'pending') if n >= len(lines) else (remit(here, lines[n]), incr('step'), set_attr(me, 'pending', wait(V('pace', 6), 'trigger me/scene_step'))))",
    "@set holoprojector/cmd_skip = $skip:(pemit(enactor, 'Nothing is playing.') if not V('pending') else (cancel_wait(V('pending')), del_attr(me, 'pending'), set_attr(me, 'step', 0), remit(here, 'The projection snaps off. (skipped)')))",
]


@pytest.mark.asyncio
class TestCutscenes:

    async def test_paced_sequence_plays_to_the_whole_room(self, world):
        sim, bela, hub = world
        await build(sim, bela, CUTSCENE_BUILD)
        await sim.do(bela, "@set holoprojector/pace = 0")  # instant for the test clock
        ada = sim.player("Ada", location=hub)
        ben = sim.player("Ben", location=hub)

        await sim.do(ada, "play briefing")
        ada_lines, ben_lines = [], []
        for _ in range(6):  # pump the virtual clock through the chain
            await sim.engine.tick_waits()
            ada_lines += sim.seen(ada)
            ben_lines += sim.seen(ben)
        text = joined(ada_lines)
        assert "A star map flickers to life." in text
        assert "The map collapses into darkness." in text
        # The whole room sees it, not just the initiator.
        assert any("star map" in m for m in ben_lines)
        # The chain ends: nothing left pending.
        assert not one(sim, "holoprojector").db.get("pending")

    async def test_skip_cuts_the_rest_of_the_sequence(self, world):
        sim, bela, hub = world
        await build(sim, bela, CUTSCENE_BUILD)
        ada = sim.player("Ada", location=hub)

        await sim.do(bela, "@set holoprojector/pace = 0")
        await sim.do(ada, "play briefing")
        await sim.engine.tick_waits()          # first line lands
        first = sim.seen(ada)
        assert any("star map" in m for m in first)

        await sim.do(ada, "skip")
        assert any("snaps off" in m for m in sim.seen(ada))
        # Pump again: no further lines arrive.
        await sim.engine.tick_waits()
        assert all("collapses into darkness" not in m for m in sim.seen(ada))

    async def test_skip_when_idle_is_harmless(self, world):
        sim, bela, hub = world
        await build(sim, bela, CUTSCENE_BUILD)
        ada = sim.player("Ada", location=hub)
        await sim.do(ada, "skip")
        assert "Nothing is playing." in sim.seen(ada)


# =========================================================================
# 204. GM possession tools
# =========================================================================

POSSESSION_BUILD = [
    "@create Baron Haldor",
    "@tag Baron Haldor = npc",
    "drop Baron Haldor",
    "@desc Baron Haldor = A stout man in a fur-trimmed robe, eyes flicking to the door.",
    "@create signet ring",
    "@set signet ring/cmd_act = $act *:force('Baron Haldor', arg0)",
    "@lock/use signet ring = caller.has_tag('steward')",
    "drop signet ring",
]


@pytest.mark.asyncio
class TestGMPossession:

    async def test_force_speaks_as_the_npc_and_forwards_perception(self, world):
        sim, bela, hub = world
        await build(sim, bela, POSSESSION_BUILD)
        onlooker = sim.player("Onlooker", location=hub)

        await sim.do(bela, "@force Baron Haldor = say Kneel before your Baron.")
        # The room hears the NPC, not the GM — seamless attribution.
        assert any('Baron Haldor says, "Kneel before your Baron."' in m
                   for m in sim.seen(onlooker))

        # Perception is forwarded back to the GM, prefixed with the body.
        await sim.do(bela, "@force Baron Haldor = look")
        assert any("[Baron Haldor]" in m for m in sim.seen(bela))

    async def test_forced_body_acts_at_its_own_permission_level(self, world):
        sim, bela, hub = world
        await build(sim, bela, POSSESSION_BUILD)
        await sim.do(bela, "@force Baron Haldor = @dig A Secret Vault")
        # An NPC body has player-level hands: building is refused.
        assert not sim.store.find_cached(name="A Secret Vault")

    async def test_softcode_relay_lets_a_trusted_player_drive_the_npc(self, world):
        sim, bela, hub = world
        await build(sim, bela, POSSESSION_BUILD)
        steward = sim.player("Steward", location=hub)
        onlooker = sim.player("Onlooker", location=hub)

        # Without the steward tag, the use lock keeps them out.
        await sim.do(steward, "act say I hold no office.")
        assert all("I hold no office" not in m for m in sim.seen(onlooker))

        steward.add_tag("steward")
        await sim.do(steward, "act say The court is in session.")
        assert any('Baron Haldor says, "The court is in session."' in m
                   for m in sim.seen(onlooker))


# =========================================================================
# 205. Scene logger
# =========================================================================

SCENE_BUILD = [
    "@create scene recorder",
    "drop scene recorder",
    "@desc scene recorder = A slim obsidian obelisk. JOIN SCENE to consent to recording; LEAVE SCENE to opt out; EXPORT reads the log back.",
    "@set scene recorder/cmd_join = $join scene:(pemit(enactor, 'You are already part of this scene.') if enactor.id in (V('cast') or []) else (set_attr(me, 'cast', (V('cast') or []) + [enactor.id]), remit(here, name(enactor) + ' steps into the scene. (now recording their poses and speech)')))",
    "@set scene recorder/cmd_leave = $leave scene:(set_attr(me, 'cast', [c for c in (V('cast') or []) if c != enactor.id]), pemit(enactor, 'You step out of the scene.'))",
    "@set scene recorder/listen_all = ^*:set_attr(me, 'log', ((V('log') or []) + [[now(), name(enactor), 'says, \"' + escape(arg0) + '\"']])[-100:]) if enactor and enactor.id in (V('cast') or []) else None",
    "@set scene recorder/on_emote = set_attr(me, 'log', ((V('log') or []) + [[now(), name(enactor), '(emotes -- pose text is not exposed to witnesses)']])[-100:]) if enactor and enactor.id in (V('cast') or []) else None",
    "@set scene recorder/cmd_export = $export:rows = V('log') or []; pemit(enactor, 'The scene is blank.') if not rows else [pemit(enactor, '[' + str(r[0] - rows[0][0]) + 's] ' + r[1] + ' ' + r[2]) for r in rows]",
]


@pytest.mark.asyncio
class TestSceneLogger:

    async def test_records_only_consenting_players_in_order(self, world):
        sim, bela, hub = world
        await build(sim, bela, SCENE_BUILD)
        ada = sim.player("Ada", location=hub)
        ben = sim.player("Ben", location=hub)
        cara = sim.player("Cara", location=hub)

        await sim.do(ada, "join scene")
        await sim.do(ben, "join scene")
        # Cara never opts in.

        await sim.do(ada, "say Well met, friends.")
        await sim.do(ben, "pose bows deeply.")
        await sim.do(cara, "say You cannot record me.")
        await sim.do(ada, "say Indeed we are gathered.")

        recorder = one(sim, "scene recorder")
        log = recorder.db.get("log")
        assert len(log) == 3, log
        assert log[0][1] == "Ada" and 'Well met' in log[0][2]
        assert log[1][1] == "Ben" and "emotes" in log[1][2]   # pose order kept
        assert log[2][1] == "Ada" and "Indeed" in log[2][2]
        assert all(row[1] != "Cara" for row in log)            # consent honored

        sim.seen(ada)
        await sim.do(ada, "export")
        out = joined(sim.seen(ada))
        assert "Ada says, \"Well met, friends.\"" in out
        assert "Ben (emotes" in out

    async def test_leaving_the_scene_stops_recording_that_player(self, world):
        sim, bela, hub = world
        await build(sim, bela, SCENE_BUILD)
        ada = sim.player("Ada", location=hub)
        await sim.do(ada, "join scene")
        await sim.do(ada, "leave scene")
        await sim.do(ada, "say off the record now.")
        recorder = one(sim, "scene recorder")
        assert not (recorder.db.get("log") or [])


# =========================================================================
# 206. Rumor mill
# =========================================================================

RUMOR_BUILD = [
    "@create Gossip Gale",
    "@tag Gossip Gale = npc",
    "drop Gossip Gale",
    "@create Old Pip",
    "@tag Old Pip = npc",
    "drop Old Pip",
    "@set Gossip Gale/ttl = 3",
    "@set Old Pip/ttl = 3",
    "@set Gossip Gale/on_tick = r = V('rumor', 0); (del_attr(me, 'rumor') if r and now() - V('rumor_at', 0) > V('ttl', 3) else (say('Word is ' + r) if r else None))",
    "@set Old Pip/on_tick = r = V('rumor', 0); (del_attr(me, 'rumor') if r and now() - V('rumor_at', 0) > V('ttl', 3) else (say('Word is ' + r) if r else None))",
    "@set Gossip Gale/listen_rumor = ^*word is *:(set_attr(me, 'rumor', trim(arg1)), set_attr(me, 'rumor_at', now())) if not V('rumor', 0) else None",
    "@set Old Pip/listen_rumor = ^*word is *:(set_attr(me, 'rumor', trim(arg1)), set_attr(me, 'rumor_at', now())) if not V('rumor', 0) else None",
]


@pytest.mark.asyncio
class TestRumorMill:

    async def test_a_rumor_hops_between_npcs_then_decays(self, world):
        sim, bela, hub = world
        await build(sim, bela, RUMOR_BUILD)
        # Seed Gale with a fresh rumor.
        await sim.do(bela, "@set Gossip Gale/rumor = the docks flood at dawn")
        await sim.do(bela, "@eval set_attr(get('Gossip Gale'), 'rumor_at', now())")

        # Gale gossips; Pip overhears and now carries the rumor too.
        await sim.do(bela, "@tr Gossip Gale/on_tick")
        assert one(sim, "Old Pip").db.get("rumor") == "the docks flood at dawn"

        # Age Pip's copy past its ttl; the next beat, Pip forgets it.
        await sim.do(bela, "@eval set_attr(get('Old Pip'), 'rumor_at', now() - 100)")
        await sim.do(bela, "@tr Old Pip/on_tick")
        assert not one(sim, "Old Pip").db.get("rumor")

    async def test_a_carrier_does_not_overwrite_its_own_rumor(self, world):
        sim, bela, hub = world
        await build(sim, bela, RUMOR_BUILD)
        await sim.do(bela, "@set Old Pip/rumor = the baron is poisoned")
        await sim.do(bela, "@eval set_attr(get('Old Pip'), 'rumor_at', now())")
        await sim.do(bela, "@set Gossip Gale/rumor = the docks flood at dawn")
        await sim.do(bela, "@eval set_attr(get('Gossip Gale'), 'rumor_at', now())")
        await sim.do(bela, "@tr Gossip Gale/on_tick")
        # Pip already has a rumor: the listen guard leaves it untouched.
        assert one(sim, "Old Pip").db.get("rumor") == "the baron is poisoned"


# =========================================================================
# 207. Achievements
# =========================================================================

ACHIEVEMENT_BUILD = [
    "@zone here = world",
    "@dig The Observatory = observatory, concourse",
    "observatory",
    "@zone here = world",
    "concourse",
    "@dig The Sealed Vault = vault, concourse",
    "vault",
    "@zone here = world",
    "@tag here = secret",
    "concourse",
    "@create Chronicle",
    "drop Chronicle",
    "@zone/master Chronicle = world",
    '@set Chronicle/badges = {"explorer": {"name": "Explorer", "secret": 0, "tiers": [1, 2, 3]}, "trespasser": {"name": "Trespasser", "secret": 1}}',
    "@set Chronicle/on_enter = seen = get_attr(enactor, 'seen_rooms') or []; [eval_attr(get('Chronicle'), 'visit', enactor.id) for g in [has_tag(enactor, 'player') and here.id not in seen] if g]; [(set_attr(enactor, 'badge_trespasser', 1), pemit(enactor, 'Hidden achievement unlocked: Trespasser!')) for g in [has_tag(enactor, 'player') and has_tag(here, 'secret') and not get_attr(enactor, 'badge_trespasser', 0)] if g]",
    "@set Chronicle/visit = p = get('#' + str(arg0)); seen = (get_attr(p, 'seen_rooms') or []) + [here.id]; set_attr(p, 'seen_rooms', seen); tiers = get_attr(get('Chronicle'), 'badges', {})['explorer']['tiers']; earned = len([t for t in tiers if len(seen) >= t]); [(set_attr(p, 'badge_explorer', earned), pemit(p, 'Achievement: Explorer (tier ' + str(earned) + ')!')) for g in [earned > get_attr(p, 'badge_explorer', 0)] if g]; result = 1",
    "@set Chronicle/cmd_badges = $badges:defs = V('badges', {}); rows = [(d['name'] + (' (tier ' + str(get_attr(enactor, 'badge_' + s, 0)) + ')' if d.get('tiers') else '')) for s, d in defs.items() if get_attr(enactor, 'badge_' + s, 0)]; pemit(enactor, 'Badges earned:' if rows else 'No badges yet.'); [pemit(enactor, '  ' + r) for r in rows]",
]


@pytest.mark.asyncio
class TestAchievements:

    async def test_progressive_tiers_and_hidden_badge(self, world):
        sim, bela, hub = world
        await sim.do(bela, "@name here = The Grand Concourse")
        await build(sim, bela, ACHIEVEMENT_BUILD)
        nova = sim.player("Nova", location=one(sim, "The Grand Concourse"))

        await sim.do(nova, "observatory")     # 1st distinct room -> tier 1
        assert nova.db.get("badge_explorer") == 1
        await sim.do(nova, "concourse")        # 2nd -> tier 2
        assert nova.db.get("badge_explorer") == 2

        await sim.do(nova, "vault")            # secret room: hidden badge + tier 3
        assert nova.db.get("badge_trespasser") == 1
        assert nova.db.get("badge_explorer") == 3
        assert any("Trespasser" in m for m in sim.seen(nova))

        await sim.do(nova, "badges")
        out = joined(sim.seen(nova))
        assert "Explorer (tier 3)" in out
        assert "Trespasser" in out

    async def test_hidden_badge_is_not_listed_until_earned(self, world):
        sim, bela, hub = world
        await sim.do(bela, "@name here = The Grand Concourse")
        await build(sim, bela, ACHIEVEMENT_BUILD)
        moon = sim.player("Moon", location=one(sim, "The Grand Concourse"))
        await sim.do(moon, "observatory")      # earns Explorer, never enters vault
        await sim.do(moon, "badges")
        out = joined(sim.seen(moon))
        assert "Explorer" in out
        assert "Trespasser" not in out         # hidden until unlocked


# =========================================================================
# 208. Collectible lore
# =========================================================================

LORE_BUILD = [
    "@create archive terminal",
    "drop archive terminal",
    "@desc archive terminal = A humming data pedestal. CODEX lists the lore you have recovered.",
    '@set archive terminal/entries = {"beacon": {"title": "The Silent Beacon", "text": "Colony ship Meridian went dark here in 2189; its beacon still pulses on a dead channel."}, "mutiny": {"title": "The Long Mutiny", "text": "The crew that survived did not do so kindly. Three names were struck from the log."}}',
    "@create data log",
    "@tag data log = thing",
    "drop data log",
    "@set data log/on_get = set_attr(enactor, 'lore_beacon', 1); pemit(enactor, 'You recovered a data log. A codex entry was unlocked.')",
    "@create faded mural",
    "drop faded mural",
    "@set faded mural/on_use = set_attr(enactor, 'lore_mutiny', 1); pemit(enactor, 'You study the faded mural. A codex entry was unlocked.')",
    "@set archive terminal/cmd_codex = $codex:defs = V('entries', {}); found = [s for s in defs if get_attr(enactor, 'lore_' + s, 0)]; pemit(enactor, f'Codex -- {len(found)}/{len(defs)} entries recovered:'); [pemit(enactor, f'  [{defs[s][\"title\"]}] {defs[s][\"text\"]}') for s in defs if get_attr(enactor, 'lore_' + s, 0)]; [pemit(enactor, '  [LOCKED] ???') for s in defs if not get_attr(enactor, 'lore_' + s, 0)]",
]


@pytest.mark.asyncio
class TestCollectibleLore:

    async def test_found_logs_unlock_codex_entries(self, world):
        sim, bela, hub = world
        await build(sim, bela, LORE_BUILD)
        sol = sim.player("Sol", location=hub)

        await sim.do(sol, "codex")
        out = joined(sim.seen(sol))
        assert "0/2 entries recovered" in out
        assert out.count("[LOCKED]") == 2

        await sim.do(sol, "get data log")
        assert sol.db.get("lore_beacon") == 1
        await sim.do(sol, "codex")
        out = joined(sim.seen(sol))
        assert "1/2 entries recovered" in out
        assert "The Silent Beacon" in out
        assert out.count("[LOCKED]") == 1     # mutiny still hidden

        await sim.do(sol, "use faded mural")
        assert sol.db.get("lore_mutiny") == 1
        await sim.do(sol, "codex")
        out = joined(sim.seen(sol))
        assert "2/2 entries recovered" in out
        assert "The Long Mutiny" in out
        assert "[LOCKED]" not in out

    async def test_lore_is_per_player(self, world):
        sim, bela, hub = world
        await build(sim, bela, LORE_BUILD)
        sol = sim.player("Sol", location=hub)
        luna = sim.player("Luna", location=hub)
        await sim.do(sol, "get data log")
        await sim.do(luna, "codex")           # Luna found nothing
        assert "0/2 entries recovered" in joined(sim.seen(luna))


# =========================================================================
# Docs <-> tests sync — every tested Build-it line must appear in its doc
# =========================================================================

DOC_TRANSCRIPTS = {
    "198_quest_framework.md": WARDEN_BUILD,
    "199_delivery_quest.md": DELIVERY_BUILD,
    "200_collection_counters.md": COLLECTION_BUILD,
    "201_branching_quest.md": BRANCHING_BUILD,
    "202_invasion.md": INVASION_BUILD,
    "203_cutscenes.md": CUTSCENE_BUILD,
    "204_gm_possession.md": POSSESSION_BUILD,
    "205_scene_logger.md": SCENE_BUILD,
    "206_rumor_mill.md": RUMOR_BUILD,
    "207_achievements.md": ACHIEVEMENT_BUILD,
    "208_collectible_lore.md": LORE_BUILD,
}


def test_tutorial_docs_contain_the_exact_tested_command_lines():
    """Every Build-it line exercised above appears verbatim in its doc,
    so the tutorials can never drift from what the tests prove works."""
    for doc_name, lines in DOC_TRANSCRIPTS.items():
        text = (DOCS / doc_name).read_text(encoding="utf-8")
        for line in lines:
            assert line in text, (
                f"{doc_name} is missing a tested tutorial line:\n{line}")
