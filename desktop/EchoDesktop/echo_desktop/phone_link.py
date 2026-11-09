"""Keep the phone connected to this PC's services.

The phone reaches FreeLLMAPI, the natural voice, Whisper and the phone bridge through `adb reverse`, which Android
forgets on every unplug, reboot or Wi-Fi change. While Echo runs, this re-adds the missing ports whenever an
authorised phone is connected (USB or wireless debugging), so the phone's AI works again without typing commands.
"""
from __future__ import annotations

import subprocess
import threading
from typing import Callable, Optional

AI, VOICE, WHISPER, BRIDGE = 31415, 31416, 31417, 31419


def wanted_ports(settings) -> list:
    ports = [AI, VOICE, WHISPER]
    if settings["phone_bridge"]:
        ports.append(BRIDGE)
    return ports


def _run(adb: str, args: list, timeout: float = 15) -> str:
    out = subprocess.run([adb, *args], capture_output=True, timeout=timeout,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return out.stdout.decode("utf-8", "replace")


def phones(adb: str) -> list:
    rows = [line.split() for line in _run(adb, ["devices"]).splitlines()[1:] if line.strip()]
    return [r[0] for r in rows if len(r) >= 2 and r[1] == "device"]


def forwarded(listing: str) -> set:
    """Ports already reversed, from `adb reverse --list` ("UsbFfs tcp:31415 tcp:31415")."""
    found = set()
    for line in listing.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[1].startswith("tcp:") and parts[1][4:].isdigit():
            found.add(int(parts[1][4:]))
    return found


def link_once(adb: str, ports: list) -> dict:
    """{serial: [ports added]} for every connected phone."""
    added = {}
    for serial in phones(adb):
        have = forwarded(_run(adb, ["-s", serial, "reverse", "--list"]))
        missing = [p for p in ports if p not in have]
        for p in missing:
            _run(adb, ["-s", serial, "reverse", f"tcp:{p}", f"tcp:{p}"])
        if missing:
            added[serial] = missing
    return added


class Keeper:
    """Checks every `every` seconds; quiet when nothing changed, tells `notify` once per (re)connection."""

    def __init__(self, settings, find_adb: Callable[[str], Optional[str]], notify: Callable[[str], None], every: float = 30):
        self.settings, self.find_adb, self.notify, self.every = settings, find_adb, notify, every
        self.stop = threading.Event()

    def start(self) -> "Keeper":
        threading.Thread(target=self._loop, name="echo-phone-link", daemon=True).start()
        return self

    def _loop(self):
        while not self.stop.wait(5 if not hasattr(self, "_ran") else self.every):
            self._ran = True
            if not self.settings["phone_link"]:
                continue
            adb = self.find_adb(self.settings["adb_path"] or "")
            if not adb:
                continue
            try:
                added = link_once(adb, wanted_ports(self.settings))
            except (OSError, subprocess.SubprocessError):
                continue
            if added:
                self.notify("📱 Phone connected: its AI and voice go through this PC again.")
