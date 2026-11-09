"""Data formats: JSON, CSV, XML, TOML, INI, URLs, query strings, colours, IP networks, versions, schedules."""
from __future__ import annotations

import colorsys
import configparser
import csv
import io
import ipaddress
import json
import mimetypes
import re
import urllib.parse
from datetime import datetime, timedelta
from typing import Literal
from xml.dom import minidom
from xml.etree import ElementTree

from . import ToolError, fmt, tool
from ..words import many

C = "data"


def load_json(text: str):
    try:
        return json.loads(text)
    except ValueError as e:
        raise ToolError(f"not valid JSON: {e}")


@tool(C, ex={"text": "{\"a\": [1, 2,]}"}, keys="json valid check lint")
def json_validate(text: str) -> str:
    """Is this valid JSON? Points at the error if not."""
    try:
        d = json.loads(text)
        kind = type(d).__name__.replace("dict", "object").replace("list", "array")
        return f"Valid JSON ({kind}{f' with {len(d)} items' if isinstance(d, (dict, list)) else ''})."
    except ValueError as e:
        return f"Invalid JSON: {e}"


@tool(C, ex={"text": "{\"b\":1,\"a\":{\"c\":[1,2]}}", "sort_keys": True}, keys="json pretty print format beautify indent")
def json_format(text: str, indent: int = 2, sort_keys: bool = False) -> str:
    """Pretty-print JSON."""
    return json.dumps(load_json(text), indent=max(0, min(indent, 8)), sort_keys=sort_keys, ensure_ascii=False)


@tool(C, ex={"text": "{\n  \"a\": 1\n}"}, keys="json minify compact one line")
def json_minify(text: str) -> str:
    """Minify JSON to one line."""
    return json.dumps(load_json(text), separators=(",", ":"), ensure_ascii=False)


def _path_get(data, path: str):
    cur = data
    for part in re.findall(r"[^.\[\]]+|\[\d+\]", path):
        if part.startswith("["):
            cur = cur[int(part[1:-1])]
        elif isinstance(cur, list) and part.isdigit():
            cur = cur[int(part)]
        elif isinstance(cur, list):
            cur = [x.get(part) if isinstance(x, dict) else None for x in cur]
        else:
            cur = cur[part]
    return cur


@tool(C, ex={"text": "{\"user\": {\"names\": [\"Asha\", \"Ravi\"]}}", "path": "user.names[1]"}, keys="json path query get value field extract")
def json_get(text: str, path: str) -> str:
    """Get a value from JSON by path, like user.names[1] or items.price (lists map over items)."""
    try:
        v = _path_get(load_json(text), path)
    except (KeyError, IndexError, TypeError):
        raise ToolError(f"nothing at {path}")
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, indent=1)


@tool(C, ex={"text": "{\"a\": 1, \"b\": {\"c\": 2}}"}, keys="json keys structure shape outline")
def json_structure(text: str) -> str:
    """Outline of a JSON document's structure (keys and types)."""
    out = []

    def walk(v, path, depth):
        if depth > 6 or len(out) > 200:
            return
        if isinstance(v, dict):
            out.append(f"{path or '$'}: object ({len(v)} keys)")
            for k, x in v.items():
                walk(x, f"{path}.{k}" if path else k, depth + 1)
        elif isinstance(v, list):
            out.append(f"{path or '$'}: array ({many(len(v), 'item')})")
            if v:
                walk(v[0], f"{path}[0]", depth + 1)
        else:
            out.append(f"{path}: {type(v).__name__}")
    walk(load_json(text), "", 0)
    return "\n".join(out)


@tool(C, ex={"text": "{\"a\": {\"b\": 1, \"c\": [2, 3]}}"}, keys="json flatten dotted keys")
def json_flatten(text: str) -> dict:
    """Flatten nested JSON into dotted keys."""
    out = {}

    def walk(v, p):
        if isinstance(v, dict) and v:
            for k, x in v.items():
                walk(x, f"{p}.{k}" if p else str(k))
        elif isinstance(v, list) and v:
            for i, x in enumerate(v):
                walk(x, f"{p}[{i}]")
        else:
            out[p or "$"] = v
    walk(load_json(text), "")
    return out


