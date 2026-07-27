# 201. Branching quest

> Checklist item 201 ([now]): *prompt() branches, mutually exclusive state attrs*

**What you'll build:** Envoy Sable offers a fork in the road, to serve the
Warlord or to serve the Rebels. Your answer, captured through
[`prompt()`](../reference/softcode.md#fn-prompt), writes a single allegiance
attribute that shuts the other path for good and decides which ending you
reach.

**Concepts:** [`prompt()`](../reference/softcode.md#fn-prompt) **choice
capture** (the player's next line runs a callback on the NPC), a **mutually
exclusive state attribute** (`allegiance`) as the branch, the short-circuit
that makes the first valid answer permanent, and endings **gated** on the
branch attribute.

## How it works

The finished shape is three attributes on one NPC plus one attribute on each
player. Sable's `$parley` command asks the question, her `on_choose` callback
writes the answer onto the player as `allegiance`, and her `$seek ending`
command reads that same attribute to pick one of two endings. This section
answers four questions a builder will have: where the branch actually lives,
how a player's next line becomes an answer, what makes the first valid answer
final, and who is allowed to write on a player's sheet.

### Where does the branch live?

In exactly one attribute, `allegiance`, stored on the player. It is unset
while the player is undecided and holds either `warlord` or `rebels`
afterwards. Because one attribute holds one value, the two endings are
mutually exclusive by construction rather than by bookkeeping: there is no
sequence of commands that leaves a player holding both.

[`set_attr`](../reference/softcode.md#fn-set_attr) writes it into the
player's own attribute store, so it persists like any other attribute, and
[`get_attr`](../reference/softcode.md#fn-get_attr) with a default of `''`
reads it back as "sworn or not" in a single expression.

### How does the player's next line become an answer?

[`prompt(target, text, callback)`](../reference/softcode.md#fn-prompt) sends
`text` to the player and captures their next line into `callback`, which is
an attribute on the object that called `prompt()`. The callback runs **as the
NPC**, with the player bound as `enactor` and the raw answer bound as `arg0`.
That is the softcode wizard already used by the
[dialogue tree](067_dialogue_tree_npc.md) and the
[self-destruct abort](056_self_destruct.md), and the
[wizards guide](../guides/wizards.md) covers the pattern in general.

Exactly one line is captured, and the capture is not a trap: `help`, `quit`,
and `exit` pass straight through to the normal dispatcher, leaving the
question still pending. Every other line, sensible or not, reaches
`on_choose`.

### What makes the first valid answer final?

`$parley` reads `allegiance` before it does anything else, so a sworn player
gets a report and nothing more. Since `prompt()` runs only on the unsworn
branch, a sworn player never has a pending question, and `on_choose` is
therefore out of reach for them: it is a plain attribute rather than a
`$`-command, and the builder tool that would run it by hand, `@tr`, is gated
on builder permission. An invalid answer writes nothing at all, which leaves
the player unsworn and free to `parley` again, so the lock-in lands on the
first *valid* answer rather than on the first attempt.

### Who is allowed to write another player's sheet?

The callback runs as Sable, so `set_attr(enactor, 'allegiance', pick)` is
checked against Sable's authority, not the player's. A scripted object acts
with its owner's authority, and writing another player's attributes requires
admin, so **build Sable from an admin account** (the same rule the
[quest framework](198_quest_framework.md) relies on). Owned by a plain
builder instead, `set_attr` returns False and silently stores nothing while
the player still reads "So be it", which is an unpleasant thing to debug
later.

Authority also bounds what a hostile answer achieves. The answer arrives as a
string in `arg0` and is never executed as code, and `on_choose` writes only
`enactor`, only the attribute `allegiance`, and only one of two literal
values, so the worst outcome of a creative answer is Sable's frown.

### Does a second NPC in the room need a target guard?

No, and this is where a `$`-command differs from a reactive hook. An
`ON_<EVENT>` [lifecycle hook](../reference/softcode.md#lifecycle-hooks) fires
on every object that witnesses the event, which is why those need a
[`target is me`](../reference/softcode.md#guard-on-target) guard. A
`$`-command instead searches the objects around the player and runs the
**first** pattern that matches, so parking a second envoy beside Sable
changes nothing: `parley` still resolves to exactly one script. The flip side
is that two objects within reach defining the same pattern means only one of
them ever answers, so keep a public verb's pattern unique in a room.

## Build it

Raise the envoy and stand her in the room where the fork is offered. She
carries no tags the scripts read; `npc` is there so other tooling can find
her:

```text
@create Envoy Sable
@tag Envoy Sable = npc
@desc Envoy Sable = A lean diplomat in a road-worn grey coat, hands folded over a sealed writ.
drop Envoy Sable
```

The fork itself. In order, it reads the player's allegiance, reports it back
privately with [`pemit`](../reference/softcode.md#fn-pemit) and stops if
there is one, and otherwise poses the question and hands the next line to
`on_choose`:

```text
@set Envoy Sable/cmd_parley = '''
$parley:
sworn = get_attr(enactor, 'allegiance', '')
if sworn:
    pemit(enactor, f'Your allegiance is already sworn: {sworn}.')
else:
    pemit(enactor, 'Sable studies you. "The Warlord or the Rebels -- whom do you serve?"')
    prompt(enactor, 'Answer warlord or rebels:', 'on_choose')  # only the unsworn are ever asked, which is what makes the choice permanent
'''
```

The choice callback normalizes the answer with
[`trim`](../reference/softcode.md#fn-trim) and `.lower()`, validates it
against the two legal values, and commits the branch attribute. Anything else
falls to the `else` and swears nothing, so the player keeps their fork:

```text
@set Envoy Sable/on_choose = '''
pick = trim(arg0).lower()  # arg0 is the answer line exactly as typed, spacing and capitals included
if pick in ('warlord', 'rebels'):
    set_attr(enactor, 'allegiance', pick)
    pemit(enactor, f'So be it. You are sworn to the {pick}.')
else:
    pemit(enactor, 'Sable frowns. "Speak plainly: warlord or rebels."')
'''
```

The gated endings are the fork's two payoffs, and each one is out of reach
from the other branch. The ladder refuses an unsworn player first, then
dispatches on the single attribute:

```text
@set Envoy Sable/cmd_ending = '''
$seek ending:
sworn = get_attr(enactor, 'allegiance', '')
if not sworn:
    pemit(enactor, 'You have sworn nothing yet.')
elif sworn == 'warlord':
    pemit(enactor, 'The Warlord crowns you warlord of the marches. [WARLORD ENDING]')
else:
    pemit(enactor, 'The Rebels raise you on their shoulders, the city freed. [REBEL ENDING]')
'''
```

## Try it

As Raven, standing with Sable:

```text
> seek ending
You have sworn nothing yet.

> parley
Sable studies you. "The Warlord or the Rebels -- whom do you serve?"
Answer warlord or rebels:

> maybe later
Sable frowns. "Speak plainly: warlord or rebels."

> parley
Sable studies you. "The Warlord or the Rebels -- whom do you serve?"
Answer warlord or rebels:

> rebels
So be it. You are sworn to the rebels.

> parley
Your allegiance is already sworn: rebels.

> seek ending
The Rebels raise you on their shoulders, the city freed. [REBEL ENDING]
```

Two results are worth confirming deliberately. The nonsense answer left
`allegiance` unset, which is why the second `parley` asked the question
again instead of reporting an oath. The `parley` *after* swearing printed the
report and installed no new question, so the next line Raven types is an
ordinary command rather than an answer.

To see the branch itself, run `@examine Raven` from a builder or admin
account and read the `Attributes:` section, which lists the single entry
`allegiance: 'rebels'`. Raven gets `Permission denied.` for the same command,
because `@examine` is a builder tool rather than a player-facing one.

A different character who swears `warlord` reaches
`[WARLORD ENDING]` and reaches only that one, and swearing on one character
leaves every other character's `allegiance` untouched, because the attribute
lives on the player who answered.

## Going further

- **Deeper trees.** Each branch may `prompt()` into its own follow-up
  callback (`on_warlord_oath`, `on_rebel_oath`) for a second fork, which is
  the same chain with more rooms in the maze (the
  [dialogue tree](067_dialogue_tree_npc.md) makes the same point about
  re-entering one node versus splitting into several).
- **Reputation, not just endings.** Have `on_choose` also call
  [`adjust_disposition`](../reference/softcode.md#fn-adjust_disposition) on
  every NPC of the losing faction, so the branch ripples out into how the
  world treats the player rather than sitting idle until the ending.
- **Reboot-proof oaths.** Pass `persistent=True` to the
  [`prompt`](../reference/softcode.md#fn-prompt) and the pending callback is
  stored on the player, so a player who was mid-answer when the server went
  down reconnects to a resume notice and their next line still runs
  `on_choose`.
- **Point of no return, spelled out.** Before committing, prompt a
  confirmation ("Are you sure? There is no unswearing this.") from inside
  `on_choose`, so the lock-in becomes a deliberate second act rather than a
  surprise.
