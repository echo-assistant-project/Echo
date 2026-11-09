"""Echo's own internet access: search the web, read pages, call free public APIs, download files.

Used by the Command Pack's "net" kind (weather, news, word lookups, package versions, site checks…) and by the AI's
internet tools (search / read / get / download), so the AI can look up whatever it needs to answer you.

Safety, enforced here rather than trusted to the AI:
- Only http/https. Every connection is checked AFTER it is made: if the far end is a private, loopback, link-local or
  otherwise non-public address the request is dropped. That stops a web page (or a confused AI) from reaching Echo's
  own local services, your router or other machines at home, including through redirects and DNS tricks.
- No system proxy, size and time limits on every response, no cookies, no logins.
- Downloads go to your Downloads folder only, are marked as coming from the internet (Windows then warns before
  running them), are never opened or run by Echo, and the caller asks you first.
- Everything fetched is untrusted data. The AI is told never to follow instructions found in it.
"""
from __future__ import annotations

import html
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Optional
from xml.etree import ElementTree

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) EchoDesktop/1.0 (personal assistant)"
TIMEOUT = 15
MAX_BYTES = 3_000_000
MAX_DOWNLOAD = 500 * 1024 * 1024


class NetError(Exception):
    """A request that failed or was refused; the message is fit to say aloud."""


def reach_reason(reason) -> str:
    """Why a site couldn't be reached, in words fit to say aloud (no Windows error numbers)."""
    if isinstance(reason, socket.gaierror):
        return "I couldn't find that site. Check the name, or the internet connection."
    if isinstance(reason, (socket.timeout, TimeoutError)) or "timed out" in str(reason):
        return "The site took too long to answer."
    if isinstance(reason, ConnectionRefusedError):
        return "That site refused the connection."
    if isinstance(reason, (ConnectionResetError, ConnectionAbortedError)) or "forcibly closed" in str(reason):
        return "The site closed the connection. Try again in a moment."
    if isinstance(reason, ssl.SSLError):
        return "The secure connection to that site failed."
    if isinstance(reason, http.client.HTTPException):
        return "The site sent a broken reply."
    return "I couldn't reach the site right now."


# ------------------------------------------------------------------------------------------------ address guard
def public_ip(addr: str) -> bool:
    """True only for globally routable unicast addresses (IPv4-mapped IPv6 is unwrapped first)."""
    try:
        ip = ipaddress.ip_address(addr.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast and not ip.is_reserved


PRIVATE = "That address is on a private or local network, so I won't connect to it."


def check_host(host: str, port: int = 443) -> None:
    """Refuse before connecting when the name only leads to non-public addresses."""
    try:
        addrs = {i[4][0] for i in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    except socket.gaierror:
        return                                    # let the real connect report "couldn't find that site"
    if addrs and not any(public_ip(a) for a in addrs):
        raise NetError(PRIVATE)


def _check_peer(sock) -> None:
    peer = sock.getpeername()[0]
    if not public_ip(peer):
        sock.close()
        raise NetError(PRIVATE)


class _GuardedHTTP(http.client.HTTPConnection):
    def connect(self):
        check_host(self.host, self.port)
        super().connect()
        _check_peer(self.sock)                    # the address actually connected to (no DNS-rebinding window)


class _GuardedHTTPS(http.client.HTTPSConnection):
    def connect(self):
        # connect the plain socket, check where it went, then start TLS (so no bytes reach a local service)
        check_host(self.host, self.port)
        http.client.HTTPConnection.connect(self)
        _check_peer(self.sock)
        server = self._tunnel_host or self.host
        self.sock = self._context.wrap_socket(self.sock, server_hostname=server)


_warmed: set = set()


def _warm_windows_roots(host: str) -> bool:
    """Windows downloads missing root certificates on demand, but only for its own HTTP stack, not Python's. When a
    certificate can't be verified, let Windows itself fetch the page headers once (installing the root it trusts),
    then the caller retries with full verification. Never disables verification."""
    if os.name != "nt" or host in _warmed or not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", host or ""):
        return False
    _warmed.add(host)
    import subprocess
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                        f"try {{ Invoke-WebRequest -UseBasicParsing -Method Head -TimeoutSec 10 -Uri 'https://{host}/' | Out-Null }} catch {{}}"],
                       capture_output=True, timeout=25, creationflags=0x08000000)
    except (OSError, subprocess.SubprocessError):
        return False
    return True


class _HTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req):
        return self.do_open(_GuardedHTTP, req)


class _HTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self):
        super().__init__(context=ssl.create_default_context())

    def https_open(self, req):
        return self.do_open(_GuardedHTTPS, req, context=self._context)


class _Redirects(urllib.request.HTTPRedirectHandler):
    max_redirections = 6

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme.lower() not in ("http", "https"):
            raise NetError("The site tried to send me somewhere that isn't a web page.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _opener():
    # no ProxyHandler entries: a proxy would hide where we really connect
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _HTTPHandler(), _HTTPSHandler(), _Redirects())


def clean_url(url: str) -> str:
    """Spoken or typed address -> full http(s) URL. Raises NetError for anything else."""
    u = (url or "").strip().strip("<>\"'")
    u = re.sub(r"\s+dot\s+", ".", u, flags=re.I).replace(" ", "")
    if not re.match(r"^[a-z][a-z0-9+.-]*://", u, re.I):
        u = "https://" + u
    parts = urllib.parse.urlsplit(u)
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise NetError("That isn't a web address I can open.")
    if parts.username or parts.password:
        raise NetError("I don't send passwords inside web addresses.")
    if parts.hostname.lower() in ("localhost",) or parts.hostname.lower().endswith((".local", ".localhost", ".internal", ".lan")):
        raise NetError("That address is on a private or local network, so I won't connect to it.")
    if "." not in parts.hostname and ":" not in parts.hostname:
        raise NetError(f"“{parts.hostname}” isn't a full web address. Say it like example dot com.")
    return urllib.parse.urlunsplit(parts)


