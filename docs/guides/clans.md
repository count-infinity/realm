# Clans

Players found and run organizations the way CoffeeMud lets them: a clan
chooses a form of **government**, the government says which **positions**
exist and what each may do, and what no position may do alone is decided
by **vote**. All of it is the `clans` feature (MUD_PLAN step 14):

- **Governments as data**: `clan_government_def` objects; eight ship in the
  `clan-governments` pack, translated from CoffeeMud's
  `resources/clangovernments.xml`.
- **Founding** for `CLAN_COST`, joining by application, positions with
  limits, locks and powers, exile, a premise and a message of the day, a
  clan home and donation room.
- **Votes** on whatever no position holds outright, decided early when
  the outcome is certain, otherwise counted against a quorum when the term
  ends.
- **A treasury**, a **tax** on members' experience, **clan levels** and the
  **benefits** each level brings.
- **Relations** declared between clans, read by softcode.
- **Upkeep**: dead clans dissolve, long-absent leaders are replaced.
- **Clan talk** (`ct`), the clan on `who`, and **softcode** for doors and
  scripts.

`clans` requires no other feature. It reaches `economy` (the treasury and
the founding cost), `channels` (clan talk), `basics` (`who`, `recall`),
`accounts` (last logins), `rules` (the tax) and `clock` (game days)
through their services, and does without each when it is missing. It must
come after `basics` and `rules` in `FEATURES` (it adds to their services);
it is in `CLASSIC` in that order.

## Founding and joining

A game made with `realm init` imports the `clan-governments` pack in
`init_world`; in an older world, a builder types `@pack clan-governments`.
A player then sees the choices and founds:

```text
> clan governments
Clan governments (clan found <name> = <government>):
  anarchy      anyone may join, and every member may do almost anything
  co-op        a house mother and father run it; no tax, no relations
  fellowship   everything, from membership to the leader, is put to the vote
  gang         ruled by one boss, who assigns the underlings
  guild        ruled by up to five guildmasters, who vote on positions and policy
  meritocracy  ruled by whoever has given the clan the most experience
  plutocracy   ruled by whoever has given the clan the most money
  union        every member votes for senators and on membership, relations and the tax
> clan found Ravens = gang
You found Ravens, a gang, and are its Boss.
```

Founding costs `CLAN_COST` (10000) through the `economy` service and needs
`CLAN_MIN_LEVEL` (1; a character with no level counts as 1). The founder
takes the government's first position and must pass its lock and the
government's `required_lock`. With `CLAN_COST = None` players cannot found
clans; an administrator makes them with `@clan create <name> =
<government>, <leader>` (Decision D7).

A new clan is `pending` until it has `CLAN_MIN_MEMBERS` members (1 by
default, so at once); a pending clan cannot levy a tax or declare
relations, and `clans` does not list it.

`clan apply <clan>` either joins at once (a government with no
`applicant_position`, such as the anarchy) or waits in the applicant
position until someone with the `accept` power types `clan accept
<player>` (or `clan reject <player>`). An applicant holds their place but
is not yet in the clan: `clan()` in softcode, `who`, clan talk and the
member count leave them out. `clan leave` leaves (or withdraws an
application). Applying is refused by the government's `required_lock`, by
`CLAN_MAX_MEMBERS` when it is not 0, and when the character already has a
clan of that **category**: a character may belong to one clan per category
(a government's `category`, `""` by default), so a game can have trade
guilds beside fighting gangs.

## The shipped governments

| Government | Who rules | The top position is filled | What is voted on |
|---|---|---|---|
| `gang` | one Boss | by appointment; a vacancy goes to the longest-serving member of the highest rank below (`rank`) | nothing |
| `guild` | up to five Guildmasters | the same (`rank`) | assignments, the home and donation room, the premise, relations (by Guildmasters and Secretaries) |
| `union` | up to five Senators | the same (`rank`) | assignments (by everyone); membership, exile, the tax, relations, the home, the premise (by the Senators) |
| `fellowship` | one First Citizen | the same (`rank`) | everything except the treasury and the message of the day, by everyone |
| `anarchy` | nobody: one position, Freeman | nobody needs to be | nothing; anyone may join |
| `co-op` | a House Mother and a House Father | the same (`rank`) | nothing; nobody can tax or declare relations |
| `meritocracy` | the High Entrepreneurs (2% of the members) | by experience donated (`xp`) | nothing; nobody can assign |
| `plutocracy` | the Tycoons (1% of the members) | by money donated (`gold`) | nothing; nobody can assign |

Each has CoffeeMud's ranks below the top (lieutenants, treasurers,
secretaries, sheriffs, managers, moguls and the rest) with CoffeeMud's
limits and powers. `clan info <clan>` shows a clan's premise, government,
level and the holders of its public positions; `clan who` its roster
(online first), for positions with `list_members`; `clans` every active
clan.

