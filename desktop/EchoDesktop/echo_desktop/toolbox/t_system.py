"""This PC: hardware, Windows, processes, apps, network and settings. Reading is free; changes ask first.
Commands run here are fixed Windows tools with fixed arguments (tasklist, netstat, netsh, ping, powercfg) — never a shell."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import csv
import io
import locale
import os
import platform
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta
from typing import Literal

from . import ToolError, tool
from ..words import many

C = "system"
NO_WINDOW = 0x08000000
CRITICAL = {"system", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe", "lsass.exe", "svchost.exe", "dwm.exe",
            "fontdrvhost.exe", "registry", "memcompression", "secure system", "explorer.exe", "msmpeng.exe"}


def run(args: list, timeout: int = 20) -> str:
    try:
        out = subprocess.run(args, capture_output=True, timeout=timeout, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as e:
        raise ToolError(f"{args[0]} failed: {e}")
    raw = out.stdout or out.stderr
    for enc in ("utf-8", "mbcs", "cp437"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def human(n):
    from .t_data import human_size
    return human_size(n)


def reg(path: str, name: str, hive=None):
    import winreg
    try:
        with winreg.OpenKey(hive or winreg.HKEY_LOCAL_MACHINE, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [("dwLength", wt.DWORD), ("dwMemoryLoad", wt.DWORD), ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def memory() -> MEMORYSTATUSEX:
    m = MEMORYSTATUSEX()
    m.dwLength = ctypes.sizeof(m)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m


@tool(C, ex={}, keys="ram memory usage free")
def memory_usage() -> str:
    """RAM in use and free."""
    m = memory()
    return f"{human(m.ullTotalPhys - m.ullAvailPhys)} of {human(m.ullTotalPhys)} RAM in use ({m.dwMemoryLoad}%); {human(m.ullAvailPhys)} free."


@tool(C, ex={}, keys="processor cpu cores model")
def cpu_info() -> str:
    """Processor model and cores."""
    name = reg(r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", "ProcessorNameString") or platform.processor()
    mhz = reg(r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", "~MHz")
    return f"{str(name).strip()}, {os.cpu_count()} logical processors" + (f", base {mhz} MHz." if mhz else ".")


def _times():
    ft = [wt.FILETIME() for _ in range(3)]
    ctypes.windll.kernel32.GetSystemTimes(*[ctypes.byref(f) for f in ft])
    v = [(f.dwHighDateTime << 32) | f.dwLowDateTime for f in ft]
    return v[0], v[1] + v[2]


@tool(C, ex={}, keys="cpu usage load busy percent")
def cpu_usage() -> str:
    """How busy the processor is right now (measured over half a second)."""
    i1, t1 = _times()
    time.sleep(0.5)
    i2, t2 = _times()
    busy = 100 * (1 - (i2 - i1) / max(t2 - t1, 1))
    return f"CPU is {busy:.0f}% busy."


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte), ("BatteryLifePercent", ctypes.c_byte),
                ("SystemStatusFlag", ctypes.c_byte), ("BatteryLifeTime", wt.DWORD), ("BatteryFullLifeTime", wt.DWORD)]


@tool(C, ex={}, keys="battery charge percent plugged charging laptop")
def battery_status() -> str:
    """Battery level, charging state and time left."""
    s = SYSTEM_POWER_STATUS()
    ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s))
    pct = s.BatteryLifePercent & 0xFF
    if s.BatteryFlag & 128 or pct == 255:
        return "This PC has no battery (it runs on mains power)."
    plugged = s.ACLineStatus == 1
    left = s.BatteryLifeTime
    t = f", about {left // 3600} h {left % 3600 // 60} min left" if left not in (0xFFFFFFFF, -1) and not plugged else ""
    saver = " Battery saver is on." if s.SystemStatusFlag & 1 else ""
    return f"Battery {pct}%, {'plugged in' + (' and charging' if s.BatteryFlag & 8 else '') if plugged else 'on battery'}{t}.{saver}"


@tool(C, ex={}, keys="uptime how long running since boot restart")
def uptime() -> str:
    """How long since the PC was started."""
    ms = ctypes.windll.kernel32.GetTickCount64()
    ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
    ms = ctypes.windll.kernel32.GetTickCount64()
    from .t_time import format_duration
    return f"Up for {format_duration(ms / 1000)} (since {datetime.now() - timedelta(milliseconds=ms):%a %d %b %H:%M})."


@tool(C, ex={}, keys="windows version os build edition")
def windows_version() -> str:
    """Windows edition, version and build."""
    k = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
    name, disp, build, ubr = reg(k, "ProductName"), reg(k, "DisplayVersion"), reg(k, "CurrentBuildNumber"), reg(k, "UBR")
    if build and int(build) >= 22000 and name:
        name = name.replace("Windows 10", "Windows 11")
    return f"{name} {disp or ''} (build {build}.{ubr}), {platform.machine()}."


@tool(C, ex={}, keys="computer name user hostname who am i")
def pc_identity() -> dict:
    """PC name, signed-in user and domain/workgroup."""
    return {"pc_name": socket.gethostname(), "user": os.environ.get("USERNAME", ""), "domain": os.environ.get("USERDOMAIN", "")}


@tool(C, ex={}, keys="screen resolution monitors display size dpi scaling")
def screen_info() -> str:
    """Screen resolution, number of monitors and scaling."""
    u = ctypes.windll.user32
    try:
        u.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        pass
    w, h, mons = u.GetSystemMetrics(0), u.GetSystemMetrics(1), u.GetSystemMetrics(80)
    dpi = u.GetDpiForSystem() if hasattr(u, "GetDpiForSystem") else 96
    return f"Main screen {w} × {h}, {mons} monitor(s), scaling {round(dpi / 96 * 100)}%."


@tool(C, ex={}, keys="overview summary computer specs health status")
def system_summary() -> dict:
    """One-glance summary: Windows, CPU, RAM, disk, battery, uptime."""
    import shutil
    d = shutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\")
    return {"windows": windows_version(), "cpu": cpu_info(), "memory": memory_usage(), "system_drive": f"{human(d.free)} free of {human(d.total)}",
            "battery": battery_status(), "uptime": uptime(), "python": sys.version.split()[0]}


def processes() -> list:
    rows = list(csv.reader(io.StringIO(run(["tasklist", "/FO", "CSV", "/NH"]))))
    out = []
    for r in rows:
        if len(r) >= 5:
            kb = int(re.sub(r"\D", "", r[4]) or 0)
            out.append((r[0], int(r[1]), kb * 1024))
    return out


@tool(C, ex={"count": 5}, keys="processes running programs task manager memory hog top")
def top_processes(count: int = 15) -> list:
    """Programs using the most memory right now."""
    ps = sorted(processes(), key=lambda p: -p[2])
    return [f"{n} (pid {pid}): {human(m)}" for n, pid, m in ps[:max(1, min(count, 100))]]


@tool(C, ex={"name": "python"}, keys="is running process find program pid")
def find_process(name: str) -> list:
    """Find running programs by name."""
    hits = [p for p in processes() if name.lower() in p[0].lower()]
    return [f"{n} (pid {pid}): {human(m)}" for n, pid, m in hits] or [f"No running program matches {name}."]


@tool(C, ask=True, keys="kill end stop close process program force quit task")
def end_process(name_or_pid: str, ctx=None) -> str:
    """Force-close a running program (unsaved work is lost). Never system processes. Asks first."""
    from .t_files import confirm
    ps = processes()
    target = [p for p in ps if (name_or_pid.isdigit() and p[1] == int(name_or_pid)) or p[0].lower() == name_or_pid.lower()
              or p[0].lower() == name_or_pid.lower() + ".exe"]
    if not target:
        raise ToolError(f"nothing running matches {name_or_pid}")
    if any(p[0].lower() in CRITICAL for p in target) or any(p[1] == os.getpid() for p in target):
        raise ToolError("that's a Windows system process (or Echo itself); ending it could crash the PC")
    confirm(ctx, "Force-close a program?", "\n".join(f"{n} (pid {pid})" for n, pid, _ in target) + "\nUnsaved work in it will be lost.")
    for _, pid, _ in target:
        run(["taskkill", "/PID", str(pid), "/F"])
    return f"Ended {len(target)} process(es)."


@tool(C, ex={}, keys="open windows apps running list")
def open_windows() -> list:
    """Titles of the app windows open right now."""
    from .. import pcctl
    return [f"{t} ({p})" for _, t, p in pcctl.top_windows()][:60]


@tool(C, ex={}, keys="active window current app focused")
def active_window() -> str:
    """Which window is in front right now."""
    from .. import pcctl
    h = pcctl.foreground()
    return f"{pcctl.title(h) or '(no title)'} — {pcctl.process_name(h) or 'unknown program'}"


def _uninstall_entries():
    import winreg
    out = {}
    for hive, path in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                       (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                       (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")):
        try:
            with winreg.OpenKey(hive, path) as k:
                for i in range(winreg.QueryInfoKey(k)[0]):
                    try:
                        with winreg.OpenKey(k, winreg.EnumKey(k, i)) as s:
                            name = winreg.QueryValueEx(s, "DisplayName")[0]
                            try:
                                ver = winreg.QueryValueEx(s, "DisplayVersion")[0]
                            except OSError:
                                ver = ""
                            try:
                                if winreg.QueryValueEx(s, "SystemComponent")[0] == 1:
                                    continue
                            except OSError:
                                pass
                            out[name] = ver
                    except OSError:
                        continue
        except OSError:
            continue
    return out


@tool(C, ex={"search": "python"}, keys="installed programs apps software list version")
def installed_apps(search: str = "") -> list:
    """Installed programs (optionally filtered by name), with versions."""
    apps = sorted(_uninstall_entries().items(), key=lambda kv: kv[0].lower())
    hits = [(n if not v or str(v) in n else f"{n} {v}").strip() for n, v in apps if search.lower() in n.lower()]   # no "IDE 2.3 2.3"
    return hits[:200] or [f"Nothing installed matches {search}."]


@tool(C, ex={}, keys="startup apps boot run login autostart")
def startup_apps() -> list:
    """Programs that start when you sign in."""
    import winreg
    out = []
    for hive, label in ((winreg.HKEY_CURRENT_USER, "you"), (winreg.HKEY_LOCAL_MACHINE, "all users")):
        try:
            with winreg.OpenKey(hive, r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
                for i in range(winreg.QueryInfoKey(k)[1]):
                    n, v, _ = winreg.EnumValue(k, i)
                    out.append(f"{n} ({label})")
        except OSError:
            pass
    folder = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup")
    if os.path.isdir(folder):
        out += [f"{f} (Startup folder)" for f in os.listdir(folder) if f.lower() != "desktop.ini"]
    return out or ["Nothing starts automatically."]


def local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))                       # no packets are sent; picks the outgoing interface
        return s.getsockname()[0]
    except OSError:
        return "unknown"
    finally:
        s.close()


@tool(C, ex={}, keys="local ip address network lan")
def network_info() -> dict:
    """This PC's local IP, Wi-Fi network and default gateway."""
    out = {"local_ip": local_ip()}
    gw = re.search(r"Default Gateway[ .]*: ([\d.]+)", run(["ipconfig"]))
    if gw:
        out["gateway"] = gw.group(1)
    out.update(wifi_status_dict())
    return out


