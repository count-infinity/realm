"""The composition trust model: harm-authoring primitives are gated to the
AUTHOR's capability, carried as the executor's delegated authority.

The rule (realm/scripting/functions.py, _may_harm): walk the executor's
owner-delegation chain -- HARM entitlement anywhere allows; a player/guest
mortal as the responsible principal denies; unowned / NPC / system world
content is trusted by construction. So:

- a builder-authored dart still fires in a player's hand (the dart delegates
  to its builder owner; the invoker's role is irrelevant),
- a player who authors the same softcode gets NameError (damage is not even
  a bound name -- the sandbox has empty __builtins__, so an unbound name is
  unrecoverable, which is why removing the name IS the boundary),
- unowned world content (a designer-placed trap) and NPCs keep working.

`heal` (beneficial) and `transfer_credits` (moves existing money) are NOT
gated; only `damage`/`apply_effect`/`remove_effect` and `adjust_credits`
(mint) are.
"""

from __future__ import annotations

import pytest

from realm.core.objects import GameObject
from realm.scripting.functions import ScriptFunctions
from realm.testing import Simulator

HARM_KEYS = frozenset({'damage', 'apply_effect', 'remove_effect',
                       'adjust_credits'})
ALWAYS_SAFE = frozenset({'heal', 'transfer_credits', 'pemit', 'get', 'rand'})


def _bound(executor):
    return set(ScriptFunctions(executor=executor).to_dict())


# --- the palette filter (unit) ----------------------------------------------

class TestHarmPaletteFilter:

    def test_builder_executor_binds_harm(self):
        bound = _bound(GameObject('B', tags=['builder']))
        assert HARM_KEYS <= bound
        assert ALWAYS_SAFE <= bound

    def test_player_executor_omits_harm(self):
        bound = _bound(GameObject('P', tags=['player']))
        assert not (HARM_KEYS & bound)          # none bound
        assert ALWAYS_SAFE <= bound             # safe palette intact

    def test_guest_executor_omits_harm(self):
        assert not (HARM_KEYS & _bound(GameObject('G', tags=['guest'])))

    def test_plain_object_owned_by_player_omits_harm(self):
        # A player's slot machine: harmless-looking object, mortal principal.
        player = GameObject('Pat', tags=['player'])
        machine = GameObject('slots')
        machine.owner = player
        assert not (HARM_KEYS & _bound(machine))
        assert ALWAYS_SAFE <= _bound(machine)   # can still emit / pay out

    def test_plain_object_owned_by_builder_binds_harm(self):
        builder = GameObject('Bob', tags=['builder'])
        trap = GameObject('trap')
        trap.owner = builder
        assert HARM_KEYS <= _bound(trap)

    def test_unowned_world_object_binds_harm(self):
        # Designer-placed / imported content is trusted by construction.
        assert HARM_KEYS <= _bound(GameObject('a rune trap'))

    def test_npc_binds_harm(self):
        # An NPC's harm is designer-authored, not player-authored.
        assert HARM_KEYS <= _bound(GameObject('dragon', tags=['npc']))

    def test_npc_owned_by_player_omits_harm(self):
        # A player's scripted pet cannot be a harm proxy.
        pat = GameObject('Pat', tags=['player'])
        pet = GameObject('imp', tags=['npc'])
        pet.owner = pat
        assert not (HARM_KEYS & _bound(pet))

    def test_no_executor_binds_harm(self):
        # No frame context (system-level) is trusted.
        assert HARM_KEYS <= _bound(None)

    def test_role_def_grant_binds_harm(self):
        # A custom rank that lists HARM works like a builder (roles-as-data):
        # a "crafter" who may author harm without being a full builder.
        from realm.permissions.entitlements import HARM, reload_role_defs
        rd = GameObject('crafter', tags=['role_def'])
        rd.db.set('entitlements', [HARM])
        sim = Simulator()
        try:
            sim.add(rd)
            reload_role_defs()
            crafter = GameObject('C', tags=['crafter'])
            assert HARM_KEYS <= _bound(crafter)
        finally:
            sim.close()
            reload_role_defs()                  # drop the test's def table


# --- author-not-invoker, through the real eval path (integration) -----------

@pytest.mark.asyncio
class TestAuthorNotInvoker:

    async def _arena(self):
        sim = Simulator()
        room = sim.room('Arena')
        builder = sim.player('Bob', location=room)
        builder.add_tag('builder')
        player = sim.player('Pat', location=room)         # plain player
        target = sim.obj('dummy', location=room)
        target.db.set('hp', 100)
        return sim, room, builder, player, target

    async def test_builder_owned_item_damages(self):
        sim, room, builder, player, target = await self._arena()
        try:
            dart = sim.obj('dart', location=room)
            dart.owner = builder
            _, err = await sim.eval(dart, "damage(get('dummy'), 5)")
            assert err is None
            assert target.db.get('hp') == 95
        finally:
            sim.close()

    async def test_builder_dart_fires_when_a_player_triggers_it(self):
        # The headline case: author authority, not invoker. A builder-owned
        # dart, triggered BY a plain player (enactor), still damages -- the
        # invoker's mortal role is irrelevant; the dart's builder owner is
        # what the gate reads. (Co-located with the target so reach is met.)
        sim, room, builder, player, target = await self._arena()
        try:
            dart = sim.obj('sold dart', location=room)
            dart.owner = builder                           # authored by Bob
            _, err = await sim.eval(dart, "damage(get('dummy'), 7)",
                                    enactor=player)         # Pat pulls it
            assert err is None
            assert target.db.get('hp') == 93
        finally:
            sim.close()

    async def test_player_owned_item_cannot_damage(self):
        sim, room, builder, player, target = await self._arena()
        try:
            gadget = sim.obj('gadget', location=player)
            gadget.owner = player                          # authored by Pat
            _, err = await sim.eval(gadget, "damage(get('dummy'), 50)")
            assert err is not None and 'damage' in err     # NameError: damage
            assert target.db.get('hp') == 100              # unharmed
        finally:
            sim.close()

    async def test_player_cannot_mint_but_can_transfer(self):
        sim, room, builder, player, target = await self._arena()
        try:
            machine = sim.obj('slots', location=room)
            machine.owner = player
            machine.db.set('credits', 100)
            player.db.set('credits', 0)
            # Minting is denied (adjust_credits unbound)...
            _, err = await sim.eval(machine, "adjust_credits(me, 1000)")
            assert err is not None and 'adjust_credits' in err
            assert machine.db.get('credits') == 100        # no money conjured
            # ...but paying out existing money is fine (transfer_credits safe).
            _, err = await sim.eval(
                machine, "transfer_credits(me, get('Pat'), 40)")
            assert err is None
            assert machine.db.get('credits') == 60
            assert player.db.get('credits') == 40
        finally:
            sim.close()

    async def test_builder_can_mint(self):
        sim, room, builder, player, target = await self._arena()
        try:
            till = sim.obj('till', location=room)
            till.owner = builder
            till.db.set('credits', 0)
            _, err = await sim.eval(till, "adjust_credits(me, 500)")
            assert err is None
            assert till.db.get('credits') == 500
        finally:
            sim.close()
