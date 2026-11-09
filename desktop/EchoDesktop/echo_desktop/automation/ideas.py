"""Run any of the 1,000 automation ideas (#101–#1100) by number: each is an action on a data source."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from . import (GENERIC, AutomationError, archive, bundle, check, checklist, compare, compare_text, correlate, dashboard, describe,
               export_csv, likely_cause, load_snapshot, profile_apply, profile_plan, read, save, save_watches, search_history,
               snap_time, snapshots, stale, summary, trend, unusual, watches)
from .probes import PROBES
from ..words import many

_ideas = None


def ideas() -> list:
    global _ideas
    if _ideas is None:
        _ideas = json.loads((Path(__file__).with_name("ideas.json")).read_text(encoding="utf-8"))
    return _ideas


def get(n: int) -> dict:
    for i in ideas():
        if i["n"] == n:
            return i
    raise AutomationError("ideas are numbered 101 to 1100")


def find(query: str, limit: int = 10) -> list:
    words = {w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 2}
    scored = []
    for i in ideas():
        hay = (i["idea"] + " " + (i["area"] or "")).lower()
        s = sum(w in hay for w in words)
        if s:
            scored.append((s, i))
    scored.sort(key=lambda x: (-x[0], x[1]["n"]))
    return [i for _, i in scored[:limit]]


def add_watch(name: str, source: str, params: dict, kind: str, every_minutes: int = 60, daily_at: str = "", rules=None, **extra) -> dict:
    w = {"id": uuid.uuid4().hex[:8], "name": name, "source": source, "params": {k: v for k, v in (params or {}).items() if not k.startswith("_")},
         "kind": kind, "every_minutes": every_minutes, "daily_at": daily_at, "rules": list(rules or []), "enabled": True,
         "created": datetime.now().isoformat(timespec="seconds"), **extra}
    ws = watches()
    ws.append(w)
    save_watches(ws)
    return w


def when(w: dict) -> str:
    return f"daily at {w['daily_at']}" if w.get("daily_at") else f"every {w['every_minutes']} minutes"


def run(n: int, params: dict = None, ctx=None) -> str:
    i = get(n)
    params = dict(params or {})
    src, how, act, subject = params.pop("source", None) or i["source"], i["how"], i["action"], i["subject"]
    head = f"Idea #{n} ({i['area']}): {i['idea']}\n"
    if src is None:
        return head + "This one needs Linux or macOS, so it can't run on this Windows PC."
    if src in GENERIC and not any(k in params for k in ("path", "url", "tool")):
        need = "url" if src in ("url", "json_api", "rss") else "tool" if src == "tool" else "path"
        return head + (f"This works on your own data: point it at {GENERIC[src]}. Run it again with {need}=…"
                       + (" (e.g. a CSV export of the records, or a JSON API URL)" if need == "path" else "") + ".")
    note = ""
    if how == "related" and src in PROBES:
        note = f"(Closest data Echo can read without admin rights: {PROBES[src].title}. It doesn't measure “{subject}” exactly.)\n"
    data = read(src, params, ctx)
    prev = snapshots(data.sid)
    out = ""
    if act in ("daily_report", "summary"):
        save(data)
        out = summary(data)
        if act == "daily_report" and params.get("schedule", True):
            w = add_watch(f"Daily report: {subject}", src, params, "report", daily_at=str(params.get("at", "08:00")), always_notify=True)
            out += f"\n\nScheduled: this report runs {when(w)} (watch {w['id']})."
    elif act in ("alert", "notify", "health_check"):
        rules = params.get("rules") or ([params["rule"]] if params.get("rule") else list(PROBES[src].attention) if src in PROBES else [])
        if not rules:
            return head + note + "Give a rule, e.g. rule=\"free_percent < 15\" or rule=\"status != OK\". Fields: " + ", ".join(list(data.records[0])[:12] if data.records else [])
        save(data)
        hits = [(r, x) for r in rules for x in check(data.records, r)]
        out = ("Right now: " + ("; ".join(f"{describe(x, data.key)} ({r})" for r, x in hits[:8]) if hits else "all OK") + ".")
        w = add_watch(f"{act.replace('_', ' ').title()}: {subject}", src, params, "check", int(params.get("every_minutes", 360 if act == "health_check" else 60)), rules=rules)
        out += f"\nWatching {when(w)}; you'll be told when it needs attention (watch {w['id']})."
    elif act in ("compare", "diff", "unusual", "correlate", "history"):
        save(data)
        if not prev:
            out = "First reading saved. Run it again later (or after the change) to compare."
            if act == "history":
                out = "History started: every reading is kept so you can search it later. " + summary(data, 5)
        else:
            base = load_snapshot(prev[0] if act == "diff" and params.get("against") == "first" else prev[-1])
            c = compare(base["records"], data.records, data.key)
            out = f"Compared with {base['time']}:\n" + compare_text(c, data.key)
            if act == "unusual":
                notes = unusual(c, data.numbers, float(params.get("jump_percent", 25)))
                out = (f"Unusual since {base['time']}: " + "; ".join(notes[:10]) + "\n" + likely_cause(notes)) if notes else f"Nothing unusual since {base['time']}."
            if act == "correlate":
                t = snap_time(prev[-1])
                ev = correlate([t, datetime.now()], int(params.get("window_minutes", 30)))
                out += "\n\nWindows events around then:\n" + ("\n".join(ev[:15]) if ev else "none in that window.")
            if act == "history":
                q = params.get("text")
                hist = search_history(data.sid, q, 30) if q else [f"{snap_time(p):%Y-%m-%d %H:%M}" for p in snapshots(data.sid)[-20:]]
                out = ("Matches in history:\n" if q else "Readings kept:\n") + "\n".join(hist)
    elif act == "export_csv":
        out = f"Saved {many(len(data.records), 'row')} to {export_csv(data)}."
    elif act == "validate":
        rules = params.get("rules") or ([params["rule"]] if params.get("rule") else list(PROBES[src].attention) if src in PROBES else [])
        if not rules:
            return head + note + "Give the policy as rules, e.g. rules=[\"enabled == True\", \"version >= 2\"]."
        lines = []
        for r in rules:
            bad = check(data.records, r)
            lines.append(f"{'✗' if bad else '✓'} {r}" + (f" — {len(bad)} item(s): " + "; ".join(describe(x, data.key) for x in bad[:4]) if bad else ""))
        out = "Policy check (✗ = items that match the problem rule):\n" + "\n".join(lines)
    elif act == "dashboard":
        save(data)
        p = dashboard([data])
        import os
        os.startfile(str(p))
        out = f"Opened the dashboard: {p}"
    elif act == "archive":
        save(data)
        out = archive(data.sid, int(params.get("keep_days", 30)))
    elif act == "dry_run":
        if params.get("profile"):
            plan = profile_plan(params["profile"])
            out = "Would change: " + ("; ".join(f"{k}: {a} → {b}" for k, a, b in plan) if plan else "nothing (already like that).")
        else:
            save(data)
            out = ("Before changing it, here's the current state (saved, so you can compare afterwards with the 'compare' idea):\n" + summary(data, 8))
    elif act == "trend":
        save(data)
        field = params.get("field") or (data.numbers[0] if data.numbers else None)
        if not field:
            return head + note + "This source has no numbers to trend. Choose field=… from: " + ", ".join(list(data.records[0])[:12] if data.records else [])
        out = trend(data.sid, field, params.get("item"), float(params["threshold"]) if params.get("threshold") is not None else None, data.key)
        if "Not enough" in out and params.get("schedule", True):
            w = add_watch(f"Trend: {subject}", src, params, "trend", int(params.get("every_minutes", 720)), field=field)
            out += f" I'll take a reading {when(w)} (watch {w['id']})."
    elif act == "bundle":
        out = f"Diagnostic bundle saved: {bundle([data])}"
    elif act == "stale":
        found = stale(data.records, float(params["max_age_days"]) if params.get("max_age_days") else 90)
        out = (f"{len(found)} missing/stale:\n" + "\n".join(found[:25])) if found else "No missing or stale values."
    elif act == "recovery":
        out = "Recovery checklist:\n" + "\n".join(checklist(i["area"], subject))
    elif act == "apply_profile":
        prof = params.get("profile")
        if not prof:
            from . import PROFILE_KEYS
            return head + note + ("Echo can apply profiles of these settings (it asks first): " +
                                  "; ".join(f"{k} ({v})" for k, v in PROFILE_KEYS.items()) + ". Run again with profile={…}. "
                                  "Other settings in this idea need their own app or admin rights.")
        plan = profile_plan(prof)
        if not plan:
            return head + "Already set like that."
        ok = getattr(ctx, "confirm", lambda *a: False)("Apply this profile?", "\n".join(f"{k}: {a} → {b}" for k, a, b in plan))
        if not ok:
            return head + "You said no, so nothing changed."
        before = save(data)
        out = "Applied: " + ", ".join(profile_apply(plan)) + f". The 'before' state is saved ({before.name})."
    return head + note + out
