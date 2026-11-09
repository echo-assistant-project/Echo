"""Echo's toolbox: 600+ typed Python tools the AI can call, inside Echo and as an MCP server for other AI apps.

Writing a tool is one decorated function — its name, docstring and type hints become the tool's name, description
and JSON input schema:

    @tool("money", ex={"price": 1180, "rate": 18})
    def gst_remove(price: float, rate: float = 18) -> str:
        '''Split a GST-inclusive price into base price and GST.'''
        ...

Flags: ask=True (changes something: the user confirms first), net=True (uses the internet), app=True (needs the
running Echo app: lists, memory, timers). Everything else is read-only and runs freely.

Finding the best tool ("routes"): with hundreds of tools no AI prompt can list them all, so `Router` ranks tools for
the request (words, synonyms, categories), the agent sees the best ~30, and can call `toolbox.find` for more.
"""
from __future__ import annotations

import importlib
import inspect
import json
import math
import re
import typing
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

MODULES = ("t_math", "t_units", "t_money", "t_time", "t_text", "t_encode", "t_data", "t_files", "t_system", "t_control",
           "t_web", "t_life", "t_india", "t_dev", "t_personal", "t_extra", "t_moltbook", "t_automation", "t_assistant", "t_festivals")
CATEGORIES = {
    "math": "Maths, statistics, numbers, randomness", "units": "Unit conversions", "money": "Money, loans, savings, tax, prices",
    "time": "Dates, times, time zones, calendars", "text": "Text tools: counts, cases, find/replace, regex, ciphers",
    "encode": "Encodings, hashes, ids, passwords, tokens", "data": "JSON, CSV, XML, URLs, colours, formats",
    "files": "Files and folders on this PC", "system": "This PC: hardware, processes, network, settings",
    "control": "Control the PC: keys, typing, mouse, windows, apps", "web": "Live information from the internet",
    "life": "Health, home, cooking, travel calculators", "india": "India: PAN, GSTIN, IFSC, PIN codes, lakh/crore",
    "dev": "Developer tools: git, code stats, templates, HTTP", "personal": "Your lists, notes, memories, timers, messages",
    "social": "Moltbook, the social network for AI agents: read, search, and (with your OK) post",
    "automation": "Watches, reports, comparisons, trends and dashboards on any data; the 1,000 automation ideas; briefings",
    "assistant": "Your personal assistant: tasks and due dates, plan my day, follow-ups, people and birthdays, habits, "
                 "expenses and budgets, journal, focus sessions, meeting notes, my day, weekly review, taught phrases",
}


class ToolError(Exception):
    """A clear, user-facing failure ("that file doesn't exist")."""


@dataclass
class Tool:
    name: str
    category: str
    description: str
    fn: Callable
    schema: dict
    ask: bool = False
    net: bool = False
    app: bool = False
    example: Optional[dict] = None
    keywords: str = ""
    wants_ctx: bool = False

    def signature(self) -> str:
        props, req = self.schema.get("properties", {}), set(self.schema.get("required", []))
        parts = []
        for k, v in props.items():
            t = v.get("type", "any")
            if "enum" in v:
                t = "|".join(map(str, v["enum"][:8]))
            parts.append(f"{k}{'' if k in req else '?'}:{t}")
        return f"{self.name}({', '.join(parts)})"


REGISTRY: dict = {}


def _json_type(ann) -> dict:
    origin = typing.get_origin(ann)
    args = typing.get_args(ann)
    if ann is inspect.Parameter.empty or ann is Any:
        return {}
    if origin is typing.Union:
        rest = [a for a in args if a is not type(None)]
        return _json_type(rest[0]) if rest else {}
    if origin is typing.Literal:
        return {"type": "string" if all(isinstance(a, str) for a in args) else "number", "enum": list(args)}
    if ann is bool:
        return {"type": "boolean"}
    if ann is int:
        return {"type": "integer"}
    if ann is float:
        return {"type": "number"}
    if ann is str:
        return {"type": "string"}
    if origin in (list, tuple) or ann in (list, tuple):
        inner = _json_type(args[0]) if args else {}
        return {"type": "array", "items": inner or {}}
    if origin is dict or ann is dict:
        return {"type": "object"}
    return {}


