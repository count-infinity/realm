"""
Mail (MUD_PLAN 7.4).

A message is an object tagged ``mail``, held by the recipient's account
(its location is the account, so it is in no room), with ``sender``,
``to``, ``subject``, ``body``, ``sent`` and ``read``. Mail is addressed to
a character and delivered to that character's account, so it waits for
whichever character the person plays next. An account holds at most
``MAIL_LIMIT`` messages.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from realm.core.action_types import ActionType
from realm.core.objects import GameObject
from realm.core.world import find_world, get_world
from realm.gateway.editor import open_editor
from realm.std.accounts.account import account_of, characters_of

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.propagation import Action

MAIL_TAG = "mail"


def mailbox(account: GameObject | None) -> list[GameObject]:
    """The account's messages, oldest first."""
    if account is None:
        return []
    letters = [o for o in account.contents if o.has_tag(MAIL_TAG)]
    return sorted(letters, key=lambda o: (float(o.db.get("sent") or 0), o.id))


def _find_character(name: str) -> GameObject | None:
    found = get_world().store.find_cached(tag="player", name=name.strip())
    return found[0] if found else None


def recipient_problem(name: str) -> tuple[GameObject | None, str]:
    """(the recipient's account, "") or (None, why not)."""
    character = _find_character(name)
    if character is None:
        return None, f"No one called '{name}' plays here."
    account = account_of(character)
    if account is None:
        return None, f"{character.name} cannot receive mail."
    limit = int(get_world().setting("MAIL_LIMIT"))
    if len(mailbox(account)) >= limit:
        return None, f"{character.name}'s mailbox is full."
    return account, ""


def _notify(account: GameObject, sender: str) -> None:
    world = find_world()
    sessions = world.sessions if world is not None else None
    if sessions is None:
        return
    mine = {c.id for c in characters_of(account)}
    for session in sessions.all_sessions():
        if session.player is not None and session.player.id in mine:
            session.player.msg(f"You have new mail from {sender}.")


async def deliver(sender: str, to: str, subject: str, body: str) -> GameObject | None:
    """Put a message in ``to``'s account; None when it cannot be delivered."""
    account, _why = recipient_problem(to)
    if account is None:
        return None
    character = _find_character(to)
    letter = GameObject(name=f"mail: {subject}", tags=[MAIL_TAG], location=account)
    letter.db.sender = sender
    letter.db.to = character.name
    letter.db.subject = subject
    letter.db.body = body
    letter.db.sent = time.time()
    letter.db.read = False
    await get_world().store.save(letter)
    _notify(account, sender)
    return letter


def unread(account: GameObject | None) -> int:
    return sum(1 for m in mailbox(account) if not m.db.get("read"))


async def login_observer(action: Action) -> None:
    """At login: how many unread messages wait."""
    if action.action_type != ActionType.CONNECT or action.actor is None:
        return
    count = unread(account_of(action.actor))
    if count:
        action.actor.msg(f"You have {count} unread message{'s' if count != 1 else ''}. "
                         f"Type 'mail' to read.")


def _when(stamp) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(float(stamp or 0)))


async def cmd_mail(ctx: CommandContext) -> None:
    """
    Read and send mail. Mail to a character waits on their account until
    they next play any of their characters.

    Usage: mail                          list your messages
           mail <n>                      read one
           mail <player> = <subject>/<body>
                                         send
           mail <player> = <subject>     write the body in the line editor
           mail/reply <n> [= <body>]     answer one
           mail/delete <n>               delete one
    """
    player = ctx.player
    account = ctx.session.account or account_of(player)
    switch = ctx.switches[0] if ctx.switches else ""
    raw = ctx.args or ""
    left = (ctx.left_args if "=" in raw else raw).strip()
    right = ctx.right_args.strip() if "=" in raw else ""
    letters = mailbox(account)

    def numbered(word: str) -> GameObject | None:
        return letters[int(word) - 1] if word.isdigit() and 0 < int(word) <= len(letters) \
            else None

    if switch in ("delete", "reply"):
        letter = numbered(left)
        if letter is None:
            await ctx.session.send(f"You have no message {left}.")
            return
        if switch == "delete":
            letter.location = None
            await get_world().store.delete(letter)
            await ctx.session.send(f"Message {left} deleted.")
            return
        await _send(ctx, str(letter.db.sender), "Re: " + str(letter.db.subject), right)
        return
    if switch:
        await ctx.session.send(f"Unknown switch /{switch}. See: help mail")
        return
    if "=" in raw:
        subject, _, body = right.partition("/")
        if not left or not subject.strip():
            await ctx.session.send("Usage: mail <player> = <subject>/<body>")
            return
        await _send(ctx, left, subject.strip(), body.strip())
        return
    if left:
        letter = numbered(left)
        if letter is None:
            await ctx.session.send(f"You have no message {left}.")
            return
        letter.db.read = True
        ctx.session.send_paged("\n".join([
            f"From: {letter.db.sender}", f"To: {letter.db.to}",
            f"Subject: {letter.db.subject}", f"Date: {_when(letter.db.sent)}", "",
            str(letter.db.body or "")]))
        return
    if account is None:
        await ctx.session.send("You have no mailbox.")
        return
    if not letters:
        await ctx.session.send("You have no mail.")
        return
    lines = ["Your mail:"]
    for n, letter in enumerate(letters, start=1):
        mark = "*" if not letter.db.get("read") else " "
        lines.append(f"  {n:>3} {mark} {str(letter.db.sender):14} {str(letter.db.subject):30} "
                     f"{_when(letter.db.sent)}")
    lines.append("(* unread)  mail <n> reads one.")
    ctx.session.send_paged("\n".join(lines))


async def _send(ctx: CommandContext, to: str, subject: str, body: str) -> None:
    """Send the letter; with no body, write it in the line editor first."""
    _account, why = recipient_problem(to)
    if why:
        await ctx.session.send(why)
        return
    if body:
        letter = await deliver(ctx.player.name, to, subject, body)
        await ctx.session.send(f"Mail sent to {letter.db.to}.")
        return

    async def send(text: str) -> bool | None:
        if not text.strip():
            await ctx.session.send("The letter is empty. Write something, or .q to "
                                   "throw it away.")
            return None
        _account, why = recipient_problem(to)
        if why:
            await ctx.session.send(why)
            return None
        letter = await deliver(ctx.player.name, to, subject, text.rstrip("\n"))
        await ctx.session.send(f"Mail sent to {letter.db.to}.")
        return True

    open_editor(ctx.session, "", title=f"a letter to {to}: {subject}", on_save=send)


__all__ = ["MAIL_TAG", "mailbox", "recipient_problem", "deliver", "unread", "login_observer",
           "cmd_mail"]
