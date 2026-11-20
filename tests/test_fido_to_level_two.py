"""
The maintainer's goal: a playable Midgaard where a new player kills beastly
fidos and levels up (2026-11-17).

A real ``GameServer`` on a ``realm init --system merc --template midgaard``
game, played through the input path a telnet connection uses (the first
hour's ``Game`` and ``Client``). The first character on a server is its
superuser, so an administrator makes one and leaves; the player is the
second, a mage (the most fragile class), with no admin help: no granted
gold, hit points, items or levels, and honest dice (seeded, never loaded).
Kit reads ``help newbie``, finds fidos with ``where fido``, sizes one up,
kills it, rests when hurt, and goes on until the game says she has raised
a level, and what it brought.

Deterministic: the seeded dice and the one ``FakeClock``; the heartbeat runs
only while the fidos come back (``Game.repopulate``), as in the first hour.
"""

from __future__ import annotations

import re
from collections import deque
from types import SimpleNamespace

from realm.cli import cmd_init
from tests.test_first_hour import Client, Game
from tests.test_first_hour import game as midgaard_game  # noqa: F401  (the fixture)


def _route(game: Game, start, wanted: set[str]) -> list[str] | None:
    """The directions from ``start`` to the nearest room named in
    ``wanted``, through open exits (what a player with the town map walks)."""
    store = game.server.persistence
    queue, seen = deque([(start, [])]), {start.id}
    while queue:
        room, steps = queue.popleft()
        if steps and room.name in wanted:
            return steps
        for exit_obj in room.contents:
            if not exit_obj.is_exit or exit_obj.has_tag("closed"):
                continue
            there = store.get_cached(str(exit_obj.db.get("destination")))
            if there is not None and there.id not in seen:
                seen.add(there.id)
                queue.append((there, [*steps, exit_obj.name]))
    return None


def _fido_here(look: str) -> bool:
    """A live fido in what ``look`` shows (not "the corpse of the beastly
    fido")."""
    return re.search(r"^  (the beastly fido|\d+ beastly fidos)$", look, re.M) is not None


def _hp(text: str) -> tuple[int, int]:
    found = re.search(r"HP: (-?\d+)/(\d+)", text)
    return int(found.group(1)), int(found.group(2))


async def _rest_up(game: Game, kit: Client) -> None:
    assert "You sit down and rest." in await kit.send("rest")
    for _ in range(20):
        await game.wait(30)
        now, full = _hp(await kit.send("score"))
        if now >= full:
            break
    assert "You stand up." in await kit.send("stand")


async def test_a_new_mage_kills_fidos_to_level_two(request, monkeypatch):
    game = request.getfixturevalue("midgaard_game")      # the first hour's game
    assert cmd_init(SimpleNamespace(name="demo", force=False, template="midgaard",
                                    features="classic", system="merc")) == 0
    monkeypatch.chdir(game.project)
    await game.start()
    try:
        # The server's first character is its superuser: someone else's.
        root = await game.connect("10.0.0.9")
        await root.send("create Root rootpassword")
        assert "SUPERUSER" in await root.send("Boss")
        await root.send("warrior")
        assert "Goodbye!" in await root.send("quit")

        kit = await game.connect()
        assert "help newbie" in kit.take()                    # the welcome banner
        await kit.send("create Kit correcthorse")
        out = await kit.send("Kit")
        assert "SUPERUSER" not in out
        out = await kit.send("mage")
        assert "You grip a gnarled dagger, ready for trouble." in out
        assert "You have been equipped by the Mud School: a war banner, a sub issue " \
            "vest, a sub issue shield." in out
        assert "Welcome to the world, Kit!" in out and "The Common Square" in out
        player = kit.player
        assert not player.has_tag("god") and not player.has_tag("admin")
        out = await kit.send("score")
        assert "You are Kit, a level 1 mage." in out and "HP: 20/20" in out
        assert "AC: 8" in out and "Practices: 5   Training sessions: 3" in out
        assert "You have 0 gold." in await kit.send("inventory")
        assert "where fido" in await kit.send("help newbie")
        await kit.send("")                                     # past the pager

        story, kills, deaths = [], 0, 0
        for _ in range(60):
            if player.db.level >= 2:
                break
            out = await kit.send("where fido")
            places = set(re.findall(r"^the beastly fido\s+(.+)$", out, re.M))
            steps = _route(game, player.location, places) if places else None
            here = _fido_here(await kit.send("look"))
            if not here and not steps:
                await game.repopulate()                        # they come back
                continue
            if not here:
                await game.walk(kit, *steps)
                if not _fido_here(await kit.send("look")):
                    continue
            if not kills:
                assert "The perfect match!" in await kit.send("consider fido")
            assert "You square off against the beastly fido!" in await kit.send("kill fido")
            await game.fight(kit, rounds=60)
            out = kit.take()
            story.append(out)
            if "You have been KILLED!!" in out:
                deaths += 1
                assert "The Common Square" in out              # she wakes at home
            else:
                assert "The beastly fido falls dead!" in out
                kills += 1
            now, full = _hp(await kit.send("score"))
            if now < full * 2 // 3:
                await _rest_up(game, kit)
        text = "\n".join(story)
        assert player.db.level == 2, f"still level 1 after {kills} fidos:\n{text}"
        assert text.count("You gain 170 experience.") == kills == 6
        assert deaths == 0
        assert "You raise a level!!  You are now level 2." in text
        assert "You gain 2 hit points, 10 mana, 2 practices and 1 training session." in text
        out = await kit.send("score")
        assert "You are Kit, a level 2 mage." in out
        assert "Experience: 20 / 2000 to level 3" in out
        assert "Practices: 7   Training sessions: 4" in out    # ROM's 5 and 3, and a level's
    finally:
        await game.stop()
