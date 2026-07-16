# 047. Falling between rooms

> Checklist item 47 — [now] — *skill gates, teleport_obj, forced movement*

**What you'll build:** A cliffside ledge that demands a Climbing roll
from everyone who steps onto it — fail, and you drop to the gully
below, taking 2d6 from the landing, with a guard so one bad step can't
cascade into an infinite ping-pong.

**Concepts:** `on_enter` as a skill gate, `teleport_obj()` forced
movement and room-owner relocation authority, `damage()` timing,
message/move queue ordering, a time-keyed reentrancy guard.

## How it works

1. **The gate is `on_enter` on the ledge.** It fires for every arrival
   (the room witnesses the move; `enactor` is the mover), rolls
   `skill_check(enactor, 'climbing', -2)` — Climbing is in the
   built-in GURPS skill table, DX-based, so no `skill_def` needed —
   and only players are tested; crates don't lose their footing.

2. **The fall is `teleport_obj`.** Forced movement skips wards (you
   don't get a *choice* about falling) while still honoring locks. The
   room may relocate the faller because of **room-owner relocation
   authority**: a room's owner may move what stands in their room —
   Penn's `tport_control_ok`, weaker than full control, and the reason
   the fall doesn't need an admin owner. (It also means falls only
   work in *owned* rooms — true of anything you dug.)

3. **Ordering is queue discipline.** Softcode's world ops and messages
   are queued and run after the script, *in order* — so the script
   queues: the victim's "you are falling" line, the teleport, the
   ledge-wide third-person line, the landing line. By the time the
   `remit` delivers, the faller has already left the ledge, so
   bystanders read the fall without the faller getting their own
   third-person echo. `damage()` needs no such care: it must be
   *called* while the victim is still in reach (same room), and it is —
   the hp change is immediate, the death-check rides the queue.

4. **The reentrancy guard is a timestamp.** The teleport fires the
   gully's own `on_enter` mid-cascade — harmless there, but if a
   miswired drop room pointed back at the ledge (or something bounced
   the victim straight back up), the gate would re-roll forever. So a
   fall stamps `fall_<id> = now()` on the ledge, and the gate waves
   through anyone who fell within the last 5 seconds — no re-roll, no
   loop, and the stamp expires by itself with no cleanup tick.

## Build it

```text
@dig Cliffside Ledge = ledge, back
ledge
@dig Scree Gully = down, up
@desc here = A boot-wide shelf hugs the cliff face. Pebbles you dislodge take a long time to land.
@set here/on_enter = k = 'fall_' + enactor.id; recent = now() - get_attr(me, k, 0) < 5; safe = not has_tag(enactor, 'player') or recent or skill_check(enactor, 'climbing', -2); (pemit(enactor, 'Scree shifts under your boots. You hug the rock and find your footing.') if has_tag(enactor, 'player') and not recent else None) if safe else (set_attr(me, k, now()), pemit(enactor, 'The lip crumbles under your boot. You are falling.'), teleport_obj(enactor, 'Scree Gully'), damage(enactor, roll('2d6')), remit(me, name(enactor) + ' misses a step and pitches over the edge!'), pemit(enactor, 'You slam into the scree below. Everything hurts.'))
back
```

(The `@dig` of the gully happens *from* the ledge, so `down`/`up`
connect the two levels — the honest way down and the long climb back.)

## Try it

Give yourself a body, then test both outcomes:

```text
@set me/hp = 14
@set me/max_hp = 14
@set me/skill_climbing = 14
ledge
  Scree shifts under your boots. You hug the rock and find your footing.
back
@set me/skill_climbing = 4
ledge
  The lip crumbles under your boot. You are falling.
  You slam into the scree below. Everything hurts.
```

You're in Scree Gully, several hp lighter; anyone on the ledge read
"...misses a step and pitches over the edge!" Climb `up` right away
and the 5-second stamp lets you regain the shelf without a fresh roll
— winded, not looping. Wait it out, and the ledge is dangerous again.

## Going further

- **Margin-scaled damage:** swap the bool `skill_check` for the
  `margin_under` primitive and size the dice by how badly the roll
  missed — a slip versus a plummet.
- **Catch yourself:** on failure, offer one `prompt()` — "grab for
  the root? (yes/no)" — a second Climbing roll at -4 before the drop
  ([tutorial 067](067_dialogue_tree_npc.md) chains prompts).
- **Chained falls:** give the gully floor its own weaker gate onto a
  lower cave — the 5-second stamps keep even a chain of ledges
  loop-safe.
- **Push people off:** a `$shove <target>` verb can't relocate a
  bystander (no consent, no ownership) — but it *can* `force` a
  contested roll and let the *ledge* do the dropping when they fail:
  route hostile pushes through the room that owns the fall.
