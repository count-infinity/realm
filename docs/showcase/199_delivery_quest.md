# 199. Delivery quest

> Checklist item 199 — [now] — *ON_RECEIVE verification, deadline timestamps, failure states*

**What you'll build:** the simplest quest done properly — Postmaster Vane
hands you sealed orders and a five-minute clock; carry them across town to
the Harbor Agent in time and you're paid, hand them over late and they're
refused and pushed back into your hands.

**Concepts:** the fetch/carry template; **verification riding `give` +
`ON_RECEIVE`** (the hand-in *is* the proof); a **deadline as a `now()`
timestamp** on the carrier; an explicit **failure state** (stale orders);
the create-into-room-then-hand-over idiom (working around the
create-into-player gap).

## How it works

A delivery quest is a triangle: a giver, a carrier item, and a recipient
who verifies. REALM's `give` already fires the recipient's `ON_RECEIVE`
*after* the item lands in their hands, and it accepts NPC recipients — so
the recipient's hook is the natural verification point. The
[job board](094_job_board.md) proves the paid-delivery pattern; this
tutorial adds the two things that make it a *quest*: a clock and a failure
branch.

Three design points:

- **The clock is a timestamp on the player.** Accepting the job stamps
  `deliver_by = now() + 300` onto the carrier. No timer object, no ticker
  in the common path — the deadline is just a number compared against
  `now()` at hand-in. (`now()` is epoch seconds; arithmetic, not
  scheduling, does the work — same clock as the [motion sensor](055_motion_sensor.md).)
- **Verification is the recipient's `ON_RECEIVE`.** The Harbor Agent keeps
  nothing, so whatever is in his hands *is* the delivery. The hook gets no
  payload (the standard event-trigger limit), but it doesn't need one: it
  reads its own contents for an `orders`-tagged item and checks the
  giver's `deliver_by` against `now()`.
- **Failure is a real branch, not silence.** On time → pay and consume the
  orders. Late → refuse and `teleport_obj` them straight back, because an
  interface that quietly swallowed a failed delivery would be a theft bug.
  Either way the deadline is cleared so the quest resets cleanly.

One engine note: `create_obj(location=<player>)` returns `None` (a known
gap — you can't mint straight into a player's hands). So Vane mints the
orders into the *room* and then `teleport_obj`s them to you — the standard
two-step for "hand a player a fresh item".

## Build it

Stand in the post office. Postmaster Vane, the giver — his `courier job`
verb refuses if you already carry orders, else mints them into the room
and presses them into your hands with the clock running:

```text
@create Postmaster Vane
@tag Postmaster Vane = npc
drop Postmaster Vane
@set Postmaster Vane/cmd_job = $courier job:has = get_attr(enactor, 'deliver_by', 0) > now(); pemit(enactor, 'You already carry sealed orders.') if has else [(set_attr(enactor, 'deliver_by', now() + 300), teleport_obj(o, enactor), pemit(enactor, 'Vane presses sealed orders into your hands. Deliver them to the Harbor Agent before they go stale.')) for o in [create_obj('sealed orders', ['thing', 'orders'], location=here)] if o]
```

The destination and the recipient. The Harbor Agent's `ON_RECEIVE` is the
whole verifier — on-time pays 60 credits and consumes the orders; stale
refuses and shoves them back:

```text
@dig The Harbor Office = harbor, back
harbor
@create Harbor Agent
@tag Harbor Agent = npc
drop Harbor Agent
@set Harbor Agent/on_receive = it = ([o for o in contents(me) if has_tag(o, 'orders')] or [None])[0]; ontime = get_attr(enactor, 'deliver_by', 0) > now(); (None if it is None else ((set_attr(enactor, 'deliver_by', 0), destroy_obj(it), adjust_credits(enactor, 60), say('The orders, at last. Sixty credits for your trouble.')) if ontime else (set_attr(enactor, 'deliver_by', 0), teleport_obj(it, enactor), say('These orders are stale. I cannot accept them.'))))
back
```

## Try it

As Raven, in the post office:

```text
courier job                          -> Vane presses sealed orders into your hands...
courier job                          -> You already carry sealed orders.
harbor
give sealed orders to Harbor Agent   -> Harbor Agent says, "The orders, at last. Sixty credits for your trouble."
```

Sixty credits richer, the orders consumed. Now the failure state: take a
fresh job and let the clock run out (or, to see it now, a builder can
`@set Raven/deliver_by = 1` to force the deadline past). Hand them in and
the Agent pushes them straight back:

```text
give sealed orders to Harbor Agent   -> Harbor Agent says, "These orders are stale. I cannot accept them."
```

The orders are back in your inventory, unpaid — a failed quest you can
still see in your hands.

## Going further

- **A visible countdown.** Put a `[[...]]` block on the orders' desc that
  reads `get_attr(loc(me), 'deliver_by', 0) - now()` and shows the seconds
  left — the [flashlight](006_flashlight.md) battery meter, pointed at a
  deadline.
- **Auto-void on expiry.** Give Vane a `script_ticker` whose `on_tick`
  sweeps `search_world(attr='deliver_by')` for players past their deadline,
  clears the attr, and pages them "your orders have expired" — the same
  sweep the [auction house](089_auction_house.md) runs on stale lots.
- **Escrowed reward.** Fund the Agent up front and pay by
  `transfer_credits` instead of minting, so the wage can't bounce (the job
  board's "money in the house before the promise" rule).
- **Chain it.** Make the Agent's success branch call the
  [Quest Warden](198_quest_framework.md)'s `advance` — the delivery
  becomes one stage of a longer quest line.
