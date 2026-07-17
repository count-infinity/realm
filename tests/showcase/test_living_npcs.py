"""
Living NPCs arc (showcase items 60, 64, 67, 68, 71).

Drives every "Build it" command line from the five tutorials
(docs/showcase/060_wandering_npc.md .. 071_guard_response.md) through a
real in-process world — Simulator wires the actual dispatcher, script
engine, and propagation engine — then verifies each tutorial's "Try it"
behavior: raw input in, session output out.

The build transcripts are read *out of the markdown* rather than
mirrored here as literals: the tutorial is the source of truth, so a
doc that stops working stops this suite. Only the walks between
tutorials (the fixture stitches five separate builds into one town) are
the harness's own.

Determinism: behavior ticks are pumped by calling the attached
behaviors' tick() directly (no wall-clock heartbeat); item 71 combat
uses a diceless GURPS ruleset (3d6 always 10, damage flat 2) and
resolve_round() fired by hand.
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
    for block in re.findall(r"```(?:text)?\n(.*?)```", match.group(1), re.S):
        lines.extend(line for line in block.splitlines() if line.strip())
    assert lines, f"{doc_name}: empty Build it"
    return lines

# Output fragments that only appear when a typed line failed.
_ERROR_MARKS = ("not found", "Usage:", "Unknown command", "Bad parameter",
                "Unknown behavior")


# --- Harness ----------------------------------------------------------------


def _find(sim, name):
    objs = sim.store.find_cached(name=name)
    assert objs, f"no object named {name!r}"
    return objs[0]


def _behavior(obj, behavior_id):
    return next(b for b in obj.get_behaviors() if b.behavior_id == behavior_id)


async def _tick(obj, behavior_id="script_ticker"):
    await _behavior(obj, behavior_id).tick(obj, 4.0)


def _text(messages):
    return "\n".join(messages)


@pytest.fixture
async def town():
    """The whole arc's town, built line by typed line."""
    sim = Simulator()
    workroom = sim.room("The Workroom")
    tam = sim.player("Tam", location=workroom)
    tam.add_tag("builder")
    workroom.owner = tam
    # prompt() finds player sessions through the engine's session manager.
    sim.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: [sim.session(tam)])

    errors: list[str] = []

    async def run(lines):
        for line in lines:
            await sim.do(tam, line)
            for msg in sim.seen(tam):
                if any(mark in msg for mark in _ERROR_MARKS):
                    errors.append(f"{line!r} -> {msg!r}")

    # Items 60 and 64 end where the next begins; 67 needs a walk back to
    # the Square before 68 digs Market Street, and 68 ends on Market
    # Street one step from where 71 starts. The walks are the harness's;
    # everything else is the tutorials', read from their markdown.
    await run(build_lines("060_wandering_npc.md"))
    await run(build_lines("064_bartender.md"))
    await run(build_lines("067_dialogue_tree_npc.md"))
    await run(["square"])
    await run(build_lines("068_npc_schedule.md"))
    await run(["square"])
    await run(build_lines("071_guard_response.md"))
    assert not errors, errors

    try:
        yield SimpleNamespace(sim=sim, tam=tam, run=run)
    finally:
        sim.close()


async def _do(town, line):
    """Type one line, return everything the builder's session printed."""
    await town.sim.do(town.tam, line)
    return _text(town.sim.seen(town.tam))


# --- 60. Wandering NPC -------------------------------------------------------


class TestWanderingNpc:

    async def test_zone_confined_wandering(self, town):
        sim, tam = town.sim, town.tam
        scamp = _find(sim, "scamp")
        square = _find(sim, "The Square")
        # The arc fixture builds the whole town, so the scamp may roam any
        # zone:town room — but never these:
        forbidden = {
            _find(sim, "Back Alley").id,      # no_wander tag
            _find(sim, "The Gates").id,       # in reach, but not zoned town
            _find(sim, "The Workroom").id,    # ditto, through 'back'
            _find(sim, "The Loft").id,        # ditto, through 'upstairs'
        }

        # The Build-it line attached and tuned the stock behavior.
        assert "wandering" in [b.behavior_id for b in scamp.get_behaviors()]
        assert scamp.location is square

        # Try it: walk over and re-tune the attached brain live.
        await _do(town, "square")
        out = await _do(
            town, "@behavior/set scamp = wandering, pause:0, wander_chance:1")
        assert "Updated 'wandering'" in out
        out = await _do(town, "@behavior scamp")
        assert "wandering" in out

        wandering = _behavior(scamp, "wandering")
        visited = set()
        for _ in range(60):
            await wandering.tick(scamp, 4.0)
            assert scamp.location.id not in forbidden, scamp.location.name
            assert scamp.location.has_tag("zone:town"), scamp.location.name
            visited.add(scamp.location.id)
        # He really moves — several town rooms get visits.
        assert len(visited) >= 3


