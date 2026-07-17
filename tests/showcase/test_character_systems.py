"""
Showcase verification — Character Systems (checklist items 132, 135-138,
140-143).

Every command line in each tutorial's "Build it" section is read straight
out of its markdown (docs/showcase/132_chargen_walkthrough.md ..
143_xp_spending.md) and driven through a real in-process world — the
realm.testing.Simulator wires the same store / propagation / scripting /
dispatcher stack a live GameServer does. The doc is the test input, so a
tutorial edit that breaks the build breaks this suite. Each play then
walks its tutorial's "Try it" flow: raw input in, session output out.

Determinism: skill checks use a level resolver (success iff effective
skill >= 10, with condition modifiers folded in exactly as the engine
does), so injuries, encumbrance, hunger, and traits change rolls by their
stated amounts. Effect beats are advanced by calling deliver_beat() by
hand; ticker behaviors are fired with @tr; the death path (item 140) uses a
diceless GURPS ruleset with resolve_round() fired by hand, and the clone
bay's zero-second wait() fuse is pumped with tick_waits() (the Simulator
defers waits to a virtual clock).
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from realm.core.beats import deliver_beat
from realm.core.checks import CheckResult, set_check_resolver, skill_level
from realm.testing import Simulator

# Output that must never appear while running a "Build it" transcript.
BUILD_RED_FLAGS = (
    "Unknown command", "Usage:", "not found", "Script error",
    "Eval error", "No permission", "Permission denied", "Bad parameter",
    "Unknown behavior",
)


# --- Build transcripts: read straight out of the tutorials ----------------------

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"

DOC_FILES = {
    132: "132_chargen_walkthrough.md",
    135: "135_injury_treatment.md",
    136: "136_encumbrance.md",
    137: "137_hunger_thirst.md",
    138: "138_sleep_rest.md",
    140: "140_death_cloning.md",
    141: "141_character_sheet.md",
    142: "142_traits_in_play.md",
    143: "143_xp_spending.md",
}


def build_lines(doc_name: str) -> list[str]:
    """Every command line in the tutorial's "Build it" fenced blocks."""
    body = (DOCS / doc_name).read_text(encoding="utf-8")
    match = re.search(r"^## Build it$(.*?)^## ", body, re.M | re.S)
    assert match, f"{doc_name}: no Build it section"
    lines: list[str] = []
    for block in re.findall(r"```text\n(.*?)```", match.group(1), re.S):
        lines.extend(line for line in block.splitlines() if line.strip())
    assert lines, f"{doc_name}: empty Build it"
    return lines


# --- Harness -------------------------------------------------------------------


def level_resolver(obj, skill, modifier):
    """Diceless: success iff skill level + modifier >= 10. `modifier` already
    carries the summed condition modifiers (check()'s condition_modifier),
    so injuries, encumbrance, hunger, and traits all fold in here."""
    effective = skill_level(obj, skill) + modifier
    return CheckResult(effective >= 10, effective - 10, 10, effective, skill)


@pytest.fixture
def sim():
    simulator = Simulator()
    set_check_resolver(level_resolver)
    # prompt() finds player sessions through the engine's session manager;
    # the Simulator leaves it to the test to wire (as the combat suite does).
    simulator.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: list(simulator._sessions.values()))
    yield simulator
    set_check_resolver(None)
    simulator.close()


@pytest.fixture
def combat():
    """A live CombatManager on a diceless ruleset; beats fired by hand."""
    from realm.combat.combatant import clear_combatant_cache
    from realm.combat.manager import CombatManager, set_combat_manager
    from realm.combat.rulesets.gurps import GURPSRuleset
    from realm.combat.system import CombatSystem

    class SteadyRuleset(GURPSRuleset):
        def roll_3d6(self):
            return 10, [3, 3, 4]

        def roll_damage(self, attacker, defender, attack_result, weapon=None):
            from realm.combat.ruleset import DamageResult, DamageType
            return DamageResult(total=3, damage_by_type={DamageType.PHYSICAL: 3})

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
    for line in lines:
        await sim.do(player, line)
        set_check_resolver(level_resolver)


