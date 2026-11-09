"""Proactive nudges (the "heartbeat" every top JARVIS/OpenClaw build has): every few minutes Echo looks at what it
already knows and speaks up only when something needs you — a task due within the hour or overdue, follow-ups and
birthdays today, a habit not done by the evening, the battery about to run out, the system drive nearly full.

Each nudge is given once (per task, per day), never during quiet hours (except a battery about to die), and the
whole thing is one setting ("proactive", say "stop the nudges"). Everything is read on this PC; nothing is sent
anywhere. `nudges()` is pure and unit-tested; `Heartbeat` is the background thread.
"""
from __future__ import annotations

import ctypes
import json
import os
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from . import pa

INTERVAL = 600            # seconds between checks
FIRST_CHECK = 120         # the first check, after Echo starts


@dataclass
class Nudge:
    key: str              # one nudge per key per day
    text: str
    urgent: bool = False  # speaks even during quiet hours


def _due(item: dict) -> Optional[datetime]:
    d = pa.parse_iso(item.get("due"))
    if d is not None and not item.get("timed"):
        d = d.replace(hour=23, minute=59)
    return d


def nudges(data: dict, now: datetime, battery: Optional[tuple] = None, disk_free: Optional[float] = None) -> list:
    """What deserves a word right now. data = the assistant store; battery = (percent, charging); disk_free = fraction."""
    out = []
    today = now.date()
    for t in data.get("tasks", []):
        if t.get("done"):
            continue
        due = _due(t)
        if due is None:
            continue
        if due < now and due.date() < today:
            out.append(Nudge(f"overdue:{t['id']}", f"“{t['title']}” is overdue (it was due {pa.say_when(due, t.get('timed', False), now)})."))
        elif t.get("timed") and now <= due <= now + timedelta(hours=1):
            mins = max(1, int((due - now).total_seconds() // 60))
            out.append(Nudge(f"soon:{t['id']}", f"“{t['title']}” is due in {mins} minute{'s' if mins != 1 else ''}."))
        elif t.get("timed") and now - timedelta(hours=2) <= due < now:
            out.append(Nudge(f"missed:{t['id']}", f"“{t['title']}” was due at {due.strftime('%I:%M %p').lstrip('0')}."))
    if now.hour >= 9:
        due_f = [f for f in data.get("followups", []) if not f.get("done") and (_due(f) or now) <= now.replace(hour=23, minute=59)]
        if due_f:
            names = ", ".join(f["title"] for f in due_f[:3]) + (" and more" if len(due_f) > 3 else "")
            out.append(Nudge("followups", f"Follow up today: {names}."))
        bdays = [p["name"] for p in data.get("people", {}).values() if p.get("birthday") == now.strftime("%m-%d")]
        if bdays:
            out.append(Nudge("birthdays", f"It's {', '.join(bdays)}'s birthday today."))
    if now.hour >= 19:
        missing = [h["name"] for h in data.get("habits", {}).values()
                   if h.get("per_week", 7) >= 7 and today.isoformat() not in (h.get("days") or [])]
        if missing:
            out.append(Nudge("habits", f"Not ticked off yet today: {', '.join(missing[:4])}."))
    if battery is not None:
        percent, charging = battery
        if not charging and percent <= 8:
            out.append(Nudge("battery-critical", f"Battery is at {percent}%. Plug in now, or the PC will shut down.", urgent=True))
        elif not charging and percent <= 15:
            out.append(Nudge("battery-low", f"Battery is at {percent}%; time to plug in."))
    if disk_free is not None and disk_free < 0.05:
        out.append(Nudge("disk", f"Your system drive is almost full ({disk_free * 100:.0f}% free). Say “clean up temp files” or "
                                 "“largest files in Downloads”."))
    return out


def in_quiet_hours(now: datetime, spec: str) -> bool:
    """spec "22-7": from 22:00 to 07:00. Empty or invalid: never quiet."""
    try:
        start, end = (int(x) for x in (spec or "").split("-"))
    except ValueError:
        return False
    h = now.hour
    return (start <= h or h < end) if start > end else (start <= h < end)


# ------------------------------------------------------------------------------------------------ PC readings
class _Power(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte), ("BatteryLifePercent", ctypes.c_ubyte),
                ("SystemStatusFlag", ctypes.c_ubyte), ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]


def battery() -> Optional[tuple]:
    """(percent, charging), or None on a desktop PC without a battery."""
    s = _Power()
    try:
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)):
            return None
    except (AttributeError, OSError):
        return None
    if s.BatteryFlag & 128 or s.BatteryLifePercent > 100:
        return None
    return int(s.BatteryLifePercent), s.ACLineStatus == 1


def disk_free() -> Optional[float]:
    try:
        u = shutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\")
        return u.free / u.total
    except OSError:
        return None


# ------------------------------------------------------------------------------------------------ the heartbeat
class Heartbeat:
    def __init__(self, settings, store: Callable[[], pa.Store], tell: Callable[[str, bool], None], state_path: Path,
                 now: Callable[[], datetime] = datetime.now, readings=None):
        """tell(text, speak) shows a nudge (and says it when speak is True)."""
        self.settings, self.store, self.tell, self.state_path, self.now = settings, store, tell, state_path, now
        self.readings = readings or (lambda: (battery(), disk_free()))
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def start(self) -> None:
        threading.Thread(target=self._loop, daemon=True, name="echo-heartbeat").start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        if self._stop.wait(FIRST_CHECK):
            return
        while not self._stop.is_set():
            try:
                if self.settings["proactive"]:
                    self.beat()
            except Exception:           # a bad reading must never stop the heartbeat
                pass
            self._stop.wait(INTERVAL)

    def current(self) -> list:
        """Every nudge that applies now, given or not ("anything I should know?")."""
        try:
            data = self.store().read()
        except OSError:
            data = {}
        bat, disk = self.readings()
        return nudges(data, self.now(), bat, disk)

    def beat(self) -> list:
        """Give the nudges not given yet today. Returns them."""
        now = self.now()
        quiet = in_quiet_hours(now, self.settings["quiet_hours"] or "")
        with self._lock:
            given = self._given(now)
            fresh = [n for n in self.current() if n.key not in given and (n.urgent or not quiet)]
            if not fresh:
                return []
            given.update(n.key for n in fresh)
            self._save(now, given)
        for n in fresh:
            self.tell("🔔 " + n.text, bool(n.urgent or not quiet))
        return fresh

    def _given(self, now: datetime) -> set:
        try:
            d = json.loads(self.state_path.read_text("utf-8"))
            return set(d.get("keys", [])) if d.get("day") == now.date().isoformat() else set()
        except (OSError, ValueError, AttributeError):
            return set()

    def _save(self, now: datetime, keys: set) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps({"day": now.date().isoformat(), "keys": sorted(keys)}), "utf-8")
        except OSError:
            pass
