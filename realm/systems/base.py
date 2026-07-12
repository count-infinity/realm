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
- **Dotted-path selection**: ``GAME_SYSTEM`` is an import path to a
  GameSystem subclass (``"rules.GameRules"``, ``"realm.systems.GurpsSystem"``),
  resolved by ``resolve_game_system`` — one greppable value that leads
  straight to the source, no registry indirection.
- **Template Method**: the chargen *flow* (prompt → answer → advance →
  finish) lives here once; systems supply the steps. ChoiceStep covers
  menu-style steps today; point-buy steps later are just new
  ChargenStep subclasses — the flow doesn't change.
- **Module singleton** ambient accessor, like the combat and
  persistence managers.
"""

from __future__ import annotations

import importlib
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

    def death_award(self, victim: GameObject) -> int:
        """Character points a kill is worth (split across the party)."""
        return max(1, int(victim.db.get('points') or 10) // 10)

    # --- Skill resolution ---
    #
    # A GameSystem owns how NON-COMBAT skill checks resolve, not just
    # combat. The server installs this at startup via set_check_resolver,
    # so `d20` really rolls d20 for stealth/persuade/search — not only
    # for combat. Default: the engine's GURPS-shaped 3d6 roll-under.

    #: Optional softcode resolution rule — an expression over the dice
    #: primitives (realm.core.dice), e.g.
    #: ``"margin_under(roll('3d6'), skill() + mod)"``. Set this and the
    #: whole game system is *data*: a builder can author the resolution
    #: in-game, no Python. When None, resolve_check falls back to Python.
    resolve_rule: str | None = None

    def resolve_check(self, obj: GameObject, skill: str, modifier: int):
        """Return a CheckResult for one skill check. If ``resolve_rule`` is
        set, the rule (softcode) resolves it; otherwise the reference
        default. Override in Python for a hand-tuned resolver."""
        from realm.core.checks import default_resolver, resolve_with_rule
        if self.resolve_rule:
            return resolve_with_rule(obj, skill, modifier, self.resolve_rule)
        return default_resolver(obj, skill, modifier)

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


def resolve_game_system(spec: str | type[GameSystem] | GameSystem) -> GameSystem:
    """
    Resolve a ``GAME_SYSTEM`` config value to a live GameSystem.

    The config form is a **dotted import path** to a GameSystem subclass —
    a value a developer can follow straight to the source, with no registry
    lookup to reverse-engineer:

        GAME_SYSTEM = "rules.GameRules"            # your scaffolded rules.py
        GAME_SYSTEM = "realm.systems.GurpsSystem"  # a built-in, unmodified

    The path is imported and instantiated. A bad path raises rather than
    falling back, so a typo fails loudly instead of quietly running the
    wrong rules. (An already-resolved class or instance is also accepted,
    for programmatic callers — it's simply passed through.)
    """
    if isinstance(spec, GameSystem):
        return spec
    if isinstance(spec, type) and issubclass(spec, GameSystem):
        return spec()
    if isinstance(spec, str):
        module_path, _, class_name = spec.rpartition(".")
        if not module_path:
            raise ValueError(
                f"GAME_SYSTEM = {spec!r} must be a dotted import path to a "
                "GameSystem subclass, e.g. 'rules.GameRules' or "
                "'realm.systems.GurpsSystem'."
            )
        try:
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
        except (ImportError, AttributeError) as exc:
            raise ValueError(
                f"GAME_SYSTEM = {spec!r} could not be imported ({exc}). Use a "
                "dotted path to a GameSystem subclass, e.g. 'rules.GameRules' "
                "or 'realm.systems.GurpsSystem'."
            ) from exc
        if not (isinstance(cls, type) and issubclass(cls, GameSystem)):
            raise TypeError(
                f"GAME_SYSTEM = {spec!r} resolved to {cls!r}, which is not a "
                "GameSystem subclass."
            )
        return cls()
    raise TypeError(
        "GAME_SYSTEM must be a dotted import-path string (or a GameSystem "
        f"class/instance); got {type(spec).__name__}."
    )


# --- Ambient accessor (set by GameServer) ------------------------------------

_active_system: GameSystem | None = None


def set_game_system(system: GameSystem | None) -> None:
    global _active_system
    _active_system = system


def get_game_system() -> GameSystem | None:
    return _active_system


def reload_rules() -> None:
    """
    Re-install the active system's data-driven tables, picking up edits to
    ``skill_def`` objects made in-game or by an import. Skill defaults are
    cached (in ``core.checks``), so they need this refresh; chargen classes
    are read live each character creation and need no reload.
    """
    system = get_game_system()
    if system is None:
        return
    from realm.core.checks import set_check_resolver, set_skill_defaults
    set_skill_defaults(system.skill_defaults())
    set_check_resolver(system.resolve_check)


__all__ = [
    "ChargenStep",
    "ChoiceStep",
    "GameSystem",
    "resolve_game_system",
    "reload_rules",
    "set_game_system",
    "get_game_system",
]
