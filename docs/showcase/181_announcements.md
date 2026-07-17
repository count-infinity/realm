# 181. Announcement system

> Checklist item 181 — [now] — *server-wide pemit fan-out, per-player opt-out, persistent history, contrast with zone remit (078) and act countdown (056)*

**What you'll build:** a `Announcer` mic that pushes a formatted notice to
**every character on the grid** — `announce <message>` — keeps a history
players can replay with `news`, and honors a per-player opt-out
(`mute news` / `unmute news`).

**Concepts:** **server-wide fan-out with `pemit()` per player** (so
opt-out can filter it — the reason it isn't a `remit` loop), a persistent
**history** attr, tag-based **opt-out**, staff gating, and the deliberate
contrast with the two broadcast idioms you've already met.

## How it works

**Why `pemit` per player, not `remit` per room.** The
[station PA](078_pa_system.md) uses `remit()` over `zone_rooms()`: fast,
unstoppable, and *unfilterable* — everyone in the room hears it, no
exceptions. That's perfect for a ceiling speaker but wrong for a
server-wide notice with an opt-out, because `remit` can't skip an
individual listener. So the announcer loops **players**, not rooms —
`search_world(tag='player')` — and `pemit`s each one, skipping anybody
tagged `no_announce`. The cost is one message per player instead of one
per room; the payoff is per-person control. (For a *resistible* broadcast
— one a soundproof room or a ward can veto — you'd reach for
`act(..., targeting='zone')`, the alarm idiom from the
[self-destruct sequence](056_self_destruct.md). An announcement isn't
resistible; it's just opt-out-able.)

**Server-wide means every player, wherever they stand.** Because delivery
is by id, a character off in Limbo — nowhere near the booth, in no zone —
still hears it. That's the difference from the zone-scoped PA: the PA
reaches a *place*; the announcer reaches *people*.

**History is a capped list.** Every notice is appended to `history`
(trimmed to the last 30) before delivery, so `news` replays what a
muted — or just-logged-in — player missed. Muting suppresses *live*
delivery only; history always has the full record.

**Staff-owned and staff-gated.** Broadcasting is owner-gated by a tag
check (`has_tag(enactor, 'admin')`); the master is admin-owned so it can
tag players who opt out. Widen the gate to a `staff` tag or a `use` lock
if more than admins should hold the mic.

## Build it

A booth on the world zone and the mic crowned master:

```text
@dig The Broadcast Booth = booth, out
booth
@zone here = world
@create Announcer
drop Announcer
@desc Announcer = A brass microphone wired to every character on the grid.
@zone/master Announcer = world
```

Broadcast (staff), replay, and opt-out:

```text
@set Announcer/cmd_announce = $announce *: (pemit(enactor,'Only staff may broadcast.') if not has_tag(enactor,'admin') else (set_attr(me,'history', ((get_attr(me,'history') or []) + [escape(arg0) + '  --' + name(enactor)])[-30:]), [pemit(p, ansi('yh','[NOTICE] ') + escape(arg0)) for p in search_world(tag='player') if not has_tag(p,'no_announce')], pemit(enactor,'Broadcast sent to all listening players.')))
@set Announcer/cmd_news = $news: h = get_attr(me,'history') or []; pemit(enactor,'No notices on file.') if not h else [pemit(enactor, str(i+1) + '. ' + ln) for i, ln in enumerate(h[-10:])]
@set Announcer/cmd_mute = $mute news: (add_tag(enactor,'no_announce'), pemit(enactor,'You opt out of live notices. NEWS still shows history; UNMUTE NEWS resumes delivery.'))
@set Announcer/cmd_unmute = $unmute news: (remove_tag(enactor,'no_announce'), pemit(enactor,'Live notices resumed.'))
```

## Try it

A staffer broadcasts; a character in the booth and one far away in Limbo
both hear it:

```text
announce Reactor drill at 0300. This is only a drill.
   -> Broadcast sent to all listening players.
   (everyone) |Y[NOTICE]|n Reactor drill at 0300. This is only a drill.
```

Opting out silences the *live* line but not the record:

```text
mute news
   -> You opt out of live notices. NEWS still shows history; UNMUTE NEWS resumes delivery.
(after the next announce, no live line arrives)
news
   -> 1. Reactor drill at 0300. This is only a drill.  --Bob
   -> 2. Second notice, please ignore.  --Bob
```

`unmute news` resumes delivery. A non-staff character who tries to
broadcast gets `Only staff may broadcast.`

## Going further

- **Priorities** — a `$alert <message>` variant in red that *ignores*
  `no_announce` for genuine emergencies; opt-out is a courtesy, not a
  gag on the fire alarm.
- **Timed notices** — a `script_ticker` walking a list of scheduled
  `[hour, text]` rows announces shift changes on their own (the
  [NPC schedule](068_npc_schedule.md) clock idiom).
- **Countdowns** — for a dramatic, abortable sequence (launch in
  10… 9…), chain `wait()`s and let `$abort` `cancel_wait()` — that's the
  [self-destruct](056_self_destruct.md) klaxon, not a one-shot notice.
- **Channels vs. notices** — if you want a *conversation*, not a
  broadcast, that's the subscriber-list
  [custom channel](074_custom_channel.md); an announcement is one-way by
  design.
