"""
The harness itself: build_lines' fence extraction — heredoc bodies keep
their internal blank lines; block-edge padding is trimmed; blank lines
outside a heredoc are no-ops at the session.
"""

from __future__ import annotations

import pytest

from tests.showcase import harness
from tests.showcase.harness import build, build_lines, find_one, make_sim


DOC = """# 999. Fixture

## Build it

```text
@create widget
drop widget
```

Some prose between blocks.

```text
@set widget/on_poke = '''
a = 1

b = 2
result = a + b
'''
```

## Try it
"""


@pytest.fixture
def fixture_doc(tmp_path, monkeypatch):
    (tmp_path / "999_fixture.md").write_text(DOC, encoding="utf-8")
    monkeypatch.setattr(harness, "DOCS", tmp_path)
    return "999_fixture.md"


def test_internal_blank_lines_survive_extraction(fixture_doc):
    lines = build_lines(fixture_doc)
    body = lines[lines.index("@set widget/on_poke = '''"):]
    assert "" in body                       # the blank inside the heredoc
    assert lines[0] == "@create widget"     # edge padding trimmed
    assert lines[-1] == "'''"


async def test_blank_line_survives_to_the_stored_script(fixture_doc):
    sim = make_sim()
    try:
        room = sim.room("R")
        bilda = sim.player("Bilda", location=room)
        bilda.add_tag("builder")
        await build(sim, bilda, build_lines(fixture_doc))
        widget = find_one(sim, "widget")
        stored = widget.db.get("on_poke")
        assert "a = 1\n\nb = 2" in stored   # the blank line is IN the script
        # ...and the script still runs.
        result, error = await sim.eval(widget, "result = eval_attr(me, 'on_poke')")
        assert error is None and result == 3
    finally:
        sim.close()
