"""Text tools: counts, readability, cases, find/replace, regex, extraction, diff, ciphers and fun."""
from __future__ import annotations

import difflib
import html
import re
import textwrap
import unicodedata
from collections import Counter
from typing import Literal

from . import ToolError, fmt, tool
from ..words import many

C = "text"
STOP = set("a an and are as at be but by for from has have he her his i in is it its me my of on or our she so that the their them "
           "there they this to was we were what when which who will with you your not no yes do does did can could would should".split())


@tool(C, ex={"text": "Echo is a helpful assistant. It answers quickly!"}, keys="count words characters sentences paragraphs length")
def text_stats(text: str) -> dict:
    """Words, characters, sentences, paragraphs, lines and reading/speaking time of a text."""
    words = re.findall(r"\b[\w'-]+\b", text)
    return {"words": len(words), "characters": len(text), "characters_no_spaces": len(re.sub(r"\s", "", text)),
            "sentences": len([s for s in re.split(r"[.!?]+", text) if s.strip()]), "paragraphs": len([p for p in re.split(r"\n\s*\n", text) if p.strip()]),
            "lines": len(text.splitlines()) or 1, "reading_time": f"{max(1, round(len(words) / 230))} min", "speaking_time": f"{max(1, round(len(words) / 140))} min"}


def _syllables(word: str) -> int:
    w = word.lower().strip(".,!?;:'\"")
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", w)))


@tool(C, ex={"text": "The cat sat on the mat. It was a sunny day and everyone was happy."}, keys="readability flesch reading ease grade level simple")
def readability(text: str) -> str:
    """Flesch reading ease and grade level (how easy a text is to read)."""
    words = re.findall(r"[A-Za-z']+", text)
    sents = max(1, len([s for s in re.split(r"[.!?]+", text) if s.strip()]))
    if not words:
        raise ToolError("no words to measure")
    syl = sum(_syllables(w) for w in words)
    ease = 206.835 - 1.015 * len(words) / sents - 84.6 * syl / len(words)
    grade = 0.39 * len(words) / sents + 11.8 * syl / len(words) - 15.59
    level = "very easy" if ease >= 80 else "easy" if ease >= 70 else "fairly easy" if ease >= 60 else "standard" if ease >= 50 else "difficult" if ease >= 30 else "very difficult"
    return f"Reading ease {fmt(round(ease, 1))} ({level}); about school grade {fmt(round(max(grade, 0), 1))}."


def _words(text):
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)
    return [w.lower() for w in re.findall(r"[A-Za-z0-9]+", spaced)]


