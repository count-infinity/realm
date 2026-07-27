# 219. Friends list

> Checklist item 219 ([now]): *contacts with login/logout notifications, privacy opt-outs, world-master ON_CONNECT/ON_DISCONNECT, consent attributes*

**What you'll build:** a Social Registry that lets any player keep a private
contact list with `befriend Vala`, `friends` and `unfriend Vala`, and that
quietly tells you when one of your contacts logs in or out. A player who would
rather travel unnoticed types `cloak`, and their comings and goings stop being
announced.

**Concepts:** a per-player contact list held as `friends_<id>` attributes on a
world-zone master; the `ON_CONNECT`/`ON_DISCONNECT` presence roster shared with
the [message in a bottle](083_message_in_bottle.md); notifications aimed only at
the watchers who asked for them; a privacy opt-out attribute; and an explicit
`members` roster, because softcode reads attributes one known name at a time.

## How it works

The finished build is a single object, the Social Registry, promoted to be the
master of the `world` zone. It carries one attribute per player holding that
player's contact ids, one `members` list naming every player who has ever used
it, one `online` list of ids currently connected, and one `hide_<id>` flag per
player who has opted out of announcements. Five `$`-commands read and write
those attributes, and two lifecycle hooks keep the `online` list current and
send the notifications. The rest of this section answers four questions: where
"who is online" comes from, how one player's list is stored, how the Registry
works out whom to notify, and who decides whether a login is announced at all.

### Where does "who is online" come from?

There is no softcode function that lists connected players. `who` is a builtin
command and sessions are not exposed to scripts, which the capability audit
tracks as gap G4. So the world keeps the answer for itself, exactly as the
Harbormaster does in [message in a bottle](083_message_in_bottle.md): the
Registry is a **world-zone master**, so it hears `event:connect` and
`event:disconnect` from every room tagged `zone:world` and maintains its own
`online` list of player ids.

