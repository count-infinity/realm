# 179. Character approval queue

> Checklist item 179 — [now] — *workflow states as tags, tag-gated start-room exit, staff decision with notify, admin authority over new characters*

**What you'll build:** an arrivals gate. New characters wait in the
Arrivals Lounge, unable to reach the Concourse until a staffer clears
them: `pending` lists who's waiting, `approve <name>` opens the door and
welcomes them, `reject <name> = <reason>` sends the note back and keeps
them pending.

**Concepts:** **workflow states as tags** (`unapproved` →
`approved`), a **tag-gated exit lock** as the gate, a **world-zone master
desk** with staff-gated verbs, `search_world()` as the queue query, and
`pemit()` notification on every decision — built with **admin authority**
because approval mutates other players' tags.

## How it works

**REALM ships character creation but not an approval gate — so you build
one.** There is no native "unapproved" state in the engine; that's a
policy your game chooses. The whole workflow is one tag on the character
and one lock on the way out. New characters arrive tagged `unapproved`
(your chargen or [onboarding](184_onboarding.md) step stamps it — or a
world-master `ON_CONNECT` does); this tutorial builds the gate and the
staff tools around that tag.

**The gate is the start room's exit.** The exit from the Arrivals Lounge
to the Concourse carries `basic` lock `not caller.has_tag('unapproved')`.
The engine's movement gate refuses anyone still tagged — the same native
enforcement the [jail](177_jail_system.md) cell wall uses — so an
unapproved character is held without any per-tick babysitting.

**The desk needs admin authority.** Clearing a character means removing a
tag *from another player*; only an ADMIN (or the owner) may. So the
Approvals Desk is admin-owned — its scripts act with staff authority, the
honest boundary the [permission tour](183_permission_tiers.md) draws.
`approve` swaps `unapproved` for `approved` and pemits the newcomer;
`reject` leaves them pending and pemits the reason. Notification is
best-effort: if the character is offline the tag change still persists, so
the gate simply opens the next time they walk it.

**The queue is a query.** `pending` is just `search_world(tag=
'unapproved')` — no separate list to keep in sync.

## Build it

An arrivals room on the world zone and a locked door onward:

```text
@dig The Arrivals Lounge = arrivals, out
arrivals
@zone here = world
@dig The Concourse = concourse, back
@lock concourse = not caller.has_tag('unapproved')
```

The desk, admin-owned and crowned world master so `pending`/`approve`/
`reject` answer from anywhere:

```text
@create Approvals Desk
drop Approvals Desk
@desc Approvals Desk = A clerk's window for new citizens. PENDING, APPROVE <name>, REJECT <name> = <reason>.
@zone/master Approvals Desk = world
```

The three staff verbs (note `pending`, not `queue` — `queue` is a builtin
and builtins win the dispatch):

```text
@set Approvals Desk/cmd_pending = $pending: q = search_world(tag='unapproved'); (pemit(enactor,'Only staff may review arrivals.') if not has_tag(enactor,'admin') else (pemit(enactor,'The approval queue is empty.') if not q else [pemit(enactor,'- ' + name(p) + ' (#' + str(p.id)[:8] + ')') for p in q]))
@set Approvals Desk/cmd_approve = $approve *: p = get(trim(arg0)); (pemit(enactor,'Only staff may clear arrivals.') if not has_tag(enactor,'admin') else (pemit(enactor, trim(arg0) + ' is not awaiting approval.') if not (p and has_tag(p,'unapproved')) else (remove_tag(p,'unapproved'), add_tag(p,'approved'), pemit(p,'Your character has been approved. Welcome aboard — the concourse is open to you.'), set_attr(me,'log', ((get_attr(me,'log') or []) + [name(enactor) + ' approved ' + name(p)])[-50:]), pemit(enactor,'Approved ' + name(p) + '.'))))
@set Approvals Desk/cmd_reject = $reject * = *: p = get(trim(arg0)); (pemit(enactor,'Only staff may clear arrivals.') if not has_tag(enactor,'admin') else (pemit(enactor, trim(arg0) + ' is not awaiting approval.') if not (p and has_tag(p,'unapproved')) else (pemit(p,'Your character needs work before approval: ' + escape(trim(arg1))), set_attr(me,'log', ((get_attr(me,'log') or []) + [name(enactor) + ' bounced ' + name(p) + ': ' + trim(arg1)])[-50:]), pemit(enactor,'Sent ' + name(p) + ' back with notes.'))))
```

## Try it

A newcomer arrives tagged `unapproved` (here we set it by hand to stand in
for the chargen step) and finds the door shut:

```text
@tag Newbie = unapproved
(Newbie) concourse
   -> You can't go concourse — it's locked.
```

A staffer reviews and clears them:

```text
pending
   -> - Newbie (#a1b2c3d4)
approve Newbie
   -> Approved Newbie.
   (Newbie) Your character has been approved. Welcome aboard — the concourse is open to you.

(Newbie) concourse
   -> The Concourse
```

Rejection notifies but holds the gate:

```text
reject Rowdy = name violates the setting; pick another
   -> Sent Rowdy back with notes.
   (Rowdy) Your character needs work before approval: name violates the setting; pick another
```

A non-staff arrival who tries `approve Newbie` is refused — `Only staff
may clear arrivals.` — so newcomers can't wave themselves through.

## Going further

- **Auto-tag on arrival** — a world-master `ON_CONNECT` that tags any
  character with no `approved` attr `unapproved`, so the gate is
  automatic (compose with [onboarding](184_onboarding.md), which already
  fires on first connect).
- **Reasons on file** — stash the reject note on the character
  (`set_attr(p, 'review_note', ...)`) so it shows at their next login,
  not just once.
- **A holding channel** — give the Arrivals Lounge a `$page staff` verb
  that `pemit`s the on-duty admins (see the
  [watchlist](186_watchlist.md) staff-fan-out idiom) so approvals happen
  live.
- **Multi-step review** — add an `under_review` tag between `unapproved`
  and `approved` for a two-pass workflow; the states are just tags, so
  add as many as your process needs.
