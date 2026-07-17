"""
Living NPCs arc (showcase items 60, 64, 67, 68, 71).

Drives every "Build it" command line from the five tutorials
(docs/showcase/060_wandering_npc.md .. 071_guard_response.md) through a
real in-process world — Simulator wires the actual dispatcher, script
engine, and propagation engine — then verifies each tutorial's "Try it"
behavior: raw input in, session output out.

Determinism: behavior ticks are pumped by calling the attached
behaviors' tick() directly (no wall-clock heartbeat); item 71 combat
uses a diceless GURPS ruleset (3d6 always 10, damage flat 2) and
resolve_round() fired by hand.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.testing import Simulator

# --- The tutorials' Build-it transcripts, verbatim -------------------------

BUILD_060 = [
    "@dig The Square = square, back",
    "square",
    "@zone here = town",
    "@dig Lamplight Lane = lane, square",
    "@dig The Gates = gates, square",
    "lane",
    "@zone here = town",
    "@dig Back Alley = alley, lane",
    "alley",
    "@zone here = town",
    "@tag here = no_wander",
    "lane",
    "square",
    "@create scamp",
    "@desc scamp = A scruffy kid, all elbows and pockets.",
    "@tag scamp = npc",
    "drop scamp",
    "@behavior scamp = wandering, pause:2, wander_chance:0.5",
]

BUILD_064 = [
    "@dig The Rusty Flagon = flagon, square",
    "flagon",
    "@zone here = town",
    "@create Mira",
    "@tag Mira = npc",
    "drop Mira",
    "@desc Mira = The Flagon's keeper. She polishes a mug and misses nothing.",
    "@set Mira/listen_tap = ^*on tap*:say Ale, five credits the mug. "
    "Pay me and it is yours.",
    "@set Mira/on_payment = paid = credits(me) - V('till', 0); "
    "((set_attr(me, 'till', credits(me)), "
    "set_attr(me, 'patron_' + enactor.id, 1), "
    "say('One ale, coming up.'), trigger('pour')) if paid >= 5 else "
    "(say('Ale is five credits, love.') if paid > 0 else None))",
    "@set Mira/pour = mug = create_obj('a mug of ale', location=here); "
    "set_attr(mug, 'description', 'Cloudy town ale, still foaming.'); "
    "set_attr(mug, 'cmd_drink', V('drink_script')); "
    "pose('sets a foaming mug on the bar.')",
    "@set Mira/drink_script = $drink *:heal(enactor, 1); "
    "pemit(enactor, 'The ale goes down warm.'); "
    "oemit(enactor, f'{name(enactor)} drains a mug of ale.'); "
    "destroy_obj(me)",
    '@set Mira/rumors = ["They say the old mine did not close for bad air '
    'alone.", "Verity shuts her shop at nine sharp - and sleeps above it.", '
    '"Scream on Market Street and count to ten. The watch is faster."]',
    "@set Mira/listen_rumor = ^*rumor*:r = V('rumors', []); "
    "i = V('idx_' + enactor.id, 0); "
    "((say(r[i % len(r)]), incr('idx_' + enactor.id)) "
    "if V('patron_' + enactor.id, 0) else "
    "say('Ale first. A wet tongue wags easier - mine included.'))",
]

BUILD_067 = [
    "@create Old Moss",
    "@tag Old Moss = npc",
    "drop Old Moss",
    "@desc Old Moss = He has the corner table and a stare that has seen "
    "the bottom of many mugs.",
    "@set Old Moss/menu = t = V('town_' + enactor.id, 0); "
    "m = V('mine_' + enactor.id, 0); "
    "d = V('drink_' + enactor.id, 0); "
    "s = V('secret_' + enactor.id, 0); "
    "result = '[1] Ask about the town.' "
    "+ (' [2] Ask about the old mine.' if t else '') "
    "+ (' [3] Press him about the collapse.' if m and d and not s else '') "
    "+ ' [q] Leave him be.'",
    "@set Old Moss/cmd_talk = $talk:met = V('met_' + enactor.id, 0); "
    "set_attr(me, 'met_' + enactor.id, 1); "
    "say('New face. Name is Moss. Sit, if you like.' if not met else "
    "f'Back again, {name(enactor)}. Thought so.'); "
    "prompt(enactor, eval_attr(me, 'menu'), 'node_root')",
    "@set Old Moss/node_root = a = trim(arg0); "
    "t = V('town_' + enactor.id, 0); "
    "m = V('mine_' + enactor.id, 0); "
    "d = V('drink_' + enactor.id, 0); "
    "s = V('secret_' + enactor.id, 0); "
    "((set_attr(me, 'town_' + enactor.id, 1), "
    "say('Quiet town. Was not always - the mine kept it loud, before the "
    "collapse.'), prompt(enactor, eval_attr(me, 'menu'), 'node_root')) "
    "if a == '1' else "
    "(set_attr(me, 'mine_' + enactor.id, 1), "
    "say('Closed ten years back. An accident, they ruled.' + ('' if d else "
    "' Dry work, remembering. Pay 5 to Old Moss and it might come back "
    "to me.')), prompt(enactor, eval_attr(me, 'menu'), 'node_root')) "
    "if a == '2' and t else "
    "(set_attr(me, 'secret_' + enactor.id, 1), "
    "pemit(enactor, 'Moss leans close: it was no accident. He hauled the "
    "charges down himself, on watch-house coin. Then he says no more.')) "
    "if a == '3' and m and d and not s else "
    "say('Moss waves you off and studies his mug.'))",
    "@set Old Moss/on_payment = paid = credits(me) - V('tab', 0); "
    "((set_attr(me, 'tab', credits(me)), "
    "set_attr(me, 'drink_' + enactor.id, 1), "
    "pose('drinks deep and wipes his beard.')) if paid >= 5 else "
    "(say('That will not wet a flea.') if paid > 0 else None))",
]

BUILD_068 = [
    "@dig Market Street = market, square",
    "market",
    "@zone here = town",
    "@dig The Loft = upstairs, downstairs",
    "@create town clock",
    "drop town clock",
    "@set town clock/hour = 6",
    "@set town clock/on_tick = set_attr(me, 'hour', "
    "(V('hour', 0) + 1) % 24)",
    "@behavior town clock = script_ticker, interval:1",
    "@create Verity",
    "@tag Verity = npc",
    "drop Verity",
    "@set Verity/on_tick = h = get_attr('town clock', 'hour', 12); "
    "trigger('open_up' if 9 <= h < 21 else 'close_down')",
    "@set Verity/open_up = (move('downstairs') if name(here) != "
    "'Market Street' else (None if 'shopkeeper' in behaviors(me) else "
    "(attach_behavior(me, 'shopkeeper', markup=1.2), "
    "say('Shutters up! Fresh goods at fair prices!'))))",
    "@set Verity/close_down = ((detach_behavior(me, 'shopkeeper'), "
    "say('Closing up. Come back at nine.')) if 'shopkeeper' in "
    "behaviors(me) else (move('upstairs') if name(here) != 'The Loft' "
    "else None))",
    "@behavior Verity = script_ticker, interval:1",
    "@create ration pack",
    "@set ration pack/value = 8",
    "give ration pack to Verity",
]

BUILD_071 = [
    "@dig Guard Post = post, square",
    "post",
    "@zone here = town",
    "@create Watchman Bren",
    "@tag Watchman Bren = npc",
    "@tag Watchman Bren = town_watch",
    "@set Watchman Bren/hp = 14",
    "@set Watchman Bren/max_hp = 14",
    "@set Watchman Bren/skill_melee = 13",
    "drop Watchman Bren",
    "@create Town Watch",
    "@zone/master Town Watch = town",
    "@set Town Watch/on_attack = crime = not has_tag(enactor, 'town_watch'); "
    "fresh = now() - V('last_alarm', 0) > 60; "
    "((set_attr(me, 'last_alarm', now()), "
    "adjust_disposition('Watchman Bren', enactor, -5), "
    "teleport_obj('Watchman Bren', here), "
    "force('Watchman Bren', 'say Town watch! Drop it, NOW!'), "
    "force('Watchman Bren', 'attack ' + name(enactor))) "
    "if crime and fresh else None)",
    "drop Town Watch",
    "square",
    "market",
    "@create dock worker",
    "@tag dock worker = npc",
    "@set dock worker/hp = 10",
    "@set dock worker/max_hp = 10",
    "@set dock worker/skill_melee = 10",
    "@set dock worker/combat_default = defend",
    "drop dock worker",
    "@create Nettie",
    "@tag Nettie = npc",
    "drop Nettie",
    "@set Nettie/on_attack = say Guards! GUARDS! Blood on Market Street!",
]

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
    # Street one step from where 71 starts.
    await run(BUILD_060)
    await run(BUILD_064)
    await run(BUILD_067)
    await run(["square"])
    await run(BUILD_068)
    await run(["square"])
    await run(BUILD_071)
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
        assert mira.db.get("till") == 5

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
