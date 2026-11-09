"""PC control pack: keyboard shortcuts, typed punctuation, mouse, windows, apps, clipboard text tools and a few
system switches, for people who can't (or would rather not) use the keyboard and mouse.

Everything runs quietly through Win32 (SendInput, window messages, the registry for your own user): no console or
helper window flashes up, and Echo doesn't take the focus from the app you're working in. Every target comes from the
catalog's fixed tables; spoken words only fill numbers. Commands marked "confirm" ask first.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import re
import subprocess
import time
from typing import Callable, Optional

from . import catalog, typer
from .words import many, preview

KINDS = {"keys", "text", "mouse", "window", "app_window", "clip", "sys"}
QUIET_SAY = {"READ", "COUNT", "SPELL_OUT", "which", "list", "where", "BRIGHTNESS_GET", "IDLE_TIME", "OPEN_WINDOWS_COUNT",
             "READ_SELECTION", "JSON_CHECK", "JWT_DECODE", "SUM_NUMBERS", "COUNT_LINES", "DCLICK_GET", "POINTER_GET"}
NO_WINDOW = 0x08000000


def is_quiet(command) -> bool:
    """Quiet = just do it and show a small caption by the orb; informational commands still answer aloud."""
    op = command.spec.get("op")
    return command.kind in KINDS and op not in QUIET_SAY


def fill_text(text: str, now=None) -> str:
    """{date} {time} {day} {iso} {tomorrow} in typed text."""
    from datetime import datetime, timedelta
    now = now or datetime.now()
    values = {"{date}": f"{now.day} {now:%B %Y}", "{time}": now.strftime("%I:%M %p").lstrip("0"), "{day}": f"{now:%A}",
              "{iso}": f"{now:%Y-%m-%d}", "{tomorrow}": f"{(now + timedelta(days=1)).day} {(now + timedelta(days=1)):%B %Y}"}
    for token, value in values.items():
        text = text.replace(token, value)
    return text


def number(slots: dict, key: str = "n", default: int = 1, low: int = 1, high: int = 100) -> int:
    try:
        return max(low, min(int(float(slots.get(key, default))), high))
    except (TypeError, ValueError):
        return default


# ------------------------------------------------------------------------------------------------ Win32 helpers
u32 = ctypes.WinDLL("user32", use_last_error=True) if os.name == "nt" else None


class RECT(ctypes.Structure):
    _fields_ = [("left", wt.LONG), ("top", wt.LONG), ("right", wt.LONG), ("bottom", wt.LONG)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", wt.DWORD)]


def _dpi_aware():
    try:
        u32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        pass


def _setup():
    u32.GetForegroundWindow.restype = wt.HWND
    u32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(RECT)]
    u32.MonitorFromWindow.argtypes = [wt.HWND, wt.DWORD]
    u32.MonitorFromWindow.restype = wt.HANDLE
    u32.GetMonitorInfoW.argtypes = [wt.HANDLE, ctypes.POINTER(MONITORINFO)]
    u32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
    u32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
    u32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    u32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
    u32.IsWindowVisible.argtypes = [wt.HWND]
    u32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
    u32.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, wt.LONG]
    u32.SetLayeredWindowAttributes.argtypes = [wt.HWND, wt.DWORD, ctypes.c_byte, wt.DWORD]
    u32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
    u32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]


if u32 is not None:
    _setup()


def foreground():
    return u32.GetForegroundWindow()


def title(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    u32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


def work_area(hwnd) -> RECT:
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    u32.GetMonitorInfoW(u32.MonitorFromWindow(hwnd, 2), ctypes.byref(info))
    return info.rcWork


def process_name(hwnd) -> str:
    pid = wt.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    k = ctypes.windll.kernel32
    k.OpenProcess.restype = wt.HANDLE
    h = k.OpenProcess(0x1000, False, pid.value)          # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(520)
        size = wt.DWORD(520)
        k.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
        if k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
        return ""
    finally:
        k.CloseHandle(h)


def top_windows() -> list:
    """Visible, titled, top-level app windows (hwnd, title, process name), front to back."""
    found = []
    proc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def cb(hwnd, _):
        if u32.IsWindowVisible(hwnd) and not u32.GetWindow(hwnd, 4):          # GW_OWNER: skip owned popups
            t = title(hwnd)
            ex = u32.GetWindowLongW(hwnd, -20)
            if t and not ex & 0x80 and t not in ("Program Manager",):         # skip tool windows
                found.append((hwnd, t, process_name(hwnd)))
        return True
    u32.GetWindow.argtypes = [wt.HWND, wt.UINT]
    u32.EnumWindows(proc(cb), 0)
    me = os.getpid()
    out = []
    for hwnd, t, p in found:
        pid = wt.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value != me:
            out.append((hwnd, t, p))
    return out


# ------------------------------------------------------------------------------------------------ kinds
def run(command, slots: dict, confirm: Callable[[str, str], bool], focus, open_app: Callable[[str], tuple]) -> tuple:
    """(ok, message) for the PC-control kinds. `focus` is typer.FocusTracker (the app you were using)."""
    spec, kind = command.spec, command.kind
    say = catalog.fill(command.say, slots) if command.say else None
    if spec.get("confirm") and not confirm(command.title, spec["confirm"]):
        return True, "Okay, I didn't do that."
    if kind not in ("app_window", "sys") and focus is not None:
        focus.focus_target()
    if kind == "keys":
        keys = spec["keys"]
        if "{n}" in keys:
            keys = keys.replace("{n}", str(number(slots, "n", 1, 1, 9)))
        times = number(slots, "n", 1, 1, 50) if spec.get("repeat") else 1
        typer.press(keys, times)
        return True, say or (command.title + (f" ×{times}" if times > 1 else "") + ".")
    if kind == "text":
        text = fill_text(spec["text"])
        if typer.plan(text) == "paste":
            typer.paste(text)
        else:
            typer.send_keys(text)
        return True, say or f"Typed {preview(text)}"
    if kind == "mouse":
        return mouse(spec["op"], slots, spec)
    if kind == "window":
        return window(spec["op"])
    if kind == "app_window":
        return app_window(spec["op"], spec["app"], open_app)
    if kind == "clip":
        return clip(spec["op"])
    if kind == "sys":
        return system(spec["op"], slots, confirm)
    return False, "EchoDesktop can't do that."


# ---- mouse
MOUSE = {"left": (0x0002, 0x0004), "right": (0x0008, 0x0010), "middle": (0x0020, 0x0040)}


def _mouse_event(flags: int, data: int = 0):
    i = typer._INPUT()
    i.type = 0
    i.mi = typer._MOUSEINPUT(0, 0, ctypes.c_ulong(data & 0xFFFFFFFF).value, flags, 0, 0)
    return i


def mouse(op: str, slots: dict, spec: dict) -> tuple:
    _dpi_aware()
    pt = wt.POINT()
    u32.GetCursorPos(ctypes.byref(pt))
    step = number(slots, "n", int(spec.get("amount", 100)), 1, 3000)
    clicks = {"click": ("left", 1), "double_click": ("left", 2), "triple_click": ("left", 3), "right_click": ("right", 1),
              "middle_click": ("middle", 1)}
    if op in clicks:
        button, n = clicks[op]
        down, up = MOUSE[button]
        typer._send([_mouse_event(down), _mouse_event(up)] * n)
        return True, op.replace("_", " ").capitalize() + "."
    if op == "hold":
        typer._send([_mouse_event(MOUSE["left"][0])])
        return True, "Holding the mouse button. Say “release” to drop."
    if op == "release":
        typer._send([_mouse_event(MOUSE["left"][1])])
        return True, "Released."
    if op.startswith("scroll_"):
        notches = number(slots, "n", 3, 1, 50)
        if op in ("scroll_up", "scroll_down"):
            typer._send([_mouse_event(0x0800, 120 * notches * (1 if op == "scroll_up" else -1))])
        else:
            typer._send([_mouse_event(0x01000, 120 * notches * (1 if op == "scroll_right" else -1))])
        return True, f"Scrolled {op[7:]}."
    sw, sh = u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)
    if op.startswith("move_"):
        dx = {"move_left": -step, "move_right": step}.get(op, 0)
        dy = {"move_up": -step, "move_down": step}.get(op, 0)
        x, y = pt.x + dx, pt.y + dy
    elif op == "center":
        x, y = sw // 2, sh // 2
    elif op in ("top_left", "top_right", "bottom_left", "bottom_right"):
        x = 20 if "left" in op else sw - 20
        y = 20 if "top" in op else sh - 20
    elif op == "window_center":
        r = RECT()
        u32.GetWindowRect(foreground(), ctypes.byref(r))
        x, y = (r.left + r.right) // 2, (r.top + r.bottom) // 2
    elif op == "at":
        # spoken as percent across and down, so it works on any screen size ("mouse to 50 30")
        x, y = sw * number(slots, "n", 50, 0, 100) // 100, sh * number(slots, "n2", 50, 0, 100) // 100
    elif op in ("faster", "slower"):
        speed = ctypes.c_int()
        ctypes.windll.user32.SystemParametersInfoW(0x70, 0, ctypes.byref(speed), 0)
        new = max(1, min(20, speed.value + (3 if op == "faster" else -3)))
        ctypes.windll.user32.SystemParametersInfoW(0x71, 0, ctypes.c_void_p(new), 3)
        return True, f"Pointer speed {new} of 20."
    elif op == "where":
        return True, f"The pointer is {100 * pt.x // max(sw, 1)} percent across and {100 * pt.y // max(sh, 1)} percent down."
    else:
        return False, "Unknown mouse action."
    u32.SetCursorPos(max(0, min(x, sw - 1)), max(0, min(y, sh - 1)))
    return True, "Moved the pointer."


# ---- windows
def _place(hwnd, x, y, w, h):
    u32.ShowWindow(hwnd, 9)                                   # restore first, so maximized windows can move
    u32.SetWindowPos(hwnd, None, int(x), int(y), int(w), int(h), 0x0004 | 0x0040)   # NOZORDER | SHOWWINDOW


def window(op: str) -> tuple:
    _dpi_aware()
    if op == "list":
        wins = top_windows()
        names = [t for _, t, _ in wins][:12]
        return True, (f"{len(wins)} windows open: " + "; ".join(names) + ".") if names else "No app windows are open."
    hwnd = foreground()
    if not hwnd:
        return False, "No window is active."
    name = title(hwnd) or "the window"
    if op == "which":
        return True, f"You're in {name}."
    if op == "maximize":
        u32.ShowWindow(hwnd, 3)
    elif op == "minimize":
        u32.ShowWindow(hwnd, 6)
    elif op == "restore":
        u32.ShowWindow(hwnd, 9)
    elif op == "close":
        u32.PostMessageW(hwnd, 0x0010, 0, 0)                  # WM_CLOSE: the app can still ask to save
    elif op == "minimize_others":
        for h, _, _ in top_windows():
            if h != hwnd:
                u32.ShowWindow(h, 6)
    elif op in ("on_top", "not_on_top"):
        u32.SetWindowPos(hwnd, wt.HWND(-1 if op == "on_top" else -2), 0, 0, 0, 0, 0x0001 | 0x0002)
    elif op in ("transparent", "opaque"):
        ex = u32.GetWindowLongW(hwnd, -20)
        u32.SetWindowLongW(hwnd, -20, ex | 0x00080000)          # WS_EX_LAYERED
        u32.SetLayeredWindowAttributes(hwnd, 0, ctypes.c_byte(190 if op == "transparent" else 255).value, 2)
    else:
        a = work_area(hwnd)
        W, H, L, T = a.right - a.left, a.bottom - a.top, a.left, a.top
        layouts = {"snap_left": (L, T, W // 2, H), "snap_right": (L + W // 2, T, W - W // 2, H),
                   "snap_top_left": (L, T, W // 2, H // 2), "snap_top_right": (L + W // 2, T, W - W // 2, H // 2),
                   "snap_bottom_left": (L, T + H // 2, W // 2, H - H // 2),
                   "snap_bottom_right": (L + W // 2, T + H // 2, W - W // 2, H - H // 2),
                   "top_half": (L, T, W, H // 2), "bottom_half": (L, T + H // 2, W, H - H // 2)}
        if op in layouts:
            _place(hwnd, *layouts[op])
        else:
            r = RECT()
            u32.GetWindowRect(hwnd, ctypes.byref(r))
            w, h = r.right - r.left, r.bottom - r.top
            if op == "bigger":
                w, h = min(W, int(w * 1.15)), min(H, int(h * 1.15))
            elif op == "smaller":
                w, h = max(320, int(w * 0.85)), max(240, int(h * 0.85))
            elif op != "center":
                return False, "Unknown window action."
            _place(hwnd, L + (W - w) // 2, T + (H - h) // 2, w, h)
    short = (name[:50].rstrip(" -–—|:·") + "…") if len(name) > 50 else name.rstrip(" -–—|:·")   # no dangling " - ."
    return True, f"{op.replace('_', ' ').capitalize()}: {short or name[:50]}."


# ---- apps
LAUNCH_WAIT = 90.0          # seconds to wait for a starting app's window (games and busy disks can be slow)
_SKIP_WORDS = {"the", "app", "microsoft", "windows", "desktop", "for", "and", "player", "beta"}


def window_handles() -> set:
    try:
        return {h for h, _, _ in top_windows()}
    except Exception:
        return set()


def name_keys(label: str) -> list:
    """Words that identify an app's window or process ("Roblox Player" -> ["roblox"], "WhatsApp" -> ["whatsapp"])."""
    words = [w for w in re.findall(r"[a-z0-9]+", label.lower()) if len(w) >= 3 and w not in _SKIP_WORDS]
    return words[:2] or [re.sub(r"[^a-z0-9]", "", label.lower())]


