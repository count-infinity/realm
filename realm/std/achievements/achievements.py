"""
Achievements (MUD_PLAN 6.5).

An ``achievement_def`` object names an achievement: its ``description``,
``hidden`` (not listed until earned), ``scope`` (``account``, the default,
or ``character``) and ``grants``: ``{"tags": [...], "check_mods":
{"will": 1, "all": 0}}``. Softcode ``grant_achievement`` records it once,
with a timestamp, in ``achievements`` on the account (or on the character,
for that scope), tells the player, fires ``account:on_achievement``, and
applies the grants: the tags go on every character of the account (now,
and at each login, so a character made later gets them) and the check
modifiers count in every check those characters make.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from realm.core.action_types import ActionType
from realm.std.accounts.account import account_of, characters_of

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.propagation import Action

ACHIEVEMENT_EVENT = "account:on_achievement"

#: character id -> {skill or "all": modifier}; cleared whenever an
#: achievement is granted or definitions reload.
_mod_cache: dict[str, dict[str, int]] = {}


def clear_cache(_world: Any = None) -> None:
    _mod_cache.clear()


def definitions() -> dict[str, GameObject]:
    from realm.core.defs import def_objects
    return def_objects("achievement")


def definition(name: str) -> GameObject | None:
    return definitions().get(str(name).strip().lower())


def _account_scoped(adef: GameObject) -> bool:
    return str(adef.db.get("scope") or "account").lower() != "character"


def earned(obj: GameObject) -> dict[str, float]:
    """Every achievement ``obj`` has earned, by name: its account's and
    its own."""
    out: dict[str, float] = {}
    account = account_of(obj)
    for holder in (account, obj):
        record = holder.db.get("achievements") if holder is not None else None
        if isinstance(record, dict):
            out.update(record)
    return out


def has(obj: GameObject, name: str) -> bool:
    adef = definition(name)
    key = adef.name if adef is not None else str(name)
    return key in earned(obj)


def _holder(obj: GameObject, adef: GameObject) -> GameObject:
    account = account_of(obj)
    return account if _account_scoped(adef) and account is not None else obj


def _grants(adef: GameObject) -> dict:
    grants = adef.db.get("grants")
    return grants if isinstance(grants, dict) else {}


def _apply_tags(obj: GameObject, adef: GameObject) -> None:
    targets = characters_of(account_of(obj)) if _account_scoped(adef) else []
    for character in targets or [obj]:
        for tag in _grants(adef).get("tags") or []:
            character.add_tag(str(tag))


async def grant(obj: GameObject, name: str) -> bool:
    """Record ``name`` for ``obj`` (once), tell them, apply the grants and
    fire the event. False when there is no such achievement or it is
    already earned."""
    from realm.core.propagation import Action, propagate
    from realm.core.world import find_world
    adef = definition(name)
    if adef is None or has(obj, adef.name):
        return False
    holder = _holder(obj, adef)
    record = dict(holder.db.get("achievements") or {})
    record[adef.name] = time.time()
    holder.db.achievements = record
    _apply_tags(obj, adef)
    clear_cache()
    obj.msg(f"Achievement earned: {adef.name}!")
    world = find_world()
    if world is not None and world.store is not None:
        await world.store.save(holder)
    # The literal type string (ACHIEVEMENT_EVENT): the payload docs check
    # reads action types from the source.
    await propagate(Action(actor=obj, target=obj, action_type="account:on_achievement",
                           extra={"achievement": adef.name}))
    return True


def achievement_modifier(obj: GameObject, skill: str) -> int:
    """``feature.check_modifier``: what the character's earned
    achievements add to a check of ``skill``."""
    if not obj.is_player:
        return 0
    mods = _mod_cache.get(obj.id)
    if mods is None:
        mods = {}
        for name in earned(obj):
            adef = definition(name)
            if adef is None:
                continue
            for key, value in (_grants(adef).get("check_mods") or {}).items():
                mods[str(key)] = mods.get(str(key), 0) + int(value)
        _mod_cache[obj.id] = mods
    return mods.get(skill, 0) + mods.get("all", 0)


async def login_observer(action: Action) -> None:
    """At login, a character takes the tags of everything its account has
    earned (a character made after the achievement gets them too)."""
    if action.action_type != ActionType.CONNECT or action.actor is None:
        return
    character = action.actor
    for name in earned(character):
        adef = definition(name)
        if adef is not None:
            for tag in _grants(adef).get("tags") or []:
                character.add_tag(str(tag))


async def cmd_achievements(ctx) -> None:
    """
    List your achievements: those earned, with when, and those still to
    earn (a hidden one only shows once it is earned).

    Usage: achievements
    """
    mine = earned(ctx.player)
    defs = sorted(definitions().values(), key=lambda o: o.name)
    lines = ["Achievements earned:"]
    got = [d for d in defs if d.name in mine]
    for adef in got:
        when = time.strftime("%Y-%m-%d", time.gmtime(float(mine[adef.name])))
        lines.append(f"  {adef.name:24} {when}  {adef.db.get('description') or ''}")
    if not got:
        lines.append("  none yet")
    todo = [d for d in defs if d.name not in mine and not d.db.get("hidden")]
    hidden = [d for d in defs if d.name not in mine and d.db.get("hidden")]
    if todo:
        lines.append("Still to earn:")
        lines.extend(f"  {d.name:24} {d.db.get('description') or ''}" for d in todo)
    if hidden:
        lines.append(f"...and {len(hidden)} hidden achievement"
                     f"{'s' if len(hidden) != 1 else ''} still to find.")
    await ctx.session.send("\n".join(lines))


__all__ = ["ACHIEVEMENT_EVENT", "clear_cache", "definitions", "definition", "earned", "has",
           "grant", "achievement_modifier", "login_observer", "cmd_achievements"]
