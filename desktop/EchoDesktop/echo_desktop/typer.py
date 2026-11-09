"""Echo types for you: text goes into whatever app you were using (Notepad, Word, VS Code, a browser box…), far
faster than any person can type.

Two ways in, both Win32 only (ctypes, no extra packages):
  * keystrokes  - SendInput with KEYEVENTF_UNICODE, hundreds of characters per call (any language / emoji);
  * paste       - put the text on the clipboard, press Ctrl+V, then put the old clipboard text back. Used for code and
                  long multi-line text, because editors re-indent and auto-close brackets when code is "typed".
Echo never presses Enter after typing, so nothing is sent or submitted on your behalf.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Optional
from .words import many

MAX_CHARS = 200_000
CHUNK = 300                     # characters per SendInput call (each = key down + key up)

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_RETURN, VK_TAB, VK_CONTROL, VK_V = 0x0D, 0x09, 0x11, 0x56
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002


@dataclass
class Result:
    ok: bool
    message: str
    chars: int = 0
    seconds: float = 0.0


def plan(text: str, mode: str = "auto") -> str:
    """'keys' or 'paste'. Auto: a single character is a keystroke; anything longer is pasted (clipboard restored after).
    Measured in Windows 11 Notepad: injected keystroke streams get garbled by its typing suggestions ("hello world" ->
    "hello ddddd", at any speed, Unicode or virtual-key), while paste was exact at ~1,200-1,400 characters a second.
    Pasting also means no Enter key is ever pressed (in chat apps Enter would send)."""
    if mode in ("keys", "paste"):
        return mode
    return "keys" if len(text) <= 1 else "paste"


def units(text: str) -> list:
    """Keyboard events for text: ('vk', code) for Enter/Tab, ('u', utf16_unit) otherwise. \r\n -> one Enter."""
    out = []
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for ch in text:
        if ch == "\n":
            out.append(("vk", VK_RETURN))
        elif ch == "\t":
            out.append(("vk", VK_TAB))
        else:
            data = ch.encode("utf-16-le")
            for i in range(0, len(data), 2):            # astral characters (emoji) are two UTF-16 units
                out.append(("u", int.from_bytes(data[i:i + 2], "little")))
    return out


# ------------------------------------------------------------------------------------------------ Win32 plumbing
class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _UNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _UNION)]


def _user32():
    u = ctypes.WinDLL("user32", use_last_error=True)
    u.SendInput.argtypes = [wt.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
    u.SendInput.restype = wt.UINT
    u.GetForegroundWindow.restype = wt.HWND
    u.SetForegroundWindow.argtypes = [wt.HWND]
    u.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
    u.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
    u.IsWindow.argtypes = [wt.HWND]
    u.OpenClipboard.argtypes = [wt.HWND]
    u.GetClipboardData.restype = wt.HANDLE
    u.SetClipboardData.argtypes = [wt.UINT, wt.HANDLE]
    u.SetClipboardData.restype = wt.HANDLE
    u.RegisterClipboardFormatW.argtypes = [wt.LPCWSTR]
    u.RegisterClipboardFormatW.restype = wt.UINT
    u.IsClipboardFormatAvailable.argtypes = [wt.UINT]
    u.GetClipboardSequenceNumber.restype = wt.DWORD
    return u


def _kernel32():
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.GlobalAlloc.argtypes = [wt.UINT, ctypes.c_size_t]
    k.GlobalAlloc.restype = wt.HGLOBAL
    k.GlobalLock.argtypes = [wt.HGLOBAL]
    k.GlobalLock.restype = ctypes.c_void_p
    k.GlobalUnlock.argtypes = [wt.HGLOBAL]
    k.GlobalFree.argtypes = [wt.HGLOBAL]
    return k


def _key(vk: int = 0, scan: int = 0, flags: int = 0) -> _INPUT:
    i = _INPUT()
    i.type = INPUT_KEYBOARD
    i.ki = _KEYBDINPUT(vk, scan, flags, 0, 0)
    return i


def _send(events: list) -> int:
    arr = (_INPUT * len(events))(*events)
    return _user32().SendInput(len(events), arr, ctypes.sizeof(_INPUT))


VK = {"ctrl": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B, "enter": 0x0D, "tab": 0x09, "esc": 0x1B, "backspace": 0x08,
      "delete": 0x2E, "del": 0x2E, "insert": 0x2D, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27, "home": 0x24,
      "end": 0x23, "pageup": 0x21, "pagedown": 0x22, "space": 0x20, "capslock": 0x14, "printscreen": 0x2C, "apps": 0x5D,
      "plus": 0xBB, "minus": 0xBD, "comma": 0xBC, "period": 0xBE, "slash": 0xBF, "backtick": 0xC0, "semicolon": 0xBA,
      "quote": 0xDE, "lbracket": 0xDB, "rbracket": 0xDD, "backslash": 0xDC, "equals": 0xBB, "numlock": 0x90,
      "scrolllock": 0x91, "pause": 0x13, "volumemute": 0xAD, "volumedown": 0xAE, "volumeup": 0xAF,
      **{f"f{i}": 0x6F + i for i in range(1, 25)}}
EXTENDED = {0x5B, 0x25, 0x26, 0x27, 0x28, 0x2C, 0x2D, 0x2E, 0x24, 0x23, 0x21, 0x22, 0x5D, 0x90}


def normalize_keys(keys) -> str:
    k = re.sub(r"[ \t]*\+[ \t]*", "+", str(keys or "").lower().strip())
    k = re.sub(r"\bcontrol\b", "ctrl", k)
    k = re.sub(r"\bwindows\b", "win", k)
    k = re.sub(r"\breturn\b", "enter", k)
    k = re.sub(r"\bescape\b", "esc", k)
    return re.sub(r"\s+", " ", k)


def chord_codes(chord: str) -> list:
    """'ctrl+shift+t' -> virtual-key codes. Raises ValueError for anything unknown."""
    codes = []
    for part in chord.split("+"):
        if part in VK:
            codes.append(VK[part])
        elif len(part) == 1 and part.isalnum():
            codes.append(ord(part.upper()))
        else:
            raise ValueError(f"unknown key '{part}'")
    if not codes or len(codes) > 4:
        raise ValueError("use one key or a short combination like ctrl+s")
    return codes


def key_sequence(keys) -> list:
    """'ctrl+k ctrl+w' (chords separated by spaces, pressed one after another) -> [[codes], [codes]]."""
    chords = normalize_keys(keys).split(" ")
    if not chords or len(chords) > 8:
        raise ValueError("too many key presses")
    return [chord_codes(c) for c in chords]


def press(keys, times: int = 1) -> None:
    """Press a chord or chord sequence (Win32 SendInput), `times` times."""
    seq = key_sequence(keys)
    for _ in range(max(1, min(int(times), 100))):
        for codes in seq:
            ext = lambda c: KEYEVENTF_EXTENDEDKEY if c in EXTENDED else 0   # noqa: E731
            events = [_key(vk=c, flags=ext(c)) for c in codes] + \
                     [_key(vk=c, flags=ext(c) | KEYEVENTF_KEYUP) for c in reversed(codes)]
            if _send(events) != len(events):
                raise OSError("Windows blocked the key press (an admin window or a secure screen may be in front).")
            time.sleep(0.03)


def send_keys(text: str) -> int:
    """Type text as Unicode keystrokes. Returns characters sent."""
    seq = units(text)
    sent = 0
    for start in range(0, len(seq), CHUNK):
        events = []
        for kind, code in seq[start:start + CHUNK]:
            if kind == "vk":
                events += [_key(vk=code), _key(vk=code, flags=KEYEVENTF_KEYUP)]
            else:
                events += [_key(scan=code, flags=KEYEVENTF_UNICODE), _key(scan=code, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
        if _send(events) != len(events):
            raise OSError("Windows blocked the keystrokes (is an admin window or a secure screen in front?)")
        sent += len(events) // 2
        time.sleep(0.004)          # let the target app drain its input queue
    return sent


SECRET_FORMAT = "EchoVaultSecret"          # marks clipboard text that came from Echo's vault
_HIDE_FORMATS = ("ExcludeClipboardContentFromMonitorProcessing", "CanIncludeInClipboardHistory", "CanUploadToCloudClipboard")


def clipboard_has_secret() -> bool:
    """True while the clipboard holds something copied out of Echo's vault."""
    try:
        fmt = _user32().RegisterClipboardFormatW(SECRET_FORMAT)
        return bool(fmt and _user32().IsClipboardFormatAvailable(fmt))
    except (AttributeError, OSError):
        return False


