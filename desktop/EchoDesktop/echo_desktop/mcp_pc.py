"""The PC side of Echo's MCP server (mcp_server.py): runs each tool. Loaded on a background thread after the AI app
connects, so connecting stays instant.

Calls may arrive together. Anything that touches the keyboard, mouse, windows or apps holds `self.pc`, so two of them
never interleave; answers that only compute or look things up (find_commands, time, unit sums, web answers, dev
tools) run straight away, in parallel.
"""
from __future__ import annotations

import base64
import ctypes
import os
import random
import threading
import time
from typing import Optional

from . import catalog, computer, control, core, pcctl, tools, typer, voice
from .mcp_rpc import error, text
from .mcp_server import ancestor_pids, ask_text, ask_yes_no

BLOCKED_KINDS = ("echo", "list", "mcp", "selection")          # these drive the Echo app itself
BLOCKED_OPS = {"DOWNLOAD", "RESEARCH", "SUMMARIZE_URL", "INTERNET_ON", "INTERNET_OFF", "INTERNET_STATUS", "SET_CITY"}
INPUT_KINDS = ("keys", "text", "mouse", "window", "clip")    # act on the user's app: bring it to the front first
SIMPLE_LEGACY = {"open_app", "open_url", "web_search", "volume", "media", "screenshot", "device_status", "lock"}


class _SpeakSettings(dict):
    """Minimal settings for voice.Speaker: the Windows voice only (no Kokoro keys in this process)."""

    def __getitem__(self, k):
        return {"use_kokoro": False}.get(k)

    def secret(self, _k):
        return ""


