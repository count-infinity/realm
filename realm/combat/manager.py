"""
CombatManager: encounter lifecycle for the running server.

One encounter per room; joining a fight in a room merges into the
existing encounter. The manager is owned by GameServer (like the script
engine) and exposed ambiently for behaviors (same pattern as the
propagation-engine and persistence singletons).

It also observes propagation: any successful action tagged ``hostile``
between two combat-capable parties starts the fight, crediting the
initiating action as the initiator's first round (casting the fireball
WAS your turn).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from realm.combat.encounter import CombatEncounter, deliver_combat_messages
from realm.combat.maneuver import QueuedAction

if TYPE_CHECKING:
    from realm.combat.system import CombatSystem
    from realm.core.objects import GameObject
    from realm.core.propagation import Action
    from realm.gateway.session import SessionManager

logger = logging.getLogger(__name__)


def is_combat_capable(obj: GameObject) -> bool:
    """Things with hit points can fight: players and statted NPCs."""
    if not (obj.has_tag('player') or obj.has_tag('npc')):
        return False
    if obj.has_tag('unconscious'):
        return False
    return obj.db.get('max_hp') is not None or obj.db.get('hp') is not None


class CombatManager:
    """Creates, merges, and ends combat encounters."""

    def __init__(
        self,
        combat_system: CombatSystem,
        *,
        beat_min: float = 4.0,
        beat_max: float = 120.0,
        beat_default: float = 15.0,
        session_manager: SessionManager | None = None,
    ):
        self.combat_system = combat_system
        self.beat_min = beat_min
        self.beat_max = beat_max
        self.beat_default = beat_default
        self.session_manager = session_manager
        self._encounters: dict[str, CombatEncounter] = {}  # room_id -> encounter

    # --- Lookup ---

    def encounter_in(self, room: GameObject | None) -> CombatEncounter | None:
        if room is None:
            return None
        return self._encounters.get(room.id)

    def encounter_of(self, obj: GameObject) -> CombatEncounter | None:
        encounter = self.encounter_in(obj.location)
        if encounter is not None and encounter.get(obj.id) is not None:
            return encounter
        return None

    # --- Lifecycle ---

    async def initiate(
        self,
        attacker: GameObject,
        defender: GameObject,
        *,
        already_acted: bool = False,
    ) -> CombatEncounter | None:
        """
        Start (or join) the fight between attacker and defender.

        The defender auto-joins targeting the attacker — retaliation
        lives on the defended side. Returns None if either party can't
        fight.
        """
        room = attacker.location
        if room is None or defender.location is not room:
            return None
        if not is_combat_capable(attacker) or not is_combat_capable(defender):
            return None

        encounter = self._encounters.get(room.id)
        if encounter is None:
            encounter = CombatEncounter(self, room)
            self._encounters[room.id] = encounter

        encounter.add(attacker, target=defender, already_acted=already_acted)
        encounter.add(defender, target=attacker)
        return encounter

    def encounter_ended(self, encounter: CombatEncounter) -> None:
        current = self._encounters.get(encounter.room.id)
        if current is encounter:
            del self._encounters[encounter.room.id]
        logger.info(f"Combat ended in {encounter.room.name} "
                    f"after {encounter.round_number} round(s)")

    def stop_all(self) -> None:
        for encounter in list(self._encounters.values()):
            encounter.end()
        self._encounters.clear()

    async def flush_sessions(self) -> None:
        """Push NPC/beat output to players between commands."""
        if self.session_manager is None:
            return
        for session in self.session_manager.all_sessions():
            try:
                await session.flush_output()
            except Exception:
                logger.exception("Combat flush error")

    # --- Hostile-action auto-combat (propagation observer) ---

    async def hostile_observer(self, action: Action) -> None:
        """
        Any successful hostile action between combat-capable parties in
        the same room starts combat — the initiator's action counts as
        their first-round move (already_acted).
        """
        if action.blocked:
            return
        if "hostile" not in action.tags:
            return
        attacker, defender = action.actor, action.target
        if attacker is None or defender is None or attacker is defender:
            return
        if attacker.location is None or attacker.location is not defender.location:
            return
        if not is_combat_capable(attacker) or not is_combat_capable(defender):
            return
        existing = self.encounter_in(attacker.location)
        if existing is not None and existing.get(attacker.id) and existing.get(defender.id):
            return  # already fighting
        await self.initiate(attacker, defender, already_acted=True)

    # --- Defeat ---

    async def handle_defeat(self, encounter, participant, killer=None) -> None:
        """Defeat inside an encounter: remove, then the shared death path."""
        obj = participant.obj
        encounter.remove(obj.id, make_peace=False)
        await self.handle_death(obj, killer.obj if killer else None)

    async def _propagate_death(self, victim: GameObject,
                               killer: GameObject | None) -> None:
        """Announce a death to the world — the ONE place that happens.

        Fired *before* the body is transformed, because witnesses inspect
        the fallen: the bounty board reads the mark's name off the corpse-
        to-be, the arena recorder narrates it. ``_npc_death`` replaces the
        NPC with a corpse, so announcing afterwards would show an empty
        room.

        ``extra['killer']`` stays a NAME for compatibility with scripts
        written against the old swing-path event; the killer *object* is
        bound as ``actor``, and ``fatal`` distinguishes a real death (an
        NPC, now a corpse) from a player knocked unconscious in place.
        """
        from realm.core.propagation import Action, propagate

        action = Action(
            actor=killer,
            target=victim,
            action_type="combat:on_death",
            extra={
                'killer': killer.name if killer is not None else None,
                'fatal': not victim.has_tag('player'),
            },
        )
        await propagate(action, deliver=False)

    async def handle_death(self, obj: GameObject,
                           killer: GameObject | None = None) -> None:
        """
        The one death path, whatever the cause (a swing, poison, a trap):
        players fall unconscious in place, revivable; NPCs die into
        lootable corpses.

        It is also the one place ``combat:on_death`` is announced. It used
        not to be: the event fired inside ``CombatSystem.attack`` — the
        *swing* path only — so an NPC killed by softcode ``damage()``, a
        poison tick or a trap died in silence, and a player going down
        emitted nothing at all. Bounty boards, arena recorders and clone
        bays had to poll. Every route into death comes through here, so
        this is where the world gets told.
        """
        await self._propagate_death(obj, killer)
        if obj.has_tag('player'):
            if not obj.has_tag('unconscious'):
                obj.add_tag('unconscious')
            obj.msg("Everything goes black...")
            if obj.location is not None:
                obj.location.msg_contents(
                    f"{obj.name} collapses, unconscious!", exclude=[obj],
                )
        else:
            await self._npc_death(obj, killer)

    async def _npc_death(self, npc: GameObject, killer: GameObject | None) -> None:
        from realm.persistence.manager import get_active_manager

        room = npc.location
        if room is not None:
            room.msg_contents(f"{npc.name} falls dead!", exclude=[npc])

        # Character-point award: the victim's worth (db.points, GURPS-ish)
        # scaled down, split across the killer's party members present
        # (solo killers keep the whole award).
        if killer is not None and killer.has_tag('player'):
            from realm.core.party import party_members
            from realm.systems.base import get_game_system
            system = get_game_system()
            award = (system.death_award(npc) if system
                     else max(1, int(npc.db.get('points') or 10) // 10))
            from realm.core.zones import zone_property
            multiplier = zone_property(room, 'xp_multiplier', 1.0)
            award = max(1, round(award * float(multiplier)))
            sharers = [m for m in party_members(killer)
                       if m.has_tag('player') and not m.has_tag('unconscious')]
            if not sharers:
                sharers = [killer]
            share = max(1, award // len(sharers))
            for member in sharers:
                member.db.character_points = \
                    int(member.db.get('character_points') or 0) + share
                member.msg(f"You gain {share} character point"
                           f"{'s' if share != 1 else ''}.")

        # Corpse: a container holding the fallen's belongings.
        from realm.core.objects import GameObject as GameObjectCls
        corpse = GameObjectCls(name=f"corpse of {npc.name}", tags=['thing', 'no_group'])
        corpse.db.container = True
        corpse.db.article = "the"
        corpse.db.description = f"The lifeless body of {npc.name}."
        for item in list(npc.contents):
            item.location = corpse
        corpse.location = room

        from realm.behaviors.decay import DecayBehavior
        corpse.add_behavior(DecayBehavior(ticks=150))

        persistence = get_active_manager()
        if persistence is not None:
            await persistence.save(corpse)
            npc.location = None
            await persistence.delete(npc)
        else:
            npc.location = None

    # --- Strategy seam (implemented in the strategies phase) ---

    def strategy_action(self, encounter, participant, *,
                        override_only: bool = False) -> QueuedAction | None:
        from realm.combat.strategy import select_strategy_action
        return select_strategy_action(encounter, participant,
                                      override_only=override_only)


# Ambient accessor (set by GameServer, same pattern as persistence).
_active_manager: CombatManager | None = None


def set_combat_manager(manager: CombatManager | None) -> None:
    global _active_manager
    _active_manager = manager


def get_combat_manager() -> CombatManager | None:
    return _active_manager


__all__ = [
    "CombatManager",
    "deliver_combat_messages",
    "is_combat_capable",
    "set_combat_manager",
    "get_combat_manager",
]
