"""Echo's vault: passwords, PINs, cards and other private data the AI can never see.

How it works (the same idea as 1Password's agentic autofill, where "raw credentials never enter the LLM context"):
  * Secrets live in their own file, %APPDATA%\\EchoDesktop\\vault.bin, encrypted with Windows DPAPI (this Windows
    user only). Nothing in the AI's reach reads it: no AI tool, no MCP server, no prompt, no memory, no chat log.
  * You add and edit them only in the Vault window, by typing. Never by voice, never through the AI.
  * You use them by voice ("unlock my phone", "type my Gmail password", "type my card number"). Echo's command
    recogniser (no AI) picks the action; Windows Hello (face, fingerprint or PIN) or your vault PIN must confirm it;
    then Echo does it directly: types the secret into the app you're using, unlocks the phone over USB/ADB, or copies it
    for 30 seconds (kept out of clipboard history). The secret is never spoken, shown in the chat, or logged.
  * It refuses to type secrets into chat apps, terminals or Echo itself, and locks after repeated failed checks.
  * Every use is recorded by name and time only ("when was my vault used").
`Vault` holds the data; `Verifier` asks for Windows Hello / the vault PIN; executors live in brain._vault.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

KINDS = {
    "login": ("Login", ["username", "password", "site"]),
    "card": ("Card", ["number", "expiry", "cvv", "holder"]),
    "phone": ("Phone unlock PIN / password", ["pin"]),
    "pin": ("PIN", ["pin"]),
    "wifi": ("Wi-Fi password", ["network", "password"]),
    "note": ("Secure note", ["text"]),
}
SECRET_FIELDS = {"password", "number", "cvv", "pin", "text", "expiry"}
SEALED_FIELDS = SECRET_FIELDS | {"username", "holder"}     # each sealed on its own; only "site" and "network" stay readable
_SEAL = "dpapi1:"


def _seal(value: str, item_id: str) -> str:
    """Encrypt one field by itself (DPAPI, tied to this Windows user and to its own item), so even the opened vault
    file holds no readable secret: each one is decrypted only at the moment it's used."""
    import base64
    from .storage import protect
    return _SEAL + base64.b64encode(protect(str(value).encode("utf-8"), ("echo-vault:" + item_id).encode())).decode()


def _sealed(value) -> bool:
    return isinstance(value, str) and value.startswith(_SEAL)


def _unseal(value: str, item_id: str) -> str:
    import base64
    from .storage import unprotect
    if not _sealed(value):
        return value
    return unprotect(base64.b64decode(value[len(_SEAL):]), ("echo-vault:" + item_id).encode()).decode("utf-8")


def mask_username(user: str) -> str:
    """"meera.k@gmail.com" -> "m•••@gmail.com"; "meera_k" -> "m•••"."""
    user = (user or "").strip()
    if not user:
        return ""
    name, at, domain = user.partition("@")
    return name[:1] + "•••" + (at + domain if at else "")


def card_network(number: str) -> str:
    n = re.sub(r"\D", "", number or "")
    if n[:1] == "4":
        return "Visa"
    if n[:2] in {"51", "52", "53", "54", "55"} or 2221 <= int(n[:4] or 0) <= 2720:
        return "Mastercard"
    if n[:2] in {"34", "37"}:
        return "American Express"
    if n[:2] in {"60", "65", "81", "82"} or n[:3] == "508":
        return "RuPay"
    return "Card"


def hint_for(kind: str, fields: dict) -> str:
    """A safe one-line description for the vault list. Never part of a secret beyond a username's first letter."""
    if kind == "login":
        return mask_username(fields.get("username", "")) or "Login"
    if kind == "card":
        return card_network(fields.get("number", "")) + " card" if fields.get("number") else "Card"
    return {"phone": "Unlocks your phone", "pin": "PIN", "wifi": "Wi-Fi", "note": "Secure note"}.get(kind, "")


