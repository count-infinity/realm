# 199. Delivery quest

> Checklist item 199 ([now]): *fetch/carry template, ON_RECEIVE verification, deadline timestamps, failure states*

**What you'll build:** the simplest quest done properly. Postmaster Vane
hands you sealed orders and a five-minute clock; carry them across town to
the Harbor Agent in time and you are paid, hand them over late and they are
refused and pushed back into your hands.

**Concepts:** the fetch/carry template; verification riding `give` plus
[`ON_RECEIVE`](../reference/softcode.md#lifecycle-hooks), where the hand-in
*is* the proof; reading
[`adata('item')`](../reference/softcode.md#event-data-namespace) and
`adata('giver')` off the event; a deadline as a
[`now()`](../reference/softcode.md#fn-now) timestamp on the courier; an
explicit failure state (stale orders) that returns the goods.

## How it works

A delivery quest is a triangle: a giver who issues the errand, a carrier
item that travels, and a recipient who verifies. Everything below hangs off
one engine fact, which is that `give` fires the *recipient's* hook and tells
that hook exactly what arrived, so the recipient is the natural place to put
the verification. This section answers three questions in turn: where the
clock lives, how the Agent knows what he was handed, and how he knows the
handover was aimed at him. The [job board](094_job_board.md) is the same
muscle pointed at open-ended paid work; a delivery quest adds a clock and a
failure branch.

### Where does the deadline live?

On the courier, as a plain number. Accepting the job stamps
`deliver_by = now() + 300` onto the player, and
[`now()`](../reference/softcode.md#fn-now) is epoch seconds, so the whole
clock is arithmetic rather than scheduling: nothing is queued, no timer
object exists, and the deadline is simply compared against `now()` again at
hand-in. The [motion sensor](055_motion_sensor.md) reads the same clock to
age its log entries.

Writing an attribute onto *another* player takes authority, and this is
where an admin-owned NPC earns its keep. Vane and the Agent are created by
an admin builder, so their scripts run with their owner's authority and may
write a courier's sheet. That is the same owner-authority rule the
[quest framework](198_quest_framework.md) relies on for stage attributes,
and it is also why Vane may mint the orders straight into the courier's
hands with
[`create_obj(..., location=enactor)`](../reference/softcode.md#fn-create_obj):
creation into a location needs control of that location, and admin
ownership supplies it. A gadget owned by an ordinary player gets `None`
back from that call and `False` from the matching
[`set_attr`](../reference/softcode.md#fn-set_attr), so staff ownership is a
requirement of this build, not a convenience.

### How does the Agent know what he was handed?

The event tells him. REALM's `give` moves the item into the recipient's
inventory and *then* fires the recipient's `ON_RECEIVE`, so by the time the
hook runs the delivery has already landed and the payload names it outright:
`adata('item')` is the thing that just arrived and `adata('giver')` is the
person who handed it over (the same object as `enactor` on this hook, since
the giver is the actor). The build reads both names because they say *why*
each is used: the orders being graded, and the courier being paid.

Reading the payload rather than rummaging through his own inventory matters.
An Agent who took `contents(me)[0]` as "the delivery" would grade the wrong
object the moment he was holding anything else, and he could be fooled by
`orders` he was already carrying. The payload does not infer; it knows.

### How does the Agent know the delivery was for him?

He checks `target`. `ON_RECEIVE` is a reactive hook, which means it fires on
*every* object in the room and not only on the recipient, so the whole body
sits under `if target is me:` (see
[Guard on `target`](../reference/softcode.md#guard-on-target) and the
[event bus tour](245_event_bus_tour.md)). Write `is` rather than `==`: the
question is whether this object *is* the recipient, which is identity, not
equality.

Skip that guard and the Agent grades handovers he never received: two other
people trading a set of orders in his office would trigger a payout and
destroy their item. The guard is the difference between "this happened to
me" and "this happened near me".

### What happens when the courier is late?

The late path is a real branch, not silence. On time, the Agent consumes the
orders with [`destroy_obj`](../reference/softcode.md#fn-destroy_obj) and pays
60 credits with
[`adjust_credits`](../reference/softcode.md#fn-adjust_credits). Late, he
refuses and puts the orders straight back into the courier's hands with
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj), because an
interface that quietly swallowed a failed delivery would be a theft bug.
Either way the deadline is cleared, which closes the job: after a refusal
`courier job` issues a fresh set of orders.

One ordering detail decides whether the branch works at all. The hook reads
the deadline into a local before clearing it, since clearing first would make
every delivery look late.

## Build it

Stand in the post office. Dig the harbor across town, then create Postmaster
Vane, the giver, and tag him `npc` so `give` will accept him as a recipient:

```text
@dig The Harbor Office = harbor, back
@create Postmaster Vane
@tag Postmaster Vane = npc
drop Postmaster Vane
```

Vane's `courier job` verb is the whole issuing side. It refuses if you are
already on the clock, and otherwise mints the orders into your hands, stamps
the deadline five minutes out, and tells you where to take them. The orders
carry an `orders` tag, which is what the Agent will grade:

```text
@set Postmaster Vane/cmd_job = '''
$courier job:
if get_attr(enactor, 'deliver_by', 0) > now():
    pemit(enactor, 'You already carry sealed orders.')
else:
    create_obj('sealed orders', ['thing', 'orders'], location=enactor)  # minting into a player needs owner authority over them
    set_attr(enactor, 'deliver_by', now() + 300)
    pemit(enactor, 'Vane presses sealed orders into your hands. Deliver them to the Harbor Agent before they go stale.')
'''
```

Walk to the harbor and create the recipient, likewise tagged `npc`:

```text
harbor
@create Harbor Agent
@tag Harbor Agent = npc
drop Harbor Agent
```

The Agent's `ON_RECEIVE` is the verifier, and it runs in five steps: gate on
the target, read the item and the giver off the event, confirm the item is
really a set of orders, decide on time against `now()`, then pay or refuse.
[`pemit`](../reference/softcode.md#fn-pemit) is not needed here because the
Agent answers out loud with the
[`say` script command](../reference/softcode.md#script-commands-simple-scripts-cmd-output-lines),
which the whole room hears:

```text
@set Harbor Agent/on_receive = '''
if target is me:  # ON_RECEIVE fires on every object in the room, so gate on the target
    orders = adata('item')  # the payload names the delivery; inferring it from contents(me) grades the wrong thing
    courier = adata('giver')
    if orders and courier and has_tag(orders, 'orders'):
        ontime = get_attr(courier, 'deliver_by', 0) > now()  # read the deadline before clearing it
        set_attr(courier, 'deliver_by', 0)
        if ontime:
            destroy_obj(orders)
            adjust_credits(courier, 60)
            say('The orders, at last. Sixty credits for your trouble.')
        else:
            teleport_obj(orders, courier)
            say('These orders are stale. I cannot accept them.')
'''
```

Head back to the post office, and the round trip is ready to run:

```text
back
```

([`has_tag`](../reference/softcode.md#fn-has_tag) is the tag test, and
[`get_attr`](../reference/softcode.md#fn-get_attr) reads an attribute off
another object with a default.)

## Try it

As Raven, standing in the post office:

```text
> courier job
Vane presses sealed orders into your hands. Deliver them to the Harbor Agent before they go stale.

> courier job
You already carry sealed orders.

> harbor
You leave harbor.

The Harbor Office
-----------------

You see:
  Harbor Agent

Exits: back

> give sealed orders to Harbor Agent
You give a sealed orders to Harbor Agent.
Harbor Agent says, "The orders, at last. Sixty credits for your trouble."
```

Confirm two things deliberately: `credits` reads sixty higher, and
`inventory` shows the orders gone, because the Agent consumed them.
`@examine Raven` shows `deliver_by = 0`, so the job is closed.

Now the failure state. Take a fresh job and let the clock run out, or force
it as a builder with `@set Raven/deliver_by = 1`, which puts the deadline in
1970. Hand the orders in and the Agent pushes them back:

```text
> give sealed orders to Harbor Agent
You give a sealed orders to Harbor Agent.
Harbor Agent says, "These orders are stale. I cannot accept them."
```

The orders are in your inventory again and unpaid, which is a failed quest
you can still see in your hands. The guard is worth testing too: with a
bystander standing in the office, `give sealed orders to <bystander>` gets
you nothing at all from the Agent, and your `deliver_by` stays set, so the
quest is still open.

## Going further

- **A visible countdown.** Put a `[[...]]` block on the orders' description
  that reads [`get_attr`](../reference/softcode.md#fn-get_attr)`(`[`loc(me)`](../reference/softcode.md#fn-loc)`, 'deliver_by', 0) - now()`
  and prints the seconds left, which is the [flashlight](006_flashlight.md)
  battery meter pointed at a deadline.
- **Auto-void on expiry.** Give Vane a `script_ticker` behavior whose
  `on_tick` sweeps
  [`search_world(attr='deliver_by')`](../reference/softcode.md#fn-search_world)
  for couriers past their deadline, clears the attribute, and `pemit`s them
  that the orders have expired, which is the same sweep the
  [auction house](089_auction_house.md) runs over stale lots.
- **Burn the stale orders.** Have the refusal branch `destroy_obj` the
  orders instead of returning them, so a missed deadline costs the courier
  the parcel and the post office has to reissue.
- **Escrowed reward.** Fund the Agent up front and pay with
  [`transfer_credits`](../reference/softcode.md#fn-transfer_credits) instead
  of minting fresh money, so the wage comes out of a purse that can run dry
  (the job board's rule of money in the house before the promise).
- **Chain it.** Point the Agent's success branch at the
  [Quest Warden](198_quest_framework.md)'s `advance` routine and the
  delivery becomes one stage of a longer quest line, in the same way
  [collection counters](200_collection_counters.md) ride `ON_GET`.
