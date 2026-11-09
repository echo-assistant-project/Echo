"""OpenAI-compatible chat client for FreeLLMAPI (same endpoint the phone uses)."""
from __future__ import annotations

import collections
import http.client
import json
import queue
import re
import statistics
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from typing import Callable, Iterator
from urllib.parse import urlparse

# Hedged requests: FreeLLMAPI's free providers sometimes stall for 30 s+ before it fails over. When the first word
# hasn't arrived by the deadline, Echo asks again with another routing strategy and keeps whichever answers first.
# FreeLLMAPI still chooses the models; these are its documented strategies (auto = balanced, then fast, reliable).
HEDGE_ROUTES = ("auto", "auto:fast", "auto:reliable")
_first_word_s: "collections.deque[float]" = collections.deque(maxlen=20)   # recent winners' time to first word


def hedge_delay() -> float:
    """How long to wait for a first word before racing another route: 1.5x the recent typical wait, 2-5 s."""
    if len(_first_word_s) < 3:
        return 2.5
    return max(2.0, min(5.0, statistics.median(_first_word_s) * 1.5))


def _cancel(holder: dict) -> None:
    holder["cancel"] = True
    conn = holder.get("conn")
    if conn is not None:
        try:
            if conn.sock is not None:
                conn.sock.shutdown(2)
        except OSError:
            pass
        try:
            conn.close()
        except OSError:
            pass


class LlmError(Exception):
    pass


class ToolsUnsupported(LlmError):
    """The server refused a request that offered tools (function calling): use Echo's JSON action format instead."""


class ToolDelta(tuple):
    """Part of a tool call while it streams in: (index, id, name, arguments piece). Text pieces are plain str."""


class OutOfTokens(LlmError):
    """FreeLLMAPI's models have no tokens left for now (kind "quota": rate limit, daily quota, credits), or this
    conversation is too long for the model (kind "context")."""

    def __init__(self, message: str, kind: str = "quota"):
        super().__init__(message)
        self.kind = kind


_CONTEXT = re.compile(r"context[ _-]?(length|window|limit)|maximum context|prompt is too long|too many tokens in|"
                      r"reduce the length|input is too long|token limit exceeded|maximum (number of )?tokens", re.I)
_QUOTA = re.compile(r"quota|rate[ _-]?limit|too many requests|insufficient|credit|exhaust|out of tokens|no tokens|"
                    r"tokens? per (minute|day|hour)|usage limit|billing|limit reached|all (providers|keys|models)", re.I)


def not_running(base: str) -> str:
    """The plain message when nothing answers at the AI address (no raw [WinError …] text)."""
    return (f"FreeLLMAPI isn't running: nothing answers at {base}. Open FreeLLMAPI (Start menu), then ask again. "
            f"(If it is open, compare the address in its tray menu with Echo Settings → AI URL.)")


def classify(code: int, text: str) -> LlmError:
    """An error answer from FreeLLMAPI -> OutOfTokens when it means "no tokens left" or "too long", else LlmError."""
    detail = " ".join(str(text or "").split())[:200]
    if _CONTEXT.search(detail):
        return OutOfTokens("This conversation is too long for the AI model.", "context")
    if code in (402, 429) or _QUOTA.search(detail):
        return OutOfTokens("FreeLLMAPI's AI models are out of tokens for now (free limits reached).", "quota")
    if code:
        if code in (401, 403):
            return LlmError(f"FreeLLMAPI wants its key (it answered {code}): copy it from FreeLLMAPI's tray icon (starts with freellmapi-) "
                            "into Echo Settings → AI API key, then ask again.")
        return LlmError(f"FreeLLMAPI answered with an error (HTTP {code}). Please ask again in a moment.")
    # a provider's raw error ({'message': 'Provider error (…): stream interrupted', 'type': …}) is not for people
    m = re.search(r"""['"]message['"]\s*:\s*['"](.+?)['"]\s*[,}]""", detail)
    reason = re.sub(r"^Provider error\s*\(.*\)\s*:\s*", "", m.group(1) if m else detail).strip(" .")
    return AiHiccup("The AI service had a hiccup" + (f" ({reason[:80]})" if reason else "") + ". Please ask me again.")