def strength(password: str) -> tuple:
    """(score 0-4, word) for the Vault window's meter."""
    p = password or ""
    if not p:
        return 0, ""
    kinds = sum(bool(re.search(rx, p)) for rx in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"))
    score = (len(p) >= 8) + (len(p) >= 12) + (len(p) >= 16) + (kinds >= 3) - (len(set(p)) < len(p) / 3)
    score = max(0, min(4, score))
    return score, ["Very weak", "Weak", "Okay", "Strong", "Very strong"][score]


def generate_password(length: int = 20) -> str:
    """A random password with letters, digits and symbols (no look-alikes like O/0, l/1)."""
    letters = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"
    pool = letters + "23456789" + "!@#$%^&*-_=+?"
    while True:
        p = "".join(secrets.choice(pool) for _ in range(max(8, length)))
        if all(re.search(rx, p) for rx in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]")):
            return p
GRACE = 60.0                 # after a check, more uses within this many seconds don't ask again ("lock my vault" ends it)
MAX_FAILS, LOCKOUT = 3, 300.0


@dataclass
class Item:
    id: str
    name: str
    kind: str

    def label(self) -> str:
        return f"{self.name} ({KINDS.get(self.kind, ('item',))[0].lower()})"


def _norm(s: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (s or "").lower()))


def host_of(text: str) -> str:
    """"https://accounts.google.com/v3/signin?…" or "accounts.google.com/…" -> "accounts.google.com" ("" if not a web address)."""
    m = re.match(r"^\s*(?:[a-z][a-z0-9+.-]*://)?(?:[^@/\s]+@)?([a-z0-9-]+(?:\.[a-z0-9-]+)+)(?::\d+)?(?:[/?#]|$)", (text or "").lower())
    return m.group(1).removeprefix("www.") if m else ""


_SECOND_LEVEL = {"co", "com", "org", "net", "gov", "ac", "edu", "nic", "res", "gen", "firm", "ind"}


def base_domain(host: str) -> str:
    """"accounts.google.com" -> "google.com"; "onlinesbi.sbi.co.in" -> "sbi.co.in"."""
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in _SECOND_LEVEL and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def site_matches(site: str, host: str) -> bool:
    """Does a saved login's website belong to the page in front? Same site or a subdomain of it — so a look-alike
    (g00gle-login.xyz, google.com.evil.io) never matches."""
    saved = host_of(site) or host_of("https://" + (site or "").strip())
    if not saved or not host:
        return False
    return host == saved or host.endswith("." + saved) or base_domain(host) == base_domain(saved)


