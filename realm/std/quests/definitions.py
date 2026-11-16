"""
Quests as data (MUD_PLAN 15.1).

A quest is a ``quest_def`` object. Its attributes:

- ``description``: shown when it is offered and in the journal;
- ``giver``: the NPC that offers it and takes it back (a name, an ``#id``,
  or a matcher dict); None for a quest taken anywhere, which completes the
  moment its last objective is met;
- ``accept_lock``: a lock expression over the player (``caller``);
- ``stages``: an ordered list of ``{"text": ..., "objectives": [...]}``;
- ``rewards``: ``award``, ``credits``, ``items`` (prototypes to clone),
  ``achievement``, ``tags``;
- ``repeatable``: False, or the seconds before it may be taken again;
- ``time_limit``: seconds to finish it, or None;
- ``scope``: ``character`` (the default) or ``account`` (done once per
  account);
- ``on_accept``, ``on_stage``, ``on_complete``, ``on_fail``: softcode.

An objective is a dict with a ``kind``, a ``count`` (default 1), an
optional ``key`` (default: its kind) and ``text``, and a matcher: any of
``id``, ``name``, ``tag`` and ``prototype_vnum``, all of which must agree.
``deliver`` also names the recipient (``to``, a name, ``#id`` or matcher
dict); ``collect`` may say ``consume``; ``custom`` has only its ``key``.

``parse_quest`` raises ``ValueError`` naming the quest, so a malformed
definition is logged and skipped when definitions load
(``realm.core.defs``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.objects import GameObject

KINDS = ("kill", "collect", "deliver", "visit", "talk", "use", "custom")
MATCH_KEYS = ("id", "name", "tag", "prototype_vnum")
OBJECTIVE_KEYS = frozenset({"kind", "count", "key", "text", "consume", "to", *MATCH_KEYS})
REWARD_KEYS = frozenset({"award", "credits", "items", "achievement", "tags"})
SCOPES = ("character", "account")
SCRIPTS = ("on_accept", "on_stage", "on_complete", "on_fail")


def _object_by_id(ident: str) -> GameObject | None:
    from realm.core.world import find_world
    world = find_world()
    store = world.store if world is not None else None
    return store.get_cached(ident.lstrip("#")) if store is not None else None


@dataclass(frozen=True)
class Matcher:
    """What an objective (or a giver) matches: every key given must agree."""

    id: str | None = None
    name: str | None = None
    tag: str | None = None
    prototype_vnum: int | None = None

    def matches(self, obj: GameObject | None) -> bool:
        if obj is None:
            return False
        if self.id is not None and obj.id != self.id:
            return False
        if self.tag is not None and not obj.has_tag(self.tag):
            return False
        if self.prototype_vnum is not None and obj.db.get("prototype_vnum") != self.prototype_vnum:
            return False
        if self.name is not None:
            from realm.core.search import match_objects
            if not match_objects(self.name, [obj], allow_substring=False).matches:
                return False
        return True

    def describe(self) -> str:
        """A short phrase for the journal: the name, else the object the
        id names, else the tag or vnum."""
        if self.name:
            return self.name
        if self.id:
            found = _object_by_id(self.id)
            return found.name if found is not None else f"#{self.id}"
        if self.tag:
            return f"anything tagged {self.tag}"
        return f"vnum {self.prototype_vnum}"


@dataclass(frozen=True)
class Objective:
    kind: str
    key: str
    count: int = 1
    match: Matcher | None = None
    to: Matcher | None = None
    consume: bool = False
    text: str | None = None

    def label(self) -> str:
        """How the journal names it (``text``, else ``kill fido``)."""
        if self.text:
            return self.text
        if self.kind == "custom":
            return self.key
        what = self.match.describe() if self.match is not None else "?"
        if self.kind == "deliver" and self.to is not None:
            return f"deliver {what} to {self.to.describe()}"
        return f"{self.kind} {what}"


@dataclass(frozen=True)
class Stage:
    text: str
    objectives: tuple[Objective, ...]


@dataclass(frozen=True)
class Rewards:
    award: int = 0
    credits: int = 0
    items: tuple[str, ...] = ()
    achievement: str | None = None
    tags: tuple[str, ...] = ()

    def describe(self) -> list[str]:
        out = []
        if self.award:
            out.append(f"award {self.award}")
        if self.credits:
            out.append(f"{self.credits} credits")
        for ref in self.items:
            proto = find_prototype(ref)
            out.append(proto.name if proto is not None else ref)
        if self.achievement:
            out.append(f"the achievement {self.achievement}")
        return out


@dataclass(frozen=True)
class Quest:
    """A parsed ``quest_def``."""

    key: str
    name: str
    description: str
    stages: tuple[Stage, ...]
    giver: Matcher | None = None
    accept_lock: str | None = None
    rewards: Rewards = Rewards()
    repeatable: float | None = None        # None: once; else seconds between
    time_limit: float | None = None
    scope: str = "character"
    scripts: dict[str, str] = field(default_factory=dict, compare=False)
    obj_id: str = field(default="", compare=False)

    def kinds(self) -> frozenset[str]:
        return frozenset(o.kind for s in self.stages for o in s.objectives)

    def stage(self, number: int) -> Stage | None:
        return self.stages[number - 1] if 1 <= number <= len(self.stages) else None


def find_prototype(ref: str) -> GameObject | None:
    """The object an item reward names: an object id (``#rom_obj_3011``
    or without the ``#``), else the one object tagged ``prototype`` with
    that name."""
    ref = str(ref).strip()
    if not ref:
        return None
    found = _object_by_id(ref)
    if found is not None:
        return found
    from realm.core.query import find_objects
    named = [o for o in find_objects(tag="prototype") if o.name.lower() == ref.lower()]
    return named[0] if len(named) == 1 else None


def _matcher(quest: str, where: str, raw: Any, *, required: bool) -> Matcher | None:
    """A matcher from a dict of match keys, or from a string (``#id`` or a
    name)."""
    if raw is None or raw == "":
        if required:
            raise ValueError(f"quest {quest!r}: {where} needs one of {', '.join(MATCH_KEYS)}")
        return None
    if isinstance(raw, str):
        return Matcher(id=raw[1:]) if raw.startswith("#") else Matcher(name=raw.strip())
    if not isinstance(raw, dict):
        raise ValueError(f"quest {quest!r}: {where} must be a name, an #id or a dict")
    unknown = set(raw) - set(MATCH_KEYS)
    if unknown:
        raise ValueError(f"quest {quest!r}: {where} has unknown keys {sorted(unknown)}")
    return _match_fields(quest, where, raw, required=required)


def _match_fields(quest: str, where: str, raw: dict, *, required: bool) -> Matcher | None:
    fields = {k: raw[k] for k in MATCH_KEYS if raw.get(k) not in (None, "")}
    if not fields:
        if required:
            raise ValueError(f"quest {quest!r}: {where} needs one of {', '.join(MATCH_KEYS)}")
        return None
    if "id" in fields:
        fields["id"] = str(fields["id"]).lstrip("#")
    if "name" in fields:
        fields["name"] = str(fields["name"]).strip()
    if "prototype_vnum" in fields:
        try:
            fields["prototype_vnum"] = int(fields["prototype_vnum"])
        except (TypeError, ValueError):
            raise ValueError(f"quest {quest!r}: {where}'s prototype_vnum must be a "
                             f"number") from None
    return Matcher(**fields)


def _count(quest: str, where: str, raw: Any) -> int:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or int(raw) < 1:
        raise ValueError(f"quest {quest!r}: {where}'s count must be a whole number of "
                         f"at least 1")
    return int(raw)


def _objective(quest: str, stage: int, index: int, raw: Any) -> Objective:
    where = f"stage {stage} objective {index}"
    if not isinstance(raw, dict):
        raise ValueError(f"quest {quest!r}: {where} must be a dict")
    kind = str(raw.get("kind") or "").lower()
    if kind not in KINDS:
        raise ValueError(f"quest {quest!r}: {where} has unknown kind {raw.get('kind')!r} "
                         f"(one of {', '.join(KINDS)})")
    unknown = set(raw) - OBJECTIVE_KEYS
    if unknown:
        raise ValueError(f"quest {quest!r}: {where} has unknown keys {sorted(unknown)}")
    if "consume" in raw and kind != "collect":
        raise ValueError(f"quest {quest!r}: {where}: only a collect objective consumes")
    if "to" in raw and kind != "deliver":
        raise ValueError(f"quest {quest!r}: {where}: only a deliver objective has 'to'")
    key = str(raw.get("key") or kind).strip().lower()
    if kind == "custom":
        if not raw.get("key"):
            raise ValueError(f"quest {quest!r}: {where}: a custom objective needs a 'key'")
        if any(raw.get(k) not in (None, "") for k in MATCH_KEYS):
            raise ValueError(f"quest {quest!r}: {where}: a custom objective matches "
                             f"nothing; softcode advances it (quest_advance)")
        match = None
    else:
        match = _match_fields(quest, where, raw, required=True)
    to = _matcher(quest, f"{where}'s 'to'", raw.get("to"), required=kind == "deliver")
    text = raw.get("text")
    return Objective(kind=kind, key=key, count=_count(quest, where, raw.get("count", 1)),
                     match=match, to=to, consume=bool(raw.get("consume")),
                     text=str(text) if text else None)


def _stages(quest: str, raw: Any) -> tuple[Stage, ...]:
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"quest {quest!r} has no stages")
    stages = []
    for number, entry in enumerate(raw, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"quest {quest!r}: stage {number} must be a dict with "
                             f"'text' and 'objectives'")
        objectives = entry.get("objectives")
        if not isinstance(objectives, list) or not objectives:
            raise ValueError(f"quest {quest!r}: stage {number} has no objectives")
        parsed = tuple(_objective(quest, number, i, o)
                       for i, o in enumerate(objectives, start=1))
        keys = [o.key for o in parsed]
        twice = sorted({k for k in keys if keys.count(k) > 1})
        if twice:
            raise ValueError(f"quest {quest!r}: stage {number} has two objectives keyed "
                             f"{twice[0]!r}; give each its own 'key'")
        stages.append(Stage(text=str(entry.get("text") or ""), objectives=parsed))
    return tuple(stages)


def _rewards(quest: str, raw: Any) -> Rewards:
    if raw in (None, {}):
        return Rewards()
    if not isinstance(raw, dict):
        raise ValueError(f"quest {quest!r}: rewards must be a dict")
    unknown = set(raw) - REWARD_KEYS
    if unknown:
        raise ValueError(f"quest {quest!r}: rewards has unknown keys {sorted(unknown)} "
                         f"(known: {', '.join(sorted(REWARD_KEYS))})")
    items = raw.get("items") or []
    items = [items] if isinstance(items, str) else list(items)
    for ref in items:
        if find_prototype(str(ref)) is None:
            raise ValueError(f"quest {quest!r}: reward item {ref!r} names no prototype "
                             f"(an object id, or the name of one object tagged prototype)")
    tags = raw.get("tags") or []
    tags = [tags] if isinstance(tags, str) else list(tags)
    try:
        award, credits = int(raw.get("award") or 0), int(raw.get("credits") or 0)
    except (TypeError, ValueError):
        raise ValueError(f"quest {quest!r}: award and credits must be numbers") from None
    return Rewards(award=award, credits=credits, items=tuple(str(i) for i in items),
                   achievement=str(raw["achievement"]) if raw.get("achievement") else None,
                   tags=tuple(str(t) for t in tags))


def _seconds(quest: str, name: str, raw: Any) -> float | None:
    if raw is None or raw is False:
        return None
    if raw is True:
        return 0.0
    if not isinstance(raw, (int, float)) or raw < 0:
        raise ValueError(f"quest {quest!r}: {name} must be a number of seconds")
    return float(raw)


def parse_quest(obj: GameObject) -> Quest:
    """Read and check a ``quest_def``; ``ValueError`` names what is wrong."""
    name = obj.name.strip()
    scope = str(obj.db.get("scope") or "character").lower()
    if scope not in SCOPES:
        raise ValueError(f"quest {name!r}: scope must be character or account")
    time_limit = _seconds(name, "time_limit", obj.db.get("time_limit"))
    if time_limit == 0:
        raise ValueError(f"quest {name!r}: time_limit must be above 0 (None: no limit)")
    lock = obj.db.get("accept_lock")
    scripts = {s: str(obj.db.get(s)) for s in SCRIPTS if obj.db.get(s)}
    return Quest(
        key=name.lower(), name=name,
        description=str(obj.db.get("description") or ""),
        stages=_stages(name, obj.db.get("stages")),
        giver=_matcher(name, "giver", obj.db.get("giver"), required=False),
        accept_lock=str(lock) if lock else None,
        rewards=_rewards(name, obj.db.get("rewards")),
        repeatable=_seconds(name, "repeatable", obj.db.get("repeatable")),
        time_limit=time_limit, scope=scope, scripts=scripts, obj_id=obj.id)


__all__ = ["KINDS", "Matcher", "Objective", "Quest", "Rewards", "Stage", "find_prototype",
           "parse_quest"]
