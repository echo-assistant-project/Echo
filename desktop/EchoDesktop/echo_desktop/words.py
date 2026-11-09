"""Small wording helpers shared by every part of Echo (no imports, so anything can use them)."""
from __future__ import annotations

_IRREGULAR = {"person": "people", "entry": "entries", "memory": "memories", "child": "children", "match": "matches",
              "box": "boxes", "category": "categories", "reply": "replies", "city": "cities", "country": "countries"}


def many(n, word: str, words: str | None = None) -> str:
    """"1 file", "2 files", "1,234 files", "1 person", "3 people". Whole numbers get thousands separators."""
    plural = words or _IRREGULAR.get(word) or (word[:-1] + "ies" if word.endswith("y") and word[-2:-1] not in "aeiou" else word + "s")
    num = f"{n:,}" if isinstance(n, int) and not isinstance(n, bool) else str(n)
    return f"{num} {word if n == 1 else plural}"


def preview(text: str, limit: int = 40) -> str:
    """A sentence-ending preview of some text: "hello world." / "Lorem ipsum dolor sit amet…" (cut at a word, never
    mid-word, and no stray full stop after the cut)."""
    t = " ".join(str(text).split())
    if not t:
        return "a space."
    if not any(c.isalnum() for c in t) and len(t) <= 5:      # a symbol on its own: Typed “?” (not “Typed ?”)
        return f"“{t}”"
    if len(t) > limit:
        cut = t[:limit].rsplit(" ", 1)[0].rstrip(" ,;:")
        return (cut or t[:limit]) + "…"
    return t if t[-1] in ".!?…" else t + "."
