"""
Showcase verification — Combat & Conflict Extensions (standalone tutorials).

Items: 109 cover system, 111 grenades, 112 non-lethal takedowns,
113 dueling system, 114 bounty board, 115 arena with spectators,
117 armor degradation, 118 bleeding & first aid, 119 NPC morale,
120 combat replay log.

Every command line in each tutorial's "Build it" section is read
straight out of its markdown (docs/showcase/NNN_*.md) and driven through
the real dispatcher (raw input in -> session output out), so the tests
execute what the docs actually say: a doc edit that breaks a build breaks
this suite. The plays then exercise the tutorials' "Try it" flows and
assert outcomes.

Determinism: skill checks use the level resolver (success iff effective
skill >= 10, contests go to the higher skill, ties to the opponent);
combat swings use a diceless GURPS ruleset (3d6 always rolls 10, damage
a flat 3 before DR). Encounter beats are fired by calling
resolve_round() by hand; wait() fuses fire on tick_waits() pumps;
out-of-combat effect beats advance via deliver_beat().
"""

from __future__ import annotations

from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from realm.combat.manager import CombatManager, set_combat_manager
from realm.combat.rulesets.gurps import GURPSRuleset
from realm.combat.system import CombatSystem
from realm.core.beats import deliver_beat
from realm.core.checks import CheckResult, set_check_resolver, skill_level
from realm.testing import Simulator


def level_resolver(obj, skill, modifier):
    effective = skill_level(obj, skill) + modifier
    return CheckResult(
        success=effective >= 10,
        margin=effective - 10,
        roll=10,
        effective=effective,
        skill=skill,
    )


class SteadyRuleset(GURPSRuleset):
    """GURPS with the dice removed: 3d6 always 10, damage a flat
    ``per_hit`` (3 unless a test dials it — item 117's armor spends
    damage points, so its arithmetic needs a knob)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.per_hit = 3

    def roll_3d6(self):
        return 10, [3, 3, 4]

    def roll_damage(self, attacker, defender, attack_result, weapon=None):
        from realm.combat.ruleset import DamageResult, DamageType
        return DamageResult(
            total=self.per_hit,
            damage_by_type={DamageType.PHYSICAL: self.per_hit})


# --- Build transcripts (read out of the tutorials themselves) ------------------

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


BUILD_109 = build_lines("109_cover_system.md")
BUILD_111 = build_lines("111_grenades.md")
BUILD_112 = build_lines("112_nonlethal_takedowns.md")
BUILD_113 = build_lines("113_dueling.md")
BUILD_114 = build_lines("114_bounty_board.md")
BUILD_115 = build_lines("115_arena_spectators.md")
BUILD_117 = build_lines("117_armor_degradation.md")   # an ADMIN build
BUILD_118 = build_lines("118_bleeding_first_aid.md")
BUILD_119 = build_lines("119_npc_morale.md")
BUILD_120 = build_lines("120_combat_replay.md")

BUILD_RED_FLAGS = (
    "Unknown command", "Usage:", "not found", "Script error",
    "can't", "don't", "No permission",
)


# --- Harness -------------------------------------------------------------------


@pytest.fixture
def sim():
    simulator = Simulator()
    set_check_resolver(level_resolver)
    # GameServer wires the session manager at startup; the Simulator
    # leaves it to the test (needed by prompt()).
    simulator.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: list(simulator._sessions.values()))
    yield simulator
    set_check_resolver(None)
    simulator.close()


@pytest.fixture
def combat():
    """A live CombatManager on a diceless ruleset; beats fired by hand."""
    from realm.combat.combatant import clear_combatant_cache
    clear_combatant_cache()
    manager = CombatManager(
        CombatSystem(ruleset=SteadyRuleset()),
        beat_min=4.0, beat_max=600.0, beat_default=300.0,
    )
    set_combat_manager(manager)
    yield manager
    manager.stop_all()
    set_combat_manager(None)
    clear_combatant_cache()


async def run_lines(sim, player, lines):
    """Drive raw command lines through the dispatcher, keeping the
    deterministic resolver pinned (a build's @reload re-installs the
    GURPS dice resolver)."""
    for line in lines:
        await sim.do(player, line)
        set_check_resolver(level_resolver)


async def build(sim, lines, *, admin=False):
    """Run one tutorial's build transcript as a builder from Limbo."""
    limbo = sim.room("Limbo")
    builder = sim.player("Bob", location=limbo)
    builder.add_tag("builder")
    if admin:
        builder.add_tag("admin")
    await run_lines(sim, builder, lines)
    out = "\n".join(sim.seen(builder))
    for flag in BUILD_RED_FLAGS:
        assert flag not in out, f"build tripped {flag!r}:\n{out}"
    return builder


def room(sim, name):
    matches = [o for o in sim.store.find_cached(name=name) if o.has_tag("room")]
    assert matches, f"no room named {name!r}"
    return matches[0]


def obj(sim, name):
    matches = sim.store.find_cached(name=name)
    assert matches, f"no object named {name!r}"
    return matches[0]


def objs(sim, name):
    return sim.store.find_cached(name=name)


def text(sim, player):
    return "\n".join(sim.seen(player))