@tool(C, ex={"old": "{\"a\": 1, \"b\": 2}", "new": "{\"a\": 1, \"b\": 3, \"c\": 4}"}, keys="json compare diff changes")
def json_diff(old: str, new: str) -> list:
    """Differences between two JSON documents."""
    a, b = json_flatten(old), json_flatten(new)
    out = [f"- {k}: {json.dumps(a[k])}" for k in a if k not in b]
    out += [f"+ {k}: {json.dumps(b[k])}" for k in b if k not in a]
    out += [f"~ {k}: {json.dumps(a[k])} → {json.dumps(b[k])}" for k in a if k in b and a[k] != b[k]]
    return out or ["No differences."]


@tool(C, ex={"text": "[{\"name\": \"Asha\", \"age\": 31}, {\"name\": \"Ravi\", \"age\": 28}]"}, keys="json to csv convert table spreadsheet")
def json_to_csv(text: str) -> str:
    """JSON array of objects to CSV."""
    d = load_json(text)
    if isinstance(d, dict):
        d = [d]
    if not isinstance(d, list) or not all(isinstance(x, dict) for x in d):
        raise ToolError("need a JSON array of objects")
    cols = list(dict.fromkeys(k for x in d for k in x))
    buf = io.StringIO()
    w = csv.DictWriter(buf, cols, lineterminator="\n")
    w.writeheader()
    for x in d:
        w.writerow({k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in x.items()})
    return buf.getvalue()


