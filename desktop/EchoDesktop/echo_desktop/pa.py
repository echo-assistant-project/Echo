"""Echo's personal-assistant memory: tasks, follow-ups, people, habits, money, journal, focus sessions, meeting notes
and phrases you taught Echo — plus a natural date parser ("tomorrow 5pm", "in 3 days", "next friday", "5 nov").

Everything stays on this PC in one DPAPI-encrypted file (%APPDATA%\\EchoDesktop\\assistant.bin, this Windows user
only). The Echo app and the echo-tools MCP server can both use it; a lock file keeps their writes from colliding.
Pure except for the store's file I/O; tested in tests/test_pa.py.
"""
from __future__ import annotations

import calendar
import json
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

# ------------------------------------------------------------------------------------------------ natural dates
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_WD = {w: i for i, w in enumerate(WEEKDAYS)}
_WD.update({"mon": 0, "tue": 1, "tues": 1, "wed": 2, "thu": 3, "thur": 3, "thurs": 3, "fri": 4, "sat": 5, "sun": 6})
_MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
_MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
_MONTHS["sept"] = 9
_NUM = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
        "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty five": 45, "couple of": 2,
        "few": 3}
_PARTS = {"morning": 9, "afternoon": 15, "evening": 18, "night": 20, "tonight": 20, "noon": 12, "midday": 12, "lunch": 13,
          "lunchtime": 13, "midnight": 0}
# parts of the day that decide am/pm for a bare hour (English and common Hindi/Telugu words people type)
_PART_OF = {"morning": "am", "mrng": "am", "subah": "am", "udayam": "am", "pondu": "am", "early morning": "am",
            "afternoon": "pm", "evening": "pm", "eve": "pm", "shaam": "pm", "sham": "pm", "sayantram": "pm",
            "night": "pm", "tonight": "pm", "raat": "pm", "raatri": "pm", "ratri": "pm"}
_PART_WORDS = "|".join(sorted(map(re.escape, _PART_OF), key=len, reverse=True))
_WDRE = "|".join(sorted(_WD, key=len, reverse=True))
_MRE = "|".join(sorted(_MONTHS, key=len, reverse=True))
_NRE = r"\d+|" + "|".join(sorted(map(re.escape, _NUM), key=len, reverse=True))


@dataclass
class When:
    at: Optional[datetime]      # None: no date or time found
    has_time: bool              # False: a whole day (due by the end of it)
    rest: str                   # the text with the date words taken out ("buy milk")


def _num(s: str) -> int:
    s = s.strip().lower()
    return int(s) if s.isdigit() else _NUM.get(s, 1)


def _future_year(month: int, day: int, today: date) -> date:
    d = date(today.year, month, min(day, calendar.monthrange(today.year, month)[1]))
    if d < today:
        d = date(today.year + 1, month, min(day, calendar.monthrange(today.year + 1, month)[1]))
    return d


def _dated(year: Optional[str], month: int, day: int, today: date) -> Optional[date]:
    try:
        return date(int(year), month, day) if year else _future_year(month, day, today)
    except ValueError:
        return None


