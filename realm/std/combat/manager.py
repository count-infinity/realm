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
from realm.std.combat.loot import loot_corpse
from realm.std.combat.maneuver import QueuedAction
from realm.std.combat.strategy import select_strategy_action

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.propagation import Action
    from realm.gateway.session import SessionManager
    from realm.std.combat.system import CombatSystem

logger = logging.getLogger(__name__)


#: What ``handle_death`` does to a body, by ``obj.db.when_spent``.
WHEN_SPENT = ('unconscious', 'corpse', 'destroy', 'none', 'respawn')

#: The rules a player may have (``PLAYER_DEATH`` picks the default).
PLAYER_RULES = ('unconscious', 'none', 'respawn')


def when_spent(obj: GameObject) -> str:
    """``obj.db.when_spent``, else the default by kind: a player follows
    the ``PLAYER_DEATH`` setting (``respawn`` unless set), anything else
    leaves a corpse. Raises ValueError for an unknown rule, for a player set
    to ``corpse`` or ``destroy``, or for anything but a player set to
    ``respawn``."""
    rule = obj.db.when_spent
    where = "when_spent"
    if rule is None:
        if not obj.is_player:
            return 'corpse'
        from realm.core.world import find_world
        world = find_world()
        rule = world.setting("PLAYER_DEATH", "respawn") if world is not None \
            else "respawn"
        where = "PLAYER_DEATH"
    shown = rule
    rule = str(rule).strip().lower()
    if rule not in WHEN_SPENT:
        raise ValueError(f"{obj.name}: {where} must be one of "
                         f"{', '.join(WHEN_SPENT)}, not {shown!r}")
    if obj.is_player and rule not in PLAYER_RULES:
        raise ValueError(f"{obj.name}: a player's {where} may be "
                         f"{', '.join(PLAYER_RULES)}, not {rule!r}")
    if not obj.is_player and rule == 'respawn':
        raise ValueError(f"{obj.name}: when_spent 'respawn' is for players only")
    return rule


