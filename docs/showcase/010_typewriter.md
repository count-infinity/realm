# 010. Typewriter & paper

> Checklist item 10 — [now] — *prompt() wizards, per-page attrs, the attribute editor*

**What you'll build:** A brass typewriter that manufactures documents:
`type <title>` rolls in a fresh sheet and opens a line-by-line writing
wizard, `PAGE` starts a new page, `DONE` pulls the sheet — a real,
carryable object whose pages live in attributes. `peruse` reads any
document back; `sign` puts a one-time signature on it.

**Concepts:** a **looping `prompt()` wizard** (the callback re-prompts
until a sentinel word), documents as spawned objects with per-page
list attributes (`page_1`, `page_2`, ...), sentinel words vs. the
prompt escape hatch, `escape()` for player prose, builtin *prefix*
shadowing (`$read` can never fire), and `@set` as the attribute editor
for finished pages.

Builds on the [combination safe](016_combination_safe.md) (single
`prompt()`) and the [camera](008_camera.md) (spawned keepsakes).

## How it works

**A wizard is a prompt that asks again.** One `prompt()` captures one
line into a callback (see the [wizards guide](../guides/wizards.md)).
A *multi-line* wizard is the same callback ending in another
`prompt()` — the loop runs until the player types a sentinel word.
Two sentinels here: `PAGE` (bump the sheet's page counter, keep
prompting) and `DONE` (release the roller). Anything else is a line of
prose, `escape()`d and appended to the current page. The engine's own
escape hatch stays open the whole time — `help`, `quit`, and `exit`
always reach the dispatcher, so a half-typed memoir never traps
anyone. And because an abandoned wizard leaves a sheet clamped in the
roller, `type` doubles as *resume*: if a sheet is already loaded, it
re-opens the prompt right where the last typist stopped.

**The document is the state, the typewriter is the tool.** Each sheet
is a `create_obj`'d thing tagged `document`, carrying `title`, a
`pages` count, and one **list attribute per page** — `page_1`,
`page_2`, ... The typewriter holds only a `sheet` pointer (the id in
the roller) while writing; after `DONE` it holds nothing. Sheets
outlive the machine, travel in pockets, and can be dropped, given, or
locked in the [safe](016_combination_safe.md).

**Why `peruse` and not `read`?** Builtins dispatch before
`$`-triggers — the vending machine taught that with `buy`. The sharper
edge here: the dispatcher also accepts *unambiguous prefixes* of
builtin names, and `read` is a prefix of `ready` (the `wield` alias).
So `read sheet` never reaches your trigger; it answers "You aren't
carrying 'sheet'." from the wield command. Check both collisions —
exact *and* prefix — before naming an object command. `peruse`, `type`,
and `sign` are clean.

**Signatures are one-shot.** `sign` appends a signature line to the
last page and stamps `signed_by`; a second signature is refused, and
you must be *holding* the document (`loc(s) is enactor` — an object
identity check, not a name check). Editing after the fact is what the
attribute editor is for: `@set` can rewrite any `page_N` list —
builder-side proofreading of player prose.

## Build it

The machine:

```text
@create brass typewriter
drop brass typewriter
```

`type` — refuse nothing, resume everything: a busy roller re-opens the
wizard, a blank title gets usage help, and a fresh title mints the
sheet (into your hands), points the roller at it, and asks for the
first line:

```text
@set brass typewriter/cmd_type = $type *: title = trim(arg0); busy = get_attr(me, 'sheet', ''); (pemit(enactor, 'A sheet is already in the roller; you pick up where the last typist left off.'), prompt(enactor, 'Next line (PAGE / DONE):', 'on_line')) if busy else None; pemit(enactor, 'Give the sheet a title: type <title>.') if not title and not busy else None; s = create_obj('a typed sheet: ' + title, tags=['thing', 'document'], location=enactor) if title and not busy else None; (set_attr(s, 'title', title), set_attr(s, 'pages', 1), set_attr(me, 'sheet', s.id), remit(here, name(enactor) + ' feeds a fresh sheet into the brass typewriter.'), prompt(enactor, 'The keys wait. Type a line (PAGE starts a new page; DONE pulls the sheet):', 'on_line')) if s else None
```

