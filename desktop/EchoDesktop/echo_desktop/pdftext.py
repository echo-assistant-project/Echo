"""Text out of PDF files, with the standard library only (Echo ships without third-party packages).

Handles what most real PDFs use: compressed streams (Flate, LZW, ASCII85, ASCIIHex), compressed object streams
(PDF 1.5+), the page tree with inherited resources, fonts with ToUnicode maps (Chrome, Word, LaTeX) and simple
fonts with /Differences, form XObjects, and TJ kerning turned into spaces. It only ever reads: nothing in a PDF is
run. Limits keep a hostile file harmless (stream size cap against zip bombs, page and depth caps).

Not handled, and said plainly: encrypted PDFs, and scanned pages (pictures of text, no text inside).
"""
from __future__ import annotations

import re
import zlib
from typing import Optional

MAX_STREAM = 40_000_000        # bytes after decompression, per stream
MAX_PAGES = 1000
MAX_CHARS = 3_000_000


class PdfError(Exception):
    """A clear, user-facing reason the PDF can't be read."""


class Ref:
    __slots__ = ("num",)

    def __init__(self, num: int):
        self.num = num

    def __repr__(self):
        return f"Ref({self.num})"


class Stream:
    __slots__ = ("d", "raw")

    def __init__(self, d: dict, raw: bytes):
        self.d, self.raw = d, raw


# ------------------------------------------------------------------------------------------------ lexer
_WS = b" \t\r\n\x00\x0c"
_DELIM = b"()<>[]{}/%"
_NUM = re.compile(rb"[+-]?(?:\d+\.?\d*|\.\d+)")
_REGULAR = re.compile(rb"[^ \t\r\n\x00\x0c()<>\[\]{}/%]+")
_ESC = {ord("n"): b"\n", ord("r"): b"\r", ord("t"): b"\t", ord("b"): b"\b", ord("f"): b"\f",
        ord("("): b"(", ord(")"): b")", ord("\\"): b"\\"}


class Lexer:
    """Tokens: ('num', v) ('name', '/X') ('str', bytes) ('[',) (']',) ('<<',) ('>>',) ('kw', 'Tj') ('eof',)."""

    def __init__(self, data: bytes, pos: int = 0):
        self.data, self.pos = data, pos

    def _skip(self):
        d, n = self.data, len(self.data)
        while self.pos < n:
            c = d[self.pos]
            if c in _WS:
                self.pos += 1
            elif c == 0x25:                      # % comment
                end = d.find(b"\n", self.pos)
                e2 = d.find(b"\r", self.pos)
                ends = [x for x in (end, e2) if x != -1]
                self.pos = min(ends) if ends else n
            else:
                break

    def next(self):
        self._skip()
        d, i = self.data, self.pos
        if i >= len(d):
            return ("eof",)
        c = d[i]
        if c == 0x28:                            # (
            return ("str", self._literal())
        if c == 0x3C:                            # <
            if d[i + 1:i + 2] == b"<":
                self.pos += 2
                return ("<<",)
            end = d.find(b">", i)
            end = len(d) if end == -1 else end
            hx = re.sub(rb"[^0-9A-Fa-f]", b"", d[i + 1:end])
            self.pos = end + 1
            if len(hx) % 2:
                hx += b"0"
            return ("str", bytes.fromhex(hx.decode()))
        if c == 0x3E:                            # >
            self.pos += 2 if d[i + 1:i + 2] == b">" else 1
            return (">>",)
        if c in b"[]{}":
            self.pos += 1
            return (chr(c),)
        if c == 0x2F:                            # /name
            m = _REGULAR.match(d, i + 1)
            raw = m.group(0) if m else b""
            self.pos = i + 1 + len(raw)
            name = re.sub(rb"#([0-9A-Fa-f]{2})", lambda g: bytes([int(g.group(1), 16)]), raw)
            return ("name", "/" + name.decode("latin-1"))
        if c == 0x29:                            # stray )
            self.pos += 1
            return self.next()
        m = _REGULAR.match(d, i)
        tok = m.group(0)
        self.pos = i + len(tok)
        if _NUM.fullmatch(tok):
            return ("num", float(tok) if b"." in tok else int(tok))
        return ("kw", tok.decode("latin-1"))

    def _literal(self) -> bytes:
        d, i, depth, out = self.data, self.pos + 1, 1, bytearray()
        n = len(d)
        while i < n:
            c = d[i]
            if c == 0x5C:                        # backslash
                i += 1
                if i >= n:
                    break
                e = d[i]
                if e in _ESC:
                    out += _ESC[e]
                    i += 1
                elif 0x30 <= e <= 0x37:
                    m = re.match(rb"[0-7]{1,3}", d[i:i + 3])
                    out.append(int(m.group(0), 8) & 0xFF)
                    i += len(m.group(0))
                elif e == 0x0D:
                    i += 2 if d[i + 1:i + 2] == b"\n" else 1
                elif e == 0x0A:
                    i += 1
                else:
                    out.append(e)
                    i += 1
                continue
            if c == 0x28:
                depth += 1
            elif c == 0x29:
                depth -= 1
                if depth == 0:
                    i += 1
                    break
            out.append(c)
            i += 1
        self.pos = i
        return bytes(out)