# ------------------------------------------------------------------------------------------------ requests
@dataclass
class Response:
    url: str
    status: int
    headers: dict
    body: bytes
    elapsed: float = 0.0

    @property
    def content_type(self) -> str:
        return (self.headers.get("content-type") or "").split(";")[0].strip().lower()

    def text(self) -> str:
        m = re.search(r"charset=([\w-]+)", self.headers.get("content-type") or "", re.I)
        enc = m.group(1) if m else "utf-8"
        try:
            return self.body.decode(enc, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")

    def json(self):
        try:
            return json.loads(self.body.decode("utf-8", errors="replace"))
        except ValueError:
            raise NetError("The service sent back something I couldn't read.")


_cache: dict = {}
_cache_lock = threading.Lock()


def request(url: str, method: str = "GET", headers: Optional[dict] = None, data: Optional[bytes] = None,
            max_bytes: int = MAX_BYTES, timeout: float = TIMEOUT, cache_seconds: float = 0) -> Response:
    try:
        return _request(url, method, headers, data, max_bytes, timeout, cache_seconds)
    except NetError as e:
        host = urllib.parse.urlsplit(clean_url(url)).hostname or ""
        if "CERTIFICATE_VERIFY_FAILED" in str(e) and _warm_windows_roots(host):
            return _request(url, method, headers, data, max_bytes, timeout, cache_seconds)
        raise


def _request(url: str, method: str, headers: Optional[dict], data: Optional[bytes], max_bytes: int, timeout: float,
             cache_seconds: float) -> Response:
    url = clean_url(url)
    key = (method, url)
    if cache_seconds and method == "GET":
        with _cache_lock:
            hit = _cache.get(key)
        if hit and time.monotonic() - hit[0] < cache_seconds:
            return hit[1]
    h = {"User-Agent": USER_AGENT, "Accept": "*/*", "Accept-Language": "en-IN,en;q=0.9"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    started = time.monotonic()
    try:
        with _opener().open(req, timeout=timeout) as r:
            body = r.read(max_bytes + 1) if method != "HEAD" else b""
            status, final, hdrs = r.status, r.geturl(), {k.lower(): v for k, v in r.headers.items()}
    except urllib.error.HTTPError as e:
        body = e.read(min(max_bytes, 200_000)) if e.fp else b""
        status, final, hdrs = e.code, e.geturl() or url, {k.lower(): v for k, v in (e.headers or {}).items()}
    except NetError:
        raise
    except urllib.error.URLError as e:
        reason = e.reason
        if isinstance(reason, NetError):
            raise reason
        if isinstance(reason, socket.timeout) or "timed out" in str(reason):
            raise NetError("The site took too long to answer.")
        if isinstance(reason, socket.gaierror):
            raise NetError("I couldn't find that site. Check the name, or the internet connection.")
        if isinstance(reason, ssl.SSLCertVerificationError):
            raise NetError(f"The site's security certificate couldn't be verified ({reason.verify_message}), so I didn't trust it.")
        raise NetError(reach_reason(reason))
    except (socket.timeout, TimeoutError):
        raise NetError("The site took too long to answer.")
    except (OSError, http.client.HTTPException) as e:
        raise NetError(reach_reason(e))
    if len(body) > max_bytes:
        body = body[:max_bytes]
    resp = Response(final, status, hdrs, body, time.monotonic() - started)
    if cache_seconds and method == "GET" and status == 200:
        with _cache_lock:
            if len(_cache) > 200:
                _cache.clear()
            _cache[key] = (time.monotonic(), resp)
    return resp


def get_json(url: str, cache_seconds: float = 120, headers: Optional[dict] = None):
    r = request(url, headers={"Accept": "application/json", **(headers or {})}, cache_seconds=cache_seconds)
    if r.status == 404:
        raise NetError("not found")
    if r.status == 429:
        raise NetError("That service is busy right now (too many requests). Try again in a minute.")
    if r.status >= 400:
        raise NetError(f"The service answered with an error ({r.status}).")
    return r.json()


def q(text: str) -> str:
    return urllib.parse.quote(text.strip(), safe="")


# ------------------------------------------------------------------------------------------------ readable text
class _Reader(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template", "iframe", "head", "nav", "footer", "form", "button", "select"}
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "blockquote", "pre",
             "dd", "dt", "table", "ul", "ol", "header", "main", "figcaption"}

    def __init__(self, base: str = "", want_links: bool = False):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip, self.title, self._in_title = [], 0, "", False
        self.base, self.want_links, self.links, self._href, self._link_text = base, want_links, [], None, []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag == "title":
            self._in_title = True
        if tag in self.BLOCK:
            self.parts.append("\n")
        if tag == "a" and self.want_links:
            href = dict(attrs).get("href")
            if href and not href.startswith(("#", "javascript:", "mailto:")):
                self._href, self._link_text = urllib.parse.urljoin(self.base, href), []

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag == "title":
            self._in_title = False
        if tag in self.BLOCK:
            self.parts.append("\n")
        if tag == "a" and self._href:
            label = " ".join("".join(self._link_text).split())
            if label:
                self.links.append((label[:80], self._href))
            self._href = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
            return
        if self.skip:
            return
        self.parts.append(data)
        if self._href is not None:
            self._link_text.append(data)


def readable(page_html: str, base: str = "", want_links: bool = False) -> tuple:
    """(title, text, links) from an HTML page: scripts, menus and footers dropped, whitespace tidied."""
    r = _Reader(base, want_links)
    try:
        r.feed(page_html)
        r.close()
    except Exception:
        pass
    lines = [" ".join(l.split()) for l in "".join(r.parts).splitlines()]
    text = "\n".join(l for l in lines if len(l) > 1)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return " ".join(r.title.split()), text, r.links


def first_sentences(text: str, n: int = 2, limit: int = 420) -> str:
    text = re.sub(r"\s*\([^()]*\)", "", text or "").strip()     # drop pronunciations / parentheticals
    text = re.sub(r"\s+([,.;:!?])", r"\1", re.sub(r"\s+", " ", text))   # and the gaps they leave ("Station  is", "x ,")
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9“\"])", text)
    out = " ".join(parts[:n]).strip()
    return out if len(out) <= limit else out[:limit].rsplit(" ", 1)[0] + "…"


def read_page(url: str, max_chars: int = 6000, want_links: bool = False) -> dict:
    r = request(url)
    if r.status >= 400:
        raise NetError(f"The page answered with an error ({r.status}).")
    ctype = r.content_type
    if "json" in ctype:
        return {"url": r.url, "title": "", "text": json.dumps(r.json(), ensure_ascii=False, indent=1)[:max_chars], "links": []}
    if ctype.startswith("text/") and "html" not in ctype:
        return {"url": r.url, "title": "", "text": r.text()[:max_chars], "links": []}
    if "html" not in ctype and ctype:
        return {"url": r.url, "title": "", "text": f"(This is a {ctype} file, {len(r.body)} bytes. Download it to use it.)", "links": []}
    title, text, links = readable(r.text(), r.url, want_links)
    return {"url": r.url, "title": title, "text": text[:max_chars], "links": links[:60]}


# ------------------------------------------------------------------------------------------------ web search
@dataclass
class Hit:
    title: str
    url: str
    snippet: str = ""


def _ddg_target(href: str) -> str:
    href = html.unescape(href)
    if href.startswith("//"):
        href = "https:" + href
    parts = urllib.parse.urlsplit(href)
    if parts.netloc.endswith("duckduckgo.com") and parts.path.startswith("/l/"):
        return urllib.parse.parse_qs(parts.query).get("uddg", [href])[0]
    return href


def parse_ddg(page: str) -> list:
    hits = []
    for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>(.*?)(?=<a[^>]+class="result__a"|\Z)', page, re.S):
        url = _ddg_target(m.group(1))
        if "duckduckgo.com/y.js" in url or not url.startswith("http"):
            continue                                            # ads
        title = html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        sm = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', m.group(3), re.S)
        snippet = html.unescape(re.sub(r"<[^>]+>", "", sm.group(1))).strip() if sm else ""
        hits.append(Hit(" ".join(title.split()), url, " ".join(snippet.split())))
    return hits


def parse_rss_items(xml_text: str, limit: int = 10) -> list:
    """[(title, link, description)] from RSS 2.0 or Atom."""
    try:
        root = ElementTree.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    except ElementTree.ParseError:
        return []
    out = []
    for item in root.iter():
        tag = item.tag.rsplit("}", 1)[-1]
        if tag not in ("item", "entry"):
            continue
        get = {c.tag.rsplit("}", 1)[-1]: c for c in item}
        title = (get.get("title").text if get.get("title") is not None else "") or ""
        link_el = get.get("link")
        link = (link_el.text or link_el.get("href") or "") if link_el is not None else ""
        desc_el = get.get("description") or get.get("summary")
        desc = re.sub(r"<[^>]+>", " ", html.unescape(desc_el.text or "")) if desc_el is not None else ""
        out.append((" ".join(title.split()), link.strip(), " ".join(desc.split())))
        if len(out) >= limit:
            break
    return out


def parse_ddg_lite(page: str) -> list:
    hits = []
    for m in re.finditer(r"<a[^>]+href=\"([^\"]+)\"[^>]+class=['\"]result-link['\"][^>]*>(.*?)</a>(.*?)(?=class=['\"]result-link|\Z)", page, re.S):
        url = _ddg_target(m.group(1))
        if not url.startswith("http") or "duckduckgo.com/y.js" in url:
            continue
        sm = re.search(r"class=['\"]result-snippet['\"][^>]*>(.*?)</td>", m.group(3), re.S)
        snippet = html.unescape(re.sub(r"<[^>]+>", "", sm.group(1))).strip() if sm else ""
        hits.append(Hit(" ".join(html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).split()), url, " ".join(snippet.split())))
    return hits


def search(query: str, n: int = 6) -> list:
    """Web results [Hit]: DuckDuckGo (HTML, then Lite), Bing's RSS feed, then Wikipedia as a last resort."""
    query = query.strip()
    if not query:
        return []
    form = {"Content-Type": "application/x-www-form-urlencoded", "Referer": "https://html.duckduckgo.com/"}
    for url, data, parse in (("https://html.duckduckgo.com/html/", urllib.parse.urlencode({"q": query}).encode(), parse_ddg),
                             ("https://lite.duckduckgo.com/lite/?q=" + q(query), None, parse_ddg_lite)):
        try:
            r = request(url, method="POST" if data else "GET", data=data, headers=form if data else None)
            hits = parse(r.text()) if r.status == 200 else []
            if hits:
                return hits[:n]
        except NetError:
            pass
    try:
        r = request("https://www.bing.com/search?format=rss&q=" + q(query), cache_seconds=300)
        hits = [Hit(t, l, d) for t, l, d in parse_rss_items(r.text(), n) if l.startswith("http")]
        if hits:
            return hits[:n]
    except NetError:
        pass
    data = get_json("https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=%d&srsearch=%s" % (n, q(query)))
    return [Hit(h["title"], "https://en.wikipedia.org/wiki/" + q(h["title"].replace(" ", "_")),
                html.unescape(re.sub(r"<[^>]+>", "", h.get("snippet", "")))) for h in data.get("query", {}).get("search", [])]


# ------------------------------------------------------------------------------------------------ downloads
def downloads_dir() -> Path:
    """The user's real Downloads folder (it can be moved to another drive), else %USERPROFILE%\\Downloads."""
    if os.name == "nt":
        try:
            import ctypes
            import uuid

            class GUID(ctypes.Structure):
                _fields_ = [("data", ctypes.c_ubyte * 16)]
            folder_id = GUID()
            folder_id.data[:] = list(uuid.UUID("374DE290-123F-4565-9164-39C4925E467B").bytes_le)
            path = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, None, ctypes.byref(path)) == 0:
                try:
                    return Path(path.value)
                finally:
                    ctypes.windll.ole32.CoTaskMemFree(path)
        except (OSError, AttributeError, ValueError):
            pass
    return Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Downloads"


def safe_filename(url: str, headers: dict) -> str:
    cd = headers.get("content-disposition") or ""
    m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd, re.I)
    name = urllib.parse.unquote(m.group(1)) if m else urllib.parse.unquote(Path(urllib.parse.urlsplit(url).path).name)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .") or "download"
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    stem = stem[:80] or "download"
    if not ext:
        guess = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png", "text/html": "html", "application/zip": "zip",
                 "text/plain": "txt", "application/json": "json"}.get((headers.get("content-type") or "").split(";")[0].strip().lower())
        ext = guess or "bin"
    return f"{stem}.{ext[:10]}"


