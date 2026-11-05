"""The Command Pack (shared/commands/*.json) for EchoDesktop: rule-for-rule mirror of the phone's CommandCatalog.kt.

Pure (no Windows calls); tested in tests/test_catalog.py together with shared/command_tests.json.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED = REPO_ROOT / "shared"

# --------------------------------------------------------------------------- speech normalisation

CONTRACTIONS = {
    "what's": "what is", "whats": "what is", "where's": "where is", "wheres": "where is", "who's": "who is",
    "whos": "who is", "how's": "how is", "when's": "when is", "why's": "why is", "it's": "it is", "that's": "that is",
    "thats": "that is", "there's": "there is", "here's": "here is", "let's": "let us", "i'm": "i am", "i'd": "i would",
    "i'll": "i will", "i've": "i have", "you're": "you are", "we're": "we are", "they're": "they are",
    "can't": "cannot", "cant": "cannot", "won't": "will not", "don't": "do not", "dont": "do not",
    "doesn't": "does not", "isn't": "is not", "aren't": "are not", "didn't": "did not", "wasn't": "was not",
    "couldn't": "could not", "shouldn't": "should not", "wouldn't": "would not", "what're": "what are",
    "how're": "how are", "u": "you", "ur": "your", "pls": "please", "plz": "please", "wanna": "want to",
    "gonna": "going to", "gimme": "give me", "lemme": "let me", "whatcha": "what are you",
}
PREFIX_FILLERS = sorted((f.split() for f in [
    "hey echo", "ok echo", "okay echo", "hi echo", "hello echo", "yo echo", "echo", "ok google", "okay google", "hey google",
    "hey siri", "siri", "alexa", "hey alexa", "ok alexa", "cortana", "hey cortana", "hey", "ok", "okay", "alright",
    "please", "kindly", "can you", "could you", "would you", "will you", "i want to", "i would like to", "i need to",
    "i want you to", "i would like you to", "i need you to", "go ahead and", "just", "quickly", "now", "so", "um",
    "uh", "hmm", "well"]), key=len, reverse=True)
SUFFIX_FILLERS = sorted((f.split() for f in [
    "please", "for me", "now", "right now", "thanks", "thank you", "echo", "real quick", "quickly"]), key=len, reverse=True)
EDGE = "\"“”‘’'.,!?;:"


def _word_char(c: str) -> bool:
    return unicodedata.category(c)[0] in "LM" or c.isdecimal()


def _digit(c: str) -> bool:
    return c.isdecimal()


def token_words(token: str) -> list:
    """One raw token -> zero or more normalised words (same rules as SpeechNorm.tokenWords)."""
    s = token.lower().replace("’", "'").replace("‘", "'").replace("ʼ", "'")
    out = []
    for i, c in enumerate(s):
        prev = s[i - 1] if i > 0 else " "
        nxt = s[i + 1] if i + 1 < len(s) else " "
        if _word_char(c) or c in "'+*^=":
            out.append(c)
        elif c == "&":
            out.append(" and ")
        elif c == "%":
            out.append(" percent ")
        elif c == "," and _digit(prev) and _digit(nxt):
            continue
        elif c in ".:/" and _digit(prev) and _digit(nxt):
            out.append(c)
        elif c == "-" and (_digit(nxt) or (_word_char(prev) and _word_char(nxt))):
            out.append(c)
        else:
            out.append(" ")
    words = []
    for w in "".join(out).split(" "):
        w = w.strip("'")
        if w:
            words.extend(CONTRACTIONS.get(w, w).split(" "))
    return words


def trim_edges(text: str) -> str:
    return text.strip().strip(EDGE + " \t")


class Utterance:
    def __init__(self, words: list, origin: list, raw: list, start: int = 0, end: Optional[int] = None):
        self._all, self._origin, self._raw = words, origin, raw
        self._from = start
        self._to = len(words) if end is None else end

    @property
    def words(self) -> list:
        return self._all[self._from:self._to]

    @property
    def size(self) -> int:
        return self._to - self._from

    @property
    def text(self) -> str:
        return "" if self.size == 0 else " ".join(self.words) + " "

    def slice(self, a: int, b: int) -> "Utterance":
        return Utterance(self._all, self._origin, self._raw, self._from + a, self._from + b)

    def raw_from(self, index: int) -> Optional[str]:
        k = self._from + index
        if k >= len(self._all) or (k > 0 and self._origin[k - 1] == self._origin[k]):
            return None
        return " ".join(self._raw[self._origin[k]:])

    def raw_until(self, count: int) -> Optional[str]:
        if count <= 0:
            return None
        k = self._from + count - 1
        if k + 1 < len(self._all) and self._origin[k + 1] == self._origin[k]:
            return None
        return " ".join(self._raw[:self._origin[k] + 1])

    def span(self, start: int, end: int) -> str:
        offset, first, last = 0, -1, -1
        words = self.words
        for i, w in enumerate(words):
            if offset == start:
                first = i
            offset += len(w) + 1
            if offset == end:
                last = i
                break
        if first < 0 or last < first:
            return self.text[start:end].strip()
        a, b = self._from + first, self._from + last
        aligned = (a == 0 or self._origin[a - 1] != self._origin[a]) and (b == len(self._all) - 1 or self._origin[b + 1] != self._origin[b])
        if aligned:
            return trim_edges(" ".join(self._raw[self._origin[a]:self._origin[b] + 1]))
        return " ".join(self._all[a:b + 1])


def utterance(raw: str) -> Utterance:
    tokens = [t for t in raw.strip().split() if t]
    words, origin = [], []
    for i, t in enumerate(tokens):
        for w in token_words(t):
            words.append(w)
            origin.append(i)
    return Utterance(words, origin, tokens)


def strip_prefix(u: Utterance) -> Utterance:
    while True:
        w = u.words
        f = next((f for f in PREFIX_FILLERS if len(f) < len(w) and w[:len(f)] == f), None)
        if f is None:
            return u
        u = u.slice(len(f), u.size)


def strip_suffix(u: Utterance) -> Utterance:
    while True:
        w = u.words
        f = next((f for f in SUFFIX_FILLERS if len(f) < len(w) and w[len(w) - len(f):] == f), None)
        if f is None:
            return u
        u = u.slice(0, u.size - len(f))


def suffix_steps(u: Utterance) -> list:
    """u, then u minus one trailing filler at a time ("... from now please" keeps "now" once "please" is gone)."""
    out = [u]
    while True:
        w = u.words
        f = next((f for f in SUFFIX_FILLERS if len(f) < len(w) and w[len(w) - len(f):] == f), None)
        if f is None:
            return out
        u = u.slice(0, u.size - len(f))
        out.append(u)


def strip_prefix_raw(raw: str) -> str:
    u = utterance(raw)
    s = strip_prefix(u)
    return raw if s.size == u.size else (u.raw_from(u.size - s.size) or raw)


def strip_suffix_raw(raw: str) -> str:
    u = utterance(raw)
    s = strip_suffix(u)
    return raw if s.size == u.size else (u.raw_until(s.size) or raw)


# --------------------------------------------------------------------------- grammar

ANY, EMPTY = "*", ""
ALL = "all"      # slot every match has: the whole request as said (minus wake/politeness words)
_SLOT = re.compile(r"[a-z][a-z0-9]{0,15}")
_NUMBER_SLOT = re.compile(r"n[0-9]?")


def is_number_slot(name: str) -> bool:
    return bool(_NUMBER_SLOT.fullmatch(name))


@dataclass
class Word:
    w: str


@dataclass
class Slot:
    name: str


@dataclass
class Group:
    options: list
    optional: bool


def _tokenize(p: str) -> list:
    out, word, i = [], [], 0

    def flush():
        if word:
            out.append("".join(word))
            word.clear()
    while i < len(p):
        c = p[i]
        if c in "()[]|":
            flush()
            out.append(c)
        elif c == "{":
            flush()
            end = p.find("}", i)
            if end < 0:
                raise ValueError(f"unclosed slot in “{p}”")
            name = p[i + 1:end]
            if not _SLOT.fullmatch(name):
                raise ValueError(f"bad slot name {{{name}}}")
            out.append("{" + name + "}")
            i = end
        elif c.isspace():
            flush()
        else:
            word.append(c)
        i += 1
    flush()
    return out


def parse_pattern(pattern: str) -> list:
    tokens = _tokenize(pattern)
    pos = 0

    def seq():
        nonlocal pos
        out = []
        while pos < len(tokens) and tokens[pos] not in (")", "]", "|"):
            t = tokens[pos]
            pos += 1
            if t in ("(", "["):
                close = ")" if t == "(" else "]"
                options = [seq()]
                while pos < len(tokens) and tokens[pos] == "|":
                    pos += 1
                    options.append(seq())
                if pos >= len(tokens) or tokens[pos] != close:
                    raise ValueError(f"unbalanced {t} in “{pattern}”")
                pos += 1
                if any(not o for o in options):
                    raise ValueError(f"empty alternative in “{pattern}”")
                out.append(Group(options, t == "["))
            elif t.startswith("{"):
                out.append(Slot(t[1:-1]))
            else:
                out.extend(Word(w) for w in token_words(t))
        return out
    nodes = seq()
    if pos != len(tokens):
        raise ValueError(f"unexpected “{tokens[pos]}” in “{pattern}”")
    if not nodes:
        raise ValueError("empty pattern")
    names = slot_names(nodes)
    if len(names) != len(set(names)):
        raise ValueError(f"repeated slot in “{pattern}”")
    if EMPTY in first(nodes):
        raise ValueError(f"pattern can match nothing: “{pattern}”")
    _check_adjacent(nodes, pattern)
    return nodes


def slot_names(nodes: list) -> list:
    out = []
    for n in nodes:
        if isinstance(n, Slot):
            out.append(n.name)
        elif isinstance(n, Group):
            for o in n.options:
                out.extend(slot_names(o))
    return out


def _check_adjacent(nodes: list, pattern: str) -> None:
    for a, b in zip(nodes, nodes[1:]):
        if isinstance(a, Slot) and isinstance(b, Slot) and not is_number_slot(a.name) and not is_number_slot(b.name):
            raise ValueError(f"two free-text slots side by side in “{pattern}”")
    for n in nodes:
        if isinstance(n, Group):
            for o in n.options:
                _check_adjacent(o, pattern)


def first(nodes: list) -> set:
    out = set()
    for n in nodes:
        if isinstance(n, Word):
            f = {n.w}
        elif isinstance(n, Slot):
            f = {ANY}
        else:
            f = set().union(*(first(o) for o in n.options)) | ({EMPTY} if n.optional else set())
        out |= f - {EMPTY}
        if EMPTY not in f:
            return out
    out.add(EMPTY)
    return out


def literals(nodes: list) -> int:
    total = 0
    for n in nodes:
        if isinstance(n, Word):
            total += 1
        elif isinstance(n, Group) and not n.optional:
            total += min(literals(o) for o in n.options)
    return total


def variants(nodes: list) -> int:
    total = 1
    for n in nodes:
        if isinstance(n, Group):
            total *= sum(variants(o) for o in n.options) + (1 if n.optional else 0)
    return total


def to_regex(nodes: list) -> str:
    out = []
    for n in nodes:
        if isinstance(n, Word):
            out.append(re.escape(n.w) + " ")
        elif isinstance(n, Slot):
            out.append(r"(-?[0-9]+(?:\.[0-9]+)? )" if is_number_slot(n.name) else "(.+? )")
        else:
            out.append("(?:" + "|".join(to_regex(o) for o in n.options) + ")" + ("?" if n.optional else ""))
    return "".join(out)


def samples(nodes: list, fill: Callable[[str], str]) -> list:
    """The plain phrasing plus one variant per alternative (sum, not product)."""
    infos = []  # (group, parent index, parent option)

    def collect(seq, parent, option):
        for n in seq:
            if isinstance(n, Group):
                infos.append((n, parent, option))
                me = len(infos) - 1
                for i, o in enumerate(n.options):
                    collect(o, me, i)
    collect(nodes, -1, -1)
    base = [-1 if g.optional else 0 for g, _, _ in infos]

    def render(choice):
        words = []

        def walk(seq):
            for n in seq:
                if isinstance(n, Word):
                    words.append(n.w)
                elif isinstance(n, Slot):
                    words.append(fill(n.name))
                else:
                    c = choice[next(i for i, info in enumerate(infos) if info[0] is n)]
                    if c >= 0:
                        walk(n.options[c])
        walk(nodes)
        return " ".join(words)
    out = [render(base)]
    for index, (group, parent, parent_option) in enumerate(infos):
        for option in range(len(group.options)):
            choice = list(base)
            choice[index] = option
            p, o = parent, parent_option
            while p >= 0:
                choice[p] = o
                _, up, up_option = infos[p]
                p, o = up, up_option
            text = render(choice)
            if text not in out:
                out.append(text)
    return out


# --------------------------------------------------------------------------- catalog

@dataclass(frozen=True)
class Command:
    id: str
    group: str
    title: str
    phrases: tuple
    spec: dict = field(compare=False, hash=False)
    say: Optional[str]
    examples: tuple
    order: int
    fallback: bool = False                      # loose keyword intent: tried after every specific phrase
    unless: object = field(default=None, compare=False, hash=False)   # regex of veto words

    @property
    def kind(self) -> str:
        return self.spec["kind"]

    SEARCH_PAGE_KINDS = ("web", "maps", "directions")

    @property
    def search_page(self) -> bool:
        """The command's whole job is to show a page of search results (Google, maps, directions, a site's search).
        Echo's AI answers these itself, and still opens the site when you want to watch, listen or shop there."""
        return self.kind in self.SEARCH_PAGE_KINDS