class EchoServer:
    def __init__(self):
        self.cat = catalog.load("desktop")
        data = tools.load_data()
        core.install_catalog(self.cat, lambda m: m.command.kind != "tool" or tools.run_match(m, tools.context(data)) is not None)
        self.tool_data = data
        self.focus = typer.FocusTracker(exclude=ancestor_pids())
        self.focus.start()
        self.screen: Optional[computer.ScreenMap] = None
        self.last_clicked: Optional[dict] = None
        self.hands = computer.Hands(control.open_app)
        self.pc = threading.RLock()
        # find_commands index: built once, not on every search
        self.index = [(c, f"{c.title} {c.group} {' '.join(c.phrases)}".lower(), c.title.lower())
                      for c in self.cat.commands if c.kind not in ("echo", "list")]
        self._samples: dict = {}
        self.cat.precompile()                                  # the first run_command shouldn't pay for these
        for phrase in ("what is 5 percent of 100", "convert 5 km to miles", "what time is it"):
            core.parse_command(phrase)

    # ---- targeting (call with self.pc held)
    def target(self, window: Optional[str]) -> Optional[str]:
        if window:
            match = next((h for h, t, _ in pcctl.top_windows() if window.lower() in t.lower()), None)
            if not match:
                return f"No open window title contains “{window}”."
            self.focus.target = match
        if not self.focus.focus_target():
            return "No app window to act on yet: ask the user to click into the app first, or pass window."
        return None

    # ---- tools
    def sample(self, c) -> str:
        s = self._samples.get(c.id)
        if s is None:
            s = catalog.samples(catalog.parse_pattern(c.phrases[0]), lambda slot: "5" if slot.startswith("n") else "pizza")[0]
            self._samples[c.id] = s
        return s

    def find_commands(self, query: str, limit=15) -> dict:
        words = {w for w in core.normalize(query).split() if len(w) > 2}
        scored = []
        for c, hay, title in self.index:
            score = sum(2 if w in title else 1 for w in words if w in hay)
            if score:
                scored.append((score, c.order, c))
        scored.sort(key=lambda sc: (-sc[0], sc[1]))
        try:
            n = max(1, min(int(limit or 15), 50))
        except (TypeError, ValueError):
            n = 15
        lines = [f"“{self.sample(c)}”  — {c.title} [{c.group}]" for _, _, c in scored[:n]]
        return text("\n".join(lines) if lines else "No matching commands. Try other words, or use look + click.")

    def run_command(self, said: str, window: Optional[str] = None) -> dict:
        parsed = core.parse_command(said)
        if not parsed or not parsed.action:
            return error(f"Echo has no command for “{said}”. Use find_commands, or type_text / press_keys / look + click.")
        a = parsed.action
        slots = a.args.get("slots", {}) if isinstance(a.args, dict) else {}
        if a.kind == "catalog":
            cmd = self.cat.by_id(a.args["id"])
            if cmd.kind in BLOCKED_KINDS or cmd.spec.get("op") in BLOCKED_OPS:
                return error("That command controls the Echo app itself and isn't available here.")
            if cmd.kind == "net":
                from . import internet
                try:
                    ans = internet.info(cmd.spec["op"], slots)
                except (internet.NetError, OSError, ValueError, KeyError) as e:
                    return error(str(e))
                return text(ans.text + (f"\n(link: {ans.open_url})" if ans.open_url else ""))
            if cmd.kind == "dev":
                from . import devtools
                try:
                    r = devtools.run(cmd.spec["op"], slots)
                except devtools.DevError as e:
                    return error(str(e))
                if r.copy is not None:
                    typer.set_clipboard_text(r.copy)          # same as when the user says it: secrets go to the clipboard only
                return text(r.text)
            if cmd.kind == "tool":
                r = tools.run_match(catalog.Match(cmd, slots), tools.context(self.tool_data))
                if r is None:
                    return error("That didn't work out.")
                if r.kind == "web":
                    control.open_url(r.url)
                return text(r.text)
            if cmd.kind == "say":
                return text(catalog.fill(cmd.spec["text"], slots))
            if cmd.kind == "content":
                items = self.tool_data.topics.get(cmd.spec["topic"]) or []
                return text(random.choice(items).replace("|", " — ")) if items else error("No content.")
            with self.pc:
                if cmd.kind in INPUT_KINDS and (problem := self.target(window)):
                    return error(problem)
                if cmd.kind in pcctl.KINDS:
                    ok, msg = pcctl.run(cmd, slots, ask_yes_no, None, control.open_app)
                else:
                    ok, msg = control.run_catalog(cmd, slots, ask_yes_no)
            return text(msg) if ok else error(msg)
        if a.kind in SIMPLE_LEGACY:
            fn = {"open_app": lambda: control.open_app(a.args["name"]), "open_url": lambda: control.open_url(a.args["url"]),
                  "web_search": lambda: control.web_search(a.args["engine"], a.args["query"]),
                  "volume": lambda: control.volume(a.args["change"], a.args.get("percent")),
                  "media": lambda: control.media(a.args["command"]), "screenshot": control.screenshot,
                  "device_status": lambda: control.status(a.args["topic"]), "lock": control.lock}[a.kind]
            with self.pc:
                ok, msg = fn()
            return text(msg) if ok else error(msg)
        return error(f"“{said}” is an Echo-app action (it needs the Echo window). Use the other tools instead.")

    def type_text(self, s: str, window: Optional[str] = None) -> dict:
        if core.is_sensitive(s):
            return error("Echo never types passwords, PINs, codes or card numbers.")
        with self.pc:
            if self.last_clicked and self.last_clicked.get("password"):
                return error("The last clicked field is a password field; the user must type passwords themselves.")
            if (problem := self.target(window)):
                return error(problem)
            r = typer.type_text(s, None)
        return text(r.message) if r.ok else error(r.message)

    def press_keys(self, keys: str, times=1, window: Optional[str] = None) -> dict:
        try:
            typer.key_sequence(keys)
            n = max(1, min(int(times or 1), 50))
        except (ValueError, TypeError) as e:
            return error(str(e))
        with self.pc:
            if (problem := self.target(window)):
                return error(problem)
            title = pcctl.title(pcctl.foreground())
            fake = computer.ScreenMap(title, 0, 0, [], [])
            if (q := computer.needs_confirm("key", {"keys": keys}, fake)) and not ask_yes_no("Press keys", q):
                return error("The user declined that key press.")
            typer.press(keys, n)
        return text(f"Pressed {keys}" + (f" ×{n}" if n > 1 else "") + f" in {title[:60]}.")

    def look(self, image: bool = False, window: Optional[str] = None) -> dict:
        with self.pc:
            if window and (problem := self.target(window)):
                return error(problem)
            hwnd = lambda: self.focus.target or computer.foreground_window()   # noqa: E731
            try:
                self.screen = computer.Eyes(voice.helper_command, hwnd)(bool(image))
            except OSError as e:
                return error(str(e))
            screen = self.screen
        content = [{"type": "text", "text": screen.describe()}]
        if image and screen.image:
            content.append({"type": "image", "data": base64.b64encode(screen.image).decode(), "mimeType": "image/jpeg"})
        return {"content": content}

    def click(self, target: Optional[str] = None, x=None, y=None, button: str = "left", double: bool = False) -> dict:
        with self.pc:
            if target and not self.screen:
                return error("Call look first, then click an id from it.")
            screen = self.screen or computer.ScreenMap("", ctypes.windll.user32.GetSystemMetrics(0),
                                                       ctypes.windll.user32.GetSystemMetrics(1), [], [])
            args = {"id": target} if target else {"x": x, "y": y}
            tool = "right_click" if button == "right" else "double_click" if double else "click"
            if (q := computer.needs_confirm(tool, args, screen)) and not ask_yes_no("Click", q):
                return error("The user declined that click.")
            p = computer.point(args, screen)
            if p is None:
                return error("Unknown target or a point outside the screen.")
            self.hands.click(p[0], p[1], button=button if button in ("left", "right") else "left", double=bool(double))
            self.last_clicked = screen.target(target) if target else None
            self.screen = None                                     # the screen changed: look again before the next id click
        return text(f"Clicked {computer.label_of(screen.target(target)) or f'{p[0]},{p[1]}'}. Call look to see the result.")

    def scroll(self, direction: str, amount=3) -> dict:
        try:
            n = max(1, min(int(amount or 3), 20))
        except (TypeError, ValueError):
            n = 3
        with self.pc:
            self.hands.scroll(n if direction == "up" else -n)
        return text(f"Scrolled {'up' if direction == 'up' else 'down'} {n}.")

    def open_app(self, name: str) -> dict:
        found = control.find_app(name)
        if not found:
            return error(f"I couldn't find {name} in the Start menu.")
        label, target = found
        with self.pc:                                          # the next key press waits until the app is up
            before = pcctl.window_handles()
            started = time.monotonic()
            os.startfile(target)
            h = pcctl.wait_for_window(label, before, timeout=pcctl.LAUNCH_WAIT)
        if h is None:
            return text(f"Started {label}; its window hasn't appeared after {pcctl.LAUNCH_WAIT:.0f} seconds (it may still be loading).")
        return text(f"{label} is open ({time.monotonic() - started:.0f} s): {pcctl.title(h)}.")

    def call(self, name: str, a: dict) -> dict:
        if name == "find_commands":
            return self.find_commands(str(a.get("query", "")), a.get("limit") or 15)
        if name == "run_command":
            return self.run_command(str(a.get("text", "")), a.get("window"))
        if name == "type_text":
            return self.type_text(str(a.get("text", "")), a.get("window"))
        if name == "press_keys":
            return self.press_keys(str(a.get("keys", "")), a.get("times") or 1, a.get("window"))
        if name == "look":
            return self.look(bool(a.get("image")), a.get("window"))
        if name == "click":
            return self.click(a.get("target"), a.get("x"), a.get("y"), str(a.get("button") or "left"), bool(a.get("double")))
        if name == "scroll":
            return self.scroll(str(a.get("direction", "down")), a.get("amount") or 3)
        if name == "list_windows":
            wins = pcctl.top_windows()
            return text("\n".join(f"{t} — {p}" for _, t, p in wins) or "No app windows are open.")
        if name == "focus_window":
            with self.pc:
                problem = self.target(str(a.get("title", "")))
                return error(problem) if problem else text(f"Now in front: {pcctl.title(pcctl.foreground())}.")
        if name == "open_app":
            return self.open_app(str(a.get("name", "")))
        if name == "open_url":
            url = core.valid_url(a.get("url"))
            if not url:
                return error("That isn't a valid http(s) address.")
            ok, msg = control.open_url(url)
            return text(msg) if ok else error(msg)
        if name == "ask_user":
            answer = ask_text(str(a.get("question", "")))
            return text(answer if answer is not None else "(the user closed the box without answering)")
        if name == "speak":
            done = threading.Event()
            voice.Speaker(_SpeakSettings()).speak(str(a.get("text", ""))[:500], "", 1.0, done.set)
            done.wait(60)
            return text("Spoken.")
        return error(f"Unknown tool {name}.")
