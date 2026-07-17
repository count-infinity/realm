# 106. Arm Wrestling

> Checklist item 106 — [now] — *contest(), remit spectacle, wagers*

**What you'll build:** A scarred bar table where two players slap down
matching stakes and settle it with one opposed strength contest —
called with crowd play-by-play, paid on the spot.

**Concepts:** `contest()` (opposed quick contests, margin vs margin),
making a *raw stat* rollable by defining a `skill_def` object +
`@reload` (skills-as-data), escrowed wagers via `ON_PAYMENT`, and
`remit()` spectacle — the crowd is the product.

## How it works

**Contests roll skills, so give strength a skill name.** `contest(a,
skill, b, skill)` has both sides roll 3d6 under their level and
compares margins of success. Levels come from `skill_<name>` attributes
or, untrained, from the game system's default table — and *that table
is data*: a `skill_def` object named `brawn` with `stat = strength`,
`penalty = 0` makes every untrained `brawn` roll resolve against the
roller's raw ST. `@reload` re-reads the table from the world (skill
defaults install at boot; the reload picks up new definitions), and
from then on `contest(a, 'brawn', b, 'brawn')` *is* the ST-vs-ST quick
contest — no engine change, one data object. (There is deliberately no
`contest(a, 'strength', ...)` shortcut: the check layer resolves skill
names only, and the `skill_def` bridge is the sanctioned way to key a
roll off a bare attribute.)

**Ties keep the champion.** `contest()` gives ties and mutual failure
to the *opponent* — the status quo holds. Since the challenged player
is passed as the opponent, calling someone out means you must beat
them outright. House rule, engine-enforced.

**The wager is the RPS escrow, simplified.** Both parties pay the
table (`ON_PAYMENT`, stake read off `adata('amount')`); the second
stake landing triggers the bout
immediately — no secret choices here, so no prompts: just the roll and
the roar. Winner takes double from the table's own balance, which at
that moment holds exactly both stakes.

## Build it

First, the skill-as-data bridge (staff, once per game):

```text
@create brawn
@tag brawn = skill_def
@set brawn/stat = strength
@set brawn/penalty = 0
@reload
```

The table:

```text
@create the wrestling table
drop the wrestling table
@desc the wrestling table = Elbow-polished oak, ringed by chalk lines and old beer. [[bt = V('bout', None); result = 'A grudge match is forming.' if bt else 'The chair opposite is empty.']]
```

The callout:

```text
@set the wrestling table/cmd_wrestle = $wrestle * for *: opp = get(trim(arg0)); w = int(trim(arg1)); ok = not V('bout', None) and opp is not None and has_tag(opp, 'player') and loc(opp) is here and opp is not enactor and w > 0; [(set_attr(me, 'bout', {'a': enactor.id, 'b': opp.id, 'wager': w, 'paid': []}), remit(here, name(enactor) + ' slaps ' + str(w) + ' credits on the table and calls out ' + name(opp) + '. Both: pay ' + str(w) + ' to the wrestling table.')) for g in [ok] if g]; pemit(enactor, 'The table is busy, or that is no valid opponent or wager.') if not ok else None
```

The escrow — second stake in, elbows down:

```text
@set the wrestling table/on_payment = paid = adata('amount', 0) if target == me else 0; bt = V('bout', None); ok = bt is not None and enactor.id in [bt['a'], bt['b']] and enactor.id not in bt['paid'] and paid == bt['wager']; [(bt['paid'].append(enactor.id), set_attr(me, 'bout', bt), pemit(enactor, 'Your stake hits the wood.')) for g in [ok] if g]; (transfer_credits(me, enactor, paid), pemit(enactor, 'The table shrugs your credits back: wrong amount, or no bout of yours.')) if not ok and paid > 0 else None; eval_attr(me, 'bout_go') if ok and len(bt['paid']) == 2 else None
```

The bout — play-by-play, one contest, the pot:

```text
@set the wrestling table/bout_go = bt = V('bout', {}); a = get('#' + bt['a']); b = get('#' + bt['b']); remit(here, name(a) + ' and ' + name(b) + ' lock hands over the scarred tabletop. The crowd leans in.'); win = a if contest(a, 'brawn', b, 'brawn') else b; lose = b if win is a else a; remit(here, 'Knuckles whiten, the table groans... ' + name(win) + " slams " + name(lose) + "'s arm down! The crowd roars."); transfer_credits(me, win, bt['wager'] * 2); remit(here, name(win) + ' scoops the pot: ' + str(bt['wager'] * 2) + ' credits.'); del_attr(me, 'bout'); result = 1
```

## Try it

Two players, one strong (`@set me/strength = 14`), one less so
(`@set me/strength = 8`), each with pocket money:

```text
wrestle Bob for 10                 -> the callout, room-wide
pay 10 to the wrestling table      -> "Your stake hits the wood."
pay 10 to the wrestling table      (Bob) -> the bout runs at once:
    "Kess and Bob lock hands over the scarred tabletop. The crowd leans in."
    "Knuckles whiten, the table groans... Kess slams Bob's arm down! The crowd roars."
    "Kess scoops the pot: 20 credits."
```

ST 14 against ST 8 wins the contest roughly four times in five —
strong, not scripted. Train `skill_brawn` above your ST (`improve`,
or a coach NPC) and technique beats meat.

## Going further

- **Best of three:** loop the contest in `bout_go` and narrate each
  fall — margins are already graded, so call the close falls
  differently from the slams.
- **Fatigue:** each bout `apply_effect(lose, 'modifier_effect',
  kind='burned_arm', check_mods={'brawn': -2}, duration=300)` — the
  condition-modifier pipeline folds it into the next contest
  automatically.
- **Side bets:** put the [bookmaker](105_npc_races.md)'s book next to
  the table — the bout resolves in one event, so the book settles the
  moment `bout_go` names a winner.
- **The house champion:** an NPC with `skill_brawn = 15` and an
  `ON_PAYMENT` that accepts any challenger's stake — the table becomes
  a credit sink with a face.
