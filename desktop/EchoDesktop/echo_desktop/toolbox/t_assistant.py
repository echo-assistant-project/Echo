"""Your personal assistant: tasks with due dates, a planned day, follow-ups, people (birthdays, last contact), habits,
money, journal, focus sessions, meeting notes, "my day" and weekly review, and phrases you teach Echo.

Modelled on what made assistants stick (see docs/PA_RESEARCH.md): one reliable place for the small things people
forget (Lindy/Superhuman follow-ups), a day planned around your time (Motion/Reclaim), meeting notes that become tasks
(Granola), a personal daily brief you steer (ChatGPT Pulse → scheduled briefings), and being understood (teach Echo
your own phrases). Everything is local and encrypted (pa.Store); deleting asks first.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Literal, Optional

from . import ToolError, fmt, tool
from .. import pa
from ..words import many

C = "assistant"
PRIORITY = {"high": 0, "normal": 1, "low": 2}


def _store(ctx) -> pa.Store:
    s = getattr(ctx, "pa_store", None)
    if s is None:
        s = _default_store()
    return s


_DEFAULT: Optional[pa.Store] = None


def _default_store() -> pa.Store:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = pa.Store()
    return _DEFAULT


def _now(ctx) -> datetime:
    f = getattr(ctx, "now", None)
    return f() if callable(f) else datetime.now()


def _clean(text: str, limit: int = 300) -> str:
    text = " ".join(str(text or "").split())[:limit]
    from ..core import is_sensitive
    if is_sensitive(text):
        raise ToolError("that looks like a password, PIN or card number, so I didn't save it")
    return text


def _due(t: dict) -> Optional[datetime]:
    d = pa.parse_iso(t.get("due"))
    if d is not None and not t.get("timed"):
        d = d.replace(hour=23, minute=59)
    return d


def _task_line(t: dict, now: datetime) -> str:
    bits = [t["title"]]
    if t.get("due"):
        bits.append("(" + pa.say_when(pa.parse_iso(t["due"]), t.get("timed", False), now) + ")")
    if t.get("priority") == "high":
        bits.append("[high]")
    if t.get("project"):
        bits.append("#" + t["project"])
    return " ".join(bits)


def _rank(t: dict, now: datetime) -> tuple:
    due = _due(t)
    return (0 if due and due < now else 1, PRIORITY.get(t.get("priority", "normal"), 1),
            due or datetime.max, t.get("created", ""))


# ------------------------------------------------------------------------------------------------ tasks
@tool(C, keys="todo to-do task add remember to do deadline due", ex={"text": "send the invoice to Ravi by friday 5pm !high #work"})
def task_add(text: str, due: str = "", priority: Literal["low", "normal", "high", ""] = "", project: str = "", minutes: int = 0,
             repeat: Literal["", "daily", "weekdays", "weekly", "monthly"] = "", ctx=None) -> str:
    """Add a task. Say the due date in plain words ("tomorrow 5pm", "by friday", "in 3 days"); "!high" or "urgent"
    marks it important, "#work" puts it in a project, "~45m" says how long it takes."""
    now = _now(ctx)
    task, when = _make_task(text, now, due, priority, project, minutes, repeat)
    with _store(ctx).edit() as d:
        # the same open task again (an AI loop, or saying it twice): keep one, and say so
        same = next((t for t in d["tasks"] if not t.get("done") and t["title"].strip().lower() == task["title"].strip().lower()
                     and (t.get("due") or "")[:10] == (task.get("due") or "")[:10]), None)
        if same is not None:
            return f"Already on your list: {same['title']}" + (f" (due {pa.say_when(pa.parse_iso(same['due']), same.get('timed'), now)})"
                                                               if same.get("due") else "") + ". I didn't add it again."
        d["tasks"].append(task)
    extra = []
    if task["due"]:
        extra.append("due " + pa.say_when(when.at, when.has_time, now))
    if task["priority"] != "normal":
        extra.append(task["priority"] + " priority")
    if task["repeat"]:
        extra.append("repeats " + task["repeat"])
    return f"Added task: {task['title']}" + (f" ({', '.join(extra)})" if extra else "") + "."


def _make_task(text: str, now: datetime, due: str = "", priority: str = "", project: str = "", minutes: int = 0,
               repeat: str = "") -> tuple:
    """A new task (not saved yet) from what was said: (task, when)."""
    raw = text[:2000]
    level = r"(?:,?\s*(?:as\s+|with\s+|at\s+)?(?:a\s+)?(high|top|low)\s+priority|(high|low)[- ]pri(?:ority)?\b)"
    if not priority:
        said = re.search(r"(?i)" + level, raw)
        if said:
            priority = "low" if (said.group(1) or said.group(2) or "").lower() == "low" else "high"
        elif re.search(r"(?i)(!high|!!|\burgent\b|\bimportant\b|\basap\b)", raw):
            priority = "high"
        elif re.search(r"(?i)(!low|\bsomeday\b|\bwhenever\b)", raw):
            priority = "low"
    raw = re.sub(r"(?i)" + level, " ", raw)             # "… tomorrow high priority": the flag, not part of the title
    raw = re.sub(r"(?i)(!high|!low|!!|\burgent\b|\basap\b|\bsomeday\b|\bwhenever\b)", " ", raw)
    tag = re.search(r"#([\w-]{1,30})", raw)
    if tag and not project:
        project = tag.group(1)
    raw = re.sub(r"#[\w-]{1,30}", " ", raw)
    est = re.search(r"~\s*(\d+)\s*(m|min|mins|h|hr|hours?)\b", raw, re.I)
    if est and not minutes:
        minutes = int(est.group(1)) * (60 if est.group(2).lower().startswith("h") else 1)
    raw = re.sub(r"~\s*\d+\s*(m|min|mins|h|hr|hours?)\b", " ", raw, flags=re.I)
    rep = re.search(r"(?i)\b(every ?day|daily|every weekday|weekdays|every week|weekly|every month|monthly)\b", raw)
    if rep and not repeat:
        w = rep.group(1).lower().replace(" ", "")
        repeat = "daily" if w in ("everyday", "daily") else "weekdays" if "weekday" in w else "weekly" if "week" in w else "monthly"
        raw = raw[:rep.start()] + " " + raw[rep.end():]
    when = pa.parse_when(due or raw, now)
    title = _clean(pa.parse_when(raw, now).rest if due else when.rest, 200)
    title = re.sub(r"(?i)^(add (a )?task( to)?|remind me to|i need to|i have to|todo|to do)\s+", "", title).strip() or "task"
    task = {"id": pa.new_id(), "title": title, "due": pa.iso(when.at), "timed": when.has_time, "priority": priority or "normal",
            "project": project.strip().lower(), "minutes": max(5, min(minutes or 30, 600)), "repeat": repeat,
            "created": pa.iso(now), "done": None}
    return task, when


@tool(C, keys="tasks todo list today overdue upcoming plate what do i have", ex={"view": "today"})
def tasks(view: Literal["today", "overdue", "upcoming", "all", "done", "nodate"] = "today", project: str = "", ctx=None) -> str:
    """Your tasks: today (overdue + due today + important), overdue, upcoming (next 7 days), all, done, or nodate."""
    now = _now(ctx)
    items = _store(ctx).read()["tasks"]
    if project:
        items = [t for t in items if t.get("project") == project.strip().lower().lstrip("#")]
    if view == "done":
        done = sorted((t for t in items if t.get("done")), key=lambda t: t["done"], reverse=True)[:15]
        return "Done recently: " + "; ".join(t["title"] for t in done) + "." if done else "Nothing marked done yet."
    open_ = [t for t in items if not t.get("done")]
    end_today = now.replace(hour=23, minute=59)
    if view == "overdue":
        sel = [t for t in open_ if _due(t) and _due(t) < now]
    elif view == "today":
        sel = [t for t in open_ if (_due(t) and _due(t) <= end_today) or (not t.get("due") and t.get("priority") == "high")]
    elif view == "upcoming":
        sel = [t for t in open_ if _due(t) and now < _due(t) <= end_today + timedelta(days=7)]
    elif view == "nodate":
        sel = [t for t in open_ if not t.get("due")]
    else:
        sel = open_
    sel.sort(key=lambda t: _rank(t, now))
    if not sel:
        if view == "today" and open_:                     # name what's next instead of just counting it
            nxt = sorted(open_, key=lambda t: _rank(t, now))
            rest = f" (and {len(nxt) - 3} more)" if len(nxt) > 3 else ""
            return ("Nothing due today. Coming up: " + "; ".join(_task_line(t, now) for t in nxt[:3]) + rest + ".")
        return {"today": "Nothing due today. Your task list is empty.",
                "overdue": "Nothing overdue. Nice.", "upcoming": "Nothing due in the next week."}.get(view, "No tasks there.")
    lines = [f"{i}. {_task_line(t, now)}" for i, t in enumerate(sel[:20], 1)]
    more = f"\n…and {len(sel) - 20} more." if len(sel) > 20 else ""
    return f"{len(sel)} task{'s' if len(sel) != 1 else ''} ({view}):\n" + "\n".join(lines) + more


@tool(C, keys="snooze postpone move reschedule delay task later", ex={"task": "invoice", "until": "monday 10am"})
def task_snooze(task: str, until: str = "tomorrow", ctx=None) -> str:
    """Move a task to a later date/time."""
    now = _now(ctx)
    w = pa.parse_when(until, now)
    if w.at is None:
        raise ToolError(f"I didn't understand “{until}” as a date")
    with _store(ctx).edit() as d:
        t = pa.match_one([x for x in d["tasks"] if not x.get("done")], task)
        if t is None:
            raise ToolError(f"I couldn't find an open task like “{task}”")
        t["due"], t["timed"] = pa.iso(w.at), w.has_time
    return f"Moved “{t['title']}” to {pa.say_when(w.at, w.has_time, now)}."


def _next_due(t: dict) -> Optional[str]:
    d = pa.parse_iso(t.get("due"))
    if not d or not t.get("repeat"):
        return None
    if t["repeat"] == "daily":
        d += timedelta(days=1)
    elif t["repeat"] == "weekdays":
        d += timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
    elif t["repeat"] == "weekly":
        d += timedelta(weeks=1)
    else:
        d = datetime.combine(pa._add_months(d.date(), 1), d.time())
    return pa.iso(d)


@tool(C, keys="done complete finish tick off mark task", ex={"task": "invoice"})
def task_done(task: str, ctx=None) -> str:
    """Mark a task done (by its words or id). Repeating tasks move to their next date."""
    now = _now(ctx)
    with _store(ctx).edit() as d:
        t = pa.match_one([x for x in d["tasks"] if not x.get("done")], task)
        if t is None:
            raise ToolError(f"I couldn't find an open task like “{task}”")
        nxt = _next_due(t)
        if nxt:
            done = dict(t, id=pa.new_id(), done=pa.iso(now), repeat="")
            d["tasks"].append(done)
            t["due"] = nxt
            return f"Done: {t['title']}. Next one is {pa.say_when(pa.parse_iso(nxt), t.get('timed', False), now)}."
        t["done"] = pa.iso(now)
    left = sum(1 for x in _store(ctx).read()["tasks"] if not x.get("done") and _due(x) and _due(x) <= now.replace(hour=23, minute=59))
    return f"Done: {t['title']}." + (f" {left} still due today." if left else "")


@tool(C, ask=True, keys="delete remove task cancel drop", ex={"task": "old task"})
def task_delete(task: str, ctx=None) -> str:
    """Delete a task for good (asks first)."""
    st = _store(ctx)
    t = pa.match_one(st.read()["tasks"], task)
    if t is None:
        raise ToolError(f"I couldn't find a task like “{task}”")
    if ctx is not None and not ctx.confirm("Delete this task?", t["title"]):
        return "Kept it."
    with st.edit() as d:
        d["tasks"] = [x for x in d["tasks"] if x["id"] != t["id"]]
    return f"Deleted “{t['title']}”."


def _busy_blocks(busy: str, day: date) -> list:
    out = []
    for a, b in re.findall(r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:-|to|–)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", busy, re.I):
        ta = pa.parse_when("at " + a if not re.search("[ap]m", a, re.I) else a, datetime.combine(day, datetime.min.time()))
        tb = pa.parse_when("at " + b if not re.search("[ap]m", b, re.I) else b, datetime.combine(day, datetime.min.time()))
        if ta.at and tb.at:
            s = datetime.combine(day, ta.at.time())
            e = datetime.combine(day, tb.at.time())
            if e > s:
                out.append((s, e))
    return sorted(out)


@tool(C, keys="plan my day schedule time block timebox calendar priorities agenda", ex={"busy": "11-12 standup, 3pm-4pm call"})
def plan_my_day(busy: str = "", end: str = "6pm", start: str = "", break_minutes: int = 10, ctx=None) -> str:
    """Time-block today: fits your open tasks (overdue and important first) into the free time between now (or
    `start`) and `end`, around busy times you name ("11-12 standup, 3pm-4pm call"), with short breaks."""
    now = _now(ctx)
    today = now.date()
    s = pa.parse_when(start or "", now).at if start else None
    begin = datetime.combine(today, s.time()) if s else max(now, datetime.combine(today, datetime.min.time()).replace(hour=9))
    begin = begin.replace(second=0, microsecond=0)
    begin += timedelta(minutes=(5 - begin.minute % 5) % 5)
    e = pa.parse_when(end, now).at
    finish = datetime.combine(today, e.time()) if e else datetime.combine(today, datetime.min.time()).replace(hour=18)
    if finish <= begin:
        return "There's no time left in the working day. Try “plan my day until 9pm”, or plan tomorrow's first task now."
    blocks = [(a, b, "📅 busy") for a, b in _busy_blocks(busy, today)]
    open_ = [t for t in _store(ctx).read()["tasks"] if not t.get("done")]
    week = now.replace(hour=23, minute=59) + timedelta(days=3)
    cand = [t for t in open_ if (_due(t) and _due(t) <= week) or t.get("priority") == "high"] or open_
    cand.sort(key=lambda t: _rank(t, now))
    timed = [t for t in cand if t.get("timed") and _due(t) and _due(t).date() == today]
    for t in timed:                                  # fixed-time tasks are appointments
        blocks.append((_due(t), _due(t) + timedelta(minutes=t.get("minutes", 30)), "📅 " + t["title"]))
    blocks.sort()
    plan, cursor, worked, left = [], begin, 0, []
    for t in [t for t in cand if t not in timed]:
        need = timedelta(minutes=t.get("minutes", 30))
        placed = False
        while cursor + need <= finish:
            clash = next(((a, b) for a, b, _ in blocks if a < cursor + need and b > cursor), None)
            if clash:
                cursor = max(cursor, clash[1])
                continue
            plan.append((cursor, cursor + need, _task_line(t, now)))
            cursor += need
            worked += need.seconds // 60
            if worked >= 90:                         # a short break after ~90 minutes of work
                cursor += timedelta(minutes=max(0, break_minutes))
                worked = 0
            placed = True
            break
        if not placed:
            left.append(t["title"])
    rows = [blk for blk in blocks if begin <= blk[0] < finish] + plan
    rows.sort()
    if not plan:
        return "Nothing to plan: no open tasks fit today. Add one with “add task …”."
    out = [f"{a.strftime('%I:%M').lstrip('0')}–{b.strftime('%I:%M %p').lstrip('0')}  {label}" for a, b, label in rows]
    tail = f"\nDidn't fit today: {', '.join(left[:6])}." if left else ""
    return f"Plan for today ({len(plan)} task{'s' if len(plan) != 1 else ''}):\n" + "\n".join(out) + tail


@tool(C, keys="what next should i do now focus priority best task")
def what_next(minutes_free: int = 0, ctx=None) -> str:
    """The one task to do now: overdue first, then important, then soonest due — and it fits the time you have."""
    now = _now(ctx)
    open_ = sorted((t for t in _store(ctx).read()["tasks"] if not t.get("done")), key=lambda t: _rank(t, now))
    if minutes_free:
        fit = [t for t in open_ if t.get("minutes", 30) <= minutes_free]
        open_ = fit or open_
    if not open_:
        return "Your task list is empty. Enjoy it, or add something with “add task …”."
    t = open_[0]
    why = "it's overdue" if _due(t) and _due(t) < now else "it's important" if t.get("priority") == "high" else \
        "it's due soonest" if t.get("due") else "it's the oldest open task"
    return f"Do this next: {_task_line(t, now)} — {why}, about {t.get('minutes', 30)} minutes."


# ------------------------------------------------------------------------------------------------ follow-ups
@tool(C, keys="follow up chase remind check back waiting on reply", ex={"text": "Ravi about the invoice in 3 days"})
def follow_up(text: str, ctx=None) -> str:
    """Remember to follow up with someone or on something ("Ravi about the invoice in 3 days"). Default: in 3 days."""
    now = _now(ctx)
    w = pa.parse_when(text, now)
    at = w.at or datetime.combine(now.date() + timedelta(days=3), datetime.min.time())
    what = _clean(re.sub(r"(?i)^(follow up (with|on)|chase|check (back )?(with|on))\s+", "", w.rest), 200) or "follow-up"
    with _store(ctx).edit() as d:
        d["followups"].append({"id": pa.new_id(), "title": what, "due": pa.iso(at), "timed": w.has_time, "created": pa.iso(now), "done": None})
    return f"I'll remind you to follow up: {what} — {pa.say_when(at, w.has_time, now)}."


@tool(C, keys="follow ups waiting on chase list due")
def follow_ups(view: Literal["due", "all"] = "due", ctx=None) -> str:
    """Follow-ups that are due now (or all open ones)."""
    now = _now(ctx)
    items = [f for f in _store(ctx).read()["followups"] if not f.get("done")]
    if view == "due":
        items = [f for f in items if pa.parse_iso(f["due"]) <= now.replace(hour=23, minute=59)]
    items.sort(key=lambda f: f["due"])
    if not items:
        return "No follow-ups due." if view == "due" else "No open follow-ups."
    return "Follow up: " + "; ".join(f"{f['title']} ({pa.say_when(pa.parse_iso(f['due']), f.get('timed', False), now)})" for f in items[:15]) + "."


@tool(C, keys="followed up done close follow-up", ex={"item": "Ravi invoice"})
def follow_up_done(item: str, ctx=None) -> str:
    """Close a follow-up."""
    with _store(ctx).edit() as d:
        f = pa.match_one([x for x in d["followups"] if not x.get("done")], item)
        if f is None:
            raise ToolError(f"No open follow-up like “{item}”")
        f["done"] = pa.iso(_now(ctx))
    return f"Closed: {f['title']}."


# ------------------------------------------------------------------------------------------------ people
def _person(d: dict, name: str, create: bool = True) -> Optional[dict]:
    key = " ".join(name.lower().split())
    if not key:
        raise ToolError("whose? say a name")
    if key in d["people"]:
        return d["people"][key]
    hit = next((v for k, v in d["people"].items() if k.split()[0] == key.split()[0] and len(key.split()) == 1), None)
    if hit or not create:
        return hit
    d["people"][key] = {"name": _clean(name.strip().title(), 60), "notes": [], "birthday": None, "contacts": []}
    return d["people"][key]


@tool(C, keys="person contact friend family remember about notes crm", ex={"name": "Ravi", "note": "likes filter coffee; daughter Asha"})
def person_note(name: str, note: str, ctx=None) -> str:
    """Remember something about a person (preferences, family, what you talked about). "birthday is 3 May" sets the birthday."""
    now = _now(ctx)
    with _store(ctx).edit() as d:
        p = _person(d, name)
        b = re.search(r"(?i)birthday\s*(?:is|on|:)?\s*(.+)$", note)
        if b:
            w = pa.parse_when(b.group(1), now)
            if w.at:
                p["birthday"] = w.at.strftime("%m-%d")
                return f"Saved: {p['name']}'s birthday is {w.at.strftime('%d %B').lstrip('0')}."
        p["notes"].append({"text": _clean(note), "at": pa.iso(now)})
        p["notes"] = p["notes"][-50:]
    return f"Noted about {p['name']}: {note}"


@tool(C, keys="birthday add save date of birth", ex={"text": "Ravi 3 May"})
def birthday_add(text: str, ctx=None) -> str:
    """Save a birthday: "Ravi 3 May", "Mom's birthday is 12/08"."""
    now = _now(ctx)
    w = pa.parse_when(re.sub(r"(?i)('s)?\s*birthday( is| on)?", " ", text), now)
    if w.at is None or not w.rest:
        raise ToolError("say a name and a date, like “Ravi 3 May”")
    with _store(ctx).edit() as d:
        p = _person(d, w.rest)
        p["birthday"] = w.at.strftime("%m-%d")
    return f"Saved: {p['name']}'s birthday is {w.at.strftime('%d %B').lstrip('0')}."


@tool(C, keys="who is what do i know about person notes", ex={"name": "Ravi"})
def person_show(name: str, ctx=None) -> str:
    """Everything you told Echo about someone: notes, birthday, when you last talked."""
    now = _now(ctx)
    p = _person(_store(ctx).read(), name, create=False)
    if p is None:
        return f"I don't have notes about {name} yet. Say “note about {name}: …”."
    parts = [p["name"] + "."]
    if p.get("birthday"):
        m, dd = map(int, p["birthday"].split("-"))
        parts.append(f"Birthday {date(2000, m, dd).strftime('%d %B').lstrip('0')}.")
    if p.get("contacts"):
        last = pa.parse_iso(p["contacts"][-1]["at"])
        parts.append(f"Last talked {(now.date() - last.date()).days} days ago" + (f" ({p['contacts'][-1]['how']})" if p['contacts'][-1].get('how') else "") + ".")
    if p.get("notes"):
        parts.append("Notes: " + "; ".join(n["text"] for n in p["notes"][-8:]) + ".")
    return " ".join(parts)


def _upcoming_birthdays(d: dict, today: date, days: int) -> list:
    out = []
    for p in d["people"].values():
        if not p.get("birthday"):
            continue
        m, dd = map(int, p["birthday"].split("-"))
        nxt = pa._future_year(m, dd, today)
        gap = (nxt - today).days
        if gap <= days:
            out.append((gap, p["name"], nxt))
    return sorted(out)


@tool(C, keys="birthdays upcoming coming up soon this week month")
def birthdays_upcoming(days: int = 30, ctx=None) -> str:
    """Birthdays in the next N days."""
    today = _now(ctx).date()
    up = _upcoming_birthdays(_store(ctx).read(), today, days)
    if not up:
        return f"No birthdays in the next {many(days, 'day')} (that I know of)."
    return "Coming up: " + "; ".join(f"{n} — {'today!' if g == 0 else 'tomorrow' if g == 1 else d.strftime('%a %d %b').replace(' 0', ' ')}" for g, n, d in up) + "."


@tool(C, keys="talked called met spoke contact log touch base", ex={"name": "Ravi", "how": "call"})
def contacted(name: str, how: str = "", ctx=None) -> str:
    """Log that you talked to someone (call, met, message)."""
    with _store(ctx).edit() as d:
        p = _person(d, name)
        p["contacts"].append({"at": pa.iso(_now(ctx)), "how": _clean(how, 40)})
        p["contacts"] = p["contacts"][-100:]
    return f"Logged: talked to {p['name']}" + (f" ({how})" if how else "") + "."


@tool(C, keys="reconnect catch up haven't talked call who should i")
def people_to_reconnect(days: int = 30, ctx=None) -> str:
    """People you haven't talked to in N days (from what you've logged)."""
    now = _now(ctx)
    stale = []
    for p in _store(ctx).read()["people"].values():
        if p.get("contacts"):
            gap = (now.date() - pa.parse_iso(p["contacts"][-1]["at"]).date()).days
            if gap >= days:
                stale.append((gap, p["name"]))
    if not stale:
        return f"You've been in touch with everyone you've logged in the last {many(days, 'day')}."
    stale.sort(reverse=True)
    return "Maybe catch up with: " + ", ".join(f"{n} ({g} days)" for g, n in stale[:8]) + "."


# ------------------------------------------------------------------------------------------------ habits
@tool(C, keys="habit track new start daily routine streak", ex={"name": "walk 30 minutes", "per_week": 5})
def habit_add(name: str, per_week: int = 7, ctx=None) -> str:
    """Start tracking a habit (how many days a week you aim for)."""
    key = _clean(name, 60).lower()
    with _store(ctx).edit() as d:
        d["habits"].setdefault(key, {"name": key, "per_week": max(1, min(7, per_week)), "days": []})["per_week"] = max(1, min(7, per_week))
    return f"Tracking “{key}”, {per_week} day{'s' if per_week != 1 else ''} a week. Say “habit done {key}” when you do it."


def _streak(days: set, today: date) -> int:
    n, d = 0, today if today.isoformat() in days else today - timedelta(days=1)
    while d.isoformat() in days:
        n += 1
        d -= timedelta(days=1)
    return n


@tool(C, keys="habit done did log check tick", ex={"name": "walk"})
def habit_done(name: str, day: str = "today", ctx=None) -> str:
    """Tick off a habit for today (or another day)."""
    now = _now(ctx)
    w = pa.parse_when(day, now)
    d_ = (w.at or now).date()
    with _store(ctx).edit() as d:
        h = d["habits"].get(name.strip().lower()) or pa.match_one(list(d["habits"].values()), name, "name")
        if h is None:
            raise ToolError(f"you're not tracking “{name}” yet — say “new habit {name}”")
        if d_.isoformat() not in h["days"]:
            h["days"].append(d_.isoformat())
            h["days"] = sorted(h["days"])[-400:]
        s = _streak(set(h["days"]), now.date())
    return f"✓ {h['name']}. Streak: {s} day{'s' if s != 1 else ''}."


@tool(C, keys="habits streaks progress how am i doing")
def habits(ctx=None) -> str:
    """Your habits: this week's count against the goal, and current streaks."""
    now = _now(ctx)
    hs = _store(ctx).read()["habits"]
    if not hs:
        return "You're not tracking any habits. Say “new habit drink water”."
    monday = now.date() - timedelta(days=now.weekday())
    out = []
    for h in hs.values():
        days = set(h["days"])
        week = sum(1 for i in range(7) if (monday + timedelta(days=i)).isoformat() in days)
        today = "✓" if now.date().isoformat() in days else "·"
        out.append(f"{today} {h['name']}: {week}/{h['per_week']} this week, streak {_streak(days, now.date())}")
    return "\n".join(out)


