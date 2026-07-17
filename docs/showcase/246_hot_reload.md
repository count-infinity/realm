# 246. Hot-reload workflow

> Checklist item 246 — [now] — *softcode is always live; @reload re-reads data rules; only engine code needs a restart*

**What you'll build:** the developer's inner loop — edit a live NPC's
softcode and watch the change take effect on the *next line*, no restart;
`@reload` when you've changed data-driven rules; and a clear picture of
what survives a reboot and what doesn't.

**Concepts:** live `@set` editing (softcode is never "compiled in"),
`@reload` for `skill_def`/`class_def` tables, and the persistence line —
`db` attributes and `expire()` survive a restart; `wait()` timers do not.

## How it works

REALM has three layers, and they refresh at three speeds:

1. **Softcode is always live.** A `cmd_*`, `on_<event>`, `listen_*`, or
   `[[…]]` block is read from the object's attribute table *every time it
   fires*. `@set` rewrites the attribute; the very next trigger runs the
   new code. There is nothing to reload — no compile step, no cache to
   bust. This is the whole point of building from inside the game.

2. **Data rules need `@reload`.** Skills and classes are `skill_def` /
   `class_def` objects, but the *check table* built from them is cached
   in the engine for speed. After you `@create` or edit a `skill_def`,
   `@reload` re-reads those objects and re-installs the table so checks
   pick up the change. (New classes are read fresh at each character
   creation, so they need no reload.) Importing a pack calls this for you.

3. **Engine code needs a restart.** Python in `realm/` — new commands,
   new behaviors, new functions — only changes on `@reboot`. If you find
   yourself wanting one for *content*, you've usually found something that
   should have been softcode or data instead.

### What survives a reboot

| Survives | Dies |
|---|---|
| `db` attributes (everything `@set`/`set_attr` writes) | `wait()` timers (in-memory, one-shot) |
| `expire()` leases (`db.expires_at` is a stored attribute) | anything held only in a running script |
| triggers, locks, behaviors (all attributes) | a half-finished `wait()` chain |

So a fuse built on `expire()` + `ON_EXPIRE` re-arms itself after a
restart; a fuse built on `wait()` quietly forgets. Use `wait()` for
sub-heartbeat precision that may be lost harmlessly (a spinning delay);
use `expire()` for anything that must survive (a summoned creature's
lifespan, a real countdown).

## Build it

A dockmaster with one verb. Fire it, edit it live, fire it again — the
change lands with no reload:

```text
@create dockmaster
drop dockmaster
@set dockmaster/cmd_hail = $hail dockmaster:pemit(enactor, 'Dockmaster: Bay 1 is open.')
```

A player hails once, you rewrite the verb *while the world runs*, and the
next hail speaks the new line:

```text
@set dockmaster/cmd_hail = $hail dockmaster:pemit(enactor, 'Dockmaster: Bay 1 is full - try Bay 7.')
```

Now the data-rule layer. You only need this after editing a `skill_def`
or `class_def`:

```text
@reload
```

`Rules reloaded from the world.` — the check table is rebuilt from the
current definition objects. Softcode edits above needed no such thing.

## Try it

```text
> hail dockmaster
Dockmaster: Bay 1 is open.
                                  (you @set the verb to its new text)
> hail dockmaster
Dockmaster: Bay 1 is full - try Bay 7.
```

Same object, same session, no restart — the second hail read the freshly
written attribute. That is the loop: type, `@set`, test, repeat, all at a
live prompt.

## Going further

- **A durable timer, tested:** rebuild any `wait()` fuse on `expire()` +
  `ON_EXPIRE` and it survives `@reboot`; the countdown lives on the
  object as `db.expires_at`.
- **Reload after import:** `@import/apply` and `@pack` change the world's
  data; `@pack` already calls `@reload` for you, so imported skills and
  classes are live immediately (item [235](235_content_packs.md)).
- **Quell to test honestly:** `quell` drops your builder powers so you
  experience an edit as a mortal would before you trust it.
- **Prove it in a test:** the Simulator drives this exact loop — set a
  verb, fire, re-set, fire — and asserts the new output. Item
  [247](247_testing_your_game.md) shows the harness.
