"""
Spells as data: ``spell_def`` objects + the cast pipeline.

A spell is NOT a framework — it is an ordinary two-pass propagated action
(``spell:<name>``) whose payload is built from a ``spell_def`` object, the
same def-object pattern as ``skill_def``/``class_def``/``behavior_def``.
The propagation engine already supplies everything magical about magic:

- **check pass** (caster first, then room, bystanders, target): wards and
  softcode ``on_check`` may ``block`` (counterspell, an anti-magic room) or
  modify the payload (``set_adata('damage', ...)`` for magic resistance,
  ``set_adata('mana_cost', ...)`` for a damping field).
- **apply** (between the passes): requirements are *announced* in the
  payload but *enforced here*, after every check-pass modification —
  the engine's "insufficient funds reads exactly like a ward veto"
  convention. Spend mana, roll the save, apply the effect.
- **react pass**: ``ON_*`` hooks, messages; a damaging spell is tagged
  ``hostile`` so the combat manager's hostile observer auto-initiates —
  the fireball WAS your turn.

A ``spell_def`` is declarative for the common shapes and softcode for the
rest:

    tags:  spell_def
    attrs: level=15, mana=15, target='victim', classes=['mage'],
           damage_dice='6d6', damage_type='fire', save='half'
    # and/or: heal_dice, effect={'behavior_id': ..., 'params': {...}},
    #         on_cast=<softcode run as the spell_def>

Typed damage routes through the active ruleset's ``apply_damage``, so the
damage-type ``resistances`` layer fires: the fire-immune dragon takes 0
from fireball with no spell-side code.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from realm.core.query import find_objects

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.propagation import Action

SPELL_DEF_TAG = "spell_def"


# --- spell_def lookup --------------------------------------------------------

def list_spell_defs() -> list[GameObject]:
    """Every spell_def in the world, stably ordered."""
    return sorted(find_objects(tag=SPELL_DEF_TAG), key=lambda o: o.id)


def find_spell_def(name: str) -> GameObject | None:
    """A spell_def by name: exact (case-insensitive) first, then a unique
    prefix — so ``cast fire`` finds fireball unless fire breath is also
    defined."""
    want = name.strip().lower()
    if not want:
        return None
    defs = list_spell_defs()
    for obj in defs:
        if obj.name.lower() == want:
            return obj
    prefixed = [o for o in defs if o.name.lower().startswith(want)]
    return prefixed[0] if len(prefixed) == 1 else None


def knows_spell(caster: GameObject, spell: GameObject) -> bool:
    """Class/level gate for players. NPCs pass — their spell list is
    whatever their caster behavior was given (Diku mobs cast by spec, not
    by class)."""
    if caster.has_tag("npc"):
        return True
    classes = spell.db.get("classes")
    if classes:
        cls = caster.db.get("character_class")
        if cls not in classes:
            return False
    level = int(spell.db.get("level") or 1)
    return int(caster.db.get("level") or 1) >= level


# --- damage plumbing ---------------------------------------------------------

def _roll_dice(spec: str) -> int:
    import re
    m = re.match(r"\s*(\d+)d(\d+)([+-]\d+)?\s*$", str(spec))
    if not m:
        try:
            return int(spec)
        except (TypeError, ValueError):
            return 0
    n, s, b = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    return sum(random.randint(1, s) for _ in range(n)) + b


def apply_typed_damage(target: GameObject, amount: int, dtype_name: str) -> int:
    """Deal ``amount`` typed damage to ``target`` through the active
    ruleset's ``apply_damage`` (so DR, resistances, and any other
    ruleset mitigation fire). Without a combat manager (tools, tests) it
    falls back to the neutral resistance helper, so a ``resistances``
    multiplier map is honored either way. Returns HP actually dealt.
    Death handling is the caller's job."""
    from realm.combat.combatant import Combatant
    from realm.combat.manager import get_combat_manager
    from realm.combat.ruleset import (
        DamageResult,
        DamageType,
        apply_type_resistance,
    )
    try:
        dtype = DamageType(str(dtype_name))
    except ValueError:
        dtype = DamageType.MAGICAL
    amount = max(0, int(amount))
    manager = get_combat_manager()
    if manager is not None:
        result = DamageResult(total=amount, damage_by_type={dtype: amount})
        return manager.combat_system.ruleset.apply_damage(
            Combatant(target), result)
    scaled, _ = apply_type_resistance(
        {dtype: amount}, target.db.get("resistances")
        if isinstance(target.db.get("resistances"), dict) else None)
    dealt = sum(scaled.values())
    hp = target.db.get("hp")
    if hp is None:
        return 0
    target.db.hp = int(hp) - dealt
    return dealt


# --- the cast pipeline -------------------------------------------------------

def _slug(name: str) -> str:
    return "_".join(str(name).lower().split())