async def build(sim, item: int, *, admin=False):
    """Run a tutorial's "Build it" transcript — read from its markdown — as a
    builder standing in Limbo. The doc IS the test input: an edit that breaks
    the build breaks this suite."""
    doc_name = DOC_FILES[item]
    limbo = sim.room("Limbo")
    builder = sim.player("Bob", location=limbo)
    builder.add_tag("builder")
    if admin:
        builder.add_tag("admin")
    await run_lines(sim, builder, build_lines(doc_name))
    out = "\n".join(sim.seen(builder))
    for flag in BUILD_RED_FLAGS:
        assert flag not in out, f"{doc_name} build tripped {flag!r}:\n{out}"
    return builder


def room(sim, name):
    matches = [o for o in sim.store.find_cached(name=name) if o.has_tag("room")]
    assert matches, f"no room named {name!r}"
    return matches[0]


def obj(sim, name):
    matches = sim.store.find_cached(name=name)
    assert matches, f"no object named {name!r}"
    return matches[0]


def text(sim, player):
    return "\n".join(sim.seen(player))


async def rounds(manager, someone, n=1):
    encounter = manager.encounter_of(someone)
    assert encounter is not None, f"{someone.name} is not in a fight"
    for _ in range(n):
        await encounter.resolve_round()


# --- 132. Chargen walkthrough --------------------------------------------------


class TestChargenWalkthrough:

    async def test_wizard_writes_a_full_sheet(self, sim):
        await build(sim, 132, admin=True)
        booth = room(sim, "The Induction Booth")
        rook = sim.player("Rook", location=booth)

        await sim.do(rook, "enlist")
        assert "Choose a background -- scout, soldier" in text(sim, rook)
        sess = sim.session(rook)
        assert sess.input_handler is not None, "enlist should prompt"

        await sess.input_handler(sess, "soldier")
        assert "Pick a bonus skill" in text(sim, rook)
        assert rook.db.get("strength") == 12
        assert rook.db.get("skill_guns") == 12
        assert rook.db.get("template") == "soldier"

        sess = sim.session(rook)
        assert sess.input_handler is not None, "background should re-prompt"
        await sess.input_handler(sess, "melee")
        out = text(sim, rook)
        assert "Induction complete. HP 12, Dodge 9" in out
        assert rook.db.get("skill_melee") == 13      # soldier's 12, +1 bonus
        assert int(rook.db.get("hp")) == 12          # derived from ST
        assert int(rook.db.get("max_hp")) == 12
        assert int(rook.db.get("dodge")) == 9        # 7 + (11+12)//8

    async def test_bad_background_reprompts_then_takes_the_next_answer(self, sim):
        await build(sim, 132, admin=True)
        booth = room(sim, "The Induction Booth")
        dex = sim.player("Dex", location=booth)

        await sim.do(dex, "enlist")
        sess = sim.session(dex)
        await sess.input_handler(sess, "wizard")
        assert "No such background." in text(sim, dex)
        assert dex.db.get("template") is None

        sess = sim.session(dex)
        await sess.input_handler(sess, "scout")
        assert dex.db.get("template") == "scout"
        assert dex.db.get("skill_stealth") == 13

    async def test_enlisting_twice_is_refused(self, sim):
        await build(sim, 132, admin=True)
        booth = room(sim, "The Induction Booth")
        vet = sim.player("Vet", location=booth, template="soldier")
        await sim.do(vet, "enlist")
        assert "already filed" in text(sim, vet)


# --- 135. Injury & treatment ---------------------------------------------------


