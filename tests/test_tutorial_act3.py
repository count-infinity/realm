"""
Tutorial Act III ("Saltmarsh") — every mechanic the tutorial teaches,
driven end-to-end exactly as a builder would type it: an NPC-piloted
crossing (wait/trigger action sequence with force()), a disposition-
priced shop, a pickpocket skill added as rules-data (skill_def +
reload), a zone-wide theft verb with a forced-confession consequence
chain, an enthrall spell (cast/ON_CAST/wards/expiring boost), and the
notary's prompt()-driven probate finale.

If this file is green, the tutorial's typed lines work.

One deliberate divergence: the tutorial paces its sequences with
wait(4, ...) / wait(3, ...); here the delay is 0 so the Simulator's
virtual clock (engine.tick_waits()) can drive them deterministically.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.core import wilderness
from realm.core.beats import deliver_beat
from realm.core.checks import skill_level
from realm.core.disposition import adjust_disposition, get_disposition
from realm.core.party import leader_id
from realm.testing import Simulator

W = 0   # the tutorial types 4 (and 3 for the bequest); see module docstring

# --- Part 10: the crossing (verbatim but for W) -------------------------------

CMD_PASSAGE = (
    "$passage:(say('All aboard, then. Keep your hands inboard.'), "
    "force(me, 'board'), set_attr(me, 'legs', 0), "
    f"set_attr(me, 'oar', wait({W}, 'trigger stroke'))) "
    "if credits(me) >= 10 else "
    "say('Ten for the crossing. Pay first, ride after.')"
)

STROKE = (
    "n = get_attr(me, 'legs', 0); "
    "crew = [p for p in contents(loc(me)) if has_tag(p, 'player')]; "
    "(force(me, 'row sea' if n == 0 else 'row north'), "
    "set_attr(me, 'legs', n + 1), "
    f"set_attr(me, 'oar', wait({W}, 'trigger stroke' if n < 6 else 'trigger landfall'))) "
    "if crew or n > 0 else "
    "(say('When you are settled aboard, we go.'), "
    f"set_attr(me, 'oar', wait({W}, 'trigger stroke')))"
)

LANDFALL = (
    "force(me, 'row harbor'); say('Saltmarsh Quay. Mind the step.'); "
    "force(me, 'ashore'); set_attr(me, 'legs', 0)"
)

CMD_BELAY = ("$belay:cancel_wait(get_attr(me, 'oar')); "
             "say('Belay that. We hold water.')")

# --- Part 11: the gift --------------------------------------------------------

ON_RECEIVE_GIFT = (
    "k = 'gift_' + enactor.id; "
    "(say('For me? Kind soul.'), adjust_disposition(me, enactor, 1), "
    "set_attr(me, k, 1)) if not get_attr(me, k) "
    "else say('You spoil me. Once was enough.')"
)

# --- Part 12: the cutpurse ----------------------------------------------------

CMD_PICKPOCKET = (
    "$pickpocket *:v = get(arg0); "
    "take = min(5, credits(v)) if v else 0; "
    "pemit(enactor, 'No such mark here.') if not v or loc(v) != here else "
    "((transfer_credits(v, enactor, take), "
    "pemit(enactor, 'Light fingers. You lift ' + str(take) + ' from ' + name(v) + '.')) "
    "if contest(enactor, 'pickpocket', v, 'observation') else "
    "(adjust_disposition(v, enactor, -2), "
    "force(v, 'say Stop thief! ' + name(enactor) + ' has my purse!')))"
)

LISTEN_THIEF = (
    "^Stop thief! * has my purse!:t = get(arg0); "
    "say('The stocks for you, ' + arg0 + '.'); "
    "adjust_disposition(me, t, -3); teleport_obj(t, 'The Stocks')"
)

# --- Part 13: the enthrall spell ----------------------------------------------

CMD_ENTHRALL = (
    "$enthrall *:v = get(arg0); "
    "pemit(enactor, 'No one by that name catches the light.') "
    "if not v or loc(v) != here else "
    "(pemit(enactor, 'You tilt the opal until ' + name(v) + "
    "' catches the light swimming in it.'), "
    "cast(v, 'enthrall', tags=['mind']))"
)

ON_CAST_THRALL = (
    "h = loc(enactor) if has_tag(enactor, 'charm') else enactor; "
    "(apply_effect(me, 'disposition_boost', target_id=h.id, delta=3, duration=30), "
    "force(me, 'follow ' + name(h)), say('Aye... anything you say, friend.')) "
    "if not contest(me, 'will', h, 'hypnotism') "
    "else say('You keep OUT of my head!')"
)

ON_CAST_MERCHANT = (
    "h = loc(enactor) if has_tag(enactor, 'charm') else enactor; "
    "(apply_effect(me, 'disposition_boost', target_id=h.id, delta=3, duration=30), "
    "say('Of course, dear. For you, anything.')) "
    "if not contest(me, 'will', h, 'hypnotism') "
    "else say('You keep OUT of my head!')"
)

IRON_MIND = "block('iron discipline') if has_atag('mind') else None"

CMD_RELEASE = ("$release *:force(get(arg0), 'unfollow'); "
               "pemit(enactor, 'You palm the opal dark.')")

# --- Part 14: the reading of the will ------------------------------------------

ON_RECEIVE_CHART = (
    "c = [o for o in contents(me) if 'chart' in name(o)]; "
    "(set_attr(me, 'chart_' + enactor.id, 1), "
    "say('The Gullwater chart. So she gave up her dead after all.')) "
    "if c else say('I have no use for this.')"
)

ON_PAYMENT_FEE = (
    "(set_attr(me, 'fee_' + enactor.id, 1), say('The clerks thank you.')) "
    "if credits(me) >= 25 "
    "else say('The probate fee is twenty-five. Not a penny less.')"
)

CMD_PROBATE = (
    "$probate:w = [o for o in contents(here) if has_tag(o, 'witness') "
    "and disposition(o, enactor) >= 1]; "
    "missing = 'the chart' if not get_attr(me, 'chart_' + enactor.id) else "
    "('the fee' if not get_attr(me, 'fee_' + enactor.id) else "
    "('a witness of standing' if not w else '')); "
    "prompt(enactor, 'Who claims the estate of Aldous Grey, keeper of the "
    "Gullwing light? Speak plainly, for the record.', 'on_claim') "
    "if not missing else say('The law wants ' + missing + '. The law will have it.')"
)

ON_CLAIM = (
    "say('Let the record show: ' + escape(arg0) + '.'); "
    "set_attr(me, 'claimant', enactor.id); "
    f"wait({W}, 'trigger bequest')"
)

BEQUEST = (
    "p = get('#' + get_attr(me, 'claimant')); "
    "say('To the hand that relit the Gullwing light: the tower, the island, "
    "and the sea-chest. Nine hundred, by my count.'); "
    "cmd('give deed = ' + name(p)); "
    "transfer_credits('the sea-chest', p, 900); "
    "force('the harbormaster', 'unfollow')"
)

CMD_WITNESS = (
    "$bear witness:(say('For the keeper? Aye. I will stand for that.'), "
    "force(me, 'follow ' + name(enactor))) "
    "if disposition(me, enactor) >= 1 "
    "else say('I stand witness for those I trust. You are not yet one of them.')"
)


def cell_exits_code(jetty_id: str, harbor_id: str) -> str:
    """Part 10's final provider line: compass everywhere, the jetty
    back-exit at (0,0), the wreck portal at (3,3), and the harbor
    landing at (0,6)."""
    return (
        "result = ['north', 'south', 'east', 'west']"
        f" + ([{{'name': 'jetty', 'destination': '{jetty_id}',"
        " 'aliases': ['out']}] if x == 0 and y == 0 else [])"
        " + ([{'name': 'wreck', 'attrs':"
        " {'dest_resolver': 'instance', 'instance_template': 'wreck',"
        f" 'instance_mode': 'shared', 'instance_return': '{jetty_id}'"
        "}}] if x == 3 and y == 3 else [])"
        f" + ([{{'name': 'harbor', 'destination': '{harbor_id}'}}]"
        " if x == 0 and y == 6 else [])"
    )


@pytest.fixture
def world():
    from realm.behaviors.shop import ShopkeeperBehavior
    from realm.systems import reload_rules

    sim = Simulator()
    wilderness.reset()

    # --- Acts I-II leftovers this act stands on ---
    jetty = sim.room("The Jetty")
    ferry = sim.obj("the ferry", location=jetty)
    ferry.db.set("cmd_board", "$board:move_to(enactor, me)")
    ferry.db.set("cmd_row", "$row *:move %0")
    ferry.db.set("cmd_ashore", "$ashore:move_to(enactor, loc(me))")
    gate = sim.obj("sea", location=jetty, tags=["exit"])
    gate.db.set("dest_resolver", "wilderness")
    gate.db.set("wild_region", "gullwater")
    gate.db.set("wild_x", 0)
    gate.db.set("wild_y", 0)

    # --- The town (parts 10-14), exits as @dig pairs would make them ---
    quay = sim.room("Saltmarsh Quay")
    market = sim.room("Market Square")
    tavern = sim.room("The Anchorage")
    stocks = sim.room("The Stocks")
    counting = sim.room("The Counting House")
    for room in (quay, market, tavern, stocks, counting):
        room.add_tag("zone:saltmarsh")

    def exit_(name, src, dest):
        e = sim.obj(name, location=src, tags=["exit"])
        e.db.set("destination", dest.id)
        return e

    exit_("market", quay, market)
    exit_("quay", market, quay)
    exit_("tavern", market, tavern)
    exit_("market", tavern, market)
    exit_("counting house", market, counting)
    exit_("market", counting, market)
    exit_("out", stocks, market)

    # --- The sea between (part 10's provider line) ---
    sea = sim.obj("gullwater", tags=["wilderness_region"])
    sea.db.set("is_valid", "result = 0 <= x <= 6 and 0 <= y <= 6")
    sea.db.set("cell_name", "result = 'Open Water'")
    sea.db.set("cell_desc", "result = 'Grey swells roll to the horizon.'")
    sea.db.set("cell_terrain", "result = 'water'")
    sea.db.set("cell_exits", cell_exits_code(jetty.id, quay.id))
    sea.db.set("edge_msg", "The swells grow too steep to row.")

    # --- The ferryman and his route ---
    ferryman = sim.obj("the ferryman", location=jetty, tags=["npc"])
    ferryman.db.set("cmd_passage", CMD_PASSAGE)
    ferryman.db.set("stroke", STROKE)
    ferryman.db.set("landfall", LANDFALL)
    ferryman.db.set("cmd_belay", CMD_BELAY)

    # --- The townsfolk ---
    salt = sim.obj("Mother Salt", location=market, tags=["npc"])
    salt.add_behavior(ShopkeeperBehavior(markup=1.3, buyback=0.4))
    salt.db.set("ON_RECEIVE", ON_RECEIVE_GIFT)
    salt.db.set("ON_CAST", ON_CAST_MERCHANT)
    salt.db.set("skill_will", -10)          # an open book, poor woman
    cloak = sim.obj("an oilskin cloak", location=salt)
    cloak.db.set("value", 18)
    herring = sim.obj("a smoked herring", location=salt)
    herring.db.set("value", 2)

    bramble = sim.obj("Old Bramble", location=market, tags=["npc"])
    bramble.db.set("credits", 15)
    bramble.db.set("intelligence", 3)       # observation defaults IQ-5

    watchman = sim.obj("the watchman", location=market, tags=["npc"])
    watchman.db.set("listen_thief", LISTEN_THIEF)
    watchman.db.set("on_check", IRON_MIND)

    sailor = sim.obj("the sailor", location=tavern, tags=["npc"])
    sailor.db.set("ON_CAST", ON_CAST_THRALL)
    sailor.db.set("skill_will", -10)

    harbormaster = sim.obj("the harbormaster", location=quay,
                           tags=["npc", "witness"])
    harbormaster.db.set("on_check", IRON_MIND)
    harbormaster.db.set("cmd_witness", CMD_WITNESS)

    quill = sim.obj("Master Quill", location=counting, tags=["npc"])
    quill.db.set("ON_RECEIVE", ON_RECEIVE_CHART)
    quill.db.set("on_payment", ON_PAYMENT_FEE)
    quill.db.set("cmd_probate", CMD_PROBATE)
    quill.db.set("on_claim", ON_CLAIM)
    quill.db.set("bequest", BEQUEST)
    deed = sim.obj("the keeper's deed", location=quill)
    chest = sim.obj("the sea-chest", location=quill)
    chest.db.set("credits", 900)

    # --- The underworld: a zone-wide verb on a zone master (part 12) ---
    shadows = sim.obj("the saltmarsh shadows",
                      tags=["zone_master", "zone:saltmarsh"])
    shadows.db.set("cmd_pickpocket", CMD_PICKPOCKET)

    # --- Rules as data: the act's two skill_def objects + @reload ---
    pickpocket = sim.obj("pickpocket", tags=["skill_def"])
    pickpocket.db.set("stat", "dexterity")
    pickpocket.db.set("penalty", -5)
    hypnotism = sim.obj("hypnotism", tags=["skill_def"])
    hypnotism.db.set("stat", "intelligence")
    hypnotism.db.set("penalty", -6)
    reload_rules()

    # --- The player: the builder herself, as in the tutorial ---
    alice = sim.player("Alice", location=jetty)
    alice.db.set("credits", 100)
    alice.db.set("dexterity", 13)
    alice.db.set("intelligence", 12)
    alice.db.set("character_points", 20)
    alice.db.set("skill_hypnotism", 16)
    # Everything above was built by her — scripts wield her authority,
    # exactly as the tutorial's superuser-built world does.
    for obj in sim.store.all_cached():
        if obj is not alice and not obj.has_tag("player"):
            obj.owner = alice

    # The pendant, bought and enchanted (part 13).
    pendant = sim.obj("a milk-opal pendant", location=alice, tags=["charm"])
    pendant.db.set("value", 60)
    pendant.db.set("cmd_enthrall", CMD_ENTHRALL)
    pendant.db.set("cmd_release", CMD_RELEASE)
    pendant.owner = alice

    # A second, unowned player — the would-be victim of part 12's aside.
    bob = sim.player("Bob", location=market)
    bob.db.set("credits", 50)

    # prompt() finds sessions through the engine's session manager.
    sim.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: [sim.session(alice), sim.session(bob)])

    try:
        yield SimpleNamespace(
            sim=sim, store=sim.store, engine=sim.engine, jetty=jetty,
            quay=quay, market=market, tavern=tavern, stocks=stocks,
            counting=counting, ferry=ferry, ferryman=ferryman, salt=salt,
            cloak=cloak, herring=herring, bramble=bramble, watchman=watchman,
            sailor=sailor, harbormaster=harbormaster, quill=quill, deed=deed,
            chest=chest, shadows=shadows, alice=alice, bob=bob,
            pendant=pendant)
    finally:
        wilderness.reset()
        sim.close()


async def pump(w, times: int = 12) -> None:
    """Advance the virtual clock: fire due waits, repeatedly (each step
    of a sequence schedules the next)."""
    for _ in range(times):
        await w.engine.tick_waits()


def credits_of(obj) -> int:
    return int(obj.db.get("credits") or 0)


def shop_of(npc):
    return next(b for b in npc.get_behaviors()
                if b.behavior_id == "shopkeeper")


@pytest.mark.asyncio
class TestTheCrossing:

    async def test_no_fare_no_ride(self, world):
        w = world
        await w.sim.do(w.alice, "passage")
        assert w.ferryman.location is w.jetty       # never boarded
        assert any("Pay first" in m for m in w.sim.seen(w.alice))

    async def test_the_ferryman_rows_you_to_town(self, world):
        """One paid fare, one typed word, and an NPC drives a vehicle
        across procedural ocean on a wait/trigger chain."""
        w = world
        await w.sim.do(w.alice, "pay 10 to the ferryman")
        assert credits_of(w.ferryman) == 10
        await w.sim.do(w.alice, "passage")
        assert w.ferryman.location is w.ferry       # force(me, 'board')
        await w.sim.do(w.alice, "board")

        await pump(w)

        assert w.ferry.location is w.quay           # landfall
        assert w.alice.location is w.ferry          # rode the whole way
        assert w.ferryman.location is w.quay        # stepped ashore
        assert any("Mind the step" in m for m in w.sim.seen(w.alice))
        await w.sim.do(w.alice, "ashore")
        assert w.alice.location is w.quay

    async def test_the_ferryman_waits_for_his_crew(self, world):
        """The first stroke polls: no passenger aboard, no departure."""
        w = world
        await w.sim.do(w.alice, "pay 10 to the ferryman")
        await w.sim.do(w.alice, "passage")
        await pump(w, 3)
        assert w.ferry.location is w.jetty          # still docked

        await w.sim.do(w.alice, "board")
        await pump(w)
        assert w.ferry.location is w.quay

    async def test_belay_cancels_the_voyage(self, world):
        """wait() hands back a handle; cancel_wait stops the sequence —
        and the oars still answer to whoever is aboard."""
        w = world
        await w.sim.do(w.alice, "pay 10 to the ferryman")
        await w.sim.do(w.alice, "passage")
        await w.sim.do(w.alice, "board")
        await w.engine.tick_waits()                 # one stroke: out the gate
        cell = w.ferry.location
        assert cell.has_tag("wildcell:gullwater:0,0")

        await w.sim.do(w.alice, "belay")
        await pump(w, 4)
        assert w.ferry.location is cell             # becalmed

        await w.sim.do(w.alice, "row north")        # take the oars yourself
        assert w.ferry.location.has_tag("wildcell:gullwater:0,1")


@pytest.mark.asyncio
class TestMarketDay:

    async def test_prices_track_disposition(self, world):
        """value x markup, bent 5% per disposition point, capped at 15%."""
        w = world
        shop = shop_of(w.salt)
        assert shop.price_to_buy(w.salt, w.cloak, w.alice) == 23   # 18 x 1.3

        adjust_disposition(w.salt, w.alice, 3)
        assert shop.price_to_buy(w.salt, w.cloak, w.alice) == 20   # -15%
        adjust_disposition(w.salt, w.alice, 2)
        assert shop.price_to_buy(w.salt, w.cloak, w.alice) == 20   # capped

    async def test_one_honest_pitch_per_person(self, world):
        w = world
        w.alice.location = w.market
        await w.sim.do(w.alice, "persuade mother salt")
        await w.sim.do(w.alice, "persuade mother salt")
        assert any("Give it a rest" in m for m in w.sim.seen(w.alice))

    async def test_the_gift_works_once(self, world):
        """ON_RECEIVE + the part-4 caching trick: generosity pays once."""
        w = world
        w.alice.location = w.market
        await w.sim.do(w.alice, "buy smoked herring")
        assert w.herring.location is w.alice
        assert credits_of(w.alice) == 97                     # round(2 x 1.3)

        await w.sim.do(w.alice, "give smoked herring to mother salt")
        assert get_disposition(w.salt, w.alice) == 1

        trinket = w.sim.obj("a pebble", location=w.alice)
        trinket.owner = w.alice
        await w.sim.do(w.alice, "give pebble to mother salt")
        assert get_disposition(w.salt, w.alice) == 1         # cached
        assert any("You spoil me" in m for m in w.sim.seen(w.alice))


@pytest.mark.asyncio
class TestTheCutpurse:

    async def test_pickpocket_is_rules_data(self, world):
        """A skill_def object + reload extends the ruleset: untrained
        pickpocket now defaults off dexterity, like the built-ins."""
        w = world
        assert skill_level(w.alice, "pickpocket") == 8       # DX 13 - 5
        assert skill_level(w.alice, "cartwheeling") == 5     # not a skill

    async def test_improve_spends_points_on_the_new_skill(self, world):
        w = world
        await w.sim.do(w.alice, "improve pickpocket")
        assert int(w.alice.db.get("skill_pickpocket")) == 9
        assert int(w.alice.db.get("character_points")) == 16

    async def test_a_won_contest_moves_real_money(self, world):
        w = world
        w.alice.location = w.market
        w.alice.db.set("skill_pickpocket", 20)
        # 17-18 is a GURPS auto-fail, so allow the deck a reshuffle.
        for _ in range(5):
            await w.sim.do(w.alice, "pickpocket old bramble")
            if credits_of(w.alice) > 100:
                break
            w.alice.location = w.market      # a fumble may have consequences
        assert credits_of(w.alice) == 105
        assert credits_of(w.bramble) == 10

    async def test_failure_summons_the_law(self, world):
        """The consequence chain: forced confession -> overheard by the
        watchman -> name captured -> grudge -> the stocks."""
        w = world
        w.alice.location = w.market
        w.alice.db.set("skill_pickpocket", -10)
        w.bramble.db.set("skill_observation", 20)
        for _ in range(3):
            await w.sim.do(w.alice, "pickpocket old bramble")
            if w.alice.location is w.stocks:
                break
        assert w.alice.location is w.stocks
        assert get_disposition(w.watchman, w.alice) == -3
        assert get_disposition(w.bramble, w.alice) <= -2

        await w.sim.do(w.alice, "out")                       # walk of shame
        assert w.alice.location is w.market

    async def test_scoped_to_the_room(self, world):
        """The loc(v) != here guard: no rifling pockets across town."""
        w = world
        w.alice.location = w.tavern                # Bramble is in the market
        w.alice.db.set("skill_pickpocket", 20)
        await w.sim.do(w.alice, "pickpocket old bramble")
        assert credits_of(w.bramble) == 15
        assert any("No such mark here" in m for m in w.sim.seen(w.alice))

    async def test_players_are_safe_from_builder_crime(self, world):
        """Alice's verb wields Alice's authority — and a plain player
        doesn't control other players, so Bob keeps his purse and is
        never forced to shout."""
        w = world
        w.alice.location = w.market
        w.alice.db.set("skill_pickpocket", 20)
        for _ in range(3):
            await w.sim.do(w.alice, "pickpocket Bob")
        assert credits_of(w.bob) == 50
        assert credits_of(w.alice) == 100
        assert w.alice.location is w.market        # no shout, no stocks


@pytest.mark.asyncio
class TestTheEnthrallSpell:

    async def test_a_lost_contest_makes_a_thrall(self, world):
        """cast() -> the victim's own ON_CAST rolls will vs hypnotism,
        follows the charm to the hand that holds it, and surrenders:
        an expiring +3 and a follow. Release is a command away."""
        w = world
        w.alice.location = w.tavern
        for _ in range(3):                          # crit edges only
            await w.sim.do(w.alice, "enthrall the sailor")
            if leader_id(w.sailor):
                break
        assert leader_id(w.sailor) == w.alice.id    # follows HER, not the opal
        assert get_disposition(w.sailor, w.alice) == 3
        assert any("anything you say" in m for m in w.sim.seen(w.alice))

        # The glaze lifts: the boost reverses itself...
        for _ in range(40):
            await deliver_beat(w.sailor)
            if get_disposition(w.sailor, w.alice) == 0:
                break
        assert get_disposition(w.sailor, w.alice) == 0
        assert leader_id(w.sailor) == w.alice.id    # ...but he still follows

        await w.sim.do(w.alice, "release the sailor")
        assert leader_id(w.sailor) is None

    async def test_enthralled_prices(self, world):
        """The boost is the same disposition the shop reads."""
        w = world
        w.alice.location = w.market
        shop = shop_of(w.salt)
        assert shop.price_to_buy(w.salt, w.cloak, w.alice) == 23
        for _ in range(3):
            await w.sim.do(w.alice, "enthrall mother salt")
            if get_disposition(w.salt, w.alice) == 3:
                break
        assert shop.price_to_buy(w.salt, w.cloak, w.alice) == 20

    async def test_the_iron_mind_blocks_the_event(self, world):
        """A ward (on_check + block) vetoes the cast in the permission
        pass: no reaction fires anywhere — the ON_CAST canary stays
        silent, and so do the bystanders'."""
        w = world
        w.alice.location = w.market
        w.watchman.db.set("ON_CAST", "say('caught in the opal light')")
        await w.sim.do(w.alice, "enthrall the watchman")
        assert not any("caught in the opal" in m for m in w.sim.seen(w.alice))
        assert get_disposition(w.watchman, w.alice) == 0
        assert get_disposition(w.salt, w.alice) == 0         # blocked for all