def _add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def parse_when(text: str, now: Optional[datetime] = None) -> When:
    """Finds one date and/or time anywhere in `text`. Indian day/month order for 5/11 (= 5 November)."""
    now = now or datetime.now()
    today = now.date()
    s = text
    day: Optional[date] = None
    clock: Optional[tuple] = None          # (hour, minute)
    exact: Optional[datetime] = None       # "in 2 hours"

    def take(pattern):
        nonlocal s
        m = re.search(pattern, s, re.I)
        if m:
            s = (s[:m.start()] + " " + s[m.end():])
        return m

    m = take(rf"\bin\s+(half an hour|({_NRE})\s+(minutes?|mins?|hours?|hrs?|days?|weeks?|months?))\b")
    if m:
        if m.group(1).lower() == "half an hour":
            exact = now + timedelta(minutes=30)
        else:
            n, unit = _num(m.group(2)), m.group(3).lower()
            if unit.startswith("min"):
                exact = now + timedelta(minutes=n)
            elif unit.startswith("h"):
                exact = now + timedelta(hours=n)
            elif unit.startswith("d"):
                day = today + timedelta(days=n)
            elif unit.startswith("w"):
                day = today + timedelta(weeks=n)
            else:
                day = _add_months(today, n)
    if exact is None and day is None:
        if m := take(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"):
            day = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        elif m := take(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b"):
            d_, mo = int(m.group(1)), int(m.group(2))
            if 1 <= mo <= 12 and 1 <= d_ <= 31:
                try:
                    y = int(m.group(3)) if m.group(3) else None
                    day = date(y + 2000 if y < 100 else y, mo, d_) if y is not None else _future_year(mo, d_, today)
                except ValueError:
                    day = None
        elif m := take(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MRE})\.?(?:\s+(\d{{4}}))?\b"):
            day = _dated(m.group(3), _MONTHS[m.group(2).lower()], int(m.group(1)), today)
        elif m := take(rf"\b({_MRE})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(\d{{4}}))?\b"):
            day = _dated(m.group(3), _MONTHS[m.group(1).lower()], int(m.group(2)), today)
        elif m := take(r"\b(?:(?:on|by|before|due|till|until)\s+)?(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)\b"
                       r"(?=\s*(?:$|[,.;!?)]|\d|(?:at|of|in|and|to|for|so|then|morning|afternoon|evening|night|noon|please|pls)\b))"):
            # "on 10th", "by the 3rd": that day of this month, or of next month once it has passed. An ordinal followed
            # by a noun ("on the 2nd floor", "on 3rd attempt") is not a date.
            n = int(m.group(1))
            if 1 <= n <= 31:
                y, mo = today.year, today.month
                for _ in range(13):
                    if n <= calendar.monthrange(y, mo)[1] and date(y, mo, n) >= today:
                        day = date(y, mo, n)
                        break
                    y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)
        elif take(r"\bday after tomorrow\b"):
            day = today + timedelta(days=2)
        elif take(r"\byesterday\b"):
            day = today - timedelta(days=1)
        elif take(r"\b(tomorrow|tmrw|tmr)\b"):
            day = today + timedelta(days=1)
        elif take(r"\btoday\b"):
            day = today
        elif m := take(r"\bend of (?:the\s+)?(day|week|month)\b"):
            unit = m.group(1).lower()
            if unit == "day":
                day, clock = today, (18, 0)
            elif unit == "week":
                day, clock = today + timedelta(days=(4 - today.weekday()) % 7), (18, 0)
            else:
                day = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
        elif m := take(r"\b(?:next|this coming)\s+(week|month)\b"):
            day = (today + timedelta(days=7 - today.weekday())) if m.group(1).lower() == "week" else _add_months(today.replace(day=1), 1)
        elif take(r"\b(?:this\s+)?weekend\b"):
            day = today + timedelta(days=(5 - today.weekday()) % 7 or 7) if today.weekday() != 5 else today
        elif m := take(rf"\b(?:(next|this|on|coming)\s+)?({_WDRE})\b"):
            ahead = (_WD[m.group(2).lower()] - today.weekday()) % 7
            day = today + timedelta(days=ahead or 7)
    if exact is None:
        # the part of the day said anywhere ("6 30 tmrw morning", "night 8", "subah 7") sets am/pm for a bare hour
        pm = re.search(rf"(?i)\b({_PART_WORDS})\b", s)
        part = _PART_OF.get(pm.group(1).lower()) if pm else None
        ampm = None
        if m := take(r"\b(?:at|by|@|around)?\s*(\d{1,2})(?:[:. ](\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)(?=\W|$)"):
            h, mi = int(m.group(1)) % 12, int(m.group(2) or 0)
            if m.group(3).lower().startswith("p"):
                h += 12
            clock, ampm = (h, mi), True
        elif m := take(r"\b(?:at|by|@|around)\s+(\d{1,2})(?:[:. ](\d{2}))?\b"):
            h, mi = int(m.group(1)), int(m.group(2) or 0)
            if 1 <= h <= 7 and not m.group(2) and part is None:
                h += 12                     # "at 5" means 5 pm (unless "morning" says otherwise)
            clock = (h % 24, mi)
        elif m := take(r"\b([01]?\d|2[0-3]):([0-5]\d)\b"):
            clock = (int(m.group(1)), int(m.group(2)))
        elif part is not None and (m := take(rf"(?i)\b(?:(?:{_PART_WORDS})\s+(?:at\s+)?(\d{{1,2}})(?:[. ](\d{{2}}))?"
                                             rf"|(\d{{1,2}})(?:[. ](\d{{2}}))?\s+(?:o'?clock\s+)?(?:in the\s+)?(?:{_PART_WORDS}))\b")):
            # "morning 8", "night 8.30", "6 30 morning", "8 o'clock night"
            h, mi = int(m.group(1) or m.group(3)), int(m.group(2) or m.group(4) or 0)
            clock = (h % 24, mi) if 0 <= h <= 23 and 0 <= mi <= 59 else None
        elif part is not None and (m := take(r"\b(\d{1,2})[. ]([0-5]\d)\b")):
            clock = (int(m.group(1)) % 24, int(m.group(2)))           # "at 6 30 tmrw morning" without "at"
        elif m := take(r"\b(?:this\s+|in the\s+|at\s+)?(morning|afternoon|evening|tonight|night|noon|midday|lunchtime|lunch|midnight)\b"):
            clock = (_PARTS[m.group(1).lower()], 0)
            if m.group(1).lower() == "tonight" and day is None:
                day = today
        if clock is not None and part is not None and not ampm:
            h = clock[0]
            if part == "am" and h == 12:
                h = 0
            elif part == "am" and 13 <= h <= 19 and h - 12 <= 7:
                h -= 12                      # "at 6 in the morning" was read as 6 pm above
            elif part == "pm" and 1 <= h <= 11:
                h += 12
            clock = (h, clock[1])
        if clock is not None:          # "10th morning 9am": the clock time already says it; drop the part of day
            take(rf"(?i)\b(?:in the\s+|this\s+)?(?:{_PART_WORDS}|o'?clock)\b")
    rest =re.sub(r"\s+", " ", s).strip(" ,.-")
    rest = re.sub(r"(?i)^(?:by|on|at|due|before|for)\s+|\s+(?:by|on|at|due|before|for|from)$", "", rest).strip(" ,.-")
    if exact is not None:
        return When(exact.replace(second=0, microsecond=0), True, rest)
    if day is None and clock is None:
        return When(None, False, text.strip())
    if day is None:
        at = datetime.combine(today, datetime.min.time()).replace(hour=clock[0], minute=clock[1])
        if at <= now:
            at += timedelta(days=1)
        return When(at, True, rest)
    if clock is None:
        return When(datetime.combine(day, datetime.min.time()), False, rest)
    return When(datetime.combine(day, datetime.min.time()).replace(hour=clock[0], minute=clock[1]), True, rest)