class AiHiccup(LlmError):
    """A one-off failure inside a provider (a dropped stream): worth one quiet retry, not the "AI is down" fallback."""


class InFlight:
    """Questions still being answered. Echo works on several requests at once, and history only gets a question
    once its answer is done — so a follow-up asked meanwhile ("how tall is it?") is told what was asked just before."""

    def __init__(self):
        self._items: list = []
        self._lock = threading.Lock()

    @contextmanager
    def answering(self, text: str):
        token = (object(), str(text or ""))
        with self._lock:
            self._items.append(token)
        try:
            yield token
        finally:
            with self._lock:
                self._items.remove(token)

    def note(self, token) -> list:
        """A system message naming the other questions in flight (asked before this one), or nothing."""
        with self._lock:
            idx = self._items.index(token) if token in self._items else len(self._items)
            earlier = [t for _, t in self._items[:idx] if t.strip()][-3:]
        if not earlier:
            return []
        asked = "; ".join(f"“{t[:300]}”" for t in earlier)
        return [{"role": "system", "content": f"Asked just before this and still being answered: {asked}. "
                                              "The next message may refer to it (it, that, there, him, her)."}]


class ChatClient:
    def __init__(self, base_url: str, api_key: str = "", model: str = "auto"):
        parsed = urlparse(base_url.strip().rstrip("/"))
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.path != "/v1":
            raise LlmError("The AI URL must look like http://127.0.0.1:31415/v1")
        self.base = base_url.strip().rstrip("/")
        self.key = api_key.strip()
        self.model = model or "auto"
        # the routes raced for "auto": a preferred model first when the user picked one (Settings → Preferred AI
        # model), then FreeLLMAPI's own routing; never only a guess of ours
        self.routes = HEDGE_ROUTES
        self.history: list = []
        self.in_flight = InFlight()                # shared with a BrainRouter, like history
        self.last_route = ""                       # which provider/model answered last (FreeLLMAPI's X-Routed-Via)

    def clear(self) -> None:
        self.history.clear()

    def ask(self, user_text: str, system_prompt: str, remember: bool = True, timeout: float = 90,
            image_jpeg: bytes | None = None) -> str:
        content = user_text
        if image_jpeg is not None:
            from .vision import image_message
            content = image_message(user_text, image_jpeg)
        with self.in_flight.answering(user_text) as me:
            messages = [{"role": "system", "content": system_prompt}, *self.history, *self.in_flight.note(me),
                        {"role": "user", "content": content}]
            reply = self.complete(messages, timeout, has_image=image_jpeg is not None)
        if remember:
            self.history += [{"role": "user", "content": user_text}, {"role": "assistant", "content": reply}]
            del self.history[:-16]                 # in place: a BrainRouter shares this list
        return reply

    def ask_stream(self, user_text: str, system_prompt: str, on_text: Callable[[str], bool], remember: bool = True,
                   timeout: float = 90) -> str:
        """Like ask(), but on_text(delta) gets the reply piece by piece as FreeLLMAPI writes it (return False from
        on_text to stop early). Returns the whole reply."""
        parts = []
        with self.in_flight.answering(user_text) as me:
            messages = [{"role": "system", "content": system_prompt}, *self.history, *self.in_flight.note(me),
                        {"role": "user", "content": user_text}]
            for delta in self.stream(messages, timeout):
                parts.append(delta)
                if on_text(delta) is False:
                    break
        reply = "".join(parts)
        if remember:
            self.history += [{"role": "user", "content": user_text}, {"role": "assistant", "content": reply}]
            del self.history[:-16]                 # in place: a BrainRouter shares this list
        return reply

    def _connection(self, timeout: float):
        url = urlparse(self.base)
        if url.scheme == "https":
            import ssl
            return http.client.HTTPSConnection(url.hostname, url.port, timeout=timeout, context=ssl.create_default_context())
        return http.client.HTTPConnection(url.hostname, url.port, timeout=timeout)

    def stream(self, messages: list, timeout: float = 90) -> Iterator[str]:
        """Server-sent events from /chat/completions with "stream": true. A server that ignores streaming and sends
        one JSON reply still works (the whole text arrives as one piece). With FreeLLMAPI's "auto" model the request
        is hedged (see HEDGE_ROUTES); any other model or server gets exactly one request."""
        if self.model == "auto":
            return self._race(messages, timeout)
        return self._stream_one(messages, timeout, self.model, {})

    def turn(self, messages: list, tools: list, on_text: Callable[[str], None] = lambda t: None,
             timeout: float = 120) -> tuple:
        """One reply that may call tools: (text, [actions.Call]). on_text gets the text as it streams."""
        from .actions import Call
        source = self._race(messages, timeout, tools) if self.model == "auto" else \
            self._stream_one(messages, timeout, self.model, {}, tools)
        text, calls = [], {}
        try:
            for piece in source:
                if isinstance(piece, ToolDelta):
                    index, cid, name, args = piece
                    c = calls.setdefault(index, {"id": "", "name": "", "args": ""})
                    c["id"] = cid or c["id"]
                    c["name"] = name or c["name"]
                    c["args"] += args or ""
                else:
                    text.append(piece)
                    on_text(piece)
        except LlmError as e:
            if re.search(r"HTTP (400|404|422)\b", str(e)):
                raise ToolsUnsupported(str(e)) from None
            raise
        out = []
        for i, c in sorted(calls.items()):
            try:
                args = json.loads(c["args"] or "{}")
            except ValueError:
                args = {}
            out.append(Call(c["id"] or f"call{i}", c["name"], args if isinstance(args, dict) else {}))
        return "".join(text), [c for c in out if c.name]

    def _race(self, messages: list, timeout: float, tools: list | None = None) -> Iterator[str]:
        events: "queue.Queue" = queue.Queue()
        holders: list = []
        started = time.monotonic()

        def run(i: int, holder: dict) -> None:
            try:
                for piece in self._stream_one(messages, timeout, self.routes[i], holder, tools):
                    if holder.get("cancel"):
                        return
                    events.put(("text", i, piece))
                events.put(("end", i, None))
            except BaseException as e:            # reported to the race, never lost in a thread
                if not holder.get("cancel"):
                    events.put(("error", i, e))

        def launch() -> float:
            holder = {"cancel": False}
            holders.append(holder)
            threading.Thread(target=run, args=(len(holders) - 1, holder), daemon=True).start()
            return time.monotonic() + hedge_delay()

        next_at = launch()
        winner, failed, last_error = None, set(), None
        try:
            while True:
                if time.monotonic() - started > timeout:
                    raise LlmError(f"FreeLLMAPI stopped answering: no reply in {timeout:.0f} s")
                can_hedge = winner is None and len(holders) < len(self.routes)
                wait = (next_at - time.monotonic()) if can_hedge else 1.0
                try:
                    kind, i, value = events.get(timeout=max(0.01, wait))
                except queue.Empty:
                    if can_hedge and time.monotonic() >= next_at:
                        next_at = launch()
                    continue
                if winner is not None and i != winner:
                    continue
                if kind == "text":
                    if winner is None:
                        winner = i
                        self.last_route = holders[i].get("routed") or self.routes[i]
                        _first_word_s.append(time.monotonic() - started)
                        for j, h in enumerate(holders):
                            if j != i:
                                _cancel(h)
                    yield value
                elif kind == "end":
                    if winner is None:
                        self.last_route = holders[i].get("routed") or self.routes[i]
                    return
                else:                                 # error
                    if winner == i:
                        raise value
                    failed.add(i)
                    last_error = value
                    if len(holders) < len(self.routes):
                        next_at = launch()            # failed fast: race the next route now, don't wait
                    elif len(failed) == len(holders):
                        raise last_error
        finally:
            for h in holders:
                _cancel(h)

    def _stream_one(self, messages: list, timeout: float, model: str, holder: dict, tools: list | None = None) -> Iterator[str]:
        payload = {"model": model, "messages": messages, "stream": True}
        if tools:
            payload["tools"] = tools
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream, application/json"}
        if self.key:
            headers["Authorization"] = "Bearer " + self.key
        conn = self._connection(timeout)
        holder["conn"] = conn
        try:
            try:
                conn.request("POST", urlparse(self.base).path + "/chat/completions", body, headers)
                response = conn.getresponse()
            except (OSError, http.client.HTTPException) as e:
                raise LlmError(not_running(self.base)) from None
            if response.status >= 400:
                try:
                    detail = response.read(4000).decode("utf-8", "replace")
                except (OSError, http.client.HTTPException):
                    detail = ""
                raise classify(response.status, detail)
            holder["routed"] = response.getheader("X-Routed-Via") or ""
            content_type = (response.getheader("Content-Type") or "").lower()
            if "event-stream" not in content_type:
                if "json" not in content_type:
                    raise LlmError("FreeLLMAPI returned a non-JSON page; check that the URL ends in /v1.")
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise LlmError("FreeLLMAPI response exceeded the 2 MB limit.")
                for i, tc in enumerate(_tool_calls(raw) if tools else []):
                    yield ToolDelta((i, tc.get("id", ""), tc.get("function", {}).get("name", ""),
                                     _args_text(tc.get("function", {}).get("arguments"))))
                text = _content(raw, allow_empty=bool(tools))
                if text:
                    yield text
                return
            completed = False
            received = 0
            deadline = time.monotonic() + timeout
            try:
                while True:
                    if time.monotonic() >= deadline:
                        raise LlmError("FreeLLMAPI stream exceeded its time limit.")
                    if conn.sock is not None:
                        conn.sock.settimeout(max(0.1, deadline - time.monotonic()))
                    line = response.readline(65537)
                    if not line:
                        if not completed:
                            raise LlmError("FreeLLMAPI stream ended before completion.")
                        break
                    received += len(line)
                    if len(line) > 65536 or received > 2 * 1024 * 1024:
                        raise LlmError("FreeLLMAPI stream exceeded its size limit.")
                    line = line.strip()
                    if not line.startswith(b"data:"):
                        continue
                    data = line[5:].strip()
                    if data == b"[DONE]":
                        completed = True
                        break
                    try:
                        obj = json.loads(data)
                    except ValueError:
                        continue
                    if isinstance(obj, dict) and obj.get("error"):
                        raise classify(0, str(obj["error"]))
                    try:
                        delta = obj["choices"][0].get("delta") or obj["choices"][0].get("message") or {}
                        if obj["choices"][0].get("finish_reason") is not None:
                            completed = True
                    except (KeyError, IndexError, TypeError, AttributeError):
                        continue
                    for tc in (delta.get("tool_calls") or []) if isinstance(delta, dict) else []:
                        fn = tc.get("function") or {}
                        yield ToolDelta((tc.get("index", 0), tc.get("id", ""), fn.get("name", ""), _args_text(fn.get("arguments"))))
                    piece = delta.get("content") if isinstance(delta, dict) else None
                    if isinstance(piece, list):
                        piece = "".join(p.get("text", "") for p in piece if isinstance(p, dict))
                    if piece:
                        yield piece
            except (OSError, http.client.HTTPException) as e:
                raise LlmError(f"FreeLLMAPI stopped answering: {e}") from None
        finally:
            conn.close()

    def complete(self, messages: list, timeout: float = 90, has_image: bool = False) -> str:
        """One chat completion for a full message list (no history kept). Hedged like stream() for "auto"."""
        if self.model == "auto" and not has_image:
            return "".join(self._race(messages, timeout))
        body = json.dumps({"model": self.model, "messages": messages, "stream": False}).encode("utf-8")
        request = urllib.request.Request(self.base + "/chat/completions", data=body, method="POST",
                                         headers={"Content-Type": "application/json", "Accept": "application/json"})
        if self.key:
            request.add_header("Authorization", "Bearer " + self.key)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise LlmError("FreeLLMAPI response exceeded the 2 MB limit.")
        except urllib.error.HTTPError as e:
            try:
                detail = e.read(4000).decode("utf-8", "replace")
            except (OSError, AttributeError):
                detail = ""
            err = classify(e.code, detail)
            if has_image and e.code in (400, 404, 415, 422) and not isinstance(err, OutOfTokens):
                err = LlmError(f"FreeLLMAPI returned HTTP {e.code} (the AI model may not support images; pick a vision model in FreeLLMAPI).")
            raise err from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise LlmError(not_running(self.base)) from None
        if "json" not in content_type.lower():
            raise LlmError("FreeLLMAPI returned a non-JSON page; check that the URL ends in /v1.")
        return _content(raw)


