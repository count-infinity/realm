# 022. Coat Check

> Checklist item 22 ([now]): *ticket pattern, paired-object bookkeeping attrs*

**What you'll build:** A brass golem behind a counter. Hand it your coat and
it hands you a numbered claim ticket. Say `claim <number>` with that ticket in
hand, today or tomorrow or after a reboot, and your coat comes back. Wrong
ticket, no coat.

**Concepts:** the **ticket pattern**, where a spawned object serves as a bearer
token, paired with **ledger attributes** on the golem (`held_<n> = #id`) so each
half can verify the other; `give` plus
[`ON_RECEIVE`](../reference/softcode.md#lifecycle-hooks) as the deposit
interface; [`create_obj`](../reference/softcode.md#fn-create_obj) and
[`destroy_obj`](../reference/softcode.md#fn-destroy_obj) for the token's
lifecycle; and the authority rules that let a counter handle other people's
property.

It reuses the [vending machine](002_vending_machine.md)'s spawner vocabulary,
and like the [basic container](014_basic_container.md) it guards every reaction
hook with [`target is me`](../reference/softcode.md#guard-on-target).

## How it works

The finished counter is a golem tagged `npc`, one persistent counter, and a
small ledger of `held_<n>` lines, one per checked coat. A deposit stamps the
coat, writes a ledger line, and mints a numbered ticket into your hand; a
`claim` reads both halves back and, only if they agree, returns the coat and
destroys the ticket. This section answers four questions: how a deposit
arrives, where the bookkeeping lives, how a claim is checked, and why the golem
is allowed to touch a coat that is not its own.

### How does a deposit arrive?

The golem is tagged `npc`, so the stock `give <item> to Coat-Check Golem` works
with no scripting of your own. A give moves the item into the golem and then
fires the recipient's [`ON_RECEIVE`](../reference/softcode.md#lifecycle-hooks)
hook, which like every reaction sees the world *after* the effect (the
[action-phases trio](../design/action-phases.md)): by the time the hook runs,
[`adata('item')`](../reference/softcode.md#event-data-namespace) is already in
the golem's hands. The hook also gets `adata('giver')`, the depositor, which is
the same object as `enactor` here, so the script just uses `enactor`. Because
`ON_RECEIVE` fires on every object in the room, the hook opens with
[`target is me`](../reference/softcode.md#guard-on-target) so a coat handed to
someone else standing nearby never triggers it.

### Where does the bookkeeping live?

The pairing is the heart of the build, because each deposit writes one attribute
onto each of three objects, and all of it is persistent, so a reboot changes
nothing:

- `checked = <n>` on the coat records which hook it hangs on.
- `claim_no = <n>` on the freshly minted ticket is the token the player carries
  away.
- `held_<n> = '#' + coat.id` on the golem is the ledger line binding a hook
  number to a specific coat.

The coat and the ticket each carry half of the pair, and the golem's ledger
records the binding between them, so at claim time each side can verify the
others.

### How is a claim checked?

`$claim <n>` demands that both halves agree: a ticket in the claimant's own hand
whose `claim_no` matches the number, and a `held_<n>` ledger line under that
number. A ticket with no ledger line behind it means the hook is bare; a number
with no ticket in hand means there is nothing to match. Only when both are
present does the golem return the coat, clear the coat's stamp and the ledger
line, and [`destroy_obj`](../reference/softcode.md#fn-destroy_obj) the ticket. A
bearer token has to be destroyed on redemption, or the same coat could be
claimed twice. The double check also has a deliberate consequence: tickets are
ordinary objects, so a player can trade, sell, or lose one, and a ticket that
has changed hands still works, which is a plot hook rather than a flaw.

### Why is the golem allowed to touch your coat?

Softcode runs with the authority of the object it runs on, so the golem can act
only on what it controls. It owns the tickets because it creates them, and it
can relocate the coats because they stand inside it once deposited. Two rules
make the deposit possible:

- [`create_obj`](../reference/softcode.md#fn-create_obj) will not mint an object
  into the inventory of someone the golem does not control, which is exactly a
  stranger at the counter, so the golem mints the ticket into its own hands (a
  `location` of `me`) and then
  [`teleport_obj`](../reference/softcode.md#fn-teleport_obj)s it across. That
  relocation needs control of the ticket, which the golem has because it made
  it, and not of the recipient, so the ticket reaches any customer.
- Stamping `checked` on the coat with
  [`set_attr`](../reference/softcode.md#fn-set_attr) needs control of the coat.
  In these tests the builder owns the golem and the coats are unowned or the
  builder's own, so control follows; to run a public counter where players own
  their own coats, make the golem an admin-owned master, the same
  owner-authority convention as any shared ledger.

If a customer absentmindedly `give`s the ticket back, the receive hook spots the
incoming `claim_ticket` tag and pushes it straight back with instructions,
because a give-based redeem would strand the token with no way to match it to
the ledger.

## Build it

The two scripts are multi-line
[`'''` heredoc blocks](../guides/world-management.md#multi-line-input-heredocs);
everything else is shell.

First the golem and its counter manner. The `npc` tag is what makes `give` land
on it:

```text
@create Coat-Check Golem
@tag Coat-Check Golem = npc
drop Coat-Check Golem
@desc Coat-Check Golem = Brass and patience. A rack of numbered hooks glitters behind it.
```

The deposit hook, whose steps run in order: guard to deposits aimed at the
golem, read the arrival, then branch on whether it carries the `claim_ticket`
tag with [`has_tag`](../reference/softcode.md#fn-has_tag). A stray ticket is
handed right back, while a coat is stamped and ledgered, then answered by a
freshly minted ticket and a [`pemit`](../reference/softcode.md#fn-pemit) line
that names the coat with [`name`](../reference/softcode.md#fn-name):

```text
@set Coat-Check Golem/on_receive = '''
if target is me:  # ON_RECEIVE fires on every object in the room, so guard it
    it = adata('item')
    if has_tag(it, 'claim_ticket'):
        teleport_obj(it, enactor)  # a stray ticket: hand it right back
        pemit(enactor, f"The golem taps the ticket and hands it back: just say claim {get_attr(it, 'claim_no')}.")
    else:
        n = V('counter', 0) + 1
        set_attr(me, 'counter', n)
        set_attr(it, 'checked', n)
        set_attr(me, f'held_{n}', '#' + it.id)
        t = create_obj(f'claim ticket {n}', ['claim_ticket'], me)  # mint in my own hands: create_obj cannot seed into a stranger's inventory
        set_attr(t, 'claim_no', n)
        teleport_obj(t, enactor)  # then hand the ticket over
        pemit(enactor, f'The golem stows your {name(it)} on hook {n} and punches ticket {n}.')
'''
```

The counter stays longhand: [`V`](../reference/softcode.md#fn-v) reads the total
up front as `n = V('counter', 0) + 1`, and `set_attr(me, 'counter', n)` writes it
back only inside the coat branch, rather than a single
[`incr('counter')`](../reference/softcode.md#fn-incr). The number has to
exist before the ticket that carries it, and it must advance only when a coat is
actually checked in, whereas `incr` is for a write that always happens.

The redeem command returns the coat only when both halves agree. It
[`trim`](../reference/softcode.md#fn-trim)s the argument to a number, reads the
ticket out of the claimant's own inventory with
[`contents`](../reference/softcode.md#fn-contents) and checks its
[`get_attr`](../reference/softcode.md#fn-get_attr) `claim_no`, resolves the coat
out of the ledger with [`get`](../reference/softcode.md#fn-get) (the stored
`'#' + id` is an exact address), and on success clears both stamps with
[`del_attr`](../reference/softcode.md#fn-del_attr):

```text
@set Coat-Check Golem/cmd_claim = '''
$claim *:
num = trim(arg0)
tick = [o for o in contents(enactor) if has_tag(o, 'claim_ticket') and str(get_attr(o, 'claim_no')) == num]
held = V('held_' + num)
it = get(held) if held else None
if tick and it:
    teleport_obj(it, enactor)
    del_attr(it, 'checked')
    del_attr(me, 'held_' + num)
    destroy_obj(tick[0])  # the token must die on redemption, or one coat could be claimed twice
    pemit(enactor, f'The golem lifts your {name(it)} off hook {num} and retires the ticket.')
elif not tick:
    pemit(enactor, 'The golem shows you two empty brass palms: no matching ticket in your hand.')
else:
    pemit(enactor, f'The golem stares at hook {num}, which is bare. Curious.')
'''
```

Something to test with:

```text
@create wool greatcoat
```

## Try it

Hand over the coat and the golem answers with a numbered ticket:

```text
> give wool greatcoat to Coat-Check Golem
The golem stows your wool greatcoat on hook 1 and punches ticket 1.
```

You are now holding `claim ticket 1` (`@examine` it: a single `claim_no`
attribute, because the token is data) while the golem holds the coat. Try to
cheat with a number you cannot back up, then claim for real:

```text
> claim 4
The golem shows you two empty brass palms: no matching ticket in your hand.

> claim 1
The golem lifts your wool greatcoat off hook 1 and retires the ticket.
```

The coat is back in your inventory and the ticket is gone from the world. A
second deposit punches ticket 2, because the counter never reuses a number, so
yesterday's stubs stay worthless. And if you absentmindedly
`give claim ticket 2 to Coat-Check Golem`, it taps the number and hands the
ticket straight back.

## Going further

- **Checking fee:** the golem already has hands, so an `on_payment` gate before
  the deposit (the [vending machine](002_vending_machine.md) credit pattern)
  can make hook space cost five credits.
- **Storage teleport:** `teleport_obj(it, get('the cloakroom'))` on deposit
  moves coats to a real back room instead of the golem's pockets. The
  `held_<n>` ledger does not care where the coat sleeps, which is the point of
  storing `#id`s rather than locations.
- **Lost-ticket desk:** an owner-only `$override <n>` that reads the ledger and
  returns the item without a token, because every ticket system eventually
  meets a customer who lost theirs.
- **Expiring stubs:** `expire(ticket, 604800)` on mint plus a weekly sweep of
  unclaimed hooks into the [trash bin](019_trash_incinerator.md), since a coat
  check is not long-term storage.
