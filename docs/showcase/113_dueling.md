# 113. Dueling system

> Checklist item 113 — [now] — *consent prompt()s, start_combat, stakes escrow*

**What you'll build:** A sanctioned dueling ring: challenges are issued
at a stone, the challenged party consents through a `prompt()`, stakes
escrow into the stone, `start_combat()` throws both duelists onto the
beat, and the stone referees — paying the pot to whoever is left
standing. The ring's ward makes it the *only* place a swing can land.

**Concepts:** consent via `prompt()` (a typed answer, never a passive
trigger), scoped PvP with a room `on_check` ward over
`combat:on_attack`, escrow by **owner authority** (an admin-owned
house), `start_combat()`, and `ON_DEATH` as the referee's whistle.

## How it works

1. **PvP is scoped by a ward, not a switch.** REALM has no global PvP
   flag; policy is data. The Ring's room `on_check` blocks any
   `combat:on_attack` unless *both* parties carry the `duelist` tag.
   The `attack` command still enrolls people in an encounter — the ward
   stops the **swing**, every beat, with the house rules as the block
   reason — so unsanctioned violence in the Ring is all wind-up and no
   contact. (Outside the Ring this ward does not exist; a consent-only
   game wards its whole world the same way, one zone master
   `on_check`.)

2. **Consent is a typed word.** `duel <name>` stashes the pair on the
   stone and `prompt()`s the challenged player. The prompt captures
   their *next line* and runs the stone's `answer` attribute with it as
   `arg0`, the answerer as `enactor` — so acceptance is something they
   deliberately typed, in line with the consent-security model (passive
   triggers grant nothing; see `tests/test_consent_security.py`).
   Anything but `accept` declines.

3. **Escrow is owner authority — the house is admin.** On acceptance
   the stone pulls the stake from *both* players
   (`transfer_credits(player, me, stake)`) and tags them `duelist`.
   Mutating other players' purses and tags is exactly what the
   documented rule "admin-owned masters may write other players'
   sheets" is for: **this build must be done by an admin character.** A
   mortal-owned stone could not seize stakes — it would have to make
   each duelist `pay` it (item 114's board does exactly that).

4. **The stone referees by witnessing.** `start_combat(a, b)` opens the
   encounter (again: admin authority — you are throwing two players you
   do not own into a fight they consented to). When a duelist drops,
   the engine propagates `combat:on_death` with the **winner as
   `enactor`**, and the stone — standing in the room — hears it on its
   `ON_DEATH` attribute: pay the pot, strip both tags, announce. The
   loser is a player at 0 HP, so the native defeat rule applies: they
   are unconscious in place, not dead, and `firstaid` brings them back
   to settle the bar tab.

## Build it

As an **admin**. The ring and its law:

```text
@dig The Ring = ring, out
ring
@set here/on_check = block('The Ring hosts sanctioned duels only -- DUEL <name> to issue a challenge.') if atype == 'combat:on_attack' and not (has_tag(actor, 'duelist') and has_tag(target, 'duelist')) else None
```

The stone. Challenge, answer, and the referee's whistle:

```text
@create dueling stone
drop dueling stone
@desc dueling stone = A waist-high basalt block, its top hollowed into a coin bowl. DUEL <name> to put money on your grievance.
@set dueling stone/stake = 25
@set dueling stone/cmd_duel = $duel *: t = get(trim(arg0)); s = V('stake', 25); (pemit(enactor, 'A duel is already in the making. Wait for it to settle.') if V('challenged') else (pemit(enactor, 'They are not here to face you.') if not (t and has_tag(t, 'player') and loc(t) == loc(me) and t != enactor) else (pemit(enactor, 'One of you cannot cover the ' + str(s) + '-credit stake.') if credits(enactor) < s or credits(t) < s else (set_attr(me, 'challenger', enactor.id), set_attr(me, 'challenged', t.id), remit(loc(me), name(enactor) + ' lays a gauntlet on the dueling stone before ' + name(t) + '.'), prompt(t, name(enactor) + ' challenges you to a duel for ' + str(s) + ' credits. Type ACCEPT to fight -- anything else declines.', 'answer')))))
@set dueling stone/answer = a = get('#' + str(V('challenger', ''))); b = get('#' + str(V('challenged', ''))); s = V('stake', 25); (None if not (a and b and enactor == b) else ((del_attr(me, 'challenger'), del_attr(me, 'challenged'), remit(loc(me), name(b) + ' declines the duel. The gauntlet is returned.')) if trim(arg0).lower() != 'accept' else (transfer_credits(a, me, s), transfer_credits(b, me, s), add_tag(a, 'duelist'), add_tag(b, 'duelist'), remit(loc(me), 'The stakes -- ' + str(2 * s) + ' credits -- rattle into the stone. FIGHT!'), start_combat(a, b))))
@set dueling stone/on_death = a = get('#' + str(V('challenger', ''))); b = get('#' + str(V('challenged', ''))); s = V('stake', 25); w = enactor; (None if not (a and b and w and (w == a or w == b) and has_tag(w, 'duelist')) else (transfer_credits(me, w, 2 * s), remove_tag(a, 'duelist'), remove_tag(b, 'duelist'), del_attr(me, 'challenger'), del_attr(me, 'challenged'), remit(loc(me), name(w) + ' stands over a fallen rival. The stone pays out ' + str(2 * s) + ' credits.')))
```

## Try it

Unsanctioned first — walk two characters into the Ring and have one
type `attack` on the other. The fight *starts* (beats tick, actions
queue) but every swing bounces:

```text
The Ring hosts sanctioned duels only -- DUEL <name> to issue a challenge.
```

Now the real thing:

```text
duel Bruce            -> (room) Ace lays a gauntlet on the dueling stone before Bruce.
                         (Bruce) Ace challenges you to a duel for 25 credits. Type ACCEPT ...
(Bruce types) accept  -> The stakes -- 50 credits -- rattle into the stone. FIGHT!
```

Both are now `duelist`-tagged, the ward yields, and the encounter runs
on the ordinary beat — `queue`, `defend`, `pace`, all of it. When one
falls: "…stands over a fallen rival. The stone pays out 50 credits."
Winner is 25 up, loser is 25 down and unconscious until someone
`firstaid`s them, and the tags are gone — the very next punch is
unsanctioned again. Declining (`no`, or anything else) returns the
gauntlet and moves no money.

**Design note (not a gap):** if a duelist *flees* the Ring, nobody
dies, so the stone never pays out — the stakes sit in escrow until a
duel is concluded. Treat fleeing as forfeit with the ON_LEAVE variation
below.

## Going further

- **Forfeit on flight** — an `ON_LEAVE` on the ring room: if the
  leaver is a `duelist`, pay the pot to the *other* duelist and clean
  up — cowardice as a settled bet.
- **Named stakes** — parse `duel bruce = 100` (a second wildcard) and
  store the stake per-challenge instead of on the stone.
- **First-blood rules** — referee on `ON_DAMAGE` instead of
  `ON_DEATH`: first hit that lands settles the bet before anyone is
  carried out.
- **A betting book for the crowd** — combine with item 115's arena:
  spectators `pay` the stone on a fighter's name before the first beat,
  and `ON_DEATH` splits the losing pool among winners (item 92's
  market math).
