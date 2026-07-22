# 020. Bookshelf

> Checklist item 20 — [now] — *$browse, contents() loops, tag filtering*

**What you'll build:** A walnut case that answers `browse` with a
numbered, alphabetized index of its books by *title* — and quietly
declines to catalogue the lost mitten someone stuffed between the
volumes.

**Concepts:** a `$`-command that presents a container's contents as
*data* — comprehension over `contents(me)`, `has_tag` filtering,
`sorted` with a key — and the tag-plus-attribute item convention: a
book is anything tagged `book`, its title one attribute, no two
objects needing to share anything else.

## How it works

**`look` lists objects; `browse` lists titles.** The stock `look`
shows a container's contents by object name — fine for a crate of
wrenches, wrong for a library, where players know titles. So the shelf
carries one `$browse` command that builds its own view: filter
`contents(me)` to things tagged `book`, sort by the `title` attribute
(falling back to the object's name, so an untitled folio still lists),
and print a numbered line per volume.

**One ordering, one source of truth.** The classic bug in hand-rolled
menus is two code paths sorting differently — the number a player
reads pointing at a different book when they use it. Here the sorted
list is built once per command; anything else the shelf grows (a
`$read <n>`, a `$pull <n>`) should call the same one-liner so the
index can never disagree with itself.

**A book is data, not code.** `@tag <thing> = book` plus
`@set <thing>/title = ...` makes anything shelvable — a spellbook from
another build, a shop ledger, a cursed diary. The shelf asks only
those two questions. Untagged objects still sit physically inside
(it's an ordinary container; `put` and `get from` work on everything)
— they're simply beneath the catalogue's notice.

## Build it

The case. Its description counts only the *books*, teaching the same
filter the command uses:

```text
@create walnut bookshelf
@tag walnut bookshelf = container
drop walnut bookshelf
@desc walnut bookshelf = A tall walnut case, shelves bowed under years of paper. [[n = len([o for o in contents(me) if has_tag(o, 'book')]); result = f'{n} volume' + ('' if n == 1 else 's') + ' stand in a ragged row. A card taped to the shelf reads: BROWSE.']]
```

The catalogue. Filter, sort by title, number the lines:

```text
@set walnut bookshelf/cmd_browse = $browse: books = sorted([o for o in contents(me) if has_tag(o, 'book')], key=lambda o: str(get_attr(o, 'title', name(o))).lower()); pemit(enactor, 'Spines on the shelf:' if books else 'The shelf holds nothing readable.'); [pemit(enactor, f"  {i + 1}. {get_attr(o, 'title', name(o))}") for i, o in enumerate(books)]
```

Stock it — three books and one interloper:

```text
@create dog-eared novel
@tag dog-eared novel = book
@set dog-eared novel/title = The Gullwater Wreck
put dog-eared novel in walnut bookshelf
@create thick cookbook
@tag thick cookbook = book
@set thick cookbook/title = Ninety Soups
put thick cookbook in walnut bookshelf
@create ships atlas
@tag ships atlas = book
@set ships atlas/title = An Atlas of Drowned Coasts
put ships atlas in walnut bookshelf
@create lost mitten
put lost mitten in walnut bookshelf
```

## Try it

```text
browse
```

answers:

```text
Spines on the shelf:
  1. An Atlas of Drowned Coasts
  2. Ninety Soups
  3. The Gullwater Wreck
```

Alphabetical by title, not by name or arrival order — and no mitten.
`look walnut bookshelf` reads `3 volumes stand in a ragged row` (the
description runs the same filter), while the plain contents list below
it still betrays the mitten to a sharp eye. Take the cookbook down
(`get thick cookbook from walnut bookshelf`), browse again: two
volumes, renumbered, still sorted.

## Going further

- **`$read <n>`:** rebuild the same sorted list, index it with
  `int(trim(arg0)) - 1`, and pemit the book's `text` attribute — the
  number the player just read in `browse` is guaranteed to match.
- **Shelve-only ward:** an `on_check` that blocks `item:on_put` for
  anything not tagged `book` turns the shelf from tolerant to typed —
  that ward is [021](021_ammo_pouch.md), verbatim, with a different
  tag.
- **A card catalogue:** the same comprehension over
  `search_world(tag='book')` lists every book in the *game*; scope is
  just which container you fold over.
- **Series order:** store a `shelf_order` number and sort by
  `(get_attr(o, 'shelf_order', 999), title)` — librarians have
  opinions alphabets can't express.