# --- 64. Bartender -----------------------------------------------------------


class TestBartender:

    async def test_menu_payment_drink_and_rumors(self, town):
        sim, tam = town.sim, town.tam
        flagon = _find(sim, "The Rusty Flagon")
        mira = _find(sim, "Mira")

        for line in ("square", "flagon", "@set me/credits = 40",
                     "@set me/hp = 9", "@set me/max_hp = 12"):
            await _do(town, line)

        # Keyword menu on a listen trigger.
        out = await _do(town, "say what's on tap?")
        assert "Ale, five credits the mug" in out

        # Rumors are gated on patronage.
        out = await _do(town, "say any rumors?")
        assert "Ale first" in out

        # Pay her: ON_PAYMENT serves a real object.
        out = await _do(town, "pay 5 to Mira")
        assert "One ale, coming up." in out
        assert "sets a foaming mug on the bar" in out
        mug = next(o for o in flagon.contents if o.name == "a mug of ale")
        assert mug.db.get("cmd_drink", "").startswith("$drink *:")
        assert mira.db.get("patron_" + tam.id) == 1
        assert tam.db.get("credits") == 35
        assert mira.db.get("credits") == 5

        # The consumable: heals, narrates, destroys itself.
        out = await _do(town, "drink ale")
        assert "The ale goes down warm." in out
        assert tam.db.get("hp") == 10
        assert all(o.name != "a mug of ale" for o in flagon.contents)

        # Rumors now flow, rotating per player.
        out = await _do(town, "say any rumors?")
        assert "the old mine did not close for bad air alone" in out
        out = await _do(town, "say rumors")
        assert "Verity shuts her shop at nine sharp" in out
        assert mira.db.get("idx_" + tam.id) == 2

    async def test_short_payment_is_refused(self, town):
        mira = _find(town.sim, "Mira")
        for line in ("square", "flagon", "@set me/credits = 40"):
            await _do(town, line)
        out = await _do(town, "pay 3 to Mira")
        assert "Ale is five credits, love." in out
        assert mira.db.get("patron_" + town.tam.id) is None


# --- 67. Dialogue-tree NPC ----------------------------------------------------


class TestDialogueTree:

    async def test_branching_memory_and_secret(self, town):
        sim, tam = town.sim, town.tam
        moss = _find(sim, "Old Moss")
        sess = sim.session(tam)

        for line in ("square", "flagon", "@set me/credits = 40"):
            await _do(town, line)

        # First meeting: greeting + the bare menu.
        out = await _do(town, "talk")
        assert "New face. Name is Moss." in out
        assert "[1] Ask about the town." in out
        assert "[2]" not in out and "[3]" not in out
        assert sess.input_handler is not None

        # Asking about the town unlocks the mine option in the re-prompt.
        await sess.input_handler(sess, "1")
        out = _text(sim.seen(tam))
        assert "Quiet town." in out
        assert "[2] Ask about the old mine." in out
        assert moss.db.get("town_" + tam.id) == 1

        # The mine branch hints at the drink gate; [3] stays hidden.
        await sess.input_handler(sess, "2")
        out = _text(sim.seen(tam))
        assert "An accident, they ruled." in out
        assert "Pay 5 to Old Moss" in out
        assert "[3]" not in out

        # Leave: the chain ends cleanly.
        await sess.input_handler(sess, "q")
        out = _text(sim.seen(tam))
        assert "waves you off" in out
        assert sess.input_handler is None

        # Buy him a drink — a real payment flips real memory.
        out = await _do(town, "pay 5 to Old Moss")
        assert "drinks deep and wipes his beard" in out
        assert moss.db.get("drink_" + tam.id) == 1
        # Mira shared the room but her till delta was zero: silence.
        assert "five credits, love" not in out

        # He remembers you, and the earned branch appears.
        out = await _do(town, "talk")
        assert "Back again, Tam. Thought so." in out
        assert "[3] Press him about the collapse." in out

        await sess.input_handler(sess, "3")
        out = _text(sim.seen(tam))
        assert "it was no accident" in out
        assert sess.input_handler is None
        assert moss.db.get("secret_" + tam.id) == 1

        # The secret is spent: the option never reappears.
        out = await _do(town, "talk")
        assert "[3]" not in out
        await sess.input_handler(sess, "q")


