"""
Clan governments as data (MUD_PLAN 14.1), after CoffeeMud's
``resources/clangovernments.xml``.

A government is a ``clan_government_def`` object. Its ``positions`` are an
ordered list, highest rank first; each position names the powers it grants.
A power no position holds outright is decided by vote: assignments among
the holders of ``vote_assign``, everything else among the holders of
``vote_other``. A power nobody holds and nobody can vote on cannot be used
in that government.

``parse_government`` reads and checks a definition; it raises
``ValueError`` naming the definition, so a malformed one is logged and
skipped when definitions load (``realm.core.defs``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.objects import GameObject

#: Every power a position may grant (CoffeeMud's ``Clan.Function``, less
#: conquest, enchanting, the morgue, journals, calendars and law books).
POWERS = frozenset({
    "accept", "reject", "assign", "exile", "set_home", "set_donate", "premise",
    "motd_write", "motd_read", "withdraw", "deposit", "deposit_list", "tax", "declare",
    "channel", "list_members", "home_privs", "benefits", "titles", "vote_assign",
    "vote_other",
})
#: The powers that are acts, and so can be put to a vote. The rest are
#: privileges a position simply has or lacks.
VOTABLE = frozenset({
    "accept", "reject", "assign", "exile", "set_home", "set_donate", "premise",
    "motd_write", "withdraw", "tax", "declare",
})
AUTO_PROMOTE = ("none", "rank", "level", "xp", "gold")
BENEFIT_KEYS = frozenset({"level", "tags", "check_mods", "pool_max"})
POSITION_KEYS = frozenset({"id", "name", "plural", "rank", "max", "lock", "public", "powers"})
#: CoffeeMud's ``DEFAULT_XP_FORMULA``: the clan experience a clan of
#: ``level`` needs to reach the next level.
DEFAULT_XP_PER_LEVEL = "500 * level + 1000 * level ** 3"

CAN, VOTE, CANNOT = "can", "vote", "cannot"


@dataclass(frozen=True)
class Position:
    """One position of a government."""

    id: str
    name: str
    plural: str
    rank: int
    max: int | str | None = None          # holders allowed; "5%": that share of members
    lock: str | None = None               # a lock expression a holder must pass
    public: bool = True
    powers: frozenset[str] = frozenset()

    def limit(self, members: int) -> int | None:
        """How many may hold this position in a clan of ``members``
        members; None for no limit. A percentage is at least 1."""
        if self.max is None:
            return None
        if isinstance(self.max, str):
            share = float(self.max.rstrip("%"))
            return max(1, math.ceil(members * share / 100))
        return int(self.max)


@dataclass(frozen=True)
class Government:
    """A parsed ``clan_government_def``."""

    name: str
    description: str
    positions: tuple[Position, ...]
    accept_position: str
    applicant_position: str | None = None
    required_lock: str | None = None
    auto_promote: str = "none"
    category: str = ""
    rivalrous: bool = True
    vote_days: float = 24
    vote_quorum: int = 50
    xp_per_level: str = DEFAULT_XP_PER_LEVEL
    benefits: tuple[dict, ...] = ()
    on_join: str | None = None
    on_leave: str | None = None
    obj_id: str = field(default="", compare=False)

    # --- positions --------------------------------------------------------------

    def position(self, word: str | None) -> Position | None:
        """The position with this id, name or plural (any case), else the
        one whose id or name starts with it."""
        if not word:
            return None
        want = str(word).strip().lower()
        for pos in self.positions:
            if want in (pos.id.lower(), pos.name.lower(), pos.plural.lower()):
                return pos
        found = [p for p in self.positions
                 if p.id.lower().startswith(want) or p.name.lower().startswith(want)]
        return found[0] if len(found) == 1 else None

    @property
    def top(self) -> Position:
        """The first position: where a founder starts."""
        return self.positions[0]

    def top_ids(self) -> set[str]:
        """Every position sharing the top rank (a co-op has two)."""
        return {p.id for p in self.positions if p.rank == self.top.rank}

    # --- powers -----------------------------------------------------------------

    def held(self, power: str) -> bool:
        """Does any position hold ``power`` outright?"""
        return any(power in p.powers for p in self.positions)

    @staticmethod
    def vote_power(power: str) -> str:
        """Who votes on ``power``: ``vote_assign`` for assignments,
        ``vote_other`` for the rest."""
        return "vote_assign" if power == "assign" else "vote_other"

    def voted(self, power: str) -> bool:
        """Is ``power`` decided by vote here? (Nobody holds it, it is an
        act, and some position may vote on it.)"""
        return (power in VOTABLE and not self.held(power)
                and self.held(self.vote_power(power)))

    def usable(self, power: str) -> bool:
        return self.held(power) or self.voted(power)

    def authority(self, position_id: str | None, power: str) -> str:
        """``can`` (the position holds the power), ``vote`` (it may put
        the power to a vote and vote on it) or ``cannot``."""
        pos = self.position(position_id) if position_id else None
        if pos is None:
            return CANNOT
        if power in pos.powers:
            return CAN
        if self.voted(power) and self.vote_power(power) in pos.powers:
            return VOTE
        return CANNOT

    def benefits_at(self, level: int) -> list[dict]:
        return [b for b in self.benefits if int(b.get("level", 1)) <= int(level)]


# --- reading a definition -------------------------------------------------------


def _fail(obj: GameObject, problem: str) -> ValueError:
    return ValueError(f"clan government {obj.name!r}: {problem}")


def _check_expression(obj: GameObject, what: str, expression: Any) -> str | None:
    if expression in (None, ""):
        return None
    from realm.core.safe_eval import compile_expression
    try:
        compile_expression(str(expression))
    except ValueError as exc:
        raise _fail(obj, f"{what} {expression!r} is not a valid expression ({exc})") from None
    return str(expression)


def _max(obj: GameObject, pid: str, value: Any) -> int | str | None:
    if value is None:
        return None
    if isinstance(value, str) and value.endswith("%"):
        try:
            share = float(value[:-1])
        except ValueError:
            share = -1.0
        if 0 < share <= 100:
            return value
    elif isinstance(value, int) and not isinstance(value, bool) and value >= 1:
        return value
    raise _fail(obj, f"position {pid!r} has max {value!r}; use a whole number of at "
                     f"least 1, a percentage like '5%', or None for no limit")


def _position(obj: GameObject, raw: Any) -> Position:
    if not isinstance(raw, dict):
        raise _fail(obj, f"each position must be a dict (got {raw!r})")
    unknown = set(raw) - POSITION_KEYS
    if unknown:
        raise _fail(obj, f"position {raw.get('id')!r} has unknown key(s) {sorted(unknown)}; "
                         f"known: {sorted(POSITION_KEYS)}")
    pid = str(raw.get("id") or "").strip().lower()
    if not pid:
        raise _fail(obj, f"a position has no id: {raw!r}")
    rank = raw.get("rank")
    if not isinstance(rank, int) or isinstance(rank, bool) or rank < 0:
        raise _fail(obj, f"position {pid!r} needs a rank, a whole number from 0 (highest)")
    powers = raw.get("powers") or []
    if not isinstance(powers, list):
        raise _fail(obj, f"position {pid!r}: powers must be a list")
    unknown_powers = sorted({str(p) for p in powers} - POWERS)
    if unknown_powers:
        raise _fail(obj, f"position {pid!r} names unknown power(s) {unknown_powers}; "
                         f"known: {sorted(POWERS)}")
    name = str(raw.get("name") or pid.replace("_", " ").title())
    return Position(
        id=pid, name=name, plural=str(raw.get("plural") or f"{name}s"), rank=rank,
        max=_max(obj, pid, raw.get("max")),
        lock=_check_expression(obj, f"position {pid!r} lock", raw.get("lock")),
        public=bool(raw.get("public", True)), powers=frozenset(str(p) for p in powers))


def _benefit(obj: GameObject, raw: Any) -> dict:
    if not isinstance(raw, dict) or set(raw) - BENEFIT_KEYS:
        raise _fail(obj, f"a benefit must be a dict of {sorted(BENEFIT_KEYS)} (got {raw!r})")
    level = raw.get("level", 1)
    if not isinstance(level, int) or isinstance(level, bool) or level < 1:
        raise _fail(obj, f"a benefit's level must be a whole number from 1 (got {level!r})")
    tags = raw.get("tags") or []
    mods = raw.get("check_mods") or {}
    pools = raw.get("pool_max") or {}
    if not isinstance(tags, list) or not isinstance(mods, dict) or not isinstance(pools, dict):
        raise _fail(obj, f"a benefit's tags must be a list and its check_mods and pool_max "
                         f"dicts (got {raw!r})")
    for value in [*mods.values(), *pools.values()]:
        if not isinstance(value, int) or isinstance(value, bool):
            raise _fail(obj, f"a benefit's check_mods and pool_max take whole numbers "
                             f"(got {raw!r})")
    return {"level": level, "tags": [str(t) for t in tags],
            "check_mods": {str(k): int(v) for k, v in mods.items()},
            "pool_max": {str(k): int(v) for k, v in pools.items()}}


def parse_government(obj: GameObject) -> Government:
    """Read and check a ``clan_government_def`` (the ``def_kind`` parser)."""
    db = obj.db
    raw_positions = db.get("positions")
    if not isinstance(raw_positions, list) or not raw_positions:
        raise _fail(obj, "it has no positions (a list, highest rank first)")
    positions = tuple(_position(obj, p) for p in raw_positions)
    ids = [p.id for p in positions]
    if len(set(ids)) != len(ids):
        raise _fail(obj, f"two positions share an id: {ids}")
    if any(b.rank < a.rank for a, b in zip(positions, positions[1:], strict=False)):
        raise _fail(obj, "positions must be listed highest rank first (rank 0 first)")
    accept = str(db.get("accept_position") or "").strip().lower()
    if accept not in ids:
        raise _fail(obj, f"accept_position {db.get('accept_position')!r} is not one of its "
                         f"positions {ids}")
    applicant = db.get("applicant_position")
    if applicant is not None:
        applicant = str(applicant).strip().lower()
        if applicant not in ids:
            raise _fail(obj, f"applicant_position {db.get('applicant_position')!r} is not "
                             f"one of its positions {ids}")
    auto = str(db.get("auto_promote") or "none").lower()
    if auto not in AUTO_PROMOTE:
        raise _fail(obj, f"auto_promote {auto!r} is not one of {list(AUTO_PROMOTE)}")
    days = db.get("vote_days", 24)
    quorum = db.get("vote_quorum", 50)
    if not isinstance(days, (int, float)) or isinstance(days, bool) or days <= 0:
        raise _fail(obj, f"vote_days must be a number of game days above 0 (got {days!r})")
    if not isinstance(quorum, int) or isinstance(quorum, bool) or not 0 <= quorum <= 100:
        raise _fail(obj, f"vote_quorum must be a percentage from 0 to 100 (got {quorum!r})")
    benefits = db.get("benefits") or []
    if not isinstance(benefits, list):
        raise _fail(obj, "benefits must be a list")
    return Government(
        name=obj.name.strip().lower(), description=str(db.get("description") or ""),
        positions=positions, accept_position=accept, applicant_position=applicant,
        required_lock=_check_expression(obj, "required_lock", db.get("required_lock")),
        auto_promote=auto, category=str(db.get("category") or "").strip().lower(),
        rivalrous=bool(db.get("rivalrous", True)), vote_days=float(days),
        vote_quorum=int(quorum),
        xp_per_level=_check_expression(obj, "xp_per_level", db.get("xp_per_level"))
        or DEFAULT_XP_PER_LEVEL,
        benefits=tuple(_benefit(obj, b) for b in benefits),
        on_join=db.get("on_join") or None, on_leave=db.get("on_leave") or None,
        obj_id=obj.id)


def governments() -> dict[str, Government]:
    """Every government that reads, by name."""
    from realm.core.defs import all_defs
    return all_defs("clan_government")


def government(name: str | None) -> Government | None:
    """A government by exact name, else a unique prefix."""
    if not name:
        return None
    from realm.core.defs import find_def
    return find_def("clan_government", str(name))


__all__ = ["POWERS", "VOTABLE", "AUTO_PROMOTE", "DEFAULT_XP_PER_LEVEL", "CAN", "VOTE",
           "CANNOT", "Position", "Government", "parse_government", "governments",
           "government"]
