"""Offline tools behind the Command Pack's "tool" kind: line-for-line mirror of the phone's LocalTools.kt.

shared/command_tests.json checks that both give exactly the same text. Pure except `windows_offset_minutes`, which
asks Windows' own ICU library for time-zone offsets (Python's zoneinfo needs the tzdata package, which EchoDesktop
does not install).
"""
from __future__ import annotations

import ctypes
import json
import math
import random
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Callable, Optional

from . import catalog

NAMES = {
    "calc", "convert", "currency", "time_in", "time_diff", "time_after", "days_until", "weeks_until", "days_since",
    "weekday_of", "holiday", "date_in", "date_rel", "now_part", "week_number", "day_of_year", "days_left_year",
    "leap_year", "days_in_month", "is_weekend", "random_number", "coin", "dice", "die_sides", "card", "rps", "magic8",
    "yes_no", "choose", "spell", "letter_count", "word_count", "nato", "morse", "reverse", "to_roman", "from_roman",
    "to_binary", "to_hex", "to_octal", "from_binary", "from_hex", "percent_of", "what_percent", "tip", "split",
    "discount", "emi", "bmi", "sqrt", "cube_root", "factorial", "is_prime", "average", "gcd", "lcm", "moon_phase",
    "full_moon", "zodiac", "chinese_zodiac", "age", "alarm_in", "alarm_days", "count_to",
}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTH_WORDS = {**{m.lower(): i + 1 for i, m in enumerate(MONTHS)}, **{m.lower()[:3]: i + 1 for i, m in enumerate(MONTHS)}, "sept": 9}
NUMBER_WORDS = {"zero": 0.0, "a": 1.0, "an": 1.0, "one": 1.0, "two": 2.0, "three": 3.0, "four": 4.0, "five": 5.0, "six": 6.0,
                "seven": 7.0, "eight": 8.0, "nine": 9.0, "ten": 10.0, "eleven": 11.0, "twelve": 12.0, "fifteen": 15.0,
                "twenty": 20.0, "thirty": 30.0, "forty": 40.0, "fifty": 50.0, "sixty": 60.0, "hundred": 100.0, "half": 0.5}
SYNODIC = 29.530588853
NEW_MOON_EPOCH = 947182440


# --------------------------------------------------------------------------- data & results

class ToolData:
    def __init__(self, text: str):
        root = json.loads(text)
        self.topics = {k: list(v) for k, v in root["topics"].items()}
        self.units = {}
        for u in root["units"]:
            unit = (u["cat"], float(u["f"]), u["names"][0])
            for name in u["names"]:
                self.units[name] = unit
        self.currencies = {alias: code.upper() for code, aliases in root["currencies"].items() for alias in aliases}
        self.cities = {k: (v[0], v[1]) for k, v in root["cities"].items()}
        self.morse = dict(root["morse"])
        self.nato = dict(root["nato"])
        self.holidays = [(h["names"], h["label"], h["rule"].split(" ")) for h in root["holidays"]]


def load_data(path: Path = catalog.SHARED / "content.json") -> ToolData:
    return ToolData(path.read_text(encoding="utf-8"))


@dataclass
class Result:
    text: str
    kind: str = "text"          # text | alarm | timer | web
    hour: int = 0
    minute: int = 0
    days: tuple = ()
    seconds: int = 0
    url: str = ""
    net: tuple = ()            # ("EXCHANGE", {...}): a live answer to try first; "web" url is the fallback


@dataclass
class Context:
    now: datetime                                   # aware
    rng: random.Random
    data: ToolData
    offset_minutes: Callable[[str, datetime], int]  # zone id, instant -> UTC offset


class _Reject(Exception):
    pass


def args_for(match) -> dict:
    return {**{k: v for k, v in match.command.spec.items() if k not in ("kind", "tool")}, **match.slots}


def run_match(match, ctx: Context) -> Optional[Result]:
    return run(match.command.spec["tool"], args_for(match), ctx)


def run(tool: str, args: dict, ctx: Context) -> Optional[Result]:
    try:
        return _dispatch(tool, args, ctx)
    except (_Reject, ArithmeticError, ValueError, KeyError, IndexError, OSError):
        return None


# --------------------------------------------------------------------------- formatting

def fmt(x: float) -> str:
    if math.isnan(x) or math.isinf(x):
        raise ArithmeticError("not finite")
    if abs(x) >= 1e15:
        exp = math.floor(math.log10(abs(x)))
        return f"{fmt(x / math.pow(10.0, exp))} times 10 to the {exp}"
    q = Decimal(x).quantize(Decimal("0.01") if abs(x) >= 1 else Decimal("0.0001"), rounding=ROUND_HALF_EVEN).normalize()
    text = format(q, "f")
    return "0" if text == "-0" else text


def clock(hour: int, minute: int) -> str:
    return f"{12 if hour % 12 == 0 else hour % 12}:{minute:02d} {'AM' if hour < 12 else 'PM'}"


def date_text(d: date) -> str:
    return f"{DAYS[d.isoweekday() - 1]}, {d.day} {MONTHS[d.month - 1]} {d.year}"


def plural(n: float, unit: str, with_number: bool = True) -> str:
    word = unit if n == 1.0 else unit + "s"
    return f"{fmt(n)} {word}" if with_number else word


