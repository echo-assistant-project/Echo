"""Probes: read one kind of thing on this PC and return records (a list of flat dicts). Read-only, no admin rights.

Each probe has: a key (the field that identifies a record, for diffs), numeric fields (for trends and thresholds), and
default "attention" rules (when something probably needs the user). PowerShell is used only with fixed scripts below.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

NO_WINDOW = 0x08000000


@dataclass
class Probe:
    name: str
    title: str
    area: str
    read: Callable[[dict], list]
    key: str = "name"
    numbers: tuple = ()
    attention: tuple = ()          # rule strings like "free_percent < 10" or "status != OK"
    keywords: str = ""
    slow: bool = False


PROBES: dict = {}


def probe(name, title, area, key="name", numbers=(), attention=(), keywords="", slow=False):
    def deco(fn):
        PROBES[name] = Probe(name, title, area, fn, key, tuple(numbers), tuple(attention), keywords, slow)
        return fn
    return deco


def ps(script: str, timeout: int = 60) -> list:
    """Run a fixed PowerShell script that ends in ConvertTo-Json; always return a list of dicts."""
    full = "$ErrorActionPreference='SilentlyContinue'; $ProgressPreference='SilentlyContinue'; " + script
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", full], capture_output=True,
                             timeout=timeout, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as e:
        raise RuntimeError(f"PowerShell failed: {e}")
    text = out.stdout.decode("utf-8", errors="replace").strip()
    if not text:
        return []
    try:
        d = json.loads(text)
    except ValueError:
        return []
    rows = d if isinstance(d, list) else [d]
    return [{k: v for k, v in r.items()} for r in rows if isinstance(r, dict)]


def J(cmd: str) -> str:
    return f"{cmd} | ConvertTo-Json -Depth 3 -Compress"


# ---- operating system ---------------------------------------------------------------------------------------------
@probe("event_errors", "Windows errors and warnings (last 24 h)", "Operating-system diagnostics", key="id", numbers=(),
       attention=("level == Error",), keywords="event log errors warnings crash system application kernel", slow=True)
def _events(p):
    hours = int(p.get("hours", 24))
    rows = ps("Get-WinEvent -FilterHashtable @{LogName='System','Application'; Level=1,2,3; StartTime=(Get-Date).AddHours(-%d)} -MaxEvents 300 | "
              "Select-Object @{n='time';e={$_.TimeCreated.ToString('s')}}, LogName, ProviderName, Id, LevelDisplayName, "
              "@{n='message';e={($_.Message -split \"`n\")[0]}}" % hours + J(""))
    return [{"id": f"{r.get('LogName')}/{r.get('ProviderName')}/{r.get('Id')}/{r.get('time')}", "time": r.get("time"), "log": r.get("LogName"),
             "source": r.get("ProviderName"), "event_id": r.get("Id"), "level": r.get("LevelDisplayName"), "message": (r.get("message") or "")[:200]}
            for r in rows]


@probe("app_crashes", "Programs that crashed (last 7 days)", "Application lifecycle", key="id", attention=("count > 0",),
       keywords="crash app hang application error faulting", slow=True)
def _crashes(p):
    rows = ps("Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000,1002; StartTime=(Get-Date).AddDays(-7)} -MaxEvents 200 | "
              "Select-Object @{n='time';e={$_.TimeCreated.ToString('s')}}, Id, @{n='app';e={$_.Properties[0].Value}}" + J(""))
    out = {}
    for r in rows:
        k = str(r.get("app") or "?")
        o = out.setdefault(k, {"id": k, "app": k, "count": 0, "last": r.get("time"), "kind": "hang" if r.get("Id") == 1002 else "crash"})
        o["count"] += 1
    return list(out.values())


@probe("updates", "Installed Windows updates", "Operating-system diagnostics", key="id", keywords="windows updates hotfix kb patches installed os updates")
def _updates(p):
    rows = ps("Get-HotFix | Select-Object HotFixID, Description, @{n='installed';e={if($_.InstalledOn){$_.InstalledOn.ToString('yyyy-MM-dd')}}}" + J(""))
    return [{"id": r.get("HotFixID"), "type": r.get("Description"), "installed": r.get("installed")} for r in rows]


@probe("drivers", "Device drivers and versions", "Operating-system diagnostics", key="device", keywords="driver versions device drivers", slow=True)
def _drivers(p):
    rows = ps("Get-CimInstance Win32_PnPSignedDriver | Where-Object DeviceName | Select-Object DeviceName, DriverVersion, Manufacturer, "
              "@{n='date';e={if($_.DriverDate){$_.DriverDate.ToString('yyyy-MM-dd')}}}" + J(""), 90)
    return [{"device": r.get("DeviceName"), "version": r.get("DriverVersion"), "maker": r.get("Manufacturer"), "date": r.get("date")} for r in rows]


@probe("device_problems", "Devices with problems (Device Manager)", "Operating-system diagnostics", key="device", attention=("count > 0",),
       keywords="device manager status problem error code yellow")
def _devprob(p):
    rows = ps("Get-CimInstance Win32_PnPEntity | Where-Object { $_.ConfigManagerErrorCode -ne 0 } | Select-Object Name, PNPClass, ConfigManagerErrorCode, Status" + J(""))
    return [{"device": r.get("Name"), "class": r.get("PNPClass"), "error_code": r.get("ConfigManagerErrorCode"), "status": r.get("Status"), "count": 1} for r in rows]


@probe("devices", "Connected devices by type", "Personal devices and peripherals", key="device",
       keywords="usb hid keyboard mouse bluetooth camera audio printer devices connected peripherals controller")
def _devices(p):
    classes = p.get("classes") or "Keyboard,Mouse,HIDClass,USB,Bluetooth,Camera,Image,AudioEndpoint,MEDIA,Printer,Biometric,SmartCardReader,Monitor"
    cls = ",".join(f"'{c.strip()}'" for c in classes.split(",") if re.fullmatch(r"[A-Za-z]+", c.strip()))
    rows = ps(f"Get-CimInstance Win32_PnPEntity | Where-Object {{ @({cls}) -contains $_.PNPClass }} | Select-Object Name, PNPClass, Status, Present" + J(""))
    return [{"device": r.get("Name"), "class": r.get("PNPClass"), "status": r.get("Status")} for r in rows if r.get("Name")]


@probe("services", "Windows services", "Operating-system diagnostics", key="name", attention=("start == Automatic and status != Running",),
       keywords="services dependencies running stopped startup type")
def _services(p):
    rows = ps("Get-Service | Select-Object Name, DisplayName, @{n='status';e={$_.Status.ToString()}}, @{n='start';e={$_.StartType.ToString()}}" + J(""))
    return [{"name": r.get("Name"), "display": r.get("DisplayName"), "status": r.get("status"), "start": r.get("start")} for r in rows]


@probe("scheduled_tasks", "Scheduled tasks (yours and apps')", "Operating-system diagnostics", key="name", attention=("last_result != 0 and last_result != 267011",),
       keywords="scheduled task history last run result", slow=True)
def _tasks(p):
    rows = ps("Get-ScheduledTask | Where-Object { $_.TaskPath -notlike '\\Microsoft\\*' } | ForEach-Object { $i = $_ | Get-ScheduledTaskInfo; "
              "[pscustomobject]@{name=$_.TaskPath+$_.TaskName; state=$_.State.ToString(); last_run=if($i.LastRunTime){$i.LastRunTime.ToString('s')}; "
              "last_result=$i.LastTaskResult; next_run=if($i.NextRunTime){$i.NextRunTime.ToString('s')}} }" + J(""), 90)
    return rows


@probe("pending_reboot", "Pending restart", "Operating-system diagnostics", key="name", attention=("pending == True",), keywords="pending reboot restart required")
def _reboot(p):
    import winreg
    checks = {"Windows Update": r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired",
              "Component servicing": r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending"}
    out = []
    for name, path in checks.items():
        try:
            winreg.CloseKey(winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path))
            pending = True
        except OSError:
            pending = False
        out.append({"name": name, "pending": pending})
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager") as k:
            v = winreg.QueryValueEx(k, "PendingFileRenameOperations")[0]
            out.append({"name": "File rename on restart", "pending": bool(v)})
    except OSError:
        out.append({"name": "File rename on restart", "pending": False})
    return out


@probe("os_info", "Windows version, uptime and kernel", "Operating-system diagnostics", key="name", numbers=("uptime_hours",),
       attention=("uptime_hours > 336",), keywords="kernel version os build uptime summary")
def _os(p):
    from ..toolbox import t_system as s
    ms = ctypes.windll.kernel32.GetTickCount64
    ms.restype = ctypes.c_ulonglong
    return [{"name": "windows", "version": s.windows_version(), "uptime_hours": round(ms() / 3_600_000, 1), "cpu": s.cpu_info()}]


@probe("env_vars", "Environment variables (secrets hidden)", "Operating-system diagnostics", key="name", keywords="environment variables path env")
def _env(p):
    out = []
    for k, v in sorted(os.environ.items()):
        hidden = bool(re.search(r"KEY|TOKEN|SECRET|PASS|PWD|CRED|AUTH", k, re.I))
        out.append({"name": k, "value": "•••" if hidden else v[:300], "empty": not v.strip()})
    for part in os.environ.get("PATH", "").split(";"):
        if part.strip() and not os.path.isdir(os.path.expandvars(part)):
            out.append({"name": f"PATH entry missing: {part}", "value": part, "empty": True})
    return out


# ---- windows, desktop, input, accessibility -----------------------------------------------------------------------
@probe("windows", "Open windows and where they are", "Window and desktop control", key="title", numbers=("width", "height"),
       keywords="window titles geometry position size focus always on top minimized fullscreen")
def _windows(p):
    from .. import pcctl
    out = []
    for h, t, proc in pcctl.top_windows():
        r = pcctl.RECT()
        pcctl.u32.GetWindowRect(h, ctypes.byref(r))
        ex = pcctl.u32.GetWindowLongW(h, -20)
        out.append({"title": t[:120], "process": proc, "x": r.left, "y": r.top, "width": r.right - r.left, "height": r.bottom - r.top,
                    "minimized": bool(ctypes.windll.user32.IsIconic(h)), "on_top": bool(ex & 0x8)})
    return out


@probe("monitors", "Monitors, resolution and scaling", "Window and desktop control", key="name", numbers=("width", "height", "scale"),
       keywords="monitor arrangement multi-monitor scaling dpi display resolution")
def _monitors(p):
    out = []
    proc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HANDLE, wt.HDC, ctypes.POINTER(wt.RECT), wt.LPARAM)

    class MI(ctypes.Structure):
        _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD), ("szDevice", wt.WCHAR * 32)]

    def cb(h, hdc, r, l):
        mi = MI()
        mi.cbSize = ctypes.sizeof(MI)
        ctypes.windll.user32.GetMonitorInfoW(h, ctypes.byref(mi))
        dx, dy = wt.UINT(), wt.UINT()
        try:
            ctypes.windll.shcore.GetDpiForMonitor(h, 0, ctypes.byref(dx), ctypes.byref(dy))
        except (OSError, AttributeError):
            dx.value = 96
        m = mi.rcMonitor
        out.append({"name": mi.szDevice, "x": m.left, "y": m.top, "width": m.right - m.left, "height": m.bottom - m.top,
                    "scale": round(dx.value / 96 * 100), "primary": bool(mi.dwFlags & 1)})
        return True
    try:
        ctypes.windll.user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        pass
    ctypes.windll.user32.EnumDisplayMonitors(None, None, proc(cb), 0)
    return out


@probe("keyboard_layouts", "Keyboard layouts installed", "Input devices", key="name", keywords="keyboard layout input language switching")
def _kbd(p):
    n = ctypes.windll.user32.GetKeyboardLayoutList(0, None)
    arr = (wt.HKL * n)()
    ctypes.windll.user32.GetKeyboardLayoutList(n, arr)
    out = []
    for h in arr:
        lang = (h or 0) & 0xFFFF
        buf = ctypes.create_unicode_buffer(85)
        ctypes.windll.kernel32.LCIDToLocaleName(lang, buf, 85, 0)
        out.append({"name": buf.value or hex(lang), "layout_id": hex((h or 0) & 0xFFFFFFFF)})
    return out


@probe("input_settings", "Mouse and keyboard settings", "Input devices", key="name", numbers=("value",),
       keywords="mouse speed acceleration double click keyboard repeat delay touchpad wheel")
def _input(p):
    spi = ctypes.windll.user32.SystemParametersInfoW

    def get(action):
        v = wt.UINT()
        spi(action, 0, ctypes.byref(v), 0)
        return v.value
    accel = (ctypes.c_int * 3)()
    spi(0x0003, 0, accel, 0)
    return [{"name": "pointer speed (1-20)", "value": get(0x0070)}, {"name": "double-click time (ms)", "value": ctypes.windll.user32.GetDoubleClickTime()},
            {"name": "key repeat delay (0-3)", "value": get(0x0016)}, {"name": "key repeat speed (0-31)", "value": get(0x000A)},
            {"name": "wheel scroll lines", "value": get(0x0068)}, {"name": "pointer precision (acceleration)", "value": int(accel[2])}]


@probe("accessibility", "Accessibility settings", "Accessibility automation", key="name",
       keywords="screen reader narrator magnifier high contrast captions sticky keys text size cursor size color filters")
def _a11y(p):
    import winreg

    def rv(path, name, hive=winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, path) as k:
                return winreg.QueryValueEx(k, name)[0]
        except OSError:
            return None

    class SK(ctypes.Structure):
        _fields_ = [("cbSize", wt.UINT), ("dwFlags", wt.DWORD)]
    sk = SK(ctypes.sizeof(SK), 0)
    ctypes.windll.user32.SystemParametersInfoW(0x003A, ctypes.sizeof(sk), ctypes.byref(sk), 0)
    return [{"name": "text size %", "value": rv(r"Software\Microsoft\Accessibility", "TextScaleFactor") or 100},
            {"name": "pointer size", "value": rv(r"Control Panel\Cursors", "CursorBaseSize") or 32},
            {"name": "sticky keys", "value": "on" if sk.dwFlags & 1 else "off"},
            {"name": "high contrast theme", "value": rv(r"Control Panel\Accessibility\HighContrast", "Flags") and ("on" if int(rv(r"Control Panel\Accessibility\HighContrast", "Flags")) & 1 else "off")},
            {"name": "colour filter", "value": "on" if rv(r"Software\Microsoft\ColorFiltering", "Active") == 1 else "off"},
            {"name": "magnifier zoom %", "value": rv(r"Software\Microsoft\ScreenMagnifier", "Magnification")},
            {"name": "narrator at sign-in", "value": rv(r"Software\Microsoft\Narrator\NoRoam", "RunningState")},
            {"name": "transparency effects", "value": rv(r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "EnableTransparency")},
            {"name": "dark mode (apps)", "value": "off" if rv(r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "AppsUseLightTheme") == 1 else "on"}]


# ---- power, storage, backup ---------------------------------------------------------------------------------------
@probe("battery", "Battery and power", "Power and thermal management", key="name", numbers=("percent",), attention=("percent < 20 and plugged == False",),
       keywords="battery charge power plan ac adapter sleep")
def _battery(p):
    from ..toolbox.t_system import SYSTEM_POWER_STATUS, power_plan
    s = SYSTEM_POWER_STATUS()
    ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s))
    pct = s.BatteryLifePercent & 0xFF
    return [{"name": "battery", "percent": None if pct == 255 else pct, "plugged": s.ACLineStatus == 1, "saver": bool(s.SystemStatusFlag & 1),
             "plan": power_plan().removeprefix("Power plan: ").rstrip(".")}]


@probe("cpu_memory", "Processor and memory load", "Power and thermal management", key="name", numbers=("cpu_percent", "memory_percent"),
       attention=("memory_percent > 90",), keywords="cpu load memory ram usage thermal performance")
def _load(p):
    from ..toolbox import t_system as s
    cpu = int(re.search(r"\d+", s.cpu_usage()).group(0))
    return [{"name": "this pc", "cpu_percent": cpu, "memory_percent": s.memory().dwMemoryLoad}]


@probe("volumes", "Drives and free space", "Storage management", key="drive", numbers=("free_gb", "free_percent"), attention=("free_percent < 10",),
       keywords="disk space free storage drives volumes capacity")
def _vols(p):
    import shutil
    out = []
    for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        root = f"{letter}:\\"
        if os.path.exists(root):
            try:
                u = shutil.disk_usage(root)
            except OSError:
                continue
            out.append({"drive": letter + ":", "free_gb": round(u.free / 1e9, 1), "total_gb": round(u.total / 1e9, 1), "free_percent": round(u.free / u.total * 100, 1)})
    return out


@probe("disk_health", "Disk health (SMART summary)", "Storage management", key="name", attention=("health != Healthy",),
       keywords="disk smart health ssd hdd physical disk failure")
def _disks(p):
    rows = ps("Get-PhysicalDisk | Select-Object FriendlyName, MediaType, HealthStatus, OperationalStatus, BusType, @{n='size_gb';e={[math]::Round($_.Size/1e9)}}" + J(""))
    return [{"name": r.get("FriendlyName"), "type": r.get("MediaType"), "health": r.get("HealthStatus"), "status": r.get("OperationalStatus"),
             "bus": r.get("BusType"), "size_gb": r.get("size_gb")} for r in rows]


@probe("folder_sizes", "Sizes of your main folders", "Storage management", key="folder", numbers=("size_gb", "files"),
       keywords="folder size downloads documents desktop pictures videos growth", slow=True)
def _folders(p):
    from ..toolbox.t_files import special, walk_files
    out = []
    for name in (p.get("folders") or "downloads,documents,desktop,pictures,videos,music").split(","):
        root = special(name.strip()) or Path(name.strip())
        if not root.exists():
            continue
        total = n = 0
        for f in walk_files(root, 300_000):
            try:
                total += f.stat().st_size
                n += 1
            except OSError:
                pass
        out.append({"folder": name.strip(), "size_gb": round(total / 1e9, 2), "files": n})
    return out


@probe("cleanup", "Space you could free (temp, recycle bin, downloads)", "Storage management", key="name", numbers=("size_mb",),
       keywords="temp files cache recycle bin cleanup junk")
def _cleanup(p):
    from ..toolbox.t_files import special, walk_files
    out = []
    for label, root in (("Temp files", Path(os.environ.get("TEMP", ""))), ("Downloads", special("downloads"))):
        total = 0
        for f in walk_files(root, 200_000):
            try:
                total += f.stat().st_size
            except OSError:
                pass
        out.append({"name": label, "size_mb": round(total / 1e6)})

    class RB(ctypes.Structure):
        _fields_ = [("cbSize", wt.DWORD), ("i64Size", ctypes.c_longlong), ("i64NumItems", ctypes.c_longlong)]
    rb = RB(ctypes.sizeof(RB), 0, 0)
    ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(rb))
    out.append({"name": "Recycle Bin", "size_mb": round(rb.i64Size / 1e6)})
    return out


@probe("backup_status", "Backup status (OneDrive, File History, restore)", "Backup and recovery", key="name",
       attention=("ok == False",), keywords="backup onedrive file history restore points sync recovery")
def _backup(p):
    from ..toolbox.t_system import processes
    home = Path(os.environ.get("USERPROFILE", ""))
    od = home / "OneDrive"
    running = {n.lower() for n, _, _ in processes()}
    fh = ps("Get-CimInstance -Namespace root/Microsoft/Windows/FileHistory -ClassName MSFT_FhConfigInfo | Select-Object TargetUrl" + J(""))
    return [{"name": "OneDrive folder", "ok": od.exists(), "detail": str(od) if od.exists() else "not set up"},
            {"name": "OneDrive running", "ok": "onedrive.exe" in running, "detail": ""},
            {"name": "File History", "ok": bool(fh), "detail": (fh[0].get("TargetUrl") if fh else "off or not available")}]


# ---- security, privacy, identity ----------------------------------------------------------------------------------
@probe("defender", "Microsoft Defender protection", "Security posture checks", key="name", attention=("ok == False",),
       keywords="antivirus defender real time protection signatures malware threats security")
def _defender(p):
    r = ps("Get-MpComputerStatus | Select-Object AMServiceEnabled, AntivirusEnabled, RealTimeProtectionEnabled, AntivirusSignatureAge, QuickScanAge, IsTamperProtected" + J(""))
    if not r:
        return [{"name": "Defender", "ok": False, "detail": "status not available (another antivirus may be in charge)"}]
    s = r[0]
    return [{"name": "real-time protection", "ok": bool(s.get("RealTimeProtectionEnabled")), "detail": ""},
            {"name": "antivirus on", "ok": bool(s.get("AntivirusEnabled")), "detail": ""},
            {"name": "virus definitions age (days)", "ok": (s.get("AntivirusSignatureAge") or 0) <= 3, "detail": s.get("AntivirusSignatureAge")},
            {"name": "days since quick scan", "ok": (s.get("QuickScanAge") or 0) <= 14, "detail": s.get("QuickScanAge")},
            {"name": "tamper protection", "ok": bool(s.get("IsTamperProtected")), "detail": ""}]


@probe("threats", "Threats Defender found", "Security operations center", key="id", attention=("count > 0",),
       keywords="threats detections malware quarantine soc alerts")
def _threats(p):
    rows = ps("Get-MpThreatDetection | Select-Object ThreatID, @{n='time';e={$_.InitialDetectionTime.ToString('s')}}, ActionSuccess, @{n='resources';e={($_.Resources -join '; ')}}" + J(""))
    return [{"id": f"{r.get('ThreatID')}/{r.get('time')}", "time": r.get("time"), "handled": r.get("ActionSuccess"), "files": (r.get("resources") or "")[:200], "count": 1} for r in rows]


@probe("firewall", "Firewall on/off by network type", "Security posture checks", key="name", attention=("enabled == False",),
       keywords="firewall profiles rules network security")
def _firewall(p):
    rows = ps("Get-NetFirewallProfile | Select-Object Name, Enabled, DefaultInboundAction" + J(""))
    return [{"name": r.get("Name"), "enabled": bool(r.get("Enabled")), "inbound_default": str(r.get("DefaultInboundAction"))} for r in rows]


@probe("security_settings", "UAC, SmartScreen and sign-in safety", "Security posture checks", key="name", attention=("ok == False",),
       keywords="uac smartscreen security posture secure boot settings")
def _secset(p):
    import winreg

    def rv(hive, path, name):
        try:
            with winreg.OpenKey(hive, path) as k:
                return winreg.QueryValueEx(k, name)[0]
        except OSError:
            return None
    uac = rv(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", "EnableLUA")
    smart = rv(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer", "SmartScreenEnabled")
    return [{"name": "User Account Control", "ok": uac != 0, "detail": uac},
            {"name": "SmartScreen for apps", "ok": smart in (None, "RequireAdmin", "Prompt", "Warn"), "detail": smart}]


@probe("listening_ports", "Programs listening on network ports", "Security posture checks", key="port",
       keywords="open ports listening exposed services network")
def _ports(p):
    from ..toolbox.t_system import listening_ports
    out = []
    for line in listening_ports():
        m = re.match(r"port (\d+) \((.+?)\): (.*)", line)
        if m:
            out.append({"port": int(m.group(1)), "scope": m.group(2), "program": m.group(3)})
    return out


@probe("startup_apps", "Programs that start at sign-in", "Application lifecycle", key="name", keywords="startup apps autostart boot login")
def _startup(p):
    from ..toolbox.t_system import startup_apps
    return [{"name": s} for s in startup_apps()]


@probe("app_permissions", "Apps allowed to use camera, microphone, location", "Privacy controls", key="name",
       keywords="privacy permissions camera microphone location app access consent")
def _perms(p):
    import winreg
    out = []
    base = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore"
    for cap in ("webcam", "microphone", "location", "contacts", "screenshot"):
        for hive in (winreg.HKEY_CURRENT_USER,):
            for sub in ("", "NonPackaged"):
                path = base + "\\" + cap + ("\\" + sub if sub else "")
                try:
                    with winreg.OpenKey(hive, path) as k:
                        for i in range(winreg.QueryInfoKey(k)[0]):
                            app = winreg.EnumKey(k, i)
                            if app == "NonPackaged":
                                continue
                            try:
                                with winreg.OpenKey(k, app) as a:
                                    v = winreg.QueryValueEx(a, "Value")[0]
                            except OSError:
                                v = "?"
                            out.append({"name": f"{cap}: {app.replace('#', chr(92))[-80:]}", "capability": cap, "allowed": v == "Allow"})
                except OSError:
                    pass
    return out


@probe("accounts", "Local accounts and administrators", "Identity and accounts", key="name", attention=("admin == True and enabled == True",),
       keywords="users accounts administrators identity local user password")
def _accounts(p):
    users = ps("Get-LocalUser | Select-Object Name, Enabled, @{n='last_logon';e={if($_.LastLogon){$_.LastLogon.ToString('s')}}}, PasswordRequired" + J(""))
    admins = {str(a.get("Name", "")).split("\\")[-1].lower() for a in ps("Get-LocalGroupMember -SID S-1-5-32-544 | Select-Object Name" + J(""))}
    return [{"name": u.get("Name"), "enabled": bool(u.get("Enabled")), "admin": str(u.get("Name", "")).lower() in admins,
             "last_logon": u.get("last_logon"), "password_required": u.get("PasswordRequired")} for u in users]


@probe("saved_credentials", "Saved Windows credentials (names only)", "Identity and accounts", key="target",
       keywords="saved credentials credential manager passwords stored targets")
def _creds(p):
    out = subprocess.run(["cmdkey", "/list"], capture_output=True, timeout=20, creationflags=NO_WINDOW).stdout.decode("utf-8", "replace")
    return [{"target": m.strip()} for m in re.findall(r"Target:\s*(.+)", out)]


# ---- apps, dev, containers ---------------------------------------------------------------------------------------
@probe("installed_apps", "Installed programs and versions", "Application lifecycle", key="name", keywords="installed apps software versions uninstall inventory")
def _apps(p):
    from ..toolbox.t_system import _uninstall_entries
    return [{"name": n, "version": v} for n, v in sorted(_uninstall_entries().items())]


@probe("app_updates", "Apps with updates available (winget)", "Application lifecycle", key="name", attention=("count > 0",),
       keywords="app updates upgrade available winget outdated software", slow=True)
def _upgrades(p):
    try:
        out = subprocess.run(["winget", "upgrade", "--accept-source-agreements"], capture_output=True, timeout=120, creationflags=NO_WINDOW).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        return []
    rows, started = [], False
    for line in out.splitlines():
        if line.startswith("---"):
            started = True
            continue
        if started and line.strip() and not re.match(r"\d+ upgrades? available", line.strip()):
            parts = re.split(r"\s{2,}", line.strip())
            if len(parts) >= 4:
                rows.append({"name": parts[0], "id": parts[1], "version": parts[2], "available": parts[3], "count": 1})
    return rows


@probe("processes", "Running programs by memory", "Application lifecycle", key="name", numbers=("memory_mb",),
       keywords="processes running programs memory usage task manager")
def _procs(p):
    from ..toolbox.t_system import processes
    agg = {}
    for n, pid, mem in processes():
        a = agg.setdefault(n, {"name": n, "instances": 0, "memory_mb": 0})
        a["instances"] += 1
        a["memory_mb"] += round(mem / 1e6)
    return sorted(agg.values(), key=lambda r: -r["memory_mb"])[:80]


@probe("git_repos", "Your git projects (workspaces): branch and changes", "Git and code review", key="name", numbers=("changed",),
       keywords="git repositories branch uncommitted changes ahead behind code review workspace")
def _git(p, ctx_workspaces=None):
    from ..toolbox.t_dev import git
    out = []
    ws = p.get("_workspaces") or {}
    for name, path in ws.items():
        root = Path(path)
        if not (root / ".git").exists():
            continue
        try:
            st = git(root, "status", "--porcelain", "--branch")
        except Exception:
            continue
        lines = st.splitlines()
        head = lines[0] if lines else ""
        ab = re.search(r"\[(.*?)\]", head)
        out.append({"name": name, "branch": head.replace("## ", "").split("...")[0], "changed": len(lines) - 1, "ahead_behind": ab.group(1) if ab else ""})
    return out


@probe("docker", "Docker containers", "Containers and virtualization", key="name", keywords="docker containers images running stopped virtualization")
def _docker(p):
    try:
        out = subprocess.run(["docker", "ps", "-a", "--format", "{{json .}}"], capture_output=True, timeout=30, creationflags=NO_WINDOW).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        return []
    rows = []
    for l in out.splitlines():
        try:
            d = json.loads(l)
            rows.append({"name": d.get("Names"), "image": d.get("Image"), "state": d.get("State"), "status": d.get("Status")})
        except ValueError:
            pass
    return rows


@probe("wsl", "WSL Linux distributions", "Containers and virtualization", key="name", keywords="wsl linux distributions virtualization")
def _wsl(p):
    try:
        raw = subprocess.run(["wsl", "-l", "-v"], capture_output=True, timeout=30, creationflags=NO_WINDOW).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    text = raw.decode("utf-16-le", errors="ignore") if b"\x00" in raw else raw.decode("utf-8", "replace")
    rows = []
    for l in text.splitlines()[1:]:
        parts = l.replace("*", " ").split()
        if len(parts) >= 3:
            rows.append({"name": parts[0], "state": parts[1], "version": parts[2], "default": "*" in l})
    return rows


@probe("gpu", "Graphics cards and drivers", "AI and machine learning operations", key="name", keywords="gpu graphics card cuda video memory ai ml")
def _gpu(p):
    rows = ps("Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, @{n='vram_gb';e={[math]::Round($_.AdapterRAM/1GB,1)}}, CurrentHorizontalResolution, CurrentVerticalResolution" + J(""))
    return [{"name": r.get("Name"), "driver": r.get("DriverVersion"), "vram_gb": r.get("vram_gb"),
             "resolution": f"{r.get('CurrentHorizontalResolution')}x{r.get('CurrentVerticalResolution')}"} for r in rows]


@probe("local_ai", "Local AI services (FreeLLMAPI, Kokoro, Whisper, Ollama)", "AI and machine learning operations", key="name",
       attention=("up == False",), keywords="local ai models ollama llm service health whisper kokoro inference")
def _local_ai(p):
    import socket
    out = []
    for name, port in (("FreeLLMAPI", 31415), ("Kokoro voice", 31416), ("Whisper speech", 31417), ("Ollama", 11434)):
        s = socket.socket()
        s.settimeout(0.5)
        up = s.connect_ex(("127.0.0.1", port)) == 0
        s.close()
        out.append({"name": name, "port": port, "up": up})
    return out


# ---- network ------------------------------------------------------------------------------------------------------
@probe("network_adapters", "Network adapters", "Network diagnostics", key="name", attention=("status == Disconnected and physical == True",),
       keywords="network adapters ethernet wifi link speed connection vpn")
def _adapters(p):
    rows = ps("Get-NetAdapter | Select-Object Name, InterfaceDescription, Status, LinkSpeed, MacAddress, @{n='physical';e={$_.HardwareInterface}}" + J(""))
    return [{"name": r.get("Name"), "device": r.get("InterfaceDescription"), "status": r.get("Status"), "speed": r.get("LinkSpeed"),
             "physical": bool(r.get("physical"))} for r in rows]


@probe("ip_config", "IP addresses, gateways and DNS", "Network diagnostics", key="name", keywords="ip address gateway dns servers configuration")
def _ipconf(p):
    rows = ps("Get-NetIPConfiguration | Where-Object { $_.IPv4Address } | Select-Object InterfaceAlias, @{n='ip';e={$_.IPv4Address.IPAddress -join ', '}}, "
              "@{n='gateway';e={$_.IPv4DefaultGateway.NextHop -join ', '}}, @{n='dns';e={$_.DNSServer.ServerAddresses -join ', '}}" + J(""))
    return [{"name": r.get("InterfaceAlias"), "ip": r.get("ip"), "gateway": r.get("gateway"), "dns": r.get("dns")} for r in rows]


@probe("wifi", "Wi-Fi connection quality", "Network diagnostics", key="name", numbers=("signal",), attention=("signal < 40",),
       keywords="wifi signal strength wireless connection quality")
def _wifi(p):
    from ..toolbox.t_system import wifi_status_dict
    d = wifi_status_dict()
    sig = re.search(r"\d+", d.get("signal", "") or "")
    return [{"name": d.get("wifi"), "signal": int(sig.group(0)) if sig else None, "speed": d.get("speed"), "band": d.get("band")}]


@probe("latency", "Internet latency to key sites", "Network diagnostics", key="name", numbers=("ms",), attention=("ms > 300",),
       keywords="latency ping internet speed slow connection response time", slow=True)
def _latency(p):
    from .. import internet
    out = []
    for site in (p.get("sites") or "google.com,cloudflare.com,github.com").split(","):
        site = site.strip()
        try:
            r = internet.request("https://" + site, method="HEAD", timeout=8)
            out.append({"name": site, "ms": round(r.elapsed * 1000), "status": r.status})
        except internet.NetError as e:
            out.append({"name": site, "ms": None, "status": str(e)[:60]})
    return out


@probe("wifi_profiles", "Saved Wi-Fi networks", "Network administration", key="name", keywords="wifi profiles saved networks")
def _wprof(p):
    out = subprocess.run(["netsh", "wlan", "show", "profiles"], capture_output=True, timeout=20, creationflags=NO_WINDOW).stdout.decode("utf-8", "replace")
    return [{"name": m.strip()} for m in re.findall(r"All User Profile\s*:\s*(.+)", out)]


@probe("proxy_hosts", "Proxy settings and hosts-file entries", "Network administration", key="name",
       keywords="proxy hosts file dns override network settings")
def _proxy(p):
    import winreg
    out = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings") as k:
            en = winreg.QueryValueEx(k, "ProxyEnable")[0]
            try:
                srv = winreg.QueryValueEx(k, "ProxyServer")[0]
            except OSError:
                srv = ""
        out.append({"name": "proxy", "value": srv if en else "off"})
    except OSError:
        pass
    hosts = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"
    try:
        for l in hosts.read_text(encoding="utf-8", errors="ignore").splitlines():
            if l.strip() and not l.strip().startswith("#"):
                out.append({"name": "hosts: " + " ".join(l.split()[1:2]), "value": l.split()[0]})
    except OSError:
        pass
    return out


# ---- browser, office, knowledge, personal -------------------------------------------------------------------------
@probe("browsers", "Browsers, versions and extensions", "Web browser management", key="name",
       keywords="browser versions extensions default chrome edge firefox")
def _browsers(p):
    from ..toolbox.t_system import _uninstall_entries
    from ..toolbox.t_extra import default_browser
    out = [{"name": f"{n} {v}".strip(), "kind": "browser"} for n, v in _uninstall_entries().items()
           if re.search(r"chrome|edge|firefox|brave|opera|vivaldi", n, re.I) and not re.search(r"update|webview", n, re.I)]
    out.append({"name": "default: " + default_browser(), "kind": "default"})
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    for label, base in (("Chrome", local / "Google/Chrome/User Data/Default/Extensions"), ("Edge", local / "Microsoft/Edge/User Data/Default/Extensions")):
        if base.is_dir():
            for ext in base.iterdir():
                man = next(ext.glob("*/manifest.json"), None)
                try:
                    nm = json.loads(man.read_text(encoding="utf-8", errors="ignore")).get("name", ext.name) if man else ext.name
                except ValueError:
                    nm = ext.name
                if not str(nm).startswith("__MSG_"):
                    out.append({"name": f"{label} extension: {nm}", "kind": "extension"})
    return out


@probe("recent_files", "Files you used recently", "Office productivity", key="name", keywords="recent documents office files opened word excel")
def _recent(p):
    rec = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Recent"
    items = sorted((f for f in rec.glob("*.lnk")), key=lambda f: -f.stat().st_mtime)[:60] if rec.is_dir() else []
    from datetime import datetime
    return [{"name": f.stem, "used": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")} for f in items]


@probe("printers", "Printers and print queue", "Personal devices and peripherals", key="name", numbers=("jobs",), attention=("jobs > 0",),
       keywords="printer print queue jobs status scanner")
def _printers(p):
    rows = ps("Get-Printer | Select-Object Name, PrinterStatus, Default, @{n='jobs';e={(Get-PrintJob -PrinterName $_.Name | Measure-Object).Count}}" + J(""))
    return [{"name": r.get("Name"), "status": str(r.get("PrinterStatus")), "jobs": r.get("jobs") or 0} for r in rows]


@probe("echo", "Echo itself: tools, MCP servers, memories, lists", "Local assistant capabilities", key="name",
       keywords="echo assistant status tools mcp servers memories lists notes timers")
def _echo(p):
    from .. import toolbox
    out = [{"name": "built-in tools", "value": len(toolbox.load())}]
    try:
        from ..storage import ListStore, MemoryStore, Settings
        s = Settings()
        out += [{"name": "MCP servers", "value": len([x for x in (s["mcp_servers"] or []) if isinstance(x, dict)])},
                {"name": "internet access", "value": s["internet_access"]}, {"name": "memories", "value": len(MemoryStore().all())}]
        ls = ListStore()
        out += [{"name": "lists", "value": len(ls.lists)}, {"name": "notes", "value": len(ls.notes)}]
    except Exception:
        pass
    return out


@probe("games", "Installed Steam games", "Gaming and streaming", key="name", numbers=("size_gb",), keywords="games steam library installed gaming")
def _games(p):
    roots = [Path(os.environ.get("ProgramFiles(x86)", "")) / "Steam" / "steamapps"]
    lib = roots[0] / "libraryfolders.vdf"
    if lib.exists():
        roots += [Path(m.replace("\\\\", "\\")) / "steamapps" for m in re.findall(r'"path"\s+"([^"]+)"', lib.read_text(encoding="utf-8", errors="ignore"))]
    out = {}
    for r in roots:
        for acf in r.glob("appmanifest_*.acf") if r.is_dir() else []:
            t = acf.read_text(encoding="utf-8", errors="ignore")
            name = re.search(r'"name"\s+"([^"]+)"', t)
            size = re.search(r'"SizeOnDisk"\s+"(\d+)"', t)
            if name:
                out[name.group(1)] = {"name": name.group(1), "size_gb": round(int(size.group(1)) / 1e9, 1) if size else None}
    return list(out.values())


@probe("audio_video_devices", "Microphones, speakers and cameras", "Audio processing", key="device",
       keywords="audio devices microphone speaker headset camera webcam video")
def _av(p):
    return _devices({"classes": "AudioEndpoint,MEDIA,Camera,Image"})
