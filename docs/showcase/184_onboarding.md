# 184. New-player onboarding

> Checklist item 184 — [now] — *world-master ON_CONNECT, first-login flag, starter kit via create_obj, mentor ping*

**What you'll build:** a `Greeter` that welcomes each new character the
first time they connect — a greeting, a starter kit (a datapad and 100
credits) dropped straight into their hands, and a quiet ping to every
mentor on duty — and never repeats itself.

**Concepts:** a **world-master `ON_CONNECT`** witnessing every login (the
[roster idiom from 083](083_message_in_bottle.md)), a **first-login
flag** so the kit is granted once, `create_obj()` + `adjust_credits()`
into a player's inventory (admin authority), and a **mentor fan-out** via
`search_world()` + `pemit()`.

## How it works

**One master hears every login.** The Greeter is master of the
`zone:world`, so `event:connect` from any world room reaches its
`on_connect`. Same plumbing as the [staff dashboard](176_staff_dashboard.md)
roster and the message-in-a-bottle Harbormaster — connection events
propagate to the zone's master.

**"First login" is an attr, not a guess.** The kit must not re-drop every
reconnect, so the hook keys off `get_attr(enactor, 'oriented')`: absent
means new, and the first thing the hook does is stamp it with `now()`.
Every later connect finds the stamp and does nothing. (Because the flag is
a persistent attribute, it survives reboots — a returning veteran is never
re-onboarded.)

**The kit needs admin authority.** Crediting and creating objects *in
another player's inventory* means mutating them — ADMIN territory. So the
Greeter is admin-owned; `adjust_credits(enactor, 100)` and
`create_obj('a welcome datapad', ['thing'], enactor)` both act with its
owner's authority (the staff-tool boundary from the
[permission tour](183_permission_tiers.md)). The greeting itself is a
plain `pemit` — no authority needed to speak to someone.

**Mentors are a tag.** Any character tagged `mentor` is on the welcome
wagon; `search_world(tag='mentor')` (minus the newcomer themselves) gets
the ping. Tag and untag mentors live — the roster is always current.

## Build it

An orientation bay on the world zone and the Greeter as its master:

```text
@dig The Orientation Bay = obay, out
obay
@zone here = world
@create Greeter
drop Greeter
@desc Greeter = A cheerful welcome-bot bolted by the airlock.
@zone/master Greeter = world
```

The whole onboarding is one first-login hook — kit, greeting, mentor
ping, guarded by the `oriented` flag:

```text
@set Greeter/on_connect = mentors = [m for m in search_world(tag='mentor') if m != enactor]; (set_attr(enactor,'oriented', now()), adjust_credits(enactor, 100), create_obj('a welcome datapad', ['thing'], enactor), pemit(enactor, 'Welcome aboard, ' + name(enactor) + '! Your kit holds a datapad and 100 credits. Type HELP anytime.'), [pemit(m, ansi('c','[mentor] ') + 'New arrival: ' + name(enactor) + ' — say hello.') for m in mentors]) if not get_attr(enactor,'oriented') else None
```

Deputize a mentor by tag:

```text
@tag Mira = mentor
```

## Try it

A new character connects in a world room for the first time:

```text
(Newbie connects)
   (Newbie) Welcome aboard, Newbie! Your kit holds a datapad and 100 credits. Type HELP anytime.
   (Mira)   |C[mentor]|n New arrival: Newbie — say hello.
```

Newbie now holds *a welcome datapad* and has 100 credits, and carries the
`oriented` stamp. Reconnecting changes nothing — no second greeting, no
second datapad, no doubled credits: the kit is a one-time gift. A
character who was already oriented (a returning veteran) triggers the hook
and silently falls through.

## Going further

- **A richer kit** — loop a prototype list, `create_obj` each: a
  datapad, a comm badge, a map. Or `@clone` a pre-built "starter crate"
  into their hands.
- **Route to a tutorial** — `teleport_obj(enactor, 'The Tutorial Deck')`
  on first login, or drop them into a private
  [instance](044_instanced_room.md) so first steps are undisturbed.
- **Pair, don't just ping** — auto-assign a mentor by writing
  `set_attr(enactor, 'mentor', mentors[0].id)` and let a `$mentor` verb
  connect them (the mentor-program idiom, item 226).
- **Compose with approval** — tag the newcomer `unapproved` here so the
  [approval gate](179_approval_queue.md) holds them until a staffer
  clears them; onboarding and approval are two halves of arrival.
- **Login streaks** — the same `ON_CONNECT` + date-math pattern rewards
  *returning* players (item 229); onboarding is the day-one case of it.
