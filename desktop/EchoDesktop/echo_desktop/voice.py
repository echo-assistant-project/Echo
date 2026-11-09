"""Speech in/out for EchoDesktop: Kokoro (pinned TLS, same host as the phone) or the built-in Windows voice,
and Windows speech recognition for push-to-talk and the "Hey Echo" wake phrase. All helpers are fixed scripts;
text travels on stdin, never on a command line."""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import queue
import re
import shutil
import ssl
import subprocess
import tempfile
import threading
import time
import winsound
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

HELPERS = Path(__file__).parent / "helpers"
POWERSHELL = shutil.which("powershell") or r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
NO_WINDOW = 0x08000000


def helper_command(script: str, *args: str) -> list:
    return [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(HELPERS / script), *args]


def find_pairing() -> Optional[dict]:
    """Reads the Kokoro pairing file written by Setup-KokoroVoice.ps1 (key + certificate fingerprint)."""
    for root in (Path(os.environ.get("LOCALAPPDATA", "")) / "EchoAndroid", Path("F:/Android")):
        path = root / "EchoVoice" / "pairing.txt"
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        key = re.search(r"^Bearer key:\s*(\S+)", text, re.M)
        pin = re.search(r"^Server certificate SHA-256:\s*([0-9a-fA-F]{64})", text, re.M)
        if key and pin:
            return {"key": key.group(1), "fingerprint": pin.group(1).lower()}
    return None


def kokoro_wav(endpoint: str, key: str, fingerprint: str, text: str, rate: float, voice: str) -> bytes:
    url = urlparse(endpoint)
    if url.scheme != "https" or url.hostname not in ("127.0.0.1", "localhost") or url.port != 31416 or url.path != "/v1/tts":
        raise ValueError("Kokoro endpoint must be https://127.0.0.1:31416/v1/tts")
    if not key or not re.fullmatch(r"[0-9a-f]{64}", fingerprint or ""):
        raise ValueError("Kokoro key or certificate fingerprint is missing")
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE          # replaced by the exact certificate pin below
    conn = http.client.HTTPSConnection(url.hostname, url.port, context=context, timeout=45)
    try:
        conn.connect()
        der = conn.sock.getpeercert(binary_form=True)
        if not der or hashlib.sha256(der).hexdigest() != fingerprint:
            raise ValueError("Kokoro certificate fingerprint does not match")
        body = json.dumps({"text": text[:4000], "rate": min(max(rate, 0.6), 1.2), "voice": voice}).encode("utf-8")
        conn.request("POST", url.path, body, {"Authorization": "Bearer " + key, "Content-Type": "application/json", "Accept": "audio/wav"})
        response = conn.getresponse()
        data = response.read(12 * 1024 * 1024 + 1)
        if response.status != 200 or response.getheader("Content-Type", "").split(";")[0].strip() != "audio/wav":
            raise ValueError(f"Kokoro returned HTTP {response.status}")
        if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
            raise ValueError("Kokoro returned an invalid WAV")
        return data
    finally:
        conn.close()


def speak_text(text: str) -> str:
    """Strip Markdown so symbols and code aren't read aloud (same rule as the phone)."""
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"\[([^\]]*)]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_`#>|~]+", "", text)
    return re.sub(r"\s+", " ", text).strip() or text


class WarmPool:
    """Keeps one speech helper per mode started, loaded and waiting (speech.ps1 -Standby), so Echo starts talking or
    listening at once instead of paying ~0.4–0.6 s of PowerShell + System.Speech start-up every time. A waiting helper
    has not attached the microphone. With enabled() false it simply starts a fresh helper each time (the old way)."""
    MODES = {"speak": ("-Stream",), "listen": (), "interrupt": ()}
    MAX_AGE = 900.0                      # replace stale helpers (default audio device or voice may have changed)

    def __init__(self, enabled: Callable[[], bool] = lambda: False):
        self.enabled = enabled
        self._ready: dict = {}
        self._lock = threading.Lock()
        self._closed = False

    def _spawn(self, mode: str) -> subprocess.Popen:
        # The helper prints WAITING once loaded (stdout); listen/interrupt readers ignore that line.
        return subprocess.Popen(helper_command("speech.ps1", "-Mode", mode, "-Standby", *self.MODES[mode]),
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)

    @staticmethod
    def _loaded(proc) -> bool:
        """Block until the helper says WAITING (fully loaded). False if it died first."""
        out = getattr(proc, "stdout", None)
        if out is None:
            return proc.poll() is None
        try:
            return out.readline().strip() == b"WAITING"
        except (OSError, ValueError):
            return False

    @staticmethod
    def _discard(proc: subprocess.Popen) -> None:
        try:
            if proc.poll() is None:
                proc.kill()
        except OSError:
            pass

    def take(self, mode: str) -> subprocess.Popen:
        """A helper waiting for its first stdin line (speak: the rate; listen/interrupt: "go")."""
        with self._lock:
            entry = self._ready.pop(mode, None)
        proc = None
        if entry is not None:
            p, born = entry
            if p.poll() is None and time.monotonic() - born < self.MAX_AGE:
                proc = p
            else:
                self._discard(p)
        if proc is None:
            proc = self._spawn(mode)
        self.refill(mode)
        return proc

    def refill(self, mode: str) -> None:
        if self._closed or not self.enabled():
            return
        with self._lock:
            entry = self._ready.get(mode)
            if entry is not None and entry[0].poll() is None:
                return

        def run():
            try:
                p = self._spawn(mode)
            except OSError:
                return
            if not self._loaded(p):           # only fully loaded helpers are handed out
                self._discard(p)
                return
            with self._lock:
                if self._closed or mode in self._ready:
                    extra = p
                else:
                    self._ready[mode], extra = (p, time.monotonic()), None
            if extra is not None:
                self._discard(extra)
        threading.Thread(target=run, daemon=True).start()

    def warm(self, *modes: str) -> None:
        for m in modes or tuple(self.MODES):
            self.refill(m)

    def ready(self) -> list:
        with self._lock:
            return sorted(m for m, (p, _) in self._ready.items() if p.poll() is None)

    def drain(self) -> None:
        """Let go of the waiting helpers (setting turned off); they're started again by warm()."""
        with self._lock:
            entries, self._ready = list(self._ready.values()), {}
        for p, _ in entries:
            self._discard(p)

    def close(self) -> None:
        self._closed = True
        self.drain()