# ------------------------------------------------------------------------------------------------ money
@tool(C, keys="spent expense paid money log rupees cost", ex={"text": "250 on lunch"})
def expense_add(text: str, amount: float = 0, category: str = "", ctx=None) -> str:
    """Log money you spent: "250 on lunch", "₹1,200 petrol", "2k amazon shoes". Category is guessed if not given."""
    amt, what, cat = pa.parse_expense(text)
    if amount:
        amt = amount
    if not amt or amt <= 0:
        raise ToolError("how much? say a number, like “250 on lunch”")
    cat = (category or cat).strip().lower()
    now = _now(ctx)
    with _store(ctx).edit() as d:
        d["expenses"].append({"id": pa.new_id(), "amount": amt, "what": _clean(what, 120), "category": cat, "at": pa.iso(now)})
        month = now.strftime("%Y-%m")
        spent = sum(e["amount"] for e in d["expenses"] if e["at"].startswith(month))
        cat_spent = sum(e["amount"] for e in d["expenses"] if e["at"].startswith(month) and e["category"] == cat)
        budget, cbudget = d["budgets"].get("total"), d["budgets"].get(cat)
    msg = f"Logged ₹{fmt(amt)} for {what} ({cat}). This month: ₹{fmt(spent)}."
    if cbudget and cat_spent > cbudget:
        msg += f" ⚠ Over your {cat} budget (₹{fmt(cat_spent)} of ₹{fmt(cbudget)})."
    elif budget:
        msg += f" {round(100 * spent / budget)}% of your monthly budget."
    return msg


