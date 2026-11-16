# 222. Org treasury & storage

> Checklist item 222 ([now]): *the clan treasury, positions as powers, lockers warded by `clan_has_power()`*

**What you'll build:** money and storage for the Void Runners from
[221](221_organizations.md). Any member pays into the clan's treasury, only
the Boss and the Treasurer draw from it, and two footlockers in the
clubhouse open by membership and by power: a member opens the common
locker, while the officers' safe opens only for someone the government lets
withdraw.

**Concepts:** the **clan treasury** (`clan deposit`, `clan withdraw`,
`clan deposits`), **powers** as the unit of authority, and **warded
containers** that ask [`clan()`](../reference/softcode.md#fn-clan) and
[`clan_has_power()`](../reference/softcode.md#fn-clan_has_power) at the
moment they are opened.

## How it works

The treasury is the clan's own: a number on the clan, moved by the
`economy` feature. The lockers are ordinary closed containers with an
`on_check` ward. This section answers who may move the money, where it
goes, and how a locker enforces a position it never stores.

### Who may move the money?

Whoever the government says. In a gang, every position holds `deposit`, so
any member may pay in; `withdraw` belongs to the Boss and the Treasurer;
`deposit_list`, the right to see who gave what, to the Boss, the
Lieutenants and the Treasurer. The command checks the power and nothing
else: an administrator outside the crew is refused like any stranger, and
there is no rank arithmetic to write.

Under a government where nobody holds `withdraw` but members vote on it,
the same `clan withdraw` opens a vote instead, and the money moves when the
vote passes ([223](223_elections.md) shows a vote).

### Where does the money go?

From the member's own money into the clan's `treasury`, and back out to
whoever withdraws. Each deposit is also counted against the member
(`donated_gold`), which is what `clan deposits` lists, and what a
plutocracy uses to decide who rules. The money never leaves the economy:
nothing is minted, nothing is burned.

### How does a footlocker enforce a position it never stores?

It asks at the moment of the open. Each locker is a closed
[container](014_basic_container.md) with an `on_check` ward on the
`item:on_open` [action](../reference/softcode.md#event-data-namespace).
The common footlocker blocks anyone for whom `clan(actor)` is not the Void
Runners; the safe blocks anyone without the `withdraw` power. Make Bob the
Treasurer and the safe opens for them, with no edit to the safe.

The lockers are `closed` but not `locked`: the `locked` tag makes `open`
refuse before any action fires, so a ward would never see the attempt. Both
wards start with `atype == 'item:on_open' and target is me`, because a ward
runs for every action this box takes part in, and only its own opening is
its business ([guarding on target](../reference/softcode.md#guard-on-target)).

## Build it

This continues from [221](221_organizations.md): the Void Runners and the
clubhouse exist, with Vala as Boss. Stand in the clubhouse and make the two
lockers:

```text
@teleport The Void Runners Clubhouse
@create crew footlocker
@tag crew footlocker = container
drop crew footlocker
close crew footlocker
@create officers safe
@tag officers safe = container
drop officers safe
close officers safe
```

(Name them without a leading "the": the engine supplies the article when it
prints `You open the crew footlocker`, and a player typing
`open the crew footlocker` is matched either way.)

The common footlocker lets in members:

```text
@set crew footlocker/on_check = '''
if atype == 'item:on_open' and target is me and clan(actor) != 'Void Runners':
    block('The footlocker is sealed to Void Runners members.')
'''
```

The officers' safe lets in whoever may draw on the treasury:

```text
@set officers safe/on_check = '''
if atype == 'item:on_open' and target is me and not clan_has_power(actor, 'withdraw'):
    block('The officers safe opens only for those who keep the treasury.')
'''
```

## Try it

Vala is the Boss and Bob a Member, as [221](221_organizations.md) left
them. Bob pays in; Bob's position allows deposits but not withdrawals:

```text
> clan deposit 40                          (Bob)
  [Void Runners] Bob deposits 40 credits in the treasury.
  You deposit 40 credits; the treasury holds 40.
> clan withdraw 10                         (Bob)
  As Member of Void Runners you cannot withdraw from its treasury.
> clan withdraw 10                         (Vala)
  [Void Runners] Vala withdraws 10 credits from the treasury.
  You withdraw 10 credits; the treasury holds 30.
> clan deposits                            (Vala)
  The treasury of Void Runners holds 30 credits. Given by members:
    Vala                    0 credits        0 experience
    Bob                    40 credits        0 experience
```

The lockers read the same clan. Cass, who never joined, is turned away by
the footlocker; Bob opens it and bounces off the safe:

```text
> open the crew footlocker                 (Cass)
  The footlocker is sealed to Void Runners members.
> open the crew footlocker                 (Bob)
  You open the crew footlocker.
> open the officers safe                   (Bob)
  The officers safe opens only for those who keep the treasury.
```

Make Bob the Treasurer, and both the treasury and the safe change their
minds:

```text
> clan assign Bob = treasurer              (Vala)
  Bob is now Treasurer.
> open the officers safe                   (Bob)
  You open the officers safe.
> clan withdraw 5                          (Bob)
  You withdraw 5 credits; the treasury holds 25.
```

## Going further

- **A tax instead of dues.** `clan tax 10` sends a tenth of every
  experience award a member earns to the clan's own experience, which
  raises its level and the benefits that come with it
  ([Clans](../guides/clans.md#the-treasury-and-the-tax)).
- **A donation room.** `clan donate`, typed by the Boss in a room, makes
  it the clan's donation room (`donate_room`); an `ON_DROP` hook there can
  carry what is dropped into the locker.
- **Clan home.** `clan home` marks the clubhouse, and members whose
  position has `home_privs` reach it with `clan recall`, under the same
  rules as `recall`.
