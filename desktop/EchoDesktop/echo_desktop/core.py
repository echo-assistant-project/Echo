"""Pure EchoDesktop logic (no Windows or UI calls), unit-tested in tests/test_core.py.

Mirrors the phone's rules: typed allow-listed actions, strict validation, personas from shared/personas.json,
and memory rules that never store secrets.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_PERSONAS = REPO_ROOT / "shared" / "personas.json"


# --------------------------------------------------------------------------- personas

@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    tagline: str
    aliases: tuple
    prompt: str
    gemini_voice: str
    speech_rate: float
    color: str
    uses_target_language: bool = False

    def system_prompt(self, target_language: str) -> str:
        return self.prompt.replace("{target_language}", target_language) if self.uses_target_language else self.prompt


_ID = re.compile(r"^[a-z0-9_-]{2,24}$")
_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def clean_line(value, max_len: int) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]", " ", value)).strip()
    return text if text and len(text) <= max_len else None


def parse_persona(obj: dict) -> Optional[Persona]:
    pid = obj.get("id")
    if not isinstance(pid, str) or not _ID.match(pid.lower()):
        return None
    name = clean_line(obj.get("name"), 24)
    prompt = obj.get("prompt") if isinstance(obj.get("prompt"), str) and 0 < len(obj["prompt"]) <= 1500 else None
    if not name or not prompt:
        return None
    aliases = [a.lower() for a in (clean_line(x, 30) for x in obj.get("aliases", []) if isinstance(x, str)) if a]
    rate = obj.get("speechRate", 0.95)
    rate = min(max(float(rate), 0.65), 1.15) if isinstance(rate, (int, float)) else 0.95
    voice = "Aoede"
    color = obj.get("color") if isinstance(obj.get("color"), str) and _COLOR.match(obj["color"]) else "#42D9FF"
    return Persona(pid.lower(), name, clean_line(obj.get("tagline"), 60) or "",
                   tuple(dict.fromkeys(aliases + [name.lower(), pid.lower()])), prompt, voice, rate, color,
                   obj.get("usesTargetLanguage") is True)


def load_personas(path: Path = SHARED_PERSONAS) -> list:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        personas = [p for p in (parse_persona(o) for o in data.get("personas", []) if isinstance(o, dict)) if p]
    except (OSError, ValueError):
        personas = []
    return personas or [Persona("echo", "Echo", "Warm everyday companion", ("echo",),
                                "You are Echo, a warm, supportive companion.", "Aoede", 0.95, "#42D9FF")]


def find_persona(personas: list, spoken: str) -> Optional[Persona]:
    key = spoken.lower().strip()
    for prefix in ("the ",):
        key = key[len(prefix):] if key.startswith(prefix) else key
    for suffix in (" mode", " persona"):
        key = key[: -len(suffix)] if key.endswith(suffix) else key
    key = key.strip()
    return next((p for p in personas if p.id == key), None) or next((p for p in personas if key in p.aliases), None)


# --------------------------------------------------------------------------- actions

@dataclass(frozen=True)
class Action:
    kind: str
    args: dict = field(default_factory=dict)

    def __hash__(self):  # args dict is not hashable; actions are compared by value in tests
        return hash((self.kind, json.dumps(self.args, sort_keys=True)))


@dataclass(frozen=True)
class Reply:
    """speech (text) | action | rejected (reason)"""
    type: str
    text: str = ""
    action: Optional[Action] = None


SCREEN_ACTIONS = {"screen_question", "camera_question", "web_task"}  # reads the screen/camera/web: only from the user's own command, never model-chosen
# write/run code, type into other apps: only from the user's own words, never chosen by the model (not even via run_command)
USER_ONLY_ACTIONS = SCREEN_ACTIONS | {"code_task", "code_continue", "project_open", "project_run", "type_text", "type_last",
                                      "compose_type", "computer_task", "voice_test", "mcp_add", "mcp_remove", "mcp_import",
                                      "mcp_trust", "mcp_reload", "change_revert", "workspace_open"}

_COMPUTER_RX = re.compile(
    r"^(?:(?:use|control|take over|take control of|operate) (?:my |the )?(?:computer|pc|laptop|desktop|mouse|screen)"
    r"(?:,| and| to| for me to)? (?P<a>.+)"
    r"|(?:on|in|using) (?:my |the )?(?:computer|pc|laptop|desktop|screen),? (?P<b>.+)"
    r"|(?P<c>(?:click|double click|right click|tap) (?:on )?.+))$")


_TOOLWORD = r"(?:tools?|mcp server|mcp tools?|mcp|server|connector)"
_MCP_RX = {
    "list": re.compile(r"^(?:what|which) (?:mcp )?(?:tools|servers|mcp servers|connectors) (?:do you have|are connected|can you use)"
                       r"|^(?:list|show) (?:me )?(?:my|the|your) (?:mcp )?(?:tools|servers|mcp servers|connectors)$"),
    "reload": re.compile(r"^(?:reload|restart|refresh|reconnect) (?:my |the |all )?(?:mcp )?(?:tools|servers|mcp servers|connectors)$"),
    "import": re.compile(r"^import (?:my |the )?(?:mcp )?(?:servers|tools|mcp servers|connectors|mcp)"
                         r"(?: from (?P<src>claude desktop|claude code|cursor|vs code|visual studio code|windsurf))?$"),
    "add": re.compile(rf"^(?:add|connect|install|set up|setup) (?:the |my |a )?(?P<what>.+?) {_TOOLWORD}$"),
    "remove": re.compile(rf"^(?:remove|disconnect|uninstall|delete) (?:the |my )?(?P<what>.+?) {_TOOLWORD}$"),
    "trust": re.compile(rf"^(?P<neg>stop trusting|don't trust|do not trust|untrust|trust) (?:the |my )?(?P<what>.+?) {_TOOLWORD}$"),
    "use": re.compile(rf"^(?:use|using|with|ask) (?:the |my )?(?P<srv>[\w .+-]+?) {_TOOLWORD}(?:,| to| and| for)? (?P<goal>.+)$"),
    "use_any": re.compile(r"^(?:use|using|with) (?:my |the |your )?(?:mcp )?(?:tools|connectors)(?:,| to| and| for)? (?P<goal>.+)$"),
}


_mcp_named = None       # "use github to …": only for MCP servers the user actually has (installed by the brain)


def install_mcp_servers(names) -> None:
    global _mcp_named
    names = sorted({normalize(n).replace("-", " ") for n in (names or []) if normalize(n)}, key=len, reverse=True)
    if not names:
        _mcp_named = None
        return
    alts = "|".join(re.escape(n).replace(r"\ ", "[ -]") for n in names)
    _mcp_named = re.compile(rf"^(?:use|using|with|ask) (?:the |my )?(?P<srv>{alts})(?: {_TOOLWORD})?(?:,| to| and| for)? (?P<goal>.+)$")


def mcp_command(lower: str, original: str) -> Optional[Reply]:
    """Managing and using MCP servers ("add the files tools", "use github to …", "import my MCP servers")."""
    def span(m, g):
        return _span(original, lower, m.start(g), m.end(g)).strip()
    if _mcp_named is not None and (m := _mcp_named.match(lower)):
        return Reply("action", action=Action("mcp_task", {"server": m.group("srv"), "goal": span(m, "goal")}))
    if _MCP_RX["list"].match(lower):
        return Reply("action", action=Action("mcp_list", {}))
    if _MCP_RX["reload"].match(lower):
        return Reply("action", action=Action("mcp_reload", {}))
    if m := _MCP_RX["import"].match(lower):
        src = (m.group("src") or "").replace("visual studio code", "vs code") or None
        return Reply("action", action=Action("mcp_import", {"source": src}))
    if m := _MCP_RX["use_any"].match(lower):
        return Reply("action", action=Action("mcp_task", {"server": None, "goal": span(m, "goal")}))
    if m := _MCP_RX["use"].match(lower):
        return Reply("action", action=Action("mcp_task", {"server": m.group("srv").strip(), "goal": span(m, "goal")}))
    if m := _MCP_RX["trust"].match(lower):
        return Reply("action", action=Action("mcp_trust", {"what": m.group("what"), "trusted": m.group("neg") == "trust"}))
    if m := _MCP_RX["add"].match(lower):
        return Reply("action", action=Action("mcp_add", {"what": m.group("what")}))
    if m := _MCP_RX["remove"].match(lower):
        return Reply("action", action=Action("mcp_remove", {"what": m.group("what")}))
    return None


_CHANGE_RX = {
    "list": re.compile(r"^(?:show|list|open) (?:me )?(?:my|the|your|echo's|echos) (?:changes|change log|changelog|recent changes|edits)$"
                       r"|^(?:change log|changelog|what did you change|what have you changed|what files did you change)$"),
    "show": re.compile(r"^(?:show|what is in|what's in|what changed in|show me the diff (?:of|for)) (?:the )?change (?:number |#)?(\d+)$"),
    "revert_n": re.compile(r"^(?P<force>force )?(?:undo|revert|roll back|rollback) (?:the )?change (?:number |#)?(?P<n>\d+)$"),
    "revert_last": re.compile(r"^(?P<force>force )?(?:undo|revert|roll back|rollback) (?:the |your |echo's |echos |that )?"
                              r"(?:last |latest |previous )?(?:change|changes|edit|edits)(?: you made)?$"),
    "path": re.compile(r"^(?:work on|open|edit) (?:the |my )?(?:project|folder|code|site|website)? ?(?:at |in )?"
                       r"(?P<path>[a-z]:[\\/][^,]+?)(?:(?:,| and| then) (?P<goal>.+))?$"),
}
_workspace_rx = None


def install_workspaces(names) -> None:
    """Named project folders from Settings ("website=C:\\…\\amaravati"): “work on my website …”, “in my website, …”."""
    global _workspace_rx
    names = sorted({normalize(n) for n in (names or []) if normalize(n)}, key=len, reverse=True)
    if not names:
        _workspace_rx = None
        return
    alts = "|".join(re.escape(n) for n in names)
    suffix = r"(?: project| folder| code| site| website| app| repo)?"
    _workspace_rx = re.compile(rf"^(?:(?:work on|open|edit|go to) (?:the |my )?(?P<a>{alts}){suffix}(?:(?:,| and| then| to) (?P<g1>.+))?"
                               rf"|(?:in|on|for) (?:the |my )?(?P<b>{alts}){suffix},? (?P<g2>.+))$")


def change_command(lower: str, original: str) -> Optional[Reply]:
    """The change log and working on the user's own folders."""
    def span(m, g):
        return _span(original, lower, m.start(g), m.end(g)).strip() if m.group(g) else ""
    if _CHANGE_RX["list"].match(lower):
        return Reply("action", action=Action("change_list", {}))
    if m := _CHANGE_RX["show"].match(lower):
        return Reply("action", action=Action("change_show", {"id": int(m.group(1))}))
    if m := _CHANGE_RX["revert_n"].match(lower):
        return Reply("action", action=Action("change_revert", {"id": int(m.group("n")), "force": bool(m.group("force"))}))
    if m := _CHANGE_RX["revert_last"].match(lower):
        return Reply("action", action=Action("change_revert", {"id": None, "force": bool(m.group("force"))}))
    if m := _CHANGE_RX["path"].match(lower):
        return Reply("action", action=Action("workspace_open", {"path": span(m, "path").rstrip("."), "goal": span(m, "goal")}))
    if _workspace_rx is not None and (m := _workspace_rx.match(lower)):
        name = m.group("a") or m.group("b")
        goal = span(m, "g1") or span(m, "g2")
        return Reply("action", action=Action("workspace_open", {"name": name, "goal": goal}))
    return None