def get_clipboard_text() -> Optional[str]:
    """The clipboard's text — never a secret copied from Echo's vault (the AI, tools and Echo's own features all read
    the clipboard through here, so a copied password can't reach them)."""
    u = _user32()
    if clipboard_has_secret():
        return None
    if not u.OpenClipboard(None):
        return None
    try:
        h = u.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return None
        k = _kernel32()
        p = k.GlobalLock(h)
        try:
            return ctypes.wstring_at(p) if p else None
        finally:
            k.GlobalUnlock(h)
    finally:
        u.CloseClipboard()


def set_clipboard_text(text: str) -> bool:
    u, k = _user32(), _kernel32()
    data = (text + "\0").encode("utf-16-le")
    for _ in range(10):                       # another app may hold the clipboard for a moment
        if u.OpenClipboard(None):
            break
        time.sleep(0.03)
    else:
        return False
    try:
        u.EmptyClipboard()
        h = k.GlobalAlloc(GMEM_MOVEABLE, len(data))
        p = k.GlobalLock(h)
        ctypes.memmove(p, data, len(data))
        k.GlobalUnlock(h)
        if not u.SetClipboardData(CF_UNICODETEXT, h):
            k.GlobalFree(h)
            return False
        return True
    finally:
        u.CloseClipboard()


