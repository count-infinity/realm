# 069. Trainer NPC

> Checklist item 69 — [now] — *CP economy, $-command wrappers, admin-owned sheet writes, data-driven curricula*

**What you'll build:** Sergeant Kel, who drills skills for coin. Her
curriculum — fees, level caps, prerequisites — is one data attribute a
staffer can reprice with a single `@set`. She takes real credits and
writes real skill levels onto the student's sheet, which only works
because of *whose* authority her scripts run with.
**Concepts:** the built-in CP economy (`points`, `improve`) and the
trainer as its credits-powered complement, `$`-command wrappers,
data-driven rules in a dict attribute, the guard-chain conditional
idiom, and **owner authority** — why the trainer must be admin-owned
to touch other players' sheets.

## How it works

**Skills and advancement already exist.** A skill is a
`skill_<name>` attribute; `points` shows your character points and
trained skills; `improve <skill>` spends 4 CP for +1. That's the
built-in economy — earned points, self-directed. A *trainer* adds the
other classic road: money for tutelage, with the world deciding what's
teachable, how far, and after what.

**The curriculum is data.** One dict attribute:

```
teaches = {"melee": {"fee": 15, "cap": 12},
           "guns":  {"fee": 25, "cap": 12, "needs": ["melee", 11]}}
```

Repricing, capping, adding a skill, chaining prerequisites — all
`@set`, no script edits. The `$train *` command just walks the record:
unknown skill → refusal; at `cap` → refusal; `needs` unmet → refusal;
can't pay → refusal; otherwise **take the fee and write the level**.
(The guard-chain of conditionals, item 64's idiom, stretched to four
gates.)

**The authority is the whole trick.** Scripts run as the NPC *with its
owner's power*. Writing `skill_melee` on another player and pulling
credits *from* them are mutations of someone else's sheet — softcode
permits them only if the executor `controls()` the target, and nobody
controls a player except an **admin** (or someone the player
delegated to via a control lock, item 66). So: **the trainer must be
created — owned — by an admin.** A builder-owned Kel would hit the
authority wall on both writes and fail silently. This is the audit's
"admin-owned masters may write other players' sheets" — the same
model as item 71's watch master moving its own guardsman, one rank
up. The flip side: the student *typed her command*, but typing a
`$`-command consents to relocation at most, never to sheet edits —
only ownership rank grants those.

## Build it

**As your admin character** (that ownership is load-bearing — see
above), dig the yard and post the sergeant:

```
@dig The Drill Yard = drills, out
drills
@create Sergeant Kel
@tag Sergeant Kel = npc
drop Sergeant Kel
@desc Sergeant Kel = Scarred forearms, patient eyes. She has taught worse than you.
@set Sergeant Kel/teaches = {"melee": {"fee": 15, "cap": 12}, "guns": {"fee": 25, "cap": 12, "needs": ["melee", 11]}}
```

The menu — read straight from the data, so it never goes stale:

```
@set Sergeant Kel/cmd_lessons = $lessons:t = V('teaches', {}); say(f"I drill: {', '.join(sorted(t))}. Coin first, bruises after. Say train and the skill.")
```

The lesson — four gates, then the transaction:

```
@set Sergeant Kel/cmd_train = $train *:s = trim(arg0).lower().replace(' ', '_'); t = V('teaches', {}); r = t.get(s); cur = get_attr(enactor, f'skill_{s}', 9); (say(f'I do not teach {s}. Ask about my lessons.') if not r else say(f'You are past my lessons in {s}. Spend points, or find a better teacher.') if cur >= r['cap'] else say(f"Not yet. Come back when your {r['needs'][0].replace('_', ' ')} reaches {r['needs'][1]}.") if 'needs' in r and get_attr(enactor, f"skill_{r['needs'][0]}", 9) < r['needs'][1] else say(f"My fee is {r['fee']} credits. You are short.") if credits(enactor) < r['fee'] else (transfer_credits(enactor, me, r['fee']), set_attr(enactor, f'skill_{s}', cur + 1), say(f"Again! ...Better. Your {s.replace('_', ' ')} is now {cur + 1}.")))
```

The `get_attr(enactor, 'skill_' + s, 9)` default of 9 is her house
rule: an untrained student's first lesson lands them at 10. (The
built-in `improve` derives untrained levels from governing attributes
instead — a trainer can be simpler because her `cap` bounds the
damage.)

## Try it

As a student (fund them from your staff character:
`@set <student>/credits = 100`):

```
lessons          → "I drill: guns, melee. Coin first, bruises after..."
train guns       → "Not yet. Come back when your melee reaches 11."
train melee      → "Again! ...Better. Your melee is now 10."  (-15 credits)
train melee      → ...now 11.   (-15)
train melee      → ...now 12.   (-15)
train melee      → "You are past my lessons in melee..."      (the cap)
train guns       → ...now 10.   (-25; the prerequisite is met)
train basketry   → "I do not teach basketry..."
points           → your sheet: skills and character points
```

Run yourself dry and she turns you away at the fee gate. And the two
economies compose: award CP for play (`character_points`), and
`improve melee` pushes past her cap 4 points at a time — coin buys
the fundamentals, experience buys mastery.

## Going further

- **Cooldowns:** store `lesson_<skill>_<id> = now()` on Kel and gate
  the transaction on `now() - ... > 3600` — one lesson per skill per
  hour, the bartender's cooldown idiom pointed at pedagogy.
- **Teach to her own level:** replace each `cap` with
  `V(f'skill_{s}', 10)` — she can't teach what she can't
  do, and *training the trainer* becomes worldbuilding.
- **Skill prerequisites from data:** `needs` chains arbitrarily deep
  through the same dict — a curriculum tree in one attribute.
- **Scholarships:** check `disposition(me, enactor)` and discount the
  fee for students she likes — `persuade` before class pays for
  itself (item 31's social layer).
- **New skills entirely:** a `skill_def` object (item 59's
  `fortitude` pattern) adds the skill to the game's table; Kel's dict
  gains a row; nobody restarts anything.
