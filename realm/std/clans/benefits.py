"""
Clan benefits (MUD_PLAN 14.4), applied the way achievements are (6.5).

Each ``benefits`` entry of a government (``{level, tags, check_mods,
pool_max}``) at or below a clan's level reaches the members whose position
has the ``benefits`` power. Tags and pool-maximum bonuses are written on
the character and remembered (``clan_tags``, ``clan_pool_bonus``), so
``refresh`` can take back exactly what clans gave: it runs at login and
whenever a member joins, leaves, changes position or the clan's level
changes. Check modifiers count through ``feature.check_modifier``, from a
cache that ``refresh`` drops.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject

TAGS_LEDGER = "clan_tags"
POOLS_LEDGER = "clan_pool_bonus"

#: character id -> {skill or "all": modifier}
_mod_cache: dict[str, dict[str, int]] = {}


def clear_cache(_world=None) -> None:
    _mod_cache.clear()


def granted(obj: GameObject) -> list[dict]:
    """Every benefit entry ``obj`` enjoys now, across its clans."""
    from realm.std.clans.clans import clans_of, government_of, has_power, is_member
    out = []
    for clan in clans_of(obj):
        gov = government_of(clan)
        if gov is None or not is_member(clan, obj) or not has_power(clan, obj, "benefits"):
            continue
        out.extend(gov.benefits_at(int(clan.db.get("level") or 1)))
    return out


def refresh(obj: GameObject) -> None:
    """Bring ``obj``'s clan tags and pool bonuses in line with what its
    clans grant now, and drop its cached check modifiers."""
    from realm.core.pools import has_pool, pool_get, pool_max, set_pool
    _mod_cache.pop(obj.id, None)
    benefits = granted(obj)
    want_tags = {t for b in benefits for t in b["tags"]}
    given = set(obj.db.get(TAGS_LEDGER) or [])
    for tag in given - want_tags:
        obj.remove_tag(tag)
    ours = given & want_tags
    for tag in want_tags - given:
        if not obj.has_tag(tag):            # one it already had is not ours to take
            obj.add_tag(tag)
            ours.add(tag)
    kept = sorted(ours)
    if kept:
        obj.db.set(TAGS_LEDGER, kept)
    elif obj.db.get(TAGS_LEDGER) is not None:
        obj.db.delete(TAGS_LEDGER)

    want_pools: dict[str, int] = {}
    for b in benefits:
        for pool, amount in b["pool_max"].items():
            want_pools[pool] = want_pools.get(pool, 0) + amount
    had = dict(obj.db.get(POOLS_LEDGER) or {})
    applied: dict[str, int] = {}
    for pool in set(want_pools) | set(had):
        delta = want_pools.get(pool, 0) - int(had.get(pool, 0))
        current = pool_max(obj, pool) if has_pool(obj, pool) else None
        if current is None:
            continue                         # no such pool (or unbounded): nothing to raise
        if delta:
            maximum = max(0, current + delta)
            value = int(pool_get(obj, pool) or 0)
            set_pool(obj, pool, min(value, maximum), max=maximum)
        if want_pools.get(pool, 0):
            applied[pool] = want_pools[pool]
    if applied:
        obj.db.set(POOLS_LEDGER, applied)
    elif obj.db.get(POOLS_LEDGER) is not None:
        obj.db.delete(POOLS_LEDGER)


def benefit_modifier(obj: GameObject, skill: str) -> int:
    """``feature.check_modifier``: what ``obj``'s clan benefits add to a
    check of ``skill``."""
    if not obj.is_player:
        return 0
    mods = _mod_cache.get(obj.id)
    if mods is None:
        mods = {}
        for benefit in granted(obj):
            for key, value in benefit["check_mods"].items():
                mods[key] = mods.get(key, 0) + int(value)
        _mod_cache[obj.id] = mods
    return mods.get(skill, 0) + mods.get("all", 0)


__all__ = ["TAGS_LEDGER", "POOLS_LEDGER", "clear_cache", "granted", "refresh",
           "benefit_modifier"]