def wifi_status_dict() -> dict:
    text = run(["netsh", "wlan", "show", "interfaces"])
    get = lambda k: (re.search(rf"^\s*{k}\s*:\s*(.+)$", text, re.M) or [None, None])[1]
    if not get("SSID"):
        return {"wifi": "not connected (or no Wi-Fi adapter)"}
    return {"wifi": get("SSID").strip(), "signal": (get("Signal") or "").strip(), "speed": (get("Receive rate \\(Mbps\\)") or "").strip() + " Mbps",
            "band": (get("Band") or get("Radio type") or "").strip()}


@tool(C, ex={}, keys="wifi signal connected network ssid strength")
def wifi_status() -> dict:
    """Wi-Fi network name, signal strength and speed."""
    return wifi_status_dict()


@tool(C, ex={}, keys="internet working online connected check")
def internet_check() -> str:
    """Is the internet working, and how fast is the first response?"""
    from .. import internet
    try:
        r = internet.request("https://clients3.google.com/generate_204", timeout=8)
        return f"Online: answered in {r.elapsed * 1000:.0f} ms."
    except internet.NetError as e:
        return f"Offline or blocked: {e}"


@tool(C, ex={"host": "google.com"}, net=True, keys="ping latency network test lag")
def ping(host: str, count: int = 4) -> str:
    """Ping a public website or server and report the delay."""
    from .. import internet
    h = re.sub(r"^https?://", "", host.strip()).split("/")[0]
    if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", h):
        raise ToolError("give a host name like google.com")
    internet.check_host(h)
    out = run(["ping", "-n", str(max(1, min(count, 10))), h], timeout=40)
    avg = re.search(r"Average = (\d+)ms", out)
    loss = re.search(r"\((\d+)% loss\)", out)
    if not avg:
        return f"No reply from {h}." + (f" ({loss.group(1)}% lost)" if loss else "")
    return f"{h}: average {avg.group(1)} ms, {loss.group(1) if loss else '?'}% packets lost."