def computer_command(lower: str, original: str) -> Optional[Reply]:
    """“On my computer, rename the file on my desktop to notes”, “use my PC to …”, “click Save”: computer use."""
    m = _COMPUTER_RX.match(lower)
    if not m:
        return None
    name = next(g for g in ("a", "b", "c") if m.group(g))
    goal = _span(original, lower, m.start(name), m.end(name)).strip()
    return Reply("action", action=Action("computer_task", {"goal": goal})) if goal else None

_CODE_NOUN = (r"(?:python|javascript|js|typescript|html|css|node(?:\.?js)?|react|flask|django|java|kotlin|c\+\+|c sharp|c#|rust|"
              r"golang|web ?site|web ?page|web ?app|landing page|home ?page|portfolio|apps?|applications?|programs?|scripts?|"
              r"games?|bots?|chat ?bot|tools?|functions?|class|module|api|server|cli|calculator|dashboard|code|snippet|algorithm|"
              r"extension|plugin|widget|form|quiz|todo list|to do list|timer app)")
_CODE_RX = {
    "compose": re.compile(r"^(?:write|draft|compose|create|make)\s+(.+?)\s+and (?:type|paste) it(?: (?:out|here|in|for me))?$"),
    "type_last": re.compile(r"^type (?:it|that|this|the code|my code|the answer|your answer|it out|that out|out the code)"
                            r"(?: (?:out|here|for me|in|into (?:the|my) (?:editor|document|window)))?$"),
    "type": re.compile(r"^type(?: out| in)?[:\s]+(.+)$"),
    "open": re.compile(r"^(?:open|show(?: me)?) (?:the |my |this )?(?:project|code|project folder|code folder)"
                       r"(?: in (?:vs ?code|visual studio code|the editor|explorer))?$|^open (?:it|that) in (?:vs ?code|visual studio code|the editor)$"),
    "run": re.compile(r"^(?:run|start|launch|test|preview|show(?: me)?) (?:it|that|the (?:project|code|program|app|script|game|website|site|page)|"
                      r"my (?:project|code|program|app|script|game|website|site))$"),
    "new": re.compile(rf"^(?:code|program|build|make|create|write|develop|generate|design)\s+(?:me\s+|up\s+|us\s+)?"
                      rf"(?:(?:a|an|the|some|my|our)\s+)?(?:[\w'+#.-]+\s+){{0,4}}?{_CODE_NOUN}\b.*$"),
    "code_verb": re.compile(r"^code (?:up |me )?.+$"),
    "cont": re.compile(r"^(?:(?:now |also |then |and )?(?:fix|improve|update|change|modify|refactor|debug|test|extend|optimi[sz]e|style|"
                       r"restyle|redesign|rename|clean up|make|turn|set)\s+(?:the|my|this|that|our)\s+(?:[\w'-]+\s+){0,4}?(?:project|code|app|website|site|page|program|"
                       r"script|game|bot|tool|function|bug|bugs|error|errors|design|layout|header|footer|css|styles?|colou?rs?)\b.*|"
                       r"(?:add|put|include)\s+.+\s+(?:to|on|in)\s+(?:the|my|this|that|our)\s+(?:project|code|app|website|site|page|program|"
                       r"script|game|bot|tool)\b.*|keep going|continue (?:the )?(?:project|coding|building))$"),
}