def download(url: str, folder: Optional[Path] = None, progress: Callable[[int], None] = lambda n: None,
             cancelled: Callable[[], bool] = lambda: False) -> Path:
    """Save url into Downloads (never overwrites, never runs it). Marks the file as from the internet."""
    url = clean_url(url)
    folder = folder or downloads_dir()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        r = _opener().open(req, timeout=TIMEOUT)
    except urllib.error.HTTPError as e:
        raise NetError(f"The site answered with an error ({e.code}).")
    except urllib.error.URLError as e:
        if isinstance(e.reason, NetError):
            raise e.reason
        raise NetError(reach_reason(e.reason))
    with r:
        headers = {k.lower(): v for k, v in r.headers.items()}
        size = int(headers.get("content-length") or 0)
        if size > MAX_DOWNLOAD:
            raise NetError(f"That file is {size // (1024 * 1024)} MB, more than I download ({MAX_DOWNLOAD // (1024 * 1024)} MB).")
        name = safe_filename(r.geturl(), headers)
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / name
        i = 1
        while target.exists():
            target = folder / f"{Path(name).stem} ({i}){Path(name).suffix}"
            i += 1
        part = target.with_name(target.name + ".part")
        got = 0
        try:
            with open(part, "wb") as f:
                while True:
                    if cancelled():
                        raise NetError("Download stopped.")
                    chunk = r.read(256 * 1024)
                    if not chunk:
                        break
                    got += len(chunk)
                    if got > MAX_DOWNLOAD:
                        raise NetError("The file is bigger than I download, so I stopped.")
                    f.write(chunk)
                    progress(got)
            os.replace(part, target)
        except BaseException:
            try:
                part.unlink()
            except OSError:
                pass
            raise
    mark_from_internet(target, url)
    return target


def mark_from_internet(path: Path, url: str) -> None:
    """Mark of the Web: Windows (SmartScreen, Office) treats the file as downloaded from the internet."""
    if os.name != "nt":
        return
    try:
        with open(f"{path}:Zone.Identifier", "w", encoding="utf-8") as f:
            f.write(f"[ZoneTransfer]\r\nZoneId=3\r\nHostUrl={url}\r\n")
    except OSError:
        pass


# ------------------------------------------------------------------------------------------------ places & weather
WMO = {0: "clear sky", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "freezing fog",
       51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 56: "freezing drizzle", 57: "freezing drizzle",
       61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain", 71: "light snow",
       73: "snow", 75: "heavy snow", 77: "snow grains", 80: "light showers", 81: "showers", 82: "violent showers",
       85: "snow showers", 86: "heavy snow showers", 95: "thunderstorms", 96: "thunderstorms with hail", 99: "thunderstorms with hail"}


@dataclass
class Place:
    name: str
    lat: float
    lon: float
    country: str = ""


# When-words people put after a place ("weather in Pune right now", "Delhi tomorrow pls"). The op they imply, or None
# when they only mean "now".
_WHEN_WORDS = [(r"tomorrow|tmrw|tmr", "TOMORROW"), (r"(?:this|the|next) week|(?:the )?next (?:few|7|seven) days", "WEEK"),
               (r"(?:this |the )?weekend", "WEEKEND"), (r"tonight", "TONIGHT"),
               (r"today|right now|now|currently|at the moment|at present|these days|this (?:morning|afternoon|evening)", None)]
_FILLER = r"please|pls|plz|thanks|thank you|for me|like|outside|there|in|for|at"


def place_and_when(text: str):
    """("Hyderabad", None) from "Hyderabad right now"; ("Pune", "TOMORROW") from "pune tomorrow pls"."""
    t = re.sub(r"[?!.]+$", "", (text or "").strip())
    when = None
    changed = True
    while changed and t:
        changed = False
        for pat, op in _WHEN_WORDS + [(_FILLER, None)]:
            for edge in (rf"(?:,?\s+|^)(?:{pat})$", rf"^(?:{pat})(?:,?\s+|$)"):
                m = re.search(edge, t, flags=re.I)
                if m:
                    t, when, changed = (t[:m.start()] + t[m.end():]).strip(" ,"), when or op, True
    return t, when


def geocode(name: str) -> Place:
    name = re.sub(r"^(the city of|city of)\s+", "", name.strip(), flags=re.I)
    name = place_and_when(name)[0] or name
    words = name.split(",")[0].split()
    # the whole name first; if a service has no such place, the longest leading run of words that is one
    # ("Hyderabad and how humid" → Hyderabad), at most 4 lookups (each cached for a day)
    for n in range(len(words), max(0, len(words) - 4), -1):
        data = get_json("https://geocoding-api.open-meteo.com/v1/search?count=1&language=en&format=json&name=" + q(" ".join(words[:n])), 86400)
        res = (data or {}).get("results") or []
        if res:
            p = res[0]
            return Place(p["name"], p["latitude"], p["longitude"], p.get("country", ""))
    raise NetError(f"I couldn't find a place called {name}.")


def where_am_i() -> Place:
    for url in ("https://ipwho.is/", "https://ipapi.co/json/"):
        try:
            d = get_json(url, 3600)
        except NetError:
            continue
        if d.get("latitude") is not None and d.get("success", True):
            return Place(d.get("city") or d.get("region") or "your area", float(d["latitude"]), float(d["longitude"]),
                         d.get("country") or d.get("country_name") or "")
    raise NetError("I couldn't work out where you are. Say “set my city to …” or ask for a city by name.")


def forecast(p: Place) -> dict:
    url = ("https://api.open-meteo.com/v1/forecast?latitude=%.4f&longitude=%.4f&timezone=auto&forecast_days=7"
           "&current=temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,"
           "wind_gusts_10m,uv_index,is_day"
           "&hourly=temperature_2m,precipitation_probability,weather_code"
           "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,"
           "snowfall_sum,sunrise,sunset,uv_index_max,wind_speed_10m_max") % (p.lat, p.lon)
    return get_json(url, 600)


def air_quality(p: Place) -> dict:
    return get_json("https://air-quality-api.open-meteo.com/v1/air-quality?latitude=%.4f&longitude=%.4f&timezone=auto"
                    "&current=us_aqi,pm2_5,pm10" % (p.lat, p.lon), 900)


def _t(x) -> str:
    return f"{round(x)}°" if x is not None else "?"