def set_clipboard_secret(text: str, clear_after: float = 30.0) -> bool:
    """Put a vault secret on the clipboard: kept out of Windows clipboard history and cloud clipboard, marked so Echo
    never reads it back, and wiped after `clear_after` seconds unless something else was copied since."""
    u, k = _user32(), _kernel32()
    data = (text + "\0").encode("utf-16-le")
    for _ in range(10):
        if u.OpenClipboard(None):
            break
        time.sleep(0.03)
    else:
        return False
    try:
        u.EmptyClipboard()
        h = k.GlobalAlloc(GMEM_MOVEABLE, len(data))
        p = k.GlobalLock(h)
        ctypes.memmove(p, data, len(data))
        k.GlobalUnlock(h)
        if not u.SetClipboardData(CF_UNICODETEXT, h):
            k.GlobalFree(h)
            return False
        for name, value in [(SECRET_FORMAT, b"1"), (_HIDE_FORMATS[0], b""), (_HIDE_FORMATS[1], b"\0\0\0\0"),
                            (_HIDE_FORMATS[2], b"\0\0\0\0")]:
            fmt = u.RegisterClipboardFormatW(name)
            hm = k.GlobalAlloc(GMEM_MOVEABLE, max(1, len(value)))
            if value:
                ptr = k.GlobalLock(hm)
                ctypes.memmove(ptr, value, len(value))
                k.GlobalUnlock(hm)
            if not u.SetClipboardData(fmt, hm):
                k.GlobalFree(hm)
        seq = u.GetClipboardSequenceNumber()
    finally:
        u.CloseClipboard()

    def wipe():
        time.sleep(clear_after)
        if _user32().GetClipboardSequenceNumber() == seq and clipboard_has_secret():
            uu = _user32()
            if uu.OpenClipboard(None):
                try:
                    uu.EmptyClipboard()
                finally:
                    uu.CloseClipboard()
    threading.Thread(target=wipe, daemon=True, name="echo-vault-clipboard").start()
    return True


