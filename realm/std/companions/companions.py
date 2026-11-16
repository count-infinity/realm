"""
Companions: one attribute, after CoffeeMud's followers (MUD_PLAN 13.1).

A companion is an NPC whose ``master`` attribute holds a character's id.
That is the whole relationship: it does not change who owns or controls
the object for building purposes. Bonding also sets the ``social``
feature's ``following`` (so the companion walks after its master), the
``companion`` tag (the index ``companions_of`` reads) and the
``companion`` behavior (the ward that keeps it from attacking its
master); releasing takes all four away.

How many a character may keep is CoffeeMud's ``FORMULA_MAXFOLLOW``
(Decision D8): the ``COMPANION_LIMIT_RULE`` setting, a rule expression;
else ``GameSystem.companion_limit``; the neutral system answers 2. The
count is CoffeeMud's ``totalFollowers``: each companion and, in turn,
its own companions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from realm.core.events import fire_event
from realm.core.language import definite_name
from realm.core.world import get_world
from realm.std.social.party import FOLLOWING_ATTR, set_following

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)

MASTER_ATTR = "master"
COMPANION_TAG = "companion"
#: Where a companion waited when it left the world with its master.
WAITING_ATTR = "companion_room"
BOND = "companion:on_bond"
RELEASE = "companion:on_release"


def _cached(obj_id) -> GameObject | None:
    store = get_world().store
    if not obj_id or store is None:
        return None
    return store.get_cached(str(obj_id).lstrip("#"))


def the(obj: GameObject, *, capital: bool = True) -> str:
    """How a line names ``obj``: "The kitten", "Alice", "Rusty"."""
    name = definite_name(obj)
    return name[:1].upper() + name[1:] if capital else name


def master_of(obj: GameObject) -> GameObject | None:
    """The character ``obj`` is a companion of, or None."""
    return _cached(obj.db.get(MASTER_ATTR))


def companions_of(character: GameObject) -> list[GameObject]:
    """``character``'s companions, wherever they are (beside it, elsewhere,
    or out of the world while it is logged out), by name."""
    store = get_world().store
    if store is None:
        return []
    return sorted((obj for obj in store.find_cached(tag=COMPANION_TAG)
                   if obj.db.get(MASTER_ATTR) == character.id),
                  key=lambda obj: (obj.name.lower(), obj.id))


def follower_count(character: GameObject) -> int:
    """CoffeeMud's ``totalFollowers``: ``character``'s companions, each
    with its own companions counted too."""
    seen = {character.id}
    stack = companions_of(character)
    total = 0
    while stack:
        obj = stack.pop()
        if obj.id in seen:
            continue
        seen.add(obj.id)
        total += 1
        stack.extend(companions_of(obj))
    return total


def _level(obj: GameObject) -> int:
    value = obj.db.get("level")
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def companion_limit(character: GameObject) -> int:
    """How many followers ``character`` may keep (Decision D8): the
    ``COMPANION_LIMIT_RULE`` setting, else the game system's
    ``companion_limit``. A rule that fails is logged and the system
    answers instead."""
    world = get_world()
    rule = world.setting("COMPANION_LIMIT_RULE")
    if rule:
        from realm.core.safe_eval import eval_expression
        from realm.scripting.namespace import build_namespace
        namespace, _frame = build_namespace(
            'rule', executor=character, enactor=character, location=character.location,
            subject=character, extra={"me": character, "level": _level(character)})
        try:
            return int(round(float(eval_expression(str(rule), namespace))))
        except Exception as exc:
            logger.warning(f"COMPANION_LIMIT_RULE {rule!r} failed for {character.name} "
                           f"({exc}); using the game system's companion_limit. Fix the "
                           f"rule in config.py.")
    return int(world.rules.companion_limit(character))


def bond_refusal(npc: GameObject, master: GameObject, *,
                 allow_player: bool = False) -> str | None:
    """Why ``npc`` cannot become ``master``'s companion, or None. ``npc``
    may also be a pet shop's stock, judged before it is copied."""
    if npc is master:
        return "You can't be your own companion."
    if npc.is_player and not allow_player:
        return f"{the(npc)} is a player, not a companion."
    if master_of(master) is npc:
        return f"{the(npc)} is your master."
    if master_of(npc) is master:
        return None
    diff = int(get_world().setting("COMPANION_LEVEL_DIFF") or 0)
    if diff > 0 and _level(npc) > _level(master) + diff:
        return f"{the(npc)} is too advanced for you."
    if follower_count(master) + 1 + follower_count(npc) > companion_limit(master):
        return "You can't accept any more followers."
    return None


