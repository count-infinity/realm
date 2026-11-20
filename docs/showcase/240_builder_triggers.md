# 240. Builder trigger system

> Checklist item 240 — [now] — *$-commands, ^listen, ON_<EVENT> — the native feature*

**What you'll build:** a lighthouse that reacts — a gallery that greets
everyone who steps onto it, a keeper who answers when he overhears the
word "dark", a lantern that flares when picked up, and a heartbeat pose
on a timer. All of it typed at the prompt; no source files, no restart.

**Concepts:** `ON_<EVENT>` lifecycle hooks, `^pattern:code` listen
triggers (`listen_*` attributes), `on_tick` + the `script_ticker`
behavior, `@tr` test-firing, the `halt` tag.

## How it works

Item [243](243_object_verbs.md) covered verbs players *type at* an
object. This tutorial is the other half of REALM's trigger system:
scripts that fire when the world *happens to* an object. Three trigger
families, all plain attributes:

| Form | Attribute | Fires when |
|---|---|---|
| `$pattern:code` | `cmd_*` | a player types a matching line (item 243) |
| `^pattern:code` | `listen_*` | matching speech is overheard (gated by the `listen` lock) |
| code | `ON_<EVENT>` | that lifecycle event reaches the object |
| code | `on_tick` | on a timer, via the `script_ticker` behavior |

Every game action flows through the propagation engine, and the script
engine observes that stream: when an action's type reaches an object (its
room, itself as target, or a zone master of the room), a matching
`ON_<EVENT>` attribute runs — executor = the object, `enactor` = whoever
acted. There is no separate "trigger editor": `@set` writes the
attribute, `@examine` shows it, `@tr obj/attr` test-fires it, and tagging
the object `halt` stops a runaway machine.

A hook doesn't just learn *that* something happened — it gets the action
itself, under the same names an `on_check` ward has always used:

| Name | Is |
|---|---|
| `enactor` / `actor` | who acted |
| `target` | what the action targets — how a witness tells "I was paid" from "someone here was paid" |
| `adata(key, default)` | the action's payload: `amount` on a payment, `item`/`giver` on a give, `damage` on a hit, `pose` on an emote, `percent` on `ON_HITPRCNT` |
| `atype`, `has_atag(tag)` | the action's type string and its tags |

The same names reach `^listen` scripts. This pass is deliberately
**read-only**: it runs after the world has already decided, so there is
no `block()` or `mod()` here — vetoing belongs to `on_check` wards,
which see the action *before* it lands.

The standard events (from the [softcode reference](../reference/softcode.md),
which is generated from the engine's own table):

| Hook | Fires when | | Hook | Fires when |
|---|---|---|---|---|
| `ON_ENTER` | something enters this location | | `ON_OPEN` | this door/container is opened |
| `ON_LEAVE` | something leaves this location | | `ON_CLOSE` | this door/container is closed |
| `ON_ARRIVE` | this object arrives somewhere new | | `ON_LOCK` | this is locked (gated) |
| `ON_FAIL` | a move was thwarted — the @afail | | `ON_UNLOCK` | this is unlocked (gated) |
| `ON_LOOK` | this object is looked at | | `ON_ATTACK` | this object attacks / is attacked |
| `ON_USE` | this object is used | | `ON_DAMAGE` | this object takes damage |
| `ON_PUSH` | this object is pushed | | `ON_HITPRCNT` | HP fell through `db.hitprcnt` |
| `ON_GET` | this object is picked up | | `ON_DEATH` | this object dies |
| `ON_DROP` | this object is dropped | | `ON_CAST` | an ability targets this object |
| `ON_GIVE` | this object is given away | | `ON_LOAD` | this object was just spawned |
| `ON_RECEIVE` | this object is given something | | `ON_EXPIRE` | its `db.expires_at` elapsed |
| `ON_PUT` | this object is put in a container | | `ON_RESET` | this zone master resets |
| `ON_WEAR` | this object is worn | | `ON_TICK` | periodic timer (`script_ticker`) |
| `ON_REMOVE` | this object is taken off (gated) | | `ON_CONNECT` | player connects |
| `ON_WIELD` / `ON_UNWIELD` | weapon readied / lowered (gated) | | `ON_DISCONNECT` | player disconnects |
| | | | `ON_PAYMENT` | this object was paid |

Matching is by suffix, so an `ON_<anything>` attribute fires for any
propagated `…:<anything>` action — `act()` can invent new events and
witnesses react with hooks nobody had to register. "Gated" hooks pair
with an `on_check` ward that can veto the action (a cursed ring refusing
`remove` — that's the interception arc's territory).

There is deliberately no `ON_SAY`: reacting to speech is what `^listen`
patterns are for, with wildcard matching and the `listen` lock deciding
whose speech an object may overhear.

## Build it

Start in the lamp room of your lighthouse. Dig the gallery and give the
new room an arrival script — `ON_ENTER` fires on the room when anything
enters it, and `enactor` is the walker:

```text
@dig The Gallery = out, in
out
@set here/on_enter = pemit(enactor, 'Salt wind claws at you as you step onto the gallery.')
in
```

A keeper who overhears. `^*dark*` matches any speech containing "dark";
the code after the `:` here is a *simple script* — a bare `say` line,
no Python needed (`%0` would carry the capture):

```text
@create keeper
drop keeper
@set keeper/listen_dark = ^*dark*:say The lamp must never go dark. Never!
```

An item that reacts to being taken — `ON_GET` fires on the thing picked
up:

```text
@create storm lantern
drop storm lantern
@set storm lantern/on_get = pemit(enactor, 'The lantern flares white as you lift it.')
```

A heartbeat. The `script_ticker` behavior runs its object's `on_tick`
script on a cadence; `@tr` test-fires any script attribute right now so
you don't have to wait 30 seconds to check your work:

```text
@behavior keeper = script_ticker, interval:30
@set keeper/on_tick = pose polishes the great lens.
@tr keeper/on_tick
```

You should see *keeper polishes the great lens.* — and so does everyone
in the room, every 30 seconds from now on.

## Try it

As a player (no builder powers needed):

```text
> out
Salt wind claws at you as you step onto the gallery.
> in
> say Looks like it's getting dark out there.
keeper says, "The lamp must never go dark. Never!"
> get storm lantern
The lantern flares white as you lift it.
```

If the keeper ever runs away with itself: `@tag keeper = halt` silences
every trigger on him while you investigate; `@untag keeper = halt`
revives him.

## Going further

- **Escalate:** `ON_ENTER` on the gallery could `skill_check(enactor,
  'climbing')` in a storm and `damage(enactor, 1)` on a failure — hooks
  run real sandboxed Python with the whole function library.
- **Read the event, not just the name:** `@tag keeper = npc` (the `give`
  builtin only hands things to players and tagged NPCs), then
  `@set keeper/on_receive = say(f'{name(adata("giver"))} gives me
  {name(adata("item"))}.')` — and he names what he was handed and by
  whom. Give him an `on_payment` that checks `target == me` and he
  ignores coins that went to someone else in the room. (`ON_GET`/
  `ON_DROP` are the exception: there the item *is* the `target`, so
  there is no `adata('item')` to read.)
- **React to new events:** fire your own with
  `act(here, 'the beam sweeps past', targeting='room',
  action_type='event:beam')` from one object, and give another
  `ON_BEAM` — suffix matching means custom events are free.
- **Zone-wide ears:** put `ON_ENTER` on a zone master and it hears
  entries in *every* member room — one greeter for the whole island.
- **Durable timers:** `wait()` is in-memory and dies on a restart; for a
  fuse that must survive, `expire()` + `ON_EXPIRE` persists.
