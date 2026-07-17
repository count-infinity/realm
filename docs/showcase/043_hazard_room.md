# 043. Hazard room

> Checklist item 43 — [now] — *on_tick damage, HT resistance, zone-master severity*

**What you'll build:** A reactor gallery that cooks its occupants — a
periodic HT-based fortitude roll, 1d6 radiation damage on a failure,
and a severity dial on the zone master that every hazard room in the
zone reads.

**Concepts:** room `script_ticker` sweeps, resisted damage
(`skill_check` + `damage()`), skills as data (`skill_def`), zone
masters as policy holders, `[[...]]` descs reading shared severity.

## How it works

This is the underwater room's skeleton ([tutorial 039](039_underwater_room.md))
with the meter removed and a *policy dial* added:

1. **The resistance roll is data.** GURPS resists radiation with HT: a
   `skill_def` named `fortitude` with `stat = health, penalty = 0`
   plus `@reload` makes `skill_check(o, 'fortitude', -sv)` a HT roll
   at minus the severity — the identical move the gas bomb made for
   its gas ([tutorial 048](048_gas_bomb.md)). If you built that
   tutorial in this world, the skill already exists; re-creating it
   just shadows the same name.

2. **The room sweeps itself.** A `script_ticker` on the room runs
   `on_tick` over its player-tagged contents: pass and you "ride it
   out", fail and `damage(o, roll('1d6'))` lands — proximity
   authority again; a room may hurt what stands in it, and lethal
   damage routes through the real death path.

3. **Severity is zone policy.** The roll's modifier isn't on the room:
   it's `rad_level` on the **zone master**, read fresh every tick with
   `get_attr('Reactor Brain', 'rad_level', 1)`. Crank one attribute
   and every hazard room in the reactor zone worsens at once — a
   meltdown event is one `@set`. (Engine systems read master policy
   attributes the same way — `xp_multiplier` on a master changes kill
   awards zone-wide; `rad_level` is your own policy in the same slot.)

4. **The desc reads the dial too — at one remove.** Each sweep also
   stamps the severity it just used onto the room (`rad_sv`), and a
   `[[...]]` block turns *that* into a dosimeter line — fair warning
   that scales with the danger, one sweep behind the dial. The
   indirection is deliberate: the tick already reads the master (on
   its own worker stack), so the block that runs on every look stays
   a cheap local `me`-read — the push-on-change habit from
   [tutorial 036](036_weather_system.md).

## Build it

The resistance skill, as data:

```text
@create fortitude
@tag fortitude = skill_def
@set fortitude/stat = health
@set fortitude/penalty = 0
@reload
```

The zone, its master, and the severity dial:

```text
@dig Reactor Gallery = catwalk, out
catwalk
@zone here = reactor
@create Reactor Brain
@zone/master Reactor Brain = reactor
drop Reactor Brain
@set Reactor Brain/rad_level = 1
```

The warning label and the hazard sweep — every other world tick,
everyone present resists at minus the current severity, and the sweep
stamps that severity onto the room for the desc to read:

```text
@desc here = A steel catwalk rings the exposed core. The air is warm and tastes of foil. [[result = 'Your dosimeter ticks ' + ('lazily.' if V('rad_sv', 1) < 3 else 'without pause.')]]
@set here/on_tick = sv = get_attr('Reactor Brain', 'rad_level', 1); set_attr(me, 'rad_sv', sv); [(pemit(o, 'Heat prickles across your skin; you ride it out.') if skill_check(o, 'fortitude', -sv) else (damage(o, roll('1d6')), pemit(o, 'Nausea doubles you over. The core is cooking you.'))) for o in contents(me) if has_tag(o, 'player')]
@behavior here = script_ticker, interval:2
```

## Try it

Give yourself a constitution and stand on the catwalk:

```text
@set me/health = 12
@set me/hp = 12
@set me/max_hp = 12
look
  ... Your dosimeter ticks lazily.
  Heat prickles across your skin; you ride it out.      <- HT 12 at -1: usually fine
```

Now melt something down:

```text
@set Reactor Brain/rad_level = 3
  Nausea doubles you over. The core is cooking you.     <- next sweep: HT at -3, bleeding hp
look
  ... Your dosimeter ticks without pause.               <- the sweep re-stamped the label
```

Watch your hp fall tick by tick (`points` / your prompt), and step
`out` — the sweep only touches the room's own contents, so the hazard
ends at the hatch.

## Going further

- **Protective gear:** open the sweep with `has_tag(o, 'rad_shielded')`
  and sell a hazmat suit that `grants_tags` it — the wearables
  pattern from [tutorial 038](038_dark_room.md).
- **Accumulating dose:** add the underwater room's per-occupant meter
  (`dose_<id>` on the room) and only start damaging past a threshold —
  radiation that forgives a sprint but not a siege.
- **Heat, cold, vacuum:** the same sweep with a different skill,
  damage die, and flavor — one pattern, every environmental hazard.
- **Event-driven severity:** the weather master
  ([tutorial 036](036_weather_system.md)) already drifts a state; let
  a solar-storm state push `rad_level` up zone-wide and your hazard
  rooms follow the sky.