@dataclass(frozen=True)
class Match:
    command: Command
    slots: dict = field(compare=False, hash=False)


@dataclass
class _Compiled:
    command: Command
    source: str
    _nodes: Optional[list]
    pattern: str                 # regex source; compiled on first use (most of the ~7,000 are never needed in a session)
    slots: list
    literals: int
    first: set
    index: int
    _regex: Optional[re.Pattern] = field(default=None, repr=False, compare=False)

    @property
    def regex(self) -> re.Pattern:
        r = self._regex
        if r is None:
            r = self._regex = re.compile(self.pattern)
        return r

    @property
    def nodes(self) -> list:
        if self._nodes is None:
            self._nodes = parse_pattern(self.source)
        return self._nodes

    def __getstate__(self):                  # the disk cache stores sources, not compiled regexes or parse trees
        state = dict(self.__dict__)
        state["_regex"] = None
        state["_nodes"] = None
        return state


_ID = re.compile(r"[a-z0-9_.-]{3,60}")
_VAR = re.compile(r"\$([A-Z][A-Z0-9]*)")
_PLACEHOLDER = re.compile(r"\{([a-z][a-z0-9]*)\}")


def fill(template: str, slots: dict, transform: Callable[[str], str] = lambda s: s) -> str:
    return _PLACEHOLDER.sub(lambda m: transform(slots[m.group(1)]) if m.group(1) in slots else "", template)


