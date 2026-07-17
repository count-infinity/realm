# 096. Secure player trade

> Checklist item 96 — [now] — *escrow objects, dual confirms, one-script commit*

**What you'll build:** a trade broker: two players open a trade, stage
goods by handing them to the broker (real escrow — neither side can
touch the other's stake), and both must confirm; any change to the table
resets all confirmations, walking out of the room voids the deal, and
the swap itself executes inside a single script — atomically or not at
all.

**Concepts:** escrow via `give` + `ON_RECEIVE` (the broker is
`npc`-tagged so the stock `give` verb works); `staged_by` stamps as the
who-gets-what ledger; the **any-change-resets** invariant; dual confirm
with the commit in **one script run** (softcode scripts don't interleave
— that's the atomicity); `ON_LEAVE` as the walkout tripwire; a shared
`reset` routine via `eval_attr`.

## How it works

Player-to-player trades die of two bugs: **snatch-back** (hand over your
sword, watch them walk before handing theirs) and **last-second swap**
(they confirm, you quietly restage a worse item, then confirm). The
broker kills both structurally.

**Escrow is possession.** Staging an item is `give <item> to Broker
Unit 7` — the engine's own verb, whose recipient-side `ON_RECEIVE`
fires *after* the handover and hands the script both halves of the
delivery: `adata('item')` is what arrived, `adata('giver')` is who
staged it (the same object as `enactor` here, which is why the build
keeps the shorter name). The arrival is stamped `staged_by = <giver
id>` — and note that the stamp is now purely the *ledger* of
who-gets-what-back, nothing more. A broker built before the payload
existed had to make that stamp do double duty: with no way to be told
what had just landed, it identified the new item by elimination — the
one thing in its hands not yet stamped — so the stamp was load-bearing
for *finding* the arrival as well as recording it. That inference is
the kind that holds until it doesn't (anything else in the broker's
inventory breaks it); `adata('item')` replaces it with a fact, and the
stamp goes back to doing one job.

From the instant it's stamped, *neither* trader can touch the item —
it's in an admin-owned NPC's inventory. Items from someone who isn't a
party to the open trade bounce straight back (`teleport_obj`) with
instructions: an escrow that quietly keeps bystanders' property is a
theft bug.

**Any change resets.** Every successful staging zeroes *both*
`confirm_a` and `confirm_b`. What you confirm is therefore always the
table *as it stands* — restaging after your counterparty confirmed
un-confirms them. This one line is the entire defense against the
last-second swap.

**The commit is one script.** `trade confirm` marks your side; when the
second confirmation lands, *that same script run* walks every stamped
item to the opposite party (`teleport_obj`, which reaches a recipient
mid-room or mid-map), strips the stamps, and clears the session. A
softcode script runs to completion before anything else acts on the
world, so there is no moment where one side has been paid and the other
hasn't — the "swap executes in one script" contract from the audit.

**Walking out cancels.** The broker carries an `ON_LEAVE`: it fires
whenever anything leaves the room (the broker witnesses the departure),
and if the leaver is a party, a shared `reset` routine returns every
staged item to whoever staged it and wipes the session. The same
routine backs the explicit `trade cancel`. Note the honest boundary:
`ON_LEAVE` fires on *movement* — a party who logs out where they stand
hasn't left the room, so the deal simply waits (add a timeout ticker if
that offends; see Going further).

## Build it

The annex and the broker — `npc`-tagged so `give` will address it:

```text
@dig The Trade Annex
@teleport The Trade Annex
@dig The Concourse = out, back
@create Broker Unit 7
@tag Broker Unit 7 = npc
drop Broker Unit 7
```

(The `out`/`back` exits matter: the walkout tripwire below is about
someone *walking* away mid-deal.)

Opening a trade binds the two parties (your counterparty must be
standing here — you're about to trust the same room's exits):

```text
@set Broker Unit 7/cmd_open = $trade with *:other = get(arg0); ok = not V('party_a') and other is not None and has_tag(other, 'player') and loc(other) is here and other.id != enactor.id; [(set_attr(me, 'party_a', enactor.id), set_attr(me, 'party_b', o.id), set_attr(me, 'name_a', name(enactor)), set_attr(me, 'name_b', name(o)), set_attr(me, 'confirm_a', 0), set_attr(me, 'confirm_b', 0), remit(here, f'{name(enactor)} opens a brokered trade with {name(o)}. Stage goods with: give <item> to Broker Unit 7')) for g, o in [[ok, other]] if g]; pemit(enactor, 'The broker is already holding a trade, or your counterparty is not here.') if not ok else None
```

The escrow intake — stamp the arrival, reset all confirmations, bounce
strangers' goods. With the arrival named by the payload, the whole hook
is two conditionals over one `it`; the staging branch no longer needs a
comprehension to bind its own variable into a guard:

