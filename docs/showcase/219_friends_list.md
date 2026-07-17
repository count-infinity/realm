# 219. Friends list

> Checklist item 219 — [now] — *contacts ledger, ON_CONNECT/ON_DISCONNECT presence notify, privacy opt-out, presence roster workaround*

**What you'll build:** a Social Registry that lets any player keep a
private contact list — `befriend Vala`, `friends`, `unfriend Vala` — and
quietly pings you when one of your contacts logs in or out. Anyone who'd
rather travel dark types `cloak` and stops broadcasting their comings and
goings.

**Concepts:** a per-player **contacts ledger** as attributes
(`friends_<id>`) on a world-zone master; the **ON_CONNECT/ON_DISCONNECT
presence roster** from the [message in a bottle](083_message_in_bottle.md)
(softcode has no "who is online" primitive, so the world keeps its own
list); connect/disconnect **notifications** to the watchers who care; a
**privacy opt-out** flag; and an explicit `members` roster because
softcode can't enumerate another object's attributes.

## How it works

**Presence is the honest problem, again.** REALM softcode still has no
function that answers "who is online" — `who` is a builtin, sessions are
invisible to scripts (audit gap G4). So the Registry does what the
Harbormaster did in [083](083_message_in_bottle.md): it is a **world-zone
master** and keeps its own `online` roster, rebuilt on every
`ON_CONNECT`/`ON_DISCONNECT` it hears from `zone:world` rooms. Same two
boundaries stated there apply here: logins in rooms outside the zone are
missed, and a hard crash can strand a stale id (we re-verify ids resolve
before trusting them). The day the engine grows `online_players()`, the
roster retires.

**Contacts are a one-way ledger.** `befriend <player>` appends that
player's id to *your* `friends_<id>` list. It's deliberately one-way, like
a phone's contacts: you watch whoever you add, whether or not they add you
back. To know who to *notify* when Bob logs in, the Registry asks the
inverse question — "who has Bob in their list?" — by walking a `members`
roster (every id that ever used the system; softcode can't iterate another
object's `friends_*` attributes, so the roster is kept explicitly, exactly
as the [bank](087_bank_accounts.md) keeps its member list).

