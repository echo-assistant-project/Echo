"""The stdio side of Echo's two MCP servers (PC control and the toolbox): newline-delimited JSON-RPC 2.0, shared so both
behave the same and stay fast.

  * `initialize` is answered at once; the heavy loading (command pack, tool modules) runs on a background thread right
    after, so the AI app connects instantly and the first tool call usually finds everything ready.
  * `tools/list` is encoded once and reused.
  * Tool calls run on a thread pool: a slow web lookup never holds up a key press. Backends lock what must not overlap
    (keyboard, mouse, dialogs).
  * Every call has a time limit: if it's exceeded the AI gets a clear answer instead of waiting forever.
  * `notifications/cancelled` is honoured (no reply is sent for a cancelled request).
  * Bad input never kills the server; stdout carries nothing but protocol messages.

Standard library only.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from collections.abc import Callable

# Newest first. The answer echoes the client's version when we know it, otherwise our newest (the spec's negotiation).
PROTOCOLS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
MAX_TEXT = 200_000                      # characters per text block sent back; more is cut with a note
WORKERS = 8
EXIT_GRACE = 60.0                       # after stdin closes, how long running calls may still finish

PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL_ERROR = -32700, -32600, -32601, -32602, -32603


def text(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}]}


def error(s: str) -> dict:
    return {"content": [{"type": "text", "text": s}], "isError": True}


def _cap(result: object) -> dict:
    """A valid CallToolResult whatever the backend returned, with huge text cut down."""
    if isinstance(result, str):
        result = text(result)
    if not isinstance(result, dict) or not isinstance(result.get("content"), list):
        return error("Echo returned nothing usable for that call.")
    for block in result["content"]:
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str) \
                and len(block["text"]) > MAX_TEXT:
            extra = len(block["text"]) - MAX_TEXT
            block["text"] = block["text"][:MAX_TEXT] + f"\n… ({extra:,} more characters cut)"
    return result


class Server:
    """One MCP server on stdin/stdout.

    tools()            -> the tool list (list of dicts), that list as JSON text, or (JSON text, list); called once.
    warm()             -> the backend object tool calls use; runs on a background thread after `initialize`.
    call(b, name, args)-> a CallToolResult dict (or plain text) for one tool call; runs on a worker thread.
    timeout(name, args)-> seconds that call may take (None = no limit).
    """

    def __init__(self, info: dict, instructions: str, tools: Callable[[], object], warm: Callable[[], object],
                 call: Callable[[object, str, dict], object], timeout: Callable[[str, dict], float | None] = lambda n, a: 300.0,
                 thread_init: Callable[[], None] | None = None):
        self.info, self.instructions = info, instructions
        self._tools_fn, self._warm_fn, self._call_fn, self._timeout_fn = tools, warm, call, timeout
        self._tools_json: str | None = None
        self._names: set | None = None
        self._tools_lock = threading.Lock()
        self._backend: object = None
        self._warm_error: BaseException | None = None
        self._ready = threading.Event()
        self._warm_started = False
        self._warm_lock = threading.Lock()
        self._out = None
        self._out_lock = threading.Lock()
        self._pending: dict = {}                     # request id -> "running" | "done" | "cancelled"
        self._pending_lock = threading.Lock()
        self._thread_init = thread_init
        self._slots = threading.BoundedSemaphore(WORKERS)
        self._running = 0
        self._idle = threading.Condition()

    # ---------------------------------------------------------------------------------------------- warm-up
    def start_warm(self) -> None:
        with self._warm_lock:
            if self._warm_started:
                return
            self._warm_started = True
        threading.Thread(target=self._warm, name="mcp-warm", daemon=True).start()

    def _warm(self) -> None:
        try:
            self._tool_names()                       # the tool list first: tools/list is usually the next request
            self._backend = self._warm_fn()
        except BaseException as e:                   # reported on every call instead of crashing
            self._warm_error = e
        finally:
            self._ready.set()

    def backend(self, wait: float = 120.0) -> object:
        self.start_warm()
        if not self._ready.wait(wait):
            raise TimeoutError("Echo is still starting up; try again in a moment.")
        if self._warm_error is not None:
            raise RuntimeError(f"Echo couldn't start: {self._warm_error}")
        return self._backend

    # ---------------------------------------------------------------------------------------------- tool list
    def _tool_names(self) -> set:
        with self._tools_lock:
            if self._names is None:
                tools = self._tools_fn()
                if isinstance(tools, tuple):             # (JSON text, the same list already parsed)
                    self._tools_json, tools = tools
                elif isinstance(tools, str):
                    self._tools_json = tools
                    tools = json.loads(tools)
                else:
                    self._tools_json = json.dumps(tools, ensure_ascii=False, separators=(",", ":"))
                self._names = {t["name"] for t in tools}
            return self._names

    # ---------------------------------------------------------------------------------------------- output
    def _send(self, msg: object, raw: str | None = None) -> None:
        line = raw if raw is not None else json.dumps(msg, ensure_ascii=False, separators=(",", ":"))
        data = line.encode("utf-8", "replace") + b"\n"
        with self._out_lock:
            try:
                self._out.write(data)
                self._out.flush()
            except (OSError, ValueError):            # the client went away
                pass

    def _reply(self, mid: object, result: object) -> None:
        self._send({"jsonrpc": "2.0", "id": mid, "result": result})

    def _fail(self, mid: object, code: int, message: str) -> None:
        self._send({"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}})

    # ---------------------------------------------------------------------------------------------- dispatch
    def handle(self, msg: object) -> None:
        if isinstance(msg, dict) and "method" not in msg and "id" in msg and ("result" in msg or "error" in msg):
            return                                   # a reply to something we never asked: ignore
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" and "method" not in msg:
            self._fail(msg.get("id") if isinstance(msg, dict) else None, INVALID_REQUEST, "Invalid request")
            return
        method, mid = msg.get("method"), msg.get("id")
        params = msg.get("params")
        if params is None:
            params = {}
        if not isinstance(method, str):
            if "id" in msg and ("result" in msg or "error" in msg):
                return                               # a reply to something we never asked: ignore
            self._fail(mid, INVALID_REQUEST, "Invalid request")
            return
        if "id" not in msg:                          # notification
            if method == "notifications/cancelled" and isinstance(params, dict):
                key = json.dumps(params.get("requestId"))
                with self._pending_lock:
                    if self._pending.get(key) == "running":
                        self._pending[key] = "cancelled"
            elif method == "notifications/initialized":
                self.start_warm()
            return
        if not isinstance(params, dict):
            self._fail(mid, INVALID_PARAMS, "params must be an object")
            return
        try:
            if method == "initialize":
                asked = params.get("protocolVersion")
                self._reply(mid, {"protocolVersion": asked if asked in PROTOCOLS else PROTOCOLS[0],
                                  "capabilities": {"tools": {"listChanged": False}},
                                  "serverInfo": self.info, "instructions": self.instructions})
                self.start_warm()
            elif method == "ping":
                self._reply(mid, {})
            elif method == "tools/list":
                self._tool_names()
                self._send(None, '{"jsonrpc":"2.0","id":%s,"result":{"tools":%s}}' % (json.dumps(mid), self._tools_json))
            elif method == "tools/call":
                self._call(mid, params)
            elif method in ("resources/list", "resources/templates/list", "prompts/list"):
                key = {"resources/list": "resources", "resources/templates/list": "resourceTemplates"}.get(method, "prompts")
                self._reply(mid, {key: []})
            elif method == "logging/setLevel":
                self._reply(mid, {})
            else:
                self._fail(mid, METHOD_NOT_FOUND, f"Method not found: {method}")
        except Exception as e:                       # never let one message take the server down
            self._fail(mid, INTERNAL_ERROR, f"Echo hit an error: {e}")

    def _call(self, mid: object, params: dict) -> None:
        name, args = params.get("name"), params.get("arguments")
        if args is None:
            args = {}
        if not isinstance(name, str) or not isinstance(args, dict):
            self._fail(mid, INVALID_PARAMS, "tools/call needs a tool name and an arguments object")
            return
        if name not in self._tool_names():
            self._fail(mid, INVALID_PARAMS, f"Unknown tool: {name}")
            return
        key = json.dumps(mid)                        # ids may be numbers or strings; keep them apart
        with self._pending_lock:
            self._pending[key] = "running"
        limit = self._timeout_fn(name, args)
        timer = None
        if limit:
            timer = threading.Timer(limit, self._timed_out, (mid, key, name, limit))
            timer.daemon = True
            timer.start()
        with self._idle:
            self._running += 1
        threading.Thread(target=self._run, args=(mid, key, name, args, timer), name=f"mcp-call {name}", daemon=True).start()

    def _cancelled(self, key: str) -> bool:
        with self._pending_lock:
            if self._pending.get(key) == "cancelled":
                self._pending.pop(key, None)
                return True
            return False

    def _finish(self, key: str) -> bool:
        """Claim the right to answer request `key` (False if it was cancelled or already answered)."""
        with self._pending_lock:
            state = self._pending.pop(key, None)
            if state == "running":
                return True
            if state == "late":
                self._pending[key] = "late"          # keep the marker until the worker ends
            return False

    def _timed_out(self, mid: object, key: str, name: str, limit: float) -> None:
        if self._finish(key):
            with self._pending_lock:
                self._pending[key] = "late"
            self._reply(mid, error(f"{name} took longer than {limit:.0f} seconds, so Echo stopped waiting for it "
                                   f"(it may still finish on the PC)."))

    def _run(self, mid: object, key: str, name: str, args: dict, timer: threading.Timer | None) -> None:
        try:
            try:
                if self._thread_init:
                    self._thread_init()
                with self._slots:                    # at most WORKERS calls do work at once; the rest queue here
                    if self._cancelled(key):
                        return
                    result = _cap(self._call_fn(self.backend(), name, args))
            except Exception as e:                   # the AI gets the reason; the server keeps going
                result = error(f"Echo hit an error: {e}")
            if timer:
                timer.cancel()
            if self._finish(key):
                self._reply(mid, result)
        finally:
            with self._pending_lock:
                if self._pending.get(key) == "late":
                    self._pending.pop(key, None)
            with self._idle:
                self._running -= 1
                self._idle.notify_all()

    # ---------------------------------------------------------------------------------------------- main loop
    def serve(self, stdin=None, stdout=None) -> None:
        self._out = stdout or open(sys.stdout.fileno(), "wb", closefd=False)
        src = stdin or open(sys.stdin.fileno(), "rb", closefd=False)
        if stdout is None:
            sys.stdout = sys.stderr                  # stray prints must never corrupt the protocol stream
        for raw in src:
            line = raw.decode("utf-8", "replace").strip().lstrip("﻿")
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                self._fail(None, PARSE_ERROR, "Parse error")
                continue
            if isinstance(msg, list):                # JSON-RPC batch (allowed by 2025-03-26)
                if not msg:
                    self._fail(None, INVALID_REQUEST, "Empty batch")
                for m in msg:
                    self.handle(m)
            else:
                self.handle(msg)
        self.drain(EXIT_GRACE)

    def drain(self, grace: float) -> None:
        """stdin closed: let running calls answer (up to `grace` seconds), then stop."""
        end = time.monotonic() + grace
        with self._idle:
            while self._running and time.monotonic() < end:
                self._idle.wait(max(0.05, end - time.monotonic()))


def run(server: Server) -> None:
    """Serve until the client closes stdin, then exit at once (helper threads must not keep the process alive)."""
    try:
        server.serve()
    finally:
        try:
            sys.stderr.flush()
        finally:
            os._exit(0)
