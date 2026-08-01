"""
The single interceptable damage chokepoint.

Every source of damage — a combat swing, a spell, a trap, a scripted
ability — funnels through :func:`deal_damage`, so one ``combat:on_damage``
event is where wards, shields, a room's "sanctuary" rule, and armor all
hook, uniformly, regardless of what dealt the blow. The event's check pass
may ``block`` the damage outright or reduce it (``mod`` / ``set_adata(
'damage', ...)``) BEFORE the ruleset's own DR/resistances run in
``apply_damage`` — the two compose.

(The event is named ``combat:on_damage`` for continuity: it predates
non-combat callers and is taught across the showcases. It is nonetheless
the universal damage event, not combat-only.)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.combat.combatant import Combatant
from realm.combat.ruleset import DamageResult, DamageType
from realm.core.action_tags import HOSTILE
from realm.core.action_types import ActionType
from realm.core.propagation import Action, propagate

if TYPE_CHECKING:
    from realm.combat.ruleset import Ruleset
    from realm.core.objects import GameObject

DAMAGE_EVENT = ActionType.ON_DAMAGE


async def deal_damage(
    attacker: GameObject | None,
    target: GameObject | Combatant,
    damage: DamageResult,
    ruleset: Ruleset,
    *,
    tags: set[str] | None = None,
) -> tuple[int, Action]:
    """Fire the interceptable damage event, honor any reduction, then apply.

    Returns ``(dealt, action)``. ``action.blocked`` is True if a ward vetoed
    the damage (dealt 0). ``damage`` is mutated in place to the final,
    post-reduction values so the caller can read totals/types for messaging.
    """
    defender = target if isinstance(target, Combatant) else Combatant(target)
    action = Action(
        actor=attacker,
        target=defender.obj,
        # Literal (not DAMAGE_EVENT) so the payload-doc AST scanner and a
        # plain grep both find this firing site.
        action_type=ActionType.ON_DAMAGE,
        tags={HOSTILE, *(tags or set())},
        extra={
            "damage": damage.total,
            "damage_types": {k.value: v
                             for k, v in damage.damage_by_type.items()},
        },
    )
    await propagate(action, deliver=False)
    if action.blocked:
        return 0, action

    # Honor a reduced payload: extra['damage'] (mutated by a ward) + any
    # modifiers, applied to the raw damage BEFORE the ruleset's own
    # DR/multipliers. Scale the per-type breakdown and DERIVE total from it
    # so total and damage_by_type never disagree (apply_damage reads types).
    final = max(0, int(action.extra.get("damage", damage.total))
                + action.total_modifier)
    if final != damage.total and damage.total > 0:
        ratio = final / damage.total
        damage.damage_by_type = {
            dtype: max(0, round(amount * ratio))
            for dtype, amount in damage.damage_by_type.items()
        }
        damage.total = sum(damage.damage_by_type.values())

    dealt = ruleset.apply_damage(defender, damage)
    return dealt, action


def typed_damage_result(amount: int, dtype_name: str, *,
                        magical: bool = False) -> DamageResult:
    """A one-type :class:`DamageResult` for callers that have a raw number
    and a type (spells, traps). Unknown type names fall back to MAGICAL.
    ``magical`` marks the DELIVERY (a spell, an enchanted source) — it
    drives the broad-family resistance ladder, not the type itself."""
    try:
        dtype = DamageType(str(dtype_name))
    except ValueError:
        dtype = DamageType.MAGICAL
    amount = max(0, int(amount))
    return DamageResult(total=amount, damage_by_type={dtype: amount},
                        magical=magical)


def apply_resisted(target: GameObject, amount: int, dtype_name: str, *,
                   magical: bool = False) -> int:
    """Apply typed damage to ``target`` synchronously, honoring its
    ``resistances`` map but WITHOUT firing the damage event. The deliberate
    bypass path: softcode ``damage()`` (a builder who calls it means it), and
    the no-combat-manager fallback in tools/tests. Returns HP dealt."""
    from realm.combat.ruleset import apply_type_resistance

    result = typed_damage_result(amount, dtype_name, magical=magical)
    resist = target.db.get("resistances")
    scaled, _ = apply_type_resistance(
        result.damage_by_type, resist if isinstance(resist, dict) else None,
        magical=magical)
    dealt = sum(scaled.values())
    hp = target.db.get("hp")
    if hp is None:
        return 0
    target.db.hp = int(hp) - dealt
    return dealt