def wait_for_window(label: str, before: set, timeout: Optional[float] = None, exes: tuple = (), poll: float = 0.3,
                    stop: Optional[Callable[[], bool]] = None):
    """The first new top-level window of the app (its process name or title matches), waiting up to `timeout` seconds
    (default LAUNCH_WAIT). None if it didn't appear in time; stop() can end the wait early."""
    keys = name_keys(label)
    end = time.monotonic() + (LAUNCH_WAIT if timeout is None else timeout)
    while True:
        for h, t, p in top_windows():
            if h in before:
                continue
            pl, tl = p.lower(), t.lower()
            if (exes and pl in exes) or any(k in pl or k in tl.replace(" ", "") or k in tl for k in keys):
                return h
        if time.monotonic() >= end or (stop and stop()):
            return None
        time.sleep(poll)


def app_window(op: str, app: str, open_app: Callable[[str], tuple]) -> tuple:
    exes, launch = catalog.APPS[app]
    wins = [(h, t) for h, t, p in top_windows() if p in exes]
    if op == "switch":
        if not wins:
            before = window_handles()
            started = time.monotonic()
            ok, msg = open_app(launch)
            if not ok:
                return ok, msg
            h = wait_for_window(launch, before, exes=exes)             # patient: slow apps still get switched to
            if h is None:
                return True, f"I started {launch}, but it's still loading after {many(int(LAUNCH_WAIT), 'second')}. It'll appear when it's ready."
            typer.bring_to_front(h)
            took = time.monotonic() - started
            return True, f"{launch} wasn't open, so I started it" + (f" (ready after {took:.0f} seconds)." if took >= 2 else ".")
        typer.bring_to_front(wins[0][0])
        return True, f"Switched to {launch}."
    if not wins:
        return True, f"{launch} isn't open."
    for h, _ in wins:
        u32.PostMessageW(h, 0x0010, 0, 0)                    # WM_CLOSE: polite, unsaved work still prompts
    return True, f"Closing {launch}."


