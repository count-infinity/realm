"""
The ``basics`` feature.

Session and utility commands: help, who, quit, time; who is on
(``world.services["who"]``, ``online_players()``, ``idle_seconds()``);
player settings (``config``, ``world.services["options"]``) and aliases.
"""

from __future__ import annotations

from types import SimpleNamespace

from realm.features import Feature
from realm.std.basics.aliases import (
    alias_interceptor,
    carry_aliases_over,
    cmd_alias,
    cmd_unalias,
)
from realm.std.basics.commands import (
    cmd_color,
    cmd_commands,
    cmd_help,
    cmd_logout,
    cmd_quit,
    cmd_recall,
    cmd_think,
    cmd_time,
    cmd_uptime,
    recall_to,
)
from realm.std.basics.options import cmd_config, offer_options
from realm.std.basics.presence import (
    WhoService,
    cmd_who,
    idle_seconds,
    linkdead_marker,
    online_players_fn,
)
from realm.std.basics.prompt import cmd_prompt, render_prompt

feature = Feature(
    'basics',
    doc='Session and utility commands: help, who, quit, time.',
)

feature.setting(
    "PROMPT", "<{hp}/{max_hp}hp> ",
    "The prompt shown after each batch of output, unless a player sets their own "
    "with `prompt`. Tokens: any pool by name and `max_<name>`, `{name}`, `{room}`, "
    "`{combat}`, `{level}`, `{xp}`. Empty for none.")
feature.prompt(render_prompt)
feature.command(
    'prompt',
    cmd_prompt,
    category='utility',
    help_text='Show or set your prompt',
    usage='prompt [template|default|off]',
)

feature.command(
    'help',
    cmd_help,
    aliases=['?'],
    category='utility',
    help_text='Show help on commands',
    usage='help [command]',
)
feature.command(
    'commands',
    cmd_commands,
    category='utility',
    help_text='List all available commands',
)
feature.command('who', cmd_who, category='utility', help_text='Show who is online')
feature.marker(linkdead_marker)
feature.softfn(online_players_fn, name='online_players', group='Objects & attributes',
               readonly=True)
feature.softfn(idle_seconds, group='Objects & attributes', readonly=True)


@feature.on_install
def _offer_who(world) -> None:
    """``world.services["who"]``: other features add to its ``fields``;
    ``world.services["recall"]``: ``to(player, room, session)`` recalls
    under ``recall``'s rules (``clans`` sends a member to the clan home)."""
    world.services["who"] = WhoService()
    world.services["recall"] = SimpleNamespace(to=recall_to)


# Player settings (MUD_PLAN 10.4) and aliases (10.3).
feature.on_install(offer_options)
feature.command('config', cmd_config, category='utility',
                help_text='Show or change your settings',
                usage='config [<option> [<value>|default]]')
feature.setting("ALIAS_LIMIT", 50, "How many aliases one character may keep.")
feature.command('alias', cmd_alias, category='utility',
                help_text='Make a short word stand for a command line',
                usage='alias [<word> [= <command>]]', parse_equals=True)
feature.command('unalias', cmd_unalias, category='utility',
                help_text='Remove one of your aliases', usage='unalias <word>')
# After accounts' character creation (0) and a freeze (1), before sleep
# (10): a sleeper's aliased "wake" is still "wake".
feature.input_interceptor(alias_interceptor, order=5)
feature.on_boot(carry_aliases_over)
feature.command(
    'quit',
    cmd_quit,
    aliases=['quit'],
    category='utility',
    help_text='Disconnect from the game',
)
feature.command(
    'logout',
    cmd_logout,
    category='utility',
    help_text='Leave your character, back to the connection screen',
    usage='logout',
)
feature.command(
    'color',
    cmd_color,
    category='utility',
    help_text='Toggle color output',
    usage='color on|off',
)
feature.command(
    'think',
    cmd_think,
    category='utility',
    help_text='Think to yourself',
    usage='think <thought>',
)
feature.command('time', cmd_time, category='utility', help_text='Show the current time')
feature.command(
    'uptime',
    cmd_uptime,
    permission='builder',
    category='utility',
    help_text='Show server uptime',
)
feature.command('recall', cmd_recall, category='utility', help_text='Return to your home')
