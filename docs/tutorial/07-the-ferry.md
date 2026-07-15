# Part 7 — The Ferry

Nobody rows the Gullwater on foot. A boat in REALM is not a system —
it's a thing you can stand *in*, that can *walk*. Containment plus
movement plus three softcode commands.

## Build her

```text
@create the ferry
@desc the ferry = A flat-bottomed skiff, tarred and patched. [[l = loc(me); result = 'Beyond the gunwale: ' + (l.name if l else 'darkness') + '.']]
@set the ferry/cmd_board = $board:move_to(enactor, me)
@set the ferry/cmd_ashore = $ashore:move_to(enactor, loc(me))
@set the ferry/cmd_row = $row *:move %0
drop the ferry
```

Three `$`-commands (part 4's trick, on a vehicle):

- `board` moves *you* into the ferry — you typed the command, so the
  move is consented, like walking a portal;
- `ashore` sets you back down wherever the ferry is;
- `row <direction>` is the whole propulsion system: `move` runs **as
  the ferry**, so the *boat* walks the exit — and you ride along,
  because you're inside it.

The `[[...]]` block in her description is the view over the gunwale:
it reads the ferry's location at look-time, so the same description
shows the Jetty at dock and Open Water at sea.

## Take her out

```text
board
row sea
look
row north
row east
```

Each stroke moves the skiff one cell; the sea materializes under her
bow as she goes. The engine's rule here is worth knowing: **terrain
materializes for players — afoot or aboard**. A boat with a crew
opens fresh water; an empty skiff cut loose (or a curious shark) is
becalmed at the edge of the known map.

Row back and `ashore` at the Jetty — or don't, and read on.

## Checkpoint

From aboard, `look` shows the ferry with the water beyond the
gunwale. `row jetty` at the entry cell walks her home through the
same exit you'd walk yourself.

!!! info "Learn more"
    Mounts and land vehicles are this same pattern — see the
    features roadmap. Gate who may board with a `use` lock on the
    ferry (`@lock/use the ferry = ...`): `$`-commands respect it.
    Followers don't auto-board; a party each types `board`.
