# Enterable Things — Object-as-Interior (inside descriptions, enter/leave, INNER/OUTER command scoping)

**Status:** Deferred design option — **not built**. REALM's shipped idiom for
interiors is *vehicle-as-room* (`docs/showcase/155_drivable_vehicle.md`), which
covers most cases. This document captures when an *object-as-interior* model
would be worth adding, the coherent bundle it implies, and where each piece
would live — so adopting it is a considered choice, not a one-off flag.

## The question

A single object often wants different behaviour depending on whether the actor
is *inside* it or *outside* it — a cockpit's `$pilot` (inside only) vs `$board`
(outside only); an inside description vs an outside one. Today a builder
hand-guards every such command with `loc(enactor) == me`. The proposal that
prompted this: per-attribute `inner` / `outer` flags so the matcher does the
guard, plus the inside-description and enter/leave affordances that make "being
inside a thing" a first-class state.

## What PennMUSH does (verified against source)

PennMUSH splits the inside/outside axis across three first-class surfaces — but
**not** commands:

- **Descriptions — first-class.** `IDESCRIBE` / `OIDESCRIBE` / `AIDESCRIBE`
  fire when the Thing is your `location`; otherwise `DESCRIBE` (outside) is used
  (`src/look.c:491-508`, with a fallback chain to `DESCRIBE`/`DESCFORMAT`).
  Rooms/exits always use `@describe`; only players/things get an inside desc.
- **Entering — first-class.** The `ENTER_OK` flag (`hdrs/flag_tab.h:34`) plus
  `enter`/`leave` commands (`src/move.c:922-989`), gated by `@lock/enter` /
  `@lock/leave` (and the `NOLEAVE` flag). "Vehicle" is a *builder convention* —
  an ENTER_OK Thing with IDESCRIBE + listen patterns — **not** an engine type
  (there is no VEHICLE flag).
- **Movement messages — first-class inside/outside split.** `OENTER`/`OLEAVE`
  to those *inside* the object vs `OXENTER`/`OXLEAVE` to those *outside*, in its
  location (`src/move.c:106-164`). Emitted only for non-room locations.
- **Directional sound.** `@filter`/`@prefix` (outward) vs `@infilter`/
  `@inprefix` (inward) across the boundary (`Filter_Lock` / `InFilter_Lock`).
- **Commands — NOT gated by inside/outside.** The matcher `atr_comm_match`
  (`src/attrib.c:1857-2112`) never consults the enactor↔object relationship: a
  Thing's `$command` fires **both** when you're inside it and when you're beside
  it in the same room. The only per-object gates are `HALT`, the `NO_COMMAND`
  flag, `@lock/command` / `@lock/use`, and the per-attribute `no_command`
  (`AF_NOPROG`) flag — none location-aware. **Builders hand-guard with
  `loc(%#)==me`**, or gate the whole object with an eval `@lock/command`.

Takeaway: **an INNER/OUTER *command* flag has no PennMUSH analog — it would be
strictly better than Penn**, which forces either a whole-object lock or a manual
per-command assertion. (Precedent that per-attribute perception flags fit the
model: `^listen`'s AHEAR/MHEAR self-vs-others flags, `attrib.c:2010-2014`.)

## What REALM does today

- **`$`-command matching is inside/outside-blind.** `get_search_objects`
  (`realm/scripting/triggers.py:458`) returns a flat list — room contents, the
  room itself (`player.location`), inventory, zone masters — so an object's
  `$commands` are eligible both when it is your location (inside) and when it is
  a room-content (outside). The matcher never distinguishes; a builder would
  guard `loc(enactor) == me` by hand, exactly Penn's situation.
- **Interiors are rooms.** The shipped vehicle idiom (155) makes the cab a
  **room** reached by a `board` exit, with relocatable `board`/`hatch` exits.
  Inside vs outside is separated by **room membership** — inside commands live
  in the cab room, outside stuff in the world room. This sidesteps INNER/OUTER
  entirely and is arguably cleaner than Penn's enterable-Thing.
- **Per-attribute flags exist.** `realm/core/attrflags.py` —
  `db.attr_flags = {attr: [flags]}`, managed by `@attr`, a deliberately minimal
  four (`secret` / `visual` / `safe` / `no_clone`, "the four that earn their
  keep of PennMUSH's ~30"). The trigger matcher does **not** consult attr-flags
  today.
- **No inside description** (`idesc`) and **no generic `enter <thing>`**
  command — entering is always via an exit into a room.

## The decision: vehicle-as-room vs object-as-interior

INNER/OUTER-on-commands **only bites when one object is both enterable and
room-visible at once** — the object-as-interior pattern REALM doesn't have. With
vehicle-as-room, room membership already scopes inner vs outer. And even under
object-as-interior, you can often scope by **placement**: an object placed
*inside* the enterable Thing appears in the search list only for occupants (its
container is their location); one in the room appears only for those outside. So
the flag is strictly needed **only** for putting *both* inner and outer commands
on the *same* object — a convenience, not a necessity.

**When object-as-interior actually wins over a room:**

- **Mass-produced / lightweight interiors** where digging a room each is heavy —
  100 escape pods, a barrel to hide in, a sedan chair, a phone booth.
- **A piloted object that must stay a first-class Thing in the room** — a mech
  that is also a combat entity you `get`/attack, not an abstract exit-pair.

For those, room-as-interior is awkward and object-as-interior is the right
model.

## The bundle (if adopted)

Object-as-interior is a *coherent set*, not a lone flag; adopt it whole or not
at all:

1. **Inside description (`idesc`)** — the real gap. When `look` runs on your
   location and it is a non-room object, show its `db.idesc` (falling back to
   `db.description`); when you look *at* the thing from outside, show
   `description`. Mirrors IDESCRIBE. Highest-value piece.
2. **`enter` / `leave` primitive** — an `enter <thing>` command (ENTER-lock
   gated, `enterable` tag) that sets your location to the thing, and `leave`
   back to its location; or bless softcode `move_to(enactor, thing)` for the
   same. Reuses the movement core and the existing enter-lock.
3. **INNER/OUTER attr-flags** — the smallest, most-decomposable piece. Add
   `inner` / `outer` to `VALID_FLAGS` in `attrflags.py`; in the trigger matcher,
   gate a flagged script attribute on `enactor.location is obj` (`inner`) /
   `enactor.location is not obj` (`outer`). Re-derive the relationship at match
   time — no need to thread it through the flat search list (unlike PennMUSH,
   whose matcher is relationship-agnostic and would need the caller to pass a
   relationship enum). Cost: one comparison per *flagged* attribute; opt-in,
   zero cost for unflagged attributes.
4. **(Optional) inside/outside action messages** — an "occupants vs onlookers"
   audience split for enter/leave and in-thing actions, à la OENTER/OXENTER.
   REALM's per-recipient propagation already makes this expressible; a helper
   would formalize it.

## Recommendation

**Keep vehicle-as-room as the default. Do not build INNER/OUTER standalone** —
it has no trigger in the current model. Add object-as-interior only when a
concrete need lands (mass interiors, or a piloted room-entity), and then as the
whole bundle above, led by `idesc` + `enter`/`leave` (the pieces we actually
lack), with INNER/OUTER as the convenience layer on top.

Cross-references: `docs/showcase/155_drivable_vehicle.md` (the vehicle-as-room
idiom), `realm/core/attrflags.py` (the flag mechanism), `realm/scripting/
triggers.py` `get_search_objects` (the match list), `docs/design/engine_vision.md`
(authority model the enter-lock plugs into).
