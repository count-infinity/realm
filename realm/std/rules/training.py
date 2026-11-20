"""
Trainers and study: ``practice``, ``train`` and ``study`` (MUD_PLAN 5.3,
5.4).

An NPC with the ``trainer`` behavior teaches: ``practice <skill>`` spends
one of the character's ``practices`` to raise a skill it teaches (by a
third of the character's intelligence) up to the trainer's ``max_level``
(default a third of the skill's cap), past which the skill improves only
by use. ``train <stat>`` spends one of the character's ``trains`` to raise
a characteristic by one, at a trainer with ``trains_stats``. ``study
<skill>`` sets an ``idle`` skill training from the wall clock.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.behaviors import Behavior
from realm.core.world import format_line, get_world
from realm.std.rules import progression
from realm.std.rules.progression import (
    accrue_training,
    prerequisites_unmet,
    progression_of,
    skill_key,
    trained,
)

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject


class TrainerBehavior(Behavior):
    """A guildmaster: teaches skills with ``practice``, characteristics
    with ``train``."""

    behavior_id = "trainer"
    param_spec = {
        'teaches': ("class", 'a list of skill names, or "class" for the '
                             "character's class skills"),
        'max_level': (None, "how far practice carries a skill (default: a third "
                            "of its cap)"),
        'trains_stats': (False, "whether `train <stat>` works here"),
    }


async def world_verb(ctx: CommandContext) -> bool:
    """Offer a line this command cannot use to the world's softcode
    ``$``-commands first (a builder's own ``$study`` or ``$train``), as
    ``cast`` does: a built-in must not shadow a verb the world defines."""
    engine = get_world().scripts
    return engine is not None and await engine.handle_unknown_command(ctx)


#: How a characteristic reads in "You are already as <word> as you can be."
STAT_WORDS = {"strength": "strong", "dexterity": "quick", "constitution": "hardy",
              "intelligence": "clever", "wisdom": "wise", "health": "healthy"}


def find_trainer(player: GameObject) -> tuple[GameObject, TrainerBehavior] | None:
    """The first trainer in the player's room."""
    room = player.location
    for obj in (room.contents if room is not None else ()):
        for behavior in obj.get_behaviors():
            if isinstance(behavior, TrainerBehavior):
                return obj, behavior
    return None


def taught_by(trainer: TrainerBehavior, player: GameObject) -> list[str]:
    teaches = trainer.get_param('teaches', "class")
    if teaches == "class":
        rules = get_world().rules
        return list(rules.class_skills(player)) if rules is not None else []
    if isinstance(teaches, str):
        teaches = [teaches]
    return [skill_key(name) for name in teaches]


def practice_floor(trainer: TrainerBehavior, player: GameObject, skill: str) -> int:
    """How far this trainer's practice carries ``skill``."""
    explicit = trainer.get_param('max_level')
    if explicit is not None:
        return int(explicit)
    rules = get_world().rules
    cap = rules.skill_cap(player, skill) if rules is not None else None
    return (cap if cap is not None else 99) // 3


async def cmd_practice(ctx: CommandContext) -> None:
    """
    Practice a skill with a trainer, spending one practice session. With
    no skill, list what the trainer here teaches.

    Usage: practice [skill]
    """
    player = ctx.player
    found = find_trainer(player)
    if found is None:
        if not await world_verb(ctx):
            await ctx.session.send("There is no one here to teach you.")
        return
    master, trainer = found
    teaches = taught_by(trainer, player)
    practices = int(player.db.get("practices") or 0)
    name = (ctx.args or "").strip()
    if not name:
        lines = [format_line(f"{master.name} teaches:")]
        for skill in teaches:
            level = trained(player, skill) or 0
            floor = practice_floor(trainer, player, skill)
            mark = "  (learned; use it to improve)" if level >= floor else ""
            lines.append(f"  {skill.replace('_', ' '):18} {level:>3}{mark}")
        lines.append(f"You have {practices} practice session{'s' if practices != 1 else ''}.")
        await ctx.session.send("\n".join(lines))
        return

    skill = skill_key(name)
    shown = skill.replace("_", " ")
    if skill not in teaches:
        await ctx.session.send(f"{master.name} does not teach {shown}.")
        return
    if progression_of(player, skill) not in ("practice", "use"):
        await ctx.session.send(f"{shown.capitalize()} does not improve by practice.")
        return
    if practices <= 0:
        await ctx.session.send("You have no practice sessions left.")
        return
    level = trained(player, skill) or 0
    floor = practice_floor(trainer, player, skill)
    if level >= floor:
        await ctx.session.send(f"You have learned all {master.name} can teach of {shown}; "
                               f"use it to improve further.")
        return
    gain = max(1, int(player.db.get("intelligence") or 10) // 3)
    player.db.set(f"skill_{skill}", min(floor, level + gain))
    player.db.practices = practices - 1
    await ctx.session.send(f"You practice {shown} ({trained(player, skill)}).")


async def cmd_train(ctx: CommandContext) -> None:
    """
    Raise a characteristic by one at a trainer, spending a training session.

    Usage: train <strength|dexterity|constitution|intelligence|wisdom|...>
    """
    player = ctx.player
    stat = (ctx.args or "").strip().lower()
    if not stat:
        if await world_verb(ctx):
            return
        trains = int(player.db.get("trains") or 0)
        await ctx.session.send(f"You have {trains} training session"
                               f"{'s' if trains != 1 else ''}. Train what?")
        return
    found = find_trainer(player)
    if found is None:
        if not await world_verb(ctx):
            await ctx.session.send("There is no one here to train you.")
        return
    master, trainer = found
    if not trainer.get_param('trains_stats', False):
        await ctx.session.send(f"{master.name} can't train your {stat}.")
        return
    value = player.db.get(stat)
    if not isinstance(value, int) or isinstance(value, bool):
        await ctx.session.send(f"You have no {stat} to train.")
        return
    trains = int(player.db.get("trains") or 0)
    if trains <= 0:
        await ctx.session.send("You have no training sessions left.")
        return
    rules = get_world().rules
    limit = rules.stat_max(player, stat) if rules is not None else None
    if limit is not None and value >= limit:
        await ctx.session.send(f"You are already as {STAT_WORDS.get(stat, 'good at ' + stat)} "
                               f"as you can be.")
        return
    player.db.set(stat, value + 1)
    player.db.trains = trains - 1
    await ctx.session.send(f"Your {stat} rises to {value + 1}.")


async def cmd_study(ctx: CommandContext) -> None:
    """
    Study a skill over real time; it keeps improving while you are away.
    One skill at a time.

    Usage: study               what you are studying
           study <skill>       start (or switch to) a skill
           study stop          stop
    """
    player = ctx.player
    accrue_training(player)
    word = (ctx.args or "").strip()
    current = player.db.get("training")
    from realm.std.rules.progression import skill_def
    if (not word or (word.lower() != "stop" and skill_def(word) is None)) \
            and await world_verb(ctx):
        return                                  # the world's own $study (a book, a sigil)
    if not word:
        await ctx.session.send(f"You are studying {current.replace('_', ' ')}." if current
                               else "You are not studying anything.")
        return
    if word.lower() == "stop":
        if not current:
            await ctx.session.send("You are not studying anything.")
            return
        player.db.delete("training")
        player.db.delete("training_since")
        await ctx.session.send(f"You stop studying {current.replace('_', ' ')}.")
        return
    skill = skill_key(word)
    shown = skill.replace("_", " ")
    model = progression_of(player, skill)
    if model != "idle":
        how = f"it improves by {model}" if model else "it does not improve"
        await ctx.session.send(f"You can't study {shown}; {how}.")
        return
    unmet = prerequisites_unmet(player, skill)
    if unmet:
        await ctx.session.send(f"You need {', '.join(unmet)} before you can study {shown}.")
        return
    player.db.training = skill
    player.db.training_since = progression.now()
    await ctx.session.send(f"You begin studying {shown}.")


__all__ = ["TrainerBehavior", "STAT_WORDS", "find_trainer", "taught_by", "practice_floor",
           "cmd_practice", "cmd_train", "cmd_study"]
