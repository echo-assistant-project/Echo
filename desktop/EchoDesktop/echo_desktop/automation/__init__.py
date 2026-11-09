"""Echo's automation engine: the 20 actions from the "1,000 automation ideas" list, on any data source.

Sources: ~50 built-in probes of this PC (probes.py) plus generic ones — a CSV/JSON/text file, a folder, a web page,
a JSON API, an RSS feed, or any of Echo's toolbox tools. Every source works with every action:

  report / summary · alert on a threshold · compare with last time · before-and-after diff · export CSV ·
  searchable history · detect unusual changes · scheduled health check · validate against a policy · notify ·
  dashboard · archive with retention · dry run · trends with an estimate · diagnostic bundle ·
  correlate with Windows events · apply a profile (asks first) · stale/missing data check · recovery checklist

History lives in %APPDATA%\\EchoDesktop\\automation; reports, CSVs, dashboards and bundles go to Downloads\\Echo reports
(new files only, never overwriting). Watches run on a schedule inside the Echo app and notify you.
"""
from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import os
import re
import threading
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from .probes import PROBES, Probe
from ..words import many

APP = Path(os.environ.get("APPDATA", str(Path.home()))) / "EchoDesktop" / "automation"
HISTORY = APP / "history"
GENERIC = {"file": "a CSV, JSON or text file (path)", "folder": "a folder's files (path)", "url": "a web page: status, speed, title, content fingerprint (url)",
           "json_api": "a public JSON API (url, optional path like items.0)", "rss": "an RSS/Atom feed (url)", "tool": "any Echo toolbox tool (tool, args)"}


class AutomationError(Exception):
    pass


def reports_dir() -> Path:
    from ..internet import downloads_dir
    d = downloads_dir() / "Echo reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_file(stem: str, ext: str) -> Path:
    base = reports_dir() / f"{re.sub(r'[^A-Za-z0-9_-]+', '_', stem)[:60]}_{datetime.now():%Y-%m-%d_%H%M%S}"
    p, i = base.with_suffix(ext), 1
    while p.exists():
        p = Path(f"{base}_{i}{ext}")
        i += 1
    return p


# ------------------------------------------------------------------------------------------------ sources
@dataclass
class Data:
    sid: str            # stable id for history: source + its parameters
    title: str
    records: list
    key: str
    numbers: tuple
    attention: tuple
    area: str = ""


def source_id(source: str, params: dict) -> str:
    clean = {k: v for k, v in sorted((params or {}).items()) if not k.startswith("_")}
    if not clean:
        return source
    return f"{source}-{hashlib.sha1(json.dumps(clean, sort_keys=True, default=str).encode()).hexdigest()[:8]}"


def _flat(d, prefix="") -> dict:
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(_flat(v, f"{prefix}{k}." ) if isinstance(v, dict) else {f"{prefix}{k}": json.dumps(v)[:300] if isinstance(v, list) else v})
    else:
        out[prefix.rstrip(".") or "value"] = d
    return out


