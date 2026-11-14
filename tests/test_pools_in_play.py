"""
KERNEL_PLAN 8.5: pools in play.

Stock combat, stock softcode, stock abilities and stock death handle
things that are not characters with hit points: a ship whose shields take
the blow before its hull, a character whose harm clock fills up, a door
with structure points, a ship whose guns run hot. No test here gives the
non-character entity an ``hp`` attribute.
"""

from __future__ import annotations

import random
import subprocess
from pathlib import Path

import pytest

from realm.core.objects import GameObject
from realm.core.pairing import pair_exits
from realm.games.d20.system import D20System
from realm.games.gurps.system import GurpsSystem
from realm.games.merc.system import MercSystem
from realm.std.abilities.abilities import invoke_ability
from realm.std.combat.encounter import CombatEncounter
from realm.testing import Simulator

SHIP_POOLS = {"shields": {"overflow": "hull"}, "hull": {"soak_attr": "armor"}}


def _ship(sim, room, **attrs):
    ship = sim.obj("ship", location=room, tags=["npc"],
                   pools=SHIP_POOLS, shields=20, max_shields=20,
                   hull=30, max_hull=30, armor=2, damage_pool="shields",
                   when_spent="none", combat_default="nothing",
                   dodge=0, armor_class=1, **attrs)
    ship.db.on_spent = "if adata('pool') == 'hull': incr('wrecked')"
    return ship


def _ability(sim, name, **attrs):
    adef = GameObject(name=name, tags=["ability_def"])
    for key, value in attrs.items():
        adef.db.set(key, value)
    sim.add(adef)
    return adef


# --- a ship under each stock ruleset -------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("system", [GurpsSystem, D20System, MercSystem],
                         ids=["gurps", "d20", "merc"])
async def test_a_ship_takes_a_fight(system, monkeypatch):
    random.seed(8)
    landed: list[tuple] = []
    land = CombatEncounter.land

    async def recording_land(self, participant, target, result, messages=None):
        await land(self, participant, target, result, messages)
        for change in result.changes:
            landed.append((change, target.obj.db.hull))

    monkeypatch.setattr(CombatEncounter, "land", recording_land)

    with Simulator(game_system=system) as sim:
        room = sim.room("Dock")
        ship = _ship(sim, room)
        gunner = sim.player("Gunner", location=room, hp=500, max_hp=500,
                            strength=20, dexterity=14, skill_melee=18,
                            proficiency_bonus=10, thac0=1, level=30)
        await sim.do(gunner, "attack ship")
        encounter = sim.world.services["combat"].encounter_of(gunner)
        assert encounter is not None, sim.seen(gunner)
        for _ in range(400):
            if ship.db.wrecked:
                break
            await encounter.resolve_round()

        assert ship.db.wrecked == 1                      # ON_SPENT once, for the hull
        assert ship.db.hull == 0 and ship.db.shields == 0
        assert "hp" not in ship.db.all() and "max_hp" not in ship.db.all()
        assert ship.location is room                     # when_spent none
        assert not any(o.name.startswith("corpse") for o in room.contents)

        spilled = False
        for change, hull_after in landed:
            assert change.pool == "shields"
            if change.spilled is None:
                if not spilled:
                    assert hull_after == 30              # shields fall first
                continue
            spilled = True
            hull = change.spilled
            assert change.new == 0
            assert hull.pool == "hull"
            assert hull.soaked == min(2, hull.requested)  # less the armor
            assert hull.applied == min(hull.old, hull.requested - hull.soaked)
        assert spilled


# --- a harm clock ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_harm_clock_fills_and_takes_its_owner_down():
    with Simulator() as sim:
        room = sim.room("Alley")
        witness = sim.obj("witness", location=room)
        witness.db.on_death = "incr('deaths')"
        trap = sim.obj("trap", location=room)
        rue = sim.player("Rue", location=room, harm=0, max_harm=6,
                         damage_pool="harm", pools={"harm": {"direction": "up"}})

        readings = []
        for _ in range(3):
            assert witness.db.deaths is None
            await sim.eval(trap, "damage(get('Rue'), 2)")
            readings.append(rue.db.harm)

        assert readings == [2, 4, 6]
        assert witness.db.deaths == 1
        assert rue.has_tag("unconscious")
        assert "hp" not in rue.db.all()


