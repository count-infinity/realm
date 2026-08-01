"""
Abilities as data: the one generic capability under spells, skills, shouts.

A spell, a combat maneuver, a war-shout, a device's power, a poison dart's
prick are the *same mechanism* with different data:

    invoke -> (gate: known? afford? ) -> propagate an event -> apply effects

"Spell" is just an ``ability_def`` flavored with a mana cost and a
spellbook (see ``systems.spells``); a "rally cry" is one flavored with a
per-day limit, a room target, and a +2 modifier effect. Nothing here
assumes a genre — cost is a **spec** (not hardcoded mana), eligibility is a
rule, effects are a **list of specs** parameterizing engine primitives and
behaviors (the composition model), and damage effects fire the shared
``combat:on_damage`` event so they are interceptable exactly like a swing.

An ``ability_def`` (or ``spell_def``) object carries:

    target   : 'self' | 'ally' | 'victim' | 'room'      (default: victim if
               it has a damage effect, else self)
    cost     : {'pool': 'mana', 'n': 15} | {'per_day': 2, 'attr': 'used_x'}
               | (legacy) mana=15
    effects  : [ {'type':'damage','dice':'6d6','damage_type':'fire',
                  'save':'half'},
                 {'type':'heal','dice':'2d8+2'},
                 {'type':'behavior','behavior_id':'modifier_effect',
                  'params':{...},'save':'negates'},
                 {'type':'softcode','code':'...'} ]
               (legacy flat fields damage_dice/heal_dice/effect/save are
                read too, so existing spell_defs need no change)
    classes / level / skill_req : eligibility (a player must qualify; NPCs
               always pass — their list is whatever behavior granted it)
    on_invoke / on_cast : bespoke softcode, run AS the def
"""

from __future__ import annotations

import random
import re
from typing import TYPE_CHECKING, Any

from realm.core.query import find_objects

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.propagation import Action

ABILITY_DEF_TAG = "ability_def"
SPELL_DEF_TAG = "spell_def"          # a flavor of ability; both are abilities
_ABILITY_TAGS = (ABILITY_DEF_TAG, SPELL_DEF_TAG)


# --- lookup -----------------------------------------------------------------

def list_ability_defs(tag: str | None = None) -> list[GameObject]:
    """Every ability_def / spell_def in the world, stably ordered. Pass a
    tag to restrict to one flavor (e.g. only ``spell_def``)."""
    seen: dict[str, GameObject] = {}
    for t in ((tag,) if tag else _ABILITY_TAGS):
        for obj in find_objects(tag=t):
            seen[obj.id] = obj
    return sorted(seen.values(), key=lambda o: o.id)


def find_ability_def(name: str, tag: str | None = None) -> GameObject | None:
    """An ability by name: exact (case-insensitive), else a unique prefix."""
    want = name.strip().lower()
    if not want:
        return None
    defs = list_ability_defs(tag)
    for obj in defs:
        if obj.name.lower() == want:
            return obj
    prefixed = [o for o in defs if o.name.lower().startswith(want)]
    return prefixed[0] if len(prefixed) == 1 else None


def can_invoke(actor: GameObject, adef: GameObject) -> bool:
    """Eligibility: may ``actor`` invoke ``adef``? NPCs always pass (their
    repertoire is whatever behavior granted it). Players must meet the
    class / level / skill requirement the def declares."""
    if actor.has_tag("npc"):
        return True
    classes = adef.db.get("classes")
    if classes and actor.db.get("character_class") not in classes:
        return False
    if int(actor.db.get("level") or 1) < int(adef.db.get("level") or 1):
        return False
    skill_req = adef.db.get("skill_req")
    if isinstance(skill_req, dict):
        from realm.core.checks import skill_level
        if skill_level(actor, str(skill_req.get("skill"))) < \
                int(skill_req.get("min") or 0):
            return False
    return True


# --- dice + damage ----------------------------------------------------------