def placeholders(template: str) -> set:
    return set(_PLACEHOLDER.findall(template))


def common_slots(node_lists: list) -> set:
    sets = [set(slot_names(n)) for n in node_lists]
    return (set.intersection(*sets) if sets else set()) | {ALL}


class Catalog:
    def __init__(self, commands: list, errors: list, compiled: list):
        self.commands = commands
        self.errors = errors
        self.patterns = compiled
        self._by_id = {c.id: c for c in commands}
        self._exact = self._index([c for c in compiled if not c.slots])
        self._templates = self._index([c for c in compiled if c.slots])

    @staticmethod
    def _index(items):
        buckets, wild = {}, []
        for c in items:
            if ANY in c.first:
                wild.append(c)
            else:
                for w in c.first:
                    buckets.setdefault(w, []).append(c)
        return buckets, wild

    def __getstate__(self):
        state = dict(self.__dict__)
        state.pop("_order", None)           # keyed by object ids: rebuilt after loading
        return state

    def by_id(self, cid: str) -> Optional[Command]:
        return self._by_id.get(cid)

    def precompile(self) -> int:
        """Compile the patterns every request is tried against (those that can start with any word), so the first
        command after start-up doesn't pay for them. Meant for a background thread; returns how many."""
        n = 0
        for _, wild in (self._exact, self._templates):
            for c in wild:
                c.regex
                n += 1
        return n

    @property
    def variant_count(self) -> int:
        return sum(variants(p.nodes) for p in self.patterns)

    def match_exact(self, raw: str) -> Optional[Match]:
        return self._match(raw, self._exact, lambda m: True)

    def match_template(self, raw: str, accept=lambda m: True) -> Optional[Match]:
        return self._match(raw, self._templates, accept)

    def match(self, raw: str, accept=lambda m: True) -> Optional[Match]:
        return self.match_exact(raw) or self.match_template(raw, accept)

    def _match(self, raw: str, index, accept) -> Optional[Match]:
        as_said = utterance(raw)
        if as_said.size == 0:
            return None
        core = strip_prefix(as_said)
        variants_, seen = [], set()
        for u in [as_said] + suffix_steps(core):
            if u.text not in seen:
                seen.add(u.text)
                variants_.append(u)
        buckets, wild = index
        order = self.__dict__.setdefault("_order", {})        # candidate order never changes: sort once per first word
        for u in variants_:
            key = (id(index), u.words[0])
            candidates = order.get(key)
            if candidates is None:
                if len(order) > 4000:
                    order.clear()
                candidates = order[key] = sorted(buckets.get(u.words[0], []) + wild,
                                                 key=lambda c: (c.command.fallback, -c.literals, c.command.order, c.index))
            for c in candidates:
                m = c.regex.fullmatch(u.text)
                if not m or (c.command.unless is not None and c.command.unless.search(u.text)):
                    continue
                slots = {}
                for i, name in enumerate(c.slots):
                    if m.group(i + 1) is not None:
                        slots[name] = u.span(m.start(i + 1), m.end(i + 1))
                slots[ALL] = u.span(0, len(u.text))
                result = Match(c.command, slots)
                if accept(result):
                    return result
        return None

    @staticmethod
    def parse(files: list, platform: str, check_spec: Callable) -> "Catalog":
        """files: [(name, json text)] in file-name order; families are local to their file."""
        errors, commands, compiled, seen, order = [], [], [], set(), 0
        for file_name, text in files:
            try:
                root = json.loads(text)
            except ValueError as e:
                errors.append(f"{file_name}: {e}")
                continue
            families = root.get("families", {})
            for member in root.get("commands", []):
                order += 1
                cid = member.get("id", "") if isinstance(member, dict) else ""
                try:
                    if not _ID.fullmatch(cid):
                        raise ValueError("bad id")
                    if cid in seen:
                        raise ValueError("duplicate id")
                    seen.add(cid)
                    family = None
                    if "family" in member:
                        family = families.get(member["family"])
                        if family is None:
                            raise ValueError(f"unknown family {member['family']}")
                    variables = {k: v for k, v in member.items() if re.fullmatch(r"[A-Z][A-Z0-9]*", k)}
                    if any(not isinstance(v, str) for v in variables.values()):
                        raise ValueError("variables must be text")

                    def sub(t: str) -> str:
                        def rep(m):
                            if m.group(1) not in variables:
                                raise ValueError(f"missing {m.group(0)}")
                            return variables[m.group(1)]
                        return _VAR.sub(rep, t)

                    def fld(key):
                        if key in member:
                            return member[key]
                        return family.get(key) if family else None
                    platforms = fld("platforms")
                    if platforms is not None and platform not in platforms:
                        continue
                    spec_json = fld(platform) if isinstance(fld(platform), dict) else fld("do")
                    if not isinstance(spec_json, dict):
                        continue
                    if any(not isinstance(v, str) for v in spec_json.values()):
                        raise ValueError("spec values must be text")
                    spec = {k: sub(v) for k, v in spec_json.items()}
                    if not spec.get("kind"):
                        raise ValueError("spec has no kind")
                    phrases = [sub(p) for p in (family.get("phrases", []) if family else []) + member.get("phrases", []) if isinstance(p, str) and p.strip()]
                    if not phrases:
                        raise ValueError("no phrases")
                    nodes = [parse_pattern(p) for p in phrases]
                    problem = check_spec(spec, nodes)
                    if problem:
                        raise ValueError(problem)
                    command = Command(cid, sub(fld("group") or "Other"), sub(fld("title") or phrases[0]), tuple(phrases), spec,
                                      sub(fld("say")) if isinstance(fld("say"), str) else None,
                                      tuple(e for e in member.get("examples", []) if isinstance(e, str)), order,
                                      fld("fallback") is True,
                                      re.compile(r"\b(?:" + fld("unless") + r")\b") if isinstance(fld("unless"), str) else None)
                    commands.append(command)
                    for i, n in enumerate(nodes):
                        compiled.append(_Compiled(command, phrases[i], n, to_regex(n), slot_names(n), literals(n), first(n), i))
                except ValueError as e:
                    errors.append(f"{file_name}/{cid}: {e}")
        return Catalog(commands, errors, compiled)


