"""
MUD_PLAN step 17: the first hour, the acceptance test of the whole plan.

One scripted session on a game made the way the plan's first line says,
``realm init demo --system merc --template midgaard``, run by a real
``GameServer`` on its own database file in the game's directory, and
played through the input path a connection uses
(``Session.submit_input``, then ``GameServer._on_command`` and
``route_input``). Each section is one numbered line of "What 'complete'
means here" at the top of ``MUD_PLAN.md`` and asserts what the player sees.

The story: Ann makes Bree (a warrior) and Cole (a cleric), each outfitted
as ROM's ``do_outfit`` does (a weapon, the Mud School's banner, vest and
shield). Bree takes the baker's quest (line 11 begins there, so her fido
kills count), picks a fight with a fido and is hurt, rests, dies to the
vagabond, recovers her things from her corpse, beats the vagabond the
second time, loots him and raises a level, sells his sword and jerkin,
buys a cap and wears it (3); finds four more fidos with ``where fido``,
kicks one, practises at her own guild (the Guild of Swordsmen, whose bar
lets in only warriors) and starts studying lore (4); is paid for the quest
(11) and logs out. Dan makes Eve; Bree, back with her lore trained, talks
to her and mails her (5); Cole finds Bree's achievement (6); Bree, the
superuser, bans, unbans and resets Dan, announces a shutdown, backs up,
makes a mistake and restores (7); Eve grows hungry and eats Bree's bread
(8); Bree buys a dog that fights beside her (its kill raises her to level
3), then a horse she rides (9); founds a clan Eve joins (10); and builds a
loft that only Friends of the Baker may climb to, which Cole does (12).
``tests/test_fido_to_level_two.py`` plays the same town as a player who is
not the superuser, from creation to level 2 on fidos alone.

Deterministic: the dice are seeded, and loaded (``Fate``) where the story
needs a fight won or lost; every clock the engine reads is one
``FakeClock`` the test moves (a second a command), so the dates on mail,
achievements and channel history are the story's own; the housekeeping a
running server does on its own (regeneration, hunger, idle training, the
clan and quest sweeps) is the server's own ``_reap``, called as the clock
moves. A fight's rounds come when the clock reaches each beat: the test
moves it there and calls the encounter's own ``beat``, what its loop does
when it wakes. The heartbeat is the server's own ``pulse``, called as the
clock moves a world beat at a time while the fidos come back; it ticks what
is due on the clock, in the order the objects got their behaviors, so the
seeded dice fall the same way under any ``PYTHONHASHSEED``.
"""

from __future__ import annotations

import asyncio
import random
import sys
from types import SimpleNamespace

import pytest

from realm.cli import cmd_backup, cmd_init, cmd_restore
from realm.config.loader import load_config
from realm.server.game import GameServer
from realm.testing import FakeClock