def roll_dice(spec: str) -> int:
    """Sum an ``NdS+B`` string (or a bare integer)."""
    m = re.match(r"\s*(\d+)d(\d+)([+-]\d+)?\s*$", str(spec))
    if not m:
        try:
            return int(spec)
        except (TypeError, ValueError):
            return 0
    n, s, b = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    return sum(random.randint(1, s) for _ in range(n)) + b


async def apply_typed_damage(target: GameObject, amount: int, dtype_name: str,
                             attacker: GameObject | None = None, *,
                             magical: bool = True) -> int:
    """Deal ``amount`` typed damage, fired through the shared
    ``combat:on_damage`` chokepoint (interceptable; routed through the
    ruleset's resistances/DR). Falls back to a direct resisted apply when no
    combat manager is installed (tools/tests). Returns HP dealt.

    ``magical`` marks the delivery for the resistance family ladder —
    True by default because ability damage is overwhelmingly spellwork;
    a mundane trap/venom ability passes ``magical=False`` (effect-spec
    key ``magical``)."""
    from realm.combat.damage import apply_resisted, deal_damage, typed_damage_result
    from realm.combat.manager import get_combat_manager

    manager = get_combat_manager()
    if manager is not None:
        result = typed_damage_result(amount, dtype_name, magical=magical)
        dealt, _action = await deal_damage(
            attacker, target, result, manager.combat_system.ruleset)
        return dealt
    return apply_resisted(target, amount, dtype_name, magical=magical)


# --- ability model (normalization) ------------------------------------------

def _effects_of(adef: GameObject) -> list[dict]:
    """The ability's effect-spec list — the ``effects`` attr if present, else
    derived from the legacy flat spell fields so old ``spell_def``s work."""
    effects = adef.db.get("effects")
    if isinstance(effects, list) and effects:
        return [e for e in effects if isinstance(e, dict)]
    out: list[dict] = []
    save = str(adef.db.get("save") or "none")
    if adef.db.get("damage_dice"):
        out.append({"type": "damage", "dice": adef.db.get("damage_dice"),
                    "damage_type": str(adef.db.get("damage_type") or "magical"),
                    "save": save})
    if adef.db.get("heal_dice"):
        out.append({"type": "heal", "dice": adef.db.get("heal_dice")})
    eff = adef.db.get("effect")
    if isinstance(eff, dict) and eff.get("behavior_id"):
        out.append({"type": "behavior", "behavior_id": eff["behavior_id"],
                    "params": eff.get("params") or {}, "save": save})
    return out


def _cost_of(adef: GameObject) -> dict | None:
    """Normalize the ability's cost to a spec, or None (free). Legacy
    ``mana=N`` is sugar for a mana-pool spec."""
    cost = adef.db.get("cost")
    if isinstance(cost, dict) and cost:
        return cost
    mana = adef.db.get("mana")
    if mana:
        return {"pool": "mana", "n": int(mana)}
    return None


def _is_offensive(adef: GameObject, effects: list[dict]) -> bool:
    return bool(adef.db.get("hostile")) or \
        any(e.get("type") == "damage" for e in effects)


def _resolve_targets(actor: GameObject, want: str,
                     explicit: GameObject | None) -> tuple[list, Any]:
    """Return ``(targets, action_target)``. For a room ability the action's
    target is the room (so bystanders are consulted) and every character in
    it is a target; otherwise a single-element list."""
    if want == "self":
        return [actor], actor
    if want == "room":
        room = actor.location
        occ = [o for o in (room.contents if room else [])
               if o.has_tag("player") or o.has_tag("npc")]
        if actor not in occ:
            occ.append(actor)
        return occ, room or actor
    if want == "ally":
        t = explicit or actor
        return [t], t
    # victim
    t = explicit or _combat_opponent(actor)
    return ([t], t) if t is not None else ([], None)


def _combat_opponent(actor: GameObject) -> GameObject | None:
    from realm.combat.manager import get_combat_manager
    manager = get_combat_manager()
    if manager is None or actor.location is None:
        return None
    enc = manager.encounter_in(actor.location)
    if enc is None:
        return None
    me = enc.get(actor.id)
    if me is None or not me.target_id:
        return None
    other = enc.get(me.target_id)
    return other.obj if other is not None else None


