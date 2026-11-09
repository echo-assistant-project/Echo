"""More tools across categories (each one says its own category)."""
from __future__ import annotations

import csv
import io
import json
import math
import re
from typing import Literal

from . import ToolError, fmt, tool
from ..words import many


# ---- time
@tool("time", ex={"places": ["Hyderabad", "London", "New York", "Tokyo"]}, keys="world clock many cities times now")
def world_clock(places: list[str]) -> list:
    """The time now in several places at once."""
    from .t_time import local_now, zone_of
    out = []
    for p in places[:12]:
        label, zone = zone_of(p)
        out.append(f"{label}: {local_now(zone):%a %I:%M %p}".replace(" 0", " "))
    return out


# ---- text
@tool("text", ex={"text": "This is a line\nthat was broken\nin the middle.\n\nNew paragraph."}, keys="remove line breaks join paragraphs unwrap pdf copy")
def remove_line_breaks(text: str, keep_paragraphs: bool = True) -> str:
    """Join lines broken in the middle of sentences (e.g. text copied from a PDF)."""
    if keep_paragraphs:
        return "\n\n".join(" ".join(p.split()) for p in re.split(r"\n\s*\n", text) if p.strip())
    return " ".join(text.split())


@tool("text", ex={"text": "Meet on 5 Nov 2026, then 2026-12-01 and 15/01/2027."}, keys="extract dates find dates in text")
def extract_dates(text: str) -> list:
    """Find dates written in a text."""
    pat = (r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b|"
           r"\b\d{1,2}(?:st|nd|rd|th)? (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?,? \d{4}\b|"
           r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.? \d{1,2}(?:st|nd|rd|th)?,? \d{4}\b")
    return re.findall(pat, text, re.I)


@tool("text", ex={"text": "This darn thing is heck of a mess", "words": ["darn", "heck"]}, keys="censor mask hide words redact")
def censor_words(text: str, words: list[str], mask: str = "*") -> str:
    """Mask chosen words in a text."""
    out = text
    for w in words:
        out = re.sub(rf"\b{re.escape(w)}\b", lambda m: (mask or "*")[0] * len(m.group(0)), out, flags=re.I)
    return out


@tool("text", ex={"text": "phone 9876543210, email asha@example.com, card 4111 1111 1111 1111"}, keys="redact personal information mask privacy pii")
def redact_personal_info(text: str) -> str:
    """Mask emails, phone numbers, card numbers, Aadhaar-like and PAN-like numbers before sharing text."""
    t = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "[email]", text)
    t = re.sub(r"\b(?:\d[ -]?){13,19}\b", "[card number]", t)
    t = re.sub(r"\b\d{4}\s?\d{4}\s?\d{4}\b", "[12-digit number]", t)
    t = re.sub(r"\b[A-Z]{5}\d{4}[A-Z]\b", "[PAN]", t)
    return re.sub(r"(?:\+?\d{1,3}[\s-]?)?\b\d{5}[\s-]?\d{5}\b|\b\d{10}\b", "[phone]", t)


BRAILLE = dict(zip("abcdefghijklmnopqrstuvwxyz", "⠁⠃⠉⠙⠑⠋⠛⠓⠊⠚⠅⠇⠍⠝⠕⠏⠟⠗⠎⠞⠥⠧⠺⠭⠽⠵"))


@tool("encode", ex={"text": "hello 42"}, keys="braille convert blind dots")
def to_braille(text: str) -> str:
    """Text to Grade-1 Unicode braille (letters and digits)."""
    out = []
    for word in text.lower().split():
        w = ""
        prev_digit = False
        for c in word:
            if c.isdigit():
                if not prev_digit:
                    w += "⠼"
                w += BRAILLE["jabcdefghi"[int(c)]]
                prev_digit = True
            else:
                w += BRAILLE.get(c, c)
                prev_digit = False
        out.append(w)
    return " ".join(out)


# ---- data
@tool("data", ex={"text": "name,city\nAsha,Pune\nRavi,Delhi\nMeena,Pune", "column": "city"}, keys="csv unique values count group by column")
def csv_column_counts(text: str, column: str) -> list:
    """How often each value appears in a CSV column."""
    from collections import Counter
    from .t_data import read_csv
    rows = read_csv(text)
    if column not in rows[0]:
        raise ToolError(f"columns are: {', '.join(rows[0])}")
    i = rows[0].index(column)
    return [f"{v}: {n}" for v, n in Counter(r[i] for r in rows[1:] if i < len(r)).most_common(50)]