class TestInjuryTreatment:

    async def test_injury_folds_into_rolls_and_treatment_clears_it(self, sim):
        await build(sim, 135)
        medbay = room(sim, "The Med Bay")
        zeke = sim.player("Zeke", location=medbay, skill_melee=12,
                          hp=20, max_hp=20)
        mara = sim.player("Mara", location=medbay, skill_first_aid=14)
        ferd = sim.player("Ferd", location=medbay, skill_first_aid=6)

        await sim.do(mara, "check Zeke")
        assert "a Melee roll SUCCEEDS cleanly." in text(sim, mara)

        await sim.do(zeke, "grip wire")
        assert "grabs the live wire and convulses!" in text(sim, zeke)
        assert zeke.has_tag("wounded")
        assert int(zeke.db.get("hp")) == 18                 # -2 HP
        assert zeke.db.get("check_mods") == {"wounded": {"all": -3}}

        await sim.do(mara, "check Zeke")
        assert "FAILS -- the hand is shaking." in text(sim, mara)   # 12 - 3 = 9

        await sim.do(ferd, "splint Zeke")                   # first_aid 6: fails
        assert "Your hands slip on the splint" in text(sim, ferd)
        assert zeke.has_tag("wounded")

        await sim.do(mara, "splint Zeke")                   # first_aid 14: works
        assert "braces and binds Zeke's arm" in text(sim, mara)
        assert not zeke.has_tag("wounded")
        assert not zeke.db.get("check_mods")                # condition stripped
        assert int(zeke.db.get("hp")) == 19                 # the dressing's +1

        await sim.do(mara, "check Zeke")
        assert "a Melee roll SUCCEEDS cleanly." in text(sim, mara)

    async def test_injury_heals_on_its_own_timer(self, sim):
        await build(sim, 135)
        medbay = room(sim, "The Med Bay")
        zeke = sim.player("Zeke", location=medbay, skill_melee=12,
                          hp=20, max_hp=20)
        await sim.do(zeke, "grip wire")
        assert zeke.has_tag("wounded")
        for _ in range(10):
            await deliver_beat(zeke)
        assert not zeke.has_tag("wounded")                  # clotted after 10 beats
        assert "the injury has healed." in text(sim, zeke).lower()

    async def test_grab_and_check_refusals(self, sim):
        await build(sim, 135)
        medbay = room(sim, "The Med Bay")
        zeke = sim.player("Zeke", location=medbay, skill_melee=12,
                          hp=20, max_hp=20)
        await sim.do(zeke, "check Nobody")
        assert "No one here by that name." in text(sim, zeke)
        await sim.do(zeke, "grip wire")
        await sim.do(zeke, "grip wire")                     # already wounded
        assert "your arm still remembers it." in text(sim, zeke)


# --- 136. Encumbrance ----------------------------------------------------------


class TestEncumbrance:

    async def test_load_scales_the_penalty(self, sim):
        await build(sim, 136)
        dock = room(sim, "The Loading Dock")
        hef = sim.player("Hef", location=dock, strength=10, basic_move=5)

        await sim.do(hef, "heft")
        assert "Basic Lift 20 lbs. You carry 0 lbs -> None encumbrance (DX 0, Move 5/5)." \
            in text(sim, hef)
        assert not hef.db.get("check_mods")

        await sim.do(hef, "get supply crate")
        await sim.do(hef, "heft")
        assert "You carry 25 lbs -> Light encumbrance (DX -1, Move 4/5)." in text(sim, hef)
        assert hef.db.get("check_mods") == {"encumbered": {"all": -1}}

        await sim.do(hef, "get ammo case")
        await sim.do(hef, "heft")
        assert "You carry 70 lbs -> Heavy encumbrance (DX -3, Move 2/5)." in text(sim, hef)
        assert hef.db.get("check_mods") == {"encumbered": {"all": -3}}

        await sim.do(hef, "drop ammo case")
        await sim.do(hef, "heft")
        assert "You carry 25 lbs -> Light encumbrance (DX -1, Move 4/5)." in text(sim, hef)

        await sim.do(hef, "drop supply crate")
        await sim.do(hef, "heft")
        assert "You carry 0 lbs -> None encumbrance (DX 0, Move 5/5)." in text(sim, hef)
        assert not hef.db.get("check_mods")

    async def test_strength_raises_the_ceiling(self, sim):
        await build(sim, 136)
        dock = room(sim, "The Loading Dock")
        ox = sim.player("Ox", location=dock, strength=14, basic_move=5)
        await sim.do(ox, "get supply crate")
        await sim.do(ox, "get ammo case")
        await sim.do(ox, "heft")                            # BL 39, 70 lbs -> Light
        assert "Basic Lift 39 lbs. You carry 70 lbs -> Light encumbrance" in text(sim, ox)


# --- 137. Hunger & thirst ------------------------------------------------------