# ---- clipboard / selected text
def _transform(op: str, text: str) -> str:
    lines = text.splitlines()
    if op == "UPPER":
        return text.upper()
    if op == "LOWER":
        return text.lower()
    if op == "TITLE":
        return re.sub(r"[A-Za-z]+('[A-Za-z]+)?", lambda m: m.group(0).capitalize(), text)
    if op == "SENTENCE":
        t = text.lower()
        return re.sub(r"(^\s*|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), t)
    if op == "TRIM":
        return "\n".join(re.sub(r"[ \t]+", " ", l).strip() for l in lines)
    if op == "SORT_LINES":
        return "\n".join(sorted(lines, key=str.lower))
    if op == "REVERSE_LINES":
        return "\n".join(reversed(lines))
    if op == "DEDUPE_LINES":
        seen, out = set(), []
        for l in lines:
            if l not in seen:
                seen.add(l)
                out.append(l)
        return "\n".join(out)
    if op == "JOIN_LINES":
        return " ".join(l.strip() for l in lines if l.strip())
    if op == "QUOTE":
        return f"“{text}”"
    if op == "BRACKETS":
        return f"({text})"
    if op == "BULLETS":
        return "\n".join(f"• {l}" for l in lines if l.strip())
    if op == "NUMBERED":
        return "\n".join(f"{i}. {l}" for i, l in enumerate((l for l in lines if l.strip()), 1))
    dev = _dev_transform(op, text, lines)
    if dev is not None:
        return dev
    words = re.findall(r"[A-Za-z0-9]+", text)
    if op == "SLUG":
        return "-".join(w.lower() for w in words)
    if op == "SNAKE":
        return "_".join(w.lower() for w in words)
    if op == "CAMEL":
        return (words[0].lower() + "".join(w.capitalize() for w in words[1:])) if words else text
    return text


def _words(text: str) -> list:
    """Identifier words: splits spaces, punctuation and camelCase ("parseHTTPResponse" -> parse, http, response)."""
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)
    return [w.lower() for w in re.findall(r"[A-Za-z0-9]+", spaced)]


