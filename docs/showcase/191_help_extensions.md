# 191. Help system extensions

> Checklist item 191 — [now] — *auto-generated help, command metadata, in-world guides*

**What you'll build:** an understanding of REALM's self-writing `help`
command, and a small in-world **field guide** that documents your own
softcode verbs — the entries the engine's help can't know about.

**Concepts:** help generated from command registration metadata
(category / usage / help_text / aliases / docstring), permission-filtered
listings, the search fallback, and why builder content needs its own
guide (builtins dispatch before `$`-triggers).

## How it works

`help` is not a hand-written manual — it is **generated from the command
registry**. Every builtin registers with metadata:

```python
register("attack", cmd_attack, aliases=["kill", "att"],
         help_text="Attack someone (starts combat)",
         usage="attack <target>")
```

From that, `help` builds itself three ways (all covered by
`tests/test_help_and_details.py`):

- **`help`** — lists every command *you can see*, grouped by its
  registered `category` (`Combat:`, `Economy:`, `Movement:` …).
  Permission filters the list: a plain player never sees the `Building:`
  commands a builder does. Add a command with a new category and a new
  heading simply appears.
- **`help <command>`** — details one command from its metadata: its
  `aliases`, `usage`, `help_text`, and the handler's docstring. Nothing
  is duplicated; the help *is* the registration.
- **`help <word>`** — when nothing matches exactly, it searches names,
  aliases, and help text and offers the hits (`help merchant` →
  `Related: buy`).

The catch for builders: your content is **softcode `$`-commands on
objects**, and those are not in the command registry — they dispatch
*after* the builtins, precisely so they can never shadow `say` or `help`.
So `help` will never list your `sheet` or `scan` verb, and you can't add
an entry to it from in-game. The idiomatic fix is to document your verbs
where players already are: a **guide object** with its own lookup verb.
It mirrors the engine's idea — entries keyed by topic, one reader that
prints them — using a fresh verb (`guide`, not `help`, which the builtin
owns).

## Build it

A field guide that indexes and prints topic entries. Each topic is a
`topic_<name>` attribute; `index` is the list of topic names (softcode
can't enumerate an object's attributes, so the guide names its own
contents — the same "carry your own index" move the datapad's `skills`
list makes in [190](190_score_screen.md)):

```text
@create field guide
drop field guide
@set field guide/index = ["sheet", "map"]
@set field guide/topic_sheet = The datapad sheet verb prints your vitals at a glance: ST/DX/IQ/HT, a HP bar, and featured skills.
@set field guide/topic_map = Looking in a mapped room paints a small grid of the rooms around you. The @ marks where you stand.
```

Two verbs read it. Bare `guide` lists the index; `guide <topic>` prints
one entry, or points you back to the list if the topic is unknown:

```text
@set field guide/cmd_index = $guide: pemit(enactor, 'Guide topics: ' + ', '.join(get_attr(me, 'index', [])) + '. Type: guide <topic>.')
@set field guide/cmd_guide = $guide *: t = trim(arg0).lower(); body = get_attr(me, 'topic_' + t, ''); pemit(enactor, ansi('ch', capstr(t)) + '\n' + body) if body else pemit(enactor, 'No guide entry for ' + t + '. Try: guide')
```

The two patterns don't collide: `$guide` compiles to an exact match, so
it only fires on the bare word, while `$guide *` needs a trailing
argument. Together they behave like a mini `help`/`help <topic>` for your
own systems.

## Try it

The builtin help, unchanged and self-generated:

```text
> help
========================================
  Available Commands
========================================
Combat:
  attack, defend, firstaid, flee, ...
Movement:
  down, east, go, north, ...
...
> help attack
attack
  aliases: kill, att
  usage: attack <target>
  Attack someone (starts combat)
```

And your in-world guide, alongside it:

```text
> guide
Guide topics: sheet, map. Type: guide <topic>.
> guide map
Map
Looking in a mapped room paints a small grid of the rooms around you. The @ marks where you stand.
> guide compass
No guide entry for compass. Try: guide
```

## Going further

- **Cross-reference the builtins:** a topic body can tell the reader
  which native command to use (`See also: score`), tying your softcode
  docs into the engine's.
- **Room-local help:** put a guide in each hub room with topics about
  that area; because it is a dropped object, `guide` only works where the
  guide is — proximity-scoped documentation.
- **Category headings:** store `index` as a dict of `section -> [topics]`
  and have `$guide` print grouped headings, mirroring how the builtin
  groups by category.
- **Auto-index on set:** wrap topic creation in a `$addtopic * = *` verb
  that appends the name to `index` as it writes `topic_<name>`, so the
  guide and its index can never drift apart.