class Fate:
    """Loaded dice for the outcomes the story needs. A fighter named in
    ``rolls`` rolls ``"best"`` or ``"worst"``: on its attacks every die (and
    the defense roll against it) and its own skill checks. A list is one
    entry per attack, the last kept. Everything else rolls the seeded dice."""

    def __init__(self) -> None:
        self.rolls: dict[str, list[str]] = {}
        self.others: str | None = None
        self.high: bool | None = None            # dice come up high (or low)
        self.last: bool | None = None

    def randint(self, low: int, high: int) -> int:
        if self.high is None:
            return random.randint(low, high)
        return high if self.high else low

    def __getattr__(self, name):                 # random.random and the rest
        return getattr(random, name)

    def _mode(self, obj_id: str, *, advance: bool) -> str | None:
        queue = self.rolls.get(obj_id)
        if not queue:
            return self.others
        return queue.pop(0) if advance and len(queue) > 1 else queue[0]

    def install(self, monkeypatch) -> None:
        from realm.games.merc.ruleset import MercRuleset
        from realm.games.merc.system import MercSystem
        for module in ("realm.games.merc.ruleset", "realm.games.merc.system"):
            monkeypatch.setattr(f"{module}.random", self)
        attack, damage = MercRuleset.roll_attack, MercRuleset.roll_damage
        check = MercSystem.resolve_check

        def roll_attack(ruleset, attacker, *args, **kwargs):
            mode = self._mode(attacker.obj.id, advance=True)
            self.high = None if mode is None else mode == "best"
            try:
                return attack(ruleset, attacker, *args, **kwargs)
            finally:
                self.last, self.high = self.high, None

        def roll_damage(ruleset, attacker, *args, **kwargs):
            self.high = self.last                # as its attack rolled
            try:
                return damage(ruleset, attacker, *args, **kwargs)
            finally:
                self.high = None

        def resolve_check(system, obj, skill, modifier):
            if self.high is not None:            # a defense, inside an attack
                return check(system, obj, skill, modifier)
            mode = self._mode(obj.id, advance=False)
            self.high = None if mode is None else mode == "worst"   # d100: low wins
            try:
                return check(system, obj, skill, modifier)
            finally:
                self.high = None
        monkeypatch.setattr(MercRuleset, "roll_attack", roll_attack)
        monkeypatch.setattr(MercRuleset, "roll_damage", roll_damage)
        monkeypatch.setattr(MercSystem, "resolve_check", resolve_check)

    def __call__(self, rolls: dict, others: str | None = None) -> None:
        """``fate({bree: ["worst", "best"]}, others="best")``: how each
        named fighter rolls, and everyone else (None: the seeded dice)."""
        self.rolls = {obj.id: [how] if isinstance(how, str) else list(how)
                      for obj, how in rolls.items()}
        self.others = others


class Client:
    """One connection, as a telnet client sees it: output and prompts."""

    def __init__(self, server: GameServer, session, out: list[str], clock: FakeClock) -> None:
        self.server, self.session, self.out, self.clock = server, session, out, clock
        self.seen = 0

    async def send(self, line: str) -> str:
        """Type ``line`` (a second after the last); what came back,
        prompts included. The line goes in as a protocol adapter hands it
        over (``Session.submit_input``: activity, flood control, multi-line
        blocks) and on through the server's own ``_on_command``, which its
        input pump would call."""
        start = len(self.out)
        self.clock.t += 1
        self.session.submit_input(line)
        queue = self.session._input_queue
        while not queue.empty():
            await self.server._on_command(self.session, queue.get_nowait())
        await self.session.flush_output()
        self.seen = len(self.out)
        return "\n".join(self.out[start:])

    def take(self) -> str:
        """What arrived since the last command or ``take``: other people's
        doings, a fight's rounds."""
        text = "\n".join(self.out[self.seen:])
        self.seen = len(self.out)
        return text

    @property
    def player(self):
        return self.session.player


