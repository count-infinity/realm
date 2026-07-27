# 069. Trainer NPC

> Checklist item 69 ([now]): *CP economy, $-command wrappers, admin-owned sheet writes, data-driven curricula*

**What you'll build:** Sergeant Kel, who drills skills for coin. Her
curriculum (fees, level caps, prerequisites) is one data attribute a
staffer can reprice with a single `@set`. She takes real credits and
writes real skill levels onto the student's sheet, which only works
because of *whose* authority her scripts run with.

**Concepts:** the built-in CP economy (`points`, `improve`) and the
trainer as its credits-powered complement, `$`-command wrappers,
data-driven rules in a dict attribute, a guard-chain of refusal
conditionals, and **owner authority**, the reason the trainer must be
admin-owned to touch other players' sheets.

## How it works

Kel is one NPC carrying two `$`-commands. `$lessons` reads a menu
straight off a data attribute, and `$train <skill>` walks four refusal
gates and then, only if none of them fired, takes the fee and raises the
skill. This section covers three things: where a skill level lives, how
the curriculum stays as data, and why the whole trick hinges on who owns
Kel.

### Where does a skill level live?

A skill is a plain attribute, `skill_<name>`, on the character, and the
engine's check system reads that attribute directly (an untrained skill
falls back to a governing-attribute default). The built-in `points`
command lists your `character_points` and every `skill_` attribute you
have trained, and `improve <skill>` spends 4 character points for +1.
That is the built-in economy: earned points, spent by the player at
will. A *trainer* adds the other classic road, money for tutelage, with
the world deciding what is teachable, how far, and after what.

### Why keep the curriculum as data?

The whole curriculum is one dict attribute:

```
teaches = {"melee": {"fee": 15, "cap": 12},
           "guns":  {"fee": 25, "cap": 12, "needs": ["melee", 11]}}
```

Repricing a skill, raising a cap, adding a skill, or chaining a
prerequisite are all `@set`, never a script edit. The `$train` command
just walks the record: an unknown skill is a refusal, a level at `cap`
is a refusal, an unmet `needs` is a refusal, an empty purse is a refusal,
and otherwise it takes the fee and writes the level. That shape is a
guard-chain of conditionals, where each gate either refuses and stops or
falls through to the next, stretched here to four gates.

### Why must the trainer be admin-owned?

