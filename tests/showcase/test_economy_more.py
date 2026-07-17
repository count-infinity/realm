"""
Showcase "Economy & Commerce" remainder (items 88, 90, 91, 93, 94, 95,
96, 97) — every tutorial transcript driven end-to-end through the
dispatcher, exactly as the docs have the builder type it.

Docs: docs/showcase/088_player_shops.md, 090_pawn_shop.md,
091_lottery.md, 093_housing_rent.md, 094_job_board.md,
095_durability_repair.md, 096_secure_trade.md, 097_barter_npc.md.

The BUILD_* lists below are verbatim the "Build it" command lines of
each tutorial. If this file is green, the typed lines work.
"""

from __future__ import annotations

import time

import pytest

import realm.behaviors  # noqa: F401 — registers script_ticker etc.
from realm.core.economy import get_credits
from realm.core.events import reap_expired
from realm.testing import Simulator

# --- 088. Player-run shop stalls -------------------------------------------------

BUILD_STALL = [
    "@dig Stall Row",
    "@teleport Stall Row",
    "@create stall three",
    "drop stall three",
    "@set stall three/rent = 20",
    "@set stall three/period = 300",
    "@set stall three/cmd_rent = $rent stall:ok = not get_attr(me, 'renter') and transfer_credits(enactor, me, get_attr(me, 'rent', 20)); [(set_attr(me, 'renter', enactor.id), set_attr(me, 'renter_name', name(enactor)), set_attr(me, 'paid_until', now() + get_attr(me, 'period', 300)), set_attr(me, 'earnings', 0), remit(here, name(enactor) + ' rents stall three and shakes out the awning.')) for g in [ok] if g]; pemit(enactor, 'Stall three is yours. Stock it, price it, collect your takings.' if ok else 'The stall is already let, or you cannot cover the rent.')",
    "@set stall three/cmd_stock = $stall stock *:itm = [o for o in contents(enactor) if name(o).lower() == arg0.strip().lower()]; ok = enactor.id == get_attr(me, 'renter') and bool(itm); [(move_to(o, me), set_attr(o, 'stall_price', max(1, get_attr(o, 'value', 1))), pemit(enactor, name(o) + ' goes on the shelf at ' + str(get_attr(o, 'stall_price', 1)) + ' credits.')) for g, lst in [[ok, itm]] if g for o in [lst[0]]]; pemit(enactor, 'Only the renter stocks this stall, and only from their own pack.') if not ok else None",
    "@set stall three/cmd_price = $stall price * = *:itm = [o for o in contents(me) if name(o).lower() == arg0.strip().lower()]; ok = enactor.id == get_attr(me, 'renter') and bool(itm) and int(arg1) > 0; [(set_attr(o, 'stall_price', int(arg1)), remit(here, get_attr(me, 'renter_name', 'The stallholder') + ' chalks a new price: ' + name(o) + ' at ' + str(int(arg1)) + ' credits.')) for g, lst in [[ok, itm]] if g for o in [lst[0]]]; pemit(enactor, 'Only the renter sets prices here.' if enactor.id != get_attr(me, 'renter') else 'No such item on the shelf, or a bad price.') if not ok else None",
    "@set stall three/cmd_shelf = $stall:pemit(enactor, 'stall three, run by ' + get_attr(me, 'renter_name', 'nobody (rent stall to claim it)') + ':'); [pemit(enactor, '  ' + name(o) + ' - ' + str(get_attr(o, 'stall_price', 0)) + ' credits') for o in contents(me) if has_attr(o, 'stall_price')]",
    "@set stall three/cmd_buy = $stall buy *:itm = [o for o in contents(me) if has_attr(o, 'stall_price') and name(o).lower() == arg0.strip().lower()]; price = get_attr(itm[0], 'stall_price', 0) if itm else 0; ok = bool(itm) and enactor.id != get_attr(me, 'renter') and transfer_credits(enactor, me, price); [(del_attr(o, 'stall_price'), teleport_obj(o, enactor), set_attr(me, 'earnings', get_attr(me, 'earnings', 0) + p), remit(here, name(enactor) + ' buys ' + name(o) + ' for ' + str(p) + ' credits.'), pemit(get('#' + get_attr(me, 'renter')), 'Your stall sells ' + name(o) + ' for ' + str(p) + ' credits.')) for g, p, lst in [[ok, price, itm]] if g for o in [lst[0]]]; pemit(enactor, 'Not on the shelf, or you cannot cover it.') if not ok else None",
    "@set stall three/cmd_collect = $stall collect:e = get_attr(me, 'earnings', 0); ok = enactor.id == get_attr(me, 'renter') and e > 0 and transfer_credits(me, enactor, e); [(set_attr(me, 'earnings', 0), pemit(enactor, 'You pocket ' + str(k) + ' credits in takings.')) for g, k in [[ok, e]] if g]; pemit(enactor, 'No takings to collect, or this is not your stall.') if not ok else None",
    "@behavior stall three = script_ticker, interval:60",
    "@set stall three/on_tick = r = get_attr(me, 'renter'); e = get_attr(me, 'earnings', 0); rent = get_attr(me, 'rent', 20); due = bool(r) and now() >= get_attr(me, 'paid_until', 0); (set_attr(me, 'earnings', e - rent), set_attr(me, 'paid_until', get_attr(me, 'paid_until', 0) + get_attr(me, 'period', 300)), pemit(get('#' + r), 'The market takes ' + str(rent) + ' credits rent from your stall takings.')) if due and e >= rent else None; ([(teleport_obj(o, get('#' + get_attr(me, 'renter'))), del_attr(o, 'stall_price')) for o in contents(me) if has_attr(o, 'stall_price')], transfer_credits(me, get('#' + r), e) if e > 0 else None, pemit(get('#' + r), 'Stall three is repossessed for unpaid rent; your goods and takings are returned.'), del_attr(me, 'renter'), del_attr(me, 'renter_name'), set_attr(me, 'earnings', 0), remit(here, 'The market warden strips stall three: TO LET.')) if due and e < rent else None",
]

# --- 090. Pawn shop ---------------------------------------------------------------

