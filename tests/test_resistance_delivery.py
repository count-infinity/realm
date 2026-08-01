"""The resistance key ladder: exact type, else delivery family.

Found playing Midgaard (2026-08-01): ROM's IMM_WEAPON/IMM_MAGIC import as
broad keys (``physical``/``magical``) that exact-key lookup never matched —
Otho the money changer, unkillable in ROM, died to a mortal's club while
every imported imm/res/vuln silently no-opped.

The model (SMAUG + CoffeeMud surveys, same date): a hit carries ONE
specific type; ``magical``/``physical`` are DELIVERY families consulted
only when the exact key misses. An enchanted (magic-tagged) weapon's hits
are magical delivery — so weapon immunity is bypassed by enchanted blades,
the classic ROM gate — while a mundane torch's fire is not gated by magic
immunity.
"""

from __future__ import annotations

from realm.combat.combatant import Combatant
from realm.combat.damage import apply_resisted
from realm.combat.ruleset import DamageResult, DamageType, apply_type_resistance
from realm.combat.rulesets.merc import MercRuleset
from realm.core.objects import GameObject


def _scaled(dmg, resist, **kw):
    scaled, _ = apply_type_resistance(dmg, resist, **kw)
    return sum(scaled.values())


class TestKeyLadder:

    IMM_WEAPON = {'physical': 0.0}
    IMM_MAGIC = {'magical': 0.0}
    OTHO = {'physical': 0.0, 'magical': 0.0}

    def test_mundane_club_vs_weapon_immune(self):
        # bludgeoning falls back to the 'physical' family: immune.
        assert _scaled({DamageType.BLUDGEONING: 10}, self.IMM_WEAPON) == 0

    def test_magic_blade_bypasses_weapon_immunity(self):
        # magical delivery skips the 'physical' family entirely.
        assert _scaled({DamageType.SLASHING: 10}, self.IMM_WEAPON,
                       magical=True) == 10

    def test_otho_is_immune_to_everything(self):
        # imm weapon AND magic — ROM's money-changer protection, faithful.
        assert _scaled({DamageType.BLUDGEONING: 10}, self.OTHO) == 0
        assert _scaled({DamageType.SLASHING: 10}, self.OTHO, magical=True) == 0
        assert _scaled({DamageType.FIRE: 10}, self.OTHO, magical=True) == 0

    def test_exact_key_beats_family(self):
        # Specific slashing resist coexists with blanket weapon immunity:
        # the exact key wins for slashing, the family covers the rest.
        resist = {'slashing': 0.5, 'physical': 0.0}
        assert _scaled({DamageType.SLASHING: 10}, resist) == 5
        assert _scaled({DamageType.PIERCING: 10}, resist) == 0

    def test_spell_vs_magic_immunity(self):
        assert _scaled({DamageType.FIRE: 10}, self.IMM_MAGIC,
                       magical=True) == 0

    def test_mundane_fire_ignores_magic_immunity(self):
        # A torch is not a spell: no exact 'fire' key, delivery not
        # magical, fire is not in the physical family — full damage.
        assert _scaled({DamageType.FIRE: 10}, self.IMM_MAGIC) == 10

    def test_elemental_exact_keys_unaffected(self):
        assert _scaled({DamageType.FIRE: 10}, {'fire': 0.5},
                       magical=True) == 5

    def test_true_damage_bypasses_all(self):
        assert _scaled({DamageType.TRUE: 10}, self.OTHO, magical=True) == 10


class TestMercDeliveryWiring:

    def _mob(self, resist):
        mob = GameObject("victim", tags=['npc'])
        mob.db.hp = 50
        mob.db.max_hp = 50
        mob.db.resistances = resist
        return mob

    def test_weapon_is_magical_reads_the_tag(self):
        ruleset = MercRuleset()
        club = GameObject("a club", tags=['thing'])
        assert not ruleset.weapon_is_magical(club)
        club.add_tag('magic')
        assert ruleset.weapon_is_magical(club)
        assert not ruleset.weapon_is_magical(None)

    def test_apply_damage_honors_delivery(self):
        ruleset = MercRuleset()
        mob = self._mob({'physical': 0.0})
        target = Combatant(mob)
        mundane = DamageResult(total=10,
                               damage_by_type={DamageType.BLUDGEONING: 10})
        assert ruleset.apply_damage(target, mundane) == 0
        enchanted = DamageResult(total=10,
                                 damage_by_type={DamageType.BLUDGEONING: 10},
                                 magical=True)
        assert ruleset.apply_damage(target, enchanted) == 10

    def test_apply_resisted_poison_regression(self):
        # The venom path: poison exact key still governs, unchanged.
        mob = self._mob({'poison': 0.0})
        assert apply_resisted(mob, 5, 'poison') == 0
        assert int(mob.db.get('hp')) == 50