@tool(C, ex={}, keys="listening ports open local servers netstat which program port")
def listening_ports() -> list:
    """Network ports this PC is listening on, and which program owns each."""
    names = {pid: n for n, pid, _ in processes()}
    out = set()
    for line in run(["netstat", "-ano", "-p", "TCP"]).splitlines():
        m = re.match(r"\s*TCP\s+(\S+):(\d+)\s+\S+\s+LISTENING\s+(\d+)", line)
        if m:
            out.add((int(m.group(2)), m.group(1), names.get(int(m.group(3)), m.group(3))))
    return [f"port {p} ({'only this PC' if a in ('127.0.0.1', '[::1]') else 'network'}): {n}" for p, a, n in sorted(out)][:80]


@tool(C, ex={"port": 8000}, keys="port free in use available local")
def port_free(port: int) -> str:
    """Is a local port free for a dev server?"""
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", port))
        return f"Port {port} is free."
    except OSError:
        owner = next((l for l in listening_ports() if l.startswith(f"port {port} ")), "")
        return f"Port {port} is in use. {owner}".strip()
    finally:
        s.close()


@tool(C, ex={"name": "PATH"}, keys="environment variable env path value")
def environment_variable(name: str) -> str:
    """Value of an environment variable (secret-looking ones are hidden)."""
    if re.search(r"KEY|TOKEN|SECRET|PASS|PWD|CRED|AUTH", name, re.I):
        return f"{name} looks secret, so I won't show it." + (" (It is set.)" if os.environ.get(name) else " (It isn't set.)")
    v = os.environ.get(name)
    if v is None:
        return f"{name} isn't set."
    return "\n".join(v.split(";")) if name.upper() == "PATH" else v


