"""
The quest commands (MUD_PLAN 15.2, 15.3): the journal (``quests``,
alias ``journal``), ``quest`` and its subcommands, and ``talk``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.commands.base import find_object
from realm.core.language import definite_name
from realm.core.propagation import Action, propagate
from realm.core.world import get_world
from realm.std.quests.quests import (
    READY,
    accept,
    complete,
    definitions,
    fail,
    givers_here,
    history,
    missing,
    offered_by,
    progress,
    records,
    refusal,
    state,
    takes_back,
    time_left,
)
from realm.std.quests.quests import _duration as duration

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject
    from realm.std.quests.definitions import Quest


def _the(obj: GameObject) -> str:
    """How a line begins with ``obj``: "The baker", "Old Moss"."""
    name = definite_name(obj)
    return name[:1].upper() + name[1:]


def _words_prefix(query: list[str], name: list[str]) -> bool:
    """Each query word begins a later word of the name, in order."""
    at = 0
    for word in query:
        while at < len(name) and not name[at].startswith(word):
            at += 1
        if at == len(name):
            return False
        at += 1
    return True


def _pick(name: str, quests: list[Quest]) -> Quest | None:
    """The quest ``name`` means among ``quests``: its name, else the one
    it begins, else the one whose words it begins (``cinder`` for The
    Cinder Road)."""
    want = name.strip().lower()
    if not want:
        return None
    for quest in quests:
        if quest.key == want:
            return quest
    for test in (lambda q: q.key.startswith(want),
                 lambda q: _words_prefix(want.split(), q.key.split())):
        found = [q for q in quests if test(q)]
        if found:
            return found[0] if len(found) == 1 else None
    return None


def _active(player: GameObject) -> list[tuple[Quest, dict]]:
    defs = definitions()
    return [(defs[k], rec) for k, rec in records(player).items() if k in defs]


def _status(player: GameObject, quest: Quest, rec: dict) -> str:
    if rec.get("stage") == READY:
        where = quest.giver.describe() if quest.giver is not None else "the giver"
        bits = [f"ready: return to {where}"]
    else:
        bits = [f"stage {rec.get('stage')} of {len(quest.stages)}"]
    left = time_left(rec)
    if left is not None:
        bits.append(f"{duration(max(0.0, left))} left")
    return f"{quest.name} ({', '.join(bits)})"


def _objective_lines(player: GameObject, quest: Quest, rec: dict, indent: str) -> list[str]:
    stage = quest.stage(rec["stage"]) if isinstance(rec.get("stage"), int) else None
    if stage is None:
        return []
    lines = [f"{indent}{stage.text}"] if stage.text else []
    for objective in stage.objectives:
        lines.append(f"{indent}  {objective.label()}: "
                     f"{progress(player, quest, objective, rec)}/{objective.count}")
    return lines


async def cmd_quests(ctx: CommandContext) -> None:
    """
    Your journal: the quests you are on, each one's stage and how far
    along you are. ``quests done`` lists the quests you have finished.

    Usage: quests
           quests done
    """
    player = ctx.player
    if ctx.args.strip().lower() in ("done", "history", "finished"):
        finished = sorted(history(player).items(), key=lambda kv: kv[1])
        if not finished:
            await ctx.session.send("You have not finished any quests yet.")
            return
        defs = definitions()
        lines = ["Quests you have finished:"]
        lines += [f"  {defs[k].name if k in defs else k}" for k, _when in finished]
        ctx.session.send_paged("\n".join(lines))
        return
    if ctx.args.strip():
        await cmd_quest(ctx)
        return
    active = _active(player)
    if not active:
        await ctx.session.send("Your journal is empty. (quest list: what the people "
                               "here offer)")
        return
    lines = ["Your quests:"]
    for quest, rec in active:
        lines.append(f"  {_status(player, quest, rec)}")
        lines += _objective_lines(player, quest, rec, "    ")
    ctx.session.send_paged("\n".join(lines))


def _detail(player: GameObject, quest: Quest) -> list[str]:
    lines = [quest.name]
    if quest.description:
        lines.append(f"  {quest.description}")
    rec = records(player).get(quest.key)
    if rec is not None:
        lines.append(f"  {_status(player, quest, rec)}")
        lines += _objective_lines(player, quest, rec, "  ")
    else:
        now_state = state(player, quest)
        if now_state is not None:
            lines.append("  You have finished it.")
        lines.append(f"  Stages: {len(quest.stages)}")
        if quest.time_limit:
            lines.append(f"  Time limit: {duration(quest.time_limit)}")
    rewards = quest.rewards.describe()
    if rewards:
        lines.append(f"  Rewards: {', '.join(rewards)}")
    return lines


async def cmd_quest(ctx: CommandContext) -> None:
    """
    Take, follow and hand in quests.

    Usage: quest                      (your journal, as `quests`)
           quest list                 (what the people here offer you)
           quest <name>               (one quest in detail)
           quest accept <name>
           quest complete [<name>]    (hand it in to its giver)
           quest abandon <name>

    A marker beside a name in the room shows a giver: (!) has a quest you
    may take, (?) waits for one you have finished.
    """
    word, _, rest = ctx.args.strip().partition(" ")
    word, rest = word.lower(), rest.strip()
    player = ctx.player
    if not word:
        await cmd_quests(ctx)
        return
    if word == "list":
        await _list(ctx, player)
    elif word == "accept":
        await _accept(ctx, player, rest)
    elif word in ("complete", "turnin"):
        await _complete(ctx, player, rest)
    elif word == "abandon":
        await _abandon(ctx, player, rest)
    else:
        name = ctx.args.strip()
        offered = [q for npc in givers_here(player) for q in offered_by(npc)]
        quest = (_pick(name, [q for q, _r in _active(player)]) or _pick(name, offered))
        if quest is None:
            await ctx.session.send(f"You know of no quest called '{name}'. (quests: your "
                                   f"journal; quest list: what is offered here)")
            return
        ctx.session.send_paged("\n".join(_detail(player, quest)))


async def _list(ctx: CommandContext, player: GameObject) -> None:
    lines = []
    for npc in givers_here(player):
        rows = []
        for quest in offered_by(npc):
            reason = refusal(player, quest)
            now_state = state(player, quest)
            if reason is None:
                note = ""
            elif now_state == READY and takes_back(npc, quest):
                note = " (finished: quest complete)"
            elif now_state is not None and now_state != "done":
                note = " (you are on it)"
            elif now_state == "done":
                note = " (done)" if quest.repeatable is None else f" ({reason})"
            else:
                continue                    # the lock: not for this player
            summary = f" - {quest.description}" if quest.description and not note else ""
            rows.append(f"  {quest.name}{note}{summary}")
        if rows:
            lines.append(f"{_the(npc)} offers:")
            lines += rows
    if not lines:
        await ctx.session.send("Nobody here has a quest for you.")
        return
    lines.append("(quest accept <name> to take one)")
    ctx.session.send_paged("\n".join(lines))


async def _accept(ctx: CommandContext, player: GameObject, name: str) -> None:
    if not name:
        await ctx.session.send("Accept which quest? (quest list)")
        return
    choices: list[tuple[Quest, GameObject | None]] = []
    for npc in givers_here(player):
        choices += [(q, npc) for q in offered_by(npc)]
    choices += [(q, None) for q in definitions().values() if q.giver is None]
    quest = _pick(name, list(dict.fromkeys(q for q, _n in choices)))
    if quest is None:
        await ctx.session.send("Nobody here offers that quest. (quest list)")
        return
    giver = next((n for q, n in choices if q is quest and n is not None), None)
    reason = await accept(player, quest, giver)
    if reason is not None:
        await ctx.session.send(reason)


async def _complete(ctx: CommandContext, player: GameObject, name: str) -> None:
    active = _active(player)
    if name:
        quest = _pick(name, [q for q, _r in active])
        if quest is None:
            await ctx.session.send(f"You are not on a quest called '{name}'.")
            return
        chosen = [quest]
    else:
        chosen = [q for q, rec in active if rec.get("stage") == READY]
        if not chosen:
            await ctx.session.send("You have no quest ready to hand in.")
            return
    givers = givers_here(player)
    handed = False
    for quest in chosen:
        if state(player, quest) != READY:
            await ctx.session.send(f"You have not finished {quest.name} yet.")
            continue
        giver = next((g for g in givers if takes_back(g, quest)), None)
        if giver is None:
            if name:
                await ctx.session.send(f"Hand {quest.name} in to "
                                       f"{quest.giver.describe()}.")
            continue
        lacking = missing(player, quest)
        if lacking:
            await ctx.session.send(f"{quest.name} still asks for: "
                                   f"{', '.join(o.label() for o in lacking)}.")
            continue
        handed = True
        await complete(player, quest, giver)
    if not handed and not name:
        await ctx.session.send("Nobody here takes back the quests you have finished.")


async def _abandon(ctx: CommandContext, player: GameObject, name: str) -> None:
    quest = _pick(name, [q for q, _r in _active(player)]) if name else None
    if quest is None:
        await ctx.session.send("Abandon which of your quests? (quests)")
        return
    await fail(player, quest, "abandoned")


# --- talk --------------------------------------------------------------------------


async def _world_verb(ctx: CommandContext) -> bool:
    """Offer the line to the world's softcode ``$``-commands first (an
    NPC's own ``$talk``): a built-in must not shadow a verb the world
    defines."""
    engine = get_world().scripts
    return engine is not None and await engine.handle_unknown_command(ctx)


async def cmd_talk(ctx: CommandContext) -> None:
    """
    Talk to someone here. Their softcode may answer (``ON_TALK``); a
    quest that asks you to talk to them counts it, and a quest giver
    tells you what they have for you.

    Usage: talk <someone>
    """
    name = ctx.args.strip()
    if name.lower().startswith("to "):
        name = name[3:].strip()
    target = find_object(ctx, name, search_inventory=False) if name else None
    if target is None or target.is_player:
        if await _world_verb(ctx):
            return
        if target is not None:
            await ctx.session.send(f"Talk to {target.name} with say or tell.")
        else:
            await ctx.session.send("Talk to whom?" if not name
                                   else f"You don't see '{name}' here.")
        return
    player = ctx.player
    action = Action(actor=player, target=target, action_type="quest:on_talk")
    action.add_message("actor", "You talk with {target:the}.")
    action.add_message("room", "{actor} talks with {target:the}.")
    await propagate(action)
    offers = offered_by(target)
    ready = [q for q in offers if takes_back(target, q) and state(player, q) == READY]
    open_ = [q for q in offers if refusal(player, q) is None]
    who = _the(target)
    if ready:
        await ctx.session.send(f"{who} is waiting for you to hand in "
                               f"{', '.join(q.name for q in ready)} (quest complete).")
    if open_:
        await ctx.session.send(f"{who} has work for you: "
                               f"{', '.join(q.name for q in open_)} (quest list).")


__all__ = ["cmd_quest", "cmd_quests", "cmd_talk"]