def fighter(sim, name, where, **over):
    """A player with a workable GURPS sheet against the diceless ruleset."""
    attrs = dict(hp=30, max_hp=30, skill_melee=16, dodge=0,
                 strength=10, dexterity=10)
    attrs.update(over)
    return sim.player(name, location=where, **attrs)


async def rounds(manager, someone, n=1):
    """Fire n combat beats on someone's encounter."""
    encounter = manager.encounter_of(someone)
    assert encounter is not None, f"{someone.name} is not in a fight"
    for _ in range(n):
        await encounter.resolve_round()


# --- 109. Cover system -----------------------------------------------------------


class TestCoverSystem:

    async def test_native_cover_spoils_ranged_fire(self, sim, combat):
        builder = await build(sim, BUILD_109)
        killhouse = room(sim, "The Killhouse")
        assert builder.location is killhouse
        # skill_ranged 11: hits at full skill (roll 10), misses at -2 cover.
        ace = fighter(sim, "Ace", killhouse, skill_ranged=11)
        bruce = fighter(sim, "Bruce", killhouse, hp=20, max_hp=20)

        await sim.do(ace, "get laser carbine")
        await sim.do(ace, "wield laser carbine")
        assert "You ready laser carbine." in text(sim, ace)

        await sim.do(ace, "attack Bruce")
        await sim.do(ace, "queue withdraw")
        await rounds(combat, ace)                      # Ace opens the range
        assert "You fall back out of reach." in text(sim, ace)

        await sim.do(ace, "queue shoot Bruce")
        await rounds(combat, ace)                      # clean shot: hits
        assert int(bruce.db.get("hp")) == 17

        await sim.do(bruce, "queue cover")
        await sim.do(ace, "queue wait")
        await rounds(combat, ace)                      # Bruce digs in
        out = text(sim, bruce)
        assert "You duck behind the overturned dropship hull." in out
        assert "takes cover behind the overturned dropship hull" in text(sim, ace)

        await sim.do(ace, "queue shoot Bruce")
        await rounds(combat, ace)                      # -2 vs cover: a miss
        assert int(bruce.db.get("hp")) == 17

    async def test_destructible_cover_denies_the_next_taker(self, sim, combat):
        builder = await build(sim, BUILD_109)
        killhouse = room(sim, "The Killhouse")
        ace = fighter(sim, "Ace", killhouse, skill_ranged=11)
        bruce = fighter(sim, "Bruce", killhouse, hp=20, max_hp=20)
        hull = obj(sim, "overturned dropship hull")

        await sim.do(builder, "shred hull")
        assert "tears chunks off the hull" in text(sim, builder)
        assert hull.has_tag("cover")
        await sim.do(builder, "shred hull")
        assert "cover for no one now!" in text(sim, builder)
        assert not hull.has_tag("cover")
        await sim.do(builder, "shred hull")
        assert "The hull is already scrap." in text(sim, builder)

        # With the tag gone, the engine refuses the maneuver.
        await sim.do(ace, "attack Bruce")
        await sim.do(bruce, "queue cover")
        await sim.do(ace, "queue wait")
        await rounds(combat, ace)
        assert "There's nothing here to take cover behind." in text(sim, bruce)


# --- 111. Grenades -----------------------------------------------------------------


