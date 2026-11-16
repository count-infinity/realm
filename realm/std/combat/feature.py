"""
The ``combat`` feature.

Beat-driven combat encounters, combat AI and damage.
"""

from __future__ import annotations

from realm.features import Feature
from realm.std.combat import softcode
from realm.std.combat.actions import CombatAction
from realm.std.combat.behaviors import (
    AggressiveBehavior,
    CombatantBehavior,
    DefensiveBehavior,
    FleeingBehavior,
    HealerBehavior,
    VenomousBehavior,
)
from realm.std.combat.commands import (
    cmd_attack,
    cmd_combat_default,
    cmd_combat_status,
    cmd_defend,
    cmd_firstaid,
    cmd_flee,
    cmd_pace,
    cmd_queue,
    cmd_rolls,
    cmd_wimpy,
)
from realm.std.combat.corpses import CorpseClaimBehavior

feature = Feature(
    'combat',
    requires=['rules', 'items'],
    doc='Beat-driven combat encounters, combat AI and damage.',
)

feature.command(
    'attack',
    cmd_attack,
    aliases=['kill', 'att'],
    category='combat',
    help_text='Attack someone (starts combat)',
    usage='attack <target>',
)
feature.command(
    'queue',
    cmd_queue,
    aliases=['q'],
    category='combat',
    help_text='Choose your next combat action',
    usage='queue <maneuver> [target]',
)
feature.command('defend', cmd_defend, category='combat', help_text='Fight defensively next beat')
feature.command(
    'flee',
    cmd_flee,
    category='combat',
    help_text='Try to escape combat',
    usage='flee [direction]',
)
feature.command(
    'combat',
    cmd_combat_status,
    aliases=['cstat'],
    category='combat',
    help_text='Show the current fight',
)
feature.command(
    'pace',
    cmd_pace,
    category='combat',
    help_text='Set your combat beat (seconds)',
    usage='pace <seconds>',
)
feature.command(
    'combatdefault',
    cmd_combat_default,
    category='combat',
    help_text='Default action when a beat fires unqueued',
    usage='combatdefault <attack|defend|repeat|nothing>',
)
feature.command(
    'wimpy',
    cmd_wimpy,
    category='combat',
    help_text='Auto-flee below an HP percentage',
    usage='wimpy <percent>|off',
)
feature.command(
    'showrolls',
    cmd_rolls,
    category='combat',
    help_text='Show or hide dice-roll detail in combat',
    usage='showrolls [on|off]',
)
feature.command(
    'firstaid',
    cmd_firstaid,
    aliases=['aid'],
    category='combat',
    help_text='Tend wounds (First Aid skill)',
    usage='firstaid [target]',
)

for _cls in (AggressiveBehavior, DefensiveBehavior, FleeingBehavior, HealerBehavior,
             CombatantBehavior, VenomousBehavior, CorpseClaimBehavior):
    feature.behavior(_cls)

feature.setting(
    "COMBAT_RULESET", None,
    "Combat ruleset name. Unset, the game system picks its own; set it only to "
    "mix systems on purpose.")
feature.setting(
    "SHOW_ROLLS", False,
    "Show dice detail on combat messages. Players override with `showrolls on|off`.")
feature.setting("COMBAT_BEAT_MIN", 4.0, "Shortest combat round, in seconds.")
feature.setting("COMBAT_BEAT_MAX", 120.0, "Longest combat round, in seconds.")
feature.setting("COMBAT_BEAT_DEFAULT", 15.0, "Default combat round, in seconds.")
feature.setting(
    "PLAYER_DEATH", "unconscious",
    "What happens to a player whose vital pool is spent, unless the player sets "
    "`when_spent`: `unconscious` (falls where they are and comes round as they "
    "heal) or `respawn` (leaves a corpse of their belongings and returns home at 1 "
    "point, paying the game system's `on_death` penalty).")
feature.setting(
    "CORPSE_LOCK_SECONDS", 300,
    "Under `respawn`, how long only the dead player (and admins) may take from "
    "their corpse. 0 leaves it open to anyone.")


@feature.on_install
def _offer_damage(world) -> None:
    """Other features deal typed damage through ``world.services["damage"]``
    (``apply_resisted``, ``deal_damage``) when ``combat`` is in the world."""
    from realm.std.combat import damage
    world.services["damage"] = damage