def strip_fences(text: str) -> str:
    """A model that wraps the whole answer in ```…``` despite being told not to: keep what's inside."""
    t = (text or "").strip()
    m = re.match(r"^```[^\n]*\n([\s\S]*?)\n?```$", t)
    return m.group(1) if m else t


_VAULT_TYPE_RX = re.compile(
    r"^type (?:in )?(?:my |the )?(?:[\w .@'-]{0,40} )?(?:password|passcode|pin|username|user name|email id|login id|"
    r"card number|card expiry(?: date)?|expiry date|card (?:cvv|cvc|security code)|cvv|cvc|security code|"
    r"card ?holder name|name on (?:my |the )?[\w ]{0,30}card)(?: for [\w .@'-]{1,40})?$")


def code_command(lower: str, original: str) -> Optional[Reply]:
    """Coding, website-building and typing commands (user's own words only)."""
    def span(m, i):
        return _span(original, lower, m.start(i), m.end(i)).strip()

    if m := _CODE_RX["compose"].match(lower):
        return Reply("action", action=Action("compose_type", {"request": span(m, 1)}))
    if _CODE_RX["type_last"].match(lower):
        return Reply("action", action=Action("type_last", {}))
    if m := _CODE_RX["type"].match(lower):
        if _VAULT_TYPE_RX.match(lower):
            return None                 # "type my Gmail password": the vault types the real one (Windows Hello first)
        text = span(m, 1)
        return Reply("action", action=Action("type_text", {"text": text})) if text else None
    if _CODE_RX["open"].match(lower):
        return Reply("action", action=Action("project_open", {}))
    if _CODE_RX["run"].match(lower):
        return Reply("action", action=Action("project_run", {}))
    if _CODE_RX["cont"].match(lower):
        return Reply("action", action=Action("code_continue", {"request": original.strip().rstrip(".!")}))
    if _CODE_RX["new"].match(lower) or _CODE_RX["code_verb"].match(lower):
        return Reply("action", action=Action("code_task", {"goal": original.strip().rstrip(".!")}))
    return None

