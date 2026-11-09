"""Automation tools: watch, compare, trend, report and dashboard any data source; run the 1,000 automation ideas by
number; plus everyday PA helpers (fetch, morning briefing, PC check-up, what changed, page/price watches)."""
from __future__ import annotations

import json
import os
from typing import Literal

from . import ToolError, tool
from ..words import many

C = "automation"


def A():
    from .. import automation
    return automation


def _data(source: str, params, ctx):
    try:
        return A().read(source, params or {}, ctx)
    except A().AutomationError as e:
        raise ToolError(str(e))


def _wrap(fn):
    try:
        return fn()
    except Exception as e:
        if isinstance(e, ToolError):
            raise
        raise ToolError(str(e))


@tool(C, ex={}, keys="automation sources what can echo monitor watch data probes")
def automation_sources() -> list:
    """Data sources Echo can read, watch and compare (built-in PC probes, plus files, folders, pages, APIs, feeds, tools)."""
    a = A()
    return [f"{p.name}: {p.title} [{p.area}]" for p in sorted(a.PROBES.values(), key=lambda p: p.area)] + [f"{k}: {v}" for k, v in a.GENERIC.items()]


@tool(C, ex={"source": "volumes"}, keys="read summary report state now status overview monitor")
def automation_report(source: str, params: dict = None, save_snapshot: bool = True, ctx=None) -> str:
    """Read a source now and summarise it (and keep the reading in history). params for generic sources: path / url / tool."""
    d = _data(source, params, ctx)
    if save_snapshot:
        A().save(d)
    return A().summary(d)


@tool(C, ex={"source": "startup_apps"}, keys="compare previous last time changed diff before after")
def automation_compare(source: str, params: dict = None, against: Literal["last", "first"] = "last", ctx=None) -> str:
    """Compare a source now with its last (or first) saved reading: what was added, removed or changed."""
    a = A()
    d = _data(source, params, ctx)
    prev = a.snapshots(d.sid)
    a.save(d)
    if not prev:
        return "First reading saved. Ask again later to see what changed."
    base = a.load_snapshot(prev[0] if against == "first" else prev[-1])
    return f"Since {base['time']}:\n" + a.compare_text(a.compare(base["records"], d.records, d.key), d.key)


@tool(C, ex={"source": "volumes"}, keys="unusual changes anomaly explain cause what happened")
def automation_unusual_changes(source: str, params: dict = None, jump_percent: float = 25, ctx=None) -> str:
    """Unusual changes since the last reading (big jumps, new or missing items) with the likely cause."""
    a = A()
    d = _data(source, params, ctx)
    prev = a.snapshots(d.sid)
    a.save(d)
    if not prev:
        return "First reading saved; ask again later."
    notes = a.unusual(a.compare(a.load_snapshot(prev[-1])["records"], d.records, d.key), d.numbers, jump_percent)
    return ("; ".join(notes[:12]) + "\n" + a.likely_cause(notes)) if notes else "Nothing unusual."


@tool(C, ex={"source": "volumes", "rule": "free_percent < 50"}, keys="threshold alert check rule condition find items where")
def automation_check(source: str, rule: str, params: dict = None, ctx=None) -> str:
    """Items in a source matching a rule like 'free_percent < 10', 'status != OK and start == Automatic', 'count > 0'."""
    d = _data(source, params, ctx)
    hits = _wrap(lambda: A().check(d.records, rule))
    return (f"{len(hits)} match: " + "; ".join(A().describe(h, d.key) for h in hits[:15])) if hits else "Nothing matches."


@tool(C, ex={"source": "firewall", "rules": ["enabled == False"]}, keys="validate policy compliance rules pass fail audit")
def automation_validate(source: str, rules: list[str], params: dict = None, ctx=None) -> str:
    """Check a source against a policy (each rule describes a problem; ✓ means no item has it)."""
    d = _data(source, params, ctx)
    out = []
    for r in rules:
        bad = _wrap(lambda: A().check(d.records, r))
        out.append(f"{'✗' if bad else '✓'} {r}" + (": " + "; ".join(A().describe(x, d.key) for x in bad[:4]) if bad else ""))
    return "\n".join(out)


@tool(C, keys="export csv spreadsheet report file timestamped")
def automation_export_csv(source: str, params: dict = None, ctx=None) -> str:
    """Export a source to a timestamped CSV in Downloads\\Echo reports."""
    d = _data(source, params, ctx)
    return f"Saved {many(len(d.records), 'row')} to {A().export_csv(d)}."


