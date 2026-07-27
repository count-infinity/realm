# 163. Vehicle fuel

> Checklist item 163 ([now]): *a consumable resource on the drivable rover, a low-fuel warning, running dry, refuel by payment*

**What you'll build:** The [drivable rover](155_drivable_vehicle.md) with
a tank. Every `drive` burns a unit, a warning light blinks when you are
nearly empty, and running dry stalls the engine until you `pay` a fuel
pump to fill up. Strand yourself out on the flats and you learn to watch
the gauge.

**Concepts:** a **consumable attribute** decremented per action; a
**guard** that refuses the move at zero; refuelling as the built-in
`pay` plus [`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks)
([tutorial 030](030_toll_gate.md)), because a pump pays out while a
player pays in; and reading the event itself with
[`adata('amount')`](../reference/softcode.md#event-data-namespace) and
[`target`](../reference/softcode.md#guard-on-target).

## How it works

The finished rover is the cab room from [tutorial 155](155_drivable_vehicle.md)
with one extra number on it, a `fuel` attribute, plus a pump parked at
the depot. This section answers three questions: where the fuel lives and
when it drops, why refuelling runs from the player toward the pump rather
than the reverse, and how the pump tells a payment meant for it from one
meant for the vending machine beside it.

**Where does the fuel live, and when does it drop?** The rover is a cab
room with a moving `board` exit and a relinkable `hatch`, exactly as
[tutorial 155](155_drivable_vehicle.md) built it. Fuel is a single number
on the cab, a `fuel` attribute with a `fuel_max` cap. The `$drive`
command gains one branch: refuse with a dead-engine message when
`fuel <= 0`, otherwise make the move and write `fuel - 1` back with
[`set_attr`](../reference/softcode.md#fn-set_attr). The blink of
"LOW FUEL" when the tank hits one unit is a conditional
[`remit`](../reference/softcode.md#fn-remit). The tank is data, and the
warning is a comparison.

**Why does refuelling run from the player to the pump?** A pump is
builder-owned, so it may set the rover's fuel freely, and
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits) moves
money only FROM something its executor controls. The pump controls its
own purse but not a player's, so the transaction runs the other way: you
`pay 20 to fuel pump`, the built-in `pay` moves the money and fires the
pump's [`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks). The hook
converts credits to fuel at its price, tops the tank up to the cap, and
hands back any change with `transfer_credits`, which it is free to do
because that is its own money going out. The rover has to be parked at
the pump, or your credits are returned.

