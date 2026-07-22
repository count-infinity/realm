# Part 2 — Keys and Doors

The lighthouse cellar is where the keeper kept... something. It's
below the Steps, behind a locked trapdoor.

## A locked exit

```text
@dig The Cellar = trapdoor, hatch
@tag trapdoor = closed
@tag trapdoor = locked
@set trapdoor/key_id = cellar_key
@set trapdoor/locked_msg = The trapdoor's iron lock is crusted with salt, but solid.
```

Try it: `open trapdoor` — refused. A `closed` exit must be opened; a
`locked` one needs its key first.

## The key, hidden in plain sight

Remember the scratched arrow and T-I-D-E from part 1? Pay it off.
Back on the Jetty (`down`):

```text
@create tide-worn key
@set tide-worn key/unlocks = cellar_key
@set tide-worn key/description = Rust in the shape of luck. The wards match a heavy lock.
drop tide-worn key
@tag tide-worn key = hidden
@set tide-worn key/conceal_difficulty = 2
```

A `hidden` object doesn't show in the room — players find it with
`search` (an Observation check against its `conceal_difficulty`; higher
= harder). As the superuser you'd *see* the key regardless — to test as
a real player, `quell` first (and `unquell` to restore your powers). The detail line you wrote is the
clue that makes searching *here* feel earned.

## The happy path, as a player

```text
search
get key
north
unlock trapdoor
open trapdoor
trapdoor
```

You're in the cellar. Dark, isn't it? Literally, if you like:

```text
@tag here = dark
```

Now it renders as pitch black unless someone carries a `light`-tagged
object or has nightvision. Make a lantern:

```text
@create storm lantern
@tag storm lantern = light
drop storm lantern
```

!!! info "Learn more"
    Locks go far beyond keys: `@lock` gates *who* may pass with safe
    expressions (`@lock/enter here = caller.has_tag('keeper')`), and
    `@set door/lock_skill = lockpicking` makes them pickable. See
    `help @lock` and the perception system for light/dark rules.
