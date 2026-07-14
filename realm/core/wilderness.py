"""
Wilderness — coordinate-keyed ephemeral cells, materialized on demand.
See docs/design/wilderness-requirements.md (the executable spec) and
docs/design/ephemeral-rooms.md (the parent design).

A **region** is a persistent master object tagged ``wilderness_region``
whose name is the region id. Its softcode attributes are the
**map-provider**, evaluated per coordinate with ``x``/``y`` bound as named
globals: ``is_valid`` (bounds), ``cell_name``, ``cell_desc``,
``cell_exits`` (open directions, default the 4-way compass; an entry may
also be a ``{"name": ..., "destination": ...}`` dict for an authored exit
back to the persistent world), ``cell_terrain`` (extra tags). ``is_valid``
and ``cell_exits`` must be pure functions of the coordinate — cells reap
and re-materialize constantly, and nondeterminism there mutates topology.

A **cell** is an ephemeral room shared by everyone at its ``(region, x,
y)`` (north is +y). Its directional exits are *real* exits with a
deferred destination (``db.dest_resolver = "wilderness"``): the movement
kernel calls :func:`resolve_wilderness_exit` after the origin-side gates
pass, the neighbor is get-or-created, and the traversal proceeds like any
door — wards, locks, ``on_enter``, follower cascade unchanged.

Cells are never persisted and are reaped once empty of players past the
region's ``idle_ttl``; teardown follows the shared R9 disposition
(``realm.core.teardown``). The live-cell index here is the lookup —
``cell_for`` runs on every step, and tag scans are linear in the whole
cache.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from realm.core.movement import register_dest_resolver
from realm.core.query import find_objects
from realm.core.teardown import (
    EPHEMERAL_TAG,
    release_contents,
    subtree_has_player,
)

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)

REGION_TAG = "wilderness_region"      # opt-in mark on a region master
RESOLVER_NAME = "wilderness"          # exits: db.dest_resolver = this

# Wilderness cells re-derive from a few provider evals — unlike instances,
# which re-import a whole zone — so the TTL is only a walk-back-rejoin
# grace, and a short one keeps a sprinting player's trail of empty cells
# small (~60 cells at one step per 2s, vs ~450 at the instance default).
DEFAULT_IDLE_TTL = 120.0

DIRECTIONS: dict[str, tuple[int, int]] = {
    "north": (0, 1), "south": (0, -1), "east": (1, 0), "west": (-1, 0),
    "northeast": (1, 1), "northwest": (-1, 1),
    "southeast": (1, -1), "southwest": (-1, -1),
}
_ALIASES = {
    "north": ["n"], "south": ["s"], "east": ["e"], "west": ["w"],
    "northeast": ["ne"], "northwest": ["nw"],
    "southeast": ["se"], "southwest": ["sw"],
}
DEFAULT_EXITS = ["north", "south", "east", "west"]

# Tags a cell_populate spawn must never carry: identity-bearing tags
# that would let a prototype impersonate a player (hold cells open, get
# evacuated), a room/exit, or an evacuation floor. Stripped loudly.
SPAWN_TAG_DENYLIST = frozenset({
    "player", "room", "exit", "start_room",
    REGION_TAG, "instance_template", "instance_master", "instance_entry",
})

# The live-cell index — THE lookup (identity tags are for debugging and
# zone tooling, never for lookup). Entries are validated against the
# active persistence cache on read, so a stale world (tests, reboots)
# can't serve a dead cell.
_cells: dict[tuple[str, int, int], GameObject] = {}
_regions: dict[str, GameObject] = {}
# In-flight builds, keyed by coordinate: the provider evals inside
# materialize_cell genuinely yield (they run off-loop), so two walkers
# stepping into one unmaterialized coord in the same window must share
# a single build — not each get a cell, doubling the encounter and
# leaking the loser outside the index where no reaper can see it.
_pending: dict[tuple[str, int, int], asyncio.Task] = {}


class ProviderError(Exception):
    """A map-provider attribute failed to evaluate — a builder bug, not a
    map edge. Never collapsed into 'invalid coordinate' (R10)."""


def _clock() -> float:
    return time.time()


def _cell_tag(region: str, x: int, y: int) -> str:
    return f"wildcell:{region}:{x},{y}"


def _region_zone(region: str) -> str:
    return f"zone:wilderness:{region}"


def _cache_live(obj: GameObject | None) -> bool:
    """Is this object still the live, registered copy?"""
    if obj is None:
        return False
    from realm.persistence.manager import get_active_manager
    manager = get_active_manager()
    return manager is None or manager.get_cached(obj.id) is obj


def reset() -> None:
    """Drop the module indexes (test hygiene / world teardown)."""
    _cells.clear()
    _regions.clear()
    _pending.clear()


def get_region(region: str) -> GameObject | None:
    """The region's master object (tag ``wilderness_region``, name ==
    region id), via a small validated cache."""
    region = str(region)
    cached = _regions.get(region)
    if cached is not None and _cache_live(cached) and cached.name == region:
        return cached
    _regions.pop(region, None)
    for candidate in find_objects(tag=REGION_TAG):
        if candidate.name == region:
            _regions[region] = candidate
            return candidate
    return None


def cell_for(region: str, x: int, y: int) -> GameObject | None:
    """The live cell at this coordinate, or None. Index lookup only."""
    key = (str(region), int(x), int(y))
    cell = _cells.get(key)
    if cell is None:
        return None
    if not _cache_live(cell):
        _cells.pop(key, None)
        return None
    return cell


def _provider_set(region_obj: GameObject, attr: str) -> bool:
    code = region_obj.db.get(attr)
    return isinstance(code, str) and bool(code.strip())


async def _eval_provider(region_obj: GameObject, attr: str,
                         x: int, y: int, *, persistence):
    """Run one map-provider attribute with ``x``/``y`` bound as named
    globals. The region master is both enactor and executor — a provider
    is a pure function of the coordinate, never of who is walking (R2
    determinism; a shared cell must not bake the first walker into what
    everyone sees). Runs off-loop (``execute_async``) so a slow provider
    can't stall the server. Raises :class:`ProviderError` on any script
    failure."""
    code = region_obj.db.get(attr)
    from realm.scripting.functions import ScriptFunctions
    from realm.scripting.sandbox import (
        ScriptContext,
        ScriptError,
        ScriptSandbox,
    )
    ctx = ScriptContext(
        enactor=region_obj,
        executor=region_obj,
        location=region_obj.location,
        extra={"x": int(x), "y": int(y)},
    )
    functions = ScriptFunctions(
        enactor=region_obj, executor=region_obj,
        location=region_obj.location, persistence=persistence)
    try:
        result, _output = await ScriptSandbox().execute_async(
            code, ctx, functions=functions.readonly_dict())
    except ScriptError as exc:
        raise ProviderError(
            f"map-provider {region_obj.name}.{attr} failed at "
            f"({x},{y}): {exc}") from exc
    return result


async def _flavor_attr(region_obj: GameObject, attr: str,
                       x: int, y: int, *, persistence) -> str | None:
    """Evaluate a cosmetic provider attr (name/desc/terrain): unset →
    None; an error is logged and falls back to None rather than aborting
    the cell (R10 — the cell still builds, tersely)."""
    if not _provider_set(region_obj, attr):
        return None
    try:
        value = await _eval_provider(region_obj, attr, x, y,
                                     persistence=persistence)
    except ProviderError as exc:
        logger.error(str(exc))
        return None
    return value


async def materialize_cell(
    region: str, x: int, y: int, persistence,
) -> GameObject | None:
    """Build the ephemeral cell at ``(region, x, y)`` from the region's
    map-provider — or return the live one. ``None`` iff ``is_valid``
    evaluated false; a provider *error* raises :class:`ProviderError`
    instead (R10 — a builder's bug never masquerades as an ocean).
    Concurrent callers for one coordinate share a single build."""
    key = (str(region), int(x), int(y))
    existing = cell_for(*key)
    if existing is not None:
        return existing
    task = _pending.get(key)
    if task is None:
        task = asyncio.create_task(
            _build_cell(key[0], key[1], key[2], persistence))
        _pending[key] = task
        task.add_done_callback(lambda _t: _pending.pop(key, None))
    return await task


async def _build_cell(
    region_name: str, x: int, y: int, persistence,
) -> GameObject | None:
    from realm.core.objects import GameObject as GameObjectCls

    region_obj = get_region(region_name)
    if region_obj is None:
        raise ProviderError(
            f"wilderness region {region_name!r} has no master object")

    if _provider_set(region_obj, "is_valid") and not await _eval_provider(
            region_obj, "is_valid", x, y, persistence=persistence):
        return None

    name = await _flavor_attr(region_obj, "cell_name", x, y,
                              persistence=persistence)
    desc = await _flavor_attr(region_obj, "cell_desc", x, y,
                              persistence=persistence)
    terrain = await _flavor_attr(region_obj, "cell_terrain", x, y,
                                 persistence=persistence)

    exits: object = DEFAULT_EXITS
    if _provider_set(region_obj, "cell_exits"):
        try:
            exits = await _eval_provider(region_obj, "cell_exits", x, y,
                                         persistence=persistence)
        except ProviderError as exc:
            logger.error(f"{exc} — falling back to the 4-way compass")
            exits = DEFAULT_EXITS
    if not isinstance(exits, (list, tuple)):
        logger.warning(
            f"map-provider {region_obj.name}.cell_exits returned "
            f"{type(exits).__name__!r} at ({x},{y}) — expected a list; "
            f"falling back to the 4-way compass")
        exits = DEFAULT_EXITS

    zone = _region_zone(region_name)
    cell = GameObjectCls(
        name=str(name) if name else f"{region_obj.name} ({x}, {y})",
        description=(str(desc) if desc
                     else "Untracked wilderness stretches away."),
        tags=["room", EPHEMERAL_TAG, zone, _cell_tag(region_name, x, y)],
    )
    cell.db.set("wild_region", region_name)
    cell.db.set("wild_x", x)
    cell.db.set("wild_y", y)
    cell.db.set("last_active", _clock())
    if terrain:
        for tag in ([terrain] if isinstance(terrain, str) else terrain):
            cell.add_tag(str(tag))
    await persistence.save(cell)      # registered in cache, skipped from DB
    # Index immediately: if an exit entry below is malformed and skipped,
    # or anything raises, the cell is still findable and reapable —
    # never an orphan the reaper can't see.
    _cells[(region_name, x, y)] = cell

    edge_msg = region_obj.db.get("edge_msg")
    for entry in exits:
        try:
            exit_obj = _build_cell_exit(entry, zone, edge_msg)
        except (TypeError, ValueError, KeyError) as exc:
            logger.warning(
                f"map-provider {region_obj.name}.cell_exits entry "
                f"{entry!r} at ({x},{y}) is malformed ({exc}); skipped")
            continue
        if exit_obj is None:
            logger.warning(
                f"map-provider {region_obj.name}.cell_exits named "
                f"unknown direction {entry!r} at ({x},{y}); skipped")
            continue
        exit_obj.location = cell
        await persistence.save(exit_obj)

    await _populate_cell(region_obj, cell, x, y, persistence)
    return cell


async def _populate_cell(region_obj: GameObject, cell: GameObject,
                         x: int, y: int, persistence) -> None:
    """Stage 3: spawn the provider's ``cell_populate`` prototypes into a
    fresh cell — the same prototype-dict vocabulary ``SpawnerBehavior``
    speaks. Spawns are born ``ephemeral`` + zone-tagged (they die with
    the cell, R9, and never hold it open). Unlike ``is_valid``/
    ``cell_exits``, this attr may be random — the reap/re-materialize
    cycle re-rolls the encounter table. Errors follow the R10 flavor
    rule: logged, cell left unpopulated."""
    if not _provider_set(region_obj, "cell_populate"):
        return
    try:
        protos = await _eval_provider(region_obj, "cell_populate", x, y,
                                      persistence=persistence)
    except ProviderError as exc:
        logger.error(f"{exc} — cell left unpopulated")
        return
    if protos is None:
        return
    if not isinstance(protos, (list, tuple)):
        logger.warning(
            f"map-provider {region_obj.name}.cell_populate returned "
            f"{type(protos).__name__!r} at ({x},{y}) — expected a list of "
            f"prototype dicts; cell left unpopulated")
        return

    from realm.behaviors.spawner import spawn_from_prototype

    zone = _region_zone(str(cell.db.get("wild_region")))
    for proto in protos:
        if not isinstance(proto, dict):
            logger.warning(
                f"map-provider {region_obj.name}.cell_populate entry "
                f"{proto!r} at ({x},{y}) is not a prototype dict; skipped")
            continue
        spawn = spawn_from_prototype(proto, cell)
        for tag in SPAWN_TAG_DENYLIST:
            if spawn.has_tag(tag):
                logger.warning(
                    f"cell_populate spawn {spawn.name} at ({x},{y}) "
                    f"claimed denylisted tag {tag!r}; stripped")
                spawn.remove_tag(tag)
        spawn.add_tag(EPHEMERAL_TAG)
        spawn.add_tag(zone)
        await persistence.save(spawn)   # registered in cache, skipped from DB


def _build_cell_exit(entry, zone: str, edge_msg) -> GameObject | None:
    """One cell exit from a provider ``cell_exits`` entry: a compass
    direction (deferred destination) or a ``{"name", "destination"}``
    dict (authored exit back to the persistent world, R5). ``None`` for
    an unknown direction; raises on a malformed entry."""
    from realm.core.objects import GameObject as GameObjectCls

    if isinstance(entry, dict):
        exit_obj = GameObjectCls(
            name=str(entry.get("name", "gate")),
            tags=["exit", EPHEMERAL_TAG, zone],
        )
        if entry.get("destination"):
            exit_obj.db.set("destination", str(entry["destination"]))
        if entry.get("aliases"):
            exit_obj.db.set("aliases", [str(a) for a in entry["aliases"]])
        return exit_obj

    direction = str(entry).lower()
    step = DIRECTIONS.get(direction)
    if step is None:
        return None
    exit_obj = GameObjectCls(
        name=direction, tags=["exit", EPHEMERAL_TAG, zone])
    exit_obj.db.set("dest_resolver", RESOLVER_NAME)
    exit_obj.db.set("wild_dx", step[0])
    exit_obj.db.set("wild_dy", step[1])
    aliases = _ALIASES.get(direction)
    if aliases:
        exit_obj.db.set("aliases", list(aliases))
    if edge_msg:
        exit_obj.db.set("fail_msg", str(edge_msg))
    return exit_obj


def _target_coords(exit_obj: GameObject) -> tuple[str, int, int] | None:
    """The coordinate an exit leads to: its own absolute
    ``wild_region``+``wild_x``/``wild_y`` (the world-entry seam), else the
    ``wild_dx``/``wild_dy`` step off the cell it sits in. Missing or
    malformed attrs are a loud dead-end, never a silent default (a gate
    with ``wild_y`` unset must not quietly drop the walker at y=0)."""
    try:
        region = exit_obj.db.get("wild_region")
        if region is not None:
            wx = exit_obj.db.get("wild_x")
            wy = exit_obj.db.get("wild_y")
            if wx is None or wy is None:
                logger.warning(
                    f"world-entry exit {exit_obj.name} ({exit_obj.id}) "
                    f"needs both wild_x and wild_y; treating as dead-end")
                return None
            return str(region), int(wx), int(wy)
        cell = exit_obj.location
        if cell is None:
            return None
        region = cell.db.get("wild_region")
        cx = cell.db.get("wild_x")
        cy = cell.db.get("wild_y")
        dx = exit_obj.db.get("wild_dx")
        dy = exit_obj.db.get("wild_dy")
        if region is None or None in (cx, cy, dx, dy):
            return None
        return str(region), int(cx) + int(dx), int(cy) + int(dy)
    except (TypeError, ValueError):
        logger.warning(
            f"exit {exit_obj.name} ({exit_obj.id}) carries malformed "
            f"wilderness coordinates; treating as dead-end")
        return None


async def resolve_wilderness_exit(
    exit_obj: GameObject, actor: GameObject,
) -> GameObject | None:
    """The registered deferred-destination resolver: get-or-create the
    cell this exit leads to. ``None`` = a true map edge (the kernel shows
    the exit's authored ``fail_msg``); a broken provider raises
    ``DestinationUnavailable`` with a *distinct* message (R10)."""
    from realm.persistence.manager import get_active_manager

    persistence = get_active_manager()
    coords = _target_coords(exit_obj)
    if coords is None:
        logger.warning(
            f"wilderness exit {exit_obj.name} ({exit_obj.id}) has no "
            f"resolvable coordinate; treating as a dead-end")
        return None
    region, x, y = coords
    try:
        cell = cell_for(region, x, y)
        if cell is None:
            # Only players materialize terrain: a mob may pursue into an
            # existing cell, but a missing neighbor is a dead-end for it
            # — one wandering wolf must not generate cells forever.
            if not actor.has_tag("player"):
                return None
            cell = await materialize_cell(region, x, y, persistence)
    except ProviderError as exc:
        logger.error(str(exc))
        from realm.core.movement import DestinationUnavailableError
        raise DestinationUnavailableError(
            "A strange force bars the way.") from exc
    if cell is not None and actor.has_tag("player"):
        # Only a player's arrival is activity: a spawn pacing between
        # cells must not refresh their TTL and keep itself alive forever
        # (R6/edge case 13 — NPCs never hold a cell open).
        cell.db.set("last_active", _clock())
    return cell


async def enter_cell(
    player: GameObject, region: str, x: int, y: int, persistence,
) -> GameObject | None:
    """The scripted-entry arm (softcode ``enter_wilderness`` drains here):
    get-or-create the cell and place the player in it via ``move_to`` —
    a placement, so teleport semantics apply. Returns the cell, or None
    (invalid coordinate, broken provider, or a lock/ward refused)."""
    try:
        cell = (cell_for(region, x, y)
                or await materialize_cell(region, x, y, persistence))
    except ProviderError as exc:
        logger.error(str(exc))
        player.msg("A strange force bars the way.")
        return None
    if cell is None:
        return None
    from realm.core.movement import move_to
    if not await move_to(player, cell):
        return None
    cell.db.set("last_active", _clock())
    return cell


async def destroy_cell(cell: GameObject, persistence) -> None:
    """Tear down one cell: R9 disposition for its occupants (players
    evacuated, player-owned property to its owner's refuge, the rest
    destroyed loudly), then delete the cell, its exits, and anything
    born with it (zone-tagged)."""
    # De-index FIRST so no walker resolving mid-teardown is handed a
    # dying cell (get-or-create builds a fresh one instead).
    _cells.pop((str(cell.db.get("wild_region")),
                int(cell.db.get("wild_x") or 0),
                int(cell.db.get("wild_y") or 0)), None)
    zone = _region_zone(str(cell.db.get("wild_region")))
    native = [o for o in cell.contents if o.has_tag(zone)]
    doomed = {cell.id} | {o.id for o in native}
    await release_contents(cell, persistence, doomed_ids=doomed)
    for obj in native:
        obj.location = None
        if persistence is not None:
            await persistence.delete(obj)
    # Anyone who slipped in during the awaits above (a move already past
    # resolution when we de-indexed) gets the same disposition.
    await release_contents(cell, persistence)
    cell.location = None
    if persistence is not None:
        await persistence.delete(cell)


async def reap_wilderness(persistence, *, now: float | None = None) -> int:
    """GC pass over the live-cell index: destroy every cell empty of
    players past its region's ``idle_ttl``. Returns the number reaped.
    Call from the world tick, next to ``instances.reap_idle``."""
    now = _clock() if now is None else now
    reaped = 0
    for key, cell in list(_cells.items()):
        if not _cache_live(cell):
            _cells.pop(key, None)
            continue
        if subtree_has_player(cell):
            cell.db.set("last_active", now)
            continue
        region_obj = get_region(key[0])
        ttl = DEFAULT_IDLE_TTL
        if region_obj is not None:
            raw_ttl = region_obj.db.get("idle_ttl")
            if raw_ttl is not None:
                try:
                    ttl = float(raw_ttl)
                except (TypeError, ValueError):
                    logger.warning(
                        f"region {key[0]!r} idle_ttl {raw_ttl!r} is not a "
                        f"number; using the {DEFAULT_IDLE_TTL:.0f}s default")
        if now - float(cell.db.get("last_active") or 0) > ttl:
            await destroy_cell(cell, persistence)
            reaped += 1
    return reaped


register_dest_resolver(RESOLVER_NAME, resolve_wilderness_exit)


__all__ = [
    "REGION_TAG", "RESOLVER_NAME", "DEFAULT_IDLE_TTL", "DIRECTIONS",
    "ProviderError",
    "get_region", "cell_for", "materialize_cell",
    "resolve_wilderness_exit", "enter_cell", "destroy_cell",
    "reap_wilderness", "reset",
]