def hm(minutes: int) -> str:
    parts = []
    if minutes // 60 > 0:
        parts.append(plural(float(minutes // 60), "hour"))
    if minutes % 60 > 0:
        parts.append(plural(float(minutes % 60), "minute"))
    return " ".join(parts)


def join_and(items: list) -> str:
    return "".join(items) if len(items) < 2 else ", ".join(items[:-1]) + " and " + items[-1]


# --------------------------------------------------------------------------- parsing helpers

def key(text: Optional[str]) -> str:
    return " ".join(w for t in (text or "").strip().split() for w in catalog.token_words(t))


def num(text: Optional[str]) -> Optional[float]:
    k = key(text)
    if re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", k):
        return float(k)
    return NUMBER_WORDS.get(k)


def whole(text: Optional[str], lo: int, hi: int) -> Optional[int]:
    n = num(text)
    if n is None or n != math.floor(n) or n < lo or n > hi:
        return None
    return int(n)


def time_unit(text: Optional[str]) -> Optional[str]:
    return {"minute": "minute", "minutes": "minute", "min": "minute", "mins": "minute", "hour": "hour", "hours": "hour",
            "hr": "hour", "hrs": "hour", "day": "day", "days": "day", "week": "week", "weeks": "week", "month": "month",
            "months": "month", "year": "year", "years": "year"}.get(key(text))


def _city(text, data: ToolData):
    """"Tokyo", "Tokyo Japan", "Orlando Florida": the longest run of words that names a known place."""
    k = key(text)
    k = k[4:] if k.startswith("the ") else k
    if k in data.cities:
        return data.cities[k]
    if re.search(r"\b(?:distance|far|km|kms|kilometres?|kilometers?|miles?|route|drive|driving|travel|road)\b", k):
        return None                         # "vijayawada to guntur distance and time": a journey, not a clock
    w = k.split(" ")
    longest = getattr(data, "_longest_city", None)
    if longest is None:                     # no place name is longer than this many words; longer runs can't match
        longest = data._longest_city = max((len(c.split(" ")) for c in data.cities), default=1)

    def find(words, most):
        for length in range(min(most, longest), 0, -1):
            for start in range(0, len(words) - length + 1):
                hit = data.cities.get(" ".join(words[start:start + length]))
                if hit:
                    return hit, start, start + length
        return None
    first = find(w, len(w) - 1)
    if first is None:
        return None
    after = w[first[2]:]
    other = find(after, len(after)) if after else None
    if other is not None and set(after[:other[1]]) & {"to", "from", "and", "vs", "versus", "till", "until"}:
        return None                         # "hyderabad to delhi": a trip between two places, not one city's time
    return first[0]


def _local(ctx: Context, zone: str) -> datetime:
    utc = ctx.now.astimezone(timezone.utc)
    return (utc + timedelta(minutes=ctx.offset_minutes(zone, ctx.now))).replace(tzinfo=None)


def _time_of_day(text):
    m = re.search(r"^([0-9]{1,2})(?::([0-9]{2}))?(?: ?(am|pm|a m|p m))?$", key(text))
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2) or "0")
    suffix = (m.group(3) or "").replace(" ", "")
    if minute > 59:
        return None
    if not suffix:
        return (hour, minute) if 0 <= hour <= 23 else None
    if not 1 <= hour <= 12:
        return None
    return hour % 12 + (12 if suffix == "pm" else 0), minute


def _weekdays(text):
    k = key(text)
    for p in ("every ", "on "):
        k = k[len(p):] if k.startswith(p) else k
    if k in ("weekday", "weekdays"):
        return (2, 3, 4, 5, 6), "on weekdays"
    if k in ("weekend", "weekends"):
        return (7, 1), "on weekends"
    if k in ("day", "everyday", "daily", "day of the week"):
        return (1, 2, 3, 4, 5, 6, 7), "every day"
    names = [n for n in re.split(r" and | |,", k) if n.strip() and n not in ("and", "every")]
    days = []
    for n in names:
        idx = next((i for i, d in enumerate(DAYS) if d.lower() == (n[:-1] if n.endswith("s") else n)), -1)
        if idx < 0:
            return None
        if idx not in days:
            days.append(idx)
    if not days:
        return None
    return tuple((i + 1) % 7 + 1 for i in days), "on " + join_and([DAYS[i] for i in days])


@dataclass
class SpokenDate:
    date: date
    label: str
    holiday: Optional[str]
    explicit_year: bool
    year_only: bool = False


def _make(y, m, d):
    try:
        return date(y, m, d)
    except ValueError:
        return None


def spoken_date(text, today: date, data: ToolData, direction: int) -> Optional[SpokenDate]:
    k = key(text)
    k = k[4:] if k.startswith("the ") else k
    if k == "today":
        return SpokenDate(today, "today", None, False)
    if k == "tomorrow":
        d = today + timedelta(days=1)
        return SpokenDate(d, date_text(d), None, False)
    if k == "yesterday":
        d = today - timedelta(days=1)
        return SpokenDate(d, date_text(d), None, False)
    year = None
    m = re.search(r"^(.*?) ([0-9]{4})$", k)
    if m:
        year, k = int(m.group(2)), m.group(1)
    if re.fullmatch(r"[0-9]{4}", k) and year is None:
        y = int(k)
        return SpokenDate(date(y, 1, 1), k, None, True, year_only=True) if 1 <= y <= 9999 else None

    def pick(make):
        if year is not None:
            return make(year)
        this_year = make(today.year)
        if this_year is None:
            return None
        if direction > 0 and this_year < today:
            return make(today.year + 1)
        if direction < 0 and this_year > today:
            return make(today.year - 1)
        return this_year
    for names, label, rule in data.holidays:
        if k in names:
            d = pick(lambda y: holiday_date(rule, y))
            if d is None:
                return None
            return SpokenDate(d, f"{label} ({date_text(d)})", label, year is not None)
    m = re.search(r"^(next |this |last |coming )?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$", k)
    if m:
        if year is not None:
            return None
        target = next(i for i, d in enumerate(DAYS) if d.lower() == m.group(2)) + 1
        dow = today.isoweekday()
        if m.group(1) == "last " or direction < 0:
            delta = -(((dow - target + 7) % 7) or 7)
        else:
            delta = ((target - dow + 7) % 7) or 7
        d = today + timedelta(days=delta)
        return SpokenDate(d, date_text(d), None, False)
    ordinal = r"([0-9]{1,2})(?:st|nd|rd|th)?"
    dm = re.search(rf"^{ordinal} (?:of )?([a-z]+)$", k)
    md = re.search(rf"^([a-z]+) {ordinal}$", k)
    slash = re.search(r"^([0-9]{1,2})/([0-9]{1,2})(?:/([0-9]{4}))?$", k)
    iso = re.search(r"^([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})$", k)
    if dm and dm.group(2) in MONTH_WORDS:
        day, month = int(dm.group(1)), MONTH_WORDS[dm.group(2)]
    elif md and md.group(1) in MONTH_WORDS:
        day, month = int(md.group(2)), MONTH_WORDS[md.group(1)]
    elif slash:
        day, month = int(slash.group(1)), int(slash.group(2))
        if slash.group(3):
            if year is not None:
                return None
            year = int(slash.group(3))
    elif iso and year is None:
        year, month, day = int(iso.group(1)), int(iso.group(2)), int(iso.group(3))
    else:
        return None
    d = pick(lambda y: _make(y, month, day))
    if d is None:
        return None
    return SpokenDate(d, date_text(d), None, year is not None)


def holiday_date(rule: list, year: int) -> Optional[date]:
    if rule[0] == "fixed":
        return _make(year, int(rule[1]), int(rule[2]))
    if rule[0] == "easter":
        return _easter(year) + timedelta(days=int(rule[1] if len(rule) > 1 else "0"))
    if rule[0] == "nth":
        month, n, dow = int(rule[1]), int(rule[2]), int(rule[3])
        if n > 0:
            first_day = date(year, month, 1)
            base = first_day + timedelta(days=(dow - first_day.isoweekday() + 7) % 7 + 7 * (n - 1))
        else:
            last = (date(year + (month == 12), month % 12 + 1, 1)) - timedelta(days=1)
            base = last - timedelta(days=(last.isoweekday() - dow + 7) % 7)
        return base + timedelta(days=int(rule[4] if len(rule) > 4 else "0"))
    return None


def _easter(y: int) -> date:
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    return date(y, (h + l - 7 * m + 114) // 31, (h + l - 7 * m + 114) % 31 + 1)


# --------------------------------------------------------------------------- maths

def roman(n: int) -> str:
    out = []
    for v, s in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
                 (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out.append(s)
            n -= v
    return "".join(out)


def from_roman(r: str) -> int:
    v = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    return sum(-v[c] if i + 1 < len(r) and v[r[i + 1]] > v[c] else v[c] for i, c in enumerate(r))


def smallest_factor(n: int) -> int:
    if n < 2:
        return n
    if n % 2 == 0:
        return 2
    p = 3
    while p * p <= n:
        if n % p == 0:
            return p
        p += 2
    return n


def moon_age(now: datetime) -> float:
    days = (int(now.timestamp()) - NEW_MOON_EPOCH) / 86400.0
    return math.fmod(math.fmod(days, SYNODIC) + SYNODIC, SYNODIC)


def moon_phase(age: float) -> str:
    for limit, name in ((1.84566, "new moon"), (5.53699, "waxing crescent"), (9.22831, "first quarter"),
                        (12.91963, "waxing gibbous"), (16.61096, "full moon"), (20.30228, "waning gibbous"),
                        (23.99361, "last quarter"), (27.68493, "waning crescent")):
        if age < limit:
            return name
    return "new moon"


def zodiac(month: int, day: int) -> str:
    starts = [20, 19, 21, 20, 21, 21, 23, 23, 23, 23, 22, 22]
    signs = ["Capricorn", "Aquarius", "Pisces", "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn"]
    return signs[month] if day >= starts[month - 1] else signs[month - 1]


TEMPS = {"c": "c", "celsius": "c", "centigrade": "c", "degrees celsius": "c", "degree celsius": "c", "degrees c": "c",
         "f": "f", "fahrenheit": "f", "degrees fahrenheit": "f", "degree fahrenheit": "f", "degrees f": "f",
         "k": "k", "kelvin": "k", "kelvins": "k"}


def convert(n: float, from_text: str, to_text: str, data: ToolData) -> Optional[str]:
    a, b = key(from_text), key(to_text)
    if a in TEMPS and b in TEMPS:
        if TEMPS[a] == TEMPS[b]:
            return None
        kelvin = n + 273.15 if TEMPS[a] == "c" else (n - 32) * 5 / 9 + 273.15 if TEMPS[a] == "f" else n
        result = kelvin - 273.15 if TEMPS[b] == "c" else (kelvin - 273.15) * 9 / 5 + 32 if TEMPS[b] == "f" else kelvin
    else:
        ua, ub = data.units.get(a), data.units.get(b)
        if ua is None or ub is None or ua[0] != ub[0] or ua[2] == ub[2]:
            return None
        result = n * ua[1] / ub[1]
    return f"{fmt(n)} {a} is {fmt(result)} {b}."


# --------------------------------------------------------------------------- calculator (own parser; never eval)

CALC_WORDS = sorted([
    ("to the power of", " ^ "), ("raised to the power of", " ^ "), ("raised to", " ^ "), ("multiplied by", " * "),
    ("divided by", " / "), ("square root of", " sqrt "), ("percent of", " % * "), ("squared", " ^ 2 "), ("cubed", " ^ 3 "),
    ("times", " * "), ("into", " * "), ("x", " * "), ("over", " / "), ("plus", " + "), ("minus", " - "),
    ("modulo", " mod "), ("power", " ^ "), ("percent", " % "), ("the", " "), ("equals", " "), ("equal", " "), ("what is", " "),
], key=lambda p: len(p[0]), reverse=True)
_TOKEN = re.compile(r"[0-9]+(?:\.[0-9]+)?|sqrt|mod|[-+*/^%()!]|\S")
_VALID = re.compile(r"[0-9]+(?:\.[0-9]+)?|sqrt|mod|[-+*/^%()!]")


def calc(expression: str) -> Optional[str]:
    s = " " + re.sub(r"(?<=[0-9]),(?=[0-9])", "", expression.lower().replace("×", "*").replace("÷", "/").replace("−", "-")).replace("=", " ").replace("?", " ") + " "
    s = re.sub(r"(?<=[0-9])x(?=[0-9])", " * ", s)
    for word, symbol in CALC_WORDS:
        s = re.sub(r"(?<![a-z])" + re.escape(word) + r"(?![a-z])", symbol, s)
    tokens = _TOKEN.findall(s)
    if not tokens or any(not _VALID.fullmatch(t) for t in tokens):
        return None
    parser = _Calc(tokens)
    value = parser.parse()
    if value is None or parser.operators == 0:
        return None
    if parser.divide_by_zero:
        return "You can't divide by zero."
    if math.isnan(value) or math.isinf(value):
        return "That's undefined."
    return f"That's {fmt(value)}."


class _Calc:
    def __init__(self, tokens):
        self.t, self.i, self.operators, self.divide_by_zero = tokens, 0, 0, False

    def parse(self):
        v = self.expr()
        return v if v is not None and self.i == len(self.t) else None

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def expr(self):
        v = self.term()
        if v is None:
            return None
        while self.peek() in ("+", "-"):
            op = self.t[self.i]
            self.i += 1
            self.operators += 1
            r = self.term()
            if r is None:
                return None
            v = v + r if op == "+" else v - r
        return v

    def term(self):
        v = self.unary()
        if v is None:
            return None
        while self.peek() in ("*", "/", "mod"):
            op = self.t[self.i]
            self.i += 1
            self.operators += 1
            r = self.unary()
            if r is None:
                return None
            if op in ("/", "mod") and r == 0.0:
                self.divide_by_zero = True
                v = math.nan
                continue
            v = v * r if op == "*" else v / r if op == "/" else math.fmod(v, r)
        return v

    def unary(self):
        p = self.peek()
        if p == "-":
            self.i += 1
            v = self.unary()
            return None if v is None else -v
        if p == "+":
            self.i += 1
            return self.unary()
        return self.power()

    def power(self):
        base = self.postfix()
        if base is None or self.peek() != "^":
            return base
        self.i += 1
        self.operators += 1
        exp = self.unary()
        if exp is None:
            return None
        try:
            return math.pow(base, exp)
        except (OverflowError, ValueError):
            return math.nan

    def postfix(self):
        v = self.primary()
        if v is None:
            return None
        while self.peek() in ("!", "%"):
            op = self.t[self.i]
            self.i += 1
            self.operators += 1
            if op == "%":
                v = v / 100
            else:
                if v != math.floor(v) or v < 0 or v > 170:
                    return math.nan
                f = 1.0
                for k in range(2, int(v) + 1):
                    f *= k
                v = f
        return v

    def primary(self):
        tok = self.peek()
        if tok is None:
            return None
        if tok == "(":
            self.i += 1
            v = self.expr()
            if v is None or self.peek() != ")":
                return None
            self.i += 1
            return v
        if tok == "sqrt":
            self.i += 1
            self.operators += 1
            v = self.unary()
            if v is None:
                return None
            return math.sqrt(v) if v >= 0 else math.nan
        if tok[0].isdigit():
            self.i += 1
            return float(tok)
        return None


# --------------------------------------------------------------------------- dispatch

def _need(value):
    if value is None:
        raise _Reject()
    return value


def _dispatch(tool: str, a: dict, ctx: Context) -> Optional[Result]:
    today = ctx.now.date()
    rng = ctx.rng
    T = Result
    if tool == "calc":
        r = calc(_need(a.get("e")))
        return T(r) if r else None
    if tool == "convert":
        r = convert(_need(num(a.get("n"))), _need(a.get("a")), _need(a.get("b")), ctx.data)
        return T(r) if r else None
    if tool == "currency":
        n = _need(num(a.get("n")))
        src, dst = ctx.data.currencies.get(key(a.get("a"))), ctx.data.currencies.get(key(a.get("b")))
        if not src or not dst or src == dst:
            return None
        return T(f"Looking up {fmt(n)} {src} in {dst}.", kind="web", url=f"https://www.google.com/search?q={fmt(n)}+{src}+to+{dst}",
                 net=("EXCHANGE", {"a": src, "b": dst, "n": str(n)}))
    if tool == "time_in":
        zone, name = _need(_city(a.get("c"), ctx.data))
        local = _local(ctx, zone)
        return T(f"In {name} it's {clock(local.hour, local.minute)} on {DAYS[local.isoweekday() - 1]}.")
    if tool == "time_diff":
        za, na = _need(_city(a.get("a"), ctx.data))
        zb, nb = _need(_city(a.get("b"), ctx.data))
        diff = ctx.offset_minutes(za, ctx.now) - ctx.offset_minutes(zb, ctx.now)
        if diff == 0:
            return T(f"{na} and {nb} are on the same time right now.")
        return T(f"{na} is {hm(diff)} ahead of {nb}." if diff > 0 else f"{na} is {hm(-diff)} behind {nb}.")
    if tool == "time_after":
        n = _need(num(a.get("n")))
        unit = _need(time_unit(a.get("u")))
        if unit == "day" or n < 0 or n > 10000:
            return None
        later = ctx.now + timedelta(seconds=math.floor(n * (3600 if unit == "hour" else 60) + 0.5))
        day = f" on {DAYS[later.isoweekday() - 1]}" if later.date() != today else ""
        return T(f"In {fmt(n)} {plural(n, unit, False)} it will be {clock(later.hour, later.minute)}{day}.")
    if tool in ("days_until", "weeks_until", "days_since"):
        past = tool == "days_since"
        d = _need(spoken_date(a.get("d"), today, ctx.data, -1 if past else 1))
        if d.year_only:
            return None
        days = (d.date - today).days
        days = -days if past else days
        if days < 0:
            return None
        if days == 0:
            return T(f"{d.label} is today.")
        if past:
            return T(f"{plural(float(days), 'day')} since {d.label}.")
        if tool == "weeks_until" and days >= 7:
            w, r = days // 7, days % 7
            return T(plural(float(w), "week") + (f" and {plural(float(r), 'day')}" if r > 0 else "") + f" until {d.label}.")
        return T(f"{plural(float(days), 'day')} until {d.label}.")
    if tool == "weekday_of":
        d = _need(spoken_date(a.get("d"), today, ctx.data, 1))
        if d.year_only:
            return None
        return T(f"{date_text(d.date)}{f' ({d.holiday})' if d.holiday else ''} is a {DAYS[d.date.isoweekday() - 1]}.")
    if tool == "holiday":
        d = _need(spoken_date(a.get("h"), today, ctx.data, 1))
        return T(f"{d.holiday} is on {date_text(d.date)}.") if d.holiday else None
    if tool == "date_in":
        n = num(a.get("n"))
        if n is None or n != math.floor(n) or not 0 <= n <= 10000:
            return None
        n = int(n)
        unit = time_unit(a.get("u"))
        if unit == "day":
            target = today + timedelta(days=n)
        elif unit == "week":
            target = today + timedelta(weeks=n)
        elif unit in ("month", "year"):
            months = n if unit == "month" else n * 12
            y, m = divmod(today.month - 1 + months, 12)
            y += today.year
            last = (date(y + (m == 11), (m + 1) % 12 + 1, 1) - timedelta(days=1)).day
            target = date(y, m + 1, min(today.day, last))
        else:
            return None
        return T(f"In {plural(float(n), unit)} it will be {date_text(target)}.")
    if tool == "date_rel":
        offset = int(_need(a.get("offset")))
        d = date_text(today + timedelta(days=offset))
        return T({1: f"Tomorrow is {d}.", -1: f"Yesterday was {d}.", 2: f"The day after tomorrow is {d}.", 0: f"Today is {d}."}.get(offset, f"That's {d}."))
    if tool == "now_part":
        part = a.get("part")
        if part == "month":
            return T(f"It's {MONTHS[today.month - 1]} {today.year}.")
        if part == "year":
            return T(f"It's {today.year}.")
        if part == "quarter":
            return T(f"It's Q{(today.month - 1) // 3 + 1} {today.year}.")
        if part == "datetime":
            return T(f"It's {clock(ctx.now.hour, ctx.now.minute)} on {date_text(today)}.")
        return None
    if tool == "week_number":
        iso = today.isocalendar()
        return T(f"It's week {iso[1]} of {iso[0]}.")
    if tool == "day_of_year":
        return T(f"Today is day {today.timetuple().tm_yday} of {today.year}.")
    if tool == "days_left_year":
        length = 366 if _leap(today.year) else 365
        left = length - today.timetuple().tm_yday
        return T(f"There {'is' if left == 1 else 'are'} {plural(float(left), 'day')} left in {today.year}.")
    if tool == "leap_year":
        y = float(today.year) if a.get("n") is None else _need(num(a.get("n")))
        if y != math.floor(y) or y < 1 or y > 9999:
            return None
        return T(f"{int(y)} {'is' if _leap(int(y)) else 'is not'} a leap year.")
    if tool == "days_in_month":
        m = _need(MONTH_WORDS.get(key(a.get("m"))))
        length = (date(today.year + (m == 12), m % 12 + 1, 1) - date(today.year, m, 1)).days
        return T(f"{MONTHS[m - 1]} has {length} days" + (f" in {today.year}." if m == 2 else "."))
    if tool == "is_weekend":
        dow = today.isoweekday()
        name = DAYS[dow - 1]
        if dow >= 6:
            return T(f"Yes, it's {name}.")
        return T(f"No, it's {name}. The weekend starts in {plural(float(6 - dow), 'day')}.")
    if tool == "random_number":
        lo = 1.0 if a.get("n") is None else _need(num(a.get("n")))
        hi = 100.0 if a.get("n2") is None else _need(num(a.get("n2")))
        if lo != math.floor(lo) or hi != math.floor(hi) or abs(lo) > 1e9 or abs(hi) > 1e9:
            return None
        lo, hi = min(lo, hi), max(lo, hi)
        return T(f"Your number is {rng.randint(int(lo), int(hi))}.")
    if tool == "coin":
        return T("Heads." if rng.random() < 0.5 else "Tails.")
    if tool == "dice":
        count = 1.0 if a.get("n") is None else _need(num(a.get("n")))
        if count != math.floor(count) or not 1 <= count <= 10:
            return None
        rolls = [rng.randint(1, 6) for _ in range(int(count))]
        if len(rolls) == 1:
            return T(f"You rolled {rolls[0]}.")
        return T(f"You rolled {join_and([str(r) for r in rolls])}, for a total of {sum(rolls)}.")
    if tool == "die_sides":
        sides = whole(a.get("n"), 2, 1000)
        return T(f"You rolled {rng.randint(1, sides)}.") if sides else None
    if tool == "card":
        ranks = ["Ace", "2", "3", "4", "5", "6", "7", "8", "9", "10", "Jack", "Queen", "King"]
        suits = ["Hearts", "Diamonds", "Clubs", "Spades"]
        return T(f"You drew the {rng.choice(ranks)} of {rng.choice(suits)}.")
    if tool == "rps":
        return T(f"I choose {rng.choice(['rock', 'paper', 'scissors'])}.")
    if tool == "magic8":
        answers = ctx.data.topics.get("magic8")
        return T(rng.choice(answers)) if answers else None
    if tool == "yes_no":
        return T("Yes." if rng.random() < 0.5 else "No.")
    if tool == "choose":
        x, y = (a.get("a") or "").strip(), (a.get("b") or "").strip()
        if not x or not y or len(x) > 60 or len(y) > 60:
            return None
        return T(f"I pick {x if rng.random() < 0.5 else y}.")
    if tool == "spell":
        w = _need(a.get("w")).strip()
        letters = "".join(c for c in w if c.isalpha())
        if not letters or len(letters) > 40 or len(w.split()) > 3:
            return None
        return T(f"{w} is spelled {', '.join(letters.upper())}.")
    if tool == "letter_count":
        w = _need(a.get("w")).strip()
        n = sum(1 for c in w if c.isalpha())
        if n == 0 or len(w) > 60:
            return None
        return T(f"{w} has {plural(float(n), 'letter')}.")
    if tool == "word_count":
        q = _need(a.get("q")).strip()
        return T(f"That's {plural(float(len(q.split())), 'word')}.")
    if tool == "nato":
        w = _need(a.get("w")).strip()
        codes = [_need(ctx.data.nato.get(c)) for c in w.lower() if c.isalnum()]
        if not codes or len(codes) > 40:
            return None
        return T(f"{w} in the NATO alphabet: {' '.join(codes)}.")
    if tool == "morse":
        w = _need(a.get("w")).strip()
        words = [" ".join(_need(ctx.data.morse.get(c)) for c in word if c.isalnum()) for word in w.lower().split()]
        words = [x for x in words if x]
        if not words or len(w) > 60:
            return None
        return T(f"{w} in Morse code: {' / '.join(words)}")
    if tool == "reverse":
        w = _need(a.get("w")).strip()
        if not w or len(w) > 60:
            return None
        return T(f"{w} backwards is {w[::-1]}.")
    if tool == "to_roman":
        n = whole(a.get("n"), 1, 3999)
        return T(f"{n} is {roman(n)}.") if n else None
    if tool == "from_roman":
        r = _need(a.get("r")).strip().upper()
        if not r or not re.fullmatch(r"M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})", r):
            return None
        return T(f"{r} is {from_roman(r)}.")
    if tool in ("to_binary", "to_hex", "to_octal"):
        n = whole(a.get("n"), 0, 9007199254740992)
        if n is None:
            return None
        spec, name = {"to_binary": ("b", "binary"), "to_hex": ("X", "hexadecimal"), "to_octal": ("o", "octal")}[tool]
        return T(f"{n} in {name} is {format(n, spec)}.")
    if tool in ("from_binary", "from_hex"):
        raw = key(a.get("b")).replace(" ", "")
        raw = raw[2:] if raw.startswith("0x") else raw
        ok = re.fullmatch(r"[01]{1,53}", raw) if tool == "from_binary" else re.fullmatch(r"[0-9a-f]{1,13}", raw)
        if not ok:
            return None
        return T(f"{raw.upper()} in {'binary' if tool == 'from_binary' else 'hexadecimal'} is {int(raw, 2 if tool == 'from_binary' else 16)}.")
    if tool == "percent_of":
        p, x = _need(num(a.get("n"))), _need(num(a.get("n2")))
        return T(f"{fmt(p)} percent of {fmt(x)} is {fmt(p * x / 100)}.")
    if tool == "what_percent":
        p, x = _need(num(a.get("n"))), _need(num(a.get("n2")))
        if x == 0.0:
            return None
        return T(f"{fmt(p)} is {fmt(p / x * 100)} percent of {fmt(x)}.")
    if tool == "tip":
        pct = 15.0 if a.get("n") is None else _need(num(a.get("n")))
        bill = _need(num(a.get("n2")))
        if pct < 0 or pct > 100 or bill <= 0:
            return None
        tip = bill * pct / 100
        return T(f"A {fmt(pct)} percent tip on {fmt(bill)} is {fmt(tip)}, making {fmt(bill + tip)} in total.")
    if tool == "split":
        amount = _need(num(a.get("n2")))
        people = _need(whole(a.get("n"), 2, 1000))
        return T(f"{fmt(amount)} split {people} ways is {fmt(amount / people)} each.")
    if tool == "discount":
        pct, price = _need(num(a.get("n"))), _need(num(a.get("n2")))
        if pct < 0 or pct > 100 or price <= 0:
            return None
        off = price * pct / 100
        return T(f"{fmt(pct)} percent off {fmt(price)} is {fmt(price - off)}, saving {fmt(off)}.")
    if tool == "emi":
        p, rate, term = _need(num(a.get("n"))), _need(num(a.get("n2"))), _need(num(a.get("n3")))
        unit = time_unit(a.get("u"))
        months = term * 12 if unit == "year" else term if unit == "month" else None
        if months is None or p <= 0 or rate < 0 or rate > 100 or months != math.floor(months) or months < 1 or months > 600:
            return None
        r = rate / 1200
        emi = p / months if r == 0.0 else p * r * math.pow(1 + r, months) / (math.pow(1 + r, months) - 1)
        return T(f"Your monthly payment would be {fmt(emi)} for {int(months)} months, with {fmt(emi * months - p)} total interest.")
    if tool == "bmi":
        kg, cm = _need(num(a.get("n"))), _need(num(a.get("n2")))
        if not 2.0 <= kg <= 500.0 or not 40.0 <= cm <= 260.0:
            return None
        m = cm / 100
        bmi = kg / (m * m)
        band = "underweight" if bmi < 18.5 else "healthy" if bmi < 25 else "overweight" if bmi < 30 else "obese"
        return T(f"Your BMI is {fmt(bmi)}, in the {band} range. BMI is only a rough guide.")
    if tool == "sqrt":
        n = _need(num(a.get("n")))
        if n < 0:
            return None
        return T(f"The square root of {fmt(n)} is {fmt(math.sqrt(n))}.")
    if tool == "cube_root":
        n = _need(num(a.get("n")))
        return T(f"The cube root of {fmt(n)} is {fmt(math.cbrt(n))}.")
    if tool == "factorial":
        n = whole(a.get("n"), 0, 1000)
        if n is None:
            return None
        f = math.factorial(n)
        return T(f"{n} factorial is {f}." if n <= 20 else f"{n} factorial has {len(str(f))} digits, too long to read out.")
    if tool == "is_prime":
        n = whole(a.get("n"), 0, 1_000_000_000_000)
        if n is None:
            return None
        p = smallest_factor(n)
        if n < 2:
            return T(f"No, {n} is not prime.")
        return T(f"Yes, {n} is prime." if p == n else f"No, {n} is not prime: it's {p} times {n // p}.")
    if tool == "average":
        s = key(a.get("l"))
        if re.sub(r"\b(and|comma)\b", " ", re.sub(r"-?[0-9]+(?:\.[0-9]+)?", " ", s)).strip():
            return None
        values = [float(v) for v in re.findall(r"-?[0-9]+(?:\.[0-9]+)?", s)]
        if len(values) < 2:
            return None
        return T(f"The average of those {len(values)} numbers is {fmt(sum(values) / len(values))}.")
    if tool in ("gcd", "lcm"):
        x, y = whole(a.get("n"), 1, 1_000_000_000_000), whole(a.get("n2"), 1, 1_000_000_000_000)
        if x is None or y is None:
            return None
        g = math.gcd(x, y)
        if tool == "gcd":
            return T(f"The greatest common divisor of {x} and {y} is {g}.")
        return T(f"The least common multiple of {x} and {y} is {x // g * y}.")
    if tool in ("moon_phase", "full_moon"):
        age = moon_age(ctx.now)
        phase = moon_phase(age)
        lit = int(math.floor((1 - math.cos(2 * math.pi * age / SYNODIC)) / 2 * 100 + 0.5))
        if tool == "moon_phase":
            return T(f"The moon is a {phase}, about {lit} percent lit.")
        if phase == "full moon":
            return T(f"Yes, it's a full moon, about {lit} percent lit.")
        days = max(math.floor(math.fmod(math.fmod(SYNODIC / 2 - age, SYNODIC) + SYNODIC, SYNODIC) + 0.5), 1.0)
        return T(f"No, it's a {phase}. The next full moon is in about {plural(float(days), 'day')}.")
    if tool == "zodiac":
        d = _need(spoken_date(a.get("d"), today, ctx.data, 0))
        if d.year_only:
            return None
        sign = zodiac(d.date.month, d.date.day)
        return T(f"Someone born on {d.date.day} {MONTHS[d.date.month - 1]} is {'an' if sign[0] in 'AEIOU' else 'a'} {sign}.")
    if tool == "chinese_zodiac":
        y = whole(a.get("n"), 1, 9999)
        if y is None:
            return None
        animals = ["Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake", "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig"]
        return T(f"{y} is the year of the {animals[((y - 4) % 12 + 12) % 12]}.")
    if tool == "age":
        d = _need(spoken_date(a.get("d"), today, ctx.data, -1))
        if not d.explicit_year or d.date > today:
            return None
        if d.year_only:
            return T(f"Someone born in {d.date.year} turns {today.year - d.date.year} in {today.year}.")
        years = today.year - d.date.year - ((today.month, today.day) < (d.date.month, d.date.day))
        return T(f"Someone born on {date_text(d.date)} is {plural(float(years), 'year')} old.")
    if tool == "alarm_in":
        n = _need(num(a.get("n")))
        unit = _need(time_unit(a.get("u")))
        if unit == "day" or n <= 0:
            return None
        seconds = math.floor(n * (3600 if unit == "hour" else 60) + 0.5)
        if not 60 <= seconds <= 86_400:
            return None
        at = ctx.now + timedelta(seconds=seconds)
        return T(f"Setting an alarm for {clock(at.hour, at.minute)}.", kind="alarm", hour=at.hour, minute=at.minute)
    if tool == "alarm_days":
        h, m = _need(_time_of_day(a.get("t")))
        days, label = _need(_weekdays(a.get("days")))
        return T(f"Setting an alarm for {clock(h, m)} {label}.", kind="alarm", hour=h, minute=m, days=days)
    if tool == "count_to":
        n = whole(a.get("n"), 1, 50)
        return T(", ".join(str(i) for i in range(1, n + 1)) + ".") if n else None
    return None


def _leap(y: int) -> bool:
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


# --------------------------------------------------------------------------- Windows time zones (ICU)

_icu = None


def windows_offset_minutes(zone: str, instant: datetime) -> int:
    """UTC offset of an IANA zone at an instant, from Windows' built-in ICU (Windows 10 1903+)."""
    global _icu
    if _icu is None:
        lib = ctypes.WinDLL("icu.dll")
        lib.ucal_open.restype = ctypes.c_void_p
        lib.ucal_open.argtypes = [ctypes.c_wchar_p, ctypes.c_int32, ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        lib.ucal_setMillis.argtypes = [ctypes.c_void_p, ctypes.c_double, ctypes.POINTER(ctypes.c_int)]
        lib.ucal_get.restype = ctypes.c_int32
        lib.ucal_get.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        lib.ucal_close.argtypes = [ctypes.c_void_p]
        lib.ucal_getTimeZoneID.restype = ctypes.c_int32
        lib.ucal_getTimeZoneID.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int32, ctypes.POINTER(ctypes.c_int)]
        _icu = lib
    status = ctypes.c_int(0)
    cal = _icu.ucal_open(zone, len(zone), b"en_US", 1, ctypes.byref(status))
    if not cal or status.value > 0:
        raise OSError(f"unknown time zone {zone}")
    # ICU quietly uses GMT ("Etc/Unknown", status 0) for a name it doesn't know: that must not pass as offset 0
    got, st = ctypes.create_unicode_buffer(128), ctypes.c_int(0)
    _icu.ucal_getTimeZoneID(cal, got, 128, ctypes.byref(st))
    if got.value == "Etc/Unknown" and zone != "Etc/Unknown":
        _icu.ucal_close(cal)
        raise OSError(f"unknown time zone {zone}")
    try:
        _icu.ucal_setMillis(cal, instant.timestamp() * 1000.0, ctypes.byref(status))
        total = _icu.ucal_get(cal, 15, ctypes.byref(status)) + _icu.ucal_get(cal, 16, ctypes.byref(status))  # zone + DST
        if status.value > 0:
            raise OSError("ICU error")
        return total // 60000
    finally:
        _icu.ucal_close(cal)


def context(data: ToolData, now: Optional[datetime] = None, rng: Optional[random.Random] = None) -> Context:
    return Context(now or datetime.now().astimezone(), rng or random.Random(), data, windows_offset_minutes)
