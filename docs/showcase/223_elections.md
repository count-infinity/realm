# 223. Elections

> Checklist item 223 — [now] — *ballot attrs, one-vote-per-member dedupe, term close via ticker tally, winner installed as leader*

**What you'll build:** the Void Runners choose their Commander at the
ballot box instead of by appointment. The leader calls an election with a
term length; members `nominate` candidates and `vote`; when the term
elapses a heartbeat tallies the ballots, installs the winner as Commander,
and demotes the old one — all inside the game.

**Concepts:** an election as **ballot attributes** on the org master
(`candidates`, `ballots`); **one vote per member** by keying the ballot
dict on the voter id (a re-vote overwrites, never stacks); a **term
timer** (`close_at` vs `now()`); and a **ticker tally** that reads the
[organization](221_organizations.md) rank ladder and writes the result
back into it.

## How it works

**The ballot is a dict keyed by voter.** `ballots = {voter_id:
candidate_id}` — storing the vote under the *voter's* id is the whole
dedupe mechanism: voting again just reassigns your one slot, so no member
can vote twice and changing your mind is free. `candidates` is a plain
list of nominated member ids. Both clear when the election closes.

**The term is arithmetic, tallied on a heartbeat.** `election start
<seconds>` stamps `close_at = now() + seconds`. The org master already
runs a `script_ticker` for this; each beat checks whether an open election
is past `close_at`, and if so counts the ballots — for each candidate, how
many dict values point at them — takes the top, and **writes the winner
into the rank ladder from [221](221_organizations.md)**: old Commander
down to Officer (2), winner up to Commander (3), `leader` reassigned. The
election and the org share one master, so the vote *is* the promotion; no
handoff step, no staff.

**Only members inside the fiction take part.** `nominate` and `vote`
demand rank ≥ 1 (you must belong) and an open poll; you can only vote for
someone actually nominated. This is the [organization](221_organizations.md)
authority boundary once more — the ballot box respects rank, not the
engine's ownership.

## Build it

*(Continues from [221](221_organizations.md).)* The org master gains a
heartbeat and the tally hook. The tally counts each candidate's ballots,
sorts, and rewrites the ladder:

```text
@teleport The Void Runners Clubhouse
@behavior the Void Runners = script_ticker, interval:30
@set the Void Runners/on_tick = isopen = V('poll_open', 0); due = isopen and now() >= V('close_at', 0); tally = [[len([1 for v in V('ballots', {}) if V('ballots', {})[v] == c]), c] for c in V('candidates', [])]; best = sorted(tally, reverse=True)[0] if tally else None; [(set_attr(me, 'rank_' + str(V('leader')), 2) if V('leader') and V('leader') != w[1] else None, set_attr(me, 'leader', w[1]), set_attr(me, 'rank_' + str(w[1]), 3), set_attr(me, 'roster', sorted(set(V('roster', []) + [w[1]]))), set_attr(me, 'poll_open', 0), del_attr(me, 'ballots'), del_attr(me, 'candidates'), del_attr(me, 'close_at'), remit(here, 'The election closes. ' + name(get('#' + str(w[1]))) + ' is elected Commander with ' + str(w[0]) + ' vote(s).')) for g, w in [[bool(due and best and best[0] > 0), best]] if g]; (set_attr(me, 'poll_open', 0), del_attr(me, 'ballots'), del_attr(me, 'candidates'), del_attr(me, 'close_at'), remit(here, 'The election closes with no votes cast.')) if due and not (best and best[0] > 0) else None
```

The leader opens the polls; members nominate and vote:

```text
@set the Void Runners/cmd_startelection = $election start *:sec = int(arg0) if trim(arg0).isdigit() else 0; ok = enactor.id == V('leader') and sec > 0 and not V('poll_open', 0); [(set_attr(me, 'poll_open', 1), set_attr(me, 'candidates', []), set_attr(me, 'ballots', {}), set_attr(me, 'close_at', now() + s), remit(here, name(enactor) + ' calls an election for Commander. Polls close in ' + str(s) + ' seconds. NOMINATE <name>, then VOTE <name>.')) for g, s in [[ok, sec]] if g]; pemit(enactor, 'Only the leader calls an election (with a positive duration, none already running).') if not ok else None
@set the Void Runners/cmd_nominate = $nominate *:other = get(trim(arg0)); ok = V('poll_open', 0) and V('rank_' + enactor.id, 0) >= 1 and other is not None and other.id in V('roster', []) and other.id not in V('candidates', []); [(set_attr(me, 'candidates', V('candidates', []) + [o.id]), remit(here, name(o) + ' is nominated for Commander.')) for g, o in [[ok, other]] if g]; pemit(enactor, 'No open election, not a member/candidate, or already nominated.') if not ok else None
@set the Void Runners/cmd_vote = $vote *:other = get(trim(arg0)); ok = V('poll_open', 0) and V('rank_' + enactor.id, 0) >= 1 and other is not None and other.id in V('candidates', []); [(set_attr(me, 'ballots', {**V('ballots', {}), enactor.id: o.id}), pemit(enactor, 'Your vote for ' + name(o) + ' is recorded.')) for g, o in [[ok, other]] if g]; pemit(enactor, 'No open election, you are not a member, or that person is not a candidate.') if not ok else None
```

`poll` — the live tally and time left:

```text
@set the Void Runners/cmd_poll = $poll:pemit(enactor, ('Election open, closing in ' + str(max(0, int(V('close_at', now()) - now()))) + 's:') if V('poll_open', 0) else 'No election is running. The leader calls one with ELECTION START <seconds>.'); [pemit(enactor, '  ' + name(get('#' + str(c))) + ' - ' + str(len([1 for v in V('ballots', {}) if V('ballots', {})[v] == c])) + ' vote(s)') for c in V('candidates', []) if get('#' + str(c))]
```

## Try it

With Vala (Commander) and Bob (Officer) both members, Vala calls a short
election. Both stand; the crew votes:

```text
(Vala) election start 60   -> Vala calls an election for Commander. Polls close in 60 seconds.
(Bob)  nominate Bob        -> Bob is nominated for Commander.
(Bob)  vote Bob            -> Your vote for Bob is recorded.
(Vala) vote Bob            -> Your vote for Bob is recorded.
poll
   Election open, closing in 60s:
     Bob - 2 vote(s)
```

Voting again just moves your one slot — `vote` a second time for someone
else and the tally shifts, it never grows past the electorate. When the
term runs out (or you force the beat for a demo), the ticker installs the
winner:

```text
@tr the Void Runners/on_tick
   -> The election closes. Bob is elected Commander with 2 vote(s).
org
   The Void Runners:
     Bob - Commander
     Vala - Officer
```

The rank ladder from [221](221_organizations.md) has been rewritten by the
vote: Bob up, Vala down, no staff hand on the scale.

## Going further

- **Terms with auto-recall** — on install, stamp `term_ends = now() +
  term`; a later beat that passes it re-opens nominations, so the crew
  votes on a fixed cycle forever.
- **Officer seats too** — key elections by office: `election start
  quartermaster = 60`, tally into `office_<name>`, so a crew fills several
  posts, not just the top chair.
- **Secret ballot** — the tally already hides individual votes; flag the
  `ballots` attr `secret` with `@attr` so not even a curious member's
  script can read who voted for whom (the [notes](225_player_notes.md)
  secret-layer trick).
- **Quorum** — require `len(ballots) >= len(roster) // 2` before a result
  stands, else the incumbent keeps the chair — one clause in the tally
  guard.
```