def read(source: str, params: Optional[dict] = None, ctx=None) -> Data:
    params = dict(params or {})
    if ctx is not None and getattr(ctx, "workspaces", None):
        params.setdefault("_workspaces", ctx.workspaces)
    sid = source_id(source, params)
    if source in PROBES:
        p = PROBES[source]
        try:
            recs = p.read(params)
        except Exception as e:
            raise AutomationError(f"couldn't read {p.title}: {e}")
        return Data(sid, p.title, recs, p.key, p.numbers, p.attention, p.area)
    if source == "file":
        from ..toolbox.t_files import resolve, read_text
        path = resolve(str(params.get("path", "")))
        text = read_text(path, 20_000_000)
        if path.suffix.lower() == ".json":
            d = json.loads(text)
            rows = d if isinstance(d, list) else next((v for v in d.values() if isinstance(v, list)), [d]) if isinstance(d, dict) else [d]
            recs = [_flat(r) for r in rows]
        elif path.suffix.lower() in (".csv", ".tsv"):
            from ..toolbox.t_data import csv_to_json
            recs = csv_to_json(text)
        else:
            recs = [{"line": i, "text": l} for i, l in enumerate(text.splitlines(), 1) if l.strip()]
        key = params.get("key") or (next(iter(recs[0]), "line") if recs else "line")
        nums = tuple(k for k, v in (recs[0].items() if recs else []) if isinstance(v, (int, float)) and not isinstance(v, bool))
        return Data(sid, f"File {path.name}", recs, key, nums, ())
    if source == "folder":
        from ..toolbox.t_files import resolve, walk_files
        root = resolve(str(params.get("path", "downloads")))
        pat = str(params.get("pattern", "*")).lower()
        import fnmatch
        recs = []
        for f in walk_files(root, 100_000):
            if fnmatch.fnmatch(f.name.lower(), pat):
                st = f.stat()
                recs.append({"name": str(f.relative_to(root)), "size_kb": round(st.st_size / 1024, 1), "type": f.suffix.lower(),
                             "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")})
        return Data(sid, f"Folder {root}", recs, "name", ("size_kb",), ())
    if source == "url":
        from .. import internet
        recs = []
        for u in [x.strip() for x in str(params.get("url", "")).split(",") if x.strip()]:
            try:
                r = internet.request(u, max_bytes=2_000_000)
                title, text, _ = internet.readable(r.text(), r.url) if "html" in r.content_type else ("", r.text(), [])
                section = str(params.get("contains", ""))
                watched = text if not section else "\n".join(l for l in text.splitlines() if section.lower() in l.lower())
                price = re.findall(r"(?:₹|Rs\.?|INR|\$|€|£)\s?([\d,]+(?:\.\d+)?)", watched)
                recs.append({"name": u, "status": r.status, "ms": round(r.elapsed * 1000), "title": title[:120], "length": len(text),
                             "fingerprint": hashlib.sha1(watched.encode()).hexdigest()[:12],
                             "first_price": float(price[0].replace(",", "")) if price else None, "excerpt": watched[:200]})
            except internet.NetError as e:
                recs.append({"name": u, "status": None, "ms": None, "title": "", "length": 0, "fingerprint": "", "first_price": None, "excerpt": str(e)})
        return Data(sid, "Web pages", recs, "name", ("ms", "length", "first_price"), ("status != 200",))
    if source == "json_api":
        from .. import internet
        d = internet.get_json(str(params.get("url", "")), 0)
        if params.get("path"):
            from ..toolbox.t_data import _path_get
            d = _path_get(d, str(params["path"]))
        rows = d if isinstance(d, list) else [d]
        recs = [_flat(r) for r in rows[:5000]]
        key = params.get("key") or (next(iter(recs[0]), "value") if recs else "value")
        nums = tuple(k for k, v in (recs[0].items() if recs else []) if isinstance(v, (int, float)) and not isinstance(v, bool))
        return Data(sid, f"API {params.get('url')}", recs, key, nums, ())
    if source == "rss":
        from .. import internet
        items = internet.parse_rss_items(internet.request(str(params.get("url", ""))).text(), 100)
        return Data(sid, f"Feed {params.get('url')}", [{"name": t, "link": l, "summary": d[:200]} for t, l, d in items], "name", (), ())
    if source == "tool":
        from .. import toolbox
        name = str(params.get("tool", ""))
        t = toolbox.load().get(name)
        if t is None or t.ask:
            raise AutomationError("use a read-only toolbox tool here (tools that change things can't be automated)")
        out = toolbox.call(name, params.get("args") or {}, ctx)
        try:
            d = json.loads(out)
            rows = d if isinstance(d, list) else [d]
            recs = [_flat(r) if isinstance(r, dict) else {"value": r} for r in rows]
        except ValueError:
            recs = [{"value": out[:2000]}]
        key = next(iter(recs[0]), "value") if recs else "value"
        return Data(sid, f"Tool {name}", recs, key, tuple(k for k, v in (recs[0].items() if recs else []) if isinstance(v, (int, float)) and not isinstance(v, bool)), ())
    raise AutomationError(f"unknown source {source}. Built-in: {', '.join(sorted(PROBES))}; generic: {', '.join(GENERIC)}")


