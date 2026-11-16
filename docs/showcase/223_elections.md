# 223. Elections

> Checklist item 223 ([now]): *the `union` government: elected senators, votes, quorums and terms*

**What you'll build:** the Free Traders, a crew whose leaders are elected.
Instead of a boss who appoints, the crew lives under the **union**
government: every member votes on who sits as a Senator, and the Senators
vote on membership, exile, relations and the tax. Nothing is scripted; the
choice of government is the whole build.

**Concepts:** a **government that votes** (`clan_government_def`), the
two **vote powers** (`vote_assign` and `vote_other`), **early decision**
(a vote ends as soon as its outcome is certain), and **terms and quorums**
(`vote_days`, `vote_quorum`).

## How it works

In the [clans](../guides/clans.md) feature, an act that no position holds
outright is put to the vote. A union's positions hold no `assign`,
`accept`, `exile` or `tax` power at all; instead every position holds
`vote_assign`, and the Senators also hold `vote_other`. So the same
commands a gang's boss types to act (`clan assign`, `clan accept`) open a
vote here. This section answers who votes on what, when a vote ends, and
what happens when it passes.

### Who votes on what?

Assignments (who holds which position) are voted on by every member whose
position holds `vote_assign`: in a union, everyone. Everything else
(accepting, rejecting, exiling, setting the home, the premise, the tax,
declaring relations) is voted on by the holders of `vote_other`: the
Senators. A member may call a vote on anything they could vote on; the one
who calls it has said yes.

### When does a vote end?

As soon as its outcome is certain: it passes the moment more than half of
the eligible voters have said yes, and fails the moment that can no longer
happen. Otherwise it runs for the government's `vote_days` (48 game days
for a union) and is then counted: it passes with more yes than no, if at
least `vote_quorum` percent (66 for a union) of the voters voted. A clan
with a single eligible voter decides at once, which is how a new union's
founding Senator can accept its first members.

### What happens when it passes?

The act is carried out as if a holder of the power had typed it, and both
outcomes are announced on clan talk and to the one who called the vote. An
election is just an assignment: making Bob a Senator is `clan assign Bob =
senator`, decided by the vote.

## Build it

Import the governments if your world lacks them, and make the hall:

```text
@pack clan-governments
@dig The Free Traders Hall
@teleport The Free Traders Hall
```

Choose the union. Vala founds it and is its first Senator; a player would
type `clan found Free Traders = union` and pay `CLAN_COST`:

```text
@clan create Free Traders = union, Vala
```

## Try it

Bob and Cass apply. Accepting is a Senators' vote, and Vala is the only
Senator, so each acceptance is decided as soon as it is called:

```text
> clan apply Free Traders                  (Bob)
> clan accept Bob                          (Vala)
  Vote 1 (accept Bob) was decided at once.
> clan apply Free Traders                  (Cass)
> clan accept Cass                         (Vala)
  Vote 2 (accept Cass) was decided at once.
```

Now the election. Cass proposes Bob for Senator; every Citizen votes on
assignments, so the vote needs two of three:

```text
> clan assign Bob = senator                (Cass)
  Vote 3 is open: make Bob Senator.
> clan votes                               (Bob)
  Open votes:
    Free Traders vote 3: make Bob Senator (called by Cass). 1 yes, 0 no of 3; closes in 48.0 game days.
> clan vote 3 yes                          (Bob)
  You vote yes; vote 3 is decided.
                                           (everyone sees:)
  [Free Traders] Vote 3 (make Bob Senator) passes, 2 to 0.
  [Free Traders] Bob is now Senator.
```

A Citizen has no say on exile, and the Senators can disagree: Vala's
motion to exile Cass needs both Senators, and Bob's no ends it at once:

```text
> clan exile Bob                           (Cass)
  As Citizen of Free Traders you cannot exile members.
> clan exile Cass                          (Vala)
  Vote 4 is open: exile Cass.
> clan vote 4 no                           (Bob)
  You vote no; vote 4 is decided.
  [Free Traders] Vote 4 (exile Cass) fails, 1 to 1.
```

The one who called a vote may withdraw it with `clan vote <n> withdraw`.

## Going further

- **A different constitution.** A `fellowship` votes on everything,
  including its single First Citizen; a `guild` lets up to five
  Guildmasters act on membership and vote among themselves on positions.
  `clan governments` lists them, and the [Clans](../guides/clans.md) guide
  compares them.
- **Your own rules.** Copy the union's definition, change `vote_days` and
  `vote_quorum`, or give the Senators `accept` outright so only
  assignments are voted on ([writing a
  government](../guides/clans.md#writing-a-government)).
- **Absent leaders.** If every Senator stays away for
  `CLAN_OVERTHROW_DAYS`, the upkeep hands the top position to the
  highest-ranking member who still plays, so a union cannot be held
  hostage by a vanished senate.
