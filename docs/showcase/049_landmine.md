# 049. Landmine

> Checklist item 49 — now — *ON_ENTER triggers, contest() detection, concealment tags*

**What you'll build:** A buried mine that detonates when someone walks
into the room — unless they win a Perception contest against its
concealment, already know it's there, or planted it themselves. Part of
the [Heist arc](arc_heist.md); it goes in the Vault Antechamber from
[item 27](027_secret_door.md).

**Concepts:** witnessed `ON_ENTER` as a proximity trigger, `contest()`
with a skill *on the object*, `on_check` wards (`block()`), `eval_attr()`
for splitting long scripts, `damage()`'s proximity authority, and the
`invisible` + `conceal_difficulty` concealment kit shared with the
secret door.

## How it works

The mine never polls and the room needs no code. When anything moves,
the arrival propagates as `event:on_enter`, and **every object in the
room witnesses it** — so a mine lying on the floor hears about every
arrival for free, with the arriver bound as `enactor`. That is the whole
proximity-trigger pattern; the same shape powers pressure plates, welcome
mats, and shop doorbells.

Detection is a **quick contest**, and here's the pleasing part: the
opposing skill lives on the *mine*. `skill_concealment = 13` is the
minelayer's craftsmanship, read by the same `skill_level` machinery as
any character skill — `contest(enactor, 'observation', me, 'concealment')`
needs no special case. Ties go to the status quo (the mine), as REALM
contests always do.

Order of the branches, mirroring how minefields actually play:

1. Not armed, not a character, or the arriver **owns the mine** — do
   nothing. The owner-exemption matters: softcode fires for *everyone*,
   including you, and a builder who steps on their own mine while
   decorating will not make that mistake twice.
2. Mine already visible (someone found it) — step around it. Knowledge
   is safety.
3. Contest won — freeze mid-step: reveal the mine to the world and no
   boom.
4. Contest lost — `eval_attr(me, 'boom')`.

The detonation lives in its own `boom` attribute — `eval_attr()` runs
another attribute as a function, sharing the same authority and message
queue — because one-line conditionals get unreadable past a point, and
because a separate `boom` is independently `@tr`-testable and reusable
(the safe's trap variant calls the same attribute).

`damage()` uses **proximity authority** — a script may hurt whatever is
in its room, no ownership needed — which is exactly the license a trap
requires and no more. Lethal damage routes through the real death path.

Last, the `on_check` **ward**: mines are not loot. The check pass runs
*before* a gated action commits, in a read-only namespace where the
script can only decide — `block(reason)` vetoes the pickup. The `target
== me` guard keeps the ward self-documenting and future-proof. (Note:
softcode wards run only when the object is a *participant* in the gated
action — actor, target, or the room — never for mere bystanders, so the
mine's ward fires only when the mine itself is the pickup target; Python
behaviors, by contrast, do get a bystander check pass. See
[053_snare.md](053_snare.md) for the participant-only rule in practice.)

## Build it

```text
@teleport me = Vault Antechamber
@create anti-personnel mine
drop anti-personnel mine
@set anti-personnel mine/armed = 1
@set anti-personnel mine/skill_concealment = 13
```

The concealment kit — identical to the secret door's, so the built-in
`search` finds mines too (`conceal_difficulty` is the search penalty;
the contest above is the mid-step check):

```text
@set anti-personnel mine/conceal_difficulty = 3
@set anti-personnel mine/reveal_msg = Dust brushed aside -- a pressure plate, wired and live!
```

The ward, the trigger, and the bang:

```text
@set anti-personnel mine/on_check = block('It is wedged into the floor -- and armed.') if atype == 'item:on_get' and target == me else None
@set anti-personnel mine/on_enter = x = enactor; (None if not (V('armed', 0) and (has_tag(x, 'player') or has_tag(x, 'npc')) and x != owner(me)) else (pemit(x, 'You step around the exposed mine.') if not has_tag(me, 'invisible') else ((remove_tag(me, 'invisible'), pemit(x, 'You freeze mid-step -- a pressure plate, right under your boot!')) if contest(x, 'observation', me, 'concealment') else eval_attr(me, 'boom'))))
@set anti-personnel mine/boom = remove_tag(me, 'invisible'); set_attr(me, 'armed', 0); pemit(enactor, 'KA-WHUMP! The floor erupts under you.'); oemit(enactor, f'{name(enactor)} sets off a buried mine!'); damage(enactor, roll('2d6'))
```

Bury it last, so you can see what you're doing while you work:

```text
@tag anti-personnel mine = invisible
```

Note what `boom` does besides hurt: it un-hides the mine and disarms it.
A spent, scorched casing is not hidden from anyone.

## Try it

Walk in (from the corridor, `loose grate`) with different eyes:

```text
(Observation 14)    -> You freeze mid-step -- a pressure plate, right under your boot!
get anti-personnel mine -> It is wedged into the floor -- and armed.
duct, loose grate   -> You step around the exposed mine.

(Observation 6)     -> KA-WHUMP! The floor erupts under you.   (2d6, for real)
```

The cautious route: if you're *already* in the room, `search` rolls
Observation at -3 and finds it (`Dust brushed aside -- a pressure plate,
wired and live!`) — but you must be in the room, and getting in is the
dangerous part. That's what makes it a minefield.

## Going further

- **Disarming** — add `$disarm mine: ...` with a `traps` skill check;
  success sets `armed = 0`, failure runs `eval_attr(me, 'boom')` at the
  disarmer's feet.
- **Area blast** — loop `contents(loc(me))` in `boom` and `damage()`
  bystanders for half. Proximity authority already covers the room.
- **Alarm plate** — replace `boom`'s damage with a zone-wide
  `act(..., targeting='zone')` and the same trigger becomes a silent
  alarm.
- **Mob casualties** — the trigger already fires for `npc`-tagged
  arrivals; route a patrol through the minefield at your own conscience.
