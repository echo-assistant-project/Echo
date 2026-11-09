"""Encodings, hashes, ids, passwords and tokens. Secrets are returned to the caller only; nothing is stored."""
from __future__ import annotations

import base64
import binascii
import codecs
import gzip
import hashlib
import hmac
import json
import math
import quopri
import re
import secrets
import string
import struct
import time
import urllib.parse
import uuid
import zlib
from typing import Literal

from . import ToolError, tool

C = "encode"


def _b64pad(s: str) -> str:
    s = re.sub(r"\s+", "", s)
    return s + "=" * (-len(s) % 4)


@tool(C, ex={"text": "hello world"}, keys="base64 encode")
def base64_encode(text: str, url_safe: bool = False) -> str:
    """Base64-encode text (UTF-8)."""
    f = base64.urlsafe_b64encode if url_safe else base64.b64encode
    return f(text.encode()).decode()


@tool(C, ex={"data": "aGVsbG8gd29ybGQ="}, keys="base64 decode")
def base64_decode(data: str) -> str:
    """Decode Base64 (normal or URL-safe) to text."""
    try:
        raw = base64.b64decode(_b64pad(data).replace("-", "+").replace("_", "/"))
    except (binascii.Error, ValueError):
        raise ToolError("that isn't valid Base64")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return f"(binary, {len(raw)} bytes) hex: {raw[:64].hex()}"


@tool(C, ex={"text": "hi"}, keys="base32 encode")
def base32_encode(text: str) -> str:
    """Base32-encode text."""
    return base64.b32encode(text.encode()).decode()


@tool(C, ex={"data": "NBUQ===="}, keys="base32 decode")
def base32_decode(data: str) -> str:
    """Decode Base32 to text."""
    s = re.sub(r"\s+", "", data).upper()
    return base64.b32decode(s + "=" * (-len(s) % 8)).decode("utf-8", errors="replace")


@tool(C, ex={"text": "Echo"}, keys="hex encode hexadecimal bytes")
def hex_encode(text: str) -> str:
    """Text to hexadecimal bytes."""
    return text.encode().hex()


@tool(C, ex={"data": "4563686f"}, keys="hex decode hexadecimal")
def hex_decode(data: str) -> str:
    """Hexadecimal bytes to text."""
    try:
        return bytes.fromhex(re.sub(r"[^0-9a-fA-F]", "", data.removeprefix("0x"))).decode("utf-8", errors="replace")
    except ValueError:
        raise ToolError("that isn't valid hex")


@tool(C, ex={"text": "a b&c=d/é"}, keys="url encode percent encoding escape")
def url_encode(text: str, keep_slashes: bool = False) -> str:
    """Percent-encode text for a URL."""
    return urllib.parse.quote(text, safe="/" if keep_slashes else "")


@tool(C, ex={"text": "a%20b%26c"}, keys="url decode percent unescape")
def url_decode(text: str) -> str:
    """Decode percent-encoded URL text (+ as space too)."""
    return urllib.parse.unquote_plus(text)


@tool(C, ex={"text": "<a href=\"x\">Tom & Jerry</a>"}, keys="html escape entities")
def html_escape(text: str) -> str:
    """Escape text for HTML (& < > \")."""
    import html
    return html.escape(text)


@tool(C, ex={"text": "&lt;b&gt;Tom &amp; Jerry&lt;/b&gt; &#8377;"}, keys="html unescape entities decode")
def html_unescape(text: str) -> str:
    """Turn HTML entities back into characters."""
    import html
    return html.unescape(text)


@tool(C, ex={"text": "line 1\n\"quoted\"\ttab"}, keys="json string escape")
def json_escape(text: str) -> str:
    """Escape text as a JSON string literal."""
    return json.dumps(text, ensure_ascii=False)


