"""
The ``clans`` feature.

Clans with governments, after CoffeeMud (MUD_PLAN step 14): governments as
data (``clan_government_def``) with positions, powers and votes; founding
for ``CLAN_COST``; a treasury, a tax on experience, clan levels with
benefits, declared relations, upkeep, clan talk, and clan locks in
softcode. See docs/guides/clans.md.

It requires nothing: ``economy``, ``channels``, ``basics`` (``who``,
``recall``), ``accounts`` (last logins), ``rules`` (the tax) and
``clock`` (game days) are reached through their services.
"""

from __future__ import annotations

from types import SimpleNamespace

from realm.core.action_types import ActionType
from realm.features import Feature, FeatureError
from realm.std.clans import clans as clan_clock
from realm.std.clans import softcode
from realm.std.clans.benefits import benefit_modifier, clear_cache, refresh
from realm.std.clans.clans import (
    ASSIGN,
    JOIN,
    LEAVE,
    LEVEL,
    TALK,
    clan_of,
    clans_of,
    day_seconds,
    find_clan,
    has_power,
    is_member,
    position_of,
    tax_filter,
    upkeep,
)
from realm.std.clans.commands import cmd_atclan, cmd_clan, cmd_clans
from realm.std.clans.governments import parse_government
from realm.std.clans.talk import cmd_clantalk
from realm.std.clans.votes import close_expired

feature = Feature(
    'clans',
    doc='Clans with governments, positions, powers and votes, after CoffeeMud.',
)

feature.setting("CLAN_COST", 10000,
                "What founding a clan costs (CoffeeMud's CLANCOST), through the economy. "
                "None: only administrators found clans (`@clan create`).")
feature.setting("CLAN_MIN_LEVEL", 1, "The level a character needs to found a clan "
                "(MINCLANLEVEL; a character with no level counts as 1).")
feature.setting("CLAN_MIN_MEMBERS", 1,
                "Members a clan needs to leave `pending` (and to declare relations or levy "
                "a tax), and how many must have played within CLAN_DEATH_DAYS for it to "
                "survive (MINCLANMEMBERS).")
feature.setting("CLAN_MAX_MEMBERS", 0, "The most members a clan may have; 0: no limit "
                "(MAXCLANMEMBERS).")
feature.setting("CLAN_MAX_TAX", 25, "The highest tax, in percent, a clan may levy on its "
                "members' experience.")
feature.setting("CLAN_DEATH_DAYS", 2160,
                "Game days within which CLAN_MIN_MEMBERS members must have played, or the "
                "clan is dissolved (DAYSCLANDEATH). 0: never.")
feature.setting("CLAN_OVERTHROW_DAYS", 952,
                "Game days after which a clan whose leaders have all been away is handed to "
                "its highest-ranking member who has played since (DAYSCLANOVERTHROW). 0: "
                "never.")

feature.def_kind("clan_government", "clan_government_def", parse_government)

feature.command('clan', cmd_clan, category='social',
                help_text='Found, join and run a clan',
                usage='clan [<subcommand> ...] (help clan)')
feature.command('clans', cmd_clans, category='social', help_text='List the clans',
                usage='clans')
feature.command('clantalk', cmd_clantalk, aliases=['ct'], category='communication',
                help_text='Talk to your clan', usage='clantalk [<clan>] <message>')
feature.command('@clan', cmd_atclan, category='building', permission='admin',
                help_text='Create, delete and change clans',
                usage='@clan create|delete|set|xp ...')

feature.check_modifier(benefit_modifier)
feature.on_reload(clear_cache)
feature.on_close(clear_cache)

for _type, _hook, _doc, _payload in (
        (JOIN, "CLANJOIN", "a character joined this clan (the member is `enactor`)",
         {"clan": "the clan's name", "position": "the position id",
          "how": "joined, accepted, founded, created or added"}),
        (LEAVE, "CLANLEAVE", "a member left this clan (the member is `enactor`)",
         {"clan": "the clan's name",
          "reason": "left, exiled, removed or dissolved"}),
        (ASSIGN, "CLANASSIGN", "a member of this clan changed position (`enactor`)",
         {"clan": "the clan's name", "position": "the new position id",
          "previous": "the old position id",
          "how": "assigned, voted, displaced, promoted, overthrown or overthrow"}),
        (LEVEL, "CLANLEVEL", "this clan reached a new level",
         {"clan": "the clan's name", "level": "the new level"}),
        (TALK, "CLANTALK", "a member spoke on clan talk (`enactor`)",
         {"clan": "the clan's name", "message": "what was said"})):
    feature.event(_type, hook=_hook, doc=_doc, payload=_payload)

for _fn in (softcode.clan, softcode.clan_position, softcode.clan_rank,
            softcode.clan_has_power, softcode.clan_level, softcode.clan_members,
            softcode.clan_relation, softcode.clans_at_war):
    feature.softfn(_fn, group='Clans', readonly=True)
feature.softfn(softcode.clan_add, group='Clans', harm=True)
feature.softfn(softcode.clan_remove, group='Clans', harm=True)
feature.queue_kind("clan_add", softcode.queued_add)
feature.queue_kind("clan_remove", softcode.queued_remove)


_last_upkeep = {"at": None}


@feature.reaper
async def clan_sweep(store) -> None:
    """Count the votes whose time is up; once a game hour, the upkeep."""
    await close_expired()
    stamp = clan_clock.now()
    last = _last_upkeep["at"]
    if last is None or stamp - last >= day_seconds() / 24:
        _last_upkeep["at"] = stamp
        await upkeep()


@feature.observer
async def clans_observer(action) -> None:
    """At login a character takes its clan benefits and reads each clan's
    message of the day its position may read."""
    if action.action_type != ActionType.CONNECT or action.actor is None:
        return
    player = action.actor
    refresh(player)
    for clan in clans_of(player):
        motd = clan.db.get("motd")
        if motd and is_member(clan, player) and has_power(clan, player, "motd_read"):
            player.msg(f"[{clan.name}] {motd}")


def clan_field(viewer, player) -> str | None:
    """A ``who`` field: each clan's name, after its title for a public
    position (``Boss of Ravens``)."""
    out = []
    for clan in clans_of(player):
        if not is_member(clan, player):
            continue
        pos = position_of(clan, player)
        out.append(f"{pos.name} of {clan.name}" if pos is not None and pos.public
                   else clan.name)
    return ", ".join(out) or None


@feature.on_install
def _offer_clans(world) -> None:
    """``who`` shows clans (``basics``'s ``who`` service) and the tax takes
    its share of awards (the ``rules`` service's ``award_filters``), so
    ``clans`` comes after both in ``FEATURES``; ``world.services["clans"]``
    answers who is in which clan."""
    loaded = set(world.features.names)
    for name, service in (("basics", "who"), ("rules", "rules")):
        if name in loaded and service not in world.services:
            raise FeatureError(f"'clans' must come after {name!r} in FEATURES (it adds to "
                               f"the {service} service)")
    who = world.services.get("who")
    if who is not None:
        who.fields.append(clan_field)
    rules = world.services.get("rules")
    if rules is not None:
        rules.award_filters.append(tax_filter)
    world.services["clans"] = SimpleNamespace(clan_of=clan_of, clans_of=clans_of,
                                              find_clan=find_clan, has_power=has_power)
