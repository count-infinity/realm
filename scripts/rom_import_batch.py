#!/usr/bin/env python3
"""
Batch-convert a directory tree of ROM ``.are`` files and report parity.

Runs ``rom_import.convert`` over every ``*.are`` / ``*.are.txt`` under a
root, writes each area's REALM JSON to an output tree, and aggregates:

- per-area stats (rooms / exits / mob & object prototypes / placed
  instances) and any parse failure,
- every capability-gap message and how many areas hit it,
- the distinct ROM features that have no MERC equivalent yet — special
  procedures (``rom_spec:*``), item types, and whether mob/obj programs
  appear — so the output is a punch list for reaching Diku parity.

    python scripts/rom_import_batch.py areas/ -o converted/ --report parity.md
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import traceback
from collections import Counter
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "rom_import", Path(__file__).resolve().parent / "rom_import.py")
rom_import = importlib.util.module_from_spec(_SPEC)
sys.modules["rom_import"] = rom_import
_SPEC.loader.exec_module(rom_import)


def _iter_areas(root: Path):
    for pat in ("*.are", "*.are.txt"):
        yield from sorted(root.rglob(pat))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", help="directory of .are/.are.txt files")
    ap.add_argument("-o", "--output", help="write converted JSON here")
    ap.add_argument("--report", help="write a parity report (markdown) here")
    args = ap.parse_args(argv)

    root = Path(args.root)
    out = Path(args.output) if args.output else None
    files = list(_iter_areas(root))

    ok, failed = 0, 0
    totals = Counter()
    gap_area_counts = Counter()      # gap message -> number of areas hitting it
    gap_total_counts = Counter()     # gap message -> total occurrences
    specs = Counter()                # spec_proc name -> areas
    item_types = Counter()           # item type -> objects
    mobprog_areas = 0
    failures: list[tuple[str, str]] = []
    per_area: list[dict] = []

    for path in files:
        rel = path.relative_to(root)
        try:
            text = path.read_text(errors="replace")
            area = rom_import.convert(text)
        except Exception as exc:                 # noqa: BLE001 — report, don't crash
            failed += 1
            failures.append((str(rel), f"{type(exc).__name__}: {exc}"))
            traceback.print_exc(file=sys.stderr)
            continue
        ok += 1

        rooms = sum(1 for o in area.objects if "room" in o["tags"])
        exits = sum(1 for o in area.objects if "exit" in o["tags"])
        placed = sum(1 for o in area.objects
                     if o["attrs"].get("prototype_vnum") is not None)
        totals["rooms"] += rooms
        totals["exits"] += exits
        totals["mob_protos"] += len(area.mob_protos)
        totals["obj_protos"] += len(area.obj_protos)
        totals["placed"] += placed
        per_area.append({"area": str(rel), "name": area.name, "rooms": rooms,
                         "exits": exits, "mobs": len(area.mob_protos),
                         "objs": len(area.obj_protos), "placed": placed})

        seen_specs = set()
        for msg, count in area.gaps.items():
            gap_area_counts[msg] += 1
            gap_total_counts[msg] += count
            if "MOBPROGS" in msg or "OBJPROGS" in msg:
                pass
        if any("PROGS" in m for m in area.gaps):
            mobprog_areas += 1
        for o in area.objects:
            for t in o["tags"]:
                if t.startswith("rom_spec:"):
                    name = t.split(":", 1)[1]
                    if name not in seen_specs:
                        specs[name] += 1
                        seen_specs.add(name)
            it = o["attrs"].get("item_type")
            if it and "prototype" in o["tags"]:
                item_types[it] += 1

        if out is not None:
            dest = (out / rel).with_suffix("")     # drop .txt
            if dest.suffix != ".json":
                dest = dest.with_suffix(".json")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(
                {"realm_format": 1, "objects": area.objects}, indent=2))

    # --- console summary ---
    print(f"[batch] {ok} converted, {failed} failed of {len(files)} files",
          file=sys.stderr)
    print(f"[batch] totals: {totals['rooms']} rooms, {totals['exits']} exits, "
          f"{totals['mob_protos']} mobs, {totals['obj_protos']} objects, "
          f"{totals['placed']} placed", file=sys.stderr)

    lines = _report(len(files), ok, failed, totals, gap_area_counts,
                    gap_total_counts, specs, item_types, mobprog_areas,
                    failures)
    if args.report:
        Path(args.report).write_text("\n".join(lines) + "\n")
        print(f"[batch] parity report -> {args.report}", file=sys.stderr)
    else:
        print("\n".join(lines))
    return 0


def _report(n, ok, failed, totals, gap_areas, gap_totals, specs, item_types,
            mobprog_areas, failures) -> list[str]:
    lines = ["# ROM -> REALM batch conversion & MERC parity report", "",
         f"Converted **{ok}/{n}** area files"
         + (f" ({failed} failed)" if failed else "") + ". World totals: "
         f"**{totals['rooms']} rooms, {totals['exits']} exits, "
         f"{totals['mob_protos']} mob prototypes, {totals['obj_protos']} "
         f"object prototypes, {totals['placed']} placed instances**.", ""]

    lines += ["## Capability gaps, by how many areas hit them", "",
          "| areas | occurrences | gap |", "|---:|---:|---|"]
    for msg, areas in gap_areas.most_common():
        lines.append(f"| {areas} | {gap_totals[msg]} | {msg} |")

    lines += ["", "## ROM special procedures found (no MERC equivalent)", "",
          f"{sum(specs.values())} spec-proc attachments across "
          f"{len(specs)} distinct procedures. Each is a compiled C behavior "
          "that must be re-authored as softcode or a behavior:", "",
          "| areas | spec_proc |", "|---:|---|"]
    for name, areas in specs.most_common(40):
        lines.append(f"| {areas} | `{name}` |")
    if mobprog_areas:
        lines += ["", f"Plus **{mobprog_areas}** areas carry MOBprogs/OBJprogs "
              "(ROM's trigger scripting) — skipped, portable to softcode."]

    lines += ["", "## Object item types seen (parity of the item model)", "",
          "| count | item type | MERC status |", "|---:|---|---|"]
    known = {"weapon", "armor", "light", "food", "drink", "drink_container",
             "container", "key", "money", "potion", "scroll", "wand", "staff",
             "treasure", "clothing", "trash", "furniture", "fountain", "pill",
             "jewelry", "boat"}
    for it, count in item_types.most_common():
        status = "modeled (tag + attrs)" if it in known else "**no MERC hook**"
        lines.append(f"| {count} | `{it}` | {status} |")

    if failures:
        lines += ["", "## Parse failures", ""]
        for name, err in failures:
            lines.append(f"- `{name}` — {err}")
    return lines


if __name__ == "__main__":
    raise SystemExit(main())
