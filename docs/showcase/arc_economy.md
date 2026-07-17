# Arc: Working economy

Five tutorials that grow one marketplace — from coins in a pocket to a
market that moves without you — typed live at a wizard's prompt, no
Python anywhere. Build them in order and they share one room, one
currency, and an escalating set of softcode ideas:

1. **[086 — Multi-denomination currency](086_currency.md)** — physical
   coins over the engine's wallet integer, with automatic change-making.
2. **[063 — Shopkeeper](063_shopkeeper.md)** — the native `shopkeeper`
   behavior plus a softcode restock heartbeat and an `ON_PAYMENT` tip jar.
3. **[087 — Bank accounts](087_bank_accounts.md)** — a ledger in attributes:
   deposits, cross-room transfers, interest ticks, an audit trail.
4. **[089 — Auction house](089_auction_house.md)** — timed listings,
   escrowed bids, sniping protection, automatic settlement.
5. **[092 — Commodity market](092_commodity_market.md)** — prices that
   drift with supply, random news shocks, and trades that move the market.

## The through-line: one integer

REALM ships money in the core: every object has a `credits` balance, read
with `credits(obj)`, moved with `transfer_credits()`, minted with
`adjust_credits()` — and the `credits`/`pay`/`list`/`buy`/`sell` builtins
all speak it. That integer stays the **canonical store of value** for the
whole arc. Coins *represent* it, the bank ledger *re-labels* it, auction
escrow *parks* it, cargo lots trade against it. No tutorial invents a
second currency; conservation is asserted in every test.

Almost everything moves through `transfer_credits()`, which cannot create
or destroy money. The exceptions are deliberate and visible: the `@eval
adjust_credits(...)` seed lines (a wizard priming the pump) and the bank's
interest faucet, which mints its own reserve on each tick so the ledger
never promises money the vault doesn't hold.

## The load-bearing pattern: the admin-owned master

Each tutorial's system lives on **one ordinary object** — the Mint, the
bank, the kiosk, the board — that you `@create` as a wizard and `drop` in
the room. Two engine rules make that object a *system*:

- **Scripts run as their object, with its owner's authority.** You are an
  admin, so your masters may move other players' credits and items. That
  is what lets `deposit 300` pull money *out of* the enactor's wallet —
  something a mortal-owned object can never do (its `transfer_credits`
  from a stranger simply returns False).
- **`$`-command triggers turn attributes into player commands.** Anyone
  in the room can type `deposit 300`; the trigger fires on the master,
  not on the player.

State is plain attributes on the master (`acct_<id>`, `lot_3`, `goods`),
so it persists like any other attribute. These masters are room-local;
for a game-wide command surface, put the master in a `zone:world`-tagged
zone and tag it `zone_master` (the world-zone master workaround — there is
no global Master Room yet).

One caution comes free with the power: an admin-owned `$`-command runs
with wizard authority *at the request of whoever typed it*. Keep the
script's effects to exactly what the command advertises.

## The heartbeat: script_ticker + on_tick + @tr

Interest, restock, settlement, and price drift all use the same cadence:

    @behavior <master> = script_ticker, interval:N
    @set <master>/on_tick = <softcode>

and every tutorial tests its tick instantly with `@tr <master>/on_tick`
(the MUSH `@trigger` — run an attribute's script right now). Where logic
outgrows one attribute, it's split into **function attributes** called
with `eval_attr(me, 'settle', i)` — a subroutine call that runs with the
caller's authority (not Penn's `u()`, which runs as the attribute's
object). For one-shot timers,
`expire()`/`ON_EXPIRE` is the persistent alternative (see 089's "Going
further"); the arc prefers `on_tick` because deadlines here move
(sniping) and recur (interest).

## Softcode habits this arc teaches

- **One line per attribute.** `@set` takes a single line, so scripts are
  `;`-chained statements and comprehensions — same idiom as the main
  tutorial's softcode part.
- **The comprehension binding trick — no longer required (2026-07-17).**
  Scripts once ran with separate local/global namespaces, so a
  comprehension, lambda or generator expression could not see names you
  assigned earlier in the same script. The idiom was to smuggle values in
  through the first `for` clause: `[... for g, a in [[ok, amt]] if g ...]`.
  You will still see that shape throughout this arc and it still works —
  but scripts now share one namespace, so nested scopes read your
  variables directly and `sorted(rows, key=lambda r: r[1])` just works.
  Reach for the smuggle only when it reads better, not because you must.
- **Builtins shadow `$`-commands.** The dispatcher tries built-in
  commands first. That's why the bank's status command is `bank` (not
  `balance`, an alias of the `credits` builtin) and the exchange trades
  with `market buy ...` (bare `buy` belongs to the shopkeeper builtin).
- **Read-modify-write for structured attributes.** Lot dicts and the
  goods table are fetched with `V()` (`get_attr` against `me`), updated,
  and written back with `set_attr` — one owner (the master) mutating its
  own state, no cross-object surgery. Plain counters skip the round trip
  entirely: `incr`/`decr` do the read-add-write in one call.

## Build order and prerequisites

Start anywhere, but the docs assume this once at the top:

    @dig Market Square
    @teleport Market Square

You must be an admin (wizard): the masters inherit their authority from
you. Test money comes from `@eval adjust_credits(me, <n>)`.

## Verification

    cd ~/realm && source venv/bin/activate
    pytest tests/showcase/test_economy_arc.py

24 tests drive every "Build it" line of all five tutorials through the
real dispatcher — change-making and conservation, the live shop with
restock and disposition pricing, bank operations/interest/audit rows,
the full auction lifecycle (escrow, refunds, sniping, settlement,
cancellation), and market trades, drift and news shocks.