class TestGrenades:

    async def test_pin_throw_fuse_and_blast(self, sim, combat):
        builder = await build(sim, BUILD_111)
        bunker = room(sim, "The Bunker")
        trench = room(sim, "The Trench")
        assert builder.location is bunker
        # Thrower: dexterity 14 -> throwing 12 (passes). In the trench:
        # Brick dives clear (reflexes 13), Mook eats shrapnel, the thug dies.
        zeke = sim.player("Zeke", location=bunker, dexterity=14,
                          hp=30, max_hp=30)
        brick = sim.player("Brick", location=trench, dexterity=14,
                           hp=30, max_hp=30)
        mook = sim.player("Mook", location=trench, dexterity=8,
                          hp=30, max_hp=30)
        thug = sim.obj("trench thug", location=trench, tags=["npc"],
                       hp=1, max_hp=1, dexterity=8)

        await sim.do(zeke, "pull pin")
        assert "Pick it up first" in text(sim, zeke)

        await sim.do(zeke, "get frag grenade")
        await run_lines(sim, builder, ["@set frag grenade/fuse = 0"])
        await sim.do(zeke, "pull pin")
        assert "pulls the pin. The spoon pings away." in text(sim, builder)
        await sim.do(zeke, "pull pin")
        assert "The pin is already out!" in text(sim, zeke)

        await sim.do(zeke, "throw grenade trench")
        assert "hurls the grenade through the trench exit!" in text(sim, builder)
        assert obj(sim, "frag grenade").location is trench
        assert "A grenade bounces in" in text(sim, brick)

        sim.seen(mook)
        await sim.engine.tick_waits()                  # the fuse runs out
        brick_out = text(sim, brick)
        assert "WHUMP." in brick_out
        assert "You dive clear of the blast!" in brick_out
        assert int(brick.db.get("hp")) == 30
        assert "Shrapnel tears into you!" in text(sim, mook)
        assert int(mook.db.get("hp")) < 30
        # The thug went to zero: the shared death path made a corpse.
        assert [o for o in trench.contents if o.name.startswith("corpse of")]
        assert objs(sim, "frag grenade") == []         # the casing is spent

    async def test_held_too_long_drops_and_detonates_at_your_feet(self, sim, combat):
        builder = await build(sim, BUILD_111)
        bunker = room(sim, "The Bunker")
        zeke = sim.player("Zeke", location=bunker, dexterity=8,
                          hp=30, max_hp=30)

        await sim.do(zeke, "get frag grenade")
        await run_lines(sim, builder, ["@set frag grenade/fuse = 0"])
        await sim.do(zeke, "pull pin")

        await sim.engine.tick_waits()                  # boom: still in hand
        assert "slips through Zeke's fingers!" in text(sim, builder)
        assert obj(sim, "frag grenade").location is bunker
        await sim.engine.tick_waits()                  # the chained blast
        assert "WHUMP." in text(sim, zeke)
        assert int(zeke.db.get("hp")) < 30             # reflexes 7: no save
        assert objs(sim, "frag grenade") == []

    async def test_bad_throw_scatters_through_another_exit(self, sim, combat):
        builder = await build(sim, BUILD_111)
        bunker = room(sim, "The Bunker")
        limbo = room(sim, "Limbo")
        mook = sim.player("Mook", location=bunker, dexterity=8,
                          hp=30, max_hp=30)

        await sim.do(mook, "throw grenade trench")
        assert "You are not holding the grenade." in text(sim, mook)

        await sim.do(mook, "get frag grenade")
        await sim.do(mook, "throw grenade nowhere")
        assert "No open exit called nowhere here." in text(sim, mook)

        # throwing 6: the throw goes wide -- the only other open exit
        # is 'out', so it skips into Limbo. Unarmed, so no boom follows.
        await sim.do(mook, "throw grenade trench")
        assert "It caroms off the frame" in text(sim, builder)
        assert obj(sim, "frag grenade").location is limbo
        await sim.engine.tick_waits()
        assert objs(sim, "frag grenade")               # inert, intact


# --- 112. Non-lethal takedowns ------------------------------------------------------


class TestNonlethalTakedowns:

    async def test_sap_bind_wake_and_release(self, sim, combat):
        builder = await build(sim, BUILD_112)
        brig = room(sim, "The Brig")
        mara = fighter(sim, "Mara", brig, skill_melee=14)
        zeke = sim.player("Zeke", location=brig, health=8,
                          hp=13, max_hp=13)
        brick = sim.player("Brick", location=brig, health=14,
                           hp=13, max_hp=13)

        # Melee 14 vs Fortitude 14: the tie goes to the target.
        await sim.do(mara, "sap Brick")
        assert "twists away from Mara's cosh!" in text(sim, mara)
        assert not brick.has_tag("unconscious")

        # Melee 14 vs Fortitude 8: down he goes -- no HP touched.
        await sim.do(mara, "sap Zeke")
        assert "fold up like wet paper" in text(sim, mara)
        assert "A starburst of white -- then nothing." in text(sim, zeke)
        assert zeke.has_tag("unconscious")
        assert int(zeke.db.get("hp")) == 13

        # Captives are out of the combat system entirely.
        await sim.do(mara, "attack Zeke")
        assert "not something you can fight" in text(sim, mara)

        await sim.do(mara, "bind Brick")
        assert "They are wide awake -- put them down first." in text(sim, mara)
        await sim.do(mara, "bind Zeke")
        assert "snaps iron binders around Zeke's wrists." in text(sim, mara)
        assert zeke.has_tag("restrained")

        # The knockout expires on its own beats; the restraint does not.
        for _ in range(8):
            await deliver_beat(zeke)
        assert not zeke.has_tag("unconscious")
        assert "skull full of gravel" in text(sim, zeke)
        assert zeke.has_tag("restrained")

        await sim.do(zeke, "out")
        assert "The binders hold -- you are going nowhere." in text(sim, zeke)
        assert zeke.location is brig

        await sim.do(mara, "release Zeke")
        assert not zeke.has_tag("restrained")
        await sim.do(zeke, "out")
        assert zeke.location is room(sim, "Limbo")

    async def test_death_path_contrast_corpse_vs_unconscious(self, sim, combat):
        builder = await build(sim, BUILD_112)
        brig = room(sim, "The Brig")
        mara = fighter(sim, "Mara", brig, skill_melee=14, dodge=12)
        thug = sim.obj("brig thug", location=brig, tags=["npc"],
                       hp=3, max_hp=3, dodge=0)
        loot = sim.obj("shiv", location=thug, tags=["thing"])

        # NPCs at zero HP DIE -- no captive, a lootable corpse.
        await sim.do(mara, "attack brig thug")
        await rounds(combat, mara)
        corpses = [o for o in brig.contents if o.name.startswith("corpse of")]
        assert len(corpses) == 1 and loot.location is corpses[0]

        # Players at zero HP fall unconscious in place, and firstaid revives.
        bruiser = sim.obj("bruiser", location=brig, tags=["npc"],
                          hp=30, max_hp=30, skill_melee=16, dodge=12)
        dana = fighter(sim, "Dana", brig, hp=3, skill_melee=4)
        await sim.do(dana, "attack bruiser")
        await rounds(combat, dana)
        assert dana.has_tag("unconscious")
        assert dana.location is brig
        assert "Everything goes black..." in text(sim, dana)

        medic = fighter(sim, "Medic", brig, skill_first_aid=14)
        await sim.do(medic, "firstaid Dana")
        assert not dana.has_tag("unconscious")
        assert int(dana.db.get("hp")) > 0


