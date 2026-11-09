"""“Where did we leave off?”: Echo keeps a short log of what you asked and what it answered (the last 300 turns),
so a new day starts with context instead of a blank slate.

Stored on this PC only (%APPDATA%\\EchoDesktop\\sessions.bin, DPAPI-encrypted like Echo's memories). Anything that
looks like a password, PIN or card number is never logged. "Clear our chat" empties it.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import core

KEEP = 300
SESSION_GAP = 2 * 3600        # a pause this long starts a new session


class SessionLog:
    def __init__(self, path: Path, encrypt: bool = True, clock=time.time):
        self.path, self.encrypt, self.clock = path, encrypt, clock
        self.lock = threading.Lock()
        self.started = clock()
        try:
            raw = path.read_bytes()
            if encrypt:
                from .storage import unprotect
                raw = unprotect(raw)
            self.items = list(json.loads(raw.decode("utf-8")))
        except (OSError, ValueError):
            self.items = []

    def _save(self) -> None:
        from .storage import _write_atomic, protect
        data = json.dumps(self.items).encode("utf-8")
        _write_atomic(self.path, protect(data) if self.encrypt else data)

    def add(self, said: str, answer: str, act: Optional[str] = None, ok: bool = True, tools: Optional[list] = None) -> None:
        """act: "you" (you asked for an action) or "ai" (the AI chose it), None for a plain answer; tools: the tools
        the AI used. These make "what did you just do?" answerable: an assistant that acts must leave receipts."""
        said, answer = " ".join(str(said).split())[:200], " ".join(str(answer).split())[:240]
        if not said or core.is_sensitive(said) or core.is_sensitive(answer):
            return
        item = {"t": self.clock(), "said": said, "answer": answer}
        if act:
            item.update({"act": act, "ok": bool(ok)})
        if tools:
            item["tools"] = [str(t)[:60] for t in tools[:12]]
        with self.lock:
            self.items.append(item)
            del self.items[:-KEEP]
            try:
                self._save()
            except OSError:
                pass

    def clear(self) -> None:
        with self.lock:
            self.items = []
            try:
                self._save()
            except OSError:
                pass

    def last_session(self) -> list:
        """The most recent run of turns before this start of Echo (or before the last long pause)."""
        with self.lock:
            items = list(self.items)
        before = [i for i in items if i["t"] < self.started] or items
        if not before:
            return []
        out = [before[-1]]
        for item in reversed(before[:-1]):
            if out[-1]["t"] - item["t"] > SESSION_GAP:
                break
            out.append(item)
        return list(reversed(out))

    def actions(self, limit: int = 8, now: Optional[datetime] = None) -> str:
        """The last things Echo did (not just said), newest first, with who decided and whether it worked."""
        now = now or datetime.now()
        with self.lock:
            done = [i for i in self.items if i.get("act")][-limit:]
        if not done:
            return "I haven't done anything on this PC for you yet that I have a record of."
        if limit == 1:                                      # "what did you just do": the one last action, one line
            i = done[-1]
            when = datetime.fromtimestamp(i["t"]).strftime("%I:%M %p").lstrip("0")
            state = "" if i.get("ok", True) else " (it didn't work)"
            return f"At {when}, for “{i['said'][:80]}”: {i['answer'][:200]}{state}"
        lines = []
        for i in reversed(done):
            when = datetime.fromtimestamp(i["t"])
            day = "" if when.date() == now.date() else when.strftime("%d %b ")
            who = "you asked" if i["act"] == "you" else "the AI chose this"
            tools = f" Tools used: {', '.join(i['tools'][:5])}." if i.get("tools") else ""
            lines.append(f"{'✓' if i.get('ok', True) else '✗'} {day}{when.strftime('%I:%M %p').lstrip('0')}: "
                         f"“{i['said'][:60]}” ({who}). {i['answer'][:110]}{tools}")
        failed = sum(1 for i in done if not i.get("ok", True))
        head = f"My last {len(done)} actions, newest first" + (f" ({failed} didn't work)" if failed else "") + ":"
        return head + "\n" + "\n".join(lines)

    def recap(self, open_tasks: int = 0, due_today: int = 0, now: Optional[datetime] = None) -> str:
        now = now or datetime.now()
        last = self.last_session()
        if not last:
            return "This is our first chat that I have a record of. What are we working on?"
        when = datetime.fromtimestamp(last[-1]["t"])
        ago = (now.date() - when.date()).days
        day = "earlier today" if ago == 0 else "yesterday" if ago == 1 else f"on {when.strftime('%A %d %B')}"
        topics, seen = [], set()
        for item in reversed(last):                          # newest first, no repeats
            key = core.normalize(item["said"])
            if key not in seen and len(topics) < 4:
                seen.add(key)
                topics.append(f"“{item['said'][:70]}”")
        text = f"Last time ({day} at {when.strftime('%I:%M %p').lstrip('0')}) you asked: {', '.join(topics)}."
        final = last[-1]["answer"]
        if final:
            text += f" My last answer was: {final[:160]}{'…' if len(final) > 160 else ''}"
        if open_tasks:
            text += f" You have {open_tasks} open task{'s' if open_tasks != 1 else ''}" + \
                    (f", {due_today} due today." if due_today else ".")
        return text