class TestHungerThirst:

    async def test_meters_drain_warn_and_faint_then_a_ration_restores(self, sim):
        builder = await build(sim, 137, admin=True)
        mess = room(sim, "The Mess Deck")
        vale = sim.player("Vale", location=mess)

        for _ in range(7):
            await sim.do(builder, "@tr life support monitor/on_tick")
            set_check_resolver(level_resolver)

        stream = text(sim, vale)
        assert "Your stomach growls; your mouth is dry." in stream   # thresholds
        assert "You are faint from hunger and thirst." in stream     # bottomed out
        assert vale.has_tag("starving")
        assert vale.db.get("check_mods") == {"starving": {"all": -2}}
        assert int(vale.db.get("thirst")) == 0
        assert int(vale.db.get("hunger")) == 30

        await sim.do(vale, "eat")
        assert "tears into a ration pack" in text(sim, vale)
        assert int(vale.db.get("hunger")) == 100
        assert int(vale.db.get("thirst")) == 100
        assert not vale.has_tag("starving")
        assert not vale.db.get("check_mods")

    async def test_no_meters_outside_the_zone(self, sim):
        builder = await build(sim, 137, admin=True)
        limbo = room(sim, "Limbo")
        drifter = sim.player("Drifter", location=limbo)      # unzoned
        for _ in range(5):
            await sim.do(builder, "@tr life support monitor/on_tick")
            set_check_resolver(level_resolver)
        assert drifter.db.get("hunger") is None              # never touched


# --- 138. Sleep & rest ---------------------------------------------------------


class TestSleepRest:

    async def test_rest_heals_locks_movement_and_wake_ends_it(self, sim):
        await build(sim, 138)
        bunkroom = room(sim, "The Bunkroom")
        nyx = sim.player("Nyx", location=bunkroom, hp=10, max_hp=30)

        await deliver_beat(nyx)
        assert int(nyx.db.get("hp")) == 10                  # no passive regen

        await sim.do(nyx, "rest")
        assert "lies back on the cot" in text(sim, nyx)
        assert nyx.has_tag("resting")

        for _ in range(3):
            await deliver_beat(nyx)
        assert int(nyx.db.get("hp")) == 19                  # +3 a beat

        await sim.do(nyx, "out")
        assert "You are wrapped in sleep -- WAKE before you can move." in text(sim, nyx)
        assert nyx.location is bunkroom

        await sim.do(nyx, "wake")
        assert not nyx.has_tag("resting")
        await deliver_beat(nyx)
        assert int(nyx.db.get("hp")) == 19                  # healer gone

        await sim.do(nyx, "out")
        assert nyx.location is room(sim, "Limbo")

    async def test_wake_when_up_is_a_no_op(self, sim):
        await build(sim, 138)
        bunkroom = room(sim, "The Bunkroom")
        nyx = sim.player("Nyx", location=bunkroom, hp=10, max_hp=30)
        await sim.do(nyx, "wake")
        assert "already up and about." in text(sim, nyx)


# --- 140. Death & cloning ------------------------------------------------------


