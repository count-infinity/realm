# 244. Player macros

> Checklist item 244 — [now] — *personal gadget $-commands running multi-line bodies; the sandbox is the safeguard*

**What you'll build:** a wrist "macro band" a *player* owns — she records
a named sequence of ordinary commands and replays it with one word. Then
you'll watch the safeguards hold: a macro can't do anything its owner
couldn't type herself, oversized macros are refused, and the sandbox caps
a runaway.

**Concepts:** player-owned `$`-command gadgets, `force()` acting with the
*enactor's* own authority, wildcard captures (`arg0`/`arg1`), a self-
imposed step cap, and the sandbox limits as the real fence.

## How it works

A "macro" is the oldest client-side convenience — bind several commands
to one keyword. REALM does it *server-side, in softcode*, so it survives
across clients and needs no special engine feature: it's item
[250](250_player_scripting.md)'s player-scripting sandbox pointed at a
humble job.

The band is a gadget the player owns, carrying two `$`-verbs:

- `$record <name> = <commands>` stores a `|`-separated command list in a
  `macro_<name>` attribute (data, like everything else).
- `$play <name>` replays it: for each step, `force(enactor, step)`.

The safety story is entirely about *whose authority runs the steps*.
`force()` only drives an object the executor **controls**, and the one
object a player's own gadget controls (through the owner) is the player
herself. So `force(enactor, ...)` runs each command exactly as if the
player had typed it — a macro can never do what its owner couldn't. That
is the whole security model: no privilege to escalate, because the macro
borrows the player's own hands, nothing more.

Three fences back it up:

1. **No escalation.** `force(enactor, '@dig …')` from a non-builder is
   just a non-builder typing `@dig` — denied.
2. **A step cap.** `record` refuses more than ten steps, and `play`
   slices to ten, so a macro can't become a command bomb.
3. **The sandbox.** Output, call, time, and recursion budgets (item 250)
   kill any replay that tries to flood or spin.

The `use` lock (`caller == owner`) keeps the band personal, and `@chown`
halts it for review on transfer — the same handover you saw for the
Chrono-Cube.

## Build it

**Staff side.** A builder makes the band, installs the two verbs, locks
it to its owner, and hands it over. `record` splits the body on `|`,
enforces the ten-step cap, and stores the list:

```text
@create macro band
@set macro band/cmd_record = $record * = *:steps = [s.strip() for s in arg1.split('|') if s.strip()]; pemit(enactor, 'Macros hold at most 10 steps.') if len(steps) > 10 else (set_attr(me, 'macro_' + arg0, '|'.join(steps)), pemit(enactor, 'Recorded ' + arg0 + ' (' + str(len(steps)) + ' steps).'))
@set macro band/cmd_play = $play *:body = get_attr(me, 'macro_' + arg0, ''); pemit(enactor, 'No macro ' + arg0 + '.') if not body else [force(enactor, s.strip()) for s in body.split('|')[:10] if s.strip()]
@lock/use macro band = caller == owner
@chown macro band = Ada
@untag macro band = halt
give macro band to Ada
```

The `[:10]` slice in `play` is the belt to `record`'s braces — even a
macro stored by some other path can't replay more than ten steps.

## Try it

**Player side.** Ada — no builder bit — records a greeting and fires it:

```text
> record hello = say Hello, station.|pose taps her comm badge.
Recorded hello (2 steps).
> play hello
You say, "Hello, station."
Ada taps her comm badge.
```

Everyone in the room sees both lines, attributed to Ada — because the
steps *are* Ada, run through her own authority.

Now the walls. Ada tries to smuggle a builder command into a macro:

```text
> record breakin = @dig Backdoor
Recorded breakin (1 steps).
> play breakin
```

Nothing happens — no room is dug. `force(Ada, '@dig Backdoor')` is Ada
typing `@dig`, and Ada is no builder. And an oversized macro is refused
outright:

```text
> record spam = say a|say a|say a|say a|say a|say a|say a|say a|say a|say a|say a
Macros hold at most 10 steps.
```

Eleven steps, nothing stored. The macro system extends a player's reach
by *convenience*, never by *authority*.

## Going further

- **Parameterised macros:** capture more wildcards — `$cast * at *` — and
  splice them into the steps you store; the player builds her own verbs.
- **Shared macro pads:** loosen the lock —
  `@lock/use macro band = caller.has_tag('crew')` — for a shared console
  a whole team may program.
- **A pause between steps:** a step of `wait 2 trigger me/next` chains a
  delayed continuation — but `wait()` is in-memory (item
  [246](246_hot_reload.md)), so a reboot forgets a half-run macro.
- **Guard against loops:** a macro whose step is `play hello` re-enters
  the same verb — the ten-step cap and the sandbox's call budget stop the
  spiral, but keep macros non-recursive by habit.