# ------------------------------------------------------------------------------------------------ history
def save(data: Data) -> Path:
    d = HISTORY / data.sid
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{datetime.now():%Y%m%d-%H%M%S-%f}.json"            # microseconds: two quick readings never overwrite each other
    p.write_text(json.dumps({"title": data.title, "key": data.key, "time": datetime.now().isoformat(timespec="seconds"), "records": data.records},
                            ensure_ascii=False, default=str), encoding="utf-8")
    return p


def snapshots(sid: str) -> list:
    d = HISTORY / sid
    return sorted(d.glob("*.json")) if d.is_dir() else []


def load_snapshot(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def snap_time(p: Path) -> datetime:
    return datetime.strptime(p.stem[:15], "%Y%m%d-%H%M%S")


# ------------------------------------------------------------------------------------------------ rules
_RULE = re.compile(r"\s*([\w .()%-]+?)\s*(==|!=|<=|>=|<|>|contains|not contains|older than)\s*(.+?)\s*$")


def _val(s: str):
    s = s.strip().strip("'\"")
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    if s.lower() in ("none", "null", "empty"):
        return None
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return s


def _test(rec: dict, field: str, op: str, want) -> bool:
    v = rec.get(field)
    if op == "contains":
        return str(want).lower() in str(v).lower()
    if op == "not contains":
        return str(want).lower() not in str(v).lower()
    if op == "older than":
        try:
            t = datetime.fromisoformat(str(v)[:19])
        except ValueError:
            return False
        return (datetime.now() - t).days > float(str(want).split()[0])
    if op in ("==", "!="):
        same = (str(v).lower() == str(want).lower()) if not isinstance(want, (int, float)) or isinstance(want, bool) else _num(v) == want
        return same if op == "==" else not same
    a, b = _num(v), want if isinstance(want, (int, float)) else _num(want)
    if a is None or b is None:
        return False
    return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]


def _num(v):
    try:
        return float(str(v).replace(",", "").rstrip("%"))
    except (TypeError, ValueError):
        return None


def check(records: list, rule: str) -> list:
    """Records matching a rule like 'free_percent < 10', 'status != OK and start == Automatic', 'count > 0' (count = how many records)."""
    parts = re.split(r"\s+and\s+", rule.strip(), flags=re.I)
    if len(parts) == 1 and re.match(r"\s*count\s*(==|!=|<=|>=|<|>)", parts[0]) and not any("count" in r for r in records[:1]):
        m = _RULE.match(parts[0])
        return [{"count": len(records)}] if m and _test({"count": len(records)}, "count", m.group(2), _val(m.group(3))) else []
    hits = []
    for r in records:
        ok = True
        for part in parts:
            m = _RULE.match(part)
            if not m:
                raise AutomationError(f"can't read the rule “{part}” (use field < number, field == text, field contains text…)")
            if not _test(r, m.group(1).strip(), m.group(2), _val(m.group(3))):
                ok = False
                break
        if ok:
            hits.append(r)
    return hits


def describe(r: dict, key: str) -> str:
    head = r.get(key)
    rest = ", ".join(f"{k} {v}" for k, v in r.items() if k != key and v not in (None, "") and not isinstance(v, (list, dict)))[:220]
    return f"{head}: {rest}" if head is not None else rest