def read_csv(text: str) -> list:
    try:
        dialect = csv.Sniffer().sniff(text[:2000], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    return [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]


@tool(C, ex={"text": "name,age\nAsha,31\nRavi,28"}, keys="csv to json convert")
def csv_to_json(text: str) -> list:
    """CSV (with a header row) to a JSON array of objects."""
    rows = read_csv(text)
    if len(rows) < 2:
        raise ToolError("need a header row and at least one data row")
    head = rows[0]

    def val(v):
        try:
            return int(v) if re.fullmatch(r"-?\d+", v) else float(v) if re.fullmatch(r"-?\d*\.\d+", v) else v
        except ValueError:
            return v
    return [{h: val(r[i]) if i < len(r) else "" for i, h in enumerate(head)} for r in rows[1:]]


@tool(C, ex={"text": "item,price,qty\npen,10,5\nbook,120,2\nbag,450,1"}, keys="csv statistics summary columns analyse spreadsheet")
def csv_summary(text: str) -> dict:
    """Rows, columns, and for number columns: sum, average, min and max."""
    rows = read_csv(text)
    if not rows:
        raise ToolError("no rows")
    head, body = rows[0], rows[1:]
    out = {"rows": len(body), "columns": head}
    for i, h in enumerate(head):
        vals = []
        for r in body:
            try:
                vals.append(float(r[i].replace(",", "")))
            except (ValueError, IndexError):
                pass
        if vals and len(vals) >= len(body) * 0.6:
            out[h] = {"sum": fmt(sum(vals)), "average": fmt(sum(vals) / len(vals), 4), "min": fmt(min(vals)), "max": fmt(max(vals))}
    return out


@tool(C, ex={"text": "name,city\nAsha,Pune\nRavi,Delhi\nMeena,Pune", "column": "city", "value": "Pune"}, keys="csv filter rows where")
def csv_filter(text: str, column: str, value: str, contains: bool = False) -> str:
    """Keep only CSV rows where a column equals (or contains) a value."""
    rows = read_csv(text)
    if column not in rows[0]:
        raise ToolError(f"columns are: {', '.join(rows[0])}")
    i = rows[0].index(column)
    keep = [r for r in rows[1:] if i < len(r) and ((value.lower() in r[i].lower()) if contains else r[i].strip().lower() == value.strip().lower())]
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows([rows[0]] + keep)
    return buf.getvalue()


@tool(C, ex={"text": "name,age\nAsha,31\nRavi,28", "column": "age"}, keys="csv sort order rows")
def csv_sort(text: str, column: str, descending: bool = False) -> str:
    """Sort CSV rows by a column (numbers sort as numbers)."""
    rows = read_csv(text)
    if column not in rows[0]:
        raise ToolError(f"columns are: {', '.join(rows[0])}")
    i = rows[0].index(column)

    def k(r):
        v = r[i] if i < len(r) else ""
        try:
            return (0, float(v.replace(",", "")), "")
        except ValueError:
            return (1, 0, v.lower())
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows([rows[0]] + sorted(rows[1:], key=k, reverse=descending))
    return buf.getvalue()


@tool(C, ex={"text": "name,age\nAsha,31"}, keys="csv markdown table")
def csv_to_markdown(text: str) -> str:
    """CSV to a Markdown table."""
    rows = read_csv(text)
    if not rows:
        raise ToolError("no rows")
    w = max(map(len, rows))
    rows = [r + [""] * (w - len(r)) for r in rows]
    return "\n".join(["| " + " | ".join(rows[0]) + " |", "|" + "---|" * w] + ["| " + " | ".join(r) + " |" for r in rows[1:]])


@tool(C, ex={"text": "[tool]\nname = \"echo\"\nversion = 2"}, keys="toml read parse convert pyproject")
def toml_to_json(text: str) -> dict:
    """Read TOML (pyproject.toml, Cargo.toml…) as JSON."""
    import tomllib
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ToolError(f"not valid TOML: {e}")


@tool(C, ex={"text": "[server]\nport = 8080\nhost = localhost"}, keys="ini config parse")
def ini_to_json(text: str) -> dict:
    """Read an INI/config file as JSON."""
    p = configparser.ConfigParser()
    if "\n" not in text.strip() and "=" in text:     # said aloud or pasted on one line: "[server] port = 8080 host = x"
        text = re.sub(r"\s*(\[[^\]]+\])\s*", r"\n\1\n", text)
        text = re.sub(r"\s+(?=[A-Za-z_][\w.-]*\s*[=:])", "\n", text).strip()
    try:
        p.read_string(text)
    except configparser.Error as e:
        raise ToolError(f"not valid INI: {e}")
    return {s: dict(p[s]) for s in p.sections()}


@tool(C, ex={"text": "DB_HOST=localhost\n# comment\nPORT=5432"}, keys="dotenv env file parse variables")
def env_file_to_json(text: str, hide_values: bool = True) -> dict:
    """Read a .env file's variable names (values hidden unless hide_values is false)."""
    out = {}
    for line in text.splitlines():
        m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", line)
        if m and not line.strip().startswith("#"):
            out[m.group(1)] = "•••" if hide_values else m.group(2).strip().strip("'\"")
    return out


def _xml_to(el):
    d = dict(el.attrib)
    kids = list(el)
    if kids:
        for k in kids:
            v = _xml_to(k)
            tag = k.tag.split("}")[-1]
            if tag in d:
                d[tag] = d[tag] if isinstance(d[tag], list) else [d[tag]]
                d[tag].append(v)
            else:
                d[tag] = v
    text = (el.text or "").strip()
    if text:
        if d:
            d["#text"] = text
        else:
            return text
    return d


@tool(C, ex={"text": "<book id=\"1\"><title>Wings of Fire</title><author>Kalam</author></book>"}, keys="xml to json convert parse")
def xml_to_json(text: str) -> dict:
    """XML to JSON."""
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as e:
        raise ToolError(f"not valid XML: {e}")
    return {root.tag.split("}")[-1]: _xml_to(root)}


@tool(C, ex={"text": "<a><b>1</b><c/></a>"}, keys="xml pretty print format indent")
def xml_format(text: str) -> str:
    """Pretty-print XML."""
    try:
        return minidom.parseString(text.encode()).toprettyxml(indent="  ").split("\n", 1)[1]
    except Exception as e:
        raise ToolError(f"not valid XML: {e}")


@tool(C, ex={"url": "https://shop.example.com:8443/cart/items?id=42&ref=mail#top"}, keys="url parse components query host path")
def url_parse(url: str) -> dict:
    """Split a URL into scheme, host, port, path, query parameters and fragment."""
    p = urllib.parse.urlsplit(url.strip())
    parts = {"scheme": p.scheme, "host": p.hostname, "port": p.port, "path": p.path, "query": dict(urllib.parse.parse_qsl(p.query)),
             "fragment": p.fragment, "username": p.username}
    return {k: v for k, v in parts.items() if v not in (None, "", {})}          # only the parts the URL has


@tool(C, ex={"base": "https://api.example.com/search", "params": {"q": "masala dosa", "page": 2}}, keys="url build query string parameters")
def url_build(base: str, params: dict) -> str:
    """Build a URL with query parameters (properly encoded)."""
    p = urllib.parse.urlsplit(base)
    q = dict(urllib.parse.parse_qsl(p.query)) | {k: str(v) for k, v in params.items()}
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(q), p.fragment))


