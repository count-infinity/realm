"""
Showcase category 18 — Quests & Storytelling (items 198-208).

Every test drives a real in-process world through the dispatcher with the
exact command lines from each tutorial's "Build it" transcript
(docs/showcase/198_quest_framework.md .. 208_collectible_lore.md), then
asserts the outcomes the tutorials promise.

The transcripts are not duplicated here: ``build_lines()`` reads every
command line straight out of the tutorial's "Build it" fenced blocks, so
the tests execute *what the doc says*. Drift between doc and test is
impossible rather than merely detectable — which is why there is no
docs<->tests sync test to keep honest.

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
import re
from types import SimpleNamespace

import pytest

from realm.testing import Simulator

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"


def build_lines(doc_name: str) -> list[str]:
    """Every command line in the tutorial's "Build it" fenced blocks."""
    body = (DOCS / doc_name).read_text()
    match = re.search(r"^## Build it$(.*?)^## ", body, re.M | re.S)
    assert match, f"{doc_name}: no Build it section"
    lines: list[str] = []
    for block in re.findall(r"```text\n(.*?)```", match.group(1), re.S):
        lines.extend(line for line in block.splitlines() if line.strip())
    assert lines, f"{doc_name}: empty Build it"
    return lines


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


async def build(sim, who, doc_name):
    """Run one tutorial's Build-it transcript, read live from its doc."""
    for line in build_lines(doc_name):
        await sim.do(who, line)


async def answer(sim, player, line):
    """Feed a line into a pending prompt() the way a live session would."""
    handler = sim.session(player).input_handler
    assert handler is not None, "prompt() should have captured the next line"
    await handler(sim.session(player), line)


# =========================================================================
# 198. Quest framework
# =========================================================================

@pytest.mark.asyncio
class TestQuestFramework:

    async def test_journal_stages_and_completion_hook(self, world):
        sim, bela, hub = world
        await build(sim, bela, "198_quest_framework.md")
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
        await build(sim, bela, "198_quest_framework.md")
        raven = sim.player("Raven", location=hub)

        await sim.do(raven, "accept quest dragons")
        assert "No such quest." in sim.seen(raven)

        await sim.do(raven, "accept quest cinders")
        sim.seen(raven)
        await sim.do(raven, "accept quest cinders")
        assert "You are already on that quest." in sim.seen(raven)

    async def test_report_with_nothing_due(self, world):
        sim, bela, hub = world
        await build(sim, bela, "198_quest_framework.md")
        raven = sim.player("Raven", location=hub)
        await sim.do(raven, "report")
        assert "You have nothing to report." in sim.seen(raven)


# =========================================================================
# 199. Delivery quest
# =========================================================================

@pytest.mark.asyncio
class TestDeliveryQuest:

    async def test_deliver_on_time_pays_out(self, world):
        sim, bela, hub = world
        await build(sim, bela, "199_delivery_quest.md")
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
        await build(sim, bela, "199_delivery_quest.md")
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

    async def test_agent_ignores_a_handover_to_someone_else(self, world):
        """ON_RECEIVE reaches every witness in the room, not just the
        recipient -- so the Agent's verifier MUST gate on `target is me`.
        Without that guard he pays out (and destroys the orders) when the
        courier hands them to a bystander standing in his office."""
        sim, bela, hub = world
        await build(sim, bela, "199_delivery_quest.md")
        raven = sim.player("Raven", location=hub)
        await sim.do(raven, "courier job")

        await sim.do(bela, "@teleport Raven = The Harbor Office")
        mook = sim.player("Mook", location=one(sim, "The Harbor Office"))
        sim.seen(raven)

        # The orders go to Mook -- NOT to the Agent standing right there.
        await sim.do(raven, "give sealed orders to Mook")
        out = joined(sim.seen(raven))
        assert "Sixty credits" not in out, "the Agent paid for a delivery he never received"
        assert (raven.db.get("credits") or 0) == 0
        assert raven.db.get("deliver_by") > 0, "the quest must stay open"
        # The orders are really Mook's; nobody destroyed or rerouted them.
        assert [o for o in mook.contents if o.name == "sealed orders"]

    async def test_agent_still_pays_with_a_bystander_present(self, world):
        """The guard must reject the wrong recipient without breaking the
        right one -- a bystander in the room changes nothing."""
        sim, bela, hub = world
        await build(sim, bela, "199_delivery_quest.md")
        raven = sim.player("Raven", location=hub)
        await sim.do(raven, "courier job")

        await sim.do(bela, "@teleport Raven = The Harbor Office")
        sim.player("Mook", location=one(sim, "The Harbor Office"))
        sim.seen(raven)

        await sim.do(raven, "give sealed orders to Harbor Agent")
        assert any("Sixty credits" in m for m in sim.seen(raven))
        assert (raven.db.get("credits") or 0) == 60


# =========================================================================
# 200. Collection counters
# =========================================================================

@pytest.mark.asyncio
class TestCollectionCounters:

    async def test_five_relays_auto_track_to_completion(self, world):
        sim, bela, hub = world
        await build(sim, bela, "200_collection_counters.md")
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
        await build(sim, bela, "200_collection_counters.md")
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

