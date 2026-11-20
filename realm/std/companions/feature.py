"""
The ``companions`` feature.

Pets, charmed followers and mounts (MUD_PLAN step 13), after CoffeeMud's
followers and ROM's pet shops and charm person. See
docs/guides/companions.md.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

from realm.core.action_tags import HOSTILE
from realm.core.action_types import ActionType
from realm.features import Feature
from realm.std.combat.actions import CombatAction
from realm.std.companions import riding, softcode
from realm.std.companions.behaviors import CharmedBehavior, CompanionBehavior
from realm.std.companions.commands import (
    cmd_companions,
    cmd_dismiss,
    cmd_dismount,
    cmd_mount,
    cmd_order,
)
from realm.std.companions.companions import (
    ACCOMPANIED,
    BOND,
    RELEASE,
    bond_refusal,
    buy_pet,
    charm,
    come_along,
    companions_of,
    leave_with,
    master_of,
    release_orphans,
    return_with,
    set_master,
    the,
)

logger = logging.getLogger(__name__)

feature = Feature(
    'companions',
    requires=['social', 'effects'],
    doc='Pets, charmed followers and mounts.',
)

feature.setting(
    "COMPANION_LIMIT_RULE", None,
    "How many followers a character may keep, as a rule expression (`me` the "
    "character, `level` its level), after CoffeeMud's FORMULA_MAXFOLLOW: "
    "`\"1 + (get_attr(me, 'charisma', 10) - 6) // 3\"`. None asks the game "
    "system's `companion_limit` (2; Merc: 1 + level // 10).")
feature.setting(
    "COMPANION_LEVEL_DIFF", 0,
    "A creature more than this many levels above a character cannot become its "
    "companion (CoffeeMud's FOLLOWLEVELDIFF). 0: no limit.")
feature.setting(
    "ORDER_REFUSED", [],
    "Command names `order` never runs as a companion, beyond the ones it always "
    "refuses (above `player` permission, `order`, `quit`).")
feature.setting(
    "MOUNTS_INDOORS", False,
    "Whether a rider may ride into a `sector:inside` room (a `no_mount` room is "
    "refused either way).")

feature.command('companions', cmd_companions, category='social',
                help_text='List your pets, charmed creatures and mounts',
                usage='companions')
feature.command('order', cmd_order, category='social',
                help_text='Order a companion to do something',
                usage='order <name|all> <command>')
feature.command('dismiss', cmd_dismiss, category='social',
                help_text='Release a companion', usage='dismiss <name>')
feature.command('mount', cmd_mount, aliases=['ride'], category='social',
                help_text='Climb onto your mount', usage='mount <name>')
feature.command('dismount', cmd_dismount, category='social',
                help_text='Get down from your mount', usage='dismount')

feature.behavior(CompanionBehavior)
feature.behavior(CharmedBehavior)

feature.traversal_gate(riding.riding_gate, reason="riding")
feature.after_traverse(riding.after_ride)
feature.move_describer(riding.describe_move)
feature.marker(riding.riding_marker)
feature.reaper(release_orphans)

feature.event(BOND, hook="BOND", doc="this creature became someone's companion "
              "(the master is `enactor`)",
              payload={"how": "bought, charmed, or set (softcode, a builder)"})
feature.event(RELEASE, hook="RELEASE", doc="this companion was freed (its former "
              "master, if any, is `enactor`)",
              payload={"reason": "dismissed, released, charm_ended, master_left, "
                                 "master_gone, attacked or rebonded"})

feature.softfn(softcode.master, group='NPCs & behaviors', readonly=True)
feature.softfn(softcode.companions, group='NPCs & behaviors', readonly=True)
feature.softfn(softcode.set_master, group='NPCs & behaviors')
feature.softfn(softcode.release, group='NPCs & behaviors')
feature.queue_kind("companion_bond", softcode.queued_bond)
feature.queue_kind("companion_release", softcode.queued_release)


async def companions_observer(action) -> None:
    """Companions leave and return with their master; come along when it
    is placed somewhere by a move tagged ``accompanied`` (recall); fight
    beside it; break with a master who turns on them; and a rider who goes
    down, or is moved without its mount, is off it."""
    kind = action.action_type
    actor, target = action.actor, action.target
    if kind == ActionType.DISCONNECT and actor is not None:
        await leave_with(actor)
    elif kind == ActionType.CONNECT and actor is not None:
        await return_with(actor)
    elif kind == CombatAction.ON_DEATH and target is not None:
        await _gone_down(target)
    elif kind == ActionType.ON_ENTER and actor is not None and "exit" not in action.extra:
        # Placed somewhere directly. Recall (``accompanied``) brings the
        # company along; any other placement (a teleport, a summons) moves
        # the mover alone, and a rider and mount left apart are parted.
        if ACCOMPANIED in action.tags:
            await come_along(actor, action.extra.get("from"), action.target, action.tags)
        mount, rider = riding.mount_of(actor), riding.rider_of(actor)
        if mount is not None and mount.location is not actor.location:
            await riding.dismount(actor, how="parted")
        elif rider is not None and rider.location is not actor.location:
            await riding.dismount(rider, how="parted")
    elif HOSTILE in action.tags and not action.blocked:
        await _fight_together(actor, target)


async def _gone_down(victim) -> None:
    """A rider or a mount went down (unconscious or dead): nobody rides on.
    (A dead companion leaves its master's list with its body: the corpse
    replaces it.)"""
    if riding.mount_of(victim) is not None:
        await riding.dismount(victim, how="fall")
    rider = riding.rider_of(victim)
    if rider is not None:
        await riding.dismount(rider, how="fall")


async def _fight_together(attacker, defender) -> None:
    """A master who attacks its own companion breaks the bond (CoffeeMud's
    charm ends so); otherwise each side's companions in the room join the
    fight against the other side."""
    if attacker is None or defender is None or attacker is defender:
        return
    if master_of(defender) is attacker:
        await set_master(defender, None, reason="attacked")
        return
    from realm.core.world import get_world
    combat = get_world().services.get("combat")
    if combat is None:
        return
    for side, enemy in ((attacker, defender), (defender, attacker)):
        if side.location is None:
            continue
        for npc in companions_of(side):
            if (npc is enemy or npc.location is not side.location
                    or npc.has_tag("unconscious") or master_of(enemy) is npc):
                continue
            if combat.assist(npc, enemy):
                side.location.msg_contents(
                    f"{the(npc)} leaps to {the(side, capital=False)}'s side!")


@feature.on_install
def _offer_companions(world) -> None:
    """``world.services["companions"]``: who leads whom, who pays for a
    rider's step, and pet shops' and charms' bonding, for ``combat``,
    ``economy``, ``abilities``, ``vitals``, ``needs`` and ``merc``. The
    observer is added here, after ``combat``'s, so a fight it starts
    already exists when companions join it."""
    world.services["companions"] = SimpleNamespace(
        master_of=master_of, companions_of=companions_of, payer=riding.payer,
        mount_of=riding.mount_of, dismount=riding.dismount,
        bond_refusal=bond_refusal, buy_pet=buy_pet, charm=charm)
    world.observe(companions_observer)


@feature.on_install
def _recall_with_company(world) -> None:
    """A recall's move is ``accompanied`` (ROM's ``do_recall`` takes the
    pet): ``basics``' ``recall`` service lists the tags its move carries.
    Install hooks run in feature order, so ``basics`` must come first."""
    recall = world.services.get("recall")
    if recall is not None:
        recall.tags.append(ACCOMPANIED)
    elif "basics" in world.features.names:
        logger.warning("companions is listed before basics in FEATURES, so a "
                       "recall leaves pets and mounts behind; list basics first.")

