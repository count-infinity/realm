"""
Combat encounters: beats, queues, and membership.

An encounter is one fight in one room. It advances on a **beat** — the
decision window (server-clamped, derived from the slowest player's
``db.combat_beat`` preference). During the window every participant may
queue a maneuver, freely replacing it; when the beat fires, all queued
actions resolve in initiative order (fixed per encounter, rolled at
join). Participants with nothing queued fall back to their
``db.combat_default`` policy (attack | defend | repeat | nothing).

The encounter is ruleset-agnostic: it owns time, membership, queues and
message delivery; every swing resolves through the CombatSystem and its
Ruleset. Encounters are runtime-only — a reboot ends fights (HP and
tags persist normally).

Combat state on objects is lean tags/attributes, softcode-inspectable:
``in_combat`` tag while enrolled (movement requires flee),
``unconscious`` tag on defeated players, ``db.combat_beat`` /
``db.combat_default`` preferences, ``db.combat_queued`` mirror of the
pending action.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from realm.core.beats import deliver_beat
from realm.core.movement import (
    has_dest_resolver,
    has_private_dest_resolver,
    move_through_exit,
    resolve_exit_destination,
)
from realm.core.pools import settle
from realm.core.propagation import Action, deliver_messages
from realm.core.search import match_objects
from realm.std.combat.actions import CombatAction
from realm.std.combat.combatant import Combatant, CombatState, get_combatant
from realm.std.combat.maneuver import QueuedAction
from realm.std.combat.system import CombatResult, find_wielded
from realm.std.rules.checks import check

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.std.combat.manager import CombatManager

logger = logging.getLogger(__name__)

#: The longest the beat loop sleeps between looks at the clock, in real
#: seconds, so a ``pace`` change or a moved clock is noticed promptly.
POLL_SECONDS = 0.5


def now() -> float:
    """The clock beats are kept on (seconds, monotonic): when a round is
    due, and how long until it is (tests replace it)."""
    return time.monotonic()


class Participant:
    """One combatant's encounter-local state."""

    __slots__ = ('obj', 'queued', 'last_action', 'initiative',
                 'target_id', 'joined_round', 'round_modifiers',
                 'next_round_modifiers', 'range_band', 'aim_bonus',
                 'aim_target', 'in_cover')

    def __init__(self, obj: GameObject, initiative: int, target_id: str | None):
        self.obj = obj
        self.queued: QueuedAction | None = None
        self.last_action: QueuedAction | None = None
        self.initiative = initiative
        self.target_id = target_id
        self.joined_round = 0
        # (stat, amount) modifiers to revert at the next round start
        self.round_modifiers: list[tuple[str, int]] = []
        # Modifiers that take effect NEXT round (a feint's opening)
        self.next_round_modifiers: list[tuple[str, int]] = []
        # Ranged model: band 0 = engaged (melee reach), 1 = at range.
        self.range_band = 0
        self.aim_bonus = 0
        self.aim_target: str | None = None
        self.in_cover = False

    @property
    def combatant(self) -> Combatant:
        return get_combatant(self.obj)

    def is_player(self) -> bool:
        return self.obj.is_player


def deliver_combat_messages(
    attacker: GameObject | None,
    defender: GameObject | None,
    messages: dict[str, str],
) -> None:
    """
    Deliver a swing's attacker/defender/others messages through the
    normal delivery path — per-looker perception applies, so an unseen
    attacker narrates as "Someone".
    """
    action = Action(actor=attacker, target=defender, action_type=CombatAction.NARRATE)
    if messages.get('attacker_msg'):
        action.add_message("actor", messages['attacker_msg'])
    if messages.get('defender_msg'):
        action.add_message("target", messages['defender_msg'])
    if messages.get('others_msg'):
        action.add_message("room", messages['others_msg'])
    deliver_messages(action)