def _clock(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%I:%M %p").lstrip("0")
    except (TypeError, ValueError):
        return iso or "?"


def aqi_words(v: float) -> str:
    for limit, word in ((50, "good"), (100, "moderate"), (150, "unhealthy for sensitive people"), (200, "unhealthy"),
                        (300, "very unhealthy")):
        if v <= limit:
            return word
    return "hazardous"


def weather_answer(op: str, f: dict, place: str, aq: Optional[dict] = None, today: Optional[date] = None) -> str:
    """Spoken weather from an Open-Meteo forecast (pure, tested with saved responses)."""
    c, d, h = f.get("current") or {}, f.get("daily") or {}, f.get("hourly") or {}
    days = d.get("time") or []
    today = today or (date.fromisoformat(days[0]) if days else date.today())

    def day(i):
        return {k: (v[i] if isinstance(v, list) and len(v) > i else None) for k, v in d.items()}
    now_desc = WMO.get(c.get("weather_code"), "mixed weather")
    if op == "WEATHER_NOW":
        return (f"In {place} it's {_t(c.get('temperature_2m'))}, {now_desc}, feels like {_t(c.get('apparent_temperature'))}. "
                f"Humidity {c.get('relative_humidity_2m', '?')}%.")
    if op == "FEELS":
        return f"It feels like {_t(c.get('apparent_temperature'))} in {place} (actual {_t(c.get('temperature_2m'))})."
    if op == "HUMIDITY":
        return f"Humidity in {place} is {c.get('relative_humidity_2m', '?')} percent."
    if op == "WIND":
        return f"Wind in {place}: {round(c.get('wind_speed_10m') or 0)} km/h, gusts up to {round(c.get('wind_gusts_10m') or 0)} km/h."
    if op == "UV":
        u = c.get("uv_index")
        level = "low" if (u or 0) < 3 else "moderate" if u < 6 else "high" if u < 8 else "very high" if u < 11 else "extreme"
        return f"The UV index in {place} is {round(u or 0, 1)} ({level}). Today's peak is {round(day(0).get('uv_index_max') or 0, 1)}."
    if op in ("TODAY", "TOMORROW"):
        i = 0 if op == "TODAY" else 1
        x = day(i)
        when = "Today" if i == 0 else "Tomorrow"
        return (f"{when} in {place}: {WMO.get(x.get('weather_code'), 'mixed weather')}, high {_t(x.get('temperature_2m_max'))}, "
                f"low {_t(x.get('temperature_2m_min'))}, {x.get('precipitation_probability_max') or 0}% chance of rain.")
    if op == "WEEK":
        parts = []
        for i in range(min(7, len(days))):
            x = day(i)
            name = "Today" if i == 0 else date.fromisoformat(days[i]).strftime("%A")
            parts.append(f"{name} {WMO.get(x.get('weather_code'), 'mixed')}, {_t(x.get('temperature_2m_max'))}/{_t(x.get('temperature_2m_min'))}")
        return f"This week in {place}: " + "; ".join(parts) + "."
    if op == "WEEKEND":
        parts = []
        for i, iso in enumerate(days):
            dd = date.fromisoformat(iso)
            if dd.weekday() in (5, 6):
                x = day(i)
                parts.append(f"{dd:%A} {WMO.get(x.get('weather_code'), 'mixed')}, high {_t(x.get('temperature_2m_max'))}, "
                             f"{x.get('precipitation_probability_max') or 0}% rain")
        return (f"This weekend in {place}: " + "; ".join(parts) + ".") if parts else "The weekend is beyond the forecast I have."
    if op in ("RAIN", "UMBRELLA"):
        times, probs = h.get("time") or [], h.get("precipitation_probability") or []
        now_iso = (c.get("time") or "")[:13]
        start = next((i for i, t in enumerate(times) if t[:13] >= now_iso), 0)
        window = [(times[i], probs[i]) for i in range(start, min(start + 12, len(times))) if probs[i] is not None]
        peak = max(window, key=lambda tp: tp[1]) if window else (None, 0)
        if op == "UMBRELLA":
            if peak[1] >= 50:
                return f"Yes, take an umbrella. Rain is likely in {place} around {_clock(peak[0])} ({peak[1]}%)."
            if peak[1] >= 25:
                return f"Maybe. There's up to a {peak[1]}% chance of rain in {place} in the next 12 hours."
            return f"No umbrella needed. Rain chances stay low in {place} for the next 12 hours."
        if peak[1] >= 25:
            return f"Up to {peak[1]}% chance of rain in {place}, most likely around {_clock(peak[0])}."
        return f"Rain isn't likely in {place} in the next 12 hours."
    if op == "JACKET":
        lo = day(0).get("temperature_2m_min")
        feel = c.get("apparent_temperature")
        cold = min(x for x in (lo, feel) if x is not None) if (lo is not None or feel is not None) else None
        if cold is None:
            return "I couldn't get the temperature."
        if cold < 12:
            return f"Yes, wear a warm jacket. It gets down to {_t(cold)} in {place}."
        if cold < 19:
            return f"A light jacket or sweater is a good idea. It dips to {_t(cold)} in {place}."
        return f"No jacket needed. It stays around {_t(cold)} or warmer in {place}."
    if op == "SNOW":
        snow = [(days[i], day(i).get("snowfall_sum") or 0) for i in range(len(days))]
        when = [date.fromisoformat(dd).strftime("%A") for dd, s in snow if s > 0]
        return f"Snow is expected in {place} on {', '.join(when)}." if when else f"No snow in the forecast for {place}."
    if op == "TONIGHT":
        times, temps = h.get("time") or [], h.get("temperature_2m") or []
        tonight = [temps[i] for i, t in enumerate(times) if t.startswith(days[0] if days else "") and t[11:13] >= "20"] + \
                  [temps[i] for i, t in enumerate(times) if len(days) > 1 and t.startswith(days[1]) and t[11:13] <= "05"]
        tonight = [x for x in tonight if x is not None]
        return f"Tonight in {place} it goes down to about {_t(min(tonight))}." if tonight else f"Tonight's low in {place} is {_t(day(1).get('temperature_2m_min'))}."
    if op == "HOURLY":
        times, temps, codes, probs = h.get("time") or [], h.get("temperature_2m") or [], h.get("weather_code") or [], h.get("precipitation_probability") or []
        now_iso = (c.get("time") or "")[:13]
        start = next((i for i, t in enumerate(times) if t[:13] >= now_iso), 0)
        parts = [f"{_clock(times[i])} {_t(temps[i])} {WMO.get(codes[i], '')}".strip() + (f", {probs[i]}% rain" if (probs[i] or 0) >= 30 else "")
                 for i in range(start + 1, min(start + 13, len(times)), 3)]
        return f"Next hours in {place}: " + "; ".join(parts) + "."
    if op in ("SUNRISE", "SUNSET"):
        x = day(0)
        return (f"Sunrise in {place} is at {_clock(x.get('sunrise'))}." if op == "SUNRISE"
                else f"Sunset in {place} is at {_clock(x.get('sunset'))}.")
    if op == "SUN":
        x = day(0)
        return f"In {place} the sun rises at {_clock(x.get('sunrise'))} and sets at {_clock(x.get('sunset'))}."
    if op == "HOT_COLD":
        hi, lo = day(0).get("temperature_2m_max"), day(0).get("temperature_2m_min")
        feel = "hot" if (hi or 0) >= 33 else "warm" if (hi or 0) >= 26 else "mild" if (hi or 0) >= 18 else "cold"
        return f"It's a {feel} day in {place}: high {_t(hi)}, low {_t(lo)}."
    if op == "AQI":
        cur = (aq or {}).get("current") or {}
        v = cur.get("us_aqi")
        if v is None:
            return f"I couldn't get the air quality for {place}."
        return (f"Air quality in {place} is {round(v)} on the US AQI scale, {aqi_words(v)}. "
                f"PM2.5 {round(cur.get('pm2_5') or 0)}, PM10 {round(cur.get('pm10') or 0)} micrograms per cubic metre.")
    if op == "WALK":
        x = day(0)
        rain = x.get("precipitation_probability_max") or 0
        t = c.get("apparent_temperature") or 0
        if rain >= 60:
            return f"Probably not: rain is likely in {place} today ({rain}%)."
        if t >= 36:
            return f"It's very hot in {place} ({_t(t)} feels-like). Go early morning or evening, and carry water."
        return f"Looks fine for a walk in {place}: {now_desc}, {_t(c.get('temperature_2m'))}."
    return "I don't know that weather question."


WEATHER_OPS = {"WEATHER_NOW", "FEELS", "HUMIDITY", "WIND", "UV", "TODAY", "TOMORROW", "WEEK", "WEEKEND", "RAIN", "UMBRELLA",
               "JACKET", "SNOW", "TONIGHT", "HOURLY", "SUNRISE", "SUNSET", "SUN", "HOT_COLD", "AQI", "WALK"}


# ------------------------------------------------------------------------------------------------ info ops
STATUS_PAGES = {
    "github": "https://www.githubstatus.com", "cloudflare": "https://www.cloudflarestatus.com",
    "discord": "https://discordstatus.com", "reddit": "https://www.redditstatus.com", "dropbox": "https://status.dropbox.com",
    "zoom": "https://status.zoom.us", "vercel": "https://www.vercel-status.com", "netlify": "https://www.netlifystatus.com",
    "digitalocean": "https://status.digitalocean.com", "npm": "https://status.npmjs.org", "anthropic": "https://status.anthropic.com",
    "bitbucket": "https://bitbucket.status.atlassian.com", "figma": "https://status.figma.com", "twilio": "https://status.twilio.com",
    "epic games": "https://status.epicgames.com", "coinbase": "https://status.coinbase.com", "jira": "https://jira-software.status.atlassian.com",
    "confluence": "https://confluence.status.atlassian.com", "trello": "https://trello.status.atlassian.com",
    "atlassian": "https://status.atlassian.com", "linode": "https://status.linode.com",
    "sentry": "https://status.sentry.io", "supabase": "https://status.supabase.com",
    "mongodb": "https://status.mongodb.com", "circleci": "https://status.circleci.com",
    # checked live 2026-11-01 (each answers /api/v2/status.json)
    "openai": "https://status.openai.com", "notion": "https://www.notion-status.com", "docker": "https://www.dockerstatus.com",
    "linear": "https://linearstatus.com", "postman": "https://status.postman.com", "shopify": "https://www.shopifystatus.com",
    "box": "https://status.box.com", "hubspot": "https://status.hubspot.com", "sendgrid": "https://status.sendgrid.com",
    "pypi": "https://status.python.org", "rubygems": "https://status.rubygems.org", "quay": "https://status.quay.io",
    "render": "https://status.render.com", "fly": "https://status.flyio.net", "elastic": "https://status.elastic.co",
    "grafana": "https://status.grafana.com", "new relic": "https://status.newrelic.com", "canva": "https://www.canvastatus.com",
    "miro": "https://status.miro.com", "asana": "https://status.asana.com", "airtable": "https://status.airtable.com",
    "vimeo": "https://www.vimeostatus.com", "twitch": "https://status.twitch.com", "monday": "https://status.monday.com",
    "clickup": "https://clickup.statuspage.io", "cursor": "https://status.cursor.com", "1password": "https://status.1password.com",
    "zapier": "https://status.zapier.com", "loom": "https://status.loom.com", "webflow": "https://status.webflow.com",
    "wix": "https://status.wix.com", "squarespace": "https://status.squarespace.com",
}
TOPICS = {"world": "WORLD", "india": "NATION", "business": "BUSINESS", "technology": "TECHNOLOGY", "tech": "TECHNOLOGY",
          "entertainment": "ENTERTAINMENT", "sports": "SPORTS", "science": "SCIENCE", "health": "HEALTH"}
LANGS = {"hindi": "hi", "telugu": "te", "tamil": "ta", "kannada": "kn", "malayalam": "ml", "marathi": "mr", "bengali": "bn",
         "gujarati": "gu", "punjabi": "pa", "urdu": "ur", "odia": "or", "english": "en", "spanish": "es", "french": "fr",
         "german": "de", "italian": "it", "portuguese": "pt", "russian": "ru", "japanese": "ja", "korean": "ko",
         "chinese": "zh-CN", "mandarin": "zh-CN", "arabic": "ar", "turkish": "tr", "dutch": "nl", "greek": "el",
         "thai": "th", "vietnamese": "vi", "indonesian": "id", "malay": "ms", "persian": "fa", "hebrew": "he",
         "polish": "pl", "swedish": "sv", "nepali": "ne", "sanskrit": "sa", "sinhala": "si", "swahili": "sw", "ukrainian": "uk"}


@dataclass
class Answer:
    text: str
    open_url: Optional[str] = None       # also open this page (an image, the first result…)
    copy: Optional[str] = None           # put this on the clipboard
    pending: Optional[str] = None        # answer for "tell me the answer"


def _pkg_names(name: str) -> list:
    n = name.strip().lower()
    out = [n.replace(" ", "-"), n.replace(" ", ""), n.replace(" ", "_"), n.replace(" dot ", ".").replace(" ", "")]
    return list(dict.fromkeys(x for x in out if x))


def _first_ok(names: list, fn):
    last = None
    for n in names:
        try:
            return n, fn(n)
        except NetError as e:
            last = e
    raise last or NetError("not found")


def _ago(iso: str) -> str:
    try:
        then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError):
        return ""
    days = (datetime.now(timezone.utc) - then).days
    return "today" if days < 1 else "yesterday" if days == 1 else f"{days} days ago" if days < 60 else f"in {then:%B %Y}"


