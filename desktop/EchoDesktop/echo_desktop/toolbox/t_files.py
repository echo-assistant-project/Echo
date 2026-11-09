"""Files and folders on this PC.

Fence: Windows, Program Files, ProgramData, Echo's own data and ~/.ssh are off-limits, and files that hold secrets
(.env, keys, credentials, password databases) are never read or written. Reading works on your folders and other
drives; anything that creates, changes, moves or deletes files is limited to your user folders and the workspaces you
set in Settings, and asks you first. Deleting goes to the Recycle Bin.
"""
from __future__ import annotations

import csv
import fnmatch
import hashlib
import os
import re
import shutil
import struct
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Literal

from . import ToolError, fmt, tool
from ..words import many

C = "files"
HOME = Path(os.environ.get("USERPROFILE", str(Path.home())))
MAX_READ = 400_000
EXECUTABLE = {".exe", ".bat", ".cmd", ".com", ".msi", ".ps1", ".vbs", ".js", ".jse", ".wsf", ".scr", ".lnk", ".reg", ".hta", ".cpl", ".msc", ".jar", ".pif"}


def special(name: str):
    from .. import internet
    k = name.strip().lower().rstrip("/\\")
    table = {"home": HOME, "~": HOME, "desktop": HOME / "Desktop", "documents": HOME / "Documents", "downloads": internet.downloads_dir(),
             "pictures": HOME / "Pictures", "music": HOME / "Music", "videos": HOME / "Videos", "onedrive": HOME / "OneDrive"}
    p = table.get(k)
    if p is not None and k in ("desktop", "documents", "pictures") and not p.exists() and (HOME / "OneDrive" / p.name).exists():
        p = HOME / "OneDrive" / p.name
    return p


def resolve(path: str, ctx=None, write: bool = False, must_exist: bool = True) -> Path:
    from ..coder import SECRET, protected_dirs
    raw = os.path.expandvars(path.strip().strip('"'))
    head, _, rest = raw.replace("\\", "/").partition("/")
    base = special(head)
    p = (base / rest) if base is not None else Path(raw).expanduser()
    if not p.is_absolute():
        p = HOME / p
    p = p.resolve()
    for d in protected_dirs():
        if p == d or d in p.parents:
            raise ToolError(f"{p} is in a protected system folder, so I won't touch it")
    if SECRET.search(p.name):
        raise ToolError(f"{p.name} looks like a secrets file, so I won't open it")
    if write:
        roots = [HOME] + [Path(w).resolve() for w in ((getattr(ctx, "workspaces", None) or {}).values())]
        appdata = HOME / "AppData"
        if not any(p == r or r in p.parents for r in roots) or p == HOME or appdata == p or appdata in p.parents:
            raise ToolError("I only change files inside your user folders or your Echo workspaces")
    if must_exist and not p.exists():
        raise ToolError(f"{p} doesn't exist")
    return p


def confirm(ctx, title: str, text: str) -> None:
    ask = getattr(ctx, "confirm", None)
    if ask is None or not ask(title, text):
        raise ToolError("you said no (or confirmation isn't available), so nothing was changed")


def human(n: float) -> str:
    from .t_data import human_size
    return human_size(n)


def info_line(p: Path) -> str:
    st = p.stat()
    kind = "folder" if p.is_dir() else human(st.st_size)
    return f"{p.name}{'/' if p.is_dir() else ''}  ({kind}, {datetime.fromtimestamp(st.st_mtime):%Y-%m-%d %H:%M})"


def walk_files(root: Path, limit: int = 20000):
    n = 0
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", "AppData", "$RECYCLE.BIN", "venv", ".venv")]
        for f in files:
            yield Path(dirpath) / f
            n += 1
            if n >= limit:
                return


@tool(C, ex={"folder": "downloads", "limit": 10}, keys="list folder contents directory ls dir files")
def list_folder(folder: str = "downloads", pattern: str = "*", limit: int = 50, sort: Literal["name", "newest", "largest"] = "newest") -> list:
    """List what's in a folder ('downloads', 'desktop', 'documents' or a full path)."""
    p = resolve(folder)
    if not p.is_dir():
        raise ToolError(f"{p} isn't a folder")
    items = [x for x in p.iterdir() if fnmatch.fnmatch(x.name.lower(), pattern.lower())]
    key = {"name": lambda x: x.name.lower(), "newest": lambda x: -x.stat().st_mtime, "largest": lambda x: -(x.stat().st_size if x.is_file() else 0)}[sort]
    items.sort(key=key)
    return [f"{p}"] + [info_line(x) for x in items[:max(1, min(limit, 500))]] + ([f"…and {len(items) - limit} more"] if len(items) > limit else [])