# --- 113. Dueling system -------------------------------------------------------------


class TestDueling:

    async def test_ward_blocks_unsanctioned_swings(self, sim, combat):
        builder = await build(sim, BUILD_113, admin=True)
        ring = room(sim, "The Ring")
        ace = fighter(sim, "Ace", ring, credits=100)
        bruce = fighter(sim, "Bruce", ring, credits=100)

        await sim.do(ace, "attack Bruce")
        await rounds(combat, ace)
        assert "The Ring hosts sanctioned duels only" in text(sim, ace)
        assert int(bruce.db.get("hp")) == 30           # nothing landed

    async def test_declined_challenge_moves_no_money(self, sim, combat):
        builder = await build(sim, BUILD_113, admin=True)
        ring = room(sim, "The Ring")
        ace = fighter(sim, "Ace", ring, credits=100)
        bruce = fighter(sim, "Bruce", ring, credits=100)
        stone = obj(sim, "dueling stone")

        await sim.do(ace, "duel Bruce")
        assert "challenges you to a duel for 25 credits" in text(sim, bruce)
        handler = sim.session(bruce).input_handler
        assert handler is not None, "prompt() should capture the next line"
        await handler(sim.session(bruce), "no")
        assert "declines the duel" in text(sim, ace)
        assert stone.db.get("challenger") is None
        assert int(ace.db.get("credits")) == 100
        assert int(bruce.db.get("credits")) == 100
        assert not ace.has_tag("duelist")

    async def test_full_duel_escrow_fight_and_payout(self, sim, combat):
        builder = await build(sim, BUILD_113, admin=True)
        ring = room(sim, "The Ring")
        # Ace defends everything (dodge 12); Bruce is two hits from down.
        ace = fighter(sim, "Ace", ring, credits=100, dodge=12)
        bruce = fighter(sim, "Bruce", ring, credits=100, hp=6, max_hp=6)
        stone = obj(sim, "dueling stone")

        await sim.do(ace, "duel Bruce")
        handler = sim.session(bruce).input_handler
        await handler(sim.session(bruce), "accept")
        assert "The stakes -- 50 credits -- rattle into the stone. FIGHT!" \
            in text(sim, ace)
        assert int(stone.db.get("credits") or 0) == 50   # escrow on the stone
        assert int(ace.db.get("credits")) == 75
        assert int(bruce.db.get("credits")) == 75
        assert ace.has_tag("duelist") and bruce.has_tag("duelist")
        assert combat.encounter_of(ace) is not None

        await rounds(combat, ace, 2)                   # 6 -> 3 -> down
        assert bruce.has_tag("unconscious")            # players never die
        assert "stands over a fallen rival. The stone pays out 50 credits." \
            in text(sim, ace)
        assert int(ace.db.get("credits")) == 125
        assert int(bruce.db.get("credits")) == 75
        assert not ace.has_tag("duelist") and not bruce.has_tag("duelist")
        assert stone.db.get("challenger") is None


# --- 114. Bounty board ----------------------------------------------------------------


