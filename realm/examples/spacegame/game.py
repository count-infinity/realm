"""
Space Station Alpha: the game's own feature.

Everything this game adds to REALM is declared on ``feature``: commands,
behaviors, softcode functions, observers, config settings. ``config.py``
lists this module in FEATURES as "game", so it loads before the world does
and saved behaviors always find their class. See docs/guides/features.md.
"""

from realm import Behavior, Feature  # noqa: F401  (Behavior: the behavior example)

feature = Feature("spacegame")


# A command. Players type `wave`.
# @feature.command("wave", category="social", help_text="Wave hello")
# async def cmd_wave(ctx):
#     await ctx.session.send("You wave.")


# A behavior. Attach it with `@behavior <object> = spacegame_chime`.
# @feature.behavior
# class Chime(Behavior):
#     behavior_id = "spacegame_chime"
#
#     @property
#     def should_tick(self):
#         return True
#
#     async def tick(self, obj, delta):
#         obj.db.set("chimes", int(obj.db.get("chimes") or 0) + 1)


# A softcode function: `double(4)`. readonly=True: locks and wards may call it.
# @feature.function(readonly=True)
# def double(n):
#     return 2 * n
