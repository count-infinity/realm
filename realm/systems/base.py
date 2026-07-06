"""
GameSystem: the swappable rules package (the GURPS/D20 seam).

The engine-vision analogy: Godot ships a physics engine you can swap;
REALM ships a *game system* you can swap. A GameSystem is an Abstract
Factory bundling every rules decision in one object:

- which combat ruleset the encounter engine uses
- skill definitions and their attribute defaults
- character advancement costs (``improve``)
- baseline stats and the character-generation flow

Patterns, deliberately:
- **Abstract Factory / Strategy**: GameSystem supplies the parts; the
  engine never branches on "is this GURPS?".
- **Registry** (same shape as BehaviorRegistry): systems register by id,
  config picks one by name (``GAME_SYSTEM = "gurps"``).
- **Template Method**: the chargen *flow* (prompt → answer → advance →
  finish) lives here once; systems supply the steps. ChoiceStep covers
  menu-style steps today; point-buy steps later are just new
  ChargenStep subclasses — the flow doesn't change.
- **Module singleton** ambient accessor, like the combat and
  persistence managers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.objects import GameObject


class ChargenStep(ABC):
    """One question in the character-generation flow."""

    key: str = "step"

    @abstractmethod
    def prompt(self, player: GameObject) -> str:
        """The text shown when this step becomes active."""

    @abstractmethod
    def handle(self, player: GameObject, response: str) -> tuple[bool, str]:
        """
        Process the player's answer.

        Returns (advance, feedback): advance=True moves to the next step.
        """


class ChoiceStep(ChargenStep):
    """
    A menu step: pick one option by number or name; ``apply`` writes it
    onto the character. Covers templates, classes, bonus skills — any
    "choose one of these" question.
    """

    def __init__(
        self,
        key: str,
        title: str,
        options: dict[str, str],
        apply: Callable[[GameObject, str], None],
    ):
        self.key = key
        self.title = title
        self.options = options  # choice key -> description
        self._apply = apply

    def prompt(self, player: GameObject) -> str:
        lines = [self.title]
        for i, (name, blurb) in enumerate(self.options.items(), 1):
            lines.append(f"  {i}. {name} — {blurb}")
        lines.append("Choose by number or name.")
        return "\n".join(lines)

    def handle(self, player: GameObject, response: str) -> tuple[bool, str]:
        response = response.strip().lower()
        names = list(self.options.keys())
        chosen: str | None = None
        if response.isdigit() and 1 <= int(response) <= len(names):
            chosen = names[int(response) - 1]
        else:
            matches = [n for n in names if n.lower().startswith(response)]
            if len(matches) == 1:
                chosen = matches[0]
        if chosen is None:
            return False, "Pick one of the listed options (number or name)."
        self._apply(player, chosen)
        return True, f"{self.key.capitalize()}: {chosen}."


class GameSystem(ABC):
    """A complete, swappable rules package."""

    system_id: str = "base"
    #: passed to create_combat_system
    ruleset_name: str = "d20"
    #: what money is called in this rules package
    currency_name: str = "credits"

    # --- Skills & checks ---

    def skill_defaults(self) -> dict[str, tuple[str, int]]:
        """skill -> (attribute, modifier) untrained defaults."""
        return {}

    # --- Advancement ---

    def improve_cost(self, skill: str, current_level: int) -> int:
        """Character points to raise ``skill`` by one level."""
        return 4

    # --- Character creation ---

    def apply_baseline(self, player: GameObject) -> None:
        """Stats every fresh character gets before chargen runs."""
        for stat, value in self.baseline_stats().items():
            if player.db.get(stat) is None:
                player.db.set(stat, value)

    def baseline_stats(self) -> dict[str, Any]:
        return {
            'strength': 10, 'dexterity': 10, 'intelligence': 10,
            'health': 10, 'hp': 10, 'max_hp': 10, 'dodge': 8,
        }

    def chargen_steps(self) -> list[ChargenStep]:
        """The questions asked at creation. Empty = instant characters."""
        return []

    def finish_chargen(self, player: GameObject) -> str:
        """Final fixups (derived stats). Returns the welcome line."""
        return "Character creation complete."


class GameSystemRegistry:
    """Registry of game systems, keyed by system_id."""

    _systems: dict[str, type[GameSystem]] = {}

    @classmethod
    def register(cls, system_class: type[GameSystem]) -> type[GameSystem]:
        cls._systems[system_class.system_id] = system_class
        return system_class

    @classmethod
    def create(cls, system_id: str) -> GameSystem | None:
        system_class = cls._systems.get(system_id)
        return system_class() if system_class else None

    @classmethod
    def list_all(cls) -> list[str]:
        return list(cls._systems.keys())


# --- Ambient accessor (set by GameServer) ------------------------------------

_active_system: GameSystem | None = None


def set_game_system(system: GameSystem | None) -> None:
    global _active_system
    _active_system = system


def get_game_system() -> GameSystem | None:
    return _active_system


__all__ = [
    "ChargenStep",
    "ChoiceStep",
    "GameSystem",
    "GameSystemRegistry",
    "set_game_system",
    "get_game_system",
]