@tool(C, ex={"name": "*.pdf", "folder": "downloads"}, keys="find search locate file by name where is")
def find_files(name: str, folder: str = "home", limit: int = 30) -> list:
    """Find files by name or pattern (e.g. 'resume', '*.pdf', 'invoice*2026*') under a folder."""
    root = resolve(folder)
    pat = name if any(c in name for c in "*?[") else f"*{name}*"
    out = []
    for f in walk_files(root):
        if fnmatch.fnmatch(f.name.lower(), pat.lower()):
            out.append(str(f))
            if len(out) >= limit:
                break
    return out or [f"No files matching {name} under {root}."]


@tool(C, ex={"text": "TODO", "folder": "documents"}, keys="search inside files grep contents text")
def search_in_files(text: str, folder: str = "documents", file_pattern: str = "*.txt;*.md;*.py;*.js;*.ts;*.json;*.csv;*.html;*.css;*.java;*.kt;*.cs;*.go;*.rs;*.yml;*.yaml;*.toml;*.ini;*.xml;*.sql;*.log",
                    limit: int = 40) -> list:
    """Search for text inside files under a folder (text files only)."""
    root = resolve(folder)
    pats = [x.strip().lower() for x in file_pattern.split(";") if x.strip()]
    needle = text.lower()
    out = []
    for f in walk_files(root):
        if not any(fnmatch.fnmatch(f.name.lower(), p) for p in pats):
            continue
        try:
            if f.stat().st_size > 2_000_000:
                continue
            for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if needle in line.lower():
                    out.append(f"{f}:{i}: {line.strip()[:160]}")
                    if len(out) >= limit:
                        return out
        except OSError:
            continue
    return out or [f"“{text}” wasn't found under {root}."]


@tool(C, ex={"path": "downloads"}, keys="file details size modified created properties")
def file_info(path: str) -> dict:
    """Size, dates and type of a file or folder."""
    p = resolve(path)
    st = p.stat()
    out = {"path": str(p), "type": "folder" if p.is_dir() else (p.suffix.lower() or "file"), "modified": f"{datetime.fromtimestamp(st.st_mtime):%Y-%m-%d %H:%M}",
           "created": f"{datetime.fromtimestamp(st.st_ctime):%Y-%m-%d %H:%M}"}
    if p.is_file():
        out["size"] = human(st.st_size)
    else:
        out["items"] = sum(1 for _ in p.iterdir())
    return out


def read_text(p: Path, limit: int = MAX_READ) -> str:
    if not p.is_file():
        raise ToolError(f"{p} isn't a file")
    data = p.read_bytes()[:limit]
    if b"\x00" in data[:4000]:
        raise ToolError(f"{p.name} is a binary file; try read_document for Word/Excel/PowerPoint")
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


@tool(C, keys="open read text file contents show")
def read_text_file(path: str, start_line: int = 1, max_lines: int = 200) -> str:
    """Read a text file (or part of it)."""
    p = resolve(path)
    lines = read_text(p).splitlines()
    s = max(1, start_line)
    chunk = lines[s - 1:s - 1 + max(1, min(max_lines, 2000))]
    more = len(lines) - (s - 1 + len(chunk))
    return "\n".join(chunk) + (f"\n…({more} more lines)" if more > 0 else "")


@tool(C, keys="tail end last lines log file")
def read_file_end(path: str, lines: int = 50) -> str:
    """The last lines of a file (handy for logs)."""
    p = resolve(path)
    size = p.stat().st_size
    with open(p, "rb") as f:
        f.seek(max(0, size - 200_000))
        text = f.read().decode("utf-8", errors="replace")
    return "\n".join(text.splitlines()[-max(1, min(lines, 1000)):])


@tool(C, keys="count lines words file")
def count_file_lines(path: str) -> str:
    """Lines, words and characters in a text file."""
    t = read_text(resolve(path), 20_000_000)
    return f"{many(len(t.splitlines()), 'line')}, {many(len(t.split()), 'word')}, {many(len(t), 'character')}."


