# 059. Tranquilizer Mechanics

> Checklist item 59 — [now] — *engine unconscious tag, command lockout, recovery waits*

**What you'll build:** A tranquilizer pistol whose dart drops a target
into real unconsciousness — the same state the combat engine uses when
HP runs out — for six rounds, plus the stim injector that jolts them
awake early.

**Concepts:** the engine's **`unconscious` tag** and what it gates
(movement, fighting), inducing it legally from softcode via
`apply_effect`'s kind-tag (proximity authority, timed by **beats**),
HT resistance as a `skill_def`, and `remove_effect()` as the wake-up.

## How it works

1. **Unconsciousness already exists — find the seam, don't rebuild
   it.** When combat drops a player to 0 HP, the engine tags them
   `unconscious`, and that tag is checked all over the engine: walking
   any exit answers `You are unconscious.`, `attack` refuses, fleeing
   is off the table, followers leave you behind. A tranquilizer
   doesn't need its own lockout machinery; it needs to *set that tag*
   — then every gate the engine already built swings shut for free.

2. **The legal way to tag a stranger is an effect.** Softcode can't
   `add_tag(victim, 'unconscious')` — mutation needs control, and you
   don't control other players. But `apply_effect()` runs on
   *proximity* authority (a dart can drug whoever it can reach), and
   every timed effect **mirrors its `kind` as a tag on the victim for
   exactly as long as it runs**. So `apply_effect(t, 'modifier_effect',
   kind='unconscious', duration=6, ...)` is the whole knockout: the
   engine tag appears, the gates close, and the effect machinery owns
   the bookkeeping. This is the same kind-tag trick as the snare
   (item 53) — pointed, this time, at a tag the *engine* respects.

   Mind what "proximity" means, though: it is the **gadget's** room,
   and a gadget in your hands has your pocket for a room. Effects and
   damage reach from where the object *stands* — which is why this
   pistol lives on a swivel mount by the door and the stim in a wall
   cradle, why the idol darts from its bracket (item 52), and why the
   gas bomb refuses to arm in your hands (item 48). Sedation gear is
   furniture; the room is its range.

3. **Waking up is the effect expiring.** `duration` counts **beats** —
   combat rounds in a fight, world ticks outside one — and when it
   runs out the effect detaches itself: tag lifted, `expire_msg`
   delivered (`You come to...`), gates open. Sedation that outlasts a
   reboot, because effects serialize with their owner. No `wait()`
   to orphan, nothing to clean up.

4. **Resistance is the same HT roll as every toxin.** A `fortitude`
   `skill_def` on `health` (the gas bomb's trick, item 48), rolled at
   -3 — tranq rounds are *meant* to put things down, but a hardy
   target shakes it off. And the counterplay mirror: `remove_effect(t,
   'unconscious')` strips the effect early — tag and all — which is
   what a stim injector is. (The built-in `firstaid` also wakes the
   *wounded* unconscious, but a tranq victim is unhurt — chemistry
   needs chemistry.)

One design note: the dart deals **no HP damage**. Tranquilizers are
interesting precisely because they route around the death path — a
knockout you can hand to players without handing them murder is why
this item exists in heist games.

## Build it

The range, and HT as a rollable skill:

```text
@dig The Med Bay = medbay, out
medbay
@create fortitude
@tag fortitude = skill_def
@set fortitude/stat = health
@set fortitude/penalty = 0
@reload
```

The pistol — find the named target in reach, dart them, and let the
HT roll decide between a wobble and the floor:

```text
@create tranq pistol
drop tranq pistol
@desc tranq pistol = A snub-nosed gas pistol on a swivel mount by the door, rotary drum full of red-feathered darts. SHOOT someone with it.
@set tranq pistol/cmd_shoot = $shoot *: t = get(trim(arg0)); (pemit(enactor, 'No sign of them in reach.') if not (t and loc(t) == loc(enactor) and (has_tag(t, 'player') or has_tag(t, 'npc'))) else (remit(loc(enactor), f"{name(enactor)} plants a red-feathered dart in {name(t)}'s neck!"), (pemit(t, 'Your vision swims... then steadies. Your neck is numb.') if skill_check(t, 'fortitude', -3) else (apply_effect(t, 'modifier_effect', kind='unconscious', duration=6, apply_msg='The room smears sideways. Then nothing.', expire_msg='You come to, cheek on the cold deck.'), remit(loc(enactor), f'{name(t)} crumples bonelessly to the floor.')))))
```

The stim — early wake-up, same proximity authority, same wall cradle:

```text
@create stim injector
drop stim injector
@desc stim injector = An emergency stim injector in a wall cradle. JAB the sedated with it.
@set stim injector/cmd_jab = $jab *: t = get(trim(arg0)); (remove_effect(t, 'unconscious'), remit(loc(enactor), f"{name(enactor)} slams a stim injector against {name(t)}'s arm. They jolt awake.")) if t and loc(t) == loc(enactor) and has_tag(t, 'unconscious') else pemit(enactor, 'They are not sedated.')
```

## Try it

Dart two targets — one hardy, one not:

```text
shoot Brick    (HT 13)  -> Brick: Your vision swims... then steadies. Your neck is numb.
shoot Zeke     (HT 8)   -> The room smears sideways. Then nothing.
                           (the room) Zeke crumples bonelessly to the floor.
```

Now watch the engine's own gates do the lockout work you never wrote:

```text
(Zeke types: out)       -> You are unconscious.
(Zeke types: attack ...)-> You are unconscious.
```

Six beats later, on its own: `You come to, cheek on the cold deck.` —
and the exits work again. Or skip the nap:

```text
jab Zeke                -> Bob slams a stim injector against Zeke's arm. They jolt awake.
```

## Going further

- **Groggy aftermath** — chain a second effect from the wake-up: a
  `modifier_effect` with `kind='groggy', duration=10,
  check_mods={'all': -2}` applied alongside, one beat longer — you
  wake before your reflexes do.
- **A gag ward too** — the unconscious can still technically speak
  (only move/combat are engine-gated). A ward on the *room* closes it
  (`@set here/on_check = ...`): `block('Only a soft snore emerges.')
  if atype == 'event:speech' and has_tag(actor, 'unconscious') else
  None` — rooms, as participants, may veto what happens in them
  (the snare's lesson, item 53).
- **Drag the body** — the sleeper is exempt from being carried
  (players can't be picked up); a `$drag *` using `teleport_obj` works
  in rooms you own — a kidnapping mechanic with the pit trap's
  authority rules (item 51).
- **Dosage stacking** — a second dart while `unconscious` could
  `remove_effect` + re-apply with `duration=12`; or check the tag and
  refuse — overdose policy is a one-line design decision either way.
