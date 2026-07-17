# 245. Event bus tour

> Checklist item 245 — [now] — *two-pass propagation, ON_<EVENT> suffix matching, act() custom events, action tags*

**What you'll build:** a working mental model of REALM's event bus — plus
a small demonstrator (a temple bell that fires a *custom* event and a
shrine that reacts to it) that proves every claim. This is the reference
the other scripting tutorials point back to.

**Concepts:** the propagation engine, the two-pass (check → apply) model,
the **event data namespace** (`target`, `atype`, `adata`, `has_atag`),
`ON_<EVENT>` suffix matching, `act()` for inventing events, `^listen` for
speech, `on_check` wards, zone-master witnessing, and who becomes
`enactor`.

## How it works

Every observable thing in REALM — a step through a door, a picked-up
lantern, a spoken word, a swung blade — becomes an **Action** that flows
through one propagation engine. Scripts don't poll and don't register
callbacks; they hang an attribute on an object, and the engine delivers
matching actions to it. That single stream is the "event bus."

### The two passes

Each action propagates in two passes over its witnesses (the room, its
contents, the target, and any zone master of the room):

1. **Check pass** — wards run first. An object's `on_check` softcode (or
   a Python behavior) may read the pending action, add a modifier, or
   **block** it. A cursed ring refusing `remove`, a sealed door refusing
   `unlock`, a guard vetoing an exit — all live here. (Interception is
   its own arc; item [240](240_builder_triggers.md) flags which hooks are
   "gated.")
2. **Apply pass** — if nothing blocked it, the action happens and
   `ON_<EVENT>` reaction scripts fire on every witness.

Because wards run *before* the world changes, a veto is clean: the move
that would have followed never happens.

### What a reaction knows: the event data namespace

A script that hears an action can read **what happened**, not merely who
did it. These names are bound in every `ON_<EVENT>` hook and every
`^listen` — the same names `on_check` wards always had:

| Name | Meaning |
|---|---|
| `atype` | the action type (`item:on_get`, `event:payment`, `combat:on_damage`, …) |
| `actor` | who is acting (the same object as `enactor`) |
| `target` | what/who the action targets |
| `adata(key, default)` | the action's payload |
| `has_atag(tag)` | orthogonal action *categories* (below) |

`target` is the one that turns a witness into a participant, and it is the
one you will forget. Read the next section before you write a hook.

`has_atag` reads a vocabulary that runs *across* action types, so you match
a category instead of enumerating every event that belongs to it. The
kernel guarantees six: `movement`, `hostile`, `visual`, `sound`,
`scripted`, `failure`. A game may add its own (`fire`, `poison`, `magic`);
`has_atag` reads them all the same. Object tags (`room`, `player`, `dark`)
are a different vocabulary on the same plumbing — those say what a *thing*
is, these say what an *action* is.

A `$`-command or a `@tr` has **no action behind it**, so these names are
unbound there. That is the honest boundary: the namespace exists because
an action does.

The payloads the engine carries today:

| Action | `adata` keys |
|---|---|
| `event:payment` | `amount` |
| `item:on_get` / `item:on_drop` | *(none — the item **is** `target`)* |
| `item:on_give` | `item` (the recipient is `target`) |
| `event:on_receive` | `item`, `giver` |
| `combat:on_damage` | `damage`, `damage_types` |
| `combat:on_attack` | `weapon`, `attacker_hp`, `defender_hp` |
| `combat:on_death` | `killer` (a *name*; the killer object is `actor`), `fatal` |
| `combat:on_hitprcnt` | `percent` |
| speech / emit | `message`; poses also carry `pose` |
| `event:on_cast` | `ability`, `caster` |

### `target`: "to me" vs "near me"

**This is the single most important line in this tutorial.** Events are
propagated to *every witness in the room* — not only to the object the
action concerns. An `ON_RECEIVE` on a shopkeeper fires when **any** two
people in his shop hand each other **anything**. An `ON_DEATH` on a boss
fires when a rat dies across the room. `ON_PAYMENT` on a till fires for
every sale in the market square.

So a reaction script must answer a question the engine will not answer for
it: **did this happen *to me*, or merely *near me*?** That is `target`:

```text
@set Harbor Agent/on_receive = it = adata('item') if target is me else None
```

Without the guard, the Agent accepts deliveries made to somebody else
standing in his office, and pays for them.