def _period(period: str, now: datetime) -> tuple:
    p = period.strip().lower()
    if p == "today":
        s = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return s, s + timedelta(days=1), "today"
    if p == "week":
        s = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        return s, s + timedelta(days=7), "this week"
    if p in ("last month", "last_month"):
        first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        s = (first - timedelta(days=1)).replace(day=1)
        return s, first, s.strftime("%B")
    if re.fullmatch(r"\d{4}-\d{2}", p):
        s = datetime.strptime(p + "-01", "%Y-%m-%d")
        return s, datetime.combine(pa._add_months(s.date(), 1), datetime.min.time()), s.strftime("%B %Y")
    s = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return s, datetime.combine(pa._add_months(s.date(), 1), datetime.min.time()), "this month"


@tool(C, keys="spending expenses how much spent month week summary budget", ex={"period": "month"})
def expenses(period: str = "month", ctx=None) -> str:
    """What you spent: today, week, month (default), last month, or YYYY-MM — by category, with your budget."""
    now = _now(ctx)
    a, b, label = _period(period, now)
    d = _store(ctx).read()
    rows = [e for e in d["expenses"] if a <= pa.parse_iso(e["at"]) < b]
    if not rows:
        return f"No spending logged {label}."
    total = sum(e["amount"] for e in rows)
    by = Counter()
    for e in rows:
        by[e["category"]] += e["amount"]
    parts = ", ".join(f"{c} ₹{fmt(v)}" for c, v in by.most_common(6))
    msg = f"Spent ₹{fmt(total)} {label} ({many(len(rows), 'entry')}): {parts}."
    if label == "this month" and d["budgets"].get("total"):
        bud = d["budgets"]["total"]
        days_in = (b - a).days
        msg += f" Budget ₹{fmt(bud)}: {round(100 * total / bud)}% used, {round(100 * now.day / days_in)}% of the month gone."
    return msg


