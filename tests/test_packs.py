"""
Stage D: content packs. Skills, classes, and equipment are data, so a
"pack" is just a directory of worldio JSON — importable whole or a file at
a time, in-game or from the CLI. The built-in ``gurps-scifi`` pack is the
first, proving the spacegame's content is now data, not Python.
"""

from __future__ import annotations

import pytest

from realm.packs import (
    import_file,
    import_pack,
    list_packs,
    pack_files,
    pack_manifest,
)
from realm.systems import reload_rules
from realm.testing import Simulator


def test_builtin_scifi_pack_is_listed():
    assert "gurps-scifi" in list_packs()
    assert "sci-fi" in pack_manifest("gurps-scifi")["description"]


def test_pack_name_path_escape_rejected():
    from realm.packs import _pack_dir
    for bad in ("../secrets", "a/b", ""):
        with pytest.raises((ValueError, FileNotFoundError)):
            _pack_dir(bad)
            pack_manifest(bad)


@pytest.mark.asyncio
async def test_import_whole_pack_makes_content_live():
    sim = Simulator()
    try:
        created = await import_pack("gurps-scifi", sim.store)
        assert len(created) > 20                       # skills + classes + gear
        reload_rules()

        # Classes MERGE with the built-ins (Stage A semantics).
        classes = sim.game_system._class_options()
        assert {"pilot", "marine", "engineer"} <= set(classes)
        assert "soldier" in classes                    # built-ins still there

        # Skills are in the check table.
        assert sim.game_system.skill_defaults()["piloting"] == ("dexterity", -4)

        # Equipment exists as objects.
        from realm.core.query import find_objects
        assert {"laser pistol", "medkit"} <= {o.name for o in
                                              find_objects(tag="equipment")}
    finally:
        sim.close()


@pytest.mark.asyncio
async def test_a_la_carte_single_file_import():
    # Importing ONE file brings only that content — classes without skills.
    sim = Simulator()
    try:
        classes_file = next(p for p in pack_files("gurps-scifi")
                            if p.name == "classes.json")
        created = await import_file(classes_file, sim.store)
        names = {o.name for o in created}
        assert "pilot" in names and "engineer" in names
        from realm.core.query import find_objects
        assert find_objects(tag="skill_def") == []     # skills NOT imported
        assert find_objects(tag="class_def") != []
    finally:
        sim.close()


@pytest.mark.asyncio
async def test_import_pack_then_create_a_pilot_character():
    """The end-to-end payoff: fresh GURPS game, import the sci-fi pack, and
    a player can be created as a pilot — content is data."""
    sim = Simulator()
    try:
        await import_pack("gurps-scifi", sim.store)
        reload_rules()
        recruit = sim.obj("Recruit")
        step = sim.game_system.chargen_steps()[0]      # the class menu
        assert "pilot" in step.options
        step.handle(recruit, "pilot")
        assert recruit.db.get("skill_piloting") == 14
        assert recruit.db.get("dexterity") == 12
    finally:
        sim.close()


@pytest.mark.asyncio
async def test_reimport_is_idempotent_for_definitions():
    # Re-importing a pack must NOT accumulate duplicate class/skill defs.
    sim = Simulator()
    try:
        from realm.core.query import find_objects
        await import_pack("gurps-scifi", sim.store)
        n_classes = len(find_objects(tag="class_def"))
        second = await import_pack("gurps-scifi", sim.store)   # again
        assert len(find_objects(tag="class_def")) == n_classes  # no doubling
        # The skipped defs aren't in the second import's created list.
        assert all("class_def" not in o.tags.to_list() for o in second)
    finally:
        sim.close()


def test_manifest_files_cannot_escape_pack_dir(tmp_path, monkeypatch):
    import realm.packs as packs
    monkeypatch.setattr(packs, "_ROOT", tmp_path)
    pack = tmp_path / "evil"
    pack.mkdir()
    (pack / "pack.json").write_text(
        '{"name": "evil", "files": ["../../../../etc/passwd"]}')
    with pytest.raises(ValueError):
        packs.pack_files("evil")


@pytest.mark.asyncio
async def test_in_game_pack_command_imports():
    sim = Simulator()
    try:
        builder = sim.player("Builder", location=sim.room("Workshop"))
        builder.add_tag("builder")
        await sim.do(builder, "@pack")                 # list
        assert any("gurps-scifi" in m for m in sim.seen(builder))
        await sim.do(builder, "@pack gurps-scifi")     # import
        assert any("now live" in m for m in sim.seen(builder))
        assert "pilot" in sim.game_system._class_options()
    finally:
        sim.close()