def _schema(fn) -> tuple:
    sig = inspect.signature(fn)
    hints = typing.get_type_hints(fn, include_extras=False)
    props, required, wants_ctx = {}, [], False
    for name, p in sig.parameters.items():
        if name == "ctx":
            wants_ctx = True
            continue
        s = _json_type(hints.get(name, p.annotation))
        if p.default is not inspect.Parameter.empty and p.default is not None:
            s["default"] = p.default
        props[name] = s
        if p.default is inspect.Parameter.empty:
            required.append(name)
    schema = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema, wants_ctx


def tool(category: str, *, ask: bool = False, net: bool = False, app: bool = False, ex: Optional[dict] = None,
         keys: str = "", name: Optional[str] = None):
    """Register a function as a tool."""
    def deco(fn):
        tname = name or fn.__name__
        if tname in REGISTRY:
            raise RuntimeError(f"duplicate tool {tname}")
        if category not in CATEGORIES:
            raise RuntimeError(f"unknown category {category}")
        doc = inspect.getdoc(fn) or tname.replace("_", " ")
        schema, wants_ctx = _schema(fn)
        REGISTRY[tname] = Tool(tname, category, " ".join(doc.split("\n\n")[0].split()), fn, schema, ask, net, app, ex, keys, wants_ctx)
        return fn
    return deco


_loaded = False


def load() -> dict:
    global _loaded
    if not _loaded:
        for m in MODULES:
            importlib.import_module(f"{__name__}.{m}")
        _loaded = True
    return REGISTRY


# ------------------------------------------------------------------------------------------------ calling
@dataclass
class Context:
    """What tools may use from their surroundings. Every field is optional; tools say clearly when one is missing."""
    settings: Any = None
    lists: Any = None                 # storage.ListStore
    memory: Any = None                # storage.MemoryStore
    confirm: Callable = lambda title, text: False
    start_timer: Optional[Callable] = None     # (seconds, label) -> (ok, msg)
    timers: Optional[Callable] = None          # () -> summary text
    reminder: Optional[Callable] = None        # (when words, label, repeat) -> (ok, msg)
    cancel_timers: Optional[Callable] = None   # (which) -> (ok, msg)
    notify: Optional[Callable] = None
    workspaces: dict = field(default_factory=dict)
    in_app: bool = False


def _coerce(value, s: dict):
    t = s.get("type")
    try:
        if t == "integer" and not isinstance(value, bool):
            return int(float(value))
        if t == "number" and not isinstance(value, bool):
            return float(value)
        if t == "boolean":
            return value if isinstance(value, bool) else str(value).strip().lower() in ("1", "true", "yes", "on")
        if t == "string" and not isinstance(value, str):
            return json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        if t == "array":
            if isinstance(value, str):
                v = value.strip()
                value = json.loads(v) if v.startswith("[") else [x.strip() for x in re.split(r"[,\n]", v) if x.strip()]
            if not isinstance(value, list):
                value = [value]
            inner = (s.get("items") or {}).get("type")
            if inner in ("integer", "number"):              # every item must be a number, not just the list
                out = []
                for x in value:
                    try:
                        out.append(_coerce(x, s["items"]))
                    except ToolError:
                        raise ToolError(f"every item needs to be a number, but got {str(x)[:30]!r}")
                return out
            return value
        if t == "object" and not isinstance(value, dict):
            parsed = json.loads(value) if isinstance(value, str) and value.strip().startswith("{") else None
            if not isinstance(parsed, dict):
                raise ToolError(f"expected an object like {{\"name\": value}} but got {str(value)[:40]!r}")
            return parsed
    except (TypeError, ValueError):
        raise ToolError(f"expected a {t} but got {str(value)[:40]!r}")
    return value


