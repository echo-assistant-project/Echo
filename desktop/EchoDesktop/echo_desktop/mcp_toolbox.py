"""Echo's toolbox as an MCP server (stdio), so Claude, Cursor, VS Code and other AI apps can use the same 600+ tools.

    <python 3.12>\\python.exe path\\to\\desktop\\EchoDesktop\\echo_tools_mcp.py
    (or: py -3.12 path\\to\\desktop\\EchoDesktop\\echo_tools_mcp.py — no space after the dash)

This front is kept light so `initialize` and `tools/list` answer at once: the tool list comes from a disk cache
(rebuilt automatically whenever any Echo source file changes) and the 600+ tool modules (toolbox/mcp.py) load on a
background thread while the AI app is still connecting. Calls run in parallel; keyboard/mouse tools take turns.
Tools that change things show a Yes/No box on this PC first.
"""
from __future__ import annotations

import json
import os
import sys

from . import mcp_rpc

SERVER_INFO = {"name": "echo-tools", "title": "Echo toolbox", "version": "2.0"}
INSTRUCTIONS = ("Echo's toolbox: 600+ exact tools for maths and statistics, unit and currency conversion, money (EMI, SIP, GST), dates and "
                "time zones, text/JSON/CSV/XML, hashes and passwords, files and folders on this Windows PC, PC information and control, "
                "live web data (weather, news, packages, GitHub, service status), India checks (PAN, GSTIN, IFSC, PIN code) and developer "
                "tools (read-only git, templates, HTTP). If you're not sure which tool fits, call find_tools first. Tools that change "
                "things ask the user on the PC.")
LIST_CACHE_VERSION = 1
HERE = os.path.dirname(os.path.abspath(__file__))


def _source_stamp() -> str:
    """Python's version plus every Echo source file's size and time: any edit gives a new stamp."""
    import hashlib
    h = hashlib.sha256(f"{sys.version}|{LIST_CACHE_VERSION}".encode())
    for root, dirs, files in os.walk(HERE):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for f in sorted(files):
            if f.endswith(".py"):
                p = os.path.join(root, f)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                h.update(f"{os.path.relpath(p, HERE)}|{st.st_size}|{st.st_mtime_ns}\n".encode())
    return h.hexdigest()[:32]


def cache_dir() -> str:
    return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "EchoDesktop", "cache")


_ASKS: set = set()                                      # tools that ask the user first (destructiveHint)


def _note_asks(tools: list) -> None:
    _ASKS.update(t["name"] for t in tools if isinstance(t, dict) and (t.get("annotations") or {}).get("destructiveHint"))


def cached_tool_list() -> tuple:
    """(JSON text, list) of the tools: from the disk cache when it's current (a few ms), else built (~0.4 s) and saved."""
    path = os.path.join(cache_dir(), f"mcp-tools-{_source_stamp()}.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = f.read()
        tools = json.loads(data)
        if isinstance(tools, list) and tools and all(isinstance(t, dict) and isinstance(t.get("name"), str) for t in tools):
            _note_asks(tools)
            return data, tools
    except (OSError, ValueError):
        pass
    from .toolbox.mcp import tool_list
    tools = tool_list()
    _note_asks(tools)
    data = json.dumps(tools, ensure_ascii=False, separators=(",", ":"))
    try:
        os.makedirs(cache_dir(), exist_ok=True)
        for old in os.listdir(cache_dir()):
            if old.startswith("mcp-tools-") and old.endswith(".json"):
                try:
                    os.remove(os.path.join(cache_dir(), old))
                except OSError:
                    pass
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, path)
    except OSError:
        pass
    return data, tools


def _warm():
    from .toolbox.mcp import Backend
    return Backend()


def _call(backend, name: str, args: dict):
    return backend.call(name, args)


def _timeout(name: str, args: dict) -> float:
    return 900.0 if name in _ASKS else 300.0            # tools that wait for the user's Yes/No get longer


def server() -> mcp_rpc.Server:
    return mcp_rpc.Server(SERVER_INFO, INSTRUCTIONS, tools=cached_tool_list, warm=_warm, call=_call, timeout=_timeout)


def main() -> None:
    mcp_rpc.run(server())


if __name__ == "__main__":
    main()
