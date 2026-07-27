# 184. New-player onboarding

> Checklist item 184 ([now]): *world-master ON_CONNECT, first-login flag, starter kit via create_obj, mentor ping*

**What you'll build:** a `Greeter` that welcomes each new character the first
time they connect, hands them a starter kit (a datapad and 100 credits)
straight into their inventory, sends a quiet ping to every mentor on duty, and
never repeats itself on later logins.

**Concepts:** a **world-zone master** witnessing every login through
[`ON_CONNECT`](../reference/softcode.md#lifecycle-hooks) (the roster idiom from
[083](083_message_in_bottle.md)), a **first-login flag** so the kit is granted
once, [`create_obj()`](../reference/softcode.md#fn-create_obj) plus
[`adjust_credits()`](../reference/softcode.md#fn-adjust_credits) into a player's
inventory under admin authority, and a **mentor fan-out** via
[`search_world()`](../reference/softcode.md#fn-search_world) and
[`pemit()`](../reference/softcode.md#fn-pemit).

## How it works

The finished machine is one object, the Greeter, carrying a single
`on_connect` script. Every time a character logs in anywhere in the world zone,
that script runs; the first time for a given character it grants a kit and
greets them, and on every later login it does nothing. This section answers
three questions: how one object hears logins from across the whole zone, how it
tells a brand-new arrival from a reconnecting veteran, and why it is allowed to
put money and objects into someone else's inventory.

### How one object hears every login

The Greeter is the master of the `zone:world` tag, so it witnesses lifecycle
events in every room that carries that tag. Zone masters observe events in
their member rooms just as bystanders standing in the room do, which is the
same plumbing behind the [staff dashboard](176_staff_dashboard.md) roster and
the message-in-a-bottle Harbormaster. A login fires `event:connect` in the
room where the character appears, and because that room is tagged `zone:world`,
the event reaches the Greeter's `on_connect`. Inside the hook the connecting
character is bound to `enactor`. For the propagation model itself, see
[the event system](../architecture/events.md) and the guided
[event bus tour](245_event_bus_tour.md).

This is a **global witness**, an object deliberately watching everyone who
connects, so it takes no `if target is me:` guard. The
[`target` guard](../reference/softcode.md#guard-on-target) is for a hook that
should react only to its own business; a zone master watching the whole zone is
the standing exception.

### How it tells a newcomer from a returning veteran

The kit must not re-drop on every reconnect, so the hook keys off
[`get_attr(enactor, 'oriented')`](../reference/softcode.md#fn-get_attr): an
absent value means the character is new, and the first thing the hook does is
stamp it with [`now()`](../reference/softcode.md#fn-now). Every later connect
finds the stamp already set and falls through without acting. Because the flag
is a persistent attribute, a character who was oriented before a reboot stays
oriented after it, so a returning veteran is never re-onboarded.

### Why it may write another player's inventory

Crediting a player and creating objects *in another player's inventory* means
mutating that player, which is admin territory. The Greeter is admin-owned, so
[`adjust_credits(enactor, 100)`](../reference/softcode.md#fn-adjust_credits) and
`create_obj('a welcome datapad', ['thing'], enactor)` both act with its owner's
authority, the staff-tool boundary from the
[permission tour](183_permission_tiers.md). The greeting itself is a plain
[`pemit`](../reference/softcode.md#fn-pemit), since speaking to someone needs no
authority.

Mentors are identified by a tag: any character tagged `mentor` is on the
welcome wagon, and `search_world(tag='mentor')` (minus the newcomer themselves)
gets the ping. Tag and untag mentors live and the roster stays current.

## Build it

First an orientation bay on the world zone, with the Greeter dropped inside it
and crowned master of the zone:

```text
@dig The Orientation Bay = obay, out
obay
@zone here = world
@create Greeter
drop Greeter
@desc Greeter = A cheerful welcome-bot bolted by the airlock.
@zone/master Greeter = world
```

The whole onboarding is one first-login hook. It stamps the `oriented` flag,
grants credits and a datapad into the newcomer's hands, greets them, then pings
every mentor except the newcomer:

```text
@set Greeter/on_connect = '''
# 'oriented' is the first-login stamp: set it once, and every later connect
# finds it already set and falls through, so the kit is a one-time gift.
if not get_attr(enactor, 'oriented'):
    set_attr(enactor, 'oriented', now())
    adjust_credits(enactor, 100)
    create_obj('a welcome datapad', ['thing'], enactor)
    pemit(enactor, 'Welcome aboard, ' + name(enactor) + '! Your kit holds a datapad and 100 credits. Type HELP anytime.')
    mentors = [m for m in search_world(tag='mentor') if m is not enactor]
    for m in mentors:
        pemit(m, ansi('c', '[mentor] ') + 'New arrival: ' + name(enactor) + ', say hello.')
'''
```

Finally, deputize a mentor by tag:

```text
@tag Mira = mentor
```

## Try it

A new character connects in a world room for the first time:

```text
(Newbie connects)
   (Newbie) Welcome aboard, Newbie! Your kit holds a datapad and 100 credits. Type HELP anytime.
   (Mira)   |C[mentor]|n New arrival: Newbie, say hello.
```

Newbie now holds *a welcome datapad*, has 100 credits, and carries the
`oriented` stamp. Reconnecting changes nothing, with no second greeting, no
second datapad, and no doubled credits, because the flag is already set. A
character who was already oriented (a returning veteran) triggers the hook and
silently falls through.

## Going further

- **A richer kit** loops a prototype list and `create_obj`s each item: a
  datapad, a comm badge, a map. Or `@clone` a pre-built "starter crate" into
  their hands.
- **Route to a tutorial** with
  [`teleport_obj(enactor, 'The Tutorial Deck')`](../reference/softcode.md#fn-teleport_obj)
  on first login, or drop them into a private
  [instance](044_instanced_room.md) so first steps are undisturbed.
- **Pair, do not just ping** by auto-assigning a mentor: write
  `set_attr(enactor, 'mentor', mentors[0].id)` and let a `$mentor` verb connect
  them, which is the [mentor program](226_mentor_program.md).
- **Compose with approval** by tagging the newcomer `unapproved` here so the
  [approval gate](179_approval_queue.md) holds them until a staffer clears them;
  onboarding and approval are two halves of arrival.
- **Login streaks** use the same `ON_CONNECT` and date-math pattern to reward
  *returning* players, which is [login streak rewards](229_login_streaks.md);
  onboarding is the day-one case of it.
