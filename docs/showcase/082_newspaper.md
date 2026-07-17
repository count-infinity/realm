# 082. Newspaper

> Checklist item 82 — [now] — *submission queue attrs, ticker publish, ON_PAYMENT kiosk vending, desc_extras pages*

**What you'll build:** The Gazette: anyone files a story with
`submit <text>`, the press thunders on a timer and rolls the queue
into a numbered issue, a paperboy hollers the headline count across
the market — and a kiosk sells physical copies (`pay 5 to kiosk`)
whose pages are readable with a plain `look`.

**Concepts:** a submission **queue attribute** compiled into
immutable per-issue attributes (`issue_<n>`), `script_ticker` as the
press schedule, the **ON_PAYMENT + ledger idiom** for coin-op
vending, `create_obj` + `desc_extras` to print objects with pages,
and the mint-then-hand-over pattern for putting goods in a buyer's
hands.

## How it works

**The bureau is a pipeline of attributes.** `submit` appends
`escape(text) + ' --' + byline` to a `queue` list. The press —
`on_tick` on a slow `script_ticker` — does nothing while the queue is
empty; when there's copy, it increments `issue`, freezes the queue
into `issue_<n>` (a new attribute per edition — back-numbers stay
readable forever), blanks the queue, and has a paperboy `remit()`
every market-zone room. Periodicity falls out of the interval: the
paper publishes when there's news, checked on the press's schedule.

**The kiosk sells without a `buy` verb.** `pay 5 to kiosk` is the
builtin economy command; it moves the credits and fires the kiosk's
`ON_PAYMENT`. Payment hooks carry no amount, so the kiosk uses the
**ledger idiom** ([slot machine](001_slot_machine.md)): `paid =
credits(me) - ledger` reconstructs the sum, wrong amounts and
too-early customers get refunded by `transfer_credits`, and the
ledger is re-stamped to the live balance either way.

**A copy is a printed object.** The kiosk mints the paper *in its own
hands* (`create_obj(..., location=me)` — conjuring directly into a
stranger's pockets is refused by design) and `teleport_obj`s it over,
the [coat check](022_coat_check.md) hand-over. Pages are
`desc_extras` rows — a masthead line first, then one `['', line]` per
story, the [camera](008_camera.md)'s photograph trick — so the
builtin `look` *is* the reading interface: no verbs to teach, and the
object is a real newspaper you can drop on a bar or give to a friend.
(The whole sheet lives in `desc_extras`, masthead included, because
softcode writes db attributes — it cannot set the engine's
`description` slot, which only `@desc` touches. `desc_extras` is the
softcode-reachable description surface.) Each copy snapshots the issue
at purchase; the bureau's `issue_<n>` attr is the archive of record.

## Build it

The office and the market, zoned together:

```text
@dig The Gazette Office = office, out
office
@zone here = market
@dig Market Square = square, office
square
@zone here = market
office
```

The bureau — desk, queue, and press:

```text
@create Gazette Bureau
drop Gazette Bureau
@desc Gazette Bureau = Ink, brass, and a thundering press. SUBMIT <text> files a story for the next issue.
@zone/master Gazette Bureau = market
@set Gazette Bureau/cmd_submit = $submit *: set_attr(me, 'queue', (get_attr(me, 'queue') or []) + [escape(arg0) + ' --' + name(enactor)]); pemit(enactor, 'The desk editor spikes your copy for the next issue.')
@set Gazette Bureau/publish = q = get_attr(me, 'queue') or []; n = get_attr(me, 'issue', 0) + 1; (set_attr(me, 'issue', n), set_attr(me, 'issue_' + str(n), q), set_attr(me, 'queue', []), [remit(r, 'A paperboy hollers: GAZETTE No. ' + str(n) + '! ' + str(len(q)) + ' stories! Fresh at the kiosk!') for r in zone_rooms('market')]) if q else None
@set Gazette Bureau/on_tick = eval_attr(me, 'publish')
@behavior Gazette Bureau = script_ticker, interval:60
```

(The bureau is the market's zone master, so `submit` works from
anywhere on the zone — stringers file from the square.)

The kiosk, in the square:

```text
square
@create news kiosk
drop news kiosk
@desc news kiosk = A tin shed papered with old front pages. PAY 5 TO KIOSK for the latest Gazette.
@set news kiosk/price = 5
@set news kiosk/ledger = 0
@set news kiosk/on_payment = b = get('Gazette Bureau'); paid = credits(me) - get_attr(me, 'ledger', 0); cost = get_attr(me, 'price', 5); n = get_attr(b, 'issue', 0); ok = bool(n) and paid >= cost; refund = paid - cost if ok else paid; (transfer_credits(me, enactor, refund) if refund > 0 else None); set_attr(me, 'ledger', credits(me)); (pemit(enactor, 'The vendor shrugs: nothing on the stand until the press runs. Coins returned.') if not n else (pemit(enactor, 'The vendor taps the price card: ' + str(cost) + ' credits. Coins returned.') if not ok else None)); [(set_attr(p, 'desc_extras', [['', 'Cheap ink on cheaper paper. The masthead reads THE GAZETTE, No. ' + str(n) + '.']] + [['', row] for row in (get_attr(b, 'issue_' + str(n)) or [])]), teleport_obj(p, enactor), pemit(enactor, 'The vendor folds a Gazette No. ' + str(n) + ' into your hands. LOOK gazette to read it.')) for p in ([create_obj('the Gazette No. ' + str(n), ['thing', 'paper'], me)] if ok else []) if p]
```

## Try it

File copy, then let the press run (or wait out the minute):

```text
submit Dock fees to double, harbormaster blames pirates.
   -> The desk editor spikes your copy for the next issue.
(Kess, in the square) submit LOST: one glass eye, sentimental value.
```

On the next press tick, everyone on the market zone hears
`A paperboy hollers: GAZETTE No. 1! 2 stories! ...` — and the queue
is spiked clean. At the kiosk:

```text
pay 5 to news kiosk
   -> You pay news kiosk 5 credits.
   -> The vendor folds a Gazette No. 1 into your hands. LOOK gazette to read it.
look gazette
   -> Cheap ink on cheaper paper. The masthead reads THE GAZETTE, No. 1.
   -> Dock fees to double, harbormaster blames pirates. --Bilda
   -> LOST: one glass eye, sentimental value. --Kess
```

Underpay and the vendor taps the price card, coins refunded; pay
before issue one exists and you get the shrug, coins refunded. New
submissions pile into the *next* edition — buy after the second press
run and the masthead reads No. 2, while your old copy still reads
No. 1: printed paper doesn't update, which is the charm.

## Going further

- **Back-numbers** — `pay` is one price for "latest"; a
  `$order <n>` verb reading `issue_<n>` sells the archive (charge
  double — collectors pay).
- **An editor** — route `submit` into a `pending` list and give the
  owner a `$spike <n>` / `$run <n>` pair: editorial control is one
  list-move.
- **Subscriptions** — a `subscribers` list on the bureau; the
  publish script mints and `teleport_obj`s a copy per subscriber —
  mind that each copy is a real object; cap your print run.
- **Headlines on the PA** — the paperboy is a `remit` loop; feed the
  first story's first sentence to the
  [station PA](078_pa_system.md) style chime for a wire-service
  feel.