@tool(C, keys="budget monthly limit set spending cap", ex={"monthly_amount": 30000, "category": "total"})
def budget_set(monthly_amount: float, category: str = "total", ctx=None) -> str:
    """Set a monthly budget, overall ("total") or for a category (food, transport, shopping…)."""
    cat = category.strip().lower() or "total"
    with _store(ctx).edit() as d:
        if monthly_amount <= 0:
            d["budgets"].pop(cat, None)
            return f"Removed the {cat} budget."
        d["budgets"][cat] = float(monthly_amount)
    return f"Monthly {cat} budget: ₹{fmt(float(monthly_amount))}. I'll warn you when you go over."


# ------------------------------------------------------------------------------------------------ journal & mood
_MOODS = {5: "great amazing fantastic wonderful excellent awesome happy", 4: "good fine nice calm productive",
          2: "tired stressed anxious meh low worried annoyed", 1: "sad terrible awful angry upset exhausted depressed"}
_MOOD = {w: s for s, ws in _MOODS.items() for w in ws.split()}


@tool(C, keys="journal diary log day reflect mood feeling", ex={"text": "Good day — finished the launch, a bit tired", "mood": 4})
def journal_add(text: str, mood: int = 0, ctx=None) -> str:
    """Write a journal entry. Mood 1–5 (guessed from your words if you don't say)."""
    if not mood:
        found = [_MOOD[w] for w in re.findall(r"[a-z]+", text.lower()) if w in _MOOD]
        mood = round(sum(found) / len(found)) if found else 0
    with _store(ctx).edit() as d:
        d["journal"].append({"at": pa.iso(_now(ctx)), "text": _clean(text, 2000), "mood": max(0, min(5, mood))})
    return "Saved to your journal." + (f" Mood {mood}/5." if mood else "")