@tool(C, ex={}, keys="python versions installed py launcher")
def python_versions() -> str:
    """Python versions installed (from the py launcher)."""
    return run(["py", "-0p"]).strip() or "The py launcher isn't installed."


@tool(C, ex={}, keys="power plan mode balanced performance saver")
def power_plan() -> str:
    """The active power plan."""
    m = re.search(r"\((.+)\)", run(["powercfg", "/getactivescheme"]))
    return f"Power plan: {m.group(1)}." if m else "I couldn't read the power plan."


@tool(C, ex={}, keys="timezone region language locale settings")
def region_settings() -> dict:
    """Time zone, language and region formats."""
    return {"time_zone": time.tzname[0], "utc_offset": time.strftime("%z"), "language": locale.getlocale()[0],
            "encoding": locale.getpreferredencoding(False)}


@tool(C, ex={}, keys="recycle bin size trash how much")
def recycle_bin_size() -> str:
    """How much is in the Recycle Bin."""
    class SHQUERYRBINFO(ctypes.Structure):
        _fields_ = [("cbSize", wt.DWORD), ("i64Size", ctypes.c_longlong), ("i64NumItems", ctypes.c_longlong)]
    info = SHQUERYRBINFO(ctypes.sizeof(SHQUERYRBINFO), 0, 0)
    ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
    return f"{many(info.i64NumItems, 'item')}, {human(info.i64Size)}."