**Notifications respect the mover's wishes, not the watcher's.** When Bob
connects, the hook notifies each *online watcher* who lists Bob — unless
Bob has set `cloak`. Privacy is the connecting player's call: `cloak` sets
`hide_<id>` and Bob comes and goes silently; `uncloak` clears it. (A
watcher who doesn't want the pings just `unfriend`s.) The verb is `cloak`,
not `hide` — `hide` is the builtin stealth command, and builtins dispatch
before `$`-triggers, so a `$hide` would never fire.

Why is the status verb `friends` and not something shorter? Builtins
dispatch before `$`-triggers — pick a word the engine doesn't already own.
`friends` is clear.

## Build it

A world-zone hub and a second world room to prove presence reaches across
the map:

```text
@dig The Social Hub = hub, out
hub
@zone here = world
@dig The Quiet Corner = corner, hub
corner
@zone here = world
hub
```

The Registry, a world-zone master (as an admin — the master `pemit`s
players wherever they stand, and owner authority is the honest footing for
a public service):

```text
@create the Social Registry
drop the Social Registry
@desc the Social Registry = A directory terminal. BEFRIEND <name> adds a contact; FRIENDS lists them; UNFRIEND <name> drops one; HIDE / UNHIDE toggles whether your logins are announced.
@zone/master the Social Registry = world
```

`befriend` / `unfriend` — one contact list per player, plus a `members`
roster so the connect hook can find watchers later:

```text
@set the Social Registry/cmd_befriend = $befriend *:other = get(trim(arg0)); mine = V('friends_' + enactor.id, []); ok = other is not None and has_tag(other, 'player') and other.id != enactor.id and other.id not in mine; [(set_attr(me, 'friends_' + enactor.id, mine + [o.id]), set_attr(me, 'members', sorted(set(V('members', []) + [enactor.id]))), pemit(enactor, 'Added ' + name(o) + ' to your contacts.')) for g, o in [[ok, other]] if g]; pemit(enactor, 'No such player, or they are already a contact.') if not ok else None
@set the Social Registry/cmd_unfriend = $unfriend *:other = get(trim(arg0)); mine = V('friends_' + enactor.id, []); ok = other is not None and other.id in mine; [(set_attr(me, 'friends_' + enactor.id, [i for i in mine if i != o.id]), pemit(enactor, 'Removed ' + name(o) + ' from your contacts.')) for g, o in [[ok, other]] if g]; pemit(enactor, 'That player is not on your contact list.') if not ok else None
```

`friends` — your list, each tagged online or offline against the roster:

```text
@set the Social Registry/cmd_friends = $friends:mine = V('friends_' + enactor.id, []); pemit(enactor, 'Your contacts:' if mine else 'Your contact list is empty. BEFRIEND <name> to start.'); [pemit(enactor, '  ' + name(get('#' + str(i))) + ' - ' + ('online' if i in V('online', []) else 'offline')) for i in mine if get('#' + str(i))]
```

`cloak` / `uncloak` — the privacy opt-out:

```text
@set the Social Registry/cmd_cloak = $cloak:set_attr(me, 'hide_' + enactor.id, 1); pemit(enactor, 'Cloaked: your logins and logouts are no longer announced.')
@set the Social Registry/cmd_uncloak = $uncloak:del_attr(me, 'hide_' + enactor.id); pemit(enactor, 'Your contacts will again be told when you come and go.')
```

The presence roster and the notifications — the two hooks that make it
live. On connect: refresh the roster (move-to-front, the bottle's idiom),
notify the online watchers who list you (unless you're hidden), then greet
you with a count of your own contacts online:

```text
@set the Social Registry/on_connect = set_attr(me, 'online', [i for i in (V('online') or []) if i != enactor.id] + [enactor.id]); [pemit(get('#' + str(m)), name(enactor) + ' has come online.') for m in V('members', []) if m in V('online', []) and m != enactor.id and enactor.id in V('friends_' + str(m), [])] if not V('hide_' + enactor.id, 0) else None; mine = [f for f in V('friends_' + enactor.id, []) if f in V('online', []) and f != enactor.id]; pemit(enactor, str(len(mine)) + ' of your contacts are online.') if V('friends_' + enactor.id, []) else None
```

On disconnect: drop from the roster, and tell the watchers you're gone
(again, silence if hidden):

```text
@set the Social Registry/on_disconnect = [pemit(get('#' + str(m)), name(enactor) + ' has gone offline.') for m in V('members', []) if m in V('online', []) and m != enactor.id and enactor.id in V('friends_' + str(m), [])] if not V('hide_' + enactor.id, 0) else None; set_attr(me, 'online', [i for i in (V('online') or []) if i != enactor.id])
```

## Try it

Bob adds Vala and Cass, then lists them:

```text
befriend Vala
   -> Added Vala to your contacts.
befriend Cass
   -> Added Cass to your contacts.
friends
   -> Your contacts:
        Vala - offline
        Cass - offline
```

Now Vala logs in. Because Bob lists Vala and Bob is online, Bob hears it —
and Vala, who lists nobody yet, just gets her own count:

```text
(to Bob)  -> Vala has come online.
(to Vala) -> ...        (no ping; she has no contacts watching her here)
```

Vala would rather travel dark:

```text
cloak
   -> Cloaked: your logins and logouts are no longer announced.
```

Now her next login and logout say nothing to Bob. `uncloak` turns the
announcements back on. Drop a contact and the pings for that person stop
at the source:

```text
unfriend Cass
   -> Removed Cass from your contacts.
```

## Going further

- **GMCP contact widget** — swap the connect `pemit` for
  `oob(get('#' + str(m)), 'Comm.Friend', {'name': name(enactor), 'status': 'online'})`
  so a rich client lights a buddy-list panel instead of printing a line.
- **Mutual-only mode** — notify a watcher only if the connector *also*
  lists them: add `and m in V('friends_' + enactor.id, [])`
  to the watcher filter, turning contacts into confirmed friendships.
- **Block list** — a `block_<id>` list that `befriend` refuses to cross,
  so a player can bar someone from adding them.
- **File the gap** — every presence feature in this showcase leans on the
  roster workaround; the real fix is an engine `online_players()` /
  `idle_seconds()` surface (audit gap G4). The roster retires the day it
  ships.
```
