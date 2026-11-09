"""Echo's change log: every file Echo creates, edits, renames or deletes is recorded per request, with the original
saved first, so any request can be reverted ("undo the last change", "revert change 12").

Layout (%APPDATA%\\EchoDesktop\\changes):
  <id>/manifest.json   {"id", "time", "request", "folder", "files": [...], "reverted_by", "revert_of"}
  <id>/<n>.orig        the file's content before this request first touched it
A revert is itself recorded as a new change, so it can be undone too. Reverting refuses to overwrite a file that was
changed again after Echo's change (reported as a conflict) unless forced.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

MAX_FILE = 25_000_000          # files bigger than this aren't edited by Echo (and so never need a backup)
KEEP = 300                     # change sets kept (oldest pruned)


def sha(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class ChangeSet:
    id: int
    request: str
    folder: str
    dir: Path
    time: float = field(default_factory=time.time)
    files: list = field(default_factory=list)       # [{"path", "action", "orig", "before", "after", "to"}]
    revert_of: Optional[int] = None
    reverted_by: Optional[int] = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # ---- recording (call BEFORE touching the file) ----------------------------------------------------------
    def _entry(self, path: Path) -> Optional[dict]:
        p = str(path.resolve())
        return next((e for e in self.files if e["path"] == p), None)

    def before_write(self, path: Path) -> None:
        """Snapshot the file once per request before Echo creates or edits it."""
        with self._lock:
            if self._entry(path):
                return
            e = {"path": str(path.resolve()), "action": "modified" if path.exists() else "created", "orig": None,
                 "before": sha(path), "after": None}
            if path.exists():
                if path.stat().st_size > MAX_FILE:
                    raise ValueError(f"{path.name} is too big for Echo to edit safely")
                e["orig"] = f"{len(self.files)}.orig"
                shutil.copy2(path, self.dir / e["orig"])
            self.files.append(e)
            self.save()

    def before_delete(self, path: Path) -> None:
        with self._lock:
            e = self._entry(path)
            if e is None:
                e = {"path": str(path.resolve()), "action": "deleted", "orig": f"{len(self.files)}.orig",
                     "before": sha(path), "after": None}
                shutil.copy2(path, self.dir / e["orig"])
                self.files.append(e)
            elif e["action"] == "created":
                e["action"] = "created_then_deleted"
            else:
                e["action"] = "deleted"
            self.save()

    def before_rename(self, src: Path, dst: Path) -> None:
        self.before_delete(src)
        self.before_write(dst)
        with self._lock:
            self._entry(src)["action"] = "renamed_away"
            self._entry(dst)["from"] = str(src.resolve())

    def finish(self) -> None:
        with self._lock:
            for e in self.files:
                e["after"] = sha(Path(e["path"]))
            self.save()

    # ---- persistence ------------------------------------------------------------------------------------------
    def to_json(self) -> dict:
        return {"id": self.id, "time": self.time, "request": self.request, "folder": self.folder, "files": self.files,
                "revert_of": self.revert_of, "reverted_by": self.reverted_by}

    def save(self) -> None:
        tmp = self.dir / "manifest.json.tmp"
        tmp.write_text(json.dumps(self.to_json(), indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.dir / "manifest.json")

    # ---- summary -------------------------------------------------------------------------------------------------
    def summary(self) -> str:
        counts = {}
        for e in self.files:
            a = {"created_then_deleted": None, "renamed_away": "renamed"}.get(e["action"], e["action"])
            if a:
                counts[a] = counts.get(a, 0) + 1
        what = ", ".join(f"{n} {a}" for a, n in counts.items()) or "no file changes"
        stamp = time.strftime("%d %b %H:%M", time.localtime(self.time))
        state = " (reverted)" if self.reverted_by else ""
        return f"#{self.id} {stamp} · {self.request[:70]} · {what}{state}"


class ChangeJournal:
    def __init__(self, directory: Path):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _ids(self) -> list:
        return sorted(int(p.name) for p in self.root.iterdir() if p.is_dir() and p.name.isdigit())

    def begin(self, request: str, folder: str = "", revert_of: Optional[int] = None) -> ChangeSet:
        with self._lock:
            ids = self._ids()
            cid = (ids[-1] + 1) if ids else 1
            d = self.root / str(cid)
            d.mkdir()
            cs = ChangeSet(cid, request.strip()[:300], folder, d, revert_of=revert_of)
            cs.save()
            for old in ids[:-KEEP] if len(ids) >= KEEP else []:
                shutil.rmtree(self.root / str(old), ignore_errors=True)
            return cs

    def load(self, cid: int) -> Optional[ChangeSet]:
        f = self.root / str(cid) / "manifest.json"
        if not f.is_file():
            return None
        d = json.loads(f.read_text(encoding="utf-8"))
        return ChangeSet(d["id"], d["request"], d.get("folder", ""), f.parent, d["time"], d["files"],
                         d.get("revert_of"), d.get("reverted_by"))

    def recent(self, n: int = 20, with_files_only: bool = True) -> list:
        out = []
        for cid in reversed(self._ids()):
            cs = self.load(cid)
            if cs and (cs.files or not with_files_only):
                out.append(cs)
            if len(out) >= n:
                break
        return out

    def last_unreverted(self) -> Optional[ChangeSet]:
        return next((cs for cs in self.recent(50) if not cs.reverted_by and cs.revert_of is None), None)

    def diff(self, cid: int, limit: int = 400) -> str:
        """Unified diff of every text file in a change (original vs now)."""
        import difflib
        cs = self.load(cid)
        if cs is None:
            return f"There's no change #{cid}."
        out = []
        for e in cs.files:
            p = Path(e["path"])
            old = (cs.dir / e["orig"]).read_bytes() if e.get("orig") and (cs.dir / e["orig"]).exists() else b""
            new = p.read_bytes() if p.is_file() else b""
            try:
                a, b = old.decode("utf-8").splitlines(), new.decode("utf-8").splitlines()
            except UnicodeDecodeError:
                out.append(f"--- {p} (binary file, {e['action']})")
                continue
            out += list(difflib.unified_diff(a, b, f"{p.name} (before #{cid})", f"{p.name} (now)", lineterm="", n=2))
        return "\n".join(out[:limit]) + ("\n…" if len(out) > limit else "") if out else "No text differences."

    def revert(self, cid: int, force: bool = False) -> tuple:
        """Undo change #cid. Returns (ok, message). Recorded as a new change (so the revert can be undone)."""
        cs = self.load(cid)
        if cs is None:
            return False, f"There's no change #{cid}."
        if cs.reverted_by:
            return False, f"Change #{cid} was already reverted (by #{cs.reverted_by})."
        if not cs.files:
            return False, f"Change #{cid} didn't touch any files."
        # a file is in conflict when it no longer looks the way Echo left it (edited, recreated or removed since)
        conflicts = [e["path"] for e in cs.files if sha(Path(e["path"])) != e.get("after")]
        if conflicts and not force:
            names = ", ".join(Path(p).name for p in conflicts[:5])
            return False, (f"{names} changed again after #{cid}, so I didn't revert it (that would lose the newer edits). "
                           f"Say “force revert change {cid}” to restore the old version anyway.")
        undo = self.begin(f"Revert #{cid}: {cs.request}", cs.folder, revert_of=cid)
        restored = 0
        for e in reversed(cs.files):
            p = Path(e["path"])
            orig = cs.dir / e["orig"] if e.get("orig") else None
            if e["action"] in ("created", "created_then_deleted"):
                if p.exists():
                    undo.before_delete(p)
                    p.unlink()
                    restored += 1
            elif orig is not None and orig.exists():
                undo.before_write(p)
                p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(orig, p)
                restored += 1
        undo.finish()
        cs.reverted_by = undo.id
        cs.save()
        return True, f"Reverted change #{cid} ({restored} file{'s' if restored != 1 else ''} restored). To undo this, revert #{undo.id}."