# --- the data -------------------------------------------------------------------


def bind(npc: GameObject, master: GameObject) -> None:
    """Write the bond (no checks, no event): ``set_master`` and the
    ``charmed`` effect use it."""
    npc.db.set(MASTER_ATTR, master.id)
    set_following(npc, master)
    npc.add_tag(COMPANION_TAG)
    if not any(b.behavior_id == "companion" for b in npc.get_behaviors()):
        from realm.core.behaviors import BehaviorRegistry
        npc.add_behavior(BehaviorRegistry.create("companion"))


def unbind(npc: GameObject) -> GameObject | None:
    """Erase the bond (no event); the former master, if any. A ridden
    mount loses its rider."""
    from realm.std.companions.riding import clear_riding
    former_id = npc.db.get(MASTER_ATTR)
    former = _cached(former_id)
    clear_riding(npc)
    npc.db.delete(MASTER_ATTR)
    if former_id and npc.db.get(FOLLOWING_ATTR) == former_id:
        set_following(npc, None)
    npc.remove_tag(COMPANION_TAG)
    for behavior in npc.get_behaviors():
        if behavior.behavior_id == "companion":
            npc.remove_behavior(behavior)
    return former


async def set_master(npc: GameObject, master: GameObject | None, *,
                     how: str = "set", reason: str = "released",
                     check: bool = True) -> str | None:
    """Make ``npc`` ``master``'s companion, or release it (``master``
    None). Returns why it was refused (the limit, the level difference),
    else None. Fires ``companion:on_bond`` (``how`` it happened) or
    ``companion:on_release`` (the ``reason``), and saves ``npc``. A
    released creature's ``charmed`` effect ends with it."""
    store = get_world().store
    current = master_of(npc)
    if master is None:
        if current is None and not npc.db.get(MASTER_ATTR):
            return None
        former = unbind(npc)
        for behavior in npc.get_behaviors():
            if behavior.behavior_id == "charmed":
                npc.remove_behavior(behavior)
        await _return_if_waiting(npc, former)
        if store is not None:
            await store.save(npc)
        await fire_event(former, npc, "companion:on_release", extra={"reason": reason})
        return None
    if current is master:
        return None
    if check:
        refusal = bond_refusal(npc, master)
        if refusal:
            return refusal
    if current is not None:
        await set_master(npc, None, reason="rebonded")
    bind(npc, master)
    if store is not None:
        await store.save(npc)
    await fire_event(master, npc, "companion:on_bond", extra={"how": how})
    return None


# --- leaving and returning with the master ----------------------------------------


async def _return_if_waiting(npc: GameObject, master: GameObject | None) -> None:
    """A companion out of the world (its master logged out) comes back: to
    its master's room, else to where it waited."""
    room_id = npc.db.get(WAITING_ATTR)
    if not room_id:
        return
    npc.db.delete(WAITING_ATTR)
    if npc.location is not None:
        return
    room = master.location if master is not None and master.location is not None \
        else _cached(room_id)
    npc.location = room


