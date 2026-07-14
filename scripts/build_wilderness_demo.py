"""
Generate the frontier demo wilderness as an importable area file.

Runs the example builder (examples/wilderness/frontier.py) once and
exports the persistent seam — trailhead, region master, gate — to
``examples/wilderness/data/frontier.json``. Cells are never exported;
they materialize when someone walks. Import with ``preserve_ids=True``
(the canonical first-boot path): the provider softcode embeds the
trailhead's id, and id remapping does not rewrite softcode.

    python scripts/build_wilderness_demo.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "examples" / "wilderness"))

OUT = ROOT / "examples" / "wilderness" / "data" / "frontier.json"


class _Collect:
    """A minimal repo that just remembers everything saved."""

    def __init__(self):
        self._objs = {}

    async def save(self, obj):
        self._objs[obj.id] = obj

    def all(self):
        return list(self._objs.values())


async def build() -> None:
    from frontier import create_frontier

    from realm.persistence.worldio import export_objects

    repo = _Collect()
    await create_frontier(repo)

    data = export_objects(repo.all())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2) + "\n")
    print(f"  wrote {OUT.relative_to(ROOT)} ({len(data['objects'])} objects)")


if __name__ == "__main__":
    asyncio.run(build())
