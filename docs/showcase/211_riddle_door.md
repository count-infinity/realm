# 211. Riddle door

> Checklist item 211 ([now]): *free-text answers, normalized/fuzzy matching, string functions*

**What you'll build:** A stone sphinx guarding an arch. It poses a riddle, you
type your answer in plain English, and if you are right in any reasonable
phrasing the arch grinds open. "the echo", "An Echo!", and "ECHO" all pass,
while "a mountain" gets nothing.

**Concepts:** capturing free text straight off the command line with a
[`$`-command](../reference/softcode.md#triggers-attributes-on-objects) wildcard,
and **normalizing** it (lowercasing, stripping punctuation and articles,
collapsing runs of spaces) so a puzzle can accept a human answer instead of
demanding an exact string.

## How it works

The finished shape is three objects and two attributes: an arch sealed with the
`closed` and `locked` tags, a sphinx standing in front of it, and a single
`$answer *` command on the sphinx that folds whatever the player typed into a
canonical string and compares it against a stored list. This section answers
three questions, in the order you will hit them: how the sphinx hears an answer
at all, how three lines of string work turn messy typing into something
comparable, and what actually moves the arch.

### How the sphinx hears an answer typed in the open

Where the [keypad](210_keypad_code.md) used
[`prompt()`](../reference/softcode.md#fn-prompt) to keep a numeric code out of
scrollback, a riddle is meant to be answered out loud, so the answer rides in
the open on the command line. The pattern `$answer *` compiles to a
case-insensitive match against the player's whole input line, and the `*`
capture lands in the script as `arg0`, so `answer An Echo!` binds
`arg0 = 'An Echo!'`.

Two dispatch facts make this work without any wiring. First, built-in commands
are tried before `$`-triggers, and `answer` is not a built-in, so the input
falls through to the softcode search. Second, that search walks the room's
contents before the room itself and the player's inventory, which is why simply
standing in the landing with the sphinx is enough. The search also stops at the
**first** object whose pattern matches, so if you later drop a second sphinx in
the same room only one of them replies rather than both.

A `$`-command needs no `if target is me:` guard, because the player named this
object when they typed its verb. That guard belongs on reactive
[`ON_<EVENT>` hooks](../reference/softcode.md#lifecycle-hooks), which fire on
every object in the room and therefore have to ask whether the event was
theirs (see [Guard on `target`](../reference/softcode.md#guard-on-target)).

### How three lines turn messy text into one comparable string

The interesting work is the normalization, and it is three ordinary Python
statements over the captured text:

1. **Lowercase and collapse whitespace.** [`trim`](../reference/softcode.md#fn-trim)
   removes the leading and trailing spaces, `.lower()` flattens the case, and a
   `.split()` / `' '.join(...)` round trip squeezes internal runs of spaces, so
   `"  An   Echo "` becomes `"an echo"`.
2. **Drop punctuation.** A comprehension keeps only alphanumerics and spaces,
   which turns `"echo!"` and `"echo."` both into `"echo"`.
3. **Drop noise words.** Filtering out `a`, `an`, and `the` collapses `"the
   echo"` and the bare `"echo"` onto the same token.

Only `trim` is a softcode function here; `.lower()`, `.split()`, `.join()`, and
`.isalnum()` are plain Python string methods, and the sandbox runs them
directly, so no regex engine and no fuzzy-distance library is involved.

What comes out is a canonical string. The sphinx stores its accepted answers
already in that canonical form as a `|`-separated list, so one riddle can honour
several right answers, and membership in that list decides the door. That
`answers` attribute is plain data rather than code, so it stays a one-line
`@set` and the `'''` block form is reserved for the script that reads it.

### What actually moves the arch

The arch carries two tags that do different jobs, the same pairing the
[lever combination](209_lever_combination.md) uses. Traversal is gated by
`closed`, so walking into a `closed` exit reports "The sphinx arch is closed."
and goes nowhere. The `open` verb is gated separately by `locked`, and it
prints the exit's `locked_msg` instead of its default line, which is where you
tell the player that the sphinx, not their shoulder, is the mechanism.

A correct answer therefore only needs to
[`remove_tag`](../reference/softcode.md#fn-remove_tag) the `closed` tag. The
`locked` tag stays on afterwards, which costs nothing because it never gated
walking in the first place, and it keeps `open sphinx arch` answering with the
riddle's hint. One built-in route still gets past a `locked` exit: `pick`
succeeds on a lockpicking check and strips `locked`, after which `open` clears
`closed` too. That is the same escape hatch every locked door in the world
offers, so treat the riddle as the intended path rather than a sealed one.

## Build it

Dig the approach and the arch beyond it, then stand the sphinx in the landing.
The riddle itself lives in the sphinx's description, which also tells the player
the verb to use:

```text
@dig The Sphinx Landing = landing, out
landing
@dig The Hidden Shrine = sphinx arch, landing
@desc The Hidden Shrine = A moss-soft chamber. Water drips somewhere, echoing.
@create stone sphinx
drop stone sphinx
@desc stone sphinx = A basalt sphinx blocks the arch. It murmurs: "I speak without a mouth and hear without an ear. I have no body, but I come alive with the wind. What am I?" (ANSWER <your reply>.)
```

Seal the arch. The `closed` tag blocks the walk, `locked` makes the built-in
`open` verb refuse, and `locked_msg` replaces the generic refusal with a nudge
toward the sphinx:

```text
@tag sphinx arch = closed
@tag sphinx arch = locked
@set sphinx arch/locked_msg = The arch is solid rock. The sphinx must be answered, not forced.
```

Record the accepted answers, already lowercased and article-free so they match
what the normalizer produces. This is a data attribute, so it stays on one line:

```text
@set stone sphinx/answers = echo|voice
```

Now the judge, as a `'''` multi-line block (open the `@set` line with a trailing
`'''`, write the body, close with a line of just `'''`; see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)).
It runs in four steps: capture and fold the text, strip punctuation, drop
articles, then either open the arch and announce it with
[`remit`](../reference/softcode.md#fn-remit) or refuse privately with
[`pemit`](../reference/softcode.md#fn-pemit):

```text
@set stone sphinx/cmd_answer = '''
$answer *:
# arg0 is everything the player typed after the word "answer"
raw = ' '.join(trim(arg0).lower().split())
clean = ''.join([c for c in raw if c.isalnum() or c == ' '])
norm = ' '.join([w for w in clean.split() if w not in ('a', 'an', 'the')])
if norm in str(V('answers')).split('|'):
    # traversal keys on 'closed' alone, so 'locked' may stay and keep refusing the open verb
    remove_tag(get('sphinx arch'), 'closed')
    remit(loc(me), 'The sphinx inclines its head. The arch grinds open.')
else:
    pemit(enactor, 'The sphinx is unmoved. "That is not the word."')
'''
```

[`V('answers')`](../reference/softcode.md#fn-v) is shorthand for reading the
sphinx's own attribute, [`get`](../reference/softcode.md#fn-get) resolves the
arch by name, and [`loc(me)`](../reference/softcode.md#fn-loc) is the landing,
so the success line is heard by everyone standing there while the refusal goes
only to the person who guessed.

## Try it

Force is the first thing a player tries, and the `locked_msg` sends them back to
the sphinx:

```text
> open sphinx arch
The arch is solid rock. The sphinx must be answered, not forced.

> sphinx arch
The sphinx arch is closed.
```

A wrong guess earns a private brush-off:

```text
> answer a mountain
The sphinx is unmoved. "That is not the word."
```

Any reasonable phrasing of the right answer works, and the whole room hears it:

```text
> answer An Echo!
The sphinx inclines its head. The arch grinds open.

> sphinx arch
You leave sphinx arch.

The Hidden Shrine
-----------------
A moss-soft chamber. Water drips somewhere, echoing.
```

The two results worth confirming deliberately are that `the echo`, `ECHO`, and
`voice` all pass from a fresh build, since the normalization erased the
difference between them, and that the arch is walkable afterwards even though
`@examine sphinx arch` still shows the `locked` tag.

## Going further

- **Hint on repeated failure.** Count wrong answers on the sphinx with
  [`incr`](../reference/softcode.md#fn-incr) and, after three,
  [`pemit`](../reference/softcode.md#fn-pemit) a clue such as the answer's first
  letter. Pair it with the reset discipline in
  [item 218](218_puzzle_reset.md) so a stuck player is never stuck for good.
- **Spoken answers.** Swap the `$answer *` command for a listen trigger,
  `@set stone sphinx/listen_echo = ^*echo*: remove_tag(get('sphinx arch'), 'closed')`,
  so merely saying the word in the room opens the arch, which is
  [item 27](027_secret_door.md)'s spoken password applied to a riddle. Listen
  triggers overhear speech, shouts, out-of-character lines, and emits, so a
  `pose` goes unheard: the answer has to be *said*.
- **Randomized riddles.** Keep a one-line data attribute holding a list of
  riddle-and-answers pairs, pick one with
  [`rand`](../reference/softcode.md#fn-rand) on first approach, and store the
  chosen index so the answer set matches the question, which is the
  [trivia host](102_trivia_host.md)'s question bank shrunk to a single door.
- **Stricter matching.** For a password rather than a riddle, drop the article
  and synonym leniency and compare the exact normalized string. It is the same
  block with fewer lines in it.
