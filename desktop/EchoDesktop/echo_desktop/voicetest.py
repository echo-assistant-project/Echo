"""Echo voice test: a window that types whatever you say, so you can see exactly what Echo hears.

Start it by saying "test my voice" to Echo, or run Run-VoiceTest.ps1. Speech is recognised by, in order:
  1. Whisper inside this window (when started with the Whisper host's Python, which has faster-whisper);
  2. the Whisper host on 127.0.0.1 (when it is set up and running);
  3. Windows speech recognition.
Optionally type what you really said and press Check: the window scores the last sentence and keeps a running total.
Audio stays in memory on this PC.
"""
from __future__ import annotations

import queue
import re
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

BG, PANEL, TEXT, MUTED, ACCENT, GOOD, BAD = "#0f1720", "#18232f", "#e8eef5", "#8aa0b5", "#42d9ff", "#4ade80", "#ff6b6b"
REPO = Path(__file__).resolve().parents[3]
MODELS = ("small.en", "base.en", "medium.en", "large-v3-turbo")
CONTRACTIONS = {"what's": "what is", "it's": "it is", "i'm": "i am", "don't": "do not", "can't": "cannot", "won't": "will not",
                "i'll": "i will", "you're": "you are", "that's": "that is", "let's": "let us", "isn't": "is not",
                "there's": "there is", "i've": "i have", "we're": "we are", "they're": "they are", "didn't": "did not"}


# ------------------------------------------------------------------------------------------------ scoring (pure)
def words(text: str) -> list:
    t = (text or "").lower().replace("’", "'").replace("%", " percent").replace("&", " and ")
    t = re.sub(r"(\d),(\d)", r"\1\2", t)
    t = re.sub(r"[^\w' ]+", " ", t)
    out = []
    for w in t.split():
        w = w.strip("'")
        if w:
            out.extend(CONTRACTIONS.get(w, w).split())
    return out


def compare(said: str, heard: str) -> dict:
    """Word-level alignment of what was said vs what was heard: errors, word count and the mistakes."""
    r, h = words(said), words(heard)
    n, m = len(r), len(h)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (r[i - 1] != h[j - 1]))
    mistakes, i, j = [], n, m
    while i > 0 or j > 0:                      # on ties: match, then extra word, then missed word, then swap
        if i > 0 and j > 0 and r[i - 1] == h[j - 1] and d[i][j] == d[i - 1][j - 1]:
            i, j = i - 1, j - 1
        elif j > 0 and d[i][j] == d[i][j - 1] + 1:
            mistakes.append(f"extra “{h[j - 1]}”")
            j -= 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            mistakes.append(f"missed “{r[i - 1]}”")
            i -= 1
        else:
            mistakes.append(f"“{r[i - 1]}” → “{h[j - 1]}”")
            i, j = i - 1, j - 1
    return {"errors": d[n][m], "words": n, "mistakes": list(reversed(mistakes))}


# ------------------------------------------------------------------------------------------------ recognisers
class LocalWhisper:
    """faster-whisper in this process, through Echo's shared pipeline (tools/WhisperHost/asr_engine.py)."""

    name = "Whisper (this window)"

    def __init__(self, model_name: str):
        import os
        sys.path.insert(0, str(REPO / "tools" / "WhisperHost"))
        import asr_engine
        from faster_whisper import WhisperModel
        self.engine = asr_engine
        self.model_name = model_name
        root = Path(os.environ.get("LOCALAPPDATA", "")) / "EchoAndroid" / "WhisperHost" / "models"
        self.model = WhisperModel(model_name, device="cpu", compute_type="int8", download_root=str(root),
                                  cpu_threads=min(8, os.cpu_count() or 4))

    def transcribe(self, pcm: bytes) -> str:
        import numpy as np
        audio = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
        return self.engine.transcribe(self.model, audio, self.engine.Settings(), language="en")["text"]


class HostWhisper:
    name = "Whisper host"

    def __init__(self, pairing):
        self.pairing = pairing
        self.model_name = pairing.get("model", "Whisper")

    def transcribe(self, pcm: bytes) -> str:
        from . import stt
        r = stt.transcribe(pcm, self.pairing, "Echo.")
        return (r.get("text") or "").strip() if r.get("no_speech", 0) < 0.6 else ""


class GpuWhisper:
    """Whisper on the Intel GPU (OpenVINO), via tools/WhisperHost/ov_engine.py."""

    name = "Whisper on Intel GPU"

    def __init__(self, model_dir_name: str):
        sys.path.insert(0, str(REPO / "tools" / "WhisperHost"))
        import ov_engine
        self.ov = ov_engine.OpenVinoWhisper(model_dir_name)
        self.model_name = f"{self.ov.model_name} ({self.ov.device})"

    def transcribe(self, pcm: bytes) -> str:
        import numpy as np
        return self.ov.transcribe(np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0)["text"]