def render(result) -> str:
    if result is None:
        return "Done."
    if isinstance(result, str):
        return result
    if isinstance(result, float):
        return fmt(result)
    return json.dumps(result, ensure_ascii=False, indent=1, default=str)


def fmt(x, places: int = 6) -> str:
    """Numbers for people: no float noise, thousands separators, trailing zeros trimmed."""
    if isinstance(x, bool):
        return str(x)
    if isinstance(x, int):
        return f"{x:,}"
    if isinstance(x, float):
        if math.isnan(x) or math.isinf(x):
            return str(x)
        if x == int(x) and abs(x) < 1e15:
            return f"{int(x):,}"
        s = f"{x:,.{places}f}".rstrip("0").rstrip(".")
        return s if s not in ("-0", "") else "0"
    return str(x)


def plain_error(e: BaseException) -> str:
    """Python's wording for bad input, in plain words ("invalid literal for int() with base 10: 'abc'" -> "that needs a
    number, but got 'abc'"). Messages a tool wrote itself pass through unchanged."""
    msg = str(e)
    m = re.search(r"invalid literal for int\(\) with base (\d+): (.+)$", msg) or re.search(r"could not convert string to float: (.+)$", msg)
    if m:
        got = m.groups()[-1].strip()[:40]
        base = m.group(1) if m.re.groups == 2 else "10"
        return (f"that needs a whole number, but got {got}" if base == "10" else f"that isn't a base-{base} number: {got}") \
            if "int()" in msg else f"that needs a number, but got {got}"
    if isinstance(e, ZeroDivisionError):
        return "that would mean dividing by zero"
    if isinstance(e, MemoryError):
        return "that's too big to process; try a smaller piece"
    if isinstance(e, (OverflowError, RecursionError)) or "too large" in msg or "Result too large" in msg:
        return "that number is too big to work out"
    if "math domain error" in msg:
        return "that's outside what can be calculated (for example the square root or log of a negative number)"
    if isinstance(e, UnicodeError):
        return "that text has characters this can't handle"
    return msg or type(e).__name__


def call(name: str, args: Optional[dict] = None, ctx: Optional[Context] = None) -> str:
    """Run a tool. Returns text; failures come back as 'ERROR: …' (the AI reads them and can try again)."""
    load()
    t = REGISTRY.get(name)
    if t is None:
        return f"ERROR: there's no tool called {name}. Use toolbox.find to look for one."
    args = dict(args or {})
    props = t.schema.get("properties", {})
    unknown = [k for k in args if k not in props]
    for k in unknown:
        args.pop(k)
    missing = [k for k in t.schema.get("required", []) if k not in args or args[k] in (None, "")]
    if missing:
        return f"ERROR: {name} needs {', '.join(missing)}. Signature: {t.signature()}"
    try:
        clean = {k: _coerce(v, props[k]) for k, v in args.items()}
        for k, v in clean.items():
            if "enum" in props[k] and v not in props[k]["enum"]:
                raise ToolError(f"{k} must be one of {', '.join(map(str, props[k]['enum']))}")
        if t.wants_ctx:
            clean["ctx"] = ctx or Context()
        return render(t.fn(**clean))
    except ToolError as e:
        return f"ERROR: {e}"
    except (ValueError, ZeroDivisionError, OverflowError, ArithmeticError, RecursionError, MemoryError) as e:
        return "ERROR: " + plain_error(e)
    except (TypeError, KeyError, IndexError) as e:
        return f"ERROR: {type(e).__name__}: {e}"
    except OSError as e:
        return f"ERROR: {e.strerror or e}"
    except Exception as e:                       # a broken tool must never take the agent down
        from ..internet import NetError
        return f"ERROR: {e}" if isinstance(e, NetError) else f"ERROR: {type(e).__name__}: {e}"