@tool(C, keys="journal read entries mood trend how have i been feeling", ex={"days": 7})
def journal_read(days: int = 7, query: str = "", ctx=None) -> str:
    """Recent journal entries (or ones mentioning `query`) and your average mood."""
    now = _now(ctx)
    since = now - timedelta(days=days)
    rows = [j for j in _store(ctx).read()["journal"] if pa.parse_iso(j["at"]) >= since or query]
    if query:
        rows = [j for j in rows if query.lower() in j["text"].lower()]
    if not rows:
        return "No journal entries there." if query else f"No journal entries in the last {days} days."
    moods = [j["mood"] for j in rows if j.get("mood")]
    head = f"{len(rows)} entr{'ies' if len(rows) != 1 else 'y'}" + (f", average mood {sum(moods) / len(moods):.1f}/5" if moods else "")
    return head + ":\n" + "\n".join(f"{pa.parse_iso(j['at']).strftime('%a %d %b')}: {j['text'][:160]}" for j in rows[-8:])


# ------------------------------------------------------------------------------------------------ focus
@tool(C, keys="focus pomodoro deep work timer session concentrate", ex={"minutes": 25, "task": "write report"})
def focus_start(minutes: int = 25, task: str = "", ctx=None) -> str:
    """Start a focus session (Pomodoro): a timer, and the session is logged for your weekly review."""
    minutes = max(5, min(180, minutes))
    label = _clean(task, 80) or "focus"
    msg = ""
    starter = getattr(ctx, "start_timer", None)
    if starter:
        ok, m = starter(minutes * 60, "Focus: " + label)
        msg = "" if ok else f" (timer: {m})"
    with _store(ctx).edit() as d:
        d["focus"].append({"at": pa.iso(_now(ctx)), "minutes": minutes, "task": label})
    return f"Focus on {label} for {minutes} minutes. I'll stay quiet{'; the timer is set' if starter and not msg else ''}.{msg}"