@tool(C, ex={"text": "\"line 1\\n\\\"quoted\\\"\""}, keys="json string unescape")
def json_unescape(text: str) -> str:
    """Unescape a JSON string literal (with or without the outer quotes)."""
    t = text.strip()
    if not (t.startswith('"') and t.endswith('"')):
        t = '"' + t + '"'
    try:
        return json.loads(t)
    except ValueError as e:
        raise ToolError(f"not a valid JSON string: {e}")


ALGOS = ["md5", "sha1", "sha224", "sha256", "sha384", "sha512", "sha3_256", "sha3_512", "blake2b", "blake2s"]


@tool(C, ex={"text": "hello", "algorithm": "sha256"}, keys="hash checksum digest md5 sha256 sha1")
def hash_text(text: str, algorithm: Literal["md5", "sha1", "sha224", "sha256", "sha384", "sha512", "sha3_256", "sha3_512", "blake2b", "blake2s"] = "sha256") -> str:
    """Hash text (UTF-8) with MD5, SHA-1, SHA-2, SHA-3 or BLAKE2."""
    return hashlib.new(algorithm, text.encode()).hexdigest()


@tool(C, ex={"text": "hello"}, keys="all hashes compare checksums")
def all_hashes(text: str) -> dict:
    """Every common hash of a text at once."""
    return {a: hashlib.new(a, text.encode()).hexdigest() for a in ALGOS}


@tool(C, ex={"key": "secret", "message": "hello"}, keys="hmac signature webhook verify sign")
def hmac_sign(key: str, message: str, algorithm: Literal["sha256", "sha1", "sha512", "md5"] = "sha256") -> str:
    """HMAC signature of a message with a key (as used by webhooks)."""
    return hmac.new(key.encode(), message.encode(), algorithm).hexdigest()


@tool(C, ex={"text": "hello"}, keys="crc32 adler32 checksum")
def crc32_checksum(text: str) -> str:
    """CRC-32 and Adler-32 checksums of text."""
    return f"CRC32 {zlib.crc32(text.encode()) & 0xffffffff:08x}; Adler32 {zlib.adler32(text.encode()) & 0xffffffff:08x}"


@tool(C, ex={"count": 2}, keys="uuid guid unique id generate")
def make_uuid(count: int = 1, uppercase: bool = False) -> str:
    """New random UUIDs (version 4)."""
    out = [str(uuid.uuid4()) for _ in range(max(1, min(count, 50)))]
    return "\n".join(u.upper() if uppercase else u for u in out)


@tool(C, ex={"name": "example.com", "namespace": "dns"}, keys="uuid5 deterministic name based")
def uuid_from_name(name: str, namespace: Literal["dns", "url", "oid", "x500"] = "dns") -> str:
    """Deterministic UUID (version 5) from a name — the same name always gives the same id."""
    ns = {"dns": uuid.NAMESPACE_DNS, "url": uuid.NAMESPACE_URL, "oid": uuid.NAMESPACE_OID, "x500": uuid.NAMESPACE_X500}[namespace]
    return str(uuid.uuid5(ns, name))


@tool(C, ex={"value": "6ba7b810-9dad-11d1-80b4-00c04fd430c8"}, keys="uuid inspect parse version")
def inspect_uuid(value: str) -> str:
    """Check a UUID and say its version."""
    try:
        u = uuid.UUID(value.strip())
    except ValueError:
        raise ToolError("that isn't a UUID")
    return f"Valid UUID, version {u.version}, variant {u.variant}."


CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


@tool(C, ex={}, keys="ulid sortable id")
def make_ulid() -> str:
    """New ULID (sortable by time, 26 characters)."""
    n = (int(time.time() * 1000) << 80) | secrets.randbits(80)
    return "".join(CROCKFORD[(n >> (5 * i)) & 31] for i in range(25, -1, -1))


@tool(C, ex={"length": 21}, keys="nanoid short id random")
def make_short_id(length: int = 21) -> str:
    """Short random URL-safe id (like NanoID)."""
    alphabet = string.ascii_letters + string.digits + "_-"
    return "".join(secrets.choice(alphabet) for _ in range(max(4, min(length, 64))))


