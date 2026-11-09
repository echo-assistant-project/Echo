"""Whisper speech recognition for EchoDesktop: microphone capture via Windows' winmm waveIn (ctypes, no packages),
the phone's voice-activity rules (port of Vad in VoiceRules.kt), and a pinned-TLS client for the local Whisper host
(tools/WhisperHost). Audio stays in memory and goes only to that host on 127.0.0.1."""
from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes as wt
import hashlib
import http.client
import json
import math
import os
import ssl
import struct
import threading
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

RATE = 16000
FRAME = 320                      # 20 ms


class Vad:
    """Energy VAD with adaptive noise floor (same constants as the phone)."""

    def __init__(self, start_frames=5, end_frames=35):
        self.start_frames, self.end_frames = start_frames, end_frames
        self.floor, self.speaking, self.above, self.gap, self.below = -60.0, False, 0, 0, 0
        self.speech_frames, self.mean, self.dev = 0, 0.0, 3.0

    @staticmethod
    def level_db(frame: bytes) -> float:
        n = len(frame) // 2
        if n == 0:
            return -90.0
        samples = struct.unpack(f"<{n}h", frame[: n * 2])
        rms = math.sqrt(sum(s * s for s in samples) / n)
        return -90.0 if rms < 1 else max(20 * math.log10(rms / 32768.0), -90.0)

    def process(self, db: float) -> Optional[str]:
        threshold = max(self.floor + 9, -50)
        loud = db > threshold
        if not self.speaking:
            if loud:
                self.above, self.gap = self.above + 1, 0
            elif self.above > 0 and self.gap < 1:
                self.gap += 1
            else:
                self.above = self.gap = 0
                self.floor = 0.7 * self.floor + 0.3 * db if db < self.floor else 0.985 * self.floor + 0.015 * db
                self.floor = min(max(self.floor, -80), -25)
            if self.above >= self.start_frames:
                self.speaking, self.below, self.speech_frames = True, 0, 0
                return "start"
        else:
            self.below = 0 if loud else self.below + 1
            if self.below >= self.end_frames:
                self.speaking, self.above, self.gap = False, 0, 0
                return "end"
            self.speech_frames += 1
            self.mean = db if self.speech_frames == 1 else 0.95 * self.mean + 0.05 * db
            self.dev = 3.0 if self.speech_frames == 1 else 0.95 * self.dev + 0.05 * abs(db - self.mean)
            if self.speech_frames > 150 and self.dev < 1.5:
                self.floor = min(max(self.mean, -80), -25)
                self.speaking, self.above, self.gap, self.speech_frames = False, 0, 0, 0
                return "end"
        return None


class _WaveFormat(ctypes.Structure):
    _fields_ = [("wFormatTag", wt.WORD), ("nChannels", wt.WORD), ("nSamplesPerSec", wt.DWORD), ("nAvgBytesPerSec", wt.DWORD),
                ("nBlockAlign", wt.WORD), ("wBitsPerSample", wt.WORD), ("cbSize", wt.WORD)]


class _WaveHdr(ctypes.Structure):
    _fields_ = [("lpData", ctypes.c_void_p), ("dwBufferLength", wt.DWORD), ("dwBytesRecorded", wt.DWORD),
                ("dwUser", ctypes.c_void_p), ("dwFlags", wt.DWORD), ("dwLoops", wt.DWORD), ("lpNext", ctypes.c_void_p),
                ("reserved", ctypes.c_void_p)]


