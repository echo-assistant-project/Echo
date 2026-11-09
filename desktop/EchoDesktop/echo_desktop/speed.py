"""Echo's own stopwatch: how long each reply really took, so "how fast are you" answers with measured numbers.

Pure (no Windows calls); tested in tests/test_speed.py.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from statistics import median
from typing import Optional


class LatencyLog:
    """Per turn: when it started, when the first answer text was ready, when the voice started. Keeps the last N."""

    def __init__(self, keep: int = 60, clock=time.monotonic):
        self.keep = keep
        self.clock = clock
        self._turns: "OrderedDict[int, dict]" = OrderedDict()
        self._lock = threading.Lock()

    def begin(self, turn: int, kind: str = "command") -> None:
        with self._lock:
            self._turns[turn] = {"t0": self.clock(), "kind": kind}
            while len(self._turns) > self.keep:
                self._turns.popitem(last=False)

    def kind(self, turn: int, kind: str) -> None:
        with self._lock:
            if turn in self._turns:
                self._turns[turn]["kind"] = kind

    def note(self, turn: int, name: str, at: Optional[float] = None) -> Optional[float]:
        """Record milestone `name` (first time only). Returns its milliseconds since the turn began."""
        with self._lock:
            t = self._turns.get(turn)
            if t is None:
                return None
            if name not in t:
                t[name] = max(0.0, ((at if at is not None else self.clock()) - t["t0"]) * 1000)
            return t[name]

    def get(self, turn: int) -> dict:
        with self._lock:
            return dict(self._turns.get(turn) or {})

    def status(self, turn: int) -> str:
        """Status line after a reply, e.g. "⚡ answer in 12 ms · voice in 41 ms"."""
        t = self.get(turn)
        bits = [f"{label} in {fmt_ms(t[k])}" for k, label in (("text_ms", "answer"), ("voice_ms", "voice")) if k in t]
        return "⚡ " + " · ".join(bits) if bits else ""

    def values(self, kind: str, name: str) -> list:
        with self._lock:
            return [t[name] for t in self._turns.values() if t["kind"] == kind and name in t]

    def summary(self) -> str:
        parts = []
        for kind, label in (("command", "commands"), ("ai", "AI answers")):
            text = self.values(kind, "text_ms")
            if not text:
                continue
            line = f"{label}: answer ready in {fmt_ms(median(text))} (median of {len(text)})"
            voice = self.values(kind, "voice_ms")
            if voice:
                line += f", voice started after {fmt_ms(median(voice))}"
            parts.append(line)
        if not parts:
            return "I haven't timed any replies yet in this session. Ask me something, then ask again."
        return "Measured on this PC this session — " + "; ".join(parts) + "."


def fmt_ms(ms: float) -> str:
    return f"{ms:.0f} ms" if ms < 1000 else f"{ms / 1000:.1f} s"