def _barely_alive(obj: GameObject, name: str) -> int:
    """The value one point short of spent for ``obj``'s pool ``name``: what
    a respawned player wakes with (1 hit point). An ``up`` pool (a harm
    clock) is one below its max; a ``down`` pool one above ``spent_at``."""
    from realm.core.pools import pool_def, pool_max
    pool = pool_def(obj, name)
    if pool is not None and pool.direction == "up":
        maximum = pool_max(obj, name)
        return max(int(maximum or 1) - 1, int(pool.floor or 0))
    return (pool.spent_at if pool is not None else 0) + 1


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

    # --- Turning a fight (rescue, disarm) ---

    def attackers_of(self, target: GameObject) -> list[GameObject]:
        """Who in ``target``'s fight is attacking it."""
        encounter = self.encounter_of(target)
        if encounter is None:
            return []
        return [p.obj for p in encounter.participants.values()
                if p.target_id == target.id and p.obj is not target]

    def target_of(self, attacker: GameObject) -> GameObject | None:
        """Whom ``attacker`` is fighting, or None out of a fight."""
        encounter = self.encounter_of(attacker)
        participant = encounter.get(attacker.id) if encounter is not None else None
        if participant is None or participant.target_id is None:
            return None
        target = encounter.get(participant.target_id)
        return target.obj if target is not None else None

    def withdraw(self, obj: GameObject) -> None:
        """Take ``obj`` out of its fight at once, wherever it is now (it may
        already have left the room: ``recall``); the others fight on, or
        the fight ends at its next beat."""
        for encounter in list(self._encounters.values()):
            if encounter.get(obj.id) is not None:
                encounter.remove(obj.id)

    def retarget(self, attacker: GameObject, new_target: GameObject) -> bool:
        """Turn ``attacker`` on ``new_target`` (a rescue). The new target
        joins the fight against the attacker if it was not in it. False
        when the attacker is not fighting here or the target cannot fight."""
        encounter = self.encounter_of(attacker)
        if encounter is None or new_target.location is not attacker.location:
            return False
        if encounter.get(new_target.id) is None:
            if not is_combat_capable(new_target):
                return False
            encounter.add(new_target, target=attacker)
        encounter.get(attacker.id).target_id = new_target.id
        return True

    def assist(self, helper: GameObject, target: GameObject) -> bool:
        """Bring ``helper`` into the fight ``target`` is in, attacking it
        (a companion beside its master). Nobody else changes target. False
        when ``target`` is not fighting here, ``helper`` already is, or
        ``helper`` cannot fight."""
        encounter = self.encounter_of(target)
        if (encounter is None or helper.location is not target.location
                or encounter.get(helper.id) is not None
                or not is_combat_capable(helper)):
            return False
        encounter.add(helper, target=target)
        return True

    def disarm(self, target: GameObject) -> GameObject | None:
        """Knock ``target``'s wielded weapon to the floor; the weapon, or None."""
        weapon = next((o for o in target.contents if o.has_tag('wielded')), None)
        if weapon is None or target.location is None:
            return None
        weapon.remove_tag('wielded')
        weapon.location = target.location
        target.msg(f"{weapon.name} flies from your hand!")
        target.location.msg_contents(f"{weapon.name} flies from {target.name}'s hand!",
                                     exclude=[target])
        return weapon

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
        ``"unconscious"`` (tagged, in place, revivable), ``"corpse"`` (a
        lootable corpse and a kill award; an NPC's default), ``"destroy"``
        (gone, its contents left in the room), ``"none"`` (nothing: the
        object's own ``ON_SPENT`` softcode decides) or ``"respawn"`` (a
        player only, and a player's default unless ``PLAYER_DEATH`` says
        otherwise: a corpse of their belongings stays, the player returns
        home at 1 point; no kill award). A player is never made a
        corpse or destroyed.

        It is also the one place ``combat:on_death`` is announced, before
        the body changes, for every rule.
        """
        rule = when_spent(obj)
        await self._propagate_death(obj, killer,
                                    fatal=rule in ('corpse', 'destroy', 'respawn'))
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
        elif rule == 'respawn':
            await self._respawn(obj, killer)

    async def _respawn(self, player: GameObject, killer: GameObject | None) -> None:
        """A player's death under ``respawn``: leave a corpse of their
        belongings, pay the rules' penalty, and return home one point short
        of spent (1 hit point)."""
        from realm.core.pools import set_pool, vital_pool
        from realm.core.teardown import start_room_floor
        from realm.std.combat.corpses import leave_player_corpse

        world = get_world()
        room = player.location
        player.msg("You have been KILLED!!")
        if room is not None:
            room.msg_contents(f"{player.name} is dead!", exclude=[player])

        encounter = self.encounter_of(player)
        if encounter is not None:
            encounter.remove(player.id)
        if room is not None:
            await leave_player_corpse(player, room, store=world.store,
                                      lock_seconds=world.setting("CORPSE_LOCK_SECONDS"))
        world.rules.on_death(player, killer)

        name = vital_pool(player)
        if name is not None:
            set_pool(player, name, _barely_alive(player, name))
        for tag in ('in_combat', 'unconscious', 'resting', 'sleeping'):
            player.remove_tag(tag)
        effects = world.services.get("effects")
        if effects is not None:
            effects.clear(player)
        vitals = world.services.get("vitals")
        if vitals is not None:
            vitals.track(player)

        home = (world.store.get_cached(str(player.db.home))
                if world.store is not None and player.db.home else None)
        home = home or world.startup_room or start_room_floor()
        if home is not None:
            player.location = home
            home.msg_contents(f"{player.name} appears, pale and shaken.",
                              exclude=[player])
            render = world.services.get("look")
            player.msg(render.render_room(home, player, arrival=True) if render is not None
                       else home.name)
        if world.store is not None:
            await world.store.save(player)

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
        # (character points, experience, or 0 for none) and how it divides
        # among the killer's party members present (solo killers keep the
        # whole award); then each of them sees the kill (Merc: alignment).
        world = get_world()
        system = world.rules
        sharers: list[GameObject] = []
        # A companion's kill is its master's (``companions``); the death
        # event above still named the companion.
        credited = killer
        companions = world.services.get("companions")
        if killer is not None and not killer.is_player and companions is not None:
            credited = companions.master_of(killer) or killer
        if credited is not None and credited.is_player:
            # The party is the killer's when the world has ``social``.
            social = world.services.get("social")
            party = social.party_members(credited) if social is not None else [credited]
            sharers = [m for m in party
                       if m.is_player and not m.has_tag('unconscious')] or [credited]
        award = system.death_award(npc, credited) if sharers else 0
        if award > 0:
            from realm.core.zones import zone_property
            multiplier = zone_property(room, 'xp_multiplier', 1.0)
            award = max(1, round(award * float(multiplier)))
            from realm.std.rules.system import award as pay_award
            for member, share in system.share_award(award, sharers):
                # Through the rules' award filters (``needs``: hungry) to the
                # system, which decides how it lands: character points
                # (PointBuyMixin), XP and a level-up (MercSystem).
                pay_award(member, share)
        for member in sharers:
            system.on_kill(member, npc)

        # Corpse: a container holding the fallen's belongings and money.
        corpse = GameObjectCls(name=f"corpse of {npc.name}",
                               tags=['thing', 'no_group', 'container'])
        corpse.db.article = "the"
        corpse.db.description = f"The lifeless body of {npc.name}."
        for item in list(npc.contents):
            item.location = corpse
        economy = world.services.get("economy")
        if economy is not None and economy.get_credits(npc) > 0:
            economy.transfer_credits(npc, corpse, economy.get_credits(npc))
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
        if killer is not None and killer.is_player and killer.location is room:
            await loot_corpse(killer, corpse)

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
