"""
Generate the spacegame world as an importable area file.

Runs the existing Python builders (world.py + nexagen.py) once and exports
everything to ``examples/spacegame/data/areas/station.json`` — worldio
data the game imports at first boot instead of building line-by-line.
The Python builders are the authoring source; this file is the artifact.

    python scripts/build_spacegame_area.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "examples" / "spacegame"))

OUT = ROOT / "examples" / "spacegame" / "data" / "areas" / "station.json"


class _Collect:
    """A minimal repo that just remembers everything saved."""

    def __init__(self):
        self._objs = {}

    async def save(self, obj):
        self._objs[obj.id] = obj

    def all(self):
        return list(self._objs.values())


async def build() -> None:
    # Register the behavior kit so NPCs' behaviors (e.g. the guard's Guard
    # behavior) attach and get exported — world.py silently skips a behavior
    # that isn't registered.
    from nexagen import create_nexagen
    from world import create_world

    import realm.behaviors  # noqa: F401
    import realm.combat.behaviors  # noqa: F401
    from realm.persistence.worldio import export_objects

    repo = _Collect()
    world = await create_world(repo)
    await create_nexagen(repo, world["promenade"])

    # The docking bay is where players spawn — tag it so the imported world
    # carries its own start room (no post-import fixup needed).
    world["docking_bay"].add_tag("start_room")

    data = export_objects(repo.all())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2) + "\n")
    print(f"  wrote {OUT.relative_to(ROOT)} ({len(data['objects'])} objects)")


if __name__ == "__main__":
    asyncio.run(build())
