"""
The ``social`` feature.

Disposition, persuasion, following and parties.
"""

from __future__ import annotations

from realm.behaviors.effects import DispositionBoostBehavior
from realm.commands.builtin.social import (
    cmd_fasttalk,
    cmd_follow,
    cmd_greet,
    cmd_party,
    cmd_persuade,
    cmd_unfollow,
)
from realm.features import Feature
from realm.std.social import softcode

feature = Feature(
    'social',
    requires=['rules'],
    doc='Disposition, persuasion, following and parties.',
)

feature.command(
    'consider',
    cmd_greet,
    aliases=['con'],
    category='social',
    help_text="Size up an NPC's attitude toward you",
    usage='consider <npc>',
)
feature.command(
    'persuade',
    cmd_persuade,
    category='social',
    help_text='Win someone over honestly (persuasion vs will)',
    usage='persuade <npc>',
)
feature.command(
    'fasttalk',
    cmd_fasttalk,
    aliases=['fast-talk'],
    category='social',
    help_text='Bend the truth for temporary goodwill (fast_talk vs detect_lies)',
    usage='fasttalk <npc>',
)
feature.command(
    'follow',
    cmd_follow,
    category='social',
    help_text='Walk exits after someone (follow with no target stops)',
    usage='follow [<target>]',
)
feature.command(
    'unfollow',
    cmd_unfollow,
    category='social',
    help_text='Stop following',
    usage='unfollow',
)
feature.command(
    'party',
    cmd_party,
    aliases=['group'],
    category='social',
    help_text="Show who's traveling with you",
    usage='party',
)

feature.behavior(DispositionBoostBehavior)


@feature.after_traverse
async def bring_followers(actor, origin, destination, exit_obj, *, fleeing):
    """Followers walk after their leader (a room-local scan of the origin,
    so chains cascade and cycles self-resolve: the mover already left the
    room being scanned). Fleeing breaks the chain: you escape alone."""
    if fleeing:
        return
    from realm.core.party import bring_followers as _bring
    await _bring(actor, origin, destination, exit_obj)


# --- softcode ------------------------------------------------------------------

feature.softfn(softcode.disposition, group='NPCs & behaviors', readonly=True)
feature.softfn(softcode.adjust_disposition, group='NPCs & behaviors')
feature.softfn(softcode.reaction_roll, group='NPCs & behaviors')
