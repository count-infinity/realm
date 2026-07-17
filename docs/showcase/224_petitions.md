# 224. Petition / ticket system

> Checklist item 224 — [now] — *request ledger attrs, staff queue, claim/resolve flow, filer notifications, connect nudge*

**What you'll build:** a Requests Desk where any player files a petition —
`petition The airlock on Deck 3 is stuck` — that drops into a staff queue.
Staff `claim` a ticket, `resolve` it with a note, and the filer is pinged
wherever they are. Staff logging in get a nudge about the open backlog.

**Concepts:** requests as a **ledger of ticket attributes** (`ticket_<n>`
dicts) on a world-zone master — the [coat check](022_coat_check.md) /
[job board](094_job_board.md) ledger shape; a **staff queue** gated by an
`admin`-tag check; a **claim → resolve** lifecycle; `pemit`
**notifications** to the filer across the map; and a connect nudge, the
[mail](075_ingame_mail.md) desk's "you have waiting items" pattern.

## How it works

**A ticket is one dict, a queue is a numbered run of them.** Each petition
becomes `ticket_<n> = {by, by_name, text, status, claimed_by,
claimed_name, note}`, with a `next_ticket` counter — the same lot
bookkeeping the [auction house](089_auction_house.md) and job board use.
`status` walks `open → claimed → closed`; the other fields carry who filed
it, who's handling it, and the resolution. Nothing is ever renumbered, so
a ticket id is a stable reference a player and a staffer can both name.

**Two audiences, one ledger.** `petitions` shows a player *their own*
tickets; the same verb shows a staffer *everything*. The split is a single
`has_tag(enactor, 'admin')` read — the honest staff boundary this showcase
uses wherever a queue needs a privileged side (the
[titles Herald](220_titles_badges.md) award gate, the same shape). Filing
is open to any player; claiming and resolving are staff-only.

**The desk reaches the filer anywhere.** Because `pemit` delivers by id,
not by room, resolving a ticket pings the filer whether they're standing
at the desk, across the station, or (as a queued line they'll read next
time) about to be. And because the desk is a **world-zone master**, the
`petition` and `petitions` verbs work from any world room, and its
`ON_CONNECT` can nudge staff about the backlog at login.

## Build it

A world-zone lobby and the desk (admin-owned so `pemit` reaches players
everywhere and the staff gate has real teeth):

```text
@dig The Requests Lobby = lobby, out
lobby
@zone here = world
@create the Requests Desk
drop the Requests Desk
@desc the Requests Desk = A service window with a call bell. PETITION <request> files one; PETITIONS lists yours. Staff: CLAIM <n>, RESOLVE <n> = <note>.
@zone/master the Requests Desk = world
```

`petition <text>` — file a ticket, confirm, and (going further) alert staff:

```text
@set the Requests Desk/cmd_petition = $petition *:txt = trim(arg0); ok = has_tag(enactor, 'player') and bool(txt); [(set_attr(me, 'ticket_' + str(n), {'by': enactor.id, 'by_name': name(enactor), 'text': escape(t), 'status': 'open', 'claimed_by': '', 'claimed_name': '', 'note': ''}), set_attr(me, 'next_ticket', n + 1), pemit(enactor, f'Filed request #{n}. Staff will review it.')) for g, t in [[ok, txt]] if g for n in [V('next_ticket', 1)]]; pemit(enactor, 'Type PETITION <your request>.') if not ok else None
```

`petitions` — the queue, filtered by who's asking:

```text
@set the Requests Desk/cmd_petitions = $petitions:rows = [[i, V('ticket_' + str(i))] for i in range(1, V('next_ticket', 1)) if V('ticket_' + str(i))]; mine = [r for r in rows if has_tag(enactor, 'admin') or r[1]['by'] == enactor.id]; pemit(enactor, 'Requests queue:' if mine else 'No requests on file for you.'); [pemit(enactor, f'  #{r[0]} [{r[1]["status"]}] {r[1]["by_name"]}: {r[1]["text"]}' + ((' - handling: ' + r[1]['claimed_name']) if r[1]['claimed_by'] else '') + ((' -> ' + r[1]['note']) if r[1]['note'] else '')) for r in mine]
```

