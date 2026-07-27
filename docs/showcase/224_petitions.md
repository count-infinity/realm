# 224. Petition / ticket system

> Checklist item 224 ([now]): *ticket-queue attrs, $claim/$resolve, pemit notifications*

**What you'll build:** a Requests Desk where any player files a petition with
`petition The airlock on Deck 3 is stuck`, dropping it into a staff queue. Staff
`claim` a ticket, `resolve` it with a note, and the filer is pinged wherever on
the map they happen to be standing. Staff who log in while work is outstanding
hear how big the backlog is.

**Concepts:** a numbered ledger of ticket attributes (`ticket_<n>` dicts) on a
world-zone master, the same shape the
[job board](094_job_board.md) and [auction house](089_auction_house.md) use for
their postings and lots; a staff side gated by
[`has_tag(enactor, 'admin')`](../reference/softcode.md#fn-has_tag); a claim and
resolve lifecycle; [`pemit`](../reference/softcode.md#fn-pemit) notifications
that reach the filer in any room; and an
[`ON_CONNECT`](../reference/softcode.md#lifecycle-hooks) nudge in the style of
the [mail desk](075_ingame_mail.md)'s waiting-letters notice.

## How it works

The finished desk is a single object holding one attribute per request, plus a
counter naming the next free number. Four verbs read and write that ledger:
`petition` appends a row, `petitions` prints the rows you are allowed to see,
`claim` stamps your name on a row, and `resolve` closes it with a note. This
section answers four questions: what a ticket actually is, how one verb serves
both players and staff, how the desk reaches a filer who has walked away, and
why the login nudge takes no `target` guard.

### What a ticket is

Each petition becomes an attribute named `ticket_<n>` whose value is a dict of
`by`, `by_name`, `text`, `status`, `claimed_by`, `claimed_name`, and `note`, and
a `next_ticket` counter says which number the following petition gets. `status`
runs `open` to `claimed` to `closed`, though `resolve` accepts an open ticket
directly, so a staffer who fixes something on the spot may skip the claim.
Nothing is ever deleted or renumbered, which is what makes a ticket id a stable
reference that a player and a staffer can both name out loud; a closed row stays
in the ledger and keeps showing in its filer's own listing with the resolution
attached.

The filer's text is stored through
[`escape`](../reference/softcode.md#fn-escape), which doubles the color markup
marker so that a request written as `The |rairlock|n is stuck` is stored as
`The ||rairlock||n is stuck` and reaches the reader as those literal characters.
Player-supplied text passes through the desk's listing to other people's
screens, so escaping it is what keeps a filer from coloring the staff queue.
The resolution note gets the same treatment, because a staffer typing a note is
supplying text to the filer's screen.

### How one verb serves two audiences

`petitions` shows a player their own tickets, and the identical verb shows a
staffer the whole queue. The entire split is one
[`has_tag(enactor, 'admin')`](../reference/softcode.md#fn-has_tag) read, which
either widens the row filter to everything or narrows it to rows whose `by`
field matches the asker's id. Filing stays open to anyone tagged `player`, while
`claim` and `resolve` check the `admin` tag before touching a row. That is the
same honest staff boundary the [titles Herald](220_titles_badges.md) puts on its
award verb.

The tag is read off `enactor`, so it is independent of who owns the desk.
Ownership decides who may edit the desk's scripts later;
[`pemit`](../reference/softcode.md#fn-pemit) and
[`get`](../reference/softcode.md#fn-get) need no authority at all, and
[`set_attr`](../reference/softcode.md#fn-set_attr) writes to `me` because a
script runs as its own object, with that object's owner's authority, and an
object always controls itself. Build the desk as staff so that staff keep
control of it.

### How the desk reaches a filer who walked away

The ticket row stores the filer's raw id, so `claim` and `resolve` recover the
player with [`get('#' + str(t['by']))`](../reference/softcode.md#fn-get), the
exact raw-id form, and `pemit` that object directly. Delivery is by object, not
by room, so the filer hears the result standing at the desk or three decks away.
A filer who has logged out simply misses the line, because `pemit` reaches a
live session and nothing else; the row itself is unharmed, so the resolution is
waiting in their next `petitions` listing. If you want a delivery that survives a
logout the way a letter does, put the notice in a per-player list attribute and
read it back on connect, which is what the [mail desk](075_ingame_mail.md) does.

Both of those verbs, and `petition` itself, work from anywhere in the world zone
rather than only at the counter, because the desk is a **world-zone master**:
REALM has no Master Room yet, so an object tagged `zone_master` in a
`zone:world` room is the standing workaround for a global `$`-command. The
trigger search adds the masters of the player's room to the objects it scans, so
a player in any room tagged `zone:world` finds `petition`. A room outside that
zone finds nothing, which is the workaround's standing boundary.

### Why the login nudge takes no target guard

An [`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks) hook fires on every
object in the room, so most of them open with `if target is me:` to tell "this
happened to me" from "this happened near me" (see
[Guard on `target`](../reference/softcode.md#guard-on-target)). A login is the
deliberate exception. `event:connect` carries the *room* as its target and the
arriving player as its actor, so `target is me` is never true on the desk and
that guard would silence the nudge forever. The desk is a global witness here,
watching everyone who arrives, so it reads `enactor` and skips the guard. What it
does check is that the
arriver is staff and that the backlog is non-empty, so an ordinary player logging
in hears nothing. The [friends list](219_friends_list.md) registry and the
[mail desk](075_ingame_mail.md) leave their own `on_connect` hooks unguarded for
the same reason.

## Build it

Start with a lobby on the world zone, since a zone master needs a room carrying
the `zone:world` tag before it can hear anything:

```text
@dig The Requests Lobby = lobby, out
lobby
@zone here = world
```

Now the desk itself, promoted to master of that zone so its verbs reach the
whole world:

```text
@create the Requests Desk
drop the Requests Desk
@desc the Requests Desk = A service window with a call bell. PETITION <request> files one; PETITIONS lists yours. Staff: CLAIM <n>, RESOLVE <n> = <note>.
@zone/master the Requests Desk = world
```

`petition <text>` reads the counter, writes the row, bumps the counter, and
confirms. [`V('next_ticket', 1)`](../reference/softcode.md#fn-v) is shorthand for
`get_attr(me, 'next_ticket', 1)`, and the default of 1 means the very first
petition lands on `ticket_1` without anyone seeding the counter:

```text
@set the Requests Desk/cmd_petition = '''
$petition *:
txt = trim(arg0)
if not (has_tag(enactor, 'player') and txt):
    pemit(enactor, 'Type PETITION <your request>.')
else:
    n = V('next_ticket', 1)
    set_attr(me, 'ticket_' + str(n), {'by': enactor.id, 'by_name': name(enactor), 'text': escape(txt), 'status': 'open', 'claimed_by': '', 'claimed_name': '', 'note': ''})
    set_attr(me, 'next_ticket', n + 1)
    pemit(enactor, f'Filed request #{n}. Staff will review it.')
'''
```

[`escape`](../reference/softcode.md#fn-escape) on the filer's text is the line to
keep: the request is replayed onto staff screens, and escaping it means a
petition full of `|r` codes prints as those characters instead of recoloring the
queue. [`trim`](../reference/softcode.md#fn-trim) tidies the capture, and
[`name`](../reference/softcode.md#fn-name) is stored alongside the id so the
listing stays readable even if the filer is offline.

`petitions` walks the numbers from 1 up to the counter, keeps the rows the asker
may see, and prints them. The `admin` read happens once, before the loop, so the
staff test costs one call rather than one per row:

```text
@set the Requests Desk/cmd_petitions = '''
$petitions:
staff = has_tag(enactor, 'admin')
rows = []
for i in range(1, V('next_ticket', 1)):
    t = V('ticket_' + str(i))
    if t and (staff or t['by'] == enactor.id):
        rows.append([i, t])
if not rows:
    pemit(enactor, 'No requests on file for you.')
else:
    pemit(enactor, 'Requests queue:')
    for i, t in rows:
        line = f'  #{i} [{t["status"]}] {t["by_name"]}: {t["text"]}'
        if t['claimed_by']:
            line = line + ' - handling: ' + t['claimed_name']
        if t['note']:
            line = line + ' -> ' + t['note']
        pemit(enactor, line)
'''
```

`claim <n>` is the first staff verb. It refuses anything that is not an open row
belonging to a real number, stamps the claimant onto a copy of the dict, and
tells the filer who picked the ticket up:

```text
@set the Requests Desk/cmd_claim = '''
$claim *:
n = trim(arg0)
t = V('ticket_' + n)
if not (has_tag(enactor, 'admin') and t and t['status'] == 'open'):
    pemit(enactor, 'No such open request, or you are not staff.')
else:
    # dict(t, ...) rewrites the whole row in one set_attr: one row, one writer
    set_attr(me, 'ticket_' + n, dict(t, status='claimed', claimed_by=enactor.id, claimed_name=name(enactor)))
    pemit(enactor, 'You claim request #' + n + '.')
    pemit(get('#' + str(t['by'])), name(enactor) + ' is now handling your request #' + n + '.')
'''
```

`resolve <n> = <note>` closes the row. It accepts any ticket that is not already
closed, so a staffer may resolve straight from `open`, and it records the
resolver in `claimed_by` so a closed row always names who finished it:

```text
@set the Requests Desk/cmd_resolve = '''
$resolve * = *:
n = trim(arg0)
note = trim(arg1)
t = V('ticket_' + n)
if not (has_tag(enactor, 'admin') and t and t['status'] != 'closed'):
    pemit(enactor, 'No such open request, or you are not staff.')
else:
    set_attr(me, 'ticket_' + n, dict(t, status='closed', note=escape(note), claimed_by=enactor.id, claimed_name=name(enactor)))
    pemit(enactor, 'Resolved request #' + n + '.')
    pemit(get('#' + str(t['by'])), 'Your request #' + n + ' was resolved by ' + name(enactor) + ': ' + escape(note))
'''
```

Finally the login nudge. It counts the open rows and speaks only to an arriving
staffer with a non-empty backlog:

```text
@set the Requests Desk/on_connect = '''
# no target guard: on a connect the target is the ROOM, so this hook deliberately
# witnesses everyone who arrives in the zone
waiting = 0
for i in range(1, V('next_ticket', 1)):
    t = V('ticket_' + str(i))
    if t and t['status'] == 'open':
        waiting = waiting + 1
if has_tag(enactor, 'admin') and waiting:
    pemit(enactor, f'Requests desk: {waiting} open request(s) awaiting staff.')
'''
```

## Try it

Bob files two petitions and reviews his own queue:

```text
> petition The airlock on Deck 3 is stuck.
Filed request #1. Staff will review it.

> petition Requesting a name change to Robert.
Filed request #2. Staff will review it.

> petitions
Requests queue:
  #1 [open] Bob: The airlock on Deck 3 is stuck.
  #2 [open] Bob: Requesting a name change to Robert.
```

Cass, who has filed nothing, gets the empty answer, and a `claim` from her is
refused because the gate is a tag on the asker:

```text
> petitions
No requests on file for you.

> claim 1
No such open request, or you are not staff.
```

Vala is staff, so the same verb shows her every filer's rows. Bob hears each
step wherever he is standing, since `pemit` delivers to the player object rather
than to the desk's room:

```text
> petitions
Requests queue:
  #1 [open] Bob: The airlock on Deck 3 is stuck.
  #2 [open] Bob: Requesting a name change to Robert.

> claim 1
You claim request #1.
        (Bob, anywhere on the station) Vala is now handling your request #1.

> resolve 1 = Maintenance dispatched; cycle the manual override.
Resolved request #1.
        (Bob) Your request #1 was resolved by Vala: Maintenance dispatched; cycle the manual override.
```

The closed row stays on file, so Bob's own listing keeps it with the resolution
attached, and a second `claim 1` is refused because the row is no longer open:

```text
> petitions
Requests queue:
  #1 [closed] Bob: The airlock on Deck 3 is stuck. - handling: Vala -> Maintenance dispatched; cycle the manual override.
  #2 [open] Bob: Requesting a name change to Robert.
```

With ticket 2 still open, Vala's next login inside the world zone greets her
with the backlog, while Bob's login is silent because he is not staff:

```text
Requests desk: 1 open request(s) awaiting staff.
```

Log in from a room that carries no `zone:world` tag and the desk says nothing,
which is the world-zone master's reach showing its edge.

## Going further

- **Categories and routing.** Add a `petition bug: <text>` form that splits the
  leading word into a `cat` field, then let `petitions bugs` filter the queue for
  the team that owns that category.
- **Reopen.** Give filers a `$reopen *` verb that flips a `closed` row back to
  `open` with a follow-up note, so a fix that did not hold stays visible instead
  of vanishing.
- **Evidence attached to a bug report.** Tag the desk `npc` so the stock `give`
  finds it, add an `ON_RECEIVE` hook guarded with `if target is me:` that stamps
  the arriving object with the giver's id, and sweep those stamped objects into
  the next petition. That is the [mail desk](075_ingame_mail.md)'s parcel escrow
  applied to a broken airlock panel.
- **Backlog sweep.** Attach the `script_ticker` behavior and give the desk an
  `on_tick` that re-pings staff about any `open` row whose age passes a
  threshold, turning the queue into a monitored backlog. The
  [auction house](089_auction_house.md) drives its lot settlement off exactly
  that pattern, an `on_tick` sweeping the numbered rows and acting on the ones
  whose deadline has passed.