def _xml_text(xml: str, para_tag: str) -> str:
    xml = re.sub(rf"</{para_tag}>", "\n", xml)
    xml = re.sub(r"<w:tab/>|<a:tab/>", "\t", xml)
    import html
    return html.unescape(re.sub(r"<[^>]+>", "", xml))


@tool(C, keys="word docx excel xlsx powerpoint pptx pdf read document office text")
def read_document(path: str, max_chars: int = 20000) -> str:
    """Read the text of a PDF, Word (.docx), Excel (.xlsx) or PowerPoint (.pptx) file, or any text file."""
    p = resolve(path)
    ext = p.suffix.lower()
    if ext == ".pdf":
        from .. import pdftext
        try:
            pages = pdftext.read(p, max_chars=max_chars * 2).split("\f")
        except pdftext.PdfError as e:
            raise ToolError(str(e))
        except OSError:
            raise ToolError("I couldn't open that file")
        text = "\n\n".join(f"— Page {i} —\n{t.strip()}" for i, t in enumerate(pages, 1) if t.strip())
        return text[:max_chars] + ("…" if len(text) > max_chars else "")
    if ext not in (".docx", ".xlsx", ".pptx"):
        return read_text(p, max_chars * 2)[:max_chars]
    try:
        z = zipfile.ZipFile(p)
    except zipfile.BadZipFile:
        raise ToolError("that file is damaged or isn't really an Office file")
    with z:
        if ext == ".docx":
            text = _xml_text(z.read("word/document.xml").decode("utf-8", "replace"), "w:p")
        elif ext == ".pptx":
            slides = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)), key=lambda n: int(re.findall(r"\d+", n)[-1]))
            text = "\n\n".join(f"— Slide {i} —\n" + _xml_text(z.read(n).decode("utf-8", "replace"), "a:p").strip() for i, n in enumerate(slides, 1))
        else:
            text = xlsx_text(z)
    return text[:max_chars] + ("…" if len(text) > max_chars else "")


def xlsx_text(z: zipfile.ZipFile, max_rows: int = 200) -> str:
    import html
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        x = z.read("xl/sharedStrings.xml").decode("utf-8", "replace")
        shared = [html.unescape(re.sub(r"<[^>]+>", "", si)) for si in re.findall(r"<si>(.*?)</si>", x, re.S)]
    sheets = sorted((n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)), key=lambda n: int(re.findall(r"\d+", n)[-1]))
    out = []
    for n in sheets[:5]:
        x = z.read(n).decode("utf-8", "replace")
        out.append(f"— {n.split('/')[-1][:-4]} —")
        for row in re.findall(r"<row[^>]*>(.*?)</row>", x, re.S)[:max_rows]:
            cells = []
            for attrs, body in re.findall(r"<c([^>]*)>(.*?)</c>", row, re.S):
                v = re.search(r"<v>(.*?)</v>", body, re.S)
                t = re.search(r'\bt="(\w+)"', attrs)
                if t and t.group(1) == "s" and v:
                    cells.append(shared[int(v.group(1))] if int(v.group(1)) < len(shared) else "")
                elif t and t.group(1) == "inlineStr":
                    cells.append(html.unescape(re.sub(r"<[^>]+>", "", body)))
                else:
                    cells.append(v.group(1) if v else "")
            out.append("\t".join(cells))
    return "\n".join(out)


@tool(C, keys="csv preview spreadsheet head rows columns")
def preview_csv_file(path: str, rows: int = 15) -> str:
    """First rows of a CSV file, plus the row count."""
    p = resolve(path)
    text = read_text(p, 5_000_000)
    from .t_data import read_csv
    r = read_csv(text)
    from .t_text import text_table
    return text_table(r[:max(2, min(rows, 100)) + 1]) + f"\n({len(r) - 1:,} data rows)"