class TestBountyBoard:

    async def test_post_stake_announce_and_verified_claim(self, sim, combat):
        builder = await build(sim, BUILD_114)
        office = room(sim, "The Bounty Office")
        gulch = room(sim, "Rattler Gulch")
        board = obj(sim, "bounty board")
        assert builder.location is office
        hunter = fighter(sim, "Ryn", gulch, dodge=12, credits=0)

        await run_lines(sim, builder, ["@set me/credits = 200"])
        await sim.do(builder, "post Dreg Farrow")
        assert "Contract drafted on Dreg Farrow." in text(sim, builder)

        await sim.do(builder, "pay 60 to bounty board")
        assert int(builder.db.get("credits")) == 140
        assert int(board.db.get("credits")) == 60      # escrow on the board
        assert board.db.get("ledger") == [["Dreg Farrow", 60]]
        # The crier is zone-wide: the hunter hears it a room away.
        assert "60 credits on the head of Dreg Farrow!" in text(sim, hunter)

        await sim.do(builder, "bounties")
        assert "[WANTED] Dreg Farrow -- 60 credits." in text(sim, builder)

        await sim.do(hunter, "attack Dreg Farrow")
        await rounds(combat, hunter, 2)                # 6 -> 3 -> dead
        assert int(hunter.db.get("credits")) == 60
        assert int(board.db.get("credits")) == 0
        assert board.db.get("ledger") == []
        assert "BOUNTY CLAIMED: Ryn collects 60 credits for Dreg Farrow." \
            in text(sim, builder)
        assert [o for o in gulch.contents if o.name.startswith("corpse of")]

        sim.seen(builder)
        await sim.do(builder, "bounties")
        assert "The board is bare." in text(sim, builder)

    async def test_a_poisoned_mark_pays_the_poisoner(self, sim, combat):
        """Poisoning a mark collects the bounty.

        Both halves had to land for this. `combat:on_death` fires from
        EVERY death, so the board hears a poison kill at all (it used to
        hear only swings) -- and `apply_effect` now stamps `source_id`
        with whoever applied the effect, so the tick can name a killer.
        Before, the board heard the death, found `enactor` None, and had
        nobody to pay: the mark died and the contract stayed open."""
        builder = await build(sim, BUILD_114)
        gulch = room(sim, "Rattler Gulch")
        board = obj(sim, "bounty board")
        dreg = obj(sim, "Dreg Farrow")
        hunter = fighter(sim, "Ryn", gulch, credits=0)

        await run_lines(sim, builder, ["@set me/credits = 200"])
        await sim.do(builder, "post Dreg Farrow")
        await sim.do(builder, "pay 60 to bounty board")
        assert board.db.get("ledger") == [["Dreg Farrow", 60]]
        sim.seen(builder)

        # A damage_over_time effect ticking on out-of-combat beats: no
        # encounter, no swing, no CombatSystem.attack anywhere. (Dosed
        # from the gulch -- get() reaches the local room only.)
        await run_lines(sim, builder, [
            "gulch",
            "@eval apply_effect(get('Dreg Farrow'), 'damage_over_time', "
            "kind='gulch_venom', damage=2, interval=1, duration=8, "
            "tick_msg='The venom burns.'); result = 1",
            "office",
        ])
        assert dreg.has_tag("gulch_venom"), "the mark was never dosed"
        assert combat.encounter_of(dreg) is None
        sim.seen(builder)

        for _ in range(3):                             # 6 -> 4 -> 2 -> 0
            await deliver_beat(dreg)

        # The death happened, the shared path announced it...
        assert int(dreg.db.get("hp")) <= 0
        assert [o for o in gulch.contents if o.name.startswith("corpse of")]
        # ...and the tick named its poisoner, so the contract settles.
        # The builder dosed the mark, so the builder collects — the hunter
        # who never touched it does not.
        assert "BOUNTY CLAIMED" in text(sim, builder)
        assert int(hunter.db.get("credits")) == 0
        assert board.db.get("ledger") == []                      # struck
        assert int(board.db.get("credits")) == 0                 # escrow paid out

    async def test_a_neighbours_payment_never_stakes_a_contract(
            self, sim, combat):
        """The board is a ZONE MASTER, so its ON_PAYMENT hears every
        payment in every badlands room -- not just its own. Without
        `target == me`, buying a drink two rooms away would eat the
        buyer's pending draft and post a contract for nothing. Drop the
        guard from the doc and this test fails."""
        builder = await build(sim, BUILD_114)
        board = obj(sim, "bounty board")
        await run_lines(sim, builder, ["@set me/credits = 200"])

        # An unrelated payee, out in the gulch, a room away from the board.
        await run_lines(sim, builder, [
            "gulch", "@create a vending machine", "drop a vending machine",
        ])
        await sim.do(builder, "post Dreg Farrow")      # a draft, pending
        sim.seen(builder)

        await sim.do(builder, "pay 25 to a vending machine")
        assert not board.db.get("ledger")              # nothing staked
        assert int(board.db.get("credits") or 0) == 0  # no escrow
        assert "crier bellows" not in text(sim, builder)
        # The draft survives, because the board never saw a payment.
        assert board.db.get("pending_" + builder.id) == "Dreg Farrow"

        # ...and a real stake still works.
        await run_lines(sim, builder, ["office"])
        await sim.do(builder, "pay 60 to bounty board")
        assert board.db.get("ledger") == [["Dreg Farrow", 60]]

    async def test_paying_without_a_draft_is_refused(self, sim, combat):
        builder = await build(sim, BUILD_114)
        await run_lines(sim, builder, ["@set me/credits = 50"])
        await sim.do(builder, "pay 10 to bounty board")
        assert "Draft a contract first: POST <name>." in text(sim, builder)
        assert not obj(sim, "bounty board").db.get("ledger")


# --- 115. Arena with spectators --------------------------------------------------------


class TestArenaSpectators:

    async def test_stands_get_the_blow_by_blow_and_only_that(self, sim, combat):
        builder = await build(sim, BUILD_115)
        pit = room(sim, "The Fight Pit")
        stands = room(sim, "The Stands")
        ace = fighter(sim, "Ace", pit, dodge=12)
        bruce = fighter(sim, "Bruce", pit, hp=6, max_hp=20)
        sal = sim.player("Sal", location=stands)

        await sim.do(ace, "attack Bruce")
        await rounds(combat, ace)
        feed = text(sim, sal)
        assert "[pit] Ace wades in on Bruce!" in feed  # the hook's target
        assert "Bruce 6/20" in feed                    # the open-read tally
        # adata('damage'): the call quotes the blow, not an HP delta.
        assert "[pit] Ace draws blood -- 3 on Bruce!" in feed

        await sim.do(bruce, "say is that ALL")
        assert "[pit] Bruce bellows: is that ALL" in text(sim, sal)

        await rounds(combat, ace)
        feed = text(sim, sal)
        assert "Bruce 3/20" in feed                    # last round's toll
        assert "THE CROWD ROARS -- Ace puts Bruce down and takes the pit!" \
            in feed

        # Ringside vs pit: fighters never see the relay tag...
        assert "[pit]" not in text(sim, ace)
        # ...and the stands never saw the pit's native narration.
        assert "squares off" not in feed