BUILD_PAWN = [
    "@dig Yaros Den",
    "@teleport Yaros Den",
    "@create the Pawn Counter",
    "drop the Pawn Counter",
    "@set the Pawn Counter/rate = 60",
    "@set the Pawn Counter/window = 300",
    "@set the Pawn Counter/fallback = 5",
    "@eval adjust_credits(get('the Pawn Counter'), 1000)",
    "@set the Pawn Counter/tag_expire = shop = get('the Pawn Counter'); iid = get_attr(me, 'item'); row = get_attr(shop, 'pledge_' + iid); (del_attr(shop, 'pledge_' + iid), add_tag(get('#' + iid), 'forfeit'), remit(loc(shop), 'Yaro shrugs and moves ' + name(get('#' + iid)) + ' to the sale rack.')) if row else None",
    "@set the Pawn Counter/cmd_pawn = $pawn *:itm = [o for o in contents(enactor) if name(o).lower() == arg0.strip().lower()]; val = (get_attr(itm[0], 'value', 0) or get_attr(me, 'fallback', 5)) if itm else 0; loan = max(1, val * get_attr(me, 'rate', 60) // 100); ok = bool(itm) and transfer_credits(me, enactor, loan); [(move_to(o, me), set_attr(me, 'pledge_' + o.id, {'owner': enactor.id, 'owner_name': name(enactor), 'loan': l, 'due': now() + get_attr(me, 'window', 300)}), set_attr(t, 'item', o.id), set_attr(t, 'on_expire', get_attr(me, 'tag_expire')), expire(t, get_attr(me, 'window', 300)), pemit(enactor, 'Yaro counts out ' + str(l) + ' credits against your ' + name(o) + '. Redeem it for ' + str(l + max(1, l // 10)) + ' within ' + str(get_attr(me, 'window', 300)) + ' seconds.')) for g, l, lst in [[ok, loan, itm]] if g for o in [lst[0]] for t in [create_obj('a pawn tag (' + name(o) + ')', tags=['thing', 'pawn_tag'], location=me)]]; pemit(enactor, 'You are not carrying that, or the counter cannot cover the loan.') if not ok else None",
    "@set the Pawn Counter/cmd_redeem = $redeem *:itm = [o for o in contents(me) if name(o).lower() == arg0.strip().lower() and has_attr(me, 'pledge_' + o.id)]; row = get_attr(me, 'pledge_' + itm[0].id) if itm else None; cost = row['loan'] + max(1, row['loan'] // 10) if row else 0; ok = bool(row) and row['owner'] == enactor.id and now() <= row['due'] and transfer_credits(enactor, me, cost); [(teleport_obj(o, enactor), del_attr(me, 'pledge_' + o.id), [destroy_obj(t) for t in contents(me) if has_tag(t, 'pawn_tag') and get_attr(t, 'item') == o.id], pemit(enactor, 'You redeem your ' + name(o) + ' for ' + str(c) + ' credits.')) for g, o, c in [[ok, itm[0] if itm else None, cost]] if g]; pemit(enactor, 'No such pledge of yours, the window has closed, or you cannot cover it.') if not ok else None",
    "@set the Pawn Counter/cmd_rack = $rack:pemit(enactor, 'On the sale rack:'); [pemit(enactor, '  ' + name(o) + ' - ' + str(max(1, get_attr(o, 'value', 0) or get_attr(me, 'fallback', 5))) + ' credits') for o in contents(me) if has_tag(o, 'forfeit')]",
    "@set the Pawn Counter/cmd_buyrack = $rack buy *:itm = [o for o in contents(me) if has_tag(o, 'forfeit') and name(o).lower() == arg0.strip().lower()]; price = max(1, get_attr(itm[0], 'value', 0) or get_attr(me, 'fallback', 5)) if itm else 0; ok = bool(itm) and transfer_credits(enactor, me, price); [(remove_tag(o, 'forfeit'), teleport_obj(o, enactor), pemit(enactor, 'Yours for ' + str(p) + ' credits. No refunds.')) for g, p, lst in [[ok, price, itm]] if g for o in [lst[0]]]; pemit(enactor, 'Not on the rack, or you cannot cover it.') if not ok else None",
]

# --- 091. Lottery -----------------------------------------------------------------

BUILD_LOTTO = [
    "@dig The Lucky Star Lounge",
    "@teleport The Lucky Star Lounge",
    "@create the lottery terminal",
    "drop the lottery terminal",
    "@set the lottery terminal/price = 10",
    "@set the lottery terminal/round = 120",
    "@set the lottery terminal/cmd_buy = $lotto buy:price = get_attr(me, 'price', 10); ok = transfer_credits(enactor, me, price); [(set_attr(me, 'sold', n), set_attr(me, 'pot', get_attr(me, 'pot', 0) + p), set_attr(me, 'stub_' + str(n), '#' + t.id), set_attr(t, 'serial', n), teleport_obj(t, enactor), set_attr(me, 'draw_at', get_attr(me, 'draw_at', 0) or now() + get_attr(me, 'round', 120)), remit(here, name(enactor) + ' buys lottery ticket ' + str(n) + '. The pot stands at ' + str(get_attr(me, 'pot', 0)) + ' credits.')) for g, p in [[ok, price]] if g for n in [get_attr(me, 'sold', 0) + 1] for t in [create_obj('lottery ticket ' + str(n), tags=['thing', 'lottery_ticket'], location=me)]]; pemit(enactor, 'The terminal blinks: insufficient credits.') if not ok else None",
    "@set the lottery terminal/cmd_status = $lotto:pemit(enactor, 'Pot: ' + str(get_attr(me, 'pot', 0)) + ' credits across ' + str(get_attr(me, 'sold', 0)) + ' tickets. Draw in ' + str(max(0, int(get_attr(me, 'draw_at', now()) - now()))) + 's.')",
    "@set the lottery terminal/draw = n = get_attr(me, 'sold', 0); w = rand(1, n) if n else 0; t = get(get_attr(me, 'stub_' + str(w))) if w else None; holder = loc(t) if t is not None else None; win = holder is not None and has_tag(holder, 'player'); pot = get_attr(me, 'pot', 0); (transfer_credits(me, holder, pot), set_attr(me, 'pot', 0), remit(here, 'The drum rattles: ticket ' + str(w) + ' wins! ' + name(holder) + ' collects ' + str(pot) + ' credits.')) if win else remit(here, 'The drum rattles: ticket ' + str(w) + ' wins... and no one holds it. The pot rolls over.'); [destroy_obj(x) for i in range(1, n + 1) for x in [get(get_attr(me, 'stub_' + str(i)))] if x is not None]; [del_attr(me, 'stub_' + str(i)) for i in range(1, n + 1)]; set_attr(me, 'sold', 0); del_attr(me, 'draw_at'); result = 1",
    "@behavior the lottery terminal = script_ticker, interval:30",
    "@set the lottery terminal/on_tick = eval_attr(me, 'draw') if get_attr(me, 'sold', 0) and now() >= get_attr(me, 'draw_at', 0) else None",
]

# --- 093. Housing rent ------------------------------------------------------------

BUILD_RENT = [
    "@dig Rooming House Hall",
    "@teleport Rooming House Hall",
    "@dig Harbor Flat = flat door, hall door",
    "@create the rent box",
    "drop the rent box",
    "@set the rent box/rent = 50",
    "@set the rent box/period = 300",
    "@set the rent box/grace = 120",
    "@set the rent box/cmd_lease = $lease flat:ok = not get_attr(me, 'tenant'); (set_attr(me, 'tenant', enactor.id), set_attr(me, 'tenant_name', name(enactor)), set_attr(me, 'paid_until', now() + get_attr(me, 'period', 300)), set_attr(me, 'warned', 0), set_attr(me, 'till', credits(me)), pemit(enactor, 'You sign the ledger: Harbor Flat is yours. Rent is ' + str(get_attr(me, 'rent', 50)) + ' credits a period, into this box.')) if ok else pemit(enactor, 'The flat is already let.')",
    "@set the rent box/on_payment = rent = get_attr(me, 'rent', 50); paid = credits(me) - get_attr(me, 'till', 0); k = paid // rent if enactor.id == get_attr(me, 'tenant') else 0; (set_attr(me, 'paid_until', max(now(), get_attr(me, 'paid_until', 0)) + get_attr(me, 'period', 300) * k), set_attr(me, 'warned', 0), pemit(enactor, 'The box stamps a receipt: ' + str(k) + ' period(s) paid.')) if k else (transfer_credits(me, enactor, paid), pemit(enactor, 'The box spits it back: ' + ('the rent is ' + str(rent) + ' a period.' if enactor.id == get_attr(me, 'tenant') else 'you hold no lease here.'))); transfer_credits(me, enactor, paid - rent * k) if k and paid - rent * k > 0 else None; set_attr(me, 'till', credits(me))",
    "flat door",
    "@set here/on_check = box = get('the rent box'); block('The landlord froze the door code: rent is overdue. (pay at the rent box)') if atype == 'event:pre_enter' and has_atag('movement') and actor.id == get_attr(box, 'tenant') and now() > get_attr(box, 'paid_until', 0) else (block('This flat is privately let.') if atype == 'event:pre_enter' and has_atag('movement') and get_attr(box, 'tenant') and actor.id != get_attr(box, 'tenant') else None)",
    "hall door",
    "@behavior the rent box = script_ticker, interval:60",
    "@set the rent box/on_tick = t = get_attr(me, 'tenant'); due = get_attr(me, 'paid_until', 0); (set_attr(me, 'warned', 1), pemit(get('#' + t), 'A courier finds you: rent on Harbor Flat is overdue. The door is frozen until you pay.')) if t and now() > due and not get_attr(me, 'warned', 0) else None; ([teleport_obj(o, loc(me)) for o in contents(get('Harbor Flat')) if not has_tag(o, 'exit')], pemit(get('#' + t), 'The movers clear Harbor Flat: your lease is terminated and your goods are in the hall.'), del_attr(me, 'tenant'), del_attr(me, 'tenant_name'), set_attr(me, 'warned', 0), remit(loc(me), 'Movers carry furniture out of Harbor Flat and change the locks.')) if t and now() > due + get_attr(me, 'grace', 120) else None",
]