EMPTY_CATALOG = Catalog([], [], [])


def load_files(directory: Path = SHARED / "commands") -> list:
    return [(p.name, p.read_text(encoding="utf-8")) for p in sorted(directory.glob("*.json"))]


# --------------------------------------------------------------------------- desktop kinds

DESKTOP_KINDS = {"web", "open", "maps", "directions", "tool", "say", "content", "echo", "list",
                 "ms_settings", "folder", "win_tool", "win_key", "power", "status",
                 # PC control pack (pcctl.py): keyboard shortcuts, typed text, mouse, windows, apps, clipboard, system
                 "keys", "text", "mouse", "window", "app_window", "clip", "sys",
                 # More pack: live answers from the internet, offline developer tools, act on the selected text, MCP
                 "net", "dev", "selection", "mcp"}
SELECTION_OPS = {"SEARCH", "YOUTUBE", "TRANSLATE", "MAP", "OPEN_LINK", "EMAIL", "WHATSAPP", "DEFINE", "WIKI", "SAVE_NOTE",
                 "IMAGES", "AMAZON", "SPEAK",
                 # these ask the AI (FreeLLMAPI) about the selected text
                 "SUMMARIZE", "EXPLAIN", "EXPLAIN_SIMPLE", "EXPLAIN_CODE", "FIND_BUGS", "CHECK_SCAM", "REPLY_DRAFT",
                 "TITLE_IDEAS", "KEY_POINTS", "ACTION_ITEMS",
                 # these ask the AI and paste the result over the selection (undo with ctrl+z)
                 "FIX_GRAMMAR", "REWRITE_FORMAL", "REWRITE_FRIENDLY", "SHORTER", "LONGER", "BULLET_SUMMARY", "ADD_COMMENTS",
                 "TRANSLATE_INPLACE", "SIMPLIFY", "POLITE"}
AI_SELECTION_OPS = {"SUMMARIZE", "EXPLAIN", "EXPLAIN_SIMPLE", "EXPLAIN_CODE", "FIND_BUGS", "CHECK_SCAM", "REPLY_DRAFT",
                    "TITLE_IDEAS", "KEY_POINTS", "ACTION_ITEMS", "FIX_GRAMMAR", "REWRITE_FORMAL", "REWRITE_FRIENDLY", "SHORTER",
                    "LONGER", "BULLET_SUMMARY", "ADD_COMMENTS", "TRANSLATE_INPLACE", "SIMPLIFY", "POLITE"}
MCP_OPS = {"TOOLS", "PRESETS", "ADD", "REMOVE", "TRUST", "UNTRUST", "AI_ON", "AI_OFF", "ECHO_CONFIG", "ECHO_CLAUDE_CODE",
           "OPEN_WINDOW", "COUNT", "STATUS",
           # Echo's built-in toolbox
           "FIND_TOOL", "TOOL_CATEGORIES", "TOOLBOX_COUNT", "TOOLS_WINDOW", "RUN_GOAL", "TOOL"}
MOUSE_OPS = {"click", "double_click", "triple_click", "right_click", "middle_click", "hold", "release", "scroll_up",
             "scroll_down", "scroll_left", "scroll_right", "move_up", "move_down", "move_left", "move_right", "center",
             "top_left", "top_right", "bottom_left", "bottom_right", "window_center", "at", "faster", "slower", "where"}
WINDOW_OPS = {"maximize", "minimize", "restore", "close", "snap_left", "snap_right", "snap_top_left", "snap_top_right",
              "snap_bottom_left", "snap_bottom_right", "top_half", "bottom_half", "center", "bigger", "smaller", "on_top",
              "not_on_top", "transparent", "opaque", "which", "list", "minimize_others"}
