"""What EchoDesktop makes of the recognizer's guesses: mirror of the phone's VoiceRules.kt (Understanding,
SpokenNumbers, Fuzzy). Pure; tested in tests/test_understanding.py."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

FILLERS = {"um", "umm", "uh", "uhh", "uhm", "er", "erm", "ah", "hmm", "mm", "mhm"}


@dataclass
class Heard:
    text: str
    confidence: float
    is_command: bool
    rank: int


def clean(text: str) -> str:
    out = []
    for word in text.strip().split():
        bare = word.lower().strip(",.!?")
        if bare in FILLERS:
            continue
        if out and bare and not bare[0].isdigit() and out[-1].lower().strip(",.") == bare:
            continue
        out.append(word)
    return " ".join(out)


def choose(hypotheses: list, confidences: Optional[list], is_command: Callable[[str], bool], vocabulary: Iterable[str] = ()) -> Optional[Heard]:
    best, best_score = None, -1.0
    vocabulary = list(vocabulary)
    for rank, raw in enumerate(hypotheses[:5]):
        if not raw.strip():
            continue
        conf = confidences[rank] if confidences and rank < len(confidences) and 0 <= confidences[rank] <= 1 else 1 - 0.15 * rank
        base = clean(raw)
        candidates = []
        for c in [base, SpokenNumbers.normalize(base), repair_name(base, vocabulary)]:
            if c and c not in candidates:
                candidates.append(c)
        command = next((c for c in candidates if is_command(c)), None)
        score = conf + (0.3 if command else 0)
        if score > best_score:
            best_score, best = score, Heard(command or candidates[0], conf, command is not None, rank)
    return best


_OPEN = re.compile(r"^(open|launch|start|go to|show me|play)\s+(.+)$", re.I)


def repair_name(text: str, vocabulary: list) -> Optional[str]:
    if not vocabulary:
        return None
    m = _OPEN.search(text.strip())
    if not m:
        return None
    target = m.group(2).strip()
    if any(v.lower() == target.lower() for v in vocabulary):
        return None
    fixed = Fuzzy.best(target, vocabulary)
    return f"{m.group(1)} {fixed}" if fixed else None


def split(text: str, is_command: Callable[[str], bool]) -> Optional[list]:
    parts = [p.strip() for p in re.split(r"\s*,?\s+(?:and then|then|and also|after that|and)\s+", text, flags=re.I) if p.strip()]
    if not 2 <= len(parts) <= 4:
        return None
    return parts if all(is_command(p) for p in parts) else None


class SpokenNumbers:
    SMALL = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
             "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
             "seventeen": 17, "eighteen": 18, "nineteen": 19}
    TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
    SCALES = {"hundred": 100, "thousand": 1000, "lakh": 100_000, "lakhs": 100_000, "million": 1_000_000, "crore": 10_000_000}

    ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9,
                "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14, "fifteenth": 15, "sixteenth": 16,
                "seventeenth": 17, "eighteenth": 18, "nineteenth": 19, "twentieth": 20, "thirtieth": 30}
    MONTHS = {"january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"}

    @staticmethod
    def _ordinal(n: int) -> str:
        return f"{n}{'th' if n % 100 in (11, 12, 13) else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"

    @classmethod
    def _is_number(cls, w: str) -> bool:
        return w in cls.SMALL or w in cls.TENS or w in cls.SCALES

    @classmethod
    def normalize(cls, text: str) -> str:
        words = []
        for w in text.strip().split():
            parts = w.split("-")
            words.extend(parts if "-" in w and all(cls._is_number(p.lower()) for p in parts) else [w])
        out, i = [], 0
        while i < len(words):
            lower = words[i].lower()
            nxt = words[i + 1].lower() if i + 1 < len(words) else ""
            # "twelfth" -> 12th; "second" only when it's clearly a date ("second of may"), not "one second".
            if lower in cls.ORDINALS and (lower != "second" or nxt == "of" or nxt in cls.MONTHS):
                out.append(cls._ordinal(cls.ORDINALS[lower]))
                i += 1
                continue
            if not (cls._is_number(lower) or (lower in ("a", "an") and nxt in cls.SCALES)):
                out.append(words[i])
                i += 1
                continue
            total = current = 0
            j, last_number, is_ordinal = i, False, False
            while j < len(words):
                w = words[j].lower()
                if w in ("a", "an") and j == i:
                    current = 1
                elif w in cls.ORDINALS and last_number and current % 100 >= 20 and current % 10 == 0 and cls.ORDINALS[w] < 10:
                    current += cls.ORDINALS[w]          # "twenty second" -> 22nd
                    is_ordinal = True
                    j += 1
                    break
                elif w in cls.SMALL:
                    v, rem = cls.SMALL[w], current % 100
                    if last_number and rem != 0 and not (rem % 10 == 0 and rem >= 20 and v < 10):
                        break
                    current += v
                elif w in cls.TENS:
                    if last_number and current % 100 != 0:
                        break
                    current += cls.TENS[w]
                elif w in cls.SCALES:
                    scale = cls.SCALES[w]
                    if scale == 100:
                        current = (current or 1) * 100
                    else:
                        total += (current or 1) * scale
                        current = 0
                elif w == "and" and last_number and j + 1 < len(words) and cls._is_number(words[j + 1].lower()) and total + current >= 100:
                    j += 1
                    continue
                else:
                    break
                last_number = True
                j += 1
            number = cls._ordinal(total + current) if is_ordinal else str(total + current)
            if j < len(words) and words[j].lower() == "point":
                digits, k = "", j + 1
                while k < len(words) and cls.SMALL.get(words[k].lower(), 99) <= 9:
                    digits += str(cls.SMALL[words[k].lower()])
                    k += 1
                if digits:
                    number, j = f"{number}.{digits}", k
            out.append(number)
            i = j
        s = " ".join(out)
        s = re.sub(r"\bhalf past (\d{1,2})\b", r"\1:30", s, flags=re.I)
        s = re.sub(r"\bquarter past (\d{1,2})\b", r"\1:15", s, flags=re.I)
        s = re.sub(r"\bquarter to (\d{1,2})\b", lambda m: f"{12 if int(m.group(1)) == 1 else int(m.group(1)) - 1}:45", s, flags=re.I)
        s = re.sub(r"\b(\d{1,2}) o'?clock\b", r"\1", s, flags=re.I)
        s = re.sub(r"\b(\d{1,2}) ([0-5]\d) (am|pm|a\.m\.|p\.m\.)", r"\1:\2 \3", s, flags=re.I)
        return s


class Fuzzy:
    @staticmethod
    def levenshtein(a: str, b: str) -> int:
        if a == b:
            return 0
        prev = list(range(len(b) + 1))
        for i in range(1, len(a) + 1):
            cur = [i] + [0] * len(b)
            for j in range(1, len(b) + 1):
                cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] != b[j - 1]))
            prev = cur
        return prev[len(b)]

    @staticmethod
    def key(text: str) -> str:
        s = "".join(c for c in text.lower() if "a" <= c <= "z")
        if not s:
            return ""
        for a, b in (("ph", "f"), ("ck", "k"), ("q", "k"), ("x", "ks"), ("z", "s")):
            s = s.replace(a, b)
        s = re.sub(r"c(?=[eiy])", "s", s).replace("c", "k")
        for a, b in (("dg", "j"), ("wh", "w"), ("kn", "n"), ("wr", "r"), ("gh", "g"), ("v", "f"), ("y", "i")):
            s = s.replace(a, b)
        return re.sub(r"(.)\1+", r"\1", s[0] + "".join(c for c in s[1:] if c not in "aeiou"))

    @classmethod
    def best(cls, spoken: str, vocabulary: list) -> Optional[str]:
        k = cls.key(spoken)
        if len(k) < 3:
            return None
        squashed = "".join(c for c in spoken.lower() if c.isalnum())
        best, best_score = None, 10 ** 9
        for name in vocabulary:
            nk = cls.key(name)
            if len(nk) < 3:
                continue
            kd = cls.levenshtein(k, nk)
            spell = cls.levenshtein(squashed, "".join(c for c in name.lower() if c.isalnum()))
            ok = kd == 0 or (kd == 1 and len(nk) >= 4) or spell * 4 <= max(len(squashed), len(name))
            if ok and kd * 10 + spell < best_score:
                best, best_score = name, kd * 10 + spell
        return best
