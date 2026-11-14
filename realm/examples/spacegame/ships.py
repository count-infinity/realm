"""
Spaceship system for the space game.

Ships are special GameObjects that can:
- Contain players and cargo
- Travel between sectors
- Engage in ship-to-ship combat
- Be upgraded with components

Ships are pools
---------------
A ship's layered health is data: two pools on the ship object
(``realm.pools``; docs/guides/pools.md). ``shields`` take a hit first and
overflow into ``hull``, which soaks ``armor`` off whatever reaches it, and
the ship is down when the hull is spent::

    pools       = {"shields": {"overflow": "hull"}, "hull": {"soak_attr": "armor"}}
    damage_pool = "shields"
    when_spent  = "none"      # a wrecked ship stays (it may have crew aboard)

So every stock source of harm, a swing, a spell, softcode ``damage()``,
``harm_pool()``, works on a ship with no ship code, ``ON_SPENT`` fires when
the hull gives out, and an ability can cost ``power`` from the same kind of
pool. What is left here is convenience: the template table (which a content
pack could carry as prototypes) and a wrapper whose damage, repair and
recharge are one pool call each.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from realm import pools

if TYPE_CHECKING:
    from realm import GameObject, Store

#: The pool definitions every ship carries (its ``pools`` attribute).
SHIP_POOLS = {"shields": {"overflow": "hull"}, "hull": {"soak_attr": "armor"}}


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
        repo: Store,
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
        from realm import GameObject

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

        # Health: shields over an armored hull (see the module docstring).
        ship.db.pools = dict(SHIP_POOLS)
        ship.db.damage_pool = "shields"
        ship.db.when_spent = "none"
        pools.set_pool(ship, "hull", template.hull_points, max=template.max_hull)
        pools.set_pool(ship, "shields", template.shields, max=template.max_shields)
        ship.db.armor = template.armor

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
        return pools.pool_get(self.obj, "hull") or 0

    @property
    def max_hull(self) -> int:
        return pools.pool_max(self.obj, "hull") or 0

    @property
    def shields(self) -> int:
        return pools.pool_get(self.obj, "shields") or 0

    @property
    def max_shields(self) -> int:
        return pools.pool_max(self.obj, "shields") or 0

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
        """The hull is not spent."""
        return not pools.is_spent(self.obj, "hull")

    def take_damage(self, amount: int) -> pools.PoolChange:
        """Harm the shields, with soak; what they cannot hold spills into
        the hull less its armor. Memory only: ``await settle(change)`` to
        fire ``ON_POOL``/``ON_SPENT`` (and the death path when the hull is
        spent)."""
        return pools.harm(self.obj, "shields", amount, soak=True)

    def repair_hull(self, amount: int) -> int:
        """Mend the hull, up to its max. Returns the amount repaired."""
        return pools.mend(self.obj, "hull", amount).applied

    def recharge_shields(self, amount: int) -> int:
        """Mend the shields, up to their max. Returns the amount recharged."""
        return pools.mend(self.obj, "shields", amount).applied

    def get_status_string(self) -> str:
        """Get a status display for the ship."""
        ship_type = self.obj.db.get("ship_type", "Unknown")
        status = "Docked" if self.is_docked else "In Flight"

        hull_pct = pools.pool_percent(self.obj, "hull") or 0
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


async def create_ship_prototypes(repo: Store) -> dict[str, GameObject]:
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