async def cast_spell(
    caster: GameObject,
    spell: GameObject,
    target: GameObject | None = None,
) -> Action | None:
    """Cast ``spell`` (a spell_def) as ``caster``: one gated propagated
    action, ``spell:<name>``. Returns the applied Action, or None if it
    was vetoed / could not pay. The caller gates *knowledge* (see
    ``knows_spell``); this gates *payment and delivery*."""
    from realm.core.propagation import Action, deliver_messages, gate_action

    name = spell.name
    # Hostile: any damaging spell, or an effect spell flagged so (curse).
    offensive = bool(spell.db.get("damage_dice")) or \
        bool(spell.db.get("hostile"))
    want = str(spell.db.get("target") or ("victim" if offensive else "self"))
    if want == "self":
        target = caster
    elif want == "ally":
        target = target or caster                # cure light: them, or you
    elif target is None:
        target = _combat_opponent(caster)
    if target is None:
        caster.msg(f"Cast {name} at whom?")
        return None

    action = Action(actor=caster, target=target,
                    action_type=f"spell:{_slug(name)}", tool=spell)
    action.tags.add("magic")
    if offensive and target is not caster:
        action.tags.add("hostile")
    # The payload: announced here, modifiable by every on_check,
    # ENFORCED in _apply below (final values win).
    action.add_data("spell", name)
    action.add_data("level", int(spell.db.get("level") or 1))
    action.add_data("mana_cost", int(spell.db.get("mana") or 0))
    if offensive:
        action.add_data("damage",
                        _roll_dice(spell.db.get("damage_dice")))
        action.add_data("damage_type",
                        str(spell.db.get("damage_type") or "magical"))

    async def _apply(act: Action) -> bool:
        return await _apply_spell(act, caster, spell, target)

    if not await gate_action(action,
                             fail_msg=f"The {name} fizzles.",
                             apply=_apply):
        return None
    if target is not caster:
        action.add_message("actor", f"You cast {name} at " + "{target:the}.")
        action.add_message("room", "{actor} casts " + name + " at {target:the}.")
    else:
        action.add_message("actor", f"You cast {name}.")
        action.add_message("room", "{actor} casts " + name + ".")
    deliver_messages(action)
    return action


def _combat_opponent(caster: GameObject) -> GameObject | None:
    """The caster's current combat target, if fighting."""
    from realm.combat.manager import get_combat_manager
    manager = get_combat_manager()
    if manager is None or caster.location is None:
        return None
    enc = manager.encounter_in(caster.location)
    if enc is None:
        return None
    me = enc.get(caster.id)
    if me is None or not me.target_id:
        return None
    other = enc.get(me.target_id)
    return other.obj if other is not None else None


async def _apply_spell(action: Action, caster: GameObject,
                       spell: GameObject, target: GameObject) -> bool:
    """The apply step: enforce the FINAL payload, then effect."""
    # 1. Mana — read post-modification cost. A mob with no mana pool casts
    #    freely (Diku spec mobs); a player with none cannot channel at all.
    cost = max(0, int(action.extra.get("mana_cost") or 0))
    mana = caster.db.get("mana")
    if mana is None:
        if not caster.has_tag("npc") and cost > 0:
            action.block("You have no mana to channel.")
            return False
    elif int(mana) < cost:
        action.block("You don't have the mana.")
        return False
    else:
        caster.db.mana = int(mana) - cost

    system = _game_system()

    # 2. Saving throw — rolled once, system policy. Affects damage
    #    (half/negates) and, on 'negates', the declarative effect too.
    save = str(spell.db.get("save") or "none")
    saved = False
    if save != "none" and system is not None and target is not caster:
        saved = system.saving_throw(target,
                                    int(action.extra.get("level") or 1))
        action.add_data("saved", saved)
        if saved:
            action.add_message("target", "You partially resist!")

    # 3. Damage (typed, through the ruleset -> resistances/DR).
    damage = int(action.extra.get("damage") or 0)
    if damage > 0:
        if saved:
            damage = 0 if save == "negates" else damage // 2
        dealt = apply_typed_damage(
            target, damage, str(action.extra.get("damage_type") or "magical"))
        action.add_data("dealt", dealt)
        await _death_check(target, killer=caster)

    # 4. Healing.
    heal_dice = spell.db.get("heal_dice")
    if heal_dice:
        hp, max_hp = target.db.get("hp"), target.db.get("max_hp")
        if hp is not None and max_hp is not None:
            healed = _roll_dice(heal_dice)
            target.db.hp = min(int(max_hp), int(hp) + healed)
            action.add_data("healed", healed)

    # 5. Declarative effect: attach a behavior (bless, curse, poison...).
    #    A save of 'negates' that succeeded shrugs the whole effect off.
    effect = spell.db.get("effect")
    if isinstance(effect, dict) and effect.get("behavior_id") and \
            not (saved and save == "negates"):
        from realm.core.behaviors import BehaviorRegistry
        behavior = BehaviorRegistry.create(
            str(effect["behavior_id"]), **dict(effect.get("params") or {}))
        if behavior is not None:
            target.add_behavior(behavior)

    # 6. Bespoke softcode, run AS the spell_def (its owner's authority).
    code = spell.db.get("on_cast")
    if isinstance(code, str) and code.strip():
        from realm.scripting.engine import get_script_engine
        engine = get_script_engine()
        if engine is not None:
            await engine.run_behavior_script(spell, code, action=action,
                                             enactor=caster)
    return True


def _game_system():
    from realm.systems.base import get_game_system
    return get_game_system()


async def _death_check(target: GameObject, killer: GameObject) -> None:
    from realm.combat.manager import get_combat_manager
    manager = get_combat_manager()
    if manager is not None and int(target.db.get("hp") or 0) <= 0:
        await manager.handle_death(target, killer=killer)


__all__ = [
    "SPELL_DEF_TAG",
    "apply_typed_damage",
    "cast_spell",
    "find_spell_def",
    "knows_spell",
    "list_spell_defs",
]