def _host(text: str) -> str:
    t = re.sub(r"\s+dot\s+", ".", text.strip().lower()).replace(" ", "")
    t = re.sub(r"^https?://", "", t).split("/")[0]
    if "." not in t:
        t += ".com"
    return t


def money(amount: float, code: str) -> str:
    """"₹4,98,000" for rupees (Indian lakh grouping), "1,234.5 USD" otherwise; paise/cents only when there are any."""
    whole, cents = divmod(round(abs(amount) * 100), 100)
    if code == "INR":
        digits = str(whole)
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            head, groups = head[:-2], [head[-2:]] + groups
        text = ",".join(([head] if head else []) + groups + [tail])
        text = "₹" + text
    else:
        text = f"{whole:,}"
    if cents:
        text += f".{cents:02d}"
    sign = "-" if amount < 0 else ""
    return sign + text if code == "INR" else f"{sign}{text} {code}"


def info(op: str, slots: dict, settings=None) -> Answer:
    """The "net" kind: ask a public service and answer in one or two spoken sentences. Raises NetError."""
    a = _info(op, slots, settings)
    if isinstance(a, Answer) and a.text and "\n" not in a.text:
        a.text = re.sub(r"[ \t ]{2,}", " ", a.text).strip()   # services' text often has stray double spaces
    return a