@tool(C, ex={"text": "hello big world", "style": "camel"}, keys="uppercase lowercase title case camelcase snake_case kebab pascal")
def change_case(text: str, style: Literal["upper", "lower", "title", "sentence", "camel", "pascal", "snake", "kebab", "constant", "dot", "swap"]) -> str:
    """Change the case of text."""
    w = _words(text)
    return {"upper": text.upper(), "lower": text.lower(), "swap": text.swapcase(),
            "title": re.sub(r"[A-Za-z]+('[A-Za-z]+)?", lambda m: m.group(0).capitalize(), text),
            "sentence": re.sub(r"(^\s*|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text.lower()),
            "camel": (w[0] + "".join(x.capitalize() for x in w[1:])) if w else "", "pascal": "".join(x.capitalize() for x in w),
            "snake": "_".join(w), "kebab": "-".join(w), "constant": "_".join(w).upper(), "dot": ".".join(w)}[style]


@tool(C, ex={"text": "Héllo Wörld: 10 tips!"}, keys="url slug permalink")
def slugify(text: str) -> str:
    """Make a URL slug ('hello-world-10-tips')."""
    t = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return "-".join(re.findall(r"[a-z0-9]+", t.lower()))


@tool(C, ex={"text": "stressed"}, keys="backwards reverse")
def reverse_text(text: str, by: Literal["characters", "words", "lines"] = "characters") -> str:
    """Reverse text by characters, words or lines."""
    if by == "words":
        return " ".join(reversed(text.split()))
    if by == "lines":
        return "\n".join(reversed(text.splitlines()))
    return text[::-1]


@tool(C, ex={"text": "banana\napple\ncherry"}, keys="sort lines alphabetical order")
def sort_lines(text: str, order: Literal["a-z", "z-a", "number", "length"] = "a-z", unique: bool = False) -> str:
    """Sort lines (A–Z, Z–A, by number or length), optionally removing duplicates."""
    lines = text.splitlines()
    if unique:
        lines = list(dict.fromkeys(lines))
    if order == "number":
        def k(l):
            m = re.search(r"-?\d+(?:\.\d+)?", l)
            return (0, float(m.group(0))) if m else (1, 0)
        return "\n".join(sorted(lines, key=k))
    if order == "length":
        return "\n".join(sorted(lines, key=len))
    return "\n".join(sorted(lines, key=str.lower, reverse=order == "z-a"))


@tool(C, ex={"text": "a\nb\na\nc\nb"}, keys="duplicates unique dedupe")
def remove_duplicate_lines(text: str, ignore_case: bool = False) -> str:
    """Remove repeated lines, keeping the first of each."""
    seen, out = set(), []
    for l in text.splitlines():
        k = l.lower() if ignore_case else l
        if k not in seen:
            seen.add(k)
            out.append(l)
    return "\n".join(out)


@tool(C, ex={"text": "I like tea. Tea is great.", "find": "tea", "replace": "coffee", "ignore_case": True}, keys="replace substitute swap words")
def find_replace(text: str, find: str, replace: str, ignore_case: bool = False, whole_word: bool = False) -> str:
    """Find and replace in text (plain text, not regex)."""
    pat = re.escape(find)
    if whole_word:
        pat = rf"\b{pat}\b"
    out, n = re.subn(pat, lambda m: replace, text, flags=re.I if ignore_case else 0)
    return f"{out}\n\n({n} replaced)"


@tool(C, ex={"pattern": r"\d{3}-\d{4}", "text": "call 555-1234 or 555-9876"}, keys="regex regular expression test match")
def regex_test(pattern: str, text: str, ignore_case: bool = False) -> dict:
    """Test a regular expression: matches, positions and groups."""
    try:
        rx = re.compile(pattern, re.I if ignore_case else 0)
    except re.error as e:
        raise ToolError(f"bad pattern: {e}")
    ms = list(rx.finditer(text))[:50]
    return {"matches": len(ms), "found": [{"text": m.group(0), "start": m.start(), "groups": list(m.groups())} for m in ms]}


@tool(C, ex={"pattern": r"(\w+)@(\w+)\.com", "replace": r"\1 at \2", "text": "mail me: asha@example.com"}, keys="regex replace substitute")
def regex_replace(pattern: str, replace: str, text: str, ignore_case: bool = False) -> str:
    """Replace using a regular expression (\\1 for groups)."""
    try:
        return re.sub(pattern, replace, text, flags=re.I if ignore_case else 0)
    except re.error as e:
        raise ToolError(f"bad pattern: {e}")


@tool(C, ex={"text": "Contact asha@example.com or ravi.k@mail.co.in"}, keys="extract emails addresses")
def extract_emails(text: str) -> list:
    """Pull out every email address."""
    return list(dict.fromkeys(re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", text)))


@tool(C, ex={"text": "See https://python.org and www.echo.app/docs."}, keys="extract links urls web addresses")
def extract_links(text: str) -> list:
    """Pull out every web link."""
    return list(dict.fromkeys(m.rstrip(".,;)") for m in re.findall(r"https?://[^\s<>\"']+|www\.[^\s<>\"']+", text)))


@tool(C, ex={"text": "Call +91 98765 43210 or 040-2345-6789"}, keys="extract phone numbers mobile")
def extract_phone_numbers(text: str) -> list:
    """Pull out phone numbers."""
    found = re.findall(r"(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,5}\)?[\s-]?)?\d{3,5}[\s-]?\d{4,5}", text)
    return list(dict.fromkeys(f.strip() for f in found if len(re.sub(r"\D", "", f)) >= 8))


@tool(C, ex={"text": "Rent 12,500; food 4,320.50; travel -200"}, keys="extract numbers amounts")
def extract_numbers(text: str) -> list:
    """Pull out the numbers (commas understood)."""
    return [float(x.replace(",", "")) if "." in x else int(x.replace(",", "")) for x in re.findall(r"-?\d+(?:,\d{2,3})*(?:\.\d+)?", text)]


@tool(C, ex={"text": "Loving #python and #AI with @echo"}, keys="hashtags mentions social")
def extract_hashtags(text: str) -> dict:
    """Pull out #hashtags and @mentions."""
    return {"hashtags": list(dict.fromkeys(re.findall(r"#\w+", text))), "mentions": list(dict.fromkeys(re.findall(r"@\w+", text)))}


@tool(C, ex={"text": "the cat and the hat and the bat sat on the mat with the cat", "top": 5}, keys="word frequency most common keywords")
def word_frequency(text: str, top: int = 10, skip_common: bool = True) -> list:
    """Most common words (common words like 'the' skipped)."""
    words = [w for w in re.findall(r"[a-z']+", text.lower()) if not skip_common or w not in STOP]
    return [f"{w}: {n}" for w, n in Counter(words).most_common(max(1, min(top, 100)))]


@tool(C, ex={"text": "Python is a programming language. Python is popular for data science and AI. Many people learn Python."}, keys="summary key sentences extractive")
def key_sentences(text: str, count: int = 3) -> list:
    """The most important sentences of a text (by word frequency; no AI needed)."""
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.split()) > 3]
    freq = Counter(w for w in re.findall(r"[a-z']+", text.lower()) if w not in STOP)
    scored = sorted(sents, key=lambda s: -sum(freq[w] for w in re.findall(r"[a-z']+", s.lower())) / (len(s.split()) ** 0.5))
    keep = set(scored[:max(1, count)])
    return [s for s in sents if s in keep]


@tool(C, ex={"text": "Echo is a personal assistant that runs on your phone and computer.", "length": 30}, keys="shorten cut truncate")
def truncate(text: str, length: int = 100, ellipsis: str = "…") -> str:
    """Shorten text to a length at a word boundary."""
    if len(text) <= length:
        return text
    cut = text[:max(1, length - len(ellipsis))].rsplit(" ", 1)[0]
    return cut + ellipsis


@tool(C, ex={"text": "  too   many    spaces \n\n\n here  "}, keys="clean whitespace tidy spaces")
def clean_whitespace(text: str) -> str:
    """Collapse extra spaces and blank lines, trim each line."""
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


@tool(C, ex={"text": "Hello, world! (Test.)"}, keys="strip punctuation symbols")
def remove_punctuation(text: str) -> str:
    """Remove punctuation."""
    return "".join(c for c in text if not unicodedata.category(c).startswith("P"))


@tool(C, ex={"text": "A long sentence that needs wrapping at a narrow width for display.", "width": 20}, keys="wrap lines width column")
def wrap_text(text: str, width: int = 80) -> str:
    """Wrap text to a line width."""
    return "\n\n".join(textwrap.fill(" ".join(p.split()), max(10, width)) for p in re.split(r"\n\s*\n", text))


@tool(C, ex={"old": "the quick brown fox", "new": "the quick red fox jumps"}, keys="compare difference diff changes")
def text_diff(old: str, new: str) -> str:
    """Show what changed between two texts (line by line, or word by word for one-liners)."""
    if "\n" not in old and "\n" not in new:
        a, b = old.split(), new.split()
        out = []
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
            if op == "equal":
                out.append(" ".join(a[i1:i2]))
            if op in ("delete", "replace"):
                out.append("[-" + " ".join(a[i1:i2]) + "-]")
            if op in ("insert", "replace"):
                out.append("{+" + " ".join(b[j1:j2]) + "+}")
        return " ".join(out)
    return "\n".join(difflib.unified_diff(old.splitlines(), new.splitlines(), "old", "new", lineterm="")) or "No differences."


@tool(C, ex={"a": "colour", "b": "color"}, keys="similarity compare match fuzzy close")
def text_similarity(a: str, b: str) -> str:
    """How similar two texts are (0–100%)."""
    return fmt(round(difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() * 100, 1)) + "% similar"


@tool(C, ex={"word": "recieve", "options": ["receive", "recipe", "relieve", "believe"]}, keys="closest match spelling suggest fuzzy")
def closest_matches(word: str, options: list[str], count: int = 3) -> list:
    """The options closest in spelling to a word."""
    return difflib.get_close_matches(word, options, n=max(1, count), cutoff=0.3)


MORSE = {"a": ".-", "b": "-...", "c": "-.-.", "d": "-..", "e": ".", "f": "..-.", "g": "--.", "h": "....", "i": "..", "j": ".---", "k": "-.-",
         "l": ".-..", "m": "--", "n": "-.", "o": "---", "p": ".--.", "q": "--.-", "r": ".-.", "s": "...", "t": "-", "u": "..-", "v": "...-",
         "w": ".--", "x": "-..-", "y": "-.--", "z": "--..", "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
         "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.", ".": ".-.-.-", ",": "--..--", "?": "..--..", "!": "-.-.--"}


@tool(C, ex={"text": "SOS help"}, keys="morse code encode")
def to_morse(text: str) -> str:
    """Text to Morse code (/ between words)."""
    return " / ".join(" ".join(MORSE[c] for c in w if c in MORSE) for w in text.lower().split())


@tool(C, ex={"morse": "... --- ... / .... . .-.. .--."}, keys="morse code decode")
def from_morse(morse: str) -> str:
    """Morse code to text."""
    rev = {v: k for k, v in MORSE.items()}
    return " ".join("".join(rev.get(s, "?") for s in w.split()) for w in morse.strip().split("/")).upper()


NATO = "Alfa Bravo Charlie Delta Echo Foxtrot Golf Hotel India Juliett Kilo Lima Mike November Oscar Papa Quebec Romeo Sierra Tango Uniform Victor Whiskey X-ray Yankee Zulu".split()


@tool(C, ex={"text": "PNR 4521 AB"}, keys="nato phonetic spell out alphabet")
def nato_spelling(text: str) -> str:
    """Spell text with the NATO phonetic alphabet (Alfa, Bravo…)."""
    digits = "Zero One Two Three Four Five Six Seven Eight Nine".split()
    out = []
    for c in text:
        if c.isalpha() and c.isascii():
            out.append(NATO[ord(c.lower()) - 97])
        elif c.isdigit():
            out.append(digits[int(c)])
        elif c == " ":
            out.append("(space)")
    return " ".join(out)


@tool(C, ex={"text": "Hello", "shift": 3}, keys="caesar cipher rot13 encrypt fun secret code")
def caesar_cipher(text: str, shift: int = 13, decode: bool = False) -> str:
    """Caesar cipher (shift 13 = ROT13). For fun, not security."""
    s = (-shift if decode else shift) % 26
    return "".join(chr((ord(c) - b + s) % 26 + b) if c.isascii() and c.isalpha() else c for c in text for b in [65 if c.isupper() else 97])


@tool(C, ex={"text": "Never odd or even"}, keys="palindrome check")
def is_palindrome(text: str) -> str:
    """Does text read the same backwards (ignoring spaces and punctuation)?"""
    t = re.sub(r"[^a-z0-9]", "", text.lower())
    return "Yes, it's a palindrome." if t and t == t[::-1] else "No, not a palindrome."


@tool(C, ex={"a": "listen", "b": "silent"}, keys="anagram check letters")
def is_anagram(a: str, b: str) -> str:
    """Are two words or phrases anagrams of each other?"""
    k = lambda s: sorted(re.sub(r"[^a-z]", "", s.lower()))
    return "Yes, they're anagrams." if k(a) == k(b) and k(a) else "No, they aren't anagrams."


@tool(C, ex={"text": "Mississippi", "character": "s"}, keys="count letter occurrences how many times")
def count_occurrences(text: str, character: str, ignore_case: bool = True) -> str:
    """How many times a letter, word or phrase appears."""
    t, c = (text.lower(), character.lower()) if ignore_case else (text, character)
    return f"{many(t.count(c), 'time')}."


@tool(C, ex={"text": "Echo"}, keys="letters vowels consonants count")
def letter_breakdown(text: str) -> dict:
    """Letters, vowels, consonants, digits, spaces and symbols in text."""
    letters = [c for c in text if c.isalpha()]
    vowels = [c for c in letters if c.lower() in "aeiou"]
    return {"letters": len(letters), "vowels": len(vowels), "consonants": len(letters) - len(vowels), "digits": sum(c.isdigit() for c in text),
            "spaces": text.count(" "), "symbols": sum(not c.isalnum() and not c.isspace() for c in text)}


@tool(C, ex={"words": 40}, keys="lorem ipsum placeholder dummy filler text")
def lorem_ipsum(words: int = 50) -> str:
    """Placeholder text."""
    base = ("lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore et dolore magna aliqua ut "
            "enim ad minim veniam quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat").split()
    w = [base[i % len(base)] for i in range(max(1, min(words, 2000)))]
    return " ".join(w).capitalize() + "."


@tool(C, ex={"text": "Portable Network Graphics"}, keys="acronym initials abbreviation")
def make_acronym(text: str) -> str:
    """Make an acronym from a phrase."""
    return "".join(w[0].upper() for w in re.findall(r"[A-Za-z0-9]+", text) if w.lower() not in ("of", "and", "the", "for", "a", "an"))


@tool(C, ex={"text": "Hi"}, keys="binary text bits ascii")
def text_to_binary(text: str) -> str:
    """Text to binary (UTF-8 bytes)."""
    return " ".join(f"{b:08b}" for b in text.encode())


@tool(C, ex={"binary": "01001000 01101001"}, keys="binary text decode bits")
def binary_to_text(binary: str) -> str:
    """Binary (8-bit groups) back to text."""
    bits = re.sub(r"[^01]", "", binary)
    if len(bits) % 8:
        raise ToolError("binary must be in groups of 8 bits")
    return bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8)).decode("utf-8", errors="replace")


