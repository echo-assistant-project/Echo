"""Developer tools that run offline ("dev" kind): ids, passwords, hashes, encodings, timestamps, HTTP codes, ports,
permissions, subnets, colours, versions, cron. Pure functions (clock and randomness injectable), unit-tested.

Each returns a DevResult: what to say, and optionally what to copy to the clipboard. Secrets (passwords, tokens) are
copied but never spoken or shown in full.
"""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import re
import secrets
import string
import urllib.parse
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from .words import many

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def epoch_utc(seconds: float) -> Optional[datetime]:
    """Unix time -> UTC datetime, including before 1970 (datetime.fromtimestamp fails for those on Windows).
    None when it's outside years 1–9999."""
    try:
        return EPOCH + timedelta(seconds=seconds)
    except (OverflowError, ValueError):
        return None


@dataclass
class DevResult:
    text: str
    copy: Optional[str] = None


class DevError(ValueError):
    pass


HTTP_CODES = {
    100: "Continue", 101: "Switching Protocols", 200: "OK", 201: "Created", 202: "Accepted", 204: "No Content",
    206: "Partial Content", 301: "Moved Permanently", 302: "Found (temporary redirect)", 303: "See Other", 304: "Not Modified",
    307: "Temporary Redirect", 308: "Permanent Redirect", 400: "Bad Request", 401: "Unauthorized (not signed in)",
    402: "Payment Required", 403: "Forbidden (signed in but not allowed)", 404: "Not Found", 405: "Method Not Allowed",
    406: "Not Acceptable", 408: "Request Timeout", 409: "Conflict", 410: "Gone", 411: "Length Required",
    412: "Precondition Failed", 413: "Content Too Large", 414: "URI Too Long", 415: "Unsupported Media Type",
    418: "I'm a teapot (a joke code)", 422: "Unprocessable Content (validation failed)", 425: "Too Early", 426: "Upgrade Required",
    428: "Precondition Required", 429: "Too Many Requests (rate limited)", 431: "Request Header Fields Too Large",
    451: "Unavailable For Legal Reasons", 500: "Internal Server Error", 501: "Not Implemented", 502: "Bad Gateway",
    503: "Service Unavailable", 504: "Gateway Timeout", 505: "HTTP Version Not Supported", 507: "Insufficient Storage",
    511: "Network Authentication Required",
}
PORTS = {
    20: "FTP data", 21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP email", 53: "DNS", 67: "DHCP server", 68: "DHCP client",
    69: "TFTP", 80: "HTTP", 110: "POP3 email", 123: "NTP time", 137: "NetBIOS name", 139: "NetBIOS session", 143: "IMAP email",
    161: "SNMP", 389: "LDAP", 443: "HTTPS", 445: "SMB file sharing", 465: "SMTP over TLS", 514: "Syslog",
    587: "SMTP submission", 636: "LDAPS", 853: "DNS over TLS", 993: "IMAPS", 995: "POP3S", 1080: "SOCKS proxy",
    1194: "OpenVPN", 1433: "Microsoft SQL Server", 1521: "Oracle database", 1883: "MQTT", 2049: "NFS", 2375: "Docker (unencrypted)",
    2376: "Docker (TLS)", 3000: "a common dev server port (Node, Grafana, Rails)", 3306: "MySQL", 3389: "Remote Desktop",
    4200: "Angular dev server", 5000: "a common dev server port (Flask, ASP.NET)", 5173: "Vite dev server", 5432: "PostgreSQL",
    5672: "RabbitMQ", 5900: "VNC", 6379: "Redis", 6443: "Kubernetes API", 8000: "a common dev server port (Django, Python)",
    8080: "an alternative HTTP port (proxies, Tomcat)", 8443: "an alternative HTTPS port", 8888: "Jupyter",
    9000: "a common app port (PHP-FPM, SonarQube)", 9090: "Prometheus", 9092: "Kafka", 9200: "Elasticsearch", 11434: "Ollama",
    27017: "MongoDB", 51820: "WireGuard",
}


