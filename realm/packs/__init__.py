"""
Content packs — importable bundles of *data*, not code.

Because skills, classes, equipment, and areas are all ordinary worldio
JSON (Stages A–C made the game data), a "pack" is nothing more than a
directory of those files. You import a whole pack, or one file at a time —
"import the sci-fi pack" and "import just the hacker class" are the same
``import_objects`` under the hood.

Built-in packs live in ``realm/packs/<name>/`` with a ``pack.json``
manifest (name, description, files) and one or more worldio ``.json``
files. Third-party packs are just directories a game points at.
"""

from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def packs_root() -> Path:
    return _ROOT


def _pack_dir(name: str) -> Path:
    # Guard against path escapes — a pack name is a single directory.
    if "/" in name or "\\" in name or name in ("", ".", ".."):
        raise ValueError(f"invalid pack name: {name!r}")
    return _ROOT / name


def list_packs() -> list[str]:
    """Names of the built-in packs (directories carrying a pack.json)."""
    return sorted(
        p.name for p in _ROOT.iterdir()
        if p.is_dir() and (p / "pack.json").exists()
    )


def pack_manifest(name: str) -> dict:
    """A pack's manifest (name, description, files)."""
    manifest = _pack_dir(name) / "pack.json"
    if not manifest.exists():
        raise FileNotFoundError(f"no such pack: {name}")
    return json.loads(manifest.read_text())


def pack_files(name: str) -> list[Path]:
    """The worldio data files in a pack, in import order (manifest order if
    given, else every ``.json`` except the manifest, sorted). Manifest
    entries are confined to the pack directory — a `files` entry can't
    escape it (the same guard the pack name gets)."""
    directory = _pack_dir(name)
    root = directory.resolve()
    manifest = pack_manifest(name)
    listed = manifest.get("files")
    if listed:
        out = []
        for f in listed:
            path = (directory / f).resolve()
            if not path.is_relative_to(root):
                raise ValueError(f"pack file escapes its pack directory: {f!r}")
            out.append(path)
        return out
    return sorted(p for p in directory.glob("*.json") if p.name != "pack.json")


async def import_file(path: Path, persistence) -> list:
    """À-la-carte: import a single worldio file (fresh ids, refs remapped)."""
    from realm.persistence.worldio import import_objects
    data = json.loads(Path(path).read_text())
    return await import_objects(data, persistence)


_DEF_TAGS = ("class_def", "skill_def")


async def import_pack(name: str, persistence) -> list:
    """
    Import every data file in a pack. Returns all newly-created objects.

    Idempotent for *definitions*: re-importing a pack skips any
    ``class_def`` / ``skill_def`` whose name already exists, so you don't
    accumulate duplicate class/skill objects (whose name-keyed readers
    would otherwise collide). Other content (equipment, areas) imports as
    fresh copies, like any worldio import.
    """
    from realm.core.query import find_objects
    from realm.persistence.worldio import import_objects

    present = {(tag, obj.name.strip().lower())
               for tag in _DEF_TAGS for obj in find_objects(tag=tag)}

    created = []
    for path in pack_files(name):
        data = json.loads(path.read_text())
        kept = []
        for obj in data.get("objects", []):
            tags = obj.get("tags", [])
            key = next(((t, str(obj.get("name", "")).strip().lower())
                        for t in _DEF_TAGS if t in tags), None)
            if key is not None:
                if key in present:
                    continue                 # already defined — skip (idempotent)
                present.add(key)
            kept.append(obj)
        created.extend(await import_objects({**data, "objects": kept}, persistence))
    return created


__all__ = [
    "packs_root",
    "list_packs",
    "pack_manifest",
    "pack_files",
    "import_file",
    "import_pack",
]
