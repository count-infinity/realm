"""The documented payload table must match what the engine actually sends.

`docs/reference/softcode.md` tells builders which keys `adata()` will
answer for each action type. It was hand-written and it was wrong twice:
it claimed `item:on_get` carried `item` (it carries nothing — the item is
`target`), that `item:on_give` carried `giver` (that only exists on
`event:on_receive`), and it filed `on_hitprcnt` under the wrong domain.
A builder following a wrong row gets `None` and no explanation.

So: derive the truth from source and assert the doc agrees. A claimed key
that the engine never sends is a lie in the reference; this test finds it.
"""

from __future__ import annotations

import ast
import glob
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "reference" / "softcode.md"


def engine_payloads() -> dict[str, set[str]]:
    """Every action type the engine constructs, and the `extra` keys it
    carries. Covers the three construction sites: Action(...),
    fire_event(actor, target, TYPE, ...) and gate_item_action(actor, TYPE,
    target, ...)."""
    found: dict[str, set[str]] = {}
    for path in glob.glob(str(REPO / "realm" / "**" / "*.py"), recursive=True):
        try:
            tree = ast.parse(pathlib.Path(path).read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", getattr(node.func, "attr", ""))
            if name not in ("Action", "fire_event", "gate_item_action"):
                continue
            atype, keys = None, None
            for kw in node.keywords:
                if kw.arg == "action_type" and isinstance(kw.value, ast.Constant):
                    atype = kw.value.value
                if kw.arg == "extra" and isinstance(kw.value, ast.Dict):
                    keys = [k.value for k in kw.value.keys
                            if isinstance(k, ast.Constant)]
            if atype is None:
                # positional: fire_event(actor, target, TYPE)
                #             gate_item_action(actor, TYPE, target)
                idx = 2 if name == "fire_event" else 1
                if len(node.args) > idx and isinstance(node.args[idx], ast.Constant):
                    atype = node.args[idx].value
            if isinstance(atype, str) and ":" in atype:
                found.setdefault(atype, set()).update(keys or [])
    return found


def documented_payloads() -> dict[str, set[str]]:
    """Rows of the doc's payload table: `| `type` / `type` | `a`, `b` |`."""
    body = DOC.read_text()
    section = re.search(r"Payloads carried today.*?(?=\n#{2,3} |\n```)", body, re.S)
    assert section, "payload table not found in the softcode reference"
    out: dict[str, set[str]] = {}
    for line in section.group(0).splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 2 or cells[0].lower().startswith("action"):
            continue
        types = re.findall(r"`([a-z_]+:[a-z_]+)`", cells[0])
        # Bare continuations like `/ `shout`` inherit the row's domain.
        domain = types[0].split(":")[0] if types else None
        for frag in re.findall(r"`([a-z_]+)`", cells[0]):
            if ":" not in frag and domain and f"{domain}:{frag}" not in types:
                types.append(f"{domain}:{frag}")
        if "none" in cells[1].lower() or "*(" in cells[1]:
            keys: set[str] = set()
        else:
            keys = set(re.findall(r"`([a-z_]+)`", cells[1]))
        for t in types:
            out.setdefault(t, set()).update(keys)
    assert out, "parsed no rows from the payload table"
    return out


def test_documented_keys_are_really_sent():
    """No row may promise a key the engine never puts in `extra`."""
    engine = engine_payloads()
    lies = []
    for atype, claimed in documented_payloads().items():
        if atype not in engine:
            continue          # doc may group/alias; absence isn't a lie
        invented = claimed - engine[atype] - {"tool", "target", "actor"}
        if invented:
            lies.append(f"{atype}: doc promises {sorted(invented)}, "
                        f"engine sends {sorted(engine[atype]) or '(nothing)'}")
    assert not lies, "reference doc promises payloads the engine never sends:\n" \
                     + "\n".join("  " + line for line in lies)


def test_the_two_rows_that_were_wrong_stay_right():
    """Regression: these are the exact claims that were false."""
    engine = engine_payloads()
    # get/drop carry nothing — the item is the action's target.
    assert engine.get("item:on_get") == set()
    assert engine.get("item:on_drop") == set()
    # give carries the item, but NOT the giver...
    assert engine.get("item:on_give") == {"item"}
    # ...`giver` lives only on the recipient-side event.
    assert engine.get("event:on_receive") == {"item", "giver"}


def test_payloads_the_showcase_relies_on_exist():
    """Tutorials read these by name; if the engine stops sending one, the
    tutorial silently reads None."""
    engine = engine_payloads()
    assert "amount" in engine.get("event:payment", set())
    assert {"damage"} <= engine.get("combat:on_damage", set())
    assert {"killer", "fatal"} <= engine.get("combat:on_death", set())
    assert "pose" in engine.get("event:emote", set())
    assert "message" in engine.get("event:speech", set())
    assert "reason" in engine.get("event:on_fail", set())