def _dev_transform(op: str, text: str, lines: list) -> Optional[str]:
    """Developer & tidy-up transforms of the selected text. None = not one of these ops. Raises ValueError on bad input."""
    import base64
    import html as _html
    import json as _json
    import random
    import urllib.parse as _up
    if op in ("JSON_PRETTY", "JSON_MINIFY"):
        data = _json.loads(text)
        return _json.dumps(data, indent=2, ensure_ascii=False) if op == "JSON_PRETTY" else _json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    if op == "B64_ENC":
        return base64.b64encode(text.encode()).decode()
    if op == "B64_DEC":
        t = re.sub(r"\s+", "", text)
        return base64.b64decode(t + "=" * (-len(t) % 4)).decode("utf-8")
    if op == "URL_ENC":
        return _up.quote(text, safe="")
    if op == "URL_DEC":
        return _up.unquote(text)
    if op == "HTML_ESC":
        return _html.escape(text, quote=True)
    if op == "HTML_UNESC":
        return _html.unescape(text)
    if op == "STRIP_HTML":
        return re.sub(r"[ \t]+", " ", _html.unescape(re.sub(r"<[^>]+>", "", text))).strip()
    if op == "ESCAPE_STR":
        return _json.dumps(text, ensure_ascii=False)[1:-1]
    if op == "UNESCAPE_STR":
        return _json.loads('"' + text.replace('"', '\\"').replace('\\\\"', '\\"') + '"')
    w = _words(text) if op in ("KEBAB", "PASCAL", "CONSTANT", "DOT_CASE", "SNAKE2", "CAMEL2", "TRAIN") else None
    if op == "KEBAB":
        return "-".join(w)
    if op == "PASCAL":
        return "".join(x.capitalize() for x in w)
    if op == "CONSTANT":
        return "_".join(x.upper() for x in w)
    if op == "DOT_CASE":
        return ".".join(w)
    if op == "TRAIN":
        return "-".join(x.capitalize() for x in w)
    if op == "SWAP_CASE":
        return text.swapcase()
    if op == "REVERSE_TEXT":
        return text[::-1]
    if op == "SORT_NUMERIC":
        def key(l):
            m = re.search(r"-?\d+(?:\.\d+)?", l)
            return (0, float(m.group(0))) if m else (1, l.lower())
        return "\n".join(sorted(lines, key=key))
    if op == "SORT_DESC":
        return "\n".join(sorted(lines, key=str.lower, reverse=True))
    if op == "SHUFFLE_LINES":
        out = list(lines)
        random.shuffle(out)
        return "\n".join(out)
    if op == "REMOVE_EMPTY":
        return "\n".join(l for l in lines if l.strip())
    if op == "LINE_NUMBERS":
        return "\n".join(f"{i}. {l}" if l.strip() else l for i, l in enumerate(lines, 1))
    if op == "TRIM_LINES":
        return "\n".join(l.rstrip() for l in lines)
    if op == "SQL_IN":
        items = [l.strip() for l in lines if l.strip()]
        return "(" + ", ".join(x if re.fullmatch(r"-?\d+(\.\d+)?", x) else "'" + x.replace("'", "''") + "'" for x in items) + ")"
    if op == "JSON_ARRAY":
        return _json.dumps([l.strip() for l in lines if l.strip()], ensure_ascii=False)
    if op == "CSV_TO_MD":
        import csv
        import io
        rows = [r for r in csv.reader(io.StringIO(text)) if r]
        if not rows:
            raise ValueError("no rows")
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        md = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
        md += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        return "\n".join(md)
    if op == "COMMENT_HASH":
        return "\n".join("# " + l if l.strip() else l for l in lines)
    if op == "COMMENT_SLASH":
        return "\n".join("// " + l if l.strip() else l for l in lines)
    if op == "UNCOMMENT":
        return "\n".join(re.sub(r"^(\s*)(#|//|--|;)\s?", r"\1", l) for l in lines)
    if op == "INDENT":
        return "\n".join("    " + l if l.strip() else l for l in lines)
    if op == "DEDENT":
        return "\n".join(re.sub(r"^( {1,4}|\t)", "", l) for l in lines)
    if op == "TABS_TO_SPACES":
        return text.expandtabs(4)
    if op == "SPACES_TO_TABS":
        return "\n".join(re.sub(r"^((?:    )+)", lambda m: "\t" * (len(m.group(1)) // 4), l) for l in lines)
    if op == "STRAIGHT_QUOTES":
        return text.translate(str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-"}))
    if op == "REMOVE_ACCENTS":
        import unicodedata
        return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    if op == "ONE_SPACE_AFTER":
        return re.sub(r"([.!?])\s{2,}", r"\1 ", text)
    if op == "WRAP_80":
        import textwrap
        return "\n\n".join(textwrap.fill(" ".join(p.split()), 80) for p in re.split(r"\n\s*\n", text))
    if op == "MARKDOWN_LINK":
        t = text.strip()
        return f"[{t}]({t})" if t.startswith("http") else f"[{t}](https://)"
    if op == "EMAILS_ONLY":
        return "\n".join(dict.fromkeys(re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)))
    if op == "URLS_ONLY":
        return "\n".join(dict.fromkeys(re.findall(r"https?://[^\s<>\"')]+", text)))
    if op == "NUMBERS_ONLY":
        return "\n".join(re.findall(r"-?\d+(?:[.,]\d+)*", text))
    return None


# read-only questions about the selection (answered aloud, nothing pasted)
def _ask_selection(op: str, text: str) -> str:
    import json as _json
    if op == "READ_SELECTION":
        return text.strip()[:1500]
    if op == "JSON_CHECK":
        try:
            _json.loads(text)
            return "That's valid JSON."
        except ValueError as e:
            return f"That isn't valid JSON: {e}."
    if op == "JWT_DECODE":
        from . import devtools
        return devtools.jwt_payload(text.strip())
    if op == "SUM_NUMBERS":
        nums = [float(x.replace(",", "")) for x in re.findall(r"-?\d+(?:,\d{3})*(?:\.\d+)?", text)]
        if not nums:
            return "I don't see any numbers in the selection."
        total = sum(nums)
        return f"{len(nums)} numbers. Total {total:,.2f}, average {total / len(nums):,.2f}, biggest {max(nums):,g}, smallest {min(nums):,g}."
    if op == "COUNT_LINES":
        lines = text.splitlines() or [text]
        return f"{many(len(lines), 'line')}, {sum(1 for l in lines if l.strip())} not empty."
    return ""


ASK_OPS = {"READ_SELECTION", "JSON_CHECK", "JWT_DECODE", "SUM_NUMBERS", "COUNT_LINES"}


def _selection() -> Optional[str]:
    """Copy the current selection (Ctrl+C) and return it; the old clipboard text is put back by the caller."""
    marker = "⁣echo-empty⁣"
    typer.set_clipboard_text(marker)
    typer.press("ctrl+c")
    for _ in range(20):
        time.sleep(0.05)
        got = typer.get_clipboard_text()
        if got and got != marker:
            return got
    return None


def clip(op: str) -> tuple:
    if op == "READ":
        text = typer.get_clipboard_text() or ""
        return (True, "Your clipboard says: " + text[:600]) if text.strip() else (True, "Your clipboard is empty.")
    if op == "CLEAR":
        typer.set_clipboard_text("")
        return True, "Clipboard cleared."
    previous = typer.get_clipboard_text()
    selected = _selection()
    try:
        if op in ("COUNT", "SPELL_OUT"):
            text = selected if selected is not None else (previous or "")
            if not text.strip():
                return True, "Select some text first."
            if op == "COUNT":
                return True, f"{many(len(re.findall(r'\S+', text)), 'word')}, {many(len(text), 'character')}, {many(len(text.splitlines()) or 1, 'line')}."
            return True, " ".join(ch if ch != " " else "space" for ch in text.strip()[:60])
        if op in ASK_OPS:
            text = selected if selected is not None else (previous or "")
            if not text.strip():
                return True, "Select some text first."
            return True, _ask_selection(op, text)
        if selected is None:
            return False, "Select some text first, then ask again."
        try:
            new = _transform(op, selected)
        except (ValueError, UnicodeDecodeError) as e:
            return False, f"That selection can't be converted ({str(e)[:80]}). Nothing was changed."
        typer.set_clipboard_text(new)
        typer.press("ctrl+v")
        time.sleep(0.25)
        return True, "Done."
    finally:
        if previous is not None and op not in ("CLEAR",):
            time.sleep(0.2)
            typer.set_clipboard_text(previous)


# ---- system switches (your own user's settings only)
def _registry(path: str, values: dict) -> None:
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as k:
        for name, value in values.items():
            winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, value)


def _broadcast(area: str) -> None:
    res = ctypes.c_size_t()
    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, area, 0x0002, 1000, ctypes.byref(res))


def _brightness(value: Optional[int] = None, delta: int = 0) -> tuple:
    get = "(Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightness -ErrorAction Stop | Select-Object -First 1).CurrentBrightness"
    out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", get], capture_output=True, text=True,
                         timeout=20, creationflags=NO_WINDOW)
    try:
        current = int(out.stdout.strip())
    except ValueError:
        return False, "This screen doesn't let Windows change its brightness (external monitors usually don't)."
    if value is None and not delta:
        return True, f"Brightness is {current} percent."
    target = max(0, min(100, value if value is not None else current + delta))
    cmd = ("$m = Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightnessMethods | Select-Object -First 1; "
           f"Invoke-CimMethod -InputObject $m -MethodName WmiSetBrightness -Arguments @{{Timeout=0; Brightness=[byte]{target}}} | Out-Null")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd], capture_output=True, timeout=20,
                   creationflags=NO_WINDOW)
    return True, f"Brightness {target} percent."