@tool(C, keys="focus stats deep work minutes how much did i focus pomodoros")
def focus_stats(days: int = 7, ctx=None) -> str:
    """Focus minutes in the last N days, by day and by task."""
    now = _now(ctx)
    rows = [f for f in _store(ctx).read()["focus"] if pa.parse_iso(f["at"]) >= now - timedelta(days=days)]
    if not rows:
        return f"No focus sessions in the last {many(days, 'day')}. Say “start a focus session”."
    total = sum(f["minutes"] for f in rows)
    by = Counter()
    for f in rows:
        by[f["task"]] += f["minutes"]
    return f"{fmt(total / 60)} hours of focus in {many(len(rows), 'session')} over {many(days, 'day')}. Most on: " + \
        ", ".join(f"{t} ({m} min)" for t, m in by.most_common(4)) + "."


# ------------------------------------------------------------------------------------------------ meetings
_ACTION = re.compile(r"(?i)^\s*(?:[-*•]\s*)?(?:\[ \]\s*|todo:?\s*|action(?: item)?:?\s*|ai:\s*|next step:?\s*|follow[- ]up:?\s*)(.+)$")
_WILL = re.compile(r"(?i)^\s*(?:[-*•]\s*)?([A-Z][a-z]+|I|We)\s+(?:will|to|should|needs? to|is going to)\s+(.{6,})$")