Two boundaries come with that and are worth stating plainly. A login in a room
that nobody tagged `zone:world` never reaches the Registry, so the roster and
the notifications both skip it. A hard shutdown can also strand an id whose
object is gone, so every script here resolves an id back to an object with
[`get`](../reference/softcode.md#fn-get) and acts only when something comes
back.

### How is one player's contact list stored?

`befriend <player>` appends that player's id to `friends_<your id>` on the
Registry, so each player's list is a separate attribute keyed by their own id
and no player's list is reachable through another player's commands. The
relationship is deliberately one-way, like the contacts in a phone: you watch
whoever you add, whether or not they add you back.

### How does the Registry know whom to notify?

Notifying works the opposite way round from adding. When Bob connects, the
question is "who has Bob's id in their list?", and answering it means checking
every list. Softcode reads an attribute by naming it, with
[`V`](../reference/softcode.md#fn-v) or `get_attr`, and every function that
reaches an attribute takes its name, so the Registry finds its own `friends_*`
attributes only by holding a list of the keys. That list is `members`, which
`befriend` extends with the caller's id, and which both hooks walk to rebuild
the set of names to check. The [bank](087_bank_accounts.md) keeps its holder
roster explicitly for the same reason.

### Why do the two hooks take no `target` guard?

Most `ON_<EVENT>` hooks need `if target is me:` because
[the whole room hears an event](../reference/softcode.md#guard-on-target).
Connect and disconnect are different for two reasons. Their `target` is the
**room** the player appeared in, never the Registry, so an identity test against
`me` would be false every single time. More to the point, the Registry is a zone
master watching everybody, which is the deliberate exception the guard rule
names. What keeps its reactions correct is not a target test but the
`enactor.id` key: every attribute it touches is named after the player who just
connected. For the propagation model behind this, see
[Action Propagation](../architecture/events.md) and the
[event bus tour](245_event_bus_tour.md); for the full hook table, see
[`ON_<EVENT>` lifecycle hooks](../reference/softcode.md#lifecycle-hooks).

One consequence is worth knowing before you read `on_connect`: an actor never
fires its own `ON_<EVENT>`, so a connecting player's own hooks stay quiet about
their own login. That is why the Registry, and not the player, sends the
"contacts online" greeting.

### Who decides whether a login is announced?

The person moving, not the person watching. `cloak` sets `hide_<id>` on the
Registry and both hooks fall silent for that player; `uncloak` deletes the flag
and the announcements resume. A watcher who would rather not hear about someone
simply drops them with `unfriend`.

The verb is `cloak` rather than `hide` because the dispatcher tries builtin
commands, unique builtin prefixes and room exits before it looks at an object's
`$`-commands, and `hide` is already the builtin stealth command. `friends`,
`befriend`, `unfriend`, `cloak` and `uncloak` are all free of that collision,
which is the only test a public verb has to pass.

## Build it

Start with a world-zone hub and a second world-zone room, so the finished build
can prove that presence reaches across the map rather than only across one
room:

```text
@dig The Social Hub = hub, out
hub
@zone here = world
@dig The Quiet Corner = corner, hub
corner
@zone here = world
hub
```

Create the Registry and promote it to master of the `world` zone. Build it as an
admin, because it messages players wherever they stand and writes on their
behalf, and owner authority is the honest footing for a public service:

```text
@create the Social Registry
drop the Social Registry
@desc the Social Registry = A directory terminal. BEFRIEND <name> adds a contact; FRIENDS lists them; UNFRIEND <name> drops one; CLOAK and UNCLOAK set whether your logins are announced.
@zone/master the Social Registry = world
```

`befriend` resolves the name with [`get`](../reference/softcode.md#fn-get) after
[`trim`](../reference/softcode.md#fn-trim), rejects anything that is not another
player, refuses a duplicate, and otherwise appends the id and records the caller
in `members`. Since `get` searches the executor's room first and then the whole
world, a contact may be anywhere:

```text
@set the Social Registry/cmd_befriend = '''
$befriend *:
other = get(trim(arg0))
mine = V('friends_' + enactor.id, [])
if other is None or not has_tag(other, 'player') or other is enactor:
    pemit(enactor, 'No such player.')
elif other.id in mine:
    pemit(enactor, name(other) + ' is already a contact.')
else:
    set_attr(me, 'friends_' + enactor.id, mine + [other.id])
    # the members roster is how the connect hook finds watchers later
    set_attr(me, 'members', sorted(set(V('members', []) + [enactor.id])))
    pemit(enactor, f'Added {name(other)} to your contacts.')
'''
```

`unfriend` is the mirror image, gated on the id already being in your own list,
and it rewrites the list without that id:

```text
@set the Social Registry/cmd_unfriend = '''
$unfriend *:
other = get(trim(arg0))
mine = V('friends_' + enactor.id, [])
if other is not None and other.id in mine:
    set_attr(me, 'friends_' + enactor.id, [i for i in mine if i != other.id])
    pemit(enactor, f'Removed {name(other)} from your contacts.')
else:
    pemit(enactor, 'That player is not on your contact list.')
'''
```

`friends` prints your list, one line each, tagging every entry against the
`online` roster:

```text
@set the Social Registry/cmd_friends = '''
$friends:
mine = V('friends_' + enactor.id, [])
online = V('online', [])
if mine:
    pemit(enactor, 'Your contacts:')
    for pid in mine:
        who = get('#' + pid)
        # a stored id outlives the object it names, so skip ids that no longer resolve
        if who is not None:
            status = 'online' if pid in online else 'offline'
            pemit(enactor, f'  {name(who)} - {status}')
else:
    pemit(enactor, 'Your contact list is empty. BEFRIEND <name> to start.')
'''
```

`cloak` and `uncloak` are the privacy opt-out, one attribute set with
[`set_attr`](../reference/softcode.md#fn-set_attr) and cleared with
[`del_attr`](../reference/softcode.md#fn-del_attr), which is safe to run even
when no flag is there:

```text
@set the Social Registry/cmd_cloak = '''
$cloak:
set_attr(me, 'hide_' + enactor.id, 1)
pemit(enactor, 'Cloaked: your logins and logouts are no longer announced.')
'''
@set the Social Registry/cmd_uncloak = '''
$uncloak:
del_attr(me, 'hide_' + enactor.id)
pemit(enactor, 'Your contacts will again be told when you come and go.')
'''
```

`on_connect` does three things in order: it refreshes the roster by moving the
arriving id to the back, it walks `members` and
[`pemit`](../reference/softcode.md#fn-pemit)s each online watcher who lists the
arriving player, and it greets the arrival with a count of their own contacts
already on. Holding the pre-arrival roster in `already_on` is what makes the
second and third steps exclude the connecting player without a separate test:

```text
@set the Social Registry/on_connect = '''
already_on = [i for i in V('online', []) if i != enactor.id]
set_attr(me, 'online', already_on + [enactor.id])
if not V('hide_' + enactor.id, 0):
    for pid in V('members', []):
        watcher = get('#' + pid)
        if watcher is not None and pid in already_on and enactor.id in V('friends_' + pid, []):
            pemit(watcher, f'{name(enactor)} has come online.')
mine = V('friends_' + enactor.id, [])
if mine:
    up = [f for f in mine if f in already_on]
    pemit(enactor, f'{len(up)} of your contacts are online.')
'''
```

`on_disconnect` is the same walk in the other direction, and it tells the
watchers before it drops the leaving id, so the departing player is still on the
roster while the announcements go out:

```text
@set the Social Registry/on_disconnect = '''
roster = V('online', [])
if not V('hide_' + enactor.id, 0):
    for pid in V('members', []):
        watcher = get('#' + pid)
        if watcher is not None and pid in roster and pid != enactor.id and enactor.id in V('friends_' + pid, []):
            pemit(watcher, f'{name(enactor)} has gone offline.')
set_attr(me, 'online', [i for i in roster if i != enactor.id])
'''
```

## Try it

Bob adds two contacts and lists them. Neither is on the roster yet, so both read
`offline`:

```text
> befriend Vala
Added Vala to your contacts.

> befriend Cass
Added Cass to your contacts.

> befriend Vala
Vala is already a contact.

> friends
Your contacts:
  Vala - offline
  Cass - offline
```

Now Bob logs in, then Vala logs in from The Quiet Corner. Bob lists Vala and Bob
is on the roster, so Bob hears about it, and the announcement crosses rooms
because both rooms are tagged `zone:world`. Vala lists nobody, so she gets
nothing at all:

```text
(Bob sees)   Vala has come online.
(Vala sees)  <nothing: she has no contacts, so there is no greeting>
```

Vala would rather travel unnoticed:

```text
> cloak
Cloaked: your logins and logouts are no longer announced.
```

Her next login and logout now say nothing to Bob, and `uncloak` turns the
announcements back on. Dropping a contact stops the pings at the source, which
is the watcher's own list:

```text
> unfriend Cass
Removed Cass from your contacts.
```

The two results worth confirming deliberately are the cross-room announcement
(move Vala to The Quiet Corner before logging her in) and the silence after
`cloak`, since both are the parts a one-room test would miss.

## Going further

- **A GMCP contact widget.** Swap the connect `pemit` for
  [`oob`](../reference/softcode.md#fn-oob):
  `oob(watcher, 'Comm.Friend', {'name': name(enactor), 'status': 'online'})`,
  so a rich client lights a buddy-list panel instead of printing a line.
- **Mutual-only mode.** Notify a watcher only when the connecting player lists
  them back, by adding `and pid in V('friends_' + enactor.id, [])` to the `if`
  inside the watcher loop. Contacts then become confirmed friendships.
- **A block list.** Keep a `block_<id>` list that `befriend` refuses to cross,
  so a player may bar someone from adding them.
- **Last-seen stamps.** Have `on_disconnect` write `seen_<id>` with
  [`now()`](../reference/softcode.md#fn-now), and have `friends` print it for
  every contact the roster shows as offline.

## Engine gaps

- Presence has no softcode surface (capability audit gap G4). An
  `online_players()` function, plus an idle measure such as `idle_seconds()`,
  would replace the `online` roster and its two boundaries with a direct read.
  Every presence feature in this showcase leans on the same workaround, so the
  [message in a bottle](083_message_in_bottle.md) and the
  [staff dashboard](176_staff_dashboard.md) carry it too.