@tool(C, keys="image picture photo size dimensions resolution width height")
def image_info(path: str) -> str:
    """Width, height and type of an image file (PNG, JPEG, GIF, BMP, WebP)."""
    p = resolve(path)
    with open(p, "rb") as f:
        head = f.read(64 * 1024)
    w = h = None
    kind = "unknown"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        kind, (w, h) = "PNG", struct.unpack(">II", head[16:24])
    elif head[:6] in (b"GIF87a", b"GIF89a"):
        kind, (w, h) = "GIF", struct.unpack("<HH", head[6:10])
    elif head[:2] == b"BM":
        kind, (w, h) = "BMP", struct.unpack("<ii", head[18:26])
    elif head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        kind = "WebP"
        if head[12:16] == b"VP8X":
            w, h = 1 + int.from_bytes(head[24:27], "little"), 1 + int.from_bytes(head[27:30], "little")
    elif head[:2] == b"\xff\xd8":
        kind, i = "JPEG", 2
        while i < len(head) - 9:
            if head[i] != 0xFF:
                i += 1
                continue
            marker, seg = head[i + 1], struct.unpack(">H", head[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", head[i + 5:i + 9])
                break
            i += 2 + seg
    if w is None:
        return f"{p.name}: {kind} image, {human(p.stat().st_size)} (size unknown)."
    return f"{p.name}: {kind}, {w} × {abs(h)} pixels ({fmt(round(w * abs(h) / 1e6, 2))} MP), {human(p.stat().st_size)}."


@tool(C, ex={"folder": "downloads"}, keys="folder size disk usage how big")
def folder_size(folder: str) -> str:
    """Total size and file count of a folder."""
    root = resolve(folder)
    total = n = 0
    for f in walk_files(root, 200_000):
        try:
            total += f.stat().st_size
            n += 1
        except OSError:
            pass
    return f"{root}: {human(total)} in {many(n, 'file')}."


@tool(C, ex={"folder": "downloads", "count": 5}, keys="biggest largest files space")
def largest_files(folder: str = "downloads", count: int = 15) -> list:
    """The biggest files under a folder."""
    root = resolve(folder)
    sized = []
    for f in walk_files(root, 100_000):
        try:
            sized.append((f.stat().st_size, f))
        except OSError:
            pass
    sized.sort(key=lambda x: -x[0])
    return [f"{human(s)}  {f}" for s, f in sized[:max(1, min(count, 100))]]


@tool(C, ex={"folder": "downloads", "count": 5}, keys="recent latest new files modified")
def recent_files(folder: str = "downloads", count: int = 15, days: int = 30) -> list:
    """Most recently changed files under a folder."""
    root = resolve(folder)
    cutoff = time.time() - days * 86400
    items = []
    for f in walk_files(root, 100_000):
        try:
            m = f.stat().st_mtime
            if m >= cutoff:
                items.append((m, f))
        except OSError:
            pass
    items.sort(key=lambda x: -x[0])
    return [f"{datetime.fromtimestamp(m):%Y-%m-%d %H:%M}  {f}" for m, f in items[:max(1, min(count, 100))]] or ["Nothing changed recently."]


@tool(C, ex={"folder": "downloads", "older_than_days": 365}, keys="old files unused cleanup stale")
def old_files(folder: str = "downloads", older_than_days: int = 180, count: int = 30) -> list:
    """Files not changed for a long time (cleanup candidates)."""
    root = resolve(folder)
    cutoff = time.time() - older_than_days * 86400
    items = []
    for f in walk_files(root, 100_000):
        try:
            st = f.stat()
            if st.st_mtime < cutoff:
                items.append((st.st_size, st.st_mtime, f))
        except OSError:
            pass
    items.sort(key=lambda x: -x[0])
    return [f"{human(s)}  {datetime.fromtimestamp(m):%Y-%m-%d}  {f}" for s, m, f in items[:count]] or ["No old files."]


def file_hash(p: Path, algo: str = "sha256") -> str:
    h = hashlib.new(algo)
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@tool(C, ex={"folder": "downloads"}, keys="duplicate files same copies cleanup")
def find_duplicate_files(folder: str = "downloads", min_size_kb: int = 10) -> list:
    """Groups of identical files (same content) under a folder."""
    root = resolve(folder)
    by_size = {}
    for f in walk_files(root, 50_000):
        try:
            s = f.stat().st_size
            if s >= min_size_kb * 1024:
                by_size.setdefault(s, []).append(f)
        except OSError:
            pass
    groups = {}
    for s, fs in by_size.items():
        if len(fs) > 1:
            for f in fs:
                try:
                    groups.setdefault((s, file_hash(f, "md5")), []).append(f)
                except OSError:
                    pass
    dupes = [g for g in groups.values() if len(g) > 1]
    if not dupes:
        return ["No duplicates found."]
    wasted = sum(g[0].stat().st_size * (len(g) - 1) for g in dupes)
    return [f"{len(dupes)} groups, {human(wasted)} could be freed:"] + [" = ".join(str(x) for x in g) for g in dupes[:30]]


@tool(C, keys="file checksum hash sha256 md5 verify download")
def hash_file(path: str, algorithm: Literal["sha256", "md5", "sha1", "sha512"] = "sha256") -> str:
    """Checksum of a file (to verify a download)."""
    p = resolve(path)
    return f"{algorithm.upper()} {file_hash(p, algorithm)}  {p.name}"


@tool(C, keys="compare two files same different")
def compare_files(path_a: str, path_b: str) -> str:
    """Are two files identical? For text files, shows what differs."""
    a, b = resolve(path_a), resolve(path_b)
    if a.stat().st_size == b.stat().st_size and file_hash(a) == file_hash(b):
        return "The files are identical."
    try:
        from .t_text import text_diff
        d = text_diff(read_text(a, 300_000), read_text(b, 300_000))
        return d[:6000]
    except ToolError:
        return f"The files differ ({human(a.stat().st_size)} vs {human(b.stat().st_size)})."


@tool(C, ex={}, keys="disk drives free space storage c drive")
def drives_free_space() -> list:
    """Every drive with free and total space."""
    out = []
    for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        root = f"{letter}:\\"
        if os.path.exists(root):
            try:
                u = shutil.disk_usage(root)
                out.append(f"{letter}: {human(u.free)} free of {human(u.total)} ({u.used / u.total * 100:.0f}% used)")
            except OSError:
                pass
    return out


@tool(C, ex={}, keys="special folders paths downloads desktop documents where")
def my_folders() -> dict:
    """Where your main folders are (Desktop, Documents, Downloads, Pictures…)."""
    return {k: str(special(k)) for k in ("desktop", "documents", "downloads", "pictures", "music", "videos", "home")}


# ---- changes (ask first) ----------------------------------------------------------------------------------------
@tool(C, ask=True, keys="write save create text file new")
def write_text_file(path: str, content: str, ctx=None, overwrite: bool = False) -> str:
    """Create (or overwrite) a text file in your folders. Asks first."""
    p = resolve(path, ctx, write=True, must_exist=False)
    if p.exists() and not overwrite:
        raise ToolError(f"{p} already exists; pass overwrite=true to replace it")
    confirm(ctx, "Save a file?", f"{'Replace' if p.exists() else 'Create'} {p}\n({len(content):,} characters)")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Saved {p}."


@tool(C, ask=True, keys="append add line to file log")
def append_to_file(path: str, content: str, ctx=None) -> str:
    """Add text to the end of a text file. Asks first."""
    p = resolve(path, ctx, write=True, must_exist=False)
    confirm(ctx, "Add to a file?", f"Append {many(len(content), 'character')} to {p}")
    with open(p, "a", encoding="utf-8") as f:
        f.write(content if content.endswith("\n") else content + "\n")
    return f"Added to {p}."


@tool(C, ask=True, keys="new folder make directory create mkdir")
def create_folder(path: str, ctx=None) -> str:
    """Create a folder. Asks first."""
    p = resolve(path, ctx, write=True, must_exist=False)
    if p.exists():
        return f"{p} already exists."
    confirm(ctx, "Create a folder?", str(p))
    p.mkdir(parents=True)
    return f"Created {p}."


def _target(src: Path, dest: str, ctx) -> Path:
    d = resolve(dest, ctx, write=True, must_exist=False)
    if d.is_dir():
        d = d / src.name
    if d.exists():
        raise ToolError(f"{d} already exists")
    return d


@tool(C, ask=True, keys="copy duplicate file folder")
def copy_file(source: str, destination: str, ctx=None) -> str:
    """Copy a file or folder. Asks first."""
    s = resolve(source)
    d = _target(s, destination, ctx)
    confirm(ctx, "Copy?", f"{s}\n→ {d}")
    (shutil.copytree if s.is_dir() else shutil.copy2)(s, d)
    return f"Copied to {d}."


@tool(C, ask=True, keys="move file folder relocate")
def move_file(source: str, destination: str, ctx=None) -> str:
    """Move a file or folder. Asks first."""
    s = resolve(source, ctx, write=True)
    _not_a_main_folder(s, "move")
    d = _target(s, destination, ctx)
    confirm(ctx, "Move?", f"{s}\n→ {d}")
    shutil.move(str(s), str(d))
    return f"Moved to {d}."


@tool(C, ask=True, keys="rename file folder")
def rename_file(path: str, new_name: str, ctx=None) -> str:
    """Rename a file or folder (same place, new name). Asks first."""
    s = resolve(path, ctx, write=True)
    if re.search(r'[<>:"/\\|?*]', new_name):
        raise ToolError("a name can't contain < > : \" / \\ | ? *")
    d = s.with_name(new_name)
    if d.exists():
        raise ToolError(f"{d.name} already exists")
    confirm(ctx, "Rename?", f"{s.name} → {new_name}")
    s.rename(d)
    return f"Renamed to {d.name}."


def to_recycle_bin(p: Path) -> None:
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
                    ("fFlags", ctypes.c_uint16), ("fAnyOperationsAborted", wintypes.BOOL), ("hNameMappings", ctypes.c_void_p),
                    ("lpszProgressTitle", wintypes.LPCWSTR)]
    op = SHFILEOPSTRUCTW(None, 3, str(p) + "\0", None, 0x0040 | 0x0010 | 0x0400 | 0x0004, False, None, None)  # DELETE, ALLOWUNDO|NOCONFIRMATION|NOERRORUI|SILENT
    if ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) != 0 or op.fAnyOperationsAborted:
        raise ToolError("Windows couldn't move it to the Recycle Bin")