@tool(C, ex={"text": "chrome"}, keys="history search past readings when did")
def automation_history_search(text: str, source: str = "", params: dict = None) -> list:
    """Search every saved reading (or one source's) for some text — 'when was this app installed / this device seen'."""
    sid = A().source_id(source, params or {}) if source else None
    return A().search_history(sid, text) or ["Nothing in history matches."]


@tool(C, ex={"source": "volumes", "field": "free_percent", "threshold": 10}, keys="trend estimate forecast when will run out growth")
def automation_trend(source: str, field: str, item: str = "", threshold: float = None, params: dict = None, ctx=None) -> str:
    """Trend of a number over saved readings, and when it would reach a threshold."""
    a = A()
    d = _data(source, params, ctx)
    a.save(d)
    return a.trend(d.sid, field, item or None, threshold, d.key)


@tool(C, keys="dashboard panel overview html page")
def automation_dashboard(sources: list[str], ctx=None) -> str:
    """Make and open an HTML dashboard (a file, no server) for several sources, with trend lines from history."""
    a = A()
    ds = [_data(s, {}, ctx) for s in sources[:12]]
    for d in ds:
        a.save(d)
    p = a.dashboard(ds)
    os.startfile(str(p))
    return f"Opened {p}."


@tool(C, keys="diagnostic bundle zip support collect logs")
def automation_bundle(sources: list[str], ctx=None) -> str:
    """Collect several sources into one diagnostic zip (Downloads\\Echo reports) to share with support."""
    return f"Saved {A().bundle([_data(s, {}, ctx) for s in sources[:20]])}."


@tool(C, keys="archive retention old records cleanup history")
def automation_archive(keep_days: int = 30, source: str = "") -> str:
    """Zip up saved readings older than N days (all sources or one)."""
    return A().archive(A().source_id(source, {}) if source else None, keep_days)


@tool(C, ex={"source": "updates", "max_age_days": 60}, keys="stale missing data empty old values quality")
def automation_stale_data(source: str, max_age_days: float = 90, params: dict = None, ctx=None) -> str:
    """Missing values and dates older than N days in a source."""
    found = A().stale(_data(source, params, ctx).records, max_age_days)
    return ("\n".join(found[:40])) if found else "No missing or stale values."


@tool(C, ex={"minutes_ago": 60}, keys="correlate windows events errors around time what happened when")
def automation_events_around(minutes_ago: float = 0, window_minutes: int = 30) -> list:
    """Windows warnings and errors around a moment (minutes ago), to explain a change."""
    from datetime import datetime, timedelta
    return A().correlate([datetime.now() - timedelta(minutes=minutes_ago)], window_minutes) or ["No warnings or errors in that window."]


@tool(C, ex={"area": "Network diagnostics", "problem": "slow wifi"}, keys="recovery checklist fix steps troubleshoot failure")
def recovery_checklist(area: str, problem: str) -> list:
    """Step-by-step recovery checklist for a kind of failure."""
    return A().checklist(area, problem)


@tool(C, ex={"profile": {"dark_mode": True, "pointer_size": 64}}, keys="profile preview dry run settings what would change")
def settings_profile_preview(profile: dict) -> str:
    """Dry run: what a settings profile would change (dark_mode, pointer_size, sticky_keys, double_click_ms, power_plan, brightness)."""
    plan = _wrap(lambda: A().profile_plan(profile))
    return "Would change: " + "; ".join(f"{k}: {a} → {b}" for k, a, b in plan) if plan else "Nothing would change."


@tool(C, ask=True, keys="apply settings profile preset switch mode")
def settings_profile_apply(profile: dict, ctx=None) -> str:
    """Apply a settings profile (e.g. {'dark_mode': true, 'power_plan': 'Power saver'}). Shows the changes and asks first."""
    from .t_files import confirm
    plan = _wrap(lambda: A().profile_plan(profile))
    if not plan:
        return "Already set like that."
    confirm(ctx, "Apply these settings?", "\n".join(f"{k}: {a} → {b}" for k, a, b in plan))
    return "Applied: " + ", ".join(A().profile_apply(plan))


# ---- watches -------------------------------------------------------------------------------------------------------
@tool(C, ex=None, keys="watch monitor schedule every check notify alert when automatically")
def watch_create(name: str, source: str, kind: Literal["check", "changes", "report", "trend"] = "check", rules: list[str] = None,
                 every_minutes: int = 60, daily_at: str = "", params: dict = None, field: str = "", threshold: float = None) -> str:
    """Watch a source on a schedule (every N minutes or daily at HH:MM). check = tell me when a rule matches; changes = tell me
    what changed; report = send a summary; trend = keep readings for trends. Runs inside the Echo app."""
    from ..automation.ideas import add_watch, when
    if source not in A().PROBES and source not in A().GENERIC:
        raise ToolError("unknown source; see automation_sources")
    if daily_at and not __import__("re").fullmatch(r"\d{1,2}:\d{2}", daily_at):
        raise ToolError("daily_at looks like 08:00")
    extra = {"field": field} if field else {}
    if threshold is not None:
        extra["threshold"] = threshold
    w = add_watch(name, source, params or {}, kind, max(5, every_minutes), daily_at, rules or [], always_notify=kind == "report", **extra)
    return f"Watching “{name}” {when(w)} (id {w['id']})."