class Game:
    """The running server, its clock, and the people connected to it."""

    def __init__(self, project, clock: FakeClock, fate: Fate) -> None:
        self.project, self.clock, self.fate = project, clock, fate
        self.server: GameServer | None = None

    async def start(self) -> GameServer:
        """``realm start`` in the game's directory (no network listener, and
        no heartbeat loop: the test moves the clock and calls ``pulse``)."""
        settings = load_config(self.project)
        self.server = GameServer(settings, enable_telnet=False, tick_interval=0)
        await self.server.start()
        return self.server

    async def stop(self) -> None:
        if self.server is not None:
            await self.server.stop()
            self.server = None

    async def connect(self, address: str = "127.0.0.1") -> Client:
        out: list[str] = []

        async def writer(text: str) -> None:
            out.append(text)

        session = await self.server.session_manager.create_session(
            protocol="test", address=address, writer=writer)
        session.set_prompt_writer(out.append)     # as telnet frames it
        await session.flush_output()
        return Client(self.server, session, out, self.clock)

    async def flush(self) -> None:
        for session in self.server.session_manager.all_sessions():
            await session.flush_output()

    async def wait(self, seconds: float, step: float = 5.0) -> None:
        """Let ``seconds`` pass on a running server: its housekeeping runs
        every ``step`` (the reapers: regeneration, hunger, training, ...)."""
        end = self.clock.t + seconds
        while self.clock.t < end:
            self.clock.t = min(end, self.clock.t + step)
            await self.server._reap()
        await self.server.persistence.flush()     # the store's own flush loop
        await self.flush()

    def combat(self):
        return self.server.world.services["combat"]

    async def fight(self, client: Client, rounds: int = 20) -> None:
        """Let the fight ``client`` is in run to its end: the clock moves
        to each beat in turn and the encounter's ``beat`` fires the round."""
        encounter = self.combat().encounter_of(client.player)
        assert encounter is not None, "not in a fight"
        await asyncio.sleep(0)                    # the beat loop says the fight began
        for _ in range(rounds):
            self.clock.advance(encounter.seconds_to_beat)
            going = await encounter.beat()
            await self.flush()
            if not going:
                break
        else:
            raise AssertionError(f"the fight did not end in {rounds} rounds:\n"
                                 + client.take())

    def find(self, name: str, *, tag: str = "npc", where=None):
        """The object ``name`` names, as a player typing it would mean it,
        with ``tag``, in ``where``."""
        from realm.core.search import match_objects
        objs = (where.contents if where is not None
                else self.server.persistence.find_cached(tag=tag))
        found = match_objects(name, [o for o in objs if o.has_tag(tag)
                                     and not o.has_tag("prototype")]).matches
        if not found:
            raise AssertionError(f"no {tag} {name!r}")
        return found[0]

    async def walk(self, client: Client, *directions: str) -> str:
        """Walk ``directions``; whoever jumps the walker on the way is
        fought off. What the walker saw, all the way."""
        seen = []
        for direction in directions:
            seen.append(await client.send(direction))
            if self.combat().encounter_of(client.player) is not None:
                await self.fight(client)
                seen.append(client.take())
        return "\n".join(seen)

    async def repopulate(self) -> None:
        """Time enough for the town's spawners to bring back the dead: the
        clock moves a world beat at a time and the server's heartbeat runs
        (``pulse``, what its loop does each time it wakes), ticking every
        behavior that is due: the spawners, and the town's wanderers and
        scavengers too. The first pulse sets each behavior's phase; the
        longest respawn takes its ``respawn_ticks`` beats after that."""
        longest = max(int(b.get_param("respawn_ticks", 150))
                      for o in self.server.persistence.all_cached()
                      for b in o.get_behaviors() if b.behavior_id == "spawner")
        beat = self.server.world.setting("WORLD_BEAT")
        for _ in range(longest + 2):
            self.clock.advance(beat)
            await self.server.pulse()
        await self.flush()


@pytest.fixture
def game(tmp_path, monkeypatch, clock):
    """``realm init demo --system merc --template midgaard`` in an empty
    directory, the fake clock (the ``clock`` fixture: every engine clock)
    and the seeded dice."""
    before = list(sys.path)
    monkeypatch.chdir(tmp_path)
    random.seed(1)
    fate = Fate()
    fate.install(monkeypatch)
    game = Game(tmp_path / "demo", clock, fate)
    yield game
    sys.modules.pop("rules", None)
    sys.modules.pop("game", None)
    sys.path[:] = before
    from realm.features import install_default
    from realm.std.combat.combatant import clear_combatant_cache
    clear_combatant_cache()
    install_default()


async def test_the_first_hour(game, capsys, monkeypatch):
    # --- 1. realm init mygame --system merc --template midgaard; realm start --
    assert cmd_init(SimpleNamespace(name="demo", force=False, template="midgaard",
                                    features="classic", system="merc")) == 0
    assert "realm start" in capsys.readouterr().out
    monkeypatch.chdir(game.project)                         # cd demo
    server = await game.start()
    out = capsys.readouterr().out                            # init_world, first boot
    assert "Imported 1048 objects (143 rooms) from Midgaard" in out
    assert "Starting room: The Common Square" in out
    try:
        await play(game, server, capsys)
    finally:
        await game.stop()