def system(op: str, slots: dict, confirm) -> tuple:
    personalize = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    advanced = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
    if op in ("DARK_ON", "DARK_OFF"):
        light = 0 if op == "DARK_ON" else 1
        _registry(personalize, {"AppsUseLightTheme": light, "SystemUsesLightTheme": light})
        _broadcast("ImmersiveColorSet")
        return True, "Dark mode on." if light == 0 else "Light mode on."
    if op in ("HIDDEN_ON", "HIDDEN_OFF", "EXT_ON", "EXT_OFF"):
        if op.startswith("HIDDEN"):
            _registry(advanced, {"Hidden": 1 if op == "HIDDEN_ON" else 2})
        else:
            _registry(advanced, {"HideFileExt": 0 if op == "EXT_ON" else 1})
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
        _broadcast("ShellState")
        return True, {"HIDDEN_ON": "Showing hidden files.", "HIDDEN_OFF": "Hiding hidden files.",
                      "EXT_ON": "Showing file extensions.", "EXT_OFF": "Hiding file extensions."}[op] + \
            " Press F5 in open folders if they don't update."
    if op == "BRIGHTER":
        return _brightness(delta=10)
    if op == "DIMMER":
        return _brightness(delta=-10)
    if op == "BRIGHTNESS_SET":
        return _brightness(value=number(slots, "n", 50, 0, 100))
    if op == "BRIGHTNESS_MAX":
        return _brightness(value=100)
    if op == "BRIGHTNESS_MIN":
        return _brightness(value=10)
    if op == "BRIGHTNESS_GET":
        return _brightness()
    if op == "EMPTY_BIN":
        if not confirm("Empty the Recycle Bin?", "Everything in the Recycle Bin will be deleted for good."):
            return True, "Okay, I left the Recycle Bin alone."
        res = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x1 | 0x2 | 0x4)
        return True, "Recycle Bin emptied." if res in (0, -2147418113) else "The Recycle Bin is already empty."
    if op == "IDLE_TIME":
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wt.UINT), ("dwTime", wt.DWORD)]
        info = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
        secs = (ctypes.windll.kernel32.GetTickCount() - info.dwTime) // 1000
        return True, f"Last keyboard or mouse input was {many(secs, 'second')} ago."
    if op == "OPEN_WINDOWS_COUNT":
        return True, f"{len(top_windows())} app windows are open."
    if op in EASE_OPS:
        return ease(op)
    return False, "Unknown system action."


