# 137. Hunger & Thirst

> Checklist item 137 ([now]): *on_tick survival meters, consumable reset, zone-policy toggle*

**What you'll build:** a life-support monitor that watches a station and, every
tick, drains each occupant's hunger and thirst meters, warning them as the
needles drop and leaving them faint (a -2 condition) when either hits zero, plus
a mess-hall dispenser whose ration pack fills them back up. These are survival
meters that exist only where you switch them on.

**Concepts:** a [`script_ticker`](../reference/softcode.md#npcs-behaviors) on a
**master object** as a per-zone clock, why draining another player's meters (and
clearing their penalty) needs **owner authority** (an admin-owned master, the
[069](069_trainer_npc.md) rule), [`zone_rooms()`](../reference/softcode.md#fn-zone_rooms)
to scope the effect to one station, and a consumable `$`-command as the reset.

## How it works

The finished shape is one wall panel and one galley unit. The panel carries a
ticker that, every beat, walks the station's rooms and shaves a little off each
crewman's hunger and thirst; the galley refills them on the word `eat`. Meters
are ordinary attributes, so the whole policy lives in `@set`-able values, and the
sweep is scoped to a zone, so the rules apply exactly where you tag rooms in.
This section answers four questions: where the numbers live, how you turn the
system on for one area, why the panel is allowed to edit other players, and what
running out actually costs.

### Where do the meters live?

Hunger and thirst are just `db.hunger` and `db.thirst` numbers on a character. A
single monitor object carries the `script_ticker` behavior, and each tick its
[`on_tick`](../reference/softcode.md#lifecycle-hooks) script sweeps every player
in the station's rooms and decrements them. Scheduling rides the server's one
heartbeat, while the policy (how fast, how loud, at what threshold you weaken)
is all in attributes you can edit at the prompt.

### How do you turn it on for one area?

The sweep runs over [`zone_rooms('station')`](../reference/softcode.md#fn-zone_rooms),
so meters exist exactly where you tag rooms into that zone and nowhere else. A
safe hub, a downtime lounge, a whole planet with no survival rules: leave it
unzoned. Run one monitor per survival zone, and a room you never zone never
starves anyone.

### Why is the panel allowed to edit other players?

The monitor *mutates other players*: [`set_attr`](../reference/softcode.md#fn-set_attr)
on their `hunger`, [`add_tag`](../reference/softcode.md#fn-add_tag) for
`starving`, and edits to their `check_mods`. Softcode may do that only if the
executor [`controls()`](../reference/softcode.md#fn-controls) the target, and
nobody controls a player except an **admin**. So the monitor (and the dispenser,
which resets those same fields) must be **admin-owned**, the identical authority
wall the trainer hits in [069](069_trainer_npc.md). An owned object acts with its
owner's authority, so an admin-owned master reaches every player's sheet. This is
also why it is a central master and not a gadget in each player's pack: a
proximity effect reaches only its own room, while the master's control authority
reaches across the whole station.

### What does running out cost?

At zero, the master merges a `{'starving': {'all': -2}}` entry into the victim's
`check_mods` and tags them `starving`. That -2 folds into every
[`skill_check()`](../reference/softcode.md#fn-skill_check) exactly like an injury
([135](135_injury_treatment.md)), because the check engine sums every entry's
`'all'` value before the roll. Hunger stops being flavor text and makes you worse
at everything until you eat.

## Build it

As your admin character, dig the station with both rooms zoned so the sweep finds
them, then create the monitor and give it a one-beat ticker:

```text
@dig The Mess Deck = mess, out
mess
@zone here = station
@dig Cargo Hold = hold, mess
hold
@zone here = station
mess
@create life support monitor
drop life support monitor
@desc life support monitor = A wall panel of green readouts, one bar per crewman, ticking slowly downward.
@behavior life support monitor = script_ticker, interval:1
```

The ticker's `on_tick` is the sweep: for every room in the zone, for every player
standing in it, hand that player's id to the per-player drain routine. It walks
[`contents`](../reference/softcode.md#fn-contents) and keeps only objects that
[`has_tag`](../reference/softcode.md#fn-has_tag) `player`, so props and the panel
itself are skipped:

```text
@set life support monitor/on_tick = '''
for r in zone_rooms('station'):
    for p in contents(r):
        if has_tag(p, 'player'):
            eval_attr(me, 'tick_meter', p.id)
'''
```

`tick_meter` runs once per crewman. It resolves the player from the id string
with [`get`](../reference/softcode.md#fn-get), reads each meter through
[`get_attr`](../reference/softcode.md#fn-get_attr), shaves 10 off hunger and 15
off thirst (each floored at zero), then asks `assess` to react. The routines call
each other with
[`eval_attr`](../reference/softcode.md#fn-eval_attr), which runs as the caller,
so `me` stays the monitor the whole way down and its owner authority carries into
every write:

```text
@set life support monitor/tick_meter = '''
p = get('#' + arg0)
if p:
    set_attr(p, 'hunger', max(0, int(get_attr(p, 'hunger', 100)) - 10))
    set_attr(p, 'thirst', max(0, int(get_attr(p, 'thirst', 100)) - 15))
    eval_attr(me, 'assess', p.id)
'''
```

`assess` reads the new levels and picks one response: empty on either meter
weakens the crewman, otherwise a low reading (40 or under on either) prints a
warning with [`pemit`](../reference/softcode.md#fn-pemit), and a healthy reading
says nothing:

```text
@set life support monitor/assess = '''
p = get('#' + arg0)
h = int(get_attr(p, 'hunger', 100))
t = int(get_attr(p, 'thirst', 100))
if h <= 0 or t <= 0:
    eval_attr(me, 'weaken', p.id)
elif h <= 40 or t <= 40:
    pemit(p, 'Your stomach growls; your mouth is dry.')
'''
```

`weaken` applies the penalty, but only once: if the crewman is already tagged
`starving` it does nothing, so the -2 never stacks across ticks. Otherwise it
merges the `starving` entry into a copy of their `check_mods`, tags them, and
tells them:

```text
@set life support monitor/weaken = '''
p = get('#' + arg0)
if not has_tag(p, 'starving'):
    m = dict(get_attr(p, 'check_mods', {}) or {})
    m['starving'] = {'all': -2}
    add_tag(p, 'starving')
    set_attr(p, 'check_mods', m)
    pemit(p, 'You are faint from hunger and thirst. (-2 to everything)')
'''
```

Now the dispenser. Create it in the mess and describe it:

```text
@create ration dispenser
drop ration dispenser
@desc ration dispenser = A humming galley unit. EAT to draw a ration pack and a water bulb.
```

Its `$eat` command tops both meters on whoever typed it, lifts the penalty
through `refresh`, and [`remit`](../reference/softcode.md#fn-remit)s to the room
using the eater's [`loc`](../reference/softcode.md#fn-loc) and
[`name`](../reference/softcode.md#fn-name). A `$`-command runs only on the
dispenser that matched the word, and `enactor` is the eater, so no room guard is
needed:

```text
@set ration dispenser/cmd_eat = '''
$eat:
set_attr(enactor, 'hunger', 100)
set_attr(enactor, 'thirst', 100)
eval_attr(me, 'refresh', enactor.id)
remit(loc(enactor), name(enactor) + ' tears into a ration pack and drains a water bulb.')
'''
```

`refresh` reverses `weaken`: it drops the `starving` entry from the eater's
`check_mods` and [`removes the tag`](../reference/softcode.md#fn-remove_tag), so
the -2 is gone the instant they eat:

```text
@set ration dispenser/refresh = '''
p = get('#' + arg0)
m = dict(get_attr(p, 'check_mods', {}) or {})
if 'starving' in m:
    m.pop('starving')
set_attr(p, 'check_mods', m)
remove_tag(p, 'starving')
'''
```

The dispenser also needs admin ownership for the same reason the monitor does: it
writes another player's sheet. Building both as your admin character satisfies
that.

## Try it

Stand on the mess deck and let the clock run. Hunger falls 10 a tick and thirst
15 a tick from 100, so thirst empties first:

```text
(tick 4: hunger 60, thirst 40)   -> Your stomach growls; your mouth is dry.
(tick 5: hunger 50, thirst 25)   -> Your stomach growls; your mouth is dry.
(tick 7: hunger 30, thirst 0)    -> You are faint from hunger and thirst. (-2 to everything)
```

Because thirst bottoms out first, you are tagged `starving` at tick 7 and carry a
-2 that a diagnostic slate ([135](135_injury_treatment.md)) would show dragging
your rolls. Hit the galley:

```text
eat            -> Susan tears into a ration pack and drains a water bulb.
```

Both meters snap back to 100, the `starving` tag lifts, and the -2 is stripped
from your `check_mods`. Walk out of the station's zone, into an unzoned corridor,
and the monitor stops touching you entirely, because meters are a property of
*where you are*, not a law of the world.

## Going further

- **A prompt, not a UI:** stream the meters to the client each tick with
  [`oob(p, 'Char.Vitals', {'hunger': h, 'thirst': t})`](../reference/softcode.md#fn-oob),
  the GMCP surface from [193](193_gmcp_oob.md) driving a status gauge.
- **Escalating cost:** at zero, swap the flat -2 for HP damage that grows the
  longer you go without, `set_attr(p, 'hp', ...)` from the same master, since its
  control authority reaches HP too. Starvation that eventually downs you.
- **Foods with profiles:** give the dispenser several items, a stim bar that
  fills only hunger and a canteen only thirst, each a `$`-command writing one
  meter, so meal planning becomes a choice.
- **Perishable rations:** stock the dispenser from a [063](063_shopkeeper.md)
  shopkeeper and give the packs a `decay` behavior, spoiled food that fills less,
  the cooking-buffs angle of [129](129_cooking_buffs.md).
