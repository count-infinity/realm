"""Declared event payloads must match what the engine actually sends.

`docs/reference/softcode.md` tells builders which keys `adata()` will
answer for each action type. It used to be hand-written and was wrong
twice: it claimed `item:on_get` carried `item` (it carries nothing — the
item is `target`), that `item:on_give` carried `giver` (that only exists
on `event:on_receive`), and it filed `on_hitprcnt` under the wrong domain.

Now the table is generated from each event's declaration
(`EventDef.payload`, KERNEL_PLAN 6.2), so it cannot drift from the
declarations; this test keeps the declarations honest by deriving the
truth from source.
"""

from __future__ import annotations

import ast
import glob
import pathlib

from realm.core.action_types import ActionType

REPO = pathlib.Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "reference" / "softcode.md"


def _action_type_value(node: ast.expr) -> str | None:
    """The action type at a construction site: a string literal, or an
    ``ActionType.X`` member (the enum that replaced the literals). Members
    resolve through the real enum, so a stale name here raises KeyError
    rather than silently vanishing from the derived table."""
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if (isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "ActionType"):
        return ActionType[node.attr].value
    return None


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
                if kw.arg == "action_type":
                    atype = _action_type_value(kw.value)
                if kw.arg == "extra" and isinstance(kw.value, ast.Dict):
                    keys = [k.value for k in kw.value.keys
                            if isinstance(k, ast.Constant)]
            if atype is None:
                # positional: fire_event(actor, target, TYPE)
                #             gate_item_action(actor, TYPE, target)
                idx = 2 if name == "fire_event" else 1
                if len(node.args) > idx:
                    atype = _action_type_value(node.args[idx])
            if isinstance(atype, str) and ":" in atype:
                found.setdefault(atype, set()).update(keys or [])
    return found


def declared_payloads() -> dict[str, set[str]]:
    """Every installed EventDef's payload keys (the CLASSIC set)."""
    from realm.core.eventdefs import installed
    return {ev.action_type: set(ev.payload) for ev in installed().events()}


IMPLICIT = {"tool", "target", "actor"}


def test_declared_keys_are_really_sent():
    """No declaration may promise a key the engine never puts in `extra`."""
    engine = engine_payloads()
    lies = []
    for atype, claimed in declared_payloads().items():
        invented = claimed - engine.get(atype, set()) - IMPLICIT
        if invented:
            lies.append(f"{atype}: declares {sorted(invented)}, engine sends "
                        f"{sorted(engine.get(atype, set())) or '(nothing)'}")
    assert not lies, "events declare payloads the engine never sends:\n" \
                     + "\n".join("  " + line for line in lies)


def test_every_sent_key_is_declared():
    """A key the engine sends but no declaration lists is invisible in the
    reference. Declare it (feature.event(..., payload=...))."""
    declared = declared_payloads()
    missing = []
    for atype, keys in engine_payloads().items():
        undeclared = keys - declared.get(atype, set())
        if undeclared:
            missing.append(f"{atype}: engine sends {sorted(undeclared)}")
    assert not missing, "undeclared payload keys:\n" + "\n".join("  " + m for m in missing)


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