STOP_PHRASES = {"stop", "cancel", "stop it", "stop now", "stop echo", "echo stop", "halt", "that's enough",
                "enough", "never mind", "nevermind", "forget it", "shut up", "be quiet", "quiet", "stop talking"}
NUMBER_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                "eight": 8, "nine": 9, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
                "fifty": 50, "sixty": 60, "ninety": 90}
_DURATION = re.compile(r"\b(\d+|" + "|".join(sorted(NUMBER_WORDS, key=len, reverse=True)) +
                       r")\s*(hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)\b")

_EXACT = {
    "volume up": Action("volume", {"change": "up"}), "louder": Action("volume", {"change": "up"}),
    "turn it up": Action("volume", {"change": "up"}), "volume down": Action("volume", {"change": "down"}),
    "quieter": Action("volume", {"change": "down"}), "turn it down": Action("volume", {"change": "down"}),
    "mute": Action("volume", {"change": "mute"}), "unmute": Action("volume", {"change": "mute"}),
    "pause": Action("media", {"command": "toggle"}), "play": Action("media", {"command": "toggle"}),
    "resume": Action("media", {"command": "toggle"}), "pause music": Action("media", {"command": "toggle"}),
    "next": Action("media", {"command": "next"}), "next song": Action("media", {"command": "next"}),
    "skip": Action("media", {"command": "next"}), "skip song": Action("media", {"command": "next"}),
    "previous": Action("media", {"command": "previous"}), "previous song": Action("media", {"command": "previous"}),
    "lock my pc": Action("lock", {}), "lock the pc": Action("lock", {}), "lock pc": Action("lock", {}),
    "lock my computer": Action("lock", {}), "lock the computer": Action("lock", {}),
    "take a screenshot": Action("screenshot", {}), "screenshot": Action("screenshot", {}),
    "what time is it": Action("device_status", {"topic": "time"}), "what's the time": Action("device_status", {"topic": "time"}),
    "what's the date": Action("device_status", {"topic": "date"}), "what day is it": Action("device_status", {"topic": "date"}),
    "battery": Action("device_status", {"topic": "battery"}), "what's my battery": Action("device_status", {"topic": "battery"}),
    "how much battery do i have": Action("device_status", {"topic": "battery"}),
    "brief me": Action("briefing", {}), "good morning": Action("briefing", {}), "daily briefing": Action("briefing", {}),
    "what do you remember": Action("list_memories", {}), "what do you know about me": Action("list_memories", {}),
    "what do you remember about me": Action("list_memories", {}),
    "forget everything": Action("forget_all", {}), "clear your memory": Action("forget_all", {}),
    "erase your memory": Action("forget_all", {}),
    "stop translating": Action("switch_persona", {"name": "echo"}), "normal mode": Action("switch_persona", {"name": "echo"}),
    "list my timers": Action("list_timers", {}), "what timers do i have": Action("list_timers", {}),
    "summarize my clipboard": Action("clipboard_question", {"question": "Summarize this."}),
    "summarise my clipboard": Action("clipboard_question", {"question": "Summarize this."}),
    "explain my clipboard": Action("clipboard_question", {"question": "Explain this."}),
    "test my voice": Action("voice_test", {}), "voice test": Action("voice_test", {}),
    "test speech recognition": Action("voice_test", {}), "test my microphone": Action("voice_test", {}),
    "dictation test": Action("voice_test", {}), "open the voice test": Action("voice_test", {}),
    "type what i say": Action("voice_test", {}), "test how well you hear me": Action("voice_test", {}),
}

