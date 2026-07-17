# 132. Chargen Walkthrough

> Checklist item 132 — [now] — *the native creation flow, GameSystem chargen steps, a live prompt() induction wizard, owner authority*

**What you'll build:** an in-world Induction Booth whose clerk walks a new
arrival through the same shape REALM's native character creation uses —
pick a background, pick a bonus skill, derive your vitals — except this
one is built live, in softcode, and you can add a question to it without
touching a line of engine code.

**Concepts:** REALM's native `create <name> <template>` chargen and the
`GameSystem.chargen_steps()` it drives; re-deriving that flow as a
softcode `prompt()` wizard; **owner authority** (writing a stranger's
sheet needs an admin-owned clerk, exactly like the trainer in
[069](069_trainer_npc.md)); and the two ways to change the initial
decisions — a code lever and a data lever.

## How it works

**REALM already has a creation flow — read it first.** When someone types
`create Rook soldier`, the engine (see
[How a Character Is Born](../concepts/character-creation.md)) asks the
active `GameSystem` three questions in order:

1. `apply_baseline(player)` writes the starting sheet (ST 10, HP 10…).
2. `chargen_steps()` returns a list of steps — GURPS ships two
   `ChoiceStep`s: **pick a template** (soldier/infiltrator/face/technician)
   and **pick a bonus skill**. The engine shows each step's prompt, runs
   its `apply` when the player answers, and stores progress in
   `db.chargen_step` so a reboot mid-creation resumes exactly where it
   left off.
3. `finish_chargen(player)` derives HP from ST, Dodge from DX+HT, and
   returns the "a soldier walks into the world" line.

**A "template" is just data.** The soldier is a dict of stats and skills
in the `TEMPLATES` table — nothing in the engine knows a soldier from a
face. That is why adding a class, a point-buy step, or removing the menu
entirely changes nothing else.

**This tutorial rebuilds that flow in the world.** Native chargen runs
*before* the player is in a room, so you can't `@set` your way into it —
it's the code lever (below). But its *shape* — a menu that writes stats
and skills onto a sheet, then derives vitals — is pure softcode, and
building it live teaches the flow better than reading it. Our Induction
Booth is that: an orientation clerk running a `prompt()` chain (the wizard
idiom from the [dialogue NPC](067_dialogue_tree_npc.md), pointed at
chargen), plus a second use for it — a *re-spec desk*, an in-fiction way
to let players change their background after the fact.

**Owner authority is load-bearing.** The clerk writes `strength`,
`skill_melee`, `hp` onto *another player's* sheet, and `prompt()` itself
requires control of the target. Softcode may mutate a player only if the
executor `controls()` them, and nobody controls a player except an
**admin** (the [069](069_trainer_npc.md) rule). So the clerk must be
created — owned — by an admin. A builder-owned clerk would fail every
write silently.

## Build it

**As your admin character**, dig the booth and post the clerk:

```text
@dig The Induction Booth = booth, out
booth
@create Orientation Clerk
@tag Orientation Clerk = npc
drop Orientation Clerk
@desc Orientation Clerk = A crisp officer behind a chrome desk, stylus poised over a fresh service record. Say ENLIST when you are ready to be inducted.
```

The backgrounds are one data attribute — the same "class is data" idea as
the native `TEMPLATES`, so re-pricing the whole roster is a single `@set`:

```text
@set Orientation Clerk/backgrounds = {"soldier": {"stats": {"strength": 12, "dexterity": 11, "health": 12}, "skills": {"melee": 12, "guns": 12}}, "scout": {"stats": {"strength": 10, "dexterity": 13, "health": 10}, "skills": {"stealth": 13, "climbing": 12}}}
@set Orientation Clerk/menu = bg = get_attr(me, 'backgrounds', {}); result = 'Choose a background -- ' + ', '.join(sorted(bg)) + '. Type the name.'
```

`enlist` opens the wizard (and refuses anyone already on file):

```text
@set Orientation Clerk/cmd_enlist = $enlist: (pemit(enactor, 'Your record is already filed; you are inducted.') if get_attr(enactor, 'template') else prompt(enactor, eval_attr(me, 'menu'), 'pick_bg'))
```

The first answer picks a background — write its stats and skills onto the
sheet, stamp the `template`, and chain into the next question. An
unrecognized answer just re-asks (`prompt` again inside the callback):