class TestDeathCloning:

    async def test_downed_player_is_cloned_and_billed(self, sim, combat):
        """The bay hears combat:on_death from a room it doesn't sit in (the
        zone master's reach) and reads adata('fatal') == False as 'a player
        dropped'."""
        await build(sim, 140, admin=True)
        clonebay = room(sim, "The Clone Bay")
        deck = room(sim, "The Combat Deck")
        cass = sim.player("Cass", location=deck, hp=4, max_hp=30,
                          skill_melee=16, dodge=0, credits=100)
        sim.obj("bruiser", location=deck, tags=["npc"],
                hp=30, max_hp=30, skill_melee=16, dodge=12)

        await sim.do(cass, "attack bruiser")
        for _ in range(3):
            if cass.has_tag("unconscious"):
                break
            await rounds(combat, cass)
        assert cass.has_tag("unconscious")                  # players fall, don't die
        assert cass.location is deck                        # the fuse hasn't fired yet

        controller = obj(sim, "resurrection controller")
        assert controller.db.get("fallen") == [cass.id]     # heard, filed

        await sim.engine.tick_waits()                       # the wait(0) handoff
        assert cass.location is clonebay                    # reborn across the station
        assert not cass.has_tag("unconscious")              # and the tag stays off
        assert int(cass.db.get("hp")) == 30                 # restored to full
        assert int(cass.db.get("credits")) == 50            # 100 - 50 clone fee
        assert int(cass.db.get("clone_count")) == 1
        assert controller.db.get("fallen") == []            # queue drained
        out = text(sim, cass)
        assert "is reborn." in out
        assert "You wake in a fresh body" in out
        # The deferred handoff is what keeps the narration honest: the death
        # event fires BEFORE handle_death stamps `unconscious` and prints its
        # line, so reviving inside the hook would invert these two.
        assert out.index("Everything goes black") < out.index("Cold light")

    async def test_the_bay_has_no_ticker_and_never_sweeps(self, sim):
        """Nothing polls: the controller is a pure listener."""
        await build(sim, 140, admin=True)
        controller = obj(sim, "resurrection controller")
        assert controller.get_behaviors() == []
        assert controller.db.get("on_tick") is None
        assert controller.has_tag("zone_master")

    async def test_two_players_dropping_at_once_both_wake(self, sim, combat):
        """Each death lights its own fuse; `fallen` is a list, so the first
        drain revives everyone and the second finds an empty queue."""
        await build(sim, 140, admin=True)
        clonebay = room(sim, "The Clone Bay")
        deck = room(sim, "The Combat Deck")
        controller = obj(sim, "resurrection controller")
        cass = sim.player("Cass", location=deck, hp=1, max_hp=30, credits=100)
        dov = sim.player("Dov", location=deck, hp=1, max_hp=30, credits=100)

        await combat.handle_death(cass)
        await combat.handle_death(dov)
        assert controller.db.get("fallen") == [cass.id, dov.id]

        await sim.engine.tick_waits()
        assert cass.location is clonebay
        assert dov.location is clonebay
        assert int(cass.db.get("clone_count")) == 1         # billed once each
        assert int(dov.db.get("clone_count")) == 1
        assert int(cass.db.get("credits")) == 50
        assert int(dov.db.get("credits")) == 50

    async def test_a_broke_traveller_is_cloned_for_every_credit_they_have(
            self, sim, combat):
        await build(sim, 140, admin=True)
        deck = room(sim, "The Combat Deck")
        pip = sim.player("Pip", location=deck, hp=1, max_hp=12, credits=10)
        await combat.handle_death(pip)
        await sim.engine.tick_waits()
        assert pip.location is room(sim, "The Clone Bay")    # nobody is left to rot
        assert int(pip.db.get("credits")) == 0              # the vat takes the lot

    async def test_npc_death_leaves_a_corpse(self, sim, combat):
        await build(sim, 140, admin=True)
        deck = room(sim, "The Combat Deck")
        ryn = sim.player("Ryn", location=deck, hp=30, max_hp=30,
                         skill_melee=16, dodge=12)
        sim.obj("deck mook", location=deck, tags=["npc"],
                hp=3, max_hp=3, dodge=0)
        await sim.do(ryn, "attack deck mook")
        await rounds(combat, ryn)
        corpses = [o for o in deck.contents if o.name.startswith("corpse of")]
        assert len(corpses) == 1                            # native corpse path

        # The bay heard this death too — adata('fatal') was True, so it kept
        # its vats shut and filed nobody.
        await sim.engine.tick_waits()
        assert not obj(sim, "resurrection controller").db.get("fallen")


# --- 141. Character sheet -------------------------------------------------------


class TestCharacterSheet:

    async def test_formatted_sheet_and_native_points(self, sim):
        await build(sim, 141)
        alcove = room(sim, "The Med Scanner Alcove")
        ivo = sim.player("Ivo", location=alcove, template="soldier",
                         strength=12, dexterity=11, intelligence=10, health=12,
                         hp=9, max_hp=12, dodge=9, character_points=6,
                         skill_melee=13, skill_guns=12)
        ivo.add_tag("wounded")

        await sim.do(ivo, "sheet")
        out = text(sim, ivo)
        assert "Ivo  --  soldier" in out
        assert "ST 12    DX 11    IQ 10    HT 12" in out
        assert "HP [#######---] 9/12     Dodge 9" in out
        assert "CP 6" in out
        assert "Skills: melee-13, guns-12" in out
        assert "Status: wounded" in out

        # The native sheet is the always-current source of truth.
        await sim.do(ivo, "points")
        pts = text(sim, ivo)
        assert "Character points: 6" in pts
        assert "melee" in pts and "13" in pts

    async def test_untrained_and_nominal_read_cleanly(self, sim):
        await build(sim, 141)
        alcove = room(sim, "The Med Scanner Alcove")
        raw = sim.player("Raw", location=alcove, hp=10, max_hp=10)
        await sim.do(raw, "sheet")
        out = text(sim, raw)
        assert "Skills: none trained" in out
        assert "Status: nominal" in out