@pytest.mark.asyncio
class TestTheReadingOfTheWill:

    async def test_the_probate_end_to_end(self, world):
        """Multi-condition gates, an errand with a follower, a prompt
        answered in your own words, and the bequest sequence."""
        w = world
        w.alice.location = w.counting

        # Gate 1: the chart. A wrong gift is refused the flag...
        await w.sim.do(w.alice, "probate")
        assert any("the chart" in m for m in w.sim.seen(w.alice))
        bauble = w.sim.obj("a brass button", location=w.alice)
        bauble.owner = w.alice
        await w.sim.do(w.alice, "give brass button to Master Quill")
        assert any("no use for this" in m for m in w.sim.seen(w.alice))
        assert not w.quill.db.get(f"chart_{w.alice.id}")

        # ...the chart is not.
        chart = w.sim.obj("the keeper's chart", location=w.alice)
        chart.owner = w.alice
        await w.sim.do(w.alice, "give the keeper's chart to Master Quill")
        assert chart.location is w.quill
        assert w.quill.db.get(f"chart_{w.alice.id}")

        # Gate 2: the fee.
        await w.sim.do(w.alice, "probate")
        assert any("the fee" in m for m in w.sim.seen(w.alice))
        await w.sim.do(w.alice, "pay 25 to master quill")
        assert w.quill.db.get(f"fee_{w.alice.id}")

        # Gate 3: a witness of standing — won honestly, walked over.
        await w.sim.do(w.alice, "probate")
        assert any("a witness of standing" in m for m in w.sim.seen(w.alice))
        w.alice.location = w.quay
        await w.sim.do(w.alice, "bear witness")
        assert leader_id(w.harbormaster) is None    # trusts nobody yet
        adjust_disposition(w.harbormaster, w.alice, 1)   # a won persuade
        await w.sim.do(w.alice, "bear witness")
        assert leader_id(w.harbormaster) == w.alice.id
        await w.sim.do(w.alice, "market")
        await w.sim.do(w.alice, "counting house")
        assert w.harbormaster.location is w.counting     # followed her in

        # The reading: prompt() captures her next line as the answer.
        await w.sim.do(w.alice, "probate")
        sess = w.sim.session(w.alice)
        assert sess.input_handler is not None
        assert any("Who claims the estate" in m for m in w.sim.seen(w.alice))
        await sess.input_handler(sess, "Keeper of the Gullwing")
        await pump(w, 3)                                 # the bequest fires

        seen = w.sim.seen(w.alice)
        assert any("Keeper of the Gullwing" in m for m in seen)
        assert w.deed.location is w.alice                # the island is hers
        assert credits_of(w.alice) == 975                # 100 - 25 + 900
        assert credits_of(w.chest) == 0
        assert leader_id(w.harbormaster) is None         # dismissed

    async def test_the_iron_witness_cannot_be_charmed(self, world):
        """Part 14's shortcut check: the harbormaster is warded, so the
        pendant is no substitute for persuasion."""
        w = world
        w.alice.location = w.quay
        await w.sim.do(w.alice, "enthrall the harbormaster")
        assert get_disposition(w.harbormaster, w.alice) == 0
        await w.sim.do(w.alice, "bear witness")
        assert leader_id(w.harbormaster) is None