The wizard loop — sentinels first, then append-and-ask-again:

```text
@set brass typewriter/on_line = s = get('#' + str(get_attr(me, 'sheet', ''))); w = trim(arg0); n = get_attr(s, 'pages', 1) if s else 0; (set_attr(me, 'sheet', ''), pemit(enactor, 'The platen ratchets back and you pull the finished sheet free.')) if not s or w == 'DONE' else ((set_attr(s, 'pages', n + 1), prompt(enactor, 'A fresh page rolls in. [page ' + str(n + 1) + '] Next line (PAGE / DONE):', 'on_line')) if w == 'PAGE' else (set_attr(s, 'page_' + str(n), get_attr(s, 'page_' + str(n), []) + [escape(arg0)]), prompt(enactor, '[page ' + str(n) + '] Next line (PAGE / DONE):', 'on_line')))
```

Reading — every page in order, headed and numbered (`get()` finds the
named document in your hands or the room):

```text
@set brass typewriter/cmd_peruse = $peruse *: s = get(trim(arg0)); ok = s is not None and has_tag(s, 'document'); pemit(enactor, 'There is no document by that name here.') if not ok else pemit(enactor, 'The type reads, page by page:'); [pemit(enactor, line) for g in [ok] if g for p in range(1, get_attr(s, 'pages', 1) + 1) for line in ['--- page ' + str(p) + ' ---'] + [str(x) for x in get_attr(s, 'page_' + str(p), [])]]
```

Signing — held documents only, once only, witnessed:

```text
@set brass typewriter/cmd_sign = $sign *: s = get(trim(arg0)); ok = s is not None and has_tag(s, 'document') and loc(s) is enactor; already = str(get_attr(s, 'signed_by', '')) if ok else ''; pemit(enactor, 'Hold the document you mean to sign.') if not ok else None; pemit(enactor, 'It already bears a signature: ' + already + '.') if ok and already else None; k = 'page_' + str(get_attr(s, 'pages', 1)) if ok else ''; (set_attr(s, k, get_attr(s, k, []) + ['Signed in a firm hand: ' + name(enactor)]), set_attr(s, 'signed_by', name(enactor)), remit(here, name(enactor) + ' signs ' + name(s) + ' with a flourish.')) if ok and not already else None
```

## Try it

```text
type Manifesto
All gadgets deserve softcode.
No exceptions.
PAGE
Draft two follows.
DONE
peruse typed sheet
sign typed sheet
peruse typed sheet
sign typed sheet          -> It already bears a signature: Bilda.
```

The room watches you feed the sheet in and, later, sign it with a
flourish; `peruse` prints both pages under `--- page N ---` headers
with the signature on the last line. Drop the sheet and `sign` refuses
— you must hold what you sign. Walk away mid-wizard and the next
person's `type` resumes your abandoned sheet (the roller doesn't care
whose fingers finish it). Typos? The attribute editor is right there:
`@set a typed sheet: Manifesto/page_1 = ["Corrected first line."]`.

## Going further

- **Documents readable anywhere:** at `DONE`, also
  `set_attr(s, 'cmd_peruse', ...)` — triggers are scanned live from
  attributes, so a command *on the sheet itself* travels with it, no
  typewriter needed.
- **A cover for `look`:** stamp the sheet's `desc_extras` with its
  title and page count (the [camera](008_camera.md)'s workaround) so
  casual looks show the cover, `peruse` the contents.
- **Carbon copies:** `@clone` a finished sheet — attributes copy, so
  the duplicate is page-perfect; watermark it by appending to
  `page_1`.
- **Notarization:** `sign` could demand a `forgery`-proof: store
  `enactor.id` too and let a court gadget verify names against ids —
  identity vs. display text, softcode's oldest lesson.