# --- 117. Armor degradation -------------------------------------------------------------


class TestArmorDegradation:

    async def test_soak_wear_out_shred_and_repair(self, sim, combat):
        builder = await build(sim, BUILD_117, admin=True)
        outfitter = room(sim, "The Outfitter")
        vest = obj(sim, "flak vest")
        # Nia swings at air (skill 4) but flees well (dexterity 14).
        nia = fighter(sim, "Nia", outfitter, hp=20, max_hp=20,
                      skill_melee=4, dexterity=14, skill_armoury=12)
        thug = sim.obj("pit thug", location=outfitter, tags=["npc"],
                       hp=30, max_hp=30, skill_melee=16, dodge=0)

        await sim.do(nia, "get flak vest")
        await sim.do(nia, "wear flak vest")
        assert ("You cinch the flak vest tight. (DR 3, 9 points of plating)"
                in text(sim, nia))
        assert int(nia.db.get("damage_resistance")) == 3
        assert int(nia.db.get("armor_plating")) == 9
        assert nia.db.get("on_damage")                 # the ledger hook

        # The thug swings for 3 against DR 3: the vest stops all 3 and is
        # billed exactly 3 points of ceramic -- adata('damage') in action.
        await sim.do(nia, "attack pit thug")
        await rounds(combat, nia)                      # hit 1: fully soaked
        assert ("Your vest soaks 3 -- 6 points of plating left."
                in text(sim, nia))
        assert int(nia.db.get("hp")) == 20
        await rounds(combat, nia)                      # hit 2: fully soaked
        assert int(nia.db.get("hp")) == 20
        assert int(nia.db.get("armor_plating")) == 3
        await rounds(combat, nia)                      # hit 3: the ceramic runs out
        assert "comes apart at the seams" in text(sim, nia)
        assert int(nia.db.get("damage_resistance")) == 0
        assert int(nia.db.get("hp")) == 17             # the breaking hit lands

        await sim.do(nia, "flee out")
        await rounds(combat, nia)                      # dexterity 14: escapes
        assert nia.location is room(sim, "Limbo")
        await sim.do(nia, "outfitter")

        await sim.do(nia, "remove flak vest")
        assert "You shrug out of the vest." in text(sim, nia)
        assert int(vest.db.get("plating")) == 0        # wear synced back
        assert nia.db.get("armor_plating") is None
        assert nia.db.get("on_damage") is None

        await sim.do(nia, "wear flak vest")
        assert "The vest is shredded" in text(sim, nia)
        assert not nia.db.get("damage_resistance")

        await sim.do(nia, "remove flak vest")
        await sim.do(nia, "drop flak vest")
        await sim.do(nia, "repair vest")
        assert "hammers the plating flat" in text(sim, nia)
        assert int(vest.db.get("plating")) == 9

        await sim.do(nia, "get flak vest")
        await sim.do(nia, "wear flak vest")
        assert "(DR 3, 9 points of plating)" in text(sim, nia)
        assert int(nia.db.get("damage_resistance")) == 3

    async def test_wear_is_billed_per_point_the_ceramic_actually_stopped(
            self, sim, combat):
        """The point of adata('damage'): the vest spends min(DR, damage),
        so a graze is cheap and an overkill costs no more than the DR the
        vest was ever worth. Neither is visible when every hit happens to
        land for exactly DR, which is why this test dials the weapon."""
        builder = await build(sim, BUILD_117, admin=True)
        outfitter = room(sim, "The Outfitter")
        vest = obj(sim, "flak vest")
        nia = fighter(sim, "Nia", outfitter, hp=40, max_hp=40, skill_melee=4)
        sim.obj("pit thug", location=outfitter, tags=["npc"],
                hp=99, max_hp=99, skill_melee=16, dodge=0)
        await sim.do(nia, "get flak vest")
        await sim.do(nia, "wear flak vest")
        await sim.do(nia, "attack pit thug")

        # A 1-point graze: DR 3 stops all of it, but only 1 point of
        # ceramic was ever in the way -- bill 1, not 3, and not a "plate".
        combat.combat_system.ruleset.per_hit = 1
        await rounds(combat, nia)
        assert "Your vest soaks 1 -- 8 points of plating left." in text(sim, nia)
        assert int(nia.db.get("hp")) == 40                 # fully soaked

        # A 20-point slug: the vest stops 3 of it and is billed 3. The
        # other 17 go through Nia. Wear tracks what the armor did, not
        # how hard it was hit.
        combat.combat_system.ruleset.per_hit = 20
        await rounds(combat, nia)
        assert "Your vest soaks 3 -- 5 points of plating left." in text(sim, nia)
        assert int(nia.db.get("hp")) == 40 - (20 - 3)      # DR still applied

        # Five points left, a 9-point blow: still only 3 of ceramic stood
        # in the way, so still only 3 is billed. A big weapon does not
        # chew armor faster than the armor can stop it.
        combat.combat_system.ruleset.per_hit = 9
        await rounds(combat, nia)
        assert "Your vest soaks 3 -- 2 points of plating left." in text(sim, nia)
        assert int(nia.db.get("hp")) == 23 - (9 - 3)

        # Two points left against another 9: the remainder is less than
        # the DR, so it breaks -- and the breaking blow lands undefended.
        await rounds(combat, nia)
        assert "comes apart at the seams" in text(sim, nia)
        assert int(nia.db.get("armor_plating")) == 0
        assert int(nia.db.get("damage_resistance")) == 0
        assert int(nia.db.get("hp")) == 17 - 9             # no DR left to help

        await sim.do(nia, "remove flak vest")
        assert int(vest.db.get("plating")) == 0

    async def test_a_bystanders_wounds_never_wear_your_vest(self, sim, combat):
        """combat:on_damage is a WITNESSED event: it fires the ON_DAMAGE
        of everything in the room, not just the defender. The wearer's
        hook is still the wearer's -- `me` is Nia either way -- so only
        `target == me` separates "I was hit" from "someone near me was
        hit". Without it a vest rots from other people's wounds. Drop the
        guard from the doc and this test fails."""
        builder = await build(sim, BUILD_117, admin=True)
        outfitter = room(sim, "The Outfitter")
        nia = fighter(sim, "Nia", outfitter, skill_melee=4)
        bruce = fighter(sim, "Bruce", outfitter, skill_melee=4)
        sim.obj("pit thug", location=outfitter, tags=["npc"],
                hp=99, max_hp=99, skill_melee=16, dodge=0)

        await sim.do(nia, "get flak vest")
        await sim.do(nia, "wear flak vest")
        assert int(nia.db.get("armor_plating")) == 9
        sim.seen(nia)

        # Bruce picks the fight. Nia just stands there wearing the vest.
        await sim.do(bruce, "attack pit thug")
        await rounds(combat, bruce, 3)
        assert int(bruce.db.get("hp")) < 30            # he is definitely taking hits
        assert int(nia.db.get("armor_plating")) == 9   # her ceramic is untouched
        assert "Your vest soaks" not in text(sim, nia)

        # Positive control: her own wounds still bill her vest. (The thug
        # is juggling two opponents, so give it a few beats to swing her way.)
        await sim.do(nia, "attack pit thug")
        for _ in range(8):
            await rounds(combat, nia)
            if int(nia.db.get("armor_plating")) < 9:
                break
        assert int(nia.db.get("armor_plating")) < 9
        assert "Your vest soaks 3" in text(sim, nia)

    async def test_repair_needs_the_vest_on_the_bench(self, sim, combat):
        builder = await build(sim, BUILD_117, admin=True)
        nia = fighter(sim, "Nia", room(sim, "The Outfitter"), skill_armoury=12)
        await sim.do(nia, "get flak vest")
        await sim.do(nia, "repair vest")
        assert "Lay the vest on the bench first" in text(sim, nia)


