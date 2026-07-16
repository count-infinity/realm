# 039. Underwater room

> Checklist item 39 — [now] — *per-occupant on_tick meters, skill_check, damage()*

**What you'll build:** A flooded cistern where every tick underwater
costs a swimming roll; failures burn through your breath, and an empty
lung meter means drowning damage until you surface.

**Concepts:** a `script_ticker` on the room itself, per-occupant meters
stored *on the room*, skills as data (`skill_def` + `@reload`),
`eval_attr` as softcode's subroutine, `damage()` proximity authority,
`on_enter`/`on_leave` bookkeeping.

## How it works

Five design decisions, each an engine seam:

1. **The room is the machine.** Behaviors attach to any object, rooms
   included — so the cistern itself carries the `script_ticker` and an
   `on_tick` that sweeps its player-tagged contents. No manager object,
   no zone wiring: the hazard is where the hazard is.

2. **Breath meters live on the room, keyed by occupant** —
   `breath_<id>` — not on the players. That's authority, not style: a
   builder-owned room may not `set_attr` on someone else's character
   (only admin-owned masters get sheet-writing power), but it can
   remember anything it likes about them on itself. `on_leave` deletes
   the key, so surfacing resets you and the room never hoards state.

3. **Swimming is data.** GURPS swims on HT; REALM's skill table extends
   from inside the game: a `skill_def` object named `swimming` with
   `stat = health` and the standard unskilled penalty, then `@reload` —
   the same move as the gas bomb's `fortitude`
   ([tutorial 048](048_gas_bomb.md)). From then on
   `skill_check(o, 'swimming')` rolls 3d6 under the swimmer's HT-based
   level.

4. **The per-diver logic is a function attribute.** One tick handles
   many divers, and each diver needs read-update-branch logic that a
   comprehension can't express cleanly — so `on_tick` stays a one-line
   sweep and calls `eval_attr(me, 'soak', o.id)` per diver: softcode's
   subroutine call ([tutorial 242](242_inline_functions.md) uses the
   same trick for renderers). One nuance: `eval_attr` passes its args
   *as strings*, so we hand it the id and the subroutine re-resolves
   with `get('#' + arg0)`.

5. **The room can hurt you because you're in it.** `damage()` is
   proximity authority — a script can damage what stands *in* it. No
   ownership of the victim needed; drowning routes through the real
   death path (unconsciousness, corpses) like any other damage.

## Build it

The skill, as data:

```text
@create swimming
@tag swimming = skill_def
@set swimming/stat = health
@set swimming/penalty = -4
@reload
```

The cistern, its meters, and its entry/exit bookkeeping:

```text
@dig Flooded Cistern = dive, surface
dive
@desc here = Green water in a drowned vault; light falls in wavering shafts from a grate far above.
@set here/breath_max = 3
@set here/on_enter = pemit(enactor, 'You knife under. The cold clamps down; hold your breath.') if has_tag(enactor, 'player') else None
@set here/on_leave = (del_attr(me, 'breath_' + enactor.id), pemit(enactor, 'You break the surface and drag in a long breath.')) if has_tag(enactor, 'player') else None
```

The per-diver subroutine and the sweep that drives it. Pass the roll
and you spend nothing; fail and your meter drops; at zero the water
comes in — 1d6 per failed tick:

```text
@set here/soak = o = get('#' + arg0); k = 'breath_' + o.id; pemit(o, 'You pace your strokes and hold what air you have.') if skill_check(o, 'swimming') else (set_attr(me, k, get_attr(me, k, get_attr(me, 'breath_max', 3)) - 1), pemit(o, 'Your chest heaves. You are running out of air!') if get_attr(me, k, 0) > 0 else (damage(o, roll('1d6')), pemit(o, 'Water forces its way in. You are drowning!')))
@set here/on_tick = [eval_attr(me, 'soak', o.id) for o in contents(me) if has_tag(o, 'player')]
@behavior here = script_ticker, interval:1
surface
```

`interval:1` checks every world tick (~4 seconds) — harsh, good for
testing; `interval:3` is a kinder cistern.

## Try it

Give yourself lungs and a body to lose, then dive:

```text
@set me/hp = 12
@set me/max_hp = 12
@set me/health = 12
dive
  You knife under. The cold clamps down; hold your breath.
  You pace your strokes and hold what air you have.        <- made the roll
  Your chest heaves. You are running out of air!           <- failed one
  Your chest heaves. You are running out of air!           <- meter falling
  Water forces its way in. You are drowning!               <- meter empty: 1d6
surface
  You break the surface and drag in a long breath.
```

`@examine here` between ticks shows your `breath_<id>` meter counting
down; surfacing deletes it, so the next dive starts full.

## Going further

- **Air pockets:** a `$breathe` command on a submerged grating that
  resets `breath_<id>` to `breath_max` — a checkpoint for long
  flooded passages.
- **Diving gear:** start the `soak` branch with
  `has_tag(o, 'water_breathing')` and sell a rebreather that
  `grants_tags` it — the wearables system from
  [tutorial 038](038_dark_room.md) does the rest.
- **Murky water:** tag the cistern `dark` and let the lighting rules
  bite too — waterproof lamps become treasure.
- **Currents:** on a bad failure margin, `teleport_obj` the diver one
  room downstream — the falling-room pattern
  ([tutorial 047](047_falling.md)) turned sideways.