```text
@set Orientation Clerk/pick_bg = c = trim(arg0).lower(); bg = get_attr(me, 'backgrounds', {}); r = bg.get(c); (prompt(enactor, 'No such background. ' + eval_attr(me, 'menu'), 'pick_bg') if not r else ([set_attr(enactor, k, v) for k, v in r['stats'].items()], [set_attr(enactor, 'skill_' + k, v) for k, v in r['skills'].items()], set_attr(enactor, 'template', c), prompt(enactor, 'Filed as ' + c + '. Pick a bonus skill -- stealth, melee, or guns.', 'pick_skill')))
```

The second answer is the bonus skill — new at your DX if untrained, +1 if
already known (mirroring the native step's rule) — then hand off to
`finish`:

```text
@set Orientation Clerk/pick_skill = s = trim(arg0).lower().replace(' ', '_'); (prompt(enactor, 'Pick stealth, melee, or guns.', 'pick_skill') if s not in ['stealth', 'melee', 'guns'] else (set_attr(enactor, 'skill_' + s, (int(get_attr(enactor, 'skill_' + s)) + 1) if get_attr(enactor, 'skill_' + s) != None else int(get_attr(enactor, 'dexterity', 10))), eval_attr(me, 'finish', enactor.id)))
```

`finish` is the softcode of `finish_chargen`: derive HP from ST and Dodge
from DX+HT, and welcome them:

```text
@set Orientation Clerk/finish = p = get('#' + arg0); st = int(get_attr(p, 'strength', 10)); set_attr(p, 'hp', st); set_attr(p, 'max_hp', st); set_attr(p, 'dodge', 7 + (int(get_attr(p, 'dexterity', 10)) + int(get_attr(p, 'health', 10))) // 8); pemit(p, 'Induction complete. HP ' + str(st) + ', Dodge ' + str(get_attr(p, 'dodge', 8)) + '. Welcome to the service, ' + get_attr(p, 'template', 'recruit') + '.')
```

## Try it

As a fresh recruit standing in the booth:

```text
enlist            -> Choose a background -- scout, soldier. Type the name.
soldier           -> Filed as soldier. Pick a bonus skill -- stealth, melee, or guns.
melee             -> Induction complete. HP 12, Dodge 9. Welcome to the service, soldier.
```

Check the result with the native sheet command (see
[141](141_character_sheet.md)): `points` shows Melee at 13 (soldier's 12,
plus the bonus), Guns at 12, and the derived vitals are on the sheet. Fat-
finger the background and the wizard just asks again:

```text
enlist            -> Choose a background -- scout, soldier. Type the name.
wizard            -> No such background. Choose a background -- scout, soldier...
```

**Adding a question is one link in the chain.** Want to ask for a
homeworld? Add a `pick_home` callback that stamps `set_attr(enactor,
'homeworld', trim(arg0))` and then calls `eval_attr(me, 'finish',
enactor.id)`, and change `pick_skill`'s hand-off to prompt `pick_home`
instead of `finish`. No step-index bookkeeping, no engine change — the
wizard's "state" is just which callback the last `prompt()` named.

**The native levers, for comparison.** To change *create-time* chargen for
everyone (before players reach a room), reach for the smallest lever in
[Customizing Character Creation](../guides/custom-chargen.md):

- **Data lever** — `@create`/`@import` a `class_def` object (a background
  as data) or a `skill_def`; the GameSystem merges it into the native
  template/skill menu with no code. This is the same table the clerk's
  `backgrounds` dict imitates. → [Skills & Classes as Data](../guides/data-driven-rules.md)
- **Code lever** — override `chargen_steps()` in your `rules.py` subclass
  (add a point-buy step, reorder, or return `[]` for instant characters).
  That is Python in *your* game module, not an engine patch, and it is the
  one path that lives outside the softcode surface.

## Going further

- **Re-spec desk:** drop the `if get_attr(enactor, 'template')` guard and
  the same clerk becomes a background-change booth — charge a fee with
  `transfer_credits` first (the [toll gate](030_toll_gate.md) idiom).
- **Point-buy step:** add a `pick_stats` callback that reads a number and
  spends from a `build_points` pool before the background step — the same
  arithmetic the native point-buy lever would add.
- **Confirmation screen:** insert a `prompt(enactor, eval_attr(me,
  'preview', ...), 'confirm')` before `finish`, echoing the chosen sheet
  and only committing on "yes".
- **Persist across a disconnect:** pass `persistent=True` to the wizard's
  `prompt()`s and the half-finished induction survives a reboot — the same
  guarantee `db.chargen_step` gives the native flow.
