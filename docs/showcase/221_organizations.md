# 221. Player organizations

> Checklist item 221 ([now]): *the `clans` feature: a government, apply/accept/assign, a door locked with `clan()`*

**What you'll build:** the Void Runners, a player crew run from inside the
game on the engine's [clans](../guides/clans.md). The crew is a **gang**: one
boss, who accepts applicants and hands out positions (lieutenant, treasurer,
staff, member). A clubhouse back room lets in members only, and that rule is
one lock expression.

**Concepts:** a clan and its **government** (the positions that exist and
the powers each grants), the **apply and accept** handshake, **assigning**
positions, and [`clan()`](../reference/softcode.md#fn-clan) in a **lock
expression**.

## How it works

A clan is engine data, not a softcode object you script by hand. The
`clans` feature (MUD_PLAN step 14) keeps the roster, the positions and their
powers, and gives every player the `clan` command; a builder only decides
which government the crew lives under and what in the world reacts to
membership. This section answers three questions: where the crew's rules
come from, who may do what, and how a door knows a member.

### Where do the crew's rules come from?

From its government, a `clan_government_def` object. The
`clan-governments` pack ships eight, translated from CoffeeMud's
`clangovernments.xml`; `clan governments` lists them. A **gang** is ruled by
one Boss and has no votes: whatever a position may do, it does at once. In
a game made with `realm init`, the pack is already imported; this build
imports it in case your world predates it.

Players found clans themselves with `clan found <name> = <government>`,
which costs `CLAN_COST` (10000 by default). An administrator can also make
one for a player with `@clan create`, which is what this build does, so the
tutorial needs no money.

### Who may do what?

Each position grants **powers**. The Boss holds all of them; a Lieutenant
may accept and reject applicants; a Member may deposit to the treasury,
speak on clan talk (`ct`) and list the roster, and nothing more. Two rules
come with positions: a position may be full (a gang has one Boss and one
Treasurer), and nobody touches a position at or above their own unless they
hold the top one, so a Lieutenant can never exile the Boss.

That authority is the clan's, not the engine's. An administrator who is
not in the Void Runners has no say in `clan accept`; staff tools like
`@clan set` edit the clan as data, which is a different thing.

### How does a door know a member?

[`clan(caller)`](../reference/softcode.md#fn-clan) names the clan the one
trying the lock belongs to (in a lock expression the one trying is
`caller`). `clan(caller) == 'Void Runners'` is true for every member and
false for anyone else, including someone who has only applied. Because the
lock asks at the moment of passage, joining, leaving and exile change who
gets through with no edit to the door.

## Build it

Import the governments, dig the clubhouse and stand in it:

```text
@pack clan-governments
@dig The Void Runners Clubhouse
@teleport The Void Runners Clubhouse
```

Make the crew, with Vala as its Boss, and give it a premise that `clan
info` shows to anyone:

```text
@clan create Void Runners = gang, Vala
@clan set Void Runners/premise = We run the void and we pay our debts.
```

Dig the back room off the clubhouse and lock the way in to members:

```text
@dig The Back Room = back room, clubhouse
@lock back room = clan(caller) == 'Void Runners'
```

## Try it

Bob applies and Vala, the Boss, accepts them. A gang has an applicant
position, so applying is not joining: the Boss is told, and Bob waits until
someone with the `accept` power answers:

```text
> clan apply Void Runners                  (Bob)
  You apply to join Void Runners.
                                           (Vala sees:)
  [Void Runners] Bob applies to join (clan accept Bob / clan reject Bob).
> clan accept Bob                          (Vala)
  [Void Runners] Bob is accepted into Void Runners as Member.
  Bob is accepted.
> clan who                                 (Bob)
  Members of Void Runners:
    Vala             Boss                 online
    Bob              Member               online
```

A Member holds none of the Boss's powers. Cass applies, and Bob cannot
answer; the back room, which reads the same roster, does not let an
applicant in:

```text
> clan apply Void Runners                  (Cass)
> clan accept Cass                         (Bob)
  As Member of Void Runners you cannot accept members.
> back room                                (Cass)
  You can't go back room — it's locked.
```

Vala makes Bob a Lieutenant. Now Bob may accept Cass, but still cannot
touch the Boss; and once Cass is in, the door lets them through:

```text
> clan assign Bob = lieutenant             (Vala)
  [Void Runners] Bob is now Lieutenant.
  Bob is now Lieutenant.
> clan exile Vala                          (Bob)
  As Lieutenant of Void Runners you cannot exile members.
> clan accept Cass                         (Bob)
  [Void Runners] Cass is accepted into Void Runners as Member.
  Cass is accepted.
> back room                                (Cass)
  You leave back room.
```

Leaving is `clan leave`. When the last Boss leaves a gang, the
longest-serving member of the highest rank below takes the chair (a gang's
`auto_promote` is `rank`), so the crew is never left without one.

## Going further

- **A treasury and lockers:** the next tutorial,
  [222. Org treasury and storage](222_org_treasury.md), uses the clan's own
  treasury and opens lockers by clan power.
- **Elections instead of appointment:** choose the `union` government and
  the members vote their leaders in; see [223. Elections](223_elections.md).
- **Rank and power locks:** `clan_rank(caller) <= 1` lets in the Boss and
  the Lieutenants; `clan_has_power(caller, 'home_privs')` whoever the
  government lets use the clan's home.
- **A greeting on joining:** a government's `on_join` softcode runs for
  every member who joins a clan of that kind, with the new member as
  `enactor` ([Clans](../guides/clans.md#writing-a-government)).