class SpeechStream:
    """Sentences in, voice out, in order. Speaking starts with the first sentence; close() when the text is complete."""

    def __init__(self, q: "queue.Queue"):
        self._q = q
        self.closed = False

    def feed(self, sentence: str) -> None:
        if not self.closed and sentence and sentence.strip():
            self._q.put(sentence)

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self._q.put(None)


class Speaker:
    STREAM_IDLE_LIMIT = 120.0            # seconds without a new sentence before a stream counts as finished

    def __init__(self, settings, pool: Optional[WarmPool] = None):
        self.settings = settings
        self.pool = pool or WarmPool()
        self._proc: Optional[subprocess.Popen] = None
        self._token = 0
        self._lock = threading.Lock()
        self.last_notice = ""
        self.first_audio_at = 0.0         # time.monotonic() when the current reply started sounding (for latency stats)

    def speak(self, text: str, voice: str, rate: float, on_done: Callable[[], None]) -> None:
        stream = self.stream(voice, rate, on_done)
        from .streaming import sentences
        for s in sentences(text):
            stream.feed(s)
        stream.close()

    def stream(self, voice: str, rate: float, on_done: Callable[[], None]) -> SpeechStream:
        """Start a reply whose sentences arrive over time (the AI is still writing). Kokoro synthesises the next
        sentence while the current one plays; the Windows voice speaks each line as it arrives."""
        self.stop()
        with self._lock:
            self._token += 1
            token = self._token
        q: queue.Queue = queue.Queue()
        threading.Thread(target=self._run, args=(token, q, voice, rate, on_done), daemon=True).start()
        return SpeechStream(q)

    def stop(self) -> None:
        with self._lock:
            self._token += 1
            proc, self._proc = self._proc, None
        if proc and proc.poll() is None:
            proc.kill()
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except RuntimeError:
            pass

    def _current(self, token: int) -> bool:
        with self._lock:
            return token == self._token

    def _next(self, q) -> Optional[str]:
        try:
            item = q.get(timeout=self.STREAM_IDLE_LIMIT)
        except queue.Empty:
            return None
        return None if item is None else speak_text(item)

    def _heard(self) -> None:
        if not self.first_audio_at:
            self.first_audio_at = time.monotonic()

    def _kokoro(self, token, q, voice, rate) -> tuple:
        """Speak with Kokoro, synthesising one sentence ahead. Returns (finished, leftover sentences for the Windows
        voice). finished=True means the stream's end was reached (nothing more to read from q)."""
        wavs: queue.Queue = queue.Queue()
        state = {"ended": False, "left": []}
        endpoint, key, pin = self.settings["kokoro_endpoint"], self.settings.secret("kokoro_key"), self.settings["kokoro_fingerprint"]

        def synth():
            try:
                while self._current(token):
                    s = self._next(q)
                    if s is None:
                        state["ended"] = True
                        return
                    try:
                        wavs.put(kokoro_wav(endpoint, key, pin, s, rate, voice))
                    except Exception as e:      # the rest goes to the Windows voice
                        self.last_notice = f"Kokoro unavailable ({e}); using the Windows voice."
                        state["left"].append(s)
                        return
            finally:
                wavs.put(None)
        threading.Thread(target=synth, daemon=True).start()
        while True:
            wav = wavs.get()
            if wav is None or not self._current(token):
                break
            fd, path = tempfile.mkstemp(prefix="echo-voice-", suffix=".wav")
            with os.fdopen(fd, "wb") as f:
                f.write(wav)
            try:
                self._heard()
                winsound.PlaySound(path, winsound.SND_FILENAME)   # blocks; stop() purges it
            finally:
                os.remove(path)
        return state["ended"], state["left"]

    def _run(self, token, q, voice, rate, on_done):
        self.last_notice = ""
        self.first_audio_at = 0.0
        try:
            left: list = []
            if self.settings["use_kokoro"] and self.settings.secret("kokoro_key"):
                ended, left = self._kokoro(token, q, voice, rate)
                if ended or not self._current(token):
                    return
            proc = self.pool.take("speak")
            with self._lock:
                if token != self._token:
                    proc.kill()
                    return
                self._proc = proc
            proc.stdin.write(f"{max(-10, min(10, round((rate - 1) * 10)))}\n".encode())
            pending = list(left)
            while True:
                s = pending.pop(0) if pending else self._next(q)
                if s is None or not self._current(token):
                    break
                proc.stdin.write((" ".join(s.split()) + "\n").encode("utf-8"))
                proc.stdin.flush()
                self._heard()
            proc.stdin.close()
            proc.wait(timeout=300)
        except Exception as e:
            if self._current(token):
                self.last_notice = f"Speech failed: {e}"
        finally:
            if self._current(token):
                on_done()