@tool(C, ask=True, keys="empty recycle bin trash clear")
def empty_recycle_bin(ctx=None) -> str:
    """Empty the Recycle Bin for good. Asks first."""
    from .t_files import confirm
    confirm(ctx, "Empty the Recycle Bin?", "Everything in it will be deleted for good. " + recycle_bin_size())
    ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x1 | 0x2 | 0x4)
    return "Recycle Bin emptied."


@tool(C, ex={}, keys="clipboard read paste what copied")
def clipboard_read() -> str:
    """What's on the clipboard (text)."""
    from .. import typer
    t = typer.get_clipboard_text()
    return t if t else "The clipboard has no text."


@tool(C, keys="clipboard copy set put text")
def clipboard_write(text: str) -> str:
    """Put text on the clipboard (ready to paste)."""
    from .. import typer
    typer.set_clipboard_text(text)
    return f"Copied {many(len(text), 'character')} to the clipboard."


@tool(C, keys="volume sound loud quiet mute speaker audio")
def set_volume(level: Literal["up", "down", "mute", "set"], percent: int = 50) -> str:
    """Change the speaker volume: up, down, mute/unmute, or set to a percent."""
    from .. import control
    return control.volume(level, max(0, min(percent, 100)) if level == "set" else None)[1]


@tool(C, keys="music media play pause next previous track song")
def media_control(action: Literal["toggle", "next", "previous"]) -> str:
    """Play/pause, next or previous track in whatever is playing."""
    from .. import control
    return control.media(action)[1]


@tool(C, keys="brightness screen dim bright")
def screen_brightness(percent: int = -1) -> str:
    """Read the screen brightness, or set it (0–100) on laptop screens."""
    from .. import pcctl
    return pcctl._brightness(None if percent < 0 else max(0, min(percent, 100)))[1]


@tool(C, keys="dark mode light mode theme")
def dark_mode(on: bool) -> str:
    """Switch Windows dark mode on or off."""
    from .. import pcctl
    return pcctl.system("DARK_ON" if on else "DARK_OFF", {}, lambda *_: True)[1]


@tool(C, keys="lock screen computer away")
def lock_pc() -> str:
    """Lock the PC (sign-in needed to come back)."""
    from .. import control
    return control.lock()[1]


@tool(C, keys="screenshot capture screen snip")
def take_screenshot() -> str:
    """Open the screen-snip tool to capture part of the screen."""
    from .. import control
    return control.screenshot()[1]


@tool(C, keys="windows settings page open bluetooth display sound")
def open_settings_page(page: str) -> str:
    """Open a Windows Settings page by its ms-settings name (e.g. bluetooth, display, sound, network-wifi, windowsupdate, apps-volume)."""
    p = page.strip().lower().removeprefix("ms-settings:")
    if not re.fullmatch(r"[a-z0-9-]*", p):
        raise ToolError("use a settings page name like bluetooth or display")
    os.startfile("ms-settings:" + p)
    return f"Opened Settings{(': ' + p) if p else ''}."
