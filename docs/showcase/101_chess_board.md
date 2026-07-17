# 101. Chess Board

> Checklist item 101 — [now] — *eval_attr render helpers, grid attrs, sandboxed validation*

**What you'll build:** A two-player chessboard rendered in text, with
seats for white and black, turn enforcement, and geometric move
validation for every piece — pawns and rooks strictly (blocked paths,
double-step, diagonal-only captures), and the rest of the army by the
same path-clearance rules.

**Concepts:** a grid as a list-of-lists attribute, pure-functional
board updates (a comprehension instead of mutation), `eval_attr()`
helper functions (`sq`, `legal`) that keep one command readable,
`member()` for file parsing, `repeat()` for the frame, and what to
leave out of a sandboxed validator (and why).

## How it works

**The board is data.** `state` is eight lists of eight one-character
strings: uppercase for white (`PRNBQK`), lowercase for black, `'.'`
for empty. Row 0 is rank 8 — the standard reading order — so rendering
is a straight comprehension and square `e2` maps to
`state[8 - 2][files.index('e')]`.

**Helpers keep the verb legible.** `eval_attr(me, 'sq', 'e2')` parses
algebraic notation into `[row, col]` (using `member()` — 1-indexed, 0
means garbage, and any malformed square just returns `None`). `legal`
holds the movement table: it computes the step direction, walks the
squares between with `all(...)` for path clearance, then applies one
rule per piece kind — pawns get direction, double-step-from-home, and
capture-only-diagonally; rooks/bishops/queens are clear straight or
diagonal lines; kings step one; knights need `sorted([abs(dr),
abs(dc)]) == [1, 2]` and jump over everything.