# ------------------------------------------------------------------------------------------------ the 20 actions
def summary(data: Data, limit: int = 12) -> str:
    recs = data.records
    lines = [f"{data.title}: {len(recs)} item{'s' if len(recs) != 1 else ''}."]
    for f in data.numbers:
        vals = [_num(r.get(f)) for r in recs if _num(r.get(f)) is not None]
        if vals:
            lines.append(f"{f}: min {min(vals):g}, max {max(vals):g}, average {sum(vals) / len(vals):.4g}.")
    flagged = []
    for rule in data.attention:
        try:
            flagged += [(rule, r) for r in check(recs, rule)]
        except AutomationError:
            pass
    if flagged:
        lines.append(f"Needs attention ({len(flagged)}): " + "; ".join(describe(r, data.key) for _, r in flagged[:6]) + ("…" if len(flagged) > 6 else ""))
    lines += ["• " + describe(r, data.key) for r in recs[:limit]]
    if len(recs) > limit:
        lines.append(f"…and {len(recs) - limit} more.")
    return "\n".join(lines)


def compare(old: list, new: list, key: str) -> dict:
    o = {str(r.get(key)): r for r in old}
    n = {str(r.get(key)): r for r in new}
    changed = []
    for k in o.keys() & n.keys():
        diffs = {f: (o[k].get(f), n[k].get(f)) for f in set(o[k]) | set(n[k]) if o[k].get(f) != n[k].get(f)}
        if diffs:
            changed.append((k, diffs))
    return {"added": [n[k] for k in n.keys() - o.keys()], "removed": [o[k] for k in o.keys() - n.keys()], "changed": changed}


def compare_text(c: dict, key: str) -> str:
    if not (c["added"] or c["removed"] or c["changed"]):
        return "No changes."
    out = []
    if c["added"]:
        out.append(f"New ({len(c['added'])}): " + "; ".join(describe(r, key) for r in c["added"][:10]))
    if c["removed"]:
        out.append(f"Gone ({len(c['removed'])}): " + "; ".join(str(r.get(key)) for r in c["removed"][:10]))
    if c["changed"]:
        out.append(f"Changed ({len(c['changed'])}): " + "; ".join(f"{k} — " + ", ".join(f"{f} {a} → {b}" for f, (a, b) in list(d.items())[:4])
                                                                  for k, d in c["changed"][:10]))
    return "\n".join(out)


def unusual(c: dict, numbers: tuple, jump_percent: float = 25) -> list:
    """Changes worth explaining: big number jumps, plus anything added/removed."""
    notes = []
    for k, d in c["changed"]:
        for f, (a, b) in d.items():
            na, nb = _num(a), _num(b)
            if f in numbers and na not in (None, 0) and nb is not None and abs(nb - na) / abs(na) * 100 >= jump_percent:
                notes.append(f"{k}: {f} jumped {na:g} → {nb:g} ({(nb - na) / abs(na) * 100:+.0f}%)")
            elif f not in numbers:
                notes.append(f"{k}: {f} changed from {a} to {b}")
    notes += [f"new: {r}" for r in [list(x.values())[0] for x in c["added"][:10]]]
    notes += [f"gone: {r}" for r in [list(x.values())[0] for x in c["removed"][:10]]]
    return notes


LIKELY = [(r"driver|version", "a driver or app update installed in the background (Windows Update or the app's own updater)"),
          (r"status|state|health", "a device/service stopped, failed or was reconfigured — see correlated Windows events"),
          (r"free|size|space", "large files were downloaded, created or deleted, or a sync tool (OneDrive) changed what's on disk"),
          (r"signal|ms|latency", "network conditions changed: distance from the router, interference, or ISP congestion"),
          (r"enabled|allowed|admin", "a setting or permission was changed by you, an installer, or a policy")]


def likely_cause(notes: list) -> str:
    text = " ".join(notes).lower()
    causes = [c for pat, c in LIKELY if re.search(pat, text)]
    return ("Likely cause: " + "; or ".join(causes[:2]) + ".") if causes else "No obvious cause from the data; check what was installed or changed around that time."


