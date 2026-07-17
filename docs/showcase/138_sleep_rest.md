# 138. Sleep & Rest

> Checklist item 138 — [now] — *rest as a proximity effect, the regeneration behavior as recovery, a lockout ward as vulnerability*

**What you'll build:** a bunk you lie down on to recover HP faster than the
world gives you for free — and while you're under, you can't just walk off:
a ward pins you to the cot until you `wake`. Rest that trades safety for
healing.

**Concepts:** REALM has **no fatigue kernel and no passive HP regen** —
recovery is opt-in, and `rest` supplies it by attaching a `regeneration`
effect (proximity authority, no admin needed); the effect's mirrored
`resting` tag as the "asleep" state; and an `on_check` **lockout ward**
that turns rest into commitment — the sleeper is vulnerable because the
sleeper can't run.

## How it works

1. **Nothing heals you on its own — so `rest` attaches a healer.** Out of
   the box a hurt character stays hurt until a medic's `firstaid`, a
   `heal()`, or an attached `regeneration` behavior tops them up; there is
   no ambient trickle and no fatigue-point pool. Rest, then, is simply
   *switching a healer on*: `apply_effect(enactor, 'regeneration',
   heal=3, ...)` pulses +3 HP a beat. The recovery "multiplier" is just
   that number against the nothing you get standing up.

2. **The bunk is a room fixture, and rest is proximity.** `regeneration`
   is one of the effects softcode may apply with **proximity** authority
   ([059](059_tranquilizer.md)) — a cot in the room can heal whoever lies
   on it, no ownership required. (Contrast [137](137_hunger_thirst.md),
   whose meters reach across a zone and so need an admin-owned master; a
   bunk only ever works on someone in the same room, so it can be a plain
   builder-owned object.)

3. **The `resting` tag is the state.** Every timed effect mirrors its
   `kind` as a tag for as long as it runs, so `kind='resting'` means the
   sleeper is literally tagged `resting` — something the desc, the ward,
   and any onlooker can read. `remove_effect(enactor, 'resting')` is
   waking: healer off, tag gone.

4. **Vulnerability is a lockout ward.** Sleep should cost something. A ward
   on the room vetoes *movement* while you're `resting` — you must `wake`
   before you can leave, which means you can't flee an ambush from your
   bedroll. That single `block()` is the whole risk model: the recovery is
   real, and so is being caught defenceless. (`duration=0` makes the
   healing last until you wake, not until a clock expires — sleep as long
   as you like; the exposure lasts just as long.)

## Build it

The bunkroom, the cot, and the two verbs:

```text
@dig The Bunkroom = bunkroom, out
bunkroom
@create field cot
drop field cot
@desc field cot = A canvas cot with a thin blanket. REST to lie down and recover; WAKE to rise.
@set field cot/cmd_rest = $rest: (pemit(enactor, 'You are already resting.') if has_tag(enactor, 'resting') else (apply_effect(enactor, 'regeneration', kind='resting', heal=3, duration=0, interval=1), remit(loc(enactor), name(enactor) + ' lies back on the cot and closes their eyes.')))
@set field cot/cmd_wake = $wake: (remove_effect(enactor, 'resting'), remit(loc(enactor), name(enactor) + ' stirs and sits up.')) if has_tag(enactor, 'resting') else pemit(enactor, 'You are already up and about.')
```

The lockout ward — a sleeper who tries to walk is held until they wake:

```text
@set here/on_check = block('You are wrapped in sleep -- WAKE before you can move.') if has_atag('movement') and adata('exit') and has_tag(actor, 'resting') else None
```

## Try it

Come in wounded (say 10 of 30 HP) and notice the world heals you by
nothing:

```text
(a beat passes)   -> still 10/30.   Standing up, no recovery.
rest              -> Nyx lies back on the cot and closes their eyes.
(a beat)          -> 13/30
(a beat)          -> 16/30
(a beat)          -> 19/30
```

Three HP a beat, only because you lay down. Now try to slip out mid-nap:

```text
out               -> You are wrapped in sleep -- WAKE before you can move.
wake              -> Nyx stirs and sits up.
out               -> (you leave)
```

Awake, the `resting` tag and its healer are gone — a beat later your HP
sits still again. Rest is the only recovery in the room, and the ward is
the price of taking it.

## Going further

- **Deeper sleep, faster heal:** a `$sleep` verb attaching a stronger
  `regeneration` (heal 6) *plus* a second ward that also blocks `attack`
  and speech while under — real unconsciousness you chose, tuned like the
  tranq's gates ([059](059_tranquilizer.md)).
- **Only safe beds heal:** gate `$rest` on a `safe`-tagged room or a
  `disposition` check on the local guard, so bedding down in the wild is a
  gamble.
- **Wake on danger:** put a zone-master `combat:on_attack` witness that
  `remove_effect`s `resting` from everyone in the room — the shout of
  battle jolts the camp awake.
- **Fatigue as its own meter:** run a [137](137_hunger_thirst.md)-style
  `fatigue` meter that only `$rest` refills, so pushing through the night
  costs you tomorrow — the FP pool REALM doesn't ship, built as data.
