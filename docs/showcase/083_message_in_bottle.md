# 083. Message in a bottle

> Checklist item 83 ([now]): *expire() drift, ON_EXPIRE self-rescue, presence roster workaround, random delivery*

**What you'll build:** A corked bottle. `pen <text>` seals a note inside it,
`toss bottle` gives it to the tide, and a long, random while later it washes
up at the feet of a random player somewhere in the world, who can
`uncork bottle` and read what you wrote.

**Concepts:** [`expire()`](../reference/softcode.md#fn-expire) as a persistent
random-delay timer, `ON_EXPIRE` as a delivery event the object survives by
clearing its own `expires_at`, an `ON_CONNECT` / `ON_DISCONNECT` presence
roster on a world-zone master (the honest workaround for softcode's missing
presence query), [`rand()`](../reference/softcode.md#fn-rand) selection, and an
object that relocates itself.

## How it works

The finished toy is one bottle and one bookkeeper. The bottle carries the
`pen` / `uncork` / `toss` commands and a note attribute, while a world-zone
master called the Harbormaster keeps a list of who is currently ashore. Tossing
the bottle sends it out to sea on a persistent countdown, and when that
countdown lapses the bottle picks a random player from the Harbormaster's list,
moves itself into that player's room, and announces the surf. This section
answers three questions: why the drift timer is [`expire()`](../reference/softcode.md#fn-expire)
rather than [`wait()`](../reference/softcode.md#fn-wait), how "a random online
player" is answered without a presence primitive, and why the bottle is allowed
to move itself.

### Why the drift is `expire()`, not `wait()`

A bottle at sea for hours has to outlast a server restart, and that is the whole
difference between the two timers. [`wait()`](../reference/softcode.md#fn-wait)
schedules a command in memory, so a reboot forgets it. [`expire()`](../reference/softcode.md#fn-expire)
instead stamps a persistent `expires_at` timestamp on the object, and the
engine's world tick reaps any object whose stamp has passed: it fires
`ON_EXPIRE`, then destroys the object unless the hook has cleared or pushed out
`expires_at`. That destroy-by-default is the hook's contract, and the bottle
exploits it, because for this build delivery is a rescue. The `ON_EXPIRE`
script picks a recipient, calls [`del_attr`](../reference/softcode.md#fn-del_attr)
on its own `expires_at` (the survival move), moves itself to the recipient's
room, and announces the surf. If it finds no one ashore it re-arms with a fresh
short fuse and drifts on. Either way the bottle never dies; it just keeps
missing landfall until a player is there to receive it.

### How the bottle finds a random online player

Softcode has no presence primitive: no function lists connected players, and
no attribute marks them, since `who` is a builtin and sessions are invisible to
scripts. The honest workaround is a roster the world maintains for itself. The
Harbormaster is a world-zone master, so it hears `event:connect` and
`event:disconnect` from every room tagged `zone:world` and keeps an `ashore`
list of player ids. Two boundaries come with that, and both are worth stating
plainly: a login in a room that nobody remembered to tag `zone:world` is missed,
and a hard crash can strand a stale id, so the delivery script re-verifies that
each id still resolves to a live object before trusting it. If the roster comes
up empty, the bottle falls back to any player object in the world, since the
bottle and its note are persistent either way and a returning player will find
it waiting at their feet. The [custom channel](074_custom_channel.md) hits the
same wall when it wants a channel roster, and it points here for the reason.

### Why the bottle may move itself

Both the toss and the landfall relocate the bottle, and both run as the bottle's
own script under its owner's authority.
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj) (a thin alias for
`move_to(force=True)`) demands control of the moved object, and the bottle,
executing its own trigger, controls itself. Rooms accept arrivals unless they
are locked, so the empty `The Open Sea` (a room with no exits, because the tide
is not a place players visit) and the destination shore both take the bottle
without complaint. Writing the note is the same idea as the
[typewriter](010_typewriter.md) pressing prose into a sheet: the text lives in
an attribute on the object, so it travels wherever the object drifts.

## Build it

A beach on the world zone, a cliff to prove the delivery reaches across rooms,
and the sea itself:

```text
@dig The Shingle Beach = beach, out
beach
@zone here = world
@dig The Sea Cliff = cliff, beach
cliff
@zone here = world
beach
@dig The Open Sea
```

The Harbormaster is created like any object and then promoted to the world
zone's brain with `@zone/master`, so it hears logins from every `zone:world`
room:

```text
@create Harbormaster
drop Harbormaster
@desc Harbormaster = A weathered official who seems to know exactly who is ashore at any hour.
@zone/master Harbormaster = world
```

The roster is two single-statement hooks. Connecting moves your id to the back
of the list and never stores it twice; disconnecting drops it. Both fire on the
Harbormaster itself as a zone master, so neither needs a `target` guard:

```text
@set Harbormaster/on_connect = set_attr(me, 'ashore', [i for i in (V('ashore') or []) if i != enactor.id] + [enactor.id])
@set Harbormaster/on_disconnect = set_attr(me, 'ashore', [i for i in (V('ashore') or []) if i != enactor.id])
```

The bottle itself is an ordinary object with a description that doubles as its
instructions:

```text
@create green bottle
@desc green bottle = Sea-scoured glass, stoppered with a cork. PEN <text> writes a note; TOSS BOTTLE gives it to the tide; UNCORK BOTTLE reads what is inside.
```

`pen` refuses unless you are holding the bottle, then stores your line as the
note with your name appended. [`escape()`](../reference/softcode.md#fn-escape)
keeps player prose out of the markup parser, and the identity check is `is not`,
never `!=`, because it compares two objects:

```text
@set green bottle/cmd_pen = '''
$pen *:
if loc(me) is not enactor:
    pemit(enactor, 'Hold the bottle to write.')
else:
    set_attr(me, 'note', f'{escape(arg0)} --{name(enactor)}')
    pemit(enactor, 'You roll the note tight and work it down the neck.')
'''
```

`uncork` reads the note back, or reports an empty bottle if none was penned:

```text
@set green bottle/cmd_uncork = '''
$uncork bottle:
if not V('note'):
    pemit(enactor, 'The bottle is empty.')
else:
    pemit(enactor, f"The note reads: {V('note')}")
'''
```

`toss` demands the bottle in hand and a note already inside, then tells the room,
sends the bottle out to sea, and starts the persistent drift countdown. The
fuse is [`expire()`](../reference/softcode.md#fn-expire), so it survives a
reboot where a [`wait()`](../reference/softcode.md#fn-wait) would not:

```text
@set green bottle/cmd_toss = '''
$toss bottle:
if loc(me) is not enactor:
    pemit(enactor, 'Hold the bottle to throw it.')
elif not V('note'):
    pemit(enactor, 'It needs a note first. PEN <text>.')
else:
    remit(loc(enactor), f'{name(enactor)} hurls the green bottle out past the breakers.')
    teleport_obj(me, 'The Open Sea')  # the bottle relocates itself, under its owner's authority
    expire(me, rand(60, 300))         # persistent fuse: survives a reboot, unlike wait()
'''
```

And landfall, the rescue-and-deliver hook. It reads the Harbormaster's roster,
keeps only ids that still resolve, falls back to every player in the world if
the roster is empty, picks one at random, and if that player is somewhere real
it clears its own fuse, moves itself to their room, and announces the surf.
`ON_EXPIRE` is a reactive hook that fires on every object in the room, so the
body is wrapped in the `target is me` guard so only the expiring bottle runs it:

```text
@set green bottle/on_expire = '''
if target is me:
    hm = get('Harbormaster')
    ids = [i for i in (get_attr(hm, 'ashore') or []) if get('#' + str(i))]  # drop stale ids a crash may have left
    pool = ids or [p.id for p in search_world(tag='player')]                # empty roster: fall back to any player
    w = get('#' + str(pool[rand(0, len(pool) - 1)])) if pool else None
    if w and loc(w):
        del_attr(me, 'expires_at')  # clear the fuse, or the world tick destroys the bottle after this hook
        teleport_obj(me, loc(w))
        pemit(w, 'A green glass bottle washes up at your feet.')
        oemit(w, 'Something glints at the tide-line.')
    else:
        expire(me, 60)  # no one to receive it: drift on with a fresh short fuse
'''
```

## Try it

Pen a note and give the bottle to the tide:

```text
> get green bottle
> pen The lighthouse ledger is a fake. Check the cellar. Tell no one.
You roll the note tight and work it down the neck.
> toss bottle
Bilda hurls the green bottle out past the breakers.
```

The bottle now sits in The Open Sea with a one-to-five-minute fuse. When it
lapses, whoever the tide favors among the players the Harbormaster knows are
ashore gets:

```text
A green glass bottle washes up at your feet.
```

The bottle is really there, in their room, note and all:

```text
> get green bottle
> uncork bottle
The note reads: The lighthouse ledger is a fake. Check the cellar. Tell no one. --Bilda
```

Toss it again and it drifts to someone else. A server reboot mid-drift changes
nothing, because `expires_at` is a persistent attribute and the world tick picks
the countdown back up. Try `pen` or `toss` with the bottle on the ground and the
tide demands you hold it first, and `uncork` on an unpenned bottle reports it
empty.

## Going further

- **Slower oceans:** `rand(3600, 86400)` makes landfall a once-a-day surprise.
  The mechanism does not care about the size of the number, which is the point
  of [`expire()`](../reference/softcode.md#fn-expire).
- **Never the sender:** stamp the sender's id at toss and filter `pool` by
  `i != V('sender')`, so the sea never hands your secret straight back to you.
- **A bottle economy:** the [newspaper](082_newspaper.md) kiosk pattern sells
  empty bottles, so castaway notes become content at five credits a throw.
- **File the gap:** a game that leans on presence really wants an engine
  primitive, a `connected()` function or an engine-maintained tag. The roster
  is a workaround, and it should retire the day the engine learns to answer
  "who is online" in softcode.
