# 096. Secure player trade

> Checklist item 96 ([now]): *escrow objects, dual confirms, one-script commit*

**What you'll build:** a trade broker. Two players open a trade, stage
goods by handing them to the broker (real escrow, so neither side can
touch the other's stake), and both must confirm. Any change to the table
resets all confirmations, walking out of the room voids the deal, and
the swap itself executes inside a single script, atomically or not at
all.

**Concepts:** escrow via the `give` verb plus an
[`on_receive`](../reference/softcode.md#lifecycle-hooks) hook (the broker
is `npc`-tagged so the stock `give` verb will address it); a `staged_by`
stamp as the who-gets-what ledger; the any-change-resets invariant; dual
confirm with the commit in one script run (softcode scripts do not
interleave, which is the atomicity); an `on_leave` hook as the walkout
tripwire; a shared `reset` routine run through
[`eval_attr`](../reference/softcode.md#fn-eval_attr).

## How it works

The finished broker is one dropped NPC that holds the whole trade: the
two parties as ids, the staged goods in its own inventory, and a pair of
confirm flags. Two players stage items, both confirm, and the goods
cross in a single script run. Player-to-player trades die of two bugs,
and this section walks through how the broker kills each one structurally
before covering how the swap commits and how the deal unwinds.

The first bug is **snatch-back**: you hand over your sword and watch the
other player walk before handing theirs. The second is the
**last-second swap**: they confirm, you quietly restage a worse item,
then you confirm.

### How goods reach escrow

Staging an item is `give <item> to Broker Unit 7`, the engine's own
verb, so the broker only has to react to the delivery. The `give` verb
addresses either a player or an `npc`-tagged object, which is why the
broker carries the `npc` tag. Once the handover applies, the recipient's
[`on_receive`](../reference/softcode.md#lifecycle-hooks) hook fires and
is handed both halves of the delivery through the
[event data namespace](../reference/softcode.md#event-data-namespace):
[`adata`](../reference/softcode.md#event-data-namespace)`('item')` is
what arrived, and `adata('giver')` is who staged it, which is the same
object as [`enactor`](../reference/softcode.md#fn-v) here. The arrival is
stamped `staged_by = <giver id>` with
[`set_attr`](../reference/softcode.md#fn-set_attr), and that stamp is the
ledger of who gets what back.

From the instant it is stamped, neither trader can touch the item,
because it sits in an admin-owned NPC's inventory. Goods from someone who
is not a party to the open trade bounce straight back with
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj) and a note,
since an escrow that quietly keeps a bystander's property is a theft bug.

### How the broker knows the gift was for it

An `on_receive` hook is a reactive
[`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks) hook, and those
fire on **every** object in the room, not only on the recipient the
handover targeted. So the broker's hook opens with the
[`target` guard](../reference/softcode.md#guard-on-target),
`if target is me:`, an identity check that reacts only to gifts pressed
into the broker's own hands. Without it the broker would stage goods that
two bystanders passed between themselves. (A `$`-command such as
`trade confirm` needs no such guard: a typed command runs only on the
object it was typed at.)

### Why any change resets the confirmations

Every successful staging zeroes both `confirm_a` and `confirm_b`. What
you confirm is therefore always the table as it stands, so restaging
after your counterparty confirmed un-confirms them. Those two lines are
the whole defense against the last-second swap.

### How the swap commits in one run

`trade confirm` marks your side, and when the second confirmation lands,
that same script run walks every stamped item to the opposite party with
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj) (which reaches
a recipient wherever they stand), strips the stamps, and clears the
session. A softcode script runs to completion before anything else acts
on the world, so there is no moment where one side has been paid and the
other has not.

### How the deal unwinds

The broker carries an `on_leave` hook. It fires whenever anything leaves
the room, because the broker witnesses the departure, and here the
witness reacts to *who left* rather than to a target: if the
`enactor` (the leaver) is a party, a shared `reset` routine returns every
staged item to whoever staged it and wipes the session. The same routine
backs the explicit `trade cancel`. Note the honest boundary:
`on_leave` fires on movement, so a party who logs out where they stand
has not left the room and the deal simply waits (add a timeout ticker if
that matters; see Going further).

## Build it

Dig the annex and its concourse, then create the broker. It is
`npc`-tagged so `give` will address it, and it is admin-built so its
scripts run with admin authority and may relocate the players' staged
goods.

```text
@dig The Trade Annex
@teleport The Trade Annex
@dig The Concourse = out, back
@create Broker Unit 7
@tag Broker Unit 7 = npc
drop Broker Unit 7
```

The `out` and `back` exits matter, because the walkout tripwire is about
someone walking away mid-deal.

Opening a trade binds the two parties. Your counterparty must be standing
here, since you are about to trust the same room's exits, and
[`get`](../reference/softcode.md#fn-get) resolves the named player while
[`has_tag`](../reference/softcode.md#fn-has_tag) and
[`loc`](../reference/softcode.md#fn-loc) confirm they are a player in
this room:

```text
@set Broker Unit 7/cmd_open = '''
$trade with *:
other = get(arg0)
ok = not V('party_a') and other is not None and has_tag(other, 'player') and loc(other) is here and other.id != enactor.id
if ok:
    set_attr(me, 'party_a', enactor.id)
    set_attr(me, 'party_b', other.id)
    set_attr(me, 'name_a', name(enactor))
    set_attr(me, 'name_b', name(other))
    set_attr(me, 'confirm_a', 0)
    set_attr(me, 'confirm_b', 0)
    remit(here, f'{name(enactor)} opens a brokered trade with {name(other)}. Stage goods with: give <item> to Broker Unit 7')
else:
    pemit(enactor, 'The broker is already holding a trade, or your counterparty is not here.')
'''
```

The escrow intake stamps the arrival, resets both confirmations, and
bounces a stranger's goods. It is a reactive hook, so the whole body sits
under the `target is me` guard:

```text
@set Broker Unit 7/on_receive = '''
if target is me:                        # events fire on the whole room; react only to gifts handed to the broker
    it = adata('item')
    if enactor.id in [V('party_a'), V('party_b')]:
        set_attr(it, 'staged_by', enactor.id)
        set_attr(me, 'confirm_a', 0)    # any change to the table wipes both confirmations
        set_attr(me, 'confirm_b', 0)
        remit(here, f'{name(enactor)} stages {name(it)}. All confirmations reset.')
    else:
        teleport_obj(it, enactor)       # not a party: hand it straight back
        pemit(enactor, 'The broker refuses: open a trade first (trade with <who>).')
'''
```

The table is readable by anyone. It lists each escrowed item that carries
a `staged_by` stamp, naming who staged it, using
[`contents`](../reference/softcode.md#fn-contents),
[`has_attr`](../reference/softcode.md#fn-has_attr), and
[`get_attr`](../reference/softcode.md#fn-get_attr):

```text
@set Broker Unit 7/cmd_status = '''
$trade status:
pemit(enactor, 'On the table:')
for o in contents(me):
    if has_attr(o, 'staged_by'):
        owner = V('name_a', '?') if get_attr(o, 'staged_by') == V('party_a') else V('name_b', '?')
        pemit(enactor, f'  {name(o)} - from {owner}')
confirmed = (V('name_a', '') + ' ' if V('confirm_a', 0) else '') + (V('name_b', '') if V('confirm_b', 0) else '')
pemit(enactor, 'Confirmed: ' + confirmed)
'''
```

The confirm-and-commit marks the enactor's side, and the second
confirmation runs the whole swap in this one run: items cross to the
*other* party, then the stamps and the session are wiped.

```text
@set Broker Unit 7/cmd_confirm = '''
$trade confirm:
a = V('party_a')
b = V('party_b')
ok = enactor.id in [a, b]
if not ok:
    pemit(enactor, 'You are not part of this trade.')
else:
    if enactor.id == a:
        set_attr(me, 'confirm_a', 1)
    else:
        set_attr(me, 'confirm_b', 1)
    done = V('confirm_a', 0) and V('confirm_b', 0)
    if done:
        for o in contents(me):
            if has_attr(o, 'staged_by'):
                dest = get('#' + (b if get_attr(o, 'staged_by') == a else a))  # each item goes to the OTHER party
                teleport_obj(o, dest)
                del_attr(o, 'staged_by')
        remit(here, f"The broker chimes: trade complete between {V('name_a', '?')} and {V('name_b', '?')}.")
        del_attr(me, 'party_a')
        del_attr(me, 'party_b')
        del_attr(me, 'name_a')
        del_attr(me, 'name_b')
        set_attr(me, 'confirm_a', 0)
        set_attr(me, 'confirm_b', 0)
        pemit(enactor, 'The trade executes.')
    else:
        pemit(enactor, 'You confirm. Waiting on the other side.')
'''
```

The shared unwind returns everything staged to whoever staged it and
clears the session. It is a function attribute run through
[`eval_attr`](../reference/softcode.md#fn-eval_attr), so its `result` is
what the caller reads, and [`del_attr`](../reference/softcode.md#fn-del_attr)
tears the session down:

```text
@set Broker Unit 7/reset = '''
for o in contents(me):
    if has_attr(o, 'staged_by'):
        teleport_obj(o, get('#' + get_attr(o, 'staged_by')))
        del_attr(o, 'staged_by')
del_attr(me, 'party_a')
del_attr(me, 'party_b')
del_attr(me, 'name_a')
del_attr(me, 'name_b')
set_attr(me, 'confirm_a', 0)
set_attr(me, 'confirm_b', 0)
result = 1
'''
```

The explicit cancel calls that routine, gated to the two parties:

```text
@set Broker Unit 7/cmd_cancel = '''
$trade cancel:
if enactor.id in [V('party_a'), V('party_b')]:
    eval_attr(me, 'reset')
    remit(here, f'{name(enactor)} backs out; the broker returns all staged goods.')
else:
    pemit(enactor, 'You are not part of this trade.')
'''
```

The tripwire calls the same routine when a party walks out. It is a
reactive hook whose target is the room, so it guards on the leaver being
a party rather than on `target is me`:

```text
@set Broker Unit 7/on_leave = '''
if enactor.id in [V('party_a'), V('party_b')]:    # the leaver is a party to the open trade
    eval_attr(me, 'reset')
    remit(here, f'The broker voids the trade as {name(enactor)} walks away; staged goods are returned.')
'''
```

## Try it

Bob has a plasma torch and Cass has a crystal skull, both standing in the
annex.

```text
(Bob)  > trade with Cass
        Bob opens a brokered trade with Cass. Stage goods with: give <item> to Broker Unit 7
(Bob)  > give plasma torch to Broker Unit 7
        Bob stages plasma torch. All confirmations reset.
(Cass) > give crystal skull to Broker Unit 7
        Cass stages crystal skull. All confirmations reset.
(Bob)  > trade confirm
        You confirm. Waiting on the other side.
(Cass) > trade confirm
        The trade executes.
        The broker chimes: trade complete between Bob and Cass.
```

Torch and skull have crossed inside one uninterruptible script. Now watch
the defenses. Restage anything after a confirm and `trade status` shows
the confirmations gone. Walk `out` mid-trade and the broker voids it,
handing everything back, so the staged goods chase you into the
Concourse. A bystander who gives the broker their boots gets them
straight back with instructions.

## Going further

- **Credits on the table.** Stage coin stacks from the
  [currency mint](086_currency.md), since physical cash rides the same
  escrow untouched. Or add a
  `trade offer <n> credits` verb that escrows wallet credits into a
  `cash_a` or `cash_b` ledger the commit script settles with
  [`transfer_credits`](../reference/softcode.md#fn-transfer_credits).
- **A confirmation window.** A
  [`prompt`](../reference/softcode.md#fn-prompt)`(enactor, 'Confirm?
  (yes/no)', 'on_answer')` for a wizard-style final check, chaining into
  the same commit routine.
- **Deal timeout.** A [`script_ticker`](../reference/softcode.md#lifecycle-hooks)
  that calls `reset` when `now() - opened_at` exceeds five minutes, which
  covers the logged-out counterparty that `on_leave` cannot see.
- **Trade log.** Append each completed swap to a capped `history`
  attribute, the same audit-row pattern the
  [bank](087_bank_accounts.md) uses, so disputes end when the broker
  remembers.
