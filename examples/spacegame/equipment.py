"""
Equipment and items for the space game.

Includes weapons, armor, and miscellaneous gear.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.persistence.repository import GameObjectRepository


class EquipmentSlot(Enum):
    """Equipment slots for characters."""
    WEAPON = "weapon"
    ARMOR = "armor"
    HELMET = "helmet"
    TOOL = "tool"
    ACCESSORY = "accessory"


class WeaponType(Enum):
    """Types of weapons."""
    MELEE = "melee"
    PISTOL = "pistol"
    RIFLE = "rifle"
    HEAVY = "heavy"
    ENERGY = "energy"


@dataclass
class EquipmentTemplate:
    """Template for equipment creation."""
    name: str
    description: str
    slot: EquipmentSlot

    # Combat stats (GURPS style)
    damage_dice: str = ""  # e.g., "1d+2" for GURPS
    damage_type: str = ""  # e.g., "piercing", "burning"
    skill_type: str = ""  # e.g., "melee", "ranged"

    # Armor stats
    damage_resistance: int = 0

    # Other stats
    weight: float = 1.0
    cost: int = 100

    # Tags to add
    tags: list[str] | None = None


# Weapons
WEAPONS = {
    "combat_knife": EquipmentTemplate(
        name="Combat Knife",
        description="A balanced combat knife with a mono-molecular edge.",
        slot=EquipmentSlot.WEAPON,
        damage_dice="1d",
        damage_type="cutting",
        skill_type="melee",
        weight=0.5,
        cost=50,
        tags=["melee", "blade"],
    ),
    "stunner": EquipmentTemplate(
        name="Stun Pistol",
        description="A non-lethal sidearm that delivers an incapacitating shock.",
        slot=EquipmentSlot.WEAPON,
        damage_dice="1d",
        damage_type="crushing",  # Stun damage
        skill_type="ranged",
        weight=1.0,
        cost=200,
        tags=["ranged", "pistol", "non_lethal"],
    ),
    "sidearm": EquipmentTemplate(
        name="Laser Pistol",
        description="A standard-issue laser sidearm. Reliable and accurate.",
        slot=EquipmentSlot.WEAPON,
        damage_dice="2d",
        damage_type="burning",
        skill_type="ranged",
        weight=1.5,
        cost=500,
        tags=["ranged", "pistol", "energy"],
    ),
    "rifle": EquipmentTemplate(
        name="Plasma Rifle",
        description="A military-grade plasma rifle with excellent stopping power.",
        slot=EquipmentSlot.WEAPON,
        damage_dice="3d",
        damage_type="burning",
        skill_type="ranged",
        weight=4.0,
        cost=1500,
        tags=["ranged", "rifle", "energy"],
    ),
    "vibroblade": EquipmentTemplate(
        name="Vibroblade",
        description="A sword with a vibrating mono-molecular edge. Devastating in close quarters.",
        slot=EquipmentSlot.WEAPON,
        damage_dice="2d+2",
        damage_type="cutting",
        skill_type="melee",
        weight=2.0,
        cost=800,
        tags=["melee", "blade", "vibro"],
    ),
    "shotgun": EquipmentTemplate(
        name="Flechette Shotgun",
        description="Fires a spread of razor-sharp flechettes. Deadly at close range.",
        slot=EquipmentSlot.WEAPON,
        damage_dice="3d",
        damage_type="piercing",
        skill_type="ranged",
        weight=5.0,
        cost=1000,
        tags=["ranged", "shotgun", "spread"],
    ),
}

# Armor
ARMOR = {
    "flight_suit": EquipmentTemplate(
        name="Flight Suit",
        description="A lightweight protective suit for pilots. Offers minimal protection.",
        slot=EquipmentSlot.ARMOR,
        damage_resistance=1,
        weight=2.0,
        cost=200,
        tags=["light_armor", "pilot"],
    ),
    "security_vest": EquipmentTemplate(
        name="Security Vest",
        description="Standard security armor. Protects vital areas.",
        slot=EquipmentSlot.ARMOR,
        damage_resistance=2,
        weight=4.0,
        cost=400,
        tags=["medium_armor", "security"],
    ),
    "combat_armor": EquipmentTemplate(
        name="Combat Armor",
        description="Full military combat suit with integrated systems.",
        slot=EquipmentSlot.ARMOR,
        damage_resistance=4,
        weight=10.0,
        cost=1200,
        tags=["heavy_armor", "military"],
    ),
    "power_armor": EquipmentTemplate(
        name="Power Armor",
        description="Powered exoskeleton armor. Extremely protective but expensive.",
        slot=EquipmentSlot.ARMOR,
        damage_resistance=8,
        weight=25.0,  # Powered, so effective weight is less
        cost=10000,
        tags=["power_armor", "military", "powered"],
    ),
}

# Tools and Gear
GEAR = {
    "medkit": EquipmentTemplate(
        name="Medical Kit",
        description="A portable medical kit with supplies for treating injuries.",
        slot=EquipmentSlot.TOOL,
        weight=2.0,
        cost=150,
        tags=["medical", "consumable"],
    ),
    "surgical_kit": EquipmentTemplate(
        name="Surgical Kit",
        description="Advanced surgical tools for complex medical procedures.",
        slot=EquipmentSlot.TOOL,
        weight=5.0,
        cost=500,
        tags=["medical", "surgery"],
    ),
    "tool_kit": EquipmentTemplate(
        name="Engineering Tool Kit",
        description="Essential tools for ship maintenance and repairs.",
        slot=EquipmentSlot.TOOL,
        weight=8.0,
        cost=300,
        tags=["engineering", "repair"],
    ),
    "datapad": EquipmentTemplate(
        name="Datapad",
        description="A handheld computer for data access and communication.",
        slot=EquipmentSlot.ACCESSORY,
        weight=0.5,
        cost=100,
        tags=["electronics", "computer"],
    ),
    "scanner": EquipmentTemplate(
        name="Portable Scanner",
        description="Multi-function scanner for analysis and detection.",
        slot=EquipmentSlot.TOOL,
        weight=1.0,
        cost=400,
        tags=["electronics", "sensor"],
    ),
    "survival_kit": EquipmentTemplate(
        name="Survival Kit",
        description="Emergency supplies for hostile environment survival.",
        slot=EquipmentSlot.TOOL,
        weight=5.0,
        cost=200,
        tags=["survival", "emergency"],
    ),
    "credit_chip": EquipmentTemplate(
        name="Credit Chip",
        description="A secure chip for storing and transferring credits.",
        slot=EquipmentSlot.ACCESSORY,
        weight=0.1,
        cost=10,
        tags=["currency", "storage"],
    ),
}


async def create_equipment_prototypes(
    repo: GameObjectRepository,
) -> dict[str, GameObject]:
    """
    Create prototype equipment objects for the game.

    These serve as templates for creating actual equipment.
    """
    from realm.core.objects import GameObject

    prototypes: dict[str, GameObject] = {}

    all_templates = {**WEAPONS, **ARMOR, **GEAR}

    for template_id, template in all_templates.items():
        obj = GameObject(
            id=f"proto_{template_id}",
            name=template.name,
        )

        obj.add_tag("prototype")
        obj.add_tag("equipment")
        obj.add_tag(f"slot:{template.slot.value}")

        if template.tags:
            for tag in template.tags:
                obj.add_tag(tag)

        obj.db.description = template.description
        obj.db.weight = template.weight
        obj.db.cost = template.cost
        obj.db.slot = template.slot.value

        # Weapon stats
        if template.damage_dice:
            obj.db.damage_dice = template.damage_dice
            obj.db.damage_type = template.damage_type
            obj.db.skill_type = template.skill_type

        # Armor stats
        if template.damage_resistance:
            obj.db.damage_resistance = template.damage_resistance

        await repo.save(obj)
        prototypes[template_id] = obj

    return prototypes


async def create_equipment_instance(
    repo: GameObjectRepository,
    template_id: str,
    owner: GameObject | None = None,
) -> GameObject | None:
    """
    Create an instance of equipment from a template.

    Args:
        repo: Repository for saving
        template_id: ID of the template (e.g., "sidearm")
        owner: Optional owner of the item

    Returns:
        New equipment GameObject or None if template not found
    """
    from realm.core.objects import GameObject
    import uuid

    all_templates = {**WEAPONS, **ARMOR, **GEAR}
    template = all_templates.get(template_id)

    if not template:
        return None

    # Generate unique ID
    unique_id = f"eq_{template_id}_{uuid.uuid4().hex[:8]}"

    obj = GameObject(
        id=unique_id,
        name=template.name,
    )

    obj.add_tag("equipment")
    obj.add_tag("thing")  # Portable item
    obj.add_tag(f"slot:{template.slot.value}")

    if template.tags:
        for tag in template.tags:
            obj.add_tag(tag)

    if owner:
        obj.owner = owner
        obj.location = owner
        owner.contents.append(obj)

    obj.db.description = template.description
    obj.db.weight = template.weight
    obj.db.cost = template.cost
    obj.db.slot = template.slot.value
    obj.db.template_id = template_id

    # Weapon stats
    if template.damage_dice:
        obj.db.damage_dice = template.damage_dice
        obj.db.damage_type = template.damage_type
        obj.db.skill_type = template.skill_type

    # Armor stats
    if template.damage_resistance:
        obj.db.damage_resistance = template.damage_resistance

    await repo.save(obj)
    return obj