# --- a door ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_door_is_battered_down():
    with Simulator() as sim:
        hall, vault = sim.room("Hall"), sim.room("Vault")
        door = sim.obj("vault door", location=hall, tags=["exit"],
                       destination=vault, structure=10, max_structure=10,
                       damage_pool="structure", when_spent="destroy")
        back = sim.obj("vault door", location=vault, tags=["exit"], destination=hall)
        pair_exits(door, back)
        ogre = sim.player("Ogre", location=hall)
        ram = _ability(sim, "battering ram", target="victim", effects=[
            {"type": "damage", "dice": "6", "damage_type": "crushing",
             "magical": False}])

        await invoke_ability(ogre, ram, door)
        assert door.db.structure < 10 and door.location is hall
        for _ in range(5):
            if door.location is None:
                break
            await invoke_ability(ogre, ram, door)

        assert door.location is None
        assert sim.store.get_cached(door.id) is None
        assert back.db.partner is None                   # the far side unpaired
        assert "hp" not in door.db.all()


# --- costs from an up pool --------------------------------------------------------


@pytest.mark.asyncio
async def test_guns_run_hot():
    with Simulator() as sim:
        room = sim.room("Void")
        ship = sim.obj("ship", location=room, tags=["npc"], heat=0, max_heat=6,
                       pools={"heat": {"direction": "up"}})
        rock = sim.obj("rock", location=room)
        volley = _ability(sim, "volley", target="victim",
                          cost={"pool": "heat", "n": 3}, effects=[])

        assert await invoke_ability(ship, volley, rock) is not None
        assert ship.db.heat == 3
        assert await invoke_ability(ship, volley, rock) is not None
        assert ship.db.heat == 6
        assert await invoke_ability(ship, volley, rock) is None   # blocked at max
        assert ship.db.heat == 6
        assert "hp" not in ship.db.all()


# --- unchanged play -----------------------------------------------------------------


PLAY_TESTS = ["tests/test_combat*.py", "tests/test_effect*.py",
              "tests/test_spell*.py", "tests/test_abilit*.py"]

#: Assertions about an API step 8 removed on purpose, not about play: 8.2
#: deleted the ``Combatant.hp`` setter (Decision log), so its test went.
REMOVED_WITH_API = {"assert obj.db.hp == 40"}


def test_play_tests_keep_their_hp_assertions():
    """Step 8 changed no ``hp`` assertion in the combat, effects, spells and
    abilities tests (KERNEL_PLAN 8.5). The baseline is the commit before
    step 8 (``Move files``); a removed assert line naming hp fails here."""
    root = Path(__file__).resolve().parent.parent
    try:
        base = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--grep=^Move files$"],
            cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    if not base:
        pytest.skip("baseline commit not in this history")
    diff = subprocess.run(
        ["git", "diff", "-U0", base, "--", *PLAY_TESTS],
        cwd=root, capture_output=True, text=True, check=True).stdout
    removed = [line for line in diff.splitlines()
               if line.startswith("-") and not line.startswith("---")
               and "assert" in line and "hp" in line]
    added = [line[1:].strip() for line in diff.splitlines()
             if line.startswith("+") and not line.startswith("+++")]
    # A line is unchanged in substance when the only edit is the Combatant
    # view's rename (8.2: hp/max_hp/hp_percent -> vital/vital_max/vital_percent).
    changed = [line for line in removed
               if _renamed(line[1:].strip()) not in added
               and line[1:].strip() not in REMOVED_WITH_API]
    assert changed == []


def _renamed(line: str) -> str:
    import re
    return re.sub(r"\.(max_)?hp\b(?!_)", lambda m: ".vital_max" if m.group(1) else ".vital",
                  line.replace(".hp_percent", ".vital_percent"))
