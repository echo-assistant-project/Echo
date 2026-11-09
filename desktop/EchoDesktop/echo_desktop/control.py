"""Allow-listed Windows actions. Apps open only from Start-menu shortcuts or a fixed list; no shells, no paths
from the AI, no arbitrary commands."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import re
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import quote, quote_plus, urlparse

BUILT_IN = {
    "settings": "ms-settings:", "windows settings": "ms-settings:", "calculator": "calc.exe", "calc": "calc.exe",
    "notepad": "notepad.exe", "paint": "mspaint.exe", "file explorer": "explorer.exe", "explorer": "explorer.exe",
    "files": "explorer.exe", "task manager": "taskmgr.exe", "camera": "microsoft.windows.camera:",
    "microsoft store": "ms-windows-store:", "store": "ms-windows-store:", "snipping tool": "ms-screenclip:",
    "mail": "mailto:", "bluetooth settings": "ms-settings:bluetooth", "wifi settings": "ms-settings:network-wifi",
    "display settings": "ms-settings:display", "sound settings": "ms-settings:sound",
}
_VK = {"volume_up": 0xAF, "volume_down": 0xAE, "mute": 0xAD, "toggle": 0xB3, "play": 0xB3, "pause": 0xB3,
       "next": 0xB0, "previous": 0xB1}


def _start_menu_shortcuts() -> dict:
    roots = [Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
             Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs"]
    found = {}
    for root in roots:
        if root.is_dir():
            for path in list(root.rglob("*.lnk")) + list(root.rglob("*.url")):
                name = path.stem.lower()
                if "uninstall" not in name:
                    found.setdefault(name, path)
    return found


_STORE_APPS: tuple = (0.0, {})


def _store_apps() -> dict:
    """Start-menu apps without a shortcut file (Store apps: WhatsApp, Outlook, Photos, Terminal…): name -> (name, app ID).
    Read from Windows' own list (Get-StartApps), cached for 10 minutes."""
    global _STORE_APPS
    if _STORE_APPS[1] and time.monotonic() - _STORE_APPS[0] < 600:
        return _STORE_APPS[1]
    import subprocess
    script = "[Console]::OutputEncoding = [Text.Encoding]::UTF8; Get-StartApps | ForEach-Object { $_.Name + \"`t\" + $_.AppID }"
    apps = {}
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, timeout=20,
                             creationflags=0x08000000)
        for line in out.stdout.decode("utf-8", "replace").splitlines():
            n, _, app_id = line.partition("\t")
            n, app_id = n.strip(), app_id.strip()
            if n and app_id and "uninstall" not in n.lower():
                apps.setdefault(n.lower(), (n, app_id))
    except (OSError, ValueError):
        pass
    _STORE_APPS = (time.monotonic(), apps)
    return apps


def _best(found: dict, wanted: str):
    return found.get(wanted) or next((v for n, v in sorted(found.items()) if len(n) >= 3 and (n.startswith(wanted) or wanted.startswith(n))), None)


def find_app(name: str, exact: bool = False) -> Optional[tuple]:
    """(label, what to start) for an installed app: Echo's built-ins, Start-menu shortcuts, then Store apps (WhatsApp,
    Outlook, Photos…) by their Windows app ID. exact=True: only an exact name match."""
    wanted = name.lower().strip()
    if not wanted:
        return None
    if wanted in BUILT_IN:
        return name, BUILT_IN[wanted]
    shortcuts = _start_menu_shortcuts()
    match = shortcuts.get(wanted) if exact else _best(shortcuts, wanted)
    if match:
        return match.stem, str(match)
    apps = _store_apps()
    found = apps.get(wanted) if exact else _best(apps, wanted)
    if found:                        # an ID from Windows' Start-menu list (never from the AI), opened via the Apps folder
        return found[0], "shell:AppsFolder\\" + found[1]
    return None


# Apps can take a while to show a window (a game launcher, or anything on a busy disk). Echo starts the app, says so at
# once, and a watcher waits patiently for its window: launch_listener(label, windows_before) is set by the brain.
launch_listener: Optional[Callable[[str, set], None]] = None


def launch(label: str, target: str) -> None:
    before = set()
    if launch_listener is not None:
        try:
            from .pcctl import window_handles
            before = window_handles()
        except Exception:
            before = set()
    os.startfile(target)
    if launch_listener is not None:
        try:
            launch_listener(label, before)
        except Exception:
            pass


_SITE_NOISE = re.compile(r"^(?:the|my)\s+|\s+(?:website|web site|site|web|page|dot com|app)$")
_DOMAIN = re.compile(r"^[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}$")


