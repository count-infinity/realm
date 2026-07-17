# 245. Event bus tour

> Checklist item 245 — [now] — *two-pass propagation, ON_<EVENT> suffix matching, act() custom events, action tags*

**What you'll build:** a working mental model of REALM's event bus — plus
a small demonstrator (a temple bell that fires a *custom* event and a
shrine that reacts to it) that proves every claim. This is the reference
the other scripting tutorials point back to.

**Concepts:** the propagation engine, the two-pass (check → apply) model,
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
triggers (the actor never fires its *own* `ON_<EVENT>`), so a witness
always knows who set the event off.

## Build it

A temple bell fires a custom `toll` event into its room; a shrine hears
it and answers. Neither knows about the other — they meet on the bus:

```text
@create temple bell
drop temple bell
@set temple bell/cmd_ring = $ring bell:act(me, 'A deep bell tolls across the temple.', targeting='room', action_type='event:toll')
@create prayer shrine
drop prayer shrine
@set prayer shrine/on_toll = remit(here, 'The shrine candles flare as the bell tolls.')
```

`ring bell` runs `act(...)` as the bell, which propagates an
`event:toll` action through the room. The shrine's `on_toll` matches by
suffix and fires, with the bell as its `enactor`.

## Try it

```text
> ring bell
A deep bell tolls across the temple.
The shrine candles flare as the bell tolls.
```

Two objects that were never wired together reacted in order — the bell
spoke to the room, the shrine answered the name. Add a third object with
its own `on_toll` and it joins in for free; nobody edits the bell.

## Going further

- **Zone-wide alarms:** `act(intruder, 'Klaxons wail!', targeting='zone',
  action_type='event:alert')` reaches every room in the zone; give each
  door an `on_alert` that slams shut. One event, a whole quarter reacts.
- **Wards that veto:** an `on_check` on a witness can `block('the seal
  holds')` during the check pass — the same bus, the interception half.
  See the [interception guide](../guides/interception.md).
- **Zone-master ears:** an `ON_ENTER` on a zone master hears entries in
  *every* member room — one greeter for an island (item
  [240](240_builder_triggers.md)).
- **Remote reach:** `act(target, msg, targeting='remote')` crosses into
  the target's room if its `reach` lock allows — the seam scrying and
  remote casting share.