GPU_MODELS = {"large-v3-turbo · Intel GPU (best)": "whisper-large-v3-turbo-int8-ov",
              "small.en · Intel GPU (fastest)": "whisper-small.en-int8-ov"}


def local_whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        import numpy  # noqa: F401
        return True
    except ImportError:
        return False


def gpu_models() -> dict:
    """GPU choices whose files are downloaded, when this Python has OpenVINO GenAI."""
    try:
        import openvino_genai  # noqa: F401
        sys.path.insert(0, str(REPO / "tools" / "WhisperHost"))
        import ov_engine
    except ImportError:
        return {}
    return {label: d for label, d in GPU_MODELS.items() if ov_engine.available(d)}


# ------------------------------------------------------------------------------------------------ window
class VoiceTest:
    def __init__(self, root=None):
        self.root = root or tk.Tk()
        self.win = self.root if root is None else tk.Toplevel(root)
        self.win.title("Echo voice test")
        self.win.configure(bg=BG)
        self.win.geometry("760x560")
        self.win.attributes("-topmost", True)
        self.events: "queue.Queue" = queue.Queue()
        self.cancel = threading.Event()
        self.running = False
        self.engine = None
        self.last_heard = ""
        self.total_errors = self.total_words = 0
        self.typing: list = []

        top = tk.Frame(self.win, bg=BG)
        top.pack(fill="x", padx=14, pady=(12, 6))
        self.button = tk.Button(top, text="🎙  Start listening", command=self.toggle, bg="#2a6f97", fg="white",
                                relief="flat", font=("Segoe UI", 11, "bold"), padx=14, pady=6)
        self.button.pack(side="left")
        tk.Button(top, text="Clear", command=self.clear, bg=PANEL, fg=TEXT, relief="flat", padx=10, pady=6).pack(side="left", padx=8)
        self.gpu = gpu_models()
        choices = list(self.gpu) + (list(MODELS) if local_whisper_available() else [])
        self.local = bool(choices)
        if self.local:
            tk.Label(top, text="Model", fg=MUTED, bg=BG).pack(side="left", padx=(12, 4))
            self.model = tk.StringVar(value=choices[0])
            box = ttk.Combobox(top, textvariable=self.model, values=choices, state="readonly", width=32)
            box.pack(side="left")
            box.bind("<<ComboboxSelected>>", lambda e: self._reset_engine())
        self.level = tk.Canvas(top, width=120, height=14, bg=PANEL, highlightthickness=0)
        self.level.pack(side="right")

        self.text = tk.Text(self.win, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", wrap="word",
                            font=("Segoe UI", 16), padx=14, pady=12, height=12)
        self.text.pack(fill="both", expand=True, padx=14)
        self.text.tag_configure("meta", foreground=MUTED, font=("Segoe UI", 9))
        self.text.tag_configure("good", foreground=GOOD, font=("Segoe UI", 10))
        self.text.tag_configure("bad", foreground=BAD, font=("Segoe UI", 10))

        check = tk.Frame(self.win, bg=BG)
        check.pack(fill="x", padx=14, pady=(8, 4))
        tk.Label(check, text="What I really said (optional):", fg=MUTED, bg=BG).pack(side="left")
        self.truth = tk.Entry(check, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 11))
        self.truth.pack(side="left", fill="x", expand=True, padx=8, ipady=4)
        self.truth.bind("<Return>", lambda e: self.check())
        tk.Button(check, text="Check", command=self.check, bg=PANEL, fg=TEXT, relief="flat", padx=10).pack(side="left")
        self.score = tk.Label(self.win, text="Accuracy: say something, then type what you really said and press Check.",
                              fg=MUTED, bg=BG, anchor="w")
        self.score.pack(fill="x", padx=14)
        self.status = tk.Label(self.win, text=self._engine_hint(), fg=MUTED, bg=BG, anchor="w")
        self.status.pack(fill="x", padx=14, pady=(2, 10))
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.win.after(30, self._drain)

    def _engine_hint(self) -> str:
        if self.gpu:
            return "Ready. Whisper runs on your Intel GPU inside this window (large-v3-turbo: most accurate, ~2–3 s)."
        if self.local:
            return "Ready. Whisper runs inside this window on the CPU (small.en is the best speed/accuracy here)."
        from . import stt
        if stt.find_whisper_pairing():
            return "Ready. Using the Whisper host (start it with tools\\WhisperHost\\Run-WhisperHost.ps1)."
        return "Ready. Using Windows speech recognition (set up the Whisper host for much better accuracy)."

    # ---- controls ----
    def toggle(self):
        if self.running:
            self.running = False
            self.cancel.set()
            self.button.config(text="🎙  Start listening", bg="#2a6f97")
            self.status.config(text="Stopped.")
            return
        self.running = True
        self.cancel = threading.Event()
        self.button.config(text="■  Stop", bg="#a33a3a")
        threading.Thread(target=self._loop, args=(self.cancel,), daemon=True).start()

    def clear(self):
        self.text.delete("1.0", "end")
        self.total_errors = self.total_words = 0
        self.score.config(text="Accuracy: cleared.", fg=MUTED)

    def close(self):
        self.running = False
        self.cancel.set()
        self.win.destroy()

    def _reset_engine(self):
        self.engine = None

    def check(self):
        said = self.truth.get().strip()
        if not said or not self.last_heard:
            return
        c = compare(said, self.last_heard)
        if not c["words"]:
            return
        self.total_errors += c["errors"]
        self.total_words += c["words"]
        acc = max(0.0, 1 - c["errors"] / c["words"])
        total = max(0.0, 1 - self.total_errors / self.total_words)
        detail = "perfect!" if not c["mistakes"] else ", ".join(c["mistakes"][:6])
        self.text.insert("end", f"   ✓ {acc:.0%} — {detail}\n", "good" if acc >= 0.97 else "bad")
        self.text.see("end")
        self.score.config(text=f"Last sentence: {acc:.0%}    All checked: {total:.1%} of {self.total_words} words",
                          fg=GOOD if total >= 0.97 else BAD)
        self.truth.delete(0, "end")

    # ---- background listening ----
    def _get_engine(self):
        if self.engine is not None:
            return self.engine
        if self.local:
            name = self.model.get()
            self.events.put(("status", f"Loading {name}… (the very first time can take a minute)"))
            self.engine = GpuWhisper(self.gpu[name]) if name in self.gpu else LocalWhisper(name)
            return self.engine
        from . import stt
        pairing = stt.find_whisper_pairing()
        if pairing:
            self.engine = HostWhisper(pairing)
        return self.engine

    def _loop(self, cancel: threading.Event):
        from . import stt
        while not cancel.is_set():
            try:
                engine = self._get_engine()
                self.events.put(("status", "Listening… speak now."))
                if engine is None:                               # Windows speech recognition
                    from .voice import Listener
                    started = time.perf_counter()
                    heard = Listener().listen_once(10)
                    name, secs = "Windows speech", time.perf_counter() - started
                else:
                    pcm = stt.record_utterance(cancel, max_seconds=30, no_speech_seconds=30)
                    if cancel.is_set():
                        break
                    if not pcm:
                        continue
                    self.events.put(("status", "Recognising…"))
                    started = time.perf_counter()
                    heard = engine.transcribe(pcm)
                    name, secs = f"{engine.name} · {engine.model_name}", time.perf_counter() - started
                if heard and not cancel.is_set():
                    self.events.put(("heard", heard, name, secs))
            except Exception as e:                               # microphone missing, host down…
                self.events.put(("error", str(e)))
                if self.engine is not None and isinstance(self.engine, HostWhisper):
                    self.engine = None
                time.sleep(1.5)
        self.events.put(("status", "Stopped."))

    def _drain(self):
        try:
            while True:
                ev = self.events.get_nowait()
                if ev[0] == "status":
                    self.status.config(text=ev[1], fg=MUTED)
                elif ev[0] == "error":
                    self.status.config(text="Problem: " + ev[1], fg=BAD)
                elif ev[0] == "heard":
                    _, heard, name, secs = ev
                    self.last_heard = heard
                    self.typing.append((heard, f"   ({name}, recognised in {secs:.1f} s)\n"))
                    if len(self.typing) == 1:
                        self._type_next(0)
        except queue.Empty:
            pass
        try:
            self.win.after(30, self._drain)
        except tk.TclError:          # window closed
            pass

    def _type_next(self, i: int):
        """Type the sentence into the window, letter by letter (fast), then its timing line."""
        if not self.typing:
            return
        heard, meta = self.typing[0]
        if i < len(heard):
            step = 3
            self.text.insert("end", heard[i:i + step])
            self.text.see("end")
            self.win.after(8, self._type_next, i + step)
            return
        self.text.insert("end", meta, "meta")
        self.text.see("end")
        self.typing.pop(0)
        if self.typing:
            self.win.after(8, self._type_next, 0)


def launch() -> tuple:
    """Open the voice test as its own process: with the Whisper host's Python when it exists (Whisper runs in the
    window), else with this Python. Returns (ok, message)."""
    import os
    import subprocess
    root = Path(os.environ.get("LOCALAPPDATA", "")) / "EchoAndroid"
    ov = root / "OpenVinoAsr" / "venv" / "Scripts" / "pythonw.exe"
    fw = root / "WhisperHost" / "venv" / "Scripts" / "pythonw.exe"
    exe = str(ov if ov.exists() else fw if fw.exists() else Path(sys.executable))
    subprocess.Popen([exe, "-m", "echo_desktop.voicetest"], cwd=str(Path(__file__).resolve().parents[1]),
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return True, "Opening the voice test. Press Start listening and talk; I'll type what I hear."


def main():
    VoiceTest().root.mainloop()


if __name__ == "__main__":
    main()