def parse_value(lx: Lexer, tok=None):
    """One PDF object (dicts, arrays, numbers, names, strings, refs, true/false/null)."""
    tok = tok or lx.next()
    kind = tok[0]
    if kind == "num":
        if isinstance(tok[1], int):              # maybe "n g R"
            save = lx.pos
            t2 = lx.next()
            if t2[0] == "num" and isinstance(t2[1], int):
                t3 = lx.next()
                if t3 == ("kw", "R"):
                    return Ref(tok[1])
            lx.pos = save
        return tok[1]
    if kind in ("name", "str"):
        return tok[1]
    if kind == "[":
        out = []
        for _ in range(1_000_000):
            t = lx.next()
            if t[0] in ("]", "eof"):
                break
            out.append(parse_value(lx, t))
        return out
    if kind == "<<":
        d = {}
        for _ in range(1_000_000):
            t = lx.next()
            if t[0] in (">>", "eof"):
                break
            if t[0] != "name":
                continue
            v = lx.next()
            if v[0] in (">>", "eof"):
                d[t[1]] = None
                break
            d[t[1]] = parse_value(lx, v)
        return d
    if kind == "kw":
        return {"true": True, "false": False, "null": None}.get(tok[1], tok[1])
    return None


# ------------------------------------------------------------------------------------------------ filters
def _lzw(data: bytes) -> bytes:
    out, table, bits, buf, nbits, prev = bytearray(), [bytes([i]) for i in range(256)] + [b"", b""], 9, 0, 0, b""
    for byte in data:
        buf, nbits = (buf << 8) | byte, nbits + 8
        while nbits >= bits:
            nbits -= bits
            code = (buf >> nbits) & ((1 << bits) - 1)
            if code == 256:                      # clear
                table, bits, prev = table[:258], 9, b""
                continue
            if code == 257:                      # end
                return bytes(out)
            if code < len(table):
                entry = table[code]
                if prev:
                    table.append(prev + entry[:1])
            elif prev:
                entry = prev + prev[:1]
                table.append(entry)
            else:
                continue
            out += entry
            if len(out) > MAX_STREAM:
                raise PdfError("a part of this PDF is too big to read")
            prev = entry
            if len(table) + 1 >= (1 << bits) and bits < 12:
                bits += 1
    return bytes(out)


def _a85(data: bytes) -> bytes:
    data = re.sub(rb"\s", b"", data)
    if data.startswith(b"<~"):
        data = data[2:]
    end = data.find(b"~>")
    if end != -1:
        data = data[:end]
    out, group = bytearray(), []
    for c in data:
        if c == ord("z") and not group:
            out += b"\0\0\0\0"
            continue
        if not 33 <= c <= 117:
            continue
        group.append(c - 33)
        if len(group) == 5:
            v = 0
            for g in group:
                v = v * 85 + g
            out += (v & 0xFFFFFFFF).to_bytes(4, "big")
            group = []
    if group:
        n = len(group)
        group += [84] * (5 - n)
        v = 0
        for g in group:
            v = v * 85 + g
        out += (v & 0xFFFFFFFF).to_bytes(4, "big")[:n - 1]
    return bytes(out)