def say_when(at: Optional[datetime], has_time: bool, now: Optional[datetime] = None) -> str:
    """"today 5:00 PM", "tomorrow", "Fri 7 Nov", "overdue since Mon 3 Nov"."""
    if at is None:
        return "no date"
    now = now or datetime.now()
    d = (at.date() - now.date()).days
    label = {0: "today", 1: "tomorrow", -1: "yesterday"}.get(d) or (at.strftime("%A") if 1 < d < 7 else at.strftime("%a %d %b").replace(" 0", " "))
    if has_time:
        label += " " + at.strftime("%I:%M %p").lstrip("0")
    return label


# ------------------------------------------------------------------------------------------------ money words
CATEGORIES = {
    "food": "food lunch dinner breakfast snack snacks coffee tea chai restaurant swiggy zomato pizza biryani meal meals cafe dosa",
    "groceries": "grocery groceries vegetables veggies fruits milk bigbasket blinkit zepto dmart kirana rice atta",
    "transport": "uber ola rapido auto cab taxi bus metro train petrol diesel fuel parking toll fastag",
    "bills": "electricity water gas bill bills recharge broadband wifi internet phone mobile postpaid dth rent maintenance",
    "shopping": "amazon flipkart myntra clothes shoes shirt shopping gift gifts meesho ajio",
    "health": "medicine medicines pharmacy doctor hospital gym chemist apollo lab test",
    "fun": "movie movies netflix prime hotstar spotify game games party outing trip",
    "education": "course books book fees tuition school college udemy coursera",
    "home": "furniture repair plumber electrician cleaning maid cook appliance",
}
_CAT = {w: c for c, words in CATEGORIES.items() for w in words.split()}


