"""Speak while the AI is still writing: cut a stream of text into sentences as soon as each one is complete.

Pure (no Windows calls); tested in tests/test_speed.py.
"""
from __future__ import annotations

import re
from typing import List

# Words whose trailing "." doesn't end a sentence.
_ABBREV = {"mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "e.g", "i.e", "approx", "no", "fig", "inc", "ltd",
           "co", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "rs", "mt", "a.m", "p.m"}
_END = re.compile(r"[.!?…]+[\"')\]]*(?=\s)|\n+")
_SOFT = re.compile(r"[,;:—–]\s")


class SentenceChunker:
    """feed(delta) -> finished sentences; flush() -> the rest.

    The first piece is allowed to be short (it's what the listener hears first, so it should start fast); later pieces
    are merged up to a comfortable length so the voice doesn't sound choppy. A very long first sentence is cut at a
    comma so speech still starts early.
    """

    def __init__(self, first_max: int = 140, min_len: int = 40, max_len: int = 400):
        self.buf = ""
        self.first = True
        self.first_max, self.min_len, self.max_len = first_max, min_len, max_len
        self._pending = ""

    def _boundaries(self) -> List[int]:
        out = []
        for m in _END.finditer(self.buf):
            if m.group(0).startswith("."):
                word = re.search(r"([A-Za-z.]+)\.*$", self.buf[:m.start()])
                if word and word.group(1).lower().rstrip(".") in _ABBREV:
                    continue
                if word and len(word.group(1)) == 1 and word.group(1).isupper():     # initials: "J. K. Rowling"
                    continue
            out.append(m.end())
        return out

    def _emit(self, piece: str) -> List[str]:
        piece = piece.strip()
        if not piece:
            return []
        if self.first:
            self.first = False
            return [piece]
        self._pending = (self._pending + " " + piece).strip() if self._pending else piece
        if len(self._pending) >= self.min_len:
            out, self._pending = [self._pending], ""
            return out
        return []

    def feed(self, delta: str) -> List[str]:
        self.buf += delta
        out: List[str] = []
        while True:
            ends = self._boundaries()
            if not ends:
                break
            cut = ends[0]
            piece, self.buf = self.buf[:cut], self.buf[cut:]
            out += self._emit(piece)
        limit = self.first_max if self.first else self.max_len
        if len(self.buf) > limit:
            soft = [m.end() for m in _SOFT.finditer(self.buf, 0, limit)]
            cut = soft[-1] if soft else (self.buf.rfind(" ", 0, limit) + 1 or limit)
            piece, self.buf = self.buf[:cut], self.buf[cut:]
            out += self._emit(piece)
        return out

    def flush(self) -> List[str]:
        rest, self.buf = self.buf.strip(), ""
        out = []
        if self._pending and rest:
            out.append((self._pending + " " + rest).strip())
        elif self._pending:
            out.append(self._pending)
        elif rest:
            out.append(rest)
        self._pending = ""
        self.first = False
        return out


def sentences(text: str) -> List[str]:
    """A whole text, cut the same way (used to pipeline speech for replies that arrive in one piece)."""
    c = SentenceChunker()
    return c.feed(text) + c.flush()