def action_items(notes: str) -> list:
    out = []
    for line in notes.splitlines():
        m = _ACTION.match(line)
        if m and not line.strip().lower().startswith(("- [x]",)):
            out.append(m.group(1).strip(" .")); continue
        m = _WILL.match(line)
        if m:
            who = m.group(1)
            out.append((m.group(2) if who in ("I", "We") else f"{who}: {m.group(2)}").strip(" ."))
    return [a for a in dict.fromkeys(out) if a][:30]


@tool(C, keys="meeting notes minutes save action items decisions transcript", ex={"title": "Weekly sync", "notes": "- Ravi will send the deck by friday\nTODO: book venue"})
def meeting_save(title: str, notes: str, action_items_list: list[str] = None, make_tasks: bool = True, ctx=None) -> str:
    """Save meeting notes; action items (from the list, or found in the notes: "TODO", "- [ ]", "Ravi will …") become
    tasks tagged #meeting with any due date they mention."""
    items = [_clean(a, 200) for a in (action_items_list or action_items(notes)) if str(a).strip()]
    skipped = max(0, len(items) - 50)
    items = items[:50]
    now = _now(ctx)
    made = [_make_task(a + " #meeting", now)[0] for a in items] if make_tasks else []
    with _store(ctx).edit() as d:                  # the meeting and all its tasks in one save
        d["meetings"].append({"id": pa.new_id(), "title": _clean(title, 120), "notes": _clean(notes, 20000), "actions": items, "at": pa.iso(now)})
        d["tasks"].extend(made)
    out = f"Saved “{title}”." + (f" {len(made)} action item{'s' if len(made) != 1 else ''} added as tasks: " +
                                  "; ".join(t["title"] for t in made[:8]) + "." if made else " No action items found." if make_tasks else "")
    return out + (f" (Kept the first 50 action items; {skipped} more weren't added.)" if skipped else "")


@tool(C, keys="meetings past notes search find what did we decide", ex={"query": "venue"})
def meetings(query: str = "", ctx=None) -> str:
    """Recent meetings, or the ones whose title/notes mention `query`."""
    rows = _store(ctx).read()["meetings"]
    if query:
        q = query.lower()
        rows = [m for m in rows if q in m["title"].lower() or q in m["notes"].lower()]
    if not rows:
        return "No meetings found."
    return "\n".join(f"{pa.parse_iso(m['at']).strftime('%a %d %b')}: {m['title']} — " +
                     ("; ".join(m["actions"][:4]) or m["notes"][:120]) for m in rows[-8:][::-1])