# --- 094. Job board ---------------------------------------------------------------

BUILD_JOBS = [
    "@dig The Hiring Hall",
    "@teleport The Hiring Hall",
    "@create the job board",
    "drop the job board",
    "@create Foreman Dray",
    "@tag Foreman Dray = npc",
    "drop Foreman Dray",
    "@eval adjust_credits(get('Foreman Dray'), 500)",
    '@set Foreman Dray/templates = [["a rat pelt", 15, "Cull the dock rats: bring me a rat pelt."], ["a salvage crystal", 40, "Recover a salvage crystal from the mud flats."]]',
    "@set Foreman Dray/post = board = get('the job board'); open_jobs = [i for i in range(1, get_attr(board, 'next_job', 1)) if get_attr(board, 'job_' + str(i))]; rows = get_attr(me, 'templates', []); pick = rows[rand(0, len(rows) - 1)] if rows else None; [(set_attr(brd, 'job_' + str(n), {'want': p[0], 'reward': p[1], 'text': p[2], 'taken': '', 'taken_name': ''}), set_attr(brd, 'next_job', n + 1), remit(here, 'Foreman Dray chalks a notice. Work posted: ' + p[2] + ' Pays ' + str(p[1]) + ' credits.')) for g, p, brd in [[len(open_jobs) < 2 and pick is not None, pick, board]] if g for n in [get_attr(brd, 'next_job', 1)]]; result = 1",
    "@behavior Foreman Dray = script_ticker, interval:45",
    "@set Foreman Dray/on_tick = eval_attr(me, 'post')",
    "@set the job board/cmd_jobs = $jobs:pemit(enactor, 'The job board:'); [pemit(enactor, '  #' + str(i) + ' ' + j['text'] + ' Pays ' + str(j['reward']) + '. ' + ('Taken by ' + j['taken_name'] if j['taken'] else 'OPEN')) for i in range(1, get_attr(me, 'next_job', 1)) for j in [get_attr(me, 'job_' + str(i))] if j]",
    "@set the job board/cmd_accept = $accept job *:j = get_attr(me, 'job_' + arg0.strip()); ok = bool(j) and not j['taken']; [(set_attr(me, 'job_' + arg0.strip(), dict(x, taken=enactor.id, taken_name=name(enactor))), pemit(enactor, 'You sign for job #' + arg0.strip() + ': ' + x['text'])) for g, x in [[ok, j]] if g]; pemit(enactor, 'No such job, or it is already taken.') if not ok else None",
    "@set Foreman Dray/on_receive = board = get('the job board'); stuff = [o for o in contents(me)]; it = stuff[0] if stuff else None; hits = [[i, j] for brd, itx in [[board, it]] for i in range(1, get_attr(brd, 'next_job', 1)) for j in [get_attr(brd, 'job_' + str(i))] if j and j['taken'] == enactor.id and itx is not None and name(itx) == j['want']]; paid = bool(hits) and transfer_credits(me, enactor, hits[0][1]['reward']); [(del_attr(brd, 'job_' + str(i)), destroy_obj(x), say('Good work, ' + name(enactor) + '. ' + str(j['reward']) + ' credits, as posted.')) for g, row, x, brd in [[paid, hits[0] if hits else None, it, board]] if g for i, j in [row]]; (teleport_obj(it, enactor), say('That is not what any job of yours calls for.')) if it is not None and not paid else None",
]

# --- 095. Item durability & repair -------------------------------------------------

BUILD_WEAR = [
    "@dig The Sparring Yard",
    "@teleport The Sparring Yard",
    "@create the wear master",
    "drop the wear master",
    "@create the repair bench",
    "drop the repair bench",
    "@set the wear master/ON_ATTACK = [(set_attr(o, 'condition', c), remit(here, name(o) + ' is looking battered.') if c == 25 else None, remit(here, name(o) + ' gives out with a crack!') if c == 0 else None) for o in contents(enactor) if has_tag(o, 'wielded') for c in [max(0, get_attr(o, 'condition', 100) - 5)]]",
    "@create a mono blade",
    "@set a mono blade/value = 40",
    "@set a mono blade/condition = 100",
    "@set a mono blade/on_check = block('The mono blade is a ruin of snapped segments. It needs a bench.') if atype == 'item:on_wield' and get_attr(me, 'condition', 100) <= 0 else None",
    "@create an arc welder",
    "@set an arc welder/condition = 20",
    "@set an arc welder/ON_USE = c = max(0, get_attr(me, 'condition', 100) - 10); set_attr(me, 'condition', c); pemit(enactor, 'The welder spits a bead of blue flame. (condition ' + str(c) + ')')",
    "@set an arc welder/on_check = block('The welder is burnt out. It needs a bench.') if atype == 'item:on_use' and get_attr(me, 'condition', 100) <= 0 else None",
    "@set the repair bench/cmd_repair = $repair *:itm = [o for o in contents(enactor) if name(o).lower() == arg0.strip().lower()]; c = get_attr(itm[0], 'condition', 100) if itm else 100; cost = max(1, (100 - c) // 2); ok = bool(itm) and c < 100 and transfer_credits(enactor, me, cost); [(set_attr(o, 'condition', 100), adjust_credits(me, -k), pemit(enactor, 'The bench grinds, reseats and trues ' + name(o) + ': good as new for ' + str(k) + ' credits.')) for g, o, k in [[ok, itm[0] if itm else None, cost]] if g]; pemit(enactor, 'Nothing to repair, or you cannot cover the fee.') if not ok else None",
]

# --- 096. Secure player trade -------------------------------------------------------