def _info(op: str, slots: dict, settings=None) -> Answer:
    s = {k: (v or "").strip() for k, v in slots.items() if isinstance(v, str)}
    arg = s.get("q") or s.get("city") or s.get("word") or ""

    if op in WEATHER_OPS:
        city, when = place_and_when(s.get("city") or s.get("q") or "")
        if when and op == "WEATHER_NOW":          # "weather in Pune tomorrow" asks for tomorrow, not now
            op = when
        home = (settings["home_city"] if settings is not None else "") or ""
        place = geocode(city) if city else (geocode(home) if home else where_am_i())
        f = forecast(place)
        guessed = not city and not home          # from the internet connection: say so once, and how to fix it
        return Answer(weather_answer(op, f, place.name, air_quality(place) if op == "AQI" else None) +
                      (f" (I went by your internet connection; if you're not in {place.name}, say “set my city to …”.)"
                       if guessed else ""))
    if op == "SET_CITY":
        place = geocode(s["city"])
        if settings is not None:
            settings["home_city"] = place.name
        return Answer(f"Got it. I'll use {place.name}{', ' + place.country if place.country else ''} for weather.")
    if op == "WHERE_AM_I":
        p = where_am_i()
        return Answer(f"Going by your internet connection, you're around {p.name}{', ' + p.country if p.country else ''}.")

    # ---- knowledge
    if op == "WIKI":
        found = get_json("https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=1&srsearch=" + q(arg), 3600)
        hits = found.get("query", {}).get("search", [])
        if not hits:
            raise NetError(f"Wikipedia has nothing on {arg}.")
        title = hits[0]["title"]
        d = get_json("https://en.wikipedia.org/api/rest_v1/page/summary/" + q(title.replace(" ", "_")), 3600)
        return Answer(first_sentences(d.get("extract", ""), 2) or f"Wikipedia has a page on {title}.",
                      pending=f"More at {d.get('content_urls', {}).get('desktop', {}).get('page', '')}")
    if op == "WIKI_RANDOM":
        d = get_json("https://en.wikipedia.org/api/rest_v1/page/random/summary", 0)
        return Answer(f"{d.get('title')}: {first_sentences(d.get('extract', ''), 2)}")
    if op == "ON_THIS_DAY":
        t = date.today()
        d = get_json(f"https://en.wikipedia.org/api/rest_v1/feed/onthisday/events/{t.month:02d}/{t.day:02d}", 86400)
        ev = sorted(d.get("events") or [], key=lambda e: -int(e.get("year", 0)))[:3]
        return Answer("On this day: " + " ".join(f"In {e.get('year')}, {first_sentences(e.get('text', ''), 1, 160)}" for e in ev))
    if op == "DEFINE":
        word = arg.lower()
        try:
            d = get_json("https://api.dictionaryapi.dev/api/v2/entries/en/" + q(word), 86400)
        except NetError:
            raise NetError(f"I couldn't find a definition for {word}.")
        meanings = (d[0].get("meanings") or []) if isinstance(d, list) and d else []
        parts = []
        for m in meanings[:2]:
            defs = m.get("definitions") or []
            if defs:
                parts.append(f"as a {m.get('partOfSpeech', 'word')}, {defs[0].get('definition', '').rstrip('.')}")
        if not parts:
            raise NetError(f"I couldn't find a definition for {word}.")
        return Answer(f"{word.capitalize()}: " + "; ".join(parts) + ".")
    if op in ("SYNONYMS", "ANTONYMS", "RHYMES", "SOUNDS_LIKE", "MEANS_LIKE", "ADJECTIVES", "STARTS_WITH"):
        param = {"SYNONYMS": "rel_syn", "ANTONYMS": "rel_ant", "RHYMES": "rel_rhy", "SOUNDS_LIKE": "sl", "MEANS_LIKE": "ml",
                 "ADJECTIVES": "rel_jjb", "STARTS_WITH": "sp"}[op]
        value = arg.lower() + ("*" if op == "STARTS_WITH" else "")
        words = [w["word"] for w in get_json(f"https://api.datamuse.com/words?max=12&{param}={q(value)}", 86400)]
        if not words:
            return Answer(f"I couldn't find any for {arg}.")
        label = {"SYNONYMS": "Words like", "ANTONYMS": "Opposites of", "RHYMES": "Rhymes for", "SOUNDS_LIKE": "Sounds like",
                 "MEANS_LIKE": "Words meaning", "ADJECTIVES": "Words to describe", "STARTS_WITH": "Words starting with"}[op]
        return Answer(f"{label} {arg}: " + ", ".join(words[:10]) + ".")
    if op == "TRANSLATE":
        name = (s.get("lang") or s.get("l") or "").lower()
        lang = LANGS.get(name)
        if not lang:
            raise NetError(f"I don't know the language {name}. Try Hindi, Telugu, Tamil, Spanish…")
        d = get_json(f"https://api.mymemory.translated.net/get?langpair=en|{lang}&q=" + q(s["q"]), 86400)
        out = html.unescape((d.get("responseData") or {}).get("translatedText") or "")
        if not out or "MYMEMORY WARNING" in out:
            raise NetError("The translation service didn't answer.")
        return Answer(f"In {name.capitalize()}: {out}", copy=out)

    # ---- money
    if op == "EXCHANGE":
        a, b = s.get("a", "").upper(), s.get("b", "").upper()
        codes = {"DOLLAR": "USD", "DOLLARS": "USD", "RUPEE": "INR", "RUPEES": "INR", "EURO": "EUR", "EUROS": "EUR",
                 "POUND": "GBP", "POUNDS": "GBP", "YEN": "JPY", "DIRHAM": "AED", "DIRHAMS": "AED", "RIYAL": "SAR",
                 "YUAN": "CNY", "RUBLE": "RUB", "FRANC": "CHF", "RINGGIT": "MYR", "BAHT": "THB", "WON": "KRW",
                 "TAKA": "BDT", "DINAR": "KWD", "SINGAPORE DOLLAR": "SGD", "AUSTRALIAN DOLLAR": "AUD", "CANADIAN DOLLAR": "CAD"}
        a, b = codes.get(a, a), codes.get(b, b)
        if not re.fullmatch(r"[A-Z]{3}", a) or not re.fullmatch(r"[A-Z]{3}", b):
            raise NetError("Say the currencies like “dollar to rupee” or “USD to INR”.")
        d = get_json(f"https://open.er-api.com/v6/latest/{a}", 1800)
        rate = (d.get("rates") or {}).get(b)
        if rate is None:
            raise NetError(f"I don't have a rate from {a} to {b}.")
        amount = float(s.get("n") or 1)
        return Answer(f"{money(amount, a)} is {money(amount * rate, b)} (1 {a} = {rate:,.4g} {b}, "
                      f"rate updated {d.get('time_last_update_utc', '')[5:16]}).")
    if op == "CRYPTO":
        found = get_json("https://api.coingecko.com/api/v3/search?query=" + q(arg), 86400).get("coins") or []
        if not found:
            raise NetError(f"I couldn't find a coin called {arg}.")
        cid, name = found[0]["id"], found[0]["name"]
        p = get_json(f"https://api.coingecko.com/api/v3/simple/price?ids={cid}&vs_currencies=usd,inr&include_24hr_change=true", 120).get(cid) or {}
        if not p:
            raise NetError(f"No price for {name} right now.")
        ch = p.get("usd_24h_change")
        return Answer(f"{name} is ${p.get('usd', 0):,.2f}, or ₹{p.get('inr', 0):,.0f}" +
                      (f", {'up' if ch >= 0 else 'down'} {abs(ch):.1f}% in 24 hours." if ch is not None else "."))

    # ---- news
    if op in ("NEWS", "NEWS_TOPIC", "NEWS_ABOUT"):
        if op == "NEWS":
            url = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
        elif op == "NEWS_TOPIC":
            url = f"https://news.google.com/rss/headlines/section/topic/{TOPICS.get(s.get('topic', '').lower(), 'WORLD')}?hl=en-IN&gl=IN&ceid=IN:en"
        else:
            url = "https://news.google.com/rss/search?hl=en-IN&gl=IN&ceid=IN:en&q=" + q(arg)
        items = parse_rss_items(request(url, cache_seconds=600).text(), 5)
        if not items:
            raise NetError("I couldn't get the news right now.")
        heads = [re.sub(r"\s+-\s+[^-]+$", "", t) for t, _, _ in items]
        return Answer("Here are the headlines. " + " … ".join(f"{i}. {h}." for i, h in enumerate(heads, 1)), pending=items[0][1])
    if op.startswith("HN_"):
        feed = {"HN_TOP": "topstories", "HN_NEW": "newstories", "HN_BEST": "beststories", "HN_ASK": "askstories", "HN_SHOW": "showstories"}[op]
        ids = get_json(f"https://hacker-news.firebaseio.com/v0/{feed}.json", 300)[:5]

        def title(i):
            try:
                return get_json(f"https://hacker-news.firebaseio.com/v0/item/{i}.json", 600).get("title", "")
            except NetError:
                return ""
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(5) as pool:
            titles = list(pool.map(title, ids))
        return Answer("On Hacker News: " + " … ".join(f"{n}. {t}." for n, t in enumerate(filter(None, titles), 1)))

    # ---- developer lookups
    if op == "NPM":
        name, d = _first_ok(_pkg_names(arg), lambda n: get_json(f"https://registry.npmjs.org/{n}/latest", 600))
        try:
            dl = get_json(f"https://api.npmjs.org/downloads/point/last-week/{name}", 3600).get("downloads")
        except NetError:
            dl = None
        return Answer(f"{name} on npm is at version {d.get('version')}." + (f" {dl:,} downloads last week." if dl else "") +
                      (f" {first_sentences(d.get('description', ''), 1, 160)}" if d.get("description") else ""))
    if op == "PYPI":
        name, d = _first_ok(_pkg_names(arg), lambda n: get_json(f"https://pypi.org/pypi/{n}/json", 600))
        i = d.get("info", {})
        return Answer(f"{i.get('name', name)} on PyPI is at version {i.get('version')}. {first_sentences(i.get('summary') or '', 1, 160)}".strip())
    if op == "CRATES":
        name, d = _first_ok(_pkg_names(arg), lambda n: get_json(f"https://crates.io/api/v1/crates/{n}", 600))
        c = d.get("crate", {})
        return Answer(f"The {c.get('name', name)} crate is at version {c.get('max_stable_version') or c.get('max_version')}, "
                      f"{c.get('downloads', 0):,} downloads in total.")
    if op == "NUGET":
        name, d = _first_ok([n.replace("-", ".") for n in _pkg_names(arg)] + _pkg_names(arg),
                            lambda n: get_json(f"https://api.nuget.org/v3-flatcontainer/{n.lower()}/index.json", 600))
        versions = [v for v in d.get("versions", []) if "-" not in v] or d.get("versions", [])
        return Answer(f"{name} on NuGet: latest version {versions[-1]}." if versions else f"No versions of {name} on NuGet.")
    if op == "GEMS":
        name, d = _first_ok(_pkg_names(arg), lambda n: get_json(f"https://rubygems.org/api/v1/gems/{n}.json", 600))
        return Answer(f"The {d.get('name', name)} gem is at version {d.get('version')}.")
    if op == "PUB":
        name, d = _first_ok([n.replace("-", "_") for n in _pkg_names(arg)], lambda n: get_json(f"https://pub.dev/api/packages/{n}", 600))
        return Answer(f"{name} on pub.dev is at version {d.get('latest', {}).get('version')}.")
    if op == "BREW":
        name, d = _first_ok(_pkg_names(arg), lambda n: get_json(f"https://formulae.brew.sh/api/formula/{n}.json", 3600))
        return Answer(f"Homebrew's {d.get('name', name)} is at version {d.get('versions', {}).get('stable')}. {d.get('desc') or ''}".strip())
    if op == "DOCKER":
        name, d = _first_ok(_pkg_names(arg), lambda n: get_json(f"https://hub.docker.com/v2/repositories/library/{n}/tags?page_size=8&ordering=last_updated", 600))
        tags = [t["name"] for t in d.get("results", [])][:8]
        return Answer(f"Latest tags for the {name} image: " + ", ".join(tags) + ".")
    if op == "MAVEN":
        d = get_json("https://search.maven.org/solrsearch/select?rows=1&wt=json&q=a:" + q(arg.replace(" ", "-")), 3600)
        docs = d.get("response", {}).get("docs") or []
        if not docs:
            raise NetError(f"Maven Central has no artifact called {arg}.")
        x = docs[0]
        return Answer(f"{x.get('g')}:{x.get('a')} latest version {x.get('latestVersion')}.")
    if op in ("GH_REPO", "GH_RELEASE"):
        repo = re.sub(r"\s*(slash|/)\s*", "/", arg.strip()).replace(" ", "-")
        if "/" not in repo:
            items = get_json("https://api.github.com/search/repositories?per_page=1&sort=stars&q=" + q(arg), 600).get("items") or []
            if not items:
                raise NetError(f"I couldn't find a GitHub repository for {arg}.")
            repo = items[0]["full_name"]
        if op == "GH_RELEASE":
            try:
                rel = get_json(f"https://api.github.com/repos/{repo}/releases/latest", 600)
                return Answer(f"The latest release of {repo} is {rel.get('tag_name')}, published {_ago(rel.get('published_at', ''))}.")
            except NetError:
                tags = get_json(f"https://api.github.com/repos/{repo}/tags?per_page=1", 600)
                if tags:
                    return Answer(f"{repo} has no releases; its newest tag is {tags[0].get('name')}.")
                raise NetError(f"{repo} has no releases.")
        d = get_json(f"https://api.github.com/repos/{repo}", 600)
        return Answer(f"{d.get('full_name')}: {d.get('stargazers_count', 0):,} stars, {d.get('forks_count', 0):,} forks, "
                      f"{d.get('open_issues_count', 0):,} open issues and pull requests, mostly {d.get('language') or 'mixed languages'}, "
                      f"last pushed {_ago(d.get('pushed_at', ''))}. {first_sentences(d.get('description') or '', 1, 160)}".strip(),
                      pending=d.get("html_url"))
    if op == "GH_USER":
        d = get_json("https://api.github.com/users/" + q(arg.replace(" ", "")), 600)
        return Answer(f"{d.get('name') or d.get('login')} on GitHub: {d.get('public_repos', 0)} public repositories, "
                      f"{d.get('followers', 0):,} followers. {d.get('bio') or ''}".strip())
    if op == "STATUS":
        svc = s.get("svc") or arg
        base = STATUS_PAGES.get(svc.lower())
        if not base:
            raise NetError(f"I don't have a status page for {svc}.")
        d = get_json(base + "/api/v2/status.json", 60)
        desc = (d.get("status") or {}).get("description") or "unknown"
        pretty = {"github": "GitHub", "npm": "npm", "pypi": "PyPI", "openai": "OpenAI", "digitalocean": "DigitalOcean",
                  "mongodb": "MongoDB", "circleci": "CircleCI", "hubspot": "HubSpot", "sendgrid": "SendGrid", "clickup": "ClickUp",
                  "1password": "1Password", "rubygems": "RubyGems", "fly": "Fly.io"}.get(svc.lower(), svc.title())
        return Answer(f"{pretty} status: {desc}.")
    if op in ("SITE_UP", "HTTP_STATUS", "RESPONSE_TIME", "HEADERS", "PAGE_TITLE", "EXPAND_URL"):
        target = arg if op in ("HTTP_STATUS", "PAGE_TITLE", "EXPAND_URL") else _host(arg)
        r = request(target if "://" in target else "https://" + (target if op != "SITE_UP" else target), method="GET", max_bytes=400_000)
        host = urllib.parse.urlsplit(r.url).hostname
        if op == "SITE_UP":
            ok = r.status < 500
            return Answer(f"{host} is {'up' if ok else 'having problems'}: it answered {r.status} in {r.elapsed * 1000:.0f} milliseconds.")
        if op == "HTTP_STATUS":
            return Answer(f"{host} answered {r.status} {http.client.responses.get(r.status, '')}.".replace("  ", " "))
        if op == "RESPONSE_TIME":
            return Answer(f"{host} answered in {r.elapsed * 1000:.0f} milliseconds.")
        if op == "HEADERS":
            keep = ["server", "content-type", "cache-control", "strict-transport-security", "x-powered-by", "cf-ray"]
            got = [f"{k}: {r.headers[k]}" for k in keep if k in r.headers]
            return Answer(f"{host} headers. " + "; ".join(got) if got else f"{host} sent no notable headers.")
        if op == "PAGE_TITLE":
            title, _, _ = readable(r.text(), r.url)
            return Answer(f"The page title is “{title}”." if title else "That page has no title.")
        return Answer(f"That link goes to {r.url}", copy=r.url)
    if op == "SSL_EXPIRY":
        host = _host(arg)
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        addr = next((i[4] for i in infos if public_ip(i[4][0])), None)
        if addr is None:
            raise NetError("That address is on a private or local network, so I won't connect to it.")
        ctx = ssl.create_default_context()
        with socket.create_connection(addr[:2], timeout=TIMEOUT) as raw, ctx.wrap_socket(raw, server_hostname=host) as tls:
            cert = tls.getpeercert()
        end = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        days = (end - datetime.now(timezone.utc)).days
        issuer = dict(x[0] for x in cert.get("issuer", ())).get("organizationName", "")
        return Answer(f"{host}'s certificate is valid until {end:%d %B %Y}, {days} days from now" + (f", issued by {issuer}." if issuer else "."))
    if op == "DNS":
        host = _host(arg)
        try:
            addrs = sorted({i[4][0] for i in socket.getaddrinfo(host, None)})
        except socket.gaierror:
            raise NetError(f"{host} doesn't resolve to any address.")
        return Answer(f"{host} resolves to " + ", ".join(addrs[:6]) + ".")
    if op == "MY_IP":
        d = get_json("https://api.ipify.org?format=json", 60)
        return Answer(f"Your public IP address is {d.get('ip')}.", copy=d.get("ip"))
    if op == "IP_INFO":
        ip = re.sub(r"\s*dot\s*", ".", arg).replace(" ", "")
        ipaddress.ip_address(ip)
        d = get_json("https://ipwho.is/" + ip, 3600)
        if d.get("success") is False:
            raise NetError(f"No details for {ip}.")
        return Answer(f"{ip} is in {d.get('city')}, {d.get('region')}, {d.get('country')}, run by {(d.get('connection') or {}).get('org') or 'an unknown provider'}.")
    if op == "DOMAIN":
        dom = _host(arg)
        try:
            d = get_json("https://rdap.org/domain/" + dom, 3600)
        except NetError as e:
            if "not found" in str(e):
                return Answer(f"{dom} doesn't seem to be registered, so it may be available. Check with a registrar to be sure.")
            raise
        ev = {e.get("eventAction"): e.get("eventDate", "")[:10] for e in d.get("events", [])}
        return Answer(f"{dom} is registered" + (f" since {ev['registration']}" if ev.get("registration") else "") +
                      (f", expiring {ev['expiration']}." if ev.get("expiration") else "."))
    if op == "SHORTEN":
        url = clean_url(arg)
        r = request("https://is.gd/create.php?format=simple&url=" + q(url))
        short = r.text().strip()
        if r.status != 200 or not short.startswith("http"):
            raise NetError("The link shortener didn't accept that address.")
        return Answer(f"Short link copied: {short}", copy=short)

    # ---- fun & everyday
    if op == "JOKE":
        d = get_json("https://official-joke-api.appspot.com/random_joke", 0)
        return Answer(d.get("setup", ""), pending=d.get("punchline"))
    if op == "QUOTE":
        d = get_json("https://zenquotes.io/api/random", 0)
        return Answer(f"“{d[0]['q']}” — {d[0]['a']}" if d else "No quote right now.")
    if op == "ADVICE":
        return Answer(get_json("https://api.adviceslip.com/advice", 0).get("slip", {}).get("advice", "Be kind to yourself."))
    if op == "USELESS_FACT":
        return Answer(get_json("https://uselessfacts.jsph.pl/api/v2/facts/random?language=en", 0).get("text", ""))
    if op == "CAT_FACT":
        return Answer(get_json("https://catfact.ninja/fact", 0).get("fact", ""))
    if op in ("DOG_PHOTO", "CAT_PHOTO"):
        try:
            if op == "DOG_PHOTO":
                url = get_json("https://random.dog/woof.json?filter=mp4,webm", 0).get("url")
            else:
                url = (get_json("https://api.thecatapi.com/v1/images/search", 0) or [{}])[0].get("url")
        except NetError:
            url = None
        animal = "dog" if op == "DOG_PHOTO" else "cat"
        return Answer(f"Here's a {animal} for you.", open_url=url or f"https://www.google.com/search?tbm=isch&q=cute+{animal}")
    if op == "TRIVIA":
        d = get_json("https://opentdb.com/api.php?amount=1&type=multiple", 0)
        r = (d.get("results") or [None])[0]
        if not r:
            raise NetError("No trivia right now.")
        opts = sorted([html.unescape(x) for x in r["incorrect_answers"]] + [html.unescape(r["correct_answer"])])
        return Answer(f"{html.unescape(r['question'])} Is it " + ", ".join(opts[:-1]) + f", or {opts[-1]}?",
                      pending=f"The answer is {html.unescape(r['correct_answer'])}.")
    if op in ("RECIPE_RANDOM", "RECIPE_FOR"):
        d = get_json("https://www.themealdb.com/api/json/v1/1/" + ("random.php" if op == "RECIPE_RANDOM" else "search.php?s=" + q(arg)), 0 if op == "RECIPE_RANDOM" else 3600)
        meals = d.get("meals") or []
        if not meals:
            raise NetError(f"I couldn't find a recipe for {arg}.")
        m = meals[0]
        ingredients = [m.get(f"strIngredient{i}") for i in range(1, 21) if (m.get(f"strIngredient{i}") or "").strip()]
        return Answer(f"{m['strMeal']} ({m.get('strArea') or 'international'} {m.get('strCategory') or ''}). You need: " +
                      ", ".join(ingredients[:12]) + ". Say “tell me the answer” for the first steps.",
                      pending=first_sentences(m.get("strInstructions") or "", 3, 500))
    if op == "MOCKTAIL":
        d = get_json("https://www.thecocktaildb.com/api/json/v1/1/filter.php?a=Non_Alcoholic", 86400)
        drinks = d.get("drinks") or []
        if not drinks:
            raise NetError("No drinks right now.")
        import random
        pick = random.choice(drinks)
        full = (get_json(f"https://www.thecocktaildb.com/api/json/v1/1/lookup.php?i={pick['idDrink']}", 86400).get("drinks") or [{}])[0]
        parts = [full.get(f"strIngredient{i}") for i in range(1, 16) if (full.get(f"strIngredient{i}") or "").strip()]
        return Answer(f"Try a {pick['strDrink']}: " + ", ".join(parts) + ".", pending=first_sentences(full.get("strInstructions") or "", 3))
    if op == "BOOK":
        d = get_json("https://openlibrary.org/search.json?limit=1&fields=title,author_name,first_publish_year&q=" + q(arg), 86400)
        docs = d.get("docs") or []
        if not docs:
            raise NetError(f"I couldn't find a book called {arg}.")
        b = docs[0]
        return Answer(f"{b.get('title')} by {', '.join((b.get('author_name') or ['an unknown author'])[:2])}" +
                      (f", first published in {b['first_publish_year']}." if b.get("first_publish_year") else "."))
    if op == "AUTHOR_BOOKS":
        d = get_json("https://openlibrary.org/search.json?limit=8&fields=title,first_publish_year&sort=editions&author=" + q(arg), 86400)
        titles = [x.get("title") for x in d.get("docs") or []][:6]
        if not titles:
            raise NetError(f"I couldn't find books by {arg}.")
        return Answer(f"Books by {arg}: " + ", ".join(titles) + ".")
    if op == "APOD":
        page = read_page("https://apod.nasa.gov/apod/astropix.html", 1500)
        title = next((l.strip() for l in page["text"].splitlines() if l.strip() and "Astronomy Picture of the Day" not in l
                      and not re.search(r"\d{4} \w+ \d{1,2}", l) and len(l) < 90), "")
        return Answer(f"NASA's astronomy picture of the day: {title}." if title else "Opening NASA's astronomy picture of the day.",
                      open_url="https://apod.nasa.gov/apod/astropix.html")
    if op == "ISS":
        d = get_json("https://api.wheretheiss.at/v1/satellites/25544", 0)
        lat, lon = d.get("latitude", 0), d.get("longitude", 0)
        return Answer(f"The space station is over latitude {lat:.1f}, longitude {lon:.1f}, at {d.get('altitude', 0):.0f} km, "
                      f"moving at {d.get('velocity', 0):,.0f} km/h.", open_url=f"https://www.google.com/maps/@{lat:.3f},{lon:.3f},4z")
    if op == "ASTRONAUTS":
        d = get_json("http://api.open-notify.org/astros.json", 3600)
        people = d.get("people") or []
        return Answer(f"{d.get('number', len(people))} people are in space right now: " + ", ".join(p["name"] for p in people[:12]) + ".")
    if op == "QUAKES":
        d = get_json("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson", 600)
        feats = d.get("features") or []
        if not feats:
            return Answer("No earthquakes of magnitude 4.5 or more in the last day.")
        big = max(feats, key=lambda f: f["properties"].get("mag") or 0)["properties"]
        return Answer(f"{len(feats)} earthquakes of magnitude 4.5 or more in the last day. The biggest was {big.get('mag')} "
                      f"{big.get('place')}.")
    if op == "HOLIDAYS":
        country = (s.get("country") or "").strip()
        aliases = {"us": "united states", "usa": "united states", "america": "united states", "uk": "united kingdom",
                   "britain": "united kingdom", "england": "united kingdom", "uae": "united arab emirates"}
        want = aliases.get(country.lower(), country.lower())
        known = get_json("https://date.nager.at/api/v3/AvailableCountries", 86400)
        code = next((c["countryCode"] for c in known if c["name"].lower() == want or c["countryCode"].lower() == want), None)
        if code is None:
            raise NetError(f"I don't have public holidays for {country}. For Indian festivals ask “when is Diwali”.")
        r = request(f"https://date.nager.at/api/v3/NextPublicHolidays/{code}", cache_seconds=86400)
        d = r.json() if r.status == 200 and r.body else []
        if not d:
            raise NetError(f"I don't have public holidays for {country}.")
        return Answer(f"Next public holidays in {country.title()}: " +
                      "; ".join(f"{h['localName']} on {date.fromisoformat(h['date']):%d %B}" for h in d[:4]) + ".")

    # ---- the web itself
    if op == "SEARCH_READ":
        hits = search(arg, 4)
        if not hits:
            raise NetError(f"I found nothing for {arg}.")
        return Answer(f"Top results for {arg}: " + " … ".join(f"{i}. {h.title}" + (f": {first_sentences(h.snippet, 1, 140)}" if h.snippet else "")
                                                               for i, h in enumerate(hits[:3], 1)), pending=hits[0].url)
    if op == "LUCKY":
        hits = search(arg, 1)
        if not hits:
            raise NetError(f"I found nothing for {arg}.")
        return Answer(f"Opening {hits[0].title}.", open_url=hits[0].url)
    if op == "FIND_SITE":
        hits = search(arg + " official website", 3)
        if not hits:
            raise NetError(f"I couldn't find a website for {arg}.")
        host = urllib.parse.urlsplit(hits[0].url).hostname
        return Answer(f"The website for {arg} looks like {host}.", open_url=hits[0].url)
    if op == "PDF":
        hits = [h for h in search(arg + " filetype:pdf", 6) if h.url.lower().split("?")[0].endswith(".pdf")] or search(arg + " pdf", 3)
        if not hits:
            raise NetError(f"I couldn't find a PDF about {arg}.")
        return Answer(f"Opening a PDF: {hits[0].title}.", open_url=hits[0].url)
    if op == "READ_PAGE":
        page = read_page(arg, 2500)
        return Answer((f"{page['title']}. " if page["title"] else "") + first_sentences(page["text"].replace("\n", " "), 4, 700))
    raise NetError("I don't know how to look that up.")


