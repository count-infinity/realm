# 248. Custom input handling

> Checklist item 248 — [now] — *prompt() for modal/line-based capture: the input-handler seam*

**What you'll build:** a quiz terminal that asks a question and reads the
player's *next raw line* as the answer — a modal, line-based capture that
sidesteps the command parser entirely. Then a two-question chain, to show
how far the seam goes.

**Concepts:** the softcode `prompt()` function, the session input-handler
seam, callbacks that run *as the executor* with the answer as `arg0`, and
the built-in escape words that keep a player from getting trapped.

## How it works

Normally every line a player types is a *command* — the dispatcher parses
it and runs a verb. Sometimes you want the opposite: ask a question and
treat the very next line as plain data, whatever it says. That is
`prompt()`, and it's the same seam the character-creation wizards
([016](016_combination_safe.md)-style) and the [typewriter](010_typewriter.md)
use.

`prompt(player, text, callback)`:

1. sends `text` to the player and installs a one-shot **input handler**
   on their session;
2. their next line is captured — *not* parsed as a command — and passed
   as `arg0` to the `callback` attribute, which runs **as the executor**
   (the terminal), with its authority;
3. the handler releases automatically, so the player is back to normal
   commands.

Chain by calling `prompt()` again inside the callback — question two
after answer one. Pass `persistent=True` and the pending prompt is stored
on the player (`db.input_prompt`) so it survives a reboot; the default is
in-memory. A few words always escape the capture — `help`, `quit`,
`exit` pass straight through, so a confused player is never stuck.

The callback runs with the terminal's authority, so it can remember the
answer (`set_attr(me, …)`), score it, react, or move on — but it can't
touch anything the terminal doesn't control, the same sandbox rule as
every other script.

## Build it

A quiz terminal. `$quiz` asks a question and names the callback;
`check_answer` grades whatever the player types next:

```text
@create quiz terminal
drop quiz terminal
@set quiz terminal/cmd_quiz = $quiz:prompt(enactor, 'Capital of the inner colony? ', 'check_answer')
@set quiz terminal/check_answer = pemit(enactor, 'Correct!' if arg0.lower() == 'helios' else 'Wrong. It is Helios.')
```

`enactor` in `check_answer` is still the player who ran `quiz`, and
`arg0` is their raw answer line — `"Helios"`, `"helios"`, or anything
else, unparsed. No command matched it; the input handler ate it.

## Try it

```text
> quiz
Capital of the inner colony?
> Helios
Correct!
> quiz
Capital of the inner colony?
> Tyr
Wrong. It is Helios.
```

Note the second line each time isn't a command — `Helios` and `Tyr` would
be "unknown command" normally. Inside the prompt they're just the answer.

## Going further

- **A chain:** have `check_answer` call `prompt(enactor, 'Round two:
  …', 'check_two')` — as many questions as you like, one attribute each.
- **Remember the reply:** `set_attr(me, 'last_score_' + str(enactor.id),
  arg0)` in the callback — the terminal keeps a scoreboard.
- **A line-based minigame:** a `wait()` between prompts makes a timed
  round; a counter attribute makes "best of five." The
  [jukebox](003_jukebox.md) request queue is the same shape.
- **Survive a reboot:** `prompt(enactor, '…', 'cb', persistent=True)` for
  a question that must outlast a restart (item [246](246_hot_reload.md)) —
  the pending prompt is stored on the player, not just in memory.
- **Free-text capture:** a suggestion box or a mailbox uses `prompt()` to
  take a whole line of prose the parser would otherwise choke on.
