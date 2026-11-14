"""
The "Where things go" table that opens docs/guides/features.md (KERNEL_PLAN
9.5): every row links to an example further down, and every example runs.

The examples share one preamble (``feature = Feature("mygame")``). Each is
executed into it in order; then the feature is loaded into a world with
the Simulator, and a few declarations are exercised.
"""

from __future__ import annotations

import re
import sys
import types
from pathlib import Path

import pytest

GUIDE = Path(__file__).resolve().parent.parent / "docs" / "guides" / "features.md"
FENCE = re.compile(r"^```python\n(.*?)^```", re.S | re.M)


def _section(title: str) -> str:
    text = GUIDE.read_text()
    start = text.index(f"\n## {title}\n")
    end = text.find("\n## ", start + 1)
    return text[start:end if end != -1 else None]


def test_the_guide_opens_with_the_table():
    text = GUIDE.read_text()
    first = text.index("\n## ")
    assert text[first:].startswith("\n## Where things go\n")
    table = _section("Where things go")
    rows = [line for line in table.splitlines() if line.startswith("| [")]
    assert len(rows) == 12
    examples = _section("Where things go: examples")
    anchors = {re.sub(r"[^a-z0-9 -]", "", h.lower()).replace(" ", "-")
               for h in re.findall(r"^### (.+)$", examples, re.M)}
    for row in rows:
        anchor = re.search(r"\]\(#([^)]+)\)", row).group(1)
        assert anchor in anchors, row


@pytest.fixture
def example_module():
    blocks = FENCE.findall(_section("Where things go: examples"))
    module = types.ModuleType("where_things_go_example")
    for block in blocks:
        if block.lstrip().startswith("# doctest: skip"):
            continue
        exec(compile(block, str(GUIDE), "exec"), module.__dict__)
    sys.modules[module.__name__] = module
    try:
        yield module
    finally:
        del sys.modules[module.__name__]


@pytest.mark.asyncio
async def test_every_example_runs(example_module):
    from realm.scripting.registry import registered
    from realm.testing import Simulator

    feature = example_module.feature
    with Simulator(features=["look", "where_things_go_example"]) as sim:
        assert sim.world.setting("WEATHER_SEED") == 1
        assert "shields" in sim.world.pools
        assert registered()["double"].fn(4) == 8
        room = sim.room("Square")
        ann = sim.player("Ann", location=room)
        await sim.do(ann, "wave")
        assert "You wave." in sim.seen(ann)
        from realm import fire_event
        room.db.on_rain = "set_attr(me, 'wet', adata('strength'))"
        await fire_event(ann, room, "weather:on_rain", extra={"strength": 3})
        assert room.db.wet == 3                        # the event and its ON_RAIN hook
        assert ann.db.actions == 1                     # the observer counted it
    assert len(feature.commands) == 1 and len(feature.lock_types) == 1