@tool(C, ex={"length": 20}, keys="password generate strong random secure")
def make_password(length: int = 16, symbols: bool = True, avoid_lookalikes: bool = False) -> str:
    """A strong random password (returned to you only; not stored)."""
    from ..devtools import password
    if not symbols or avoid_lookalikes:
        pool = string.ascii_letters + string.digits + ("!@#$%^&*-_=+?" if symbols else "")
        if avoid_lookalikes:
            pool = "".join(c for c in pool if c not in "Il1O0o")
        return "".join(secrets.choice(pool) for _ in range(max(8, min(length, 128))))
    return password(max(8, min(length, 64)))


@tool(C, ex={"words": 4}, keys="passphrase memorable password words diceware")
def make_passphrase(words: int = 4, separator: str = "-") -> str:
    """A memorable passphrase of random words."""
    from ..devtools import passphrase
    return passphrase(words).replace("-", separator)


@tool(C, ex={"password": "Summer2024!"}, keys="password strength check secure weak")
def password_strength(password: str) -> str:
    """How strong a password is (estimated guessing effort). It isn't sent or stored anywhere."""
    pool = sum(n for cond, n in ((re.search(r"[a-z]", password), 26), (re.search(r"[A-Z]", password), 26),
                                  (re.search(r"\d", password), 10), (re.search(r"[^A-Za-z0-9]", password), 33)) if cond)
    bits = len(password) * math.log2(pool or 1)
    common = re.search(r"(password|1234|qwerty|admin|welcome|iloveyou|abc123|letmein|monkey)", password.lower())
    if re.search(r"(19|20)\d\d", password) or re.search(r"(.)\1\1", password):
        bits -= 10
    if common:
        bits = min(bits, 20)
    level = "very weak" if bits < 28 else "weak" if bits < 40 else "fair" if bits < 60 else "strong" if bits < 80 else "very strong"
    tips = [] if bits >= 60 else ["make it longer (16+ characters)", "avoid words, names, years and keyboard patterns", "or use a passphrase of 4+ random words"]
    return f"{level.capitalize()} (about {round(max(bits, 0))} bits)." + (" Tips: " + "; ".join(tips) + "." if tips else "")


@tool(C, ex={"bytes_count": 32}, keys="random token secret api key hex")
def random_token(bytes_count: int = 32, style: Literal["hex", "urlsafe", "base64"] = "hex") -> str:
    """Cryptographically random token."""
    n = max(8, min(bytes_count, 128))
    return {"hex": secrets.token_hex, "urlsafe": secrets.token_urlsafe}.get(style, lambda k: base64.b64encode(secrets.token_bytes(k)).decode())(n)


