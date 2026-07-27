# 226. Mentor program

> Checklist item 226 ([now]): *mentor tags, pairing attrs, ON_CONNECT nudges*

**What you'll build:** a Mentor Guild that pairs new players with veterans. A
flagged veteran types `mentor signup` to volunteer, a newcomer types `mentor
request` and is matched to the least-busy volunteer, and when either of them
logs in the guild tells the other that their partner is around.

**Concepts:** a **veteran flag** (the `veteran` tag) gating who may mentor; a
**matchmaker** that picks the available mentor with the fewest mentees; a
**two-way pairing** (`mentor_of_<id>` and `mentees_<id>`) stored on a
world-zone master; and **`ON_CONNECT` nudges** riding a presence roster of the
kind the [friends list](219_friends_list.md) and the
[message in a bottle](083_message_in_bottle.md) keep.

## How it works

The finished guild is one admin-owned object standing in a `zone:world` room.
It carries four `$`-commands (`mentor signup`, `mentor request`, `mentor`,
`mentor graduate`), a handful of pairing attributes, and two connection hooks.
Everything a pairing needs lives on that single object, so nothing is lost when
a player logs out and nothing has to be searched for at match time. This
section answers four questions: who is allowed to volunteer, how the matchmaker
chooses, where a pairing is written, and how the guild finds out that somebody
logged in.

### Who is allowed to mentor?

