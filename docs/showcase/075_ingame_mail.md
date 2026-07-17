# 075. In-game mail

> Checklist item 75 — [now] — *post-office master, per-player ledgers, CC, attachment escrow, ON_CONNECT notice*

**What you'll build:** A Postmaster who runs persistent mail:
`send <names> = <message>` posts a letter (comma-separated names CC
extra recipients), `mail` lists your inbox, `mail <n>` reads one,
`give` the Postmaster an item before you send and it rides along as an
attachment your recipient can `claim` — and the postal wire tells you
about waiting letters the moment you connect.

**Concepts:** per-player **ledger attributes** on an admin-owned
master (`mail_<id>` = list of letters), attachment **escrow** via
`give` + `ON_RECEIVE` and redemption via `teleport_obj` out of the
master's hands, multi-capture `$`-patterns (`$send * = *`), and
`ON_CONNECT` heard by a **world-zone master**.

## How it works

**Mail is a ledger, not an object.** Each letter is a row —
`[sender, body, attachment_ids, to_line]` — appended to a `mail_<id>`
attribute on the Postmaster, one list per recipient. Attributes are
persistent, so mail survives reboots; and because the rows live on
the *master*, one authority owns every mailbox — the same owner-
authority convention as the [coat check](022_coat_check.md) and the
[bank](087_bank_accounts.md). CC is just more rows: `send zeke,kess =
...` appends the same letter to both ledgers, each copy carrying the
full address line so everyone can see who else got it.