class CombatEncounter:
    """A single fight in a single room, advancing on its own beat."""

    def __init__(self, manager: CombatManager, room: GameObject):
        self.manager = manager
        self.room = room
        self.combat_system = manager.combat_system
        self.round_number = 0
        self.participants: dict[str, Participant] = {}
        self.beat_seconds: float = manager.beat_default
        self._task: asyncio.Task | None = None
        self._next_fire: float = 0.0
        self._resolving = False
        self._over = False

    # --- Membership ---

    def add(
        self,
        obj: GameObject,
        *,
        target: GameObject | None = None,
        already_acted: bool = False,
    ) -> Participant:
        """
        Enroll a combatant. ``already_acted`` credits the joining action
        (the fireball that started the fight WAS their first move).
        """
        existing = self.participants.get(obj.id)
        if existing is not None:
            if target is not None:
                existing.target_id = target.id
            return existing

        combatant = get_combatant(obj)
        initiative = self.combat_system.ruleset.roll_initiative(combatant).total
        participant = Participant(obj, initiative, target.id if target else None)
        participant.joined_round = self.round_number
        if already_acted:
            participant.last_action = QueuedAction(
                maneuver="attack", target_id=target.id if target else None,
            )
        self.participants[obj.id] = participant

        combatant.state = CombatState.COMBAT
        obj.add_tag('in_combat')
        self._recompute_beat()
        self._ensure_running()
        return participant

    def remove(self, obj_id: str, *, make_peace: bool = True) -> None:
        participant = self.participants.pop(obj_id, None)
        if participant is None:
            return
        obj = participant.obj
        obj.remove_tag('in_combat')
        obj.db.combat_queued = None
        if make_peace:
            combatant = get_combatant(obj)
            if combatant.state == CombatState.COMBAT:
                combatant.state = CombatState.IDLE
            combatant.target = None
            combatant.clear_modifiers()
        # Anyone targeting the departed retargets next round.
        for other in self.participants.values():
            if other.target_id == obj_id:
                other.target_id = None
        self._recompute_beat()

    def get(self, obj_id: str) -> Participant | None:
        return self.participants.get(obj_id)

    # --- Queueing ---

    def queue(self, obj: GameObject, action: QueuedAction) -> None:
        """Set/replace what fires on the next beat."""
        participant = self.participants.get(obj.id)
        if participant is None:
            raise ValueError(f"{obj.name} is not in this encounter")
        participant.queued = action
        # Softcode-inspectable mirror
        obj.db.combat_queued = [action.maneuver, action.target_id, action.args]

    # --- Pacing ---

    def _recompute_beat(self) -> None:
        """Slowest player's preference wins, clamped to server bounds."""
        prefs = []
        for participant in self.participants.values():
            if participant.is_player():
                pref = participant.obj.db.get('combat_beat')
                if pref is not None:
                    prefs.append(float(pref))
        beat = max(prefs) if prefs else self.manager.beat_default
        self.beat_seconds = max(self.manager.beat_min,
                                min(self.manager.beat_max, beat))

    @property
    def seconds_to_beat(self) -> float:
        return max(0.0, self._next_fire - now())

    # --- The beat loop ---

    def _ensure_running(self) -> None:
        if self._over:
            return
        if self._task is None or self._task.done():
            self._next_fire = now() + self.beat_seconds
            self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        """The beat loop: sleep (real time, at most ``POLL_SECONDS``) until
        the beat is due on ``now()``, then :meth:`beat`."""
        self._announce(
            f"*** Combat begins! Next beat in {int(self.beat_seconds)}s "
            f"— queue your action. ***"
        )
        try:
            while await self.beat():
                await asyncio.sleep(min(self.seconds_to_beat, POLL_SECONDS))
        finally:
            await self._close()

    async def beat(self) -> bool:
        """One look at the clock, what the beat loop does each time it
        wakes: fire the round when its beat is due on ``now()``, then set the
        next one a beat away; close the fight once it is over. True while the
        fight goes on.

        The loop sleeps in real time. A test that has moved the clock calls
        this instead of waiting for the loop to wake: a round fires only when
        due, so the two never fire the same beat twice."""
        if self._over:
            return False
        if not self.participants:
            await self._close()
            return False
        if self._resolving or now() < self._next_fire:
            return True
        try:
            await self.resolve_round()
        except Exception:
            self._resolving = False
            logger.exception("Error resolving combat round")
        if not self._check_continue():
            await self._close()
            return False
        self._next_fire = now() + self.beat_seconds
        await self.manager.flush_sessions()
        return True

    async def _close(self) -> None:
        """Finish the fight, once, whoever sees it end: the loop, a
        :meth:`beat` called from outside it (which stops the loop), or the
        loop's cancellation by :meth:`end`."""
        if self._over:
            return
        self._over = True
        if self._task is not None and self._task is not asyncio.current_task():
            self._task.cancel()
        await self._finish()

    async def resolve_round(self) -> None:
        """Fire the beat: resolve everyone's action in initiative order."""
        self._resolving = True
        self.round_number += 1

        # Beat-driven effects (poison, bleed, buffs, regen) advance one
        # COMBAT beat this round — so slowing the fight (a long `pace`, a
        # Time-Lord's dilation) slows them with it. Combatants carry the
        # 'in_combat' tag, so the ambient beat driver skips them; the
        # encounter is their sole beat source (no double-tick).
        for participant in list(self.participants.values()):
            try:
                await deliver_beat(participant.obj)
            except Exception:
                logger.exception("Beat effect error in combat")

        # Revert last round's stance modifiers, then promote deferred
        # ones (a feint's opening applies during THIS round).
        for participant in self.participants.values():
            combatant = participant.combatant
            for stat, amount in participant.round_modifiers:
                combatant.remove_modifier(stat, amount)
            participant.round_modifiers.clear()
            for stat, amount in participant.next_round_modifiers:
                combatant.add_modifier(stat, amount, 'deferred')
                participant.round_modifiers.append((stat, amount))
            participant.next_round_modifiers.clear()

        order = sorted(self.participants.values(),
                       key=lambda p: p.initiative, reverse=True)

        for participant in order:
            if participant.obj.id not in self.participants:
                continue  # removed mid-round (fled, died)
            if not participant.combatant.is_alive:
                continue
            if participant.obj.location is not self.room:
                self.remove(participant.obj.id)
                continue

            action = self._select_action(participant)
            participant.queued = None
            participant.obj.db.combat_queued = None
            if action is None:
                continue
            participant.last_action = action

            try:
                await self._resolve_action(participant, action)
            except Exception:
                logger.exception(
                    f"Error resolving {action.maneuver} for {participant.obj.name}"
                )

        self._prune()
        self._resolving = False

        if self._check_continue():
            self._announce_round_status()

    def _select_action(self, participant: Participant) -> QueuedAction | None:
        """Queued action, else strategy, else the combat_default policy."""
        # Strategy override rules preempt even a manual queue.
        strategy_action = self.manager.strategy_action(
            self, participant, override_only=participant.queued is not None,
        )
        if strategy_action is not None:
            return strategy_action
        if participant.queued is not None:
            return participant.queued

        policy = str(participant.obj.db.get('combat_default') or 'repeat')
        if policy == 'nothing':
            return None
        if policy == 'defend':
            return QueuedAction(maneuver='defend')
        if policy == 'repeat' and participant.last_action is not None:
            return participant.last_action
        # 'attack' policy, or 'repeat' with no history yet
        return QueuedAction(maneuver='attack', target_id=participant.target_id)

    def _resolve_target(self, participant: Participant,
                        action: QueuedAction) -> Participant | None:
        """Resolve the action's target at fire time; retarget if stale."""
        target_id = action.target_id or participant.target_id
        target = self.participants.get(target_id) if target_id else None
        if target is not None and target.combatant.is_alive:
            participant.target_id = target.obj.id
            return target
        # Retarget: first living participant targeting ME.
        for other in self.participants.values():
            if other.obj.id == participant.obj.id:
                continue
            if other.target_id == participant.obj.id and other.combatant.is_alive:
                participant.target_id = other.obj.id
                return other
        return None

    async def _resolve_action(self, participant: Participant,
                              action: QueuedAction) -> None:
        key = action.maneuver
        obj = participant.obj

        if key == 'attack':
            target = self._resolve_target(participant, action)
            if target is None:
                obj.msg("You have no target to attack.")
                return
            if participant.range_band != 0 or target.range_band != 0:
                obj.msg("You're out of melee reach — 'close' the distance "
                        "or 'shoot'.")
                return
            weapon = find_wielded(obj)
            if weapon is not None and weapon.has_tag('ranged'):
                weapon = None  # you don't club people with your rifle
            result = await self.combat_system.attack(obj, target.obj,
                                                     weapon=weapon)
            await self.land(participant, target, result)
            # Extra swings the ruleset grants (Merc's second and third
            # attack), at the same target while it is still in the fight.
            for _ in range(self.combat_system.ruleset.extra_attacks(obj)):
                if self.get(target.obj.id) is None or not target.combatant.is_alive:
                    break
                result = await self.combat_system.attack(obj, target.obj, weapon=weapon)
                await self.land(participant, target, result)
            return

        if key == 'shoot':
            await self._resolve_shoot(participant, action)
            return

        if key == 'aim':
            self._resolve_aim(participant, action)
            return

        if key == 'close':
            if participant.range_band == 0:
                obj.msg("You're already in the thick of it.")
                return
            participant.range_band = 0
            participant.in_cover = False
            deliver_combat_messages(obj, None, {
                'attacker_msg': "You close the distance!",
                'others_msg': "{actor} closes in!",
            })
            return

        if key == 'withdraw':
            if participant.range_band != 0:
                obj.msg("You're already keeping your distance.")
                return
            participant.range_band = 1
            participant.in_cover = False
            deliver_combat_messages(obj, None, {
                'attacker_msg': "You fall back out of reach.",
                'others_msg': "{actor} falls back, opening the range.",
            })
            return

        if key == 'cover':
            cover_objs = [o for o in self.room.contents if o.has_tag('cover')]
            if not cover_objs:
                obj.msg("There's nothing here to take cover behind.")
                return
            participant.in_cover = True
            cover_name = cover_objs[0].name
            deliver_combat_messages(obj, None, {
                'attacker_msg': f"You duck behind the {cover_name}.",
                'others_msg': f"{{actor}} takes cover behind the {cover_name}.",
            })
            return

        if key == 'defend':
            combatant = participant.combatant
            for stat in ('dodge', 'parry', 'block'):
                combatant.add_modifier(stat, 2, 'defensive stance')
                participant.round_modifiers.append((stat, 2))
            deliver_combat_messages(obj, None, {
                'attacker_msg': "You fight defensively.",
                'others_msg': "{actor} takes a defensive stance.",
            })
            return

        if key == 'flee':
            await self._resolve_flee(participant, action)
            return

        if key == 'wait':
            obj.msg("You bide your time.")
            return

        handled = await self.combat_system.ruleset.resolve_special_maneuver(
            self.combat_system, self, participant, action,
            self._resolve_target(participant, action),
        )
        if not handled:
            obj.msg(f"You don't know how to {key}.")

    async def land(self, participant: Participant, target: Participant,
                   result: CombatResult, messages: dict[str, str] | None = None) -> None:
        """Finish a swing or a shot: show its messages (``messages``, else
        the result's), take a defeated target out of the fight, then settle
        the blow's pool changes. Settling is where the target dies or
        reaches its ``hitprcnt`` (the vital-pool observers), so the room
        hears the hit before the fall."""
        deliver_combat_messages(participant.obj, target.obj,
                                result.messages if messages is None else messages)
        if result.target_defeated:
            self.remove(target.obj.id, make_peace=False)
        for change in result.changes:
            await settle(change, source=participant.obj)

    async def _resolve_shoot(self, participant: Participant,
                             action: QueuedAction) -> None:
        """Ranged attack: works at any band; aim bonus consumed, close
        quarters and cover penalized. Same delivery/defeat path as melee."""

        obj = participant.obj
        target = self._resolve_target(participant, action)
        if target is None:
            obj.msg("You have no target to shoot.")
            return
        weapon = find_wielded(obj)
        if weapon is None or not weapon.has_tag('ranged'):
            obj.msg("You need a wielded ranged weapon to shoot "
                    "(wield <weapon>).")
            return

        modifiers: dict[str, int] = {}
        if participant.aim_bonus and participant.aim_target == target.obj.id:
            modifiers['aim'] = participant.aim_bonus
        participant.aim_bonus = 0
        participant.aim_target = None
        if participant.range_band == 0 and target.range_band == 0:
            modifiers['close quarters'] = -2
        if target.in_cover:
            modifiers['cover'] = -2

        result = await self.combat_system.attack(
            obj, target.obj, weapon=weapon, modifiers=modifiers)
        await self.land(participant, target, result)

    def _resolve_aim(self, participant: Participant,
                     action: QueuedAction) -> None:
        """Steady aim: +Acc on the next shot at that target, +1 per extra
        round of aiming, capped at Acc+2. Lost if you switch targets."""

        obj = participant.obj
        target = self._resolve_target(participant, action)
        if target is None:
            obj.msg("You have no target to aim at.")
            return
        weapon = find_wielded(obj)
        if weapon is None or not weapon.has_tag('ranged'):
            obj.msg("You need a wielded ranged weapon to aim.")
            return

        acc = int(weapon.db.get('acc') or 1)
        if participant.aim_target == target.obj.id:
            participant.aim_bonus = min(acc + 2, participant.aim_bonus + 1)
        else:
            participant.aim_bonus = acc
            participant.aim_target = target.obj.id
        deliver_combat_messages(obj, target.obj, {
            'attacker_msg': (f"You take aim at {target.obj.name} "
                             f"(+{participant.aim_bonus} next shot)."),
            'others_msg': "{actor} takes careful aim at {target}.",
        })

    async def _resolve_flee(self, participant: Participant,
                            action: QueuedAction) -> None:

        obj = participant.obj
        # Instance portals resolve to PRIVATE per-walker space — fleeing
        # through one isn't an escape, it's an unpursuable teleport into
        # a freshly imported dungeon. Excluded from flee entirely.
        exits = [o for o in self.room.contents if o.is_exit
                 and not o.has_tag('closed')
                 and not has_private_dest_resolver(o)]
        exit_obj = None
        if action.args:
            result = match_objects(action.args, exits, allow_substring=False)
            exit_obj = result.matches[0] if result.matches else None
        elif exits:
            import random
            # "up" is the desperate last resort, per MUD tradition.
            preferred = [e for e in exits if e.name.lower() != 'up'] or exits
            exit_obj = random.choice(preferred)

        if exit_obj is None:
            obj.msg("There's nowhere to flee!")
            return

        if not check(obj, 'flee').success:
            deliver_combat_messages(obj, None, {
                'attacker_msg': "You try to disengage but can't break away!",
                'others_msg': "{actor} tries to flee but is cut off!",
            })
            return

        destination = resolve_exit_destination(exit_obj)
        if destination is None and not has_dest_resolver(exit_obj):
            # A deferred exit (a wilderness cell edge) resolves inside
            # move_through_exit — only a true dead-end blocks the flee.
            obj.msg("There's nowhere to flee!")
            return

        self.remove(obj.id)
        moved = await move_through_exit(obj, destination, exit_obj=exit_obj,
                                        fleeing=True)
        if moved:
            self._announce(f"{obj.name} flees {exit_obj.name}!")
            obj.msg("You flee!")
        else:
            # The exit refused (lock, skill gate) — dragged back in.
            self.add(obj)
            obj.msg("Your escape is blocked!")

    # --- Round bookkeeping ---

    def _prune(self) -> None:
        for obj_id in list(self.participants.keys()):
            participant = self.participants.get(obj_id)
            if participant and not participant.combatant.is_alive:
                self.remove(obj_id, make_peace=False)

    def _check_continue(self) -> bool:
        """A fight needs at least two living participants, one of them with
        another as its target (two mobs whose quarry died or fled have no
        one to hit, and stop)."""
        alive = {p.obj.id for p in self.participants.values() if p.combatant.is_alive}
        return len(alive) >= 2 and any(
            self.participants[obj_id].target_id in alive for obj_id in alive)

    def _announce(self, text: str) -> None:
        for participant in self.participants.values():
            participant.obj.msg(text)

    def _announce_round_status(self) -> None:
        for participant in self.participants.values():
            if not participant.is_player():
                continue
            combatant = participant.combatant
            participant.obj.msg_oob("Char.Vitals", {
                "hp": combatant.vital, "max_hp": combatant.vital_max,
                "round": self.round_number,
            })
            planned = self._select_action(participant)
            if planned is None:
                desc = "nothing"
            else:
                maneuver = self.combat_system.ruleset.get_maneuver(planned.maneuver)
                target = self.participants.get(planned.target_id or "")
                desc = planned.describe(
                    maneuver, target.obj.name if target else None,
                ) if maneuver else planned.maneuver
            participant.obj.msg(
                f"-- Round {self.round_number} done. Next beat in "
                f"{int(self.beat_seconds)}s; you will: {desc}. "
                f"(queue <maneuver> to change)"
            )

    async def _finish(self) -> None:
        self._announce("*** The fight is over. ***")
        for obj_id in list(self.participants.keys()):
            self.remove(obj_id)
        self.manager.encounter_ended(self)
        await self.manager.flush_sessions()

    def end(self) -> None:
        """Stop the fight (server shutdown or manager teardown)."""
        if self._task is not None:
            self._task.cancel()
