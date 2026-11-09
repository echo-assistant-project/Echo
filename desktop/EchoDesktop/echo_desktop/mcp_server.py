"""Echo as an MCP server: lets any MCP-capable AI app (Claude Desktop, Claude Code, Cursor, VS Code, LM Studio…) use
your Windows PC through Echo — its 3,800+ PC commands, typing, the screen map, mouse and keyboard.

Run (stdio):   <python 3.12>\\python.exe <repo>\\desktop\\EchoDesktop\\echo_mcp.py
               (or: py -3.12 <repo>\\desktop\\EchoDesktop\\echo_mcp.py — no space after the dash)
Standard library only. Newline-delimited JSON-RPC 2.0 on stdin/stdout (mcp_rpc.py); nothing else is written to stdout.

This module is kept light so the server answers `initialize` at once; the PC side (mcp_pc.py: the command pack,
keyboard, mouse, screen) loads on a background thread straight after.

Safety, same rules as Echo itself:
  * risky steps (Send/Buy/Delete/Install-type clicks, Enter in chat apps, Alt+F4, power, deleting files, empty the
    Recycle Bin…) pop up a Windows confirmation on this PC — the AI can't answer it;
  * never types passwords/PINs/card numbers or into password fields;
  * the AI app's own window is never the target: keys go to the app you were using before you asked.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import threading

from . import mcp_rpc

SERVER_INFO = {"name": "echo-pc", "title": "Echo PC control", "version": "2.0"}
INSTRUCTIONS = (
    "Echo controls the user's Windows PC. Prefer, in order: run_command with a short natural phrase (use find_commands "
    "to discover the 3,800+ built-in commands: shortcuts, windows, apps, settings, Office/VS Code/browser keys, clipboard "
    "text tools, live answers…); then type_text / press_keys; then look + click for anything else. Keys and typing go to "
    "the app the user was using (not your own window) unless you pass window. Risky steps show a confirmation on the PC.")


# ------------------------------------------------------------------------------------------------ helpers
def ancestor_pids() -> set:
    """This process's parents up the tree (the AI app that launched us), so their windows are never targeted."""
    class PE(ctypes.Structure):
        _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
                    ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                    ("szExeFile", ctypes.c_wchar * 260)]
    k = ctypes.windll.kernel32
    k.CreateToolhelp32Snapshot.restype = wt.HANDLE
    snap = k.CreateToolhelp32Snapshot(0x2, 0)
    parents = {}
    try:
        e = PE()
        e.dwSize = ctypes.sizeof(PE)
        ok = k.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            parents[e.th32ProcessID] = e.th32ParentProcessID
            ok = k.Process32NextW(snap, ctypes.byref(e))
    finally:
        k.CloseHandle(snap)
    out, pid = set(), os.getpid()
    for _ in range(12):
        pid = parents.get(pid)
        if not pid or pid in out or pid in (0, 4):
            break
        out.add(pid)
    return out


_DIALOG = threading.Lock()              # one box on screen at a time, whichever call asks


def ask_yes_no(title: str, question: str) -> bool:
    import tkinter as tk
    from tkinter import messagebox
    with _DIALOG:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            return bool(messagebox.askyesno("Echo · " + title, question + "\n\n(Asked by an AI app through Echo.)", parent=root))
        finally:
            root.destroy()


def ask_text(question: str) -> str | None:
    import tkinter as tk
    from tkinter import simpledialog
    with _DIALOG:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            return simpledialog.askstring("Echo · the AI asks", question, parent=root)
        finally:
            root.destroy()


def dpi_aware() -> None:
    """Real screen pixels for look/click, on whichever thread runs the call."""
    try:
        ctypes.windll.user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        pass