**Moves never mutate.** Rather than poking the nested lists, `$move`
rebuilds the whole 8×8 grid in one comprehension that drops the piece
on the target and blanks the source, then `set_attr`s it back — cheap
(64 cells is nothing against the sandbox's 25,000-call budget) and
atomic: a failed validation never half-writes a board.

**What's deliberately missing:** check, checkmate, castling, en
passant, promotion. Geometric legality is one pass over one move; check
detection means simulating every reply, which multiplies the work and
the code — that's a Going-further, and the note there says where the
budget goes.

## Build it

Board, reset, and seats:

```text
@create a chessboard
drop a chessboard
@desc a chessboard = Scarred maple, ranks and files burned in. [[result = ('White' if V('turn', 'w') == 'w' else 'Black') + ' to move.']]
@set a chessboard/fresh = result = [list('rnbqkbnr'), list('pppppppp'), list('........'), list('........'), list('........'), list('........'), list('PPPPPPPP'), list('RNBQKBNR')]
@set a chessboard/cmd_reset = $chess reset: set_attr(me, 'state', eval_attr(me, 'fresh')); set_attr(me, 'turn', 'w'); set_attr(me, 'white', ''); set_attr(me, 'black', ''); remit(here, 'The chessboard resets to the opening position. Claim sides: white / black.')
@set a chessboard/cmd_white = $white: taken = V('white', ''); (set_attr(me, 'white', enactor.id), remit(here, name(enactor) + ' takes white.')) if not taken else pemit(enactor, 'White is taken.')
@set a chessboard/cmd_black = $black: taken = V('black', ''); (set_attr(me, 'black', enactor.id), remit(here, name(enactor) + ' takes black.')) if not taken else pemit(enactor, 'Black is taken.')
```

The renderer — one `pemit` per rank, framed with `repeat()`:

```text
@set a chessboard/cmd_board = $board: b = V('state', []); pemit(enactor, '  +' + repeat('-', 17) + '+'); [pemit(enactor, f'{8 - i} | {" ".join(b[i])} |') for i in range(8)]; pemit(enactor, '  +' + repeat('-', 17) + '+'); pemit(enactor, '    a b c d e f g h')
```

The parsing and legality helpers:

```text
@set a chessboard/sq = f = member(arg0[0], 'a b c d e f g h'); r = int(arg0[1]) if arg0[1].isdigit() else 0; result = [8 - r, f - 1] if f and 1 <= r <= 8 else None
@set a chessboard/legal = b = V('state', []); p = arg0; fr = int(arg1); fc = int(arg2); tr = int(arg3); tc = int(arg4); dr = tr - fr; dc = tc - fc; k = p.lower(); fwd = -1 if p.isupper() else 1; start = 6 if p.isupper() else 1; tgt = b[tr][tc]; steps = max(abs(dr), abs(dc)); sr = (dr > 0) - (dr < 0); sc = (dc > 0) - (dc < 0); clear = all(b[fr + sr * i][fc + sc * i] == '.' for i in range(1, steps)); result = (dc == 0 and tgt == '.' and (dr == fwd or (fr == start and dr == 2 * fwd and clear)) or (abs(dc) == 1 and dr == fwd and tgt != '.')) if k == 'p' else ((dr == 0 or dc == 0) and clear if k == 'r' else (abs(dr) == abs(dc) and clear if k == 'b' else ((dr == 0 or dc == 0 or abs(dr) == abs(dc)) and clear if k == 'q' else (steps == 1 if k == 'k' else sorted([abs(dr), abs(dc)]) == [1, 2]))))
```

The move — seat, turn, ownership, target, geometry, then the pure
rebuild:

```text
@set a chessboard/cmd_move = $move * *: b = V('state', []); a = eval_attr(me, 'sq', trim(arg0)); z = eval_attr(me, 'sq', trim(arg1)); t = V('turn', 'w'); seat = V('white' if t == 'w' else 'black', ''); ok = bool(b) and a is not None and z is not None and enactor.id == seat; p = b[a[0]][a[1]] if ok else '.'; mine = p != '.' and (p.isupper() if t == 'w' else p.islower()); tgt = b[z[0]][z[1]] if ok else '.'; onmine = tgt != '.' and (tgt.isupper() if t == 'w' else tgt.islower()); ok2 = ok and mine and not onmine and eval_attr(me, 'legal', p, a[0], a[1], z[0], z[1]); [(set_attr(me, 'state', [[p if [i, j] == z else ('.' if [i, j] == a else b[i][j]) for j in range(8)] for i in range(8)]), set_attr(me, 'turn', 'b' if t == 'w' else 'w'), remit(here, ('White' if t == 'w' else 'Black') + ' plays ' + trim(arg0) + '-' + trim(arg1) + (', taking ' + tgt + '.' if tgt != '.' else '.'))) for g in [ok2] if g]; pemit(enactor, 'The pieces refuse: not your seat, not your turn, or not a legal move.') if not ok2 else None
```

## Try it

```text
chess reset
white                 (one player)
black                 (the other)
board                 -> the opening position, framed
move e2 e4            (white) -> "White plays e2-e4."
move e2 e4            (white again) -> "The pieces refuse..."
move e7 e5            (black)
move d1 h5            (white; the queen's diagonal is open now)
move a7 a6            (black)
move h5 e5            (white) -> "White plays h5-e5, taking p."
board                 -> the black pawn is gone
```

Blocked paths refuse honestly: `move a1 a4` with the a-pawn home is
rejected — the rook can't ghost through it. Knights can: `move b1 c3`
works from the opening.

## Going further

- **Check detection:** after each move, scan the 64 squares for the
  enemy king and ask `legal` whether any of your pieces reaches it —
  one extra pass (≤ 16 `eval_attr` calls, well inside the sandbox
  budget). Full *checkmate* means trying every reply — that's ~1,000
  legality calls, still legal but the code stops fitting in one
  attribute; split it across helpers.
- **Promotion:** in the rebuild, `'Q' if k == 'p' and tr in [0, 7]
  else p`.
- **Spectator boards:** swap the renderer's `pemit` for `remit` on
  capture turns, or `oob(enactor, 'Chess.Board', {...})` to feed a
  client-side board via GMCP.
- **Clocks:** stamp `now()` each move and a `script_ticker` that
  forfeits the seat whose total exceeds ten minutes.

**~~Engine gaps~~ — FIXED 2026-07-17.** The path-clearance check used to be
written `all([... for i in range(1, steps)])`, a *list* comprehension,
rather than the tidier generator now above. That was forced: the sandbox
exec'd scripts with separate `globals`/`locals` dicts, so generator
expressions and `lambda`s `NameError`ed on locals like `b`, `fr`, `sc`.
Scripts now share one namespace and the bare generator works (see item
100) — and it is the better tool here for a reason beyond tidiness: a
generator **short-circuits**. `all(...)` stops at the first occupied
square instead of testing the whole path and then throwing the list
away, which on a queen's eight-square slide is most of the work saved.