NET_OPS = WEATHER_OPS | {
    "SET_CITY", "WHERE_AM_I", "WIKI", "WIKI_RANDOM", "ON_THIS_DAY", "DEFINE", "SYNONYMS", "ANTONYMS", "RHYMES", "SOUNDS_LIKE",
    "MEANS_LIKE", "ADJECTIVES", "STARTS_WITH", "TRANSLATE", "EXCHANGE", "CRYPTO", "NEWS", "NEWS_TOPIC", "NEWS_ABOUT",
    "HN_TOP", "HN_NEW", "HN_BEST", "HN_ASK", "HN_SHOW", "NPM", "PYPI", "CRATES", "NUGET", "GEMS", "PUB", "BREW", "DOCKER",
    "MAVEN", "GH_REPO", "GH_RELEASE", "GH_USER", "STATUS", "SITE_UP", "HTTP_STATUS", "RESPONSE_TIME", "HEADERS",
    "PAGE_TITLE", "EXPAND_URL", "SSL_EXPIRY", "DNS", "MY_IP", "IP_INFO", "DOMAIN", "SHORTEN", "JOKE", "QUOTE", "ADVICE",
    "USELESS_FACT", "CAT_FACT", "DOG_PHOTO", "CAT_PHOTO", "TRIVIA", "RECIPE_RANDOM", "RECIPE_FOR", "MOCKTAIL", "BOOK", "AUTHOR_BOOKS",
    "APOD", "ISS", "ASTRONAUTS", "QUAKES", "HOLIDAYS", "SEARCH_READ", "LUCKY", "FIND_SITE", "PDF", "READ_PAGE",
    # handled by the brain (they need the AI, a confirmation, or change Echo's settings)
    "RESEARCH", "SUMMARIZE_URL", "DOWNLOAD", "INTERNET_ON", "INTERNET_OFF", "INTERNET_STATUS",
}
BRAIN_NET_OPS = {"RESEARCH", "SUMMARIZE_URL", "DOWNLOAD", "INTERNET_ON", "INTERNET_OFF", "INTERNET_STATUS"}