@tool(C, ex={"query": "a=1&b=hello%20world&b=2"}, keys="query string parse decode parameters")
def query_string_parse(query: str) -> dict:
    """Parse a query string (repeated keys become lists)."""
    out = {}
    for k, v in urllib.parse.parse_qsl(query.lstrip("?"), keep_blank_values=True):
        out[k] = v if k not in out else (out[k] if isinstance(out[k], list) else [out[k]]) + [v]
    return out


@tool(C, ex={"url": "https://www.example.com/a/b?utm_source=x&id=7&fbclid=y"}, keys="clean url tracking utm remove")
def clean_url_tracking(url: str) -> str:
    """Remove tracking parameters (utm_, fbclid, gclid…) from a link."""
    p = urllib.parse.urlsplit(url.strip())
    keep = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True)
            if not re.match(r"utm_|fbclid$|gclid$|mc_|igshid$|si$|ref_src$|yclid$|_ga$", k)]
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(keep), p.fragment))


@tool(C, ex={"email": "asha.k@example.co.in"}, keys="email address valid check format")
def email_check(email: str) -> str:
    """Check an email address's format (not whether the mailbox exists)."""
    ok = re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+", email.strip())
    if not ok or ".." in email:
        return "Not a valid email address format."
    return "Valid format." + (" (Looks like a typo: did you mean gmail.com?)" if re.search(r"@g(m|n)ai?l\.(co|cm|con)$", email.lower()) else "")


@tool(C, ex={"value": "#1e90ff"}, keys="colour color hex rgb hsl convert")
def color_convert(value: str) -> dict:
    """Convert a colour between hex, RGB and HSL ('#1e90ff', 'rgb(30,144,255)', 'hsl(210,100%,56%)')."""
    v = value.strip().lower()
    if v.startswith("hsl"):
        h, s, l = [float(x) for x in re.findall(r"[\d.]+", v)[:3]]
        r, g, b = [round(c * 255) for c in colorsys.hls_to_rgb(h / 360, l / 100, s / 100)]
    elif v.startswith("rgb") or re.fullmatch(r"\d+[ ,]+\d+[ ,]+\d+", v):
        r, g, b = [int(float(x)) for x in re.findall(r"[\d.]+", v)[:3]]
    else:
        h = v.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if not re.fullmatch(r"[0-9a-f]{6}", h):
            raise ToolError("use #rrggbb, rgb(r,g,b) or hsl(h,s%,l%)")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    hh, ll, ss = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return {"hex": f"#{r:02x}{g:02x}{b:02x}", "rgb": f"rgb({r}, {g}, {b})", "hsl": f"hsl({round(hh * 360)}, {round(ss * 100)}%, {round(ll * 100)}%)"}