CLIP_OPS = {"READ", "CLEAR", "UPPER", "LOWER", "TITLE", "SENTENCE", "TRIM", "SORT_LINES", "REVERSE_LINES", "DEDUPE_LINES",
            "JOIN_LINES", "COUNT", "SPELL_OUT", "QUOTE", "BRACKETS", "BULLETS", "NUMBERED", "SLUG", "SNAKE", "CAMEL",
            # developer & tidy-up transforms (pcctl._dev_transform) and read-only checks (pcctl.ASK_OPS)
            "JSON_PRETTY", "JSON_MINIFY", "B64_ENC", "B64_DEC", "URL_ENC", "URL_DEC", "HTML_ESC", "HTML_UNESC", "STRIP_HTML",
            "ESCAPE_STR", "UNESCAPE_STR", "KEBAB", "PASCAL", "CONSTANT", "DOT_CASE", "TRAIN", "SWAP_CASE", "REVERSE_TEXT",
            "SORT_NUMERIC", "SORT_DESC", "SHUFFLE_LINES", "REMOVE_EMPTY", "LINE_NUMBERS", "TRIM_LINES", "SQL_IN", "JSON_ARRAY",
            "CSV_TO_MD", "COMMENT_HASH", "COMMENT_SLASH", "UNCOMMENT", "INDENT", "DEDENT", "TABS_TO_SPACES", "SPACES_TO_TABS",
            "STRAIGHT_QUOTES", "REMOVE_ACCENTS", "ONE_SPACE_AFTER", "WRAP_80", "MARKDOWN_LINK", "EMAILS_ONLY", "URLS_ONLY",
            "NUMBERS_ONLY", "READ_SELECTION", "JSON_CHECK", "JWT_DECODE", "SUM_NUMBERS", "COUNT_LINES"}
SYS_OPS = {"DARK_ON", "DARK_OFF", "BRIGHTER", "DIMMER", "BRIGHTNESS_SET", "BRIGHTNESS_MAX", "BRIGHTNESS_MIN", "EMPTY_BIN",
           "HIDDEN_ON", "HIDDEN_OFF", "EXT_ON", "EXT_OFF", "BRIGHTNESS_GET", "IDLE_TIME", "OPEN_WINDOWS_COUNT",
           # easier-to-use settings (pcctl.EASE_OPS)
           "DCLICK_SLOWER", "DCLICK_FASTER", "DCLICK_NORMAL", "DCLICK_GET", "KEY_REPEAT_SLOWER", "KEY_REPEAT_NORMAL",
           "STICKY_ON", "STICKY_OFF", "MOUSE_TRAILS_ON", "MOUSE_TRAILS_OFF", "MOUSE_SONAR_ON", "MOUSE_SONAR_OFF",
           "CARET_WIDER", "CARET_NORMAL", "POINTER_BIGGER", "POINTER_SMALLER", "POINTER_NORMAL", "POINTER_GET"}