def site_for(name: str, search=None):
    """(label, url) of the website called `name`, or None. Nothing is listed in code: a name that already is a domain
    ("flipkart.com"), a site in the Command Pack's data, else the web's top result for "<name> official website"."""
    key = re.sub(r"\s+", " ", (name or "").lower().strip(" .!?"))
    for _ in range(2):
        key = _SITE_NOISE.sub("", key).strip()
    if not key or len(key.split()) > 4:                # a name, not a sentence
        return None
    if _DOMAIN.match(key):
        return key, "https://" + key
    try:                                               # the Command Pack's website data ("open.gmail" …)
        from . import core
        cat = core._catalog
        if cat is not None:
            for c in cat.commands:
                if c.id.startswith("open.") and c.spec.get("url") and key in (str(c.spec.get("app", "")).lower(), c.id[5:].replace("_", " ")):
                    return c.spec.get("app") or c.title, c.spec["url"]
    except Exception:
        pass
    try:                                               # anything else: ask the web where its official site is
        if search is None:
            from .internet import search
        hits = search(key + " official website", 3)
    except Exception:
        return None
    compact = re.sub(r"[^a-z0-9]", "", key)
    words = [w for w in re.findall(r"[a-z0-9]+", key) if len(w) >= 3] or [compact]
    for h in hits:
        u = urlparse(h.url)
        host = (u.hostname or "").lower()
        if u.scheme not in ("http", "https") or not host or "wikipedia.org" in host:
            continue
        flat = host.replace("-", "").replace(".", "")
        # only the name's own site: "zomato" -> zomato.com, "prime video" -> primevideo.com, "youtube music" ->
        # music.youtube.com; a random page that merely mentions the words doesn't count
        if compact in flat or all(w in flat for w in words):
            return host.removeprefix("www."), f"{u.scheme}://{host}/"
    return None


def open_app(name: str) -> tuple:
    found = find_app(name)
    if not found:
        site = site_for(name)                          # "open youtube": no YouTube app installed, so open the website
        if site:
            webbrowser.open(site[1])
            return True, f"Opening {site[0]}."
        return False, f"I couldn't find {name} in the Start menu."
    label, target = found
    launch(label, target)
    return True, f"Opening {label}."


def open_url(url: str) -> tuple:
    webbrowser.open(url)
    return True, f"Opening {url}."


def web_search(engine: str, query: str) -> tuple:
    url = {"google": "https://www.google.com/search?q=" + quote_plus(query),
           "youtube": "https://www.youtube.com/results?search_query=" + quote_plus(query),
           "spotify": "https://open.spotify.com/search/" + quote(query)}[engine]
    webbrowser.open(url)
    return True, f"Showing {engine.title()} results for {query}."


def _key(vk: int, times: int = 1) -> None:
    for _ in range(times):
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)


def volume(change: str, percent=None) -> tuple:
    if change == "up":
        _key(_VK["volume_up"], 5)
        return True, "Volume up."
    if change == "down":
        _key(_VK["volume_down"], 5)
        return True, "Volume down."
    if change == "mute":
        _key(_VK["mute"])
        return True, "Toggled mute."
    # Windows volume keys move in 2% steps: go to zero, then step up.
    _key(_VK["volume_down"], 50)
    _key(_VK["volume_up"], int(percent) // 2)
    return True, f"Volume set to about {int(percent)} percent."


def media(command: str) -> tuple:
    _key(_VK[command])
    return True, f"Sent {command} to the active media app."


def lock() -> tuple:
    ctypes.windll.user32.LockWorkStation()
    return True, "Locking the PC."


def screenshot() -> tuple:
    os.startfile("ms-screenclip:")
    return True, "Snipping is open; select the area to capture."


class _PowerStatus(ctypes.Structure):
    _fields_ = [("ACLineStatus", wt.BYTE), ("BatteryFlag", wt.BYTE), ("BatteryLifePercent", wt.BYTE),
                ("SystemStatusFlag", wt.BYTE), ("BatteryLifeTime", wt.DWORD), ("BatteryFullLifeTime", wt.DWORD)]


def status(topic: str) -> tuple:
    now = datetime.now()
    if topic == "time":
        return True, "It's " + now.strftime("%I:%M %p").lstrip("0") + "."
    if topic == "date":
        return True, "Today is " + now.strftime("%A, %d %B %Y") + "."
    power = _PowerStatus()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(power)) or power.BatteryLifePercent == 255:
        return True, "This PC doesn't report a battery (it's probably plugged-in only)."
    charging = " and charging" if power.ACLineStatus == 1 else ""
    return True, f"Battery is at {power.BatteryLifePercent} percent{charging}."