def _unpredict(data: bytes, parms: dict) -> bytes:
    pred = int((parms or {}).get("/Predictor", 1) or 1)
    if pred < 10:
        return data
    cols = int(parms.get("/Columns", 1) or 1) * max(1, int(parms.get("/Colors", 1) or 1)) * \
        max(1, int(parms.get("/BitsPerComponent", 8) or 8)) // 8
    bpp = max(1, max(1, int(parms.get("/Colors", 1) or 1)) * max(1, int(parms.get("/BitsPerComponent", 8) or 8)) // 8)
    out, prev, row = bytearray(), bytearray(cols), cols + 1
    for i in range(0, len(data) - row + 1, row):
        ft, cur = data[i], bytearray(data[i + 1:i + row])
        for x in range(cols):
            a = cur[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if ft == 1:
                cur[x] = (cur[x] + a) & 0xFF
            elif ft == 2:
                cur[x] = (cur[x] + b) & 0xFF
            elif ft == 3:
                cur[x] = (cur[x] + (a + b) // 2) & 0xFF
            elif ft == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                cur[x] = (cur[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 0xFF
        out += cur
        prev = cur
    return bytes(out)


def _as_list(v) -> list:
    return v if isinstance(v, list) else [] if v is None else [v]


# ------------------------------------------------------------------------------------------------ document
_OBJ = re.compile(rb"(\d+)\s+(\d+)\s+obj\b")


class Document:
    def __init__(self, data: bytes):
        if not data.lstrip()[:5].startswith(b"%PDF"):
            raise PdfError("that file isn't a PDF")
        self.data = data
        self.objects: dict = {}
        self._scan()
        self._object_streams()
        if re.search(rb"/Encrypt\s+\d+\s+\d+\s+R", data) or re.search(rb"/Encrypt\s*<<", data):
            raise PdfError("this PDF is encrypted (password-protected), so I can't read its text")

    def _scan(self) -> None:
        d, pos = self.data, 0
        while True:
            m = _OBJ.search(d, pos)
            if not m:
                break
            num = int(m.group(1))
            lx = Lexer(d, m.end())
            try:
                value = parse_value(lx)
            except (IndexError, ValueError, RecursionError):
                pos = m.end()
                continue
            save = lx.pos
            tok = lx.next()
            if tok == ("kw", "stream") and isinstance(value, dict):
                start = lx.pos
                if d[start:start + 2] == b"\r\n":
                    start += 2
                elif d[start:start + 1] in (b"\n", b"\r"):
                    start += 1
                length = value.get("/Length")
                end = -1
                if isinstance(length, int) and 0 <= length and re.match(rb"\s*endstream", d[start + length:start + length + 20]):
                    end = start + length
                if end == -1:
                    end = d.find(b"endstream", start)
                    if end == -1:
                        end = len(d)
                    while end > start and d[end - 1:end] in (b"\n", b"\r"):
                        end -= 1
                self.objects[num] = Stream(value, d[start:end])
                pos = end
            else:
                lx.pos = save
                self.objects[num] = value
                pos = max(lx.pos, m.end())

    def _object_streams(self) -> None:
        for obj in list(self.objects.values()):
            if not (isinstance(obj, Stream) and obj.d.get("/Type") == "/ObjStm"):
                continue
            try:
                data = self.decode(obj)
                n, first = int(obj.d.get("/N", 0)), int(obj.d.get("/First", 0))
                lx = Lexer(data)
                pairs = []
                for _ in range(n):
                    a, b = lx.next(), lx.next()
                    if a[0] != "num" or b[0] != "num":
                        break
                    pairs.append((int(a[1]), int(b[1])))
                for num, off in pairs:
                    if num not in self.objects:
                        self.objects[num] = parse_value(Lexer(data, first + off))
            except (PdfError, ValueError, IndexError, zlib.error, RecursionError):
                continue

    def get(self, v, depth: int = 0):
        while isinstance(v, Ref) and depth < 32:
            v = self.objects.get(v.num)
            depth += 1
        return v

    def decode(self, s: Stream) -> bytes:
        data = s.raw
        filters = [self.get(f) for f in _as_list(self.get(s.d.get("/Filter")))]
        parms = [self.get(p) for p in _as_list(self.get(s.d.get("/DecodeParms")))]
        for i, f in enumerate(filters):
            p = parms[i] if i < len(parms) and isinstance(parms[i], dict) else {}
            if f in ("/FlateDecode", "/Fl"):
                z = zlib.decompressobj()
                try:
                    data = z.decompress(data, MAX_STREAM)
                except zlib.error:
                    data = _inflate_lenient(data)
                if z.unconsumed_tail:
                    raise PdfError("a part of this PDF is too big to read")
                data = _unpredict(data, p)
            elif f in ("/LZWDecode", "/LZW"):
                data = _unpredict(_lzw(data), p)
            elif f in ("/ASCII85Decode", "/A85"):
                data = _a85(data)
            elif f in ("/ASCIIHexDecode", "/AHx"):
                hx = re.sub(rb"[^0-9A-Fa-f]", b"", data.split(b">")[0])
                data = bytes.fromhex((hx + b"0" * (len(hx) % 2)).decode())
            else:
                raise PdfError(f"unsupported filter {f}")       # images (DCT, JBIG2…): not text
        return data

    # ---- pages
    def pages(self) -> list:
        """(page dict, inherited resources) in reading order."""
        root = None
        for m in re.finditer(rb"/Root\s+(\d+)\s+\d+\s+R", self.data):
            root = self.get(Ref(int(m.group(1))))           # the last trailer wins (incremental updates)
        if not isinstance(root, dict):
            root = next((o for o in self.objects.values() if isinstance(o, dict) and o.get("/Type") == "/Catalog"), None)
        out: list = []
        seen: set = set()

        def walk(node_ref, inherited, depth):
            node = self.get(node_ref)
            key = node_ref.num if isinstance(node_ref, Ref) else id(node)
            if not isinstance(node, dict) or key in seen or depth > 64 or len(out) >= MAX_PAGES:
                return
            seen.add(key)
            res = self.get(node.get("/Resources")) or inherited
            if node.get("/Type") == "/Pages" or "/Kids" in node:
                for kid in _as_list(self.get(node.get("/Kids"))):
                    walk(kid, res, depth + 1)
            else:
                out.append((node, res))
        if isinstance(root, dict) and root.get("/Pages") is not None:
            walk(root.get("/Pages"), None, 0)
        if not out:                                           # no usable page tree: every page object, in file order
            for num in sorted(self.objects):
                o = self.objects[num]
                if isinstance(o, dict) and o.get("/Type") == "/Page" and len(out) < MAX_PAGES:
                    out.append((o, self.get(o.get("/Resources"))))
        return out

    def page_text(self, page: dict, resources) -> str:
        parts = []
        for c in _as_list(self.get(page.get("/Contents"))):
            s = self.get(c)
            if isinstance(s, Stream):
                try:
                    parts.append(self.decode(s))
                except (PdfError, zlib.error, ValueError):
                    continue
        return TextRun(self).run(b"\n".join(parts), resources)


def _inflate_lenient(data: bytes) -> bytes:
    """A damaged Flate stream: keep what decompresses before the damage."""
    out = bytearray()
    z = zlib.decompressobj()
    for i in range(0, len(data), 1024):
        try:
            out += z.decompress(data[i:i + 1024])
        except zlib.error:
            break
        if len(out) > MAX_STREAM:
            raise PdfError("a part of this PDF is too big to read")
    return bytes(out)


# ------------------------------------------------------------------------------------------------ fonts
_GLYPHS = {"space": " ", "quoteright": "’", "quoteleft": "‘", "quotedblleft": "“", "quotedblright": "”",
           "quotesingle": "'", "quotedbl": '"', "endash": "–", "emdash": "—", "bullet": "•", "fi": "fi",
           "fl": "fl", "ff": "ff", "ffi": "ffi", "ffl": "ffl", "hyphen": "-", "minus": "-", "period": ".", "comma": ",",
           "colon": ":", "semicolon": ";", "exclam": "!", "question": "?", "parenleft": "(", "parenright": ")",
           "bracketleft": "[", "bracketright": "]", "slash": "/", "backslash": "\\", "ampersand": "&", "at": "@",
           "numbersign": "#", "dollar": "$", "percent": "%", "asterisk": "*", "plus": "+", "equal": "=", "less": "<",
           "greater": ">", "underscore": "_", "ellipsis": "…", "copyright": "©", "registered": "®",
           "trademark": "™", "degree": "°", "rupee": "₹", "Euro": "€", "sterling": "£",
           "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
           "eight": "8", "nine": "9"}


def glyph_char(name: str) -> str:
    n = name.lstrip("/")
    if n in _GLYPHS:
        return _GLYPHS[n]
    if len(n) == 1:
        return n
    m = re.fullmatch(r"uni([0-9A-Fa-f]{4})+", n)
    if m:
        return "".join(chr(int(n[i:i + 4], 16)) for i in range(3, len(n), 4))
    m = re.fullmatch(r"u([0-9A-Fa-f]{4,6})", n)
    if m:
        try:
            return chr(int(m.group(1), 16))
        except ValueError:
            return ""
    return ""


def _utf16(b: bytes) -> str:
    try:
        return (b if len(b) % 2 == 0 else b + b"\0").decode("utf-16-be")
    except UnicodeDecodeError:
        return ""


def parse_cmap(data: bytes) -> tuple:
    """A ToUnicode CMap -> ({code: text}, code width in bytes)."""
    lx, table, width, mode, buf = Lexer(data), {}, 0, None, []
    for _ in range(2_000_000):
        t = lx.next()
        if t[0] == "eof":
            break
        if t[0] == "kw":
            k = t[1]
            if k in ("begincodespacerange", "beginbfchar", "beginbfrange"):
                mode, buf = k, []
            elif k == "endcodespacerange":
                for i in range(0, len(buf) - 1, 2):
                    if isinstance(buf[i], bytes):
                        width = max(width, len(buf[i]))
                mode = None
            elif k == "endbfchar":
                for i in range(0, len(buf) - 1, 2):
                    src, dst = buf[i], buf[i + 1]
                    if isinstance(src, bytes):
                        width = width or len(src)
                        table[int.from_bytes(src, "big")] = _utf16(dst) if isinstance(dst, bytes) else glyph_char(str(dst))
                mode = None
            elif k == "endbfrange":
                for i in range(0, len(buf) - 2, 3):
                    lo, hi, dst = buf[i], buf[i + 1], buf[i + 2]
                    if not (isinstance(lo, bytes) and isinstance(hi, bytes)):
                        continue
                    width = width or len(lo)
                    a, b = int.from_bytes(lo, "big"), int.from_bytes(hi, "big")
                    if b < a or b - a > 65535:
                        continue
                    if isinstance(dst, list):
                        for j, d in enumerate(dst[:b - a + 1]):
                            if isinstance(d, bytes):
                                table[a + j] = _utf16(d)
                    elif isinstance(dst, bytes):
                        base = _utf16(dst)
                        if base:
                            head, last = base[:-1], ord(base[-1])
                            for j in range(b - a + 1):
                                if last + j <= 0x10FFFF:
                                    table[a + j] = head + chr(last + j)
                mode = None
            continue
        if mode:
            if t[0] == "[":
                buf.append(parse_value(lx, t))
            else:
                buf.append(t[1] if len(t) > 1 else None)
    return table, width or 1


class Font:
    def __init__(self, doc: Document, fd):
        fd = doc.get(fd) if fd is not None else None
        fd = fd if isinstance(fd, dict) else {}
        self.cmap: dict = {}
        self.width = 2 if fd.get("/Subtype") == "/Type0" else 1
        self.diffs: dict = {}
        self.unknown = False
        tu = doc.get(fd.get("/ToUnicode"))
        if isinstance(tu, Stream):
            try:
                self.cmap, self.width = parse_cmap(doc.decode(tu))
            except (PdfError, zlib.error, ValueError, IndexError):
                self.cmap = {}
        # glyph widths (thousandths of the font size), to tell a word gap from letters placed one by one
        self.widths: dict = {}
        self.default_width = 500
        if fd.get("/Subtype") == "/Type0":
            desc = _as_list(doc.get(fd.get("/DescendantFonts")))
            cid = doc.get(desc[0]) if desc else None
            if isinstance(cid, dict):
                self.default_width = cid.get("/DW", 1000) if isinstance(cid.get("/DW", 1000), (int, float)) else 1000
                w = _as_list(doc.get(cid.get("/W")))
                i = 0
                while i < len(w) - 1 and len(self.widths) < 100_000:
                    first, nxt = doc.get(w[i]), doc.get(w[i + 1])
                    if isinstance(first, int) and isinstance(nxt, list):
                        for j, v in enumerate(nxt):
                            if isinstance(v, (int, float)):
                                self.widths[first + j] = v
                        i += 2
                    elif isinstance(first, int) and isinstance(nxt, int) and i + 2 < len(w):
                        v = doc.get(w[i + 2])
                        if isinstance(v, (int, float)) and 0 <= nxt - first <= 65535:
                            for c in range(first, nxt + 1):
                                self.widths[c] = v
                        i += 3
                    else:
                        break
        else:
            fc = fd.get("/FirstChar", 0)
            ws = doc.get(fd.get("/Widths"))
            if isinstance(fc, int) and isinstance(ws, list):
                for j, v in enumerate(ws):
                    v = doc.get(v)
                    if isinstance(v, (int, float)):
                        self.widths[fc + j] = v
        enc = doc.get(fd.get("/Encoding"))
        if isinstance(enc, dict):
            code = 0
            for item in _as_list(doc.get(enc.get("/Differences"))):
                if isinstance(item, int):
                    code = item
                elif isinstance(item, str) and item.startswith("/"):
                    ch = glyph_char(item)
                    if ch:
                        self.diffs[code] = ch
                    code += 1
        self.unknown = self.width == 2 and not self.cmap      # e.g. Identity-H with no ToUnicode: no way to know the letters

    def text(self, b: bytes) -> str:
        if self.unknown:
            return ""
        w, out = self.width, []
        for i in range(0, len(b) - w + 1, w):
            code = int.from_bytes(b[i:i + w], "big")
            ch = self.cmap.get(code)
            if ch is None:
                ch = self.diffs.get(code)
            if ch is None:
                ch = bytes([code]).decode("cp1252", "replace").replace("�", "") if w == 1 and code > 31 else ""
            out.append(ch)
        return "".join(out)

    def advance(self, b: bytes) -> float:
        """Width of these bytes in thousandths of the font size."""
        w = self.width
        return sum(self.widths.get(int.from_bytes(b[i:i + w], "big"), self.default_width) for i in range(0, len(b) - w + 1, w))


# ------------------------------------------------------------------------------------------------ content streams
class TextRun:
    def __init__(self, doc: Document):
        self.doc = doc
        self.out: list = []
        self.fonts: dict = {}
        self.last = None              # (x, y) where the last shown string ended

    def _emit(self, s: str):
        if s:
            self.out.append(s)

    def _newline(self):
        if self.out and not self.out[-1].endswith("\n"):
            self.out.append("\n")

    def _space(self):
        if self.out and not self.out[-1].endswith((" ", "\n")):
            self.out.append(" ")

    def run(self, content: bytes, resources, depth: int = 0) -> str:
        self._run(content, resources, depth)
        text = "".join(self.out)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return re.sub(r"[ \t]{2,}", " ", text).strip()

    def _font(self, resources, name):
        res = self.doc.get(resources) if resources is not None else None
        fonts = self.doc.get(res.get("/Font")) if isinstance(res, dict) else None
        ref = fonts.get(name) if isinstance(fonts, dict) else None
        key = ref.num if isinstance(ref, Ref) else (id(fonts), name)
        if key not in self.fonts:
            self.fonts[key] = Font(self.doc, ref)
        return self.fonts[key]

    def _show(self, st: dict, font: "Font", b: bytes) -> None:
        """Show a string at the current text position: a new line when y moved, a space when there's a gap."""
        a, d, size = st["a"], st["d"], st["size"]
        x, y = st["x"], st["y"]
        unit = max(abs(size * a), abs(size * d), 0.01)
        last = self.last
        if last is not None:
            lx_, ly = last
            if abs(y - ly) > 0.5 * unit:
                self._newline()
            elif x - lx_ > 0.15 * unit or x - lx_ < -3 * unit:
                self._space()
        self._emit(font.text(b))
        st["x"] = x + font.advance(b) / 1000.0 * size * a
        self.last = (st["x"], y)

    def _run(self, content: bytes, resources, depth: int) -> None:
        if depth > 6:
            return
        lx, stack = Lexer(content), []
        font = Font(self.doc, None)
        st = {"a": 1.0, "d": 1.0, "x": 0.0, "y": 0.0, "lx": 0.0, "ly": 0.0, "size": 10.0, "tl": 0.0}
        num = (int, float)

        def move(tx, ty):
            st["lx"] += tx * st["a"]
            st["ly"] += ty * st["d"]
            st["x"], st["y"] = st["lx"], st["ly"]
        for _ in range(5_000_000):
            t = lx.next()
            kind = t[0]
            if kind == "eof":
                break
            if kind != "kw":
                if kind in ("[", "<<"):
                    stack.append(parse_value(lx, t))
                elif kind not in ("]", ">>"):
                    stack.append(t[1])
                continue
            op = t[1]
            args, stack = stack, []
            if op == "Tf" and len(args) >= 2 and isinstance(args[-2], str):
                font = self._font(resources, args[-2])
                if isinstance(args[-1], num):
                    st["size"] = args[-1]
            elif op == "Tj" and args and isinstance(args[-1], bytes):
                self._show(st, font, args[-1])
            elif op in ("'", '"') and args and isinstance(args[-1], bytes):
                move(0, -st["tl"])
                self._show(st, font, args[-1])
            elif op == "TJ" and args and isinstance(args[-1], list):
                for item in args[-1]:
                    if isinstance(item, bytes):
                        self._show(st, font, item)
                    elif isinstance(item, num):
                        st["x"] -= item / 1000.0 * st["size"] * st["a"]
            elif op in ("Td", "TD") and len(args) >= 2 and all(isinstance(v, num) for v in args[-2:]):
                if op == "TD":
                    st["tl"] = -args[-1]
                move(args[-2], args[-1])
            elif op == "Tm" and len(args) >= 6 and all(isinstance(v, num) for v in args[-6:]):
                a, _, _, d, e, f = args[-6:]
                st["a"], st["d"] = a or 1.0, d or 1.0
                st["lx"], st["ly"] = st["x"], st["y"] = e, f
            elif op == "TL" and args and isinstance(args[-1], num):
                st["tl"] = args[-1]
            elif op == "T*":
                move(0, -st["tl"])
            elif op == "BT":
                st["a"], st["d"], st["lx"], st["ly"], st["x"], st["y"] = 1.0, 1.0, 0.0, 0.0, 0.0, 0.0
            elif op == "Do" and args and isinstance(args[-1], str):
                self._xobject(resources, args[-1], depth)
            elif op == "BI":                                   # inline image: skip its bytes
                end = re.compile(rb"\sEI(?=[\s]|$)").search(content, lx.pos)
                lx.pos = end.end() if end else len(content)

    def _xobject(self, resources, name, depth):
        res = self.doc.get(resources) if resources is not None else None
        xo = self.doc.get(res.get("/XObject")) if isinstance(res, dict) else None
        s = self.doc.get(xo.get(name)) if isinstance(xo, dict) else None
        if isinstance(s, Stream) and s.d.get("/Subtype") == "/Form":
            try:
                data = self.doc.decode(s)
            except (PdfError, zlib.error, ValueError):
                return
            self._newline()
            self.last = None
            self._run(data, self.doc.get(s.d.get("/Resources")) or resources, depth + 1)
            self._newline()
            self.last = None


# ------------------------------------------------------------------------------------------------ public
def extract(data: bytes, max_chars: int = MAX_CHARS, pages: Optional[int] = None) -> str:
    """All the text of a PDF, page by page ("\\f" between pages). Raises PdfError with a plain reason."""
    doc = Document(data)
    out, total = [], 0
    page_list = doc.pages()
    if not page_list:
        raise PdfError("I couldn't find any pages in this PDF (it may be damaged)")
    for page, res in page_list[:pages or MAX_PAGES]:
        try:
            text = doc.page_text(page, res)
        except RecursionError:
            text = ""
        out.append(text)
        total += len(text)
        if total >= max_chars:
            break
    joined = "\f".join(out)
    if not joined.replace("\f", "").strip():
        raise PdfError("this PDF has no text inside; it's probably scanned pages (pictures of text)")
    return joined[:max_chars]


def read(path, max_chars: int = MAX_CHARS) -> str:
    with open(path, "rb") as f:
        return extract(f.read(), max_chars)
