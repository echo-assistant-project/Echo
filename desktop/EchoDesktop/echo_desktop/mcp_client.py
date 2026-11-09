"""MCP (Model Context Protocol) client, standard library only.

Two transports:
  * stdio: Echo starts the server as a child process (no console window) and talks newline-delimited JSON-RPC 2.0;
  * Streamable HTTP: remote servers at a URL (JSON or Server-Sent-Events replies, Mcp-Session-Id, bearer headers).
Handshake: initialize -> notifications/initialized -> tools/list (paged) -> tools/call.

Server entries (settings["mcp_servers"]):
  {"name": "files", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:/Users/me/Documents"]}
  {"name": "github", "url": "https://api.githubcopilot.com/mcp/", "headers": {"Authorization": "Bearer …"}}
  optional: "env", "cwd", "enabled": false, "trusted": true (run its non-read-only tools without asking)
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
from typing import Optional

PROTOCOL_VERSION = "2025-06-18"
CLIENT_INFO = {"name": "EchoDesktop", "version": "1.1"}
MAX_TEXT = 20_000


class McpError(Exception):
    pass


def tool_text(result: dict) -> str:
    """Flatten an MCP tools/call result to text (text parts joined; other parts named; structured content as JSON)."""
    parts = []
    for part in result.get("content") or []:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text":
            parts.append(str(part.get("text", "")))
        elif part.get("type") == "resource" and isinstance(part.get("resource"), dict) and "text" in part["resource"]:
            parts.append(str(part["resource"]["text"]))
        else:
            parts.append(f"[{part.get('type', 'data')} content]")
    if not parts and result.get("structuredContent") is not None:
        parts.append(json.dumps(result["structuredContent"], ensure_ascii=False)[:MAX_TEXT])
    text = "\n".join(p for p in parts if p).strip()
    if len(text) > MAX_TEXT:
        text = text[:MAX_TEXT] + "\n…[shortened]"
    if result.get("isError"):
        return "ERROR: " + (text or "the tool failed")
    return text or "(no output)"


def resolve_command(command: str) -> str:
    """'npx' -> 'C:\\Program Files\\nodejs\\npx.cmd' (Windows needs the real file; PATHEXT is honoured)."""
    if os.path.isabs(command) and os.path.exists(command):
        return command
    found = shutil.which(command)
    if found:
        return found
    raise McpError(f"“{command}” isn't installed or isn't on PATH.")


class _Client:
    """Shared JSON-RPC bookkeeping; subclasses implement _exchange (send a request, get its response)."""

    def __init__(self, name: str):
        self.name = name
        self.tools: list = []
        self.server_info: dict = {}
        self._next_id = 0
        self._lock = threading.Lock()
        self.started = False

    def _id(self) -> int:
        with self._lock:
            self._next_id += 1
            return self._next_id

    def _handshake(self, timeout: float) -> None:
        info = self._request("initialize", {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                                            "clientInfo": CLIENT_INFO}, timeout)
        if not isinstance(info, dict) or "protocolVersion" not in info:
            raise McpError(f"The {self.name} tool server didn't complete the MCP handshake.")
        self.server_info = info.get("serverInfo") or {}
        self._notify("notifications/initialized", {})
        tools, cursor = [], None
        for _ in range(20):                                          # tools/list is paged
            page = self._request("tools/list", {"cursor": cursor} if cursor else {}, timeout)
            tools += page.get("tools", [])
            cursor = page.get("nextCursor")
            if not cursor:
                break
        self.tools = tools
        self.started = True

    def call(self, tool: str, arguments: dict, timeout: float = 120) -> str:
        self.start()
        return tool_text(self._request("tools/call", {"name": tool, "arguments": arguments or {}}, timeout))

    # subclasses
    def start(self, timeout: float = 60) -> None:
        raise NotImplementedError

    def _request(self, method: str, params: dict, timeout: float):
        raise NotImplementedError

    def _notify(self, method: str, params: dict) -> None:
        raise NotImplementedError

    def close(self) -> None:
        self.started = False


class StdioMcpClient(_Client):
    def __init__(self, name: str, command: str, args: Optional[list] = None, env: Optional[dict] = None,
                 cwd: Optional[str] = None):
        super().__init__(name)
        self.command, self.args, self.env, self.cwd = command, list(args or []), env, cwd
        self.proc: Optional[subprocess.Popen] = None
        self._pending: dict = {}

    def start(self, timeout: float = 60) -> None:
        if self.proc and self.proc.poll() is None and self.started:
            return
        env = {**os.environ, **{k: str(v) for k, v in (self.env or {}).items()}}
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.proc = subprocess.Popen([resolve_command(self.command), *map(str, self.args)], stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=self.cwd or None, env=env,
                                         creationflags=flags, text=True, encoding="utf-8", errors="replace", bufsize=1)
        except OSError as e:
            raise McpError(f"Couldn't start the {self.name} tool server: {e}") from None
        threading.Thread(target=self._reader, daemon=True).start()
        self._handshake(timeout)

    def _reader(self) -> None:
        proc = self.proc
        try:
            self._read_lines(proc)
        except (ValueError, OSError):      # close() shut the pipe while we were reading
            pass
        for q in list(self._pending.values()):
            q.put({"error": {"message": "the tool server stopped"}})
        self._pending.clear()

    def _read_lines(self, proc) -> None:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue           # servers may log noise to stdout; ignore it
            if isinstance(msg, dict) and "id" in msg and ("result" in msg or "error" in msg):
                q = self._pending.pop(msg["id"], None)
                if q:
                    q.put(msg)
            elif isinstance(msg, dict) and "id" in msg and "method" in msg:
                # server -> client requests (ping, sampling, roots…): answer ping, decline the rest politely
                reply = {"jsonrpc": "2.0", "id": msg["id"]}
                reply.update({"result": {}} if msg["method"] == "ping" else
                             {"error": {"code": -32601, "message": "EchoDesktop doesn't support " + str(msg["method"])}})
                try:
                    self._send(reply)
                except McpError:
                    pass

    def _send(self, msg: dict) -> None:
        if not self.proc or self.proc.poll() is not None:
            raise McpError(f"The {self.name} tool server isn't running.")
        try:
            self.proc.stdin.write(json.dumps(msg) + "\n")
            self.proc.stdin.flush()
        except OSError:
            raise McpError(f"Lost the connection to the {self.name} tool server.") from None

    def _notify(self, method: str, params: dict) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _request(self, method: str, params: dict, timeout: float):
        rid = self._id()
        q: "queue.Queue" = queue.Queue()
        self._pending[rid] = q
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        try:
            msg = q.get(timeout=timeout)
        except queue.Empty:
            self._pending.pop(rid, None)
            raise McpError(f"The {self.name} tool server took too long ({method}).") from None
        if "error" in msg:
            raise McpError(f"{self.name}: {msg['error'].get('message', 'error')}")
        return msg.get("result") or {}

    def close(self) -> None:
        super().close()
        proc, self.proc = self.proc, None
        if proc is None:
            return
        if proc.poll() is None:
            try:
                proc.stdin.close()
                proc.wait(timeout=3)
            except Exception:
                proc.kill()
                try:
                    proc.wait(timeout=3)
                except Exception:
                    pass
        for pipe in (proc.stdin, proc.stdout):    # closed even when the server had already exited (no leaked handles)
            try:
                if pipe:
                    pipe.close()
            except Exception:
                pass


class HttpMcpClient(_Client):
    """Streamable HTTP transport (MCP 2025-03-26+): POST each message; the reply is JSON or an SSE stream."""

    def __init__(self, name: str, url: str, headers: Optional[dict] = None):
        super().__init__(name)
        if not url.lower().startswith(("https://", "http://127.0.0.1", "http://localhost")):
            raise McpError(f"{name}: remote MCP servers must use https (plain http only on this PC).")
        self.url, self.headers = url, {k: str(v) for k, v in (headers or {}).items()}
        self.session: Optional[str] = None

    def start(self, timeout: float = 60) -> None:
        if not self.started:
            self._handshake(timeout)

    def _post(self, msg: dict, timeout: float):
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                   "MCP-Protocol-Version": PROTOCOL_VERSION, **self.headers}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        req = urllib.request.Request(self.url, data=json.dumps(msg).encode("utf-8"), headers=headers, method="POST")
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            hint = " (check the API key/token)" if e.code in (401, 403) else ""
            raise McpError(f"{self.name}: HTTP {e.code}{hint}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise McpError(f"{self.name}: can't reach {self.url} ({getattr(e, 'reason', e)})") from None
        self.session = resp.headers.get("Mcp-Session-Id") or self.session
        return resp

    def _notify(self, method: str, params: dict) -> None:
        with self._post({"jsonrpc": "2.0", "method": method, "params": params}, 30) as r:
            r.read()

    def _request(self, method: str, params: dict, timeout: float):
        rid = self._id()
        with self._post({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}, timeout) as resp:
            kind = (resp.headers.get("Content-Type") or "").lower()
            msg = None
            if "text/event-stream" in kind:
                data = []
                for raw in resp:
                    line = raw.decode("utf-8", "replace").rstrip("\r\n")
                    if line.startswith("data:"):
                        data.append(line[5:].lstrip())
                    elif not line and data:
                        try:
                            candidate = json.loads("\n".join(data))
                        except ValueError:
                            candidate = None
                        data = []
                        if isinstance(candidate, dict) and candidate.get("id") == rid:
                            msg = candidate
                            break
            else:
                body = resp.read()
                try:
                    parsed = json.loads(body) if body else {}
                except ValueError:
                    raise McpError(f"{self.name}: the server sent something that isn't JSON.") from None
                if isinstance(parsed, list):
                    parsed = next((m for m in parsed if isinstance(m, dict) and m.get("id") == rid), {})
                msg = parsed
        if not msg:
            raise McpError(f"{self.name}: no reply to {method}.")
        if "error" in msg:
            raise McpError(f"{self.name}: {msg['error'].get('message', 'error')}")
        return msg.get("result") or {}

    def close(self) -> None:
        if self.session:
            try:
                headers = {"Mcp-Session-Id": self.session, **self.headers}
                urllib.request.urlopen(urllib.request.Request(self.url, headers=headers, method="DELETE"), timeout=5).close()
            except Exception:
                pass
        self.session = None
        super().close()


def make_client(s: dict) -> _Client:
    if s.get("url"):
        return HttpMcpClient(s["name"], s["url"], s.get("headers"))
    return StdioMcpClient(s["name"], s["command"], s.get("args"), s.get("env"), s.get("cwd"))


class McpHub:
    """All configured servers; tools are addressed as "<server>.<tool>"."""

    def __init__(self, servers: list):
        self.clients: dict = {}
        self.trusted: set = set()
        self.errors: dict = {}
        for s in servers or []:
            if isinstance(s, dict) and s.get("name") and (s.get("command") or s.get("url")) and s.get("enabled", True):
                try:
                    self.clients[s["name"]] = make_client(s)
                except McpError as e:
                    self.errors[s["name"]] = str(e)
                if s.get("trusted"):
                    self.trusted.add(s["name"])

    def start(self) -> list:
        """Start every server (in parallel); returns a list of error strings for those that failed."""
        threads = []

        def go(name, c):
            try:
                c.start()
            except McpError as e:
                self.errors[name] = str(e)
        for name, c in self.clients.items():
            t = threading.Thread(target=go, args=(name, c), daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join(90)
        return list(self.errors.values())

    def tools(self) -> list:
        out = []
        for name, c in self.clients.items():
            for t in c.tools:
                out.append({"name": f"{name}.{t.get('name')}", "description": t.get("description", ""),
                            "inputSchema": t.get("inputSchema", {}), "annotations": t.get("annotations") or {},
                            "server": name})
        return out

    def call(self, qualified: str, arguments: dict) -> str:
        server, _, tool = qualified.partition(".")
        client = self.clients.get(server)
        if not client or not tool:
            raise McpError(f"Unknown tool {qualified!r}.")
        return client.call(tool, arguments)

    def close(self) -> None:
        for c in self.clients.values():
            c.close()