@tool("data", ex={"text": "| a | b |\n|---|---|\n| 1 | 2 |"}, keys="markdown table to csv convert")
def markdown_table_to_csv(text: str) -> str:
    """Markdown table to CSV."""
    rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in text.strip().splitlines() if l.strip().startswith("|")]
    rows = [r for r in rows if not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    return buf.getvalue()


@tool("data", ex={"text": "<shop><item price='10'>pen</item><item price='99'>bag</item></shop>", "path": ".//item"}, keys="xml xpath find elements query")
def xml_find(text: str, path: str) -> list:
    """Find elements in XML with an ElementTree path (like .//item or ./book/title)."""
    from xml.etree import ElementTree
    try:
        root = ElementTree.fromstring(text)
        found = root.findall(path)
    except (ElementTree.ParseError, SyntaxError) as e:
        raise ToolError(str(e))
    return [f"<{e.tag}{''.join(f' {k}={v!r}' for k, v in e.attrib.items())}> {(e.text or '').strip()}" for e in found[:100]]


@tool("data", ex={"text": "name,age,joined\nAsha,31,2024-01-05\nRavi,28,2025-03-10", "table": "people"}, keys="csv to sql insert create table")
def csv_to_sql(text: str, table: str) -> str:
    """CREATE TABLE and INSERT statements from CSV (types guessed)."""
    from .t_data import read_csv
    rows = read_csv(text)
    if len(rows) < 2:
        raise ToolError("need a header and data")
    head = [re.sub(r"\W+", "_", h.strip()).strip("_").lower() or f"col{i}" for i, h in enumerate(rows[0])]

    def kind(i):
        vals = [r[i] for r in rows[1:] if i < len(r) and r[i] != ""]
        if vals and all(re.fullmatch(r"-?\d+", v) for v in vals):
            return "INTEGER"
        if vals and all(re.fullmatch(r"-?\d*\.?\d+", v) for v in vals):
            return "REAL"
        return "TEXT"
    types = [kind(i) for i in range(len(head))]
    tname = re.sub(r"\W+", "_", table)
    out = [f"CREATE TABLE {tname} (\n  " + ",\n  ".join(f"{h} {t}" for h, t in zip(head, types)) + "\n);"]
    for r in rows[1:201]:
        vals = [("NULL" if i >= len(r) or r[i] == "" else r[i] if types[i] != "TEXT" else "'" + r[i].replace("'", "''") + "'") for i in range(len(head))]
        out.append(f"INSERT INTO {tname} ({', '.join(head)}) VALUES ({', '.join(vals)});")
    return "\n".join(out)


# ---- math
@tool("math", ex={"amount": 90000, "percents": [50, 30, 20]}, keys="split by percent shares budget 50 30 20")
def split_by_percent(amount: float, percents: list[float]) -> list:
    """Split an amount by percentages (e.g. a 50/30/20 budget)."""
    if abs(sum(percents) - 100) > 0.01:
        raise ToolError(f"percents add up to {fmt(sum(percents))}, not 100")
    return [f"{fmt(p)}%: {fmt(round(amount * p / 100, 2))}" for p in percents]


@tool("math", ex={"cgpa": 8.4}, keys="cgpa gpa percentage convert cbse grade")
def cgpa_to_percentage(cgpa: float, scale: Literal["cbse", "x10", "us_4"] = "cbse") -> str:
    """Convert CGPA to a percentage (CBSE: × 9.5; plain ×10; or US 4-point to an approximate %)."""
    if scale == "cbse":
        return f"{fmt(round(cgpa * 9.5, 2))}% (CBSE formula CGPA × 9.5; your university may use its own)."
    if scale == "x10":
        return f"{fmt(round(cgpa * 10, 2))}%"
    return f"About {fmt(round(cgpa / 4 * 100, 1))}% (rough; US schools don't use a fixed formula)."


@tool("math", ex={"n": 28}, keys="number properties even odd square perfect digits sum")
def number_properties(n: int) -> dict:
    """Interesting facts about a whole number: even/odd, prime, square, cube, perfect, digit sum, binary."""
    from .t_math import is_prime
    a = abs(n)
    divs = sum(d + (a // d if d * d != a and d != 1 else 0) for d in range(1, math.isqrt(a) + 1) if a % d == 0) if a > 1 else 0
    return {"parity": "even" if n % 2 == 0 else "odd", "prime": is_prime(n), "square": math.isqrt(a) ** 2 == a,
            "cube": round(a ** (1 / 3)) ** 3 == a, "perfect": a > 1 and divs == a, "digit_sum": sum(map(int, str(a))),
            "binary": bin(n), "roman": __import__("echo_desktop.toolbox.t_math", fromlist=["to_roman"]).to_roman(n) if 1 <= n <= 3999 else "n/a"}


# ---- money
@tool("money", ex={"principal": 1000000, "rate_a": 8.5, "years_a": 20, "rate_b": 8.9, "years_b": 15}, keys="compare two loans better offer")
def compare_loans(principal: float, rate_a: float, years_a: float, rate_b: float, years_b: float) -> str:
    """Compare two loan offers by EMI and total interest."""
    from .t_money import _emi, rs
    ea, eb = _emi(principal, rate_a, round(years_a * 12)), _emi(principal, rate_b, round(years_b * 12))
    ia, ib = ea * round(years_a * 12) - principal, eb * round(years_b * 12) - principal
    better = "A" if ia < ib else "B"
    return (f"A: EMI {rs(ea)}, interest {rs(ia)}. B: EMI {rs(eb)}, interest {rs(ib)}. "
            f"Offer {better} costs {rs(abs(ia - ib))} less interest overall (check fees too).")


@tool("money", ex={"current": 60000, "hike_percent": 12}, keys="salary hike increment raise new salary")
def salary_hike(current: float, hike_percent: float) -> str:
    """New salary after a percentage hike."""
    from .t_money import rs
    return f"New salary {rs(current * (1 + hike_percent / 100))} (up {rs(current * hike_percent / 100)})."


@tool("money", ex={"last_basic_plus_da": 50000, "years": 8}, keys="gratuity india calculate retirement")
def gratuity(last_basic_plus_da: float, years: float) -> str:
    """Gratuity under India's Payment of Gratuity Act (15 days' pay per year of service; 5+ years usually needed)."""
    from .t_money import rs
    y = math.floor(years) + (1 if years % 1 >= 0.5 else 0)
    note = "" if years >= 5 else " Note: usually payable only after 5 years of service."
    counted = f"{y} years" + (f" ({fmt(round(years, 2))} rounded: 6 months or more counts as a year)" if y != years else "")
    return (f"Gratuity {rs(last_basic_plus_da * 15 / 26 * y)} = {rs(last_basic_plus_da)} × 15/26 × {counted}, under the "
            f"Payment of Gratuity Act (tax-free up to ₹20 lakh).{note}")


@tool("money", ex={"goal": 300000, "monthly": 15000, "annual_return": 7}, keys="savings goal how long months to save")
def savings_goal_time(goal: float, monthly: float, annual_return: float = 0, already_saved: float = 0) -> str:
    """How many months to reach a savings goal."""
    r = annual_return / 12 / 100
    bal, m = already_saved, 0
    while bal < goal and m < 1200:
        bal = bal * (1 + r) + monthly
        m += 1
    if m >= 1200:
        raise ToolError("that would take over 100 years")
    return f"{many(m, 'month')} ({many(m // 12, 'year')} {many(m % 12, 'month')})."


# ---- system
@tool("system", keys="screen off display turn off monitor sleep")
def turn_off_screen() -> str:
    """Turn off the screen (move the mouse or press a key to wake it)."""
    import ctypes
    ctypes.windll.user32.PostMessageW(0xFFFF, 0x0112, 0xF170, 2)
    return "Screen off. Move the mouse to wake it."


@tool("system", ask=True, keys="sleep pc computer suspend")
def sleep_pc(ctx=None) -> str:
    """Put the PC to sleep. Asks first."""
    import ctypes
    from .t_files import confirm
    confirm(ctx, "Put the PC to sleep?", "Unsaved work stays open; the PC wakes with the power button or keyboard.")
    ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
    return "Going to sleep."


@tool("system", ex={}, keys="wifi networks nearby available scan")
def wifi_networks_nearby() -> list:
    """Wi-Fi networks in range, with signal strength."""
    from .t_system import run
    text = run(["netsh", "wlan", "show", "networks", "mode=bssid"])
    out, name = [], None
    for line in text.splitlines():
        m = re.match(r"\s*SSID \d+ : (.*)", line)
        if m:
            name = m.group(1).strip() or "(hidden)"
        s = re.match(r"\s*Signal\s*: (\d+)%", line)
        if s and name:
            out.append((int(s.group(1)), name))
            name = None
    return [f"{n}: {s}%" for s, n in sorted(set(out), reverse=True)] or ["No networks found (is Wi-Fi on?)."]


@tool("system", ex={}, keys="default browser which")
def default_browser() -> str:
    """Which web browser opens links by default."""
    from .t_system import reg
    import winreg
    pid = reg(r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice", "ProgId", winreg.HKEY_CURRENT_USER) or ""
    names = {"chrome": "Google Chrome", "msedge": "Microsoft Edge", "firefox": "Firefox", "brave": "Brave", "opera": "Opera"}
    return next((v for k, v in names.items() if k in pid.lower()), pid or "unknown")


@tool("system", ex={}, keys="temp files temporary cleanup space junk")
def temp_files_size() -> str:
    """How much space your temporary files use (clean them in Settings → Storage)."""
    import os
    from pathlib import Path
    from .t_files import human
    total = n = 0
    for dirpath, _, files in os.walk(os.environ.get("TEMP", "")):
        for f in files:
            try:
                total += (Path(dirpath) / f).stat().st_size
                n += 1
            except OSError:
                pass
    return f"Temporary files: {human(total)} in {many(n, 'file')}. Say “open storage settings” to clean up."


# ---- web
@tool("web", net=True, ex={"base": "USD", "target": "INR", "days": 30}, keys="currency history trend exchange rate past")
def currency_history(base: str, target: str, days: int = 30) -> str:
    """How an exchange rate moved over recent days."""
    from datetime import date, timedelta
    from .t_web import J
    start = date.today() - timedelta(days=max(2, min(days, 365)))
    d = J(f"https://api.frankfurter.app/{start}..?from={base.upper()}&to={target.upper()}", 3600)
    rates = [(k, v[target.upper()]) for k, v in sorted((d.get("rates") or {}).items())]
    if not rates:
        raise ToolError("no history for that pair")
    first, last = rates[0][1], rates[-1][1]
    lo, hi = min(r for _, r in rates), max(r for _, r in rates)
    return (f"{base.upper()}→{target.upper()}: {fmt(first, 4)} on {rates[0][0]} → {fmt(last, 4)} on {rates[-1][0]} "
            f"({(last - first) / first * 100:+.2f}%); range {fmt(lo, 4)}–{fmt(hi, 4)}.")


@tool("web", net=True, ex={"query": "http client", "count": 5}, keys="rust crates search library")
def crates_search(query: str, count: int = 8) -> list:
    """Search crates.io for Rust libraries."""
    from .t_web import J, Q
    d = J(f"https://crates.io/api/v1/crates?per_page={max(1, min(count, 25))}&q=" + Q(query), 600)
    return [f"{c['name']} {c.get('max_stable_version') or c.get('max_version')} — {(c.get('description') or '')[:90]}" for c in d.get("crates", [])]


# ---- dev
def _ts_type(v, name, out, py=False):
    if isinstance(v, bool):
        return "bool" if py else "boolean"
    if isinstance(v, int):
        return "int" if py else "number"
    if isinstance(v, float):
        return "float" if py else "number"
    if isinstance(v, str):
        return "str" if py else "string"
    if v is None:
        return "None" if py else "null"
    if isinstance(v, list):
        inner = _ts_type(v[0], name.rstrip("s") or name, out, py) if v else ("Any" if py else "unknown")
        return f"list[{inner}]" if py else f"{inner}[]"
    cname = "".join(p.capitalize() for p in re.findall(r"[A-Za-z0-9]+", name)) or "Item"
    fields = [(k, _ts_type(x, k, out, py)) for k, x in v.items()]
    if py:
        out.append(f"@dataclass\nclass {cname}:\n" + "\n".join(f"    {re.sub(r'\\W', '_', k)}: {t}" for k, t in fields))
    else:
        out.append(f"export interface {cname} {{\n" + "\n".join(f"  {k if re.fullmatch(r'[A-Za-z_$][\\w$]*', k) else json.dumps(k)}: {t};" for k, t in fields) + "\n}")
    return cname


@tool("dev", ex={"text": "{\"id\": 1, \"name\": \"Asha\", \"tags\": [\"a\"], \"address\": {\"city\": \"Pune\"}}", "name": "User"}, keys="json to typescript interface types")
def json_to_typescript(text: str, name: str = "Root") -> str:
    """TypeScript interfaces from an example JSON object."""
    from .t_data import load_json
    out = []
    _ts_type(load_json(text), name, out)
    return "\n\n".join(out)


@tool("dev", ex={"text": "{\"id\": 1, \"name\": \"Asha\", \"address\": {\"city\": \"Pune\"}}", "name": "User"}, keys="json to python dataclass class types")
def json_to_dataclass(text: str, name: str = "Root") -> str:
    """Python dataclasses from an example JSON object."""
    from .t_data import load_json
    out = []
    _ts_type(load_json(text), name, out, py=True)
    return "from dataclasses import dataclass\nfrom typing import Any\n\n\n" + "\n\n\n".join(out)


@tool("dev", ex={"text": "DB_HOST=localhost\nAPI_KEY=abc123\n# comment"}, keys="env example template dotenv share")
def env_example(text: str) -> str:
    """A shareable .env.example from a .env (same names, values removed)."""
    out = []
    for line in text.splitlines():
        m = re.match(r"\s*(export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        out.append(f"{m.group(2)}=" if m and not line.strip().startswith("#") else line)
    return "\n".join(out)
