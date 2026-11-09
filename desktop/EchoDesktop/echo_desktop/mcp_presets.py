"""Ready-made MCP servers ("add the files tools") and import of MCP setups the user already has in other AI apps
(Claude Desktop, Claude Code, Cursor, VS Code, Windsurf). Pure functions over plain dicts; the brain saves the result
in settings["mcp_servers"]."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

HOME = Path(os.environ.get("USERPROFILE", str(Path.home())))
APPDATA = Path(os.environ.get("APPDATA", str(HOME)))


def _docs() -> str:
    for p in (HOME / "OneDrive" / "Documents", HOME / "Documents"):
        if p.exists():
            return str(p)
    return str(HOME)


# name -> (spoken names, description, server entry). Official/reference servers; installed on first use by npx/uvx.
PRESETS = {
    "files": (("files", "file", "filesystem", "file system", "my files"), "Read, search and edit files in Documents, Desktop and Downloads",
              {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", _docs(), str(HOME / "Desktop"), str(HOME / "Downloads")]}),
    "fetch": (("fetch", "web fetch", "fetch web pages", "reader"), "Fetch any web page as clean text",
              {"command": "uvx", "args": ["mcp-server-fetch"]}),
    "git": (("git",), "Inspect and work with git repositories",
            {"command": "uvx", "args": ["mcp-server-git"]}),
    "time": (("time", "time zones", "clock"), "Current time and time-zone conversion",
             {"command": "uvx", "args": ["mcp-server-time"]}),
    "memory": (("memory", "knowledge graph", "notes graph"), "A persistent knowledge graph the AI can remember things in",
               {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-memory"]}),
    "thinking": (("thinking", "sequential thinking", "reasoning"), "Step-by-step reasoning scratchpad for hard problems",
                 {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]}),
    "everything": (("everything", "test server", "demo"), "The MCP reference test server (for trying things out)",
                   {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-everything"]}),
    "github": (("github", "git hub"), "GitHub (repos, issues, pull requests) — needs a GitHub token in the entry's headers",
               {"url": "https://api.githubcopilot.com/mcp/", "headers": {"Authorization": "Bearer <your GitHub token>"}}),
    # added 2026-11: each one checked to exist (package on npm/PyPI, or the remote server answering MCP initialize)
    "context7": (("context7", "context 7", "library docs", "code docs"), "Up-to-date docs and code examples for any library",
                 {"url": "https://mcp.context7.com/mcp"}),
    "deepwiki": (("deepwiki", "deep wiki", "repo docs", "github docs"), "Ask questions about any public GitHub repository",
                 {"url": "https://mcp.deepwiki.com/mcp"}),
    "mslearn": (("microsoft learn", "ms learn", "microsoft docs", "ms docs", "azure docs", "windows docs"),
                "Search Microsoft's official documentation (Windows, Azure, .NET, Office)",
                {"url": "https://learn.microsoft.com/api/mcp"}),
    "huggingface": (("hugging face", "huggingface", "hf"), "Search Hugging Face models, datasets, spaces and papers",
                    {"url": "https://huggingface.co/mcp"}),
    "markitdown": (("markitdown", "mark it down", "document reader", "convert documents"),
                   "Turn PDFs, Word, Excel, PowerPoint and web pages into readable text",
                   {"command": "uvx", "args": ["markitdown-mcp"]}),
    "duckduckgo": (("duckduckgo", "duck duck go", "web search", "search"), "Web search through DuckDuckGo",
                   {"command": "uvx", "args": ["duckduckgo-mcp-server"]}),
    "awsdocs": (("aws docs", "aws documentation", "amazon web services docs"), "Search and read AWS documentation",
                {"command": "uvx", "args": ["awslabs.aws-documentation-mcp-server@latest"], "env": {"FASTMCP_LOG_LEVEL": "ERROR"}}),
}
READ_ONLY_PRESETS = {"fetch", "time", "thinking", "context7", "deepwiki", "mslearn", "awsdocs", "duckduckgo"}   # can't change anything


def find_preset(spoken: str) -> Optional[str]:
    s = re.sub(r"[^a-z0-9 ]", "", (spoken or "").lower()).strip()
    s = re.sub(r"\b(the|my|mcp|tools?|servers?|server|connector)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    for key, (names, _, _) in PRESETS.items():
        if s == key or s in names:
            return key
    return None


def preset_entry(key: str) -> dict:
    names, desc, entry = PRESETS[key]
    return {"name": key, **json.loads(json.dumps(entry)), "description": desc, **({"trusted": True} if key in READ_ONLY_PRESETS else {})}


# ------------------------------------------------------------------------------------------------ import
SOURCES = {
    "claude desktop": [APPDATA / "Claude" / "claude_desktop_config.json"],
    "claude code": [HOME / ".claude.json", HOME / ".claude" / "settings.json"],
    "cursor": [HOME / ".cursor" / "mcp.json"],
    "vs code": [APPDATA / "Code" / "User" / "mcp.json", APPDATA / "Code" / "User" / "settings.json"],
    "windsurf": [HOME / ".codeium" / "windsurf" / "mcp_config.json"],
}


def _strip_jsonc(text: str) -> str:
    text = re.sub(r"(?m)^\s*//.*$", "", text)
    return re.sub(r",(\s*[}\]])", r"\1", text)


def servers_in(data) -> list:
    """MCP server entries from any of the common config shapes (mcpServers / servers / mcp.servers / projects.*.mcpServers)."""
    found = []

    def take(block):
        if not isinstance(block, dict):
            return
        for name, cfg in block.items():
            if not isinstance(cfg, dict):
                continue
            entry = {"name": re.sub(r"[^a-z0-9_-]+", "-", str(name).lower()).strip("-")[:30] or "server"}
            if cfg.get("command"):
                entry.update(command=str(cfg["command"]), args=[str(a) for a in cfg.get("args") or []])
                if isinstance(cfg.get("env"), dict):
                    entry["env"] = {str(k): str(v) for k, v in cfg["env"].items()}
                if cfg.get("cwd"):
                    entry["cwd"] = str(cfg["cwd"])
            elif cfg.get("url") and str(cfg.get("type", "http")).lower() in ("http", "streamable-http", "streamablehttp", ""):
                entry.update(url=str(cfg["url"]))
                if isinstance(cfg.get("headers"), dict):
                    entry["headers"] = {str(k): str(v) for k, v in cfg["headers"].items()}
            else:
                continue                                      # sse-only / unknown transports are skipped
            if cfg.get("disabled") is True:
                entry["enabled"] = False
            found.append(entry)
    if isinstance(data, dict):
        take(data.get("mcpServers"))
        take(data.get("servers"))
        if isinstance(data.get("mcp"), dict):
            take(data["mcp"].get("servers"))
        for proj in (data.get("projects") or {}).values() if isinstance(data.get("projects"), dict) else []:
            if isinstance(proj, dict):
                take(proj.get("mcpServers"))
    return found


def import_from(source: Optional[str] = None) -> tuple:
    """(servers, sources_read). source: one of SOURCES keys, or None for all of them."""
    keys = [source] if source in SOURCES else list(SOURCES)
    servers, read = [], []
    for k in keys:
        for path in SOURCES[k]:
            if not path.is_file():
                continue
            try:
                data = json.loads(_strip_jsonc(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
            got = servers_in(data)
            if got:
                read.append(k)
                servers += got
    return servers, read


def merge(existing: list, new: list) -> tuple:
    """Add servers whose names aren't taken yet (an Echo name is never overwritten). Returns (merged, added_names)."""
    have = {s.get("name") for s in existing if isinstance(s, dict)} | {"browser"}
    merged, added = list(existing), []
    for s in new:
        if s["name"] in have or s["name"] == "echo":       # never import Echo into itself
            continue
        merged.append(s)
        have.add(s["name"])
        added.append(s["name"])
    return merged, added
