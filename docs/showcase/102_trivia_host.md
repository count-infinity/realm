# 102. Trivia Host NPC

> Checklist item 102 — [now] — *pack/attr question data, prompt() answer windows, scoring*

**What you'll build:** Quizmaster Quill, a barroom NPC who runs timed
trivia rounds from a question list: he asks, the room shouts, the first
correct answer scores, and the clock closes questions nobody gets.

**Concepts:** question data as a JSON attribute, `^listen` triggers as
the answer channel (everyone shouts at once — no turn-taking), `wait()`
answer windows with a *deadline stamp* so stale timers can't misfire, a
scores ledger, and pacing knobs (`window`, `tempo`) kept in data.

## How it works

**Questions are data.** The `questions` attribute is a JSON list of
`{"q": ..., "a": ...}` rows. Edit it live, or ship a whole quiz night
as a pack and `@import` it — the host doesn't care where the list came
from.

**Answers are speech.** A `^*` listen trigger hears everything said in
the room; the guard chain (`running`, `open`, speaker is a player,
answer substring in what they said) decides if it was a scoring shout.
No `prompt()` here on purpose: prompts capture one player's next line,
but trivia is a *race* — listen triggers hear everyone simultaneously,
which is the game.

**The window is a wait with a stamp.** Asking a question sets `open`
and schedules `wait(window, 'trigger me/times_up')`. But a correct
answer also advances the round — and the old timer is still coming.
The fix is a `deadline` attribute stamped at ask time: `times_up` only
acts if the question is still open *and* `now()` has actually reached
the deadline. A stale timer arriving mid-next-question sees a fresh
deadline and stands down. (Waits are in-memory — a reboot mid-round
stalls the game; `trivia` starts a fresh one.)

**Scores are a ledger.** `scores` maps player name → points on the
host; `standings` prints it sorted. `@examine Quizmaster Quill` is the
audit trail.

## Build it

The host and his material:

```text
@create Quizmaster Quill
@tag Quizmaster Quill = npc
drop Quizmaster Quill
@desc Quizmaster Quill = A waistcoated fussbudget with index cards and a brass bell.
@set Quizmaster Quill/questions = [{"q": "Which planet wears the Great Red Spot?", "a": "jupiter"}, {"q": "How many faces has a d20?", "a": "20"}, {"q": "What do you pay a ferryman?", "a": "coin"}]
@set Quizmaster Quill/window = 20
@set Quizmaster Quill/tempo = 4
```

Starting a round:

```text
@set Quizmaster Quill/cmd_start = $trivia: ok = not V('running', 0); [(set_attr(me, 'running', 1), set_attr(me, 'idx', 0), set_attr(me, 'scores', {}), remit(here, f'Quill rings his bell: Trivia! Shout your answers. {len(V("questions", []))} questions.'), eval_attr(me, 'ask')) for g in [ok] if g]; pemit(enactor, 'A game is already running.') if not ok else None
```

The asking engine — one helper that either poses the next question
(stamping the deadline and arming the timer) or ends the game with the
winner:

```text
@set Quizmaster Quill/ask = qs = V('questions', []); i = V('idx', 0); sc = V('scores', {}); top = max(sc.values()) if sc else 0; champs = ', '.join(sorted(nm for nm, pts in sc.items() if pts == top)) if sc else 'nobody'; (set_attr(me, 'open', 1), set_attr(me, 'deadline', now() + V('window', 20)), remit(here, f'Question {i + 1}: {qs[i]["q"]}'), wait(V('window', 20), 'trigger me/times_up')) if i < len(qs) else (set_attr(me, 'running', 0), remit(here, f'That is the game! Top score: {champs} with {top}.')); result = 1
@set Quizmaster Quill/next_q = eval_attr(me, 'ask')
```

The clock — note both guards, `open` *and* the deadline:

```text
@set Quizmaster Quill/times_up = qs = V('questions', []); i = V('idx', 0); (set_attr(me, 'open', 0), incr('idx'), remit(here, f'Time! The answer was: {qs[i]["a"]}.'), wait(V('tempo', 4), 'trigger me/next_q')) if V('open', 0) and now() >= V('deadline', 0) else None
```

The ears — first correct shout takes the point and closes the window:

```text
@set Quizmaster Quill/listen_guess = ^*: qs = V('questions', []); i = V('idx', 0); live = V('running', 0) and V('open', 0) and has_tag(enactor, 'player') and i < len(qs); hit = live and qs[i]['a'] in trim(arg0).lower(); sc = V('scores', {}); [(set_attr(me, 'open', 0), incr('idx'), sc.update({name(enactor): sc.get(name(enactor), 0) + 1}), set_attr(me, 'scores', sc), remit(here, f'{name(enactor)} has it: {qs[i]["a"]}! Score: {sc[name(enactor)]}.'), wait(V('tempo', 4), 'trigger me/next_q')) for g in [hit] if g]
```

The leaderboard:

```text
@set Quizmaster Quill/cmd_scores = $standings: sc = V('scores', {}); pemit(enactor, 'Trivia standings:'); [pemit(enactor, f'  {nm} -- {pts}') for nm, pts in sorted(sc.items(), key=lambda kv: -kv[1])]; pemit(enactor, '  (no scores yet)') if not sc else None
```

## Try it

```text
trivia               -> the bell, then "Question 1: Which planet wears the Great Red Spot?"
say saturn?          -> nothing; wrong guesses cost nothing
say jupiter!         -> "Kess has it: jupiter! Score: 1."
                        ...a beat later: "Question 2: How many faces has a d20?"
(say nothing)        -> after 20s: "Time! The answer was: 20."
say coin             -> "Bob has it: coin! Score: 1."
standings            -> the ledger, sorted
                        then: "That is the game! Top score: Bob, Kess with 1."
```

Quill never scores himself — listen triggers deliberately skip their
own speaker, so reading out an answer can't award him the point.

## Going further

- **Question packs:** move `questions` into a pack (`@pack`) per theme
  night and `@import` the evening's set — data-file trivia, literally.
- **Sudden death:** in `ask`'s finale branch, if two names share `top`,
  reset `questions` to a tiebreaker list and keep `running`.
- **House prizes:** give Quill a float and `transfer_credits(me,
  winner, purse)` in the finale — the [slot machine](001_slot_machine.md)
  seeding pattern.
- **Category picks:** between questions, `prompt()` the current leader
  to choose the next category — prompts for the one decision that *is*
  single-player, listens for the race.

**~~Engine gaps~~ — FIXED 2026-07-17.** The champion line used to be built
with `', '.join(sorted([nm for nm, pts in sc.items() if pts == top]))` — a
*list* comprehension, because the bare generator now above used to
`NameError` on the script-local `top` inside its filter: the sandbox
exec'd with split `globals`/`locals`, so genexprs and `lambda`s couldn't
see script locals. Scripts now share one namespace and the generator
works (full note on item 100). The list-comp form was never wrong, only
forced.
