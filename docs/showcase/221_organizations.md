# 221. Player organizations

> Checklist item 221 — [now] — *guild/crew master, rank ladder attrs, invite/join flow, roster, rank authority*

**What you'll build:** the Void Runners — a player crew run entirely from
inside the game. One player founds it, officers invite outsiders, invitees
`org join`, and a rank ladder (Recruit → Officer → Commander) governs who
may promote, demote, or expel whom. The whole crew lives as attributes on
one clubhouse master.

**Concepts:** an **organization master** holding the roster and a
**rank ladder** as per-member attributes (`rank_<id>`); an **invite/join**
handshake; a shared `rankname` routine via `eval_attr`; and — the load
-bearing idea — **rank authority** enforced in softcode, kept strictly
separate from the engine's owner authority.

## How it works

**One object is the whole crew.** The Void Runners clubhouse holds:
`leader` (an id), `roster` (member ids), `invites` (pending ids),
`rank_<id>` (each member's rung), and `rank_names` (the ladder's labels).
Nothing is stored on the players themselves — membership is a ledger on
the master, so a member who logs off, or stands on the far side of the
map, is still on the books and still reachable by `pemit`.

**Two authorities, never mixed — this is the boundary to understand.**
The master is admin-owned, but that ownership is *plumbing*: it only lets
the object write its own roster and message members anywhere. Every
*social* power — who may invite, promote, demote, kick — is **rank**,
read from `rank_<id>` and checked in each verb. An admin with no rank in
the crew has no crew powers through these verbs; a Recruit with rank 1
can't promote anyone. The engine's `controls()` gate guards *data*; the
rank checks guard *the fiction*. Keeping them apart is what makes this a
player organization and not a staff tool.

**The rank rule in one line:** you may act on a member only if you
out-rank them, and you may raise someone only to a rung strictly below
your own. So a Commander (3) can lift a Recruit (1) to Officer (2), but no
one can mint a peer or a superior. The ladder can't be climbed past the
person doing the lifting.

## Build it

A clubhouse and the crew master. It's admin-owned so it can write its own
roster and reach members wherever they are — but read on: no rank flows
from that ownership:

```text
@dig The Void Runners Clubhouse
@teleport The Void Runners Clubhouse
@create the Void Runners
drop the Void Runners
@desc the Void Runners = A crew charter bolted to the wall. ORG founds/reads the roster; ORG INVITE <name>, ORG JOIN, ORG PROMOTE/DEMOTE/KICK <name>, ORG LEAVE.
@set the Void Runners/rank_names = ["", "Recruit", "Officer", "Commander"]
```

The shared ladder-label routine (one place names the rungs):

```text
@set the Void Runners/rankname = rn = V('rank_names', []); n = int(arg0); result = rn[n] if 0 <= n < len(rn) else 'Rank ' + str(n)
```

`org found` — the first claimant takes the Commander's chair:

```text
@set the Void Runners/cmd_found = $org found:ok = not V('leader'); [(set_attr(me, 'leader', enactor.id), set_attr(me, 'rank_' + enactor.id, 3), set_attr(me, 'roster', sorted(set(V('roster', []) + [enactor.id]))), remit(here, name(enactor) + ' founds the Void Runners and takes the Commander chair.')) for g in [ok] if g]; pemit(enactor, 'The Void Runners already have a leader.') if not ok else None
```

`org invite <name>` (Officer+) and `org join` (the invitee accepts):

```text
@set the Void Runners/cmd_invite = $org invite *:other = get(trim(arg0)); mine = V('rank_' + enactor.id, 0); ok = mine >= 2 and other is not None and has_tag(other, 'player') and other.id not in V('roster', []); [(set_attr(me, 'invites', sorted(set(V('invites', []) + [o.id]))), pemit(o, name(enactor) + ' invites you to join the Void Runners. Go to the clubhouse and type ORG JOIN to accept.'), pemit(enactor, 'Invitation sent to ' + name(o) + '.')) for g, o in [[ok, other]] if g]; pemit(enactor, 'Only officers invite, and only outsiders.') if not ok else None
@set the Void Runners/cmd_join = $org join:inv = V('invites', []); ok = enactor.id in inv; [(set_attr(me, 'rank_' + enactor.id, 1), set_attr(me, 'roster', sorted(set(V('roster', []) + [enactor.id]))), set_attr(me, 'invites', [i for i in inv if i != enactor.id]), remit(here, name(enactor) + ' joins the Void Runners as a Recruit.')) for g in [ok] if g]; pemit(enactor, 'You have no invitation to the Void Runners.') if not ok else None
```

`org` (bare) — the roster, sorted by rank, each rung named:

