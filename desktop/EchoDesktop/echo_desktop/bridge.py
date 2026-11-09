"""Phone -> PC bridge for website tasks.

The phone reaches it through USB with `adb reverse tcp:31419 tcp:31419` (same pattern as the Whisper host), so the
server listens on 127.0.0.1 only. Every request needs `Authorization: Bearer <bridge key>` (shown in EchoDesktop
Settings). One endpoint:

    POST /v1/web   {"text": "go to gmail and read my latest email"}  ->  {"kind": "done|ask|confirm|error", "text": "…"}

While a phone run waits for "yes"/"no" (or an answer), the next POST is treated as that reply.
"""
from __future__ import annotations

import hmac
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional

HOST, PORT = "127.0.0.1", 31419
MAX_BODY = 4096
PHONE = "phone"


def new_key() -> str:
    return secrets.token_urlsafe(24)


def authorized(header: Optional[str], key: str) -> bool:
    if not key or not header or not header.startswith("Bearer "):
        return False
    return hmac.compare_digest(header[7:].strip().encode(), key.encode())


def handle_text(web, text: str, complete: Callable) -> dict:
    """Pure request logic (unit-tested with a fake WebSessions)."""
    text = (text or "").strip()
    if not text:
        return {"kind": "error", "text": "Say what to do on a website."}
    if not web.enabled():
        return {"kind": "error", "text": "Website control is off on the PC. Turn it on in EchoDesktop Settings."}
    if web.waiting(PHONE):
        outcome = web.answer(PHONE, text)
        if outcome is not None:
            return {"kind": outcome.kind, "text": outcome.text}
    outcome = web.start(PHONE, text, complete)
    return {"kind": outcome.kind, "text": outcome.text}


class BridgeServer:
    def __init__(self, web, key_fn: Callable[[], str], complete: Callable, on_task: Callable[[str], None] = lambda t: None):
        self.web, self.key_fn, self.complete, self.on_task = web, key_fn, complete, on_task
        self.server: Optional[ThreadingHTTPServer] = None
        self._busy = threading.Lock()

    def running(self) -> bool:
        return self.server is not None

    def start(self) -> None:
        if self.server is not None:
            return
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):          # keep the console quiet
                pass

            def _send(self, code: int, obj: dict):
                body = json.dumps(obj).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/v1/health":
                    return self._send(200, {"ok": True, "web": bridge.web.enabled()}) \
                        if authorized(self.headers.get("Authorization"), bridge.key_fn()) else self._send(401, {"error": "bad key"})
                self._send(404, {"error": "not found"})

            def do_POST(self):
                if self.path != "/v1/web":
                    return self._send(404, {"error": "not found"})
                if not authorized(self.headers.get("Authorization"), bridge.key_fn()):
                    return self._send(401, {"error": "bad key"})
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0 or length > MAX_BODY:
                    return self._send(413, {"error": "body too large"})
                try:
                    text = json.loads(self.rfile.read(length)).get("text", "")
                except (ValueError, AttributeError):
                    return self._send(400, {"error": "bad json"})
                if not bridge._busy.acquire(blocking=False):
                    return self._send(409, {"kind": "error", "text": "The PC is still busy with the last web task."})
                try:
                    bridge.on_task(str(text)[:500])
                    result = handle_text(bridge.web, str(text)[:500], bridge.complete)
                except Exception as e:  # report, never crash the server thread
                    result = {"kind": "error", "text": f"The PC hit an error: {e}"}
                finally:
                    bridge._busy.release()
                self._send(200, result)

        self.server = ThreadingHTTPServer((HOST, PORT), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
