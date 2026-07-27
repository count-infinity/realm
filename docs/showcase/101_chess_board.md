# 101. Chess Board

> Checklist item 101 ([now]): *eval_attr render helpers, grid attrs, sandboxed validation*

**What you'll build:** A two-player chessboard rendered in text, with
seats for white and black, turn enforcement, and geometric move
validation for every piece: pawns and rooks strictly (blocked paths,
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
for empty. Row 0 is rank 8, the standard reading order, so rendering is
a straight loop and square `e2` lands at row `8 - 2` and the e file's
column. [`set_attr()`](../reference/softcode.md#fn-set_attr) stores the
grid and [`V()`](../reference/softcode.md#fn-v) reads it back.

**Helpers keep the verb legible.**
[`eval_attr(me, 'sq', 'e2')`](../reference/softcode.md#fn-eval_attr) runs
the named `sq` attribute and hands back its `result`: it parses
algebraic notation into `[row, col]` using
[`member()`](../reference/softcode.md#fn-member), which is 1-indexed and
returns 0 for a file that is not a letter a to h, so any malformed square
returns `None`. `legal` holds the movement table: it computes the step
direction, walks the squares between with `all(...)` for path clearance,
then applies one rule per piece kind. Pawns get direction, a double-step
only from the home rank, and capture only on the diagonal; rooks,
bishops, and queens need a clear straight or diagonal line; kings step
one square; knights need `sorted([abs(dr), abs(dc)]) == [1, 2]` and jump
over everything.

**Moves never mutate.** Rather than poking the nested lists, `$move`
rebuilds the whole 8x8 grid in one comprehension that drops the piece
on the target and blanks the source, then stores it. That is cheap (64
cells is nothing against the sandbox call budget) and atomic, since a
failed validation never half-writes a board.

**What is deliberately missing:** check, checkmate, castling, en
passant, promotion. Geometric legality is one pass over one move,
whereas check detection means simulating every reply, which multiplies
the work and the code. That is a Going-further, and the note there says
where the budget goes.

## Build it

Create the board, drop it in the room, and give it a description that
reports whose move it is:

```text
@create a chessboard
drop a chessboard
@desc a chessboard = Scarred maple, ranks and files burned in. [[result = ('White' if V('turn', 'w') == 'w' else 'Black') + ' to move.']]
```

A `fresh` helper returns the opening position as eight rows built with
`list()`. It is one statement, so it stays on one line:

```text
@set a chessboard/fresh = result = [list('rnbqkbnr'), list('pppppppp'), list('........'), list('........'), list('........'), list('........'), list('PPPPPPPP'), list('RNBQKBNR')]
```

`chess reset` copies that fresh position onto `state`, sets white to
move, clears both seats, and announces it with
[`remit()`](../reference/softcode.md#fn-remit):

```text
@set a chessboard/cmd_reset = '''
$chess reset:
set_attr(me, 'state', eval_attr(me, 'fresh'))
set_attr(me, 'turn', 'w')
set_attr(me, 'white', '')
set_attr(me, 'black', '')
remit(here, 'The chessboard resets to the opening position. Claim sides: white / black.')
'''
```

`white` and `black` claim the two seats. A seat records the claimant's
id and announces to the room with
[`name()`](../reference/softcode.md#fn-name); a second claim bounces with
[`pemit()`](../reference/softcode.md#fn-pemit):

```text
@set a chessboard/cmd_white = '''
$white:
taken = V('white', '')
if not taken:
    set_attr(me, 'white', enactor.id)
    remit(here, name(enactor) + ' takes white.')
else:
    pemit(enactor, 'White is taken.')
'''
@set a chessboard/cmd_black = '''
$black:
taken = V('black', '')
if not taken:
    set_attr(me, 'black', enactor.id)
    remit(here, name(enactor) + ' takes black.')
else:
    pemit(enactor, 'Black is taken.')
'''
```

The renderer prints one `pemit` per rank, framed top and bottom with
[`repeat()`](../reference/softcode.md#fn-repeat) and labelled with a file
line beneath. A real `for` loop reads more plainly here than a
comprehension whose only purpose is its side effect:

```text
@set a chessboard/cmd_board = '''
$board:
b = V('state', [])
pemit(enactor, '  +' + repeat('-', 17) + '+')
for i in range(8):
    pemit(enactor, f'{8 - i} | {" ".join(b[i])} |')
pemit(enactor, '  +' + repeat('-', 17) + '+')
pemit(enactor, '    a b c d e f g h')
'''
```

The two helpers do the reading and the geometry. `sq` turns `e2` into
`[row, col]`, and `legal` answers one yes/no per piece kind:

```text
@set a chessboard/sq = '''
f = member(arg0[0], 'a b c d e f g h')  # 1-indexed; 0 means the file was not a to h
r = int(arg0[1]) if arg0[1].isdigit() else 0
if f and 1 <= r <= 8:
    result = [8 - r, f - 1]
else:
    result = None
'''
@set a chessboard/legal = '''
b = V('state', [])
p = arg0
fr = int(arg1)
fc = int(arg2)
tr = int(arg3)
tc = int(arg4)
dr = tr - fr
dc = tc - fc
k = p.lower()
fwd = -1 if p.isupper() else 1
start = 6 if p.isupper() else 1
tgt = b[tr][tc]
steps = max(abs(dr), abs(dc))
sr = (dr > 0) - (dr < 0)
sc = (dc > 0) - (dc < 0)
clear = all(b[fr + sr * i][fc + sc * i] == '.' for i in range(1, steps))  # every square between source and target is empty
if k == 'p':
    result = (dc == 0 and tgt == '.' and (dr == fwd or (fr == start and dr == 2 * fwd and clear))) or (abs(dc) == 1 and dr == fwd and tgt != '.')  # a pawn advances straight but captures only on the diagonal
elif k == 'r':
    result = (dr == 0 or dc == 0) and clear
elif k == 'b':
    result = abs(dr) == abs(dc) and clear
elif k == 'q':
    result = (dr == 0 or dc == 0 or abs(dr) == abs(dc)) and clear
elif k == 'k':
    result = steps == 1
else:
    result = sorted([abs(dr), abs(dc)]) == [1, 2]  # a knight jumps, so clearance never applies
'''
```

The move parses each square with
[`trim()`](../reference/softcode.md#fn-trim), then checks seat, turn,
ownership, and target before asking `legal` for the geometry. Only when
every gate passes does it rebuild the grid and hand the turn over:

```text
@set a chessboard/cmd_move = '''
$move * *:
b = V('state', [])
a = eval_attr(me, 'sq', trim(arg0))
z = eval_attr(me, 'sq', trim(arg1))
t = V('turn', 'w')
seat = V('white' if t == 'w' else 'black', '')
ok = bool(b) and a is not None and z is not None and enactor.id == seat
p = b[a[0]][a[1]] if ok else '.'
mine = p != '.' and (p.isupper() if t == 'w' else p.islower())
tgt = b[z[0]][z[1]] if ok else '.'
onmine = tgt != '.' and (tgt.isupper() if t == 'w' else tgt.islower())  # cannot land on your own piece
ok2 = ok and mine and not onmine and eval_attr(me, 'legal', p, a[0], a[1], z[0], z[1])
if ok2:
    set_attr(me, 'state', [[p if [i, j] == z else ('.' if [i, j] == a else b[i][j]) for j in range(8)] for i in range(8)])  # rebuild the whole grid; a rejected move never half-writes it
    set_attr(me, 'turn', 'b' if t == 'w' else 'w')
    remit(here, ('White' if t == 'w' else 'Black') + ' plays ' + trim(arg0) + '-' + trim(arg1) + (', taking ' + tgt + '.' if tgt != '.' else '.'))
else:
    pemit(enactor, 'The pieces refuse: not your seat, not your turn, or not a legal move.')
'''
```

Every verb above is a `$`-command, so it fires only on the board that
carries it, with the typist as `enactor`. That is why none of them take
a `target is me` guard: that guard belongs to a reactive
[`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks) hook, which
fires on every object in the room, and this board has no such hook.

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

Blocked paths refuse honestly: `move a1 a4` with the a-pawn still home
is rejected, since the rook cannot ghost through it. Knights are the
exception, because a knight jumps: `move b1 c3` works from the opening.

## Going further

- **Check detection:** after each move, scan the 64 squares for the
  enemy king and ask `legal` whether any of your pieces reaches it, one
  extra pass (at most 16 `eval_attr` calls, well inside the sandbox
  budget). Full *checkmate* means trying every reply, roughly 1,000
  legality calls, still within budget but the code stops fitting in one
  attribute, so split it across helpers.
- **Promotion:** in the rebuild, `'Q' if k == 'p' and tr in [0, 7]
  else p`.
- **Spectator boards:** swap the renderer's `pemit` for `remit` on
  capture turns, or `oob(enactor, 'Chess.Board', {...})` to feed a
  client-side board via GMCP.
- **Clocks:** stamp `now()` each move and a `script_ticker` that
  forfeits the seat whose total exceeds ten minutes.

**~~Engine gaps~~, FIXED 2026-07-17.** The path-clearance check reads
`all(... for i in range(1, steps))`, a bare generator expression. That
generator matters beyond tidiness, because it **short-circuits**:
`all(...)` stops at the first occupied square instead of testing the
whole path and then discarding the result, which on a queen's
eight-square slide saves most of the work. It relies on scripts sharing
one namespace so the generator can read locals like `b`, `fr`, and `sc`,
the same property the [poker table](100_poker_table.md) evaluator leans
on for its `lambda` tie-break.
