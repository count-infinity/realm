# Crime & Justice

REALM ships the **minimal-viable** crime layer — the model Diku pioneered,
modernized. A player who assaults or murders another player is flagged
**wanted**; guards attack the wanted; the flag decays or clears on death.
It is deliberately small: no courts, no arrest choreography. The whole thing
rests on one elegant rule (Diku's `check_killer`): **attacking someone who
is already wanted is free** — so the flag is self-enforcing and needs no
justice engine.

## How it works

- **Wanted is a timed tag.** An offender gets a `wanted:<crime>` tag
  (`wanted:assault`, `wanted:murder`) plus a `wanted_heat` integer. A
  `wanted` behavior (`WantedBehavior`) counts the sentence down and strips
  the tags when it expires — heat scales the duration.
- **Detection is passive.** One observer (`crime_observer`, registered at
  boot beside the stealth/hostile observers) watches the existing combat
  events:
  - `combat:on_damage`, player-on-player → the **aggressor** is flagged
    `wanted:assault` (the *initiator*, never the invoker — the same
    enactor/executor signal the harm gate uses).
  - `combat:on_death`, player kills a non-wanted player → the killer is
    flagged `wanted:murder` (higher heat).
  - Attacking a **mob** is never a crime; attacking an **outlaw** is free.
- **Death pardons.** Dying strips the victim's own wanted status — the
  self-closing loop: wanted → open season → death → clean slate.
- **Enforcement is a behavior.** `PeacekeeperBehavior` (`peacekeeper`) scans
  its room each tick and attacks the highest-heat wanted player present.
  This is what ROM's `spec_guard` maps to (imported cityguards become
  peacekeepers) — distinct from the `guard` behavior, which blocks movement.

```text
# Put a peacekeeper on a town guard:
@behavior cityguard = peacekeeper, yell:"Halt, in the name of the law!"
```

Everything is tags and behaviors over the existing event bus — no engine
subsystem, no hardcoded guard/jail VNUMs (the trap of the C MUDs this is
drawn from).

## What's deliberately out of scope

This is the *core* tier. Two richer tiers are designed but not built (see
BACKLOG), because they are real features, not small mappings:

- **Jurisdiction & consent** — `lawful`/`safe` zone tags deciding *what
  counts as a crime where*, and a PvP-consent axis so consented duels and
  wilderness run no enforcement. (Right now any player-on-player hit in the
  world is a crime.)
- **Arrest & jail** — officers that seek/subdue/escort, a judge that
  sentences, and a timed jail (relocate + auto-release). The core skips
  straight to "guards attack the wanted", which is most of the value.

The synthesized design for both — drawn from tbaMUD, CoffeeMud, and SMAUG —
lives in BACKLOG under "Crime & justice layer".