def trend(sid: str, field: str, item: Optional[str] = None, threshold: Optional[float] = None, key: str = None) -> str:
    pts = []
    for p in snapshots(sid)[-500:]:
        s = load_snapshot(p)
        k = key or s.get("key")
        vals = [_num(r.get(field)) for r in s["records"] if (item is None or str(r.get(k)) == str(item)) and _num(r.get(field)) is not None]
        if vals:
            pts.append((snap_time(p), sum(vals) / len(vals) if item is None and len(vals) > 1 else vals[0]))
    if len(pts) < 2:
        return f"Not enough history yet ({len(pts)} reading{'s' if len(pts) != 1 else ''}). Take snapshots over time (or set a watch) and ask again."
    t0 = pts[0][0]
    xs = [(t - t0).total_seconds() / 86400 for t, _ in pts]
    ys = [v for _, v in pts]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs) or 1e-9
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    out = f"{field}{' for ' + str(item) if item else ''}: {ys[0]:g} → {ys[-1]:g} over {xs[-1]:.1f} days ({n} readings), trend {slope:+.3g} per day."
    if threshold is not None and slope != 0:
        days = (threshold - ys[-1]) / slope
        if days <= 0:
            out += f" It's moving away from {threshold:g}."
        elif days > 3650:
            out += f" At this rate it won't reach {threshold:g} for over ten years."
        else:
            out += f" At this rate it reaches {threshold:g} in about {many(round(days), 'day')} ({(datetime.now() + timedelta(days=days)):%d %b %Y})."
    return out


def export_csv(data: Data) -> Path:
    p = new_file(data.title, ".csv")
    cols = list(dict.fromkeys(k for r in data.records for k in r))
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, cols, extrasaction="ignore")
        w.writeheader()
        for r in data.records:
            w.writerow({k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in r.items()})
    return p


def search_history(sid: Optional[str], text: str, limit: int = 40) -> list:
    out = []
    dirs = [HISTORY / sid] if sid else (sorted(HISTORY.iterdir()) if HISTORY.is_dir() else [])
    for d in dirs:
        for p in sorted(d.glob("*.json"), reverse=True):
            s = load_snapshot(p)
            for r in s["records"]:
                if text.lower() in json.dumps(r, ensure_ascii=False, default=str).lower():
                    out.append(f"{snap_time(p):%Y-%m-%d %H:%M} [{d.name}] {describe(r, s.get('key'))}")
                    if len(out) >= limit:
                        return out
    return out


def archive(sid: Optional[str], keep_days: int) -> str:
    cutoff = datetime.now() - timedelta(days=keep_days)
    dirs = [HISTORY / sid] if sid else (list(HISTORY.iterdir()) if HISTORY.is_dir() else [])
    moved = 0
    for d in dirs:
        old = [p for p in d.glob("*.json") if snap_time(p) < cutoff]
        if not old:
            continue
        z = d / f"archive-{datetime.now():%Y%m%d}.zip"
        with zipfile.ZipFile(z, "a", zipfile.ZIP_DEFLATED) as zf:
            for p in old:
                zf.write(p, p.name)
                p.unlink()
                moved += 1
    return f"Archived {moved} old snapshots (older than {keep_days} days) into zip files; recent history kept."


def stale(records: list, max_age_days: Optional[float] = None) -> list:
    out = []
    for r in records:
        empty = [k for k, v in r.items() if v in (None, "", [], {})]
        if empty:
            out.append(f"{describe(r, next(iter(r)))} — missing {', '.join(empty[:6])}")
        if max_age_days:
            for k, v in r.items():
                if isinstance(v, str) and re.match(r"\d{4}-\d{2}-\d{2}", v):
                    try:
                        age = (datetime.now() - datetime.fromisoformat(v[:19])).days
                    except ValueError:
                        continue
                    if age > max_age_days:
                        out.append(f"{describe(r, next(iter(r)))} — {k} is {many(age, 'day')} old")
    return out


