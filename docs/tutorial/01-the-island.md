# Part 1 — The Island

Connect to a fresh game (`realm init lighthouse && cd lighthouse &&
realm start`), create your superuser (`create Keeper <password>`),
pick any background, and you're in The Void. Let's leave it.

## Rooms and exits

`@dig` creates a room and, optionally, an exit pair to it:

```text
@dig The Jetty = north, south
north
```

You're standing on the jetty. Two more:

```text
@dig The Lighthouse Steps = up, down
up
@dig The Lamp Room = up, down
```

Don't go up yet — the lamp room is for part 5.

## Descriptions

```text
@desc here = Salt-bleached steps spiral up the cliff face. Gull nests
crowd every ledge, and the lighthouse door hangs off one hinge above.
```

(Your client sends that as one line.) `look` to admire it.

## Details only some characters see

Here's the first taste of what makes this an engine and not a notepad —
a **per-viewer detail**. Characters with sharp eyes see more:

```text
@detail here = check('observation', -2) -> Scratched into the third
step: a crude arrow pointing down, and the letters T-I-D-E.
@detail here = Broken glass glitters between the stones.
```

The first line rolls the looker's `observation` skill (at -2) every
time they look; the second shows to everyone. Try `look` — as a fresh
superuser your observation is untrained, so the scratches are a coin
flip. `@detail here` lists what you've set; `@detail/clear here`
wipes them.

## Checkpoint

`look` from the Jetty should show your description, maybe the
scratches, and exits north (Void... rename it later), south, up.

!!! info "Learn more"
    `help building` lists every builder command. Details support
    stable thresholds too — `skill('observation') >= 12` — and
    full inline logic with `[[...]]` blocks (part 4).
