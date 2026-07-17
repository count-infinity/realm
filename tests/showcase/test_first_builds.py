"""
Showcase arc "First builds" — checklist items 5, 1, 2, 14, 25.

Verifies the tutorials in docs/showcase/ (005_magic_8ball.md,
001_slot_machine.md, 002_vending_machine.md, 014_basic_container.md,
025_lockable_door.md) by driving a real in-process world — the
realm.testing.Simulator wires the same store/propagation/scripting/
dispatcher stack a live GameServer does — with the tutorials' EXACT
command lines (raw input in, session output out).

The build transcripts below are copied verbatim from the docs' "Build
it" sections; if a tutorial changes, change it here too. Randomness is
pinned by patching random.randint (the one source both rand() and
dice() draw from), the same trick the infiltration tests use with the
check resolver.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from realm.core.economy import get_credits
from realm.testing import Simulator

# Output that must never appear while running a "Build it" transcript —
# catches typos, permission problems, and validation failures in any
# tutorial line.
BUILD_FAILURE_MARKERS = (
    "Unknown command",
    "Permission denied",
    "Usage:",
    "not found",
    "Script error",
    "Eval error",
    "error",
)


@pytest.fixture
def sim():
    s = Simulator()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def pinned_rand(monkeypatch):
    """Pin rand(): random.randint returns holder['value'] clamped to range."""
    holder = {"value": 1}

    def fake_randint(low, high):
        return max(low, min(holder["value"], high))

    monkeypatch.setattr(
        "realm.scripting.functions.random.randint", fake_randint)
    return holder


def workshop_and_builder(sim):
    """The standing start of every tutorial: a room and a builder in it."""
    room = sim.room("The Workshop")
    bilda = sim.player("Bilda", location=room)
    bilda.add_tag("builder")
    return room, bilda


async def build(sim, player, lines):
    """Run a Build-it transcript; fail loudly if any line misfires."""
    for line in lines:
        await sim.do(player, line)
        out = "\n".join(sim.seen(player))
        for marker in BUILD_FAILURE_MARKERS:
            assert marker not in out, f"build line {line!r} failed: {out!r}"


async def do(sim, player, line):
    """Run one command and return everything the player saw."""
    await sim.do(player, line)
    return sim.seen(player)


def find_one(sim, name):
    matches = sim.store.find_cached(name=name)
    assert matches, f"no object named {name!r} in the world"
    return matches[0]


# =========================================================================
# 005. Magic 8-ball — docs/showcase/005_magic_8ball.md
# =========================================================================

EIGHTBALL_BUILD = [
    "@create oracle ball",
    "drop oracle ball",
    "@desc oracle ball = A matte-black sphere the size of a fist. A small "
    "window on one side swims with dark fluid. It looks like it wants to "
    "be shaken.",
    "@set oracle ball/cmd_shake = $shake: say(switch(rand(1, 8), "
    "1, 'It is certain.', 2, 'Signs point to yes.', 3, 'Ask again later.', "
    "4, 'The stars are silent on this one.', 5, 'Outlook grim.', "
    "6, 'Very doubtful.', 7, 'Yes - but not the way you hope.', "
    "'The fluid clouds. No answer comes.'))",
]

EIGHTBALL_RETHEME = [
    '@set oracle ball/answers = ["Yes.", "No.", "The dice are still '
    'rolling."]',
    "@set oracle ball/cmd_shake = $shake: a = V('answers'); "
    "pose(f\"trembles in {name(enactor)}'s grip.\"); "
    "say(a[rand(0, len(a) - 1)])",
]


class TestMagic8Ball:

    async def test_shake_answers_from_the_switch_table(self, sim, pinned_rand):
        room, bilda = workshop_and_builder(sim)
        kess = sim.player("Kess", location=room)
        await build(sim, bilda, EIGHTBALL_BUILD)
        sim.seen(kess)  # discard build chatter

        pinned_rand["value"] = 3
        out = await do(sim, bilda, "shake")
        assert 'oracle ball says, "Ask again later."' in out
        # Bystanders hear the oracle too — the ball speaks to the room.
        assert 'oracle ball says, "Ask again later."' in sim.seen(kess)

    async def test_shake_falls_through_to_the_default_answer(
            self, sim, pinned_rand):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, EIGHTBALL_BUILD)

        pinned_rand["value"] = 8  # no case 8 in the table -> default
        out = await do(sim, bilda, "shake")
        assert 'oracle ball says, "The fluid clouds. No answer comes."' in out

    async def test_retheme_reads_the_answers_attribute(self, sim, pinned_rand):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, EIGHTBALL_BUILD)
        await build(sim, bilda, EIGHTBALL_RETHEME)

        pinned_rand["value"] = 2  # index 2 of the 3-answer list
        out = await do(sim, bilda, "shake")
        assert "oracle ball trembles in Bilda's grip." in out
        assert 'oracle ball says, "The dice are still rolling."' in out

    async def test_shake_only_works_near_the_ball(self, sim):
        room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, EIGHTBALL_BUILD)
        elsewhere = sim.room("Elsewhere")
        remote = sim.player("Remy", location=elsewhere)
        out = await do(sim, remote, "shake")
        # Not in the search path (room contents/room/inventory/zone), so
        # the trigger never fires (a live server answers "Huh?").
        assert not any("oracle ball says" in line for line in out)


# =========================================================================
# 001. Slot machine — docs/showcase/001_slot_machine.md
# =========================================================================

SLOT_BUILD = [
    "@create slot machine",
    "drop slot machine",
    "@desc slot machine = A one-armed bandit in scuffed chrome, three "
    "reels asleep behind smeared glass. [[result = f'The hopper holds "
    "{credits(me)} credits.']]",
    "@set slot machine/cost = 10",
    "@set slot machine/on_payment = cost = V('cost', 10); "
    "paid = credits(me) - V('ledger', 0); "
    "k = 'stake_' + enactor.id; "
    "(incr(k), "
    "transfer_credits(me, enactor, paid - cost), "
    "pemit(enactor, 'Clunk. The lever unlocks: type pull.')) "
    "if paid >= cost else "
    "(transfer_credits(me, enactor, paid), "
    "pemit(enactor, f'A pull costs {cost} credits. Coins "
    "returned.')); "
    "set_attr(me, 'ledger', credits(me))",
    "@set slot machine/cmd_pull = $pull: k = 'stake_' + enactor.id; "
    "staked = V(k, 0); "
    "pemit(enactor, 'The lever will not budge. Stake a pull first: "
    "pay 10 to slot machine.') if not staked else None; "
    "roll = rand(1, 100); "
    "tier = 1 if roll <= 1 else (2 if roll <= 5 else (3 if roll <= 15 "
    "else (4 if roll <= 35 else 5))); "
    "prize = switch(tier, 1, 250, 2, 50, 3, 20, 4, 10, 0); "
    "reels = switch(tier, 1, '[ NOVA : NOVA : NOVA ]', "
    "2, '[ BELL : BELL : BELL ]', 3, '[ STAR : STAR : ---- ]', "
    "4, '[ STAR : ---- : ---- ]', '[ ---- : ---- : ---- ]'); "
    "(decr(k), "
    "oemit(enactor, f'{name(enactor)} pulls the lever. The reels "
    "clatter.'), "
    "pemit(enactor, reels), "
    "(transfer_credits(me, enactor, prize), "
    "pemit(enactor, f'Payout! {prize} credits rattle into the "
    "tray.')) if prize else "
    "pemit(enactor, 'The reels settle on nothing. The house smiles.'), "
    "set_attr(me, 'ledger', credits(me))) if staked else None",
    "@eval m = get('slot machine'); adjust_credits(m, 500); "
    "set_attr(m, 'ledger', credits(m)); result = credits(m)",
]

# The payout table as documented: weight -> prize on a 10-credit stake.
SLOT_TABLE = {250: 1, 50: 4, 20: 10, 10: 20, 0: 65}


class TestSlotMachine:

    async def test_documented_house_edge_is_a_real_house_edge(self):
        """Expected return must stay under the 10-credit stake."""
        total_weight = sum(SLOT_TABLE.values())
        assert total_weight == 100
        expected = sum(p * w for p, w in SLOT_TABLE.items()) / total_weight
        assert expected == 8.5  # 85% return — the documented 15% edge
        assert expected < 10

    async def test_full_session_stake_jackpot_refund_and_bust(
            self, sim, pinned_rand):
        room, bilda = workshop_and_builder(sim)
        kess = sim.player("Kess", location=room)
        await build(sim, bilda, SLOT_BUILD)
        machine = find_one(sim, "slot machine")
        assert get_credits(machine) == 500  # the float

        # Pocket money for the player (tutorial line).
        await build(sim, bilda, ["@eval adjust_credits(me, 120); "
                                 "result = credits(me)"])
        out = await do(sim, bilda, "credits")
        assert "You are carrying 120 credits." in out

        # Pull without staking: refused, nothing moves.
        out = await do(sim, bilda, "pull")
        assert ("The lever will not budge. Stake a pull first: "
                "pay 10 to slot machine." in out)
        assert get_credits(bilda) == 120

        # Stake and hit the jackpot (roll pinned to 1).
        out = await do(sim, bilda, "pay 10 to slot machine")
        assert "Clunk. The lever unlocks: type pull." in out
        assert get_credits(bilda) == 110
        assert get_credits(machine) == 510

        sim.seen(kess)
        pinned_rand["value"] = 1
        out = await do(sim, bilda, "pull")
        assert "[ NOVA : NOVA : NOVA ]" in out
        assert "Payout! 250 credits rattle into the tray." in out
        assert get_credits(bilda) == 360
        assert get_credits(machine) == 260
        # The room watches you play (oemit excludes the actor).
        kess_saw = sim.seen(kess)
        assert "Bilda pulls the lever. The reels clatter." in kess_saw

        # Underpaying is refunded in full.
        out = await do(sim, bilda, "pay 3 to slot machine")
        assert "A pull costs 10 credits. Coins returned." in out
        assert get_credits(bilda) == 360
        assert get_credits(machine) == 260

        # Stake again and bust (roll pinned to 100).
        await do(sim, bilda, "pay 10 to slot machine")
        pinned_rand["value"] = 100
        out = await do(sim, bilda, "pull")
        assert "[ ---- : ---- : ---- ]" in out
        assert "The reels settle on nothing. The house smiles." in out
        assert get_credits(bilda) == 350
        assert get_credits(machine) == 270

        # The living description reads the hopper.
        out = await do(sim, bilda, "look slot machine")
        assert any("The hopper holds 270 credits." in line for line in out)

    async def test_stake_is_consumed_one_pull_per_payment(
            self, sim, pinned_rand):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, SLOT_BUILD)
        await build(sim, bilda, ["@eval adjust_credits(me, 120); "
                                 "result = credits(me)"])
        await do(sim, bilda, "pay 10 to slot machine")
        pinned_rand["value"] = 100
        await do(sim, bilda, "pull")
        out = await do(sim, bilda, "pull")   # second pull: stake is spent
        assert ("The lever will not budge. Stake a pull first: "
                "pay 10 to slot machine." in out)


# =========================================================================
# 002. Vending machine — docs/showcase/002_vending_machine.md
# =========================================================================

VENDING_BUILD = [
    "@create vending machine",
    "drop vending machine",
    "@desc vending machine = A humming slab of scratched enamel and "
    "glass. Goods sleep in their spiral coils. [[result = f'The display "
    "reads CREDIT: {V(\"credit_\" + viewer.id, 0)}.']]",
    '@set vending machine/menu = ["coffee", "ration"]',
    '@set vending machine/item_coffee = {"name": "bulb of cold coffee", '
    '"price": 25, "weight": 1}',
    '@set vending machine/item_ration = {"name": "vacuum-sealed ration", '
    '"price": 40, "weight": 2}',
    "@set vending machine/stock_coffee = 5",
    "@set vending machine/stock_ration = 2",
    "@set vending machine/on_payment = paid = credits(me) - "
    "V('ledger', 0); set_attr(me, 'ledger', credits(me)); "
    "k = 'credit_' + enactor.id; bal = incr(k, paid); "
    "pemit(enactor, f'The display blinks. CREDIT: {bal}. "
    "Type vend <selection>.')",
    "@set vending machine/cmd_browse = $browse: menu = V("
    "'menu', []); pemit(enactor, 'Selections (pay first, then vend "
    "<selection>):'); [pemit(enactor, f'  {sel} - "
    "{V(\"item_\" + sel)[\"price\"]} cr - "
    "{V(\"item_\" + sel)[\"name\"]} "
    "({V(\"stock_\" + sel, 0)} left)') for sel in menu]",
    "@set vending machine/cmd_vend = $vend *: sel = trim(arg0).lower(); "
    "item = V('item_' + sel); k = 'credit_' + enactor.id; "
    "bal = V(k, 0); left = V('stock_' + sel, 0); "
    "price = item['price'] if item else 0; "
    "ok = bool(item) and left > 0 and bal >= price; "
    "pemit(enactor, 'The panel blinks: NO SUCH SELECTION. Try browse.') "
    "if not item else None; "
    "pemit(enactor, f'The {sel} coil is empty. SOLD OUT.') "
    "if item and left < 1 else None; "
    "pemit(enactor, f'CREDIT {bal} of {price}. "
    "Feed it: pay {price - bal} to vending machine.') "
    "if item and left > 0 and bal < price else None; "
    "(decr(k, price), decr('stock_' + sel), "
    "set_attr(create_obj(item['name']), 'weight', "
    "item['weight']), remit(here, f'The vending machine whirs and drops "
    "a {item[\"name\"]} into the tray.')) if ok else None",
]


class TestVendingMachine:

    async def test_browse_lists_prices_and_stock(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, VENDING_BUILD)
        out = await do(sim, bilda, "browse")
        joined = "\n".join(out)
        assert "Selections (pay first, then vend <selection>):" in joined
        assert "coffee - 25 cr - bulb of cold coffee (5 left)" in joined
        assert "ration - 40 cr - vacuum-sealed ration (2 left)" in joined

    async def test_pay_then_vend_dispenses_a_spawned_item(self, sim):
        room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, VENDING_BUILD)
        await build(sim, bilda, ["@eval adjust_credits(me, 200); "
                                 "result = credits(me)"])

        # No credit yet: told exactly what to feed it.
        out = await do(sim, bilda, "vend coffee")
        assert ("CREDIT 0 of 25. Feed it: pay 25 to vending machine."
                in out)

        out = await do(sim, bilda, "pay 25 to vending machine")
        assert "The display blinks. CREDIT: 25. Type vend <selection>." in out

        # The living description shows YOUR credit.
        out = await do(sim, bilda, "look vending machine")
        assert any("The display reads CREDIT: 25." in line for line in out)

        out = await do(sim, bilda, "vend coffee")
        assert ("The vending machine whirs and drops a bulb of cold "
                "coffee into the tray." in out)

        # The product is a real object in the room, with the weight attr
        # the container tutorial (014) will weigh.
        bulb = find_one(sim, "bulb of cold coffee")
        assert bulb.location is room
        assert bulb.db.get("weight") == 1

        out = await do(sim, bilda, "get bulb of cold coffee")
        assert "You pick up a bulb of cold coffee." in out
        assert bulb.location is bilda

        # Stock decremented; credit spent.
        out = await do(sim, bilda, "browse")
        assert any("coffee - 25 cr" in line and "(4 left)" in line
                   for line in out)

    async def test_unknown_selection_and_sell_out(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, VENDING_BUILD)
        await build(sim, bilda, ["@eval adjust_credits(me, 200); "
                                 "result = credits(me)"])

        out = await do(sim, bilda, "vend gruel")
        assert "The panel blinks: NO SUCH SELECTION. Try browse." in out

        await do(sim, bilda, "pay 80 to vending machine")
        await do(sim, bilda, "vend ration")
        out = await do(sim, bilda, "vend ration")
        assert ("The vending machine whirs and drops a vacuum-sealed "
                "ration into the tray." in out)
        out = await do(sim, bilda, "vend ration")
        assert "The ration coil is empty. SOLD OUT." in out

        machine = find_one(sim, "vending machine")
        assert get_credits(machine) == 80
        assert get_credits(bilda) == 120


# =========================================================================
# 014. Basic container — docs/showcase/014_basic_container.md
# =========================================================================

SACK_BUILD = [
    "@create canvas sack",
    "drop canvas sack",
    "@desc canvas sack = A patched canvas sack. [[n = len(contents(me)); "
    "result = f'It bulges around {n} item{\"\" if n == 1 else \"s\"}.']]",
    "@set canvas sack/container = true",
    "@set canvas sack/capacity = 3",
    "@set canvas sack/weight_limit = 10",
    "@set canvas sack/on_check = mine = atype == 'item:on_put' and "
    "target is me; item = adata('item'); "
    "adding = get_attr(item, 'weight', 0); held = len(contents(me)); "
    "load = sum([get_attr(o, 'weight', 0) for o in contents(me)]); "
    "cap = V('capacity', 3); "
    "limit = V('weight_limit', 10); "
    "block(f'The {name(me)} is stuffed full - {cap} "
    "items is its limit.') if mine and held >= cap else None; "
    "block(f'At {adding} lbs that would overload the "
    "{name(me)} ({load} of {limit} lbs used).') "
    "if mine and held < cap and load + adding > limit else None",
    "@set canvas sack/on_put = pemit(enactor, f'The {name(me)}"
    " now holds {len(contents(me)) + 1} of "
    "{V(\"capacity\", 3)} items.')",
]

SACK_PROPS = [
    "@create pebble",
    "@set pebble/weight = 1",
    "@create brick",
    "@set brick/weight = 4",
    "@create lead ingot",
    "@set lead ingot/weight = 8",
    "@create bottle cap",
    "@create rusty spoon",
]


class TestBasicContainer:

    async def _built(self, sim):
        room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, SACK_BUILD)
        await build(sim, bilda, SACK_PROPS)
        sack = find_one(sim, "canvas sack")
        return room, bilda, sack

    async def test_weight_ward_blocks_the_overload(self, sim):
        _room, bilda, sack = await self._built(sim)

        out = await do(sim, bilda, "put pebble in canvas sack")
        assert "You put a pebble in the canvas sack." in out
        assert "The canvas sack now holds 1 of 3 items." in out

        out = await do(sim, bilda, "put brick in canvas sack")
        assert "The canvas sack now holds 2 of 3 items." in out

        # 5 lbs in, 8 more would burst the 10 lb limit: block(), with math.
        out = await do(sim, bilda, "put lead ingot in canvas sack")
        assert ("At 8 lbs that would overload the canvas sack "
                "(5 of 10 lbs used)." in out)
        ingot = find_one(sim, "lead ingot")
        assert ingot.location is bilda, "blocked put must not move the item"
        assert len(sack.contents) == 2

    async def test_count_ward_blocks_the_fourth_item(self, sim):
        _room, bilda, sack = await self._built(sim)
        await do(sim, bilda, "put pebble in canvas sack")
        await do(sim, bilda, "put brick in canvas sack")
        await do(sim, bilda, "put bottle cap in canvas sack")

        out = await do(sim, bilda, "put rusty spoon in canvas sack")
        assert "The canvas sack is stuffed full - 3 items is its limit." in out
        assert len(sack.contents) == 3

        # The living description counts the load.
        out = await do(sim, bilda, "look canvas sack")
        assert any("It bulges around 3 items." in line for line in out)

    async def test_closed_sack_refuses_both_directions(self, sim):
        _room, bilda, sack = await self._built(sim)
        await do(sim, bilda, "put pebble in canvas sack")

        out = await do(sim, bilda, "close canvas sack")
        assert "You close the canvas sack." in out

        out = await do(sim, bilda, "put brick in canvas sack")
        assert "canvas sack is closed." in "\n".join(out)
        out = await do(sim, bilda, "get pebble from canvas sack")
        assert "canvas sack is closed." in "\n".join(out)

        out = await do(sim, bilda, "open canvas sack")
        assert "You open the canvas sack." in out
        out = await do(sim, bilda, "get pebble from canvas sack")
        assert "You pick up a pebble." in out
        assert len(sack.contents) == 0


# =========================================================================
# 025. Lockable door — docs/showcase/025_lockable_door.md
# =========================================================================

DOOR_MIRROR_HOOKS = [
    "@set vault door/key_id = vault_brass",
    "@set vault door/locked_msg = The wheel spins uselessly. Locked tight.",
    "@set vault door/on_open = remove_tag(V('partner'), 'closed')",
    "@set vault door/on_close = add_tag(V('partner'), 'closed')",
    "@set vault door/on_lock = set_attr(V('partner'), 'locked', True)",
    "@set vault door/on_unlock = set_attr(V('partner'), 'locked', False)",
]

DOOR_BUILD_SIDE_A = [
    "@dig The Vault = vault door, vault door",
    "@create brass key",
    "@set brass key/unlocks = vault_brass",
    "@eval a = [o for o in contents(here) if has_tag(o, 'exit') and "
    "name(o) == 'vault door'][0]; b = [o for o in contents(get('#' + "
    "str(get_attr(a, 'destination')))) if has_tag(o, 'exit') and "
    "str(get_attr(o, 'destination')) == here.id][0]; "
    "set_attr(a, 'partner', '#' + b.id); "
    "set_attr(b, 'partner', '#' + a.id); result = 'both sides wired'",
    *DOOR_MIRROR_HOOKS,
]


def door_sides(sim, workshop):
    vault = find_one(sim, "The Vault")
    side_a = next(o for o in workshop.contents if o.has_tag("exit"))
    side_b = next(o for o in vault.contents if o.has_tag("exit"))
    return vault, side_a, side_b


def door_state(exit_obj):
    return (exit_obj.has_tag("closed"), bool(exit_obj.db.get("locked")))


class TestLockableDoor:

    async def _built(self, sim):
        """Run the full two-sided build: side A, walk through, side B,
        walk back. Leaves the builder in the workshop, key in hand."""
        workshop, bilda = workshop_and_builder(sim)
        await build(sim, bilda, DOOR_BUILD_SIDE_A)
        await do(sim, bilda, "vault door")           # walk into the vault
        vault, side_a, side_b = door_sides(sim, workshop)
        assert bilda.location is vault
        await build(sim, bilda, DOOR_MIRROR_HOOKS)   # same lines, side B
        await do(sim, bilda, "vault door")           # walk back
        assert bilda.location is workshop
        return workshop, vault, bilda, side_a, side_b

    async def test_wiring_reports_both_sides(self, sim):
        workshop, bilda = workshop_and_builder(sim)
        await sim.do(bilda, DOOR_BUILD_SIDE_A[0])
        out = sim.seen(bilda)
        assert any("Room created: The Vault" in line for line in out)
        for line in DOOR_BUILD_SIDE_A[1:4]:
            await sim.do(bilda, line)
        out = sim.seen(bilda)
        assert any("both sides wired" in line for line in out)
        _vault, side_a, side_b = door_sides(sim, workshop)
        assert side_a.db.get("partner") == "#" + side_b.id
        assert side_b.db.get("partner") == "#" + side_a.id

    async def test_close_and_lock_mirror_to_the_far_side(self, sim):
        workshop, vault, bilda, side_a, side_b = await self._built(sim)

        out = await do(sim, bilda, "close vault door")
        assert "You close the vault door." in out
        assert door_state(side_a) == (True, False)
        assert door_state(side_b) == (True, False), "far side must agree"

        out = await do(sim, bilda, "lock vault door")
        assert "You lock vault door with brass key." in out
        assert door_state(side_a) == (True, True)
        assert door_state(side_b) == (True, True), "far side must agree"

        # Walking is refused by the closed door; opening by the lock.
        out = await do(sim, bilda, "vault door")
        assert "The vault door is closed." in out
        assert bilda.location is workshop
        out = await do(sim, bilda, "open vault door")
        assert "The wheel spins uselessly. Locked tight." in out

        # The key opens the way — and the far side follows every step.
        out = await do(sim, bilda, "unlock vault door")
        assert "You unlock vault door with brass key." in out
        assert door_state(side_a) == (True, False)
        assert door_state(side_b) == (True, False)

        out = await do(sim, bilda, "open vault door")
        assert "You open the vault door." in out
        assert door_state(side_a) == (False, False)
        assert door_state(side_b) == (False, False)

        await do(sim, bilda, "vault door")
        assert bilda.location is vault

    async def test_locking_from_inside_locks_the_workshop_side(self, sim):
        workshop, vault, bilda, side_a, side_b = await self._built(sim)
        kess = sim.player("Kess", location=workshop)

        # The builder walks in and locks up behind them.
        await do(sim, bilda, "vault door")
        assert bilda.location is vault
        await do(sim, bilda, "close vault door")
        await do(sim, bilda, "lock vault door")
        assert door_state(side_a) == (True, True)
        assert door_state(side_b) == (True, True)

        # A keyless visitor on the OTHER side is properly shut out.
        out = await do(sim, kess, "vault door")
        assert "The vault door is closed." in out
        assert kess.location is workshop
        out = await do(sim, kess, "open vault door")
        assert "The wheel spins uselessly. Locked tight." in out
        out = await do(sim, kess, "unlock vault door")
        assert "You don't have the key." in out


# =========================================================================
# Docs <-> tests sync — the transcripts above must match the tutorials
# =========================================================================

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"

DOC_TRANSCRIPTS = {
    "005_magic_8ball.md": EIGHTBALL_BUILD + EIGHTBALL_RETHEME,
    "001_slot_machine.md": SLOT_BUILD,
    "002_vending_machine.md": VENDING_BUILD,
    "014_basic_container.md": SACK_BUILD + SACK_PROPS,
    "025_lockable_door.md": DOOR_BUILD_SIDE_A,  # mirror hooks included
}


def test_tutorial_docs_contain_the_exact_tested_command_lines():
    """Every Build-it line exercised above appears verbatim in its doc,
    so the tutorials can never drift from what the tests prove works."""
    for doc_name, lines in DOC_TRANSCRIPTS.items():
        text = (DOCS / doc_name).read_text(encoding="utf-8")
        for line in lines:
            assert line in text, (
                f"{doc_name} is missing a tested tutorial line:\n{line}")
