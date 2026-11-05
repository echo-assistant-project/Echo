"""Settings and memory storage under %APPDATA%\\EchoDesktop, encrypted with Windows DPAPI (current user only)."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from . import core

APP_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "EchoDesktop"


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> _Blob:
    buffer = ctypes.create_string_buffer(data, len(data))
    return _Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))


def protect(data: bytes, entropy: bytes = b"") -> bytes:
    """DPAPI CryptProtectData: only this Windows user on this PC can decrypt. `entropy` is an extra secret the same
    value must be decrypted with (Echo's vault uses it to seal each field to its own item)."""
    out = _Blob()
    extra = ctypes.byref(_blob(entropy)) if entropy else None
    if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(_blob(data)), "EchoDesktop", extra, None, None, 0x1, ctypes.byref(out)):
        raise OSError("CryptProtectData failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def unprotect(data: bytes, entropy: bytes = b"") -> bytes:
    out = _Blob()
    extra = ctypes.byref(_blob(entropy)) if entropy else None
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(_blob(data)), None, extra, None, None, 0x1, ctypes.byref(out)):
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


DEFAULTS = {
    "llm_url": "http://127.0.0.1:31415/v1",
    "workspaces": "",                      # your own project folders Echo may edit: "website=C:\\…\\site; app=D:\\code\\app"
    "mcp_ai_tools": True,                 # the AI may use your MCP servers' tools (anything not read-only still asks)
    "internet_access": True,              # Echo may search the web, read pages and call public APIs (downloads still ask)
    "ai_tools": True,                     # the AI may use Echo's 600+ built-in tools (anything that changes things asks first)
    "home_city": "",                      # for weather when no city is named ("set my city to …"); empty = from your IP
    "computer_use": False,                # let the AI use the mouse and keyboard in any app (asks before risky steps)
    "code_autorun": False,                 # let Echo run the code it writes without asking per project
    "persona": "echo",
    "target_language": "Hindi",
    "user_name": "",
    "auto_memory": True,
    "use_skills": True,                 # give the AI the matching skill (.md how-to); answer from skills when out of tokens
    "screen_understanding": False,
    "camera_understanding": False,
    "camera_index": 0,
    "web_control": False,       # let Echo click/type/read on its known websites (built-in browser, echo_desktop/browser)
    "web_extra_sites": "",      # more sites: "Name=https://example.com;Other=https://…"
    "mcp_servers": [],          # extra MCP servers: [{"name", "command", "args", "env"}]
    "phone_bridge": False,      # accept web tasks from the phone over adb reverse (127.0.0.1:31419)
    "wake_word": False,
    "use_gemini": True,
    "gemini_model": "gemini-3.1-flash-tts-preview",
    "gemini_voice": "Achernar",
    "orb_size": 96,
    "orb_opacity": 0.75,
    "orb_color": "",
    "orb_x": -1,
    "orb_y": -1,
    "interruptions": True,     # say "stop" / "wait" while Echo talks
    "fast_voice": False,       # load speech helpers only when explicitly requested
    "native_tools": True,      # the AI acts through real tool calls (several steps per request); off: Echo's JSON format
    "stream_replies": True,    # speak the AI's answer sentence by sentence while it is still being written
    "replies_muted": False,    # text-only replies
    "voice_rate_offset": 0.0,  # "speak faster/slower"
    # ---- the JARVIS pack
    "brain_mode": "cloud",     # Echo thinks with FreeLLMAPI only (the local Ollama/llama model was removed)
    "local_llm_url": "http://127.0.0.1:11434/v1",   # Ollama (or LM Studio: http://127.0.0.1:1234/v1)
    "local_model": "",         # empty: the first model the local server has
    "privacy_mode": False,     # no internet, local AI only ("privacy mode on")
    "privacy_saved": {},       # settings to restore when privacy mode goes off
    "proactive": True,         # nudges: tasks due, follow-ups, birthdays, habits, low battery, full disk
    "quiet_hours": "22-7",     # no spoken nudges between these hours (a dying battery still speaks)
    "hotkey": "ctrl+alt+e",    # press anywhere to talk to Echo; empty turns it off
    "telegram": False,         # message Echo from your own Telegram bot (token in secrets)
    "telegram_chat": 0,        # the one Telegram chat allowed to talk to Echo (approved on the PC)
    "auto_start_helpers": False,  # speech services are started explicitly
    "adb_path": "",           # adb.exe for "unlock my phone" (empty: found automatically)
}


