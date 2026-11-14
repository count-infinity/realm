"""
One way to build an object from data (KERNEL_PLAN 5.3).
"""

from __future__ import annotations

from realm.scripting.scripted_behavior import ScriptedBehavior
from realm.core.inflate import inflate


def test_spec_fields_land():
    obj = inflate({"name": "lamp", "description": "Brass.", "tags": ["thing"],
                   "attrs": {"lit": True}, "locks": {"use": "True"},
                   "behaviors": [{"behavior_id": "decay", "params": {"ticks": 3}}]},
                  obj_id="lamp-1")
    assert (obj.id, obj.name, obj.description) == ("lamp-1", "lamp", "Brass.")
    assert obj.has_tag("thing") and obj.db.get("lit") is True
    assert obj.locks == {"use": "True"}
    assert [b.behavior_id for b in obj.get_behaviors()] == ["decay"]


def test_strict_drops_unknown_behaviors_and_reports_them_once(caplog):
    spec = {"name": "imp", "behaviors": [{"behavior_id": "nope"},
                                         {"behavior_id": "nope"},
                                         {"behavior_id": "nada"}]}
    with caplog.at_level("WARNING", logger="realm.core.inflate"):
        obj = inflate(spec, strict_behaviors=True)
    assert obj.get_behaviors() == []
    messages = [r.getMessage() for r in caplog.records]
    assert len(messages) == 1 and "nada, nope" in messages[0]


def test_lenient_keeps_a_placeholder_for_a_later_def():
    obj = inflate({"name": "imp", "behaviors": [{"behavior_id": "later_def"}]})
    [behavior] = obj.get_behaviors()
    assert isinstance(behavior, ScriptedBehavior)
    assert behavior.behavior_id == "later_def"
