"""Hindu festivals, ekadashis, purnimas and sankrantis for 2026–2027 from Drik Panchang (shared/festivals.json): exact
dates and weekdays instead of the AI's guesses ("Diwali 31 October" was a real wrong answer)."""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

from . import ToolError, tool

C = "time"
DATA = Path(__file__).resolve().parents[4] / "shared" / "festivals.json"


@lru_cache(maxsize=1)
def _data() -> dict:
    try:
        return json.loads(DATA.read_text("utf-8"))
    except (OSError, ValueError):
        return {"festivals": [], "aliases": {}, "years": []}


def _today(ctx) -> date:
    f = getattr(ctx, "now", None)
    return (f() if callable(f) else datetime.now()).date()


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())).strip()


def _say(f: dict, today: date) -> str:
    d = date.fromisoformat(f["date"])
    days = (d - today).days
    when = "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days" if 0 < days <= 60 else (
        "yesterday" if days == -1 else f"{-days} days ago" if days < 0 else "")
    return f"{f['name']}: {d:%A} {d.day} {d:%B %Y}" + (f" ({when})" if when else "") + (f" — {f['detail']}" if f.get("detail") else "")


def _matches(name: str) -> list:
    d = _data()
    q = _norm(name)
    q = _norm(d["aliases"].get(q, q))
    for word, real in d["aliases"].items():           # an alias inside a longer phrase ("deepavali ee year")
        if re.search(rf"\b{re.escape(word)}\b", q):
            q = _norm(real)
            break
    words = set(q.split()) - {"festival", "day", "date", "this", "year", "next", "the", "when", "is"}
    if not words:
        return []
    exact = [f for f in d["festivals"] if _norm(f["name"]) == q]
    if exact:
        return exact
    return [f for f in d["festivals"] if words <= set(_norm(f["name"]).split())]


def _source() -> str:
    return "(Drik Panchang, New Delhi; regional calendars can differ by a day.)"


@tool(C, keys="festival hindu date when diwali deepavali ekadashi ekadasi purnima pournami sankranti ugadi holi dussehra "
             "dasara ganesh vinayaka chavithi navratri shivaratri rakhi janmashtami panchang tithi amavasya",
      ex={"name": "Diwali"})
def festival_date(name: str, year: int = 0, ctx=None) -> str:
    """When a Hindu festival is (Diwali, Ugadi, Karthika Pournami, Sankranti, a named Ekadashi…): the next one from
    today, or the one in `year`. Dates and weekdays from Drik Panchang for 2026–2027."""
    today = _today(ctx)
    found = _matches(name)
    if year:
        found = [f for f in found if f["date"].startswith(str(year))]
    if not found:
        raise ToolError(f"I don't have “{name}” in my festival calendar (2026–2027). Try another name, or ask me to look it up.")
    upcoming = [f for f in found if f["date"] >= today.isoformat()]
    pick = (upcoming or found)[0] if not year else found[0]
    passed = [f for f in found if f["date"][:4] == str(today.year) and 0 < (today - date.fromisoformat(f["date"])).days <= 45]
    if not year and passed and pick is not passed[-1]:
        # "Diwali this year" asked the day after: say it has passed, and when the next one is
        return f"This year's was {_say(passed[-1], today)}. Next: {_say(pick, today)}. {_source()}"
    extra = ""
    if _norm(pick["name"]) == "makara sankranti":
        d = date.fromordinal(date.fromisoformat(pick["date"]).toordinal())
        extra = (f" In Andhra Pradesh and Telangana: Bhogi is the day before ({date.fromordinal(d.toordinal() - 1):%A %d %B}), "
                 f"Kanuma the day after ({date.fromordinal(d.toordinal() + 1):%A %d %B}).")
    return _say(pick, today) + "." + extra + " " + _source()


@tool(C, keys="festival today tomorrow any festival ekadashi today is today amavasya purnima vrat", ex={"day": "today"})
def festivals_on(day: str = "today", ctx=None) -> str:
    """Festivals, ekadashis, purnimas and sankrantis on a day ("today", "tomorrow" or YYYY-MM-DD)."""
    today = _today(ctx)
    d = today if day.strip().lower() in ("", "today") else date.fromordinal(today.toordinal() + 1) \
        if day.strip().lower() == "tomorrow" else date.fromisoformat(day.strip())
    hits = [f for f in _data()["festivals"] if f["date"] == d.isoformat()]
    if not hits:
        nxt = [f for f in _data()["festivals"] if f["date"] > d.isoformat()][:1]
        return (f"No festival in my calendar on {d:%A} {d.day} {d:%B %Y}."
                + (f" Next: {_say(nxt[0], today)}." if nxt else "") + " " + _source())
    return "; ".join(_say(f, today) for f in hits) + ". " + _source()


@tool(C, keys="tithi panchang today date thithi paksha lunar month hindu calendar amavasya pournami pratipada",
      ex={"day": "today"})
def tithi(day: str = "today", ctx=None) -> str:
    """Today's (or a date's) date, tithi, paksha and lunar month, computed from the Sun and Moon at sunrise (New
    Delhi), with when the tithi ends and any festival that day."""
    from .. import panchang
    from .t_time import parse_date
    today = _today(ctx)
    key = (day or "today").strip().lower()
    d = today if key in ("", "today", "now") else today + timedelta(days=1) if key == "tomorrow" else \
        today - timedelta(days=1) if key == "yesterday" else parse_date(day)
    p = panchang.day_panchang(d)
    month = p["month"] if p["month"] == p["month_north"] else \
        f"{p['month']} (South Indian amanta, used in AP/Telangana; {p['month_north']} in the North Indian calendar)"
    ends = p["ends"]
    till = f"{ends:%I:%M %p}".lstrip("0") + ("" if ends.date() == d else f" on {ends:%a %d %b}")
    fest = [f["name"] for f in _data()["festivals"] if f["date"] == d.isoformat()]
    return (f"{d:%A} {d.day} {d:%B %Y}: {p['name']} till {till}, then {p['next']}. Month: {month}."
            + (f" Festival: {', '.join(fest)}." if fest else "")
            + " (Tithi at sunrise, New Delhi; your town can differ by a few minutes.)")


@tool(C, keys="next ekadashi purnima pournami amavasya sankranti festival upcoming festivals list month",
      ex={"kind": "Ekadashi"})
def next_festivals(kind: str = "", count: int = 3, ctx=None) -> str:
    """The next festivals from today, or the next of one kind ("Ekadashi", "Purnima", "Sankranti", "Amavasya")."""
    today = _today(ctx).isoformat()
    d = _data()
    q = _norm(d["aliases"].get(_norm(kind), kind))
    items = [f for f in d["festivals"] if f["date"] >= today and (not q or q in _norm(f["name"]))]
    if not items:
        raise ToolError("Nothing more of that kind in my festival calendar (it covers 2026–2027).")
    return "; ".join(_say(f, _today(ctx)) for f in items[:max(1, min(count, 10))]) + ". " + _source()
