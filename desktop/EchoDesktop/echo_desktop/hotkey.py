"""A global shortcut that summons Echo from any app (default Ctrl+Alt+E), like the hotkeys in the popular JARVIS
builds: press it and Echo starts listening; press it while Echo talks and it stops.

Win32 RegisterHotKey on a background thread with its own message loop. If another app already owns the shortcut,
Echo says so instead of stealing it. Setting "hotkey" ("ctrl+alt+e"; empty turns it off).
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import threading
from typing import Callable, Optional

MODS = {"alt": 0x1, "ctrl": 0x2, "control": 0x2, "shift": 0x4, "win": 0x8}
NOREPEAT = 0x4000
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012
NAMED = {"space": 0x20, "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
         "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B, "insert": 0x2D, "home": 0x24, "end": 0x23, "pause": 0x13}


def parse(spec: str) -> Optional[tuple]:
    """"ctrl+alt+e" -> (modifiers, virtual key). None if it isn't a usable shortcut (it needs a modifier and one key)."""
    parts = [p.strip().lower() for p in (spec or "").replace(" ", "").split("+") if p.strip()]
    if len(parts) < 2:
        return None
    mods = 0
    for p in parts[:-1]:
        if p not in MODS:
            return None
        mods |= MODS[p]
    key = parts[-1]
    if key in NAMED:
        vk = NAMED[key]
    elif len(key) == 1 and key.isalnum():
        vk = ord(key.upper())
    else:
        return None
    return mods, vk


def pretty(spec: str) -> str:
    return "+".join(p.capitalize() if len(p) > 1 else p.upper() for p in spec.lower().replace(" ", "").split("+"))


class GlobalHotkey:
    def __init__(self, spec: str, on_press: Callable[[], None], on_error: Callable[[str], None] = lambda s: None):
        self.spec, self.on_press, self.on_error = spec, on_press, on_error
        self._thread_id = 0
        self._ready = threading.Event()
        self.ok = False

    def start(self) -> bool:
        if parse(self.spec) is None:
            if self.spec:
                self.on_error(f"“{self.spec}” isn't a shortcut I can use (try ctrl+alt+e).")
            return False
        threading.Thread(target=self._loop, daemon=True, name="echo-hotkey").start()
        self._ready.wait(3)
        return self.ok

    def stop(self) -> None:
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)

    def _loop(self) -> None:
        u = ctypes.windll.user32
        mods, vk = parse(self.spec)
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        self.ok = bool(u.RegisterHotKey(None, 1, mods | NOREPEAT, vk))
        self._ready.set()
        if not self.ok:
            self.on_error(f"Another app already uses {pretty(self.spec)}, so Echo's shortcut is off. Pick another in Settings.")
            return
        msg = wt.MSG()
        try:
            while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    try:
                        self.on_press()
                    except Exception:
                        pass
        finally:
            u.UnregisterHotKey(None, 1)
