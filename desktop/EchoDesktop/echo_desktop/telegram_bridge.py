"""Talk to Echo from your phone through Telegram, the way OpenClaw-style assistants "live in your chat apps":
message your own Telegram bot ("what's my battery?", "my tasks today", "what do my notes say about the lease?",
"lock my PC") and Echo answers there.

Safety
  * Off by default. You create the bot yourself (Telegram @BotFather) and paste its token into Settings; the token is
    stored DPAPI-encrypted.
  * Only ONE Telegram account may talk to Echo. The first one that writes is shown on the PC and must be approved
    there; everyone else is ignored without a reply.
  * Nothing listens on your network: Echo polls Telegram over HTTPS (outbound only).
  * Anything that would ask for a confirmation on the PC is declined automatically when you're remote, and features
    that need you at the PC (typing, clicking, Echo's settings) say so instead of running.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Optional

API = "https://api.telegram.org/bot{token}/{method}"
MAX_REPLY = 3900              # Telegram allows 4096 characters per message


def _request(token: str, method: str, params: dict, timeout: float) -> dict:
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(API.format(token=token, method=method), data=data, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


class TelegramBridge:
    def __init__(self, token: Callable[[], str], allowed: Callable[[], int], set_allowed: Callable[[int], None],
                 handle: Callable[[str], str], approve: Callable[[str], bool], status: Callable[[str], None] = lambda s: None,
                 request=_request):
        self.token, self.allowed, self.set_allowed = token, allowed, set_allowed
        self.handle, self.approve, self.status, self.request = handle, approve, status, request
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.offset = 0

    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if not self.running():
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True, name="echo-telegram")
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        failures = 0
        while not self._stop.is_set():
            token = self.token()
            if not token:
                self.status("Telegram: no bot token yet (Settings).")
                return
            try:
                got = self.request(token, "getUpdates", {"offset": self.offset, "timeout": 30,
                                                         "allowed_updates": json.dumps(["message"])}, 40)
                failures = 0
            except urllib.error.HTTPError as e:
                if e.code in (401, 404):
                    self.status("Telegram: the bot token was rejected. Check it in Settings.")
                    return
                failures += 1
                got = {}
            except (OSError, ValueError):
                failures += 1
                got = {}
            if failures:
                self._stop.wait(min(60, 5 * failures))
                continue
            for update in got.get("result", []) if isinstance(got, dict) else []:
                self.offset = max(self.offset, int(update.get("update_id", 0)) + 1)
                try:
                    self.on_update(token, update)
                except Exception as e:        # one bad message must not stop the bridge
                    self.status(f"Telegram: {e}")

    def on_update(self, token: str, update: dict) -> None:
        msg = update.get("message") or {}
        chat = (msg.get("chat") or {}).get("id")
        text = (msg.get("text") or "").strip()
        if not chat or (msg.get("chat") or {}).get("type") != "private":
            return                            # only one-to-one chats, never groups
        sender = msg.get("from") or {}
        who = sender.get("username") and "@" + sender["username"] or sender.get("first_name") or "someone"
        allowed = self.allowed()
        if not allowed:
            if not self.approve(f"Telegram user {who} (chat {chat}) wants to talk to Echo on this PC.\n\n"
                                "Allow ONLY if this is you. Nobody else will be able to use it."):
                return
            self.set_allowed(int(chat))
            self.send(token, chat, "Connected. I'm Echo on your PC — ask me anything, or say “help”.")
            return
        if int(chat) != int(allowed):
            return                            # strangers get silence
        if not text:
            self.send(token, chat, "Send me text messages (voice notes and files aren't supported yet).")
            return
        if text in ("/start", "help", "/help"):
            reply = ("Try: “my tasks today”, “what's my battery”, “anything I should know”, “where did we leave off”, "
                     "“what do my notes say about …”, “lock my PC”, or ask any question.")
        else:
            self.status(f"📱 Telegram: {text[:60]}")
            reply = self.handle(text) or "Done."
        self.send(token, chat, reply)

    def send(self, token: str, chat: int, text: str) -> None:
        text = text if len(text) <= MAX_REPLY else text[:MAX_REPLY] + "…"
        for attempt in range(2):
            try:
                self.request(token, "sendMessage", {"chat_id": chat, "text": text}, 20)
                return
            except (OSError, ValueError):
                time.sleep(1 + attempt)