class Vault:
    def __init__(self, path: Path, encrypt: bool = True, clock=time.time):
        self.path, self.encrypt, self.clock = path, encrypt, clock
        self.lock = threading.Lock()

    # ---- file
    def _read(self) -> dict:
        try:
            raw = self.path.read_bytes()
        except OSError:
            return {"version": 1, "items": [], "pin": None, "log": []}
        if self.encrypt:
            from .storage import unprotect
            raw = unprotect(raw)
        d = json.loads(raw.decode("utf-8"))
        d.setdefault("items", []), d.setdefault("pin", None), d.setdefault("log", [])
        if any(not _sealed(v) for i in d["items"] for k, v in i["fields"].items() if k in SEALED_FIELDS):
            for i in d["items"]:                      # an older vault: seal every secret field now
                i.setdefault("hint", hint_for(i["kind"], {k: v for k, v in i["fields"].items() if not _sealed(v)}))
                i["fields"] = {k: (_seal(v, i["id"]) if k in SEALED_FIELDS and not _sealed(v) else v) for k, v in i["fields"].items()}
            self._write(d)
        return d

    def _write(self, d: dict) -> None:
        from .storage import _write_atomic, protect
        raw = json.dumps(d).encode("utf-8")
        _write_atomic(self.path, protect(raw) if self.encrypt else raw)

    # ---- what anyone may see: names and kinds only
    def items(self) -> list:
        with self.lock:
            return [Item(i["id"], i["name"], i["kind"]) for i in self._read()["items"]]

    def find(self, spoken: str, kind: Optional[str] = None) -> tuple:
        """(item, None) for the best match, or (None, question/explanation)."""
        items = [i for i in self.items() if kind is None or i.kind == kind]
        if not items:
            what = KINDS[kind][0].lower() if kind else "secret"
            return None, f"There's no {what} in your vault yet. Say “open my vault” to add one."
        want = _norm(spoken)
        if not want:
            if len(items) == 1:
                return items[0], None
            return None, "Which one? " + ", ".join(i.name for i in items[:8]) + "."
        exact = [i for i in items if _norm(i.name) == want]
        if exact:
            return exact[0], None
        part = [i for i in items if want in _norm(i.name) or _norm(i.name) in want]
        if len(part) == 1:
            return part[0], None
        words = set(want.split())
        scored = sorted(((len(words & set(_norm(i.name).split())), i) for i in items), key=lambda x: -x[0])
        if scored and scored[0][0] and (len(scored) == 1 or scored[0][0] > scored[1][0]):
            return scored[0][1], None
        options = part or items
        return None, f"I couldn't tell which one you meant by “{spoken}”: " + ", ".join(i.name for i in options[:8]) + "."

    # ---- editing (only from the Vault window)
    def add(self, name: str, kind: str, fields: dict) -> Item:
        if kind not in KINDS:
            raise ValueError("unknown kind")
        name = " ".join(str(name).split())[:60]
        if not name:
            raise ValueError("give it a name, like “Gmail” or “HDFC card”")
        clean = {k: str(v) for k, v in fields.items() if k in KINDS[kind][1] and str(v) != ""}
        if kind == "card":
            clean["number"] = re.sub(r"[\s-]", "", clean.get("number", ""))
            if not clean["number"].isdigit() or not 12 <= len(clean["number"]) <= 19:
                raise ValueError("the card number should be 12 to 19 digits")
        if kind == "phone" and not clean.get("pin"):
            raise ValueError("type the phone's PIN or password")
        with self.lock:
            d = self._read()
            if any(_norm(i["name"]) == _norm(name) for i in d["items"]):
                raise ValueError(f"there's already an item called {name}")
            item_id = uuid.uuid4().hex
            item = {"id": item_id, "name": name, "kind": kind, "hint": hint_for(kind, clean), "created": self.clock(),
                    "fields": {k: (_seal(v, item_id) if k in SEALED_FIELDS else v) for k, v in clean.items()}}
            d["items"].append(item)
            self._write(d)
        return Item(item["id"], name, kind)

    def update(self, item_id: str, fields: dict) -> None:
        with self.lock:
            d = self._read()
            for i in d["items"]:
                if i["id"] == item_id:
                    new = {k: str(v) for k, v in fields.items() if k in KINDS[i["kind"]][1] and str(v) != ""}
                    if i["kind"] == "card" and "number" in new:
                        new["number"] = re.sub(r"[\s-]", "", new["number"])
                    i["fields"].update({k: (_seal(v, item_id) if k in SEALED_FIELDS else v) for k, v in new.items()})
                    if new:
                        i["hint"] = hint_for(i["kind"], new) if ("username" in new or "number" in new) else i.get("hint", "")
            self._write(d)

    def delete(self, item_id: str) -> None:
        with self.lock:
            d = self._read()
            d["items"] = [i for i in d["items"] if i["id"] != item_id]
            self._write(d)

    # ---- the only way a secret leaves the file
    def reveal(self, item: Item, field: str, purpose: str) -> Optional[str]:
        """The value of one field, for one action that was already verified. Recorded by name, never by value."""
        with self.lock:
            d = self._read()
            raw = next((i for i in d["items"] if i["id"] == item.id), None)
            if raw is None:
                return None
            value = raw["fields"].get(field)
            value = _unseal(value, raw["id"]) if value is not None and field in SEALED_FIELDS else value
            d["log"] = (d["log"] + [{"t": self.clock(), "name": raw["name"], "what": purpose[:40]}])[-200:]
            self._write(d)
        return value

    def details(self) -> list:
        """For the Vault window: every item with what's safe to show (name, kind, website, a hint like "m•••@gmail.com"
        or "Visa card", which fields it has, when it was added). No secret is decrypted."""
        with self.lock:
            return [{"id": i["id"], "name": i["name"], "kind": i["kind"], "site": i["fields"].get("site", ""),
                     "network": i["fields"].get("network", ""), "hint": i.get("hint", ""), "fields": sorted(i["fields"]),
                     "created": i.get("created", 0)} for i in self._read()["items"]]

    def fields_of(self, item: Item) -> list:
        """Which fields this item has (names only)."""
        with self.lock:
            raw = next((i for i in self._read()["items"] if i["id"] == item.id), None)
        return [k for k in (raw or {}).get("fields", {})]

    def sites(self) -> dict:
        """{item id: website} for logins (where a login belongs isn't secret; it's what autofill matches on)."""
        with self.lock:
            return {i["id"]: i["fields"].get("site", "") for i in self._read()["items"] if i["kind"] == "login"}

    def for_page(self, host: str, title: str) -> tuple:
        """Autofill: the login for the website (or app) in front. (item, None) or (None, why)."""
        logins = [i for i in self.items() if i.kind == "login"]
        if not logins:
            return None, "There's no login in your vault yet. Say “open my vault” to add one."
        sites = self.sites()
        if host:
            hits = [i for i in logins if site_matches(sites.get(i.id, ""), host)]
            if len(hits) == 1:
                return hits[0], None
            if len(hits) > 1:
                return None, f"You have {len(hits)} logins for {host}: " + ", ".join(i.name for i in hits) + \
                       ". Say “sign me in with …” and the name."
        words = set(_norm(f"{host.replace('.', ' ')} {title}").split()) - {"com", "www", "in", "org", "net", "sign", "login",
                                                                          "log", "google", "chrome", "microsoft", "edge", "mozilla", "firefox"}
        named = [i for i in logins if not sites.get(i.id) and set(_norm(i.name).split()) & words]
        if len(named) == 1:
            return named[0], None
        where = host or (title[:40] if title else "this window")
        return None, f"I don't have a login saved for {where}. Say “sign me in with …” and its name, or add the website to it in your vault."

    def history(self, n: int = 8) -> list:
        with self.lock:
            return list(self._read()["log"][-n:])

    # ---- vault PIN (used when Windows Hello isn't set up)
    def has_pin(self) -> bool:
        with self.lock:
            return bool(self._read()["pin"])

    def set_pin(self, pin: str) -> None:
        if not (4 <= len(pin) <= 32):
            raise ValueError("use 4 to 32 characters")
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 200_000)
        with self.lock:
            d = self._read()
            d["pin"] = {"salt": salt.hex(), "hash": digest.hex(), "iterations": 200_000}
            self._write(d)

    def check_pin(self, pin: str) -> bool:
        with self.lock:
            p = self._read()["pin"]
        if not p:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), bytes.fromhex(p["salt"]), int(p["iterations"]))
        return hmac.compare_digest(digest.hex(), p["hash"])


