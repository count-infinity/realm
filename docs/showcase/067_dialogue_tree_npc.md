# 067. Dialogue-tree NPC

> Checklist item 67 — [now] — *prompt() callback chains, per-player memory attrs*

**What you'll build:** Old Moss, a tavern regular you `talk` to. The
conversation is a branching menu that loops until you leave — and he
remembers, per player and across reboots, whether you've met, what
you've asked, whether you bought him a drink, and whether he already
told you his secret.
**Concepts:** softcode wizards (`prompt()` callback chains), rendering
menus with `eval_attr()`, per-player memory keyed by `enactor.id`,
gating dialogue options on memory, composing with `ON_PAYMENT`.

## How it works

REALM's `prompt(target, text, callback)` asks a player a question and
runs the named attribute **as the NPC** when they answer, with the
answer bound as `arg0`. A dialogue *tree* is just a callback that says
its piece and prompts again — the loop is the chain.

The structure, four attributes on one NPC:

- **`menu`** — a function attribute evaluated with `eval_attr(me,
  'menu')`. It reads the asker's memory flags and *builds* the option
  list: options you haven't earned are simply not printed. One menu
  serves every player because the flags are keyed by `enactor.id`.
- **`cmd_talk`** — the `$talk` command: greet (first meeting vs.
  return visit — the `met_<id>` flag), then `prompt()` into the tree.
- **`node_root`** — the single dispatch callback. `arg0` is what the
  player typed; a chained conditional routes it: lore branches set
  their flag, speak, and re-prompt; the secret branch fires once and
  ends the chain; anything else is a polite brush-off.
- **`on_payment`** — the drink gate, borrowed straight from item 64's
  balance-delta idiom. Buying Moss a drink is a *real payment*, not a
  menu fiction: the flag it sets is what unlocks the secret branch.

Memory is nothing but attributes on Moss (`town_<id>`, `mine_<id>`,
`drink_<id>`, `secret_<id>`), so it persists like everything else and
`@examine Old Moss` shows exactly what he knows about whom. The
authority model does the safety work: callbacks run as Moss, so a
malicious answer can at worst change Moss's own attrs — never the
player's sheet.

## Build it

In The Rusty Flagon (item 64), seat the regular:

```
@create Old Moss
@tag Old Moss = npc
drop Old Moss
@desc Old Moss = He has the corner table and a stare that has seen the bottom of many mugs.
```

**The menu function.** Options appear as flags accumulate — `[2]` after
you've asked about the town, `[3]` only once you've asked about the
mine *and* stood him a drink, and never again after the secret is
spent:

```
@set Old Moss/menu = t = V('town_' + enactor.id, 0); m = V('mine_' + enactor.id, 0); d = V('drink_' + enactor.id, 0); s = V('secret_' + enactor.id, 0); result = '[1] Ask about the town.' + (' [2] Ask about the old mine.' if t else '') + (' [3] Press him about the collapse.' if m and d and not s else '') + ' [q] Leave him be.'
```

**The opener.** `$talk` greets by memory and starts the chain:

```
@set Old Moss/cmd_talk = $talk:met = V('met_' + enactor.id, 0); set_attr(me, 'met_' + enactor.id, 1); say('New face. Name is Moss. Sit, if you like.' if not met else f'Back again, {name(enactor)}. Thought so.'); prompt(enactor, eval_attr(me, 'menu'), 'node_root')
```

**The tree.** One callback dispatches every answer. Note how each lore
branch sets its flag *before* re-prompting, so the menu it prints
already includes what the answer just unlocked:

```
@set Old Moss/node_root = a = trim(arg0); t = V('town_' + enactor.id, 0); m = V('mine_' + enactor.id, 0); d = V('drink_' + enactor.id, 0); s = V('secret_' + enactor.id, 0); ((set_attr(me, 'town_' + enactor.id, 1), say('Quiet town. Was not always - the mine kept it loud, before the collapse.'), prompt(enactor, eval_attr(me, 'menu'), 'node_root')) if a == '1' else (set_attr(me, 'mine_' + enactor.id, 1), say('Closed ten years back. An accident, they ruled.' + ('' if d else ' Dry work, remembering. Pay 5 to Old Moss and it might come back to me.')), prompt(enactor, eval_attr(me, 'menu'), 'node_root')) if a == '2' and t else (set_attr(me, 'secret_' + enactor.id, 1), pemit(enactor, 'Moss leans close: it was no accident. He hauled the charges down himself, on watch-house coin. Then he says no more.')) if a == '3' and m and d and not s else say('Moss waves you off and studies his mug.'))
```

The secret goes out on `pemit` — a private line for the one player who
earned it, not table talk for the room.

**The drink gate.** The same three-way `ON_PAYMENT` as Mira's (serve /
grumble / ignore a bystander's payment) — vital here, since Moss and
Mira share a room and both hear every payment event:

```
@set Old Moss/on_payment = paid = credits(me) - V('tab', 0); ((set_attr(me, 'tab', credits(me)), set_attr(me, 'drink_' + enactor.id, 1), pose('drinks deep and wipes his beard.')) if paid >= 5 else (say('That will not wet a flea.') if paid > 0 else None))
```

## Try it

```
@set me/credits = 40
talk                → "New face. Name is Moss..."  [1] ... [q]
1                   → town lore; the menu regrows with [2]
2                   → mine lore, and a hint: buy him a drink
q                   → "Moss waves you off..."
pay 5 to Old Moss   → he drinks deep
talk                → "Back again, <you>. Thought so." — [3] is offered
3                   → the secret, whispered to you alone
talk                → the menu again — [3] is gone for good
q
```

While a prompt is pending, your next line is the answer — `help` still
passes through to the game, and answers run with Moss's authority, not
yours.

## Going further

- **Deeper trees:** each branch can prompt into its *own* callback
  (`'node_mine'`, `'node_secret'`) instead of re-entering `node_root` —
  same chain, more rooms in the maze.
- **Reboot-proof interrogations:** add `persistent=True` to a prompt
  and a player mid-answer at reboot still triggers the callback with
  their next line after reconnecting.
- **Disposition-aware greetings:** open `cmd_talk` with
  `disposition(me, enactor)` and have Moss clam up for anyone he
  dislikes — `persuade` becomes the key to the whole tree.
- **Let memory leak outward:** the `secret_<id>` flag is readable by
  your other objects — a quest board could list "knows the mine
  truth" players, or the Town Watch master (item 71) could take an
  interest in who's been asking.