def _not_a_main_folder(p: Path, verb: str) -> None:
    """Whole main folders (Documents, Desktop, Downloads, Pictures, Music, Videos, OneDrive, your user folder) are never
    deleted or moved by Echo, whoever asks: one wrong word would take years of files. Single files and sub-folders are fine."""
    mains = {HOME.resolve()}
    for name in ("documents", "desktop", "downloads", "pictures", "music", "videos", "onedrive"):
        try:
            d = special(name)
        except Exception:
            d = None
        if d is not None:
            mains.add(Path(d).resolve())
    if p.resolve() in mains:
        raise ToolError(f"I won't {verb} your whole {p.name} folder. Name the files or sub-folder you mean, or do it in "
                        f"File Explorer yourself.")


@tool(C, ask=True, keys="delete remove trash recycle bin file")
def delete_to_recycle_bin(path: str, ctx=None) -> str:
    """Move a file or folder to the Recycle Bin (you can restore it). Asks first."""
    p = resolve(path, ctx, write=True)
    _not_a_main_folder(p, "delete")
    confirm(ctx, "Move to the Recycle Bin?", str(p))
    to_recycle_bin(p)
    return f"Moved {p.name} to the Recycle Bin."


@tool(C, ask=True, keys="zip compress archive files")
def zip_files(paths: list[str], zip_path: str, ctx=None) -> str:
    """Put files/folders into a .zip. Asks first."""
    srcs = [resolve(x) for x in paths]
    z = resolve(zip_path if zip_path.lower().endswith(".zip") else zip_path + ".zip", ctx, write=True, must_exist=False)
    if z.exists():
        raise ToolError(f"{z} already exists")
    confirm(ctx, "Make a zip?", f"{len(srcs)} item(s) → {z}")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for s in srcs:
            if s.is_dir():
                for f in walk_files(s):
                    zf.write(f, f.relative_to(s.parent))
            else:
                zf.write(s, s.name)
    return f"Created {z} ({human(z.stat().st_size)})."