_RX = {
    "screen": re.compile(r"^(?:what's on (?:my|the) screen|what is on (?:my|the) screen|what am i looking at|"
                         r"(?:read|summari[sz]e|explain|describe|translate) (?:this|my|the) (?:screen|page|window)(?: (?:in)?to .+)?|"
                         r"explain this|summari[sz]e this)$"),
    "camera": re.compile(r"^(?:what do you see|what can you see|what are you seeing|what am i holding|what's in my hand|"
                         r"what is in my hand|what's in front of (?:me|you)|what is in front of (?:me|you)|"
                         r"look at (?:this|me|that)|(?:what|who) is this|what's this|identify this|"
                         r"(?:use|open|check) (?:the |my )?(?:camera|webcam)|"
                         r"(?:look|see) (?:through|with) (?:the |my )?(?:camera|webcam)|"
                         r"(?:describe|read|explain|translate|count) (?:what you see|this|that|what i'm holding|what i am holding)"
                         r"(?: (?:on|with|through|from) (?:the |my )?(?:camera|webcam))?|"
                         r".+ (?:on|with|through|from|using) (?:the |my )?(?:camera|webcam))$"),
    "timer": re.compile(r"^(?:set (?:a |an )?timer(?: for)?|start (?:a |an )?timer(?: for)?|timer(?: for)?)\s+(.+?)(?:\s+(?:called|named)\s+(.+))?$"),
    "remind_in": re.compile(r"^remind me in\s+(.+?)\s+to\s+(.+)$"),
    "remind_in_last": re.compile(r"^remind me to\s+(.+?)\s+in\s+(.+)$"),
    "volume_set": re.compile(r"^(?:set (?:the )?volume (?:to|at)|volume(?: to)?)\s+(\d{1,3})\s*(?:percent|%)?$"),
    "remember": re.compile(r"^(?:remember|don't forget|note) (?:that\s+)?(.+)$"),
    "forget": re.compile(r"^forget (?:that\s+|about\s+)?(.+)$"),
    "name": re.compile(r"^(?:call me|my name is|my name's)\s+(.+)$"),
    "translate": re.compile(r"^(?:translate|interpret)(?: everything| for me)?\s+(?:in)?to\s+(.+)$"),
    "switch": re.compile(r"^(?:switch to|change to|activate|enable|use|talk to|go into|enter)\s+(?:the\s+)?(.+?)(?:\s+(?:mode|persona))?$"),
    "mode": re.compile(r"^(.+?)\s+mode(?:\s+on)?$"),
    "be": re.compile(r"^(?:be|act|go)\s+(.+)$"),
    "youtube": re.compile(r"^(?:search youtube for|find on youtube|play (.+?) on youtube)\s*(.*)$"),
    "spotify": re.compile(r"^(?:search spotify for|play (.+?) on spotify)\s*(.*)$"),
    "google": re.compile(r"^(?:google|search google for|search for|look up)\s+(.+?)(?:\s+on google)?$"),
    "open": re.compile(r"^(?:open|launch|start)\s+(.+)$"),
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().rstrip(".!?")).lower()


def is_stop(text: str) -> bool:
    t = normalize(text)
    for prefix in ("hey echo ", "echo "):
        if t.startswith(prefix):
            t = t[len(prefix):]
    return t in STOP_PHRASES


def duration_seconds(text: str) -> Optional[int]:
    t = text.lower().strip()
    if t in ("half an hour", "half hour"):
        return 1800
    total, matched = 0, False
    for amount, unit in _DURATION.findall(t):
        n = int(amount) if amount.isdigit() else NUMBER_WORDS.get(amount)
        if n is None:
            continue
        total += n * (3600 if unit.startswith("h") else 60 if unit.startswith("m") else 1)
        matched = True
    return total if matched and total > 0 else None


def valid_url(url) -> Optional[str]:
    if not isinstance(url, str) or not url.strip() or len(url) > 2048:
        return None
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        return None
    return url.strip()


def _span(original: str, lower: str, start: int, end: int) -> str:
    collapsed = re.sub(r"\s+", " ", original.strip().rstrip(".!?"))
    return collapsed[start:end] if len(collapsed) == len(lower) else lower[start:end]


_catalog = None          # the Command Pack (echo_desktop.catalog.Catalog), installed by the brain and tests
_catalog_accept = None


def install_catalog(cat, accept) -> None:
    global _catalog, _catalog_accept
    _catalog, _catalog_accept = cat, accept


def _from_catalog(match) -> Reply:
    return Reply("action", action=Action("catalog", {"id": match.command.id, "slots": dict(match.slots)}))


def new_code_request(text: str) -> bool:
    """Does this ask Echo to build something new ("make my portfolio website", "code a snake game")?"""
    from . import catalog
    t = normalize(catalog.strip_prefix_raw(text or ""))
    return bool(_CODE_RX["new"].match(t) or _CODE_RX["code_verb"].match(t))


_SELECTION_WORDS = re.compile(
    r"\b(?:(?:the|this|that|my)\s+)?(?:text|words|part|bit|paragraph|line|lines|sentence|sentences|passage)\s+"
    r"(?:that\s+|which\s+)?i(?:'ve|\s+have)?\s+(?:just\s+)?(?:selected|highlighted|marked)\b"
    r"|\bwhat(?:ever)?\s+i(?:'ve|\s+have)?\s+(?:just\s+)?(?:selected|highlighted)\b", re.I)


def parse_command(text: str, persona_aliases: frozenset = frozenset()) -> Optional[Reply]:
    """Deterministic commands. Returns None for conversation (which goes to the model)."""
    from . import catalog
    raw = catalog.strip_prefix_raw(text)             # "hey echo, could you please …" -> "…"
    # "… for me / please / now" first: otherwise "open youtube for me" looks for an app called "youtube for me"
    shorter = catalog.strip_suffix_raw(raw)
    for candidate in ((shorter, raw) if shorter != raw else (raw,)):
        reply = _parse_core(text, candidate, persona_aliases)
        if reply is not None:
            return reply
    # "summarise the text I have selected", "translate what I highlighted": other words for "the selection"
    said_selection = _SELECTION_WORDS.sub("the selection", raw)
    if said_selection != raw:
        reply = _parse_core(said_selection, catalog.strip_suffix_raw(said_selection), persona_aliases)
        if reply is not None:
            return reply
    # "summarize my latest email in Gmail": a task on a known website goes to the web agent (when it's installed).
    if _web_site_rx is not None and _web_site_rx["mention"].search(normalize(raw)):
        return Reply("action", action=Action("web_task", {"goal": raw.strip()}))
    # Nothing matched literally: the learned intent model guesses what the person meant (or leaves it to the AI).
    if _intent_model is not None and _catalog is not None:
        label, p = _intent_model.classify(text)
        command = _catalog.by_id(label) if label != "AI" and p >= _intent_model.threshold else None
        if command is not None:
            return Reply("action", action=Action("catalog", {"id": command.id, "slots": {catalog.ALL: catalog.trim_edges(raw)}}))
    return None