# Apps Echo can switch to / close: process names it looks for, and the Start-menu name used to launch it.
APPS = {
    "chrome": (("chrome.exe",), "Google Chrome"), "edge": (("msedge.exe",), "Microsoft Edge"),
    "firefox": (("firefox.exe",), "Firefox"), "brave": (("brave.exe",), "Brave"), "opera": (("opera.exe",), "Opera"),
    "vscode": (("code.exe",), "Visual Studio Code"), "visual_studio": (("devenv.exe",), "Visual Studio"),
    "notepad": (("notepad.exe",), "Notepad"), "notepadpp": (("notepad++.exe",), "Notepad++"),
    "word": (("winword.exe",), "Word"), "excel": (("excel.exe",), "Excel"), "powerpoint": (("powerpnt.exe",), "PowerPoint"),
    "outlook": (("outlook.exe", "olk.exe"), "Outlook"), "onenote": (("onenote.exe",), "OneNote"),
    "teams": (("ms-teams.exe", "teams.exe"), "Microsoft Teams"), "slack": (("slack.exe",), "Slack"),
    "discord": (("discord.exe",), "Discord"), "zoom": (("zoom.exe",), "Zoom"), "whatsapp": (("whatsapp.exe", "whatsapp.root.exe"), "WhatsApp"),
    "telegram": (("telegram.exe",), "Telegram"), "spotify": (("spotify.exe",), "Spotify"), "vlc": (("vlc.exe",), "VLC media player"),
    "explorer": (("explorer.exe",), "File Explorer"), "terminal": (("windowsterminal.exe", "wt.exe"), "Terminal"),
    "powershell": (("powershell.exe", "pwsh.exe"), "Windows PowerShell"), "cmd": (("cmd.exe",), "Command Prompt"),
    "settings": (("systemsettings.exe",), "Settings"), "calculator": (("calculatorapp.exe", "calc.exe"), "Calculator"),
    "paint": (("mspaint.exe",), "Paint"), "photos": (("photos.exe", "microsoft.photos.exe"), "Photos"),
    "snipping": (("snippingtool.exe",), "Snipping Tool"), "task_manager": (("taskmgr.exe",), "Task Manager"),
    "steam": (("steam.exe",), "Steam"), "epic": (("epicgameslauncher.exe",), "Epic Games Launcher"), "obs": (("obs64.exe",), "OBS Studio"),
    "android_studio": (("studio64.exe",), "Android Studio"), "intellij": (("idea64.exe",), "IntelliJ IDEA"),
    "pycharm": (("pycharm64.exe",), "PyCharm"), "eclipse": (("eclipse.exe",), "Eclipse"), "postman": (("postman.exe",), "Postman"),
    "docker": (("docker desktop.exe",), "Docker Desktop"), "github_desktop": (("githubdesktop.exe",), "GitHub Desktop"),
    "figma": (("figma.exe",), "Figma"), "photoshop": (("photoshop.exe",), "Adobe Photoshop"),
    "illustrator": (("illustrator.exe",), "Adobe Illustrator"), "premiere": (("adobe premiere pro.exe",), "Adobe Premiere Pro"),
    "acrobat": (("acrobat.exe", "acrord32.exe"), "Adobe Acrobat"), "sublime": (("sublime_text.exe",), "Sublime Text"),
    "unity": (("unity hub.exe", "unity.exe"), "Unity Hub"), "blender": (("blender.exe",), "Blender"), "skype": (("skype.exe",), "Skype"),
    "signal": (("signal.exe",), "Signal"), "mail": (("hxoutlook.exe", "olk.exe"), "Mail"), "sticky_notes": (("microsoft.notes.exe",), "Sticky Notes"),
    "copilot": (("copilot.exe",), "Copilot"), "clock": (("time.exe", "clock.exe"), "Clock"), "media_player": (("microsoft.media.player.exe",), "Media Player"),
    "xbox": (("xboxpcapp.exe",), "Xbox"), "store": (("winstore.app.exe",), "Microsoft Store"), "cursor": (("cursor.exe",), "Cursor"),
    "rider": (("rider64.exe",), "Rider"), "webstorm": (("webstorm64.exe",), "WebStorm"), "dbeaver": (("dbeaver.exe",), "DBeaver"),
    "virtualbox": (("virtualbox.exe",), "Oracle VirtualBox"), "anydesk": (("anydesk.exe",), "AnyDesk"),
    "teamviewer": (("teamviewer.exe",), "TeamViewer"), "audacity": (("audacity.exe",), "Audacity"),
    "gimp": (("gimp-2.10.exe", "gimp-3.0.exe"), "GIMP"), "canva": (("canva.exe",), "Canva"), "notion": (("notion.exe",), "Notion"),
    "obsidian": (("obsidian.exe",), "Obsidian"), "evernote": (("evernote.exe",), "Evernote"), "todo": (("todo.exe",), "Microsoft To Do"),
    "thunderbird": (("thunderbird.exe",), "Thunderbird"), "winrar": (("winrar.exe",), "WinRAR"), "7zip": (("7zfm.exe",), "7-Zip File Manager"),
    "itunes": (("itunes.exe",), "iTunes"), "kindle": (("kindle.exe",), "Kindle"), "minecraft": (("minecraft.exe", "minecraftlauncher.exe"), "Minecraft Launcher"),
    "roblox": (("robloxplayerbeta.exe",), "Roblox Player"), "roblox_studio": (("robloxstudiobeta.exe",), "Roblox Studio"),
    "voice_access": (("voiceaccess.exe",), "Voice access"), "magnifier_app": (("magnify.exe",), "Magnifier"),
    "osk": (("osk.exe",), "On-Screen Keyboard"), "git_bash": (("mintty.exe", "git-bash.exe"), "Git Bash"),
    "anaconda": (("anaconda-navigator.exe",), "Anaconda Navigator"), "matlab": (("matlab.exe",), "MATLAB"),
    "arduino": (("arduino ide.exe", "arduino.exe"), "Arduino IDE"), "putty": (("putty.exe",), "PuTTY"),
    "filezilla": (("filezilla.exe",), "FileZilla"), "wireshark": (("wireshark.exe",), "Wireshark"),
    "vmware": (("vmware.exe",), "VMware Workstation"), "qbittorrent": (("qbittorrent.exe",), "qBittorrent"),
    "libreoffice": (("soffice.bin", "soffice.exe"), "LibreOffice"), "foxit": (("foxitpdfreader.exe", "foxitreader.exe"), "Foxit PDF Reader"),
    "zotero": (("zotero.exe",), "Zotero"), "keepass": (("keepassxc.exe", "keepass.exe"), "KeePassXC"),
    "bitwarden": (("bitwarden.exe",), "Bitwarden"), "jupyter": (("jupyter-lab.exe", "jupyterlab.exe"), "Jupyter"),
}
FOLDERS = {
    "downloads": "shell:Downloads", "documents": "shell:Personal", "pictures": "shell:My Pictures", "music": "shell:My Music",
    "videos": "shell:My Video", "desktop": "shell:Desktop", "recycle_bin": "shell:RecycleBinFolder", "this_pc": "shell:MyComputerFolder",
    "screenshots": "shell:Screenshots", "profile": "shell:Profile", "appdata": "shell:AppData", "startup": "shell:Startup",
    "fonts": "shell:Fonts", "onedrive": "shell:OneDrive", "recent": "shell:Recent", "camera_roll": "shell:Camera Roll",
    "network": "shell:NetworkPlacesFolder", "control_panel": "shell:ControlPanelFolder",
    # Mega pack (99-mega.json)
    "send_to": "shell:SendTo", "start_menu": "shell:Start Menu", "programs": "shell:Programs", "common_startup": "shell:Common Startup",
    "apps_folder": "shell:AppsFolder", "templates": "shell:Templates", "favorites": "shell:Favorites", "links": "shell:Links",
    "saved_games": "shell:SavedGames", "searches": "shell:Searches", "contacts": "shell:Contacts", "local_appdata": "shell:Local AppData",
    "locallow": "shell:LocalAppDataLow", "public": "shell:Public", "public_documents": "shell:Common Documents",
    "public_desktop": "shell:Common Desktop", "history": "shell:History", "libraries": "shell:Libraries",
    "quick_launch": "shell:Quick Launch", "captures": "shell:Captures", "printers": "shell:PrintersFolder",
    "network_connections": "shell:ConnectionsFolder", "pinned": "shell:User Pinned",
    "windows_folder": "shell:Windows", "system32": "shell:System", "program_files": "shell:ProgramFiles",
    "program_files_x86": "shell:ProgramFilesX86", "common_programs": "shell:Common Programs", "admin_tools": "shell:Administrative Tools",
}
WIN_TOOLS = {
    "taskmgr": "taskmgr.exe", "devmgmt": "devmgmt.msc", "diskmgmt": "diskmgmt.msc", "services": "services.msc",
    "eventvwr": "eventvwr.msc", "compmgmt": "compmgmt.msc", "resmon": "resmon.exe", "perfmon": "perfmon.exe",
    "msinfo32": "msinfo32.exe", "mstsc": "mstsc.exe", "charmap": "charmap.exe", "osk": "osk.exe", "magnify": "magnify.exe",
    "dxdiag": "dxdiag.exe", "cleanmgr": "cleanmgr.exe", "sndvol": "sndvol.exe", "mmsys": "mmsys.cpl", "ncpa": "ncpa.cpl",
    "appwiz": "appwiz.cpl", "powercfg": "powercfg.cpl", "sysdm": "sysdm.cpl", "main_cpl": "main.cpl", "firewall": "firewall.cpl",
    "inetcpl": "inetcpl.cpl", "joy": "joy.cpl", "intl": "intl.cpl", "taskschd": "taskschd.msc", "winver": "winver.exe",
    "clock": "ms-clock:", "photos": "ms-photos:", "media_player": "mswindowsmusic:", "movies_tv": "mswindowsvideo:",
    "maps": "bingmaps:", "feedback_hub": "feedback-hub:", "store_updates": "ms-windows-store://downloadsandupdates",
    "wifi_list": "ms-availablenetworks:",
    # Mega pack (99-mega.json): admin and system tools that ship with Windows (no shells)
    "lusrmgr": "lusrmgr.msc", "gpedit": "gpedit.msc", "secpol": "secpol.msc", "certmgr": "certmgr.msc", "wf": "wf.msc",
    "fsmgmt": "fsmgmt.msc", "printmanagement": "printmanagement.msc", "tpm": "tpm.msc", "mdsched": "mdsched.exe",
    "msconfig": "msconfig.exe", "odbc": "odbcad32.exe", "dfrgui": "dfrgui.exe", "rstrui": "rstrui.exe",
    "sys_advanced": "SystemPropertiesAdvanced.exe", "sys_protection": "SystemPropertiesProtection.exe",
    "sys_remote": "SystemPropertiesRemote.exe", "sys_performance": "SystemPropertiesPerformance.exe",
    "sys_name": "SystemPropertiesComputerName.exe", "colorcpl": "colorcpl.exe", "timedate": "timedate.cpl", "wscui": "wscui.cpl",
    "msra": "msra.exe", "narrator": "narrator.exe", "wfs": "wfs.exe", "mrt": "mrt.exe", "sigverif": "sigverif.exe",
    "credwiz": "credwiz.exe", "iexpress": "iexpress.exe", "eudcedit": "eudcedit.exe", "dpiscaling": "dpiscaling.exe",
    "notepad": "notepad.exe", "calc": "calc.exe", "mspaint": "mspaint.exe", "snipping": "snippingtool.exe",
    "calculator_uri": "ms-calculator:", "camera_app": "microsoft.windows.camera:", "store": "ms-windows-store:",
}
WIN_KEYS = {  # virtual-key chords, Win key first; only global shell shortcuts
    "show_desktop": (0x5B, 0x44), "minimize_all": (0x5B, 0x4D), "task_view": (0x5B, 0x09), "emoji": (0x5B, 0xBE),
    "clipboard_history": (0x5B, 0x56), "notifications": (0x5B, 0x4E), "quick_settings": (0x5B, 0x41), "search": (0x5B, 0x53),
    "project": (0x5B, 0x50), "new_desktop": (0x5B, 0x11, 0x44), "next_desktop": (0x5B, 0x11, 0x27),
    "previous_desktop": (0x5B, 0x11, 0x25), "close_desktop": (0x5B, 0x11, 0x73), "voice_typing": (0x5B, 0x48),
    "zoom_in": (0x5B, 0xBB), "zoom_out": (0x5B, 0xBD), "widgets": (0x5B, 0x57), "game_bar": (0x5B, 0x47),
    "screenshot_file": (0x5B, 0x2C), "cast": (0x5B, 0x4B), "switch_language": (0x5B, 0x20),
}
POWER_OPS = {"sleep", "shutdown", "restart", "cancel"}
STATUS_TOPICS = {"disk", "ram", "uptime", "screen", "timezone", "echo_version", "cpu", "language", "os", "pc_name", "ip", "battery_time", "user"}
ECHO_OPS = {"HELP", "COUNT", "EXAMPLE", "GROUPS", "REPEAT", "VOICE_FASTER", "VOICE_SLOWER", "VOICE_NORMAL", "MUTE_REPLIES",
            "UNMUTE_REPLIES", "CLEAR_CHAT", "LIST_PERSONAS", "CURRENT_PERSONA", "LIST_ROUTINES", "WHATS_MY_NAME", "AUTO_MEMORY_OFF",
            "AUTO_MEMORY_ON", "WAKE_WORD_OFF", "WAKE_WORD_ON", "STOPWATCH_START", "STOPWATCH_STOP", "STOPWATCH_STATUS",
            "STOPWATCH_RESET", "ORB_BIGGER", "ORB_SMALLER", "ORB_HIDE", "ORB_SHOW", "ORB_COLOR", "ORB_MORE_TRANSPARENT",
            "ORB_LESS_TRANSPARENT", "ORB_RESET", "OPEN_SETTINGS", "VERSION", "ANSWER", "MEMORY_COUNT", "SPEED"}
