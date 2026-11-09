"""The toolbox side of Echo's toolbox MCP server (the stdio front is mcp_toolbox.py): the tool list and running a call.
Loaded on a background thread right after the AI app connects.

Tools that change things show a Yes/No box on this PC first. Tools that need the running Echo app (lists, memories,
timers) aren't offered here.
"""
from __future__ import annotations

import threading

from . import Context, call, find, load, router
from .. import mcp_rpc

INTERNET = {
    "web_search": ("internet.search", "Search the web: titles, links and snippets.", {"query": {"type": "string"}}, ["query"]),
    "read_web_page": ("internet.read", "Read a public web page as plain text.", {"url": {"type": "string"}, "links": {"type": "boolean"}}, ["url"]),
    "get_json_api": ("internet.get_json", "GET a public JSON API.", {"url": {"type": "string"}}, ["url"]),
    "download_file": ("internet.download", "Download a file into Downloads (asks the user first; never opened).", {"url": {"type": "string"}}, ["url"]),
}


def ask_yes_no(title: str, text: str) -> bool:
    from ..mcp_server import ask_yes_no as ask
    return ask(title, text)


def context() -> Context:
    ws = {}
    try:
        from ..storage import Settings
        from .. import core
        for part in (Settings()["workspaces"] or "").split(";"):
            name, _, path = part.partition("=")
            if name.strip() and path.strip():
                ws[core.normalize(name)] = path.strip().strip('"')
    except Exception:
        pass
    return Context(confirm=ask_yes_no, workspaces=ws)


def tool_list() -> list:
    out = [{"name": "find_tools", "title": "Find the right tool", "description": "Search the 600+ tools by what you want to do.",
            "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 50}},
                            "required": ["query"]},
            "annotations": {"readOnlyHint": True}}]
    for t in sorted(load().values(), key=lambda t: (t.category, t.name)):
        if t.app:
            continue
        out.append({"name": t.name, "title": t.name.replace("_", " ").capitalize(), "description": f"[{t.category}] {t.description}",
                    "inputSchema": t.schema, "annotations": {"readOnlyHint": not t.ask, "destructiveHint": t.ask, "openWorldHint": t.net}})
    for name, (_, desc, props, req) in INTERNET.items():
        out.append({"name": name, "title": name.replace("_", " ").capitalize(), "description": "[web] " + desc,
                    "inputSchema": {"type": "object", "properties": props, "required": req},
                    "annotations": {"readOnlyHint": name != "download_file", "destructiveHint": name == "download_file",
                                    "openWorldHint": True}})
    return out


def run_tool(name: str, args: dict, ctx: Context) -> dict:
    if name == "find_tools":
        try:
            k = max(1, min(int(args.get("limit") or 12), 50))
        except (TypeError, ValueError):
            k = 12
        return mcp_rpc.text(find(str(args.get("query", "")), k).replace("toolbox.", ""))
    if name in INTERNET:
        from ..internet import InternetTools
        if name == "download_file" and not ask_yes_no("Download a file?", f"{args.get('url')}\n\nIt goes to Downloads and isn't opened."):
            return mcp_rpc.error("The user said no.")
        r = InternetTools().call(INTERNET[name][0], args)
    else:
        r = call(name, args, ctx)
    return {"content": [{"type": "text", "text": r}], "isError": r.startswith("ERROR")}


class Backend:
    """Everything a call needs, made once: the tools, the search index and the context."""

    def __init__(self):
        self.reg = load()
        router()                                        # the search index, so the first find_tools is instant
        self.ctx = context()
        self.input = threading.Lock()                   # keyboard/mouse/window tools take turns

    def call(self, name: str, args: dict) -> dict:
        t = self.reg.get(name)
        if t is not None and t.category == "control":
            with self.input:
                return run_tool(name, args, self.ctx)
        return run_tool(name, args, self.ctx)


def main() -> None:
    from ..mcp_toolbox import main as serve
    serve()


if __name__ == "__main__":
    main()