async def leave_with(master: GameObject) -> None:
    """``master`` leaves play: a charmed creature is freed (CoffeeMud and
    ROM end a charm when the charmer quits); every other companion in the
    world is taken out of it, its room remembered."""
    world = get_world()
    combat = world.services.get("combat")
    for npc in companions_of(master):
        if npc.is_player or npc.location is None:
            continue
        if npc.has_tag("charmed"):
            await set_master(npc, None, reason="master_left")
            continue
        if combat is not None:
            combat.withdraw(npc)
        room = npc.location
        npc.db.set(WAITING_ATTR, room.id)
        npc.location = None
        if room is master.location:
            room.msg_contents(f"{the(npc)} goes with {master.name}.", exclude=[master])
        if world.store is not None:
            await world.store.save(npc)


async def return_with(master: GameObject) -> None:
    """``master`` enters play: its companions waiting out of the world
    come back beside it."""
    world = get_world()
    for npc in companions_of(master):
        if npc.location is not None or not npc.db.get(WAITING_ATTR):
            continue
        await _return_if_waiting(npc, master)
        if npc.location is not None and npc.location is master.location:
            npc.location.msg_contents(f"{the(npc)} is here with {master.name}.",
                                      exclude=[master])
        if world.store is not None:
            await world.store.save(npc)


async def release_orphans(store) -> int:
    """The reaper: a companion whose master no longer exists is released
    (and, if it was out of the world, put back where it waited)."""
    if store is None:
        return 0
    freed = 0
    for npc in list(store.find_cached(tag=COMPANION_TAG)):
        if master_of(npc) is None:
            await set_master(npc, None, reason="master_gone")
            freed += 1
    return freed


# --- pets and charms ---------------------------------------------------------------


async def buy_pet(buyer: GameObject, stock: GameObject) -> GameObject:
    """A copy of a pet shop's ``stock`` beside ``buyer``, bonded to it (the
    caller has checked ``bond_refusal`` and taken the money)."""
    from realm.core.ops.objects import clone
    pet = clone(None, stock, location=buyer.location).value
    pet.remove_tag("prototype")
    pet.db.delete(WAITING_ATTR)
    pet.db.delete(MASTER_ATTR)
    store = get_world().store
    if store is not None:
        await store.save(pet)
    await set_master(pet, buyer, how="bought", check=False)
    return pet


async def charm(caster: GameObject, target: GameObject, *, duration: int,
                turns_hostile: bool = False, level_check: bool = True) -> str | None:
    """Charm ``target`` (an ability's ``charm`` effect): it becomes
    ``caster``'s companion until the ``charmed`` effect ends. Returns why
    not, or None. A player can be charmed only where the zone allows
    player-versus-player (``zone_property(room, "pvp")``)."""
    from realm.core.behaviors import BehaviorRegistry
    from realm.core.zones import zone_property
    name = the(target)
    if target is caster:
        return "You like yourself even better!"
    if master_of(caster) is not None:
        return "You feel like taking, not giving, orders."
    if target.is_player and not zone_property(target.location, "pvp"):
        return f"{name} can't be charmed here."
    if master_of(target) is not None:
        return f"{name} already follows someone."
    if level_check and _level(target) > _level(caster):
        return f"{name} is too strong-willed for you."
    refusal = bond_refusal(target, caster, allow_player=True)
    if refusal:
        return refusal
    combat = get_world().services.get("combat")
    if combat is not None:
        combat.withdraw(target)
    await set_master(target, caster, how="charmed", check=False)
    target.add_behavior(BehaviorRegistry.create(
        "charmed", duration=max(1, int(duration)), source_id=caster.id,
        turns_hostile=bool(turns_hostile)))
    target.msg(f"Isn't {caster.name} just so nice?")
    caster.msg(f"{name} looks at you with adoring eyes.")
    store = get_world().store
    if store is not None:
        await store.save(target)
    return None


__all__ = [
    "BOND",
    "COMPANION_TAG",
    "MASTER_ATTR",
    "RELEASE",
    "WAITING_ATTR",
    "bind",
    "bond_refusal",
    "buy_pet",
    "charm",
    "companion_limit",
    "companions_of",
    "follower_count",
    "leave_with",
    "master_of",
    "release_orphans",
    "return_with",
    "set_master",
    "the",
    "unbind",
]
