# 103. Rock-Paper-Scissors

> Checklist item 103 — [now] — *dual prompt() secrets, escrowed bets, reveal remit*

**What you'll build:** A dueling stone that referees wagered
rock-paper-scissors: both players escrow the stake by paying it,
both commit a throw in secret through simultaneous `prompt()`s, and
the stone reveals both at once — winner takes the pot, ties refund.

**Concepts:** the double-commit pattern (secret choices banked in a
`secret`-flagged attribute, revealed only when both are in), `prompt()`
to *two* players at once, wager escrow via `ON_PAYMENT` + the ledger
idiom, refund paths for every wrong turn, and an arbiter object as the
trust anchor.

## How it works

**Simultaneity is the whole game** — and a text game is turn-based by
nature. The stone fakes true simultaneity with *double-commit*: each
duelist's throw goes into the stone's `choices` dict the moment they
answer their prompt, but nothing is announced until both keys exist.
Since `choices` is flagged `secret`, the first committer's throw is
unreadable — by the opponent, by bystanders' gadgets, by anyone but the
stone's own scripts ([item 16](016_combination_safe.md)'s lock, applied
to game state). Commit order stops mattering; that's simultaneity.

**The wager is escrow, not promise.** `challenge Bob for 10` only
books the bout. The stakes move on `pay 10 to the dueling stone` —
real consent, real credits — and the ledger idiom reads each amount.
Wrong amount, wrong player, no bout? The payment bounces straight back.
Only when *both* stakes are in does the stone prompt both duelists;
from that moment the pot can only leave through `resolve`: doubled to
the winner, or split back on a tie.

**Prompts run as the stone.** Each answer fires `on_throw` with the
stone as executor — so a malicious answer can at worst scribble on the
stone's own attributes. Invalid throws re-prompt rather than forfeit.

## Build it

The stone and its sealed choice box:

```text
@create the dueling stone
drop the dueling stone
@desc the dueling stone = A waist-high basalt block, split by a coin slot. [[bt = V('bout', None); result = 'A bout is in progress.' if bt else 'The stone waits for a challenge.']]
@set the dueling stone/choices = {}
@attr the dueling stone/choices = secret
```

The challenge — one live bout at a time, opponent must be a player,
present, and not yourself:

```text
@set the dueling stone/cmd_challenge = $challenge * for *: opp = get(trim(arg0)); w = int(trim(arg1)); ok = not V('bout', None) and opp is not None and has_tag(opp, 'player') and loc(opp) is here and opp is not enactor and w > 0; [(set_attr(me, 'bout', {'a': enactor.id, 'b': opp.id, 'wager': w, 'paid': []}), set_attr(me, 'choices', {}), remit(here, name(enactor) + ' challenges ' + name(opp) + ' at the dueling stone: rock-paper-scissors for ' + str(w) + ' credits. Both must pay ' + str(w) + ' to the dueling stone.')) for g in [ok] if g]; pemit(enactor, 'The stone is busy, or that is no valid opponent or wager.') if not ok else None
```

The escrow. Exact stake from a listed duelist banks; everything else
bounces. The second stake triggers both prompts:

```text
@set the dueling stone/on_payment = paid = credits(me) - V('ledger', 0); bt = V('bout', None); ok = bt is not None and enactor.id in [bt['a'], bt['b']] and enactor.id not in bt['paid'] and paid == bt['wager']; [(bt['paid'].append(enactor.id), set_attr(me, 'bout', bt), pemit(enactor, 'The stone accepts your stake.')) for g in [ok] if g]; [(remit(here, 'Both stakes are in. The stone addresses the duelists.'), prompt(get('#' + bt['a']), 'The stone hums: rock, paper, or scissors?', 'on_throw'), prompt(get('#' + bt['b']), 'The stone hums: rock, paper, or scissors?', 'on_throw')) for g in [ok and len(bt['paid']) == 2] if g]; (transfer_credits(me, enactor, paid), pemit(enactor, 'The stone spits your credits back: wrong amount, or no bout of yours.')) if not ok and paid > 0 else None; set_attr(me, 'ledger', credits(me))
```

The commit — bank the throw in secret; resolve on the second:

```text
@set the dueling stone/on_throw = c = trim(arg0).lower(); bt = V('bout', None); valid = c in ['rock', 'paper', 'scissors'] and bt is not None and enactor.id in [bt['a'], bt['b']]; ch = V('choices', {}); [(ch.update({enactor.id: c}), set_attr(me, 'choices', ch), pemit(enactor, 'The stone sears your choice in silence: ' + c + '.')) for g in [valid] if g]; prompt(enactor, 'Rock, paper, or scissors -- nothing else:', 'on_throw') if bt is not None and not valid else None; eval_attr(me, 'resolve') if valid and len(ch) == 2 else None
```

The reveal — both throws in one breath, then the pot moves:

```text
@set the dueling stone/resolve = bt = V('bout', {}); ch = V('choices', {}); a = bt['a']; b = bt['b']; an = name(get('#' + a)); bn = name(get('#' + b)); ca = ch[a]; cb = ch[b]; beats = {'rock': 'scissors', 'paper': 'rock', 'scissors': 'paper'}; w = a if beats[ca] == cb else (b if beats[cb] == ca else ''); remit(here, 'The stone flares: ' + an + ' throws ' + ca + '; ' + bn + ' throws ' + cb + '.'); (transfer_credits(me, get('#' + a), bt['wager']), transfer_credits(me, get('#' + b), bt['wager']), remit(here, 'A tie. The stakes slide back out of the slot.')) if not w else (transfer_credits(me, get('#' + w), bt['wager'] * 2), remit(here, name(get('#' + w)) + ' takes the pot: ' + str(bt['wager'] * 2) + ' credits.')); del_attr(me, 'bout'); set_attr(me, 'choices', {}); set_attr(me, 'ledger', credits(me)); result = 1
```

## Try it

Two players with pocket money:

```text
challenge Bob for 10             -> the room hears the terms
pay 10 to the dueling stone      -> "The stone accepts your stake."
pay 10 to the dueling stone      (Bob) -> both prompted, privately
rock                             (you, answering the prompt)
scissors                         (Bob, answering his)
    -> "The stone flares: Kess throws rock; Bob throws scissors."
    -> "Kess takes the pot: 20 credits."
```

Mid-bout, the opponent's committed throw is a locked box:

```text
@eval result = get_attr(get('the dueling stone'), 'choices')   -> => None
```

Ties (`rock` vs `rock`) hand both stakes straight back. A stranger who
pays the stone mid-bout gets refunded with a clank.

## Going further

- **Best of three:** keep a `wins` dict in the bout and have `resolve`
  re-prompt until someone reaches two — the pot only moves on the
  match point.
- **Blind auctions, sealed bids:** the double-commit core (secret dict
  + reveal when all keys present) is the same pattern — swap throws for
  numbers and highest-takes-it.
- **Lizard-Spock:** widen the `beats` dict to two victims each — the
  validator list and the dict are the only rule surface.
- **Idle forfeit:** stamp `now()` when prompts go out; a `script_ticker`
  refunds a duelist whose opponent has sat on the prompt for five
  minutes ([wait() dies on reboot](250_player_scripting.md); the stamp
  survives).