def _num(slots: dict, key: str = "n") -> int:
    try:
        return int(float(slots.get(key, "")))
    except (TypeError, ValueError):
        raise DevError("I need a number for that.")


def _text(slots: dict) -> str:
    t = (slots.get("q") or "").strip()
    if not t:
        raise DevError("Say the text too.")
    return t


def password(length: int = 16, rng=secrets) -> str:
    length = max(8, min(length, 64))
    pools = [string.ascii_lowercase, string.ascii_uppercase, string.digits, "!@#$%^&*-_=+?"]
    chars = [rng.choice(p) for p in pools]
    everything = "".join(pools)
    chars += [rng.choice(everything) for _ in range(length - len(chars))]
    for i in range(len(chars) - 1, 0, -1):                 # Fisher-Yates with the secure generator
        j = rng.randbelow(i + 1)
        chars[i], chars[j] = chars[j], chars[i]
    return "".join(chars)


def passphrase(words: int = 4, rng=secrets) -> str:
    pool = ("apple river stone cloud tiger mango pencil rocket garden silver window planet coffee lemon forest candle "
            "bridge orange violet thunder pepper dragon marble rabbit castle meadow falcon harbor jungle copper anchor "
            "lantern breeze cactus walnut puzzle saddle timber velvet wizard yellow zebra canyon nickel orbit pixel quartz").split()
    return "-".join(rng.choice(pool) for _ in range(max(3, min(words, 8)))) + "-" + str(rng.randbelow(90) + 10)


def chmod_words(mode: str) -> str:
    if not re.fullmatch(r"[0-7]{3,4}", mode):
        raise DevError("Permissions look like 644 or 755.")
    mode = mode[-3:]
    names = ("owner", "group", "others")
    parts = []
    for who, digit in zip(names, mode):
        d = int(digit)
        rights = [w for bit, w in ((4, "read"), (2, "write"), (1, "execute")) if d & bit]
        parts.append(f"{who} can {' and '.join(rights) if rights else 'do nothing'}")
    symbolic = "".join(("r" if int(d) & 4 else "-") + ("w" if int(d) & 2 else "-") + ("x" if int(d) & 1 else "-") for d in mode)
    return f"{mode} is {symbolic}: " + "; ".join(parts) + "."


def subnet(text: str) -> str:
    t = re.sub(r"\s*(dot|point)\s*", ".", text.strip()).replace(" slash ", "/").replace(" ", "")
    try:
        net = ipaddress.ip_network(t, strict=False)
    except ValueError:
        raise DevError("Say a network like 192.168.1.0/24.")
    if net.version == 4:
        hosts = max(net.num_addresses - 2, 0) if net.prefixlen < 31 else net.num_addresses
        first = net.network_address + (1 if net.prefixlen < 31 else 0)
        last = net.broadcast_address - (1 if net.prefixlen < 31 else 0)
        return (f"{net}: netmask {net.netmask}, {hosts:,} usable hosts from {first} to {last}, broadcast {net.broadcast_address}"
                f"{', a private range' if net.is_private else ''}.")
    return f"{net}: {net.num_addresses:,} addresses, from {net.network_address} to {net.broadcast_address}."


def ip_kind(text: str) -> str:
    t = re.sub(r"\s*(dot|point)\s*", ".", text.strip()).replace(" ", "")
    try:
        ip = ipaddress.ip_address(t)
    except ValueError:
        return f"{text} is not a valid IP address."
    kind = ("loopback (this computer)" if ip.is_loopback else "private (home or office network)" if ip.is_private
            else "link-local" if ip.is_link_local else "multicast" if ip.is_multicast else "public")
    return f"{ip} is a valid IPv{ip.version} address, {kind}."


def hex_to_rgb(text: str) -> str:
    h = re.sub(r"[^0-9a-fA-F]", "", text.replace("hash", ""))
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise DevError("Say a colour like hash ff8800.")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"#{h.lower()} is rgb({r}, {g}, {b})."