# ------------------------------------------------------------------------------------------------ routing
_STOP = set("a an the to of for in on at by with and or is are be my me i you your it this that what how do does can please "
            "from into as get give show tell find make want need some any".split())
SYNONYMS = {
    "weather": "forecast temperature rain climate", "rain": "umbrella weather precipitation", "temperature": "weather hot cold",
    "money": "price cost rupees dollar", "convert": "conversion change units", "loan": "emi interest mortgage borrow",
    "invest": "sip returns savings mutual fund", "tax": "gst income", "time": "clock hour timezone", "date": "day calendar",
    "file": "files document folder", "folder": "directory files", "find": "search locate look", "search": "find look query",
    "delete": "remove trash erase", "copy": "duplicate clipboard", "password": "secret passphrase credential",
    "hash": "checksum sha md5 digest", "encode": "encoding base64 url", "json": "data object", "csv": "spreadsheet table",
    "news": "headlines articles", "word": "dictionary define meaning", "translate": "language translation",
    "volume": "sound audio loud", "screen": "display monitor brightness", "window": "app program", "app": "program application",
    "process": "program task running", "network": "internet wifi ip", "wifi": "network wireless internet", "ip": "address network",
    "battery": "power charge", "memory": "ram remember", "remember": "memory note save", "note": "notes memo",
    "list": "lists shopping todo", "timer": "countdown alarm reminder", "remind": "reminder timer alarm",
    "email": "mail message", "message": "whatsapp text sms", "health": "bmi calories fitness", "cook": "recipe kitchen food",
    "recipe": "cook food dish", "git": "repository commit branch", "code": "programming developer source",
    "package": "library version npm pypi", "github": "repo repository", "website": "site page url web", "url": "link website",
    "random": "pick choose dice coin", "stats": "statistics average mean", "average": "mean statistics",
    "bank": "ifsc", "pincode": "pin postal", "train": "railway", "movie": "film tv show", "song": "music track",
    "translate_text": "translation", "task": "todo tasks deadline", "todo": "task tasks", "spent": "expense spending money",
    "spend": "expense spending", "expense": "spent money budget", "plan": "schedule day time block", "habit": "habits streak",
    "birthday": "birthdays person", "journal": "diary mood", "focus": "pomodoro deep work", "meeting": "meetings notes action items",
    "follow": "followup follow_up chase", "day": "today brief", "moltbook": "agents social network posts", "agents": "moltbook", "type": "keyboard typing", "click": "mouse pointer", "key": "keyboard shortcut press",
}


def _tokens(text: str) -> list:
    words = re.findall(r"[a-z0-9]+", text.lower().replace("_", " "))
    out = []
    for w in words:
        if w in _STOP:
            continue
        out.append(w)
        if len(w) > 4 and w.endswith("s"):
            out.append(w[:-1])
    return out


class Router:
    """BM25 over each tool's name, description, keywords and category, with synonym expansion of the request."""

    def __init__(self, tools: list):
        self.tools = tools
        self.docs = []
        for t in tools:
            text = " ".join([t.name.replace("_", " ")] * 3 + [t.description, t.keywords * 2, t.category, CATEGORIES.get(t.category, "")])
            self.docs.append(Counter(_tokens(text)))
        self.N = len(self.docs) or 1
        self.avg = sum(sum(d.values()) for d in self.docs) / self.N
        df = Counter()
        for d in self.docs:
            df.update(set(d))
        self.idf = {w: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for w, n in df.items()}

    def search(self, query: str, k: int = 30, categories: Optional[set] = None) -> list:
        q = _tokens(query)
        weights = Counter()
        for w in q:
            weights[w] += 1.0
            for s in SYNONYMS.get(w, "").split():
                weights[s] += 0.4
        scored = []
        for t, d in zip(self.tools, self.docs):
            if categories and t.category not in categories:
                continue
            length = sum(d.values()) or 1
            score = 0.0
            for w, qw in weights.items():
                f = d.get(w)
                if f:
                    score += qw * self.idf.get(w, 0) * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * length / self.avg))
            if score > 0:
                scored.append((score, t))
        scored.sort(key=lambda st: -st[0])
        return [t for _, t in scored[:k]]