## Positions and powers

A position is a dict in the government's ordered `positions` list, highest
rank first:

| Key | |
|---|---|
| `id` | its name in commands and softcode (`boss`, `first_citizen`) |
| `name`, `plural` | how it reads (`Boss`, `Bosses`) |
| `rank` | 0 is highest; two positions may share a rank (the co-op's) |
| `max` | holders allowed: a number, a share of the members (`"2%"`, at least 1), or None for no limit |
| `lock` | a lock expression a holder must pass (`caller` is the character, `target` the clan) |
| `public` | whether outsiders see who holds it (`clan info`, `who`) |
| `powers` | what it may do (below) |

The powers:

| Power | Lets a holder |
|---|---|
| `accept`, `reject` | answer applications |
| `assign` | move members between positions (`clan assign <member> = <position>`) |
| `exile` | put a member out (`clan exile <member>`) |
| `set_home`, `set_donate` | make the room they stand in the clan home (`clan home`) or donation room (`clan donate`) |
| `premise`, `motd_write` | write the premise (`clan premise = ...`), the message of the day (`clan motd = ...`) |
| `motd_read` | read the message of the day (`clan motd`, and at login) |
| `withdraw`, `deposit`, `deposit_list` | take from and give to the treasury, see who gave what |
| `tax` | set the tax (`clan tax <percent>`) |
| `declare` | declare a relation (`clan declare <clan> = <relation>`) |
| `channel` | speak and hear on clan talk |
| `list_members` | see the roster (`clan who`) |
| `home_privs` | go to the clan home (`clan recall`) |
| `benefits` | enjoy the clan's level benefits |
| `titles` | (a title on `who` comes from the position being `public`; the power is kept for a game's own titles) |
| `vote_assign`, `vote_other` | vote on assignments, on everything else |

A definition naming any other power is refused when definitions load, with
its name in the warning (as is one with no positions, or an
`accept_position` that is not one of its positions).

Two rules come with assignment. A position at its limit is full (`The
position of Treasurer is full.`), except the top one: assigning someone to
a full top position makes them its holder and the longest holder steps
down to the accept position, which is how a boss hands over. And nobody
assigns or exiles a member at or above their own rank, or assigns a
position at or above it, unless they hold the top position. The last
holder of the top rank cannot be moved off it until replaced.

`auto_promote` says how the top position is filled: `none` leaves it to
appointment or vote; `rank` fills a vacant top rank with the
longest-serving member of the highest rank below it that anyone holds;
`level` gives it to the highest-level qualifying member, `xp` to whoever
has donated the most experience and `gold` to whoever has donated the most
money, re-evaluated after each donation and tax payment (`level` at the
upkeep), displacing a holder who is passed. A holder keeps the position
on a tie.

## Voting

A power no position holds outright is decided by vote: assignments among
the holders of `vote_assign`, everything else among the holders of
`vote_other`. A power nobody holds and nobody can vote on cannot be used
in that government, and the command says so (`A co-op cannot levy a tax:
no position holds that power or votes on it.`). Only acts are voted on;
privileges (`deposit`, `channel`, `home_privs` and the like) a position
simply has or lacks.

A member who could vote on an act calls the vote by typing the act:

```text
> clan assign Bob = first citizen                     (Cass, in a fellowship of three)
Vote 1 is open: make Bob First Citizen.
> clan votes                                          (Bob)
Open votes:
  Friends vote 1: make Bob First Citizen (called by Cass). 1 yes, 0 no of 3; closes in 100.0 game days.
> clan vote 1 yes                                     (Bob)
[Friends] Vote 1 (make Bob First Citizen) passes, 2 to 0.
[Friends] Alice steps down to Citizen.
[Friends] Bob is now First Citizen.
You are now First Citizen of Friends.
You vote yes; vote 1 is decided.
```

The one who calls it has said yes. A vote passes as soon as more than half
of all eligible voters have said yes, and fails as soon as that is
impossible; a clan with one eligible voter therefore decides at once.
Otherwise it is counted when it closes, `vote_days` game days after it
opened: it passes with more yes than no if at least `vote_quorum` percent
of the eligible voters voted. A passed vote carries out its act as if a
holder of the power had typed it (the rank rule does not apply); either
outcome is announced on clan talk and to the one who called it. `clan vote
<n> yes|no` casts or changes a ballot (`clan vote <clan> <n> yes` when two
of your clans have a vote `n`); the caller may `clan vote <n> withdraw`.

Game days come from the `clock` service (`HOURS_PER_DAY` game hours at
`GAME_TIME_RATIO`: 48 real minutes by default). **In a game without
`clock`, one game day is one real hour.** A reaper closes the votes whose
time is up.

## The treasury and the tax

`clan deposit <amount>` (the `deposit` power) moves money from the member
to the clan's `treasury` and counts it in the member's `donated_gold`;
`clan withdraw <amount>` (`withdraw`, or a vote) moves it out to the one
who typed it (or called the vote); `clan deposits` (`deposit_list`) shows
the balance and who has given what. Without the `economy` feature the
commands say the treasury is unavailable.

`clan tax <percent>` (`tax`, at most `CLAN_MAX_TAX`, 25) takes that share
of every experience or character-point award a member earns, before the
member gets it: the share goes to the clan's `xp` and the member's
`donated_xp`, and the member is told (`Ravens takes 20 as its tax.`). The
tax is a filter on the `rules` service's `award_filters`, so it applies to
whatever pays through `award()` (kills, quest rewards). `clan donate xp
<amount>` (`deposit`) gives directly, where the game system has something
spendable: Merc's experience toward the next level (giving it never costs
a level), GURPS and D20's unspent character points
(`GameSystem.spendable_award` and `spend_award`).

## Levels and benefits

A clan starts at level 1. Its experience is cumulative, as in CoffeeMud:
a clan of level `n` reaches `n + 1` when its `xp` reaches the government's
`xp_per_level` evaluated with `level = n` (a rule expression; CoffeeMud's
`500 * level + 1000 * level ** 3` by default, so 1500 for level 2), and
members are told. `@clan xp <name> = <amount>` adds experience.

A government's `benefits` is a list of `{level, tags, check_mods,
pool_max}`. Every entry at or below the clan's level reaches each member
whose position has the `benefits` power, the way achievements do:

- `tags` are added to the character (and taken away again when the member
  leaves, is exiled, changes position, or the clan loses the level; a tag
  the character already had is not the clan's to take);
- `check_mods` (`{"stealth": 1, "all": 1}`) count in every check, through
  a `feature.check_modifier`;
- `pool_max` (`{"hp": 4}`) raises the pool's maximum while it lasts.

They are brought up to date at login and whenever membership, position or
level changes. The shipped governments carry CoffeeMud's hit point, mana
and movement bonuses (`hp` +4 at level 3, `mana` +2 at level 8, and so on
to level 20); a pool a character lacks is skipped.

## Relations

`clan declare <clan> = war|hostile|neutral|friendly|ally` (the `declare`
power, or a vote) records how this clan stands toward another. Both clans
must be active and their governments `rivalrous`. A declaration is
one-sided; `clan relations` shows both sides, and an alliance holds only
when both have declared it:

```text
> clan relations
Relations of Ravens:
  Smiths               we: ally      they: ally (alliance)