_web_site_rx = None      # installed by the brain when "Control websites" is on


def install_web_sites(names) -> None:
    """Site names the web agent can control (lower case). Empty/None turns web tasks off."""
    global _web_site_rx
    names = sorted({normalize(n) for n in (names or []) if normalize(n)}, key=len, reverse=True)
    if not names:
        _web_site_rx = None
        return
    site = "(?:the )?(?:" + "|".join(re.escape(n) for n in names) + r")(?: website| site| app| page)?"
    _web_site_rx = {
        # "go to gmail and read my latest email", "on youtube, subscribe to mkbhd", "use the browser to ..."
        "lead": re.compile(rf"^(?:(?:go to|open|visit) {site},? (?:and |then |and then )|(?:on|in|using) {site},? )(.+)$"),
        "browser": re.compile(r"^(?:use|using|with) (?:the |my )?(?:browser|web|internet),? (?:to )?(.+)$"),
        "mention": re.compile(rf"^(?:\w+\s+){{1,}}.*\b(?:on|in|using|from|at) {site}(?: for me)?$"),
    }


def web_task(lower: str, original: str, is_command) -> Optional[Reply]:
    """Explicit web-task phrasings; the rest of the sentence must not itself be an ordinary Echo command."""
    if _web_site_rx is None:
        return None
    if _web_site_rx["browser"].match(lower):
        return Reply("action", action=Action("web_task", {"goal": original}))
    m = _web_site_rx["lead"].match(lower)
    if m and not is_command(m.group(1)):
        return Reply("action", action=Action("web_task", {"goal": original}))
    return None


_intent_model = None


def install_intent_model(model) -> None:
    global _intent_model
    _intent_model = model


def _parse_core(said: str, text: str, persona_aliases: frozenset) -> Optional[Reply]:
    original = text.strip()
    lower = normalize(text)
    if not lower:
        return None
    if is_stop(text):
        return Reply("action", action=Action("stop"))
    if lower in _EXACT:
        return Reply("action", action=_EXACT[lower])
    if _RX["screen"].match(lower):
        return Reply("action", action=Action("screen_question", {"question": original}))
    if _RX["camera"].match(lower):
        return Reply("action", action=Action("camera_question", {"question": original}))
    if (web := web_task(lower, original, lambda rest: _parse_core(rest, rest, persona_aliases) is not None)) is not None:
        return web
    if _catalog is not None and (m := _catalog.match_exact(said)):
        return _from_catalog(m)
    if (change := change_command(lower, original)) is not None:
        return change
    if (code := code_command(lower, original)) is not None:
        return code
    if (computer := computer_command(lower, original)) is not None:
        return computer
    if (mcp := mcp_command(lower, original)) is not None:
        return mcp

    def grp(m, i):
        return _span(original, lower, m.start(i), m.end(i)) if m.group(i) is not None else None

    if m := _RX["remind_in"].match(lower):
        secs = duration_seconds(m.group(1))
        return _timer(secs, grp(m, 2))
    if m := _RX["remind_in_last"].match(lower):
        secs = duration_seconds(m.group(2))
        if secs:
            return _timer(secs, grp(m, 1))
    if m := _RX["timer"].match(lower):
        return _timer(duration_seconds(m.group(1)), grp(m, 2))
    if m := _RX["volume_set"].match(lower):
        pct = int(m.group(1))
        return Reply("rejected", "Volume goes from 0 to 100 percent.") if pct > 100 else \
            Reply("action", action=Action("volume", {"change": "set", "percent": pct}))
    if lower.startswith(("remember", "don't forget", "note")) and (m := _RX["remember"].match(lower)):
        fact = clean_line(grp(m, 1), 300)
        return Reply("action", action=Action("remember", {"fact": fact})) if fact else Reply("rejected", "That memory is empty or too long.")
    if m := _RX["forget"].match(lower):
        return Reply("action", action=Action("forget", {"phrase": grp(m, 1)}))
    if m := _RX["name"].match(lower):
        name = clean_line(grp(m, 1), 40)
        return Reply("action", action=Action("set_name", {"name": name})) if name else None
    if m := _RX["translate"].match(lower):
        lang = clean_line(grp(m, 1), 30)
        if lang and re.fullmatch(r"[^\W\d_][\w ()-]*", lang):
            return Reply("action", action=Action("set_translator", {"language": lang.title()}))
    if m := _RX["switch"].match(lower):
        if m.group(1) in persona_aliases or lower.endswith((" mode", " persona")):
            return Reply("action", action=Action("switch_persona", {"name": m.group(1)}))
    for key in ("mode", "be"):
        if (m := _RX[key].match(lower)) and m.group(1) in persona_aliases:
            return Reply("action", action=Action("switch_persona", {"name": m.group(1)}))
    if _catalog is not None and (m := _catalog.match_template(said, _catalog_accept)):
        return _from_catalog(m)
    if m := _RX["youtube"].match(lower):
        query = grp(m, 1) or grp(m, 2)
        if query:
            return Reply("action", action=Action("web_search", {"engine": "youtube", "query": query}))
    if m := _RX["spotify"].match(lower):
        query = grp(m, 1) or grp(m, 2)
        if query:
            return Reply("action", action=Action("web_search", {"engine": "spotify", "query": query}))
    if m := _RX["google"].match(lower):
        return Reply("action", action=Action("web_search", {"engine": "google", "query": grp(m, 1)}))
    if m := _RX["open"].match(lower):
        target = grp(m, 1).strip()
        if target.lower().startswith(("http://", "https://")):
            url = valid_url(target)
            return Reply("action", action=Action("open_url", {"url": url})) if url else Reply("rejected", "That website address is not valid.")
        name = clean_line(target, 60)
        return Reply("action", action=Action("open_app", {"name": name})) if name else None
    return None


