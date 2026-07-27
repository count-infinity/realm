# 103. Rock-Paper-Scissors

> Checklist item 103 ([now]): *dual prompt() secrets, escrowed bets, reveal remit*

**What you'll build:** A dueling stone that referees wagered
rock-paper-scissors. Both players escrow the stake by paying it, both commit a
throw in secret through simultaneous [`prompt()`](../reference/softcode.md#fn-prompt)s,
and the stone reveals both at once, so the winner takes the pot and a tie
refunds.

**Concepts:** the double-commit pattern (secret choices banked in a
`secret`-flagged attribute and revealed only once both are in),
[`prompt()`](../reference/softcode.md#fn-prompt) to *two* players at once, wager
escrow through [`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks) plus
[`adata('amount')`](../reference/softcode.md#event-data-namespace), refund paths
for every wrong turn, and an arbiter object as the trust anchor.

## How it works

The finished stone runs a bout in three beats: a `challenge` books it, two
payments escrow the stakes and fire two private prompts, and two secret throws
reveal together and move the pot. The trick worth understanding is how a
turn-based game fakes a simultaneous reveal, and how the money is held safely in
between. This section answers both.

### How two players throw at once when the game is turn-based

A text game takes one line at a time, so the stone fakes simultaneity with a
*double-commit*. Each duelist's throw goes into the stone's `choices` dict the
moment they answer their prompt, keyed by that player's id, but nothing is
announced until both keys are present. Because `choices` is flagged `secret`,
the first committer's throw is unreadable by the opponent, by a bystander's
gadget, or by anyone but the stone's own scripts. That is [item
16](016_combination_safe.md)'s lock applied to game state. Since neither throw
is visible until both are banked, commit order stops mattering, and that is what
makes the reveal simultaneous.

### How the stakes are held without trusting either player

The wager is escrow, not a promise. Typing `challenge Bob for 10` only books the
bout. The stakes move when each player runs `pay 10 to the dueling stone`, which
is real consent moving real credits, and the
[`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks) hook reads each amount
straight off the action with
[`adata('amount')`](../reference/softcode.md#event-data-namespace). The stone
checks `paid == bt['wager']`, so it needs the size of *this* payment exactly, not
a running balance. A wrong amount, a stranger, or no booked bout, and the
payment bounces straight back through
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits). Only once both
stakes are in does the stone prompt both duelists, and from that moment the pot
can leave only through the reveal: doubled to the winner, or split back on a tie.

### Why a stray payment cannot arm a stake

An [`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks) hook fires on *every*
object in the room, not only the one that was paid, so the hook opens with `if
target is me:`. Without that guard, paying a tip jar standing next to the stone
would run the stone's hook with the jar's amount and bank a stake for free. This
is the [guard on `target`](../reference/softcode.md#guard-on-target), and it is
an identity check: `target is me`, never `target == me`. The stone's `$challenge`
command needs no such guard, because a `$`-command fires only on the object that
carries it.

### Why a bad answer cannot forfeit or corrupt the game

Each prompt answer runs the stone's `on_throw` as the stone itself, with the
answering player bound as `enactor`. A malicious or fat-fingered answer can at
worst scribble on the stone's own attributes, never on another object, and an
invalid throw re-prompts rather than forfeiting the bout.

## Build it

Create the stone and give it a face that reads its own state at look time. The
inline `[[...]]` block runs per viewer, so the line reflects whether a bout is
live:

```text
@create the dueling stone
drop the dueling stone
@desc the dueling stone = A waist-high basalt block, split by a coin slot. [[bt = V('bout', None); result = 'A bout is in progress.' if bt else 'The stone waits for a challenge.']]
```

Give it the sealed choice box. It starts empty, and the `secret` flag is what
makes a committed throw unreadable to everyone but the stone's own scripts:

```text
@set the dueling stone/choices = {}
@attr the dueling stone/choices = secret
```

The `$challenge` command books one bout at a time. It reads
[`V('bout', None)`](../reference/softcode.md#fn-v) to refuse when the stone is
busy, and it requires an opponent who is a present player, not yourself, at a
positive wager. On success it writes the bout with
[`set_attr`](../reference/softcode.md#fn-set_attr), clears the choice box, and
announces the terms to the room with
[`remit`](../reference/softcode.md#fn-remit):

```text
@set the dueling stone/cmd_challenge = '''
$challenge * for *:
opp = get(trim(arg0))
w = int(trim(arg1))
ok = V('bout', None) is None and opp is not None and has_tag(opp, 'player') and loc(opp) is here and opp is not enactor and w > 0
if ok:
    set_attr(me, 'bout', {'a': enactor.id, 'b': opp.id, 'wager': w, 'paid': []})
    set_attr(me, 'choices', {})  # a fresh, empty secret box for this bout
    remit(here, name(enactor) + ' challenges ' + name(opp) + ' at the dueling stone: rock-paper-scissors for ' + str(w) + ' credits. Both must pay ' + str(w) + ' to the dueling stone.')
else:
    pemit(enactor, 'The stone is busy, or that is no valid opponent or wager.')
'''
```

The escrow hook banks an exact stake from a listed duelist and bounces
everything else. When the second stake lands it prompts both players at once
with [`prompt`](../reference/softcode.md#fn-prompt), each answer routed to
`on_throw`:

```text
@set the dueling stone/on_payment = '''
if target is me:  # ON_PAYMENT fires on EVERY object in the room, so guard it
    paid = adata('amount', 0)
    bt = V('bout', None)
    ok = bt is not None and enactor.id in [bt['a'], bt['b']] and enactor.id not in bt['paid'] and paid == bt['wager']
    if ok:
        bt['paid'].append(enactor.id)
        set_attr(me, 'bout', bt)
        pemit(enactor, 'The stone accepts your stake.')
        if len(bt['paid']) == 2:  # both stakes in: prompt both duelists in secret
            remit(here, 'Both stakes are in. The stone addresses the duelists.')
            prompt(get('#' + bt['a']), 'The stone hums: rock, paper, or scissors?', 'on_throw')
            prompt(get('#' + bt['b']), 'The stone hums: rock, paper, or scissors?', 'on_throw')
    elif paid > 0:
        transfer_credits(me, enactor, paid)  # wrong amount or no bout of yours: bounce it
        pemit(enactor, 'The stone spits your credits back: wrong amount, or no bout of yours.')
'''
```

The commit hook banks each throw into the secret `choices` dict, keyed by the
answering player's id. An invalid word re-prompts, and the second valid throw
triggers the reveal through
[`eval_attr`](../reference/softcode.md#fn-eval_attr):

```text
@set the dueling stone/on_throw = '''
c = trim(arg0).lower()
bt = V('bout', None)
valid = c in ['rock', 'paper', 'scissors'] and bt is not None and enactor.id in [bt['a'], bt['b']]
ch = V('choices', {})
if valid:
    ch.update({enactor.id: c})  # bank the throw into the secret box
    set_attr(me, 'choices', ch)
    pemit(enactor, 'The stone sears your choice in silence: ' + c + '.')
    if len(ch) == 2:  # the second throw is in: reveal both at once
        eval_attr(me, 'resolve')
elif bt is not None:
    prompt(enactor, 'Rock, paper, or scissors -- nothing else:', 'on_throw')
'''
```

The reveal shows both throws in one breath, decides the winner from a beats
table, moves the pot, and then clears the bout with
[`del_attr`](../reference/softcode.md#fn-del_attr) so the stone is free for the
next challenge:

```text
@set the dueling stone/resolve = '''
bt = V('bout', {})
ch = V('choices', {})
a = bt['a']
b = bt['b']
an = name(get('#' + a))
bn = name(get('#' + b))
ca = ch[a]
cb = ch[b]
beats = {'rock': 'scissors', 'paper': 'rock', 'scissors': 'paper'}
w = a if beats[ca] == cb else (b if beats[cb] == ca else '')  # '' means a tie
remit(here, 'The stone flares: ' + an + ' throws ' + ca + '; ' + bn + ' throws ' + cb + '.')
if w:
    transfer_credits(me, get('#' + w), bt['wager'] * 2)
    remit(here, name(get('#' + w)) + ' takes the pot: ' + str(bt['wager'] * 2) + ' credits.')
else:
    transfer_credits(me, get('#' + a), bt['wager'])
    transfer_credits(me, get('#' + b), bt['wager'])
    remit(here, 'A tie. The stakes slide back out of the slot.')
del_attr(me, 'bout')  # bout closed: the stone is free for the next challenge
set_attr(me, 'choices', {})
result = 1
'''
```

## Try it

Two players with pocket money run a full bout:

```text
> challenge Bob for 10
Kess challenges Bob at the dueling stone: rock-paper-scissors for 10 credits. Both must pay 10 to the dueling stone.

> pay 10 to the dueling stone
The stone accepts your stake.

(Bob) pay 10 to the dueling stone
Both stakes are in. The stone addresses the duelists.
The stone hums: rock, paper, or scissors?

(you, answering the prompt) rock
The stone sears your choice in silence: rock.

(Bob, answering his prompt) scissors
The stone flares: Kess throws rock; Bob throws scissors.
Kess takes the pot: 20 credits.
```

Mid-bout, the opponent's committed throw is a locked box. A stranger reading the
choices attribute gets nothing back:

```text
> @eval result = get_attr(get('the dueling stone'), 'choices')
=> None
```

A tie (`rock` against `rock`) hands both stakes straight back, and a stranger who
pays the stone mid-bout is refunded with a clank.

## Going further

- **Best of three:** keep a `wins` dict in the bout and have `resolve`
  re-prompt until someone reaches two, so the pot moves only on the match point.
- **Blind auctions, sealed bids:** the double-commit core (a secret dict plus a
  reveal once all keys are present) is the same pattern. Swap throws for numbers
  and let the highest take it.
- **Lizard-Spock:** widen the `beats` dict to two victims each. The validator
  list and the dict are the only rule surface.
- **Idle forfeit:** stamp `now()` when the prompts go out and have a
  `script_ticker` refund a duelist whose opponent has sat on the prompt for five
  minutes. A [`wait()`](../reference/softcode.md#fn-wait) dies on a reboot, so a
  stamped time is the way that survives one (see
  [250_player_scripting.md](250_player_scripting.md)).
```