`claim <n>` and `resolve <n> = <note>` — the staff side, each pinging the
filer:

```text
@set the Requests Desk/cmd_claim = $claim *:n = trim(arg0); t = V('ticket_' + n); ok = has_tag(enactor, 'admin') and bool(t) and t['status'] == 'open'; [(set_attr(me, 'ticket_' + n, dict(x, status='claimed', claimed_by=enactor.id, claimed_name=name(enactor))), pemit(enactor, 'You claim request #' + n + '.'), pemit(get('#' + str(x['by'])), name(enactor) + ' is now handling your request #' + n + '.')) for g, x in [[ok, t]] if g]; pemit(enactor, 'No such open request, or you are not staff.') if not ok else None
@set the Requests Desk/cmd_resolve = $resolve * = *:n = trim(arg0); note = trim(arg1); t = V('ticket_' + n); ok = has_tag(enactor, 'admin') and bool(t) and t['status'] != 'closed'; [(set_attr(me, 'ticket_' + n, dict(x, status='closed', note=escape(nt), claimed_by=enactor.id, claimed_name=name(enactor))), pemit(enactor, 'Resolved request #' + n + '.'), pemit(get('#' + str(x['by'])), 'Your request #' + n + ' was resolved by ' + name(enactor) + ': ' + escape(nt))) for g, x, nt in [[ok, t, note]] if g]; pemit(enactor, 'No such open request, or you are not staff.') if not ok else None
```

The connect nudge — staff hear the backlog at login:

```text
@set the Requests Desk/on_connect = openn = len([1 for i in range(1, V('next_ticket', 1)) if V('ticket_' + str(i)) and V('ticket_' + str(i))['status'] == 'open']); pemit(enactor, 'Requests desk: ' + str(openn) + ' open request(s) awaiting staff.') if has_tag(enactor, 'admin') and openn else None
```

## Try it

Bob files two petitions and reviews his own:

```text
(Bob) petition The airlock on Deck 3 is stuck.
   -> Filed request #1. Staff will review it.
(Bob) petition Requesting a name change to Robert.
   -> Filed request #2. Staff will review it.
(Bob) petitions
   Requests queue:
     #1 [open] Bob: The airlock on Deck 3 is stuck.
     #2 [open] Bob: Requesting a name change to Robert.
```

Staff see the whole queue, claim one, and resolve it — Bob hears the
result from wherever he is:

```text
(Vala) petitions        -> the same two tickets, from every filer
(Vala) claim 1          -> You claim request #1.
(to Bob)                -> Vala is now handling your request #1.
(Vala) resolve 1 = Maintenance dispatched; cycle the manual override.
(to Bob)                -> Your request #1 was resolved by Vala: Maintenance dispatched; cycle the manual override.
```

A non-staff `claim 1` answers "you are not staff"; and when Vala next logs
in with tickets still open, the desk nudges her: "Requests desk: 1 open
request(s) awaiting staff."

## Going further

- **Categories & routing** — a `petition bug: <text>` form that stamps a
  `cat` field, and per-category staff rosters so `petitions bugs` filters
  the queue for the team that owns it.
- **Reopen** — a filer `$reopen <n>` that flips a closed ticket back to
  open with a follow-up note, so a bad fix doesn't vanish.
- **Escrowed evidence** — `give` the desk an item first and attach it to
  the next petition (the [mail](075_ingame_mail.md) parcel trick), so a
  bug report can carry the broken object.
- **SLA sweep** — a `script_ticker` that flags any `open` ticket older
  than an hour and re-pings staff, turning the queue into a real backlog
  monitor (the [job board](094_job_board.md) deadline variant).
```