@tool(C, ask=True, keys="unzip extract archive")
def unzip_file(zip_path: str, destination: str = "", ctx=None) -> str:
    """Extract a .zip (into a folder next to it by default). Asks first; blocks unsafe paths inside the zip."""
    z = resolve(zip_path)
    dest = resolve(destination, ctx, write=True, must_exist=False) if destination else resolve(str(z.with_suffix("")), ctx, write=True, must_exist=False)
    with zipfile.ZipFile(z) as zf:
        names = zf.namelist()
        for n in names:
            target = (dest / n).resolve()
            if dest.resolve() not in target.parents and target != dest.resolve():
                raise ToolError(f"the zip contains an unsafe path ({n}), so I won't extract it")
        total = sum(i.file_size for i in zf.infolist())
        confirm(ctx, "Extract the zip?", f"{many(len(names), 'file')} ({human(total)}) → {dest}")
        zf.extractall(dest)
    return f"Extracted {many(len(names), 'file')} to {dest}."


@tool(C, keys="zip contents list inside archive")
def list_zip(zip_path: str) -> list:
    """What's inside a .zip file."""
    z = resolve(zip_path)
    with zipfile.ZipFile(z) as zf:
        infos = zf.infolist()
    return [f"{many(len(infos), 'entry')}, {human(sum(i.file_size for i in infos))} unpacked"] + [f"{i.filename} ({human(i.file_size)})" for i in infos[:100]]