@tool(C, ex={"text": "é₹😀"}, keys="unicode character name code point info")
def character_info(text: str) -> list:
    """Unicode name and code point of each character (up to 40)."""
    return [f"{c!r} U+{ord(c):04X} {unicodedata.name(c, '(no name)')}" for c in text[:40]]


@tool(C, ex={"query": "heart"}, keys="emoji find search symbol")
def find_emoji(query: str, limit: int = 15) -> list:
    """Find emoji and symbols by name ('heart', 'rupee', 'arrow')."""
    q = query.upper().split()
    out = []
    for cp in list(range(0x2190, 0x2C00)) + list(range(0x1F300, 0x1FAFF)) + [0x20B9]:
        name = unicodedata.name(chr(cp), "")
        if name and all(w in name for w in q):
            out.append(f"{chr(cp)} {name.title()}")
            if len(out) >= limit:
                break
    return out or ["Nothing found."]


@tool(C, ex={"text": "<p>Hello <b>world</b> &amp; friends</p>"}, keys="strip html tags plain text")
def html_to_text(text: str) -> str:
    """HTML to plain text."""
    from ..internet import readable
    return readable(text)[1] or html.unescape(re.sub(r"<[^>]+>", "", text))


@tool(C, ex={"text": "# Title\n\nSome **bold** and [a link](https://x.org).\n\n- item"}, keys="markdown plain text strip formatting")
def markdown_to_text(text: str) -> str:
    """Markdown to plain text."""
    t = re.sub(r"```.*?```", lambda m: m.group(0).strip("`"), text, flags=re.S)
    t = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", t)
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.M)
    t = re.sub(r"(\*\*|__|\*|_|`)(.+?)\1", r"\2", t)
    return re.sub(r"^\s*[-*+]\s+", "• ", t, flags=re.M)