`mentor signup` opens with
[`has_tag(enactor, 'veteran')`](../reference/softcode.md#fn-has_tag), so the
program is curated rather than open to anyone. Staff hand the flag out with
`@tag <player> = veteran`, or another master grants it on a playtime or level
milestone. A volunteer who passes the check is appended to the guild's
`mentors` list and also picks up a `mentor` tag with
[`add_tag`](../reference/softcode.md#fn-add_tag), which is handy for locks and
channel membership elsewhere.

That `add_tag` is the reason the guild is created by an admin. Softcode runs
with the authority of the object it runs on, and an object wields its owner's
authority, so an **admin-owned** guild controls the players who talk to it and
may tag them. A guild owned by an ordinary builder would silently fail that
line, because builder authority reaches unowned world props and stops short of
players.

### How does the guild pick a mentor for a newcomer?

`mentor request` sorts the pool by load. It builds one `[mentee_count,
mentor_id]` pair per volunteer, sorts the list, and takes the first entry, so
the volunteer with the fewest current mentees receives the newcomer and the
work spreads instead of piling onto whoever signed up first. Ties fall to the
lower object id, which is stable but arbitrary. The requester is filtered out
of the pool, so a veteran who wants a mentor of their own is never matched with
themselves.

### Where does a pairing live?

Both directions are written, on the guild and nowhere else:

- `mentor_of_<mentee id>` holds one mentor id, pointing up the relationship.
- `mentees_<mentor id>` holds a list of mentee ids, pointing down it.

Either side is then a single [`V()`](../reference/softcode.md#fn-v) read, with
no scan of the world and no walk over the other key. Keeping both halves on the
master (rather than on the two players) means a pairing survives logout,
reaches players standing anywhere in the zone, and stays readable by the
connection hooks below, which run as the guild and see only the guild's own
attributes cheaply.

### How does the guild know somebody logged in?

Softcode has no primitive that answers "who is online" (sessions are invisible
to scripts, audit gap G4 in
[capability_audit.md](capability_audit.md)), so the guild keeps its own
`online` list, refreshed by its
[`ON_CONNECT` and `ON_DISCONNECT`](../reference/softcode.md#lifecycle-hooks)
hooks. Two engine facts make that work:

- A lifecycle event reaches every object in the room where it happened **and**
  every zone master whose `zone:` tag the room carries, which is why one guild
  object standing in the hall hears logins from every `zone:world` room on the
  map. Logins in rooms outside the zone are not heard, so tag the rooms you
  care about into `world`.
- Inside the hook, `enactor` is the player who just connected and `target` is
  the room they appeared in.

That second point decides the guard. An `ON_<EVENT>` hook normally opens with
[`if target is me:`](../reference/softcode.md#guard-on-target) because the hook
fires on every object present, not only the one the action aimed at. A
connection aims at a room, so `target is me` would never be true for the guild
and the hook would go silent forever. The guild is the deliberate exception:
it is a **global witness** and takes no target guard, filtering on `enactor`
instead. Every branch in the hook is keyed to the connecting player's own
pairing attributes, so a login by somebody with no mentor and no mentees
produces no output at all. For the propagation model behind this, see
[Action Propagation](../architecture/events.md) and the
[event bus tour](245_event_bus_tour.md).

With the roster in hand the nudges are two reads. If the connecting player has
a mentor and that mentor is already on the roster, the mentor is told. If the
connecting player has mentees, they get a count of how many of them are on.

## Build it

A world-zone guild hall, then the matchmaker itself. `@zone here = world`
tags the room into the zone and `@zone/master` crowns the guild, which is the
pair of lines that lets one object hear the whole zone. Create it as an admin,
because it tags volunteers and messages both sides of a pairing:

```text
@dig The Mentor Guild Hall = guild, out
guild
@zone here = world
@create the Mentor Guild
drop the Mentor Guild
@desc the Mentor Guild = A welcome desk hung with "ask me" badges. MENTOR SIGNUP volunteers (veterans); MENTOR REQUEST matches a newcomer; MENTOR shows your status; MENTOR GRADUATE ends a pairing.
@zone/master the Mentor Guild = world
```

Every script below is a `'''` multi-line block: end the `@set` line with a
trailing `'''`, write the body as ordinary indented softcode, and close with a
line of just `'''` (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)).
For a `$`-command the pattern line is the first line inside the block.

**Volunteering.** `mentor signup` rejects the unflagged, refuses a second
signup, and otherwise records the volunteer three ways: on the `mentors` pool,
with a `mentor` tag, and in the confirmation back to them.

```text
@set the Mentor Guild/cmd_signup = '''
$mentor signup:
if not has_tag(enactor, 'veteran'):
    pemit(enactor, 'Only veterans may mentor. (Ask staff for the veteran flag.)')
elif enactor.id in V('mentors', []):
    pemit(enactor, 'You are already a mentor.')
else:
    set_attr(me, 'mentors', sorted(set(V('mentors', []) + [enactor.id])))
    add_tag(enactor, 'mentor')  # needs an admin owner: builders may not tag players
    pemit(enactor, 'You are now a mentor. New players may be matched with you.')
'''
```

**Matching.** `mentor request` builds the load table, refuses when the caller
already has a mentor or the pool is empty, and otherwise writes both halves of
the pairing with [`set_attr`](../reference/softcode.md#fn-set_attr) before
telling each side about the other:

```text
@set the Mentor Guild/cmd_request = '''
$mentor request:
pool = [m for m in V('mentors', []) if m != enactor.id]
load = sorted([[len(V('mentees_' + m, [])), m] for m in pool])
if not has_tag(enactor, 'player'):
    pemit(enactor, 'Only players may be matched with a mentor.')
elif V('mentor_of_' + enactor.id):
    pemit(enactor, 'You already have a mentor.')
elif not load:
    pemit(enactor, 'No mentors are available right now. Check back soon.')
else:
    mid = load[0][1]  # fewest mentees first; a tie falls to the lower object id
    mentor = get('#' + mid)
    set_attr(me, 'mentor_of_' + enactor.id, mid)
    set_attr(me, 'mentees_' + mid, V('mentees_' + mid, []) + [enactor.id])
    pemit(enactor, f'You are matched with mentor {name(mentor)}. Say hello!')
    pemit(mentor, f'{name(enactor)} has been matched to you as a new mentee.')
'''
```

**Status.** Plain `mentor` reads both directions of the pairing for whoever
typed it, which is one line for the mentor they have and, when they have any,
one line for the mentees they carry. Ids are resolved through
[`get`](../reference/softcode.md#fn-get) and dead ones are dropped, so a
departed player leaves no broken entry:

```text
@set the Mentor Guild/cmd_status = '''
$mentor:
mid = V('mentor_of_' + enactor.id)
mentor = get('#' + mid) if mid else None
mine = [p for p in [get('#' + i) for i in V('mentees_' + enactor.id, [])] if p]
if mentor:
    pemit(enactor, f'Your mentor: {name(mentor)}')
else:
    pemit(enactor, 'You have no mentor. MENTOR REQUEST to be matched.')
if mine:
    pemit(enactor, 'Your mentees: ' + ', '.join([name(p) for p in mine]))
'''
```

**Graduating.** The mentee ends the pairing, and both halves have to come apart
together: [`del_attr`](../reference/softcode.md#fn-del_attr) clears the upward
key while the mentor's list is rewritten without them.

```text
@set the Mentor Guild/cmd_graduate = '''
$mentor graduate:
mid = V('mentor_of_' + enactor.id)
if not mid:
    pemit(enactor, 'You have no mentor to graduate from.')
else:
    del_attr(me, 'mentor_of_' + enactor.id)
    set_attr(me, 'mentees_' + mid, [x for x in V('mentees_' + mid, []) if x != enactor.id])
    pemit(get('#' + mid), f'{name(enactor)} has graduated from your mentorship.')
    pemit(enactor, 'You have graduated. Good luck out there!')
'''
```

**Presence.** The connect hook does three things in order: it refreshes the
roster with the arriving player at the end, it pings that player's mentor if
the mentor was already on, and it greets a mentor with a count of their
mentees who are on. `roster` deliberately holds the list *without* the arriving
player, so both membership tests read cleanly.

```text
@set the Mentor Guild/on_connect = '''
# No target guard here: a connect targets the ROOM, so this is a global
# witness. enactor is the player who just connected.
roster = [i for i in V('online', []) if i != enactor.id]
set_attr(me, 'online', roster + [enactor.id])
mid = V('mentor_of_' + enactor.id)
if mid and mid in roster:
    pemit(get('#' + mid), f'Your mentee {name(enactor)} just logged in.')
mine = V('mentees_' + enactor.id, [])
if mine:
    pemit(enactor, f'Mentees online right now: {len([k for k in mine if k in roster])} of {len(mine)}.')
'''
```

Leaving is one statement, so it stays a one-liner:

```text
@set the Mentor Guild/on_disconnect = set_attr(me, 'online', [i for i in V('online', []) if i != enactor.id])
```

## Try it

Staff flag Vala a veteran and she volunteers. Bob, brand new, asks for a match
and both sides hear about it:

```text
> @tag Vala = veteran
Added tag 'veteran' to Vala.

(Vala) > mentor signup
You are now a mentor. New players may be matched with you.

(Bob) > mentor request
You are matched with mentor Vala. Say hello!
   (to Vala) Bob has been matched to you as a new mentee.

(Vala) > mentor
You have no mentor. MENTOR REQUEST to be matched.
Your mentees: Bob
```

Now presence. Order matters, because the ping to a mentor only fires when the
mentor is already on the roster. Vala logs in first and hears her own count,
then Bob logs in and Vala is told:

```text
(Vala connects)
   (to Vala) Mentees online right now: 0 of 1.

(Bob connects)
   (to Vala) Your mentee Bob just logged in.
```

Cass, who has neither a mentor nor mentees, connects in the same room and sees
nothing from the guild, which is the global witness filtering on `enactor`
doing its job. Add a second veteran and the load sort shows itself: a third
newcomer goes to whichever volunteer currently has fewer mentees rather than
piling onto Vala. When Bob outgrows the program he types `mentor graduate`,
Vala is told, and her list frees up for the next arrival:

```text
(Bob) > mentor graduate
You have graduated. Good luck out there!
   (to Vala) Bob has graduated from your mentorship.
```

## Going further

- **Auto-veteran.** Grant the `veteran` tag on a playtime or level milestone
  from another master, so the pool refills itself as players mature.
- **Mentor rewards.** Pay a small stipend on graduation with
  [`transfer_credits`](../reference/softcode.md#fn-transfer_credits) from a
  funded guild purse, following the [job board](094_job_board.md) wage pattern.
- **Newbie channel.** Pair this with a
  [custom channel](074_custom_channel.md) that only mentors and current mentees
  may join, so beginner questions have a home.
- **Match by interest.** Stamp mentors with focus tags such as `combat` or
  `crafting` and let `mentor request <topic>` narrow the pool before the
  load sort runs.

**Engine gaps:** audit gap G4 (presence and session surface). The `online`
roster here exists only because softcode has no `online_players()` function;
the day one ships, both hooks shrink to a single live read and logins outside
`zone:world` stop being invisible.
