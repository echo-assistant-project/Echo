"""Dates, times, time zones and calendars (time zones come from Windows' own ICU data, offline)."""
from __future__ import annotations

import calendar
import re
from datetime import date, datetime, time, timedelta, timezone

from . import ToolError, fmt, tool
from ..words import many

C = "time"
_data = None


def data():
    global _data
    if _data is None:
        from .. import tools
        _data = tools.load_data()
    return _data


def zone_of(place: str) -> tuple:
    """(label, IANA zone) for a city/country name or an IANA zone like Asia/Kolkata."""
    from .. import tools
    p = " ".join(place.split())
    if len(p) > 100:
        raise ToolError("that place name is too long; say a city, country or zone like Asia/Kolkata")
    if re.fullmatch(r"[A-Za-z_]+/[A-Za-z_/+-]+|UTC|GMT", p):
        return p, "UTC" if p == "GMT" else p
    hit = tools._city(p, data())
    if hit:
        zone, name = hit                                   # tools._city gives (zone, name)
        return name, zone
    try:                                                   # unknown to the offline table: ask the geocoder
        from .. import internet
        d = internet.get_json("https://geocoding-api.open-meteo.com/v1/search?count=1&format=json&name=" + internet.q(p), 86400)
        r = (d.get("results") or [None])[0]
        if r and r.get("timezone"):
            return f"{r['name']}, {r.get('country', '')}".strip(", "), r["timezone"]
    except Exception:
        pass
    raise ToolError(f"I don't know the time zone of {place}")


def local_now(zone: str, now: datetime = None) -> datetime:
    from .. import tools
    now = now or datetime.now(timezone.utc)
    return (now.astimezone(timezone.utc) + timedelta(minutes=tools.windows_offset_minutes(zone, now))).replace(tzinfo=None)


def parse_date(text: str) -> date:
    t = text.strip().lower()
    today = date.today()
    if t in ("today", "now"):
        return today
    if t == "tomorrow":
        return today + timedelta(days=1)
    if t == "yesterday":
        return today - timedelta(days=1)
    for f in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y", "%B %d, %Y", "%d %B", "%B %d"):
        try:
            d = datetime.strptime(text.strip().replace(",", "") if "%B %d, %Y" != f else text.strip(), f).date()
            return d.replace(year=today.year) if "%Y" not in f else d
        except ValueError:
            continue
    raise ToolError(f"I can't read the date {text!r}; use 2026-12-25 or 25 December 2026")


def parse_time(text: str) -> time:
    m = re.fullmatch(r"\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?\s*", text.lower())
    if not m:
        raise ToolError(f"I can't read the time {text!r}; use 9:30 pm or 21:30")
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").replace(".", "")
    if ap == "pm" and h < 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    if not (0 <= h < 24 and 0 <= mi < 60):
        raise ToolError("that time doesn't exist")
    return time(h, mi)


def nice(dt: datetime) -> str:
    return dt.strftime("%A %d %B %Y, %I:%M %p").replace(" 0", " ")


@tool(C, ex={"place": "Tokyo"}, keys="current time clock city world timezone")
def time_in(place: str) -> str:
    """Current local time in a city, country or time zone."""
    label, zone = zone_of(place)
    return f"{nice(local_now(zone))} in {label} ({zone})."


@tool(C, ex={"time_text": "9:30 pm", "from_place": "New York", "to_place": "Hyderabad"}, keys="convert timezone meeting call")
def convert_time_zone(time_text: str, from_place: str, to_place: str, on_date: str = "today") -> str:
    """Convert a clock time from one city/zone to another."""
    from .. import tools
    (fl, fz), (tl, tz) = zone_of(from_place), zone_of(to_place)
    d, t = parse_date(on_date), parse_time(time_text)
    naive = datetime.combine(d, t)
    guess = naive.replace(tzinfo=timezone.utc)
    off = tools.windows_offset_minutes(fz, guess)
    instant = (naive - timedelta(minutes=off)).replace(tzinfo=timezone.utc)
    out = local_now(tz, instant)
    return f"{t.strftime('%I:%M %p').lstrip('0')} in {fl} = {out.strftime('%I:%M %p').lstrip('0')} {out:%A} in {tl}."


