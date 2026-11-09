"""Your lists, notes, memories and timers (inside the Echo app; stored encrypted on this PC). Clearing or forgetting
asks first. Also reminders files (.ics) your calendar can import."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Literal

from . import ToolError, tool
from ..words import many

C = "personal"


def _lists(ctx):
    l = getattr(ctx, "lists", None)
    if l is None:
        raise ToolError("lists need the Echo app")
    return l


def _mem(ctx):
    m = getattr(ctx, "memory", None)
    if m is None:
        raise ToolError("memories need the Echo app")
    return m


@tool(C, app=True, keys="add to list shopping todo grocery")
def list_add(items: list[str], list_name: str = "shopping", ctx=None) -> str:
    """Add items to one of your lists (shopping, to-do, packing…)."""
    r = _lists(ctx).add(list_name.strip().lower(), ", ".join(items))
    if r[0] == "added":
        return f"Added {', '.join(r[1]) or 'nothing new'} to your {list_name} list." + (f" Already there: {', '.join(r[2])}." if r[2] else "")
    return {"sensitive": "That looks like a password or code, so I didn't add it.", "full": "That list (or your lists) is full.",
            "empty": "Nothing to add."}[r[0]]


@tool(C, app=True, keys="remove item list cross off done")
def list_remove(item: str, list_name: str = "shopping", ctx=None) -> str:
    """Remove (tick off) an item from a list."""
    l = _lists(ctx)
    name = list_name.strip().lower()
    found = l.find(name, item)
    return f"Removed {found} from {name}." if found and l.remove(name, found) else f"{item} isn't on your {name} list."


@tool(C, app=True, keys="show read list items what's on")
def list_show(list_name: str = "shopping", ctx=None) -> str:
    """What's on a list."""
    items = _lists(ctx).lists.get(list_name.strip().lower(), [])
    return f"{list_name}: " + ", ".join(items) if items else f"Your {list_name} list is empty."


@tool(C, app=True, keys="all lists names")
def lists_all(ctx=None) -> str:
    """All your lists with item counts."""
    l = _lists(ctx).lists
    return ", ".join(f"{k} ({len(v)})" for k, v in l.items()) or "You have no lists yet."


@tool(C, app=True, ask=True, keys="clear empty list delete all items")
def list_clear(list_name: str, ctx=None) -> str:
    """Empty a list. Asks first."""
    from .t_files import confirm
    l = _lists(ctx)
    n = len(l.lists.get(list_name, []))
    if not n:
        return f"Your {list_name} list is already empty."
    confirm(ctx, "Clear this list?", f"{list_name}: {many(n, 'item')}")
    l.clear(list_name)
    return f"Cleared your {list_name} list."


@tool(C, app=True, keys="note save write down jot memo")
def note_add(text: str, ctx=None) -> str:
    """Save a short note (passwords and codes are refused)."""
    r = _lists(ctx).add_note(text)
    return {True: "Noted.", False: "That looks like a password or code, so I didn't save it.", None: "That note was empty or too long."}[r]


@tool(C, app=True, keys="notes search find read")
def notes_search(query: str = "", ctx=None) -> list:
    """Your notes, newest first (optionally only those containing some words)."""
    notes = _lists(ctx).notes
    q = query.lower()
    return [n for n in notes if q in n.lower()][:30] or ["No notes found."]


@tool(C, app=True, keys="remember fact preference memory save about me")
def remember(fact: str, ctx=None) -> str:
    """Remember a lasting fact or preference about the user (never passwords, codes or card numbers)."""
    r = _mem(ctx).remember(fact, "tool")
    return {"saved": "I'll remember that.", "updated": "Updated: I'll remember that instead of the older fact.",
            "duplicate": "I already remember that.", "opinion": "Not saved: I don't store opinions on the user's behalf.",
            "unsafe": "Not saved: memories can't turn off Echo's confirmations or safety rules.",
            "sensitive": "That looks sensitive (a password, code, card or ID number), so I won't remember it. It belongs in the vault.",
            "invalid": "That memory is empty or too long."}.get(r, "I couldn't save that.")


@tool(C, app=True, keys="recall memories what do you know about me search")
def recall(query: str = "", ctx=None) -> list:
    """What Echo remembers about the user (optionally matching some words)."""
    from .. import core
    import time
    items = _mem(ctx).all()
    if query:
        items = core.rank_memories(items, query, time.time())
    return [i["text"] for i in items[:20]] or ["I don't remember anything about that yet."]


@tool(C, app=True, ask=True, keys="forget memory delete remove")
def forget(phrase: str, ctx=None) -> str:
    """Forget memories matching a phrase. Asks first."""
    from .. import core
    from .t_files import confirm
    m = _mem(ctx)
    hits = core.forget_matches(m.all(), phrase)
    if not hits:
        return f"I don't have a memory matching {phrase}."
    confirm(ctx, "Forget this?", "\n".join("• " + h["text"] for h in hits))
    m.delete({h["id"] for h in hits})
    return f"Forgot {len(hits)} memory(ies)."


