# 183. Permission tiers in practice

> Checklist item 183 — [now] — *the native model end-to-end: roles, locks, controls(), quell — a worked tour*

**What you'll build:** nothing new — this is a **tour** of the permission
model every other tutorial has been quietly standing on. You'll watch a
tag-gated lock refuse a mortal and admit the cleared, an admin bypass a
hard-deny lock and then *drop* that power with `quell`, and the one
authority predicate — `controls()` — decide who a script may touch.

**Concepts:** the five **roles** (god / admin / builder / player / guest)
and how a tag confers them, **locks** as the per-action gate, **admin
bypass** and its voluntary surrender via **quell**, and **`controls()`**
as the single mutation authority behind all softcode.

## How it works

REALM's permission model is three small ideas that compose. Learn them
once here and every "who's allowed to…" question in the showcase answers
itself.

### 1. Roles come from tags

An object's role is read straight off its tags, highest wins:

| Tag(s) | Role | Reach |
|---|---|---|
| `god` | **GOD** | everything, bypasses even other gods' control locks |
| `admin` / `wizard` | **ADMIN** | controls everything; bypasses locks |
| `builder` / `staff` | **BUILDER** | building commands; controls *unowned, non-player* world objects |
| `player` | **PLAYER** | acts on self and what it owns |
| (none) / `guest` | **GUEST** | the floor |

`has_permission(obj, 'builder')` is a `>=` test: an admin passes the
builder check, a player does not. That ladder is why `@dig` answers a
builder and refuses a mortal — the command is registered
`permission="builder"`, and the dispatcher checks the typer's role.

### 2. Locks gate individual actions

A lock is a sandboxed boolean expression, evaluated with `caller` (who's
acting), `target`, and `owner` in scope. Lock *types* name the action
they gate — `basic` (get/touch), `enter` (put-in / room-entry), `use`
(`$`-verbs), `control` (possession), `speech`, and more. The engine
checks the relevant lock inside the action itself, so a lock set on an
object **actually stops the deed**, whether that's picking it up, walking
an exit, or speaking in a room. Two rules make locks safe:

- **Fail closed.** An expression that errors (a missing attr, a typo)
  denies — it never falls open.
- **Admins bypass, gods always.** ADMIN skips ordinary locks; a `control`
  lock on a *god's* property still stops an admin. Bypass is a ladder,
  not a master key.

Set them with `@lock[/type] <obj> = <expr>`; the command validates the
expression at write time and refuses `import`, dunders, and syntax
errors, so a broken lock never reaches storage.

### 3. controls() is the one mutation authority

Every mutating softcode function — `set_attr`, `move_to`, `destroy_obj`,
`add_tag`, `force`, … — passes through a single predicate before it acts:

> **You control** yourself, what you **own**, and — as **ADMIN+** —
> everything. A **builder** additionally controls unowned, non-player
> world objects. And by **Penn delegation**, an object acts with *its
> owner's* authority (which is why `@chown` halts a scripted object: its
> code must not run with the new owner's power until reviewed).

This is the whole reason the showcase's staff consoles are **admin-owned**
and its player gadgets are safe: an admin-owned [jail](177_jail_system.md)
or [approvals desk](179_approval_queue.md) controls players *because its
owner does*; a player's [Chrono-Cube](250_player_scripting.md) controls
only that player's world *because that's all its owner controls*.
`controls()` is also exposed to softcode directly, so a script can check
its own reach before trying.

### quell — voluntarily acting as a mortal

An admin can't honestly test a mortal's experience while bypassing every
lock. `quell` drops your role to a mortal's for the session — you stop
bypassing locks and lose ADMIN authority — until `unquell`. It's the
Evennia idiom, and it's how staff verify a gate actually holds. (For
possession and the `control` lock as *consent*, see the
[puppet](066_puppet.md) — that's the fourth corner of this model.)

## Build it

A small security office and one tag-gated box:

```text
@dig The Security Office = secoff, out
secoff
@create strongbox
drop strongbox
@desc strongbox = A heavy lockbox. Only the cleared may lift it.
@lock strongbox = caller.has_tag('cleared')
```

## Try it

**Locks gate by expression.** A mortal without the tag is refused; grant
the tag and the same deed succeeds:

```text
(Rook) get strongbox
   -> You can't pick up strongbox.
@tag Rook = cleared
(Rook) get strongbox
   -> (Rook now holds the strongbox)
```

**Admins bypass — then quell to feel the wall.** Set a hard-deny lock
that *no* expression passes; the admin lifts it anyway, then quells and is
stopped like anyone:

```text
@lock strongbox = False
get strongbox            -> (admin picks it up — bypass)
drop strongbox
quell
get strongbox            -> You can't pick up strongbox.   (mortal now)
unquell
get strongbox            -> (powers restored — picks it up)
```

**controls() gates softcode mutation.** The same `set_attr` on a player's
sheet returns `False` for a builder who doesn't control them and `True`
for an admin who controls everything:

```text
(Bel, a builder)  @eval result = set_attr(get('Rook'), 'hp', 7)
   -> => False        (and Rook's hp is untouched)
(Odin, an admin)  @eval result = set_attr(get('Rook'), 'hp', 7)
   -> => True         (Rook's hp is now 7)
```

That single `False`/`True` is the entire security story of REALM's
softcode: a script may write exactly what its owner may, and not one
attribute more.

## Going further

- **Custom lock types are just names** — `@lock/use`, `@lock/enter`, or a
  bespoke `on_check` ward tag; the [keycard door](026_keycard_door.md)
  and [toll gate](030_toll_gate.md) show locks gating movement and money.
- **Delegated control** — hand a trusted player authority over a specific
  object with `@lock/control obj = caller.has_tag('deputy')`; they act on
  it without owning it (the [puppet](066_puppet.md) consent model).
- **quell in review** — quell before walking your own
  [approval gate](179_approval_queue.md) or [jail](177_jail_system.md) to
  confirm a mortal really can't slip through.
- **The capstone** — [restricted player scripting](250_player_scripting.md)
  hands this exact model to *players* and attacks it: same roles, same
  `controls()`, same locks, every wall holding.
