import hmac
import io
import json
import os
import re
import ssl
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
from kokoro_onnx import Kokoro

MODEL = os.environ["ECHO_KOKORO_MODEL"]
VOICES = os.environ["ECHO_KOKORO_VOICES"]
TOKEN = os.environ["ECHO_VOICE_API_KEY"]
CERT = os.environ["ECHO_VOICE_CERT_FILE"]
KEY = os.environ["ECHO_VOICE_KEY_FILE"]

kokoro = Kokoro(MODEL, VOICES)
synthesis_lock = threading.Lock()
DEFAULT_VOICE = "af_heart"
VOICE_PATTERN = re.compile(r"^[a-z]{2}_[a-z]{2,16}$")
try:
    AVAILABLE_VOICES = set(kokoro.get_voices())
except Exception:
    AVAILABLE_VOICES = {DEFAULT_VOICE}


def pick_voice(requested):
    """Persona voices are allow-listed against the installed voice pack; anything else uses af_heart."""
    if isinstance(requested, str) and VOICE_PATTERN.match(requested) and requested in AVAILABLE_VOICES:
        return requested
    return DEFAULT_VOICE


def as_wav(samples, sample_rate):
    audio = np.asarray(samples, dtype=np.float32).reshape(-1)
    pcm = np.clip(audio, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2", copy=False)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(int(sample_rate))
        wav.writeframes(pcm.tobytes())
    return buffer.getvalue()


class Handler(BaseHTTPRequestHandler):
    server_version = "EchoKokoro/1"
    sys_version = ""

    def log_message(self, fmt, *args):
        return

    def authorized(self):
        value = self.headers.get("Authorization", "")
        if not value.lower().startswith("bearer "):
            return False
        provided = value[7:].strip().encode("utf-8")
        expected = TOKEN.encode("utf-8")
        return hmac.compare_digest(provided, expected)

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
            self.send_json(200, {"status": "ok", "voice": DEFAULT_VOICE, "voices": sorted(AVAILABLE_VOICES), "engine": "Kokoro-82M"})
        else:
            self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        if not self.authorized():
            self.send_json(401, {"error": "Unauthorized"})
            return
        if self.path != "/v1/tts":
            self.send_json(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 32768:
                self.send_json(413, {"error": "Request size must be between 2 and 32768 bytes."})
                return
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("JSON body must be an object")
            text = str(data.get("text", "")).strip()
            speed = float(data.get("rate", 0.9))
            voice = pick_voice(data.get("voice"))
            if not text or len(text) > 4000:
                self.send_json(400, {"error": "Text is required and limited to 4,000 characters."})
                return
            if not 0.6 <= speed <= 1.2:
                self.send_json(400, {"error": "Rate must be from 0.6 to 1.2."})
                return
        except (ValueError, TypeError, json.JSONDecodeError):
            self.send_json(400, {"error": "Invalid JSON request."})
            return

        try:
            with synthesis_lock:
                lang = "en-gb" if voice.startswith("b") else "en-us"
                samples, sample_rate = kokoro.create(text, voice=voice, speed=speed, lang=lang)
            audio = as_wav(samples, sample_rate)
        except Exception:
            self.send_json(503, {"error": "Kokoro could not synthesize this text."})
            return
        # Send outside the synthesis try: a client disconnect must not trigger a second response.
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("X-Echo-Voice", voice)
        self.send_header("Content-Length", str(len(audio)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(audio)

    def do_HEAD(self):
        self.send_json(405, {"error": "Method not allowed."})


server = ThreadingHTTPServer(("127.0.0.1", 31416), Handler)
tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
tls.minimum_version = ssl.TLSVersion.TLSv1_2
tls.load_cert_chain(CERT, KEY)
server.socket = tls.wrap_socket(server.socket, server_side=True)
print("Kokoro-82M af_heart voice host listening on loopback port 31416.", flush=True)
print("Use adb reverse tcp:31416 tcp:31416 for USB phone access.", flush=True)
try:
    server.serve_forever(poll_interval=0.25)
finally:
    server.server_close()
    close_voices = getattr(kokoro.voices, "close", None)
    if callable(close_voices):
        close_voices()