@tool(C, ex={"text": "apples\nbananas\ncherries", "style": "numbered"}, keys="bullet list numbered checklist")
def make_list(text: str, style: Literal["bullets", "numbered", "checklist", "comma"] = "bullets") -> str:
    """Turn lines into a bulleted, numbered, checklist or comma-separated list."""
    items = [l.strip(" -*•\t") for l in re.split(r"\n|;", text) if l.strip(" -*•\t")]
    if style == "comma":
        return ", ".join(items[:-1]) + (" and " + items[-1] if len(items) > 1 else (items[0] if items else ""))
    mark = {"bullets": lambda i: "•", "numbered": lambda i: f"{i}.", "checklist": lambda i: "☐"}[style]
    return "\n".join(f"{mark(i)} {x}" for i, x in enumerate(items, 1))


@tool(C, ex={"rows": [["Name", "Age"], ["Asha", "31"], ["Ravi", "28"]]}, keys="table align columns format")
def text_table(rows: list[list[str]]) -> str:
    """Line up rows into a neat text table."""
    if not rows:
        raise ToolError("no rows")
    rows = [[str(c) for c in r] for r in rows]
    w = [max(len(r[i]) if i < len(r) else 0 for r in rows) for i in range(max(map(len, rows)))]
    lines = ["  ".join((r[i] if i < len(r) else "").ljust(w[i]) for i in range(len(w))).rstrip() for r in rows]
    lines.insert(1, "  ".join("-" * x for x in w))
    return "\n".join(lines)