# ------------------------------------------------------------------------------------------------ tools
TOOLS = [
    {"name": "find_commands", "title": "Find Echo commands",
     "description": "Search Echo's built-in PC commands (shortcuts, windows, apps, settings, Office/VS Code/browser keys, "
                    "clipboard text tools, folders, system info…). Returns example phrases for run_command.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string", "description": "what you want to do"},
                                                      "limit": {"type": "integer", "minimum": 1, "maximum": 50}},
                     "required": ["query"]},
     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
    {"name": "run_command", "title": "Run an Echo command",
     "description": "Do one thing on the PC with a short natural phrase, e.g. 'copy that', 'snap this window left', "
                    "'switch to chrome', 'new tab', 'format the document', 'turn on dark mode', 'open device manager', "
                    "'scroll down 5', 'undo 3 times', 'what is my ip address', 'volume up'.",
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"},
                                                      "window": {"type": "string", "description": "optional: part of the target window's title"}},
                     "required": ["text"]},
     "annotations": {"destructiveHint": True, "openWorldHint": False}},
    {"name": "type_text", "title": "Type text",
     "description": "Type text into the app the user is working in (pasted exactly; Enter is never pressed at the end).",
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}, "window": {"type": "string"}},
                     "required": ["text"]},
     "annotations": {"destructiveHint": False, "openWorldHint": False}},
    {"name": "press_keys", "title": "Press keys",
     "description": "Press a key or shortcut, e.g. 'enter', 'ctrl+s', 'alt+tab', 'ctrl+k ctrl+w' (sequence).",
     "inputSchema": {"type": "object", "properties": {"keys": {"type": "string"}, "times": {"type": "integer", "minimum": 1, "maximum": 50},
                                                      "window": {"type": "string"}}, "required": ["keys"]},
     "annotations": {"destructiveHint": True, "openWorldHint": False}},
    {"name": "look", "title": "Look at the screen",
     "description": "The active window's buttons/fields/links (e#) and all text on screen (t#) with positions, plus "
                    "optionally a screenshot. Use the ids with click.",
     "inputSchema": {"type": "object", "properties": {"image": {"type": "boolean", "description": "include a screenshot"},
                                                      "window": {"type": "string"}}},
     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
    {"name": "click", "title": "Click",
     "description": "Click an element from the latest look (target 'e3' / 't7') or a point (x, y in screen pixels).",
     "inputSchema": {"type": "object", "properties": {"target": {"type": "string"}, "x": {"type": "integer"}, "y": {"type": "integer"},
                                                      "button": {"type": "string", "enum": ["left", "right"]},
                                                      "double": {"type": "boolean"}}},
     "annotations": {"destructiveHint": True, "openWorldHint": False}},
    {"name": "scroll", "title": "Scroll",
     "description": "Scroll the mouse wheel where the pointer is.",
     "inputSchema": {"type": "object", "properties": {"direction": {"type": "string", "enum": ["up", "down"]},
                                                      "amount": {"type": "integer", "minimum": 1, "maximum": 20}}, "required": ["direction"]},
     "annotations": {"destructiveHint": False, "openWorldHint": False}},
    {"name": "list_windows", "title": "List open windows", "description": "Open app windows (title and program), front to back.",
     "inputSchema": {"type": "object", "properties": {}}, "annotations": {"readOnlyHint": True, "openWorldHint": False}},
    {"name": "focus_window", "title": "Bring a window to the front",
     "description": "Bring the first window whose title contains the text to the front (later typing goes there).",
     "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]},
     "annotations": {"destructiveHint": False, "openWorldHint": False}},
    {"name": "open_app", "title": "Open an app",
     "description": "Start an app by its Start-menu name (e.g. 'Notepad', 'Spotify') and wait for its window (slow apps get up to 90 s).",
     "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
     "annotations": {"destructiveHint": False, "openWorldHint": False}},
    {"name": "open_url", "title": "Open a web page", "description": "Open an https web page in the default browser.",
     "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
     "annotations": {"destructiveHint": False, "openWorldHint": True}},
    {"name": "ask_user", "title": "Ask the user",
     "description": "Show a small box on the PC asking the user a question and return their typed answer.",
     "inputSchema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]},
     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
    {"name": "speak", "title": "Say something out loud", "description": "Speak a short sentence with the Windows voice.",
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
]
TIMEOUTS = {"find_commands": 60, "list_windows": 30, "look": 90, "speak": 90, "open_app": 150, "ask_user": 1800}


def _warm():
    dpi_aware()
    from .mcp_pc import EchoServer
    return EchoServer()


def server() -> mcp_rpc.Server:
    return mcp_rpc.Server(SERVER_INFO, INSTRUCTIONS, tools=lambda: TOOLS, warm=_warm,
                          call=lambda backend, name, args: backend.call(name, args),
                          timeout=lambda name, args: TIMEOUTS.get(name, 600),   # 600: room for a confirmation box
                          thread_init=dpi_aware)


def main() -> None:
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        pass
    dpi_aware()
    mcp_rpc.run(server())


if __name__ == "__main__":
    main()
