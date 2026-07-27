# 140. Death & Cloning

> Checklist item 140 ([now]): *the native death path, corpses, a clone-bay zone master listening on ON_DEATH, owner authority to raise the fallen*

**What you'll build:** a sci-fi resurrection system. When a player is
beaten down on the combat deck, a clone-bay controller hears it happen,
wakes them in a fresh body across the station, restores them to full, and
bills them for the vat. It is a death-and-respawn loop, and a close look at
what the engine tells you when someone dies, and *when* it tells you.

**Concepts:** REALM's **one death path** (`handle_death`) and its two
outcomes, where players fall unconscious in place and NPCs become lootable
corpses; [`ON_DEATH`](../reference/softcode.md#lifecycle-hooks) with
[`adata('fatal')`](../reference/softcode.md#event-data-namespace) as the
"a player dropped" signal; a **zone master** hearing every room of the
colony ([071](071_guard_response.md)); the **deferred handoff**, why an
undertaker acts just *after* the event it heard rather than inside it;
owner authority to teleport and heal a player ([069](069_trainer_npc.md)).

## How it works

The finished bay is a single admin-owned object sitting in the Clone Bay
with no ticker at all: it sleeps until a `combat:on_death` event reaches it,
files the fallen player's id, and lights a zero-second fuse that does the
rebirth once the death path has finished. This section answers four
questions in turn: what death actually does, how the bay is told which kind
happened, how one object hears rooms it does not sit in, and why the rebirth
waits a moment instead of firing inside the hook.

1. **There is exactly one death path, and it forks by kind.** Whatever
   deals the finishing blow, a swing, a poison tick, or a softcode
   [`damage()`](../reference/softcode.md#fn-damage), routes through the
   combat manager's `handle_death`:
   - **A player** is tagged `unconscious` in place and told *"Everything
     goes black..."*. Players stay alive and go down, revivable by
     `firstaid` ([112](112_nonlethal_takedowns.md)), or, here, by cloning.
   - **An NPC** becomes a **corpse**: a container holding everything it
     carried, dropped in the room, given a `decay` behavior that rots it
     after about 150 ticks, while a character-point award is split to the
     killer's party. Loot and XP, both native.

2. **The bay listens, and `fatal` tells it which fork happened.**
   `handle_death` announces `combat:on_death` from the one path every
   death reaches, so the bay does not hunt for the fallen, it is *told*.
   The payload carries the fork:
   - [`adata('fatal')`](../reference/softcode.md#event-data-namespace) is
     **False** when a player was knocked down. That is precisely the clone
     bay's business.
   - `adata('fatal')` is **True** for a real death, an NPC that is now a
     corpse. Not ours.

   The payload also carries `killer` as a name and binds the killer
   *object* as `actor`. The name is the attacker on a swing, the applier on
   a poison tick, the scripted object on a softcode `damage()`, and empty
   when a death has no source. The bay reads neither: it keys entirely off
   `target` (the body) and `fatal`.

3. **A zone master hears the whole colony.** The controller sits in the
   Clone Bay, but people die on the Combat Deck. Crown it with
   `@zone/master ... = colony` and events in **every** member room reach
   its `ON_<EVENT>` attributes, the same one-brain-per-area move the town
   watch makes in [071](071_guard_response.md). Tag another room into
   `colony` later and the bay covers it with nothing rewired. A zone master
   is a global witness, so its hook takes no `target is me` guard: it wants
   every death in its reach, and `fatal` alone selects the player-downs.

4. **The event fires *before* the body is transformed, so the rebirth
   waits for it.** This is the subtlety worth the tutorial. Deaths are
   announced first on purpose, because witnesses want to inspect the fallen
   before an NPC is swapped for a corpse: a bounty board reads the mark's
   name off the body ([114](114_bounty_board.md)), an arena recorder
   narrates it ([115](115_arena_spectators.md)). The consequence for us is
   that when `ON_DEATH` runs, `handle_death` has **not yet** stamped the
   `unconscious` tag, so a listener that revives *inside the hook* gets its
   [`remove_tag`](../reference/softcode.md#fn-remove_tag) overwritten a
   moment later, and the player wakes in the vat still tagged out cold,
   having been told "Cold light, then breath" *before* "Everything goes
   black...".

   So the bay does what any undertaker does: it hears the death, writes the
   name down, and does the work once the room has settled.
   [`wait(0, 'trigger me/drain')`](../reference/softcode.md#fn-wait) is that
   pause. It is not a delay, since zero seconds is zero seconds; it is a
   **yield**. A `wait()` runs on its own timer rather than on the caller's
   stack, so `wait(0, ...)` means "the moment the thing that called me has
   finished." `ON_DEATH` is a notification, not a place to rewrite the
   outcome, and the deferred handoff is the general shape for reacting *to*
   an event rather than *within* it. The fuse lives only in memory, which is
   irrelevant here where it lives for zero seconds, but see
   [148](148_delayed_actions.md) and [152](152_persistent_timers.md) for
   when that trade matters.

   The name goes into a **list**, not a slot, because two crew can drop in
   the same round and each death schedules its own fuse. Appending and
   letting `drain` empty the queue means the first fuse to fire revives
   everyone and the second finds nothing to do, which is correct at any body
   count. A single `fallen` attribute would let the second death clobber
   the first.

5. **Raising a player needs owner authority.** The controller teleports the
   fallen, sets their HP, clears `unconscious`, and pulls the clone fee from
   them, all mutations of a player's sheet, which softcode may do only with
   [`controls()`](../reference/softcode.md#fn-controls). So the controller
   is **admin-owned**, the same wall as the trainer
   ([069](069_trainer_npc.md)) and the survival master
   ([137](137_hunger_thirst.md)). A builder-owned bay would hear every death
   and then fail every write.

## Build it

**As your admin character**, dig the colony with both rooms zoned so the
master hears the deck as well as its own bay, then create the controller,
crown it a zone master, and set its two data attributes (which room is the
bay, and the clone fee):

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
@zone/master resurrection controller = colony
@set resurrection controller/bay = The Clone Bay
@set resurrection controller/fee = 50
```

The ear. `on_death` files the fallen body's id and lights a zero-second
fuse, but only for a player-down. Because a zone master witnesses the whole
colony, this hook wants every death and so takes no `target is me` guard;
`fatal` is the whole filter:

```text
@set resurrection controller/on_death = '''
# Zone master, so no target guard: fatal picks the player-downs out of every death in the colony.
if target and not adata('fatal', True):
    set_attr(me, 'fallen', V('fallen', []) + [target.id])
    # Defer past handle_death so the unconscious tag is set before revive clears it.
    wait(0, 'trigger me/drain')
'''
```

The pause. `drain` fires once the death path has finished, snapshots the
queue, empties it, and hands each filed id to `revive`. Draining the whole
list means a second fuse the same round finds an empty queue and does
nothing:

```text
@set resurrection controller/drain = '''
ids = V('fallen', [])
set_attr(me, 'fallen', [])
for i in ids:
    eval_attr(me, 'revive', i)
'''
```

The rebirth, run on one body. `revive` resolves the player by id, moves them
to the bay, wakes them, restores HP to full, debits the fee (taking every
credit they have if they are short), stamps a life counter, and narrates the
vat to the player and the room:

```text
@set resurrection controller/revive = '''
p = get('#' + arg0)
bay = get(V('bay', ''))
fee = int(V('fee', 50))
if p and bay:
    teleport_obj(p, bay)
    remove_tag(p, 'unconscious')
    set_attr(p, 'hp', int(get_attr(p, 'max_hp', 10)))
    if credits(p) >= fee:
        transfer_credits(p, me, fee)
    else:
        set_attr(p, 'credits', 0)
    count = int(get_attr(p, 'clone_count', 0)) + 1
    set_attr(p, 'clone_count', count)
    pemit(p, f'Cold light, then breath. You wake in a fresh body in the clone bay -- whole again. (clone #{count}, {fee} credits debited)')
    remit(bay, f'A clone vat cracks open with a hiss -- {name(p)} is reborn.')
'''
```

The controller has no `script_ticker`, so nothing sweeps and nothing wakes
up to check. The bay sleeps until somebody dies.

## Try it

Go down fighting on the deck, where an NPC beats a low-HP character to zero:

```text
(combat resolves)   -> Everything goes black...     (you fall unconscious, in place)
                    -> A clone vat cracks open with a hiss -- Cass is reborn.
                    -> Cold light, then breath. You wake in a fresh body in
                       the clone bay -- whole again. (clone #1, 50 credits debited)
```

Read the order of those lines: the black comes first, then the vat. The
controller heard the death *before* "Everything goes black..." was even
printed, and the zero-second fuse is what lets the narration land the right
way round. That is the deferred handoff earning its keep. Swap the `wait()`
for a direct call inside the hook and you would see the two lines invert,
and you would wake in the bay still tagged `unconscious`.

You are now in the Clone Bay at full HP, 50 credits lighter, with a
`clone_count` of 1 on your sheet, the respawn tax and a life counter in one.
Kill an *NPC* on the deck instead and you get the other fork: it `falls
dead`, leaving a lootable **corpse** where it stood with its gear inside,
and you collect the character-point award. The controller heard that death
too, and `adata('fatal')` was True, so it kept its vats shut. Same death
path, two destinies, one event that tells them apart.

## Going further

- **Limited lives:** gate `revive` on `clone_count < V('max_clones', 3)`.
  Past the limit, no vat opens and death is real. Permadeath as a policy
  attribute.
- **A sweep as the safety net:** an event you miss is missed forever, so if
  the bay is `halt`ed when you die, no fuse is ever lit and you lie on the
  deck until someone `firstaid`s you. A polling build is the cure, and it
  composes: keep `on_death` for the instant respawn and add a slow
  `script_ticker` whose `on_tick` sweeps
  [`zone_rooms('colony')`](../reference/softcode.md#fn-zone_rooms) for
  anyone tagged `player` and `unconscious` and hands each to `revive`.
  Listening is the fast path; the sweep is the reconciler that catches what
  the fast path dropped.
- **Clone degradation:** subtract a point of `max_hp` (or a stat) each
  rebirth, copies of copies, the genre's favorite tax.
- **Loot your own corpse:** give players the NPC treatment too by spawning a
  corpse container with their gear at the fall site, and make retrieval part
  of the respawn, the classic "death run".
- **Insurance, not billing:** flip the fee into a subscription, an `on_tick`
  premium ([093](093_housing_rent.md)) that, if paid, makes the clone free;
  lapse it and the vat wants cash up front.
