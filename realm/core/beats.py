"""
Beats — the game turn-clock, distinct from the real-time heartbeat.

REALM runs two clocks (see docs/design/time-and-beats.md):

- **Real-time seconds** — a fast heartbeat (~0.1s) driving infrastructure:
  ``wait()``, output flush, reapers, and *world* behaviors (spawners, decay,
  wander) whose cadence is pinned to ``WORLD_TICK`` so the heartbeat rate
  never changes their pacing.
- **Beats (= rounds)** — the turn-unit for **character effects** (poison,
  bleed, buffs, regen) and combat maneuvers. A beat's real-time length is
  *contextual*: the encounter's adjustable beat in combat, the ambient
  ``WORLD_TICK`` out of combat. Slow the encounter and everything beat-based
  on its participants dilates together — bullet-time.

A ``BeatBehavior`` is advanced by ``deliver_beat(obj)`` — called by the
combat encounter for its participants, or by the ambient driver on the
heartbeat for everyone else. Per-creature ``db.beat_multiplier`` (haste 2.0,
slow 0.5, a Time-Lord bubble 0.25 on victims) scales how many beats a
creature experiences per source-beat, accumulated so fractions like 1.5
land as 1,2,1,2.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.behaviors import WORLD_TICK, Behavior, set_world_tick

if TYPE_CHECKING:
    from realm.core.objects import GameObject


class BeatBehavior(Behavior):
    """A behavior driven by BEATS, not the real-time heartbeat. It never
    ticks on the heartbeat (``should_tick`` is False); ``on_beat`` is called
    once per beat by whatever owns the object's time — the encounter in
    combat, the ambient driver otherwise."""

    @property
    def should_tick(self) -> bool:
        return False

    async def on_beat(self, obj: GameObject) -> None:  # pragma: no cover
        """Override: one beat of the effect."""


#: Sanity ceiling on beats-per-source-beat. ``beat_multiplier`` is
#: softcode-settable, so an absurd value (haste 1e12) must never spin the
#: event loop synchronously — clamp it. 64 beats/round is already unreachable
#: in play. See docs/design/time-and-beats.md.
MAX_BEAT_MULTIPLIER: float = 64.0


def _consume_beats(obj: GameObject) -> int:
    """How many beats ``obj`` experiences for one source-beat, honoring its
    ``beat_multiplier`` with fractional carry (1.5 → 1,2,1,2…). A multiplier of
    0 *freezes* the creature (0 beats — stasis); values are clamped to
    ``[0, MAX_BEAT_MULTIPLIER]`` so softcode can't DoS the loop."""
    raw = obj.db.get("beat_multiplier")
    mult = 1.0 if raw is None else float(raw)   # 0.0 must stay 0.0, not `or 1`
    if mult == 1.0:
        # No dilation: clear any stale carry from a lapsed haste/slow so it
        # can't grant an early beat when a fractional multiplier next resumes.
        if obj.db.get("beat_acc"):
            obj.db.delete("beat_acc")
        return 1
    mult = max(0.0, min(mult, MAX_BEAT_MULTIPLIER))
    acc = float(obj.db.get("beat_acc") or 0.0) + mult
    whole = int(acc)
    obj.db.set("beat_acc", acc - whole)
    return whole


async def deliver_beat(obj: GameObject) -> None:
    """Deliver one source-beat to ``obj`` — advancing every ``BeatBehavior``
    on it by the object's (multiplied) beat count. Called by the encounter
    for combatants and by the ambient driver for everyone else."""
    if not has_beat_behavior(obj):
        return
    for _ in range(_consume_beats(obj)):
        # Re-read fresh each beat: an effect that expired on an earlier beat of
        # THIS delivery (under haste) has detached and must not be advanced
        # again — a stale snapshot would re-arm it (resurrect + over-pulse).
        for behavior in list(obj.get_behaviors()):
            if isinstance(behavior, BeatBehavior) and behavior.owner is not None:
                await behavior.on_beat(obj)


def has_beat_behavior(obj: GameObject) -> bool:
    return any(isinstance(b, BeatBehavior) for b in obj.get_behaviors())


#: Objects being driven by an encounter carry this tag; the ambient beat
#: driver skips them so they don't get a beat from both sources (double-tick
#: guard). Combat applies/removes it as fights begin and end.
IN_COMBAT_TAG = "in_combat"


def ambient_beat_targets(objs: list[GameObject]) -> list[GameObject]:
    """From ``objs``, the ones the *ambient* (out-of-combat) beat driver
    should advance: those with beat behaviors that an encounter isn't already
    driving. The double-tick guard — a combatant gets its beats from
    ``resolve_round``, never also from the ambient driver."""
    return [o for o in objs
            if not o.has_tag(IN_COMBAT_TAG) and has_beat_behavior(o)]


__all__ = [
    "WORLD_TICK", "set_world_tick", "BeatBehavior", "deliver_beat",
    "has_beat_behavior", "ambient_beat_targets", "IN_COMBAT_TAG",
]