# ---- easier-to-use settings (your own user, reversible: each has a "normal" command)
EASE_OPS = {"DCLICK_SLOWER", "DCLICK_FASTER", "DCLICK_NORMAL", "DCLICK_GET", "KEY_REPEAT_SLOWER", "KEY_REPEAT_NORMAL",
            "STICKY_ON", "STICKY_OFF", "MOUSE_TRAILS_ON", "MOUSE_TRAILS_OFF", "MOUSE_SONAR_ON", "MOUSE_SONAR_OFF",
            "CARET_WIDER", "CARET_NORMAL", "POINTER_BIGGER", "POINTER_SMALLER", "POINTER_NORMAL", "POINTER_GET"}
_SPIF = 0x01 | 0x02          # save to the user profile and tell running apps


def clamp_step(current: int, step: int, low: int, high: int) -> int:
    return max(low, min(high, current + step))


def ease(op: str) -> tuple:
    spi = ctypes.windll.user32.SystemParametersInfoW
    if op.startswith("DCLICK"):
        current = ctypes.windll.user32.GetDoubleClickTime()
        if op == "DCLICK_GET":
            return True, f"Double-click speed is {current} milliseconds (normal is 500; higher is easier)."
        new = {"DCLICK_SLOWER": clamp_step(current, 150, 200, 900), "DCLICK_FASTER": clamp_step(current, -150, 200, 900),
               "DCLICK_NORMAL": 500}[op]
        spi(0x0020, new, None, _SPIF)                                   # SPI_SETDOUBLECLICKTIME
        return True, f"Double-click time is now {new} milliseconds" + (" — you can click more slowly." if new > current else ".")
    if op == "KEY_REPEAT_SLOWER":
        spi(0x0017, 3, None, _SPIF)                                     # SPI_SETKEYBOARDDELAY: longest delay
        spi(0x000B, 12, None, _SPIF)                                    # SPI_SETKEYBOARDSPEED: slower repeat
        return True, "Keys now wait longer before repeating, so holding a key a moment won't type it twice."
    if op == "KEY_REPEAT_NORMAL":
        spi(0x0017, 1, None, _SPIF)
        spi(0x000B, 31, None, _SPIF)
        return True, "Key repeat is back to normal."
    if op in ("STICKY_ON", "STICKY_OFF"):
        class STICKYKEYS(ctypes.Structure):
            _fields_ = [("cbSize", wt.UINT), ("dwFlags", wt.DWORD)]
        sk = STICKYKEYS(ctypes.sizeof(STICKYKEYS), 0)
        spi(0x003A, ctypes.sizeof(sk), ctypes.byref(sk), 0)             # SPI_GETSTICKYKEYS
        sk.dwFlags = (sk.dwFlags | 0x1) if op == "STICKY_ON" else (sk.dwFlags & ~0x1)
        spi(0x003B, ctypes.sizeof(sk), ctypes.byref(sk), _SPIF)         # SPI_SETSTICKYKEYS
        return True, ("Sticky Keys on: press Shift, Ctrl or Alt one at a time instead of holding them together."
                      if op == "STICKY_ON" else "Sticky Keys off.")
    if op in ("MOUSE_TRAILS_ON", "MOUSE_TRAILS_OFF"):
        spi(0x005D, 7 if op == "MOUSE_TRAILS_ON" else 0, None, _SPIF)   # SPI_SETMOUSETRAILS
        return True, "Pointer trails on, so the pointer is easier to follow." if op == "MOUSE_TRAILS_ON" else "Pointer trails off."
    if op in ("MOUSE_SONAR_ON", "MOUSE_SONAR_OFF"):
        spi(0x101D, 0, ctypes.c_void_p(1 if op == "MOUSE_SONAR_ON" else 0), _SPIF)   # SPI_SETMOUSESONAR
        return True, ("Done. Tap the Ctrl key any time and a circle shows where the pointer is."
                      if op == "MOUSE_SONAR_ON" else "The Ctrl-key pointer finder is off.")
    if op in ("CARET_WIDER", "CARET_NORMAL"):
        spi(0x2007, 0, ctypes.c_void_p(4 if op == "CARET_WIDER" else 1), _SPIF)      # SPI_SETCARETWIDTH
        return True, "The typing cursor is thicker now (new windows show it first)." if op == "CARET_WIDER" else "Typing cursor back to normal."
    if op.startswith("POINTER"):
        import winreg
        path = r"Control Panel\Cursors"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
            try:
                current = int(winreg.QueryValueEx(k, "CursorBaseSize")[0])
            except OSError:
                current = 32
            if op == "POINTER_GET":
                return True, f"The pointer size is {current} (normal is 32, biggest is 256)."
            new = {"POINTER_BIGGER": clamp_step(current, 32, 32, 256), "POINTER_SMALLER": clamp_step(current, -32, 32, 256),
                   "POINTER_NORMAL": 32}[op]
            winreg.SetValueEx(k, "CursorBaseSize", 0, winreg.REG_DWORD, new)
        spi(0x0057, 0, None, _SPIF)                                     # SPI_SETCURSORS: reload the pointer set
        return True, (f"Pointer size {new} of 256." + (" If it didn't change, say “open mouse pointer settings”." if new != current else ""))
    return False, "Unknown setting."
