"""Glue between EchoDesktop and its website tools: Echo's built-in browser (in-process, browser/) plus any MCP servers
you added, the sites Echo knows, and web-agent sessions.

Used by the brain (voice/typed commands) and by bridge.py (tasks relayed from the phone).
"""
from __future__ import annotations

import threading
from typing import Optional

from . import core
from .browser import BrowserHub, load_sites
from .internet import CombinedHub
from .mcp_client import McpHub
from .web_agent import Outcome, Run, WebAgent, answer_kind


def site_names(extra: str = "") -> list:
    try:
        return sorted(load_sites(extra=extra))
    except Exception:
        return []


def server_configs(settings) -> list:
    """The MCP servers the user added in settings["mcp_servers"] (the browser is built in, not a server)."""
    return [s for s in settings["mcp_servers"] or [] if isinstance(s, dict) and s.get("name") not in (None, "browser")]


class WebSessions:
    """One shared tool hub; one pending web-agent run per conversation key ("desktop", "phone")."""

    def __init__(self, settings):
        self.settings = settings
        self.hub: Optional[CombinedHub] = None
        self.browser: Optional[BrowserHub] = None
        self.mcp: Optional[McpHub] = None
        self.runs: dict = {}
        self._lock = threading.Lock()
        self._installed = None

    def enabled(self) -> bool:
        return bool(self.settings["web_control"])

    def sync(self) -> None:
        """Install/remove the web-task phrases to match the setting."""
        state = (self.enabled(), self.settings["web_extra_sites"])
        if state != self._installed:
            core.install_web_sites(site_names(state[1]) if state[0] else None)
            self._installed = state
            if not state[0]:
                self.close()

    def _hub(self) -> CombinedHub:
        with self._lock:
            if self.hub is None:
                self.browser = BrowserHub(lambda: self.settings["web_extra_sites"] or "")
                configs = server_configs(self.settings)
                if configs:
                    self.mcp = McpHub(configs)
                    self.mcp.start()                       # a failing extra server never blocks the browser
                self.hub = CombinedHub(self.browser, self.mcp)
            return self.hub

    def waiting(self, key: str) -> Optional[str]:
        """'confirm' or 'ask' when the run for `key` is waiting for the user."""
        run = self.runs.get(key)
        return None if run is None else ("confirm" if run[1].pending else "ask")

    def cancel(self, key: str) -> None:
        self.runs.pop(key, None)

    def start(self, key: str, goal: str, complete, status=lambda s: None, cancelled=lambda: False) -> Outcome:
        agent = WebAgent(complete, self._hub(), status, cancelled)
        run, outcome = agent.start(goal)
        return self._keep(key, agent, run, outcome)

    def answer(self, key: str, text: str) -> Optional[Outcome]:
        """Feed the user's reply to a waiting run. None means the reply wasn't for the web run (it was dropped)."""
        held = self.runs.pop(key, None)
        if held is None:
            return None
        agent, run = held
        if run.pending is not None and answer_kind(text) is None:
            return None                                   # a new command, not a yes/no: drop the pending click
        return self._keep(key, agent, run, agent.resume(run, text))

    def _keep(self, key: str, agent: WebAgent, run: Run, outcome: Outcome) -> Outcome:
        if outcome.kind in ("confirm", "ask"):
            self.runs[key] = (agent, run)
        return outcome

    def close(self) -> None:
        with self._lock:
            for h in (self.browser, self.mcp):
                if h is not None:
                    h.close()
            self.hub = self.browser = self.mcp = None
        self.runs.clear()
