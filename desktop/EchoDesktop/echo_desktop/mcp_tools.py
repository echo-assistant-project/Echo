"""The user's MCP servers for Echo's AI: start them lazily, list, add presets, import from other apps, trust, remove."""
from __future__ import annotations

import threading
from typing import Optional

from . import mcp_presets
from .mcp_client import McpHub


class ToolHub:
    def __init__(self, settings):
        self.settings = settings
        self.hub: Optional[McpHub] = None
        self._key = None
        self._lock = threading.Lock()

    def servers(self) -> list:
        return [s for s in (self.settings["mcp_servers"] or []) if isinstance(s, dict) and s.get("name") != "browser"]

    def enabled_servers(self) -> list:
        return [s for s in self.servers() if s.get("enabled", True)]

    def names(self) -> list:
        return [s["name"] for s in self.enabled_servers()]

    def get(self) -> McpHub:
        """The running hub (started on first use, restarted when the server list changes)."""
        import json
        key = json.dumps(self.enabled_servers(), sort_keys=True)
        with self._lock:
            if self.hub is None or key != self._key:
                if self.hub is not None:
                    self.hub.close()
                self.hub = McpHub(self.enabled_servers())
                self.hub.start()
                self._key = key
            return self.hub

    def reload(self) -> McpHub:
        with self._lock:
            if self.hub is not None:
                self.hub.close()
            self.hub = None
        return self.get()

    def close(self) -> None:
        with self._lock:
            if self.hub is not None:
                self.hub.close()
            self.hub = None

    def _save(self, servers: list) -> None:
        browser = [s for s in (self.settings["mcp_servers"] or []) if isinstance(s, dict) and s.get("name") == "browser"]
        self.settings["mcp_servers"] = browser + servers
        self.sync_phrases()

    def sync_phrases(self) -> None:
        """Let “use <server> to …” work for exactly the servers the user has."""
        from . import core
        core.install_mcp_servers(self.names())

    # ---- spoken management -------------------------------------------------------------------------------------
    def describe(self) -> str:
        servers = self.servers()
        if not servers:
            return ("No MCP servers are connected yet. Say “add the files tools”, “add the fetch tools”, or “import my MCP "
                    "servers” to bring in the ones you set up for Claude, Cursor or VS Code.")
        hub = self.get()
        parts = []
        for s in servers:
            name = s["name"]
            if not s.get("enabled", True):
                parts.append(f"{name} (off)")
            elif name in hub.errors:
                parts.append(f"{name} (not working: {hub.errors[name][:80]})")
            else:
                n = len([t for t in hub.tools() if t["server"] == name])
                parts.append(f"{name} ({n} tools{', trusted' if s.get('trusted') else ''})")
        return "Connected MCP servers: " + "; ".join(parts) + "."

    def add_preset(self, spoken: str) -> tuple:
        key = mcp_presets.find_preset(spoken)
        if key is None:
            return False, ("I don't have a ready-made server called “" + spoken + "”. I can add: " +
                           ", ".join(mcp_presets.PRESETS) + ". Or import yours with “import my MCP servers”.")
        merged, added = mcp_presets.merge(self.servers(), [mcp_presets.preset_entry(key)])
        if not added:
            return True, f"The {key} tools are already connected."
        self._save(merged)
        note = " Put your GitHub token in its entry in Settings first." if key == "github" else ""
        return True, f"Added the {key} tools: {mcp_presets.PRESETS[key][1].lower()}.{note} They start the first time I use them."

    def remove(self, spoken: str) -> tuple:
        target = (mcp_presets.find_preset(spoken) or spoken).strip().lower()
        keep = [s for s in self.servers() if s["name"].lower() != target]
        if len(keep) == len(self.servers()):
            return False, f"No MCP server called “{spoken}”. " + self.describe()
        self._save(keep)
        return True, f"Removed the {target} tools."

    def set_trusted(self, spoken: str, trusted: bool) -> tuple:
        target = (mcp_presets.find_preset(spoken) or spoken).strip().lower()
        servers = self.servers()
        for s in servers:
            if s["name"].lower() == target:
                if trusted:
                    s["trusted"] = True
                else:
                    s.pop("trusted", None)
                self._save(servers)
                return True, (f"I'll use the {target} tools without asking each time." if trusted
                              else f"I'll ask before using the {target} tools again.")
        return False, f"No MCP server called “{spoken}”."

    def import_servers(self, source: Optional[str]) -> tuple:
        found, read = mcp_presets.import_from(source)
        if not found:
            where = source or "Claude Desktop, Claude Code, Cursor, VS Code or Windsurf"
            return True, f"I didn't find any MCP servers set up in {where}."
        merged, added = mcp_presets.merge(self.servers(), found)
        self._save(merged)
        if not added:
            return True, "Those MCP servers are already in Echo."
        return True, f"Imported {len(added)} MCP server{'s' if len(added) != 1 else ''} from {', '.join(read)}: {', '.join(added)}."

    def prompt_line(self) -> str:
        names = self.names()
        if not names:
            return ""
        descs = []
        for s in self.enabled_servers():
            d = s.get("description") or ""
            descs.append(f"{s['name']}" + (f" ({d[:60]})" if d else ""))
        return "The user's connected MCP tool servers (use them with the use_tools action): " + "; ".join(descs) + "."