BUILD_TRADE = [
    "@dig The Trade Annex",
    "@teleport The Trade Annex",
    "@dig The Concourse = out, back",
    "@create Broker Unit 7",
    "@tag Broker Unit 7 = npc",
    "drop Broker Unit 7",
    "@set Broker Unit 7/cmd_open = $trade with *:other = get(arg0); ok = not get_attr(me, 'party_a') and other is not None and has_tag(other, 'player') and loc(other) is here and other.id != enactor.id; [(set_attr(me, 'party_a', enactor.id), set_attr(me, 'party_b', o.id), set_attr(me, 'name_a', name(enactor)), set_attr(me, 'name_b', name(o)), set_attr(me, 'confirm_a', 0), set_attr(me, 'confirm_b', 0), remit(here, name(enactor) + ' opens a brokered trade with ' + name(o) + '. Stage goods with: give <item> to Broker Unit 7')) for g, o in [[ok, other]] if g]; pemit(enactor, 'The broker is already holding a trade, or your counterparty is not here.') if not ok else None",
    "@set Broker Unit 7/on_receive = a = get_attr(me, 'party_a'); b = get_attr(me, 'party_b'); new = [o for o in contents(me) if not has_attr(o, 'staged_by')]; it = new[0] if new else None; ok = it is not None and enactor.id in [a, b]; [(set_attr(x, 'staged_by', enactor.id), set_attr(me, 'confirm_a', 0), set_attr(me, 'confirm_b', 0), remit(here, name(enactor) + ' stages ' + name(x) + '. All confirmations reset.')) for g, x in [[ok, it]] if g]; (teleport_obj(it, enactor), pemit(enactor, 'The broker refuses: open a trade first (trade with <who>).')) if it is not None and not ok else None",
    "@set Broker Unit 7/cmd_status = $trade status:pemit(enactor, 'On the table:'); [pemit(enactor, '  ' + name(o) + ' - from ' + (get_attr(me, 'name_a', '?') if get_attr(o, 'staged_by') == get_attr(me, 'party_a') else get_attr(me, 'name_b', '?'))) for o in contents(me) if has_attr(o, 'staged_by')]; pemit(enactor, 'Confirmed: ' + (get_attr(me, 'name_a', '') + ' ' if get_attr(me, 'confirm_a', 0) else '') + (get_attr(me, 'name_b', '') if get_attr(me, 'confirm_b', 0) else ''))",
    "@set Broker Unit 7/cmd_confirm = $trade confirm:a = get_attr(me, 'party_a'); b = get_attr(me, 'party_b'); ok = enactor.id in [a, b]; set_attr(me, 'confirm_a', 1) if ok and enactor.id == a else None; set_attr(me, 'confirm_b', 1) if ok and enactor.id == b else None; done = ok and get_attr(me, 'confirm_a', 0) and get_attr(me, 'confirm_b', 0); [(teleport_obj(o, get('#' + (pb if get_attr(o, 'staged_by') == pa else pa))), del_attr(o, 'staged_by')) for g, pa, pb in [[done, a, b]] if g for o in contents(me) if has_attr(o, 'staged_by')]; (remit(here, 'The broker chimes: trade complete between ' + get_attr(me, 'name_a', '?') + ' and ' + get_attr(me, 'name_b', '?') + '.'), del_attr(me, 'party_a'), del_attr(me, 'party_b'), del_attr(me, 'name_a'), del_attr(me, 'name_b'), set_attr(me, 'confirm_a', 0), set_attr(me, 'confirm_b', 0)) if done else None; pemit(enactor, 'You confirm. Waiting on the other side.' if ok and not done else ('You are not part of this trade.' if not ok else 'The trade executes.'))",
    "@set Broker Unit 7/reset = [(teleport_obj(o, get('#' + get_attr(o, 'staged_by'))), del_attr(o, 'staged_by')) for o in contents(me) if has_attr(o, 'staged_by')]; del_attr(me, 'party_a'); del_attr(me, 'party_b'); del_attr(me, 'name_a'); del_attr(me, 'name_b'); set_attr(me, 'confirm_a', 0); set_attr(me, 'confirm_b', 0); result = 1",
    "@set Broker Unit 7/cmd_cancel = $trade cancel:ok = enactor.id in [get_attr(me, 'party_a'), get_attr(me, 'party_b')]; (eval_attr(me, 'reset'), remit(here, name(enactor) + ' backs out; the broker returns all staged goods.')) if ok else pemit(enactor, 'You are not part of this trade.')",
    "@set Broker Unit 7/ON_LEAVE = w = enactor.id in [get_attr(me, 'party_a'), get_attr(me, 'party_b')]; (eval_attr(me, 'reset'), remit(here, 'The broker voids the trade as ' + name(enactor) + ' walks away; staged goods are returned.')) if w else None",
]

# --- 097. Barter NPC ----------------------------------------------------------------

BUILD_BARTER = [
    "@dig The Tinker Yard",
    "@teleport The Tinker Yard",
    "@create Rook the Tinker",
    "@tag Rook the Tinker = npc",
    "drop Rook the Tinker",
    '@set Rook the Tinker/wants = [["scrap_metal", "a patched thermal cloak"], ["power_cell", "a tinkered lantern"]]',
    "@set Rook the Tinker/cmd_wants = $wants:pemit(enactor, 'Rook trades goods for goods. No coin.'); [pemit(enactor, '  anything ' + w + ' -> ' + g) for w, g in get_attr(me, 'wants', [])]",
    "@set Rook the Tinker/on_receive = stuff = [o for o in contents(me) if not has_attr(o, 'kept')]; it = stuff[0] if stuff else None; deal = [[w, g] for itx in [it] for w, g in get_attr(me, 'wants', []) if itx is not None and has_tag(itx, w)]; [(set_attr(x, 'kept', 1), teleport_obj(c, enactor), say('A fair swap: ' + name(c) + ' for your ' + name(x) + '.')) for ok, x, d in [[bool(deal), it, deal]] if ok for w, g in [d[0]] for c in [create_obj(g, tags=['thing'], location=me)]]; (teleport_obj(it, enactor), say('No use to me. Ask me what I want.')) if it is not None and not deal else None",
    "@create a bent hull plate",
    "@tag a bent hull plate = scrap_metal",
]


# --- Harness ------------------------------------------------------------------------


class World:
    """A wizard (Vala) and two mortals (Bob, Cass). Each tutorial digs its
    own room live; the mortals wander in behind the wizard."""

    def __init__(self):
        self.sim = Simulator()
        self.landing = self.sim.room("The Landing")
        self.vala = self.sim.player("Vala", location=self.landing)
        self.vala.add_tag("admin")
        self.bob = self.sim.player("Bob", location=self.landing)
        self.cass = self.sim.player("Cass", location=self.landing)

    async def build(self, lines):
        for line in lines:
            await self.sim.do(self.vala, line)
        room = self.vala.location
        self.bob.location = room
        self.cass.location = room
        # Drain build chatter so tests assert on fresh output only.
        for p in (self.vala, self.bob, self.cass):
            self.sim.seen(p)
        return room

    def text(self, player) -> str:
        return "\n".join(self.sim.seen(player))

    def find(self, name):
        hits = self.sim.store.find_cached(name=name)
        return hits[0] if hits else None

    async def fund(self, player, amount):
        await self.sim.do(self.vala,
                          f"@eval adjust_credits(get('{player.name}'), {amount})")

    async def hand(self, item_name, player):
        """Vala @creates during builds leave items in her pack; hand one over."""
        await self.sim.do(self.vala, f"give {item_name} to {player.name}")

    def close(self):
        self.sim.close()


@pytest.fixture
async def world():
    w = World()
    try:
        yield w
    finally:
        w.close()


