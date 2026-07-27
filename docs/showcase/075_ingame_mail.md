# 075. In-game mail

> Checklist item 75 ([now]): *post-office master, per-player ledgers, CC, attachment escrow, ON_CONNECT notice*

**What you'll build:** A Postmaster who runs persistent mail. `send <names> =
<message>` posts a letter (comma-separated names CC extra recipients), `mail`
lists your inbox, and `mail <n>` reads one. `give` the Postmaster an item before
you send and it rides along as an attachment your recipient can `claim`, and the
postal wire tells you about waiting letters the moment you connect.

**Concepts:** per-player **ledger attributes** on an admin-owned master
(`mail_<id>` = list of letters), attachment **escrow** via `give` plus
`ON_RECEIVE` and redemption via
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj) out of the master's
hands, multi-capture `$`-patterns (`$send * = *`), and `ON_CONNECT` heard by a
**world-zone master**.

## How it works

The finished post office is one admin-owned object, the Postmaster, that carries
every mail command and stores one list per recipient. Someone types
`send zeke = ...` from any room on the world zone, a row lands in Zeke's list,
and a login notice surfaces it the next time Zeke connects. This section answers
four questions: where the mail lives, how a handed-over parcel becomes an
attachment, how an offline recipient still gets the letter, and why
`$send * = *` is safe to claim.

### Where the mail lives (a ledger, not an object)

There is no built-in mail system in REALM, so the whole post office is softcode.
Each letter is a row, `[sender, body, attachment_ids, to_line]`, appended with
[`set_attr`](../reference/softcode.md#fn-set_attr) to a `mail_<id>` attribute on
the Postmaster, one list per recipient, and read back with
[`V`](../reference/softcode.md#fn-v). Attributes are persistent, so mail survives
reboots, and because the rows live on the *master*, one authority owns every
mailbox, the same owner-authority convention as the
[coat check](022_coat_check.md) and the [bank](087_bank_accounts.md). CC is just
more rows: `send zeke,kess = ...` appends the same letter to both lists, each
copy carrying the full address line so everyone can see who else got it.

### How a handed-over parcel becomes an attachment

`give parcel to Postmaster` tells the `ON_RECEIVE` hook a great deal:
[`adata('item')`](../reference/softcode.md#event-data-namespace) is the parcel
and `enactor` is the giver. What the handover payload cannot say is who the
parcel is *for*, because it describes the handover, not your intentions. So the
counter takes your parcel now and asks who it is for later: the hook stamps the
arrival with `escrow = <giver's id>`, and your next `send` sweeps everything
stamped with *your* id into the letter.

That hook needs a [`target is me`](../reference/softcode.md#guard-on-target)
guard, because `event:on_receive` is witnessed by every object in the room, not
delivered only to the addressee. Without the guard, handing a parcel to another
player standing in the lobby would make the clerk escrow it too.

On redemption, `claim <n>`
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj)s the items out of the
master to you, which is legal because anything standing *inside* the master is
the master's to relocate, and blanks the row's attachment list so a second claim
finds nothing. A spent stamp is set to `''` rather than deleted, so it stops
matching `get_attr(o, 'escrow') == enactor.id` on a later `send` without
pretending it was never stamped. One honest corner: objects cannot be
duplicated, so on a CC'd letter the parcels ride with the *first* recipient only,
and the copies say so by carrying an empty list.

### How an offline recipient still gets the letter

