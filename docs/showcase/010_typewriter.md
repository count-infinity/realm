# 010. Typewriter & paper

> Checklist item 10 ([now]): *prompt() wizards, per-page attrs, the attribute editor*

**What you'll build:** A brass typewriter that manufactures documents.
`type <title>` rolls in a fresh sheet and opens a line-by-line writing
wizard, `PAGE` starts a new page, and `DONE` pulls the sheet: a real,
carryable object whose pages live in attributes. `peruse` reads any
document back; `sign` puts a one-time signature on it.

**Concepts:** a **looping [`prompt()`](../reference/softcode.md#fn-prompt)
wizard** (the callback re-prompts until a sentinel word), documents as
spawned objects with per-page list attributes (`page_1`, `page_2`, ...),
sentinel words versus the prompt escape hatch,
[`escape()`](../reference/softcode.md#fn-escape) for player prose,
builtin *prefix* shadowing (`$read` can never fire), and `@set` as the
attribute editor for finished pages.

Builds on the [combination safe](016_combination_safe.md) (a single
`prompt()`) and the [camera](008_camera.md) (spawned keepsakes).

## How it works

**A wizard is a prompt that asks again.** One `prompt()` captures one
line into a callback (see the [wizards guide](../guides/wizards.md)),
with the answer bound as `arg0`. A *multi-line* wizard is the same
callback ending in another `prompt()`, so the loop runs until the player
types a sentinel word. Two sentinels here: `PAGE` (bump the sheet's page
counter, keep prompting) and `DONE` (release the roller). Anything else
is a line of prose, `escape()`d and appended to the current page. The
engine's own escape hatch stays open the whole time, because a line
starting with `help`, `quit`, or `exit` always falls through to the
dispatcher, so a half-typed memoir never traps anyone. And because an
abandoned wizard leaves a sheet clamped in the roller, `type` doubles as
*resume*: if a sheet is already loaded, it re-opens the prompt right
where the last typist stopped.

**The document is the state, the typewriter is the tool.** Each sheet is
a [`create_obj`](../reference/softcode.md#fn-create_obj)'d thing tagged
`document`, carrying `title`, a `pages` count, and one **list attribute
per page**: `page_1`, `page_2`, and so on. The typewriter holds only a
`sheet` pointer (the id in the roller) while writing; after `DONE` it
holds nothing. Sheets outlive the machine, travel in pockets, and can be
dropped, given, or locked in the [safe](016_combination_safe.md).

**Why `peruse` and not `read`?** Builtins dispatch before `$`-triggers;
the [vending machine](002_vending_machine.md) taught that with `buy`.
The sharper edge here is that the dispatcher also accepts *unambiguous
prefixes* of builtin names and aliases, and `read` is a prefix of
`ready`, the `wield` alias. So `read sheet` never reaches your trigger;
it answers "You aren't carrying 'sheet'." from the wield command. Check
both collisions, exact *and* prefix, before naming an object command.
`peruse`, `type`, and `sign` are clean.

**Signatures are one-shot.** `sign` appends a signature line to the last
page and stamps `signed_by`; a second signature is refused, and you must
be *holding* the document ([`loc(s)`](../reference/softcode.md#fn-loc)
`is enactor`, an object identity check, not a name check). Editing after
the fact is what the attribute editor is for: `@set` can rewrite any
`page_N` list, which is builder-side proofreading of player prose.

## Build it

The scripts here are `'''` multi-line blocks (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)).

The machine:

```text
@create brass typewriter
drop brass typewriter
```

**Load a sheet.** `type` either resumes or mints: a busy roller re-opens
the wizard where the last typist stopped, and a fresh title creates the
sheet, points the roller at it, and asks for the first line. The pattern
`$type *` requires an argument, so a bare `type` matches nothing and
falls through unmatched (a live server answers `Huh?`):

```text
@set brass typewriter/cmd_type = '''
$type *:
title = trim(arg0)
if V('sheet', ''):
    pemit(enactor, 'A sheet is already in the roller; you pick up where the last typist left off.')
    prompt(enactor, 'Next line (PAGE / DONE):', 'on_line')
else:
    s = create_obj(f'a typed sheet: {title}', tags=['thing', 'document'], location=enactor)
    if s:  # creating into a player's inventory needs authority over them; s is None without it
        set_attr(s, 'title', title)
        set_attr(s, 'pages', 1)
        set_attr(me, 'sheet', s.id)
        remit(here, f'{name(enactor)} feeds a fresh sheet into the brass typewriter.')
        prompt(enactor, 'The keys wait. Type a line (PAGE starts a new page; DONE pulls the sheet):', 'on_line')
'''
```

[`V('sheet', '')`](../reference/softcode.md#fn-v) reads the roller
pointer off the machine, [`trim`](../reference/softcode.md#fn-trim)
strips the typed title, [`pemit`](../reference/softcode.md#fn-pemit)
speaks to the typist alone, and
[`remit`](../reference/softcode.md#fn-remit) lets the whole room watch
the sheet go in. One quiet limit sits in the guard: `location=enactor`
drops the new sheet straight into the typist's hands, and putting an
object into a player's inventory is a mutation of that player, which
takes the machine's authority over them. A scripted object acts with its
owner's authority, so this typewriter mints for its owner (you); for
anyone else `create_obj` returns None and the `if s:` guard keeps the
machine silent. Anyone at all may still resume and finish a loaded
sheet, because writing touches only the sheet, and the machine owns
that.

**The wizard loop.** The callback looks up the sheet by its stored id,
checks the sentinels first, and otherwise appends the line: `DONE` (or a
sheet that has vanished mid-wizard) frees the roller, `PAGE` bumps the
page counter, and any other answer is `escape()`d prose appended to the
current page. [`get`](../reference/softcode.md#fn-get) with a
`#`-prefixed id is the exact lookup:

```text
@set brass typewriter/on_line = '''
s = get(f"#{V('sheet', '')}")
w = trim(arg0)
if s is None or w == 'DONE':
    set_attr(me, 'sheet', '')
    pemit(enactor, 'The platen ratchets back and you pull the finished sheet free.')
elif w == 'PAGE':
    n = get_attr(s, 'pages', 1)
    set_attr(s, 'pages', n + 1)
    prompt(enactor, f'A fresh page rolls in. [page {n + 1}] Next line (PAGE / DONE):', 'on_line')
else:
    n = get_attr(s, 'pages', 1)
    k = f'page_{n}'
    set_attr(s, k, get_attr(s, k, []) + [escape(arg0)])
    prompt(enactor, f'[page {n}] Next line (PAGE / DONE):', 'on_line')  # every live branch re-prompts: the re-ask IS the loop
'''
```

**Reading.** `peruse` finds the named document with `get()`, which
matches by name near the machine first and then anywhere in the world,
so the sheet in your hand and the sheet on the table both answer. The
[`has_tag`](../reference/softcode.md#fn-has_tag) check keeps it from
reciting the furniture, and every page prints in order under a
`--- page N ---` header:

```text
@set brass typewriter/cmd_peruse = '''
$peruse *:
s = get(trim(arg0))
if s is None or not has_tag(s, 'document'):
    pemit(enactor, 'There is no document by that name here.')
else:
    pemit(enactor, 'The type reads, page by page:')
    for p in range(1, get_attr(s, 'pages', 1) + 1):
        pemit(enactor, f'--- page {p} ---')
        for line in get_attr(s, f'page_{p}', []):
            pemit(enactor, str(line))  # str(): a hand-edited page may hold non-strings
'''
```

**Signing.** Held documents only, once only, witnessed by the room. The
signature is one more line appended to the last page, plus a `signed_by`
stamp that refuses a second signing:

```text
@set brass typewriter/cmd_sign = '''
$sign *:
s = get(trim(arg0))
if s is None or not has_tag(s, 'document') or loc(s) is not enactor:  # held means loc(s) is enactor: identity, so 'is', never '=='
    pemit(enactor, 'Hold the document you mean to sign.')
else:
    already = str(get_attr(s, 'signed_by', ''))
    if already:
        pemit(enactor, f'It already bears a signature: {already}.')
    else:
        k = f"page_{get_attr(s, 'pages', 1)}"
        set_attr(s, k, get_attr(s, k, []) + [f'Signed in a firm hand: {name(enactor)}'])
        set_attr(s, 'signed_by', name(enactor))
        remit(here, f'{name(enactor)} signs {name(s)} with a flourish.')
'''
```

## Try it

```text
> type Manifesto
Bilda feeds a fresh sheet into the brass typewriter.
The keys wait. Type a line (PAGE starts a new page; DONE pulls the sheet):

> All gadgets deserve softcode.
[page 1] Next line (PAGE / DONE):

> No exceptions.
[page 1] Next line (PAGE / DONE):

> PAGE
A fresh page rolls in. [page 2] Next line (PAGE / DONE):

> Draft two follows.
[page 2] Next line (PAGE / DONE):

> DONE
The platen ratchets back and you pull the finished sheet free.

> peruse typed sheet
The type reads, page by page:
--- page 1 ---
All gadgets deserve softcode.
No exceptions.
--- page 2 ---
Draft two follows.

> sign typed sheet
Bilda signs a typed sheet: Manifesto with a flourish.

> sign typed sheet
It already bears a signature: Bilda.
```

The room watches you feed the sheet in and later sign it with a
flourish, because both moments are `remit`s; after signing, `peruse`
ends with `Signed in a firm hand: Bilda` on the last page. Drop the
sheet and `sign` refuses with "Hold the document you mean to sign.",
since you must hold what you sign. Walk away mid-wizard and the next
person's `type` resumes your abandoned sheet; the roller does not care
whose fingers finish it. Typos? The attribute editor is right there:
`@set a typed sheet: Manifesto/page_1 = ["Corrected first line."]`.

## Going further

- **Documents readable anywhere:** at `DONE`, also
  `set_attr(s, 'cmd_peruse', ...)`. Triggers are scanned live from
  attributes, so a command *on the sheet itself* travels with it, no
  typewriter needed.
- **A cover for `look`:** stamp the sheet's `desc_extras` with its title
  and page count (the [camera](008_camera.md)'s workaround), so casual
  looks show the cover and `peruse` the contents.
- **Carbon copies:** `@clone` a finished sheet: attributes copy, so the
  duplicate is page-perfect; watermark it by appending to `page_1`.
- **Notarization:** `sign` could demand a forgery-proof: store
  `enactor.id` alongside the name and let a court gadget verify names
  against ids, because identity versus display text is softcode's
  oldest lesson.