# --- 088 tests ------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPlayerStall:

    async def _open(self, w):
        await w.build(BUILD_STALL)
        stall = w.find("stall three")
        await w.sim.do(w.vala, "@create a stimpack")
        await w.sim.do(w.vala, "@set a stimpack/value = 20")
        await w.hand("a stimpack", w.bob)
        await w.fund(w.bob, 100)
        await w.fund(w.cass, 100)
        for p in (w.vala, w.bob, w.cass):
            w.sim.seen(p)
        return stall

    async def test_rent_stock_and_reprice(self, world):
        w = world
        stall = await self._open(w)

        await w.sim.do(w.bob, "rent stall")
        assert "Stall three is yours." in w.text(w.bob)
        assert get_credits(w.bob) == 80
        assert get_credits(stall) == 20                 # first period up front
        assert stall.db.get("renter") == w.bob.id

        await w.sim.do(w.bob, "stall stock a stimpack")
        assert "goes on the shelf at 20 credits." in w.text(w.bob)
        stim = w.find("a stimpack")
        assert stim.location is stall                   # escrowed
        assert stim.db.get("stall_price") == 20

        await w.sim.do(w.bob, "stall price a stimpack = 35")
        assert stim.db.get("stall_price") == 35
        assert "chalks a new price: a stimpack at 35 credits." in w.text(w.cass)

        await w.sim.do(w.cass, "stall")
        out = w.text(w.cass)
        assert "stall three, run by Bob:" in out
        assert "a stimpack - 35 credits" in out

    async def test_only_the_renter_configures(self, world):
        w = world
        stall = await self._open(w)
        await w.sim.do(w.bob, "rent stall")
        await w.sim.do(w.bob, "stall stock a stimpack")

        await w.sim.do(w.cass, "stall price a stimpack = 1")
        assert "Only the renter sets prices here." in w.text(w.cass)
        assert w.find("a stimpack").db.get("stall_price") == 20

        await w.sim.do(w.cass, "stall collect")
        assert "this is not your stall" in w.text(w.cass)

        await w.sim.do(w.cass, "rent stall")            # already let
        assert "already let" in w.text(w.cass)
        assert stall.db.get("renter") == w.bob.id

    async def test_buy_pays_the_ledger_and_collect_pays_the_renter(self, world):
        w = world
        stall = await self._open(w)
        await w.sim.do(w.bob, "rent stall")
        await w.sim.do(w.bob, "stall stock a stimpack")
        await w.sim.do(w.bob, "stall price a stimpack = 35")

        await w.sim.do(w.cass, "stall buy a stimpack")
        assert get_credits(w.cass) == 65
        stim = w.find("a stimpack")
        assert stim.location is w.cass
        assert stim.db.get("stall_price") is None
        assert stall.db.get("earnings") == 35
        assert get_credits(stall) == 20 + 35            # rent + earnings
        assert "Your stall sells a stimpack for 35 credits." in w.text(w.bob)

        await w.sim.do(w.bob, "stall collect")
        assert "You pocket 35 credits in takings." in w.text(w.bob)
        assert get_credits(w.bob) == 80 + 35
        assert stall.db.get("earnings") == 0
        assert get_credits(stall) == 20                 # the market's rent

    async def test_rent_tick_docks_earnings(self, world):
        w = world
        stall = await self._open(w)
        await w.sim.do(w.bob, "rent stall")
        await w.sim.do(w.bob, "stall stock a stimpack")
        await w.sim.do(w.cass, "stall buy a stimpack")  # earnings 20
        assert stall.db.get("earnings") == 20

        await w.sim.do(w.vala,
                       "@eval set_attr(get('stall three'), 'paid_until', now() - 1)")
        before = stall.db.get("paid_until")
        await w.sim.do(w.vala, "@tr stall three/on_tick")
        assert stall.db.get("earnings") == 0            # 20 - 20 rent
        assert stall.db.get("paid_until") == before + 300
        assert stall.db.get("renter") == w.bob.id       # still trading
        assert "The market takes 20 credits rent" in w.text(w.bob)

    async def test_broke_stall_is_repossessed_to_an_absent_renter(self, world):
        w = world
        stall = await self._open(w)
        await w.sim.do(w.bob, "rent stall")
        await w.sim.do(w.bob, "stall stock a stimpack")
        w.bob.location = w.landing                      # renter wanders off
        await w.sim.do(w.vala,
                       "@eval set_attr(get('stall three'), 'paid_until', now() - 1)")

        await w.sim.do(w.vala, "@tr stall three/on_tick")
        stim = w.find("a stimpack")
        assert stim.location is w.bob                   # goods chased him home
        assert stim.db.get("stall_price") is None
        assert stall.db.get("renter") is None
        assert "repossessed for unpaid rent" in w.text(w.bob)
        assert "TO LET" in w.text(w.cass)

        await w.sim.do(w.cass, "rent stall")            # pitch is free again
        assert stall.db.get("renter") == w.cass.id


# --- 090 tests ------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPawnShop:

    async def _open(self, w):
        await w.build(BUILD_PAWN)
        shop = w.find("the Pawn Counter")
        await w.sim.do(w.vala, "@create a chrono watch")
        await w.sim.do(w.vala, "@set a chrono watch/value = 40")
        await w.hand("a chrono watch", w.bob)
        for p in (w.vala, w.bob, w.cass):
            w.sim.seen(p)
        return shop

    async def test_pawn_advances_a_percentage_and_escrows(self, world):
        w = world
        shop = await self._open(w)

        await w.sim.do(w.bob, "pawn a chrono watch")
        out = w.text(w.bob)
        assert "Yaro counts out 24 credits" in out       # 40 * 60%
        assert "Redeem it for 26" in out                 # loan 24 + max(1, 24//10)=2 vig
        assert get_credits(w.bob) == 24
        watch = w.find("a chrono watch")
        assert watch.location is shop                    # escrowed
        row = shop.db.get("pledge_" + watch.id)
        assert row["owner"] == w.bob.id and row["loan"] == 24
        tag = w.find("a pawn tag (a chrono watch)")
        assert tag is not None and tag.location is shop
        assert tag.db.get("item") == watch.id
        assert tag.db.get("expires_at") is not None      # the forfeit timer

    async def test_redeem_inside_the_window_costs_the_vig(self, world):
        w = world
        shop = await self._open(w)
        await w.fund(w.bob, 10)
        await w.sim.do(w.bob, "pawn a chrono watch")     # bob: 10 + 24 = 34

        await w.sim.do(w.bob, "redeem a chrono watch")
        assert "You redeem your a chrono watch for 26 credits." in w.text(w.bob)
        watch = w.find("a chrono watch")
        assert watch.location is w.bob
        assert get_credits(w.bob) == 34 - 26
        assert shop.db.get("pledge_" + watch.id) is None
        assert w.find("a pawn tag (a chrono watch)") is None   # tag retired
        assert get_credits(shop) == 1000 - 24 + 26       # the vig stayed

    async def test_unvalued_goods_pawn_at_the_fallback(self, world):
        w = world
        await self._open(w)
        await w.sim.do(w.vala, "@create a mystery box")
        await w.hand("a mystery box", w.cass)

        await w.sim.do(w.cass, "pawn a mystery box")
        assert "Yaro counts out 3 credits" in w.text(w.cass)   # 60% of 5
        assert get_credits(w.cass) == 3

    async def test_lapsed_window_forfeits_to_the_rack(self, world):
        w = world
        shop = await self._open(w)
        await w.sim.do(w.bob, "pawn a chrono watch")
        watch = w.find("a chrono watch")

        # The reaper fires the tag's ON_EXPIRE, then retires the tag.
        reaped = await reap_expired(w.sim.store, now=time.time() + 301)
        assert reaped >= 1
        assert shop.db.get("pledge_" + watch.id) is None
        assert watch.has_tag("forfeit")
        assert watch.location is shop
        assert w.find("a pawn tag (a chrono watch)") is None
        assert "moves a chrono watch to the sale rack" in w.text(w.cass)

        await w.fund(w.bob, 100)
        await w.sim.do(w.bob, "redeem a chrono watch")
        assert "the window has closed" in w.text(w.bob)

        await w.sim.do(w.cass, "rack")
        assert "a chrono watch - 40 credits" in w.text(w.cass)
        await w.fund(w.cass, 40)
        await w.sim.do(w.cass, "rack buy a chrono watch")
        assert "Yours for 40 credits." in w.text(w.cass)
        assert watch.location is w.cass
        assert not watch.has_tag("forfeit")

    async def test_pawning_nothing_is_refused(self, world):
        w = world
        await self._open(w)
        await w.sim.do(w.cass, "pawn a golden idol")
        assert "You are not carrying that" in w.text(w.cass)