When you `send`, the clerk [`pemit`](../reference/softcode.md#fn-pemit)s "a
letter arrived" to each recipient, but `pemit` only reaches a live session, so an
offline recipient simply misses that line. The letter does not depend on it: the
row is already in the ledger. On connect, the `ON_CONNECT` hook reads the
recipient's list and pemits the waiting count. The Postmaster hears logins
because it is a world-zone master, so `event:connect` from any room tagged
`zone:world` reaches it. A login room outside the zone is silent, which is the
world-zone workaround's standing boundary. This is the same global reach the
[custom channel](074_custom_channel.md) uses to talk to every station room.

### Why `$send * = *` is safe

No builtin is named `send`, and none *starts with* `send`, so when the dispatcher
finds no builtin and no unique-prefix match it falls through to the softcode
`$`-trigger search. (Builtins dispatch first, which is why `say` or `who` can
never be softcoded over.) The two wildcards anchor on ` = `, the same shape as
`@set`'s own grammar. The reading commands are two triggers on one object: bare
`$mail` lists, `$mail *` reads a numbered line, and bare `mail` never carries an
argument, so the two patterns cannot collide.

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

The Postmaster is an `npc` (so the stock `give` finds it) promoted to world-zone
master:

```text
@create Postmaster
@tag Postmaster = npc
drop Postmaster
@desc Postmaster = A clerk of brass and patience behind a grille. SEND <names> = <message> posts a letter (commas CC extras); MAIL lists yours; MAIL <n> reads one; CLAIM <n> collects parcels. GIVE it an item first to attach it.
@zone/master Postmaster = world
```

The escrow hook stamps whatever just arrived with the giver's id. The guard is
what keeps a handover meant for someone else out of the escrow:

```text
@set Postmaster/on_receive = '''
if target is me:  # on_receive is witnessed room-wide, not only by the addressee
    it = adata('item')
    set_attr(it, 'escrow', enactor.id)
    pemit(enactor, f'The clerk tags your {name(it)}: it will ride along with your next SEND.')
'''
```

Sending resolves every name, refuses the whole letter if any is wrong, and
attaches your pending escrow to the first recipient:

```text
@set Postmaster/cmd_send = '''
$send * = *:
names = [trim(n) for n in trim(arg0).split(',') if trim(n)]
rcpts = [get(n) for n in names]
ok = [p for p in rcpts if p and has_tag(p, 'player')]
parcels = [o for o in contents(me) if get_attr(o, 'escrow') == enactor.id]
if len(ok) < len(names) or not ok:
    pemit(enactor, 'The clerk taps the address line: no such citizen on the rolls.')
else:
    for p in ok:
        rides = [o.id for o in parcels] if p is ok[0] else []  # parcels ride with the first recipient only
        set_attr(me, 'mail_' + p.id, (V('mail_' + p.id) or []) + [[name(enactor), escape(trim(arg1)), rides, escape(trim(arg0))]])
    for o in parcels:
        set_attr(o, 'escrow', '')  # spent: '' no longer matches enactor.id on the next SEND
    for p in ok:
        pemit(p, f'The postal wire clicks: a letter from {name(enactor)} has arrived for you.')
    pemit(enactor, f'The clerk stamps the letter for {len(ok)} recipient(s)' + (f' with {len(parcels)} parcel(s) attached' if parcels else '') + '.')
'''
```

Reading is two patterns on one object. Bare `mail` lists the inbox:

```text
@set Postmaster/cmd_mail = '''
$mail:
rows = V('mail_' + enactor.id) or []
if not rows:
    pemit(enactor, 'The clerk checks the pigeonholes: nothing for you.')
else:
    for i, r in enumerate(rows):
        pemit(enactor, f'{i + 1}. From {r[0]} (to {r[3]})' + (f' [{len(r[2])} parcel(s)]' if r[2] else ''))
'''
```

And `mail <n>` opens one letter, naming its parcels if any wait:

```text
@set Postmaster/cmd_mailn = '''
$mail *:
rows = V('mail_' + enactor.id) or []
k = int(trim(arg0)) if trim(arg0).isdigit() else 0
if not (1 <= k <= len(rows)):
    pemit(enactor, f'No letter numbered {trim(arg0)}.')
else:
    r = rows[k - 1]
    pemit(enactor, f'From {r[0]}, to {r[3]}:')
    pemit(enactor, f'  {r[1]}')
    if r[2]:
        pemit(enactor, f'{len(r[2])} parcel(s) wait behind the grille. CLAIM {k} collects them.')
'''
```

Claiming verifies the parcels are still in the master's hands, hands them over,
and blanks the row so a second claim finds nothing:

```text
@set Postmaster/cmd_claim = '''
$claim *:
rows = V('mail_' + enactor.id) or []
k = int(trim(arg0)) if trim(arg0).isdigit() else 0
ids = rows[k - 1][2] if 1 <= k <= len(rows) else []
live = [o for o in [get('#' + str(i)) for i in ids] if o and loc(o) is me]
if not live:
    pemit(enactor, 'The clerk turns up empty palms: nothing to collect under that number.')
else:
    for o in live:
        teleport_obj(o, enactor)  # inside the master, so the master may relocate them
    set_attr(me, 'mail_' + enactor.id, [r if j != k - 1 else [r[0], r[1], [], r[3]] for j, r in enumerate(rows)])
    pemit(enactor, f'The clerk slides {len(live)} parcel(s) under the grille.')
'''
```

And the login notice reads your list and speaks only if something waits. It
takes no `target` guard, because a world-zone master is a deliberate global
witness of every login, and it already scopes itself to the connecting player by
reading that player's own list:

```text
@set Postmaster/on_connect = '''
n = len(V('mail_' + enactor.id) or [])
if n:
    pemit(enactor, f'The postal wire hums: {n} letter(s) wait for you at the Post Office.')
'''
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

Kess's copy reads the same but carries no parcels, because one compass exists and
the address line tells her who has it. Log out and back in with unread mail and
the wire hums at you. And `send nobody = hi` bounces whole, because the clerk
refuses a letter with any bad address.

## Going further

- **Deleting mail:** a `$burn <n>` that drops the row (attachments first, and
  decide whether unclaimed parcels return to sender or go to the
  [incinerator](019_trash_incinerator.md)).
- **Postage:** an `ON_PAYMENT` gate and a `paid_<id>` ledger, two credits a
  letter and five with a parcel (the [vending machine](002_vending_machine.md)
  idiom).
- **Return to sender:** stamp rows with `now()`, then a slow ticker sweeps
  letters older than a month back onto the sender's ledger.
- **Branch offices:** the ledgers live on one master, so a second counter in
  another town is just another zone room, and the pigeonholes are everywhere the
  zone is.
