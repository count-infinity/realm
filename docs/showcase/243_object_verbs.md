# 243. Object-verb pattern

> Checklist item 243 — [now] — *$-commands gated by the use lock — native*

**What you'll build:** a holo-jukebox that understands `play <track>` and
`tracks` — bespoke verbs that live *on the object*, exist only where the
object is, and are gated by its `use` lock.

**Concepts:** `$pattern:code` command triggers (`cmd_*` attributes),
wildcard captures (`arg0`), `pemit`/`remit`, data attributes read by
softcode, the `use` lock, and the builtins-first dispatch boundary.

## How it works

This is PennMUSH's `$command` idiom, native in REALM: any attribute named
`cmd_<anything>` whose value is `$pattern:code` turns player input into a
script. When you type a line the dispatcher can't match to a built-in
command or an exit, it searches for `$`-triggers in a fixed order — the
contents of your room, the room itself, your inventory, then any zone
masters of the room. First match wins; `*` in the pattern captures text
into `arg0` (or `%0` in simple scripts).

The code after the `:` runs **as the jukebox**, with its owner's
authority: `me` is the jukebox, `enactor` is whoever typed the verb. That
one line is REALM's whole extension model — you'll see it again in every
tutorial in this arc.

Two gates keep it honest:

- **The `use` lock** decides who may fire an object's `$`-commands at all
  (unset = everyone in reach).
- **Builtins dispatch first.** The engine resolves built-in commands
  (exact name, alias, or unique prefix) and exits *before* it consults
  `$`-triggers, so softcode can extend the verb set but can never shadow
  or hijack `say`, `get`, `who`, or any other built-in.

## Build it

Everything below is typed live by a builder. Create the jukebox and put
it in the room (`@create` drops new things in your inventory):

```text
@create holo-jukebox
drop holo-jukebox
```

Its *content* is plain data — a JSON list any builder can retune later
without touching the verbs:

```text
@set holo-jukebox/tracks = ["Stardock Shanty", "Nebula Nocturne", "The Comet's Tail"]
```

Now the verbs. A no-argument verb first — `pemit` answers only the person
who asked:

```text
@set holo-jukebox/cmd_tracks = $tracks:pemit(enactor, 'Track list: ' + ', '.join(get_attr(me, 'tracks', [])))
```

And the star of the show, `play <anything>`. The `*` capture arrives as
`arg0`; the code is one line of sandboxed Python (`;` separates
statements, and a conditional *expression* handles the two outcomes).
`remit` speaks to the whole room; the miss message goes only to the
requester:

```text
@set holo-jukebox/cmd_play = $play *:hits = [t for t in get_attr(me, 'tracks', []) if arg0.lower() in t.lower()]; remit(here, name(me) + ' spins up: ' + hits[0]) if hits else pemit(enactor, name(me) + ' does not know that one.')
```

**Gate the verbs.** The `use` lock covers every `$`-command on the
object. Lock expressions see `caller` (whoever's typing), `target`, and
`owner`:

```text
@lock/use holo-jukebox = caller == owner
```

Now only the jukebox's owner can drive it — everyone else's `play` is
silently ignored, exactly as if the verb didn't exist for them. Open it
back up by clearing the lock:

```text
@lock/use holo-jukebox =
```

**The boundary: builtins win.** Try to hijack a built-in and nothing
happens — `say` is resolved by the dispatcher before `$`-triggers are
ever searched:

```text
@set holo-jukebox/cmd_hijack = $say *:pemit(enactor, 'GOTCHA')
```

`say hello there` still produces a normal say; the trigger never fires.
This is deliberate: object verbs *extend* the game's vocabulary, they
can't rewrite it. (Note the same applies to unique command *prefixes* —
if `pla` uniquely prefixes a built-in, the built-in gets it.)

## Try it

```text
> tracks
Track list: Stardock Shanty, Nebula Nocturne, The Comet's Tail
> play comet
holo-jukebox spins up: The Comet's Tail        (everyone in the room sees this)
> play polka
holo-jukebox does not know that one.           (only you see this)
```

Walk to the next room and `play comet` is just an unknown command — the
verb lives with the object.

## Going further

- **Coin-operated:** softcode can't reach into a player's pocket (the
  authority model again) — players *push* money with the built-in
  `pay 5 to holo-jukebox`, and an `ON_PAYMENT` script on the jukebox
  queues the song. The verb takes requests; the payment hook takes coins.
- **Verbs in your pocket:** `$`-triggers on inventory items work too —
  a communicator with `$hail *` travels with its carrier.
- **Zone-wide verbs:** put `$`-commands on a zone master and every room
  in the zone hears them. There is no global Master Room yet — the
  engine-blessed workaround for world-wide verbs is a *world-zone
  master*: an object tagged as master of a `zone:world` tag carried by
  every room.
- **A deliberate portal:** because typing an object's `$`-command is
  deliberate interaction, the script may relocate *you* —
  `$enter portal:move_to(enactor, 'The Oubliette')`. Passive triggers
  never get that power; item [250](250_player_scripting.md) tours the
  consent model.
