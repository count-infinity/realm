# 163. Vehicle fuel

> Checklist item 163 — now — *a consumable resource on the drivable rover, a low-fuel warning, running dry, refuel by payment*

**What you'll build:** The [drivable rover](155_drivable_vehicle.md) with
a tank. Every `drive` burns a unit; a warning light blinks when you're
nearly empty; run dry and the engine won't catch until you `pay` a fuel
pump to fill up. Strand yourself out on the flats and you'll learn to
watch the gauge.

**Concepts:** a **consumable attribute** decremented per action; a
**guard** that refuses the move at zero; refuelling as the built-in
`pay` + `ON_PAYMENT` **till-delta** ([tutorial 030](030_toll_gate.md)),
because a pump can't reach into a player's purse — the player pays it.

## How it works

**Fuel is one number on the cab.** The rover from
[tutorial 155](155_drivable_vehicle.md) is a cab room with a moving
`board` exit and a relinkable `hatch`. Add a `fuel` attribute and one
line to `drive`: refuse with a dead-engine message when `fuel <= 0`,
otherwise do the move and `fuel - 1`. A blink of "LOW FUEL" when the tank
hits one unit is just a conditional `remit`. The tank is data; the
warning is a comparison.

**Refuelling has to be player-initiated.** A pump is builder-owned; it
can *set* the rover's fuel freely, but it can't take a credit from a
player it doesn't control. So the transaction runs the other way: you
`pay 20 to fuel pump`, the built-in `pay` moves the money and fires the
pump's `ON_PAYMENT`, and the hook reads how much arrived by the
**till-delta** (`credits(me) - till`), converts credits to fuel at its
price, tops the tank up to its cap, and hands back any change with
`transfer_credits` — which it *can* do, because it's paying out its own
money. The rover has to be parked at the pump, or your credits bounce
straight back.

**Running dry is a real stall.** The pump lives at the depot, so
emptying the tank out on the flats leaves you stranded — you walk, or
someone brings you fuel. That consequence is the whole point of a gauge.

## Build it

A depot with a stretch of flats to burn fuel on, and the rover parked at
the depot — wired like [155](155_drivable_vehicle.md), plus a tank:

```text
@dig The Depot
@teleport me = The Depot
@dig The Flats = north, south
@dig The Rover = board, hatch
@teleport me = The Rover
@eval cab=here; hatch=[e for e in contents(cab) if has_tag(e,'exit') and name(e)=='hatch'][0]; board=[o for o in search_world(name='board') if has_tag(o,'exit')][0]; set_attr(cab,'hatch','#'+hatch.id); set_attr(cab,'board','#'+board.id); set_attr(cab,'parked_at', str(get_attr(hatch,'destination'))); set_attr(cab,'fuel', 2); set_attr(cab,'fuel_max', 6); result='wired'
```

The dashboard — `drive` now checks the tank, burns a unit, and warns
when low; `fuel` reads the gauge:

```text
@create dashboard
@desc dashboard = A steering yoke, a throttle, and a fuel gauge. DRIVE <direction>; FUEL to read the tank.
drop dashboard
@set dashboard/cmd_drive = $drive *: way = trim(arg0).lower(); cab = here; fuel = get_attr(cab, 'fuel', 0); outer = get('#' + str(get_attr(cab, 'parked_at'))); ex = [e for e in contents(outer) if has_tag(e, 'exit') and name(e) == way]; dest = get('#' + str(get_attr(ex[0], 'destination'))) if ex else None; (pemit(enactor, 'The tank is dry. The engine coughs and dies.') if fuel <= 0 else (pemit(enactor, 'The rover cannot roll ' + way + ' from here.') if dest is None else (remit(outer, 'The rover grinds ' + way + ' and rolls out of sight.'), teleport_obj(get(get_attr(cab, 'board')), dest), set_attr(get(get_attr(cab, 'hatch')), 'destination', dest.id), set_attr(cab, 'parked_at', dest.id), set_attr(cab, 'fuel', fuel - 1), remit(dest, 'A dusty rover rolls in and settles, engine ticking.'), remit(cab, 'The cab lurches ' + way + '. Fuel gauge reads ' + str(fuel - 1) + '.'), (remit(cab, 'A warning light blinks: LOW FUEL.') if fuel - 1 == 1 else None))))
@set dashboard/cmd_fuel = $fuel: pemit(enactor, 'Fuel gauge: ' + str(get_attr(here, 'fuel', 0)) + '/' + str(get_attr(here, 'fuel_max', 0)) + '.')
```

The pump at the depot — pay it, and its `ON_PAYMENT` fills the tank at
five credits a unit, with change:

```text
@teleport me = The Depot
@create fuel pump
@desc fuel pump = A grimy autopump. PAY <credits> TO FUEL PUMP while parked here (5 cr/unit).
drop fuel pump
@set fuel pump/price = 5
@set fuel pump/on_payment = price = V('price', 5); till = V('till', 0); paid = credits(me) - till; set_attr(me, 'till', credits(me)); cab = get('The Rover'); room = get_attr(cab, 'fuel_max', 6) - get_attr(cab, 'fuel', 0); bought = min(paid // price, room); refund = paid - bought * price; (transfer_credits(me, enactor, paid), set_attr(me, 'till', credits(me)), pemit(enactor, 'The rover is not parked at the pump; your credits are returned.')) if str(get_attr(cab, 'parked_at')) != loc(me).id else (set_attr(cab, 'fuel', get_attr(cab, 'fuel', 0) + bought), (transfer_credits(me, enactor, refund), set_attr(me, 'till', credits(me))) if refund > 0 else None, pemit(enactor, 'The pump chatters: ' + str(bought) + ' units aboard, tank now ' + str(get_attr(cab, 'fuel')) + '.' + (' Change: ' + str(refund) + ' cr.' if refund > 0 else '')))
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

Stranded — but you rolled back to the depot first, so hop out and buy
fuel:

```text
hatch               -> out at The Depot
pay 20 to fuel pump -> "The pump chatters: 4 units aboard, tank now 4."
```

`fuel` from the seat reads the gauge any time. Try `pay` while the rover
is parked elsewhere — your credits come straight back. Overpay past the
tank's cap and the pump refunds the difference (the till-delta keeps the
books honest).

## Going further

- **A jerry can:** a carriable object with its own `fuel`; a `$pour`
  command that moves units into a parked rover — roadside rescue, and a
  reason to keep one in the back.
- **Mileage as terrain:** charge two units for an uphill
  [climbing](034_climbing_exit.md) exit, one on the flat — read a `cost`
  attribute off the outer exit before decrementing.
- **Gauge on the outside:** stamp the fuel level into the rover's
  push-on-change `sitrep` ([tutorial 155](155_drivable_vehicle.md)) so a
  mechanic can read the tank without boarding.
- **Electric range:** rename `fuel` to `charge` and let it trickle back
  up on a `script_ticker` while parked at a depot pad — refuelling that
  costs time instead of credits.