**Attachments are escrow, in two moves.** Event hooks carry no
payload, so `give parcel to Postmaster` can't say "this is for Zeke".
Instead the `ON_RECEIVE` hook stamps whatever just arrived with
`escrow = <giver's id>` (the new arrival is whatever in `contents(me)`
isn't stamped yet — the contents-diff idiom from item 22), and your
next `send` sweeps everything stamped with *your* id into the letter.
On redemption, `claim <n>` teleports the items out of the master to
you — legal because anything standing *inside* the master is the
master's to relocate — and blanks the row's attachment list so a
second claim finds nothing. Stamps are set to `''` rather than
deleted when consumed, so already-delivered parcels never look "new"
to the receive hook again. One honest corner: objects can't be
duplicated, so on a CC'd letter the parcels ride with the *first*
recipient only; the copies say so by carrying an empty list.

**"You have mail" is a witnessed event.** When a player connects, the
engine propagates `event:connect` from their location — the room, its
contents, and its **zone masters** witness it. The Postmaster is a
world-zone master, so it hears logins anywhere a room is tagged
`zone:world` and pemits the count. (A login room outside the zone is
silent — the world-zone workaround's standing boundary; note it.)

**Why `$send * = *` is safe.** `send` collides with no builtin (and
no builtin *starts with* `send` — the dispatcher's prefix matching
would win otherwise), and the two wildcards anchor on ` = `, the same
shape as `@set`'s own grammar.

## Build it

The post office and a street, both on the world zone:

```text
@dig The Post Office = post, out
post
@zone here = world
@dig The Promenade = walk, post
walk
@zone here = world
post
```

The Postmaster — an `npc` (so the stock `give` finds it) promoted to
world-zone master:

```text
@create Postmaster
@tag Postmaster = npc
drop Postmaster
@desc Postmaster = A clerk of brass and patience behind a grille. SEND <names> = <message> posts a letter (commas CC extras); MAIL lists yours; MAIL <n> reads one; CLAIM <n> collects parcels. GIVE it an item first to attach it.
@zone/master Postmaster = world
```

The escrow hook — stamp whatever just arrived:

```text
@set Postmaster/on_receive = new = [o for o in contents(me) if not has_attr(o, 'escrow')]; [(set_attr(o, 'escrow', enactor.id), pemit(enactor, 'The clerk tags your ' + name(o) + ': it will ride along with your next SEND.')) for o in new]
```

Sending — resolve every name, refuse the lot if any is wrong,
attach your pending escrow to the first recipient:

```text
@set Postmaster/cmd_send = $send * = *: names = [trim(n) for n in trim(arg0).split(',') if trim(n)]; rcpts = [get(n) for n in names]; ok = [p for p in rcpts if p and has_tag(p, 'player')]; parcels = [o for o in contents(me) if get_attr(o, 'escrow') == enactor.id]; (pemit(enactor, 'The clerk taps the address line: no such citizen on the rolls.') if len(ok) < len(names) or not ok else ([set_attr(me, 'mail_' + p.id, (get_attr(me, 'mail_' + p.id) or []) + [[name(enactor), escape(trim(arg1)), [o.id for o in parcels] if p is ok[0] else [], escape(trim(arg0))]]) for p in ok], [set_attr(o, 'escrow', '') for o in parcels], [pemit(p, 'The postal wire clicks: a letter from ' + name(enactor) + ' has arrived for you.') for p in ok], pemit(enactor, 'The clerk stamps the letter for ' + str(len(ok)) + ' recipient(s)' + (' with ' + str(len(parcels)) + ' parcel(s) attached' if parcels else '') + '.')))
```

Reading — `mail` lists, `mail <n>` opens (two patterns on one object:
the bare `$mail` never matches a numbered line, so they can't fight):

```text
@set Postmaster/cmd_mail = $mail: rows = get_attr(me, 'mail_' + enactor.id) or []; pemit(enactor, 'The clerk checks the pigeonholes: nothing for you.') if not rows else [pemit(enactor, str(i + 1) + '. From ' + r[0] + ' (to ' + r[3] + ')' + (' [' + str(len(r[2])) + ' parcel(s)]' if r[2] else '')) for i, r in enumerate(rows)]
@set Postmaster/cmd_mailn = $mail *: rows = get_attr(me, 'mail_' + enactor.id) or []; k = int(trim(arg0)) if trim(arg0).isdigit() else 0; pemit(enactor, 'No letter numbered ' + trim(arg0) + '.') if not (1 <= k <= len(rows)) else (pemit(enactor, 'From ' + rows[k-1][0] + ', to ' + rows[k-1][3] + ':'), pemit(enactor, '  ' + rows[k-1][1]), (pemit(enactor, str(len(rows[k-1][2])) + ' parcel(s) wait behind the grille. CLAIM ' + str(k) + ' collects them.') if rows[k-1][2] else None))
```

Claiming — verify the parcels are still in the master's hands, hand
them over, blank the row:

```text
@set Postmaster/cmd_claim = $claim *: rows = get_attr(me, 'mail_' + enactor.id) or []; k = int(trim(arg0)) if trim(arg0).isdigit() else 0; items = [get('#' + str(i)) for i in (rows[k-1][2] if 1 <= k <= len(rows) else [])]; live = [o for o in items if o and loc(o) == me]; (pemit(enactor, 'The clerk turns up empty palms: nothing to collect under that number.') if not live else ([teleport_obj(o, enactor) for o in live], set_attr(me, 'mail_' + enactor.id, [r if j != k - 1 else [r[0], r[1], [], r[3]] for j, r in enumerate(rows)]), pemit(enactor, 'The clerk slides ' + str(len(live)) + ' parcel(s) under the grille.')))
```

And the login notice:

```text
@set Postmaster/on_connect = n = len(get_attr(me, 'mail_' + enactor.id) or []); pemit(enactor, 'The postal wire hums: ' + str(n) + ' letter(s) wait for you at the Post Office.') if n else None
```

## Try it

As Bilda, with Zeke and Kess somewhere on the world zone:

```text
give brass compass to Postmaster
   -> The clerk tags your brass compass: it will ride along with your next SEND.
send zeke,kess = The dig starts at dawn. Compass attached for the lead cart.
   -> The clerk stamps the letter for 2 recipient(s) with 1 parcel(s) attached.
```

Zeke (anywhere on the zone) hears the wire click immediately; later:

```text
(Zeke) mail        -> 1. From Bilda (to zeke,kess) [1 parcel(s)]
(Zeke) mail 1      -> From Bilda, to zeke,kess: ... CLAIM 1 collects them.
(Zeke) claim 1     -> The clerk slides 1 parcel(s) under the grille.
(Zeke) claim 1     -> The clerk turns up empty palms: ...
```

Kess's copy reads the same but carries no parcels — one compass
exists, and the address line tells her who has it. Log out and back
in with unread mail and the wire hums at you. And `send nobody = hi`
bounces whole: the clerk refuses a letter with any bad address.

## Going further

- **Deleting mail** — a `$burn <n>` that drops the row (attachments
  first — decide whether unclaimed parcels return to sender or go to
  the [incinerator](019_trash_incinerator.md)).
- **Postage** — an `ON_PAYMENT` gate and a `paid_<id>` ledger: two
  credits a letter, five with a parcel (the
  [vending machine](002_vending_machine.md) idiom).
- **Return to sender** — stamp rows with `now()`; a slow ticker
  sweeps letters older than a month back onto the sender's ledger.
- **Branch offices** — the ledgers live on one master, so a second
  counter in another town is just another zone room; the pigeonholes
  are everywhere the zone is.
