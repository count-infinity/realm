# 160. Sneaking

> Checklist item 160 — now — *hide command, stealth contests, concealment state*

**What you'll build:** Almost nothing — and that's the lesson. REALM's
stealth stack (`hide`, quiet movement, spotting contests, `search`,
loud-action exposure) is engine-native. This tutorial composes it into
the heist's endgame and adds the two pieces softcode owns: a `watchful`
sentry whose alertness ratchets up, and a creaky floorboard that does
the ratcheting. Part of the [Heist arc](arc_heist.md); builds in the
Nexagen Vault.

**Concepts:** the `hidden` tag and its life cycle, `hide` / `search`
contests, the `watchful` behavior + `alert_level`, `@behavior` with
parameters, a `^listen` reacting to an *object's* emit, and
`skill_check` on movement via a witness.

## How it works

What the engine already does (see `tests/test_infiltration.py` and
`tests/test_perception.py` — the engine's own proofs):

- **`hide`** rolls Stealth (darkness gives +3) and sets the `hidden`
  tag. Hidden characters vanish from room displays, can't be targeted,
  and are named "Someone" in any message they cause.
- **Movement is quiet.** Walking does *not* break stealth — sneaking
  room to room is the point. Bystanders see only `Someone arrives.`:
  stealth hides *who*, not *that the door moved*.
- **`watchful` NPCs contest arrivals.** A hidden character entering the
  room triggers Perception-vs-Stealth; the NPC's `alert_level` attribute
  is added to its roll, and a win breaks the sneak, says the `spot_msg`,
  and raises `alert_level` further. Visible arrivals just get the
  `challenge` line.
- **`search` contests hiders** (Observation vs Stealth, ties to the
  hider), and **loud actions** — speaking, shouting, grabbing things —
  break stealth by themselves (the engine's stealth observer).

What softcode adds here is *escalation*. The floorboard is a witness:
its `ON_ENTER` rolls Stealth at -3 for any hidden arrival. Fail, and the
board — not the sneak — `emit`s a creak. An emit is real, overhearable
speech-like output, so the sentry's `^*creak*` listen fires, bumps its
own `alert_level`, and barks. The chain is five things you already know
— witness, check, emit, listen, attribute — composing into "the guard
gets warier every time the floor gives you away," with no system for it
anywhere.

Note whose stealth breaks: nobody's. The creak's *actor is the
floorboard*, so the sneak stays hidden — the sentry knows someone is
there, not where. Exactly right for a creak in the dark.

## Build it

The sentry. `@behavior` attaches engine behaviors with parameters;
`watchful` reads `skill_observation` and `alert_level` off its object:

```text
@teleport me = Nexagen Vault
@create Vault Sentry
@tag Vault Sentry = npc
drop Vault Sentry
@set Vault Sentry/hp = 13
@set Vault Sentry/max_hp = 13
@set Vault Sentry/health = 10
@set Vault Sentry/skill_observation = 12
@behavior Vault Sentry = watchful, challenge:This wing is off limits., spot_msg:Intruder! Show yourself!
```

Its ear — any overheard creak raises the alert one notch, permanently
(until you `@set` it back; a reset is a Going-further):

```text
@set Vault Sentry/listen_creak = ^*creak*: incr('alert_level'); say('Who goes there?')
```

The floorboard — a witness that only cares about hidden characters:

```text
@create loose floorboard
drop loose floorboard
@desc loose floorboard = One plank sits a hair prouder than its brothers.
@set loose floorboard/on_enter = (None if not (has_tag(enactor, 'hidden') and has_tag(enactor, 'player')) else (pemit(enactor, 'You cross the boards without a sound.') if skill_check(enactor, 'stealth', -3) else cmd('emit A floorboard creaks sharply!')))
```

(`cmd('emit ...')` makes the *floorboard* speak to the room — that's
what the sentry's listen overhears.)

## Try it

Walk in openly:

```text
vault door           -> Vault Sentry says, "This wing is off limits."
```

Sneak in with middling Stealth (12, vs the sentry's Observation 12 —
ties go to the hider):

```text
hide                 -> You slip out of sight.
vault door           -> (the room sees only "Someone arrives.")
                     -> A floorboard creaks sharply!        (Stealth -3 missed)
                     -> Vault Sentry says, "Who goes there?"
```

You're still hidden — but the sentry's `alert_level` is now 1, so its
next contest rolls at +1. Slip out and try again:

```text
antechamber
vault door           -> Vault Sentry spots you! ... "Intruder! Show yourself!"
```

A master sneak (Stealth 15) crosses the boards silently and beats the
sentry even alerted — until they open their mouth:

```text
say the vault is ours -> Your action gives you away!
```

And any patient searcher settles it with dice: `search` contests
Observation against the hider's Stealth — `Hawk spots you!`.

## Going further

- **Cooling off** — `@behavior Vault Sentry = script_ticker, interval:40`
  plus an `on_tick` that decrements `alert_level` toward zero: alarms
  fade if the intruder goes to ground.
- **Alert consequences** — at `alert_level` 3+, have the tick lock the
  vault door (`add_tag`) or `force` the sentry to patrol; the number is
  just an attribute every script can read.
- **Dark-side advantage** — `@tag` the vault `dark`: `hide` gains +3
  there, and a sentry without `nightvision` is on the wrong end of the
  perception engine.
- **Backup** — swap the sentry's bark for a zone-wide
  `act(..., targeting='zone')` so every guard in the wing hears the
  creak; add `hostile:true` to `watchful` and a spot starts real combat.
