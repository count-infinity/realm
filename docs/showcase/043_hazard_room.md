# 043. Hazard room

> Checklist item 43 ([now]): *on_tick damage, HT resistance, zone-master severity*

**What you'll build:** A reactor gallery that cooks its occupants: a
periodic health roll, 1d6 radiation damage on a failure, and a severity
dial on the zone master that every hazard room in the zone reads.

**Concepts:** a room `script_ticker` sweep, resisted damage
([`skill_check`](../reference/softcode.md#fn-skill_check) plus
[`damage`](../reference/softcode.md#fn-damage)), skills as data (a
`skill_def`), zone masters as policy holders, and a `[[...]]` description
reading shared severity.

## How it works

A reactor gallery cooks whoever stands in it. Every couple of world
beats the room rolls each occupant's health against the current
radiation level and burns the ones who fail, while a severity dial on
the zone master lets you crank the whole reactor zone hotter with one
`@set`. Four things make that work: where the resistance roll comes
from, how the room sweeps its own occupants, why the severity lives off
the room, and how the warning label stays cheap.

1. **The resistance roll is data.** GURPS resists radiation with the HT
   attribute, so a `skill_def` object named `fortitude` (`stat = health`,
   `penalty = 0`) plus `@reload` teaches the skill table one new row.
   That makes [`skill_check`](../reference/softcode.md#fn-skill_check)`(o,
   'fortitude', -sv)` a health roll at a penalty equal to the current
   severity, the same fortitude roll the [gas bomb](048_gas_bomb.md)
   makes for its gas. If you already built that in this world the skill
   exists, and re-creating it is harmless.

2. **The room sweeps itself.** A
   [`script_ticker`](../reference/softcode.md#lifecycle-hooks) behavior on
   the room runs its [`on_tick`](../reference/softcode.md#lifecycle-hooks)
   over the room's [`contents`](../reference/softcode.md#fn-contents).
   Whoever passes the roll rides it out, and whoever fails takes
   [`damage`](../reference/softcode.md#fn-damage)`(o, roll('1d6'))`.
   Damage is a proximity authority, so a room may hurt what stands inside
   it, and a lethal hit routes through the real death path.

3. **Severity is zone policy.** The roll's penalty is not stored on the
   room. It is a `rad_level` attribute on the zone master, read fresh
   every sweep with [`get_attr`](../reference/softcode.md#fn-get_attr)`('Reactor
   Brain', 'rad_level', 1)`. Because every hazard room in the reactor zone
   reads the same master, one `@set Reactor Brain/rad_level = 3` worsens
   all of them at once, so a meltdown event is a single attribute write.
   Master objects are where the engine keeps zone-wide policy too: the
   combat manager reads `xp_multiplier` off a room's zone masters to scale
   kill awards for the whole zone, and your `rad_level` sits in the same
   kind of slot.

4. **The label reads the dial, one sweep behind.** Each sweep also stamps
   the severity it just used onto the room with
   [`set_attr`](../reference/softcode.md#fn-set_attr)`(me, 'rad_sv', sv)`,
   and a `[[...]]` block in the description turns that into a dosimeter
   line that scales with the danger. The indirection is deliberate:
   the sweep already reads the master on its own worker stack, so the
   description block that runs on every look stays one cheap local
   [`V`](../reference/softcode.md#fn-v)`('rad_sv', 1)` read on the room
   itself. That is the push-on-change habit from the
   [weather system](036_weather_system.md).

## Build it

First, the resistance skill as data. Create a `skill_def` named
`fortitude`, point it at the health attribute with no penalty, and
`@reload` so the skill table picks it up:

```text
@create fortitude
@tag fortitude = skill_def
@set fortitude/stat = health
@set fortitude/penalty = 0
@reload
```

Next, the zone and its severity dial. Dig the gallery, step onto the
catwalk, tag the room into a `reactor` zone, and crown a Reactor Brain as
that zone's master with `rad_level` starting at 1:

```text
@dig Reactor Gallery = catwalk, out
catwalk
@zone here = reactor
@create Reactor Brain
@zone/master Reactor Brain = reactor
drop Reactor Brain
@set Reactor Brain/rad_level = 1
```

Now the warning label. The `[[...]]` block runs at look time and reads
the severity the last sweep stamped onto the room, so the dosimeter line
tracks the danger one sweep late:

```text
@desc here = A steel catwalk rings the exposed core. The air is warm and tastes of foil. [[result = 'Your dosimeter ticks ' + ('lazily.' if V('rad_sv', 1) < 3 else 'without pause.')]]
```

Finally the hazard sweep itself. The `on_tick` block reads the current
severity off the master, stamps it back onto the room for the label,
then rolls every player present against fortitude at minus that severity:

```text
@set here/on_tick = '''
sv = get_attr('Reactor Brain', 'rad_level', 1)
set_attr(me, 'rad_sv', sv)  # stamp it so the desc reads it next look
for o in contents(me):
    if has_tag(o, 'player'):  # only cook players, not the floor or the master
        if skill_check(o, 'fortitude', -sv):
            pemit(o, 'Heat prickles across your skin; you ride it out.')
        else:
            damage(o, roll('1d6'))
            pemit(o, 'Nausea doubles you over. The core is cooking you.')
'''
@behavior here = script_ticker, interval:2
```

The `has_tag(o, 'player')` test is the guard that matters here. An
`on_tick` has no target of its own, so instead of the `if target is me:`
line a reactive hook needs, the sweep filters its own contents down to
players. Everything else in the room, the master included, is left alone.

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

Watch your hp fall sweep by sweep (`points`, or your prompt), then step
`out`. The sweep only touches the room's own contents, so the hazard
ends at the hatch.

## Going further

- **Protective gear:** open the sweep with `if has_tag(o, 'rad_shielded'):
  continue` and sell a hazmat suit that `grants_tags` it, the wearables
  pattern from the [dark room](038_dark_room.md).
- **Accumulating dose:** add a per-occupant meter (`dose_<id>` on the
  room) and only start damaging past a threshold, so radiation forgives a
  sprint but not a siege.
- **Heat, cold, vacuum:** the same sweep with a different skill, damage
  die, and flavor, one pattern for every environmental hazard.
- **Event-driven severity:** the [weather system](036_weather_system.md)
  already drifts a state on a master, so let a solar-storm state push
  `rad_level` up zone-wide and your hazard rooms follow the sky.
