# 226. Mentor program

> Checklist item 226 — [now] — *veteran flag, newbie matchmaking by load, pairing ledger, ON_CONNECT nudges, presence roster*

**What you'll build:** a Mentor Guild that pairs new players with
veterans. A flagged veteran types `mentor signup` to volunteer; a newcomer
types `mentor request` and is matched to the least-busy mentor; and when
either logs in, the guild nudges the other that their partner is around.

**Concepts:** a **veteran flag** (`veteran` tag) gating who may mentor; a
**matchmaker** that picks the available mentor with the fewest mentees; a
**pairing ledger** (`mentor_of_<id>`, `mentees_<id>`) on a world-zone
master; and **ON_CONNECT nudges** riding the presence roster from
[friends](219_friends_list.md) / [message in a bottle](083_message_in_bottle.md).

## How it works

**Veterans opt in; the flag is the gate.** `mentor signup` checks
`has_tag(enactor, 'veteran')` — staff grant the flag (or a playtime
milestone does) — and adds the volunteer to the `mentors` pool, tagging
them `mentor` for good measure. No flag, no mentoring: the program is
curated, not a free-for-all.

**Matchmaking is least-loaded-first.** `mentor request` builds
`[[mentee_count, mentor_id], ...]` over the pool and sorts — the mentor
with the fewest current mentees floats to the top and gets the newcomer.
The pairing is written both ways: `mentor_of_<newbie>` points up,
`mentees_<mentor>` lists down, so either side can be looked up in one read.
Storing it all on the master (not the players) means a pairing survives
logout and works across the map.

**Nudges need presence, so the guild keeps a roster.** Softcode still
can't ask who's online (audit gap G4), so the guild is a **world-zone
master** maintaining its own `online` list on `ON_CONNECT`/`ON_DISCONNECT`
— the same workaround the [friends list](219_friends_list.md) uses. On
connect it pings a mentee's mentor (if the mentor's online) and greets a
mentor with a count of their online mentees. The pairing plus the roster is
all the "someone to show you the ropes just logged in" nudge needs.

## Build it

A world-zone guild hall and the matchmaker master (admin-owned so it can
tag volunteers and reach both sides of a pairing anywhere):

```text
@dig The Mentor Guild Hall = guild, out
guild
@zone here = world
@create the Mentor Guild
drop the Mentor Guild
@desc the Mentor Guild = A welcome desk hung with "ask me" badges. MENTOR SIGNUP volunteers (veterans); MENTOR REQUEST matches a newcomer; MENTOR shows your status; MENTOR GRADUATE ends a pairing.
@zone/master the Mentor Guild = world
```

`mentor signup` (veterans only) and `mentor request` (the least-loaded
match):

```text
@set the Mentor Guild/cmd_signup = $mentor signup:ok = has_tag(enactor, 'veteran') and enactor.id not in V('mentors', []); [(set_attr(me, 'mentors', sorted(set(V('mentors', []) + [enactor.id]))), add_tag(enactor, 'mentor'), set_attr(me, 'members', sorted(set(V('members', []) + [enactor.id]))), pemit(enactor, 'You are now a mentor. New players may be matched with you.')) for g in [ok] if g]; pemit(enactor, 'You are already a mentor.' if has_tag(enactor, 'veteran') else 'Only veterans may mentor. (Ask staff for the veteran flag.)') if not ok else None
@set the Mentor Guild/cmd_request = $mentor request:cur = V('mentor_of_' + enactor.id); avail = [[len(V('mentees_' + str(m), [])), m] for m in V('mentors', []) if m != enactor.id]; pick = sorted(avail)[0][1] if avail else None; ok = not cur and pick is not None and has_tag(enactor, 'player'); [(set_attr(me, 'mentor_of_' + enactor.id, mid), set_attr(me, 'mentees_' + str(mid), V('mentees_' + str(mid), []) + [enactor.id]), set_attr(me, 'members', sorted(set(V('members', []) + [enactor.id, mid]))), pemit(enactor, 'You are matched with mentor ' + name(get('#' + str(mid))) + '. Say hello!'), pemit(get('#' + str(mid)), name(enactor) + ' has been matched to you as a new mentee.')) for g, mid in [[ok, pick]] if g]; pemit(enactor, 'You already have a mentor.' if cur else 'No mentors are available right now. Check back soon.') if not ok else None
```