```text
@set Broker Unit 7/on_receive = it = adata('item') if target is me else None; ok = it is not None and enactor.id in [V('party_a'), V('party_b')]; (set_attr(it, 'staged_by', enactor.id), set_attr(me, 'confirm_a', 0), set_attr(me, 'confirm_b', 0), remit(here, f'{name(enactor)} stages {name(it)}. All confirmations reset.')) if ok else None; (teleport_obj(it, enactor), pemit(enactor, 'The broker refuses: open a trade first (trade with <who>).')) if it is not None and not ok else None
```

The table, readable by anyone:

```text
@set Broker Unit 7/cmd_status = $trade status:pemit(enactor, 'On the table:'); [pemit(enactor, f"  {name(o)} - from " + (V('name_a', '?') if get_attr(o, 'staged_by') == V('party_a') else V('name_b', '?'))) for o in contents(me) if has_attr(o, 'staged_by')]; pemit(enactor, 'Confirmed: ' + (V('name_a', '') + ' ' if V('confirm_a', 0) else '') + (V('name_b', '') if V('confirm_b', 0) else ''))
```

The confirm-and-commit. The second confirmation executes the whole swap
in this one run — items cross to the *other* party, stamps and session
are wiped:

```text
@set Broker Unit 7/cmd_confirm = $trade confirm:a = V('party_a'); b = V('party_b'); ok = enactor.id in [a, b]; set_attr(me, 'confirm_a', 1) if ok and enactor.id == a else None; set_attr(me, 'confirm_b', 1) if ok and enactor.id == b else None; done = ok and V('confirm_a', 0) and V('confirm_b', 0); [(teleport_obj(o, get('#' + (pb if get_attr(o, 'staged_by') == pa else pa))), del_attr(o, 'staged_by')) for g, pa, pb in [[done, a, b]] if g for o in contents(me) if has_attr(o, 'staged_by')]; (remit(here, f"The broker chimes: trade complete between {V('name_a', '?')} and {V('name_b', '?')}."), del_attr(me, 'party_a'), del_attr(me, 'party_b'), del_attr(me, 'name_a'), del_attr(me, 'name_b'), set_attr(me, 'confirm_a', 0), set_attr(me, 'confirm_b', 0)) if done else None; pemit(enactor, 'You confirm. Waiting on the other side.' if ok and not done else ('You are not part of this trade.' if not ok else 'The trade executes.'))
```

The shared unwind — everything staged goes back to whoever staged it:

```text
@set Broker Unit 7/reset = [(teleport_obj(o, get('#' + get_attr(o, 'staged_by'))), del_attr(o, 'staged_by')) for o in contents(me) if has_attr(o, 'staged_by')]; del_attr(me, 'party_a'); del_attr(me, 'party_b'); del_attr(me, 'name_a'); del_attr(me, 'name_b'); set_attr(me, 'confirm_a', 0); set_attr(me, 'confirm_b', 0); result = 1
```

...used by the polite exit and the tripwire alike:

```text
@set Broker Unit 7/cmd_cancel = $trade cancel:ok = enactor.id in [V('party_a'), V('party_b')]; (eval_attr(me, 'reset'), remit(here, f'{name(enactor)} backs out; the broker returns all staged goods.')) if ok else pemit(enactor, 'You are not part of this trade.')
@set Broker Unit 7/ON_LEAVE = w = enactor.id in [V('party_a'), V('party_b')]; (eval_attr(me, 'reset'), remit(here, f'The broker voids the trade as {name(enactor)} walks away; staged goods are returned.')) if w else None
```

## Try it

Bob has a plasma torch; Cass has a crystal skull.

```text
(Bob)  trade with Cass                  -> "Bob opens a brokered trade..."
(Bob)  give plasma torch to Broker Unit 7
                                        -> "Bob stages plasma torch. All
                                            confirmations reset."
(Cass) give crystal skull to Broker Unit 7
(Bob)  trade confirm                    -> "You confirm. Waiting..."
(Cass) trade confirm                    -> "The broker chimes: trade complete..."
```

Torch and skull have crossed — in one uninterruptible script. Now watch
the defenses: restage anything after a confirm and `trade status` shows
the confirmations gone. Walk `out` mid-trade and the broker voids it,
handing everything back — the staged goods chase you into the
Concourse. A bystander who gives the broker their boots gets them
straight back with instructions.

## Going further

- **Credits on the table.** Stage coin stacks from the Mint (086) —
  physical cash rides the same escrow untouched; or add a
  `trade offer <n> credits` verb escrowing wallet credits into a
  `cash_a`/`cash_b` ledger the commit script settles with
  `transfer_credits`.
- **A confirmation window.** `prompt(enactor, 'Confirm? (yes/no)',
  'on_answer')` for a wizard-style final check — the audit's
  `prompt()` shape, chaining into the same commit routine.
- **Deal timeout.** A `script_ticker` that calls `reset` when
  `now() - opened_at` exceeds five minutes — covers the logged-out
  counterparty `ON_LEAVE` can't see.
- **Trade log.** Append each completed swap to a capped `history`
  attribute (the bank's audit-row pattern, 087) — disputes end when the
  broker remembers.
