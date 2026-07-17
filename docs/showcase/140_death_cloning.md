# 140. Death & Cloning

> Checklist item 140 — [now] — *the native death path, corpses, a polling clone-bay master, owner authority to raise the fallen*

**What you'll build:** a sci-fi resurrection system. When a player is
beaten down on the combat deck, a clone-bay controller notices, wakes them
in a fresh body across the station, restores them to full, and bills them
for the vat. Death with a respawn loop — and a hard look at what the engine
does and doesn't tell you when someone dies.

**Concepts:** REALM's **one death path** (`handle_death`) and its two
outcomes — players fall unconscious in place, NPCs become lootable
corpses; a **polling** clone bay (written before `combat:on_death` fired
for players — it now does, so listening is an option; the ticker remains
a good demonstration in its own right); owner authority to teleport and
heal a player ([069](069_trainer_npc.md)).

## How it works

1. **There is exactly one death path, and it forks by kind.** Whatever
   deals the finishing blow — a swing, a poison tick, a softcode
   `damage()` — routes through the combat manager's `handle_death`:
   - **A player** is tagged `unconscious` in place and told *"Everything
     goes black…"*. Players don't die; they go down, revivable by
     `firstaid` ([112](112_nonlethal_takedowns.md)) — or, here, by cloning.
   - **An NPC** becomes a **corpse**: a container holding everything it
     carried, dropped in the room, given a `decay` behavior (it rots after
     ~150 ticks), while a character-point award is split to the killer's
     party. Loot and XP, both native.

2. **The clone bay watches for the downed, because nothing tells it.**
   Here is the sharp edge: when a *player* falls, `handle_death` tags them
   `unconscious` and stops — it fires **no** `ON_DEATH`/`on_death` event
   for a player at all. So there is nothing for a clone bay to *hook*. The
   robust pattern is to **poll**: an admin-owned controller carries
   `script_ticker`, and each tick it sweeps `zone_rooms('colony')` for
   anyone tagged both `player` and `unconscious`, and clones them. State
   you can't be notified of, you look for — the leaderboard's idiom
   ([228]) pointed at mortality.

3. **Raising a player needs owner authority.** The controller teleports the
   fallen, sets their HP, clears `unconscious`, and pulls the clone fee
   *from* them — all mutations of a player's sheet, which softcode may do
   only with `controls()`. So the controller is **admin-owned**, the same
   wall as the trainer ([069](069_trainer_npc.md)) and the survival master
   ([137](137_hunger_thirst.md)). A builder-owned bay would poll happily
   and then fail every write.

4. **~~Engine gaps~~ — BOTH FIXED 2026-07-17.** This build polls because
   of two gaps that no longer exist. `combat:on_death` is now announced
   from `CombatManager.handle_death` — the one path every death reaches —
   so:
   - **A player going down fires it.** It used to emit nothing at all, and
     polling the `unconscious` tag was the only signal. A bay can now
     *listen*: `ON_DEATH` with `adata('fatal') == False` is exactly "a
     player dropped". (The polling version below still works, and is a
     fine demonstration of a ticker — but it is no longer forced.)
   - **Softcode and effect kills fire it.** An NPC killed by `damage()` or
     a `damage_over_time` tick used to die silently, so bounty boards
     ([114](114_bounty_board.md)) and arena bells
     ([115](115_arena_spectators.md)) missed it. They don't now, and you no
     longer have to land the killing blow with the combat system for a
     witness to hear it.

## Build it

**As your admin character**, dig the colony (both rooms zoned so the sweep
reaches the deck) and post the controller in the bay:

```text
@dig The Clone Bay = clonebay, out
clonebay
@zone here = colony
@dig The Combat Deck = deck, clonebay
deck
@zone here = colony
clonebay
@create resurrection controller
drop resurrection controller
@desc resurrection controller = A bank of glass vats trailing coolant mist, wired to a patient monitor that never blinks.
@set resurrection controller/bay = The Clone Bay
@set resurrection controller/fee = 50
@behavior resurrection controller = script_ticker, interval:1
```

The poll, and the rebirth it performs on each fallen player:

```text
@set resurrection controller/on_tick = [eval_attr(me, 'revive', p.id) for r in zone_rooms('colony') for p in contents(r) if has_tag(p, 'player') and has_tag(p, 'unconscious')]
@set resurrection controller/revive = p = get('#' + arg0); bay = get(V('bay', '')); fee = int(V('fee', 50)); (None if not (p and bay) else (teleport_obj(p, bay), remove_tag(p, 'unconscious'), set_attr(p, 'hp', int(get_attr(p, 'max_hp', 10))), (transfer_credits(p, me, fee) if credits(p) >= fee else set_attr(p, 'credits', 0)), set_attr(p, 'clone_count', int(get_attr(p, 'clone_count', 0)) + 1), pemit(p, 'Cold light, then breath. You wake in a fresh body in the clone bay -- whole again. (clone #' + str(get_attr(p, 'clone_count', 1)) + ', ' + str(fee) + ' credits debited)'), remit(bay, 'A clone vat cracks open with a hiss -- ' + name(p) + ' is reborn.')))
```

## Try it

Go down fighting on the deck — an NPC beats a low-HP character to zero:

```text
(combat resolves)   -> Everything goes black...     (you fall unconscious, in place)
```

You're tagged `unconscious`, lying on the deck. On the controller's next
tick the poll finds you:

```text
(a tick passes)     -> A clone vat cracks open with a hiss -- Cass is reborn.
                    -> Cold light, then breath. You wake in a fresh body in
                       the clone bay -- whole again. (clone #1, 50 credits debited)
```

You're now in the Clone Bay at full HP, 50 credits lighter, with a
`clone_count` of 1 on your sheet — the respawn tax and a life counter in
one. Kill an *NPC* on the deck instead and you get the other fork: it
`falls dead`, leaving a lootable **corpse** where it stood (its gear
inside), and you collect the character-point award. Same death path, two
destinies — and, per the gaps above, only the NPC's swing-death would ring
a bell you hung on `on_death`.

## Going further

- **Limited lives:** gate `revive` on `clone_count < V('max_clones', 3)` —
  past the limit, no vat opens and death is real. Permadeath as a policy
  attribute.
- **Clone degradation:** subtract a point of `max_hp` (or a stat) each
  rebirth — copies of copies, the genre's favorite tax.
- **Loot your own corpse:** give players the NPC treatment too — spawn a
  corpse container with their gear at the fall site and make retrieval part
  of the respawn, the classic "death run".
- **Insurance, not billing:** flip the fee into a subscription — an
  `on_tick` premium ([093](093_housing_rent.md)) that, if paid, makes the
  clone free; lapse it and the vat wants cash up front.
