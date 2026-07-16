# 093. Housing rent

> Checklist item 93 — [now] — *on_tick billing, grace attrs, lockout/eviction*

**What you'll build:** a lettable flat with a rent box in the hall:
lease it, pay rent into the box, and fall behind at your peril — the
door code freezes the moment you're overdue (lockout by arithmetic), a
courier warns you once, and after the grace period the movers clear the
flat and terminate the lease.

**Concepts:** the till-delta `ON_PAYMENT` idiom (the trigger namespace
has no amount — reconstruct it from the balance); a **pre-enter ward on
the destination room** (`atype == 'event:pre_enter'`) for lockout that
needs no ticker to be correct; `script_ticker` escalation — warn, then
evict; repossession via `teleport_obj` sweeping a room the master's
owner controls; grace as an attribute, not a state machine.

## How it works

The whole tenancy lives on **the rent box** in the hall — deliberately
*outside* the flat, because a locked-out tenant must still be able to
reach the payment point. Its state: `tenant`, `paid_until`, `rent`,
`period`, `grace`, `warned`, and the till.

**Three deadlines, one number.** Everything keys off `paid_until`:

- *due* — `now() > paid_until`: the ward stops honoring the tenant.
  That's the **lockout**, and it needs no tick, no flag, no cleanup —
  the toll-gate doctrine of state that expires by comparison. A tenant
  *inside* is not trapped: the ward gates only `event:pre_enter`, the
  destination-side veto every walk and teleport runs, so leaving is
  free and re-entering is not.
- *due, on the heartbeat* — the tick notices and sends **one** warning
  (`warned` flags it, payment clears it): eviction should never be a
  surprise.
- *due + grace* — the tick **evicts**: every non-exit thing in the flat
  (the loitering tenant included) is swept to the hall by
  `teleport_obj`, and the lease attributes are deleted. The box's
  scripts run with its admin owner's authority, and the flat is
  admin-dug, so relocating whatever stands in it is the room-owner
  teleport rule at work. `teleport_obj` is a forced move — it tunnels
  the flat's own ward, which is what you want: the ward keeps people
  *out*, never repossession *in progress*.

**Payment is the till-delta idiom.** `pay 50 to the rent box` fires
`ON_PAYMENT`, which is *not told the amount* — the engine gap first
documented at the toll gate (030). But the credits have already landed,
so `paid = credits(me) - till` reconstructs it exactly. The box banks
whole periods (`paid // rent` of them — overpay two rents, get two
periods), pushes back any remainder, refunds strangers outright, and
updates the till after every branch so the arithmetic never drifts.
Extension is `max(now(), paid_until) + period * k`: paying while overdue
starts from *now*, not from the debt.

## Build it

The hall, the flat (exits both ways), and the box with its terms:

```text
@dig Rooming House Hall
@teleport Rooming House Hall
@dig Harbor Flat = flat door, hall door
@create the rent box
drop the rent box
@set the rent box/rent = 50
@set the rent box/period = 300
@set the rent box/grace = 120
```

`lease flat` — first period on the house; the till baseline is set here
so the first payment's delta is right:

```text
@set the rent box/cmd_lease = $lease flat:ok = not get_attr(me, 'tenant'); (set_attr(me, 'tenant', enactor.id), set_attr(me, 'tenant_name', name(enactor)), set_attr(me, 'paid_until', now() + get_attr(me, 'period', 300)), set_attr(me, 'warned', 0), set_attr(me, 'till', credits(me)), pemit(enactor, 'You sign the ledger: Harbor Flat is yours. Rent is ' + str(get_attr(me, 'rent', 50)) + ' credits a period, into this box.')) if ok else pemit(enactor, 'The flat is already let.')
```

The payment reaction — till-delta, whole periods banked, remainder and
strangers refunded:

```text
@set the rent box/on_payment = rent = get_attr(me, 'rent', 50); paid = credits(me) - get_attr(me, 'till', 0); k = paid // rent if enactor.id == get_attr(me, 'tenant') else 0; (set_attr(me, 'paid_until', max(now(), get_attr(me, 'paid_until', 0)) + get_attr(me, 'period', 300) * k), set_attr(me, 'warned', 0), pemit(enactor, 'The box stamps a receipt: ' + str(k) + ' period(s) paid.')) if k else (transfer_credits(me, enactor, paid), pemit(enactor, 'The box spits it back: ' + ('the rent is ' + str(rent) + ' a period.' if enactor.id == get_attr(me, 'tenant') else 'you hold no lease here.'))); transfer_credits(me, enactor, paid - rent * k) if k and paid - rent * k > 0 else None; set_attr(me, 'till', credits(me))
```

The lockout ward, on the flat itself (walk in to set it, walk out).
It reads the box's state at decision time — no tick keeps it honest,
arithmetic does. Strangers are barred whenever the flat is let; the
tenant is barred only when overdue:

```text
flat door
@set here/on_check = box = get('the rent box'); block('The landlord froze the door code: rent is overdue. (pay at the rent box)') if atype == 'event:pre_enter' and has_atag('movement') and actor.id == get_attr(box, 'tenant') and now() > get_attr(box, 'paid_until', 0) else (block('This flat is privately let.') if atype == 'event:pre_enter' and has_atag('movement') and get_attr(box, 'tenant') and actor.id != get_attr(box, 'tenant') else None)
hall door
```

And the escalation heartbeat on the box — warn once when overdue, evict
past the grace:

```text
@behavior the rent box = script_ticker, interval:60
@set the rent box/on_tick = t = get_attr(me, 'tenant'); due = get_attr(me, 'paid_until', 0); (set_attr(me, 'warned', 1), pemit(get('#' + t), 'A courier finds you: rent on Harbor Flat is overdue. The door is frozen until you pay.')) if t and now() > due and not get_attr(me, 'warned', 0) else None; ([teleport_obj(o, loc(me)) for o in contents(get('Harbor Flat')) if not has_tag(o, 'exit')], pemit(get('#' + t), 'The movers clear Harbor Flat: your lease is terminated and your goods are in the hall.'), del_attr(me, 'tenant'), del_attr(me, 'tenant_name'), set_attr(me, 'warned', 0), remit(loc(me), 'Movers carry furniture out of Harbor Flat and change the locks.')) if t and now() > due + get_attr(me, 'grace', 120) else None
```

## Try it

As Bob, with 120 credits:

```text
lease flat              -> "You sign the ledger: Harbor Flat is yours..."
flat door               -> you're home
drop a duffel bag
hall door
```

Cass tries `flat door`: "This flat is privately let." Now let the rent
lapse — `@eval set_attr(get('the rent box'), 'paid_until', now() - 10)`
— and Bob's own `flat door` gets "The landlord froze the door code."
The next tick (`@tr the rent box/on_tick`) sends the courier's warning,
once. Pay up:

```text
pay 50 to the rent box  -> "The box stamps a receipt: 1 period(s) paid."
flat door               -> the code works again
```

Instead, stay delinquent past the grace and trigger the tick: the movers
sweep the duffel bag (and Bob, if he's lurking inside) into the hall,
the lease attributes vanish, and the flat is open to the next `lease
flat`. Underpay (`pay 30`) and the box spits it straight back.

## Going further

- **Deposit and damages.** Take `rent * 2` at `lease` into a `deposit`
  attribute; eviction keeps it, a voluntary `$end lease` refunds it —
  landlord economics in two attributes.
- **A whole corridor.** Move the ledger rows to `tenant_<room-id>` keys
  and let one box manage every flat off the hall — the branch-terminal
  pattern from the bank (087).
- **Repossessed to storage, not the hall.** Sweep to a warehouse room
  and ledger each item under the ex-tenant's id — the coat-check pattern
  (022) turns eviction into a storage-fee side quest.
- **Key sharing.** A `guests` list attribute the ward also honors
  (`actor.id in get_attr(box, 'guests', [])`) with `$invite *`/`$evict *`
  verbs — tenancy becomes a small social system.