@pytest.mark.asyncio
class TestBranchingQuest:

    async def test_choice_locks_a_branch_and_gates_the_ending(self, world):
        sim, bela, hub = world
        await build(sim, bela, "201_branching_quest.md")
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
        await build(sim, bela, "201_branching_quest.md")
        raven = sim.player("Raven", location=hub)
        await sim.do(raven, "parley")
        await answer(sim, raven, "warlord")
        await sim.do(raven, "seek ending")
        assert any("[WARLORD ENDING]" in m for m in sim.seen(raven))

    async def test_a_nonsense_answer_swears_nothing(self, world):
        sim, bela, hub = world
        await build(sim, bela, "201_branching_quest.md")
        raven = sim.player("Raven", location=hub)
        await sim.do(raven, "parley")
        await answer(sim, raven, "maybe later")
        assert any("Speak plainly" in m for m in sim.seen(raven))
        assert not raven.db.get("allegiance")


# =========================================================================
# 202. World event: invasion
# =========================================================================

@pytest.mark.asyncio
class TestInvasion:

    async def test_phased_waves_spawn_then_clean_up(self, world):
        sim, bela, hub = world
        # The build's first line names the starting room the citadel gate.
        await build(sim, bela, "202_invasion.md")
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
        await build(sim, bela, "202_invasion.md")
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

@pytest.mark.asyncio
class TestCutscenes:

    async def test_paced_sequence_plays_to_the_whole_room(self, world):
        sim, bela, hub = world
        await build(sim, bela, "203_cutscenes.md")
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
        await build(sim, bela, "203_cutscenes.md")
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
        await build(sim, bela, "203_cutscenes.md")
        ada = sim.player("Ada", location=hub)
        await sim.do(ada, "skip")
        assert "Nothing is playing." in sim.seen(ada)


# =========================================================================
# 204. GM possession tools
# =========================================================================

@pytest.mark.asyncio
class TestGMPossession:

    async def test_force_speaks_as_the_npc_and_forwards_perception(self, world):
        sim, bela, hub = world
        await build(sim, bela, "204_gm_possession.md")
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
        await build(sim, bela, "204_gm_possession.md")
        await sim.do(bela, "@force Baron Haldor = @dig A Secret Vault")
        # An NPC body has player-level hands: building is refused.
        assert not sim.store.find_cached(name="A Secret Vault")

    async def test_softcode_relay_lets_a_trusted_player_drive_the_npc(self, world):
        sim, bela, hub = world
        await build(sim, bela, "204_gm_possession.md")
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

@pytest.mark.asyncio
class TestSceneLogger:

    async def test_records_only_consenting_players_in_order(self, world):
        sim, bela, hub = world
        await build(sim, bela, "205_scene_logger.md")
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
        # The pose is logged verbatim -- ON_EMOTE carries the text as
        # adata('pose'), so the recorder needs no cooperation from Ben.
        assert log[1][1] == "Ben" and log[1][2] == "bows deeply."
        assert log[2][1] == "Ada" and "Indeed" in log[2][2]
        assert all(row[1] != "Cara" for row in log)            # consent honored

        sim.seen(ada)
        await sim.do(ada, "export")
        out = joined(sim.seen(ada))
        assert "Ada says, \"Well met, friends.\"" in out
        assert "Ben bows deeply." in out

    async def test_leaving_the_scene_stops_recording_that_player(self, world):
        sim, bela, hub = world
        await build(sim, bela, "205_scene_logger.md")
        ada = sim.player("Ada", location=hub)
        await sim.do(ada, "join scene")
        await sim.do(ada, "leave scene")
        await sim.do(ada, "say off the record now.")
        recorder = one(sim, "scene recorder")
        assert not (recorder.db.get("log") or [])


# =========================================================================
# 206. Rumor mill
# =========================================================================

@pytest.mark.asyncio
class TestRumorMill:

    async def test_a_rumor_hops_between_npcs_then_decays(self, world):
        sim, bela, hub = world
        await build(sim, bela, "206_rumor_mill.md")   # seeds Gale's rumor

        # Gale gossips; Pip overhears and now carries the rumor too.
        await sim.do(bela, "@tr Gossip Gale/on_tick")
        assert one(sim, "Old Pip").db.get("rumor") == "the docks flood at dawn"

        # Age Pip's copy past its ttl; the next beat, Pip forgets it.
        await sim.do(bela, "@eval set_attr(get('Old Pip'), 'rumor_at', now() - 100)")
        await sim.do(bela, "@tr Old Pip/on_tick")
        assert not one(sim, "Old Pip").db.get("rumor")

    async def test_a_carrier_does_not_overwrite_its_own_rumor(self, world):
        sim, bela, hub = world
        await build(sim, bela, "206_rumor_mill.md")
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

@pytest.mark.asyncio
class TestAchievements:

    async def test_progressive_tiers_and_hidden_badge(self, world):
        sim, bela, hub = world
        await build(sim, bela, "207_achievements.md")
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
        await build(sim, bela, "207_achievements.md")
        moon = sim.player("Moon", location=one(sim, "The Grand Concourse"))
        await sim.do(moon, "observatory")      # earns Explorer, never enters vault
        await sim.do(moon, "badges")
        out = joined(sim.seen(moon))
        assert "Explorer" in out
        assert "Trespasser" not in out         # hidden until unlocked


# =========================================================================
# 208. Collectible lore
# =========================================================================

@pytest.mark.asyncio
class TestCollectibleLore:

    async def test_found_logs_unlock_codex_entries(self, world):
        sim, bela, hub = world
        await build(sim, bela, "208_collectible_lore.md")
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
        await build(sim, bela, "208_collectible_lore.md")
        sol = sim.player("Sol", location=hub)
        luna = sim.player("Luna", location=hub)
        await sim.do(sol, "get data log")
        await sim.do(luna, "codex")           # Luna found nothing
        assert "0/2 entries recovered" in joined(sim.seen(luna))
