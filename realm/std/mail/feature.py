"""
The ``mail`` feature.

Mail to characters, held by their accounts until they next play (MUD_PLAN
7.4; docs/guides/communication.md).
"""

from __future__ import annotations

from realm.features import Feature
from realm.std.mail import softcode
from realm.std.mail.mail import cmd_mail, deliver, login_observer

feature = Feature(
    'mail',
    requires=['accounts'],
    doc='Mail to characters, kept on their accounts.',
)

feature.setting("MAIL_LIMIT", 100, "How many messages one account's mailbox holds.")
feature.command('mail', cmd_mail, category='communication', help_text='Read and send mail',
                usage='mail [<n> | <player> = <subject>/<body>]', parse_equals=True)
feature.observer(login_observer)
feature.softfn(softcode.send_mail, group='Messaging & prompts', harm=True)


async def _send(engine, frame, sender, payload) -> None:
    """Queued by softcode send_mail()."""
    to, subject, body = payload
    await deliver(sender.name, to, subject, body)


feature.queue_kind("mail", _send)