# --- 68. NPC daily schedule ----------------------------------------------------


class TestNpcSchedule:

    async def test_a_day_in_the_life(self, town):
        sim, tam = town.sim, town.tam
        clock = _find(sim, "town clock")
        verity = _find(sim, "Verity")
        market = _find(sim, "Market Street")
        loft = _find(sim, "The Loft")

        async def pump():
            await _tick(clock)
            await _tick(verity)

        def keeping_shop():
            return "shopkeeper" in [b.behavior_id
                                    for b in verity.get_behaviors()]

        # Built at hour 6, dropped at the market, not yet trading.
        assert clock.db.get("hour") == 6
        assert verity.location is market and not keeping_shop()

        await pump()                       # hour 7: off hours — walk home
        assert clock.db.get("hour") == 7
        assert verity.location is loft
        out = await _do(town, "list")
        assert "no merchant here" in out

        await pump()                       # hour 8: asleep upstairs
        assert verity.location is loft

        await pump()                       # hour 9: commute to work
        assert verity.location is market and not keeping_shop()

        await pump()                       # hour 10: open — announce + attach
        out = _text(sim.seen(tam))
        assert "Shutters up! Fresh goods at fair prices!" in out
        assert keeping_shop()

        # The stall works: stock is inventory, prices are value x markup.
        await _do(town, "@set me/credits = 40")
        out = await _do(town, "list")
        assert "ration pack" in out and "10" in out
        out = await _do(town, "buy ration pack")
        assert "You buy ration pack" in out
        pack = _find(sim, "ration pack")
        assert pack.location is tam
        assert tam.db.get("credits") == 30
        assert verity.db.get("credits") == 10

        for _ in range(10):                # hours 11..20: open all day
            await pump()
        assert clock.db.get("hour") == 20
        assert verity.location is market and keeping_shop()

        await pump()                       # hour 21: close — detach + announce
        out = _text(sim.seen(tam))
        assert "Closing up. Come back at nine." in out
        assert not keeping_shop()
        assert verity.location is market   # hasn't left yet...
        out = await _do(town, "list")
        assert "no merchant here" in out   # ...but the shop is already shut

        await pump()                       # hour 22: walk home
        assert verity.location is loft


# --- 71. Guard response ---------------------------------------------------------


class TestGuardResponse:

    async def test_crime_summons_the_watch(self, town):
        from realm.combat.manager import CombatManager, set_combat_manager
        from realm.combat.rulesets.gurps import GURPSRuleset
        from realm.combat.system import CombatSystem
        from realm.core.disposition import get_disposition

        class SteadyRuleset(GURPSRuleset):
            """GURPS with the dice removed: 3d6 always 10, damage flat 2."""

            def roll_3d6(self):
                return 10, [3, 3, 4]

            def roll_damage(self, attacker, defender, attack_result,
                            weapon=None):
                from realm.combat.ruleset import DamageResult, DamageType
                return DamageResult(total=2,
                                    damage_by_type={DamageType.PHYSICAL: 2})

        sim, tam = town.sim, town.tam
        bren = _find(sim, "Watchman Bren")
        market = _find(sim, "Market Street")
        post = _find(sim, "Guard Post")
        master = _find(sim, "Town Watch")
        assert bren.location is post
        assert master.has_tag("zone_master") and master.has_tag("zone:town")

        manager = CombatManager(CombatSystem(ruleset=SteadyRuleset()),
                                beat_min=4.0, beat_max=600.0,
                                beat_default=300.0)
        set_combat_manager(manager)
        try:
            # Try it: give yourself a sheet and start the trouble.
            for line in ("@set me/hp = 12", "@set me/max_hp = 12",
                         "@set me/skill_melee = 12"):
                await _do(town, line)

            out = await _do(town, "attack dock worker")
            assert "square off against dock worker" in out
            encounter = manager.encounter_of(tam)
            assert encounter is not None

            # The first swing is the crime the whole zone hears.
            await encounter.resolve_round()
            out = _text(sim.seen(tam))
            assert "Guards! GUARDS! Blood on Market Street!" in out
            assert "Town watch! Drop it, NOW!" in out
            assert bren.location is market            # summoned to the scene
            assert get_disposition(bren, tam) == -5   # the watch remembers
            assert manager.encounter_of(bren) is encounter  # and joins in

            # One brawl, one dispatch: the cooldown holds on later swings.
            await encounter.resolve_round()
            assert get_disposition(bren, tam) == -5
        finally:
            manager.stop_all()
            set_combat_manager(None)