# --- 091 tests ------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLottery:

    async def test_buy_mints_a_recorded_ticket(self, world):
        w = world
        await w.build(BUILD_LOTTO)
        term = w.find("the lottery terminal")
        await w.fund(w.bob, 50)

        await w.sim.do(w.bob, "lotto buy")
        assert get_credits(w.bob) == 40
        assert get_credits(term) == 10                  # pot escrowed here
        assert term.db.get("pot") == 10
        assert term.db.get("sold") == 1
        assert term.db.get("draw_at") is not None
        ticket = w.find("lottery ticket 1")
        assert ticket.location is w.bob                 # minted at self, teleported
        assert term.db.get("stub_1") == "#" + ticket.id
        assert ticket.db.get("serial") == 1
        assert "buys lottery ticket 1. The pot stands at 10 credits." \
            in w.text(w.cass)

        await w.sim.do(w.bob, "lotto")
        assert "Pot: 10 credits across 1 tickets." in w.text(w.bob)

    async def test_forged_ticket_never_wins_the_ledger_does(self, world):
        w = world
        await w.build(BUILD_LOTTO)
        term = w.find("the lottery terminal")
        await w.fund(w.bob, 10)
        await w.sim.do(w.bob, "lotto buy")              # genuine ticket 1 -> Bob

        # Cass forges a perfect lookalike, serial and all.
        await w.sim.do(w.vala, "@create lottery ticket 1")
        await w.sim.do(w.vala, "@set lottery ticket 1/serial = 1")
        await w.hand("lottery ticket 1", w.cass)
        fakes = [o for o in w.cass.contents if o.name == "lottery ticket 1"]
        assert len(fakes) == 1

        await w.sim.do(w.vala, "@tr the lottery terminal/draw")
        assert get_credits(w.bob) == 10                 # the pot came back to Bob
        assert get_credits(w.cass) == 0
        assert "ticket 1 wins! Bob collects 10 credits." in w.text(w.cass)
        # Round retired: ledger empty, genuine stub destroyed, forgery ignored.
        assert term.db.get("pot") == 0
        assert term.db.get("sold") == 0
        assert term.db.get("stub_1") is None
        assert [o for o in w.bob.contents if o.has_tag("lottery_ticket")] == []
        assert fakes[0].location is w.cass              # the fake still sits there

    async def test_tickets_are_bearer_instruments(self, world):
        w = world
        await w.build(BUILD_LOTTO)
        await w.fund(w.bob, 10)
        await w.sim.do(w.bob, "lotto buy")
        await w.sim.do(w.bob, "give lottery ticket 1 to Cass")

        await w.sim.do(w.vala, "@tr the lottery terminal/draw")
        assert get_credits(w.cass) == 10                # the holder wins
        assert get_credits(w.bob) == 0

    async def test_unheld_winner_rolls_the_pot_over(self, world):
        w = world
        await w.build(BUILD_LOTTO)
        term = w.find("the lottery terminal")
        await w.fund(w.bob, 20)
        await w.sim.do(w.bob, "lotto buy")
        await w.sim.do(w.bob, "drop lottery ticket 1")  # stub lies on the floor

        await w.sim.do(w.vala, "@tr the lottery terminal/draw")
        assert "The pot rolls over." in w.text(w.cass)
        assert term.db.get("pot") == 10                 # carried forward
        assert term.db.get("sold") == 0
        assert w.find("lottery ticket 1") is None       # retired anyway

        # Next round stacks onto the rolled-over pot.
        await w.sim.do(w.bob, "lotto buy")
        assert term.db.get("pot") == 20
        await w.sim.do(w.vala, "@tr the lottery terminal/draw")
        assert get_credits(w.bob) == 20                 # spent 20, won 20

    async def test_broke_buyer_is_refused(self, world):
        w = world
        await w.build(BUILD_LOTTO)
        term = w.find("the lottery terminal")
        await w.sim.do(w.cass, "lotto buy")
        assert "insufficient credits" in w.text(w.cass)
        assert term.db.get("sold") is None

    async def test_tick_draws_only_past_the_deadline(self, world):
        w = world
        await w.build(BUILD_LOTTO)
        term = w.find("the lottery terminal")
        await w.fund(w.bob, 10)
        await w.sim.do(w.bob, "lotto buy")

        await w.sim.do(w.vala, "@tr the lottery terminal/on_tick")
        assert term.db.get("sold") == 1                 # 120s round still open

        await w.sim.do(w.vala,
                       "@eval set_attr(get('the lottery terminal'), 'draw_at', now() - 1)")
        await w.sim.do(w.vala, "@tr the lottery terminal/on_tick")
        assert term.db.get("sold") == 0                 # due -> drawn
        assert get_credits(w.bob) == 10


# --- 093 tests ------------------------------------------------------------------------


@pytest.mark.asyncio
class TestHousingRent:

    async def _open(self, w):
        hall = await w.build(BUILD_RENT)
        assert hall.name == "Rooming House Hall"        # Vala walked back out
        box = w.find("the rent box")
        flat = w.find("Harbor Flat")
        await w.fund(w.bob, 200)
        for p in (w.vala, w.bob, w.cass):
            w.sim.seen(p)
        return hall, flat, box

    async def test_lease_admits_the_tenant_and_bars_strangers(self, world):
        w = world
        hall, flat, box = await self._open(w)

        await w.sim.do(w.bob, "lease flat")
        assert "Harbor Flat is yours." in w.text(w.bob)
        assert box.db.get("tenant") == w.bob.id

        await w.sim.do(w.bob, "flat door")
        assert w.bob.location is flat
        await w.sim.do(w.cass, "flat door")
        assert "This flat is privately let." in w.text(w.cass)
        assert w.cass.location is hall
        await w.sim.do(w.bob, "hall door")
        assert w.bob.location is hall

    async def test_overdue_rent_freezes_the_door_until_paid(self, world):
        w = world
        hall, flat, box = await self._open(w)
        await w.sim.do(w.bob, "lease flat")
        await w.sim.do(w.vala,
                       "@eval set_attr(get('the rent box'), 'paid_until', now() - 10)")

        await w.sim.do(w.bob, "flat door")
        assert "The landlord froze the door code" in w.text(w.bob)
        assert w.bob.location is hall                   # locked out by arithmetic

        await w.sim.do(w.bob, "pay 50 to the rent box")
        assert "The box stamps a receipt: 1 period(s) paid." in w.text(w.bob)
        assert get_credits(w.bob) == 150
        assert box.db.get("paid_until") > time.time()

        await w.sim.do(w.bob, "flat door")
        assert w.bob.location is flat                   # the code works again

    async def test_underpay_and_stranger_money_bounce(self, world):
        w = world
        hall, flat, box = await self._open(w)
        await w.sim.do(w.bob, "lease flat")

        await w.sim.do(w.bob, "pay 30 to the rent box")
        assert "The box spits it back: the rent is 50 a period." in w.text(w.bob)
        assert get_credits(w.bob) == 200                # refunded in full

        await w.fund(w.cass, 60)
        await w.sim.do(w.cass, "pay 60 to the rent box")
        assert "you hold no lease here." in w.text(w.cass)
        assert get_credits(w.cass) == 60
        assert get_credits(box) == 0                    # till never drifts

    async def test_tick_warns_once_inside_the_grace(self, world):
        w = world
        hall, flat, box = await self._open(w)
        await w.sim.do(w.bob, "lease flat")
        await w.sim.do(w.vala,
                       "@eval set_attr(get('the rent box'), 'paid_until', now() - 10)")

        await w.sim.do(w.vala, "@tr the rent box/on_tick")
        assert "A courier finds you: rent on Harbor Flat is overdue." \
            in w.text(w.bob)
        assert box.db.get("warned") == 1
        assert box.db.get("tenant") == w.bob.id         # grace: no eviction yet

        await w.sim.do(w.vala, "@tr the rent box/on_tick")
        assert "A courier finds you" not in w.text(w.bob)   # warned once

    async def test_past_grace_the_movers_clear_the_flat(self, world):
        w = world
        hall, flat, box = await self._open(w)
        await w.sim.do(w.bob, "lease flat")
        await w.sim.do(w.vala, "@create a duffel bag")
        await w.hand("a duffel bag", w.bob)
        await w.sim.do(w.bob, "flat door")
        await w.sim.do(w.bob, "drop a duffel bag")
        assert w.find("a duffel bag").location is flat

        await w.sim.do(w.vala,
                       "@eval set_attr(get('the rent box'), 'paid_until', now() - 999)")
        await w.sim.do(w.vala, "@tr the rent box/on_tick")
        assert w.bob.location is hall                   # tenant swept out too
        assert w.find("a duffel bag").location is hall
        assert box.db.get("tenant") is None
        assert "your lease is terminated" in w.text(w.bob)
        assert "Movers carry furniture out of Harbor Flat" in w.text(w.cass)
        # Exits stayed put, and the flat is open to the next tenant.
        assert any(o.has_tag("exit") for o in flat.contents)
        await w.sim.do(w.cass, "flat door")
        assert w.cass.location is flat