# ------------------------------------------------------------------------------------------------ brief & review
@tool(C, keys="my day brief briefing morning today overview pulse agenda summary")
def my_day(ctx=None) -> str:
    """Your personal brief for today: what's overdue and due, follow-ups, birthdays, habits left, money, and the one
    thing to start with."""
    now = _now(ctx)
    d = _store(ctx).read()
    end = now.replace(hour=23, minute=59)
    hour = now.hour
    parts = [("Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening") + "."]
    open_ = [t for t in d["tasks"] if not t.get("done")]
    over = sorted([t for t in open_ if _due(t) and _due(t) < now.replace(hour=0, minute=0)], key=lambda t: _rank(t, now))
    today = sorted([t for t in open_ if _due(t) and now.replace(hour=0, minute=0) <= _due(t) <= end], key=lambda t: _rank(t, now))
    if over:
        parts.append(f"{len(over)} overdue: " + ", ".join(t["title"] for t in over[:3]) + ".")
    if today:
        parts.append(f"{len(today)} due today: " + ", ".join(_task_line(t, now) for t in today[:4]) + ".")
    if not over and not today:
        parts.append("Nothing due today." + (f" {len(open_)} open task{'s' if len(open_) != 1 else ''} in total." if open_ else ""))
    fu = [f for f in d["followups"] if not f.get("done") and pa.parse_iso(f["due"]) <= end]
    if fu:
        parts.append("Follow up: " + ", ".join(f["title"] for f in fu[:3]) + ".")
    bd = _upcoming_birthdays(d, now.date(), 7)
    if bd:
        parts.append("Birthdays: " + ", ".join(f"{n} {'today' if g == 0 else 'tomorrow' if g == 1 else 'on ' + dd.strftime('%A')}" for g, n, dd in bd) + ".")
    left = [h["name"] for h in d["habits"].values() if now.date().isoformat() not in h["days"]]
    if left:
        parts.append("Habits left today: " + ", ".join(left[:4]) + ".")
    month = now.strftime("%Y-%m")
    spent = sum(e["amount"] for e in d["expenses"] if e["at"].startswith(month))
    if spent:
        bud = d["budgets"].get("total")
        parts.append(f"Spent ₹{fmt(spent)} this month" + (f" ({round(100 * spent / bud)}% of budget)." if bud else "."))
    if open_:
        parts.append(what_next(ctx=ctx))
    return " ".join(parts)


@tool(C, keys="weekly review week summary reflection how did my week go")
def weekly_review(ctx=None) -> str:
    """The last 7 days: tasks finished, still overdue, habits, focus time, spending, mood — and people to catch up with."""
    now = _now(ctx)
    since = now - timedelta(days=7)
    d = _store(ctx).read()
    done = [t for t in d["tasks"] if t.get("done") and pa.parse_iso(t["done"]) >= since]
    over = [t for t in d["tasks"] if not t.get("done") and _due(t) and _due(t) < now]
    parts = [f"This week you finished {len(done)} task{'s' if len(done) != 1 else ''}" + (": " + ", ".join(t["title"] for t in done[:5]) if done else "") + "."]
    if over:
        parts.append(f"{len(over)} still overdue (oldest: {sorted(over, key=lambda t: t['due'])[0]['title']}).")
    week_days = {(now.date() - timedelta(days=i)).isoformat() for i in range(7)}
    for h in d["habits"].values():
        n = len(week_days & set(h["days"]))
        parts.append(f"{h['name']}: {n}/{h['per_week']}.")
    fm = sum(f["minutes"] for f in d["focus"] if pa.parse_iso(f["at"]) >= since)
    if fm:
        parts.append(f"Focus: {fmt(fm / 60)} hours.")
    sp = [e for e in d["expenses"] if pa.parse_iso(e["at"]) >= since]
    if sp:
        by = Counter()
        for e in sp:
            by[e["category"]] += e["amount"]
        parts.append(f"Spent ₹{fmt(sum(by.values()))}, most on {by.most_common(1)[0][0]}.")
    moods = [j["mood"] for j in d["journal"] if j.get("mood") and pa.parse_iso(j["at"]) >= since]
    if moods:
        parts.append(f"Average mood {sum(moods) / len(moods):.1f}/5.")
    stale = people_to_reconnect(30, ctx=ctx)
    if stale.startswith("Maybe"):
        parts.append(stale)
    return " ".join(parts)


# ------------------------------------------------------------------------------------------------ phrases you teach
@tool(C, keys="teach learn custom phrase shortcut alias when i say macro routine", ex={"text": "work mode = open visual studio code, open teams, do not disturb on"})
def teach_phrase(text: str, ctx=None) -> str:
    """Teach Echo your own phrase: "work mode = open VS Code, open Teams, do not disturb on". Each step is a normal
    Echo command; saying the phrase runs them in order (only safe kinds of commands)."""
    m = re.match(r"(?i)^\s*(?:when i say\s+)?[\"“]?(.+?)[\"”]?\s*(?:=|:|->|means|do|then do)\s+(.+)$", text)
    if not m:
        raise ToolError("say it like “work mode = open VS Code, open Teams”")
    from ..core import normalize
    phrase = normalize(m.group(1))
    steps = [s.strip(" .") for s in re.split(r"\s*(?:,|;|\bthen\b|\band then\b|\band\b)\s*", m.group(2)) if s.strip(" .")]
    if not phrase or not steps:
        raise ToolError("I need a phrase and at least one step")
    if len(steps) > 10:
        raise ToolError("ten steps at most")
    with _store(ctx).edit() as d:
        d["phrases"][phrase] = [_clean(s, 120) for s in steps]
    return f"Learned “{phrase}”: " + " → ".join(steps) + "."


@tool(C, keys="taught phrases shortcuts learned list custom")
def phrases_taught(ctx=None) -> str:
    """The phrases you've taught Echo."""
    p = _store(ctx).read()["phrases"]
    return "\n".join(f"“{k}”: " + " → ".join(v) for k, v in p.items()) if p else "You haven't taught me any phrases yet."


@tool(C, ask=True, keys="forget unlearn remove taught phrase shortcut", ex={"phrase": "work mode"})
def phrase_forget(phrase: str, ctx=None) -> str:
    """Forget a phrase you taught (asks first)."""
    from ..core import normalize
    key = normalize(phrase)
    st = _store(ctx)
    if key not in st.read()["phrases"]:
        raise ToolError(f"I don't know the phrase “{phrase}”")
    if ctx is not None and not ctx.confirm("Forget this phrase?", key):
        return "Kept it."
    with st.edit() as d:
        d["phrases"].pop(key, None)
    return f"Forgot “{key}”."