def parse_expense(text: str) -> tuple:
    """"250 on lunch", "₹1,200 petrol", "rs 99 for netflix" -> (amount, what, category)."""
    m = re.search(r"(?:₹|rs\.?|inr|rupees?)?\s*(\d[\d,]*(?:\.\d{1,2})?)\s*(k|thousand|lakh|rupees?|rs|bucks)?", text, re.I)
    if not m:
        return None, text.strip(), "other"
    amount = float(m.group(1).replace(",", ""))
    unit = (m.group(2) or "").lower()
    amount *= 1000 if unit in ("k", "thousand") else 100000 if unit == "lakh" else 1
    what = (text[:m.start()] + " " + text[m.end():])
    what = re.sub(r"(?i)\b(i\s+)?(spent|paid|spend|pay|on|for|at|rupees?|rs\.?|inr|₹)\b", " ", what)
    what = re.sub(r"\s+", " ", what).strip(" ,.-") or "expense"
    words = re.findall(r"[a-z]+", what.lower())
    return round(amount, 2), what, next((_CAT[w] for w in words if w in _CAT), "other")


# ------------------------------------------------------------------------------------------------ store
def _app_dir() -> Path:
    return Path(os.environ.get("APPDATA", str(Path.home()))) / "EchoDesktop"


EMPTY = {"version": 1, "tasks": [], "followups": [], "people": {}, "habits": {}, "expenses": [], "budgets": {},
         "journal": [], "focus": [], "meetings": [], "phrases": {}}
LIMITS = {"tasks": 3000, "followups": 1000, "expenses": 20000, "journal": 5000, "focus": 10000, "meetings": 1000}


class Store:
    """One encrypted JSON document. Use `with store.edit() as d:` to change it (locked, saved atomically)."""
    _thread_lock = threading.Lock()

    def __init__(self, path: Optional[Path] = None, encrypt: bool = True):
        self.path = Path(path) if path else _app_dir() / "assistant.bin"
        self.encrypt = encrypt

    def _decode(self, raw: bytes) -> dict:
        if self.encrypt:
            from .storage import unprotect
            raw = unprotect(raw)
        data = json.loads(raw.decode("utf-8"))
        for k, v in EMPTY.items():
            data.setdefault(k, json.loads(json.dumps(v)))
        return data

    def read(self) -> dict:
        try:
            return self._decode(self.path.read_bytes())
        except FileNotFoundError:
            return json.loads(json.dumps(EMPTY))
        except (OSError, ValueError) as e:
            raise OSError(f"Echo's assistant data couldn't be read ({e}).") from None

    @contextmanager
    def _locked(self):
        import msvcrt
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._thread_lock:
            fd = os.open(str(self.path.with_suffix(".lock")), os.O_RDWR | os.O_CREAT)
            try:
                for _ in range(50):
                    try:
                        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                        break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise OSError("Echo's assistant data is busy; try again.")
                try:
                    yield
                finally:
                    os.lseek(fd, 0, 0)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            finally:
                os.close(fd)

    @contextmanager
    def edit(self):
        with self._locked():
            data = self.read()
            yield data
            for k, cap in LIMITS.items():
                if len(data[k]) > cap:
                    data[k] = data[k][-cap:]
            raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
            if self.encrypt:
                from .storage import protect
                raw = protect(raw)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_bytes(raw)
            os.replace(tmp, self.path)


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat(timespec="minutes") if dt else None


def parse_iso(s: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(s) if s else None


def match_one(items: list, query: str, field: str = "title") -> Optional[dict]:
    """By id, exact text, or the item sharing the most words with the query."""
    q = query.strip().lower()
    if not q:
        return None
    for it in items:
        if it.get("id") == q or it.get(field, "").lower() == q:
            return it
    # "the Priya term sheet task", "the deck one": the words that name it, not "the … task"
    qw = set(re.findall(r"[a-z0-9]+", q)) - {"the", "a", "an", "my", "that", "this", "task", "tasks", "one", "item", "todo",
                                             "to", "do", "reminder", "thing", "about", "for", "of", "on", "with"} or set(re.findall(r"[a-z0-9]+", q))
    covering = [it for it in items if qw and qw <= set(re.findall(r"[a-z0-9]+", it.get(field, "").lower()))]
    if covering:                                   # every word you said is in it: the shortest such item
        return min(covering, key=lambda it: len(it.get(field, "")))
    best, score = None, 0.0
    for it in items:
        w = set(re.findall(r"[a-z0-9]+", it.get(field, "").lower()))
        if not w:
            continue
        s = max(len(qw & w) / len(qw | w), 0.9 * len(qw & w) / len(qw))     # most of the words you said are in it
        if s > score:
            best, score = it, s
    return best if score >= 0.5 else None
