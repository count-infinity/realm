# 143. XP Spending

> Checklist item 143 — [now] — *the native points/improve economy, a self-serve training terminal, time-gating with now(), owner authority*

**What you'll build:** a self-serve training terminal where a character
spends their own character points to raise a skill — but not all at once.
Each skill goes on a **cooldown** after you drill it, so advancement is
paced by the clock, not just by your wallet. It's the built-in economy with
a training-time governor bolted on.

**Concepts:** the native `points`/`improve` economy (earned CP, 4 per
level); why a *paced* version has to reimplement `improve` in softcode
(built-ins can't be intercepted); `now()` timestamp arithmetic as a
cooldown; and the owner authority a terminal needs to write a player's
sheet ([069](069_trainer_npc.md)).

## How it works

1. **Advancement already exists.** `points` (aliases `score`, `cp`) shows
   your character points and trained skills; `improve <skill>` spends 4 CP
   for +1. Characters *earn* CP by play — the death award splits points to
   the killer's party ([140](140_death_cloning.md)) — and spend them on
   themselves, no NPC required. That built-in loop is the baseline; this
   tutorial is the *time-gated* road, where the [069](069_trainer_npc.md)
   trainer was the *coin-gated* one.

2. **A paced trainer must reimplement `improve`.** Built-in commands
   dispatch *before* softcode, so you can't wrap or intercept `improve` to
   add a cooldown — `improve` will always run un-gated. The training
   terminal therefore does its own version: check the cooldown, check the
   CP, then write the skill and deduct the points itself. Same 4-CP price,
   plus a governor the native command doesn't have.

3. **The cooldown is `now()` arithmetic.** After a successful drill the
   terminal stamps `last_<player>_<skill> = now()` on itself. The next
   attempt refuses if `now() - last < cooldown`. Per-skill, per-player keys
   mean drilling Melee never blocks Stealth, and the whole limit is two
   `@set`-able numbers (`cost`, `cooldown`) — reprice or re-pace with no
   script edit, the [069](069_trainer_npc.md) data-first idiom.

4. **Writing the sheet needs owner authority.** Raising *another* player's
   `skill_*` and spending *their* CP are mutations of their sheet, allowed
   only to something that `controls()` them — an admin. So the terminal is
   **admin-owned**, exactly like the trainer, the survival master
   ([137](137_hunger_thirst.md)), and the clone bay
   ([140](140_death_cloning.md)). The player typing `study` consents to
   nothing beyond the transaction the terminal offers; the authority to
   edit the sheet is the terminal's, by ownership.

## Build it

**As your admin character**, raise the annex and the terminal, and set its
two dials:

```text
@dig The Training Annex = annex, out
annex
@create training terminal
drop training terminal
@desc training terminal = A neural-drill rig with a padded headset. STUDY <skill> to spend character points -- one drill per skill, then it needs time to set.
@set training terminal/cost = 4
@set training terminal/cooldown = 3600
@set training terminal/cmd_study = $study *: s = trim(arg0).lower().replace(' ', '_'); (pemit(enactor, 'Name a skill to drill.') if not s else eval_attr(me, 'drill', enactor.id, s))
```

The drill itself — cooldown gate, then CP gate, then the transaction:

```text
@set training terminal/drill = p = get('#' + arg0); s = arg1; cost = int(V('cost', 4)); cd = int(V('cooldown', 3600)); last = int(V('last_' + p.id + '_' + s, 0)); cp = int(get_attr(p, 'character_points', 0)); cur = int(get_attr(p, 'skill_' + s, get_attr(p, 'dexterity', 10))); (pemit(p, 'Neural buffers still consolidating ' + s.replace('_', ' ') + ' -- ' + str(cd - (now() - last)) + 's to go.') if now() - last < cd else (pemit(p, 'Drilling ' + s.replace('_', ' ') + ' costs ' + str(cost) + ' CP; you have ' + str(cp) + '.') if cp < cost else (set_attr(p, 'skill_' + s, cur + 1), set_attr(p, 'character_points', cp - cost), set_attr(me, 'last_' + p.id + '_' + s, now()), pemit(p, 'You drill ' + s.replace('_', ' ') + ' hard. It clicks -- now ' + str(cur + 1) + '. (' + str(cp - cost) + ' CP left)'))))
```

## Try it

With 12 character points on the sheet (`points` to check), drill Melee —
then find the governor:

```text
study melee       -> You drill melee hard. It clicks -- now 11. (8 CP left)
study melee       -> Neural buffers still consolidating melee -- 3599s to go.
study stealth     -> You drill stealth hard. It clicks -- now 11. (4 CP left)
```

Melee is locked but Stealth isn't — the cooldowns are per-skill. Wait out
the timer (or, as staff, `@set training terminal/cooldown = 0` to prove the
gate opens) and Melee drills again until the coin runs dry:

```text
study melee       -> You drill melee hard. It clicks -- now 12. (0 CP left)
study guns        -> Drilling guns costs 4 CP; you have 0.
```

Out of points, the terminal turns you away exactly like the trainer's fee
gate. And the two roads compose with the native one: `improve melee` spends
the *same* CP with no cooldown at all — so a game can offer un-paced
self-study, time-gated drilling, and a coin-charging tutor
([069](069_trainer_npc.md)) side by side, all reading and writing the one
`character_points` economy.

## Going further

- **Skill caps:** refuse when `cur >= V('cap', 15)` — the terminal teaches
  fundamentals, mastery comes from play (the trainer's cap idiom).
- **Diminishing returns:** make `cost` climb with level — `cost = cur - 9`
  — so the first point is cheap and the twelfth is dear, GURPS's real
  point curve in one line.
- **Prerequisites:** gate `guns` on `get_attr(p, 'skill_melee', 0) >= 12`
  — a curriculum tree, the [069](069_trainer_npc.md) `needs` chain without
  the NPC.
- **Study time, not instant:** replace the immediate write with a
  `wait(30, 'trigger me/finish_' + p.id)` so drilling *takes* the cooldown
  in real time — the [029](029_timed_door.md) ticket pattern turned into a
  training montage.
