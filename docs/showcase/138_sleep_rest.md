# 138. Sleep & Rest

> Checklist item 138 ([now]): *rest tags, regeneration boosts, vulnerability wards*

**What you'll build:** a bunk you lie down on to recover HP faster than the
world gives you for free, and while you are under a ward pins you to the cot
until you `wake`. Rest that trades safety for healing.

**Concepts:** recovery is opt-in, so `rest` supplies it by attaching a
[`regeneration`](../reference/softcode.md#fn-apply_effect) effect (proximity
authority, no admin needed); the effect's mirrored `resting` tag stands in for
the "asleep" state; and an `on_check` lockout ward turns rest into commitment,
because the sleeper is exposed for exactly as long as the sleeper stays put.

## How it works

The finished bunk is three attributes on one room fixture: a `$rest` verb that
switches a healer on, a `$wake` verb that switches it off, and a ward on the
room that vetoes movement while the healer runs. This section answers where the
healing comes from, why a plain builder-owned cot is allowed to apply it, how
the sleeper's state is read back, and where the risk lives.

### Where does the healing come from?

Nothing heals a hurt character on its own. Out of the box a wounded body stays
wounded until a medic's [`firstaid`](135_injury_treatment.md), a
[`heal()`](../reference/softcode.md#fn-heal), or an attached `regeneration`
effect tops it up. There is no ambient trickle and no fatigue-point pool, so
resting is simply switching a healer on:
[`apply_effect`](../reference/softcode.md#fn-apply_effect)`(enactor,
'regeneration', heal=3, ...)` pulses +3 HP a beat. The recovery "multiplier" is
just that number set against the nothing you get standing up.

### Why a plain cot is allowed to heal you

`regeneration` is one of the effects softcode may apply with **proximity**
authority, the same gate the tranquilizer dart uses in
[059](059_tranquilizer.md): a fixture in the room can heal whoever is in that
room, no ownership required. Contrast the survival meters in
[137](137_hunger_thirst.md), which reach across a whole zone and so need an
admin-owned master. A bunk only ever works on someone in the same room, so it
can be an ordinary builder-owned object.

### How the state is read back

Every timed effect mirrors its `kind` as a tag on the owner for as long as it
runs, so applying the effect with `kind='resting'` tags the sleeper `resting`,
something the desc, the ward, and any onlooker can read with
[`has_tag`](../reference/softcode.md#fn-has_tag).
[`remove_effect`](../reference/softcode.md#fn-remove_effect)`(enactor,
'resting')` is waking: healer off, tag gone.

### Where the risk lives

Sleep should cost something. A ward on the room vetoes *movement* while you are
`resting`, so you must `wake` before you can leave, which means an ambush finds
you pinned to your bedroll. That single
[`block`](../reference/softcode.md#event-data-namespace)`()` is the whole risk
model: the recovery is real, and so is being caught defenceless. Setting
`duration=0` keeps the healing running until you wake rather than until a clock
expires, so you sleep as long as you like and stay exposed just as long.

## Build it

This tutorial is written as commands a builder types live. First dig the
bunkroom, step into it, and drop a cot to rest on:

```text
@dig The Bunkroom = bunkroom, out
bunkroom
@create field cot
drop field cot
@desc field cot = A canvas cot with a thin blanket. REST to lie down and recover; WAKE to rise.
```

The `$rest` verb refuses a double-rest, then attaches the healer and announces
the scene. The effect's `kind='resting'` becomes the state tag, and `duration=0`
keeps it running until `wake` removes it:

```text
@set field cot/cmd_rest = '''
$rest:
if has_tag(enactor, 'resting'):
    pemit(enactor, 'You are already resting.')
else:
    # kind='resting' mirrors as a tag; duration=0 heals until WAKE, not on a clock
    apply_effect(enactor, 'regeneration', kind='resting', heal=3, duration=0, interval=1)
    remit(loc(enactor), name(enactor) + ' lies back on the cot and closes their eyes.')
'''
```

The `$wake` verb is the mirror: strip the effect (healer off, tag gone) if the
enactor is resting, otherwise say so:

```text
@set field cot/cmd_wake = '''
$wake:
if has_tag(enactor, 'resting'):
    remove_effect(enactor, 'resting')
    remit(loc(enactor), name(enactor) + ' stirs and sits up.')
else:
    pemit(enactor, 'You are already up and about.')
'''
```

Finally the lockout ward. It watches the whole room and keys on the mover, so a
sleeper who tries to walk is held while anyone else leaves freely:

```text
@set here/on_check = block('You are wrapped in sleep -- WAKE before you can move.') if has_atag('movement') and adata('exit') and has_tag(actor, 'resting') else None
```

The ward is a global witness, not a reaction to one object, so it takes no
`target is me` guard: it reads [`has_atag`](../reference/softcode.md#event-data-namespace)`('movement')`
to catch any relocation, [`adata`](../reference/softcode.md#event-data-namespace)`('exit')`
to limit that to a walk through an exit, and `has_tag(actor, 'resting')` so it
holds only the sleeper. Someone standing beside the cot walks out untouched.

## Try it

Come in wounded (say 10 of 30 HP) and notice the world heals you by nothing:

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

Awake, the `resting` tag and its healer are gone, so a beat later your HP sits
still again. Rest is the only recovery in the room, and the ward is the price of
taking it.

## Going further

- **Deeper sleep, faster heal:** a `$sleep` verb attaching a stronger
  `regeneration` (heal 6) plus a second ward that also blocks `attack` and
  speech while under, real unconsciousness you chose, tuned like the tranq's
  gates ([059](059_tranquilizer.md)).
- **Only safe beds heal:** gate `$rest` on a `safe`-tagged room or a
  `disposition` check on the local guard, so bedding down in the wild is a
  gamble.
- **Wake on danger:** put a zone-master `combat:on_attack` witness that
  `remove_effect`s `resting` from everyone in the room, so the shout of battle
  jolts the camp awake.
- **Fatigue as its own meter:** run a [137](137_hunger_thirst.md)-style
  `fatigue` meter that only `$rest` refills, so pushing through the night costs
  you tomorrow, an FP pool built as data.