def _timer(seconds, label) -> Reply:
    if not seconds or not 1 <= seconds <= 86400:
        return Reply("rejected", "That timer length doesn't look right.")
    return Reply("action", action=Action("set_timer", {"seconds": seconds, "label": clean_line(label, 60) if label else None}))


MODEL_ACTIONS = {"open_app", "open_url", "web_search", "volume", "media", "set_timer", "device_status", "briefing",
                 "remember", "switch_persona", "lock", "screenshot", "stop", "run_command", "use_tools", "research"}


def parse_model_reply(reply: str) -> Reply:
    text = reply.strip()
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", text)
    candidate = fence.group(1).strip() if fence else text
    if not (candidate.startswith("{") and candidate.endswith("}")):
        return Reply("speech", text)
    try:
        obj = json.loads(candidate)
    except ValueError:
        return Reply("speech", text)
    if not isinstance(obj, dict) or "action" not in obj:
        say = clean_line(obj.get("say"), 2000) if isinstance(obj, dict) else None
        return Reply("speech", say or text)
    return validate_model_action(obj)


def validate_model_action(obj: dict) -> Reply:
    name = obj.get("action")
    if not isinstance(name, str) or name.lower() not in MODEL_ACTIONS:
        return Reply("rejected", f"The assistant asked for an action EchoDesktop doesn't support ({str(name)[:40]}). Nothing was done.")
    name = name.lower()
    args = obj.get("args") if isinstance(obj.get("args"), dict) else {}
    say = clean_line(obj.get("say"), 300) or ""

    def bad(field_name):
        return Reply("rejected", f"The assistant's {name} request had an invalid {field_name}. Nothing was done.")

    if name == "open_app":
        app = clean_line(args.get("name"), 60)
        return Reply("action", say, Action(name, {"name": app})) if app else bad("name")
    if name == "open_url":
        url = valid_url(args.get("url"))
        return Reply("action", say, Action(name, {"url": url})) if url else bad("url")
    if name == "web_search":
        engine = args.get("engine", "google")
        query = clean_line(args.get("query"), 200)
        if engine not in ("google", "youtube", "spotify") or not query:
            return bad("search")
        return Reply("action", say, Action(name, {"engine": engine, "query": query}))
    if name == "volume":
        change = args.get("change")
        pct = args.get("percent")
        if change not in ("up", "down", "mute", "set"):
            return bad("change")
        if change == "set" and not (isinstance(pct, int) and not isinstance(pct, bool) and 0 <= pct <= 100):
            return bad("percent")
        return Reply("action", say, Action(name, {"change": change, "percent": pct if change == "set" else None}))
    if name == "media":
        command = args.get("command")
        return Reply("action", say, Action(name, {"command": command})) if command in ("toggle", "play", "pause", "next", "previous") else bad("command")
    if name == "set_timer":
        secs = args.get("seconds")
        if not (isinstance(secs, int) and not isinstance(secs, bool) and 1 <= secs <= 86400):
            return bad("seconds")
        return Reply("action", say, Action(name, {"seconds": secs, "label": clean_line(args.get("label"), 60)}))
    if name == "device_status":
        topic = args.get("topic")
        return Reply("action", say, Action(name, {"topic": topic})) if topic in ("time", "date", "battery") else bad("topic")
    if name == "remember":
        fact = clean_line(args.get("fact"), 300)
        return Reply("action", say, Action(name, {"fact": fact})) if fact else bad("fact")
    if name == "switch_persona":
        persona = clean_line(args.get("name"), 30)
        return Reply("action", say, Action(name, {"name": persona})) if persona else bad("name")
    if name == "research":
        question = clean_line(args.get("question"), 400)
        return Reply("action", say, Action(name, {"question": question})) if question else bad("question")
    if name == "use_tools":
        goal = clean_line(args.get("goal"), 600)
        return Reply("action", say, Action(name, {"goal": goal, "server": clean_line(args.get("server"), 40)})) if goal else bad("goal")
    if name == "run_command":
        # The model names a Command Pack phrase; the deterministic parser decides what (if anything) it means.
        phrase = clean_line(args.get("text"), 200)
        parsed = parse_command(phrase) if phrase else None
        if not parsed:
            return Reply("rejected", f"EchoDesktop has no command for “{(phrase or '')[:60]}”. Nothing was done.")
        if parsed.action is not None and parsed.action.kind in USER_ONLY_ACTIONS:
            return Reply("rejected", "That needs you to ask me directly. Nothing was done.")
        return Reply(parsed.type, say or parsed.text, parsed.action)
    return Reply("action", say, Action(name, {}))


