# 114. Bounty board

> Checklist item 114 — [now] — *ON_DEATH verification, escrow payouts*

**What you'll build:** A bounty office for the badlands: anyone can
post a contract on a name and stake credits into the board; the board —
a **zone master** — hears every death in the zone, verifies the claim
(right head, player killer), and pays the hunter on the spot.

**Concepts:** zone masters as verification witnesses (`ON_DEATH` over a
whole zone, item 71's law pattern), escrow via the `pay` command +
`ON_PAYMENT` (reading the stake with `adata('amount')`), the death
event's `target` as the victim of record, a ledger as a list attribute,
and `act(..., targeting='zone')` for zone-wide criers.

## How it works

1. **Posting is two deliberate steps.** `post <name>` drafts a contract
   (a `pending_<poster>` attr), then the poster stakes it with the
   ordinary `pay` command — softcode cannot *take* a mortal's money, so
   the poster hands it over, and the board's `ON_PAYMENT` fires with
   the payer as `enactor`, the payee as `target`, and the stake as
   `adata('amount')`. The staked credits physically sit **on the board
   object**: that is the escrow. The ledger itself is a list of
   `[name, pot]` pairs (paying the same name again fattens the pot), and
   the crier announces each contract zone-wide with
   `act(me, ..., targeting='zone')`.

   **The `if target == me` guard matters double here.** `ON_PAYMENT` is
   a witnessed event — it fires on every object that can hear it — and a
   zone master hears *the whole zone*. Without the test, buying a drink
   in Rattler Gulch would fire the board's payment hook two rooms away,
   eat the buyer's pending draft and post a contract for nothing.
   `enactor` is who paid; `target` is who was **paid**; a master with an
   ear that wide had better check the second one.
   ([Item 108](108_casino_floor.md) has the general rule.)

2. **Verification is witnessing, not trust.** The board is crowned
   `@zone/master` over `badlands`, so events in *every* badlands room
   reach its `ON_<EVENT>` attributes — item 71 used this to dispatch
   the watch; here it is the claims adjuster. A death propagates
   `combat:on_death` with the **killer as `enactor`** and the
   **victim as `target`**: the board reads the name off the corpse-to-be
   and checks it against the ledger. Right head + player killer = pay
   `transfer_credits(me, enactor, pot)`, strike the entry, and the crier
   announces the claim. No `$claim` command exists to lie to — the only
   way onto the ledger's payout line is to actually be the reason
   something died.

3. **What the board hears — and what it still cannot.** The board used to
   be deaf to everything but a combat swing: `combat:on_death` propagated
   only from `CombatSystem.attack`, so a mark killed by softcode
   `damage()` (item 111's grenade) or a `damage_over_time` effect died
   with the board none the wiser. That is **fixed** — the announcement
   now lives in `CombatManager.handle_death`, which *every* route
   reaches, and the board hears all of them.

   Hearing is not the same as being able to pay — the **killer** has to
   survive the indirect routes too, and now does for effects:
   `apply_effect` stamps whoever applied it, so a poison tick names its
   poisoner and the contract settles. One route still attributes
   loosely: a softcode `damage()` kill names the *scripted object* that
   dealt the blow — the grenade, the dart trap — rather than the hand
   that threw it, which is arguably honest (the grenade did kill you)
   but means a thrown-weapon bounty credits the weapon. `target` is
   always right, so the board always knows *who died*. The build is
   written to fail closed rather than pay
   the wrong purse.

4. **Dead, or merely down.** `adata('fatal')` is True for a real death —
   an NPC becoming a corpse — and False for a **player** knocked
   unconscious in place, because players do not die. The board pays on
   either (a mark is a mark), but that one boolean is what a
   dead-or-alive office would branch on; see Going further.

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
@set bounty board/on_payment = paid = adata('amount', 0) if target == me else 0; nm = V('pending_' + enactor.id, ''); led = V('ledger') or []; pot = paid + sum(e[1] for e in led if e[0] == nm); (None if not paid else (pemit(enactor, 'Draft a contract first: POST <name>.') if not nm else (set_attr(me, 'ledger', [e for e in led if e[0] != nm] + [[nm, pot]]), del_attr(me, 'pending_' + enactor.id), act(me, 'The office crier bellows: ' + str(pot) + ' credits on the head of ' + nm + '!', targeting='zone'))))
@set bounty board/cmd_bounties = $bounties: led = V('ledger') or []; (pemit(enactor, 'The board is bare. The badlands sleep easy.') if not led else [pemit(enactor, '[WANTED] ' + e[0] + ' -- ' + str(e[1]) + ' credits.') for e in led])
@set bounty board/on_death = led = V('ledger') or []; nm = name(target) if target else ''; pot = sum(e[1] for e in led if e[0] == nm); (None if not (pot and enactor and has_tag(enactor, 'player')) else (transfer_credits(me, enactor, pot), set_attr(me, 'ledger', [e for e in led if e[0] != nm]), act(me, 'BOUNTY CLAIMED: ' + name(enactor) + ' collects ' + str(pot) + ' credits for ' + nm + '.', targeting='zone')))
```

The `on_death` hook is the whole verification, and it is four names
long: `target` is who died, `enactor` is who killed them, the ledger
says what that head is worth. It used to sweep `contents(here)` for
bodies at 0 HP whose names matched — because the hook could not see its
own event's victim, only the room it happened in. It can now, so the
sweep is gone, and with it the sweep's quiet bug: a mark whose corpse
was carried off, or who died as the last object to leave the room, paid
nobody.

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

Poison a mark and the contract settles just the same. The board *hears*
the death — a `damage_over_time` tick reaches it exactly as a sword
through the chest does — and the tick names its poisoner, because
`apply_effect` records whoever applied it. Dose Dreg from the gulch,
walk back to the office, and the venom collects your bounty for you.

**~~Engine gap~~ — closed 2026-07-17.** `combat:on_death` used to carry no
killer on the indirect paths: `DamageOverTimeEffect` called
`CombatManager.handle_death(obj)` without one, so `actor`/`enactor` and
`adata('killer')` were `None` for every poison, bleed and burn kill.
Anything that pays, credits or blames for a death — bounty offices, arena
purses, XP, kill records — was limited to melee swings. `apply_effect` now
stamps `source_id` with its executor and the effect carries that through to
`handle_death`, so effects name their instigator.

One route still attributes loosely, by design rather than omission:
softcode `damage()` names the *scripted object* that dealt the blow (the
grenade, the dart trap) rather than the hand that threw it. For a bounty
that means a thrown-weapon kill credits the weapon. Whether that is a bug
or the truth is a design question — the grenade *did* kill you — so if you
want the thrower credited, pass it yourself: `apply_effect(..., source_id=
enactor.id)` on a trap, or have the throwing verb do the `damage()` so its
executor is the thrower.

(The three gaps this tutorial once listed — swing-path-only deaths, a hook
that could not name its own victim, and a killerless poison — were all
closed on 2026-07-17.)

## Going further

- **Rescind with a cut** — a `$rescind *` that refunds the poster
  minus a 10% office fee (the board keeps its till honest either way).
- **Dead-or-alive** — pay full on `adata('fatal')` and half otherwise:
  a mark dragged in breathing is worth less than a corpse, and the
  event already tells you which you have. (Item 112's binders make the
  capture possible.)
- **Player marks** — the ledger already takes any name, and `target`
  names players as readily as NPCs; the only asymmetry left is
  `adata('fatal')`, which is False for them, because a player "death"
  is an unconscious body on the floor.
- **Wanted posters** — a `script_ticker` that re-bellows the top
  contract every few minutes, and `@detail`s on the board for each
  entry (item 42).
