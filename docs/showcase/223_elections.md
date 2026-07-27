# 223. Elections

> Checklist item 223 ([now]): *ballot attrs, vote dedupe, on_tick tallies*

**What you'll build:** the Void Runners choose their Commander at the
ballot box instead of by appointment. The leader calls an election with a
term length, members `nominate` candidates and `vote`, and when the term
elapses a heartbeat tallies the ballots, installs the winner as Commander,
and steps the outgoing one down, all inside the game.

**Concepts:** an election as **ballot attributes** on the org master
(`candidates`, `ballots`); **one vote per member**, achieved by keying the
ballot dict on the voter's id so a second vote overwrites the first rather
than stacking beside it; a **term deadline** compared against
[`now()`](../reference/softcode.md#fn-now); and a **ticker tally** that
reads the [organization](221_organizations.md) rank ladder and writes the
result back into it.

## How it works

The finished machine is four attributes and one heartbeat bolted onto the
crew master from [221](221_organizations.md). Three attributes hold the
poll itself (`poll_open`, `candidates`, `ballots`), a fourth holds its
deadline (`close_at`), and the heartbeat is a `script_ticker` behavior
whose `on_tick` script counts the ballots once that deadline has passed.
This section answers three questions in turn: how one member is held to
one vote, how the term ends with nobody typing anything, and where the
winner's new rank comes from.

### How does the ballot hold each member to one vote?

`ballots` is a dict keyed by the *voter*, shaped `{voter_id:
candidate_id}`, and that shape is the entire dedupe mechanism. The `vote`
verb writes it back as
[`{**V('ballots', {}), enactor.id: other.id}`](../reference/softcode.md#fn-v),
which reassigns the voter's one slot instead of appending a second entry, so
voting again moves your single ballot and changing your mind is free.
Beside it, `candidates` is a plain list of nominated member ids. Both are
deleted when the poll closes, so the next election starts from a clean
sheet rather than inheriting last term's names.

### How does the term end with nobody typing anything?

`election start <seconds>` stamps `close_at = now() + seconds`, and that
number is the whole timer. The master carries a `script_ticker` behavior,
attached in this tutorial's build because [221](221_organizations.md)
gives the master no behavior of its own, and each beat runs the master's
`on_tick` script, which asks a single question: is a poll open, and has
`now()` reached `close_at`? Storing the deadline as an ordinary attribute
rather than an in-memory countdown like
[`wait()`](../reference/softcode.md#fn-wait) is what makes the term
durable, since the number sits on the object and any later beat can still
find the poll due.

`interval:30` counts **thirty world beats**, not thirty seconds, and a
beat is four seconds by default, so this tally wakes about every two
minutes. A poll therefore closes on the first beat after its deadline
rather than on the exact second, which is fine for a term measured in
minutes or days and worth knowing before you promise a crew a precise
closing time. While you are building, `@tr the Void Runners/on_tick`
fires the same script by hand so you never wait for a beat.

### Where does the winner's new rank come from?

The tally builds one `[count, candidate_id]` pair per candidate, sorts the
pairs highest-first, and takes the top one. It then writes straight into
221's rank ladder with
[`set_attr`](../reference/softcode.md#fn-set_attr): the outgoing Commander
steps down to Officer (rank 2),
the winner is set to Commander (rank 3), and `leader` is reassigned. The
election and the organization share one master, so the vote *is* the
promotion, with no handoff step and no staff hand on the scale. An
incumbent who wins again keeps rank 3, because the step-down line runs
only when the old leader and the winner are different people. Two
candidates finishing level are separated by whichever id happens to sort
higher, which is arbitrary, so add a runoff if your crew cares (see
"Going further").

### Who is allowed to take part?

`nominate` and `vote` each require an open poll and a rank of at least 1
on the master, which is to say you have to belong. A nomination must name
a fellow member who is not already on the ballot, and a vote must name
someone actually nominated. This is [221](221_organizations.md)'s
authority boundary once more: the ballot box respects rank, not the
engine's ownership, so an admin who never joined the crew is refused at
`vote`, `nominate`, and `election start` alike. All four verbs are
[`$`-commands](../reference/softcode.md#triggers-attributes-on-objects) on the master,
which react to typed input rather than to events, so unlike an
`ON_<EVENT>` hook they need no
[`target` guard](../reference/softcode.md#guard-on-target).

## Build it

*(Continues from [221](221_organizations.md), which built the clubhouse
and the crew master.)* The scripts below are `'''` multi-line blocks; see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs).

Stand in the clubhouse and give the master a heartbeat, which is the only
new plumbing this tutorial needs:

```text
@teleport The Void Runners Clubhouse
@behavior the Void Runners = script_ticker, interval:30
```

The tally. It runs only when a poll is open and its deadline has passed,
counts each candidate's ballots, sorts the pairs highest-first, and then
either installs the winner on the ladder or reports an empty poll. Either
way it clears the poll attributes on the way out, using
[`del_attr`](../reference/softcode.md#fn-del_attr) so the next election
starts empty:

```text
@set the Void Runners/on_tick = '''
if V('poll_open', 0) and now() >= V('close_at', 0):
    votes = list(V('ballots', {}).values())
    tally = sorted([[votes.count(cid), cid] for cid in V('candidates', [])], reverse=True)
    winner = tally[0] if tally and tally[0][0] > 0 else None
    if winner is not None:
        count, wid = winner
        old = V('leader')
        if old and old != wid:
            set_attr(me, 'rank_' + str(old), 2)  # the outgoing Commander stays on as an Officer
        set_attr(me, 'leader', wid)
        set_attr(me, 'rank_' + str(wid), 3)
        set_attr(me, 'roster', sorted(set(V('roster', []) + [wid])))
        remit(here, f"The election closes. {name(get('#' + str(wid)))} is elected Commander with {count} vote(s).")
    else:
        remit(here, 'The election closes with no votes cast.')
    set_attr(me, 'poll_open', 0)
    del_attr(me, 'ballots')
    del_attr(me, 'candidates')
    del_attr(me, 'close_at')
'''
```

`election start <seconds>` opens the polls. Only the sitting leader may
call one, the duration has to be a positive number, and a second call
while a poll is already open is refused, so the three conditions ride
together in one `if`. Opening the poll writes the empty ballot box and the
deadline, then announces the whole thing to the room with
[`remit`](../reference/softcode.md#fn-remit), while a refusal goes only to
the person who typed it via [`pemit`](../reference/softcode.md#fn-pemit).
[`trim`](../reference/softcode.md#fn-trim) plus `isdigit` is what keeps
`election start soon` from raising, since a non-numeric argument becomes a
duration of zero and falls through to the refusal:

```text
@set the Void Runners/cmd_startelection = '''
$election start *:
sec = int(arg0) if trim(arg0).isdigit() else 0
if enactor.id == V('leader') and sec > 0 and not V('poll_open', 0):
    set_attr(me, 'poll_open', 1)
    set_attr(me, 'candidates', [])
    set_attr(me, 'ballots', {})
    set_attr(me, 'close_at', now() + sec)
    remit(here, f'{name(enactor)} calls an election for Commander. Polls close in {sec} seconds. NOMINATE <name>, then VOTE <name>.')
else:
    pemit(enactor, 'Only the leader calls an election, for a positive duration, and only when none is already running.')
'''
```

`nominate <name>` puts a member on the ballot.
[`get`](../reference/softcode.md#fn-get) resolves the typed name to an
object, the nominator needs a rung of their own, the nominee has to be on
the roster, and a repeat nomination is refused rather than duplicated.
Only the id goes into `candidates`, never the object, because ids are what
the roster and the rank keys are already made of:

```text
@set the Void Runners/cmd_nominate = '''
$nominate *:
other = get(trim(arg0))
if (V('poll_open', 0) and V('rank_' + enactor.id, 0) >= 1 and other is not None
        and other.id in V('roster', []) and other.id not in V('candidates', [])):
    set_attr(me, 'candidates', V('candidates', []) + [other.id])
    remit(here, f'{name(other)} is nominated for Commander.')
else:
    pemit(enactor, 'No open election, not a member, or already nominated.')
'''
```

`vote <name>` records one ballot. The single interesting line is the
write, which rebuilds the dict with the voter's id as the key, so a member
who votes twice simply moves their existing ballot:

```text
@set the Void Runners/cmd_vote = '''
$vote *:
other = get(trim(arg0))
if (V('poll_open', 0) and V('rank_' + enactor.id, 0) >= 1
        and other is not None and other.id in V('candidates', [])):
    set_attr(me, 'ballots', {**V('ballots', {}), enactor.id: other.id})  # keyed by voter, so a re-vote replaces
    pemit(enactor, f'Your vote for {name(other)} is recorded.')
else:
    pemit(enactor, 'No open election, you are not a member, or that person is not a candidate.')
'''
```

`poll` reports the live standings and the time left, counting the same way
the tally does and printing each candidate through
[`name`](../reference/softcode.md#fn-name). A candidate whose object has
gone missing is skipped rather than breaking the listing:

```text
@set the Void Runners/cmd_poll = '''
$poll:
if V('poll_open', 0):
    left = max(0, int(V('close_at', now()) - now()))
    pemit(enactor, f'Election open, closing in {left}s:')
    votes = list(V('ballots', {}).values())
    for cid in V('candidates', []):
        who = get('#' + str(cid))
        if who is not None:
            pemit(enactor, f'  {name(who)} - {votes.count(cid)} vote(s)')
else:
    pemit(enactor, 'No election is running. The leader calls one with ELECTION START <seconds>.')
'''
```

## Try it

Vala (Commander) and Bob (Recruit) are both on the roster from
[221](221_organizations.md), and Cass never joined. Vala calls a short
election, both members stand, and each votes for themselves. The name in
brackets is whoever is at the keyboard:

```text
> election start 60                       [Vala]
Vala calls an election for Commander. Polls close in 60 seconds. NOMINATE <name>, then VOTE <name>.

> nominate Bob                            [Bob]
Bob is nominated for Commander.

> nominate Vala                           [Vala]
Vala is nominated for Commander.

> vote Bob                                [Bob]
Your vote for Bob is recorded.

> vote Vala                               [Vala]
Your vote for Vala is recorded.

> poll                                    [Bob]
Election open, closing in 60s:
  Bob - 1 vote(s)
  Vala - 1 vote(s)
```

Now watch the dedupe, which is the result worth confirming deliberately.
Vala changes her mind and votes for Bob instead. Her existing ballot moves
rather than a second one appearing, so the two totals still add to two:

```text
> vote Bob                                [Vala]
Your vote for Bob is recorded.

> poll                                    [Bob]
Election open, closing in 60s:
  Bob - 2 vote(s)
  Vala - 0 vote(s)
```

An outsider gets nowhere at all:

```text
> vote Bob                                [Cass]
No open election, you are not a member, or that person is not a candidate.
```

Now close the term. On a live server the deadline simply arrives and the
next beat notices; for a demo, push `close_at` into the past and fire the
tally by hand:

```text
> @eval set_attr(get('the Void Runners'), 'close_at', now() - 1)    [Vala]
Done.

> @tr the Void Runners/on_tick            [Vala]
The election closes. Bob is elected Commander with 2 vote(s).
Triggered the Void Runners/on_tick.

> org                                     [Vala]
The Void Runners:
  Bob - Commander
  Vala - Officer
```

That roster is the second result to confirm: 221's rank ladder has been
rewritten by the vote, with Bob up and Vala down, and nobody typed a
promote command. Run `poll` again and it answers "No election is
running", because the tally deleted `ballots`, `candidates`, and
`close_at` on its way out. Had the term expired with nobody voting, the
same beat would have announced "The election closes with no votes cast"
and left the incumbent in the chair.

## Going further

- **Terms with auto-recall.** On install, stamp `term_ends = now() +
  term`; a later beat that passes it re-opens nominations, so the crew
  votes on a fixed cycle forever without anyone remembering to call it.
- **Officer seats too.** Key elections by office, as in `election start
  quartermaster = 60`, and tally into `office_<name>`, so one crew fills
  several posts rather than only the top chair.
- **Secret ballot.** `@attr the Void Runners/ballots = secret` stops a
  curious member's script from reading who voted for whom, the same
  secret layer the [notes](225_player_notes.md) tutorial uses. `poll` and
  the tally keep working, because they run *as* the master and a master
  always reads its own attributes, and the flag lives in `attr_flags`
  rather than on the value, so it survives the `del_attr` at every
  closing.
- **Runoffs and quorums.** Compare `tally[0][0]` against `tally[1][0]` and
  re-open the poll with only those two names when they are level; or
  require `len(V('ballots', {})) >= len(V('roster', [])) // 2` before a
  result stands, leaving the incumbent in place otherwise. Each is one
  extra clause inside the tally's `if`.
