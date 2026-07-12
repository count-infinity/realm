"""
Generate the built-in ``gurps-scifi`` content pack as importable data.

A pack is just worldio JSON — classes, skills, and equipment expressed as
tagged objects (the Stage A/D payoff: content is data, not Python). This
script authors that content once via the definitions API and the exporter,
so the shipped files are guaranteed to be valid worldio format. Re-run to
regenerate:  python scripts/build_scifi_pack.py
"""

from __future__ import annotations

import json
from pathlib import Path

from realm.core.objects import GameObject
from realm.persistence.worldio import export_objects
from realm.systems.definitions import define_class, define_skill

PACK = Path(__file__).resolve().parent.parent / "realm" / "packs" / "gurps-scifi"

# --- Skills: name -> (governing attribute, untrained penalty) ----------------
SKILLS = {
    "piloting": ("dexterity", -4),
    "gunnery": ("dexterity", -4),
    "navigation": ("intelligence", -4),
    "sensors": ("intelligence", -5),
    "engineering": ("intelligence", -5),
    "electronics": ("intelligence", -5),
    "mechanics": ("intelligence", -5),
    "computers": ("intelligence", -4),
    "medicine": ("intelligence", -5),
    "surgery": ("intelligence", -6),
    "diagnosis": ("intelligence", -5),
    "first_aid": ("intelligence", -4),
    "tactics": ("intelligence", -5),
    "survival": ("intelligence", -4),
    "tracking": ("intelligence", -5),
    "merchant": ("intelligence", -5),
    "diplomacy": ("intelligence", -5),
    "detect_lies": ("intelligence", -6),
    "streetwise": ("intelligence", -5),
    "ranged": ("dexterity", -4),
    "melee": ("dexterity", -4),
    "stealth": ("dexterity", -5),
    "observation": ("intelligence", -5),
}

# --- Classes: name -> (blurb, stats, skills) ---------------------------------
CLASSES = {
    "pilot": ("expert flyer, master of evasion (DX 12; piloting, navigation)",
              {"strength": 10, "dexterity": 12, "intelligence": 11, "health": 10},
              {"piloting": 14, "navigation": 12, "sensors": 11, "ranged": 10}),
    "marine": ("shipboard combat specialist (ST 12, HT 12; guns, tactics)",
               {"strength": 12, "dexterity": 11, "intelligence": 10, "health": 12},
               {"melee": 13, "ranged": 14, "tactics": 11, "first_aid": 10}),
    "engineer": ("keeps the ship running (IQ 13; engineering, electronics)",
                 {"strength": 10, "dexterity": 11, "intelligence": 13, "health": 10},
                 {"engineering": 14, "electronics": 13, "mechanics": 13, "computers": 12}),
    "medic": ("field surgeon (IQ 13; medicine, surgery)",
              {"strength": 10, "dexterity": 12, "intelligence": 13, "health": 10},
              {"medicine": 14, "first_aid": 13, "surgery": 12, "diagnosis": 12}),
    "merchant": ("trader and negotiator (IQ 12; merchant, diplomacy)",
                 {"strength": 10, "dexterity": 10, "intelligence": 12, "health": 10},
                 {"merchant": 14, "diplomacy": 13, "detect_lies": 12, "streetwise": 11}),
    "scout": ("recon and survival (DX 12; stealth, observation)",
              {"strength": 10, "dexterity": 12, "intelligence": 11, "health": 10},
              {"stealth": 13, "observation": 14, "survival": 12, "ranged": 12}),
}


def _equipment() -> list[GameObject]:
    def item(name, desc, tags, **attrs):
        obj = GameObject(name=name, description=desc,
                         tags=["thing", "equipment", *tags])
        for k, v in attrs.items():
            obj.db.set(k, v)
        return obj

    return [
        item("laser pistol", "A compact energy sidearm.",
             ["wieldable"], damage="1d+2", skill_type="ranged", value=250),
        item("combat rifle", "A rugged automatic rifle.",
             ["wieldable"], damage="3d", skill_type="ranged", value=800),
        item("combat armor", "Segmented ballistic plate.",
             ["wearable"], damage_resistance=4, slot="armor", value=1200),
        item("medkit", "A field trauma kit.",
             [], heals="2d", uses=3, value=150),
    ]


def build() -> None:
    PACK.mkdir(parents=True, exist_ok=True)

    files = {
        "skills.json": [define_skill(n, stat, pen)
                        for n, (stat, pen) in SKILLS.items()],
        "classes.json": [define_class(n, blurb, stats, skills)
                         for n, (blurb, stats, skills) in CLASSES.items()],
        "equipment.json": _equipment(),
    }
    for filename, objects in files.items():
        data = export_objects(objects)
        (PACK / filename).write_text(json.dumps(data, indent=2) + "\n")
        print(f"  wrote {filename} ({len(objects)} objects)")

    manifest = {
        "name": "gurps-scifi",
        "description": "GURPS sci-fi content: 6 classes, ship/combat skills, "
                       "and basic gear. Import whole, or a file at a time.",
        "files": ["skills.json", "classes.json", "equipment.json"],
    }
    (PACK / "pack.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"  wrote pack.json → {PACK}")


if __name__ == "__main__":
    build()