# --- 094 tests ------------------------------------------------------------------------


@pytest.mark.asyncio
class TestJobBoard:

    async def _open(self, w):
        await w.build(BUILD_JOBS)
        return w.find("the job board"), w.find("Foreman Dray")

    async def test_the_foreman_posts_up_to_two_jobs(self, world):
        w = world
        board, dray = await self._open(w)

        await w.sim.do(w.vala, "@tr Foreman Dray/on_tick")
        assert board.db.get("job_1") is not None
        assert "Work posted:" in w.text(w.cass)         # remit reaches the room

        await w.sim.do(w.vala, "@tr Foreman Dray/on_tick")
        assert board.db.get("job_2") is not None
        await w.sim.do(w.vala, "@tr Foreman Dray/on_tick")
        assert board.db.get("next_job") == 3            # capped at two open

        await w.sim.do(w.bob, "jobs")
        out = w.text(w.bob)
        assert "The job board:" in out and "OPEN" in out

    async def test_accept_claims_a_job_exclusively(self, world):
        w = world
        board, dray = await self._open(w)
        await w.sim.do(w.vala, "@tr Foreman Dray/on_tick")

        await w.sim.do(w.bob, "accept job 1")
        assert "You sign for job #1:" in w.text(w.bob)
        assert board.db.get("job_1")["taken"] == w.bob.id

        await w.sim.do(w.cass, "accept job 1")
        assert "already taken" in w.text(w.cass)
        await w.sim.do(w.cass, "accept job 9")
        assert "No such job" in w.text(w.cass)

    async def test_hand_in_verifies_and_pays_automatically(self, world):
        w = world
        board, dray = await self._open(w)
        await w.sim.do(w.vala, "@tr Foreman Dray/on_tick")
        job = board.db.get("job_1")
        await w.sim.do(w.bob, "accept job 1")
        await w.sim.do(w.vala, f"@create {job['want']}")
        await w.hand(job["want"], w.bob)
        dray_purse = get_credits(dray)

        await w.sim.do(w.bob, f"give {job['want']} to Foreman Dray")
        assert f"Good work, Bob. {job['reward']} credits, as posted." \
            in w.text(w.cass)
        assert get_credits(w.bob) == job["reward"]      # wages landed
        assert get_credits(dray) == dray_purse - job["reward"]
        assert board.db.get("job_1") is None            # posting closed
        assert w.find(job["want"]) is None              # goods consumed

    async def test_wrong_or_unclaimed_deliveries_bounce(self, world):
        w = world
        board, dray = await self._open(w)
        await w.sim.do(w.vala, "@tr Foreman Dray/on_tick")
        job = board.db.get("job_1")
        await w.sim.do(w.bob, "accept job 1")

        await w.sim.do(w.vala, "@create a soggy boot")
        await w.hand("a soggy boot", w.bob)
        await w.sim.do(w.bob, "give a soggy boot to Foreman Dray")
        assert "That is not what any job of yours calls for." in w.text(w.bob)
        assert w.find("a soggy boot").location is w.bob     # pushed back

        # The right goods from someone who never signed also bounce.
        await w.sim.do(w.vala, f"@create {job['want']}")
        await w.hand(job["want"], w.cass)
        await w.sim.do(w.cass, f"give {job['want']} to Foreman Dray")
        assert w.find(job["want"]).location is w.cass
        assert get_credits(w.cass) == 0


# --- 095 tests ------------------------------------------------------------------------


@pytest.fixture
def combat():
    """A deterministic combat manager wired into the Simulator's world:
    3d6 always rolls 10 (skill 12 hits, dodge 0 fails), damage is flat 1."""
    from realm.combat.manager import CombatManager, set_combat_manager
    from realm.combat.rulesets.gurps import GURPSRuleset
    from realm.combat.system import CombatSystem

    class FixedRuleset(GURPSRuleset):
        def roll_3d6(self):
            return 10, [3, 3, 4]

        def roll_damage(self, attacker, defender, attack_result, weapon=None):
            from realm.combat.ruleset import DamageResult, DamageType
            return DamageResult(total=1,
                                damage_by_type={DamageType.PHYSICAL: 1})

    mgr = CombatManager(CombatSystem(ruleset=FixedRuleset()),
                        beat_min=4.0, beat_max=120.0, beat_default=60.0)
    set_combat_manager(mgr)
    try:
        yield mgr
    finally:
        mgr.stop_all()
        set_combat_manager(None)


@pytest.mark.asyncio
class TestDurability:

    async def _open(self, w):
        yard = await w.build(BUILD_WEAR)
        blade = w.find("a mono blade")
        welder = w.find("an arc welder")
        await w.hand("a mono blade", w.bob)
        await w.hand("an arc welder", w.bob)
        for stat, val in (("hp", 30), ("max_hp", 30), ("skill_melee", 12),
                          ("dodge", 6), ("strength", 10), ("dexterity", 12)):
            w.bob.db.set(stat, val)
        dummy = w.sim.obj("training dummy", location=yard, tags=["npc"],
                          hp=50, max_hp=50, dodge=0, strength=10, dexterity=10)
        return blade, welder, dummy

    async def test_every_swing_wears_the_wielded_weapon(self, world, combat):
        w = world
        blade, welder, dummy = await self._open(w)
        await w.sim.do(w.bob, "wield a mono blade")
        assert blade.has_tag("wielded")

        await w.sim.do(w.bob, "attack training dummy")
        enc = combat.encounter_of(w.bob)
        assert enc is not None
        await enc.resolve_round()
        assert blade.db.get("condition") == 95          # one swing, minus 5
        await enc.resolve_round()
        assert blade.db.get("condition") == 90

    async def test_thresholds_announce_and_zero_blocks_rewield(self, world, combat):
        w = world
        blade, welder, dummy = await self._open(w)
        await w.sim.do(w.bob, "wield a mono blade")
        await w.sim.do(w.bob, "attack training dummy")
        enc = combat.encounter_of(w.bob)

        blade.db.set("condition", 30)
        await enc.resolve_round()
        assert blade.db.get("condition") == 25
        assert "a mono blade is looking battered." in w.text(w.cass)

        blade.db.set("condition", 5)
        await enc.resolve_round()
        assert blade.db.get("condition") == 0
        assert "a mono blade gives out with a crack!" in w.text(w.cass)

        await w.sim.do(w.bob, "unwield")
        assert not blade.has_tag("wielded")
        await w.sim.do(w.bob, "wield a mono blade")
        assert "ruin of snapped segments" in w.text(w.bob)   # ward refuses
        assert not blade.has_tag("wielded")

    async def test_repair_restores_and_burns_the_fee(self, world, combat):
        w = world
        blade, welder, dummy = await self._open(w)
        bench = w.find("the repair bench")
        blade.db.set("condition", 0)
        await w.fund(w.bob, 100)

        await w.sim.do(w.bob, "repair a mono blade")
        assert "good as new for 50 credits." in w.text(w.bob)
        assert blade.db.get("condition") == 100
        assert get_credits(w.bob) == 50
        assert get_credits(bench) == 0                  # the fee was burned

        await w.sim.do(w.bob, "wield a mono blade")
        assert blade.has_tag("wielded")                 # good as new indeed

        await w.sim.do(w.bob, "repair a mono blade")    # nothing to fix now
        assert "Nothing to repair" in w.text(w.bob)

    async def test_tools_wear_themselves_on_use(self, world):
        w = world
        blade, welder, dummy = await self._open(w)

        await w.sim.do(w.bob, "use an arc welder")
        assert welder.db.get("condition") == 10
        assert "(condition 10)" in w.text(w.bob)
        await w.sim.do(w.bob, "use an arc welder")
        assert welder.db.get("condition") == 0

        await w.sim.do(w.bob, "use an arc welder")      # its own ward now blocks
        assert "The welder is burnt out." in w.text(w.bob)
        assert welder.db.get("condition") == 0

        await w.fund(w.bob, 100)
        await w.sim.do(w.bob, "repair an arc welder")
        assert welder.db.get("condition") == 100
        assert get_credits(w.bob) == 50