# --- the invoke pipeline ----------------------------------------------------

def _slug(name: str) -> str:
    return "_".join(str(name).lower().split())


async def invoke_ability(
    actor: GameObject,
    adef: GameObject,
    target: GameObject | None = None,
    *,
    verb: str = "use",
    domain: str = "ability",
) -> Action | None:
    """Invoke ``adef`` as ``actor``: one gated, propagated ``<domain>:<name>``
    action. Eligibility is the caller's gate (see ``can_invoke``); this pays
    the cost and applies the effects. Returns the applied Action, or None if
    vetoed / unaffordable / untargetable.

    ``verb``/``domain`` flavor the messages and event type — spells pass
    ``verb='cast', domain='spell'``; a shout passes ``verb='shout'``."""
    from realm.core.propagation import Action, deliver_messages, gate_action

    name = adef.name
    effects = _effects_of(adef)
    offensive = _is_offensive(adef, effects)
    want = str(adef.db.get("target") or ("victim" if offensive else "self"))
    targets, action_target = _resolve_targets(actor, want, target)
    if not targets or action_target is None:
        actor.msg(f"{verb.capitalize()} {name} at whom?")
        return None

    action = Action(actor=actor, target=action_target,
                    action_type=f"{domain}:{_slug(name)}", tool=adef)
    action.tags.add("magic" if domain == "spell" else domain)
    if offensive and action_target is not actor:
        action.tags.add("hostile")
    action.add_data(domain, name)          # 'spell'/'ability' -> name
    action.add_data("level", int(adef.db.get("level") or 1))
    cost = _cost_of(adef)
    if cost and cost.get("pool"):
        n = int(cost.get("n") or 0)
        action.add_data("cost", n)                 # generic ward hook
        action.add_data(f"{cost['pool']}_cost", n)  # e.g. mana_cost (per-pool)
    # Announce the first damage figure so a ward can read/shave adata('damage').
    for eff in effects:
        if eff.get("type") == "damage":
            action.add_data("damage", roll_dice(eff.get("dice", "0")))
            action.add_data("damage_type", str(eff.get("damage_type")
                                               or "magical"))
            break

    async def _apply(act: Action) -> bool:
        return await _apply_ability(act, actor, adef, targets, cost, effects)

    if not await gate_action(action, fail_msg=f"The {name} fizzles.",
                             apply=_apply):
        return None

    solo = len(targets) == 1 and targets[0] is actor
    if solo or want == "room":
        action.add_message("actor", f"You {verb} {name}.")
        action.add_message("room", "{actor} " + f"{verb}s {name}.")
    else:
        action.add_message("actor", f"You {verb} {name} at " + "{target:the}.")
        action.add_message("room",
                           "{actor} " + f"{verb}s {name} at " + "{target:the}.")
    deliver_messages(action)
    return action


async def _apply_ability(action: Action, actor: GameObject, adef: GameObject,
                         targets: list, cost: dict | None,
                         effects: list[dict]) -> bool:
    """Apply step: pay the (final) cost, then each effect to each target."""
    if not _pay_cost(actor, cost, action):
        return False

    system = _game_system()
    # A ward may have shaved the announced damage; carry the ratio to effects.
    for target in targets:
        saved = _roll_save(system, actor, target, adef, effects, action)
        for eff in effects:
            await _apply_effect(action, actor, target, eff, saved, system)

    code = adef.db.get("on_invoke") or adef.db.get("on_cast")
    if isinstance(code, str) and code.strip():
        from realm.scripting.engine import get_script_engine
        engine = get_script_engine()
        if engine is not None:
            await engine.run_behavior_script(adef, code, action=action,
                                             enactor=actor)
    return True