def rgb_to_hex(text: str) -> DevResult:
    nums = [int(x) for x in re.findall(r"\d+", text)]
    if len(nums) != 3 or any(n > 255 for n in nums):
        raise DevError("Say three numbers from 0 to 255, like 255 136 0.")
    out = "#%02x%02x%02x" % tuple(nums)
    return DevResult(f"rgb({', '.join(map(str, nums))}) is {out}. Copied.", copy=out)


def _ver(v: str) -> tuple:
    v = v.strip().lstrip("vV")
    main, _, pre = v.partition("-")
    parts = [int(x) for x in re.findall(r"\d+", main)[:3]]
    parts += [0] * (3 - len(parts))
    return tuple(parts) + ((0, pre) if pre else (1, ""),)


def compare_versions(text: str) -> str:
    vs = re.findall(r"v?\d+(?:\.\d+){0,2}(?:-[0-9A-Za-z.]+)?", text.replace(" point ", ".").replace(" dot ", "."))
    if len(vs) < 2:
        raise DevError("Say two versions, like 1.2.10 and 1.10.0.")
    a, b = vs[0], vs[1]
    ka, kb = _ver(a), _ver(b)
    if ka == kb:
        return f"{a} and {b} are the same version."
    newer, older = (a, b) if ka > kb else (b, a)
    return f"{newer} is newer than {older}."


CRON_FIELDS = ("minute", "hour", "day of the month", "month", "day of the week")
DOW = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def explain_cron(text: str) -> str:
    t = text.strip().replace(" star ", " * ").replace("star", "*")
    fields = t.split()
    if len(fields) != 5:
        raise DevError("A cron schedule has five parts: minute hour day month weekday, like 0 9 * * 1.")
    m, h, dom, mon, dow = fields

    def part(value, name):
        if value == "*":
            return None
        if value.startswith("*/"):
            return f"every {value[2:]} {name}s"
        if name == "day of the week" and re.fullmatch(r"[0-7](,[0-7])*", value):
            return "on " + ", ".join(DOW[int(x)] for x in value.split(","))
        if name == "day of the week" and re.fullmatch(r"[0-7]-[0-7]", value):
            a, b = value.split("-")
            return f"{DOW[int(a)]} to {DOW[int(b)]}"
        return f"{name} {value}"
    when = []
    if re.fullmatch(r"\d+", m) and re.fullmatch(r"\d+", h):
        when.append(f"at {int(h):02d}:{int(m):02d}")
    else:
        when += [p for p in (part(m, "minute"), part(h, "hour")) if p]
        if m == "*" and h == "*":
            when.append("every minute")
    when += [p for p in (part(dom, "day of the month"), part(mon, "month"), part(dow, "day of the week")) if p]
    return f"“{t}” runs " + ", ".join(when) + "."


def jwt_payload(token: str) -> str:
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise DevError("That isn't a JWT (it needs three dot-separated parts).")
    import json
    try:
        pad = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(pad))
    except (ValueError, TypeError):
        raise DevError("I couldn't decode that token.")
    bits = []
    for k in ("sub", "name", "email", "iss", "aud", "scope"):
        if k in payload:
            bits.append(f"{k} {payload[k]}")
    for k in ("iat", "exp"):
        if isinstance(payload.get(k), (int, float)):
            when = epoch_utc(payload[k])
            if when is None:
                continue
            label ="issued" if k == "iat" else ("expired" if when < datetime.now(timezone.utc) else "expires")
            bits.append(f"{label} {when:%d %b %Y %H:%M} UTC")
    return "Token claims: " + ("; ".join(bits) if bits else ", ".join(list(payload)[:10])) + ". (Not verified.)"


LOREM = ("lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore et dolore magna "
         "aliqua ut enim ad minim veniam quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat").split()


