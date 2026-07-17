# 201. Branching quest

> Checklist item 201 — [now] — *prompt() branches, mutually exclusive state attrs*

**What you'll build:** Envoy Sable offers a fork in the road — serve the
Warlord or the Rebels. Your answer, captured through `prompt()`, sets a
single allegiance attribute that locks out the other choice forever and
decides which ending you can reach.

**Concepts:** `prompt()` **choice capture** (the player's next line runs a
callback), a **mutually exclusive state attribute** (`allegiance`) as the
branch, the lock-in check that makes a choice permanent, and endings
**gated** on the branch attribute.

## How it works

A branch is one attribute with a small set of legal values. `prompt(target,
text, callback)` asks a question and runs the named callback **as the NPC**
when the player answers, their words bound as `arg0` — the softcode wizard
already used by the [dialogue tree](067_dialogue_tree_npc.md) and the
[self-destruct abort](056_self_destruct.md). Here the callback validates
the answer and writes `allegiance` onto the player.

Three moving parts:

- **The fork prompts.** `parley` first checks whether allegiance is
  already sworn — if so it reports it and stops (no second prompt). Only an
  unsworn player is asked the question and handed into `on_choose`.
- **The choice is mutually exclusive by construction.** `on_choose`
  accepts only `warlord` or `rebels` and writes it once; a garbled answer
  swears nothing, so the player can try again. Because the fork guards on
  "already sworn", the *first* valid answer is final — that's the lock-in.
- **Endings read the branch.** `seek ending` refuses if nothing is sworn,
  then dispatches on `allegiance` to one of two outcomes. Two endings, one
  attribute, no way to reach both.

Authority keeps it safe: the callback runs as Sable, so a malicious answer
can at worst change *this player's* allegiance (and only to a value Sable's
own code allows) — never anyone else's sheet.

## Build it

Envoy Sable and her fork. Note `parley` short-circuits for the already
sworn, and only otherwise `prompt()`s into `on_choose`:

```text
@create Envoy Sable
@tag Envoy Sable = npc
drop Envoy Sable
@set Envoy Sable/cmd_parley = $parley:(pemit(enactor, 'Your allegiance is already sworn: ' + get_attr(enactor, 'allegiance') + '.') if get_attr(enactor, 'allegiance', 0) else (pemit(enactor, 'Sable studies you. "The Warlord or the Rebels -- whom do you serve?"'), prompt(enactor, 'Answer warlord or rebels:', 'on_choose')))
```

The choice callback — validate, then commit the branch attribute exactly
once:

```text
@set Envoy Sable/on_choose = pick = trim(arg0).lower(); (set_attr(enactor, 'allegiance', pick), pemit(enactor, 'So be it. You are sworn to the ' + pick + '.')) if pick in ('warlord', 'rebels') else pemit(enactor, 'Sable frowns. "Speak plainly: warlord or rebels."')
```

The gated endings — the fork's two payoffs, each unreachable from the
other branch:

```text
@set Envoy Sable/cmd_ending = $seek ending:a = get_attr(enactor, 'allegiance', 0); pemit(enactor, 'You have sworn nothing yet.') if not a else (pemit(enactor, 'The Warlord crowns you warlord of the marches. [WARLORD ENDING]') if a == 'warlord' else pemit(enactor, 'The Rebels raise you on their shoulders, the city freed. [REBEL ENDING]'))
```

## Try it

As Raven:

```text
seek ending                  -> You have sworn nothing yet.
parley                       -> Sable studies you. "The Warlord or the Rebels -- whom do you serve?"
                                Answer warlord or rebels:
rebels                       -> So be it. You are sworn to the rebels.
parley                       -> Your allegiance is already sworn: rebels.
seek ending                  -> The Rebels raise you on their shoulders, the city freed. [REBEL ENDING]
```

The second `parley` never re-prompts — the branch is locked. Answer with
nonsense instead (`maybe later`) and Sable frowns; `allegiance` stays
unset and you can choose again. A different character who swears `warlord`
reaches the other ending and can never see the rebel one: mutually
exclusive, permanent, inspectable (`@examine Raven` shows the single
`allegiance` attr).

While a prompt is pending, your next line is the answer — `help` and
`quit` still pass through to the game, and the callback runs with Sable's
authority, not yours.

## Going further

- **Deeper trees.** Each branch can `prompt()` into its *own* follow-up
  callback (`on_warlord_oath`, `on_rebel_oath`) for a second fork — the
  same chain, more rooms in the maze (the dialogue tree's deep-branch note).
- **Reputation, not just endings.** Have `on_choose` also
  `adjust_disposition` every NPC of the losing faction against the player —
  the branch ripples out into how the world treats them.
- **Reboot-proof oaths.** Add `persistent=True` to the prompt so a player
  mid-answer at reboot still triggers the callback on their next line.
- **Point of no return, spelled out.** Before committing, prompt a
  confirmation (`Are you sure? This cannot be undone.`) so the lock-in is a
  deliberate act — a second `prompt()` inside `on_choose`.