def record_utterance(cancel: Optional[threading.Event] = None, max_seconds: float = 15, no_speech_seconds: float = 7) -> bytes:
    """Records from the default microphone until ~0.7 s of silence after speech. Returns PCM16 16 kHz mono
    (with 300 ms before the speech started), or b"" when nobody spoke."""
    winmm = ctypes.windll.winmm
    winmm.waveInOpen.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint, ctypes.POINTER(_WaveFormat), ctypes.c_void_p, ctypes.c_void_p, wt.DWORD]
    for name in ("waveInPrepareHeader", "waveInAddBuffer", "waveInUnprepareHeader"):
        getattr(winmm, name).argtypes = [ctypes.c_void_p, ctypes.POINTER(_WaveHdr), ctypes.c_uint]
    for name in ("waveInStart", "waveInStop", "waveInReset", "waveInClose"):
        getattr(winmm, name).argtypes = [ctypes.c_void_p]
    fmt = _WaveFormat(1, 1, RATE, RATE * 2, 2, 16, 0)
    handle = ctypes.c_void_p()
    if winmm.waveInOpen(ctypes.byref(handle), 0xFFFFFFFF, ctypes.byref(fmt), 0, 0, 0) != 0:
        raise OSError("No microphone is available.")
    size, count = FRAME * 2 * 5, 8                   # 100 ms buffers
    buffers = [ctypes.create_string_buffer(size) for _ in range(count)]
    headers = [_WaveHdr(ctypes.cast(b, ctypes.c_void_p), size, 0, None, 0, 0, None, None) for b in buffers]
    audio, vad, started_at, speech_start = bytearray(), Vad(), time.monotonic(), None
    try:
        for h in headers:
            winmm.waveInPrepareHeader(handle, ctypes.byref(h), ctypes.sizeof(h))
            winmm.waveInAddBuffer(handle, ctypes.byref(h), ctypes.sizeof(h))
        winmm.waveInStart(handle)
        i, done = 0, False
        while not done:
            if cancel is not None and cancel.is_set():
                return b""
            h = headers[i]
            if not h.dwFlags & 1:                     # WHDR_DONE
                time.sleep(0.01)
                continue
            chunk = ctypes.string_at(h.lpData, h.dwBytesRecorded)
            h.dwFlags &= ~1
            winmm.waveInAddBuffer(handle, ctypes.byref(h), ctypes.sizeof(h))
            i = (i + 1) % count
            for k in range(0, len(chunk) - FRAME * 2 + 1, FRAME * 2):
                frame = chunk[k:k + FRAME * 2]
                audio.extend(frame)
                event = vad.process(Vad.level_db(frame))
                if event == "start" and speech_start is None:
                    speech_start = max(0, len(audio) - (5 + 15) * FRAME * 2)   # keep ~300 ms before speech
                elif event == "end" and speech_start is not None:
                    done = True
                    break
            elapsed = time.monotonic() - started_at
            if elapsed > max_seconds or (speech_start is None and elapsed > no_speech_seconds):
                done = True
    finally:
        winmm.waveInStop(handle)
        winmm.waveInReset(handle)
        for h in headers:
            winmm.waveInUnprepareHeader(handle, ctypes.byref(h), ctypes.sizeof(h))
        winmm.waveInClose(handle)
    return bytes(audio[speech_start:]) if speech_start is not None else b""


def find_whisper_pairing() -> Optional[dict]:
    path = Path(os.environ.get("LOCALAPPDATA", "")) / "EchoAndroid" / "WhisperHost" / "pairing.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if data.get("key") and data.get("fingerprint") and data.get("endpoint"):
        return {"endpoint": data["endpoint"], "key": data["key"], "fingerprint": data["fingerprint"].lower()}
    return None


def transcribe(pcm: bytes, pairing: dict, prompt: str = "", language: str = "en", timeout: float = 20) -> dict:
    url = urlparse(pairing["endpoint"])
    if url.scheme != "https" or url.hostname not in ("127.0.0.1", "localhost") or url.path != "/v1/stt":
        raise ValueError("Whisper endpoint must be https://127.0.0.1:<port>/v1/stt")
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE          # replaced by the exact certificate pin below
    conn = http.client.HTTPSConnection(url.hostname, url.port, context=context, timeout=timeout)
    try:
        conn.connect()
        der = conn.sock.getpeercert(binary_form=True)
        if not der or hashlib.sha256(der).hexdigest() != pairing["fingerprint"]:
            raise ValueError("Whisper host certificate fingerprint does not match")
        conn.request("POST", url.path, pcm, {"Authorization": "Bearer " + pairing["key"], "Content-Type": "application/octet-stream",
                                            "X-Echo-Language": language,
                                            "X-Echo-Prompt": base64.b64encode(prompt[:600].encode("utf-8")).decode("ascii")})
        response = conn.getresponse()
        body = response.read(65536)
        if response.status != 200:
            raise ValueError(f"Whisper host returned HTTP {response.status}")
        return json.loads(body)
    finally:
        conn.close()