def correlate(times: list, window_minutes: int = 30) -> list:
    """Windows System/Application warnings and errors within ±window of the given times."""
    from .probes import ps
    out = []
    for t in times[:5]:
        a, b = (t - timedelta(minutes=window_minutes)).strftime("%Y-%m-%dT%H:%M:%S"), (t + timedelta(minutes=window_minutes)).strftime("%Y-%m-%dT%H:%M:%S")
        rows = ps("Get-WinEvent -FilterHashtable @{LogName='System','Application'; Level=1,2,3; StartTime=[datetime]'%s'; EndTime=[datetime]'%s'} -MaxEvents 15 | "
                  "Select-Object @{n='time';e={$_.TimeCreated.ToString('s')}}, ProviderName, Id, @{n='m';e={($_.Message -split \"`n\")[0]}} | ConvertTo-Json -Compress" % (a, b))
        out += [f"{r.get('time')} {r.get('ProviderName')} #{r.get('Id')}: {(r.get('m') or '')[:140]}" for r in rows]
    return out


def dashboard(datas: list) -> Path:
    """One HTML page (opens in the browser from disk; no server) with a table per source and sparklines from history."""
    css = ("body{font-family:Segoe UI,system-ui,sans-serif;margin:24px;background:#0b1320;color:#e6f1fa}h1{font-size:22px}h2{font-size:17px;margin-top:28px}"
           "table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid #22324a;padding:4px 8px;text-align:left}"
           ".warn{color:#ffb454}.muted{color:#9eb2c3}svg{vertical-align:middle}")
    parts = [f"<!doctype html><meta charset=utf-8><title>Echo dashboard</title><style>{css}</style><h1>Echo dashboard</h1>"
             f"<p class=muted>{datetime.now():%A %d %B %Y, %H:%M}</p>"]
    for d in datas:
        flagged = set()
        for rule in d.attention:
            try:
                flagged |= {str(r.get(d.key)) for r in check(d.records, rule)}
            except AutomationError:
                pass
        cols = list(dict.fromkeys(k for r in d.records[:200] for k in r))[:8]
        parts.append(f"<h2>{html.escape(d.title)} <span class=muted>({len(d.records)})</span></h2>")
        for f in d.numbers[:2]:
            series = []
            for p in snapshots(d.sid)[-40:]:
                vals = [_num(r.get(f)) for r in load_snapshot(p)["records"] if _num(r.get(f)) is not None]
                if vals:
                    series.append(sum(vals) / len(vals))
            if len(series) > 1:
                lo, hi = min(series), max(series)
                pts = " ".join(f"{i * 120 / (len(series) - 1):.1f},{24 - (v - lo) / ((hi - lo) or 1) * 22:.1f}" for i, v in enumerate(series))
                parts.append(f"<p class=muted>{html.escape(f)} trend <svg width=120 height=26><polyline fill=none stroke=#42d9ff stroke-width=2 points='{pts}'/></svg> "
                             f"{series[0]:.4g} → {series[-1]:.4g}</p>")
        parts.append("<table><tr>" + "".join(f"<th>{html.escape(c)}</th>" for c in cols) + "</tr>")
        for r in d.records[:200]:
            cls = " class=warn" if str(r.get(d.key)) in flagged else ""
            parts.append(f"<tr{cls}>" + "".join(f"<td>{html.escape(str(r.get(c, ''))[:120])}</td>" for c in cols) + "</tr>")
        parts.append("</table>")
    p = new_file("dashboard", ".html")
    p.write_text("".join(parts), encoding="utf-8")
    return p


def bundle(datas: list) -> Path:
    p = new_file("diagnostic_bundle", ".zip")
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", f"Echo diagnostic bundle, {datetime.now():%Y-%m-%d %H:%M}. One JSON + summary per source. Secrets are not included.")
        for d in datas:
            zf.writestr(f"{d.sid}.json", json.dumps(d.records, ensure_ascii=False, indent=1, default=str))
            zf.writestr(f"{d.sid}.txt", summary(d, 100))
    return p


