# How-To: Content Packs

Because skills, classes, equipment, and areas are all just data (see
[Skills & Classes as Data](data-driven-rules.md)), a **pack** is nothing
more than a directory of importable files. "Import the sci-fi pack",
"import one class", and "import Midgaard" are the *same* operation — a
worldio import. A pack is a curated bundle you can take whole or à la
carte.

## Use a pack

Built-in packs ship with the engine. List and import from the CLI:

```bash
realm pack list
realm pack import gurps-scifi
```

…or in-game (builder-gated):

```text
@pack                 # list the packs
@pack gurps-scifi     # import it — classes and skills go live immediately
```

Importing `gurps-scifi` adds six classes (pilot, marine, engineer, medic,
merchant, scout), the ship/combat skills they use, and some gear — all as
data. The classes **merge** with whatever's already there, so a fresh
GURPS game gains them alongside its built-ins, and a new character can be
created as a `pilot` right away.

## À la carte

A pack is a folder of worldio files, so you can import just one:

```bash
realm import realm/packs/gurps-scifi/classes.json   # only the classes
```

Skills, classes, and equipment are separate files precisely so you can
take what you want and leave the rest.

## What's in a pack

```
realm/packs/gurps-scifi/
    pack.json        # manifest: name, description, file order
    skills.json      # skill_def objects
    classes.json     # class_def objects
    equipment.json   # prototype objects
```

Each `.json` is ordinary worldio export data (`{"realm_format": 1,
"objects": [...]}`) — the same format `@export` / `realm export` produce.

## Author your own pack

Make a directory with a `pack.json` and one or more worldio files. The
easy way to produce the data is to build it in-game or in Python and
`@export` / `realm export` it, or use the `realm.systems.definitions`
builders (`define_skill`, `define_class`) with the exporter — see
`scripts/build_scifi_pack.py`, which generates the sci-fi pack. Then it
imports like any other pack. A third-party pack is just a directory a game
points at; nothing about it is special code.