@tool(C, ex={"secret": "JBSWY3DPEHPK3PXP"}, keys="totp 2fa authenticator code otp")
def totp_code(secret: str, digits: int = 6, period: int = 30) -> str:
    """Current 2FA (TOTP) code for a Base32 secret, like an authenticator app."""
    if not 6 <= digits <= 10:
        raise ToolError("TOTP codes have 6 to 10 digits (usually 6)")
    if not 1 <= period <= 600:
        raise ToolError("the period is in seconds, usually 30")
    key = base64.b32decode(re.sub(r"\s", "", secret).upper() + "=" * (-len(re.sub(r"\s", "", secret)) % 8))
    counter = int(time.time() // period)
    h = hmac.new(key, struct.pack(">Q", counter), "sha1").digest()
    o = h[-1] & 0x0F
    code = (struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % 10 ** digits
    return f"{code:0{digits}d} (valid for {period - int(time.time()) % period} more seconds)"


@tool(C, ex={"token": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI0MiIsIm5hbWUiOiJBc2hhIn0.sig"}, keys="jwt decode token claims inspect")
def jwt_decode(token: str) -> dict:
    """Read a JWT's header and claims (signature not verified)."""
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise ToolError("a JWT has three dot-separated parts")
    try:
        header = json.loads(base64.urlsafe_b64decode(_b64pad(parts[0])))
        claims = json.loads(base64.urlsafe_b64decode(_b64pad(parts[1])))
    except (ValueError, binascii.Error):
        raise ToolError("couldn't decode that token")
    for k in ("iat", "exp", "nbf"):
        if isinstance(claims.get(k), (int, float)):
            claims[k + "_readable"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(claims[k]))
    return {"header": header, "claims": claims, "note": "signature not verified"}


@tool(C, ex={"claims": {"sub": "42"}, "secret": "test-secret"}, keys="jwt sign create token hs256")
def jwt_sign(claims: dict, secret: str, expires_minutes: int = 60) -> str:
    """Create an HS256-signed JWT (for testing your own apps)."""
    body = dict(claims)
    now = int(time.time())
    body.setdefault("iat", now)
    if expires_minutes:
        body.setdefault("exp", now + expires_minutes * 60)
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d, separators=(",", ":")).encode()).decode().rstrip("=")
    head = enc({"alg": "HS256", "typ": "JWT"}) + "." + enc(body)
    sig = base64.urlsafe_b64encode(hmac.new(secret.encode(), head.encode(), "sha256").digest()).decode().rstrip("=")
    return head + "." + sig


@tool(C, ex={"text": "hello hello hello hello"}, keys="compress gzip base64 shrink")
def gzip_compress(text: str) -> str:
    """Gzip-compress text and give it back as Base64."""
    raw = gzip.compress(text.encode())
    return f"{base64.b64encode(raw).decode()}\n({len(text.encode())} → {len(raw)} bytes)"


@tool(C, keys="decompress gunzip base64")
def gzip_decompress(data: str) -> str:
    """Decompress Base64 gzip data back to text."""
    try:
        return gzip.decompress(base64.b64decode(_b64pad(data))).decode("utf-8", errors="replace")
    except (OSError, binascii.Error, EOFError):
        raise ToolError("that isn't Base64 gzip data")


@tool(C, ex={"domain": "münchen.de"}, keys="punycode idn international domain")
def punycode(domain: str, decode: bool = False) -> str:
    """Convert an international domain name to/from punycode (xn--…)."""
    try:
        return domain.encode("ascii").decode("idna") if decode else domain.encode("idna").decode("ascii")
    except UnicodeError as e:
        raise ToolError(f"can't convert: {e}")


@tool(C, ex={"text": "café = 5€"}, keys="quoted printable email encoding")
def quoted_printable(text: str, decode: bool = False) -> str:
    """Quoted-printable encoding (used in emails)."""
    return quopri.decodestring(text.encode()).decode("utf-8", errors="replace") if decode else quopri.encodestring(text.encode()).decode()


@tool(C, ex={"text": "Hello", "decode": False}, keys="rot47 obfuscate")
def rot47(text: str) -> str:
    """ROT47 (shifts all printable ASCII; applying it twice gives the original)."""
    return "".join(chr(33 + (ord(c) - 33 + 47) % 94) if 33 <= ord(c) <= 126 else c for c in text)


@tool(C, ex={"text": "€ and ₹"}, keys="unicode escape \\u codepoints")
def unicode_escape(text: str, decode: bool = False) -> str:
    """Write non-ASCII characters as \\uXXXX escapes (or decode them)."""
    if decode:
        return codecs.decode(text, "unicode_escape")
    return text.encode("unicode_escape").decode("ascii")


@tool(C, ex={"length": 6}, keys="otp numeric code verification pin")
def random_pin(length: int = 6) -> str:
    """Random numeric PIN or code."""
    return "".join(str(secrets.randbelow(10)) for _ in range(max(3, min(length, 16))))
