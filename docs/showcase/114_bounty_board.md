# 114. Bounty board

> Checklist item 114 — [now] — *ON_DEATH verification, escrow payouts*

**What you'll build:** A bounty office for the badlands: anyone can
post a contract on a name and stake credits into the board; the board —
a **zone master** — hears every death in the zone, verifies the claim
(right head, player killer), and pays the hunter on the spot.

**Concepts:** zone masters as verification witnesses (`ON_DEATH` over a
whole zone, item 71's law pattern), escrow via the `pay` command +
`ON_PAYMENT` till accounting (item 64's bar tab), a capped ledger as a
list attribute, and `act(..., targeting='zone')` for zone-wide criers.

## How it works

1. **Posting is two deliberate steps.** `post <name>` drafts a contract
   (a `pending_<poster>` attr), then the poster stakes it with the
   ordinary `pay` command — softcode cannot *take* a mortal's money, so
   the poster hands it over, and the board's `ON_PAYMENT` fires with
   the payer as `enactor`. The hook cannot see the amount directly, so
   the board keeps a `till` attr and reads the delta
   (`credits(me) - till`) — item 64's bar-tab idiom. The staked credits
   physically sit **on the board object**: that is the escrow. The
   ledger itself is a list of `[name, pot]` pairs (paying the same name
   again fattens the pot), and the crier announces each contract
   zone-wide with `act(me, ..., targeting='zone')`.

2. **Verification is witnessing, not trust.** The board is crowned
   `@zone/master` over `badlands`, so events in *every* badlands room
   reach its `ON_<EVENT>` attributes — item 71 used this to dispatch
   the watch; here it is the claims adjuster. A combat kill propagates
   `combat:on_death` with the **killer as `enactor`**, and inside the
   trigger `here` is the room where it happened. The hook namespace
   carries no victim, so the board *verifies against the world*: it
   sweeps `contents(here)` for anything at 0 HP whose name is on the
   ledger — at trigger time the fallen mark is still in the room, HP
   spent, corpse not yet swept. Right head + player killer = pay
   `transfer_credits(me, enactor, pot)`, strike the entry, and the
   crier announces the claim. No `$claim` command exists to lie to.

3. **What the board cannot hear (engine gap, reported).** Only the
   combat-swing path (`CombatSystem.attack`) propagates
   `combat:on_death`. Deaths from softcode `damage()` (item 111's
   grenade) or `damage_over_time` effects (poison, bleeding) route
   through the same corpse-making death handler *without* propagating
   the event — so poisoning your mark collects no bounty. Precise gap:
   `CombatManager.handle_death` does not fire `combat:on_death`;
   `ON_DEATH` witnesses only hear swings.

## Build it

The office and the hunting ground, zoned:

```text
@dig The Bounty Office = office, out
office
@zone here = badlands
@dig Rattler Gulch = gulch, office
gulch
@zone here = badlands
office
```

The board — crowned master, then taught to take contracts:

```text
@create bounty board
drop bounty board
@desc bounty board = Sun-cracked cork and yellowed paper. POST <name> to draft a contract, then PAY this board to stake it. BOUNTIES lists what is open.
@zone/master bounty board = badlands
@set bounty board/cmd_post = $post *: set_attr(me, 'pending_' + enactor.id, trim(arg0)); pemit(enactor, 'Contract drafted on ' + trim(arg0) + '. Now stake the reward: PAY <amount> TO bounty board.')
@set bounty board/on_payment = paid = credits(me) - V('till', 0); set_attr(me, 'till', credits(me)); nm = V('pending_' + enactor.id, ''); led = V('ledger') or []; pot = paid + sum([e[1] for e in led if e[0] == nm]); (pemit(enactor, 'Draft a contract first: POST <name>.') if not nm else (set_attr(me, 'ledger', [e for e in led if e[0] != nm] + [[nm, pot]]), del_attr(me, 'pending_' + enactor.id), act(me, 'The office crier bellows: ' + str(pot) + ' credits on the head of ' + nm + '!', targeting='zone')))
@set bounty board/cmd_bounties = $bounties: led = V('ledger') or []; (pemit(enactor, 'The board is bare. The badlands sleep easy.') if not led else [pemit(enactor, '[WANTED] ' + e[0] + ' -- ' + str(e[1]) + ' credits.') for e in led])
@set bounty board/on_death = led = V('ledger') or []; heads = [o for o in contents(here) if get_attr(o, 'hp', 1) <= 0 and name(o) in [e[0] for e in led]]; pot = sum([e[1] for e in led if e[0] in [name(o) for o in heads]]); (None if not (heads and pot and enactor and has_tag(enactor, 'player')) else (transfer_credits(me, enactor, pot), set_attr(me, 'ledger', [e for e in led if e[0] not in [name(o) for o in heads]]), act(me, 'BOUNTY CLAIMED: ' + name(enactor) + ' collects ' + str(pot) + ' credits for ' + ', '.join([name(o) for o in heads]) + '.', targeting='zone')))
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

Post and stake:

```text
post Dreg Farrow            -> Contract drafted on Dreg Farrow. Now stake the reward: ...
pay 60 to bounty board      -> You pay bounty board 60 credits.
                               (zone-wide) The office crier bellows: 60 credits on the head of Dreg Farrow!
bounties                    -> [WANTED] Dreg Farrow -- 60 credits.
```

Now a hunter in Rattler Gulch — who heard the crier from there —
`attack Dreg Farrow` and finishes the job. The moment the killing swing
lands, before the corpse hits the dirt:

```text
BOUNTY CLAIMED: <hunter> collects 60 credits for Dreg Farrow.
```

The hunter's purse is 60 heavier, the board's escrow is empty, the
ledger entry is gone, and `bounties` reads bare again. The corpse (and
whatever Dreg carried) belongs to whoever loots first.

**Engine gap (reported):** `combat:on_death` propagates only from the
combat-swing path; `CombatManager.handle_death` (softcode `damage()`
kills, damage-over-time kills) creates the corpse without firing the
event, so `ON_DEATH` witnesses — this board — cannot verify poison or
grenade kills. A propagated death event on the shared path would close
it.

## Going further

- **Rescind with a cut** — a `$rescind *` that refunds the poster
  minus a 10% office fee (the board keeps its till honest either way).
- **Dead-or-alive** — pay half for a *captive*: a `$claim` that checks
  a `restrained`-tagged, living target in the office (item 112's
  binders make the capture possible).
- **Player marks** — the ledger already takes any name; note the
  asymmetry: player "deaths" leave an unconscious body, not a corpse,
  so verify with `has_tag(o, 'unconscious')` instead of `hp <= 0`.
- **Wanted posters** — a `script_ticker` that re-bellows the top
  contract every few minutes, and `@detail`s on the board for each
  entry (item 42).
