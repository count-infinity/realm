"""
The ``operations`` feature.

The administrator's tools for a live server: ``@wall``, ``@shutdown``,
``@reboot``, ``@snoop``, ``@freeze`` and ``@thaw``. (Idle and link-dead
sessions, flood control, backups and migrations are the kernel's and
``realm``'s: docs/guides/operations.md.)
"""

from __future__ import annotations

from realm.features import Feature
from realm.std.operations.commands import (
    cmd_freeze,
    cmd_reboot,
    cmd_shutdown,
    cmd_snoop,
    cmd_thaw,
    cmd_wall,
    frozen_interceptor,
)

feature = Feature(
    'operations',
    doc='Admin tools for a live server: @wall, @shutdown, @reboot, @snoop, @freeze.',
)

feature.command('@wall', cmd_wall, permission='admin', category='admin',
                help_text='Announce to everyone connected', usage='@wall <message>')
feature.command('@shutdown', cmd_shutdown, permission='admin', category='admin',
                help_text='Count down, save and stop the server',
                usage='@shutdown [seconds] [= reason] | @shutdown/cancel', parse_equals=True)
feature.command('@reboot', cmd_reboot, permission='admin', category='admin',
                help_text='Count down, save and restart the server',
                usage='@reboot [seconds] [= reason] | @reboot/cancel', parse_equals=True)
feature.command('@snoop', cmd_snoop, permission='admin', category='admin',
                help_text="See a player's output", usage='@snoop [player]')
feature.command('@freeze', cmd_freeze, permission='admin', category='admin',
                help_text="Refuse a player's input", usage='@freeze <player>')
feature.command('@thaw', cmd_thaw, permission='admin', category='admin',
                help_text='Let a frozen player act again', usage='@thaw <player>')
# Before every other interceptor: a frozen sleeper is frozen first.
feature.input_interceptor(frozen_interceptor, order=1)
