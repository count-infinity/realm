"""
Spaceship system for the space game.

Ships are special GameObjects that can:
- Contain players and cargo
- Travel between sectors
- Engage in ship-to-ship combat
- Be upgraded with components
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.persistence.repository import GameObjectRepository


class ShipClass(Enum):
    """Ship classifications."""
    SHUTTLE = "shuttle"
    FIGHTER = "fighter"
    FREIGHTER = "freighter"
    CORVETTE = "corvette"
    CRUISER = "cruiser"


@dataclass
class ShipTemplate:
    """Template for ship creation."""
    ship_class: ShipClass
    name: str
    description: str

    # Hull stats
    hull_points: int
    max_hull: int
    armor: int

    # Systems
    shields: int
    max_shields: int
    power_output: int

    # Movement
    speed: int  # Relative speed rating
    maneuverability: int  # Dodge equivalent

    # Cargo
    cargo_capacity: int

    # Crew
    min_crew: int
    max_crew: int

    # Weapons slots
    weapon_slots: int

    # Base cost in credits
    cost: int


SHIP_TEMPLATES = {
    ShipClass.SHUTTLE: ShipTemplate(
        ship_class=ShipClass.SHUTTLE,
        name="Light Shuttle",
        description="A small, unarmed transport shuttle. Basic but reliable.",
        hull_points=20,
        max_hull=20,
        armor=0,
        shields=10,
        max_shields=10,
        power_output=50,
        speed=3,
        maneuverability=6,
        cargo_capacity=10,
        min_crew=1,
        max_crew=4,
        weapon_slots=0,
        cost=5000,
    ),
    ShipClass.FIGHTER: ShipTemplate(
        ship_class=ShipClass.FIGHTER,
        name="Strike Fighter",
        description="A nimble single-seat combat craft. Fast and deadly.",
        hull_points=30,
        max_hull=30,
        armor=2,
        shields=20,
        max_shields=20,
        power_output=80,
        speed=8,
        maneuverability=10,
        cargo_capacity=2,
        min_crew=1,
        max_crew=1,
        weapon_slots=2,
        cost=15000,
    ),
    ShipClass.FREIGHTER: ShipTemplate(
        ship_class=ShipClass.FREIGHTER,
        name="Cargo Freighter",
        description="A sturdy cargo vessel. Slow but spacious.",
        hull_points=60,
        max_hull=60,
        armor=3,
        shields=30,
        max_shields=30,
        power_output=100,
        speed=2,
        maneuverability=4,
        cargo_capacity=100,
        min_crew=2,
        max_crew=6,
        weapon_slots=1,
        cost=25000,
    ),
    ShipClass.CORVETTE: ShipTemplate(
        ship_class=ShipClass.CORVETTE,
        name="Light Corvette",
        description="A versatile patrol craft. Balanced combat capability.",
        hull_points=80,
        max_hull=80,
        armor=5,
        shields=50,
        max_shields=50,
        power_output=150,
        speed=5,
        maneuverability=7,
        cargo_capacity=30,
        min_crew=4,
        max_crew=12,
        weapon_slots=4,
        cost=50000,
    ),
    ShipClass.CRUISER: ShipTemplate(
        ship_class=ShipClass.CRUISER,
        name="Heavy Cruiser",
        description="A formidable warship. Heavily armed and armored.",
        hull_points=150,
        max_hull=150,
        armor=10,
        shields=100,
        max_shields=100,
        power_output=300,
        speed=3,
        maneuverability=5,
        cargo_capacity=50,
        min_crew=10,
        max_crew=30,
        weapon_slots=8,
        cost=150000,
    ),
}


class Spaceship:
    """
    Wrapper for ship GameObjects.

    Provides ship-specific functionality for the space game.
    """

    def __init__(self, obj: GameObject):
        """
        Wrap a GameObject as a spaceship.

        Args:
            obj: The ship's GameObject
        """
        self.obj = obj

    @classmethod
    async def create(
        cls,
        repo: GameObjectRepository,
        ship_class: ShipClass,
        name: str,
        owner: GameObject | None = None,
    ) -> Spaceship:
        """
        Create a new spaceship.

        Args:
            repo: Repository for saving
            ship_class: Type of ship
            name: Ship's name
            owner: Optional owner

        Returns:
            Spaceship wrapper
        """
        from realm.core.objects import GameObject

        template = SHIP_TEMPLATES[ship_class]

        ship = GameObject(
            id=f"ship_{name.lower().replace(' ', '_')}",
            name=name,
        )
        ship.add_tag("ship")
        ship.add_tag("container")
        ship.add_tag(f"ship_class:{ship_class.value}")

        if owner:
            ship.owner = owner
            ship.add_tag(f"owner:{owner.id}")

        # Set ship stats from template
        ship.db.ship_class = ship_class.value
        ship.db.ship_type = template.name
        ship.db.description = template.description

        # Hull
        ship.db.hull = template.hull_points
        ship.db.max_hull = template.max_hull
        ship.db.armor = template.armor

        # Shields
        ship.db.shields = template.shields
        ship.db.max_shields = template.max_shields

        # Power
        ship.db.power = template.power_output
        ship.db.max_power = template.power_output

        # Movement
        ship.db.speed = template.speed
        ship.db.maneuverability = template.maneuverability

        # Cargo
        ship.db.cargo_capacity = template.cargo_capacity
        ship.db.cargo_used = 0

        # Crew
        ship.db.min_crew = template.min_crew
        ship.db.max_crew = template.max_crew

        # Weapons
        ship.db.weapon_slots = template.weapon_slots
        ship.db.weapons = []

        # Ship status
        ship.db.docked = True
        ship.db.current_sector = None

        await repo.save(ship)
        return cls(ship)

    @property
    def hull(self) -> int:
        return self.obj.db.get("hull", 0)

    @property
    def max_hull(self) -> int:
        return self.obj.db.get("max_hull", 0)

    @property
    def shields(self) -> int:
        return self.obj.db.get("shields", 0)

    @property
    def max_shields(self) -> int:
        return self.obj.db.get("max_shields", 0)

    @property
    def armor(self) -> int:
        return self.obj.db.get("armor", 0)

    @property
    def speed(self) -> int:
        return self.obj.db.get("speed", 0)

    @property
    def is_docked(self) -> bool:
        return self.obj.db.get("docked", True)

    @property
    def is_operational(self) -> bool:
        """Check if ship can operate (has hull integrity)."""
        return self.hull > 0

    def take_damage(self, amount: int) -> dict[str, int]:
        """
        Apply damage to the ship.

        Damage is applied to shields first, then hull (reduced by armor).

        Returns dict with 'shields_damage', 'hull_damage', 'absorbed'.
        """
        result = {"shields_damage": 0, "hull_damage": 0, "absorbed": 0}

        remaining = amount

        # Shields absorb damage first
        shields = self.shields
        if shields > 0:
            shield_damage = min(shields, remaining)
            self.obj.db.shields = shields - shield_damage
            remaining -= shield_damage
            result["shields_damage"] = shield_damage

        # Armor reduces remaining damage
        if remaining > 0:
            armor = self.armor
            absorbed = min(armor, remaining)
            remaining -= absorbed
            result["absorbed"] = absorbed

        # Hull takes remaining damage
        if remaining > 0:
            hull = self.hull
            hull_damage = min(hull, remaining)
            self.obj.db.hull = hull - hull_damage
            result["hull_damage"] = hull_damage

        return result

    def repair_hull(self, amount: int) -> int:
        """Repair hull damage. Returns actual amount repaired."""
        current = self.hull
        max_hull = self.max_hull
        new_hull = min(max_hull, current + amount)
        repaired = new_hull - current
        self.obj.db.hull = new_hull
        return repaired

    def recharge_shields(self, amount: int) -> int:
        """Recharge shields. Returns actual amount recharged."""
        current = self.shields
        max_shields = self.max_shields
        new_shields = min(max_shields, current + amount)
        recharged = new_shields - current
        self.obj.db.shields = new_shields
        return recharged

    def get_status_string(self) -> str:
        """Get a status display for the ship."""
        ship_type = self.obj.db.get("ship_type", "Unknown")
        status = "Docked" if self.is_docked else "In Flight"

        hull_pct = (self.hull / self.max_hull * 100) if self.max_hull > 0 else 0
        if hull_pct >= 75:
            hull_status = "Operational"
        elif hull_pct >= 50:
            hull_status = "Damaged"
        elif hull_pct >= 25:
            hull_status = "Critical"
        elif hull_pct > 0:
            hull_status = "Failing"
        else:
            hull_status = "Destroyed"

        return (
            f"{self.obj.name} ({ship_type})\n"
            f"Status: {status}\n"
            f"Hull: {self.hull}/{self.max_hull} ({hull_status})\n"
            f"Shields: {self.shields}/{self.max_shields}\n"
            f"Armor: {self.armor}"
        )


async def create_ship_prototypes(repo: GameObjectRepository) -> dict[str, GameObject]:
    """
    Create prototype ships for the game.

    These serve as templates players can purchase.
    """
    prototypes = {}

    for ship_class, template in SHIP_TEMPLATES.items():
        ship = await Spaceship.create(
            repo=repo,
            ship_class=ship_class,
            name=f"Prototype {template.name}",
        )
        ship.obj.add_tag("prototype")
        ship.obj.db.cost = template.cost
        prototypes[ship_class.value] = ship.obj
        await repo.save(ship.obj)

    return prototypes
