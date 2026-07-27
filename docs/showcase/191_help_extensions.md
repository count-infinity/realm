# 191. Help system extensions

> Checklist item 191 ([now]): *auto-generated help, command metadata, in-world guides*

**What you'll build:** an understanding of REALM's self-writing `help`
command, plus a small in-world **field guide** that documents your own
softcode verbs, the entries the engine's help has no view into.

**Concepts:** help generated from command registration metadata
(category / usage / help_text / aliases / docstring), permission-filtered
listings, the search fallback, and why builder content needs its own
guide (builtins dispatch before `$`-triggers).

## How it works

`help` is not a hand-written manual. It is **generated from the command
registry**: every builtin registers with metadata, and `help` reads that
metadata back out. A registration looks like this in the engine:

```text
register("attack", cmd_attack, aliases=["kill", "att"],
         help_text="Attack someone (starts combat)",
         usage="attack <target>")
```

From that one record, `help` builds itself three ways:

- **`help`** lists every command *you can see*, grouped by its
  registered `category` (`Combat:`, `Economy:`, `Movement:` and so on).
  Permission filters the list, since the lister only keeps commands whose
  permission you pass, so a plain player never sees the `Building:`
  commands a builder does. Register a command under a fresh category and a
  new heading appears on its own.
- **`help <command>`** details one command from its metadata: its
  `aliases`, `usage`, `help_text`, and the handler's docstring. Nothing is
  duplicated, because the help *is* the registration.
- **`help <word>`** falls back to search when nothing matches exactly. It
  scans command names, aliases, and help text, then offers the hits
  (`help merchant` answers `Related: buy, list, sell`).

The catch for builders is that your own content lives in softcode
`$`-commands on objects, and those never enter the command registry. They
dispatch *after* the builtins (the dispatcher tries builtins, aliases,
prefixes, and exits first, then hands unmatched input to softcode),
precisely so a `$`-command can never shadow `say` or `help`. One
consequence is that `help` has no view into your `sheet` or `scan` verb,
and there is no in-game way to add an entry to it. The idiomatic fix is to
document your verbs where players already are: a **guide object** with its
own lookup verb. It mirrors the engine's idea, entries keyed by topic and
one reader that prints them, using a fresh verb (`guide`, since the builtin
owns `help`).

## Build it

Start with the object itself. Create the field guide and drop it, so its
`$`-commands are live for anyone standing in the room:

```text
@create field guide
drop field guide
```

Now give it its contents. Each topic is a `topic_<name>` attribute, and
`index` is the list of topic names. REALM offers no primitive that lists an
object's attribute names, so the guide names its own contents in `index`,
the same carry-your-own-index move the datapad's `skills` list makes in
[190](190_score_screen.md). These are data values, not scripts, so each is
a single-line `@set`:

```text
@set field guide/index = ["sheet", "map"]
@set field guide/topic_sheet = The datapad sheet verb prints your vitals at a glance: ST/DX/IQ/HT, a HP bar, and featured skills.
@set field guide/topic_map = Looking in a mapped room paints a small grid of the rooms around you. The @ marks where you stand.
```

Bare `guide` lists the index. It is one statement, so it stays a one-liner:
it reads `index` with [`V`](../reference/softcode.md#fn-v) and sends the
line with [`pemit`](../reference/softcode.md#fn-pemit), which delivers after
the script returns.

```text
@set field guide/cmd_index = $guide: pemit(enactor, 'Guide topics: ' + ', '.join(V('index', [])) + '. Type: guide <topic>.')
```

`guide <topic>` prints one entry, or points back to the list when the topic
is unknown. It normalises the argument with
[`trim`](../reference/softcode.md#fn-trim), reads the matching
`topic_<name>`, and branches on whether that body exists, capitalising the
heading with [`capstr`](../reference/softcode.md#fn-capstr) and colouring it
with [`ansi`](../reference/softcode.md#fn-ansi). The branch makes this a
multi-line script, so it is a `'''` heredoc with a real `if`/`else`:

```text
@set field guide/cmd_guide = $guide *:'''
t = trim(arg0).lower()
body = V('topic_' + t, '')
if body:
    pemit(enactor, f'{ansi("ch", capstr(t))}\n{body}')
else:
    pemit(enactor, f'No guide entry for {t}. Try: guide')
'''
```

The two verbs never collide, because `$guide` compiles to an exact match
and fires only on the bare word, while `$guide *` needs a trailing
argument. Together they behave like a mini `help` / `help <topic>` for your
own systems. A `$`-command takes no `target` guard: it fires for the
enactor who typed it, not once per object in the room, and a second field
guide dropped alongside the first still answers `guide` only once.

## Try it

The builtin help, unchanged and self-generated. The compass directions land
under `General:`, while `Movement:` holds the verbs that are not directions:

```text
> help
========================================
  Available Commands
========================================

Building:
  @areas, @attr, @behavior, @clone, @create, @desc, ...

Combat:
  attack, combat, defend, firstaid, flee, queue, ...

General:
  down, east, north, northeast, south, up, west, ...

Movement:
  go, in, out
...
help <command> for details; help <word> searches help text.
> help attack
attack
  aliases: kill, att
  usage: attack <target>
  Attack someone (starts combat)

  Attack someone — starts combat, or switches your target in a fight.

  Usage: attack <target>
  kill <target>

  Example:
  attack thug
> help merchant
No command 'merchant'. Related: buy, list, sell
```

And your in-world guide, alongside it. The topic heading prints in bright
cyan (the `ansi("ch", ...)` header), and an unknown topic points you back:

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

- **Cross-reference the builtins:** a topic body can tell the reader which
  native command to use (`See also: score`), tying your softcode docs into
  the engine's.
- **Room-local help:** put a guide in each hub room with topics about that
  area. Because it is a dropped object, `guide` answers only where the guide
  is, giving you proximity-scoped documentation.
- **Category headings:** store `index` as a dict of `section -> [topics]`
  and have `$guide` print grouped headings, mirroring how the builtin groups
  by category.
- **Auto-index on set:** wrap topic creation in a `$addtopic * = *` verb that
  appends the name to `index` as it writes `topic_<name>`, so the guide and
  its index stay in step.
