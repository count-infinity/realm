# 052. Poison Dart Trap

> Checklist item 52 — [now] — *ON_GET/ON_USE traps, apply_effect damage_over_time*

**What you'll build:** A jade idol that answers a touch — or a grab —
with a dart and a lingering venom that ticks damage for the next six
rounds, unless the victim's constitution shakes it off. Plus the
antidote that cures it.

**Concepts:** `$`-command and `ON_GET` as two triggers on one trap,
`eval_attr()` as the shared payload, the engine's **effect machinery**
(`apply_effect('damage_over_time', ...)` — a ticking condition that
persists, tags its victim, and expires on its own), resistance as a
`skill_def`, and `remove_effect()` as counterplay.

## How it works

1. **Two triggers, one payload.** "Touching the wrong object" arrives
   through two doors: the explicit verb (`touch idol`, a `$`-command on
   the idol) and the greedy one (`get idol` — the engine fires the
   idol's `ON_GET` when someone picks it up, *before* the idol leaves
   the floor). Both are one-line callers of a single `dart` attribute
   via `eval_attr()` — the same shared-subroutine shape as the camera's
   relay (item 54). Fix the dart once, both triggers sharpen.

2. **The poison is an engine effect, not a script loop.** REALM's
   status machinery is `apply_effect()`: it attaches a registered
   effect behavior to the victim. `damage_over_time` pulses damage each
   **beat** (the game's round-clock: combat rounds in a fight, the
   world tick outside one), for `duration` beats, narrating with
   `tick_msg`/`room_msg`, then expires by itself with `expire_msg`.
   Three things you get free that a hand-rolled `wait()` loop would
   not give you: the effect **persists across a reboot** (behaviors
   serialize; a poisoned character is still poisoned after a restart),
   it **tags the victim** (`has_tag(x, 'poison')` is readable by locks,
   perception, and other softcode while it runs), and lethal pulses
   route through the real death path.

   The authority is proximity, not control — the same license as
   `damage()`: a trap may poison whoever stands next to it. That is
   why the *idol* applies the effect, and why ON_GET (which fires
   while the idol is still on the floor beside its victim) is in
   reach.

3. **Resistance is data.** GURPS resists poison with HT. One
   `skill_def` object named `fortitude` (`stat = health`) plus
   `@reload` teaches the skill table a new row — the identical trick
   to the gas bomb's fortitude roll (item 48). `skill_check(enactor,
   'fortitude', -2)` then rolls the toucher's own health attribute.

4. **The cure is `remove_effect()`** — strip an active effect by kind,
   same proximity authority. An antidote vial is a `$drink` command
   that checks the victim actually carries the `poison` tag (the
   effect's own tag, remember), cures, and destroys itself.

## Build it

A room for the shrine, and the resistance skill as data:

```text
@dig The Reliquary = reliquary, out
reliquary
@create fortitude
@tag fortitude = skill_def
@set fortitude/stat = health
@set fortitude/penalty = 0
@reload
```

The idol. The `dart` payload: a visible dart, a scratch of real damage,
then the HT roll decides whether venom takes hold:

```text
@create jade idol
drop jade idol
@desc jade idol = A grinning green figurine on a wall bracket. Its eyes follow you.
@set jade idol/dart = remit(loc(me), 'A hidden nozzle spits a needle-thin dart!'); damage(enactor, roll('1d2')); (pemit(enactor, 'A cold numbness spreads from the scratch.'), apply_effect(enactor, 'damage_over_time', kind='poison', damage=1, interval=1, duration=6, tick_msg='Venom burns through your veins!', room_msg='{name} shivers, grey-faced and sweating.', expire_msg='The fever finally breaks.')) if not skill_check(enactor, 'fortitude', -2) else pemit(enactor, 'Your head swims for a moment -- then clears. Only a scratch.')
@set jade idol/cmd_touch = $touch idol: eval_attr(me, 'dart')
@set jade idol/on_get = eval_attr(me, 'dart')
```

And the counterplay, left where a merciful builder leaves such things:

```text
@create antidote vial
drop antidote vial
@desc antidote vial = A stoppered vial of milky liquid, labeled in a careful hand: AFTER THE IDOL.
@set antidote vial/cmd_drink = $drink antidote: (remove_effect(enactor, 'poison'), pemit(enactor, 'Bitter warmth washes the numbness out of your blood.'), destroy_obj(me)) if has_tag(enactor, 'poison') else pemit(enactor, 'You are not poisoned. Save it.')
```

## Try it

```text
touch idol   (HT 13)  -> ...Only a scratch.            (1d2 dart damage, no venom)
touch idol   (HT 8)   -> A cold numbness spreads from the scratch.
```

Then, each beat, the poisoned one reads `Venom burns through your
veins!` and loses 1 HP while the room watches them shiver — six beats
and `The fever finally breaks.` on its own. Grabbing it instead:

```text
get jade idol         -> A hidden nozzle spits a needle-thin dart!
                         (the same payload -- and you're still holding the idol)
```

The cure, any time before the fever runs its course:

```text
drink antidote        -> Bitter warmth washes the numbness out of your blood.
```

`remove_effect` detaches the behavior mid-run: the tag lifts, the
ticking stops, the vial is gone.

## Going further

- **Blinding venom** — effects carry check modifiers: add
  `check_mods={'observation': -4}` to the `apply_effect` call and the
  poisoned can barely see straight until it lifts (the same plumbing
  as the banshee's fear).
- **One dart only** — gate `dart` on a `loaded` attribute and zero it
  after firing; a `$reload idol` for the owner re-arms it.
- **Trapped chest instead** — the payload is portable: put
  `eval_attr(me, 'dart')` in a container's `ON_OPEN` and the same
  venom guards loot.
- **Slow rot** — `interval=3, duration=30` turns a nuisance into a
  journey-length problem that outlives a server restart; the antidote
  trade gets interesting.