# The JARVIS pack (desktop): two brains, privacy mode, nudges, notes, recap, Telegram, hotkey, click by name
JARVIS_OPS = {"BRAIN_STATUS", "BRAIN_LOCAL", "BRAIN_CLOUD", "BRAIN_AUTO", "PRIVACY_ON", "PRIVACY_OFF", "PRIVACY_STATUS",
              "NUDGES_NOW", "PROACTIVE_ON", "PROACTIVE_OFF", "NOTES_ADD", "NOTES_FORGET", "NOTES_REFRESH", "NOTES_STATUS",
              "NOTES_ASK", "RECAP", "TELEGRAM_STATUS", "TELEGRAM_OFF", "TELEGRAM_UNPAIR", "HOTKEY_STATUS",
              "ACTIONS_LOG", "PHRASES_CHECK", "WHAT_CAN_I_SAY", "PHRASE_FORGET",      # lessons from assistants that failed
              "SKILLS_LIST", "SKILL_READ", "SKILLS_FOLDER", "SKILLS_ON", "SKILLS_OFF",  # skills: .md how-tos Echo reads
              "SKILL_COURSES", "SKILL_TEACH", "LESSON_NEXT", "LESSON_AGAIN", "LESSON_STOP"}   # courses and tutor mode
ECHO_OPS |= JARVIS_OPS | {"CLICK_NAMED", "DOUBLE_CLICK_NAMED", "RIGHT_CLICK_NAMED"}
# The vault (desktop): your own words only — the AI, MCP and Telegram can never run these
VAULT_OPS = {"VAULT_OPEN", "VAULT_LIST", "VAULT_LOCK", "VAULT_LOG", "VAULT_UNLOCK_PHONE", "VAULT_TYPE_PASSWORD",
             "VAULT_TYPE_USERNAME", "VAULT_FILL_LOGIN", "VAULT_TYPE_PIN", "VAULT_TYPE_CARD_NUMBER", "VAULT_TYPE_CARD_EXPIRY",
             "VAULT_TYPE_CARD_CVV", "VAULT_TYPE_CARD_HOLDER", "VAULT_COPY", "VAULT_SHOW", "VAULT_AUTOFILL", "VAULT_LOGIN"}
ECHO_OPS |= VAULT_OPS
LIST_OPS = {"ADD", "SHOW", "REMOVE", "CLEAR", "LISTS", "NOTE", "NOTES", "LAST_NOTE", "DELETE_NOTES", "NOTE_COUNT", "CREATE"}
MODES = {"driving", "walking", "bicycling", "two-wheeler", "transit"}