This trap is new, and it is sharp. Before the data namespace existed, hooks
worked by rummaging through their own contents (`[o for o in contents(me)
if has_tag(o, 'orders')]`) — which was clumsy, but *accidentally* answered
"to me" as a side effect: an item given to someone else was never in your
pockets to find. Reaching for `adata('item')` drops the clumsiness **and
the guard along with it**. When you modernize an old hook, put the guard
back explicitly.

The rule of thumb:

| Hook lives on | Wants | Because |
|---|---|---|
| a **participant** (a shopkeeper, a boss, a till) | `target is me` | it should only react to its own business |
| a **zone master / chronicle** (a global witness) | *no* `target` guard | it is never the target; it watches everyone |

A global witness has the mirror-image job: it never asks `target is me`,
but it must be careful *whose* record it writes — `actor` did the thing,
`target` had it done to them.

### Two smaller traps

- **`get`/`drop` carry no `item` key.** The item *is* `target`. Reach for
  `adata('item')` there and you get `None`. `adata('item')` exists where
  the target is a *person* — `give` and `receive`.
- **`ON_GET` fires before the item lands.** The whole two-pass propagation
  runs while the item is still on the floor, so an inventory read inside
  `on_get` will not see it. You rarely need one now: `target` already
  names the item.

### The apply pass is read-only

`on_check` wards get everything above **plus** the decision verbs —
`block(reason)`, `mod(n)`, `is_blocked()`, `set_adata(k, v)`. Reaction
scripts do not. By the time an `ON_<EVENT>` runs the decision is already
made and the world has already changed, so there is nothing left to veto:
the apply pass **observes**. If you want to stop something, you want a
ward ([interception guide](../guides/interception.md)) — not an
`ON_<EVENT>` that tries to undo its own aftermath.

### The four ways to hear an event

| Form | Attribute | Fires when |
|---|---|---|
| `$pattern:code` | `cmd_*` | a player types a matching line ([243](243_object_verbs.md)) |
| `^pattern:code` | `listen_*` | matching speech is overheard (gated by the `listen` lock) |
| `ON_<EVENT>` | `on_<event>` | that lifecycle event reaches the object |
| `on_tick` | — | on a timer, via the `script_ticker` behavior |

`ON_<EVENT>` matching is **by suffix**: an `on_toll` attribute fires for
any propagated action whose type ends in `…:toll`. That is why you never
register events — you just react to a name, and anyone (including
`act()`) may fire that name.

### The standard lifecycle events

These are the events the engine fires itself (the single source of truth
is `STANDARD_EVENTS` in `realm/scripting/triggers.py`, which the
[softcode reference](../reference/softcode.md) renders):

| Group | Hooks |
|---|---|
| **Movement / location** | `ON_ENTER`, `ON_LEAVE`, `ON_ARRIVE`, `ON_FAIL` |
| **Perception / interaction** | `ON_LOOK`, `ON_USE`, `ON_PUSH` |
| **Item lifecycle** | `ON_GET`, `ON_DROP`, `ON_GIVE`, `ON_RECEIVE`, `ON_PUT`, `ON_WEAR`, `ON_REMOVE`, `ON_WIELD`, `ON_UNWIELD`, `ON_OPEN`, `ON_CLOSE`, `ON_LOCK`, `ON_UNLOCK` |
| **Combat** | `ON_ATTACK`, `ON_DAMAGE`, `ON_HITPRCNT`, `ON_DEATH`, `ON_CAST` |
| **Existence** | `ON_LOAD`, `ON_EXPIRE`, `ON_RESET`, `ON_TICK` |
| **Session** | `ON_CONNECT`, `ON_DISCONNECT`, `ON_PAYMENT` |

`REMOVE`, `WIELD`/`UNWIELD`, `LOCK`/`UNLOCK`, and `CAST` are the *gated*
ones — their check pass can be vetoed by an `on_check` ward. There is
deliberately **no `ON_SAY`**: speech is what `^listen` patterns are for,
with wildcard matching and the `listen` lock.

### ON_DEATH fires from every death

`combat:on_death` deserves its own note, because it used to be narrower
than its name. It fired inside the *swing* path only — so an NPC killed by
softcode `damage()`, by a poison tick, or by a trap died in silence, and a
player going down announced nothing at all. Bounty boards and arena
recorders had to poll for corpses.