@tool(C, ex={"place_a": "London", "place_b": "Mumbai"}, keys="time difference offset hours ahead behind")
def time_difference(place_a: str, place_b: str) -> str:
    """How many hours one place is ahead of another right now."""
    from .. import tools
    now = datetime.now(timezone.utc)
    (la, za), (lb, zb) = zone_of(place_a), zone_of(place_b)
    diff = tools.windows_offset_minutes(zb, now) - tools.windows_offset_minutes(za, now)
    h, m = divmod(abs(diff), 60)
    span = f"{h} hours" + (f" {m} minutes" if m else "")
    return f"{lb} is {span} {'ahead of' if diff > 0 else 'behind'} {la}." if diff else f"{la} and {lb} have the same time."


@tool(C, ex={"places": ["Hyderabad", "London", "New York"], "start_hour": 9, "end_hour": 18}, keys="meeting planner overlap working hours")
def meeting_overlap(places: list[str], start_hour: int = 9, end_hour: int = 18) -> str:
    """Hours (in the first place's time) when everyone is within working hours today."""
    from .. import tools
    zones = [zone_of(p) for p in places]
    if len(zones) < 2:
        raise ToolError("give at least two places")
    now = datetime.now(timezone.utc)
    offs = [tools.windows_offset_minutes(z, now) for _, z in zones]
    good = []
    for h in range(24):
        ok = all(start_hour <= ((h * 60 + o - offs[0]) // 60) % 24 < end_hour for o in offs)
        if ok:
            good.append(h)
    if not good:
        return "There's no hour when everyone is in working hours. Try widening the hours."
    return f"In {zones[0][0]} time, everyone is free-ish at: " + ", ".join(f"{h:02d}:00" for h in good) + "."


@tool(C, ex={"start": "2026-11-01", "days": 45}, keys="add days date after before plus minus weeks months")
def add_to_date(start: str = "today", days: int = 0, weeks: int = 0, months: int = 0, years: int = 0) -> str:
    """A date plus or minus days, weeks, months or years."""
    d = parse_date(start)
    m = d.month - 1 + months + years * 12
    y, m = d.year + m // 12, m % 12 + 1
    d = date(y, m, min(d.day, calendar.monthrange(y, m)[1])) + timedelta(days=days, weeks=weeks)
    return d.strftime("%A %d %B %Y")


@tool(C, ex={"start": "2026-01-26", "end": "2026-08-15"}, keys="days between difference how many days until since")
def date_difference(start: str, end: str = "today") -> str:
    """Days (and weeks, months) between two dates."""
    a, b = parse_date(start), parse_date(end)
    days = (b - a).days
    y = b.year - a.year - ((b.month, b.day) < (a.month, a.day))
    months = (b.year - a.year) * 12 + b.month - a.month - (b.day < a.day)
    return f"{abs(days):,} days ({abs(days) // 7} weeks {abs(days) % 7} days; about {abs(months)} months, {abs(y)} full years)" + (" ago" if days < 0 else "") + "."


@tool(C, ex={"start": "2026-11-02", "end": "2026-11-30"}, keys="working days business days weekdays excluding weekends")
def business_days(start: str, end: str, holidays: list[str] = None) -> str:
    """Working days (Mon–Fri) between two dates, inclusive, minus any holidays you list."""
    a, b = sorted((parse_date(start), parse_date(end)))
    skip = {parse_date(h) for h in (holidays or [])}
    n = sum(1 for i in range((b - a).days + 1) if (d := a + timedelta(days=i)).weekday() < 5 and d not in skip)
    off = f", minus {many(len(skip), 'holiday')} you listed" if skip else " (no public holidays removed)"
    return f"{n} working days, {a:%a %d %b %Y} to {b:%a %d %b %Y} inclusive, Monday to Friday{off}."


@tool(C, ex={"day": "15 August 1947"}, keys="what day of the week was")
def weekday_of(day: str) -> str:
    """Which day of the week a date falls on."""
    return parse_date(day).strftime("%A")


@tool(C, ex={"birth_date": "1990-05-17"}, keys="how old age birthday")
def age(birth_date: str, on_date: str = "today") -> str:
    """Exact age from a birth date, and days to the next birthday."""
    b, t = parse_date(birth_date), parse_date(on_date)
    y = t.year - b.year - ((t.month, t.day) < (b.month, b.day))
    last = b.replace(year=b.year + y) if not (b.month == 2 and b.day == 29) else date(b.year + y, 3, 1)
    months = (t.year - last.year) * 12 + t.month - last.month - (t.day < last.day)
    nxt = date(t.year + ((t.month, t.day) >= (b.month, b.day)), b.month, b.day if not (b.month == 2 and b.day == 29) else 28)
    return f"{many(y, 'year')} {many(months, 'month')} old ({many((t - b).days, 'day')}). Next birthday in {many((nxt - t).days, 'day')} ({nxt:%A})."


@tool(C, ex={"event": "2027-01-01"}, keys="countdown days left until")
def countdown(event: str) -> str:
    """Time left until a date (or date and time, '2026-12-31 23:59')."""
    parts = event.strip().rsplit(" ", 1)
    try:
        when = datetime.combine(parse_date(parts[0]), parse_time(parts[1])) if len(parts) == 2 and ":" in parts[1] else datetime.combine(parse_date(event), time())
    except ToolError:
        when = datetime.combine(parse_date(event), time())
    diff = when - datetime.now()
    if diff.total_seconds() < 0:
        return f"That was {many(-diff.days, 'day')} ago."
    h, rem = divmod(diff.seconds, 3600)
    return f"{many(diff.days, 'day')}, {many(h, 'hour')} and {many(rem // 60, 'minute')} to go."


@tool(C, ex={"day": "today"}, keys="iso week number")
def week_number(day: str = "today") -> str:
    """ISO week number and day of the year for a date."""
    d = parse_date(day)
    y, w, _ = d.isocalendar()
    return f"Week {w} of {y}; day {d.timetuple().tm_yday} of {366 if calendar.isleap(d.year) else 365}."


@tool(C, ex={"year": 2028}, keys="leap year february 29")
def leap_year(year: int) -> str:
    """Is a year a leap year?"""
    return f"{year} is {'a' if calendar.isleap(year) else 'not a'} leap year."


@tool(C, ex={"year": 2026, "month": 11}, keys="calendar month view")
def month_calendar(year: int = 0, month: int = 0) -> str:
    """A month's calendar as text (defaults to this month)."""
    t = date.today()
    return calendar.month(year or t.year, month or t.month)


@tool(C, ex={"weekday": "friday"}, keys="next coming monday tuesday wednesday thursday friday saturday sunday")
def next_weekday(weekday: str, after: str = "today") -> str:
    """Date of the next given weekday."""
    names = [d.lower() for d in calendar.day_name]
    w = weekday.strip().lower()
    match = next((i for i, n in enumerate(names) if n.startswith(w[:3])), None)
    if match is None:
        raise ToolError("say a weekday like Friday")
    d = parse_date(after)
    ahead = (match - d.weekday() - 1) % 7 + 1
    return (d + timedelta(days=ahead)).strftime("%A %d %B %Y")


@tool(C, ex={"year": 2026, "month": 11, "weekday": "thursday", "nth": 4}, keys="nth weekday month like fourth thursday last friday")
def nth_weekday_of_month(year: int, month: int, weekday: str, nth: int = 1) -> str:
    """The n-th (or last, nth=-1) given weekday of a month."""
    names = [d.lower() for d in calendar.day_name]
    wd = next((i for i, n in enumerate(names) if n.startswith(weekday.strip().lower()[:3])), None)
    if wd is None:
        raise ToolError("say a weekday like Thursday")
    days = [d for d in calendar.Calendar().itermonthdates(year, month) if d.month == month and d.weekday() == wd]
    try:
        return days[nth - 1 if nth > 0 else nth].strftime("%A %d %B %Y")
    except IndexError:
        raise ToolError("that month doesn't have that many")


@tool(C, ex={"timestamp": 1790000000}, keys="unix epoch timestamp convert")
def unix_to_date(timestamp: float, place: str = "") -> str:
    """Unix timestamp (seconds or milliseconds) to a readable date, in UTC and your time or a city's."""
    from ..devtools import epoch_utc
    ts = timestamp / 1000 if abs(timestamp) > 1e11 else timestamp
    utc = epoch_utc(ts)
    if utc is None:
        raise ToolError("that's too far from 1970 to be a date")
    if place:
        local = local_now(zone_of(place)[1], utc)
    else:                                   # your current offset (Windows can't convert dates before 1970 itself)
        local = (utc + (datetime.now().astimezone().utcoffset() or timedelta(0))).replace(tzinfo=None)
    return f"{utc:%Y-%m-%d %H:%M:%S} UTC = {nice(local)} {'in ' + place if place else 'your time'}."


@tool(C, ex={"day": "2026-12-25", "time_text": "10:00"}, keys="unix epoch timestamp")
def date_to_unix(day: str, time_text: str = "00:00") -> str:
    """A local date and time to a Unix timestamp."""
    dt = datetime.combine(parse_date(day), parse_time(time_text)).astimezone()
    return str(int(dt.timestamp()))


@tool(C, ex={"wake_time": "6:30 am"}, keys="sleep bedtime cycles when should i sleep")
def bedtime_for(wake_time: str) -> str:
    """Good bedtimes for waking at a time (90-minute sleep cycles, 15 minutes to fall asleep)."""
    w = datetime.combine(date.today(), parse_time(wake_time))
    times = [(w - timedelta(minutes=90 * c + 15)).strftime("%I:%M %p").lstrip("0") for c in (6, 5, 4)]
    return "Try going to bed at " + ", ".join(times) + " (6, 5 or 4 sleep cycles)."


@tool(C, ex={"bed_time": "11 pm"}, keys="wake up time sleep cycles alarm")
def wake_times_for(bed_time: str) -> str:
    """Good wake-up times if you go to bed at a time (90-minute cycles)."""
    b = datetime.combine(date.today(), parse_time(bed_time)) + timedelta(minutes=15)
    return "Wake at " + ", ".join((b + timedelta(minutes=90 * c)).strftime("%I:%M %p").lstrip("0") for c in (4, 5, 6)) + "."


@tool(C, ex={"day": "today"}, keys="moon phase lunar full moon new moon")
def moon_phase(day: str = "today") -> str:
    """Moon phase on a date."""
    d = parse_date(day)
    known = date(2000, 1, 6)
    age_ = ((d - known).days % 29.530588853)
    names = [(1.85, "new moon"), (5.54, "waxing crescent"), (9.23, "first quarter"), (12.92, "waxing gibbous"), (16.61, "full moon"),
             (20.30, "waning gibbous"), (23.99, "last quarter"), (27.68, "waning crescent"), (29.6, "new moon")]
    return f"{next(n for lim, n in names if age_ < lim).capitalize()} ({fmt(round(age_, 1))} days into the cycle)."


@tool(C, ex={"birth_date": "1992-08-21"}, keys="zodiac star sign horoscope")
def zodiac_sign(birth_date: str) -> str:
    """Western zodiac sign and Chinese zodiac animal for a birth date."""
    d = parse_date(birth_date)
    signs = [(1, 20, "Capricorn"), (2, 19, "Aquarius"), (3, 21, "Pisces"), (4, 20, "Aries"), (5, 21, "Taurus"), (6, 21, "Gemini"),
             (7, 23, "Cancer"), (8, 23, "Leo"), (9, 23, "Virgo"), (10, 23, "Libra"), (11, 22, "Scorpio"), (12, 22, "Sagittarius"), (12, 32, "Capricorn")]
    sign = next(s for m, dd, s in signs if (d.month, d.day) < (m, dd))
    animals = "Rat Ox Tiger Rabbit Dragon Snake Horse Goat Monkey Rooster Dog Pig".split()
    return f"{sign}; Chinese zodiac: {animals[(d.year - 2020) % 12]} (by calendar year)."


@tool(C, ex={"name": "christmas"}, keys="festival holiday date when is")
def holiday_date(name: str, year: int = 0) -> str:
    """Next date of a fixed or rule-based holiday (Christmas, Easter, Republic Day, Mother's Day, Thanksgiving…).
    Lunar festivals like Diwali or Eid change yearly: look those up with web tools."""
    from .. import tools
    ctx = tools.context(data())
    r = tools.run("holiday", {"h": name, "y": str(year or date.today().year)}, ctx) or tools.run("holiday", {"h": name}, ctx)
    if r is None:
        raise ToolError(f"I don't have the date of {name}")
    return r.text


@tool(C, ex={"seconds": 98765}, keys="seconds to hours minutes duration format")
def format_duration(seconds: float) -> str:
    """Turn seconds into days, hours, minutes and seconds."""
    s = int(abs(seconds))
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    parts = [f"{v} {u}{'s' if v != 1 else ''}" for v, u in ((d, "day"), (h, "hour"), (m, "minute"), (s, "second")) if v]
    return ", ".join(parts) or "0 seconds"


@tool(C, ex={"start": "9:15 am", "end": "5:40 pm", "break_minutes": 45}, keys="hours worked shift timesheet duration between times")
def hours_between(start: str, end: str, break_minutes: int = 0) -> str:
    """Hours and minutes between two clock times (overnight works), minus a break."""
    a, b = parse_time(start), parse_time(end)
    mins = (b.hour * 60 + b.minute - a.hour * 60 - a.minute) % 1440 - break_minutes
    return f"{many(mins // 60, 'hour')} {many(mins % 60, 'minute')} ({fmt(round(mins / 60, 2))} hours)."


@tool(C, ex={"time_text": "18:45"}, keys="24 hour 12 hour clock convert am pm military")
def clock_12_24(time_text: str) -> str:
    """Convert a time between 12-hour and 24-hour clocks."""
    t = parse_time(time_text)
    return f"{t:%H:%M} = {t.strftime('%I:%M %p').lstrip('0')}"


@tool(C, ex={"day": "today"}, keys="quarters financial year fy")
def financial_year(day: str = "today") -> str:
    """Indian financial year (April–March) and quarter for a date, plus the calendar quarter."""
    d = parse_date(day)
    start = d.year if d.month >= 4 else d.year - 1
    fq = (d.month - 4) % 12 // 3 + 1
    return f"FY {start}-{str(start + 1)[2:]} (Q{fq} of the financial year); calendar quarter Q{(d.month - 1) // 3 + 1} {d.year}."


@tool(C, ex={"start": "2026-11-01", "every_days": 28, "count": 6}, keys="recurring schedule repeat every dates")
def repeating_dates(start: str, every_days: int, count: int = 6) -> list:
    """A list of dates repeating every N days (refills, payments, cycles)."""
    d = parse_date(start)
    return [(d + timedelta(days=every_days * i)).strftime("%a %d %b %Y") for i in range(max(1, min(count, 60)))]
