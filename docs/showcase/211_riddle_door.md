# 211. Riddle door

> Checklist item 211 — now — *free-text answer, normalized/fuzzy matching, string functions*

**What you'll build:** A stone sphinx guarding an arch. It poses a riddle;
you type your answer in plain English; if you're right — in any
reasonable phrasing — the arch grinds open. "the echo", "An Echo!", and
"ECHO" all pass; "a mountain" does not.

**Concepts:** capturing free text straight off the command line with a
`$`-command wildcard, and **normalizing** it — lowercasing, stripping
punctuation and articles, collapsing spaces — so a puzzle can accept a
human answer instead of demanding an exact string.

## How it works

Where the [keypad](210_keypad_code.md) used `prompt()` for a secret code,
a riddle is *meant* to be spoken aloud, so the answer rides in the open
on the command line: `$answer *` captures everything after `answer ` as
`arg0`. The interesting work is turning messy human text into something
comparable:

1. **Lowercase and collapse whitespace** — `trim(arg0).lower()` and a
   `split()`/`join()` round-trip fold `"  An   Echo "` down to
   `"an echo"`.
2. **Drop punctuation** — a comprehension keeps only alphanumerics and
   spaces, so `"echo!"` and `"echo."` become `"echo"`.
3. **Drop noise words** — filtering out `a`, `an`, `the` means the phrasing
   `"the echo"` and the bare `"echo"` reduce to the same token.

What's left is a canonical string. The sphinx stores its accepted
answers already in that canonical form — a `|`-separated list, so one
riddle can honour several right answers — and simple membership decides
the door. No regex, no fuzzy-distance library; just the string helpers
(`trim`, `lower`, `split`) plus a comprehension, all sandbox-cheap.

The arch is the now-familiar `closed`+`locked` exit from
[item 209](209_lever_combination.md): the sphinx's `remove_tag` is the
only thing that opens it.

## Build it

Dig the approach and the arch beyond it, and seal the arch:

```text
@dig The Sphinx Landing = landing, out
landing
@dig The Hidden Shrine = sphinx arch, landing
@desc The Hidden Shrine = A moss-soft chamber. Water drips somewhere, echoing.
@tag sphinx arch = closed
@set sphinx arch/locked = true
@set sphinx arch/locked_msg = The arch is solid rock. The sphinx must be answered, not forced.
```

The sphinx. Its riddle lives in the description; its answers live in a
canonical (lowercased, article-free) `|`-list:

```text
@create stone sphinx
drop stone sphinx
@desc stone sphinx = A basalt sphinx blocks the arch. It murmurs: "I speak without a mouth and hear without an ear. I have no body, but I come alive with the wind. What am I?" (ANSWER <your reply>.)
@set stone sphinx/answers = echo|voice
```

The judge — capture, normalize, compare:

```text
@set stone sphinx/cmd_answer = $answer *: raw = ' '.join(trim(arg0).lower().split()); clean = ''.join([c for c in raw if c.isalnum() or c == ' ']); norm = ' '.join([w for w in clean.split() if w not in ('a', 'an', 'the')]); (remove_tag(get('sphinx arch'), 'closed'), remit(loc(me), 'The sphinx inclines its head. The arch grinds open.')) if norm in str(get_attr(me, 'answers')).split('|') else pemit(enactor, 'The sphinx is unmoved. "That is not the word."')
```

## Try it

A wrong guess earns nothing:

```text
answer a mountain    -> The sphinx is unmoved. "That is not the word."
```

Any reasonable phrasing of the right answer works:

```text
answer An Echo!      -> The sphinx inclines its head. The arch grinds open.
sphinx arch          -> the Hidden Shrine
```

Try it again from scratch with `the echo`, `ECHO`, or `voice` — all pass;
the normalization erased the difference. And `open sphinx arch` never
works: the sphinx is the only key.

## Going further

- **Hint on repeated failure** — count wrong answers and, after three,
  have the sphinx `pemit` a clue (the description's first letters), the
  anti-frustration reflex this whole chapter cares about (see
  [item 218](218_puzzle_reset.md)).
- **Spoken answers** — swap `$answer *` for a `^*echo*` listen so that
  merely *saying* the word in the room opens the arch — knowledge as a
  password, from [item 27](027_secret_door.md)'s "a knock that opens it".
- **Randomized riddles** — keep a list of `[riddle, answers]` pairs and
  have the sphinx pick one with `rand()` on first approach, storing the
  chosen index so its answer set matches — the [trivia host](102_trivia_host.md)'s
  question bank.
- **Stricter matching** — for a password rather than a riddle, drop the
  article/synonym leniency and compare the exact normalized string; the
  same three lines, fewer of them.