@tool(C, ex={}, keys="watches list scheduled monitors active")
def watch_list() -> list:
    """All watches with their schedule and last result."""
    from ..automation.ideas import when
    ws = A().watches()
    return [f"{w['id']} {'✓' if w.get('enabled', True) else '⏸'} {w['name']} — {w['source']} {w['kind']} {when(w)}; last: {(w.get('last_result') or 'not run yet')[:120]}"
            for w in ws] or ["No watches yet."]


@tool(C, keys="watch remove delete stop monitoring")
def watch_remove(watch_id: str) -> str:
    """Stop and delete a watch."""
    ws = A().watches()
    keep = [w for w in ws if w["id"] != watch_id.strip()]
    if len(keep) == len(ws):
        raise ToolError("no watch with that id")
    A().save_watches(keep)
    return "Watch removed."


@tool(C, keys="watch run now test check immediately")
def watch_run_now(watch_id: str, ctx=None) -> str:
    """Run a watch right now and show its result."""
    w = next((w for w in A().watches() if w["id"] == watch_id.strip()), None)
    if not w:
        raise ToolError("no watch with that id")
    attention, msg = A().run_watch(w, ctx)
    return ("⚠ " if attention else "") + msg


# ---- the 1,000 ideas -----------------------------------------------------------------------------------------------
@tool(C, ex={"query": "disk space low"}, keys="automation ideas find search idea list number")
def idea_find(query: str, limit: int = 10) -> list:
    """Find ideas in the 1,000-idea automation list by words."""
    from ..automation import ideas
    return [f"#{i['n']} [{i['area']}] {i['idea']} — source {i['source'] or 'n/a'} ({i['how']})" for i in ideas.find(query, limit)] or ["No idea matches."]


@tool(C, ex={"number": 245}, keys="idea show details number")
def idea_show(number: int) -> dict:
    """Details of idea #N: area, action, subject and which data it uses."""
    from ..automation import ideas
    return _wrap(lambda: ideas.get(number))


@tool(C, keys="idea run do execute number automation")
def idea_run(number: int, params: dict = None, ctx=None) -> str:
    """Do idea #N from the 1,000-idea list (101–1100). params: path/url/tool for your own data; rule(s), field, threshold,
    every_minutes, at (HH:MM), profile, keep_days as the idea needs."""
    from ..automation import ideas
    return _wrap(lambda: ideas.run(number, params or {}, ctx))


@tool(C, ex={}, keys="ideas coverage how many automation list status")
def idea_coverage() -> str:
    """How the 1,000 ideas are covered: built-in data, related data, your own data, or not on Windows."""
    from collections import Counter
    from ..automation import ideas
    c = Counter(i["how"] for i in ideas.ideas())
    return (f"{len(ideas.ideas())} ideas, all 20 kinds of action supported. Data: {c['built-in']} read directly by Echo, {c['related']} use the closest "
            f"related PC data, {c['generic']} work on your own file/folder/web page/API, {c.get('not on this PC (needs Linux or macOS)', 0)} need Linux or macOS.")


# ---- everyday PA helpers ----------------------------------------------------------------------------------------------
@tool("web", net=True, ex={"url": "https://example.com", "max_length": 800}, keys="fetch url page get read website content markdown")
def fetch(url: str, max_length: int = 5000, start_index: int = 0, raw: bool = False) -> str:
    """Fetch a URL and return its readable text (or raw HTML/JSON with raw=true). Long pages: use start_index to read on."""
    from .. import internet
    r = internet.request(url, max_bytes=3_000_000)
    if raw or "html" not in r.content_type:
        text = r.text()
        if "json" in r.content_type:
            try:
                text = json.dumps(json.loads(text), indent=1, ensure_ascii=False)
            except ValueError:
                pass
    else:
        title, body, _ = internet.readable(r.text(), r.url)
        text = (f"# {title}\n\n" if title else "") + body
    n = max(100, min(max_length, 20000))
    chunk = text[start_index:start_index + n]
    more = len(text) - (start_index + len(chunk))
    return f"[{r.url} — HTTP {r.status}]\n{chunk}" + (f"\n\n…{more} more characters; call again with start_index={start_index + len(chunk)}" if more > 0 else "")


