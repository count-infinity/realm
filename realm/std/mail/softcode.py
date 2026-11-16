"""
Softcode functions: mail. The ``mail`` feature declares each; the first
parameter is the run's frame.
"""

from __future__ import annotations

from realm.std.mail.mail import recipient_problem


def send_mail(frame, to: str, subject: str, body: str) -> bool:
    """
    Send mail to a character, from this object (system mail: a guild's
    dues notice, a quest's reward slip). False when the character has no
    account or a full mailbox. Queued.

    Example: send_mail('Gus', 'Dues', 'Your guild dues are late.')
    """
    account, _why = recipient_problem(str(to))
    if account is None or frame.executor is None:
        return False
    frame.command_queue.append(('mail', frame.executor, (str(to), str(subject), str(body))))
    return True


__all__ = ["send_mail"]
