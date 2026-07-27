# 169. Zone mass-edit

> Checklist item 169 ([now]): *zone_rooms() queries, dry-run discipline, apply-to-commit*

**What you'll build:** a `retheme <zone>` verb that sweeps every room in
a zone and reports **what it would change** (a dry run), and only touches
the world when you add the `apply` keyword. It is the safe way to edit
fifty rooms at once. The warden that carries the verb is a builder-owned
tool, so it writes under builder authority.

**Concepts:** [`zone_rooms()`](../reference/softcode.md#fn-zone_rooms) as the
target set, the **dry-run-first** discipline (echo the plan, commit only on
`apply`), and [`set_attr`](../reference/softcode.md#fn-set_attr) across a whole
zone in one pass, which is softcode's answer to a bulk editor with a preview.

## How it works

The finished tool is a single verb, `retheme`, that runs in two modes off
one code path. Typed bare (`retheme chapel`) it names every change it would
make and writes nothing; typed with the `apply` keyword (`retheme apply
chapel`) it makes those exact changes. This section answers three questions:
how the verb finds its targets, why the default is a dry run, and how one
verb carries both modes without drifting apart.

### How the verb finds its targets

`zone_rooms('chapel')` returns every room tagged `zone:chapel`, so a loop
over it is your batch. Membership is the tag, which means a room added to
the zone later is picked up automatically on the next sweep and you never
maintain a list. The `@zone here = chapel` command in the build is what
stamps that tag onto a room.

### Why the default is a dry run

Mass edits are exactly where a typo becomes fifty typos, so the verb's
*default* behavior is to **describe** each change ("would set ambient on
Nave") and mutate nothing. Only `retheme apply chapel` actually writes. The
preview and the commit share one loop, so what you saw in the dry run is
exactly what you get when you apply it.

### How one verb carries both modes

The verb is a `$`-command stored in the warden's `cmd_retheme` attribute (a
[command trigger](../reference/softcode.md#triggers-attributes-on-objects)),
and the whole typed argument arrives as `arg0`. It
[`trim`](../reference/softcode.md#fn-trim)s that argument and splits it on
spaces, treats the first word as the mode flag and the last word as the zone
name, then loops over `zone_rooms(zone)`. Each iteration branches on the
flag: the commit path calls `set_attr` and confirms by
[`name`](../reference/softcode.md#fn-name), while the preview path only
reports with [`pemit`](../reference/softcode.md#fn-pemit).

This is the softcode sibling of the native `@foreach`
([batchcode areas](166_batchcode_areas.md)): `@foreach` is the
fire-and-forget bulk command, and a `retheme`-style verb is what you build
when the edit deserves a look before you commit.

## Build it

Dig two rooms and tag both into the same zone:

```text
@dig Nave = nave, back
nave
@zone here = chapel
@dig Crypt = crypt, up
crypt
@zone here = chapel
up
```

Create the warden and drop it where builders can reach it:

```text
@create warden
drop warden
```

Now the dual-mode sweep. It splits `arg0`, reads the first word as the mode
and the last word as the zone, prints a header, then loops the zone's rooms
and either previews or commits each one:

```text
@set warden/cmd_retheme = '''
$retheme *:
parts = trim(arg0).split(' ')
apply = parts[0] == 'apply'
zone = parts[-1]  # zone is the last word, so 'chapel' and 'apply chapel' both parse
rooms = zone_rooms(zone)
header = 'APPLYING to ' if apply else 'DRY RUN over '
pemit(enactor, header + str(len(rooms)) + ' rooms in ' + zone + ':')
for r in rooms:
    if apply:
        set_attr(r, 'ambient', 'Candlewax and cold stone.')
        pemit(enactor, '  set ambient on ' + name(r))
    else:
        pemit(enactor, '  would set ambient on ' + name(r))
'''
```

## Try it

```text
> retheme chapel
  DRY RUN over 2 rooms in chapel:
    would set ambient on Nave
    would set ambient on Crypt
```

Nothing changed: `@examine Nave` shows no `ambient` yet. Now commit:

```text
> retheme apply chapel
  APPLYING to 2 rooms in chapel:
    set ambient on Nave
    set ambient on Crypt
```

Both rooms now carry the attribute. Because the target is `zone_rooms()`,
tagging a third room into `chapel` and re-running picks it up with no edit
to the verb.

## Going further

- **Edit anything:** swap the `set_attr` for
  [`add_tag(r, 'sanctified')`](../reference/softcode.md#fn-add_tag), a
  `desc_extras` stamp, or an `@behavior` attach. The dry-run scaffold is the
  reusable part.
- **Targeted sweeps:** filter the loop, for example skip rooms carrying an
  `outdoors` tag with
  [`has_tag`](../reference/softcode.md#fn-has_tag), to retheme only interiors.
- **Undo-friendly:** stamp the *old* value into a `prev_ambient` attribute as
  you overwrite, and a `retheme revert` mode reads it back, giving you a poor
  builder's transaction log.
- **Fire-and-forget:** when a preview is unnecessary, the native
  `@foreach tag:zone:chapel = @set %o/ambient = ...` commits the same edit in
  one line. See [batchcode areas](166_batchcode_areas.md).
```