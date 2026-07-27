# 143. XP Spending

> Checklist item 143 ([now]): *the native points/improve economy, a self-serve training terminal, now() cooldowns, owner authority*

**What you'll build:** a self-serve training terminal where a character
spends their own character points to raise a skill, but not all at once.
Each skill goes on a cooldown after you drill it, so advancement is paced by
the clock as well as by your wallet. It is the built-in economy with a
training-time governor added on top.

**Concepts:** the native `points`/`improve` economy (earned CP, 4 per level);
why a *paced* trainer rebuilds `improve` in softcode instead of wrapping it;
[`now()`](../reference/softcode.md#fn-now) timestamp arithmetic as a cooldown;
and the owner authority a terminal needs to write a player's sheet, exactly
like the coin-charging tutor in [069](069_trainer_npc.md).

## How it works

The finished terminal is a single object you `study` at. Typing `study melee`
checks whether that skill is still cooling down, then whether you can afford
the point, and only then raises the skill and deducts the cost. The cooldown
is remembered per player and per skill, so drilling one skill never locks
another. This section answers where the points come from, why the terminal
reimplements the built-in `improve` rather than intercepting it, how the
clock gate is just subtraction on `now()`, and why the terminal has to be
admin-owned.

### Where do character points come from, and what does `improve` do?

Advancement already ships in the engine. The built-in `points` command
(aliases `score` and `cp`) prints your character points and your trained
skills, and `improve <skill>` spends 4 CP to raise a skill by one level.
Characters earn CP through play: when a party kills an NPC, the death award
is split across the killer's party members who are present
([140](140_death_cloning.md)), and each spends their own points on
themselves with no NPC required. That built-in loop is the baseline. This
tutorial adds the *time-gated* road, where the [069](069_trainer_npc.md)
trainer is the *coin-gated* one.

### Why rebuild `improve` instead of wrapping it?

Built-in commands dispatch before softcode: the dispatcher matches a builtin
first and only falls through to `$`-command triggers when no builtin claims
the word. So a softcode `$improve` never runs while the native `improve`
exists, which means a cooldown has to live in a command of its own. The
training terminal offers `study`, and `study` does its own version of the
transaction: check the cooldown, check the points, then write the skill and
deduct the cost. It charges the same 4 CP, plus the governor the native
command leaves off.

### How does the cooldown work with `now()`?

[`now()`](../reference/softcode.md#fn-now) returns the current time as epoch
seconds. After a successful drill the terminal stamps
`last_<player>_<skill> = now()` on itself, and the next attempt is refused
while `now() - last < cooldown`. The key carries both the player id and the
skill name, so drilling Melee never blocks Stealth, and the whole limit is
two `@set`-able numbers, `cost` and `cooldown`. Repricing or re-pacing the
terminal is a single `@set` with no script edit, which is the same
data-first shape the [069](069_trainer_npc.md) trainer uses for its fees.

### Why must the terminal be admin-owned?

Raising *another* player's `skill_*` and spending *their* CP are mutations of
that player's sheet, and [`set_attr`](../reference/softcode.md#fn-set_attr)
allows a write only when the executor
[`controls()`](../reference/softcode.md#fn-controls) the target. A `$`-command
runs as the object that holds it, so the terminal is the executor, and an
object acts with its owner's authority. Owning the terminal with an admin
character therefore lets it reach any player's sheet, the same ownership
model behind the trainer, the survival master ([137](137_hunger_thirst.md)),
and the clone bay ([140](140_death_cloning.md)). The player typing `study`
consents to nothing beyond the transaction the terminal offers; the authority
to edit the sheet belongs to the terminal, by ownership.

## Build it

As your admin character, raise the annex and the terminal, then describe it:

```text
@dig The Training Annex = annex, out
annex
@create training terminal
drop training terminal
@desc training terminal = A neural-drill rig with a padded headset. STUDY <skill> to spend character points -- one drill per skill, then it needs time to set.
```

The two dials are plain numbers, so the whole limit repriced or re-paced is a
single `@set`. `cost` is the CP price of one drill; `cooldown` is the wait, in
seconds, before that same skill drills again:

```text
@set training terminal/cost = 4
@set training terminal/cooldown = 3600
```

Now the `study` command itself. It runs the three gates in order: the
cooldown, then the purse, then the transaction that raises the skill and
takes the points. It reads the price and wait off itself with
[`V`](../reference/softcode.md#fn-v) (shorthand for `get_attr(me, ...)`),
reads the player's current points and skill with
[`get_attr`](../reference/softcode.md#fn-get_attr), and writes both the
player and its own cooldown stamp with
[`set_attr`](../reference/softcode.md#fn-set_attr):

```text
@set training terminal/cmd_study = '''
$study *:
s = trim(arg0).lower().replace(' ', '_')
if not s:
    pemit(enactor, 'Name a skill to drill.')
else:
    cost = int(V('cost', 4))
    cd = int(V('cooldown', 3600))
    # per-player, per-skill key: drilling Melee never blocks Stealth
    last = int(V('last_' + enactor.id + '_' + s, 0))
    cp = int(get_attr(enactor, 'character_points', 0))
    # an untrained skill starts at the character's raw DX
    cur = int(get_attr(enactor, 'skill_' + s, get_attr(enactor, 'dexterity', 10)))
    nice = s.replace('_', ' ')
    if now() - last < cd:
        pemit(enactor, f'Neural buffers still consolidating {nice} -- {cd - (now() - last)}s to go.')
    elif cp < cost:
        pemit(enactor, f'Drilling {nice} costs {cost} CP; you have {cp}.')
    else:
        set_attr(enactor, 'skill_' + s, cur + 1)
        set_attr(enactor, 'character_points', cp - cost)
        set_attr(me, 'last_' + enactor.id + '_' + s, now())
        pemit(enactor, f'You drill {nice} hard. It clicks -- now {cur + 1}. ({cp - cost} CP left)')
'''
```

Both writes to the player go through the terminal's owner authority: because
an admin owns the terminal, [`set_attr`](../reference/softcode.md#fn-set_attr)
on the enactor succeeds where a player-owned object's write would be refused.
[`pemit`](../reference/softcode.md#fn-pemit) speaks privately to the enactor,
and [`trim`](../reference/softcode.md#fn-trim) trims the captured skill name.

## Try it

With 12 character points on the sheet (`points` to check), drill Melee, then
find the governor:

```text
study melee       -> You drill melee hard. It clicks -- now 11. (8 CP left)
study melee       -> Neural buffers still consolidating melee -- 3600s to go.
study stealth     -> You drill stealth hard. It clicks -- now 11. (4 CP left)
```

The countdown number on the refused line depends on the second the clock is
read, so it will vary. Melee is locked while Stealth is free, because the
cooldowns are keyed per skill. Wait out the timer, or as staff
`@set training terminal/cooldown = 0` to prove the gate opens, and Melee
drills again until the coin runs dry:

```text
study melee       -> You drill melee hard. It clicks -- now 12. (0 CP left)
study guns        -> Drilling guns costs 4 CP; you have 0.
```

Out of points, the terminal turns you away the same way the trainer's fee gate
does. The two roads compose with the native one: `improve melee` spends the
*same* CP with no cooldown at all, so a game can offer un-paced self-study,
time-gated drilling, and a coin-charging tutor ([069](069_trainer_npc.md))
side by side, all reading and writing the one `character_points` economy.

```text
improve stealth   -> You train stealth to 12 (0 points remain).
```

## Going further

- **Skill caps:** refuse when `cur >= V('cap', 15)`, so the terminal teaches
  fundamentals while mastery comes from play, the trainer's cap idiom.
- **Diminishing returns:** let `cost` climb with level, for example
  `cost = cur - 9`, so the first point is cheap and the twelfth is dear,
  GURPS's real point curve in one line.
- **Prerequisites:** gate `guns` on `get_attr(enactor, 'skill_melee', 0) >= 12`
  for a curriculum tree, the [069](069_trainer_npc.md) `needs` chain without
  the NPC.
- **Study time, not instant:** replace the immediate write with
  [`wait`](../reference/softcode.md#fn-wait) firing a follow-up command
  (`wait(30, 'trigger me/finish_' + enactor.id)`), so drilling *takes* time in
  real seconds, the [029](029_timed_door.md) timed pattern turned into a
  training montage.