ACTION_PROTOCOL = """Your replies are spoken aloud on the user's Windows PC, so answer in short plain sentences without Markdown.
When the user clearly asks you to do something on the PC, reply with ONLY one JSON object and nothing else:
{"action":"<name>","args":{...},"say":"<optional short spoken line>"}
Allowed actions and args:
- open_app {"name": app name from the Start menu}
- open_url {"url": full https URL}
- web_search {"engine": "google"|"youtube"|"spotify", "query": text}
- volume {"change": "up"|"down"|"mute"|"set", "percent": 0-100 when set}
- media {"command": "toggle"|"next"|"previous"}
- set_timer {"seconds": 1-86400, "label": optional text}
- device_status {"topic": "time"|"date"|"battery"}
- briefing {}
- remember {"fact": one short lasting fact or preference the user shared}  (never passwords, codes or card numbers)
- switch_persona {"name": persona name}
- lock {}
- screenshot {}
- stop {}
- run_command {"text": one short command phrase EchoDesktop understands, e.g. "time in Tokyo", "convert 5 km to miles", "open device manager", "add milk to my shopping list", "open bluetooth settings"}  (EchoDesktop parses it itself; use it when no other action fits)
  It also controls the PC quietly: "copy that", "paste", "undo", "save this", "new tab", "switch to chrome", "close notepad", "snap this window left", "maximize this window", "scroll down 5", "select the next word", "go to the end of the line", "dark mode on", "make the screen brighter", "format the document", "toggle terminal", "mute myself in teams", "next slide".
  Live answers from the internet too: "weather tomorrow", "will it rain today in Pune", "latest version of react on npm", "is github down", "define serendipity", "news about ISRO", "price of bitcoin", "dollar to rupee rate".
- research {"question": what to find out}  (when the answer needs current or specific facts from the internet that you don't know for sure: Echo searches the web and reads pages itself, then answers)
- use_tools {"goal": the task in plain words, "server": optional MCP server name}  (Echo has 600+ exact built-in tools: maths, statistics, unit and currency conversion, loans/EMI/SIP/GST, dates and time zones, text and JSON/CSV tools, hashes and passwords, files and folders on this PC, PC info and control, live web data, India checks like PAN/GSTIN/IFSC/PIN code, developer tools like git status, and the user's lists, notes and timers — plus the user's MCP servers listed below. Use it whenever a calculation, file, lookup or several steps are needed instead of guessing; Echo asks the user before anything that changes things)
Never invent other actions, never claim an action already happened, and if the request is unclear ask a short question instead.
Reading the screen only happens when the user asks directly (for example "what's on my screen")."""


# --------------------------------------------------------------------------- memory rules

_STOP_WORDS = {"a", "an", "the", "is", "are", "was", "were", "i", "me", "my", "you", "your", "to", "of", "and", "or",
               "in", "on", "at", "for", "it", "that", "this", "with", "do", "does", "what", "who", "when", "where",
               "how", "be", "am", "about"}
_SENSITIVE = [
    re.compile(r"\b(?:password|passcode|passwd|pin|otp|one[- ]time code|cvv|cvc|security code|secret|api key|token|seed phrase|recovery phrase)\b", re.I),
    re.compile(r"\b(?:\d[ -]?){12,19}\b"),
    re.compile(r"\b\d{4,8}\b.*\b(?:code|pin)\b", re.I),
]


def is_sensitive(text: str) -> bool:
    return any(p.search(text) for p in _SENSITIVE)


def tokens(text: str) -> set:
    return {t for t in re.split(r"[^\w]+", text.lower()) if len(t) > 1 and t not in _STOP_WORDS}


def rank_memories(items: list, query: str, now: float, limit: int = 8) -> list:
    q = tokens(query)

    def score(item):
        overlap = len(tokens(item["text"]) & q)
        age_days = max(now - item.get("used", item["created"]), 0) / 86400
        return overlap * 2 + 0.5 / (1 + age_days / 30) + (0.3 if item.get("source") == "user" else 0) + min(item.get("uses", 0), 10) * 0.02

    return sorted(items, key=score, reverse=True)[:limit]


def forget_matches(items: list, phrase: str) -> list:
    wanted = tokens(phrase)
    if not wanted:
        return []
    exact = [i for i in items if i["text"].lower() == phrase.strip().lower()]
    if exact:
        return exact
    scored = [(i, len(tokens(i["text"]) & wanted)) for i in items]
    scored = [(i, s) for i, s in scored if s > 0]
    if not scored:
        return []
    best = max(s for _, s in scored)
    if best * 2 < len(wanted) + 1:
        return []
    return [i for i, s in scored if s == best]


def is_duplicate(items: list, text: str) -> bool:
    new = tokens(text)
    if not new:
        return True
    for item in items:
        other = tokens(item["text"])
        if other and len(new & other) / len(new | other) >= 0.8:
            return True
    return False


def format_duration(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    parts = [f"{v} {u}{'' if v == 1 else 's'}" for v, u in ((h, "hour"), (m, "minute"), (s, "second")) if v]
    return " ".join(parts) or "0 seconds"


def orb_radius(base: float, phase: float, active: bool) -> float:
    """Pulse used by the desktop orb animation."""
    return base * (1 + 0.08 * math.sin(phase * 2 * math.pi)) if active else base