@tool(C, ex={"text": "line one\nline two"}, keys="line numbers number lines")
def number_lines(text: str, start: int = 1) -> str:
    """Add line numbers."""
    lines = text.splitlines()
    w = len(str(start + len(lines)))
    return "\n".join(f"{i:>{w}}  {l}" for i, l in enumerate(lines, start))


@tool(C, ex={"text": "pig latin is fun"}, keys="pig latin fun game")
def pig_latin(text: str) -> str:
    """Translate into Pig Latin (a word game)."""
    def pl(w):
        m = re.match(r"([^aeiouAEIOU]*)(.*)", w)
        return (m.group(2) + m.group(1) + "ay") if m.group(1) else w + "way"
    return " ".join(pl(w) if w.isalpha() else w for w in text.split())


@tool(C, ex={"text": "naïve café Ångström"}, keys="accents diacritics ascii transliterate")
def remove_accents(text: str) -> str:
    """Remove accents (café → cafe)."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


@tool(C, ex={"text": "He said “hi” — it’s fine…"}, keys="smart quotes straight plain ascii punctuation")
def straighten_quotes(text: str) -> str:
    """Curly quotes, long dashes and ellipses to plain ASCII."""
    return text.translate(str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", "…": "...", " ": " "}))


@tool(C, ex={"text": "apple, banana, cherry", "separator": ","}, keys="split text into lines separator")
def split_text(text: str, separator: str = ",") -> list:
    """Split text into pieces by a separator."""
    return [p.strip() for p in text.split(separator if separator else None) if p.strip()]


@tool(C, ex={"items": ["a", "b", "c"], "separator": " | "}, keys="join combine merge lines")
def join_items(items: list[str], separator: str = ", ") -> str:
    """Join pieces into one line with a separator."""
    return separator.join(map(str, items))


@tool(C, ex={"text": "Echo", "width": 20, "fill": "*"}, keys="pad center align left right")
def pad_text(text: str, width: int, align: Literal["left", "right", "center"] = "center", fill: str = " ") -> str:
    """Pad text to a width (left, right or centre)."""
    f = (fill or " ")[0]
    return {"left": text.ljust, "right": text.rjust, "center": text.center}[align](width, f)


@tool(C, ex={"text": "ha", "times": 3}, keys="repeat duplicate")
def repeat_text(text: str, times: int, separator: str = "") -> str:
    """Repeat text a number of times."""
    return separator.join([text] * max(1, min(times, 1000)))


@tool(C, ex={"text": "The quick brown fox jumps over the lazy dog"}, keys="pangram all letters alphabet")
def is_pangram(text: str) -> str:
    """Does text use every letter of the alphabet? Lists missing letters."""
    missing = sorted(set("abcdefghijklmnopqrstuvwxyz") - set(text.lower()))
    return "Yes, every letter is used." if not missing else "Missing: " + ", ".join(missing)