# ------------------------------------------------------------------------------------------------ AI tools
class InternetTools:
    """Built-in tools for Echo's AI agents (same shape as an MCP hub: tools() and call()).

    search, read and get_json are read-only and run freely; download changes your disk, so the agent asks first.
    """
    SERVER = "internet"

    def __init__(self, enabled: Callable[[], bool] = lambda: True):
        self.enabled = enabled

    def tools(self) -> list:
        if not self.enabled():
            return []
        ro = {"readOnlyHint": True}
        return [
            {"server": self.SERVER, "name": "internet.search", "annotations": ro,
             "description": "Search the web. Returns titles, links and snippets.",
             "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
            {"server": self.SERVER, "name": "internet.read", "annotations": ro,
             "description": "Read a web page as plain text (title, text, and links if asked).",
             "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}, "links": {"type": "boolean"}},
                             "required": ["url"]}},
            {"server": self.SERVER, "name": "internet.get_json", "annotations": ro,
             "description": "GET a public JSON API (e.g. https://api.github.com/..., https://api.open-meteo.com/...).",
             "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
            {"server": self.SERVER, "name": "internet.download",
             "description": "Download a file into the user's Downloads folder (the user is asked first; never opened or run).",
             "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
        ]

    trusted: set = set()

    def call(self, name: str, args: dict) -> str:
        try:
            if name == "internet.search":
                hits = search(str(args.get("query", "")), 8)
                return "\n".join(f"{i}. {h.title}\n   {h.url}\n   {h.snippet[:240]}" for i, h in enumerate(hits, 1)) or "No results."
            if name == "internet.read":
                page = read_page(str(args.get("url", "")), 7000, bool(args.get("links")))
                links = "\n".join(f"- {t}: {u}" for t, u in page["links"][:40]) if args.get("links") else ""
                return f"URL: {page['url']}\nTITLE: {page['title']}\n\n{page['text']}" + (f"\n\nLINKS:\n{links}" if links else "")
            if name == "internet.get_json":
                return json.dumps(get_json(str(args.get("url", "")), 60), ensure_ascii=False)[:7000]
            if name == "internet.download":
                path = download(str(args.get("url", "")))
                return f"Saved to {path} ({path.stat().st_size:,} bytes). Not opened."
        except NetError as e:
            return f"ERROR: {e}"
        except ValueError as e:
            return f"ERROR: {e}"
        return f"ERROR: unknown tool {name}"


class CombinedHub:
    """Built-in internet tools + the user's MCP servers, as one hub for the tool agent."""

    def __init__(self, *hubs):
        self.hubs = [h for h in hubs if h is not None]

    def tools(self) -> list:
        out = []
        for h in self.hubs:
            try:
                out += h.tools()
            except Exception:
                pass
        return out

    @property
    def trusted(self) -> set:
        t = set()
        for h in self.hubs:
            t |= set(getattr(h, "trusted", set()) or set())
        return t

    def route(self, goal: str, k: int = 30) -> list:
        """The tools most likely to help with `goal`: routed hubs give their best k, small hubs give everything."""
        out = []
        for h in self.hubs:
            try:
                out += h.route(goal, k) if hasattr(h, "route") else h.tools()[:60]
            except Exception:
                pass
        return out

    def call(self, name: str, args: dict) -> str:
        for h in self.hubs:
            if any(t["name"] == name for t in h.tools()):
                return h.call(name, args)
        return f"ERROR: unknown tool {name}"
