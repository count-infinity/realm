# 179. Character approval queue

> Checklist item 179 ([now]): *unapproved tags, gating wards, $approve + pemit*

**What you'll build:** an arrivals gate. New characters wait in the Arrivals
Lounge, unable to reach the Concourse until a staffer clears them: `pending`
lists who is waiting, `approve <name>` opens the door and welcomes them, and
`reject <name> = <reason>` sends the note back while keeping them pending.

**Concepts:** workflow states as tags (`unapproved` becomes `approved`), a
tag-gated exit lock as the gate, a world-zone master desk with staff-gated
verbs, [`search_world()`](../reference/softcode.md#fn-search_world) as the
queue query, and [`pemit()`](../reference/softcode.md#fn-pemit) notification on
every decision, all built with admin authority because approval mutates other
players' tags.

## How it works

The finished workflow is small: one tag on the character decides whether the
start room lets them out, and one admin-owned desk gives staff three verbs to
change that tag. This section answers three questions in turn: what holds a
newcomer in place, why the desk must run with staff authority, and how the
queue stays current without a list to maintain.

### What holds an unapproved character in place?

REALM ships character creation but has no approval gate, because a gate is a
policy your game chooses rather than an engine feature. The whole workflow is
one tag on the character and one lock on the way out. New characters arrive
tagged `unapproved` (your chargen or [onboarding](184_onboarding.md) step
stamps it, or a world-master `ON_CONNECT` does), and this tutorial builds the
gate and the staff tools around that tag.

The gate is the start room's exit. The exit from the Arrivals Lounge to the
Concourse carries a `basic` lock, `not caller.has_tag('unapproved')`. The
engine's movement gate refuses anyone still tagged, the same native
enforcement the [jail](177_jail_system.md) cell wall uses, so an unapproved
character is held without any per-tick babysitting.

### Why does the desk run with staff authority?

Clearing a character means removing a tag from another player, which only an
ADMIN (or that player's owner) may do. So the Approvals Desk is admin-owned,
and its scripts act with staff authority, the honest boundary the
[permission tour](183_permission_tiers.md) draws. `approve` swaps `unapproved`
for `approved` and pemits the newcomer, while `reject` leaves them pending and
pemits the reason. Notification is best-effort: if the character is offline the
tag change still persists, so the gate simply opens the next time they walk it.

The desk is also crowned world master, which means an object in a
`zone:world`-tagged room, since there is no Master Room yet. That is what lets
`pending`, `approve`, and `reject` answer from anywhere in the world rather
than only in the room the desk sits in.

### How does the queue stay current?

The queue is a query, not a stored list. `pending` is just
[`search_world`](../reference/softcode.md#fn-search_world)`(tag='unapproved')`,
so there is nothing to keep in sync: a character shows up in the queue exactly
as long as they carry the tag, and drops out the instant `approve` removes it.

## Build it

Start with an arrivals room on the world zone and a locked door onward. The
lock is a `basic` lock whose expression reads
[`has_tag`](../reference/softcode.md#fn-has_tag) on the mover, so the engine's
movement gate turns anyone still `unapproved` back at the exit.

```text
@dig The Arrivals Lounge = arrivals, out
arrivals
@zone here = world
@dig The Concourse = concourse, back
@lock concourse = not caller.has_tag('unapproved')
```

Now the desk itself, admin-owned so its scripts carry staff authority, and
crowned world master so its verbs answer from anywhere in the world:

```text
@create Approvals Desk
drop Approvals Desk
@desc Approvals Desk = A clerk's window for new citizens. PENDING, APPROVE <name>, REJECT <name> = <reason>.
@zone/master Approvals Desk = world
```

The first verb is `pending`, the queue readout. Name it `pending` rather than
`queue`, because `queue` is a builtin and builtins win the dispatch. It gates
on staff, then reads the queue with
[`search_world`](../reference/softcode.md#fn-search_world) and pemits one line
per waiting character, showing a short id so two same-named arrivals stay
distinct:

```text
@set Approvals Desk/cmd_pending = '''
$pending:
if not has_tag(enactor, 'admin'):
    pemit(enactor, 'Only staff may review arrivals.')
else:
    q = search_world(tag='unapproved')
    if not q:
        pemit(enactor, 'The approval queue is empty.')
    else:
        for p in q:
            pemit(enactor, f'- {name(p)} (#{str(p.id)[:8]})')
'''
```

The second verb is `approve <name>`. It resolves the name with
[`get`](../reference/softcode.md#fn-get), refuses a non-staff caller, refuses
anyone who is not actually waiting, and otherwise swaps the tag with
[`remove_tag`](../reference/softcode.md#fn-remove_tag) and
[`add_tag`](../reference/softcode.md#fn-add_tag), welcomes the newcomer, records
the decision, and confirms to the staffer:

```text
@set Approvals Desk/cmd_approve = '''
$approve *:
name_in = trim(arg0)
p = get(name_in)
if not has_tag(enactor, 'admin'):
    pemit(enactor, 'Only staff may clear arrivals.')
elif not (p and has_tag(p, 'unapproved')):
    pemit(enactor, f'{name_in} is not awaiting approval.')
else:
    remove_tag(p, 'unapproved')
    add_tag(p, 'approved')
    pemit(p, 'Your character has been approved. Welcome aboard, the concourse is open to you.')
    # rebuild the log and keep only the last 50 decisions
    set_attr(me, 'log', ((V('log') or []) + [f'{name(enactor)} approved {name(p)}'])[-50:])
    pemit(enactor, f'Approved {name(p)}.')
'''
```

The log line is the standard capped-history idiom:
[`V`](../reference/softcode.md#fn-v) reads the desk's own `log` attr (defaulting
to an empty list), the new entry is appended, `[-50:]` keeps only the most
recent fifty, and [`set_attr`](../reference/softcode.md#fn-set_attr) writes the
rebuilt list back. Throughout, [`name`](../reference/softcode.md#fn-name) renders
a friendly label and [`trim`](../reference/softcode.md#fn-trim) cleans the
whitespace off the matched `*` argument before it is used as a lookup key.

The third verb is `reject <name> = <reason>`. It runs the same staff and
waiting checks, then pemits the reason to the character and records the bounce.
The reason is player-typed, so pass it through
[`escape`](../reference/softcode.md#fn-escape) before it reaches the newcomer,
which neutralizes any color markup they tried to smuggle in. Rejection leaves
the `unapproved` tag in place, so the gate stays shut:

```text
@set Approvals Desk/cmd_reject = '''
$reject * = *:
name_in = trim(arg0)
p = get(name_in)
if not has_tag(enactor, 'admin'):
    pemit(enactor, 'Only staff may clear arrivals.')
elif not (p and has_tag(p, 'unapproved')):
    pemit(enactor, f'{name_in} is not awaiting approval.')
else:
    note = escape(trim(arg1))
    pemit(p, f'Your character needs work before approval: {note}')
    set_attr(me, 'log', ((V('log') or []) + [f'{name(enactor)} bounced {name(p)}: {trim(arg1)}'])[-50:])
    pemit(enactor, f'Sent {name(p)} back with notes.')
'''
```

## Try it

A newcomer arrives tagged `unapproved` (here we set it by hand to stand in for
the chargen step) and finds the door shut:

```text
@tag Newbie = unapproved
(Newbie) concourse
   -> You can't go concourse — it's locked.
```

A staffer reviews the queue and clears them. The short id after the name will
differ from the one shown here, since it is the head of the character's raw id:

```text
pending
   -> - Newbie (#a1b2c3d4)
approve Newbie
   -> Approved Newbie.
   (Newbie) Your character has been approved. Welcome aboard, the concourse is open to you.

(Newbie) concourse
   -> The Concourse
```

Rejection notifies the character but holds the gate:

```text
reject Rowdy = name violates the setting; pick another
   -> Sent Rowdy back with notes.
   (Rowdy) Your character needs work before approval: name violates the setting; pick another
```

A non-staff arrival who tries `approve Newbie` is refused with `Only staff may
clear arrivals.`, so newcomers have no way to wave themselves through:

```text
(Newbie) approve Newbie
   -> Only staff may clear arrivals.
```

## Going further

- **Auto-tag on arrival.** A world-master `ON_CONNECT` that tags any character
  lacking an `approved` attr as `unapproved` makes the gate automatic. Compose
  it with [onboarding](184_onboarding.md), which already fires on first connect.
- **Reasons on file.** Stash the reject note on the character with
  `set_attr(p, 'review_note', ...)` so it shows at their next login rather than
  only once.
- **A holding channel.** Give the Arrivals Lounge a `$page staff` verb that
  pemits the on-duty admins (see the [watchlist](186_watchlist.md) staff
  fan-out idiom) so approvals happen live.
- **Multi-step review.** Add an `under_review` tag between `unapproved` and
  `approved` for a two-pass workflow. The states are just tags, so add as many
  as your process needs.