class Settings:
    """Plain settings in settings.json; secrets (API keys) DPAPI-encrypted in secrets.bin."""

    def __init__(self, directory: Path = APP_DIR):
        self.path = directory / "settings.json"
        self.secret_path = directory / "secrets.bin"
        self.values = dict(DEFAULTS)
        try:
            self.values.update({k: v for k, v in json.loads(self.path.read_text("utf-8")).items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass
        try:
            self.secrets = json.loads(unprotect(self.secret_path.read_bytes()).decode("utf-8"))
        except (OSError, ValueError):
            self.secrets = {}

    def __getitem__(self, key):
        return self.values.get(key, DEFAULTS.get(key))

    def __setitem__(self, key, value):
        self.values[key] = value
        _write_atomic(self.path, json.dumps(self.values, indent=2).encode("utf-8"))

    def secret(self, key: str) -> str:
        return self.secrets.get(key, "")

    def set_secret(self, key: str, value: str) -> None:
        self.secrets[key] = value.strip()
        _write_atomic(self.secret_path, protect(json.dumps(self.secrets).encode("utf-8")))


class MemoryStore:
    """Long-term memory: DPAPI-encrypted JSON, same rules as the phone (secrets never stored)."""

    def __init__(self, directory: Path = APP_DIR):
        self.path = directory / "memory.bin"
        self.lock = threading.Lock()
        try:
            self.items = json.loads(unprotect(self.path.read_bytes()).decode("utf-8"))
        except (OSError, ValueError):
            self.items = []

    def _save(self):
        _write_atomic(self.path, protect(json.dumps(self.items).encode("utf-8")))

    def all(self) -> list:
        with self.lock:
            return sorted(self.items, key=lambda i: i["created"], reverse=True)

    def remember(self, text: str, source: str) -> str:
        """Returns 'saved' | 'updated' | 'duplicate' | 'sensitive' | 'opinion' | 'invalid'.

        'updated': a newer fact about the same thing replaced the old one ("I live in Pune" replaces "I live in
        Hyderabad"; the replaced text is in self.replaced). 'opinion': the AI tried to save a belief or opinion of
        the user's, which makes assistants agree instead of help (you can still say "remember that I think …")."""
        from . import lessons
        self.replaced = None
        clean = core.clean_line(text.strip().rstrip("."), 300) if isinstance(text, str) else None
        if not clean:
            return "invalid"
        if core.is_sensitive(clean):
            return "sensitive"
        if source != "user" and lessons.is_opinion(clean):
            return "opinion"
        slot = lessons.memory_slot(clean)
        with self.lock:
            if core.is_duplicate(self.items, clean):
                return "duplicate"
            old = [i for i in self.items if slot and lessons.memory_slot(i["text"]) == slot]
            if old and source != "user" and any(i.get("source") == "user" for i in old):
                return "duplicate"          # the AI never overwrites what you told Echo yourself
            if old:
                self.replaced = "; ".join(i["text"] for i in old)
                gone = {i["id"] for i in old}
                self.items = [i for i in self.items if i["id"] not in gone]
            now = time.time()
            self.items.append({"id": uuid.uuid4().hex, "text": clean, "created": now, "used": now, "uses": 0, "source": source})
            self.items = sorted(self.items, key=lambda i: i["used"])[-300:]
            self._save()
        return "updated" if old else "saved"

    def recall(self, query: str) -> list:
        with self.lock:
            picked = core.rank_memories(self.items, query, time.time())
            ids = {i["id"] for i in picked}
            for item in self.items:
                if item["id"] in ids:
                    item["used"] = time.time()
                    item["uses"] = item.get("uses", 0) + 1
            if picked:
                self._save()
            return picked

    def delete(self, ids: set) -> None:
        with self.lock:
            self.items = [i for i in self.items if i["id"] not in ids]
            self._save()

    def clear(self) -> None:
        with self.lock:
            self.items = []
            self._save()


LIST_ALIASES = {"grocery": "shopping", "groceries": "shopping", "shop": "shopping", "todo": "to-do", "to do": "to-do",
                "task": "to-do", "tasks": "to-do", "reminder": "reminders"}


def list_name(spoken) -> Optional[str]:
    from . import tools
    k = tools.key(spoken)
    for p in ("my ", "the "):
        k = k[len(p):] if k.startswith(p) else k
    k = k.strip()
    if not k or len(k) > 30:
        return None
    return LIST_ALIASES.get(k, k)


def split_items(text: str) -> list:
    items = [core.clean_line(p.strip().rstrip("."), 120) for p in re.split(r"\s*(?:,|;|\band\b|\bplus\b)\s*", text)]
    return [i for i in items if i]


def same_item(a: str, b: str) -> bool:
    a, b = a.lower().strip(), b.lower().strip()
    return a == b or a.rstrip("s") == b.rstrip("s")


class ListStore:
    """Lists & notes, DPAPI-encrypted like memories; text that looks like a secret is never stored."""

    def __init__(self, directory: Path = APP_DIR):
        self.path = directory / "lists.bin"
        self.lock = threading.Lock()
        try:
            data = json.loads(unprotect(self.path.read_bytes()).decode("utf-8"))
        except (OSError, ValueError):
            data = {}
        self.lists = {k: list(v) for k, v in data.get("lists", {}).items()}
        self.notes = list(data.get("notes", []))

    def _save(self):
        _write_atomic(self.path, protect(json.dumps({"lists": self.lists, "notes": self.notes}).encode("utf-8")))

    def add(self, name: str, text: str) -> tuple:
        """Returns ('added', added, skipped) | ('sensitive',) | ('full',) | ('empty',)."""
        items = split_items(text)
        if not items:
            return ("empty",)
        if any(core.is_sensitive(i) for i in items):
            return ("sensitive",)
        with self.lock:
            if name not in self.lists and len(self.lists) >= 30:
                return ("full",)
            target = self.lists.setdefault(name, [])
            added, skipped = [], []
            for item in items:
                if any(same_item(x, item) for x in target):
                    skipped.append(item)
                elif len(target) >= 100:
                    return ("full",)
                else:
                    target.append(item)
                    added.append(item)
            self._save()
        return ("added", added, skipped)

    def find(self, name: str, spoken: str) -> Optional[str]:
        return next((x for x in self.lists.get(name, []) if same_item(x, spoken)), None)

    def remove(self, name: str, item: str) -> bool:
        with self.lock:
            items = self.lists.get(name, [])
            if item not in items:
                return False
            items.remove(item)
            if not items:
                self.lists.pop(name, None)
            self._save()
            return True

    def clear(self, name: str) -> None:
        with self.lock:
            self.lists.pop(name, None)
            self._save()

    def add_note(self, text: str) -> Optional[bool]:
        note = core.clean_line(text, 500)
        if not note:
            return None
        if core.is_sensitive(note):
            return False
        with self.lock:
            self.notes.insert(0, note)
            del self.notes[200:]
            self._save()
        return True

    def clear_notes(self) -> None:
        with self.lock:
            self.notes = []
            self._save()