# --- 142. Traits in play -------------------------------------------------------


class TestTraitsInPlay:

    async def test_modifier_traits_shift_rolls_and_a_phobia_bites(self, sim):
        await build(sim, 142)
        clinic = room(sim, "The Gene Clinic")
        rell = sim.player("Rell", location=clinic,
                          skill_observation=8, skill_melee=9)

        await sim.do(rell, "prove")
        assert "Observation: fail | Melee: fail" in text(sim, rell)

        await sim.do(rell, "graft reflexes")
        assert "reflexes wind tight" in text(sim, rell)
        await sim.do(rell, "prove")
        assert "Observation: fail | Melee: pass" in text(sim, rell)   # +1 all

        await sim.do(rell, "graft keen eye")
        await sim.do(rell, "prove")
        assert "Observation: pass | Melee: pass" in text(sim, rell)   # +2 obs

        await sim.do(rell, "graft claustrophobia")
        assert rell.has_tag("claustrophobia")
        await sim.do(rell, "crawlway")
        assert "The walls crush inward." in text(sim, rell)
        assert rell.has_tag("panic")

        await sim.do(rell, "clinic")
        await sim.do(rell, "prove")
        assert "Observation: fail | Melee: fail" in text(sim, rell)   # panic -2 drags both

    async def test_unknown_trait_and_double_graft(self, sim):
        await build(sim, 142)
        clinic = room(sim, "The Gene Clinic")
        rell = sim.player("Rell", location=clinic,
                          skill_observation=8, skill_melee=9)
        await sim.do(rell, "graft flight")
        assert "No such trait on file." in text(sim, rell)
        await sim.do(rell, "graft reflexes")
        await sim.do(rell, "graft reflexes")
        assert "already spliced in." in text(sim, rell)


# --- 143. XP spending ----------------------------------------------------------


class TestXpSpending:

    async def test_study_spends_cp_gated_by_cooldown_and_purse(self, sim):
        builder = await build(sim, 143, admin=True)
        annex = room(sim, "The Training Annex")
        dex = sim.player("Dex", location=annex, character_points=12,
                         dexterity=10, skill_melee=10, skill_stealth=10)

        await sim.do(dex, "study melee")
        assert "You drill melee hard. It clicks -- now 11. (8 CP left)" in text(sim, dex)
        assert dex.db.get("skill_melee") == 11
        assert int(dex.db.get("character_points")) == 8

        await sim.do(dex, "study melee")                    # cooldown
        assert "still consolidating melee" in text(sim, dex)
        assert dex.db.get("skill_melee") == 11              # unchanged

        await sim.do(dex, "study stealth")                  # a different skill: free
        assert "It clicks -- now 11. (4 CP left)" in text(sim, dex)

        await run_lines(sim, builder, ["@set training terminal/cooldown = 0"])
        await sim.do(dex, "study melee")                    # cooldown lifted
        assert "It clicks -- now 12. (0 CP left)" in text(sim, dex)
        assert int(dex.db.get("character_points")) == 0

        await sim.do(dex, "study guns")                     # out of points
        assert "Drilling guns costs 4 CP; you have 0." in text(sim, dex)
        assert dex.db.get("skill_guns") is None

    async def test_native_improve_is_the_ungated_baseline(self, sim):
        await build(sim, 143, admin=True)
        annex = room(sim, "The Training Annex")
        pat = sim.player("Pat", location=annex, character_points=4,
                         dexterity=10, skill_stealth=11)
        await sim.do(pat, "improve stealth")
        assert "You train stealth to 12" in text(sim, pat)
        assert pat.db.get("skill_stealth") == 12
        assert int(pat.db.get("character_points")) == 0