async def play(game: Game, server: GameServer, capsys) -> None:
    ann = await game.connect()
    out = ann.take()
    assert "M I D G A A R D" in out and "create <account> <password>" in out

    # --- 2. an account, then two characters on it ----------------------------
    out = await ann.send("create Ann correcthorse")
    assert "Account 'Ann' created. Name your first character:" in out
    out = await ann.send("Bree")
    assert "Character 'Bree' created." in out and "Choose your class:" in out
    assert "hp" not in out                     # no prompt before there is a character
    out = await ann.send("warrior")
    assert "Welcome to the world, Bree!" in out and "The Common Square" in out
    bree = ann.player
    out = await ann.send("characters")
    assert "Bree             level 1 warrior" in out
    out = await ann.send("new Cole")
    assert "Character 'Cole' created." in out
    out = await ann.send("cleric")
    assert "Welcome to the world, Cole!" in out
    cole = ann.player
    out = await ann.send("characters")
    assert "Bree" in out and "Cole             level 1 cleric" in out
    out = await ann.send("play Bree")
    assert "The Common Square" in out and ann.player is bree
    assert "Cole" not in out                     # out of play: not in the room

    # --- 11 (begun). The baker's quest, taken first so the fidos count ----------
    assert "<20hp 100m 100mv>" in out             # the prompt
    out = await game.walk(ann, "north", "west", "north")
    assert "The Bakery" in out and "baker (!)" in out
    out = await ann.send("quest list")
    assert "The baker offers:" in out and "Fido trouble" in out
    out = await ann.send("quest accept fido trouble")
    assert "Quest accepted: Fido trouble." in out
    out = await ann.send("quests")
    assert "Fido trouble (stage 1 of 1)" in out and "fidos killed: 0/5" in out

    # --- 3. alone from level 1 to level 2 ----------------------------------------
    # Back in the square, a beastly fido. It lets her be (ROM's fido bites
    # only sleepers), so she picks the fight. It rolls its best; Bree
    # fumbles (twice: her first swing, and in the next round) before she
    # finds her stroke. She wins, hurt.
    out = await game.walk(ann, "south", "east", "south")
    assert "The Common Square" in out and "the beastly fido" in out
    game.fate({bree: ["worst", "worst", "best"]}, others="best")
    assert "You square off against the beastly fido!" in await ann.send("kill fido")
    await game.fight(ann)
    out = ann.take()
    assert "CRITICAL! The beastly fido hits you for 8 damage!" in out
    assert "The beastly fido falls dead!" in out and "You gain 170 experience." in out
    assert "[Fido trouble] fidos killed: 1/5" in out
    assert "<4hp 100m 89mv>" in out
    out = await ann.send("score")
    assert "Experience: 170 / 1000 to level 2" in out and "HP: 4/20" in out
    # Rest it off.
    assert "You sit down and rest." in await ann.send("rest")
    await game.wait(60)
    assert "<20hp 100m 100mv>" in await ann.send("stand")
    # The vagabond in the dark alley, and the alley cat: Bree dies.
    await ann.send("east")
    game.fate({bree: "worst"}, others="best")
    assert "You square off against the vagabond!" in await ann.send("kill vagabond")
    await game.fight(ann)
    out = ann.take()
    assert "You have been KILLED!!" in out and "You lose 170 experience." in out
    assert "The Common Square" in out and "<1hp 100m 98mv>" in out   # back home
    # Rest, go back for the body (the alley cat, ROM's wimpy kind, lets her
    # be), and put her things back on.
    await ann.send("rest")
    await game.wait(60)
    await ann.send("stand")
    game.fate({bree: "best"}, others="worst")
    out = await ann.send("east")
    assert "the corpse of Bree" in out and "an alley cat" in out
    assert game.combat().encounter_of(bree) is None
    assert "You pick up a short sword, a war banner, a sub issue vest, and a sub issue " \
        "shield." in await ann.send("get all from corpse")
    assert "You ready a short sword." in await ann.send("wield sword")
    out = await ann.send("wear all")
    assert "You put on the war banner." in out and "You put on the sub issue shield." in out
    # The vagabond again, and this time she wins: his gear is hers, and
    # she raises a level (his 800, doubled at level 1 as ROM pays).
    assert "You square off against the vagabond!" in await ann.send("kill vagabond")
    await game.fight(ann)
    out = ann.take()
    assert "The vagabond falls dead!" in out and "You gain 1600 experience." in out
    assert "You raise a level!!  You are now level 2." in out
    assert "You gain 6 hit points, 1 practice and 1 training session. " \
        "Your THAC0 is now 19." in out
    out = await ann.send("get all from corpse vagabond")
    assert "a small sword" in out and "a hard leather jerkin" in out
    # To the weapon shop.
    out = await game.walk(ann, "west", "north", "east", "east", "north")
    assert "The Weapon Shop" in out
    assert "You sell a small sword for 100 gold." in await ann.send("sell small")
    # The armourer takes his jerkin.
    out = await game.walk(ann, "south", "west", "west", "west", "south")
    assert "The Armoury" in out
    assert "You sell a hard leather jerkin for 215 gold." in await ann.send("sell jerkin")
    # The leather shop: a cap, bought and worn.
    await game.walk(ann, "north", "east", "south", "west", "west", "north")
    assert "a leather cap — 150 gold" in await ann.send("list")
    assert "Which 'cap' do you mean?" in await ann.send("buy cap")
    assert "You buy a leather cap for 150 gold." in await ann.send("buy cap-1")
    assert "You put on the leather cap." in await ann.send("wear cap")
    out = await ann.send("score")
    assert "You are Bree, a level 2 warrior." in out
    assert "Wearing:  a war banner, a sub issue vest, a sub issue shield, a leather cap" in out
    # ROM's 5 practices and 3 training sessions at creation, and a level's.
    assert "AC: 7" in out and "Practices: 6   Training sessions: 4" in out
    assert "Experience: 600 / 2000 to level 3" in out
    out = await ann.send("equipment")
    assert "<head>    a leather cap" in out and "<wielded> a short sword" in out
    assert "<body>    a sub issue vest" in out and "<shield>  a sub issue shield" in out
    assert "<26hp 100m 69mv>" in out
    out = await ann.send("inventory")
    assert "a leather bracer" in out and "You have 165 gold." in out and "cap" not in out

    # --- 4. a class skill by name, learning by use, practice, study ----------------
    out = await ann.send("skills")
    assert "kick                 40%   (use: 0/10)" in out
    assert "melee                41%   (use: 6/10)" in out  # learnt by use already
    await game.repopulate()                                 # the fidos are back
    # Four more fidos for the baker: `where` says where they are.
    out = await ann.send("where fido")
    assert out.count("the beastly fido") == 4
    assert "Melancholy's Maps" in out and "The Common Square" in out
    game.fate({bree: "best"}, others="worst")
    out = await game.walk(ann, "south", "east", "north")
    assert "Melancholy's Maps" in out and "the beastly fido" in out
    assert "You kick the beastly fido." in await ann.send("kick fido")
    await game.fight(ann)
    assert "The beastly fido falls dead!" in ann.take()
    out = await game.walk(ann, "south", "east")
    assert "The Common Square" in out and "the beastly fido" in out
    await ann.send("kill fido")
    await game.fight(ann)
    out = await game.walk(ann, "north", "west", "west")
    assert "Main Street" in out and "the beastly fido" in out
    await ann.send("kill fido")
    await game.fight(ann)
    out = await game.walk(ann, "east", "east", "east", "east")
    assert "The Main Street" in out and "the beastly fido" in out
    await ann.send("kill fido")
    await game.fight(ann)
    out = ann.take()
    assert "The beastly fido falls dead!" in out and "fidos killed: 5/5" in out
    out = await ann.send("skills")
    assert "kick                 40%   (use: 2/10)" in out  # kicking teaches kicking
    assert "melee                42%   (use: 4/10)" in out  # and swinging, swinging
    # Her own guild: the Guild of Swordsmen, through its bar, which lets
    # in warriors (and barbarians) only.
    out = await game.walk(ann, "south", "east", "south")
    assert "The Tournament and Practice Yard" in out and "the guildmaster" in out
    out = await ann.send("practice")
    assert "The guildmaster teaches:" in out and "bash                30" in out
    assert "You have 6 practice sessions." in out
    assert "You practice bash (31)." in await ann.send("practice bash")
    assert "You have 5 practice sessions." in await ann.send("practice")
    assert "You begin studying lore." in await ann.send("study lore")

    # --- 11 (ended). Five fidos: back to the baker to be paid ---------------------
    assert "Fido trouble (ready: return to baker)" in await ann.send("quests")
    out = await game.walk(ann, "north", "west", "north", "west", "west", "west", "north")
    assert "the baker (?)" in out                           # waiting for her
    out = await ann.send("quest complete")
    assert "Quest complete: Fido trouble!" in out and "You gain 250 experience." in out
    assert "You receive a bread." in out
    assert "Achievement earned: Friend of the Baker!" in out
    assert "Fido trouble" in await ann.send("quests done")

    # Bree logs out; her lore keeps training.
    assert "Goodbye!" in await ann.send("quit")
    await game.wait(2 * 3600, step=600)

    # --- 5. a tell, a channel, and mail for someone offline -------------------------
    dan = await game.connect("10.0.0.2")
    await dan.send("create Dan opensesame")
    await dan.send("Eve")
    out = await dan.send("thief")
    assert "Welcome to the world, Eve!" in out and "The Common Square" in out
    ann = await game.connect()
    out = await ann.send("connect Ann correcthorse")
    assert "Bree             level 2 warrior" in out           # two characters: the menu
    out = await ann.send("play Bree")
    # (4, ended) Lore trained while she was away.
    assert "You have finished training lore to level 9." in out
    assert "The Bakery" in out
    out = await ann.send("skills")
    assert "lore                 9%   (training)" in out
    # Bree in the Bakery, Eve in the Common Square.
    out = await ann.send("tell Eve Welcome to Midgaard. Mind the fidos.")
    assert "You tell Eve, 'Welcome to Midgaard. Mind the fidos.'" in out
    assert "Bree tells you, 'Welcome to Midgaard. Mind the fidos.'" in dan.take()
    await dan.send("reply Thanks! Where is the baker?")
    assert "Eve tells you, 'Thanks! Where is the baker?'" in ann.take()
    await ann.send("gossip The baker in the Bakery has work for fido hunters.")
    assert "[gossip] Bree: The baker in the Bakery has work for fido hunters." in dan.take()
    # Eve logs off; Bree leaves her a letter.
    assert "Goodbye!" in await dan.send("quit")
    assert dan.session not in game.server.session_manager.all_sessions()
    out = await ann.send("tell Eve Are you there?")
    assert "Eve is not online. Leave them a message with mail." in out
    out = await ann.send("mail Eve = Fido hunting/Meet me in the Common Square at dawn.")
    assert "Mail sent to Eve." in out

    # --- 6. an achievement earned on one character, seen on the other -------------
    await ann.send("characters")
    out = await ann.send("play Cole")
    assert "Welcome back, Cole!" in out
    out = await ann.send("achievements")
    assert f"{'Friend of the Baker':24} 2027-01-15" in out and "none yet" not in out
    assert cole.has_tag("baker_friend")         # its grant; section 12 opens a door with it

    # --- 7. an administrator: ban, reset a password, shut down, back up, restore ---
    await ann.send("characters")
    assert "Welcome back, Bree!" in await ann.send("play Bree")     # the superuser
    out = await ann.send("@account Dan")
    assert "Account Dan" in out and "characters:  Eve" in out
    out = await ann.send("@account/ban Dan 1d = feeding the fidos")
    assert "Dan is banned until" in out
    dan = await game.connect("10.0.0.2")
    out = await dan.send("connect Dan opensesame")
    assert "This account is banned until" in out and "feeding the fidos" in out
    assert dan.player is None
    assert "Dan is no longer banned." in await ann.send("@account/unban Dan")
    assert "Dan's password is reset." in await ann.send("@account/password Dan = fidohunter")
    assert "Invalid password." in await dan.send("connect Dan opensesame")
    out = await dan.send("connect Dan fidohunter")
    # (5, ended) The letter waited for her.
    assert "Welcome back, Eve!" in out and "You have 1 unread message." in out
    out = await dan.send("mail 1")
    assert "From: Bree" in out and "Meet me in the Common Square at dawn." in out
    assert "Date: 2027-01-15 " in out                     # the story's day
    # A shutdown, announced to everyone.
    out = await ann.send("@shutdown 60 = restoring a backup")
    announced = "*** The server is shutting down in 60 seconds (restoring a backup). ***"
    assert announced in out and announced in dan.take()
    await ann.send("@shutdown/cancel")
    assert "*** The shutdown is cancelled by Bree. ***" in dan.take()
    # A backup of the running game ...
    await game.wait(10)                           # the store flushes
    capsys.readouterr()
    assert cmd_backup(SimpleNamespace(file=None, keep=None)) == 0     # realm backup
    printed = capsys.readouterr().out.strip()
    assert printed.startswith("Backed up ") and "midgaard.db to " in printed
    backup = printed.split(" to ", 1)[1]
    # ... a builder's mistake ...
    out = await ann.send("look")
    assert "The Bakery" in out and "the baker" in out
    assert "Destroyed the baker and 6 contained object(s)." in await ann.send("@destroy baker")
    await game.wait(10)
    # ... so down it goes, now, and the backup goes back.
    await ann.send("@shutdown 0 = restoring this morning's backup")
    while server._stop_task is None:              # the countdown, at zero
        await asyncio.sleep(0)
    await server._stop_task
    game.server = None
    out = ann.take()
    assert "*** The server is shutting down now (restoring this morning's backup). ***" in out
    assert "Server shutting down. Goodbye!" in out
    assert cmd_restore(SimpleNamespace(file=backup)) == 0
    assert "Restored " in capsys.readouterr().out
    server = await game.start()
    ann = await game.connect()
    await ann.send("connect Ann correcthorse")
    out = await ann.send("play Bree")
    assert "The Bakery" in out and "the baker" in out          # as it was
    bree = ann.player

    # --- 8. hungry, then fed ---------------------------------------------------------
    dan = await game.connect("10.0.0.2")
    out = await dan.send("connect Dan fidohunter")
    assert "Welcome back, Eve!" in out and "The Common Square" in out
    out = await dan.send("score")
    assert "You are hungry." not in out
    await game.wait(1800, step=40)                # half an hour, awake
    out = await dan.send("score")
    assert "You are hungry." in out
    game.fate({bree: "best"}, others="worst")
    out = await game.walk(ann, "south", "east", "south")
    assert "Eve" in out
    assert "You give a bread to Eve." in await ann.send("give bread to Eve")
    assert "Bree gives you a bread." in dan.take()
    assert "You eat a bread." in await dan.send("eat bread")
    assert "You are hungry." not in await dan.send("score")

    # --- 9. a pet that follows and fights, a horse that carries ----------------------
    out = await game.walk(ann, "east", "east", "north")
    assert "The Pet Shop" in out
    out = await ann.send("list")
    assert "Pets for sale:" in out and "the rottweiler — 4 gold" in out
    assert "a brown horse (mount) — 10 gold" in out
    out = await ann.send("buy rottweiler")
    assert "You buy the rottweiler for 4 gold." in out
    rottweiler = game.find("rottweiler", where=bree.location)
    out = await game.walk(ann, "south", "west")
    assert "The rottweiler arrives." in out and "The Dark Alley" in out
    game.fate({bree: "best", rottweiler: "best"}, others="worst")
    await ann.send("kill vagabond")
    await game.fight(ann)
    out = ann.take()
    assert "The rottweiler leaps to Bree's side!" in out
    assert "The rottweiler hits the vagabond!" in out and "The vagabond falls dead!" in out
    assert "You raise a level!!  You are now level 3." in out     # the dog's kill is hers
    # One companion at Bree's level (Merc: 1 + level / 10, still 1 at 3):
    # the dog goes, and a horse takes its place.
    assert "You dismiss the rottweiler." in await ann.send("dismiss rottweiler")
    await game.walk(ann, "east", "north")
    assert "You buy a brown horse for 10 gold." in await ann.send("buy horse")
    assert "You can't ride in here." in await ann.send("mount horse")   # a shop
    out = await ann.send("south")
    assert "A brown horse arrives." in out and "<32hp 100m 80mv>" in out
    horse = game.find("brown horse", where=bree.location)
    assert "You mount the brown horse." in await ann.send("mount horse")
    out = await game.walk(ann, "west", "west")
    assert "You ride west on a brown horse." in out and "The Common Square" in out
    assert "<32hp 100m 80mv>" in out                      # Bree spent nothing ...
    assert horse.db.move < horse.db.max_move              # ... the horse paid
    assert "a brown horse (mount, ridden)" in await ann.send("companions")
    assert "Bree arrives, riding a brown horse." in dan.take()
    assert "You dismount" in await ann.send("dismount")

    # --- 10. a clan: founded, a member accepted, its channel, its door -----------------
    out = await ann.send("clan governments")
    assert "gang         ruled by one boss, who assigns the underlings" in out
    # Founding costs CLAN_COST (10000); the superuser bankrolls her own test.
    assert "Set Bree/credits = 10080" in await ann.send("@set me/credits = 10080")
    out = await ann.send("clan found Fido Hunters = gang")
    assert "You found Fido Hunters, a gang, and are its Boss." in out
    assert "You have 80 gold." in await ann.send("inventory")
    # A clubhouse off the square, its door locked to the clan.
    out = await ann.send("@dig The Clubhouse = clubhouse, out")
    assert "Room created: The Clubhouse" in out
    assert "Lock/basic set on clubhouse." in await ann.send(
        "@lock clubhouse = clan(caller) == 'Fido Hunters'")
    assert "You apply to join Fido Hunters." in await dan.send("clan apply Fido Hunters")
    assert "[Fido Hunters] Eve applies to join" in ann.take()
    assert "You can't go clubhouse — it's locked." in await dan.send("clubhouse")
    assert "Eve is accepted." in await ann.send("clan accept Eve")
    assert "You are accepted into Fido Hunters as Member." in dan.take()
    await dan.send("ct Thanks, boss!")
    assert "[Fido Hunters] Eve: Thanks, boss!" in ann.take()
    out = await dan.send("clubhouse")
    assert "You leave clubhouse." in out and "The Clubhouse" in out
    out = await ann.send("who")
    assert "Bree the Swordpupil (3 warrior) [Boss of Fido Hunters]" in out
    assert "Eve the Pilferer (1 thief) [Fido Hunters]" in out

    # --- 12. building in softcode, no restart ------------------------------------------
    game.fate({bree: "best"}, others="worst")
    out = await game.walk(ann, "north", "west", "north")
    assert "The Bakery" in out
    # A loft above the Bakery, its stair open to Friends of the Baker; a
    # sack of flour with a verb of its own. Live, as typed.
    out = await ann.send("@dig The Baker's Loft = up, down")
    assert "Room created: The Baker's Loft" in out
    await ann.send("@lock up = has_achievement(caller, 'Friend of the Baker')")
    assert "The Baker's Loft" in await ann.send("up")
    assert "Description set" in await ann.send(
        "@desc here = Flour sacks are stacked to the rafters. It is warm up here.")
    assert "Created: a sack of flour" in await ann.send("@create a sack of flour")
    await ann.send("@set sack/cmd_sniff = $sniff sack: "
                   "pemit(enactor, 'It smells of warm bread.')")
    await ann.send("drop sack")
    assert "It smells of warm bread." in await ann.send("sniff sack")
    # A script on the room, typed as a block (a line of ''' opens and closes it).
    for line in ("@set here/on_enter='''",
                 "greeting = 'The baker calls up the stair: Mind the flour, '",
                 "pemit(enactor, greeting + name(enactor) + '!')",
                 "'''"):
        out = await ann.send(line)
    assert "Set The Baker's Loft/on_enter" in out
    await ann.send("down")
    # Eve is no friend of the baker; Cole is, through Bree (section 6).
    game.fate({}, others="worst")
    out = await game.walk(dan, "out", "north", "west", "north")
    assert "The Bakery" in out
    assert "You can't go up — it's locked." in await dan.send("up")
    await ann.send("characters")
    assert "Welcome back, Cole!" in await ann.send("play Cole")
    out = await game.walk(ann, "north", "west", "north")
    assert "The Bakery" in out and "Eve" in out and "Bree" not in out
    out = await ann.send("up")
    assert "The Baker's Loft" in out and "a sack of flour" in out
    assert "The baker calls up the stair: Mind the flour, Cole!" in out
    assert "It smells of warm bread." in await ann.send("sniff sack")