Scripts run as the NPC with its owner's power. Writing `skill_melee` onto
another player and pulling credits *from* them are both mutations of
someone else's sheet, and softcode permits those only when the executor
[`controls`](../reference/softcode.md#fn-controls) the target. Nobody
controls a player except an **admin** (or someone the player delegated to
with a control lock, [the puppet](066_puppet.md)). So Kel has to be
created, and therefore owned, by an admin. A builder-owned Kel hits the
authority wall on both writes and fails silently: the announcement still
prints while the credit and skill writes quietly do nothing, so the
student is told their skill rose when it did not. This is the audit's
"admin-owned masters may write other players' sheets." The
[Town Watch master](071_guard_response.md) runs with the same owner
authority but only over its own guardsman and cannot touch a player at
all, which is exactly why the trainer needs the higher admin rank: a
student is a player. The student typed the command, but typing a
`$`-command never authorizes a sheet edit; only the executor's ownership
rank does.

## Build it

**As your admin character** (that ownership is load-bearing, see above),
dig the yard and post the sergeant:

```text
@dig The Drill Yard = drills, out
drills
@create Sergeant Kel
@tag Sergeant Kel = npc
drop Sergeant Kel
@desc Sergeant Kel = Scarred forearms, patient eyes. She has taught worse than you.
```

Her whole curriculum is this one attribute, which `@set` stores as JSON,
so a staffer reprices the drill hall without ever touching a script:

```text
@set Sergeant Kel/teaches = {"melee": {"fee": 15, "cap": 12}, "guns": {"fee": 25, "cap": 12, "needs": ["melee", 11]}}
```

The menu reads straight from that data with
[`V`](../reference/softcode.md#fn-v) (shorthand for `get_attr(me, ...)`),
so it lists exactly what `teaches` holds and never goes stale:

```text
@set Sergeant Kel/cmd_lessons = '''
$lessons:
t = V('teaches', {})
say(f"I drill: {', '.join(sorted(t))}. Coin first, bruises after. Say train and the skill.")
'''
```

The lesson walks four refusal gates and, only if none fires, runs the
transaction. The `$train *` pattern binds the student's word as `arg0`;
[`trim`](../reference/softcode.md#fn-trim) cleans it,
[`get_attr`](../reference/softcode.md#fn-get_attr) reads the student's
current level with a house-rule default of 9, and
[`credits`](../reference/softcode.md#fn-credits) checks their purse. The
final `else` is the only place
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits) and
[`set_attr`](../reference/softcode.md#fn-set_attr) run. The gates fire in
order: skill not on the curriculum, level already at `cap`, prerequisite
in `needs` not yet met, and purse short of the fee.

```text
@set Sergeant Kel/cmd_train = '''
$train *:
s = trim(arg0).lower().replace(' ', '_')
t = V('teaches', {})
r = t.get(s)
cur = get_attr(enactor, f'skill_{s}', 9)  # untrained reads as 9, so a first lesson lands at 10
if not r:
    say(f'I do not teach {s}. Ask about my lessons.')
elif cur >= r['cap']:
    say(f'You are past my lessons in {s}. Spend points, or find a better teacher.')
elif 'needs' in r and get_attr(enactor, f"skill_{r['needs'][0]}", 9) < r['needs'][1]:
    say(f"Not yet. Come back when your {r['needs'][0].replace('_', ' ')} reaches {r['needs'][1]}.")
elif credits(enactor) < r['fee']:
    say(f"My fee is {r['fee']} credits. You are short.")
else:
    transfer_credits(enactor, me, r['fee'])   # takes the student's credits: works only under admin ownership
    set_attr(enactor, f'skill_{s}', cur + 1)  # writes the student's sheet: same ownership gate
    say(f"Again! ...Better. Your {s.replace('_', ' ')} is now {cur + 1}.")
'''
```

The default of 9 on that first `get_attr` is Kel's house rule, so an
untrained student's first lesson lands them at 10. Note that both writes
in the `else` return quietly and do nothing when the executor cannot
control the target, which is why a builder-owned Kel would announce
success while changing nothing: owner authority is what makes the
transaction real.

## Try it

As a student (fund them from your staff character:
`@set <student>/credits = 100`):

```text
lessons          -> "I drill: guns, melee. Coin first, bruises after..."
train guns       -> "Not yet. Come back when your melee reaches 11."
train melee      -> "Again! ...Better. Your melee is now 10."  (-15 credits)
train melee      -> ...now 11.   (-15)
train melee      -> ...now 12.   (-15)
train melee      -> "You are past my lessons in melee..."      (the cap)
train guns       -> ...now 10.   (-25; the prerequisite is met)
train basketry   -> "I do not teach basketry..."
points           -> your sheet: skills and character points
```

Run yourself dry and she turns you away at the fee gate. The two
economies compose: award character points for play, and `improve melee`
pushes past her cap four points at a time, so coin buys the fundamentals
while experience buys mastery.

## Going further

- **Cooldowns:** store `lesson_<skill>_<id> = now()` on Kel and gate the
  transaction on `now() - ... > 3600`, one lesson per skill per hour, the
  same [`now()`](../reference/softcode.md#fn-now) cooldown the
  [patrolling guard](061_patrolling_guard.md) uses for its challenge.
- **Teach to her own level:** replace each `cap` with
  `V(f'skill_{s}', 10)`, so she cannot teach what she cannot do, and
  *training the trainer* becomes worldbuilding.
- **Skill prerequisites from data:** `needs` chains arbitrarily deep
  through the same dict, a curriculum tree in one attribute.
- **Scholarships:** check
  [`disposition(me, enactor)`](../reference/softcode.md#fn-disposition)
  and discount the fee for students she likes, so `persuade` before class
  pays for itself ([the guarded exit](031_guarded_exit.md)'s social
  layer).
- **New skills entirely:** a `skill_def` object
  ([the gas bomb](048_gas_bomb.md)'s `fortitude` pattern) adds a skill to
  the game's table when `@reload` re-reads it, Kel's dict gains a row, and
  nobody restarts anything.
