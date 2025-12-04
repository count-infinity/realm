"""
Space game character creation and management.

Provides GURPS-based character templates for the space game.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.objects import GameObject


class CharacterRole(Enum):
    """Character roles/classes for the space game."""
    PILOT = "pilot"
    MARINE = "marine"
    ENGINEER = "engineer"
    MEDIC = "medic"
    MERCHANT = "merchant"
    SCOUT = "scout"


@dataclass
class CharacterTemplate:
    """Template for creating characters of a specific role."""
    role: CharacterRole
    description: str

    # Base GURPS attributes (10 is human average)
    strength: int = 10
    dexterity: int = 10
    intelligence: int = 10
    health: int = 10

    # Derived stats
    hp: int = 10
    will: int = 10
    perception: int = 10

    # Skills (GURPS skill levels, 10 = trained, 12 = professional, 14+ = expert)
    skills: dict[str, int] | None = None

    # Starting equipment
    equipment: list[str] | None = None


# Pre-defined character templates
TEMPLATES = {
    CharacterRole.PILOT: CharacterTemplate(
        role=CharacterRole.PILOT,
        description="Expert spacecraft pilots, masters of navigation and evasion.",
        dexterity=12,
        intelligence=11,
        skills={
            "piloting": 14,
            "navigation": 12,
            "sensors": 11,
            "skill_ranged": 10,
        },
        equipment=["flight_suit", "sidearm"],
    ),
    CharacterRole.MARINE: CharacterTemplate(
        role=CharacterRole.MARINE,
        description="Combat specialists trained for shipboard and planetary operations.",
        strength=12,
        health=12,
        skills={
            "skill_melee": 13,
            "skill_ranged": 14,
            "tactics": 11,
            "first_aid": 10,
        },
        equipment=["combat_armor", "rifle", "combat_knife"],
    ),
    CharacterRole.ENGINEER: CharacterTemplate(
        role=CharacterRole.ENGINEER,
        description="Technical experts who keep ships running and systems operational.",
        intelligence=13,
        dexterity=11,
        skills={
            "engineering": 14,
            "electronics": 13,
            "mechanics": 13,
            "computers": 12,
        },
        equipment=["tool_kit", "datapad"],
    ),
    CharacterRole.MEDIC: CharacterTemplate(
        role=CharacterRole.MEDIC,
        description="Medical professionals skilled in treating injuries and diseases.",
        intelligence=13,
        dexterity=12,
        skills={
            "medicine": 14,
            "first_aid": 13,
            "surgery": 12,
            "diagnosis": 12,
        },
        equipment=["medkit", "surgical_kit"],
    ),
    CharacterRole.MERCHANT: CharacterTemplate(
        role=CharacterRole.MERCHANT,
        description="Traders and negotiators, experts in commerce and persuasion.",
        intelligence=12,
        will=12,
        skills={
            "merchant": 14,
            "diplomacy": 13,
            "detect_lies": 12,
            "streetwise": 11,
        },
        equipment=["datapad", "credit_chip"],
    ),
    CharacterRole.SCOUT: CharacterTemplate(
        role=CharacterRole.SCOUT,
        description="Reconnaissance specialists skilled in exploration and survival.",
        dexterity=12,
        perception=12,
        skills={
            "stealth": 13,
            "observation": 14,
            "survival": 12,
            "tracking": 11,
            "skill_ranged": 12,
        },
        equipment=["survival_kit", "scanner", "sidearm"],
    ),
}


class SpaceCharacter:
    """
    Wrapper for player characters in the space game.

    Provides GURPS-specific character management.
    """

    def __init__(self, obj: GameObject):
        """
        Wrap a GameObject as a space character.

        Args:
            obj: The player's GameObject
        """
        self.obj = obj

    @classmethod
    def create(
        cls,
        obj: GameObject,
        role: CharacterRole,
        name: str | None = None,
    ) -> SpaceCharacter:
        """
        Initialize a GameObject as a space character.

        Args:
            obj: The GameObject to configure
            role: Character role/class
            name: Optional character name (uses obj.name if not provided)

        Returns:
            SpaceCharacter wrapper
        """
        template = TEMPLATES[role]

        # Set name
        if name:
            obj.name = name

        # Add tags
        obj.add_tag("player")
        obj.add_tag(f"role:{role.value}")

        # Set GURPS attributes
        obj.db.strength = template.strength
        obj.db.dexterity = template.dexterity
        obj.db.intelligence = template.intelligence
        obj.db.health = template.health

        # Derived stats
        obj.db.hp = template.hp or template.health
        obj.db.max_hp = obj.db.hp
        obj.db.will = template.will or template.intelligence
        obj.db.perception = template.perception or template.intelligence

        # Combat stats (derived from attributes for GURPS)
        obj.db.dodge = 3 + (template.dexterity // 2)  # Base dodge
        obj.db.damage_resistance = 0  # No armor by default

        # Skills
        if template.skills:
            for skill, level in template.skills.items():
                obj.db.set(skill, level)

        # Role description
        obj.db.role = role.value
        obj.db.role_description = template.description

        # Starting credits
        obj.db.credits = 500

        return cls(obj)

    @property
    def strength(self) -> int:
        return self.obj.db.get("strength", 10)

    @property
    def dexterity(self) -> int:
        return self.obj.db.get("dexterity", 10)

    @property
    def intelligence(self) -> int:
        return self.obj.db.get("intelligence", 10)

    @property
    def health(self) -> int:
        return self.obj.db.get("health", 10)

    @property
    def hp(self) -> int:
        return self.obj.db.get("hp", self.health)

    @property
    def max_hp(self) -> int:
        return self.obj.db.get("max_hp", self.health)

    @property
    def credits(self) -> int:
        return self.obj.db.get("credits", 0)

    def get_skill(self, skill: str) -> int:
        """Get skill level (default 8 = untrained default)."""
        return self.obj.db.get(skill, 8)

    def modify_credits(self, amount: int) -> int:
        """Add or subtract credits. Returns new balance."""
        current = self.credits
        new_balance = max(0, current + amount)
        self.obj.db.credits = new_balance
        return new_balance

    def heal(self, amount: int) -> int:
        """Heal HP. Returns actual amount healed."""
        current = self.hp
        max_hp = self.max_hp
        new_hp = min(max_hp, current + amount)
        healed = new_hp - current
        self.obj.db.hp = new_hp
        return healed

    def take_damage(self, amount: int) -> int:
        """Take damage. Returns actual damage taken."""
        current = self.hp
        new_hp = max(0, current - amount)
        damage = current - new_hp
        self.obj.db.hp = new_hp
        return damage

    def is_alive(self) -> bool:
        """Check if character is alive."""
        return self.hp > 0

    def get_status_string(self) -> str:
        """Get a status string for display."""
        role = self.obj.db.get("role", "unknown")
        hp_pct = (self.hp / self.max_hp * 100) if self.max_hp > 0 else 0

        if hp_pct >= 75:
            health_status = "Healthy"
        elif hp_pct >= 50:
            health_status = "Wounded"
        elif hp_pct >= 25:
            health_status = "Injured"
        elif hp_pct > 0:
            health_status = "Critical"
        else:
            health_status = "Incapacitated"

        return (
            f"{self.obj.name} ({role.title()})\n"
            f"HP: {self.hp}/{self.max_hp} ({health_status})\n"
            f"Credits: {self.credits}"
        )
