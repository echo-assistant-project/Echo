"""Echo speech-recognition host: Whisper (faster-whisper / CTranslate2) on this PC for the phone and EchoDesktop.

Security model (same as the Kokoro voice host): binds 127.0.0.1 only (the phone reaches it through
`adb reverse tcp:31417 tcp:31417`), TLS with a self-signed certificate the clients pin by SHA-256, and a random
Bearer key. Audio arrives as raw 16 kHz mono PCM, is transcribed in memory and is never written to disk or logged.

POST /v1/stt   body: PCM16LE 16 kHz mono (0.2–30 s)
               headers: X-Echo-Language: en | hi | te | … | auto   X-Echo-Prompt: base64(UTF-8) vocabulary hint
               -> {"text", "confidence", "no_speech", "language", "ms", "model"}
GET  /health   -> {"status": "ok", "model": …}
"""
import base64
import hmac
import json
import os
import re
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

import asr_engine  # same folder: the pipeline the VoiceAccuracy test measures

BACKEND = os.environ.get("ECHO_WHISPER_BACKEND", "faster-whisper")     # or "openvino" (Intel GPU, see ov_engine.py)
MODEL_NAME = os.environ.get("ECHO_WHISPER_MODEL", "small.en")
MODELS_DIR = os.environ.get("ECHO_WHISPER_MODELS_DIR", "")
TOKEN = os.environ["ECHO_WHISPER_API_KEY"]
CERT = os.environ["ECHO_WHISPER_CERT_FILE"]
KEY = os.environ["ECHO_WHISPER_KEY_FILE"]
PORT = int(os.environ.get("ECHO_WHISPER_PORT", "31417"))
MAX_BYTES = 16000 * 2 * 30
LANGUAGE = re.compile(r"^(auto|[a-z]{2,3})$")

lock = threading.Lock()
if BACKEND == "openvino":
    import ov_engine
    ov = ov_engine.OpenVinoWhisper(os.environ.get("ECHO_OV_MODEL", ov_engine.DEFAULT_MODEL))
    MODEL_NAME = f"{ov.model_name} (OpenVINO {ov.device})"
    model = None
else:
    from faster_whisper import WhisperModel
    # 8 threads measured fastest on this 14-thread Core Ultra (more threads add slow efficiency cores)
    model = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8", download_root=MODELS_DIR,
                         cpu_threads=min(8, os.cpu_count() or 4))
english_only = MODEL_NAME.endswith(".en")


def transcribe(pcm: bytes, language: str, prompt: str) -> dict:
    audio = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
    started = time.perf_counter()
    with lock:
        if model is None:
            result = ov.transcribe(audio)
        else:
            lang = "en" if english_only or language == "en" else (None if language == "auto" else language)
            result = asr_engine.transcribe(model, audio, asr_engine.Settings(prompt=prompt or None), language=lang)
    result.update(ms=int((time.perf_counter() - started) * 1000), model=MODEL_NAME)
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "EchoWhisper/1"
    sys_version = ""

    def log_message(self, fmt, *args):
        return

    def authorized(self):
        value = self.headers.get("Authorization", "")
        if not value.lower().startswith("bearer "):
            return False
        return hmac.compare_digest(value[7:].strip().encode("utf-8"), TOKEN.encode("utf-8"))

    def send_json(self, status, value):
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if not self.authorized():
            self.send_json(401, {"error": "Unauthorized"})
        elif self.path == "/health":
            self.send_json(200, {"status": "ok", "model": MODEL_NAME, "engine": "faster-whisper"})
        else:
            self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        if not self.authorized():
            self.send_json(401, {"error": "Unauthorized"})
            return
        if self.path != "/v1/stt":
            self.send_json(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            language = self.headers.get("X-Echo-Language", "en").strip().lower()
            prompt = base64.b64decode(self.headers.get("X-Echo-Prompt", ""), validate=True).decode("utf-8")[:800]
        except (ValueError, UnicodeDecodeError):
            self.send_json(400, {"error": "Invalid request headers."})
            return
        if length < 6400 or length > MAX_BYTES or length % 2:
            self.send_json(413, {"error": "Audio must be 0.2 to 30 seconds of 16 kHz mono PCM16."})
            return
        if not LANGUAGE.match(language):
            self.send_json(400, {"error": "Invalid language."})
            return
        pcm = self.rfile.read(length)
        try:
            result = transcribe(pcm, language, prompt)
        except Exception:
            self.send_json(503, {"error": "Whisper could not transcribe this audio."})
            return
        self.send_json(200, result)

    def do_HEAD(self):
        self.send_json(405, {"error": "Method not allowed."})


server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
tls.minimum_version = ssl.TLSVersion.TLSv1_2
tls.load_cert_chain(CERT, KEY)
server.socket = tls.wrap_socket(server.socket, server_side=True)
print(f"Echo Whisper host ({MODEL_NAME}, {BACKEND}) listening on loopback port {PORT}.", flush=True)
print(f"Phone over USB/wireless debugging: adb reverse tcp:{PORT} tcp:{PORT}", flush=True)
try:
    server.serve_forever(poll_interval=0.25)
finally:
    server.server_close()