def _pay_cost(actor: GameObject, cost: dict | None, action: Action) -> bool:
    """Charge the ability's cost, or block the action like a ward veto."""
    if not cost:
        return True
    if cost.get("pool"):
        pool = str(cost["pool"])
        # A ward may have rewritten the announced cost; enforce the final one
        # (per-pool key first, e.g. mana_cost, then the generic cost).
        n = max(0, int(action.extra.get(
            f"{pool}_cost", action.extra.get("cost", cost.get("n") or 0))))
        have = actor.db.get(pool)
        if have is None:
            if not actor.has_tag("npc") and n > 0:
                action.block(f"You have no {pool} to spend.")
                return False
        elif int(have) < n:
            action.block(f"You don't have the {pool}.")
            return False
        else:
            actor.db.set(pool, int(have) - n)
        return True
    if cost.get("per_day"):
        # A counter toward a daily cap; reset is rest-driven (see BACKLOG —
        # a real day/night reset is a separate feature). NPCs are uncapped.
        if actor.has_tag("npc"):
            return True
        attr = str(cost.get("attr")
                   or "used_" + action.action_type.replace(":", "_"))
        used = int(actor.db.get(attr) or 0)
        if used >= int(cost["per_day"]):
            action.block("You cannot do that again yet today.")
            return False
        actor.db.set(attr, used + 1)
        return True
    return True


def _roll_save(system, actor, target, adef, effects, action) -> bool:
    """One saving throw per target (Diku rolls once), consulted by every
    effect that declares a save mode. False when nothing saves."""
    if target is actor or system is None:
        return False
    if not any(str(e.get("save") or "none") != "none" for e in effects):
        return False
    saved = system.saving_throw(target, int(action.extra.get("level") or 1))
    action.add_data("saved", saved)
    if saved:
        target.msg("You partially resist!")
    return saved


async def _apply_effect(action: Action, actor: GameObject, target: GameObject,
                        eff: dict, saved: bool, system) -> None:
    etype = eff.get("type")
    save = str(eff.get("save") or "none")

    if etype == "damage":
        amount = roll_dice(eff.get("dice", "0"))
        # For the single-target case honor a ward's shaved adata('damage').
        if action.target is target and "damage" in action.extra:
            amount = int(action.extra.get("damage") or amount)
        if saved:
            amount = 0 if save == "negates" else amount // 2
        dealt = await apply_typed_damage(
            target, amount, str(eff.get("damage_type") or "magical"),
            attacker=actor, magical=bool(eff.get("magical", True)))
        action.add_data("dealt", dealt)
        await _death_check(target, killer=actor)

    elif etype == "heal":
        hp, max_hp = target.db.get("hp"), target.db.get("max_hp")
        if hp is not None and max_hp is not None:
            healed = roll_dice(eff.get("dice", "0"))
            target.db.hp = min(int(max_hp), int(hp) + healed)
            action.add_data("healed", healed)

    elif etype == "behavior":
        if saved and save == "negates":
            return
        from realm.core.behaviors import BehaviorRegistry
        behavior = BehaviorRegistry.create(
            str(eff.get("behavior_id")), **dict(eff.get("params") or {}))
        if behavior is not None:
            target.add_behavior(behavior)

    elif etype == "softcode":
        code = eff.get("code")
        if isinstance(code, str) and code.strip():
            from realm.scripting.engine import get_script_engine
            engine = get_script_engine()
            if engine is not None:
                await engine.run_behavior_script(
                    action.tool, code, action=action, enactor=actor,
                    params={"target": target})


def _game_system():
    from realm.systems.base import get_game_system
    return get_game_system()


async def _death_check(target: GameObject, killer: GameObject) -> None:
    from realm.combat.manager import get_combat_manager
    manager = get_combat_manager()
    if manager is not None and int(target.db.get("hp") or 0) <= 0:
        await manager.handle_death(target, killer=killer)


__all__ = [
    "ABILITY_DEF_TAG",
    "SPELL_DEF_TAG",
    "apply_typed_damage",
    "can_invoke",
    "find_ability_def",
    "invoke_ability",
    "list_ability_defs",
    "roll_dice",
]