@tool(C, net=True, ex={"city": "Hyderabad"}, keys="morning briefing daily summary today weather news reminders agenda")
def daily_briefing(city: str = "", topics: list[str] = None, ctx=None) -> str:
    """One morning briefing: date, weather, headlines, timers, lists and anything on the PC that needs attention."""
    from datetime import datetime
    from .. import internet
    parts = [datetime.now().strftime("Good %s! It's %%A %%d %%B." % ("morning" if datetime.now().hour < 12 else "afternoon" if datetime.now().hour < 17 else "evening"))]
    try:
        parts.append(internet.info("TODAY", {"city": city}).text)
    except Exception as e:
        parts.append(f"(Weather unavailable: {e})")
    for t in (topics or ["top"])[:3]:
        try:
            parts.append(internet.info("NEWS" if t == "top" else "NEWS_TOPIC", {"topic": t}).text)
        except Exception:
            pass
    timers = getattr(ctx, "timers", None)
    if timers:
        parts.append(timers())
    lists = getattr(ctx, "lists", None)
    if lists is not None and lists.lists:
        parts.append("Your lists: " + ", ".join(f"{k} ({len(v)})" for k, v in lists.lists.items()) + ".")
    issues = _attention(["volumes", "battery", "pending_reboot", "defender"])
    parts.append(("PC: " + "; ".join(issues)) if issues else "Your PC looks healthy.")
    return "\n\n".join(parts)


def _attention(sources) -> list:
    a = A()
    out = []
    for s in sources:
        try:
            d = a.read(s, {})
        except Exception:
            continue
        for rule in d.attention:
            try:
                out += [f"{d.title}: {a.describe(r, d.key)}" for r in a.check(d.records, rule)][:3]
            except Exception:
                pass
    return out


@tool(C, ex={}, keys="pc checkup health check computer problems scan everything ok")
def pc_checkup(ctx=None) -> str:
    """Full PC check-up: storage, disk health, Windows errors, device problems, crashes, pending restart, Defender, firewall, battery, memory."""
    srcs = ["volumes", "disk_health", "device_problems", "app_crashes", "pending_reboot", "defender", "firewall", "security_settings", "battery", "cpu_memory"]
    issues = _attention(srcs)
    return ("Things to look at:\n• " + "\n• ".join(issues[:25])) if issues else f"All {len(srcs)} checks look fine: storage, disks, devices, crashes, restarts, protection, battery and memory."


@tool(C, ex={}, keys="what changed on my pc since last time new apps startup changes")
def what_changed(ctx=None) -> str:
    """What changed on this PC since the last check: installed apps, startup apps, updates, drivers… (first run saves a baseline)."""
    a = A()
    out = []
    for s in ("installed_apps", "startup_apps", "updates", "listening_ports", "accounts", "browsers", "app_permissions"):
        try:
            d = a.read(s, {})
        except Exception:
            continue
        prev = a.snapshots(d.sid)
        a.save(d)
        if prev:
            t = a.compare_text(a.compare(a.load_snapshot(prev[-1])["records"], d.records, d.key), d.key)
            if t != "No changes.":
                out.append(f"{d.title}:\n{t}")
    return "\n\n".join(out) if out else "No changes since the last check (or this was the first check, now saved as the baseline)."


@tool(C, net=True, ex=None, keys="watch web page changes notify update monitor site content")
def watch_web_page(url: str, contains: str = "", every_minutes: int = 120) -> str:
    """Tell me when a web page changes (optionally only the lines containing some words)."""
    params = {"url": url}
    if contains:
        params["contains"] = contains
    return watch_create(f"Page changes: {url}", "url", "changes", None, every_minutes, "", params)


@tool(C, net=True, ex=None, keys="price drop alert watch product cheaper")
def price_alert(url: str, below: float, every_minutes: int = 360) -> str:
    """Tell me when the first price shown on a product page drops below an amount."""
    return watch_create(f"Price below {below}: {url}", "url", "check", [f"first_price < {below}"], every_minutes, "", {"url": url})


@tool(C, ex=None, keys="schedule tool run every routine automatic daily repeat")
def schedule_tool(tool_name: str, args: dict = None, daily_at: str = "08:00", every_minutes: int = 0) -> str:
    """Run any read-only Echo tool on a schedule and send me the result (e.g. weather_forecast daily at 07:30)."""
    from . import load
    t = load().get(tool_name)
    if t is None or t.ask:
        raise ToolError("choose a read-only tool (tools that change things can't run unattended)")
    return watch_create(f"Scheduled {tool_name}", "tool", "report", None, every_minutes or 1440, "" if every_minutes else daily_at,
                        {"tool": tool_name, "args": args or {}})
