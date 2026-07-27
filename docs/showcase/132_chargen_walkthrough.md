# 132. Chargen Walkthrough

> Checklist item 132 ([now]): *the native creation flow, GameSystem chargen steps, a live prompt() induction wizard, owner authority*

**What you'll build:** an in-world Induction Booth whose clerk walks a new
arrival through the same shape REALM's native character creation uses (pick a
background, pick a bonus skill, derive your vitals), except this one is built
live in softcode, and you can add a question to it without touching a line of
engine code.

**Concepts:** REALM's native creation flow and the `GameSystem.chargen_steps()`
it drives; re-deriving that flow as a softcode
[`prompt()`](../reference/softcode.md#fn-prompt) wizard; owner authority
(writing a stranger's sheet needs an admin-owned clerk, exactly like the
trainer in [069](069_trainer_npc.md)); and the two ways to change the initial
decisions, a code lever and a data lever.

## How it works

The finished booth is one NPC running a chain of `prompt()` questions. Each
answer writes onto the recruit's sheet and asks the next question, until a
final step derives their vitals. Before building it, it helps to see the engine
flow the booth mirrors, because the booth is a faithful softcode copy of it.

### What the engine does when a character is created

When someone creates a character with `create Rook <password>`, the engine (see
[How a Character Is Born](../concepts/character-creation.md)) asks the active
`GameSystem` three things in order:

1. `apply_baseline(player)` writes the starting sheet (ST 10, HP 10, and the
   rest of the defaults).
2. `chargen_steps()` returns a list of steps. GURPS ships two `ChoiceStep`s:
   pick a background (soldier, infiltrator, face, or technician, answered by
   number or by name) and pick a bonus skill. The engine shows each step's
   prompt, runs its `apply` when the player answers, and stores progress in
   `db.chargen_step`, so a reboot mid-creation resumes exactly where it left
   off.
3. `finish_chargen(player)` derives HP from ST and Dodge from DX and HT, then
   returns the "a soldier walks into the world" line.

A background is just data: the soldier is a dict of stats and skills in the
`TEMPLATES` table, and nothing in the engine knows a soldier from a face. That
is why adding a class, adding a point-buy step, or removing the menu entirely
changes nothing else.

### Why rebuild it in the world

Native chargen runs before the player is in a room, so you cannot `@set` your
way into it: that is the code lever, described at the end. Its shape, though (a
menu that writes stats and skills onto a sheet and then derives vitals), is pure
softcode, and building it live teaches the flow better than reading it. The
Induction Booth is that build: an orientation clerk running a `prompt()` chain
(the wizard idiom from the [dialogue-tree NPC](067_dialogue_tree_npc.md),
pointed at chargen), plus a second use for the same clerk as a re-spec desk, an
in-fiction way to let players change their background after the fact.

### Why the clerk must be admin-owned

The clerk writes `strength`, `skill_melee`, and `hp` onto another player's
sheet, and [`set_attr`](../reference/softcode.md#fn-set_attr) succeeds only when
the executor controls the target. Softcode may mutate a player only if the
executor `controls()` them, and nobody controls a player except an admin (the
[069](069_trainer_npc.md) rule). So the clerk must be created, and therefore
owned, by an admin. A builder-owned clerk would run the prompts fine, since a
`prompt()` does not itself need control, but every write onto the recruit would
fail silently, and the sheet would never be filled in.

## Build it

As your admin character, dig the booth, step inside, and post the clerk. The
`ENLIST` cue in the description tells a new arrival how to begin:

```text
@dig The Induction Booth = booth, out
booth
@create Orientation Clerk
@tag Orientation Clerk = npc
drop Orientation Clerk
@desc Orientation Clerk = A crisp officer behind a chrome desk, stylus poised over a fresh service record. Say ENLIST when you are ready to be inducted.
```

The backgrounds are one data attribute, the same "class is data" idea as the
native `TEMPLATES`, so re-pricing the whole roster is a single `@set`:

```text
@set Orientation Clerk/backgrounds = {"soldier": {"stats": {"strength": 12, "dexterity": 11, "health": 12}, "skills": {"melee": 12, "guns": 12}}, "scout": {"stats": {"strength": 10, "dexterity": 13, "health": 10}, "skills": {"stealth": 13, "climbing": 12}}}
```

The menu is a function attribute: [`eval_attr(me, 'menu')`](../reference/softcode.md#fn-eval_attr)
runs it and hands back its `result`. It reads the `backgrounds` table with
[`V()`](../reference/softcode.md#fn-v) and lists the names, so re-pricing the
roster re-labels the menu with no further edit:

```text
@set Orientation Clerk/menu = '''
bg = V('backgrounds', {})
result = 'Choose a background -- ' + ', '.join(sorted(bg)) + '. Type the name.'
'''
```

`enlist` opens the wizard, and refuses anyone already on file. The
[`prompt()`](../reference/softcode.md#fn-prompt) captures the enlistee's next
line into `pick_bg`:

```text
@set Orientation Clerk/cmd_enlist = '''
$enlist:
if get_attr(enactor, 'template'):
    pemit(enactor, 'Your record is already filed; you are inducted.')
else:
    prompt(enactor, eval_attr(me, 'menu'), 'pick_bg')
'''
```

The answer arrives in `pick_bg` bound as `arg0`, and the callback runs as the
clerk. A recognized background writes its stats and skills onto the sheet with
[`set_attr`](../reference/softcode.md#fn-set_attr), stamps the `template`, and
chains into the next question; an unrecognized answer just re-asks by prompting
`pick_bg` again:

```text
@set Orientation Clerk/pick_bg = '''
c = trim(arg0).lower()
bg = V('backgrounds', {})
r = bg.get(c)
if not r:
    prompt(enactor, 'No such background. ' + eval_attr(me, 'menu'), 'pick_bg')
else:
    for k, v in r['stats'].items():
        set_attr(enactor, k, v)
    for k, v in r['skills'].items():
        set_attr(enactor, 'skill_' + k, v)
    set_attr(enactor, 'template', c)
    prompt(enactor, 'Filed as ' + c + '. Pick a bonus skill -- stealth, melee, or guns.', 'pick_skill')
'''
```

The second answer is the bonus skill: new at the recruit's DX if untrained, or
+1 if already known, which mirrors the native step's rule. A skill outside the
offered set re-asks; otherwise the callback hands off to `finish`:

```text
@set Orientation Clerk/pick_skill = '''
s = trim(arg0).lower().replace(' ', '_')
if s not in ['stealth', 'melee', 'guns']:
    prompt(enactor, 'Pick stealth, melee, or guns.', 'pick_skill')
else:
    current = get_attr(enactor, 'skill_' + s)
    if current is None:
        set_attr(enactor, 'skill_' + s, int(get_attr(enactor, 'dexterity', 10)))
    else:
        set_attr(enactor, 'skill_' + s, int(current) + 1)
    eval_attr(me, 'finish', enactor.id)
'''
```

`finish` is the softcode of `finish_chargen`. It looks up the recruit by id with
[`get`](../reference/softcode.md#fn-get) (`arg0` is the id passed by
`pick_skill`), derives HP from ST and Dodge from DX and HT, and welcomes them
with [`pemit`](../reference/softcode.md#fn-pemit):

```text
@set Orientation Clerk/finish = '''
p = get('#' + arg0)
st = int(get_attr(p, 'strength', 10))
set_attr(p, 'hp', st)
set_attr(p, 'max_hp', st)
dodge = 7 + (int(get_attr(p, 'dexterity', 10)) + int(get_attr(p, 'health', 10))) // 8
set_attr(p, 'dodge', dodge)
pemit(p, 'Induction complete. HP ' + str(st) + ', Dodge ' + str(dodge) + '. Welcome to the service, ' + get_attr(p, 'template', 'recruit') + '.')
'''
```

`finish` reaches the recruit through `eval_attr`, which runs a subroutine with
the caller's authority on the same queue, so its `set_attr` writes and its
`pemit` flush with the clerk's turn and land under the clerk's ownership.

## Try it

As a fresh recruit standing in the booth:

```text
enlist            -> Choose a background -- scout, soldier. Type the name.
soldier           -> Filed as soldier. Pick a bonus skill -- stealth, melee, or guns.
melee             -> Induction complete. HP 12, Dodge 9. Welcome to the service, soldier.
```

Check the result with the native sheet command (see
[141](141_character_sheet.md)): `points` shows Melee at 13 (soldier's 12 plus
the bonus), Guns at 12, and the derived vitals are on the sheet. Fat-finger the
background and the wizard just asks again:

```text
enlist            -> Choose a background -- scout, soldier. Type the name.
wizard            -> No such background. Choose a background -- scout, soldier. Type the name.
```

While a prompt is pending, the recruit's next line is the answer, but a line
starting with `help`, `quit`, or `exit` still falls through to the game, so a
half-finished induction never traps anyone.

**Adding a question is one link in the chain.** To ask for a homeworld, add a
`pick_home` callback that stamps `set_attr(enactor, 'homeworld', trim(arg0))`
and then calls `eval_attr(me, 'finish', enactor.id)`, and change `pick_skill`'s
hand-off to prompt `pick_home` instead of `finish`. There is no step-index
bookkeeping and no engine change, because the wizard's state is just which
callback the last `prompt()` named.

**The native levers, for comparison.** To change create-time chargen for
everyone (before players reach a room), reach for the smallest lever in
[Customizing Character Creation](../guides/custom-chargen.md):

- **Data lever:** `@create` or `@import` a `class_def` object (a background as
  data) or a `skill_def`, and the GameSystem merges it into the native template
  or skill menu with no code. This is the same table the clerk's `backgrounds`
  dict imitates. See [Skills and Classes as Data](../guides/data-driven-rules.md).
- **Code lever:** override `chargen_steps()` in your `rules.py` subclass (add a
  point-buy step, reorder the steps, or return `[]` for instant characters).
  That is Python in your own game module, not an engine patch, and it is the one
  path that lives outside the softcode surface.

## Going further

- **Re-spec desk:** drop the `if get_attr(enactor, 'template')` guard and the
  same clerk becomes a background-change booth. Charge a fee with
  `transfer_credits` first (the [toll gate](030_toll_gate.md) idiom).
- **Point-buy step:** add a `pick_stats` callback that reads a number and spends
  from a `build_points` pool before the background step, the same arithmetic the
  native point-buy lever would add.
- **Confirmation screen:** insert a `prompt(enactor, eval_attr(me, 'preview',
  ...), 'confirm')` before `finish`, echoing the chosen sheet and only
  committing on "yes".
- **Persist across a disconnect:** pass `persistent=True` to the wizard's
  `prompt()`s and the half-finished induction survives a reboot, the same
  guarantee `db.chargen_step` gives the native flow.