class Verifier:
    """Proves a person at this PC approved this use: Windows Hello first, the vault PIN otherwise. One check covers
    GRACE seconds; MAX_FAILS failures lock everything for LOCKOUT seconds."""

    def __init__(self, vault: Vault, hello: Callable[[str], str], ask_pin: Callable[[str], Optional[str]], clock=time.monotonic):
        self.vault, self.hello, self.ask_pin, self.clock = vault, hello, ask_pin, clock
        self._ok_until = 0.0
        self._fails: list = []
        self._lock = threading.Lock()

    def lock(self) -> None:
        self._ok_until = 0.0

    def locked_out(self) -> float:
        now = self.clock()
        self._fails = [t for t in self._fails if now - t < LOCKOUT]
        return LOCKOUT - (now - self._fails[0]) if len(self._fails) >= MAX_FAILS else 0.0

    def verify(self, reason: str) -> tuple:
        """(True, "") when approved; (False, why) otherwise."""
        with self._lock:
            wait = self.locked_out()
            if wait:
                return False, f"The vault is locked for {int(wait // 60) + 1} more minute(s) after failed checks."
            if self.clock() < self._ok_until:
                return True, ""
            result = self.hello(reason)
            if result == "VERIFIED":
                ok = True
            elif result == "CANCELED":
                return False, "Okay, cancelled."
            elif self.vault.has_pin():
                pin = self.ask_pin(reason)
                if pin is None:
                    return False, "Okay, cancelled."
                ok = self.vault.check_pin(pin)
            elif result == "UNAVAILABLE":
                return False, ("To use your vault, set up Windows Hello (Settings → Accounts → Sign-in options) or set a "
                               "vault PIN in the Vault window.")
            else:
                ok = False
            if not ok:
                self._fails.append(self.clock())
                left = MAX_FAILS - len(self._fails)
                return False, "That check didn't pass." + (f" {left} more tries before the vault locks." if left > 0 else
                                                          " The vault is locked for 5 minutes.")
            self._fails.clear()
            self._ok_until = self.clock() + GRACE
            return True, ""