_router: Optional[Router] = None


def router() -> Router:
    global _router
    if _router is None:
        _router = Router(list(load().values()))
    return _router


def find(query: str, k: int = 12) -> str:
    hits = router().search(query, k)
    if not hits:
        return "No matching tools. Try other words, or list categories with toolbox.categories."
    return "\n".join(f"- toolbox.{t.signature()}{' [asks first]' if t.ask else ''}: {t.description}" for t in hits)


# ------------------------------------------------------------------------------------------------ hub (agent + MCP shape)
SERVER = "toolbox"


def mcp_entry(t: Tool, prefix: str = SERVER + ".") -> dict:
    return {"server": SERVER, "name": prefix + t.name, "title": t.name.replace("_", " ").capitalize(), "description": t.description,
            "inputSchema": t.schema, "builtin": True, "ask": t.ask, "category": t.category,
            "annotations": {"readOnlyHint": not t.ask, "destructiveHint": t.ask, "openWorldHint": t.net}}


class ToolboxHub:
    """The toolbox as a hub for Echo's tool agent: tools(), call(), and routing for big tool sets."""
    trusted: set = set()

    def __init__(self, ctx: Optional[Context] = None, enabled: Callable[[], bool] = lambda: True,
                 internet: Callable[[], bool] = lambda: True):
        self.ctx = ctx or Context()
        self.enabled, self.internet = enabled, internet

    def _visible(self) -> list:
        if not self.enabled():
            return []
        net_ok = self.internet()
        return [t for t in load().values() if (net_ok or not t.net) and (self.ctx.in_app or not t.app)]

    def tools(self) -> list:
        out = [mcp_entry(t) for t in self._visible()]
        if out:
            out += META
        return out

    def route(self, goal: str, k: int = 30) -> list:
        visible = {t.name for t in self._visible()}
        hits = [t for t in router().search(goal, k * 2) if t.name in visible][:k]
        return [mcp_entry(t) for t in hits] + META

    def call(self, name: str, args: dict) -> str:
        short = name.split(".", 1)[1] if name.startswith(SERVER + ".") else name
        if short == "find":
            return find(str(args.get("query", "")), int(args.get("limit", 12) or 12))
        if short == "categories":
            counts = Counter(t.category for t in self._visible())
            return "\n".join(f"- {c} ({counts[c]} tools): {d}" for c, d in CATEGORIES.items() if counts[c])
        if short == "list_category":
            cat = str(args.get("category", ""))
            return "\n".join(f"- toolbox.{t.signature()}: {t.description}" for t in self._visible() if t.category == cat) or "No such category."
        visible = {t.name for t in self._visible()}
        if short not in visible:
            return f"ERROR: there's no tool called {short} here."
        return call(short, args, self.ctx)


META = [
    {"server": SERVER, "name": "toolbox.find", "builtin": True, "ask": False, "annotations": {"readOnlyHint": True},
     "description": "Search Echo's 600+ tools by what you want to do; returns the best matches with their arguments.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]}},
    {"server": SERVER, "name": "toolbox.categories", "builtin": True, "ask": False, "annotations": {"readOnlyHint": True},
     "description": "List the tool categories and how many tools each has.", "inputSchema": {"type": "object", "properties": {}}},
    {"server": SERVER, "name": "toolbox.list_category", "builtin": True, "ask": False, "annotations": {"readOnlyHint": True},
     "description": "List every tool in one category.",
     "inputSchema": {"type": "object", "properties": {"category": {"type": "string", "enum": list(CATEGORIES)}}, "required": ["category"]}},
]