# --- 096 tests ------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSecureTrade:

    async def _open(self, w):
        await w.build(BUILD_TRADE)
        broker = w.find("Broker Unit 7")
        await w.sim.do(w.vala, "@create plasma torch")
        await w.hand("plasma torch", w.bob)
        await w.sim.do(w.vala, "@create crystal skull")
        await w.hand("crystal skull", w.cass)
        for p in (w.vala, w.bob, w.cass):
            w.sim.seen(p)
        return broker

    async def test_stage_confirm_and_atomic_swap(self, world):
        w = world
        broker = await self._open(w)

        await w.sim.do(w.bob, "trade with Cass")
        assert "opens a brokered trade with Cass" in w.text(w.cass)
        assert broker.db.get("party_a") == w.bob.id
        assert broker.db.get("party_b") == w.cass.id

        await w.sim.do(w.bob, "give plasma torch to Broker Unit 7")
        torch = w.find("plasma torch")
        assert torch.location is broker                 # escrowed
        assert torch.db.get("staged_by") == w.bob.id
        assert "Bob stages plasma torch. All confirmations reset." \
            in w.text(w.cass)

        await w.sim.do(w.cass, "give crystal skull to Broker Unit 7")
        skull = w.find("crystal skull")
        assert skull.location is broker

        await w.sim.do(w.bob, "trade confirm")
        assert "You confirm. Waiting on the other side." in w.text(w.bob)
        assert broker.db.get("confirm_a") == 1

        await w.sim.do(w.cass, "trade confirm")         # the one-script commit
        assert "The trade executes." in w.text(w.cass)
        assert "trade complete between Bob and Cass" in w.text(w.bob)
        assert torch.location is w.cass
        assert skull.location is w.bob
        assert torch.db.get("staged_by") is None
        assert broker.db.get("party_a") is None         # session cleared

    async def test_any_change_resets_confirmations(self, world):
        w = world
        broker = await self._open(w)
        await w.sim.do(w.vala, "@create old boot")
        await w.hand("old boot", w.cass)
        await w.sim.do(w.bob, "trade with Cass")
        await w.sim.do(w.bob, "give plasma torch to Broker Unit 7")
        await w.sim.do(w.cass, "give crystal skull to Broker Unit 7")
        await w.sim.do(w.bob, "trade confirm")
        assert broker.db.get("confirm_a") == 1

        await w.sim.do(w.cass, "give old boot to Broker Unit 7")
        assert broker.db.get("confirm_a") == 0          # Bob's confirm wiped
        assert "All confirmations reset." in w.text(w.bob)

        await w.sim.do(w.bob, "trade confirm")
        await w.sim.do(w.cass, "trade confirm")
        # Bob gets both of Cass's staged items; Cass gets the torch.
        assert w.find("old boot").location is w.bob
        assert w.find("crystal skull").location is w.bob
        assert w.find("plasma torch").location is w.cass

    async def test_bystanders_and_strays_are_refused(self, world):
        w = world
        broker = await self._open(w)
        # No trade open: staging bounces with instructions.
        await w.sim.do(w.bob, "give plasma torch to Broker Unit 7")
        assert "open a trade first" in w.text(w.bob)
        assert w.find("plasma torch").location is w.bob

        await w.sim.do(w.bob, "trade with Cass")
        await w.sim.do(w.vala, "@create sturdy boots")
        await w.sim.do(w.vala, "give sturdy boots to Broker Unit 7")
        assert w.find("sturdy boots").location is w.vala    # not a party
        await w.sim.do(w.vala, "trade confirm")
        assert "You are not part of this trade." in w.text(w.vala)

    async def test_walking_out_voids_the_deal(self, world):
        w = world
        broker = await self._open(w)
        await w.sim.do(w.bob, "trade with Cass")
        await w.sim.do(w.bob, "give plasma torch to Broker Unit 7")
        await w.sim.do(w.cass, "give crystal skull to Broker Unit 7")

        await w.sim.do(w.bob, "out")                    # ON_LEAVE tripwire
        assert w.bob.location is w.find("The Concourse")
        assert "The broker voids the trade as Bob walks away" in w.text(w.cass)
        assert w.find("plasma torch").location is w.bob      # chased him out
        assert w.find("crystal skull").location is w.cass
        assert broker.db.get("party_a") is None

    async def test_cancel_returns_everything(self, world):
        w = world
        broker = await self._open(w)
        await w.sim.do(w.bob, "trade with Cass")
        await w.sim.do(w.bob, "give plasma torch to Broker Unit 7")

        await w.sim.do(w.cass, "trade cancel")
        assert "backs out; the broker returns all staged goods." in w.text(w.bob)
        assert w.find("plasma torch").location is w.bob
        assert broker.db.get("party_a") is None


# --- 097 tests ------------------------------------------------------------------------


@pytest.mark.asyncio
class TestBarterNPC:

    async def _open(self, w):
        await w.build(BUILD_BARTER)
        rook = w.find("Rook the Tinker")
        await w.hand("a bent hull plate", w.bob)
        for p in (w.vala, w.bob, w.cass):
            w.sim.seen(p)
        return rook

    async def test_wants_lists_the_menu(self, world):
        w = world
        await self._open(w)
        await w.sim.do(w.bob, "wants")
        out = w.text(w.bob)
        assert "Rook trades goods for goods. No coin." in out
        assert "anything scrap_metal -> a patched thermal cloak" in out
        assert "anything power_cell -> a tinkered lantern" in out

    async def test_matching_gift_swaps_item_for_item(self, world):
        w = world
        rook = await self._open(w)
        assert get_credits(w.bob) == 0 and get_credits(rook) == 0

        await w.sim.do(w.bob, "give a bent hull plate to Rook the Tinker")
        assert "A fair swap: a patched thermal cloak for your a bent hull plate." \
            in w.text(w.bob)
        cloak = w.find("a patched thermal cloak")
        assert cloak.location is w.bob                  # counter-gift delivered
        plate = w.find("a bent hull plate")
        assert plate.location is rook and plate.db.get("kept") == 1

        # Wallets untouched on both sides — the whole point.
        assert get_credits(w.bob) == 0
        assert get_credits(rook) == 0

    async def test_off_list_goods_bounce_back(self, world):
        w = world
        rook = await self._open(w)
        await w.sim.do(w.vala, "@create a ration bar")
        await w.hand("a ration bar", w.cass)

        await w.sim.do(w.cass, "give a ration bar to Rook the Tinker")
        assert "No use to me. Ask me what I want." in w.text(w.cass)
        assert w.find("a ration bar").location is w.cass
        assert w.find("a patched thermal cloak") is None

    async def test_the_tag_is_the_currency_not_the_name(self, world):
        w = world
        rook = await self._open(w)
        await w.sim.do(w.vala, "@create a snapped strut")
        await w.sim.do(w.vala, "@tag a snapped strut = scrap_metal")
        await w.hand("a snapped strut", w.cass)

        await w.sim.do(w.cass, "give a snapped strut to Rook the Tinker")
        assert "A fair swap: a patched thermal cloak for your a snapped strut." \
            in w.text(w.cass)
        cloaks = w.sim.store.find_cached(name="a patched thermal cloak")
        assert len(cloaks) == 1 and cloaks[0].location is w.cass
