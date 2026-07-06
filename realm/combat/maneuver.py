"""
Combat maneuvers: the action vocabulary a ruleset offers.

The encounter engine is ruleset-agnostic — it schedules whatever
maneuvers the active ruleset publishes and never touches dice. A
ruleset describes its vocabulary as data (this module) and resolves it
in ``Ruleset.resolve_maneuver``; adding All-Out Attack to GURPS or
Sneak Attack to D20 never touches the scheduler.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Maneuver:
    """One queueable combat action, described as data."""

    key: str                       # canonical: "attack", "all_out_attack"
    name: str                      # display: "All-Out Attack"
    aliases: tuple[str, ...] = ()
    needs_target: bool = False
    cost: int = 1                  # beats consumed (v1: always 1; schema
                                   # supports multi-beat wind-ups later)
    help_text: str = ""


@dataclass
class QueuedAction:
    """
    What a participant will do when the beat fires.

    Freely replaceable until then. ``target_id`` resolves at fire time —
    a target that died or fled invalidates gracefully.
    """

    maneuver: str
    target_id: str | None = None
    args: str = ""

    def describe(self, maneuver: Maneuver, target_name: str | None = None) -> str:
        if target_name and maneuver.needs_target:
            return f"{maneuver.name} {target_name}"
        return maneuver.name


# The base vocabulary every ruleset offers. Rulesets extend, not replace.
BASE_MANEUVERS: tuple[Maneuver, ...] = (
    Maneuver(
        key="attack",
        name="Attack",
        aliases=("att", "hit", "kill"),
        needs_target=True,
        help_text="Strike your target with your readied weapon.",
    ),
    Maneuver(
        key="defend",
        name="Defend",
        aliases=("def", "guard"),
        help_text="Fight defensively: +2 to active defenses this round, no attack.",
    ),
    Maneuver(
        key="flee",
        name="Flee",
        aliases=("run", "escape", "retreat"),
        help_text="Attempt to disengage and leave through an exit.",
    ),
    Maneuver(
        key="shoot",
        name="Shoot",
        aliases=("fire",),
        needs_target=True,
        help_text="Attack with your wielded ranged weapon (works at range; "
                  "-2 in close quarters, -2 vs cover).",
    ),
    Maneuver(
        key="aim",
        name="Aim",
        aliases=(),
        needs_target=True,
        help_text="Steady your ranged weapon: +Acc to your next shot at "
                  "that target (+1 more per extra round, max Acc+2).",
    ),
    Maneuver(
        key="close",
        name="Close In",
        aliases=("advance", "charge"),
        help_text="Close the distance to melee reach.",
    ),
    Maneuver(
        key="withdraw",
        name="Withdraw",
        aliases=("fallback", "distance"),
        help_text="Fall back to range — out of melee reach; ranged attacks "
                  "still apply.",
    ),
    Maneuver(
        key="cover",
        name="Take Cover",
        aliases=("takecover", "duck"),
        help_text="Duck behind cover (needs a cover-tagged object here): "
                  "-2 to ranged attacks against you until you move.",
    ),
    Maneuver(
        key="wait",
        name="Wait",
        aliases=("pass", "nothing"),
        help_text="Do nothing this round.",
    ),
)


__all__ = ["Maneuver", "QueuedAction", "BASE_MANEUVERS"]