```text
@set the Void Runners/cmd_roster = $org:ros = [i for r, i in sorted([[-V('rank_' + str(x), 0), x] for x in V('roster', [])])]; pemit(enactor, 'The Void Runners:' if ros else 'The Void Runners have no members yet. ORG FOUND to start one.'); [pemit(enactor, '  ' + name(get('#' + str(i))) + ' - ' + str(eval_attr(me, 'rankname', V('rank_' + str(i), 0)))) for i in ros if get('#' + str(i))]
```

`org promote` / `org demote` / `org kick` — the rank rule, enforced three
ways:

```text
@set the Void Runners/cmd_promote = $org promote *:other = get(trim(arg0)); mine = V('rank_' + enactor.id, 0); rn = V('rank_names', []); tr = V('rank_' + other.id, 0) if other is not None else 0; ok = mine >= 2 and other is not None and other.id in V('roster', []) and other.id != enactor.id and tr + 1 < mine and tr + 1 < len(rn); [(set_attr(me, 'rank_' + o.id, t + 1), remit(here, name(enactor) + ' promotes ' + name(o) + ' to ' + str(eval_attr(me, 'rankname', t + 1)) + '.'), pemit(o, 'You have been promoted in the Void Runners.')) for g, o, t in [[ok, other, tr]] if g]; pemit(enactor, 'You cannot promote them: outrank them, and only up to below your own rung.') if not ok else None
@set the Void Runners/cmd_demote = $org demote *:other = get(trim(arg0)); mine = V('rank_' + enactor.id, 0); tr = V('rank_' + other.id, 0) if other is not None else 0; ok = mine >= 2 and other is not None and other.id in V('roster', []) and other.id != enactor.id and tr < mine and tr > 1; [(set_attr(me, 'rank_' + o.id, t - 1), remit(here, name(enactor) + ' demotes ' + name(o) + ' to ' + str(eval_attr(me, 'rankname', t - 1)) + '.'), pemit(o, 'You have been demoted in the Void Runners.')) for g, o, t in [[ok, other, tr]] if g]; pemit(enactor, 'You cannot demote them.') if not ok else None
@set the Void Runners/cmd_kick = $org kick *:other = get(trim(arg0)); mine = V('rank_' + enactor.id, 0); tr = V('rank_' + other.id, 0) if other is not None else 0; ok = mine >= 2 and other is not None and other.id in V('roster', []) and other.id != enactor.id and tr < mine; [(set_attr(me, 'roster', [i for i in V('roster', []) if i != o.id]), del_attr(me, 'rank_' + o.id), remit(here, name(enactor) + ' expels ' + name(o) + ' from the Void Runners.'), pemit(o, 'You have been removed from the Void Runners.')) for g, o in [[ok, other]] if g]; pemit(enactor, 'You cannot expel them: you must outrank a fellow member.') if not ok else None
```

`org leave` — anyone may walk, but a leader must hand off first:

```text
@set the Void Runners/cmd_leave = $org leave:ros = V('roster', []); isleader = enactor.id == V('leader'); ok = enactor.id in ros and not (isleader and len(ros) > 1); [(set_attr(me, 'roster', [i for i in ros if i != enactor.id]), del_attr(me, 'rank_' + enactor.id), del_attr(me, 'leader') if isleader else None, remit(here, name(enactor) + ' leaves the Void Runners.')) for g in [ok] if g]; pemit(enactor, 'You are not a member, or a leader must promote a successor before leaving.') if not ok else None
```

## Try it

Vala founds the crew and invites Bob; Bob accepts:

```text
(Vala) org found        -> Vala founds the Void Runners and takes the Commander chair.
(Vala) org invite Bob   -> Invitation sent to Bob.
(Bob)  org join         -> Bob joins the Void Runners as a Recruit.
org
   The Void Runners:
     Vala - Commander
     Bob - Recruit
```

The rank rule in action — the Commander can lift Bob to Officer, but Bob
(now Officer) still can't touch the Commander:

```text
(Vala) org promote Bob  -> Vala promotes Bob to Officer.
(Bob)  org kick Vala    -> You cannot expel them: you must outrank a fellow member.
```

An outsider with no rank gets nowhere: `org invite Cass` as a non-member
answers "Only officers invite." That's the boundary — even a staff account
that never `org found`ed has no standing in the fiction.

## Going further

- **Multiple crews** — every `@create`d charter is an independent org;
  a player can hold rank in several at once, since all state is keyed to
  the master, not the player.
- **Org tags for perks** — on join, `add_tag(o, 'crew:voidrunners')`
  (owner authority) so doors and shops can gate on membership with a lock
  expression, the [guarded exit](031_guarded_exit.md) pattern.
- **A shared treasury and rank-gated lockers** — that's the next tutorial,
  [022. Org treasury & storage](222_org_treasury.md), which bolts onto
  this exact master.
- **Elections instead of appointment** — let the crew *vote* its
  Commander; see [223. Elections](223_elections.md), which reads and
  writes this same rank ladder.
```