# --- 118. Bleeding & first aid -------------------------------------------------------------


class TestBleedingFirstAid:

    async def test_wounds_bleed_on_the_beat_and_bandage_stops_them(self, sim, combat):
        builder = await build(sim, BUILD_118)
        yard = room(sim, "The Red Yard")
        ace = fighter(sim, "Ace", yard, dodge=12)
        bruce = fighter(sim, "Bruce", yard, hp=20, max_hp=20)
        ferd = fighter(sim, "Ferd", yard, skill_first_aid=6)
        mara = fighter(sim, "Mara", yard, skill_first_aid=14)

        await sim.do(ace, "attack Bruce")
        await rounds(combat, ace)                      # round 1: first wound
        assert int(bruce.db.get("hp")) == 17
        assert not bruce.has_tag("bleeding")           # hooks saw him unhurt

        await rounds(combat, ace)                      # round 2: now he bleeds
        assert bruce.has_tag("bleeding")
        assert int(bruce.db.get("hp")) == 14

        await rounds(combat, ace)                      # round 3: beat + swing
        assert int(bruce.db.get("hp")) == 10           # -1 bleed, -3 hit
        assert "Your wound runs red" in text(sim, bruce)

        # Ringside medics work mid-fight -- $bandage is a room command.
        await sim.do(ferd, "bandage Bruce")
        assert "The dressing soaks through." in text(sim, ferd)
        assert bruce.has_tag("bleeding")

        await sim.do(mara, "bandage Bruce")
        assert "ties off Bruce's wound. The bleeding stops." in text(sim, mara)
        assert not bruce.has_tag("bleeding")
        assert int(bruce.db.get("hp")) == 11           # the dressing's +1

        await rounds(combat, ace)                      # round 4: no bleed tick
        assert int(bruce.db.get("hp")) == 8            # only the swing
        # ...but the new wound sets him bleeding again -- battlefield rules.
        assert bruce.has_tag("bleeding")

        # The attacker was never wounded, so he never bled.
        assert not ace.has_tag("bleeding")

    async def test_bandage_refuses_the_unwounded(self, sim, combat):
        builder = await build(sim, BUILD_118)
        yard = room(sim, "The Red Yard")
        mara = fighter(sim, "Mara", yard, skill_first_aid=14)
        brick = fighter(sim, "Brick", yard)
        await sim.do(mara, "bandage Brick")
        assert "They are not bleeding." in text(sim, mara)
        await sim.do(mara, "bandage Nobody")
        assert "No patient by that name here." in text(sim, mara)