CHECKLISTS = {
    "Operating-system diagnostics": ["Save a snapshot now (so you can compare later).", "Look at Windows errors from the last day (source event_errors).",
                                     "Restart once if a restart is pending.", "Run Windows Update, then restart.",
                                     "If a device misbehaves: Device Manager → right-click → Update driver / Roll back driver.",
                                     "Run 'sfc /scannow' in an administrator terminal to repair system files.", "If it started after a change, use a restore point."],
    "Storage management": ["Check free space (source volumes) and disk health (source disk_health).", "Empty the Recycle Bin and temp files (Settings → Storage → Cleanup).",
                           "Move big videos/photos to OneDrive or an external drive.", "If a disk isn't Healthy: back up now, then replace it."],
    "Network diagnostics": ["Check the Wi-Fi signal and latency.", "Restart the router and the PC.", "Run Settings → Network → Network troubleshooter.",
                            "Forget and rejoin the Wi-Fi network.", "Try a wired connection or another device to see if it's the ISP."],
    "Security posture checks": ["Make sure Defender real-time protection is on and definitions are fresh.", "Run a quick scan.",
                                "Check the firewall is on for all network types.", "Review startup apps and listening ports for anything unknown.",
                                "Change passwords for important accounts from a clean device if you suspect compromise."],
    "Backup and recovery": ["Confirm OneDrive (or File History) is running.", "Open a backed-up file to prove the backup is readable.",
                            "Keep one copy offline (external drive).", "Write down how you'd restore, and test it once."],
}


def checklist(area: str, subject: str) -> list:
    steps = CHECKLISTS.get(area) or ["Save a snapshot of the current state.", f"Compare {subject} with the last good snapshot.",
                                     "Correlate the time it broke with Windows events and recent installs.", "Undo the most recent change, one at a time.",
                                     "Restart the app/device/service involved.", "Check the vendor's status page or docs.", "If nothing works, collect a diagnostic bundle and ask for help."]
    return [f"{i}. {s}" for i, s in enumerate(steps, 1)]


# ------------------------------------------------------------------------------------------------ profiles (apply settings; asks first)
def _settings_now() -> dict:
    from .probes import _a11y, _input
    from ..toolbox.t_system import power_plan
    a = {r["name"]: r["value"] for r in _a11y({})}
    i = {r["name"]: r["value"] for r in _input({})}
    return {"dark_mode": a.get("dark mode (apps)") == "on", "pointer_size": a.get("pointer size"), "sticky_keys": a.get("sticky keys") == "on",
            "double_click_ms": i.get("double-click time (ms)"), "power_plan": power_plan().removeprefix("Power plan: ").rstrip(".")}


PROFILE_KEYS = {"dark_mode": "true/false", "pointer_size": "32–256", "sticky_keys": "true/false", "double_click_ms": "200–900",
                "power_plan": "Balanced / High performance / Power saver (as listed by Windows)", "brightness": "0–100"}


def profile_plan(profile: dict) -> list:
    now = _settings_now()
    plan = []
    for k, v in profile.items():
        if k not in PROFILE_KEYS:
            raise AutomationError(f"profiles can set: {', '.join(PROFILE_KEYS)}")
        if k == "brightness" or str(now.get(k)).lower() != str(v).lower():
            plan.append((k, now.get(k), v))
    return plan


def profile_apply(plan: list) -> list:
    import ctypes
    import winreg
    from .. import pcctl
    done = []
    for k, _, v in plan:
        if k == "dark_mode":
            pcctl.system("DARK_ON" if str(v).lower() in ("true", "1", "on") else "DARK_OFF", {}, lambda *_: True)
        elif k == "pointer_size":
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors", 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "CursorBaseSize", 0, winreg.REG_DWORD, max(32, min(int(v), 256)))
            ctypes.windll.user32.SystemParametersInfoW(0x0057, 0, None, 3)
        elif k == "sticky_keys":
            pcctl.ease("STICKY_ON" if str(v).lower() in ("true", "1", "on") else "STICKY_OFF")
        elif k == "double_click_ms":
            ctypes.windll.user32.SystemParametersInfoW(0x0020, max(200, min(int(v), 900)), None, 3)
        elif k == "brightness":
            pcctl._brightness(max(0, min(int(v), 100)))
        elif k == "power_plan":
            from ..toolbox.t_system import run
            listing = run(["powercfg", "/list"])
            m = re.search(r"GUID: ([0-9a-f-]{36})\s+\(" + re.escape(str(v)) + r"\)", listing, re.I)
            if not m:
                raise AutomationError(f"no power plan called {v}; plans: " + ", ".join(re.findall(r"\((.+?)\)", listing)))
            run(["powercfg", "/setactive", m.group(1)])
        done.append(f"{k} → {v}")
    return done


