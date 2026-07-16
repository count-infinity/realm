# 022. Coat Check

> Checklist item 22 — [now] — *ticket pattern, paired-object bookkeeping attrs*

**What you'll build:** A brass golem behind a counter. Hand it your
coat and it hands you a numbered claim ticket; say `claim <number>`
with the ticket in hand — today, tomorrow, after a reboot — and your
coat comes back. Wrong ticket, no coat.

**Concepts:** the **ticket pattern** — a spawned object as a bearer
token — paired with **ledger attributes** on the master
(`held_<n> = #id`) so each half can verify the other; `give` +
`ON_RECEIVE` as the deposit interface; `create_obj`/`destroy_obj` for
the token's lifecycle; and the two authority rules that let a counter
handle other people's property.

## How it works

**Deposit is a `give`.** The golem is tagged `npc`, so the stock
`give <item> to Coat-Check Golem` works, and — unlike `put`, whose
hook fires before the item lands — the recipient-side `ON_RECEIVE`
fires *after* the handover. The script can't be told which item
arrived (event hooks carry no payload), but it doesn't need to be: the
new arrival is whatever in `contents(me)` isn't yet stamped. Each
deposit stamps the item (`checked = n`), advances the counter, records
`held_<n> = '#' + item.id` in the ledger, and mints the token — a
`claim_ticket`-tagged object with a `claim_no` attribute: the paired
bookkeeping, one half on each object, all of it persistent. Reboots
don't blink. One authority nicety: the golem mints the ticket *in its
own hands* and then `teleport_obj`s it over — `create_obj` refuses to
conjure things directly into a stranger's pockets, but handing over
what you hold is always yours to do.

**Redeem is a claim, checked twice.** `$claim <n>` demands both
halves agree: a ticket in *your hand* whose `claim_no` matches, and a
ledger entry under that number. Ticket but no entry: the rack is bare.
Number but no ticket: brass palms. Both: the golem teleports the item
back to you, clears the stamp and the ledger line, and destroys the
ticket — a bearer token must die on redemption or it's a duplication
bug. Note what the double check buys: tickets are ordinary objects, so
players can trade, sell, or steal them — a stolen ticket *works*,
which is not a flaw but a plot.

**Why the golem is allowed.** It mutates the tickets (it owns what it
creates) and relocates the coats (anything standing *inside* it — the
room-owner teleport rule). Stamping a stranger's coat, though, needs
control of the coat — so run a public counter as an admin-owned
master, the same owner-authority convention as any shared ledger.

**Handed the ticket by mistake?** The golem's receive script spots
incoming `claim_ticket`s and pushes them straight back with
instructions — a give-based redeem would strand tokens in the ledger's
blind spot, so the interface refuses it.

## Build it

The golem and its counter manner:

```text
@create Coat-Check Golem
@tag Coat-Check Golem = npc
drop Coat-Check Golem
@desc Coat-Check Golem = Brass and patience. A rack of numbered hooks glitters behind it.
```

The deposit script — return stray tickets, stamp the new arrival,
ledger it, mint the token:

```text
@set Coat-Check Golem/on_receive = tk = [o for o in contents(me) if has_tag(o, 'claim_ticket')]; new = [o for o in contents(me) if not has_tag(o, 'claim_ticket') and not has_attr(o, 'checked')]; it = new[0] if new else None; n = get_attr(me, 'counter', 0) + 1 if it else 0; t = create_obj('claim ticket ' + str(n), ['claim_ticket'], me) if it else None; (teleport_obj(tk[0], enactor), pemit(enactor, 'The golem taps the ticket and hands it back: just say claim ' + str(get_attr(tk[0], 'claim_no')) + '.')) if tk else None; (set_attr(me, 'counter', n), set_attr(it, 'checked', n), set_attr(me, 'held_' + str(n), '#' + it.id), set_attr(t, 'claim_no', n), teleport_obj(t, enactor), pemit(enactor, 'The golem stows your ' + name(it) + ' on hook ' + str(n) + ' and punches ticket ' + str(n) + '.')) if it else None
```

The redeem command — both halves or nothing:

```text
@set Coat-Check Golem/cmd_claim = $claim *: tick = [o for o in contents(enactor) if has_tag(o, 'claim_ticket') and str(get_attr(o, 'claim_no')) == trim(arg0)]; held = get_attr(me, 'held_' + trim(arg0)); it = get(held) if held else None; (teleport_obj(it, enactor), del_attr(it, 'checked'), del_attr(me, 'held_' + trim(arg0)), destroy_obj(tick[0]), pemit(enactor, 'The golem lifts your ' + name(it) + ' off hook ' + trim(arg0) + ' and retires the ticket.')) if tick and it else pemit(enactor, 'The golem shows you two empty brass palms: no matching ticket in your hand.' if not tick else 'The golem stares at hook ' + trim(arg0) + ', which is bare. Curious.')
```

Something worth checking:

```text
@create wool greatcoat
```

## Try it

```text
give wool greatcoat to Coat-Check Golem
   -> The golem stows your wool greatcoat on hook 1 and punches ticket 1.
```

You're holding `claim ticket 1` (`@examine` it: one `claim_no`
attribute — the token is data); the golem holds the coat. Try to cheat
first:

```text
claim 4    -> The golem shows you two empty brass palms: no matching ticket in your hand.
claim 1    -> The golem lifts your wool greatcoat off hook 1 and retires the ticket.
```

The coat is back in your inventory and the ticket is gone from the
world. A second deposit punches ticket 2 — the counter never reuses a
number, so yesterday's stubs stay worthless. And if you absentmindedly
`give claim ticket 2 to Coat-Check Golem`, it taps the number and
hands it straight back.

## Going further

- **Checking fee:** the golem already has hands — an `on_payment`
  gate before deposit (the [vending machine](002_vending_machine.md)
  credit pattern) makes hook space cost five credits.
- **Storage teleport:** `teleport_obj(it, get('the cloakroom'))` on
  deposit moves coats to a real back room instead of the golem's
  pockets — the `held_<n>` ledger doesn't care where the coat sleeps,
  which is the point of keeping `#id`s, not locations.
- **Lost-ticket desk:** an owner-only `$override <n>` that reads the
  ledger and returns the item without a token — every ticket system
  eventually meets a customer who lost theirs.
- **Expiring stubs:** `expire(ticket, 604800)` on mint plus a weekly
  sweep of unclaimed hooks into the
  [trash bin](019_trash_incinerator.md) — coat checks are not
  long-term storage.