```

Softcode reads them: `clan_relation(a, b)` is clan `a`'s relation toward
`b`, and `clans_at_war(a, b)` is true when either has declared war. The
engine attaches no combat consequence; who may attack whom stays the
`crime` feature's and the zone's business, and a game's own rules can ask
`clans_at_war(clan(attacker), clan(victim))`.

## Upkeep

A reaper, once a game hour:

- dissolves a clan when fewer than `CLAN_MIN_MEMBERS` of its members have
  played within `CLAN_DEATH_DAYS` game days (2160; 0 disables), returning
  nothing and telling its members;
- replaces the holders of the top rank when every one of them has been
  away for `CLAN_OVERTHROW_DAYS` (952; 0 disables) with the highest-ranking
  qualifying member who has played within that time; the absent ones step
  down to the accept position.

"Played" is now for someone online, else their account's `last_login`,
never earlier than joining the clan. The roster prunes itself: a member
whose character no longer exists is dropped the next time the roster is
read, so deleting a character needs no call into `clans`. The last member
to leave dissolves the clan. `clan disband` (the top position) dissolves
it on purpose, after `clan disband <name>` confirms, and pays the treasury
to the one who disbands it.

## Talk, who, home

`clantalk <message>` (`ct`) speaks to the online members whose position
has `channel`: one propagated action, `clan:on_talk` (hook `CLANTALK`,
the clan as target), delivered through the `channels` feature's delivery
path, so a sleeper does not hear it. A member of clans in two categories
names the clan: `ct Smiths The forge is lit.`; `ct` alone shows the recent
lines. Without `channels`, clan talk is unavailable. Clan announcements
(joins, votes, levels) go to the same members and into the same history.

`who` shows each clan beside a member's name, after its title for a
public position: `Alice [Boss of Ravens]`, `Bob [Ravens]`.

`clan home` and `clan donate`, typed by a holder of `set_home` or
`set_donate`, make the room they stand in the clan's `home` or
`donate_room`. `clan recall` takes a member with `home_privs` there under
the same rules as `recall` (not from a `no_recall` room, a check in a
fight, the game system's cost), through the `basics` feature's `recall`
service. The message of the day is shown at login to positions with
`motd_read`.

## Softcode

The read-only functions are also there in lock expressions, where the one
trying the lock is `caller`:

| Function | |
|---|---|
| `clan(obj, category='')` | the name of `obj`'s clan, or None (an applicant is not in it yet) |
| `clan_position(obj, category='')` | the id of its position |
| `clan_rank(obj, category='')` | its position's rank, 0 highest |
| `clan_has_power(obj, power, category='')` | whether its position holds `power` outright |
| `clan_level(name)` | a clan's level |
| `clan_members(name)` | a clan's members, highest rank first |
| `clan_relation(a, b)` | clan `a`'s relation toward `b` |
| `clans_at_war(a, b)` | whether either has declared war |
| `clan_add(obj, name, position=None)` | put a character in a clan (builders; after the script) |
| `clan_remove(obj, name)` | take one out (builders; after the script) |

```text
@lock hall door = clan(caller) == 'Ravens'
@lock war room = clan_rank(caller) is not None and clan_rank(caller) <= 1
@lock armory = clan_has_power(caller, 'home_privs')
```

The events fire on the clan object, with the member as `enactor`:
`clan:on_join` (`CLANJOIN`; `adata('how')`: joined, accepted, founded,
created or added), `clan:on_leave` (`CLANLEAVE`; `reason`: left, exiled,
rejected, removed or dissolved), `clan:on_assign` (`CLANASSIGN`;
`position`, `previous`, `how`), `clan:on_level` (`CLANLEVEL`; `level`)
and `clan:on_talk` (`CLANTALK`; `message`).

Administrators: `@clan create <name> = <government>, <leader>`, `@clan
delete <name>`, `@clan set <name>/<field> = <value>` (premise, motd,
treasury, tax, xp, level, status, government, home, donate_room) and
`@clan xp <name> = <amount>`.

## Writing a government

A government is an object tagged `clan_government_def`, usually in a pack
file. Every key but `positions` and `accept_position` has a default:

| Key | Default | |
|---|---|---|
| `description` | `""` | one line, shown by `clan governments` |
| `positions` | | the ordered list above |
| `accept_position` | | where an accepted applicant lands |
| `applicant_position` | None | where an applicant waits; None: whoever applies is in at once |
| `required_lock` | None | who may apply (or found): a lock expression, `caller` the character |
| `auto_promote` | `none` | `none`, `rank`, `level`, `xp` or `gold` |
| `category` | `""` | one clan per category per character |
| `rivalrous` | True | whether its clans may declare relations |
| `vote_days`, `vote_quorum` | 24, 50 | how long a vote runs in game days; the percentage of voters needed |
| `xp_per_level` | `500 * level + 1000 * level ** 3` | the clan experience a clan of `level` needs to rise |
| `benefits` | `[]` | `{level, tags, check_mods, pool_max}` entries |
| `on_join`, `on_leave` | None | softcode run, as the definition, for a member joining or leaving (`enactor`, with the event's `adata`) |

REALM ships neither CoffeeMud's theocracy nor its family, because they
need deities and kinship. A game that has them builds them with position
locks. A theocracy, where only clerics may be high priest and every member
must worship the clan's deity:

```json
{
 "realm_format": 1,
 "objects": [
  {
   "id": "clan_government_theocracy",
   "name": "theocracy",
   "tags": ["clan_government_def"],
   "attrs": {
    "description": "clerics rule in the name of the clan's god",
    "positions": [
     {"id": "high_priest", "name": "High Priest", "rank": 0, "max": 1,
      "lock": "get_attr(caller, 'character_class') == 'cleric'",
      "powers": ["accept", "reject", "assign", "exile", "set_home", "premise",
                 "motd_write", "motd_read", "withdraw", "deposit", "deposit_list",
                 "tax", "declare", "channel", "list_members", "home_privs",
                 "benefits", "titles"]},
     {"id": "priest", "rank": 1,
      "lock": "get_attr(caller, 'character_class') == 'cleric'",
      "powers": ["accept", "reject", "deposit", "channel", "list_members",
                 "home_privs", "benefits", "titles"]},
     {"id": "believer", "rank": 2, "public": false,
      "powers": ["deposit", "channel", "list_members", "home_privs", "benefits"]},
     {"id": "applicant", "rank": 3, "public": false, "powers": []}
    ],
    "accept_position": "believer",
    "applicant_position": "applicant",
    "required_lock": "get_attr(caller, 'deity') is not None",
    "auto_promote": "level",
    "category": "faith",
    "on_join": "pemit(enactor, 'You kneel, and the faithful welcome you.')"
   }
  }
 ]
}
```

Import it with `realm import theocracy.json` (or put it in a pack). Its
`auto_promote` is `level`, as CoffeeMud's `LEVEL_OVERWRITE`: the
highest-level cleric leads (checked at the upkeep). A position lock, and
`required_lock` when someone applies, is evaluated with the clan as
`target`, so a game that gives each clan a `deity` attribute holds
believers to it with `get_attr(caller, 'deity') == get_attr(target,
'deity')`.

A family is the same pattern: positions locked on a `family` attribute
the game keeps on characters, with `required_lock` `get_attr(caller,
'family') == ...`.

## Settings

| Key | Default | |
|---|---|---|
| `CLAN_COST` | 10000 | what founding costs; None: only `@clan create` |
| `CLAN_MIN_LEVEL` | 1 | the level needed to found |
| `CLAN_MIN_MEMBERS` | 1 | members to leave `pending`, and to survive the upkeep |
| `CLAN_MAX_MEMBERS` | 0 | the most members a clan may have (0: no limit) |
| `CLAN_MAX_TAX` | 25 | the highest tax, in percent |
| `CLAN_DEATH_DAYS` | 2160 | game days without enough members playing before a clan dissolves (0: never) |
| `CLAN_OVERTHROW_DAYS` | 952 | game days of absent leaders before they are replaced (0: never) |

## Where it comes from

CoffeeMud: `resources/clangovernments.xml` (the governments),
`Common/interfaces/Clan.java` (the `Function` enum of powers, the `REL_*`
relations, `AutoPromoteFlag`), `Common/DefaultClan.java` (votes, tax as
`applyExpMods`, experience and levels in `setExp`, the default
`xp_per_level` from `DefaultClanGovernment.java`), `Commands/ClanAssign.java`
and `Libraries/Clans.java` (who votes on what), and the `CLANCOST`,
`MINCLANLEVEL`, `MINCLANMEMBERS`, `MAXCLANMEMBERS`, `DAYSCLANDEATH` and
`DAYSCLANOVERTHROW` entries of `coffeemud.ini`.

Taken: governments as data with ranked positions, limits (including
CoffeeMud's percentage limits), masks (as lock expressions) and powers;
the applicant and accept positions; `auto_promote` by rank, level,
experience and money; votes among `VOTE_ASSIGN` and `VOTE_OTHER` holders,
with each government's `MAXDAYS` and `QUORUMPCT`; a full top position
changing hands by displacing its holder to the accept position, and the
last top holder kept until replaced (`ClanAssign`); the treasury, the tax
on experience, cumulative clan experience and levels, the hit point, mana
and movement level bonuses; the five relations, one-sided, alliance only
when mutual; founding cost, minimum level, minimum and maximum members,
death and overthrow days; clan categories.

Changed: a power no position holds outright is voted on (CoffeeMud lists
the voted powers separately; for the shipped governments the two agree).
The one who calls a vote has voted yes, and a vote ends as soon as its
outcome is certain. The co-op's House Mother and House Father carry no
gender locks (REALM characters have no sex); a game that has one adds a
lock. The plutocracy's lower positions are named Tenant and Serf
(CoffeeMud reuses Hard Worker and Worker). Clan levels bring hit point,
mana and movement bonuses only.

Left out: theocracy, family and profession (deities, kinship and class
grants); conquest, trophies, clan items and enchanting, ordering
underlings, the morgue, clan journals, calendars, law books and web pages;
clan abilities (`Spell_ClanHome` and the rest), stat, attack, armor,
experience and faction adjustments among the level benefits; dues; the
`FADING` and `STAGNANT` states; titles beyond `who`. A declared war is a
fact softcode can read, with no combat consequence (MUD_PLAN Non-goals).