# ------------------------------------------------------------------------------------------------ watches & scheduler
WATCHES = APP / "watches.json"
_lock = threading.Lock()


def watches() -> list:
    try:
        return json.loads(WATCHES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def save_watches(ws: list) -> None:
    APP.mkdir(parents=True, exist_ok=True)
    tmp = WATCHES.with_suffix(".tmp")
    tmp.write_text(json.dumps(ws, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, WATCHES)


def due(w: dict, now: datetime) -> bool:
    last = datetime.fromisoformat(w["last_run"]) if w.get("last_run") else None
    if w.get("daily_at"):
        h, m = map(int, w["daily_at"].split(":"))
        slot = now.replace(hour=h, minute=m, second=0, microsecond=0)
        return now >= slot and (last is None or last < slot)
    every = max(5, int(w.get("every_minutes") or 60))
    return last is None or now - last >= timedelta(minutes=every)


def run_watch(w: dict, ctx=None) -> tuple:
    """(needs_attention, message). Kinds: check (rules), changes, report, trend, tool."""
    data = read(w["source"], w.get("params") or {}, ctx)
    prev = snapshots(data.sid)
    save(data)
    kind = w.get("kind", "check")
    if kind == "changes":
        if not prev:
            return False, f"{data.title}: first reading saved."
        c = compare(load_snapshot(prev[-1])["records"], data.records, data.key)
        notes = unusual(c, data.numbers, float(w.get("jump_percent", 25)))
        return bool(notes), (f"{data.title} changed: " + "; ".join(notes[:6]) + ". " + likely_cause(notes)) if notes else f"{data.title}: no changes."
    if kind == "report":
        return True, summary(data)
    if kind == "trend":
        return False, trend(data.sid, w["field"], w.get("item"), w.get("threshold"))
    rules = w.get("rules") or list(data.attention)
    hits = []
    for rule in rules:
        hits += [(rule, r) for r in check(data.records, rule)]
    if hits:
        return True, f"{w.get('name') or data.title}: " + "; ".join(f"{describe(r, data.key)} ({rule})" for rule, r in hits[:6])
    return False, f"{w.get('name') or data.title}: all OK."


class Scheduler:
    """Runs due watches every 30 s inside the Echo app; notifies only when something needs attention (or for reports)."""

    def __init__(self, notify: Callable[[str], None], ctx=None):
        self.notify, self.ctx = notify, ctx
        self._stop = threading.Event()
        self.thread = None

    def start(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self._loop, daemon=True, name="echo-automation")
            self.thread.start()

    def stop(self):
        self._stop.set()

    def tick(self, now: Optional[datetime] = None) -> list:
        now = now or datetime.now()
        results = []
        with _lock:
            ws = watches()
        for w in ws:
            if not w.get("enabled", True) or not due(w, now):
                continue
            try:
                attention, msg = run_watch(w, self.ctx)
            except Exception as e:
                attention, msg = True, f"Watch “{w.get('name')}” failed: {e}"
            w["last_run"], w["last_result"] = now.isoformat(timespec="seconds"), msg[:500]
            results.append((w, attention, msg))
            if attention or w.get("always_notify"):
                try:
                    self.notify("⏰ " + msg)
                except Exception:
                    pass
        if results:
            with _lock:
                latest = {w["id"]: w for w, _, _ in results}
                save_watches([latest.get(x["id"], x) for x in watches()])
        return results

    def _loop(self):
        while not self._stop.wait(30):
            try:
                self.tick()
            except Exception:
                pass