def run(op: str, slots: dict, now: Optional[datetime] = None, rng=secrets) -> DevResult:
    now = now or datetime.now(timezone.utc)
    if op == "UUID":
        u = str(uuid.UUID(int=rng.randbits(128), version=4))
        return DevResult(f"New UUID copied: {u}", copy=u)
    if op == "PASSWORD":
        n = _num(slots) if slots.get("n") else 16
        pw = password(n, rng)
        return DevResult(f"A strong {len(pw)}-character password is on your clipboard. Paste it where you need it, then copy "
                         f"something else so it doesn't linger.", copy=pw)
    if op == "PASSPHRASE":
        pp = passphrase(4, rng)
        return DevResult("A four-word passphrase is on your clipboard.", copy=pp)
    if op == "TOKEN":
        tok = rng.token_hex(max(8, min(_num(slots) if slots.get("n") else 32, 64)))
        return DevResult(f"A random {len(tok) * 4}-bit hex token is on your clipboard.", copy=tok)
    if op == "PIN":
        digits = max(4, min(_num(slots) if slots.get("n") else 6, 12))
        pin = "".join(str(rng.randbelow(10)) for _ in range(digits))
        return DevResult(f"A random {digits}-digit PIN is on your clipboard.", copy=pin)
    if op == "EPOCH_NOW":
        t = int(now.timestamp())
        return DevResult(f"The Unix time now is {t}. Copied.", copy=str(t))
    if op == "EPOCH_MS":
        t = int(now.timestamp() * 1000)
        return DevResult(f"Milliseconds since 1970: {t}. Copied.", copy=str(t))
    if op == "EPOCH_TO_DATE":
        n = _num(slots)
        if abs(n) > 10 ** 11:
            n = int(n / 1000)                            # milliseconds
        when = epoch_utc(n)
        if when is None:
            return DevResult(f"{n} is too far from 1970 to be a date.")
        local = when + (datetime.now().astimezone().utcoffset() or timedelta(0))
        return DevResult(f"{n} is {when:%A %d %B %Y, %H:%M:%S} UTC, {local:%I:%M %p} your time.")
    if op == "ISO_NOW":
        s = now.astimezone().isoformat(timespec="seconds")
        return DevResult(f"Copied {s}", copy=s)
    if op in ("B64_ENC", "B64_DEC", "URL_ENC", "URL_DEC", "MD5", "SHA1", "SHA256", "SHA512", "HEX_ENC", "LENGTH", "CHAR_CODE", "UPPER_TEXT", "SLUG_TEXT"):
        t = _text(slots)
        if op == "B64_ENC":
            out = base64.b64encode(t.encode()).decode()
        elif op == "B64_DEC":
            try:
                out = base64.b64decode(t.replace(" ", "") + "=" * (-len(t.replace(" ", "")) % 4), validate=False).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                raise DevError("That isn't valid Base64 text.")
        elif op == "URL_ENC":
            out = urllib.parse.quote(t, safe="")
        elif op == "URL_DEC":
            out = urllib.parse.unquote(t)
        elif op in ("MD5", "SHA1", "SHA256", "SHA512"):
            out = hashlib.new(op.lower().replace("sha", "sha"), t.encode()).hexdigest()
            return DevResult(f"The {op} of “{t[:40]}” is copied. It starts {out[:8]}.", copy=out)
        elif op == "HEX_ENC":
            out = t.encode().hex()
        elif op == "LENGTH":
            return DevResult(f"“{t[:60]}” is {many(len(t), 'character')}, {many(len(t.encode()), 'byte')} in UTF-8.")
        elif op == "CHAR_CODE":
            ch = t[0] if len(t) == 1 else t.strip()[:1]
            return DevResult(f"“{ch}” is code {ord(ch)}, hex {ord(ch):X}, Unicode U+{ord(ch):04X}.")
        elif op == "UPPER_TEXT":
            out = t.upper()
        else:
            out = "-".join(re.findall(r"[a-z0-9]+", t.lower()))
        return DevResult(f"Copied: {out[:120]}", copy=out)
    if op == "CODE_CHAR":
        n = _num(slots)
        if not 0 <= n <= 0x10FFFF:
            raise DevError("That's outside Unicode.")
        return DevResult(f"Code {n} is “{chr(n)}”.", copy=chr(n))
    if op == "HTTP_CODE":
        n = _num(slots)
        meaning = HTTP_CODES.get(n)
        if not meaning:
            family = {1: "informational", 2: "success", 3: "redirect", 4: "client error", 5: "server error"}.get(n // 100)
            if not family:
                raise DevError(f"{n} isn't an HTTP status code.")
            return DevResult(f"{n} is a {family} code.")
        return DevResult(f"HTTP {n} means {meaning}.")
    if op == "PORT":
        n = _num(slots)
        if not 0 <= n <= 65535:
            raise DevError("Ports go from 0 to 65535.")
        known = PORTS.get(n)
        if known:
            return DevResult(f"Port {n} is usually {known}.")
        band = "a well-known system port" if n < 1024 else "a registered port" if n < 49152 else "a dynamic (temporary) port"
        return DevResult(f"Port {n} has no standard use I know; it's {band}.")
    if op == "CHMOD":
        return DevResult(chmod_words(str(_num(slots))))
    if op == "SUBNET":
        return DevResult(subnet(_text(slots)))
    if op == "IP_CHECK":
        return DevResult(ip_kind(_text(slots)))
    if op == "HEX_TO_RGB":
        return DevResult(hex_to_rgb(_text(slots)))
    if op == "RGB_TO_HEX":
        return rgb_to_hex(_text(slots))
    if op == "SEMVER":
        return DevResult(compare_versions(_text(slots)))
    if op == "CRON":
        return DevResult(explain_cron(_text(slots)))
    if op == "LOREM":
        n = max(1, min(_num(slots) if slots.get("n") else 50, 500))
        words = [LOREM[i % len(LOREM)] for i in range(n)]
        out = " ".join(words).capitalize() + "."
        return DevResult(f"{many(n, 'word')} of placeholder text copied.", copy=out)
    if op == "BYTES":
        n = float(slots.get("n") or 0)
        unit = (slots.get("u") or "").lower().rstrip("s")
        powers = {"byte": 0, "kilobyte": 1, "kb": 1, "kib": 1, "megabyte": 2, "mb": 2, "mib": 2, "gigabyte": 3, "gb": 3,
                  "gib": 3, "terabyte": 4, "tb": 4, "tib": 4}
        if unit not in powers:
            raise DevError("Say bytes, kilobytes, megabytes, gigabytes or terabytes.")
        b = n * 1024 ** powers[unit]
        return DevResult(f"{n:g} {unit}s is {b:,.0f} bytes (binary, 1024-based), or {n * 1000 ** powers[unit]:,.0f} in decimal units.")
    if op == "BINARY_OF":
        n = _num(slots)
        return DevResult(f"{n} in binary is {n:b}, in hex {n:X}, in octal {n:o}.")
    raise DevError("I don't know that developer tool.")


DEV_OPS = {"UUID", "PASSWORD", "PASSPHRASE", "TOKEN", "PIN", "EPOCH_NOW", "EPOCH_MS", "EPOCH_TO_DATE", "ISO_NOW", "B64_ENC",
           "B64_DEC", "URL_ENC", "URL_DEC", "MD5", "SHA1", "SHA256", "SHA512", "HEX_ENC", "LENGTH", "CHAR_CODE", "UPPER_TEXT",
           "SLUG_TEXT", "CODE_CHAR", "HTTP_CODE", "PORT", "CHMOD", "SUBNET", "IP_CHECK", "HEX_TO_RGB", "RGB_TO_HEX", "SEMVER",
           "CRON", "LOREM", "BYTES", "BINARY_OF"}