def paste(text: str) -> None:
    previous = get_clipboard_text()
    if not set_clipboard_text(text):
        raise OSError("The clipboard is busy; try again.")
    time.sleep(0.03)
    _send([_key(vk=VK_CONTROL), _key(vk=VK_V), _key(vk=VK_V, flags=KEYEVENTF_KEYUP), _key(vk=VK_CONTROL, flags=KEYEVENTF_KEYUP)])
    if previous is not None:
        def restore():
            time.sleep(0.6)                    # after the target app has read the clipboard
            set_clipboard_text(previous)
        threading.Thread(target=restore, daemon=True).start()


# ------------------------------------------------------------------------------------------------ target window
class FocusTracker:
    """Remembers the last window you used that isn't Echo, so "type …" said into Echo's chat box still lands there."""

    def __init__(self, exclude: Optional[set] = None):
        self.target = None
        self.title = ""
        self.exclude = {os.getpid()} | set(exclude or ())     # processes whose windows are never the target
        self._stop = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self._watch, daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _watch(self):
        u = _user32()
        while not self._stop.wait(0.3):
            hwnd = u.GetForegroundWindow()
            if not hwnd:
                continue
            pid = wt.DWORD()
            u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value not in self.exclude:
                buf = ctypes.create_unicode_buffer(256)
                u.GetWindowTextW(hwnd, buf, 256)
                if buf.value:                  # skip the desktop/taskbar (no title)
                    self.target, self.title = hwnd, buf.value

    def focus_target(self) -> bool:
        """Bring the remembered window back to the front if Echo itself is in front now."""
        u = _user32()
        hwnd = u.GetForegroundWindow()
        pid = wt.DWORD()
        if hwnd:
            u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if hwnd and pid.value not in self.exclude:
            return True                         # some other app is already in front: type there
        if not self.target or not u.IsWindow(self.target):
            return False
        bring_to_front(self.target)
        time.sleep(0.15)
        return True


def bring_to_front(hwnd) -> bool:
    """SetForegroundWindow that works from a background process: briefly join the foreground thread's input queue."""
    u, k = _user32(), _kernel32()
    u.IsIconic.argtypes = [wt.HWND]
    u.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
    u.BringWindowToTop.argtypes = [wt.HWND]
    u.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
    if u.IsIconic(hwnd):
        u.ShowWindow(hwnd, 9)                     # SW_RESTORE
    fg = u.GetForegroundWindow()
    fg_thread = u.GetWindowThreadProcessId(fg, None) if fg else 0
    me = k.GetCurrentThreadId()
    attached = bool(fg_thread and fg_thread != me and u.AttachThreadInput(me, fg_thread, True))
    try:
        ok = bool(u.SetForegroundWindow(hwnd))
        u.BringWindowToTop(hwnd)
    finally:
        if attached:
            u.AttachThreadInput(me, fg_thread, False)
    return ok


def type_text(text: str, tracker: Optional[FocusTracker] = None, mode: str = "auto") -> Result:
    text = (text or "")
    if not text.strip():
        return Result(False, "There's nothing to type.")
    if len(text) > MAX_CHARS:
        return Result(False, f"That's over {MAX_CHARS:,} characters; I won't type that much at once.")
    if tracker is not None and not tracker.focus_target():
        return Result(False, "Click into the app where you want the text first, then ask me again.")
    how = plan(text, mode)
    started = time.perf_counter()
    try:
        if how == "paste":
            paste(text)
        else:
            send_keys(text)
    except OSError as e:
        return Result(False, str(e))
    seconds = time.perf_counter() - started
    where = f" into {tracker.title[:40]}" if tracker is not None and tracker.title else ""
    speed = f"{len(text) / max(seconds, 1e-3):,.0f} characters a second" if how == "keys" else "pasted in one go"
    return Result(True, f"Typed {many(len(text), 'character')}{where} ({speed}).", len(text), seconds)