# --- 119. NPC morale ---------------------------------------------------------------------


class TestNPCMorale:

    async def test_broken_nerve_surrenders_and_warms_to_the_victor(self, sim, combat):
        from realm.core.disposition import get_disposition

        builder = await build(sim, BUILD_119)
        lair = room(sim, "Raider Lair")
        limbo = room(sim, "Limbo")
        vex = obj(sim, "Vex")
        hunter = fighter(sim, "Hunter", limbo, dodge=12)

        await sim.do(hunter, "lair")                   # aggressive engages
        assert '"Your boots -- I want them."' in text(sim, hunter)
        assert combat.encounter_of(vex) is not None

        await sim.do(hunter, "attack Vex")
        await rounds(combat, hunter)                   # 12 -> 9 (75%)
        assert not vex.has_tag("surrendered")
        await rounds(combat, hunter)                   # 9 -> 6: crosses 50%
        assert "I yield! I yield" in text(sim, hunter)
        assert vex.has_tag("surrendered")
        assert "aggressive" not in [b.behavior_id for b in vex.get_behaviors()]
        assert vex.db.get("combat_strategy") == [["", "wait"]]
        assert get_disposition(vex, hunter) == 5

        # Hands up means hands up: she waits the next beat out.
        await sim.do(hunter, "queue wait")
        await rounds(combat, hunter)
        assert int(vex.db.get("hp")) == 6
        assert int(hunter.db.get("hp")) == 30

    async def test_steady_nerve_flees_on_the_next_beat(self, sim, combat):
        builder = await build(sim, BUILD_119)
        lair = room(sim, "Raider Lair")
        limbo = room(sim, "Limbo")
        vex = obj(sim, "Vex")
        await run_lines(sim, builder, ["@set Vex/health = 13"])
        hunter = fighter(sim, "Hunter", limbo, dodge=12)

        await sim.do(hunter, "lair")
        await sim.do(hunter, "attack Vex")
        await rounds(combat, hunter, 2)                # crosses 50%: nerve holds
        assert "Not like this!" in text(sim, hunter)
        assert "fleeing" in [b.behavior_id for b in vex.get_behaviors()]

        await rounds(combat, hunter)                   # the override rule fires
        assert vex.location is limbo                   # out the only exit
        assert not vex.has_tag("in_combat")
        assert not vex.has_tag("surrendered")


# --- 120. Combat replay log -----------------------------------------------------------------


class TestCombatReplay:

    async def test_scribe_records_and_replay_reads_back_in_order(self, sim, combat):
        builder = await build(sim, BUILD_120)
        cage = room(sim, "The Fight Cage")
        chronicle = obj(sim, "match chronicle")
        ace = fighter(sim, "Ace", cage, dodge=12)
        bruce = fighter(sim, "Bruce", cage, hp=6, max_hp=20)

        await sim.do(ace, "attack Bruce")
        await rounds(combat, ace)                      # 6 -> 3
        await sim.do(bruce, "say remember this")
        await rounds(combat, ace)                      # 3 -> down: FINISH

        rows = chronicle.db.get("log")
        assert rows and len(rows) <= 30
        joined = "\n".join(r[1] for r in rows)
        # Each head logs its own event: target, damage, weapon (fists here).
        assert "Ace presses the attack on Bruce barehanded. [" in joined
        assert "Bruce 6:20" in joined                  # the pre-blow tally
        assert "Ace lands 3 on Bruce." in joined
        assert "Bruce shouts: remember this" in joined
        assert "FINISH -- Ace ends Bruce." in joined
        assert joined.index("Bruce 6:20") < joined.index("remember this") \
            < joined.index("FINISH")

        await sim.do(ace, "replay")
        out = text(sim, ace)
        assert "s ago] Ace presses the attack on Bruce" in out
        assert "s ago] FINISH -- Ace ends Bruce." in out

    async def test_wipe_is_owner_only(self, sim, combat):
        builder = await build(sim, BUILD_120)
        cage = room(sim, "The Fight Cage")
        chronicle = obj(sim, "match chronicle")
        ace = fighter(sim, "Ace", cage, dodge=12)
        bruce = fighter(sim, "Bruce", cage, hp=6, max_hp=20)
        await sim.do(ace, "attack Bruce")
        await rounds(combat, ace)
        assert chronicle.db.get("log")

        await sim.do(ace, "wipe ledger")
        assert "clutches its ledger jealously" in text(sim, ace)
        assert chronicle.db.get("log")

        await sim.do(builder, "wipe ledger")
        assert "You tear out the used pages." in text(sim, builder)
        assert not chronicle.db.get("log")
        await sim.do(builder, "replay")
        assert "The ledger is blank." in text(sim, builder)
