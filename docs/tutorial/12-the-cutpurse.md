# Part 12 — The Cutpurse

Saltmarsh has a market; markets have pockets. This part adds a
**pickpocket skill to the game's rules** — not to the engine, to the
*data* — then gives the whole town a verb for it, and a watchman who
makes the verb interesting.

## A skill is data

The skill list isn't code. A skill is an object tagged `skill_def`;
the active ruleset merges yours over its built-ins:

```text
@create pickpocket
@tag pickpocket = skill_def
@set pickpocket/stat = dexterity
@set pickpocket/penalty = -5
@reload
```

`stat` and `penalty` are the untrained default — GURPS-speak for
"anyone may try it at DX-5". `@reload` re-reads the rules from the
world; from this moment `pickpocket` rolls, improves, and defaults
like any skill that shipped in the box:

```text
points
improve pickpocket
improve pickpocket
```

(Character points from the banshee and whatever else you've put down.
Training from untrained starts you at the default and climbs from
there — 4 points a level.)

## A verb for the whole town

Where should the command live? Not on an item (pickpockets don't
carry a license) and not on one room. Every room you've dug here
carries `zone:saltmarsh` — so hang it on a **zone master**, and it
works town-wide:

```text
@create the saltmarsh shadows
@tag the saltmarsh shadows = zone_master
@tag the saltmarsh shadows = zone:saltmarsh
@set the saltmarsh shadows/cmd_pickpocket = $pickpocket *:v = get(arg0); take = min(5, credits(v)) if v else 0; pemit(enactor, 'No such mark here.') if not v or loc(v) != here else ((transfer_credits(v, enactor, take), pemit(enactor, 'Light fingers. You lift ' + str(take) + ' from ' + name(v) + '.')) if contest(enactor, 'pickpocket', v, 'observation') else (adjust_disposition(v, enactor, -2), force(v, 'say Stop thief! ' + name(enactor) + ' has my purse!')))
@teleport the saltmarsh shadows = The Void
```

(Park it in the Void: a zone master is found by its tags, not its
location — and anything in your *inventory* offers you its commands
everywhere, which is not what "works in Saltmarsh" means.)

Two details earn their keep. The `loc(v) != here` guard scopes the
crime: `get()` falls back to a *world* search, and a verb that lets
you rifle pockets three rooms away is a bug wearing a feature's coat.
Then the **quick contest**: your `pickpocket` against the mark's
`observation`, ties to the defender. Win and up to five credits move
— `transfer_credits` is real money, the same ledger the shop uses.
Lose and the *victim* is forced to cry thief, with your name in it.
That shout is not decoration.

## The law

```text
@dig The Stocks = stocks, out
@teleport me = Market Square
@create the watchman
@tag the watchman = npc
drop the watchman
@set the watchman/listen_thief = ^Stop thief! * has my purse!:t = get(arg0); say('The stocks for you, ' + arg0 + '.'); adjust_disposition(me, t, -3); teleport_obj(t, 'The Stocks')
```

Follow the chain, because this is the whole lesson: a zone-wide
`$`-verb rolls a contest → failure **forces the victim to speak** →
speech is a real, overhearable action → the watchman's `^listen`
pattern *captures your name from the shout* (`*` → `arg0`) → he looks
you up, remembers (-3, forever), and marches you to the stocks.
Five mechanics you already knew, composed into a consequence no
single script owns.

## Work the square

```text
pickpocket old bramble
```

Succeed and you're five credits the richer — `credits` to confirm.
Fail and you're in the stocks with the gulls laughing; `out` and try
the other pocket. Bramble carries fifteen; after that you're robbing
a man of herring money.

!!! info "Learn more"
    Try picking a *player's* pocket: from a builder-owned verb, the
    transfer and the forced shout both quietly fail — softcode wields
    its **owner's** authority, and builders don't control players. So
    players are safe by authority, not by policy... unless the verb's
    owner is an admin (you, right now), whose gadgets control
    everyone. `@chown the saltmarsh shadows = <a builder>` before
    opening night, or run a game of god-thieves — but choose it. For
    marks that fight back, `watchful` NPCs spot sneaks, and the
    disposition you're burning feeds every price, guard, and reaction
    roll in town.
