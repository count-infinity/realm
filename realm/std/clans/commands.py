"""
The clan commands (MUD_PLAN 14.2 to 14.5, 14.7): ``clan`` and its
subcommands, ``clans``, and the administrators' ``@clan``.

A subcommand that needs a power acts in the first of the character's
clans where its position holds that power or may vote on it (the default
category first); ``leave``, ``who``, ``info``, ``relations`` and ``vote``
take a clan's name.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.world import get_world
from realm.gateway.session import is_online
from realm.std.clans import clans as clan_clock
from realm.std.clans import votes as clan_votes
from realm.std.clans.acts import act, refusal, relation
from realm.std.clans.clans import (
    ACTIVE,
    PENDING,
    RELATIONS,
    add_member,
    add_xp,
    all_clans,
    authority,
    clans_of,
    day_seconds,
    dissolve,
    find_clan,
    fire_levels,
    found,
    full,
    full_members,
    government_of,
    has_power,
    is_active,
    is_applicant,
    is_member,
    members,
    name_refusal,
    position_of,
    promote,
    record_of,
    refresh_members,
    roster,
    setting,
    size,
    tell_clan,
)
from realm.std.clans.governments import CANNOT, government, governments

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject


def _level(obj: GameObject) -> int:
    value = obj.db.get("level")
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 1


def _amount(text: str) -> int | None:
    text = text.strip()
    return int(text) if text.isdigit() and int(text) > 0 else None


def _economy():
    return get_world().services.get("economy")


def _member(clan: GameObject, name: str) -> GameObject | None:
    """A member (or applicant) of ``clan`` by name or unique prefix."""
    want = name.strip().lower()
    if not want:
        return None
    people = [o for o, _r in roster(clan)]
    for obj in people:
        if obj.name.lower() == want:
            return obj
    found_ = [o for o in people if o.name.lower().startswith(want)]
    return found_[0] if len(found_) == 1 else None


def _passes(clan_or_gov_lock: str | None, obj: GameObject, target: GameObject) -> bool:
    if not clan_or_gov_lock:
        return True
    from realm.permissions.locks import LockEvaluator
    return LockEvaluator().evaluate(clan_or_gov_lock, obj, target)


def _acting_clan(player: GameObject, power: str) -> tuple[GameObject | None, str | None]:
    """The clan ``player`` acts in for ``power``, or why there is none."""
    mine = [c for c in clans_of(player) if is_member(c, player)]
    if not mine:
        return None, "You are not in a clan."
    for clan in mine:
        if authority(clan, player, power) != CANNOT:
            return clan, None
    return None, refusal(mine[0], player, power)


def _named_or_own(player: GameObject, name: str) -> tuple[GameObject | None, str | None]:
    if name.strip():
        clan = find_clan(name)
        return (clan, None) if clan is not None else (None, f"There is no clan called {name}.")
    mine = [c for c in clans_of(player) if record_of(c, player) is not None]
    if not mine:
        return None, "You are not in a clan."
    return mine[0], None


def _title(clan: GameObject, obj: GameObject) -> str:
    pos = position_of(clan, obj)
    return pos.name if pos is not None else "member"


def _days(seconds: float) -> str:
    days = max(0.0, seconds) / day_seconds()
    return f"{days:.1f} game day{'s' if round(days, 1) != 1 else ''}"


# --- clan ----------------------------------------------------------------------


async def cmd_clan(ctx: CommandContext) -> None:
    """
    Found, join and run a clan. Each clan's government says which
    positions exist and what each may do; an act no position holds is put
    to a vote.

    Usage:
        clan                              your clans
        clan info [<clan>]                a clan's premise and leaders
        clan who [<clan>]                 its members
        clan governments                  what a founder may choose
        clan found <name> = <government>  found one (it costs CLAN_COST)
        clan apply <clan>   clan leave [<clan>]
        clan accept|reject <player>       answer an application
        clan assign <member> = <position> clan exile <member>
        clan premise = <text>             clan motd [= <text>]
        clan home   clan donate           set from where you stand
        clan recall                       go to the clan's home
        clan deposit|withdraw <amount>    clan deposits
        clan tax <percent>                clan donate xp <amount>
        clan declare <clan> = war|hostile|neutral|friendly|ally
        clan relations [<clan>]
        clan votes   clan vote [<clan>] <n> yes|no|withdraw
        clan disband
    """
    sub, _, rest = (ctx.args or "").strip().partition(" ")
    handler = _SUBCOMMANDS.get(sub.lower()) if sub else _mine
    if handler is None:
        await ctx.session.send(f"Unknown clan command '{sub}'. See: help clan")
        return
    await handler(ctx, rest.strip())


async def _mine(ctx: CommandContext, _rest: str) -> None:
    player = ctx.player
    clans = clans_of(player)
    if not clans:
        await ctx.session.send("You are not in a clan. See: clans, clan apply, clan found.")
        return
    lines = []
    for clan in clans:
        gov = government_of(clan)
        kind = gov.name if gov is not None else "clan"
        if is_applicant(clan, player):
            lines.append(f"You have applied to {clan.name} (a {kind}).")
            continue
        pending = " It is not yet fully founded." if clan.db.get("status") == PENDING else ""
        lines.append(f"You are {_title(clan, player)} of {clan.name} (a {kind}, level "
                     f"{clan.db.get('level') or 1}).{pending}")
    await ctx.session.send("\n".join(lines))


async def _info(ctx: CommandContext, rest: str) -> None:
    clan, why = _named_or_own(ctx.player, rest)
    if clan is None:
        await ctx.session.send(why)
        return
    gov = government_of(clan)
    lines = [f"{clan.name}: a {gov.name if gov else 'clan'} ({gov.description if gov else ''})",
             f"  Level {clan.db.get('level') or 1}, {size(clan)} member(s)"
             f"{', not yet fully founded' if clan.db.get('status') == PENDING else ''}."]
    if clan.db.get("premise"):
        lines.append(f"  Premise: {clan.db.get('premise')}")
    if gov is not None:
        for pos in gov.positions:
            if not pos.public or pos.id == gov.applicant_position:
                continue
            names = [o.name for o, r in full_members(clan) if r.get("position") == pos.id]
            if names:
                label = pos.plural if len(names) > 1 else pos.name
                lines.append(f"  {label}: {', '.join(names)}")
    await ctx.session.send("\n".join(lines))


async def _who(ctx: CommandContext, rest: str) -> None:
    player = ctx.player
    clan, why = _named_or_own(player, rest)
    if clan is None:
        await ctx.session.send(why)
        return
    if not has_power(clan, player, "list_members"):
        await ctx.session.send(f"You may not list the members of {clan.name}.")
        return
    people = roster(clan)
    people.sort(key=lambda p: not is_online(p[0]))
    lines = [f"Members of {clan.name}:"]
    for obj, _rec in people:
        state = "online" if is_online(obj) else ""
        lines.append(f"  {obj.name:16} {_title(clan, obj):20} {state}")
    ctx.session.send_paged("\n".join(lines))


async def _governments(ctx: CommandContext, _rest: str) -> None:
    govs = sorted(governments().values(), key=lambda g: g.name)
    if not govs:
        await ctx.session.send("There are no clan governments in this world (an "
                               "administrator imports them: @pack clan-governments).")
        return
    lines = ["Clan governments (clan found <name> = <government>):"]
    for gov in govs:
        lines.append(f"  {gov.name:12} {gov.description}")
    await ctx.session.send("\n".join(lines))


async def _found(ctx: CommandContext, rest: str) -> None:
    player = ctx.player
    cost = setting("CLAN_COST")
    if cost is None:
        await ctx.session.send("Only an administrator founds clans here.")
        return
    name, eq, gov_name = rest.partition("=")
    gov = government(gov_name.strip()) if eq else None
    if not eq or not name.strip():
        await ctx.session.send("Usage: clan found <name> = <government> (see clan governments)")
        return
    if gov is None:
        await ctx.session.send(f"There is no government '{gov_name.strip()}' "
                               f"(see clan governments).")
        return
    why = name_refusal(name)
    if why is None and _level(player) < int(setting("CLAN_MIN_LEVEL") or 0):
        why = f"You must be level {setting('CLAN_MIN_LEVEL')} to found a clan."
    if why is None and clan_of_category(player, gov.category) is not None:
        why = "You are already in a clan of that kind."
    if why is None and not (_passes(gov.required_lock, player, player)
                            and _passes(gov.top.lock, player, player)):
        why = f"You may not lead a {gov.name}."
    cost = int(cost)
    economy = _economy()
    if why is None and cost > 0:
        if economy is None:
            why = "Founding a clan is unavailable here."
        elif economy.get_credits(player) < cost:
            why = f"Founding a clan costs {cost} {economy.currency_name()}."
    if why is not None:
        await ctx.session.send(why)
        return
    if cost > 0:
        economy.adjust_credits(player, -cost)
    clan = await found(name, gov, player)
    note = ("" if is_active(clan) else
            f" It is pending until it has {setting('CLAN_MIN_MEMBERS')} members.")
    await ctx.session.send(f"You found {clan.name}, a {gov.name}, and are its "
                           f"{gov.top.name}.{note}")


def clan_of_category(player: GameObject, category: str) -> GameObject | None:
    """The clan (joined or applied to) ``player`` holds in ``category``."""
    for clan in clans_of(player):
        gov = government_of(clan)
        if gov is not None and gov.category == category:
            return clan
    return None


async def _apply(ctx: CommandContext, rest: str) -> None:
    player = ctx.player
    clan = find_clan(rest)
    if clan is None:
        await ctx.session.send(f"There is no clan called {rest}." if rest else
                               "Usage: clan apply <clan>")
        return
    gov = government_of(clan)
    limit = int(setting("CLAN_MAX_MEMBERS") or 0)
    why = None
    if record_of(clan, player) is not None:
        why = f"You are already in {clan.name}."
    elif clan_of_category(player, gov.category) is not None:
        why = "You are already in a clan of that kind."
    elif not _passes(gov.required_lock, player, clan):
        why = f"{clan.name} will not have you."
    elif limit and size(clan) >= limit:
        why = f"{clan.name} has all the members it may."
    if why is not None:
        await ctx.session.send(why)
        return
    if gov.applicant_position is None:
        pos = gov.position(gov.accept_position)
        if full(clan, pos):
            await ctx.session.send(f"{clan.name} has no room for another {pos.name}.")
            return
        await add_member(clan, player, pos.id, how="joined")
        tell_clan(clan, f"{player.name} joins {clan.name} as {pos.name}.")
        await ctx.session.send(f"You join {clan.name} as {pos.name}.")
        return
    await add_member(clan, player, gov.applicant_position, how="applied")
    for obj, _rec in full_members(clan):
        if authority(clan, obj, "accept") != CANNOT:
            obj.msg(f"[{clan.name}] {player.name} applies to join "
                    f"(clan accept {player.name} / clan reject {player.name}).")
    await ctx.session.send(f"You apply to join {clan.name}.")


async def _answer(ctx: CommandContext, rest: str, power: str) -> None:
    player = ctx.player
    clan, why = _acting_clan(player, power)
    if clan is None:
        await ctx.session.send(why)
        return
    who = _member(clan, rest)
    if who is None or not is_applicant(clan, who):
        await ctx.session.send(f"{rest or 'Nobody'} has not applied to {clan.name}.")
        return
    verb = "accept" if power == "accept" else "reject"
    await ctx.session.send(await act(clan, player, power, {"member": who.id},
                                     f"{verb} {who.name}"))


async def _accept(ctx: CommandContext, rest: str) -> None:
    await _answer(ctx, rest, "accept")


async def _reject(ctx: CommandContext, rest: str) -> None:
    await _answer(ctx, rest, "reject")


async def _leave(ctx: CommandContext, rest: str) -> None:
    from realm.std.clans.clans import remove_member
    player = ctx.player
    clan, why = _named_or_own(player, rest)
    if clan is None or record_of(clan, player) is None:
        await ctx.session.send(why or f"You are not in {clan.name}.")
        return
    applied = is_applicant(clan, player)
    await remove_member(clan, player, reason="withdrawn" if applied else "left")
    if find_clan(clan.name) is not None and not applied:
        tell_clan(clan, f"{player.name} leaves {clan.name}.")
    await ctx.session.send(f"You withdraw your application to {clan.name}." if applied
                           else f"You leave {clan.name}.")


async def _assign(ctx: CommandContext, rest: str) -> None:
    player = ctx.player
    clan, why = _acting_clan(player, "assign")
    if clan is None:
        await ctx.session.send(why)
        return
    name, eq, pos_word = rest.partition("=")
    gov = government_of(clan)
    who = _member(clan, name)
    pos = gov.position(pos_word.strip())
    if not eq or who is None:
        await ctx.session.send("Usage: clan assign <member> = <position>")
        return
    if pos is None:
        names = ", ".join(p.name for p in gov.positions if p.id != gov.applicant_position)
        await ctx.session.send(f"There is no position '{pos_word.strip()}' ({names}).")
        return
    await ctx.session.send(await act(clan, player, "assign",
                                     {"member": who.id, "position": pos.id},
                                     f"make {who.name} {pos.name}"))


async def _exile(ctx: CommandContext, rest: str) -> None:
    player = ctx.player
    clan, why = _acting_clan(player, "exile")
    if clan is None:
        await ctx.session.send(why)
        return
    who = _member(clan, rest)
    if who is None:
        await ctx.session.send(f"There is no member of {clan.name} called {rest}.")
        return
    await ctx.session.send(await act(clan, player, "exile", {"member": who.id},
                                     f"exile {who.name}"))


async def _premise(ctx: CommandContext, rest: str) -> None:
    _blank, eq, text = rest.partition("=")
    if not eq:
        await ctx.session.send("Usage: clan premise = <text>")
        return
    clan, why = _acting_clan(ctx.player, "premise")
    if clan is None:
        await ctx.session.send(why)
        return
    await ctx.session.send(await act(clan, ctx.player, "premise", {"text": text.strip()},
                                     "change the premise"))


async def _motd(ctx: CommandContext, rest: str) -> None:
    player = ctx.player
    _blank, eq, text = rest.partition("=")
    if eq:
        clan, why = _acting_clan(player, "motd_write")
        if clan is None:
            await ctx.session.send(why)
            return
        await ctx.session.send(await act(clan, player, "motd_write", {"text": text.strip()},
                                         "change the message of the day"))
        return
    clan, why = _acting_clan(player, "motd_read")
    if clan is None:
        await ctx.session.send(why)
        return
    await ctx.session.send(f"{clan.name}: {clan.db.get('motd') or 'no message of the day.'}")


async def _set_place(ctx: CommandContext, power: str, label: str) -> None:
    player = ctx.player
    clan, why = _acting_clan(player, power)
    room = player.location
    if clan is None:
        await ctx.session.send(why)
        return
    if room is None or not room.is_room:
        await ctx.session.send("Stand in the room you mean.")
        return
    await ctx.session.send(await act(clan, player, power, {"room": room.id},
                                     f"make {room.name} the clan's {label}"))


async def _home(ctx: CommandContext, _rest: str) -> None:
    await _set_place(ctx, "set_home", "home")


async def _donate(ctx: CommandContext, rest: str) -> None:
    if rest.lower().startswith("xp"):
        await _donate_xp(ctx, rest[2:])
        return
    await _set_place(ctx, "set_donate", "donation room")


async def _donate_xp(ctx: CommandContext, rest: str) -> None:
    player = ctx.player
    rules = get_world().rules
    amount = _amount(rest)
    clan, why = _acting_clan(player, "deposit")
    if clan is not None and not has_power(clan, player, "deposit"):
        clan, why = None, refusal(clan, player, "deposit")
    if clan is None:
        await ctx.session.send(why)
        return
    balance = rules.spendable_award(player) if rules is not None else None
    if balance is None:
        await ctx.session.send("There is no experience to give in this game.")
        return
    if amount is None or amount > balance:
        await ctx.session.send(f"Give how much? You have {balance} to give.")
        return
    rules.spend_award(player, amount)
    levels = add_xp(clan, amount, player)
    tell_clan(clan, f"{player.name} gives {amount} experience to {clan.name}.")
    await fire_levels(clan, levels)
    if government_of(clan).auto_promote == "xp":
        await promote(clan)
    await ctx.session.send(f"You give {amount} experience to {clan.name}.")


async def _recall(ctx: CommandContext, _rest: str) -> None:
    player = ctx.player
    mine = [c for c in clans_of(player) if is_member(c, player)
            and has_power(c, player, "home_privs") and c.db.get("home")]
    if not mine:
        await ctx.session.send("You have no clan home to go to.")
        return
    world = get_world()
    recall = world.services.get("recall")
    home = world.store.get_cached(str(mine[0].db.get("home")))
    if recall is None or home is None:
        await ctx.session.send("You cannot recall to your clan's home.")
        return
    await recall.to(player, home, ctx.session)


async def _disband(ctx: CommandContext, rest: str) -> None:
    player = ctx.player
    mine = [c for c in clans_of(player) if is_member(c, player)]
    tops = [c for c in mine if position_of(c, player) is not None
            and position_of(c, player).id in government_of(c).top_ids()]
    if not tops:
        await ctx.session.send("Only a clan's leader disbands it.")
        return
    clan = tops[0]
    if len(tops) > 1 and rest:
        clan = next((c for c in tops if c.name.lower() == rest.lower()), clan)
    treasury = int(clan.db.get("treasury") or 0)
    if rest.strip().lower() != clan.name.lower():
        economy = _economy()
        money = f" Its treasury of {treasury} {economy.currency_name()} comes to you." \
            if treasury and economy is not None else ""
        await ctx.session.send(f"This dissolves {clan.name} for good.{money} "
                               f"To go ahead: clan disband {clan.name}")
        return
    economy = _economy()
    if treasury and economy is not None:
        economy.adjust_credits(player, treasury)
        clan.db.treasury = 0
    name = clan.name
    await dissolve(clan, f"disbanded by {player.name}")
    await ctx.session.send(f"You disband {name}.")


async def _votes(ctx: CommandContext, _rest: str) -> None:
    player = ctx.player
    lines = []
    store = get_world().store
    for clan in clans_of(player):
        if not is_member(clan, player):
            continue
        for vote in clan_votes.open_votes(clan):
            yes, no, eligible = clan_votes.tally(clan, vote)
            mine = vote["ballots"].get(player.id)
            yours = "" if mine is None else f" You said {'yes' if mine else 'no'}."
            proposer = store.get_cached(str(vote["proposer"]))
            lines.append(f"  {clan.name} vote {vote['id']}: {vote['describe']} (called by "
                         f"{proposer.name if proposer else 'someone gone'}). {yes} yes, "
                         f"{no} no of {eligible}; closes in "
                         f"{_days(float(vote['closes']) - clan_clock.now())}.{yours}")
    if not lines:
        await ctx.session.send("Your clans have no open votes.")
        return
    await ctx.session.send("Open votes:\n" + "\n".join(lines))


async def _vote(ctx: CommandContext, rest: str) -> None:
    player = ctx.player
    words = rest.split()
    if len(words) < 2 or words[-1].lower() not in ("yes", "no", "withdraw") \
            or not words[-2].isdigit():
        await ctx.session.send("Usage: clan vote [<clan>] <n> yes|no|withdraw")
        return
    number, choice = int(words[-2]), words[-1].lower()
    named = " ".join(words[:-2])
    mine = [c for c in clans_of(player) if is_member(c, player)]
    if named:
        mine = [c for c in mine if c.name.lower().startswith(named.lower())]
    holding = [c for c in mine if clan_votes.find_vote(c, number) is not None]
    if not holding:
        await ctx.session.send(f"There is no open vote {number} in your clans.")
        return
    if len(holding) > 1:
        await ctx.session.send(f"Which clan? clan vote <clan> {number} {choice}")
        return
    clan = holding[0]
    if choice == "withdraw":
        await ctx.session.send(await clan_votes.withdraw(clan, player, number))
    else:
        await ctx.session.send(await clan_votes.cast(clan, player, number, choice == "yes"))


async def _deposit(ctx: CommandContext, rest: str) -> None:
    player = ctx.player
    economy = _economy()
    clan, why = _acting_clan(player, "deposit")
    if clan is not None and not has_power(clan, player, "deposit"):
        clan, why = None, refusal(clan, player, "deposit")
    if clan is None:
        await ctx.session.send(why)
        return
    if economy is None:
        await ctx.session.send(f"The treasury of {clan.name} is unavailable here.")
        return
    amount = _amount(rest)
    if amount is None:
        await ctx.session.send("Usage: clan deposit <amount>")
        return
    if not economy.adjust_credits(player, -amount):
        await ctx.session.send("You don't have that much.")
        return
    clan.db.treasury = int(clan.db.get("treasury") or 0) + amount
    members_ = members(clan)
    members_[player.id]["donated_gold"] = \
        int(members_[player.id].get("donated_gold") or 0) + amount
    clan.db.members = members_
    money = economy.currency_name()
    tell_clan(clan, f"{player.name} deposits {amount} {money} in the treasury.")
    if government_of(clan).auto_promote == "gold":
        await promote(clan)
    await ctx.session.send(f"You deposit {amount} {money}; the treasury holds "
                           f"{clan.db.treasury}.")


async def _withdraw(ctx: CommandContext, rest: str) -> None:
    player = ctx.player
    clan, why = _acting_clan(player, "withdraw")
    if clan is None:
        await ctx.session.send(why)
        return
    economy = _economy()
    if economy is None:
        await ctx.session.send(f"The treasury of {clan.name} is unavailable here.")
        return
    amount = _amount(rest)
    if amount is None:
        await ctx.session.send("Usage: clan withdraw <amount>")
        return
    await ctx.session.send(await act(clan, player, "withdraw", {"amount": amount},
                                     f"withdraw {amount} {economy.currency_name()}"))


async def _deposits(ctx: CommandContext, _rest: str) -> None:
    player = ctx.player
    clan, why = _acting_clan(player, "deposit_list")
    if clan is not None and not has_power(clan, player, "deposit_list"):
        clan, why = None, refusal(clan, player, "deposit_list")
    if clan is None:
        await ctx.session.send(why)
        return
    economy = _economy()
    money = economy.currency_name() if economy is not None else "money"
    lines = [f"The treasury of {clan.name} holds {clan.db.get('treasury') or 0} {money}. "
             f"Given by members:"]
    for obj, rec in roster(clan):
        lines.append(f"  {obj.name:16} {int(rec.get('donated_gold') or 0):>8} {money} "
                     f"{int(rec.get('donated_xp') or 0):>8} experience")
    ctx.session.send_paged("\n".join(lines))


async def _tax(ctx: CommandContext, rest: str) -> None:
    player = ctx.player
    clan, why = _acting_clan(player, "tax")
    if clan is None:
        await ctx.session.send(why)
        return
    text = rest.strip().rstrip("%")
    if not text.isdigit():
        await ctx.session.send(f"{clan.name} taxes {clan.db.get('tax') or 0}%. "
                               f"Usage: clan tax <percent>")
        return
    await ctx.session.send(await act(clan, player, "tax", {"percent": int(text)},
                                     f"set the tax to {int(text)}%"))


async def _declare(ctx: CommandContext, rest: str) -> None:
    player = ctx.player
    clan, why = _acting_clan(player, "declare")
    if clan is None:
        await ctx.session.send(why)
        return
    name, eq, what = rest.partition("=")
    other = find_clan(name)
    what = what.strip().lower()
    if not eq or what not in RELATIONS:
        await ctx.session.send(f"Usage: clan declare <clan> = {'|'.join(RELATIONS)}")
        return
    if other is None or other is clan:
        await ctx.session.send(f"There is no other clan called {name.strip()}.")
        return
    if not is_active(clan) or not is_active(other):
        await ctx.session.send("Both clans must be fully founded to declare relations.")
        return
    await ctx.session.send(await act(clan, player, "declare",
                                     {"clan": other.name, "relation": what},
                                     f"declare {what} toward {other.name}"))


async def _relations(ctx: CommandContext, rest: str) -> None:
    clan, why = _named_or_own(ctx.player, rest)
    if clan is None:
        await ctx.session.send(why)
        return
    lines = [f"Relations of {clan.name}:"]
    for other in all_clans():
        if other is clan:
            continue
        ours, theirs = relation(clan, other), relation(other, clan)
        if ours == theirs == "neutral":
            continue
        note = " (alliance)" if ours == theirs == "ally" else ""
        lines.append(f"  {other.name:20} we: {ours:9} they: {theirs}{note}")
    if len(lines) == 1:
        lines.append("  neutral toward every clan")
    await ctx.session.send("\n".join(lines))


_SUBCOMMANDS = {
    "info": _info, "who": _who, "governments": _governments, "found": _found,
    "apply": _apply, "accept": _accept, "reject": _reject, "leave": _leave,
    "assign": _assign, "exile": _exile, "premise": _premise, "motd": _motd,
    "home": _home, "donate": _donate, "recall": _recall, "disband": _disband,
    "votes": _votes, "vote": _vote, "deposit": _deposit, "withdraw": _withdraw,
    "deposits": _deposits, "tax": _tax, "declare": _declare, "relations": _relations,
}


# --- clans ---------------------------------------------------------------------


async def cmd_clans(ctx: CommandContext) -> None:
    """
    List every clan: its government, members and level.

    Usage: clans
    """
    rows = [c for c in all_clans() if c.db.get("status") == ACTIVE]
    if not rows:
        await ctx.session.send("There are no clans yet. Found one: clan found <name> = "
                               "<government> (see clan governments).")
        return
    lines = ["Clans:"]
    for clan in rows:
        gov = government_of(clan)
        lines.append(f"  {clan.name:24} {gov.name if gov else '?':12} {size(clan):>3} members"
                     f"  level {clan.db.get('level') or 1}")
    ctx.session.send_paged("\n".join(lines))


# --- @clan ---------------------------------------------------------------------

SETTABLE = {"premise": str, "motd": str, "treasury": int, "tax": int, "xp": int,
            "level": int, "status": str, "government": str, "home": str,
            "donate_room": str}


async def cmd_atclan(ctx: CommandContext) -> None:
    """
    Administer clans.

    Usage:
        @clan create <name> = <government>, <leader>
        @clan delete <name>
        @clan set <name>/<field> = <value>
        @clan xp <name> = <amount>

    The fields: premise, motd, treasury, tax, xp, level, status (pending
    or active), government, home, donate_room (room ids).
    """
    sub, _, rest = (ctx.args or "").strip().partition(" ")
    sub = sub.lower()
    if sub == "create":
        await _admin_create(ctx, rest)
    elif sub == "delete":
        clan = find_clan(rest.strip())
        if clan is None:
            await ctx.session.send(f"There is no clan called {rest.strip()}.")
            return
        name = clan.name
        await dissolve(clan, f"deleted by {ctx.player.name}")
        await ctx.session.send(f"Deleted {name}.")
    elif sub == "set":
        await _admin_set(ctx, rest)
    elif sub == "xp":
        name, eq, amount = rest.partition("=")
        clan = find_clan(name.strip())
        if clan is None or not eq or not amount.strip().lstrip("-").isdigit():
            await ctx.session.send("Usage: @clan xp <name> = <amount>")
            return
        levels = add_xp(clan, int(amount))
        await fire_levels(clan, levels)
        await ctx.session.send(f"{clan.name} has {clan.db.get('xp')} experience, level "
                               f"{clan.db.get('level')}.")
    else:
        await ctx.session.send("Usage: @clan create|delete|set|xp ... (help @clan)")


async def _admin_create(ctx: CommandContext, rest: str) -> None:
    name, eq, tail = rest.partition("=")
    gov_name, comma, leader_name = tail.partition(",")
    gov = government(gov_name.strip())
    store = get_world().store
    leaders = store.find_cached(tag="player", name=leader_name.strip()) if comma else []
    if not eq or not comma:
        await ctx.session.send("Usage: @clan create <name> = <government>, <leader>")
        return
    why = name_refusal(name)
    if why is None and gov is None:
        why = f"There is no government '{gov_name.strip()}'."
    if why is None and not leaders:
        why = f"There is no character called {leader_name.strip()}."
    if why is None and clan_of_category(leaders[0], gov.category) is not None:
        why = f"{leaders[0].name} is already in a clan of that kind."
    if why is not None:
        await ctx.session.send(why)
        return
    clan = await found(name, gov, leaders[0], how="created")
    await ctx.session.send(f"Created {clan.name}, a {gov.name} led by {leaders[0].name}.")


async def _admin_set(ctx: CommandContext, rest: str) -> None:
    target, eq, value = rest.partition("=")
    name, slash, attr = target.strip().rpartition("/")
    clan = find_clan(name)
    attr = attr.strip().lower()
    value = value.strip()
    if not eq or not slash or clan is None or attr not in SETTABLE:
        await ctx.session.send(f"Usage: @clan set <name>/<field> = <value>; fields: "
                               f"{', '.join(SETTABLE)}")
        return
    if SETTABLE[attr] is int:
        if not value.lstrip("-").isdigit():
            await ctx.session.send(f"{attr} takes a whole number.")
            return
        clan.db.set(attr, int(value))
    elif attr == "status" and value not in (PENDING, ACTIVE):
        await ctx.session.send("status is pending or active.")
        return
    elif attr == "government" and government(value) is None:
        await ctx.session.send(f"There is no government '{value}'.")
        return
    else:
        clan.db.set(attr, government(value).name if attr == "government" else value)
    if attr in ("level", "government"):
        refresh_members(clan)
    await ctx.session.send(f"{clan.name}/{attr} = {clan.db.get(attr)!r}")


__all__ = ["cmd_clan", "cmd_clans", "cmd_atclan", "clan_of_category"]
