"""
CombatManager: encounter lifecycle for the running server.

One encounter per room; joining a fight in a room merges into the
existing encounter. The combat feature creates it when the world is
built; code reaches it as ``get_world().services.get("combat")``.

It also observes propagation: any successful action tagged ``hostile``
between two combat-capable parties starts the fight, crediting the
initiating action as the initiator's first round (casting the fireball
WAS your turn).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from realm.core.behaviors import BehaviorRegistry
from realm.core.objects import GameObject as GameObjectCls
from realm.core.pools import damage_pool
from realm.core.propagation import Action, propagate
from realm.core.world import get_world
from realm.std.combat.actions import CombatAction
from realm.std.combat.encounter import CombatEncounter, deliver_combat_messages
from realm.std.combat.maneuver import QueuedAction
from realm.std.combat.strategy import select_strategy_action

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.propagation import Action
    from realm.gateway.session import SessionManager
    from realm.std.combat.system import CombatSystem

logger = logging.getLogger(__name__)


#: What ``handle_death`` does to a body, by ``obj.db.when_spent``.
WHEN_SPENT = ('unconscious', 'corpse', 'destroy', 'none')


def when_spent(obj: GameObject) -> str:
    """``obj.db.when_spent``, else today's rule by kind: a player falls
    unconscious, anything else leaves a corpse. Raises ValueError for an
    unknown rule, or for a player set to ``corpse`` or ``destroy``."""
    rule = obj.db.when_spent
    if rule is None:
        return 'unconscious' if obj.is_player else 'corpse'
    rule = str(rule).strip().lower()
    if rule not in WHEN_SPENT:
        raise ValueError(f"{obj.name}: when_spent must be one of "
                         f"{', '.join(WHEN_SPENT)}, not {obj.db.when_spent!r}")
    if obj.is_player and rule in ('corpse', 'destroy'):
        raise ValueError(f"{obj.name}: a player's when_spent may be unconscious "
                         f"or none, not {rule!r}")
    return rule


def is_combat_capable(obj: GameObject) -> bool:
    """Players and NPCs with a damage pool (hit points, by default) can fight."""
    if not (obj.is_player or obj.is_npc):
        return False
    if obj.has_tag('unconscious'):
        return False
    return damage_pool(obj) is not None


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

    # --- Death ---

    async def _propagate_death(self, victim: GameObject,
                               killer: GameObject | None, *, fatal: bool) -> None:
        """Announce a death to the world — the ONE place that happens.

        Fired *before* the body is transformed, because witnesses inspect
        the fallen: the bounty board reads the mark's name off the corpse-
        to-be, the arena recorder narrates it. ``_npc_death`` replaces the
        NPC with a corpse, so announcing afterwards would show an empty
        room.

        ``extra['killer']`` stays a NAME for compatibility with scripts
        written against the old swing-path event; the killer *object* is
        bound as ``actor``, and ``fatal`` says whether the body is gone (a
        corpse, or destroyed) or stays (unconscious, or ``none``).
        """

        action = Action(
            actor=killer,
            target=victim,
            action_type=CombatAction.ON_DEATH,
            extra={
                'killer': killer.name if killer is not None else None,
                'fatal': fatal,
            },
        )
        await propagate(action, deliver=False)

    async def handle_death(self, obj: GameObject,
                           killer: GameObject | None = None) -> None:
        """
        The one death path, whatever the cause (a swing, poison, a trap):
        combat's observer on ``pool:on_spent`` calls it when an object's
        vital pool is spent (``realm.std.combat.vitals``).

        ``obj.db.when_spent`` says what happens to the body (WHEN_SPENT):
        ``"unconscious"`` (tagged, in place, revivable; a player's
        default), ``"corpse"`` (a lootable corpse and a character-point
        award; an NPC's default), ``"destroy"`` (gone, its contents left
        in the room) or ``"none"`` (nothing: the object's own ``ON_SPENT``
        softcode decides). A player is never made a corpse or destroyed.

        It is also the one place ``combat:on_death`` is announced, before
        the body changes, for every rule.
        """
        rule = when_spent(obj)
        await self._propagate_death(obj, killer, fatal=rule in ('corpse', 'destroy'))
        if rule == 'unconscious':
            if not obj.has_tag('unconscious'):
                obj.add_tag('unconscious')
            obj.msg("Everything goes black...")
            if obj.location is not None:
                obj.location.msg_contents(
                    f"{obj.name} collapses, unconscious!", exclude=[obj],
                )
        elif rule == 'corpse':
            await self._npc_death(obj, killer)
        elif rule == 'destroy':
            await self._destroy(obj)

    async def _destroy(self, obj: GameObject) -> None:
        """The one destroy path (``ops.objects.destroy``): an exit unpairs,
        a player inside is evacuated, its other contents go with it. A
        ``safe`` object refuses (``Refused``)."""
        from realm.core.ops.objects import destroy
        room = obj.location
        if room is not None:
            room.msg_contents(f"{obj.name} is destroyed!", exclude=[obj])
        await destroy(None, obj, get_world().store)

    async def _npc_death(self, npc: GameObject, killer: GameObject | None) -> None:

        room = npc.location
        if room is not None:
            room.msg_contents(f"{npc.name} falls dead!", exclude=[npc])

        # The kill award: the game system says what the victim is worth
        # (character points, experience, or 0 for none), split across the
        # killer's party members present (solo killers keep the whole award).
        system = get_world().rules
        award = (system.death_award(npc, killer)
                 if killer is not None and killer.is_player else 0)
        if award > 0:
            from realm.core.zones import zone_property
            multiplier = zone_property(room, 'xp_multiplier', 1.0)
            award = max(1, round(award * float(multiplier)))
            # The party shares it when the world has ``social``.
            social = get_world().services.get("social")
            party = social.party_members(killer) if social is not None else [killer]
            sharers = [m for m in party
                       if m.is_player and not m.has_tag('unconscious')]
            if not sharers:
                sharers = [killer]
            share = max(1, award // len(sharers))
            for member in sharers:
                # The system decides how a reward lands: character points
                # (PointBuyMixin), XP and a level-up (MercSystem).
                system.grant_award(member, share)

        # Corpse: a container holding the fallen's belongings.
        corpse = GameObjectCls(name=f"corpse of {npc.name}",
                               tags=['thing', 'no_group', 'container'])
        corpse.db.article = "the"
        corpse.db.description = f"The lifeless body of {npc.name}."
        for item in list(npc.contents):
            item.location = corpse
        corpse.location = room

        # It rots away when the world has a ``decay`` behavior (``npc``).
        if BehaviorRegistry.get("decay") is not None:
            corpse.add_behavior(BehaviorRegistry.create("decay", ticks=150))

        persistence = get_world().store
        if persistence is not None:
            await persistence.save(corpse)
            npc.location = None
            await persistence.delete(npc)
        else:
            npc.location = None

    # --- Strategy seam (implemented in the strategies phase) ---

    def strategy_action(self, encounter, participant, *,
                        override_only: bool = False) -> QueuedAction | None:
        return select_strategy_action(encounter, participant,
                                      override_only=override_only)


# Ambient accessor (set by GameServer, same pattern as persistence).
__all__ = [
    "WHEN_SPENT",
    "CombatManager",
    "deliver_combat_messages",
    "is_combat_capable",
    "when_spent",
]