Now **every** route into death announces, from the one shared death path:

- swings, softcode `damage()`, damage-over-time ticks, traps;
- **players** going down, not just NPCs.

Read `adata('fatal')` to tell the two apart: `True` is a real death (an
NPC, about to become a corpse), `False` is a player knocked unconscious in
place and revivable. The event fires *before* the body is transformed, so
a witness can still inspect the fallen. `actor` is the killer object (or
`None` — a trap has no killer); `adata('killer')` is their *name*.

```text
@set Chronicle/on_death = pemit(actor, name(target) + ' falls.') if adata('fatal') else None
```

### act(): inventing your own events

`act(target, message, targeting=…, action_type='event:<name>')` pushes a
brand-new action onto the bus. Give some other object an `on_<name>` and
it reacts — no engine change, because suffix matching makes every event
name free. `targeting` chooses the audience:

- `'room'` — the target's room (local, still propagated so wards apply).
- `'remote'` — the target's *other* room (scry, remote cast); gated by
  that room's `reach` lock.
- `'zone'` — every room in the target's zone (an alarm).

The action's **actor** becomes the `enactor` of every reaction it
triggers (the actor never fires its *own* `ON_<EVENT>` — the bell below
does not hear itself), so a witness always knows who set the event off.

An `act()`ed event binds the data namespace too: `target` is the object
you passed, and the message lands as `adata('message')`. `act()` has no
parameter for arbitrary keys, so a custom event's payload is its message —
stamp richer state on an attribute and let the witness read it.

## Build it

A temple bell fires a custom `toll` event into its room; a shrine hears
it and answers. Neither knows about the other — they meet on the bus:

```text
@create temple bell
drop temple bell
@set temple bell/cmd_ring = $ring bell:act(me, 'A deep bell tolls across the temple.', targeting='room', action_type='event:toll')
@create prayer shrine
drop prayer shrine
@set prayer shrine/on_toll = remit(here, 'The shrine candles flare as ' + name(target) + ' tolls: "' + adata('message', '') + '"')
```

`ring bell` runs `act(...)` as the bell, which propagates an `event:toll`
action through the room. The shrine's `on_toll` matches by suffix and
fires, with the bell as its `enactor` — and it reads the event's own data
to answer: `target` names *what* tolled and `adata('message')` quotes what
the toll said. The shrine has no reference to the bell anywhere in its
script; everything it knows arrived with the action.

## Try it

```text
> ring bell
A deep bell tolls across the temple.
The shrine candles flare as temple bell tolls: "A deep bell tolls across the temple."
```

Two objects that were never wired together reacted in order — the bell
spoke to the room, the shrine answered the name *and quoted it back*. Add
a third object with its own `on_toll` and it joins in for free; nobody
edits the bell. Swap the bell for a gong and the shrine's line follows,
because it reads `target` rather than a name it was told at build time.

## Going further

- **Zone-wide alarms:** `act(intruder, 'Klaxons wail!', targeting='zone',
  action_type='event:alert')` reaches every room in the zone; give each
  door an `on_alert` that slams shut. One event, a whole quarter reacts.
- **Wards that veto:** an `on_check` on a witness can `block('the seal
  holds')` during the check pass — the same bus, the interception half.
  Wards also get `mod(n)` and `set_adata(k, v)`, so a ward can *rewrite*
  the payload a later reaction reads. See the
  [interception guide](../guides/interception.md).
- **"Was that me?":** `target is me` in any `ON_<EVENT>` separates being
  the subject of an action from merely witnessing it — a till that hears
  `ON_PAYMENT` for the whole market only rings for its own sales. The
  delivery quest ([199](199_delivery_quest.md)) shows it load-bearing: the
  same hook without the guard pays out for a handover to a bystander.
- **Match a category, not a list:** `has_atag('movement')` in a ward stops
  walking, fleeing, following *and* a cast-teleport in one line, without
  naming any of them — and `has_atag('movement') and not adata('exit')`
  narrows that to teleports only, since a walk carries the exit it used.
- **Zone-master ears:** an `ON_ENTER` on a zone master hears entries in
  *every* member room — one greeter for an island (item
  [240](240_builder_triggers.md)).
- **Remote reach:** `act(target, msg, targeting='remote')` crosses into
  the target's room if its `reach` lock allows — the seam scrying and
  remote casting share.
