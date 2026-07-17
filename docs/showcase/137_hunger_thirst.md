# 137. Hunger & Thirst

> Checklist item 137 — [now] — *a ticking survival master, opt-in per-zone meters, owner authority to write player sheets, consumables*

**What you'll build:** a life-support monitor that watches a station and,
every tick, drains each occupant's hunger and thirst meters — warning them
as the needles drop and leaving them **faint** (a −2 condition) when either
hits zero — plus a mess-hall dispenser whose ration pack fills them back
up. Survival meters that only exist where you switch them on.

**Concepts:** `script_ticker` on a **master object** as a per-zone clock,
why draining another player's meters (and clearing their penalty) needs
**owner authority** — an admin-owned master, the [069](069_trainer_npc.md)
rule — `zone_rooms()` to scope the effect to one station, and a consumable
`$`-command as the reset.

## How it works

1. **Meters are attributes; the master is their clock.** Hunger and thirst
   are just `db.hunger` / `db.thirst` numbers on a character. A single
   monitor object carries the `script_ticker` behavior, and each tick its
   `on_tick` sweeps every player in the station's rooms and decrements
   them. Scheduling rides the server's one heartbeat; the *policy* — how
   fast, how loud, at what threshold you weaken — is all in `@set`-able
   attributes.

2. **Opt-in by zone.** The sweep runs over `zone_rooms('station')`, so
   meters exist exactly where you tag rooms into that zone and nowhere
   else. A safe hub, a downtime lounge, a whole planet with no survival
   rules — just don't zone it. One monitor per survival zone; a room you
   never zone never starves anyone.

3. **Writing a player's sheet needs owner authority.** The monitor
   *mutates other players* — `set_attr(hunger)`, `add_tag('starving')`,
   editing their `check_mods`. Softcode may do that only if it
   `controls()` the target, and nobody controls a player but an **admin**.
   So the monitor (and the dispenser, which resets those same fields) must
   be **admin-owned** — the identical authority wall the trainer hits in
   [069](069_trainer_npc.md). This is also why it's a central master and
   not a gadget in each player's pack: proximity effects can't reach across
   the station, but an admin-owned master's control authority can.

4. **The bite is a condition.** At zero, the master merges a
   `{'starving': {'all': -2}}` entry into the victim's `check_mods` and
   tags them `starving`. That −2 folds into every `skill_check()` exactly
   like an injury ([135](135_injury_treatment.md)) — hunger doesn't just
   flavor-text at you, it makes you worse at everything until you eat.

## Build it

**As your admin character**, dig the station (both rooms zoned so the sweep
finds them) and post the monitor:

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

The sweep, and the per-player drain it fans out to:

```text
@set life support monitor/on_tick = [eval_attr(me, 'tick_meter', p.id) for r in zone_rooms('station') for p in contents(r) if has_tag(p, 'player')]
@set life support monitor/tick_meter = p = get('#' + arg0); (None if not p else (set_attr(p, 'hunger', max(0, int(get_attr(p, 'hunger', 100)) - 10)), set_attr(p, 'thirst', max(0, int(get_attr(p, 'thirst', 100)) - 15)), eval_attr(me, 'assess', p.id)))
@set life support monitor/assess = p = get('#' + arg0); h = int(get_attr(p, 'hunger', 100)); t = int(get_attr(p, 'thirst', 100)); (eval_attr(me, 'weaken', p.id) if (h <= 0 or t <= 0) else (pemit(p, 'Your stomach growls; your mouth is dry.') if (h <= 40 or t <= 40) else None))
@set life support monitor/weaken = p = get('#' + arg0); m = dict(get_attr(p, 'check_mods', {}) or {}); m['starving'] = {'all': -2}; (None if has_tag(p, 'starving') else (add_tag(p, 'starving'), set_attr(p, 'check_mods', m), pemit(p, 'You are faint from hunger and thirst. (-2 to everything)')))
```

The dispenser — a ration pack that tops both meters and lifts the penalty:

```text
@create ration dispenser
drop ration dispenser
@desc ration dispenser = A humming galley unit. EAT to draw a ration pack and a water bulb.
@set ration dispenser/cmd_eat = $eat: (set_attr(enactor, 'hunger', 100), set_attr(enactor, 'thirst', 100), eval_attr(me, 'refresh', enactor.id), remit(loc(enactor), name(enactor) + ' tears into a ration pack and drains a water bulb.'))
@set ration dispenser/refresh = p = get('#' + arg0); m = dict(get_attr(p, 'check_mods', {}) or {}); (m.pop('starving') if 'starving' in m else 0); set_attr(p, 'check_mods', m); remove_tag(p, 'starving')
```

## Try it

Stand on the mess deck and let the clock run (drain shown per tick, hunger
−10, thirst −15 from 100):

```text
(tick 4: hunger 60, thirst 40)   -> Your stomach growls; your mouth is dry.
(tick 5: hunger 50, thirst 25)   -> Your stomach growls; your mouth is dry.
(tick 7: hunger 30, thirst 0)    -> You are faint from hunger and thirst. (-2 to everything)
```

Thirst bottoms out first (it drains faster), so you're tagged `starving`
and carrying a −2 that a diagnostic slate ([135](135_injury_treatment.md))
would show dragging your rolls. Hit the galley:

```text
eat            -> Susan tears into a ration pack and drains a water bulb.
```

Both meters snap back to 100, the `starving` tag lifts, and the −2 is
stripped from your `check_mods`. Walk out of the station's zone — into an
unzoned corridor — and the monitor stops caring about you entirely: meters
are a property of *where you are*, not a law of the world.

## Going further

- **A prompt, not a UI:** stream the meters to the client with `oob(p,
  'Char.Vitals', {'hunger': h, 'thirst': t})` each tick — the GMCP surface
  from [193] driving a status gauge.
- **Escalating cost:** at zero, swap the flat −2 for HP damage that grows
  the longer you go without — `set_attr(p, 'hp', ...)` from the same master
  (control authority reaches HP too). Starvation that eventually downs you.
- **Foods with profiles:** give the dispenser several items — a stim bar
  that only fills hunger, a canteen only thirst — each a `$`-command
  writing one meter, so meal planning becomes a choice.
- **Perishable rations:** stock the dispenser from a [063](063_shopkeeper.md)
  shopkeeper and give the packs a `decay` behavior — spoiled food that
  fills less, the cooking-buffs angle of [129](129_cooking_buffs.md).