def check_desktop(spec: dict, nodes: list) -> Optional[str]:
    from . import tools  # local import: tools imports this module
    kind = spec.get("kind")
    common = common_slots(nodes)

    def slots_ok(template):
        missing = placeholders(template) - common
        return f"phrase is missing slot(s) {missing}" if missing else None

    def https(url):
        return None if isinstance(url, str) and url.startswith("https://") else "needs an https url"
    if kind not in DESKTOP_KINDS:
        return f"kind {kind} is not available on desktop"
    if kind == "web":
        return https(spec.get("url")) or slots_ok(spec["url"])
    if kind == "open":
        return https(spec.get("url"))
    if kind in ("maps", "directions"):
        if not spec.get("q"):
            return f"{kind} needs q"
        if kind == "directions" and spec.get("mode") not in MODES:
            return f"unknown mode {spec.get('mode')}"
        return slots_ok(spec["q"])
    if kind == "tool":
        return None if spec.get("tool") in tools.NAMES else f"unknown tool {spec.get('tool')}"
    if kind == "say":
        return None if spec.get("text") else "say needs text"
    if kind == "content":
        return None if spec.get("topic") else "content needs topic"
    if kind == "echo":
        return None if spec.get("op") in ECHO_OPS else f"unknown op {spec.get('op')}"
    if kind == "list":
        return None if spec.get("op") in LIST_OPS else f"unknown op {spec.get('op')}"
    if kind == "ms_settings":
        return None if re.fullmatch(r"[a-z0-9-]*", spec.get("page", "-x-")) else "bad settings page"
    if kind == "folder":
        return None if spec.get("target") in FOLDERS else f"unknown folder {spec.get('target')}"
    if kind == "win_tool":
        return None if spec.get("target") in WIN_TOOLS else f"unknown tool {spec.get('target')}"
    if kind == "win_key":
        return None if spec.get("target") in WIN_KEYS else f"unknown key {spec.get('target')}"
    if kind == "power":
        return None if spec.get("op") in POWER_OPS else f"unknown power op {spec.get('op')}"
    if kind == "status":
        return None if spec.get("topic") in STATUS_TOPICS else f"unknown topic {spec.get('topic')}"
    if kind == "keys":
        from . import typer
        keys = str(spec.get("keys", ""))
        if "{n}" in keys and "n" not in common:
            return "keys use {n} but the phrase has no {n} slot"
        try:
            typer.key_sequence(keys.replace("{n}", "1"))
        except ValueError as e:
            return f"bad keys '{keys}': {e}"
        return None
    if kind == "text":
        return None if isinstance(spec.get("text"), str) and 0 < len(spec["text"]) <= 200 else "text needs 1-200 characters"
    if kind == "mouse":
        if spec.get("op") not in MOUSE_OPS:
            return f"unknown mouse op {spec.get('op')}"
        return "mouse at needs {n} and {n2}" if spec["op"] == "at" and not {"n", "n2"} <= common else None
    if kind == "window":
        return None if spec.get("op") in WINDOW_OPS else f"unknown window op {spec.get('op')}"
    if kind == "app_window":
        return None if spec.get("op") in ("switch", "close") and spec.get("app") in APPS else f"bad app_window {spec}"
    if kind == "clip":
        return None if spec.get("op") in CLIP_OPS else f"unknown clip op {spec.get('op')}"
    if kind == "sys":
        return None if spec.get("op") in SYS_OPS else f"unknown sys op {spec.get('op')}"
    if kind == "net":
        from . import internet
        if spec.get("op") not in internet.NET_OPS:
            return f"unknown net op {spec.get('op')}"
        return (https(spec["fallback"]) or slots_ok(spec["fallback"])) if "fallback" in spec else None
    if kind == "dev":
        from . import devtools
        return None if spec.get("op") in devtools.DEV_OPS else f"unknown dev op {spec.get('op')}"
    if kind == "selection":
        return None if spec.get("op") in SELECTION_OPS else f"unknown selection op {spec.get('op')}"
    if kind == "mcp":
        from . import mcp_presets
        if spec.get("op") not in MCP_OPS:
            return f"unknown mcp op {spec.get('op')}"
        if spec["op"] in ("ADD", "REMOVE", "TRUST", "UNTRUST") and spec.get("preset") not in mcp_presets.PRESETS:
            return f"unknown MCP preset {spec.get('preset')}"
        if spec["op"] == "TOOL":
            from . import toolbox
            t = toolbox.load().get(spec.get("tool", ""))
            if t is None:
                return f"unknown tool {spec.get('tool')}"
            if t.ask:
                return "voice shortcuts only run tools that don't change things"
        return None
    return None


def _cache_key(files: list, platform: str) -> str:
    """Changes when any command file, or any Echo source file that validates commands, changes."""
    import hashlib
    import sys
    h = hashlib.sha256(f"{platform}|{sys.version}|{CACHE_VERSION}".encode())
    for name, text in files:
        h.update(name.encode() + b"\0" + text.encode("utf-8") + b"\0")
    here = Path(__file__).parent
    for p in sorted(here.rglob("*.py")):
        try:
            st = p.stat()
        except OSError:
            continue
        h.update(f"{p.relative_to(here)}|{st.st_size}|{st.st_mtime_ns}\n".encode())
    return h.hexdigest()[:32]


CACHE_VERSION = 1


def cache_dir() -> Path:
    import os
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "EchoDesktop" / "cache"


def load(platform: str = "desktop", use_cache: bool = True) -> Catalog:
    """The Command Pack. Parsing ~7,000 phrase patterns takes about a second, so the parsed pack is cached on disk
    (keyed by a hash of every command file and Echo's source) and later starts load it in a fraction of that."""
    files = load_files()
    if not use_cache:
        return Catalog.parse(files, platform, check_desktop)
    import pickle
    path = cache_dir() / f"commands-{platform}-{_cache_key(files, platform)}.pickle"
    try:
        with open(path, "rb") as f:
            cat = pickle.load(f)
        if isinstance(cat, Catalog):
            return cat
    except (OSError, EOFError, pickle.UnpicklingError, AttributeError, ImportError, TypeError, ValueError):
        pass
    cat = Catalog.parse(files, platform, check_desktop)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        for old in path.parent.glob(f"commands-{platform}-*.pickle"):
            old.unlink(missing_ok=True)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            pickle.dump(cat, f, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(path)
    except OSError:
        pass
    return cat