@tool(C, app=True, keys="timer countdown minutes alarm set start")
def set_timer(minutes: float, label: str = "", ctx=None) -> str:
    """Start a timer (Echo announces it when it ends)."""
    start = getattr(ctx, "start_timer", None)
    if start is None:
        raise ToolError("timers need the Echo app")
    secs = int(minutes * 60)
    if not 1 <= secs <= 86400:
        raise ToolError("timers go from 1 second to 24 hours")
    return start(secs, label or None)[1]


@tool(C, app=True, keys="reminder remind me later at time date daily every day alarm")
def remind_at(time_text: str, message: str, repeat: Literal["", "daily", "weekdays", "weekly", "monthly"] = "", ctx=None) -> str:
    """Remind the user at a time or date in their own words ("8 pm", "tomorrow 9am", "on 10th 9am", "saturday 11am");
    repeat "daily"/"weekdays"/"weekly" for a recurring one. Saved: it survives a restart."""
    remind = getattr(ctx, "reminder", None)
    if remind is None:
        from .t_time import parse_time
        t = parse_time(time_text)
        now = datetime.now()
        when = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
        if when <= now:
            when += timedelta(days=1)
        return set_timer((when - now).total_seconds() / 60, message, ctx=ctx) + f" (at {when:%I:%M %p, %a})."
    ok, msg = remind(time_text, message, repeat)
    if not ok:
        raise ToolError(msg)
    return msg


@tool(C, app=True, keys="reminders timers list show my alarms when is")
def reminders_list(ctx=None) -> str:
    """The reminders and timers Echo has set, with date, time and repeat."""
    show = getattr(ctx, "timers", None)
    if show is None:
        raise ToolError("reminders need the Echo app")
    return show()


@tool(C, app=True, keys="cancel delete remove stop reminder timer alarm change move reschedule")
def reminder_cancel(which: str, ctx=None) -> str:
    """Cancel the reminders/timers whose name matches `which` ("all" for every one). To move one: cancel, then remind_at."""
    cancel = getattr(ctx, "cancel_timers", None)
    if cancel is None:
        raise ToolError("reminders need the Echo app")
    ok, msg = cancel(which)
    if not ok:
        raise ToolError(msg)
    return msg


@tool(C, app=True, keys="timers running list active")
def list_timers(ctx=None) -> str:
    """Timers that are running."""
    t = getattr(ctx, "timers", None)
    if t is None:
        raise ToolError("timers need the Echo app")
    return t()


@tool(C, ask=True, keys="calendar event invite ics file outlook reminder appointment")
def calendar_file(title: str, start: str, duration_minutes: int = 60, location: str = "", notes: str = "", remind_minutes: int = 15, ctx=None) -> str:
    """Make a calendar event file (.ics) in Downloads and open it, so Outlook/Calendar can add it. start like '2026-11-05 15:30'. Asks first."""
    from .. import internet
    from .t_files import confirm
    from .t_time import parse_date, parse_time
    d, _, tm = start.strip().partition(" ")
    s = datetime.combine(parse_date(d), parse_time(tm or "09:00"))
    e = s + timedelta(minutes=duration_minutes)
    esc = lambda x: re.sub(r"([,;\\])", r"\\\1", x).replace("\n", "\\n")
    ics = "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Echo//EN", "BEGIN:VEVENT",
                       f"UID:{s:%Y%m%dT%H%M%S}-{abs(hash(title)) % 10**8}@echo", f"DTSTAMP:{datetime.utcnow():%Y%m%dT%H%M%SZ}",
                       f"DTSTART:{s:%Y%m%dT%H%M%S}", f"DTEND:{e:%Y%m%dT%H%M%S}", f"SUMMARY:{esc(title)}",
                       *([f"LOCATION:{esc(location)}"] if location else []), *([f"DESCRIPTION:{esc(notes)}"] if notes else []),
                       "BEGIN:VALARM", f"TRIGGER:-PT{max(0, remind_minutes)}M", "ACTION:DISPLAY", f"DESCRIPTION:{esc(title)}", "END:VALARM",
                       "END:VEVENT", "END:VCALENDAR", ""])
    path = internet.downloads_dir() / (re.sub(r"[^\w -]", "", title)[:40].strip() or "event") + ".ics"
    confirm(ctx, "Create a calendar event?", f"{title}\n{s:%a %d %b %Y %I:%M %p} for {duration_minutes} min\nSaved to {path}")
    path.write_text(ics, encoding="utf-8")
    import os
    os.startfile(str(path))
    return f"Created {path.name} and opened it — choose Save in your calendar."


@tool(C, app=True, keys="notify popup show message alert")
def show_message(text: str, ctx=None) -> str:
    """Show a message in Echo's window (for results the user should see)."""
    n = getattr(ctx, "notify", None)
    if n is None:
        raise ToolError("this needs the Echo app")
    n(text)
    return "Shown."
