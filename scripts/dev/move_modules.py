#!/usr/bin/env python
"""
Move Python modules and rewrite every reference to them.

    python scripts/dev/move_modules.py moves.json [--dry-run]

``moves.json`` maps an old dotted module path to its new one:

    {"realm.systems.gurps": "realm.games.gurps.system",
     "realm.combat": "realm.std.combat"}

An old path may be a module (``x.py``) or a package (a directory). For each
move the script runs ``git mv`` (creating missing packages with an empty
``__init__.py``), then rewrites, across ``realm/``, ``tests/``, ``docs/``,
``examples/`` and ``scripts/`` (``realm/templates/`` included):

- dotted paths anywhere: ``from X import``, ``import X``, ``import X as``,
  string literals (``GAME_SYSTEM`` values, ``patch("realm....")`` targets),
  backticked paths in Markdown;
- ``from <parent> import <module>`` when ``<parent>.<module>`` moved;
- slash paths (``realm/systems/gurps.py``, ``realm/combat/``).

An old package left holding only its ``__init__.py`` is removed (no shims,
no re-exports). The script prints every file it changed, then every
occurrence of an old path it could not rewrite. ``docs/design/`` is
historical record and is not rewritten; its occurrences are only counted.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN = ["realm", "tests", "docs", "examples", "scripts"]
SUFFIXES = {".py", ".md", ".template", ".toml", ".cfg", ".ini", ".yml", ".yaml", ".txt"}
HISTORICAL = ROOT / "docs" / "design"


def to_path(dotted: str) -> Path:
    return ROOT.joinpath(*dotted.split("."))


def source_of(dotted: str) -> Path:
    """The file or package directory a dotted path names."""
    base = to_path(dotted)
    if base.is_dir():
        return base
    module = base.with_suffix(".py")
    if module.is_file():
        return module
    raise SystemExit(f"error: {dotted!r} is neither a module nor a package under {ROOT}")


def git(*args: str) -> None:
    subprocess.run(["git", *args], cwd=ROOT, check=True)


def ensure_package(directory: Path, created: list[Path]) -> None:
    """Make ``directory`` (and its parents up to ROOT) importable packages."""
    for d in [directory, *directory.parents]:
        if d == ROOT or ROOT not in d.parents:
            break
        d.mkdir(exist_ok=True)
        init = d / "__init__.py"
        if not init.exists():
            init.write_text("")
            created.append(init)


def scanned_files() -> list[Path]:
    out = []
    for top in SCAN:
        for p in (ROOT / top).rglob("*"):
            if (p.is_file() and p.suffix in SUFFIXES and "__pycache__" not in p.parts
                    and p != Path(__file__).resolve()):      # its own examples
                out.append(p)
    return out


def build_rewriters(moves: dict[str, str]):
    """One pass per form, longest old path first so a module move inside a
    moved package wins over the package."""
    olds = sorted(moves, key=len, reverse=True)
    dotted = re.compile(
        r"(?<![\w.])(" + "|".join(re.escape(o) for o in olds) + r")(?![\w])")

    def slash(o: str) -> str:
        return o.replace(".", "/")
    slashes = {slash(o): slash(n) for o, n in moves.items()}
    slash_re = re.compile(
        r"(?<![\w/])(" + "|".join(re.escape(s) for s in sorted(slashes, key=len, reverse=True))
        + r")(?=\.py\b|/|(?![\w]))")

    # from <parent> import <name>[, ...] where <parent>.<name> moved
    from_re = re.compile(r"^([ \t]*)from ([\w.]+) import ([^\n(]+)$", re.M)

    def rewrite(text: str) -> tuple[str, list[str]]:
        problems: list[str] = []

        def fix_from(m: re.Match) -> str:
            ind, parent, names = m.group(1), m.group(2), m.group(3)
            items = [n.strip() for n in names.split("#")[0].split(",") if n.strip()]
            moved = [n for n in items if f"{parent}.{n.split(' as ')[0]}" in moves]
            if not moved:
                return m.group(0)
            if len(moved) != len(items):
                problems.append(f"mixed import of moved submodules: {m.group(0).strip()}")
                return m.group(0)
            lines = []
            for item in items:
                name, _, alias = item.partition(" as ")
                new = moves[f"{parent}.{name.strip()}"]
                new_parent, _, new_name = new.rpartition(".")
                as_ = f" as {alias.strip()}" if alias else (
                    f" as {name.strip()}" if new_name != name.strip() else "")
                lines.append(f"{ind}from {new_parent} import {new_name}{as_}")
            return "\n".join(lines)

        text = from_re.sub(fix_from, text)
        text = dotted.sub(lambda m: moves[m.group(1)], text)
        text = slash_re.sub(lambda m: slashes[m.group(1)], text)
        return text, problems

    return rewrite, dotted, slash_re


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("moves", help="JSON file: old dotted path -> new dotted path")
    ap.add_argument("--dry-run", action="store_true", help="report, change nothing")
    args = ap.parse_args()
    moves: dict[str, str] = json.loads(Path(args.moves).read_text())

    sources = {old: source_of(old) for old in moves}
    old_packages = {sources[o].parent for o in moves if sources[o].is_file()}
    old_packages |= {sources[o].parent for o in moves if sources[o].is_dir()}

    created: list[Path] = []
    if not args.dry_run:
        for old, new in moves.items():
            src = sources[old]
            dest = to_path(new) if src.is_dir() else to_path(new).with_suffix(".py")
            if dest.exists():
                raise SystemExit(f"error: {dest.relative_to(ROOT)} already exists")
            ensure_package(dest.parent, created)
            git("mv", str(src.relative_to(ROOT)), str(dest.relative_to(ROOT)))
        for init in created:
            git("add", str(init.relative_to(ROOT)))

    rewrite, dotted, slash_re = build_rewriters(moves)
    changed: list[str] = []
    problems: list[str] = []
    historical = 0
    for path in scanned_files():
        text = path.read_text(encoding="utf-8")
        if HISTORICAL in path.parents:
            historical += len(dotted.findall(text)) + len(slash_re.findall(text))
            continue
        new, issues = rewrite(text)
        rel = str(path.relative_to(ROOT))
        problems += [f"{rel}: {i}" for i in issues]
        if new != text:
            changed.append(rel)
            if not args.dry_run:
                path.write_text(new, encoding="utf-8")

    # An old package left with nothing but __init__.py goes too.
    removed: list[str] = []
    for pkg in sorted(old_packages, key=lambda p: len(p.parts), reverse=True):
        if not pkg.is_dir() or pkg == ROOT:
            continue
        left = [p for p in pkg.rglob("*") if p.is_file() and p.name != "__init__.py"
                and "__pycache__" not in p.parts]
        if not left and (pkg / "__init__.py").exists():
            dotted_pkg = ".".join(pkg.relative_to(ROOT).parts)
            removed.append(dotted_pkg)
            if not args.dry_run:
                git("rm", "-q", "-f", str((pkg / "__init__.py").relative_to(ROOT)))
                shutil.rmtree(pkg)          # only caches are left

    # Anything still naming an old path (or a removed package) is reported.
    leftovers = list(moves) + removed
    left_re = re.compile(r"(?<![\w.])(" + "|".join(re.escape(o) for o in leftovers)
                         + r")(?![\w])")
    news = set(moves.values())
    token_re = re.compile(r"[\w.]+")

    def is_new(line: str, start: int) -> bool:
        # A new path may extend its old one (realm.games.gurps ->
        # realm.games.gurps.feature): that is not a leftover.
        token = token_re.match(line, start).group(0)
        return any(token == n or token.startswith(n + ".") for n in news)

    unrewritten: list[str] = []
    for path in scanned_files():
        if HISTORICAL in path.parents:
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if any(not is_new(line, m.start()) for m in left_re.finditer(line)):
                unrewritten.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()}")

    print(f"{'would change' if args.dry_run else 'changed'} {len(changed)} files:")
    for rel in changed:
        print(f"  {rel}")
    if created:
        print("created packages:", *(str(p.relative_to(ROOT)) for p in created), sep="\n  ")
    if removed:
        print("removed empty packages:", *removed, sep="\n  ")
    if historical:
        print(f"docs/design/ (not rewritten): {historical} occurrences")
    if problems or unrewritten:
        print("NOT REWRITTEN:")
        for line in problems + unrewritten:
            print(f"  {line}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