def _lum(hexv):
    rgb = [int(hexv[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


@tool(C, ex={"foreground": "#777777", "background": "#ffffff"}, keys="contrast ratio accessibility wcag readable colours")
def color_contrast(foreground: str, background: str) -> str:
    """WCAG contrast ratio of two colours and whether text is readable."""
    a, b = _lum(color_convert(foreground)["hex"]), _lum(color_convert(background)["hex"])
    ratio = (max(a, b) + 0.05) / (min(a, b) + 0.05)
    verdict = "passes AA and AAA" if ratio >= 7 else "passes AA (normal text)" if ratio >= 4.5 else "passes AA for large text only" if ratio >= 3 else "fails — hard to read"
    return f"Contrast {ratio:.2f}:1, {verdict}."


@tool(C, ex={"value": "#1e90ff"}, keys="palette colour scheme complementary harmony shades")
def color_palette(value: str) -> dict:
    """Matching colours: complementary, analogous, triadic, and lighter/darker shades."""
    hexv = color_convert(value)["hex"]
    r, g, b = (int(hexv[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, l, s = colorsys.rgb_to_hls(r, g, b)

    def mk(hh, ll=l):
        rr, gg, bb = colorsys.hls_to_rgb(hh % 1, max(0, min(ll, 1)), s)
        return f"#{round(rr * 255):02x}{round(gg * 255):02x}{round(bb * 255):02x}"
    return {"base": hexv, "complementary": mk(h + 0.5), "analogous": [mk(h - 1 / 12), mk(h + 1 / 12)],
            "triadic": [mk(h + 1 / 3), mk(h + 2 / 3)], "shades": [mk(h, l * f) for f in (0.4, 0.7)], "tints": [mk(h, l + (1 - l) * f) for f in (0.4, 0.7)]}


@tool(C, ex={"network": "192.168.1.0/24"}, keys="subnet cidr netmask hosts ip range calculator")
def subnet_info(network: str) -> str:
    """Subnet calculator: netmask, usable hosts, range, broadcast."""
    from ..devtools import subnet
    return subnet(network)


@tool(C, ex={"address": "10.0.5.20", "network": "10.0.0.0/16"}, keys="ip in subnet contains range belongs")
def ip_in_network(address: str, network: str) -> str:
    """Is an IP address inside a network range?"""
    try:
        inside = ipaddress.ip_address(address.strip()) in ipaddress.ip_network(network.strip(), strict=False)
    except ValueError as e:
        raise ToolError(str(e))
    return f"{address} is {'inside' if inside else 'outside'} {network}."


@tool(C, ex={"address": "172.16.4.1"}, keys="ip address type private public valid")
def ip_address_info(address: str) -> str:
    """What kind of IP address this is (private, public, loopback…)."""
    from ..devtools import ip_kind
    return ip_kind(address)


@tool(C, ex={"a": "1.2.10", "b": "1.10.0"}, keys="semver compare versions newer")
def version_compare(a: str, b: str) -> str:
    """Compare two version numbers."""
    from ..devtools import compare_versions
    return compare_versions(f"{a} and {b}")


@tool(C, ex={"version": "2.4.1", "part": "minor"}, keys="semver bump increment version release")
def version_bump(version: str, part: Literal["major", "minor", "patch"] = "patch") -> str:
    """Next version number (major/minor/patch bump)."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?", version.strip())
    if not m:
        raise ToolError("use a version like 2.4.1")
    a, b, c = map(int, m.groups())
    return {"major": f"{a + 1}.0.0", "minor": f"{a}.{b + 1}.0", "patch": f"{a}.{b}.{c + 1}"}[part]


@tool(C, ex={"schedule": "0 9 * * 1-5"}, keys="cron explain schedule crontab")
def cron_explain(schedule: str) -> str:
    """Explain a 5-part cron schedule in words."""
    from ..devtools import explain_cron
    return explain_cron(schedule)


def _cron_field(spec: str, low: int, high: int) -> set:
    out = set()
    for part in spec.split(","):
        step = 1
        if "/" in part:
            part, s = part.split("/")
            step = int(s)
        if part in ("*", ""):
            a, b = low, high
        elif "-" in part:
            a, b = map(int, part.split("-"))
        else:
            a = b = int(part)
        out.update(range(a, b + 1, step))
    return out


@tool(C, ex={"schedule": "30 9 * * 1", "count": 3}, keys="cron next run times when")
def cron_next_runs(schedule: str, count: int = 5) -> list:
    """The next times a cron schedule will run (local time)."""
    f = schedule.split()
    if len(f) != 5:
        raise ToolError("a cron schedule has 5 parts")
    mins, hrs, doms, mons = _cron_field(f[0], 0, 59), _cron_field(f[1], 0, 23), _cron_field(f[2], 1, 31), _cron_field(f[3], 1, 12)
    dows = {d % 7 for d in _cron_field(f[4], 0, 7)}
    start = datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=1)
    want = max(1, min(count, 20))
    times = sorted((h, m) for h in hrs for m in mins)
    out, day = [], start.date()
    for _ in range(366 * 30):               # day by day; 30 years covers 29 February and weekday combinations
        if day.month in mons:
            dom_ok, dow_ok = day.day in doms, (day.isoweekday() % 7) in dows
            if (dom_ok and dow_ok) if (f[2] == "*" or f[4] == "*") else (dom_ok or dow_ok):
                for h, m in times:
                    t = datetime(day.year, day.month, day.day, h, m)
                    if t >= start:
                        out.append(t.strftime("%a %d %b %Y %H:%M"))
                        if len(out) >= want:
                            return out
        day += timedelta(days=1)
    if not out:
        raise ToolError("that schedule never runs (for example 31 February)")
    return out


@tool(C, ex={"code": 429}, keys="http status code meaning error")
def http_status_meaning(code: int) -> str:
    """What an HTTP status code means."""
    from ..devtools import run
    return run("HTTP_CODE", {"n": str(code)}).text


@tool(C, ex={"port": 5432}, keys="port number service what runs")
def port_meaning(port: int) -> str:
    """What usually runs on a network port."""
    from ..devtools import run
    return run("PORT", {"n": str(port)}).text


@tool(C, ex={"mode": 644}, keys="chmod unix permissions explain")
def chmod_explain(mode: int) -> str:
    """Explain Unix file permissions like 755 or 644."""
    from ..devtools import chmod_words
    return chmod_words(str(mode))


@tool(C, ex={"owner": "rwx", "group": "rx", "others": "r"}, keys="chmod calculate number permissions")
def chmod_calculate(owner: str = "rw", group: str = "r", others: str = "r") -> str:
    """Permission letters (r, w, x) to a chmod number."""
    def d(s):
        return 4 * ("r" in s) + 2 * ("w" in s) + 1 * ("x" in s)
    return f"chmod {d(owner)}{d(group)}{d(others)}"


@tool(C, ex={"name": "report.pdf"}, keys="mime type content type file extension")
def mime_type(name: str) -> str:
    """MIME type for a file name or extension (and extensions for a MIME type like image/png)."""
    if "/" in name and "." not in name.split("/")[-1]:
        exts = mimetypes.guess_all_extensions(name.strip())
        return ", ".join(exts) or "unknown type"
    t, enc = mimetypes.guess_type(name if "." in name else "x." + name)
    return t or "unknown"


@tool(C, ex={"size_bytes": 1536000}, keys="file size human readable bytes kb mb")
def human_size(size_bytes: float) -> str:
    """Bytes to a readable size (KB, MB, GB)."""
    n = float(size_bytes)
    for unit in ("bytes", "KB", "MB", "GB", "TB", "PB"):
        if abs(n) < 1024 or unit == "PB":
            return f"{fmt(round(n, 2))} {unit}"
        n /= 1024


@tool(C, ex={"text": "{\"name\": \"Asha\", \"age\": 31, \"tags\": [\"a\"]}"}, keys="json schema infer generate")
def json_schema_from_example(text: str) -> dict:
    """Make a JSON Schema from an example JSON value."""
    def s(v):
        if isinstance(v, bool):
            return {"type": "boolean"}
        if isinstance(v, int):
            return {"type": "integer"}
        if isinstance(v, float):
            return {"type": "number"}
        if isinstance(v, str):
            return {"type": "string"}
        if v is None:
            return {"type": "null"}
        if isinstance(v, list):
            return {"type": "array", "items": s(v[0]) if v else {}}
        return {"type": "object", "properties": {k: s(x) for k, x in v.items()}, "required": list(v)}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", **s(load_json(text))}


@tool(C, ex={"sql": "select id,name from users where age>30 and city='Pune' order by name"}, keys="sql format pretty query")
def sql_format(sql: str) -> str:
    """Tidy an SQL query: keywords in capitals, one clause per line."""
    kws = ["select", "from", "where", "and", "or", "order by", "group by", "having", "limit", "offset", "join", "left join", "right join",
           "inner join", "on", "as", "insert into", "values", "update", "set", "delete from", "distinct", "count", "union", "desc", "asc", "in", "not", "null", "is", "like", "between"]
    out = sql.strip()
    for k in sorted(kws, key=len, reverse=True):
        out = re.sub(rf"(?<![\w'])({re.escape(k)})(?![\w'])", k.upper(), out, flags=re.I)
    out = re.sub(r"\s+(FROM|WHERE|GROUP BY|ORDER BY|HAVING|LIMIT|LEFT JOIN|RIGHT JOIN|INNER JOIN|JOIN|UNION|VALUES|SET)\b", r"\n\1", out)
    out = re.sub(r"\s+(AND|OR)\b", r"\n  \1", out)
    return re.sub(r",(?=\S)", ", ", out)
