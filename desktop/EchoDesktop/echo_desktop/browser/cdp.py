"""Chrome DevTools Protocol over a WebSocket, standard library only: start the Chrome or Edge that's already on this PC
with Echo's own profile and drive it — no Playwright, no pip packages, no browser downloads.

The debugging port is opened by the browser on 127.0.0.1 only, and only for Echo's separate profile
(%LOCALAPPDATA%\\Echo\\browser-profile), never your everyday Chrome profile.
"""
from __future__ import annotations

import base64
import collections
import hashlib
import json
import os
import queue
import socket
import struct
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class CdpError(RuntimeError):
    pass


# ------------------------------------------------------------------------------------------------ WebSocket (RFC 6455)
class WebSocket:
    """Client side: text frames out (masked, as the RFC requires), text/continuation/ping/close in."""

    def __init__(self, url: str, timeout: float = 10):
        u = urlparse(url)
        if u.scheme != "ws" or u.hostname not in ("127.0.0.1", "localhost"):
            raise CdpError("Echo only talks to a browser on this PC.")
        self.sock = socket.create_connection((u.hostname, u.port or 80), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        path = u.path + ("?" + u.query if u.query else "")
        self.sock.sendall((f"GET {path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\n"
                           f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise CdpError("The browser closed the connection during the handshake.")
            head += chunk
        head, _, self._buf = head.partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        if " 101 " not in lines[0] + " ":
            raise CdpError(f"The browser refused the connection: {lines[0]}")
        want = base64.b64encode(hashlib.sha1((key + _GUID).encode()).digest()).decode()
        headers = {k.strip().lower(): v.strip() for k, _, v in (l.partition(":") for l in lines[1:])}
        if headers.get("sec-websocket-accept") != want:
            raise CdpError("The browser's WebSocket answer didn't match.")
        self.sock.settimeout(None)
        self._send_lock = threading.Lock()

    def _read(self, n: int) -> bytes:
        while len(self._buf) < n:
            chunk = self.sock.recv(max(65536, n - len(self._buf)))
            if not chunk:
                raise ConnectionError("browser connection closed")
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def _frame(self, opcode: int, payload: bytes) -> None:
        n = len(payload)
        head = bytes([0x80 | opcode])
        head += bytes([0x80 | n]) if n < 126 else (bytes([0x80 | 126]) + struct.pack(">H", n) if n < 65536
                                                    else bytes([0x80 | 127]) + struct.pack(">Q", n))
        mask = os.urandom(4)
        with self._send_lock:
            self.sock.sendall(head + mask + _mask(payload, mask))

    def send(self, text: str) -> None:
        self._frame(0x1, text.encode("utf-8"))

    def recv(self) -> str:
        """The next whole text message (pings are answered here)."""
        parts = []
        while True:
            b1, b2 = self._read(2)
            fin, opcode, n = b1 & 0x80, b1 & 0x0F, b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            mask = self._read(4) if b2 & 0x80 else None
            data = self._read(n)
            if mask:
                data = _mask(data, mask)
            if opcode == 0x8:
                raise ConnectionError("browser closed the connection")
            if opcode == 0x9:
                self._frame(0xA, data)
                continue
            if opcode in (0x1, 0x2, 0x0):
                parts.append(data)
                if fin:
                    return b"".join(parts).decode("utf-8", "replace")

    def close(self) -> None:
        try:
            self._frame(0x8, b"")
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


def _mask(data: bytes, mask: bytes) -> bytes:
    """XOR with the 4-byte mask, fast for big payloads (whole-integer XOR instead of byte by byte)."""
    n = len(data)
    key = int.from_bytes((mask * (n // 4 + 1))[:n], "little")
    return (int.from_bytes(data, "little") ^ key).to_bytes(n, "little")


# ------------------------------------------------------------------------------------------------ one tab
class Session:
    """A CDP connection to one page: call(method, params) -> result; a reader thread matches replies by id."""

    def __init__(self, ws_url: str):
        self.ws = WebSocket(ws_url)
        self._next = 0
        self._waiting: dict = {}
        self._lock = threading.Lock()
        self.alive = True
        self.events: collections.deque = collections.deque(maxlen=200)   # recent events: (method, params)
        threading.Thread(target=self._reader, daemon=True, name="echo-cdp").start()

    def _reader(self) -> None:
        try:
            while True:
                msg = json.loads(self.ws.recv())
                if "id" not in msg and "method" in msg:
                    self.events.append((msg["method"], msg.get("params") or {}))
                    continue
                q = self._waiting.pop(msg.get("id"), None)
                if q is not None:
                    q.put(msg)
        except (OSError, ConnectionError, ValueError):
            pass
        finally:
            self.alive = False
            for q in list(self._waiting.values()):
                q.put({"error": {"message": "the browser window was closed"}})
            self._waiting.clear()

    def call(self, method: str, params: Optional[dict] = None, timeout: float = 30):
        if not self.alive:
            raise CdpError("The Echo browser window was closed.")
        with self._lock:
            self._next += 1
            mid = self._next
        q: queue.Queue = queue.Queue()
        self._waiting[mid] = q
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        try:
            msg = q.get(timeout=timeout)
        except queue.Empty:
            self._waiting.pop(mid, None)
            raise CdpError(f"The browser took too long ({method}).") from None
        if "error" in msg:
            raise CdpError(str(msg["error"].get("message") or msg["error"]))
        return msg.get("result") or {}

    def close(self) -> None:
        self.alive = False
        self.ws.close()


# ------------------------------------------------------------------------------------------------ the browser
def find_browser() -> Optional[str]:
    """Chrome, else Edge: ECHO_BROWSER, then Windows' App Paths, then the usual install folders."""
    if os.environ.get("ECHO_BROWSER") and Path(os.environ["ECHO_BROWSER"]).is_file():
        return os.environ["ECHO_BROWSER"]
    try:
        import winreg
        for exe in ("chrome.exe", "msedge.exe"):
            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(root, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}") as k:
                        p = winreg.QueryValue(k, None)
                    if p and Path(p).is_file():
                        return p
                except OSError:
                    continue
    except ImportError:
        pass
    for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")):
        for rel in (r"Google\Chrome\Application\chrome.exe", r"Microsoft\Edge\Application\msedge.exe"):
            if base and (Path(base) / rel).is_file():
                return str(Path(base) / rel)
    return None


def _http_json(port: int, path: str, method: str = "GET"):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method)
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.load(r)


class Chrome:
    """Echo's own browser window (Chrome or Edge with a separate profile), started on first use and reused."""

    def __init__(self, profile: Path, headless: bool = False, exe: Optional[str] = None):
        self.profile, self.headless, self.exe = Path(profile), headless, exe
        self.proc: Optional[subprocess.Popen] = None
        self.port: Optional[int] = None

    def _port_file(self) -> Path:
        return self.profile / "DevToolsActivePort"

    def _live_port(self) -> Optional[int]:
        """The port of a browser already running on this profile (e.g. from an earlier Echo session)."""
        try:
            port = int(self._port_file().read_text(encoding="ascii").split()[0])
            _http_json(port, "/json/version")
            return port
        except (OSError, ValueError, IndexError):
            return None

    def start(self, timeout: float = 25) -> int:
        if self.port and self._live_port() == self.port:
            return self.port
        port = self._live_port()
        if port:
            self.port = port
            return port
        exe = self.exe or find_browser()
        if not exe:
            raise CdpError("Echo needs Chrome or Edge to control websites, and neither is installed.")
        self.profile.mkdir(parents=True, exist_ok=True)
        try:
            self._port_file().unlink()
        except OSError:
            pass
        args = [exe, f"--user-data-dir={self.profile}", "--remote-debugging-port=0", "--remote-debugging-address=127.0.0.1",
                "--no-first-run", "--no-default-browser-check", "--disable-features=Translate,MediaRouter",
                "--window-size=1280,900"]
        if self.headless:
            args.append("--headless=new")
        args.append("about:blank")
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if self.headless else 0)
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            port = self._live_port()
            if port:
                self.port = port
                return port
            if self.proc.poll() is not None and not self._port_file().exists():
                raise CdpError("The browser closed as soon as it started.")
            time.sleep(0.15)
        raise CdpError("The browser didn't start in time.")

    def page(self) -> Session:
        """A session on the browser's current tab (a new one if it has none)."""
        port = self.start()
        pages = [t for t in _http_json(port, "/json/list") if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
        if not pages:
            pages = [_http_json(port, "/json/new?about:blank", "PUT")]
        return Session(pages[0]["webSocketDebuggerUrl"])

    def close(self) -> None:
        """Close the browser Echo started (a browser it only attached to is closed through CDP too)."""
        port = self.port or self._live_port()
        if port:
            try:
                ver = _http_json(port, "/json/version")
                s = Session(ver["webSocketDebuggerUrl"])
                try:
                    s.call("Browser.close", timeout=5)
                except CdpError:
                    pass
                s.close()
            except (OSError, ValueError, KeyError, CdpError):
                pass
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc, self.port = None, None
