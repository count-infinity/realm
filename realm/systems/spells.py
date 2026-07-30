"""
Spells: a *flavor* of the generic ability mechanism (systems.abilities).

There is nothing genre-specific left here. A spell is an ``ability_def``
tagged ``spell_def`` and invoked with the ``cast`` verb — mana is just one
cost pool, class/level just one eligibility rule. The whole pipeline
(gate -> propagate ``spell:<name>`` -> pay cost -> apply effects, damage
firing the shared ``combat:on_damage`` event) lives in ``abilities``; this
module is the thin spell-shaped API the ``cast`` command, the ``caster``
behavior, the ROM importer, and the ``merc-classic`` pack use.

A ``spell_def`` still reads its old flat fields (``mana``, ``damage_dice``,
``heal_dice``, ``effect``, ``save``, ``classes``, ``level``, ``target``,
``on_cast``), so nothing authored before the generalization changed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.systems.abilities import (
    SPELL_DEF_TAG,
    apply_typed_damage,
    can_invoke,
    find_ability_def,
    invoke_ability,
    list_ability_defs,
)

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.propagation import Action


def list_spell_defs() -> list[GameObject]:
    """Every spell_def in the world, stably ordered."""
    return list_ability_defs(tag=SPELL_DEF_TAG)


def find_spell_def(name: str) -> GameObject | None:
    """A spell_def by name (exact, else unique prefix)."""
    return find_ability_def(name, tag=SPELL_DEF_TAG)


def knows_spell(caster: GameObject, spell: GameObject) -> bool:
    """Class/level eligibility (NPCs always pass) — the spell-flavored name
    for the generic ``can_invoke``."""
    return can_invoke(caster, spell)


async def cast_spell(
    caster: GameObject,
    spell: GameObject,
    target: GameObject | None = None,
) -> Action | None:
    """Cast ``spell`` as ``caster`` — the ability pipeline with the ``cast``
    verb and the ``spell:`` event domain."""
    return await invoke_ability(caster, spell, target,
                                verb="cast", domain="spell")


__all__ = [
    "SPELL_DEF_TAG",
    "apply_typed_damage",
    "cast_spell",
    "find_spell_def",
    "knows_spell",
    "list_spell_defs",
]