**How does the pump know how much was paid?** An `ON_<EVENT>` hook is
handed the action's payload, and a payment's payload is the sum paid, so
the pump reads it with
[`adata('amount')`](../reference/softcode.md#event-data-namespace). That
one call is the exact figure that landed, which is all the pump's
arithmetic needs.

**How does the pump know the payment was for it?** An `ON_PAYMENT` fires
on every object in the room, not only on the till that got the money. Pay
the vending machine next to the pump and the pump's hook still runs, with
the vending machine's `amount` in the payload. So the hook opens by
checking [`target is me`](../reference/softcode.md#guard-on-target):
`target` is the object the payment was aimed at, and comparing it by
identity to `me` separates "I was paid" from "someone near me was paid".
Write it as `target is me`, not `target == me`, since it is an identity
check. Without the guard the pump would read the vending machine's amount
and dispense free fuel.

**Running dry is a real stall.** The pump lives at the depot, so emptying
the tank out on the flats leaves you stranded: you walk, or someone
brings you fuel. That consequence is the whole point of a gauge.

## Build it

A depot with a stretch of flats to burn fuel on, and the rover dug from
the depot so its `board` exit parks there, wired like
[155](155_drivable_vehicle.md):

```text
@dig The Depot
@teleport me = The Depot
@dig The Flats = north, south
@dig The Rover = board, hatch
@teleport me = The Rover
```

The wiring hands the cab handles to both of its exits and its starting
berth, then fills the new `fuel` and `fuel_max` attributes. This is
one-shot builder setup, so it stays a single `@eval`:

```text
@eval cab=here; hatch=[e for e in contents(cab) if has_tag(e,'exit') and name(e)=='hatch'][0]; board=[o for o in search_world(name='board') if has_tag(o,'exit')][0]; set_attr(cab,'hatch','#'+hatch.id); set_attr(cab,'board','#'+board.id); set_attr(cab,'parked_at', str(get_attr(hatch,'destination'))); set_attr(cab,'fuel', 2); set_attr(cab,'fuel_max', 6); result='wired'
```

The dashboard rides in the cab. Create it and drop it so it hears
commands from the seat:

```text
@create dashboard
@desc dashboard = A steering yoke, a throttle, and a fuel gauge. DRIVE <direction>; FUEL to read the tank.
drop dashboard
```

`$drive` reads the parked room's exit the way the rover always did, but
now it checks the tank first, burns a unit on a successful roll, and
blinks the warning light when a single unit is left. It reads the wildcard
capture as `arg0`, refuses on a dry tank or a dead direction, and
otherwise moves the rover and decrements `fuel`:

```text
@set dashboard/cmd_drive = '''
$drive *:
way = trim(arg0).lower()
cab = here
fuel = get_attr(cab, 'fuel', 0)
outer = get('#' + str(get_attr(cab, 'parked_at')))
ex = [e for e in contents(outer) if has_tag(e, 'exit') and name(e) == way]
dest = get('#' + str(get_attr(ex[0], 'destination'))) if ex else None
if fuel <= 0:
    pemit(enactor, 'The tank is dry. The engine coughs and dies.')
elif dest is None:
    pemit(enactor, f'The rover cannot roll {way} from here.')
else:
    burned = fuel - 1
    remit(outer, f'The rover grinds {way} and rolls out of sight.')
    teleport_obj(get(get_attr(cab, 'board')), dest)
    set_attr(get(get_attr(cab, 'hatch')), 'destination', dest.id)
    set_attr(cab, 'parked_at', dest.id)
    set_attr(cab, 'fuel', burned)
    remit(dest, 'A dusty rover rolls in and settles, engine ticking.')
    remit(cab, f'The cab lurches {way}. Fuel gauge reads {burned}.')
    if burned == 1:  # exactly one unit left: blink the low-fuel light
        remit(cab, 'A warning light blinks: LOW FUEL.')
'''
```

`$fuel` reads the gauge from the seat. It is a single message, so it stays
a one-liner:

```text
@set dashboard/cmd_fuel = $fuel: pemit(enactor, f"Fuel gauge: {get_attr(here, 'fuel', 0)}/{get_attr(here, 'fuel_max', 0)}.")
```

The pump at the depot. Create it, drop it, and set its price as a plain
data attribute:

```text
@teleport me = The Depot
@create fuel pump
@desc fuel pump = A grimy autopump. PAY <credits> TO FUEL PUMP while parked here (5 cr/unit).
drop fuel pump
@set fuel pump/price = 5
```

The `ON_PAYMENT` hook fills the tank. It opens with the `target is me`
guard so a payment made to something else nearby is ignored, refuses when
the rover is parked elsewhere by handing the whole payment straight back,
and otherwise buys as many units as the money and the tank's headroom
allow, refunding any overpay:

```text
@set fuel pump/on_payment = '''
if target is me:  # ON_PAYMENT fires on EVERY object in the room, so guard it
    paid = adata('amount', 0)
    price = V('price', 5)
    cab = get('The Rover')
    if str(get_attr(cab, 'parked_at')) != loc(me).id:
        transfer_credits(me, enactor, paid)  # rover elsewhere: hand the whole payment back
        pemit(enactor, 'The rover is not parked at the pump; your credits are returned.')
    else:
        room = get_attr(cab, 'fuel_max', 6) - get_attr(cab, 'fuel', 0)
        bought = min(paid // price, room)
        refund = paid - bought * price
        set_attr(cab, 'fuel', get_attr(cab, 'fuel', 0) + bought)
        if refund > 0:
            transfer_credits(me, enactor, refund)  # overpaid past the cap: return the difference
        tank = get_attr(cab, 'fuel')
        change = f' Change: {refund} cr.' if refund > 0 else ''
        pemit(enactor, f'The pump chatters: {bought} units aboard, tank now {tank}.{change}')
'''
@teleport me = The Depot
```

## Try it

With two units in the tank:

```text
board               -> into The Rover
drive north         -> "...Fuel gauge reads 1." "A warning light blinks: LOW FUEL."
drive south         -> back at the depot; the gauge reads 0
drive north         -> "The tank is dry. The engine coughs and dies."
```

You are stranded, but you rolled back to the depot first, so hop out and
buy fuel:

```text
hatch               -> out at The Depot
pay 20 to fuel pump -> "The pump chatters: 4 units aboard, tank now 4."
```

`fuel` from the seat reads the gauge any time. Try `pay` while the rover
is parked elsewhere and your credits come straight back. Overpay past the
tank's cap and the pump refunds the difference: pay 50 into a tank sitting
at two units, the pump buys the four units of headroom for twenty credits,
and thirty come back as change, because
[`adata('amount')`](../reference/softcode.md#event-data-namespace) told it
exactly what landed.

## Going further

- **A jerry can:** a carriable object with its own `fuel` and a `$pour`
  command that moves units into a parked rover, so a roadside rescue
  becomes a reason to keep one in the back.
- **Mileage as terrain:** charge two units for an uphill
  [climbing](034_climbing_exit.md) exit and one on the flat by reading a
  `cost` attribute off the outer exit before decrementing.
- **Gauge on the outside:** stamp the fuel level into the rover's
  push-on-change `sitrep` ([tutorial 155](155_drivable_vehicle.md)) so a
  mechanic reads the tank without boarding.
- **Electric range:** rename `fuel` to `charge` and let it trickle back
  up on a `script_ticker` while parked at a depot pad, so refuelling costs
  time instead of credits.