@feature.on_install
def _start_combat(world) -> None:
    """Create the CombatManager. The ruleset is COMBAT_RULESET, else the
    game system's own pairing; hostile actions between combat-capable
    parties then start a fight (the fireball WAS your turn)."""
    from realm.std.combat.manager import CombatManager
    from realm.std.combat.system import create_combat_system

    manager = CombatManager(
        create_combat_system(world.setting("COMBAT_RULESET") or world.rules.ruleset_name),
        beat_min=world.setting("COMBAT_BEAT_MIN"),
        beat_max=world.setting("COMBAT_BEAT_MAX"),
        beat_default=world.setting("COMBAT_BEAT_DEFAULT"),
        session_manager=world.sessions,
    )
    world.services["combat"] = manager
    world.add_closer(manager.stop_all)
    world.observe(manager.hostile_observer)


@feature.on_install
def _watch_vital_pools(world) -> None:
    """Death, ``ON_HITPRCNT`` and coming round follow the vital pool,
    whatever moved it (``realm.std.combat.vitals``)."""
    from realm.std.combat.vitals import death_observer, revive_observer, threshold_observer
    world.observe(death_observer)
    world.observe(threshold_observer)
    world.observe(revive_observer)


@feature.on_boot
async def _scrub_stale_combat_state(world) -> None:
    """Encounters do not survive a reboot, but the ``in_combat`` tag does.
    Clear it (and any queued action) so creatures saved mid-fight rejoin
    the ambient beat and can move and be engaged again."""
    import logging
    for obj in list(world.store.find_cached(tag='in_combat')):
        obj.remove_tag('in_combat')
        if obj.db.get('combat_queued') is not None:
            obj.db.combat_queued = None
        await world.store.save(obj)
        logging.getLogger(__name__).info(
            f"Cleared stale in_combat on {obj.name} (no encounter survives reboot)")


async def _start(engine, frame, obj, target) -> None:
    """Queued by softcode start_combat()."""
    from realm.core.world import get_world
    manager = get_world().services.get("combat")
    if manager is not None:
        await manager.initiate(obj, target)


feature.queue_kind("combat", _start)


# --- events -------------------------------------------------------------------


feature.event(CombatAction.ON_ATTACK, hook="ATTACK", doc="this object attacks or is attacked",
              payload={"weapon": "the weapon used", "attacker_hp": "the attacker's HP",
                       "defender_hp": "the defender's HP"})
feature.event(CombatAction.ON_DAMAGE, hook="DAMAGE", doc="this object takes damage",
              payload={"damage": "the amount (a ward may lower it)",
                       "damage_types": "amount per damage type"})
feature.event(CombatAction.ON_DEATH, hook="DEATH",
              doc=("this object goes down: its vital pool is spent, by any cause (a "
                   "swing, poison, a trap, softcode damage). `adata('fatal')` is True "
                   "when the body is gone (a corpse, or destroyed), False when it stays "
                   "(unconscious, or `when_spent` is none)"),
              payload={"killer": "the killer's name (the killer object is actor)",
                       "fatal": "True when the body is gone"})
feature.event(CombatAction.ON_HITPRCNT, hook="HITPRCNT",
              doc=("the vital pool (HP) fell through this object's db.hitprcnt "
                   "threshold, from any source: a swing, poison, a trap, softcode"),
              payload={"percent": "HP percent now", "threshold": "the crossed threshold"})
feature.event(CombatAction.NARRATE, doc="combat narration")


# --- softcode ------------------------------------------------------------------

feature.softfn(softcode.damage, group='Combat & effects', harm=True)
feature.softfn(softcode.heal, group='Combat & effects')
feature.softfn(softcode.start_combat, group='Combat & effects')


@feature.traversal_gate(reason="combat")
async def _held_by_the_fight(actor, exit_obj, direction, *, fleeing):
    """Mid-combat, leaving the room takes a flee attempt (``fleeing``); the
    unconscious go nowhere."""
    if actor.has_tag('unconscious'):
        return "You are unconscious."
    if actor.has_tag('in_combat') and not fleeing:
        return "You're in the middle of combat — flee to escape!"
    return None

