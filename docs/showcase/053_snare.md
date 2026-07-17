# 053. Snare

> Checklist item 53 — [now] — *restraint tags, movement wards, $struggle contest loops*

**What you'll build:** A hunting snare that whips tight around an
ankle and holds the victim in the room until they tear free with
Strength contests — each failed struggle loosening the wire a little.

**Concepts:** what actually *blocks movement* in softcode — an
`on_check` ward vetoing `event:on_leave`; the effect machinery's
kind-tag as a restraint flag (`apply_effect` with `duration=0`),
`contest()` against a skill stored *on the trap*, ST-as-a-skill via
`skill_def`, and degrading trap state as a mercy rule.

## How it works

The question this item answers: **how does softcode stop someone from
leaving a room?** Not by owning them, and not by editing their sheet —
by *vetoing the move as it happens*.

1. **Every move is a gated action, and the room is its doorman.**
   Walking out fires `event:on_leave` through the propagation engine's
   check pass *before* the actor relocates, and the action's
   **participants** — the mover and the origin room — get to run their
   `on_check` wards against it (bystanders witness and react, but
   their softcode never runs on the check pass; the room is the
   participant that owns departures). A ward is decision-only softcode (read-only
   namespace, plus `block()`), bound to the in-flight action: `atype`
   is the action's type, `actor` is who's moving. So the ward goes
   **on the room**, one line: *if this is a departure and the actor is
   snared, `block()`*. The engine shows the walker your block reason
   and the move never happens. Note what this ward does **not** need:
   any code on the victim, or knowledge of which exit they tried.

2. **"Snared" is an effect, and the tag comes free.** The snare cannot
   `add_tag(victim, ...)` — mutating a stranger requires control. But
   `apply_effect()` runs on *proximity* authority, and every timed
   effect mirrors its `kind` as a tag on the victim for exactly as
   long as it is active. So `apply_effect(x, 'modifier_effect',
   kind='snared', duration=0)` is the legal way to hang a restraint
   flag on someone else: `duration=0` means "until removed", the tag
   `snared` appears for the ward to read, and `remove_effect(x,
   'snared')` takes flag and effect away in one motion. The status
   machinery is the tag ledger; wards just read it.

3. **Breaking out is a quick contest — and the opposing skill lives on
   the trap.** `contest(enactor, 'might', me, 'hold')` rolls the
   victim's ST against `skill_hold` on the snare (the trapper's
   craftsmanship), exactly like the landmine's concealment contest
   (item 49). ST-as-a-skill is one more `skill_def` (`might`,
   `stat = strength`, penalty 0) — untrained, everyone rolls their raw
   Strength. Ties go to the snare: REALM contests favor the status
   quo, and the status quo has you by the ankle.

4. **Failure loosens the wire.** Each failed `$struggle` decrements
   `skill_hold` — the snare's skill is just an attribute, so the trap
   itself can degrade. A weak character is delayed, not imprisoned;
   the contest loop always terminates. That is trap design as much as
   engine fact.

One honest note: the ward gates *walking* (and scripted `move_to`).
A `teleport_obj` / `@teleport` is a forced placement and tunnels past
wards by design — an admin can always yank a victim free.

## Build it

The trail, and ST as a rollable skill:

```text
@dig The Game Trail = trail, out
trail
@create might
@tag might = skill_def
@set might/stat = strength
@set might/penalty = 0
@reload
```

The snare. `armed` spends itself on the first victim (it is *holding*
them); `skill_hold = 12` is the trapper's craft:

```text
@create hunting snare
drop hunting snare
@desc hunting snare = A whippy sapling, a loop of ground wire, and patience.
@set hunting snare/armed = 1
@set hunting snare/skill_hold = 12
@set hunting snare/on_enter = x = enactor; (set_attr(me, 'armed', 0), remit(loc(me), f"A wire loop snaps tight around {name(x)}'s ankle!"), apply_effect(x, 'modifier_effect', kind='snared', duration=0, apply_msg='The world jerks sideways -- you are caught fast!')) if V('armed', 0) and (has_tag(x, 'player') or has_tag(x, 'npc')) and x != owner(me) else None
```

The ward — on the room, the whole restraint in one decision:

```text
@set here/on_check = block('The snare around your ankle jerks taut! (STRUGGLE to break free)') if atype == 'event:on_leave' and has_tag(actor, 'snared') else None
```

And the way out — win the contest and shed the effect, lose it and
the wire gives a point of `hold`:

```text
@set hunting snare/cmd_struggle = $struggle: pemit(enactor, 'You are not caught in anything.') if not has_tag(enactor, 'snared') else ((remove_effect(enactor, 'snared'), remit(loc(me), f'{name(enactor)} tears free of the snare!')) if contest(enactor, 'might', me, 'hold') else (decr('skill_hold'), pemit(enactor, 'You strain against the wire. It gives a little -- and holds.')))
```

## Try it

Walk someone in (ST 12, against `hold` 12):

```text
(they enter)      -> The world jerks sideways -- you are caught fast!
(they type: out)  -> The snare around your ankle jerks taut! (STRUGGLE to break free)
struggle          -> You strain against the wire. It gives a little -- and holds.
                     (a tie -- ties go to the snare; hold is now 11)
struggle          -> Zeke tears free of the snare!
out               -> (gone)
```

While held, *every* exit refuses them — the ward doesn't know or care
which way they tried. The sprung snare (`armed = 0`) ignores the next
walker; `@set hunting snare/armed = 1` resets the trap, though the
wire keeps its stretched `skill_hold` unless you re-set that too.

## Going further

- **Hobbled, not just held** — add `check_mods={'melee': -2,
  'stealth': -4}` to the `apply_effect` call: fighting and sneaking
  from inside a snare should be worse, and every check reads the
  modifier automatically.
- **A friend with a knife** — a `$cut snare` command on the snare
  itself: `remove_effect(V('victim'), 'snared')` if the
  enactor is *not* the one caught (store the victim id when it
  springs). Rescue beats brute force.
- **Timeout mercy** — give the effect `duration=30` instead of 0 and
  captivity expires on its own: a poacher's snare, not a dungeon.
- **The trapper's page** — splice in item 50's line:
  `pemit(owner(me), '[snare] Something is thrashing on the Game
  Trail.')` when it springs. Traps compose.