def greeting() -> str:
    hour = time.localtime().tm_hour
    return "Good morning" if 5 <= hour < 12 else "Good afternoon" if 12 <= hour < 17 else "Good evening"


# --------------------------------------------------------------------------- Command Pack kinds

PRO_ONLY = {"gpedit.msc", "secpol.msc", "printmanagement.msc", "lusrmgr.msc"}     # need Windows Pro/Enterprise


def windows_edition() -> str:
    """"Core" on Windows Home, "Professional", "Enterprise"…; "" if unknown."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as k:
            return str(winreg.QueryValueEx(k, "EditionID")[0])
    except OSError:
        return ""


def tool_available(target: str) -> bool:
    """A program from WIN_TOOLS on disk, or a URI scheme registered on this PC."""
    if target.lower().endswith((".exe", ".msc", ".cpl")):
        import shutil
        root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        return (root / "System32" / target).exists() or (root / target).exists() or bool(shutil.which(target))
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, target.split(":", 1)[0]):
            return True
    except OSError:
        return False


def _quote(value: str) -> str:
    return quote(value, safe="")


def run_catalog(command, slots: dict, confirm) -> tuple:
    """Desktop kinds of the Command Pack. Every target comes from the catalog's fixed tables or https templates;
    spoken words only fill slots. `confirm(title, text) -> bool` guards power actions."""
    from . import catalog
    spec, kind = command.spec, command.kind
    say = catalog.fill(command.say, slots) if command.say else None
    if kind == "web":
        url = valid_url_https(catalog.fill(spec["url"], slots, _quote))
        if not url:
            return False, "That web address isn't valid, so I didn't open it."
        webbrowser.open(url)
        return True, say or f"Opening {url}."
    if kind == "open":
        app = spec.get("app", "")
        found = find_app(app, exact=True) if app else None      # the installed app (shortcut or Store app) first
        if found and not found[1].startswith(("ms-settings:", "mailto:")):
            launch(*found)
            return True, say or f"Opening {found[0]}."
        webbrowser.open(spec["url"])
        return True, say or f"Opening {spec['url']}."
    if kind == "maps":
        q = catalog.fill(spec["q"], slots)
        webbrowser.open("https://www.google.com/maps/search/?api=1&query=" + _quote(q))
        return True, say or f"Showing {q} on the map."
    if kind == "directions":
        q = catalog.fill(spec["q"], slots)
        webbrowser.open(f"https://www.google.com/maps/dir/?api=1&destination={_quote(q)}&travelmode={spec['mode']}")
        return True, say or f"Showing directions to {q}."
    if kind == "ms_settings":
        os.startfile("ms-settings:" + spec["page"])
        return True, say or "Opening Settings."
    name = command.title.removeprefix("Open ").strip() or "it"
    if kind == "folder":
        try:
            os.startfile(catalog.FOLDERS[spec["target"]])
        except OSError:
            return False, f"Windows on this PC doesn't have the {name} folder."
        return True, say or f"Opening {name}."
    if kind == "win_tool":
        target = catalog.WIN_TOOLS[spec["target"]]
        if target.lower() in PRO_ONLY and windows_edition() == "Core":
            return False, f"{name} isn't part of Windows Home; it comes with Windows Pro."
        if not tool_available(target):
            return False, f"{name} isn't installed on this PC (it may be an optional Windows feature)."
        try:
            os.startfile(target)
        except OSError:
            return False, f"Windows couldn't open {name}."
        return True, say or f"Opening {name}."
    if kind == "win_key":
        chord = catalog.WIN_KEYS[spec["target"]]
        extended = {0x5B, 0x25, 0x26, 0x27, 0x28, 0x2C}
        for vk in chord:
            ctypes.windll.user32.keybd_event(vk, 0, 1 if vk in extended else 0, 0)
        for vk in reversed(chord):
            ctypes.windll.user32.keybd_event(vk, 0, (1 if vk in extended else 0) | 2, 0)
        return True, say or command.title + "."
    if kind == "power":
        return _power(spec["op"], confirm)
    if kind == "status":
        return True, pc_status(spec["topic"])
    return False, "EchoDesktop can't do that."


def valid_url_https(url: str):
    from . import core
    u = core.valid_url(url)
    return u if u and u.lower().startswith("https://") else None


def _power(op: str, confirm) -> tuple:
    import subprocess
    if op == "cancel":
        done = subprocess.run(["shutdown", "/a"], capture_output=True, creationflags=0x08000000).returncode == 0
        return True, "Cancelled the scheduled shutdown." if done else "There was no shutdown to cancel."
    titles = {"sleep": ("Put the PC to sleep?", "Unsaved work stays open, but apps pause."),
              "shutdown": ("Shut down the PC?", "Windows shuts down in 60 seconds. Save your work. Say “cancel shutdown” to stop it."),
              "restart": ("Restart the PC?", "Windows restarts in 60 seconds. Save your work. Say “cancel restart” to stop it.")}
    title, text = titles[op]
    if not confirm(title, text):
        return True, "Okay, nothing changed."
    if op == "sleep":
        ctypes.windll.powrprof.SetSuspendState(0, 0, 0)
        return True, "Going to sleep."
    flag = "/s" if op == "shutdown" else "/r"
    subprocess.run(["shutdown", flag, "/t", "60"], capture_output=True, creationflags=0x08000000)
    return True, ("Shutting down" if op == "shutdown" else "Restarting") + " in 60 seconds. Say “cancel shutdown” to stop it."


class _MemoryStatus(ctypes.Structure):
    _fields_ = [("dwLength", wt.DWORD), ("dwMemoryLoad", wt.DWORD), ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def _gb(n: float) -> str:
    return f"{n / 1073741824:.1f} GB"


def _cpu_busy_percent(interval: float = 0.25) -> int:
    def times():
        idle, kernel, user = wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
        ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
        as_int = lambda f: (f.dwHighDateTime << 32) | f.dwLowDateTime
        return as_int(idle), as_int(kernel) + as_int(user)
    i1, t1 = times()
    time.sleep(interval)
    i2, t2 = times()
    total = t2 - t1
    return 0 if total <= 0 else round(100 * (total - (i2 - i1)) / total)


def pc_status(topic: str) -> str:
    import getpass
    import locale
    import platform
    import shutil
    import socket
    import sys
    from . import __version__, core
    if topic == "disk":
        drive = os.environ.get("SystemDrive", "C:") + "\\"
        usage = shutil.disk_usage(drive)
        return f"{_gb(usage.free)} free of {_gb(usage.total)} on {drive[:2]}."
    if topic == "ram":
        m = _MemoryStatus()
        m.dwLength = ctypes.sizeof(_MemoryStatus)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return f"{_gb(m.ullAvailPhys)} of {_gb(m.ullTotalPhys)} memory is available ({m.dwMemoryLoad}% in use)."
    if topic == "uptime":
        ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
        seconds = ctypes.windll.kernel32.GetTickCount64() // 1000
        return f"Your PC has been on for {core.format_duration(max(60, seconds // 60 * 60))}."
    if topic == "screen":
        w, h = ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)
        return f"Your main screen is {w} by {h} (scaled) pixels."
    if topic == "timezone":
        now = datetime.now().astimezone()
        offset = now.utcoffset().total_seconds() / 3600
        return f"You're in {now.tzname()} (UTC{'+' if offset >= 0 else '-'}{abs(offset):g})."
    if topic == "echo_version":
        return f"EchoDesktop version {__version__}."
    if topic == "cpu":
        return f"{platform.processor() or 'Processor'}: {os.cpu_count()} logical cores, about {_cpu_busy_percent()}% busy right now."
    if topic == "language":
        lang = locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), "unknown")
        return f"Windows' display language is {lang}."
    if topic == "os":
        build = sys.getwindowsversion().build
        return f"Windows {'11' if build >= 22000 else '10'} (build {build})."
    if topic == "pc_name":
        return f"This PC is called {platform.node()}."
    if topic == "ip":
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("192.0.2.1", 9))   # picks the route only; UDP connect sends nothing
            return f"Your local IP address is {s.getsockname()[0]}."
        except OSError:
            return "You don't seem to be on a network."
        finally:
            s.close()
    if topic == "battery_time":
        p = _PowerStatus()
        ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(p))
        if p.BatteryLifePercent == 255:
            return "This PC doesn't report a battery."
        if p.ACLineStatus == 1:
            return f"You're plugged in at {p.BatteryLifePercent} percent."
        if p.BatteryLifeTime == 0xFFFFFFFF:
            return f"Battery is at {p.BatteryLifePercent} percent; Windows hasn't estimated the time left yet."
        return f"About {core.format_duration(p.BatteryLifeTime // 60 * 60)} left at {p.BatteryLifePercent} percent."
    if topic == "user":
        return f"You're signed in as {getpass.getuser()}."
    return "I can't read that on this PC."