def _unreachable(e: LlmError) -> bool:
    """The server isn't there (or stopped mid-way), as opposed to it answering with an error."""
    return str(e).startswith(("Can't reach", "FreeLLMAPI isn't running", "FreeLLMAPI stopped answering"))


def local_models(base_url: str, timeout: float = 2.0) -> list:
    """Model names an OpenAI-compatible local server (Ollama, LM Studio…) offers; [] when it isn't running."""
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/models", timeout=timeout) as r:
            data = json.loads(r.read())
        return [m["id"] for m in data.get("data", []) if isinstance(m, dict) and m.get("id")]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return []


class BrainRouter:
    """Echo's two brains, like the best JARVIS builds: the main AI (FreeLLMAPI) and a local one on this PC (Ollama or
    LM Studio at local_url). mode "auto" uses the main AI and switches to the local one by itself when the main one
    can't be reached (offline, server down); "local" uses only the local one (privacy mode); "cloud" only the main one.
    Same methods as ChatClient, one shared conversation, so switching mid-chat keeps the context."""

    RETRY_MAIN_AFTER = 60.0          # after the main AI failed, try it again only after this many seconds
    RETRY_MAIN_AFTER_QUOTA = 600.0   # out of tokens: free limits usually reset within minutes

    def __init__(self, main_url: str, main_key: str = "", local_url: str = "http://127.0.0.1:11434/v1",
                 local_model: str = "", mode: str = "auto", models=local_models, clock=None, preferred: str = ""):
        import time as _time
        self.main = ChatClient(main_url, main_key)
        if preferred and preferred.strip() and preferred.strip() != "auto":
            self.main.routes = (preferred.strip(), "auto", "auto:reliable")
        self.local_url, self.local_model, self.mode = local_url, local_model, mode
        self._models, self._clock = models, clock or _time.monotonic
        self._local: ChatClient | None = None
        self._main_down_until = 0.0
        self._why_down: LlmError | None = None
        self.history: list = []
        self.main.history = self.history
        self.in_flight = self.main.in_flight     # one conversation: both brains see the questions in flight
        self.last_used = ""                 # "main" | "local": which brain answered last

    # ---- which brain
    def _local_client(self) -> ChatClient | None:
        if self._local is None:
            model = self.local_model
            if not model:
                names = self._models(self.local_url)
                if not names:
                    return None
                model = names[0]
            self._local = ChatClient(self.local_url, "", model)
            self._local.history = self.history
            self._local.in_flight = self.in_flight
        return self._local

    def order(self) -> list:
        if self.mode == "local":
            return ["local"]
        if self.mode == "cloud":
            return ["main"]
        return ["local", "main"] if self._clock() < self._main_down_until else ["main", "local"]

    def describe(self) -> str:
        local = self._local.model if self._local else (self.local_model or "")
        names = {"main": "the main AI (FreeLLMAPI)", "local": f"the local AI on this PC{f' ({local})' if local else ''}"}
        now = names.get(self.last_used, "")
        mode = {"auto": "Auto: the main AI, and the local one when the main one is unreachable",
                "local": "Local only (private: nothing leaves this PC)", "cloud": "Main AI only"}[self.mode]
        return f"{mode}." + (f" Last answer came from {now}." if now else "")

    def _attempt(self, call):
        last: LlmError | None = None
        for which in self.order():
            client = self.main if which == "main" else self._local_client()
            if client is None:
                last = last or LlmError(f"No local AI is running at {self.local_url} (install Ollama and pull a model).")
                if which == "local" and self.mode == "auto" and self._clock() < self._main_down_until and \
                        isinstance(self._why_down, OutOfTokens):
                    last = self._why_down                # still out of tokens, and there's no local AI
                continue
            try:
                try:
                    result = call(client)
                except OutOfTokens as e:
                    if e.kind != "context" or len(self.history) <= 2:
                        raise
                    del self.history[:-2]            # too long: keep only the last exchange and try once more
                    result = call(client)
                self.last_used = which
                if which == "main":
                    self._main_down_until = 0.0
                return result
            except LlmError as e:
                if which == "main" and isinstance(e, OutOfTokens) and e.kind == "quota":
                    self._main_down_until = self._clock() + self.RETRY_MAIN_AFTER_QUOTA   # the local AI takes over
                    self._why_down = last = e
                    continue
                if which == "main" and _unreachable(e):
                    self._main_down_until = self._clock() + self.RETRY_MAIN_AFTER
                    last = e
                    continue
                if which == "local" and _unreachable(e):
                    self._local = None            # it may come back with another model; look again next time
                    last = e
                    continue
                raise
        raise last or LlmError("No AI is reachable.")

    # ---- ChatClient's interface
    def clear(self) -> None:
        self.history.clear()

    def ask(self, user_text: str, system_prompt: str, remember: bool = True, timeout: float = 90,
            image_jpeg: bytes | None = None) -> str:
        return self._attempt(lambda c: c.ask(user_text, system_prompt, remember, timeout, image_jpeg))

    def ask_stream(self, user_text: str, system_prompt: str, on_text: Callable[[str], bool], remember: bool = True,
                   timeout: float = 90) -> str:
        return self._attempt(lambda c: c.ask_stream(user_text, system_prompt, on_text, remember, timeout))

    def stream(self, messages: list, timeout: float = 90) -> Iterator[str]:
        return iter([self.complete(messages, timeout)])

    def complete(self, messages: list, timeout: float = 90, has_image: bool = False) -> str:
        return self._attempt(lambda c: c.complete(messages, timeout, has_image))

    def turn(self, messages: list, tools: list, on_text: Callable[[str], None] = lambda t: None, timeout: float = 120) -> tuple:
        return self._attempt(lambda c: c.turn(messages, tools, on_text, timeout))


def _args_text(args) -> str:
    """Tool arguments arrive as a JSON string piece (OpenAI) or, from some servers, as an object."""
    if args is None:
        return ""
    return args if isinstance(args, str) else json.dumps(args)


def _tool_calls(raw: bytes) -> list:
    try:
        return json.loads(raw)["choices"][0]["message"].get("tool_calls") or []
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        return []


def _content(raw: bytes, allow_empty: bool = False) -> str:
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("error") and not data.get("choices"):
            raise classify(0, str(data["error"]))        # an error sent with "200 OK"
        content = data["choices"][0]["message"].get("content") if allow_empty else data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise LlmError("FreeLLMAPI returned JSON in an unexpected format.") from None
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text")
    return str(content or "")
