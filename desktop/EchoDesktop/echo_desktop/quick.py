"""Exact answers in milliseconds, without the AI, for requests that are really a calculation or a lookup Echo already
has a tool for ("3 lakh loan 14% 3 years emi", "remove 18% gst from 1,18,000", "5 feet 2 inch in cm", "working days
between 10 November and 5 December", "karthika pournami eppudu", "today tithi").

How it stays general and safe (nothing here knows any example sentence):
- the toolbox Router ranks tools by their own names, descriptions and keywords;
- a tool is used only if one of ITS OWN name/keyword words is in the request (no synonym-only guesses);
- its arguments are filled by meaning, from the request: a number with % is a rate, "N years M months" a duration,
  ₹/rs/lakh/crore/k an amount, "D Month [YYYY]" a date, "N unit in unit" a conversion;
- every required argument must get exactly one value and no number in the request may be left unused, otherwise the
  AI answers as before (it is never worse than before, only faster when it's certain);
- a short follow-up ("if 2 years only then?", "make it 3000", "same but 2 years 6 months") re-runs the last
  calculation with just the changed value.
The answer repeats the inputs it used, so the user can see exactly what was calculated.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

NUM = r"\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+"
SCALE = {"lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "l": 1e5, "crore": 1e7, "crores": 1e7, "cr": 1e7,
         "k": 1e3, "thousand": 1e3, "million": 1e6, "mn": 1e6}
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
# argument names by meaning (any tool that uses these names takes part; no tool is listed by name)
RATE = {"annual_rate", "annual_return", "rate", "percent", "interest_rate", "return_rate", "inflation"}
YEARS = {"years"}
MONTHS_P = {"months"}
MONEY = {"principal", "price", "amount", "monthly", "goal", "start", "end", "bill", "last_basic_plus_da", "yearly",
         "cost", "gain", "salary", "income", "sip", "loan", "deposit"}
DATES = {"start", "end", "day", "date", "on_date", "from_date", "to_date"}
PEOPLE = {"people", "persons", "members"}
PLAIN = {"value", "part", "whole", "old", "new", "n", "number"}       # a plain quantity, not money ("20% of 4500")
QUICK_CATEGORIES = {"money", "units", "time", "india", "math"}
GENERIC = {"convert", "value", "number", "calc", "calculate", "total", "how", "much", "many", "what", "time", "date",
           "days", "day", "year", "years", "month", "months", "monthly", "price", "amount", "rate", "add",
           "remove", "split", "get", "find", "between", "from", "to", "in", "the", "a", "of", "for", "and", "on", "at"}
EXPLAIN = re.compile(r"(?i)\b(?:explain|why|how does|how do|what is the difference|compare|vs|versus|should i|"
                     r"better|best|advice|suggest|step by step|meaning|define|briefly|summar)\b")
FOLLOW = re.compile(r"(?i)^\s*(?:and\s+|ok\s+|now\s+|but\s+)?(?:if|what if|then|same|make it|instead|change it|try)\b|"
                    r"^\s*(?:and|but|ok|now)\s+(?:at|for|with|over|in)\b|\b(?:then|instead|same|only|make it)\b")


@dataclass
class Tok:
    kind: str            # pct | years | months | money | num | date | qty
    value: object
    pos: int
    unit: str = ""
    text: str = ""


@dataclass
class Last:
    tool: str = ""
    args: dict = field(default_factory=dict)
    at: float = 0.0


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _units():
    from .toolbox import t_units as U
    tables = {"convert_length": U.LENGTH, "convert_weight": U.MASS, "convert_volume": U.VOLUME, "convert_area": U.AREA,
              "convert_speed": U.SPEED, "convert_data_size": U.DATA, "convert_energy": U.ENERGY,
              "convert_pressure": U.PRESSURE, "convert_power": U.POWER, "convert_angle": U.ANGLE}
    alias = {}
    for tool, table in tables.items():
        for key, (factor, names) in table.items():
            for n in (key,) + tuple(names):
                alias.setdefault(n.lower(), (tool, key, factor))
    return alias


_UNIT_ALIAS: Optional[dict] = None


def unit_alias() -> dict:
    global _UNIT_ALIAS
    if _UNIT_ALIAS is None:
        _UNIT_ALIAS = _units()
    return _UNIT_ALIAS


def tokens(text: str, today: Optional[date] = None) -> list:
    """Typed values in the request, in order. Spans used by one kind are not read again as plain numbers."""
    t = text.lower().replace("₹", " rs ")
    out, taken = [], []

    def free(a, b):
        return all(b <= x or a >= y for x, y in taken)

    def add(tok, a, b):
        out.append(tok)
        taken.append((a, b))

    # dates: "10 November [2026]", "November 10[, 2026]", "10/11/2026", "2026-11-10"
    mon = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
    for m in re.finditer(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{mon}\.?(?:,?\s+(\d{{4}}))?\b", t):
        add(Tok("date", (int(m.group(1)), MONTHS.index(m.group(2)[:3]) + 1, m.group(3)), m.start(), text=m.group(0)), *m.span())
    for m in re.finditer(rf"\b{mon}\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(\d{{4}}))?\b", t):
        if free(*m.span()):
            add(Tok("date", (int(m.group(2)), MONTHS.index(m.group(1)[:3]) + 1, m.group(3)), m.start(), text=m.group(0)), *m.span())
    for m in re.finditer(r"\b(\d{4})-(\d{2})-(\d{2})\b|\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b", t):
        if free(*m.span()):
            g = m.groups()
            v = (int(g[2]), int(g[1]), g[0]) if g[0] else (int(g[3]), int(g[4]), g[5])
            add(Tok("date", v, m.start(), text=m.group(0)), *m.span())
    for m in re.finditer(rf"({NUM})\s*(?:people|persons|ppl|members|friends|of us|heads)\b", t):
        add(Tok("people", int(_num(m.group(1))), m.start(), text=m.group(0)), *m.span())
    for m in re.finditer(rf"({NUM})\s*(?:%|percent\b|per cent\b|pc\b|pct\b)", t):
        add(Tok("pct", _num(m.group(1)), m.start(), text=m.group(0)), *m.span())
    for m in re.finditer(rf"({NUM})\s*(?:years?|yrs?)\b(?:\s*(?:and\s+)?({NUM})\s*(?:months?|mths?)\b)?", t):
        if free(*m.span()):
            y = _num(m.group(1)) + (_num(m.group(2)) / 12 if m.group(2) else 0)
            add(Tok("years", y, m.start(), text=m.group(0)), *m.span())
    for m in re.finditer(rf"({NUM})\s*(?:months?|mths?)\b", t):
        if free(*m.span()):
            add(Tok("months", _num(m.group(1)), m.start(), text=m.group(0)), *m.span())
    scale = "|".join(sorted(SCALE, key=len, reverse=True))
    for m in re.finditer(rf"(?:\b(?:rs\.?|inr|rupees?)\s*)?({NUM})\s*({scale})\b|\b(?:rs\.?|inr)\s*({NUM})|({NUM})\s*(?:rs\b|rupees?\b|/-)", t):
        if free(*m.span()):
            if m.group(1):
                v = _num(m.group(1)) * SCALE[m.group(2)]
            else:
                v = _num(m.group(3) or m.group(4))
            add(Tok("money", v, m.start(), text=m.group(0)), *m.span())
    alias = unit_alias()
    names = "|".join(re.escape(a) for a in sorted(alias, key=len, reverse=True))
    for m in re.finditer(rf"({NUM})\s*({names})(?![a-z])", t):
        if free(*m.span()):
            add(Tok("qty", _num(m.group(1)), m.start(), unit=m.group(2), text=m.group(0)), *m.span())
    for m in re.finditer(NUM, t):
        if free(*m.span()) and not re.match(r"[a-z]", t[m.end():m.end() + 1] or " "):
            if t[max(0, m.start() - 1):m.start()].isalpha():
                continue                                   # part of a word or code ("80c", "194j", "v2")
            add(Tok("num", _num(m.group(0)), m.start(), text=m.group(0)), *m.span())
    out.sort(key=lambda k: k.pos)
    return out


def _date(tok: Tok, today: date) -> date:
    d, mth, y = tok.value
    year = int(y) if y else today.year
    return date(year, mth, d)


def _words(text: str) -> set:
    ws = set(re.findall(r"[a-z0-9]+", text.lower()))
    return ws | {w[:-1] for w in ws if len(w) > 4 and w.endswith("s")}


def _kind(name: str, schema: dict) -> str:
    t = schema.get("type")
    if t in ("number", "integer"):
        if name in RATE:
            return "rate"
        if name in YEARS:
            return "years"
        if name in MONTHS_P:
            return "months"
        if name in MONEY:
            return "money"
        if name in PEOPLE:
            return "people"
        if name in PLAIN:
            return "plain"
        return ""
    if t == "string" and name in DATES:
        return "date"
    return ""


def fill(tool, toks: list, today: date) -> Optional[dict]:
    """Arguments for `tool` from the typed values, or None when anything is missing, doubtful or left over."""
    props, req = tool.schema.get("properties", {}), list(tool.schema.get("required", []))
    kinds = {p: _kind(p, s) for p, s in props.items()}
    if any(not kinds[p] for p in req):
        return None
    pools = {"rate": [t for t in toks if t.kind == "pct"], "years": [t for t in toks if t.kind == "years"],
             "months": [t for t in toks if t.kind == "months"], "date": [t for t in toks if t.kind == "date"],
             "money": [t for t in toks if t.kind == "money"], "people": [t for t in toks if t.kind == "people"]}
    plain = [t for t in toks if t.kind == "num"]
    if any(t.kind == "qty" for t in toks):
        return None
    need = {k: [p for p in props if kinds[p] == k and (p in req or pools.get(k))] for k in set(kinds.values()) if k}
    # a duration said in the other unit ("18 months" for a years argument, "3 years" for months)
    if need.get("years") and not pools["years"] and pools["months"]:
        pools["years"] = [Tok("years", t.value / 12, t.pos, text=t.text) for t in pools["months"]]
        pools["months"] = []
    if need.get("months") and not pools["months"] and pools["years"]:
        pools["months"] = [Tok("months", round(t.value * 12), t.pos, text=t.text) for t in pools["years"]]
        pools["years"] = []
    if need.get("plain"):                                  # a plain quantity: any unmarked number (or a ₹ amount)
        pools["plain"] = sorted(plain + ([] if need.get("money") else pools["money"]), key=lambda t: t.pos)
        plain = []
    # plain numbers can only be amounts (never rates or durations, which people always mark)
    if len(pools["money"]) < len(need.get("money", [])):
        pools["money"] = sorted(pools["money"] + plain, key=lambda t: t.pos)
        plain = []
    args = {}
    for kind, params in need.items():
        pool = pools.get(kind, [])
        must = [p for p in params if p in req]
        if len(pool) < len(must) or len(pool) > len(params):
            return None
        for p, tok in zip(params, pool):
            args[p] = _date(tok, today).isoformat() if kind == "date" else tok.value
    used = len({id(t) for k in need for t in pools.get(k, [])})
    if plain or used != len(toks):                       # a number we'd silently ignore: let the AI read it all
        return None
    return args


def _say_inputs(tool, args: dict) -> str:
    from .toolbox.t_money import rs
    from .toolbox import fmt
    props = tool.schema.get("properties", {})
    money = [rs(args[p]) for p in props if p in args and _kind(p, props[p]) == "money"]
    parts = [" → ".join(money) if {"start", "end"} <= set(args) else ", ".join(money)] if money else []
    plain = {p: fmt(args[p]) for p in props if p in args and _kind(p, props[p]) == "plain"}
    if {"part", "whole"} <= set(plain):
        parts.append(f"{plain['part']} of {plain['whole']}")
    elif {"old", "new"} <= set(plain):
        parts.append(f"{plain['old']} → {plain['new']}")
    elif plain:
        rate = [p for p in props if p in args and _kind(p, props[p]) == "rate"]
        if rate and len(plain) == 1:                       # "55% of 58,400"
            return f"{fmt(args[rate[0]])}% of {next(iter(plain.values()))}"
        parts.append(", ".join(plain.values()))
    for p in props:
        if p not in args:
            continue
        k = _kind(p, props[p])
        if k == "rate":
            parts.append(f"at {fmt(args[p])}%")
        elif k == "years":
            y = args[p]
            whole, mo = int(y), round((y - int(y)) * 12)
            parts.append("for " + " ".join(x for x in (f"{whole} year{'s' if whole != 1 else ''}" if whole else "",
                                                        f"{mo} month{'s' if mo != 1 else ''}" if mo else "") if x))
        elif k == "months":
            parts.append(f"for {int(args[p])} months")
        elif k == "people":
            parts.append(f"for {int(args[p])} people")
    if "start" in args and isinstance(args.get("start"), str):
        a, b = date.fromisoformat(args["start"]), date.fromisoformat(args["end"])
        parts = [f"{a:%d %b %Y} to {b:%d %b %Y}"]
    return " ".join(x for x in parts if x)


def _says(tool) -> bool:
    """The tool answers in words (str/number), not a table or JSON that needs the AI to explain it."""
    import inspect
    ret = inspect.signature(tool.fn).return_annotation
    return ret in (str, float, int, "str", "float", "int")


def _with_inputs(tool, args: dict, out: str) -> str:
    """The answer, led by the inputs used — unless the answer already shows every one of them."""
    from .toolbox import fmt
    from .toolbox.t_money import rs
    digits = [d.strip(".") for d in re.sub(r"[^\d.]", " ", out.replace(",", "")).split()]
    def shown(v):
        if not isinstance(v, (int, float)):
            try:
                d = date.fromisoformat(str(v))
                return f"{d:%d %b %Y}" in out or f"{d.day} {d:%b %Y}" in out
            except ValueError:
                return str(v) in out
        return any(re.sub(r"[^\d.]", "", s).rstrip(".") in digits for s in (fmt(v), rs(v), str(v)))
    if all(shown(v) for v in args.values()):
        return out
    head = _say_inputs(tool, args)
    return f"{head}: {out}" if head else out


class Quick:
    def __init__(self, toolbox_call, router, now=None, ctx=None):
        self.call, self.router, self.now = toolbox_call, router, now or (lambda: date.today())
        self.last = Last()

    # ---------------------------------------------------------------- calendar: festivals and tithi
    def calendar(self, text: str) -> Optional[str]:
        from .toolbox import t_festivals as F
        low = F._norm(text)
        words = set(low.split())
        when = re.search(r"\b(?:when|dates?|days?|eppudu|eppudo|epudu|kab|kabhi|which|falls?|ela|enni|how many days)\b|"
                         r"ఎప్పుడు|कब", text.lower())
        if words & {"tithi", "thithi", "panchang", "panchangam", "paksha"} or "తిథి" in text or "तिथि" in text:
            day = "tomorrow" if "tomorrow" in words or "repu" in words else "yesterday" if "yesterday" in words else "today"
            toks = [t for t in tokens(text) if t.kind == "date"]
            if toks:
                day = _date(toks[0], self.now()).isoformat()
            return self.call("tithi", {"day": day})
        if not when and not words & {"next", "upcoming"}:
            return None
        d = F._data()
        names = {F._norm(f["name"]): f["name"] for f in d["festivals"]}
        names.update({F._norm(a): r for a, r in d["aliases"].items()})
        best = ""
        for n in names:
            nw = n.split()
            if nw and set(nw) <= words and len(n) > len(best):
                best = n
        kinds = {"ekadashi", "ekadasi", "purnima", "pournami", "amavasya", "amavasai", "sankranti"}
        year = re.search(r"\b(20\d\d)\b", text)
        if not best or F._norm(names[best]) in kinds:
            kind = names.get(best) or next((names.get(w, w) for w in words if w in kinds), "")
            if not kind:
                return None
            return self.call("next_festivals", {"kind": kind, "count": 1})   # "next ekadashi": the next of that kind
        return self.call("festival_date", {"name": names[best], **({"year": int(year.group(1))} if year else {})})

    # ---------------------------------------------------------------- units: "5 feet 2 inch in cm"
    def units(self, text: str) -> Optional[str]:
        from .toolbox import fmt
        t = text.lower()
        alias = unit_alias()
        names = "|".join(re.escape(a) for a in sorted(alias, key=len, reverse=True))
        m = re.search(rf"\b(?:in|to|into|as)\s+(?:a\s+)?({names})\s*\??\s*$", t)
        if not m:
            return None
        target = alias[m.group(1)]
        toks = tokens(text[:m.start()])
        qty = [k for k in toks if k.kind == "qty"]
        if not qty or len(qty) != len(toks):
            return None
        parts = [alias[k.unit] for k in qty]
        if any(p[0] != target[0] for p in parts):
            return None                                    # mixed kinds ("5 kg in cm"): not a conversion
        total = sum(k.value * p[2] for k, p in zip(qty, parts)) / target[2]
        said = " ".join(f"{fmt(k.value)} {p[1]}" for k, p in zip(qty, parts))
        return f"{said} = {fmt(round(total, 4))} {target[1]}"

    # ---------------------------------------------------------------- tools by meaning
    def compute(self, text: str) -> Optional[str]:
        if EXPLAIN.search(text) or len(text.split()) > 30:
            return None
        today = self.now()
        toks = tokens(text, today)
        if not toks:
            return None
        if FOLLOW.search(text) and self.last.tool and time.monotonic() - self.last.at < 900:
            again = self.follow_up(text, toks, today)       # "make it 4 lakh" changes the last sum first
            if again:
                return again
        said = _words(text) | ({"percent"} if "%" in text else set())
        ranked = self.router.search(text.replace("%", " percent "), 8)
        fits = []
        for i, tool in enumerate(ranked):
            if tool.category not in QUICK_CATEGORIES or tool.ask or tool.app or not _says(tool):
                continue
            words = _words(tool.name.replace("_", " ")) | _words(tool.keywords)
            if not (words - GENERIC) & said:
                continue                                   # the request never names this tool's subject
            args = fill(tool, toks, today)
            if args is not None:                           # most of its own words said ("remove gst" → gst_remove)
                fits.append((-len(words & said), i, tool, args))
        for _, _, tool, args in sorted(fits, key=lambda f: f[:2])[:1]:
            out = self.call(tool.name, args)
            if out.startswith("ERROR"):
                return None
            self.last = Last(tool.name, dict(args), time.monotonic())
            return _with_inputs(tool, args, out)
        return self.follow_up(text, toks, today)

    def follow_up(self, text: str, toks: list, today: date) -> Optional[str]:
        """"if 2 years only then?" / "make it 3000" / "same but at 8%": the last calculation with one value changed."""
        if not self.last.tool or time.monotonic() - self.last.at > 900 or len(text.split()) > 12 or not FOLLOW.search(text):
            return None
        from .toolbox import load
        tool = load().get(self.last.tool)
        props = tool.schema.get("properties", {})
        args = dict(self.last.args)
        changed = False
        if not toks or len(toks) > 3 or len({t.kind for t in toks}) != len(toks):
            return None                                    # one new value per kind, or it's a new question
        for tok in toks:
            kind = {"pct": "rate", "years": "years", "months": "months", "money": "money", "num": "money",
                    "date": "date"}.get(tok.kind)
            if kind == "years" and not any(_kind(p, s) == "years" for p, s in props.items()):
                kind, tok = "months", Tok("months", round(tok.value * 12), tok.pos)
            if kind == "months" and not any(_kind(p, s) == "months" for p, s in props.items()):
                kind, tok = "years", Tok("years", tok.value / 12, tok.pos)
            params = [p for p, s in props.items() if _kind(p, s) == kind]
            if len(params) != 1:
                return None                                # which amount? the AI asks
            args[params[0]] = _date(tok, today).isoformat() if kind == "date" else tok.value
            changed = True
        if not changed:
            return None
        out = self.call(tool.name, args)
        if out.startswith("ERROR"):
            return None
        self.last = Last(tool.name, dict(args), time.monotonic())
        return _with_inputs(tool, args, out)

    def answer(self, text: str) -> Optional[str]:
        for step in (self.calendar, self.units, self.compute):
            try:
                out = step(text)
            except Exception:                              # a fast path never breaks the normal answer
                out = None
            if out:
                return out
        return None
