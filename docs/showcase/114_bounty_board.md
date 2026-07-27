# 114. Bounty board

> Checklist item 114 ([now]): *ON_DEATH verification, escrow payouts*

**What you'll build:** a bounty office for the badlands where anyone can post a
contract on a name and stake credits into the board. The board is a **zone
master**, so it overhears every death across the zone, checks the fallen against
its contracts, and pays the hunter on the spot.

**Concepts:** zone masters as verification witnesses (an
[`ON_DEATH`](../reference/softcode.md#lifecycle-hooks) heard over a whole zone,
the same law pattern as the [guard response](071_guard_response.md)), escrow via
the `pay` command plus [`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks)
(reading the stake with [`adata('amount')`](../reference/softcode.md#event-data-namespace)),
the death event's `target` as the victim of record, a ledger held as a list
attribute, and [`act`](../reference/softcode.md#fn-act) with `targeting='zone'`
for a zone-wide crier.

## How it works

The finished office is a single board object that is also a zone master, which
means events in every badlands room reach its `ON_<EVENT>` attributes. Posting
stakes credits physically onto the board, and that pile is the escrow. A death
anywhere in the zone reaches the board's `ON_DEATH`, which reads the fallen's
name, matches it against the ledger, and pays the killer. This is the same
per-object ledger idea the [job board](094_job_board.md) uses for delivery jobs,
turned toward kills instead of hand-ins. Four questions carry the build: where
the stake sits, why a payment across the zone does not stake a phantom contract,
how the board learns who died and who killed them, and what "death" even means
for a player.

### Where the stake sits, and why the poster hands it over

Posting is two deliberate steps. A `post <name>` command drafts a contract by
writing a `pending_<poster>` attribute, and then the poster stakes it with the
ordinary `pay` command. The poster hands the money over rather than the board
taking it, because [`transfer_credits`](../reference/softcode.md#fn-transfer_credits)
only moves money *from* something its executor controls, and the board does not
control a mortal's purse. When the payment lands, the board's `ON_PAYMENT` fires
with the payer bound as `enactor`, the payee as `target`, and the stake readable
as [`adata('amount')`](../reference/softcode.md#event-data-namespace). The staked
credits now sit on the board object itself, which is the escrow.

The ledger is a list of `[name, pot]` pairs, so paying the same name again
fattens its pot, and the crier announces each contract zone-wide with
[`act`](../reference/softcode.md#fn-act)`(me, ..., targeting='zone')`, which
reaches every room in the board's zone.

### How a payment across the zone does not stake a phantom contract

`ON_PAYMENT` is a witnessed event: it fires on every object that can hear it,
and a zone master hears the whole zone. So the hook opens with `if target is
me:`, an identity check (see
[Guard on `target`](../reference/softcode.md#guard-on-target)). Here `enactor`
is who paid and `target` is who was **paid**, so the board must confirm it was
the payee before it consumes anyone's pending draft. Without that line, buying a
drink two rooms away would fire the board's payment hook, eat the buyer's draft,
and post a contract for nothing. The [casino floor](108_casino_floor.md) states
the general rule for this hook.

### How the board learns who died and who did the killing

Verification is witnessing, not trust. The board is crowned `@zone/master` over
`badlands`, so a death in any badlands room reaches its `ON_DEATH`. A death
propagates `combat:on_death` with the **victim bound as `target`** and the
**killer as `enactor`**, so the board reads the name off the fallen and checks it
against the ledger. A matching name plus a player killer pays
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits)`(me, enactor,
pot)`, strikes the entry, and the crier announces the claim. There is no `$claim`
command to lie to, because the only way onto a payout line is to actually be the
reason something died.

This is the deliberate exception to the target guard: a zone master is a global
witness watching everyone, exactly like the guard response's dispatcher, so its
`ON_DEATH` takes no `if target is me:` line. Instead it guards on the two things
that make a claim real, a ledgered name and a player killer, and it fails closed
otherwise, so a mark killed by another NPC leaves the contract standing.

Every route into death comes through one place. `combat:on_death` is announced
from `CombatManager.handle_death`, which a sword swing, a softcode
[`damage()`](../reference/softcode.md#fn-damage) call, and a `damage_over_time`
tick all reach, so the board hears them all. Hearing a death is not the same as
being able to pay for it: the killer has to survive the indirect routes too. An
effect names its instigator because
[`apply_effect`](../reference/softcode.md#fn-apply_effect) stamps `source_id`
with whoever applied it, so a poison tick carries its poisoner through to the
death and the contract settles. One route attributes loosely by design: a
softcode `damage()` kill names the *scripted object* that dealt the blow, the
[grenade](111_grenades.md) or the dart trap, rather than the hand that threw it,
so a thrown-weapon bounty credits the weapon. `target` is always the victim, so
the board always knows who died even when it cannot pin the killer.

### Dead, or merely down

[`adata('fatal')`](../reference/softcode.md#event-data-namespace) is True for a
real death, an NPC becoming a corpse, and False for a **player** knocked
unconscious in place, because players do not die. This board pays on either, since
a mark is a mark, but that one boolean is what a dead-or-alive office would branch
on (see Going further).

## Build it

The office and the hunting ground, both zoned into `badlands` so the board can
hear across them:

```text
@dig The Bounty Office = office, out
office
@zone here = badlands
@dig Rattler Gulch = gulch, office
gulch
@zone here = badlands
office
```

The board itself, crowned master. `@zone/master` makes it hear events in every
room of the zone, not just its own:

```text
@create bounty board
drop bounty board
@desc bounty board = Sun-cracked cork and yellowed paper. POST <name> to draft a contract, then PAY this board to stake it. BOUNTIES lists what is open.
@zone/master bounty board = badlands
```

Posting drafts a contract into a `pending_<poster>` key, one draft per poster,
and tells them how to stake it:

```text
@set bounty board/cmd_post = '''
$post *:
nm = trim(arg0)
set_attr(me, 'pending_' + enactor.id, nm)  # one draft per poster, keyed by id
pemit(enactor, 'Contract drafted on ' + nm + '. Now stake the reward: PAY <amount> TO bounty board.')
'''
```

The payment hook turns a stake into a contract. The `if target is me:` guard is
load-bearing because the zone master hears every payment in the zone, so only a
payment *to the board* should stake anything:

```text
@set bounty board/on_payment = '''
if target is me:  # a zone master hears EVERY payment in the zone; guard to its own
    nm = V('pending_' + enactor.id, '')
    if not nm:
        pemit(enactor, 'Draft a contract first: POST <name>.')
    else:
        led = V('ledger') or []
        pot = adata('amount', 0) + sum(e[1] for e in led if e[0] == nm)
        set_attr(me, 'ledger', [e for e in led if e[0] != nm] + [[nm, pot]])
        del_attr(me, 'pending_' + enactor.id)
        act(me, 'The office crier bellows: ' + str(pot) + ' credits on the head of ' + nm + '!', targeting='zone')
'''
```

The reading face lists the open contracts, or says the board is bare:

```text
@set bounty board/cmd_bounties = '''
$bounties:
led = V('ledger') or []
if not led:
    pemit(enactor, 'The board is bare. The badlands sleep easy.')
else:
    for e in led:
        pemit(enactor, '[WANTED] ' + e[0] + ' -- ' + str(e[1]) + ' credits.')
'''
```

The verifier is the whole point, and it is four names long: `target` is who
died, `enactor` is who killed them, and the ledger says what that head is worth.
It takes **no** `target is me` guard, because a zone master is a global witness
that wants to hear every death; it guards instead on a ledgered name and a player
killer, and pays out of its own escrow:

```text
@set bounty board/on_death = '''
led = V('ledger') or []
nm = name(target) if target else ''
pot = sum(e[1] for e in led if e[0] == nm)
if pot and enactor and has_tag(enactor, 'player'):  # right head, killed by a player
    transfer_credits(me, enactor, pot)
    set_attr(me, 'ledger', [e for e in led if e[0] != nm])
    act(me, 'BOUNTY CLAIMED: ' + name(enactor) + ' collects ' + str(pot) + ' credits for ' + nm + '.', targeting='zone')
'''
```

And a mark worth money, out in the gulch:

```text
gulch
@create Dreg Farrow
@tag Dreg Farrow = npc
@set Dreg Farrow/hp = 6
@set Dreg Farrow/max_hp = 6
@set Dreg Farrow/skill_melee = 10
@set Dreg Farrow/dodge = 0
drop Dreg Farrow
office
```

## Try it

Post a contract and stake it. The crier is zone-wide, so a hunter standing in
Rattler Gulch hears it a room away:

```text
post Dreg Farrow            -> Contract drafted on Dreg Farrow. Now stake the reward: ...
pay 60 to bounty board      -> You pay bounty board 60 credits.
                               (zone-wide) The office crier bellows: 60 credits on the head of Dreg Farrow!
bounties                    -> [WANTED] Dreg Farrow -- 60 credits.
```

Now a hunter in Rattler Gulch runs `attack Dreg Farrow` and finishes the job.
The moment the killing swing lands, before the corpse settles:

```text
BOUNTY CLAIMED: <hunter> collects 60 credits for Dreg Farrow.
```

The hunter's purse is 60 heavier, the board's escrow is empty, the ledger entry
is gone, and `bounties` reads bare again. The corpse (and whatever Dreg carried)
belongs to whoever loots first.

Poison settles the contract just the same. The board hears the death because a
`damage_over_time` tick reaches `handle_death` exactly as a sword does, and the
tick names its poisoner because `apply_effect` records whoever applied it. Dose
Dreg from the gulch, walk back to the office, and the venom collects the bounty
for you.

## Going further

- **Rescind with a cut.** A `$rescind *` that refunds the poster minus a small
  office fee, so the board keeps its till honest either way.
- **Dead-or-alive.** Pay full on `adata('fatal')` and half otherwise, since a
  mark dragged in breathing is worth less than a corpse and the event already
  tells you which you have. The [non-lethal takedowns](112_nonlethal_takedowns.md)
  make the capture possible.
- **Player marks.** The ledger already takes any name, and `target` names players
  as readily as NPCs; the only asymmetry left is `adata('fatal')`, which is False
  for a player, because a player "death" is an unconscious body on the floor.
- **Wanted posters.** A `script_ticker` that re-bellows the top contract every
  few minutes, plus a `@detail` on the board for each entry (see
  [room details](042_room_details.md)).
- **Credit the thrower.** A softcode `damage()` kill credits the scripted object,
  so if you want a trap's owner paid instead, pass it yourself with
  `apply_effect(..., source_id=enactor.id)`, or have the throwing verb call
  `damage()` so its executor is the thrower.
```