class Listener:
    """Push-to-talk (one utterance) and the wake-phrase loop, via Windows speech recognition."""

    def __init__(self, pool: Optional[WarmPool] = None):
        self.pool = pool or WarmPool()
        self._listen: Optional[subprocess.Popen] = None
        self._wake: Optional[subprocess.Popen] = None
        self._interrupt: Optional[subprocess.Popen] = None

    def listen_nbest(self, timeout: int = 8) -> tuple:
        """One utterance -> (hypotheses best-first, confidences). Empty lists when nothing was heard."""
        self.stop_wake()
        if timeout == 8:                     # the warm helper uses the default timeout
            proc = self.pool.take("listen")
            proc.stdin.write(b"go\n")
            proc.stdin.flush()
        else:
            proc = subprocess.Popen(helper_command("speech.ps1", "-Mode", "listen", "-TimeoutSeconds", str(timeout)),
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NO_WINDOW)
        self._listen = proc
        try:
            out, _ = proc.communicate(timeout=timeout + 15)
        except subprocess.TimeoutExpired:
            proc.kill()
            return [], []
        finally:
            self._listen = None
        texts, scores = [], []
        for line in out.decode("utf-8", "replace").splitlines():
            conf, sep, text = line.partition("\t")
            if sep and text.strip():
                texts.append(text.strip())
                try:
                    scores.append(float(conf.replace(",", ".")))
                except ValueError:
                    scores.append(-1.0)
        return texts, scores

    def listen_once(self, timeout: int = 8) -> str:
        texts, _ = self.listen_nbest(timeout)
        return texts[0] if texts else ""

    def start_interrupt(self, on_stop: Callable[[], None]) -> None:
        """While Echo talks: a small stop/wait grammar, so the user can cut Echo off by voice (barge-in)."""
        self.stop_interrupt()
        proc = self.pool.take("interrupt")
        try:
            proc.stdin.write(b"go\n")
            proc.stdin.flush()
        except OSError:
            return
        self._interrupt = proc

        def read():
            for raw in proc.stdout:
                if raw.decode("utf-8", "replace").strip() == "STOP":
                    on_stop()
                    return
        threading.Thread(target=read, daemon=True).start()

    def stop_interrupt(self) -> None:
        proc, self._interrupt = self._interrupt, None
        if proc and proc.poll() is None:
            proc.kill()

    def cancel_listen(self) -> None:
        proc = self._listen
        if proc and proc.poll() is None:
            proc.kill()

    def start_wake(self, on_wake: Callable[[], None]) -> None:
        if self._wake and self._wake.poll() is None:
            return
        proc = subprocess.Popen(helper_command("speech.ps1", "-Mode", "wake"), stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
        self._wake = proc

        def read():
            for raw in proc.stdout:
                if raw.decode("utf-8", "replace").strip() == "WAKE":
                    on_wake()
        threading.Thread(target=read, daemon=True).start()

    def stop_wake(self) -> None:
        proc, self._wake = self._wake, None
        if proc and proc.poll() is None:
            proc.kill()


def read_screen_text(timeout: int = 40) -> str:
    out = subprocess.run(helper_command("screen_ocr.ps1"), capture_output=True, timeout=timeout, creationflags=NO_WINDOW)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.decode("utf-8", "replace").strip().splitlines()[-1] if out.stderr else "OCR failed")
    return out.stdout.decode("utf-8", "replace").strip()