def windows_hello(helper_command) -> Callable[[str], str]:
    """Runs helpers/hello.ps1: VERIFIED / CANCELED / FAILED / UNAVAILABLE."""
    def ask(reason: str) -> str:
        try:
            out = subprocess.run(helper_command("hello.ps1", "-Message", reason[:200]), capture_output=True, timeout=180,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            word = out.stdout.decode("utf-8", "replace").strip().splitlines()
            return word[-1].strip() if word else "UNAVAILABLE"
        except (OSError, subprocess.TimeoutExpired):
            return "UNAVAILABLE"
    return ask


# ------------------------------------------------------------------------------------------------ phone over ADB
def find_adb(configured: str = "") -> Optional[str]:
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = [configured, shutil.which("adb") or "", os.path.join(local, "Microsoft", "WinGet", "Links", "adb.exe")]
    winget = Path(local) / "Microsoft" / "WinGet" / "Packages"
    if winget.is_dir():                                   # installed by Echo's setup app (winget Google.PlatformTools)
        candidates += [str(p) for p in winget.glob("Google.PlatformTools*/platform-tools/adb.exe")]
    for root in (os.environ.get("ANDROID_HOME", ""), os.environ.get("ANDROID_SDK_ROOT", ""),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "EchoAndroid", "Sdk"),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk")):
        if root:
            candidates.append(os.path.join(root, "platform-tools", "adb.exe"))
    return next((c for c in candidates if c and os.path.isfile(c)), None)


def _adb(adb: str, args: list, stdin: Optional[bytes] = None, timeout: float = 20) -> subprocess.CompletedProcess:
    return subprocess.run([adb, *args], input=stdin, capture_output=True, timeout=timeout,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def phone_ready(adb: Optional[str]) -> tuple:
    """(serial, None) when exactly one authorised phone is connected; (None, why) otherwise."""
    if not adb:
        return None, "I can't find adb (Android platform-tools). Install it, or set its path in Settings."
    try:
        out = _adb(adb, ["devices"], timeout=15).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.TimeoutExpired):
        return None, "adb didn't answer."
    rows = [line.split() for line in out.splitlines()[1:] if line.strip()]
    ready = [r[0] for r in rows if len(r) >= 2 and r[1] == "device"]
    if any(len(r) >= 2 and r[1] == "unauthorized" for r in rows) and not ready:
        return None, "The phone is connected but hasn't allowed this PC yet. Accept the USB debugging prompt on the phone."
    if not ready:
        return None, "No phone is connected. Plug it in by USB (or connect Wireless debugging) and try again."
    if len(ready) > 1:
        return None, "More than one phone is connected; unplug the others."
    return ready[0], None


def adb_text(secret: str) -> str:
    """A value for `adb shell input text`, quoted for the phone's shell (spaces become %s)."""
    return "'" + secret.replace("'", "'\\''").replace(" ", "%s") + "'"


def unlock_phone(adb: str, serial: str, secret: str) -> tuple:
    """Wake the phone, open the PIN pad, type the PIN/password and press Enter. The secret goes to adb on stdin,
    never on a command line other programs could see."""
    try:
        size = _adb(adb, ["-s", serial, "shell", "wm", "size"]).stdout.decode("utf-8", "replace")
        m = re.findall(r"(\d+)x(\d+)", size)
        w, h = (int(m[-1][0]), int(m[-1][1])) if m else (1080, 2400)
        script = (f"input keyevent KEYCODE_WAKEUP\nsleep 0.5\ninput swipe {w // 2} {int(h * 0.85)} {w // 2} {int(h * 0.25)} 250\n"
                  f"sleep 0.7\ninput text {adb_text(secret)}\nsleep 0.2\ninput keyevent KEYCODE_ENTER\nexit\n")
        out = _adb(adb, ["-s", serial, "shell"], stdin=script.encode("utf-8"), timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"The phone didn't respond ({type(e).__name__})."
    if out.returncode != 0:
        return False, "The phone refused the input (is it connected and allowed?)."
    return True, "Sent your PIN to the phone; it should be unlocked now."
