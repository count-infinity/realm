# 102. Trivia Host NPC

> Checklist item 102 ([now]): *pack/attr question data, prompt() answer windows, scoring*

**What you'll build:** Quizmaster Quill, a barroom NPC who runs timed
trivia rounds from a question list. He asks, the room shouts, the first
correct answer scores, and a clock closes the questions nobody gets.

**Concepts:** question data as a JSON attribute, a
[`^listen`](007_voice_recorder.md) trigger as the answer channel (so
everyone shouts at once, with no turn-taking),
[`wait()`](../reference/softcode.md#fn-wait) answer windows carrying a
*deadline stamp* so a stale timer cannot misfire, a
[`scores`](../reference/softcode.md#fn-set_attr) ledger, and pacing knobs
(`window`, `tempo`) kept in data.

## How it works

Quill holds a list of questions and walks it one at a time. Each ask
opens a timed window; whoever shouts the right answer first scores and
the round jumps ahead, and if the window runs out first Quill reads the
answer and moves on. The whole thing is five attributes: the question
data, a starter command, an asking helper, a clock, and a pair of ears.
This section explains where the answers come from, how the window closes
two different ways without the timers tripping over each other, and where
the score lives.

**Questions are data.** The `questions` attribute is a JSON list of
`{"q": ..., "a": ...}` rows. You edit it live, or ship a whole quiz night
as a pack and `@import` it, because the host does not care where the list
came from.

**Answers are speech.** A [`^*`](007_voice_recorder.md) listen trigger
hears everything said in Quill's room, binding the speaker as `enactor`
and the whole line as `arg0`. A listen trigger fires on the object that
carries it, so Quill alone reacts, and the engine skips an object's own
speech, so Quill never scores himself. There is no
[`prompt()`](../reference/softcode.md#fn-prompt) here on purpose: a prompt
captures one player's next line, but trivia is a race, and a listen
trigger hears everyone at once, which is the game. The guard is game
state, not a room-broadcast check: the shout counts only while a round is
`running`, the window is `open`, the speaker
[`has_tag`](../reference/softcode.md#fn-has_tag) `player`, and the trimmed
line contains the answer.

**The window is a wait with a stamp.** Asking a question sets `open` and
schedules [`wait(window, 'trigger me/times_up')`](../reference/softcode.md#fn-wait),
where `trigger me/times_up` is the script command that fires the
`times_up` attribute when the timer elapses. But a correct answer also
advances the round, and the old timer is still coming. The fix is a
`deadline` attribute stamped with [`now()`](../reference/softcode.md#fn-now)
at ask time: `times_up` acts only if the question is still `open` *and*
`now()` has actually reached that deadline, so a stale timer arriving
mid-next-question sees a fresh deadline and stands down. Waits are
in-memory, so a reboot mid-round stalls the game and `trivia` starts a
fresh one.

**Scores are a ledger.** The `scores` attribute maps each player name to
points on the host, and `standings` prints it sorted. `@examine Quizmaster
Quill` is the audit trail.

## Build it

The scripts here are `'''` multi-line blocks (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)).

Seat the host and give him a face:

```text
@create Quizmaster Quill
@tag Quizmaster Quill = npc
drop Quizmaster Quill
@desc Quizmaster Quill = A waistcoated fussbudget with index cards and a brass bell.
```

His material and pacing. The `questions` list is the whole quiz, `window`
is how many seconds a question stays open, and `tempo` is the pause
between questions:

```text
@set Quizmaster Quill/questions = [{"q": "Which planet wears the Great Red Spot?", "a": "jupiter"}, {"q": "How many faces has a d20?", "a": "20"}, {"q": "What do you pay a ferryman?", "a": "coin"}]
@set Quizmaster Quill/window = 20
@set Quizmaster Quill/tempo = 4
```

The starter. `$trivia` refuses if a game is already
[`running`](../reference/softcode.md#fn-v), otherwise it
[`set_attr`](../reference/softcode.md#fn-set_attr)s the round state, rings
the bell to the room with [`remit`](../reference/softcode.md#fn-remit),
and hands off to the asking helper with
[`eval_attr`](../reference/softcode.md#fn-eval_attr):

```text
@set Quizmaster Quill/cmd_start = '''
$trivia:
if V('running', 0):
    pemit(enactor, 'A game is already running.')
else:
    set_attr(me, 'running', 1)
    set_attr(me, 'idx', 0)
    set_attr(me, 'scores', {})
    remit(here, f'Quill rings his bell: Trivia! Shout your answers. {len(V("questions", []))} questions.')
    eval_attr(me, 'ask')
'''
```

The asking helper. It reads the current standings up front, then either
poses the next question (stamping the deadline and arming the timer) or,
once the list is exhausted, ends the game with the winner. `next_q` is the
one-line callback the timers fire to re-enter it:

```text
@set Quizmaster Quill/ask = '''
qs = V('questions', [])
i = V('idx', 0)
sc = V('scores', {})
top = max(sc.values()) if sc else 0
champs = ', '.join(sorted(nm for nm, pts in sc.items() if pts == top)) if sc else 'nobody'
if i < len(qs):
    set_attr(me, 'open', 1)
    set_attr(me, 'deadline', now() + V('window', 20))  # the time this question must be answered before
    remit(here, f'Question {i + 1}: {qs[i]["q"]}')
    wait(V('window', 20), 'trigger me/times_up')
else:
    set_attr(me, 'running', 0)
    remit(here, f'That is the game! Top score: {champs} with {top}.')
result = 1
'''
@set Quizmaster Quill/next_q = eval_attr(me, 'ask')
```

The clock. When the window elapses unanswered, `times_up`
[`incr`](../reference/softcode.md#fn-incr)ements the question index, reads
out the answer, and schedules the next question after `tempo` seconds. The
guard is the whole point:

```text
@set Quizmaster Quill/times_up = '''
qs = V('questions', [])
i = V('idx', 0)
# ignore a stale timer: fire only if this question is still open and its deadline has passed
if V('open', 0) and now() >= V('deadline', 0):
    set_attr(me, 'open', 0)
    incr('idx')
    remit(here, f'Time! The answer was: {qs[i]["a"]}.')
    wait(V('tempo', 4), 'trigger me/next_q')
'''
```

The ears. One `^*` trigger hears every line said in the room. When a live
question is open and the trimmed shout contains the answer, the first
correct speaker takes the point and the window closes:

```text
@set Quizmaster Quill/listen_guess = '''
^*:
# fires on every player's speech in the room; Quill never overhears himself
qs = V('questions', [])
i = V('idx', 0)
live = V('running', 0) and V('open', 0) and has_tag(enactor, 'player') and i < len(qs)
if live and qs[i]['a'] in trim(arg0).lower():
    nm = name(enactor)
    sc = V('scores', {})
    set_attr(me, 'open', 0)
    incr('idx')                     # i was read before this, so qs[i] is still the question just answered
    sc[nm] = sc.get(nm, 0) + 1
    set_attr(me, 'scores', sc)
    remit(here, f'{nm} has it: {qs[i]["a"]}! Score: {sc[nm]}.')
    wait(V('tempo', 4), 'trigger me/next_q')
'''
```

The leaderboard. `$standings` prints the ledger sorted high to low, or a
note when nobody has scored:

```text
@set Quizmaster Quill/cmd_scores = '''
$standings:
sc = V('scores', {})
pemit(enactor, 'Trivia standings:')
if not sc:
    pemit(enactor, '  (no scores yet)')
else:
    for nm, pts in sorted(sc.items(), key=lambda kv: -kv[1]):
        pemit(enactor, f'  {nm} -- {pts}')
'''
```

## Try it

```text
trivia               -> the bell, then "Question 1: Which planet wears the Great Red Spot?"
say saturn?          -> nothing; wrong guesses cost nothing
say jupiter!         -> "Kess has it: jupiter! Score: 1."
                        a beat later: "Question 2: How many faces has a d20?"
(say nothing)        -> after the window: "Time! The answer was: 20."
say coin             -> "Bob has it: coin! Score: 1."
standings            -> the ledger, sorted
                        then: "That is the game! Top score: Bob, Kess with 1."
```

Quill announces answers with [`remit`](../reference/softcode.md#fn-remit),
which is delivered text rather than speech, so his own announcements never
reach a listen trigger. Even if he spoke them aloud, the
[`has_tag(enactor, 'player')`](../reference/softcode.md#fn-has_tag) guard
would refuse him the point, and the engine skips an object's own speech
besides. A `^listen` needs no `target is me`
[guard](../reference/softcode.md#guard-on-target): it fires on Quill
alone, unlike an `ON_<EVENT>` hook that reacts on every object in the
room.

## Going further

- **Question packs:** move `questions` into a pack (`@pack`) per theme
  night and `@import` the evening's set, which is data-file trivia,
  literally.
- **Sudden death:** in `ask`'s finale branch, if two names share `top`,
  reset `questions` to a tiebreaker list and keep `running`.
- **House prizes:** give Quill a float and `transfer_credits(me, winner,
  purse)` in the finale, borrowing the [slot machine](001_slot_machine.md)
  seeding pattern.
- **Category picks:** between questions,
  [`prompt()`](../reference/softcode.md#fn-prompt) the current leader to
  choose the next category, using a prompt for the one decision that *is*
  single-player and the listen trigger for the race. See the
  [dialogue-tree NPC](067_dialogue_tree_npc.md) for prompt callback chains.
```