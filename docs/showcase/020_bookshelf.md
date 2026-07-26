# 020. Bookshelf

> Checklist item 20 ([now]): *$browse, contents() loops, tag filtering*

**What you'll build:** A walnut case that answers `browse` with a numbered,
alphabetized index of its books by *title*, and quietly declines to catalogue
the lost mitten someone stuffed between the volumes.

**Concepts:** a `$`-command that presents a container's contents as *data*,
built from a comprehension over [`contents(me)`](../reference/softcode.md#fn-contents),
[`has_tag`](../reference/softcode.md#fn-has_tag) filtering, and `sorted` with a
key. It also teaches the tag-plus-attribute item convention: a book is anything
tagged `book`, its title one attribute, with no two objects needing to share
anything else.

It builds the same `$browse` idea as the [vending machine](002_vending_machine.md),
but over the container's live contents instead of a fixed menu, so the list
changes as books come and go.

## How it works

A bookshelf is an ordinary [container](014_basic_container.md) that grows one
extra command. That command, `browse`, filters the shelf's contents down to
books, sorts them by title, and prints a numbered index. This section covers why
`browse` exists next to `look`, how the sorted list stays honest, and why a book
is nothing more than a tag and an attribute.

### Why browse when look already lists contents

The stock `look` shows a container's contents by object name, which is fine for
a crate of wrenches but wrong for a library, where players know titles, not
object names. So the shelf carries one `$browse` command that builds its own
view: it filters [`contents(me)`](../reference/softcode.md#fn-contents) to things
tagged `book`, reads each title with [`get_attr`](../reference/softcode.md#fn-get_attr)
(falling back to the object's [`name`](../reference/softcode.md#fn-name) so an
untitled folio still lists), sorts on that, and prints a numbered line per volume
with [`pemit`](../reference/softcode.md#fn-pemit).

### One ordering, one source of truth

The classic bug in a hand-rolled menu is two code paths that sort differently,
so the number a player reads points at a different book when they use it. Here
the sorted list is built once per command, so anything else the shelf grows (a
`$read <n>`, a `$pull <n>`) should reuse that same `sorted(...)` line, and the
index can never disagree with itself.

### A book is data, not code

`@tag <thing> = book` plus `@set <thing>/title = ...` makes anything shelvable,
whether it is a spellbook from another build, a shop ledger, or a cursed diary.
The shelf asks only those two questions. Untagged objects still sit physically
inside, because it is an ordinary container and `put` and `get from` work on
everything; they are simply beneath the catalogue's notice.

## Build it

The case carries a living description that counts only the *books*, running the
same book filter the command does, so `look` and `browse` always agree on how
many volumes there are:

```text
@create walnut bookshelf
drop walnut bookshelf
@desc walnut bookshelf = A tall walnut case, shelves bowed under years of paper. [[n = len([o for o in contents(me) if has_tag(o, 'book')]); result = f'{n} volume' + ('' if n == 1 else 's') + ' stand in a ragged row. A card taped to the shelf reads: BROWSE.']]
```

The `container` tag switches on the built-in `put` and `get from` verbs, the
same machinery the [basic container](014_basic_container.md) uses; `container`
is a tag, not an attribute:

```text
@tag walnut bookshelf = container
```

The catalogue is one `$browse` command, written as a `'''` multi-line block (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)). Its
steps in order: filter the contents to books, sort them by title, then print a
numbered line each:

```text
@set walnut bookshelf/cmd_browse = '''
$browse:
# filter to books, then sort by title (case-insensitive; an untitled book falls back to its object name)
books = sorted([o for o in contents(me) if has_tag(o, 'book')], key=lambda o: str(get_attr(o, 'title', name(o))).lower())
pemit(enactor, 'Spines on the shelf:' if books else 'The shelf holds nothing readable.')
for i, o in enumerate(books):
    pemit(enactor, f"  {i + 1}. {get_attr(o, 'title', name(o))}")  # i + 1 numbers the list from 1, not 0
'''
```

Stock the shelf with three books and one interloper. Each book is tagged `book`
and carries a `title`; the mitten gets neither, so the catalogue ignores it while
it still sits physically on the shelf:

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

Alphabetical by title, not by name or arrival order, and no mitten.
`look walnut bookshelf` reads `3 volumes stand in a ragged row` because the
description runs the same filter, while the plain contents list below it still
betrays the mitten to a sharp eye. Take the cookbook down with `get thick
cookbook from walnut bookshelf`, then browse again: two volumes, renumbered,
still sorted.

## Going further

- **`$read <n>`:** rebuild the same sorted list, index it with
  `int(trim(arg0)) - 1`, and pemit the book's `text` attribute, so the number
  the player just read in `browse` is guaranteed to match.
- **Shelve-only ward:** an `on_check` that blocks `item:on_put` for anything not
  tagged `book` turns the shelf from tolerant to typed. That ward is the
  [ammo pouch](021_ammo_pouch.md), verbatim, with a different tag.
- **A card catalogue:** the same comprehension over
  [`search_world(tag='book')`](../reference/softcode.md#fn-search_world) lists
  every book in the *game*; scope is just which container you fold over.
- **Series order:** store a `shelf_order` number and sort by
  `(get_attr(o, 'shelf_order', 999), title)`, because librarians have opinions
  alphabets cannot express.
