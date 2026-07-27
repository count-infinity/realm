# 093. Housing rent

> Checklist item 93 ([now]): *on_tick billing, grace attrs, lockout/eviction*

**What you'll build:** a lettable flat with a rent box in the hall. A
tenant leases it, pays rent into the box, and falls behind at their peril:
the door code freezes the moment they are overdue, a courier warns them
once, and after the grace period the movers clear the flat and terminate
the lease.

**Concepts:** [`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks) with
[`adata('amount')`](../reference/softcode.md#event-data-namespace) for
banking rent by whole periods; a **pre-enter ward** on the destination room
(the `event:pre_enter` action) for a lockout that needs no ticker to stay
correct; a [`script_ticker`](../reference/softcode.md#npcs-behaviors)
that escalates from warning to eviction; repossession with
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj); and grace kept
as an attribute rather than a state machine.

## How it works

The finished tenancy is a rent box in the hall and a ward on the flat. The
box holds every fact about the lease as plain attributes, the ward reads
those facts to decide who may walk in, and a heartbeat on the box escalates
against a tenant who stops paying. This section answers three questions:
where the lease lives, how one number drives the whole tenancy, and how a
payment banks time.

### Where the lease lives

All of the tenancy state sits on the box, deliberately *outside* the flat,
because a locked-out tenant must still be able to reach the payment point.
Its attributes are `tenant` (the tenant's id), `tenant_name`, `rent`,
`period`, `grace`, `paid_until`, and `warned`. Not one of them is a copy of
the box's own credit balance, which the engine tracks on its own.

### How one number drives the tenancy

Everything keys off `paid_until`, the epoch second the paid-up period runs
out. Three deadlines fall out of that single number:

- *Overdue* is `now() > paid_until`. The ward stops honoring the tenant at
  that instant, which is the **lockout**. It needs no tick, no flag, and no
  cleanup, because the comparison is true the moment the clock passes and
  false again the moment a payment pushes `paid_until` forward. A tenant
  already *inside* is never trapped, since the ward gates only
  `event:pre_enter`, the check every arrival runs, so walking out fires
  `event:on_leave` and passes untouched.
- *Overdue, on the heartbeat* is when the tick notices and sends one
  warning. `warned` records that the courier has been sent, and a payment
  clears it, so eviction is never a surprise.
- *Overdue plus grace* is when the tick **evicts**. Every non-exit thing in
  the flat, the loitering tenant included, is swept to the hall with
  [`teleport_obj`](../reference/softcode.md#fn-teleport_obj), and the lease
  attributes are deleted. The box's scripts run with its admin owner's
  authority and the flat is admin-dug, so relocating whatever stands in it
  is the room owner's teleport right at work.
  [`teleport_obj`](../reference/softcode.md#fn-teleport_obj) is a forced
  move that tunnels the flat's own ward, which is exactly what you want: the
  ward keeps strangers out, and it must not stand in the way of a
  repossession.

### How a payment banks time

`pay 50 to the rent box` fires
[`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks), and the action's
payload carries the sum, which the hook reads with
[`adata('amount', 0)`](../reference/softcode.md#event-data-namespace). The
box banks whole periods (`paid // rent` of them, so overpaying two rents
buys two periods), pushes back any remainder, and refunds strangers
outright. The extension is `max(now(), paid_until) + period * k`, so paying
while overdue starts the clock from *now* rather than from the debt. The
same event fires on every object in the room, so the hook opens with
`if target is me:` to react only to money paid into this box, exactly the
[guard on `target`](../reference/softcode.md#guard-on-target) the
[slot machine](001_slot_machine.md) and [bank](087_bank_accounts.md) use.

## Build it

First the shell: dig the hall, stand in it, dig the flat off it with a
`flat door` in and a `hall door` back, then create the rent box and drop it
in the hall.

```text
@dig Rooming House Hall
@teleport Rooming House Hall
@dig Harbor Flat = flat door, hall door
@create the rent box
drop the rent box
```

The terms are plain data, so a dearer or slower flat is a `@set`, not a
script edit. Rent is 50 credits, a period is 300 seconds, and the grace
after the due date is 120 seconds:

```text
@set the rent box/rent = 50
@set the rent box/period = 300
@set the rent box/grace = 120
```

`lease flat` claims the flat when it is vacant. It records the tenant and
their name, gives them the first period on the house, and clears any stale
`warned` flag:

```text
@set the rent box/cmd_lease = '''
$lease flat:
if V('tenant'):
    pemit(enactor, 'The flat is already let.')
else:
    set_attr(me, 'tenant', enactor.id)
    set_attr(me, 'tenant_name', name(enactor))
    set_attr(me, 'paid_until', now() + V('period', 300))  # first period free
    set_attr(me, 'warned', 0)
    pemit(enactor, f"You sign the ledger: Harbor Flat is yours. Rent is {V('rent', 50)} credits a period, into this box.")
'''
```

The payment reaction reads the amount, banks whole periods, and refunds the
rest. Its steps in order: guard to money paid into this box, compute how
many periods the tenant's payment covers, and then either stamp the periods
and push back the change, or refund the whole sum with the reason:

```text
@set the rent box/on_payment = '''
if target is me:  # ON_PAYMENT fires on EVERY object in the room, so guard it
    rent = V('rent', 50)
    paid = adata('amount', 0)
    k = paid // rent if enactor.id == V('tenant') else 0  # whole periods, tenants only
    if k:
        set_attr(me, 'paid_until', max(now(), V('paid_until', 0)) + V('period', 300) * k)
        set_attr(me, 'warned', 0)  # paying up clears the warning
        change = paid - rent * k
        if change > 0:
            transfer_credits(me, enactor, change)  # push back the remainder
        pemit(enactor, f'The box stamps a receipt: {k} period(s) paid.')
    else:
        transfer_credits(me, enactor, paid)  # underpay or no lease: refund in full
        pemit(enactor, 'The box spits it back: ' + (f'the rent is {rent} a period.' if enactor.id == V('tenant') else 'you hold no lease here.'))
'''
```

The lockout lives in a ward on the flat, so step into the flat first to make
`here` resolve to it:

```text
flat door
```

The ward reads the box's state at decision time, so no tick keeps it honest,
arithmetic does. It fires only on arrivals into the flat, bars strangers
whenever the flat is let, and bars the tenant only while they are overdue.
The `atype == 'event:pre_enter'` filter is the load-bearing guard: a
departure fires `event:on_leave` with this same flat as target, so keying on
the arrival is what lets a locked-out tenant still walk *out*:

```text
@set here/on_check = '''
if atype == 'event:pre_enter' and has_atag('movement'):  # arrivals only; on_leave passes untouched
    box = get('the rent box')
    tenant = get_attr(box, 'tenant')
    if tenant and actor.id != tenant:
        block('This flat is privately let.')
    elif actor.id == tenant and now() > get_attr(box, 'paid_until', 0):
        block('The landlord froze the door code: rent is overdue. (pay at the rent box)')
'''
```

Walk back to the hall so the rest of the build runs where the box stands:

```text
hall door
```

Finally, give the box a heartbeat and the escalation script. A ticker fires
only on the box itself, so it needs no `target` guard. Past the grace it
evicts; otherwise, if overdue and not yet warned, it sends the courier once:

```text
@behavior the rent box = script_ticker, interval:60
@set the rent box/on_tick = '''
t = V('tenant')
if t:
    due = V('paid_until', 0)
    if now() > due + V('grace', 120):
        for o in contents(get('Harbor Flat')):
            if not has_tag(o, 'exit'):
                teleport_obj(o, loc(me))  # forced move tunnels the flat's own ward
        pemit(get('#' + t), 'The movers clear Harbor Flat: your lease is terminated and your goods are in the hall.')
        del_attr(me, 'tenant')
        del_attr(me, 'tenant_name')
        set_attr(me, 'warned', 0)
        remit(loc(me), 'Movers carry furniture out of Harbor Flat and change the locks.')
    elif now() > due and not V('warned', 0):
        set_attr(me, 'warned', 1)  # warn once; payment clears this flag
        pemit(get('#' + t), 'A courier finds you: rent on Harbor Flat is overdue. The door is frozen until you pay.')
'''
```

## Try it

As Bob, with 200 credits, lease the flat and move in with a bag:

```text
lease flat              -> "You sign the ledger: Harbor Flat is yours..."
flat door               -> you are home
drop a duffel bag
hall door
```

Cass tries `flat door` and reads "This flat is privately let." Now let the
rent lapse and watch the door freeze against Bob himself:

```text
@eval set_attr(get('the rent box'), 'paid_until', now() - 10)
flat door               -> "The landlord froze the door code..."
```

The next tick sends the courier's warning, once. Pay up and the code works
again:

```text
@tr the rent box/on_tick   -> "A courier finds you: rent on Harbor Flat is overdue."
pay 50 to the rent box     -> "The box stamps a receipt: 1 period(s) paid."
flat door                  -> the code works again
```

Instead, stay delinquent past the grace and trigger the tick: the movers
sweep the duffel bag (and Bob, if he is lurking inside) into the hall, the
lease attributes vanish, and the flat is open to the next `lease flat`.
Underpay with `pay 30 to the rent box` and the box spits it straight back,
and money from anyone without a lease bounces with "you hold no lease here."

## Going further

- **Deposit and damages.** Take `rent * 2` at `lease` into a `deposit`
  attribute, keep it on eviction, and refund it on a voluntary `$end lease`:
  landlord economics in two attributes.
- **A whole corridor.** Move the lease rows to `tenant_<room-id>` keys and
  let one box manage every flat off the hall, the branch-terminal pattern
  from the [bank](087_bank_accounts.md).
- **Repossessed to storage, not the hall.** Sweep to a warehouse room and
  record each item under the former tenant's id, turning eviction into a
  storage-fee side quest.
- **Key sharing.** A `guests` list the ward also honors
  (`actor.id in get_attr(box, 'guests', [])`) with `$invite *` and
  `$evict *` verbs makes tenancy a small social system.