`mentor` (status) and `mentor graduate` (the mentee ends it):

```text
@set the Mentor Guild/cmd_status = $mentor:cur = V('mentor_of_' + enactor.id); mine = V('mentees_' + enactor.id, []); pemit(enactor, ('Your mentor: ' + name(get('#' + str(cur)))) if cur else 'You have no mentor. MENTOR REQUEST to be matched.'); pemit(enactor, 'Your mentees: ' + ', '.join([name(get('#' + str(x))) for x in mine if get('#' + str(x))])) if mine else None
@set the Mentor Guild/cmd_graduate = $mentor graduate:cur = V('mentor_of_' + enactor.id); ok = bool(cur); [(del_attr(me, 'mentor_of_' + enactor.id), set_attr(me, 'mentees_' + str(m), [x for x in V('mentees_' + str(m), []) if x != enactor.id]), pemit(get('#' + str(m)), name(enactor) + ' has graduated from your mentorship.'), pemit(enactor, 'You have graduated. Good luck out there!')) for g, m in [[ok, cur]] if g]; pemit(enactor, 'You have no mentor to graduate from.') if not ok else None
```

The presence hooks — roster upkeep plus the login nudges:

```text
@set the Mentor Guild/on_connect = set_attr(me, 'online', [i for i in (V('online') or []) if i != enactor.id] + [enactor.id]); m = V('mentor_of_' + enactor.id); pemit(get('#' + str(m)), 'Your mentee ' + name(enactor) + ' just logged in.') if m and m in V('online', []) else None; pemit(enactor, str(len([k for k in V('mentees_' + enactor.id, []) if k in V('online', []) and k != enactor.id])) + ' of your mentees are online.') if V('mentees_' + enactor.id, []) else None
@set the Mentor Guild/on_disconnect = set_attr(me, 'online', [i for i in (V('online') or []) if i != enactor.id])
```

## Try it

Staff flag Vala a veteran; she signs up. Bob, brand new, requests a match:

```text
@tag Vala = veteran
(Vala) mentor signup     -> You are now a mentor. New players may be matched with you.
(Bob)  mentor request    -> You are matched with mentor Vala. Say hello!
(to Vala)                -> Bob has been matched to you as a new mentee.
(Vala) mentor
   Your mentees: Bob
```

Now presence does its work. When Bob logs in, Vala hears it; when Vala
logs in with Bob already on, she gets the count:

```text
(Bob connects)  -> (to Vala) Your mentee Bob just logged in.
(Vala connects) -> (to Vala) 1 of your mentees are online.
```

A second newcomer, Cass, requests a mentor. If a second veteran has signed
up, the matchmaker hands Cass to whoever has fewer mentees — spreading the
load instead of dogpiling one volunteer. Bob outgrows the program with
`mentor graduate`, and Vala's mentee list frees up for the next arrival.

## Going further

- **Auto-veteran** — grant the `veteran` tag on a playtime or level
  milestone from another master, so the pool refills itself as players
  mature.
- **Mentor rewards** — pay a small stipend on `graduate`
  (`transfer_credits` from a funded guild purse, the [job board](094_job_board.md)
  wage pattern) to reward veterans who see a newcomer through.
- **Newbie channel** — pair this with a [custom channel](074_custom_channel.md)
  that only mentors and current mentees can join, so questions have a home.
- **Match by interest** — stamp mentors with focus tags (`combat`,
  `crafting`) and let `mentor request <topic>` filter the pool before the
  least-loaded sort.
```