@tool(C, keys="open file document photo default app")
def open_file(path: str) -> str:
    """Open a file with its usual app (documents, photos, music…; programs and scripts are never run)."""
    p = resolve(path)
    if p.suffix.lower() in EXECUTABLE:
        raise ToolError("I don't run programs or scripts this way")
    os.startfile(str(p))
    return f"Opened {p.name}."


@tool(C, keys="show in explorer reveal folder location")
def show_in_explorer(path: str) -> str:
    """Open File Explorer at a file (selected) or folder."""
    import subprocess
    p = resolve(path)
    if p.is_dir():
        os.startfile(str(p))
    else:
        subprocess.Popen(["explorer", "/select,", str(p)])
    return f"Showing {p.name} in File Explorer."


@tool(C, ex={"folder": "downloads"}, keys="file types extensions summary what kinds")
def file_types_summary(folder: str = "downloads") -> list:
    """How many files of each type a folder has, and their total size."""
    root = resolve(folder)
    stats = {}
    for f in walk_files(root, 100_000):
        try:
            s = f.stat().st_size
        except OSError:
            continue
        e = f.suffix.lower() or "(none)"
        n, t = stats.get(e, (0, 0))
        stats[e] = (n + 1, t + s)
    return [f"{e}: {many(n, 'file')}, {human(t)}" for e, (n, t) in sorted(stats.items(), key=lambda x: -x[1][1])[:30]]


@tool(C, ask=True, keys="organize sort downloads by type folders tidy cleanup")
def organize_by_type(folder: str = "downloads", ctx=None) -> str:
    """Tidy a folder: move its loose files into sub-folders by type (Images, Documents, Videos, Music, Archives, Installers, Other). Asks first."""
    root = resolve(folder, ctx, write=True)
    groups = {"Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".bmp", ".svg"}, "Documents": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv", ".odt", ".md", ".rtf"},
              "Videos": {".mp4", ".mkv", ".mov", ".avi", ".webm"}, "Music": {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"},
              "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"}, "Installers": {".exe", ".msi", ".apk"}}
    files = [f for f in root.iterdir() if f.is_file() and not f.name.endswith(".part")]
    if not files:
        return "No loose files to sort."
    confirm(ctx, "Tidy this folder?", f"Move {many(len(files), 'file')} in {root} into type folders.")
    moved = 0
    for f in files:
        g = next((k for k, exts in groups.items() if f.suffix.lower() in exts), "Other")
        d = root / g
        d.mkdir(exist_ok=True)
        t = d / f.name
        i = 1
        while t.exists():
            t = d / f"{f.stem} ({i}){f.suffix}"
            i += 1
        shutil.move(str(f), str(t))
        moved += 1
    return f"Moved {many(moved, 'file')} into type folders in {root}."


@tool(C, ask=True, keys="bulk rename batch numbering files")
def batch_rename(folder: str, pattern: str, prefix: str, ctx=None, start: int = 1) -> str:
    """Rename every file matching a pattern to prefix_001, prefix_002… (keeping extensions). Asks first."""
    root = resolve(folder, ctx, write=True)
    files = sorted(f for f in root.iterdir() if f.is_file() and fnmatch.fnmatch(f.name.lower(), pattern.lower()))
    if not files:
        raise ToolError("no files match")
    width = len(str(start + len(files)))
    plan = [(f, root / f"{prefix}_{i:0{max(3, width)}d}{f.suffix}") for i, f in enumerate(files, start)]
    if any(t.exists() and t not in files for _, t in plan):
        raise ToolError("some new names already exist")
    confirm(ctx, "Rename files?", "\n".join(f"{a.name} → {b.name}" for a, b in plan[:15]) + (f"\n…{len(plan) - 15} more" if len(plan) > 15 else ""))
    tmp = [(a, a.with_name(f".echo-tmp-{i}{a.suffix}")) for i, (a, _) in enumerate(plan)]
    for a, t in tmp:
        a.rename(t)
    for (_, t), (_, b) in zip(tmp, plan):
        t.rename(b)
    return f"Renamed {many(len(plan), 'file')}."
