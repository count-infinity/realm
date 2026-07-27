# 221. Player organizations

> Checklist item 221 ([now]): *guilds/crews with ranks, invites, and rosters; org master objects, rank attrs, lock expressions*

**What you'll build:** the Void Runners, a player crew run entirely from inside
the game. One player founds it, officers invite outsiders, invitees `org join`,
and a rank ladder (Recruit, then Officer, then Commander) governs who may
promote, demote, or expel whom. The whole crew lives as attributes on one
clubhouse charter.

**Concepts:** an **organization master** holding the roster, a **rank ladder**
kept as per-member attributes (`rank_<id>`), an **invite/join** handshake, a
shared label routine called with
[`eval_attr`](../reference/softcode.md#fn-eval_attr), and the load-bearing idea,
**rank authority** enforced in softcode and kept strictly separate from the
engine's control authority.

## How it works

The finished crew is one ordinary object standing in a room. Players type `org`
verbs at it, the object reads and rewrites its own attributes, and every social
power in the fiction comes from a number stored on that object rather than from
anything the engine knows about. This section answers four questions: where the
crew's data lives, which authority does what, what the rank rule actually says,
and how a rung gets a name.

### Where does the crew live?

One object is the whole crew. The Void Runners charter holds `leader` (a player
id), `roster` (a list of member ids), `invites` (pending ids), one `rank_<id>`
per member holding their rung, and `rank_names`, the ladder's labels. Nothing is
stored on the players themselves, so a member who logs off, or who stands on the
far side of the map, is still on the books and still reachable with
[`pemit`](../reference/softcode.md#fn-pemit), which delivers to a target in any
room.

The alternative would be tagging each member with something like
`crew:voidrunners` and rebuilding the roster from
[`search_world`](../reference/softcode.md#fn-search_world). That works, but it
costs a capped world scan every time somebody types `org`, it needs a second
tag (or a [`tag_value`](../reference/softcode.md#fn-tag_value)) to carry the
rung, and stamping a tag onto a player
object requires authority over that player. Keeping the ledger on the charter
makes the roster a single attribute read, which is why the build below does it
that way. The tag is still useful as a *derived* marker for doors and shops to
test, and "Going further" adds one.

### Which authority does what?

Two authorities run side by side here, and the whole tutorial rests on keeping
them apart.

The engine's authority is [`controls`](../reference/softcode.md#fn-controls),
the gate every mutation passes. A script runs as its own object, and an object
always controls itself, so the charter can rewrite its own `roster`, `invites`,
and `rank_<id>` attributes no matter who owns it. Ownership only starts to
matter when the master writes on *another* object: from an admin-owned charter,
[`set_attr`](../reference/softcode.md#fn-set_attr) and
[`add_tag`](../reference/softcode.md#fn-add_tag) aimed at a player succeed
through owner delegation, while from a builder-owned one they return `False` and
change nothing, silently, because a builder controls unowned world props but
never player objects. This build stays inside the charter's own attributes, so
it runs either way; the tag idea in "Going further" is the part that wants an
admin owner.

The crew's authority is **rank**, read from `rank_<id>` and checked by hand in
every verb. An admin who never joined has rank 0 and therefore no crew powers
through these verbs, and a Recruit at rank 1 may promote nobody. (That admin
could of course `@set` the charter's attributes directly, since builder tools
answer to `controls`, but that is editing the object, not acting in the
fiction.) The engine gate guards *data*; the rank checks guard *the fiction*,
and that separation is what makes this a player organization rather than a staff
tool.

### What is the rank rule?

You may act on a member only if you outrank them, and you may raise someone only
to a rung strictly below your own. A Commander at 3 lifts a Recruit at 1 to
Officer at 2, and nobody mints a peer or a superior. The same comparison also
rules out acting on yourself, since your rung never outranks itself, so the
verbs need no separate self check.

### How does a rung get a name?

`rank_names` is a plain list, so rung 2 is `rank_names[2]`. Rather than repeat
that lookup in the roster, promote, and demote verbs, one attribute named
`rankname` does it and those verbs
call it with [`eval_attr`](../reference/softcode.md#fn-eval_attr), which
evaluates an attribute as a subroutine and returns its `result`. `eval_attr`
leaves the executor unchanged, so inside `rankname` the name `me` is still the
charter and [`V`](../reference/softcode.md#fn-v) reads the charter's own
`rank_names`.

Every verb below is a `$`-command rather than an `ON_<EVENT>` hook, so none of
them carries an `if target is me:`
[target guard](../reference/softcode.md#guard-on-target): a hook fires on every
object in the room, while a `$`-command runs only on the object whose pattern
matched, and the search stops at the first match. Two consequences are worth
holding on to. A charter answers only players standing in its room, which is why
the invitation tells the invitee where to go, and one room holds one charter,
because a second object carrying the same `$org` patterns would never be
reached.

## Build it

Dig the clubhouse, create the charter, and drop it so its `$org` commands are in
reach of anyone standing there:

```text
@dig The Void Runners Clubhouse
@teleport The Void Runners Clubhouse
@create the Void Runners
drop the Void Runners
@desc the Void Runners = A crew charter bolted to the wall. ORG reads the roster; ORG FOUND, ORG INVITE <name>, ORG JOIN, ORG PROMOTE/DEMOTE/KICK <name>, ORG LEAVE.
```

The ladder is data rather than code, so it stays a single-line `@set` with a
JSON list as its value. Index 0 is the empty rung an outsider holds, which keeps
every other index equal to the rank number it names:

```text
@set the Void Runners/rank_names = ["", "Recruit", "Officer", "Commander"]
```

Now the shared label routine, so exactly one place turns a number into a word.
It reads the ladder, coerces the argument the caller passed, and falls back to a
generic label if the ladder is shorter than the number:

```text
@set the Void Runners/rankname = '''
ladder = V('rank_names', [])
n = int(arg0)
result = ladder[n] if 0 <= n < len(ladder) else f'Rank {n}'
'''
```

`org found` seats the first claimant in the Commander's chair. It refuses if a
leader already exists, and otherwise writes three attributes (the leader id, the
founder's rung, and the roster) before announcing the moment to the room with
[`remit`](../reference/softcode.md#fn-remit):

```text
@set the Void Runners/cmd_found = '''
$org found:
if V('leader'):
    pemit(enactor, 'The Void Runners already have a leader.')
else:
    set_attr(me, 'leader', enactor.id)
    set_attr(me, 'rank_' + enactor.id, 3)
    set_attr(me, 'roster', sorted(set(V('roster', []) + [enactor.id])))
    remit(here, f'{name(enactor)} founds the Void Runners and takes the Commander chair.')
'''
```

`org invite <name>` is the officers' half of the handshake. It resolves the
named person with [`get`](../reference/softcode.md#fn-get) and
[`trim`](../reference/softcode.md#fn-trim), checks the caller's own rung, and
then walks three refusals before the commit: too junior, no such person, or
already a member. [`has_tag`](../reference/softcode.md#fn-has_tag) keeps the
invitation pointed at a player rather than at a crate:

```text
@set the Void Runners/cmd_invite = '''
$org invite *:
other = get(trim(arg0))
mine = V('rank_' + enactor.id, 0)
roster = V('roster', [])
if mine < 2:
    pemit(enactor, 'Only officers invite people into the Void Runners.')
elif other is None or not has_tag(other, 'player'):
    pemit(enactor, 'There is nobody here by that name.')
elif other.id in roster:
    pemit(enactor, f'{name(other)} already rides with the Void Runners.')
else:
    set_attr(me, 'invites', sorted(set(V('invites', []) + [other.id])))
    pemit(other, f'{name(enactor)} invites you to join the Void Runners. Go to the clubhouse and type ORG JOIN to accept.')
    pemit(enactor, f'Invitation sent to {name(other)}.')
'''
```

`org join` is the invitee's half. Accepting spends the invitation, so the same
line writes the new Recruit's rung, extends the roster, and drops the id from
`invites`:

```text
@set the Void Runners/cmd_join = '''
$org join:
invites = V('invites', [])
if enactor.id in invites:
    set_attr(me, 'rank_' + enactor.id, 1)
    set_attr(me, 'roster', sorted(set(V('roster', []) + [enactor.id])))
    set_attr(me, 'invites', [i for i in invites if i != enactor.id])
    remit(here, f'{name(enactor)} joins the Void Runners as a Recruit.')
else:
    pemit(enactor, 'You have no invitation to the Void Runners.')
'''
```

Bare `org` prints the roster from the top rung down. It turns each stored id
back into an object, sorts on the negated rung so the highest sorts first (with
the name breaking ties), and names each rung through the shared routine:

```text
@set the Void Runners/cmd_roster = '''
$org:
# get() returns None for a member whose object is gone, so filter before naming.
members = [m for m in [get('#' + i) for i in V('roster', [])] if m is not None]
ranked = sorted([[-V('rank_' + m.id, 0), name(m)] for m in members])
if not ranked:
    pemit(enactor, 'The Void Runners have no members yet. ORG FOUND to start one.')
else:
    pemit(enactor, 'The Void Runners:')
    for neg, who in ranked:
        label = eval_attr(me, 'rankname', -neg)
        pemit(enactor, f'  {who} - {label}')
'''
```

`org promote` is the rank rule written out. The caller must be an officer, the
target must be a member, and the new rung has to land strictly below the
caller's own and inside the ladder:

```text
@set the Void Runners/cmd_promote = '''
$org promote *:
other = get(trim(arg0))
mine = V('rank_' + enactor.id, 0)
ladder = V('rank_names', [])
theirs = V('rank_' + other.id, 0) if other is not None else 0
if other is None or other.id not in V('roster', []):
    pemit(enactor, 'No Void Runner by that name.')
# theirs + 1 >= mine also blocks promoting yourself: a rung never outranks itself.
elif mine < 2 or theirs + 1 >= mine or theirs + 1 >= len(ladder):
    pemit(enactor, 'You may promote only a member you outrank, and only as far as the rung below your own.')
else:
    set_attr(me, 'rank_' + other.id, theirs + 1)
    label = eval_attr(me, 'rankname', theirs + 1)
    remit(here, f'{name(enactor)} promotes {name(other)} to {label}.')
    pemit(other, 'You have been promoted in the Void Runners.')
'''
```

`org demote` is the mirror image, with a floor at Recruit: a member already at
rung 1 leaves the crew by being expelled rather than by sinking to rung 0:

```text
@set the Void Runners/cmd_demote = '''
$org demote *:
other = get(trim(arg0))
mine = V('rank_' + enactor.id, 0)
theirs = V('rank_' + other.id, 0) if other is not None else 0
if other is None or other.id not in V('roster', []):
    pemit(enactor, 'No Void Runner by that name.')
elif mine < 2 or theirs >= mine or theirs <= 1:
    pemit(enactor, 'You may demote only a member you outrank, and never below Recruit.')
else:
    set_attr(me, 'rank_' + other.id, theirs - 1)
    label = eval_attr(me, 'rankname', theirs - 1)
    remit(here, f'{name(enactor)} demotes {name(other)} to {label}.')
    pemit(other, 'You have been demoted in the Void Runners.')
'''
```

`org kick` drops the id from the roster and deletes the rung attribute with
[`del_attr`](../reference/softcode.md#fn-del_attr), so no stale rank is left
behind if that player is invited back later:

```text
@set the Void Runners/cmd_kick = '''
$org kick *:
other = get(trim(arg0))
mine = V('rank_' + enactor.id, 0)
theirs = V('rank_' + other.id, 0) if other is not None else 0
if other is None or other.id not in V('roster', []):
    pemit(enactor, 'No Void Runner by that name.')
elif mine < 2 or theirs >= mine:
    pemit(enactor, 'To expel someone, you must outrank a fellow member.')
else:
    set_attr(me, 'roster', [i for i in V('roster', []) if i != other.id])
    del_attr(me, 'rank_' + other.id)
    remit(here, f'{name(enactor)} expels {name(other)} from the Void Runners.')
    pemit(other, 'You have been removed from the Void Runners.')
'''
```

`org leave` lets anyone walk, with one exception: while other members remain,
the leader has to hand the chair over first, so the crew is never left with a
`leader` id that is no longer on the roster. The last member out clears the
`leader` attribute on the way:

```text
@set the Void Runners/cmd_leave = '''
$org leave:
roster = V('roster', [])
is_leader = enactor.id == V('leader')
if enactor.id not in roster:
    pemit(enactor, 'You are not a Void Runner.')
elif is_leader and len(roster) > 1:
    pemit(enactor, 'A leader must promote a successor before leaving.')
else:
    set_attr(me, 'roster', [i for i in roster if i != enactor.id])
    del_attr(me, 'rank_' + enactor.id)
    if is_leader:
        del_attr(me, 'leader')
    remit(here, f'{name(enactor)} leaves the Void Runners.')
'''
```

## Try it

Vala founds the crew, invites Bob, and Bob accepts. The founding and joining
lines are room emits, so everyone in the clubhouse sees them, while the
invitation and the confirmation are private:

```text
> org found                                (Vala)
  Vala founds the Void Runners and takes the Commander chair.
> org invite Bob                           (Vala)
  Invitation sent to Bob.
                                           (Bob sees:)
  Vala invites you to join the Void Runners. Go to the clubhouse and type ORG JOIN to accept.
> org join                                 (Bob)
  Bob joins the Void Runners as a Recruit.
> org                                      (Bob)
  The Void Runners:
    Vala - Commander
    Bob - Recruit
```

Now confirm the two halves of the rank rule deliberately. A Recruit is too
junior to invite anyone, and once promoted to Officer he still stops one rung
short of the Commander above him:

```text
> org invite Cass                          (Bob, still a Recruit)
  Only officers invite people into the Void Runners.
> org promote Bob                          (Vala)
  Vala promotes Bob to Officer.
> org kick Vala                            (Bob, now an Officer)
  To expel someone, you must outrank a fellow member.
> org invite Cass                          (Bob, now an Officer)
  Invitation sent to Cass.
```

Demotion runs the ladder the other way and stops at Recruit, since rung 0 means
"outsider" and leaving the crew is `org kick` or `org leave` rather than a
demotion:

```text
> org demote Bob                           (Vala)
  Vala demotes Bob to Recruit.
> org demote Bob                           (Vala)
  You may demote only a member you outrank, and never below Recruit.
```

The founder is held to the same ladder. While Bob is still aboard, Vala's exit
is refused, and the crew keeps a leader:

```text
> org leave                                (Vala)
  A leader must promote a successor before leaving.
> org leave                                (Bob)
  Bob leaves the Void Runners.
```

The refusals are the results worth confirming deliberately, because each one is
decided by a `rank_<id>` attribute and by nothing else. Vala's powers here come
from having founded the crew rather than from her staff tag, so a second staff
account that never ran `org found` is refused exactly as Bob was.

## Going further

- **A second crew:** every `@create`d charter is an independent organization
  with its own roster, and a player may hold rank in several at once, since all
  state is keyed to the charter rather than to the player. Give each crew its
  own clubhouse room, though, because a `$`-command search stops at the first
  matching object, so two charters sharing a room would leave the second one
  mute. Renaming the verbs on the second charter (`wardens invite`) is the other
  way out.
- **Org tags for perks:** on join, add `add_tag(other, 'crew:voidrunners')` so
  doors and shops gate on membership with a lock expression, the
  [guarded exit](031_guarded_exit.md) pattern. The tag write reaches a player
  object only from an admin-owned charter, and pair it with a matching
  [`remove_tag`](../reference/softcode.md#fn-remove_tag) in `org kick` and
  `org leave` so the perk expires with the membership.
- **A shared treasury and rank-gated lockers:** the next tutorial,
  [222. Org treasury and storage](222_org_treasury.md), bolts onto this exact
  charter and reads the same `rank_<id>` attributes.
- **Elections instead of appointment:** let the crew vote for its Commander in
  [223. Elections](223_elections.md), which reads and rewrites this same rank
  ladder from a ticker.
