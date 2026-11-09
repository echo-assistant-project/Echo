"""Hand-gesture recognition for Echo (from the MediaPipe hand-tracking workshop, tools/workshop/hand_tracking.py).

Pure rules on MediaPipe's 21 hand landmarks (normalised x, y; y grows downwards), so they're unit-tested without a
camera. desktop/EchoGestures runs the webcam and sends recognised gestures to EchoDesktop over UDP on 127.0.0.1.

Gestures -> Echo: open palm = stop / interrupt Echo, victory (two fingers) = start talking, fist = play/pause,
thumbs up / down = volume up / down, swipe left / right = previous / next track.
"""
from __future__ import annotations

import json
import math
import socket
import threading
from typing import Callable, Optional

PORT = 31418
WRIST, THUMB_MCP, THUMB_IP, THUMB_TIP = 0, 2, 3, 4
TIPS = (8, 12, 16, 20)       # index, middle, ring, pinky
PIPS = (6, 10, 14, 18)
INDEX_MCP, MIDDLE_MCP, PINKY_MCP = 5, 9, 17
ACTIONS = {"open_palm": "stop", "victory": "talk", "fist": "play_pause", "thumbs_up": "volume_up",
           "thumbs_down": "volume_down", "swipe_left": "previous", "swipe_right": "next"}


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def classify(lm: list) -> Optional[str]:
    """Static gesture from 21 (x, y) landmarks, or None when unsure."""
    if len(lm) != 21:
        return None
    size = _dist(lm[WRIST], lm[MIDDLE_MCP]) or 1e-6
    extended = [lm[t][1] < lm[p][1] - 0.15 * size for t, p in zip(TIPS, PIPS)]
    folded = [_dist(lm[t], lm[WRIST]) < _dist(lm[p], lm[WRIST]) * 1.05 for t, p in zip(TIPS, PIPS)]
    thumb_out = _dist(lm[THUMB_TIP], lm[INDEX_MCP]) > 0.6 * size
    if all(extended) and thumb_out:
        return "open_palm"
    if extended[0] and extended[1] and folded[2] and folded[3]:
        return "victory"
    if all(folded):
        tip, mcp = lm[THUMB_TIP], lm[THUMB_MCP]
        if thumb_out and tip[1] < mcp[1] - 0.5 * size and tip[1] < lm[INDEX_MCP][1] - 0.2 * size:
            return "thumbs_up"
        if thumb_out and tip[1] > mcp[1] + 0.5 * size and tip[1] > lm[PINKY_MCP][1] + 0.2 * size:
            return "thumbs_down"
        if not thumb_out:
            return "fist"
    return None


class Smoother:
    """Fires a gesture once it has been held for `hold` frames, then waits `cooldown` frames; detects swipes from
    wrist movement of an open hand. Pure: feed one frame at a time."""

    def __init__(self, hold: int = 6, cooldown: int = 25, swipe_frames: int = 12, swipe_distance: float = 0.25):
        self.hold, self.cooldown, self.swipe_frames, self.swipe_distance = hold, cooldown, swipe_frames, swipe_distance
        self.last, self.count, self.wait = None, 0, 0
        self.track = []

    def feed(self, lm: Optional[list]) -> Optional[str]:
        if self.wait > 0:
            self.wait -= 1
            self.track.clear()
            return None
        if lm is None:
            self.last, self.count = None, 0
            self.track.clear()
            return None
        self.track = (self.track + [lm[WRIST][0]])[-self.swipe_frames:]
        if len(self.track) == self.swipe_frames and abs(self.track[-1] - self.track[0]) >= self.swipe_distance:
            self.wait, self.last, self.count = self.cooldown, None, 0
            # The camera image is mirrored in EchoGestures, so x grows to the user's right.
            return "swipe_right" if self.track[-1] > self.track[0] else "swipe_left"
        g = classify(lm)
        self.count = self.count + 1 if g is not None and g == self.last else 1
        self.last = g
        if g is not None and self.count >= self.hold:
            self.wait, self.count = self.cooldown, 0
            return g
        return None


def send(gesture: str, port: int = PORT) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto(json.dumps({"gesture": gesture}).encode("utf-8"), ("127.0.0.1", port))


def listen(on_action: Callable[[str], None], port: int = PORT) -> Optional[threading.Thread]:
    """EchoDesktop side: UDP listener on 127.0.0.1 only; unknown messages are ignored."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        sock.close()
        return None

    def loop():
        while True:
            data, _ = sock.recvfrom(256)
            try:
                action = ACTIONS.get(json.loads(data.decode("utf-8")).get("gesture"))
            except (ValueError, AttributeError):
                continue
            if action:
                on_action(action)
    t = threading.Thread(target=loop, daemon=True, name="echo-gestures")
    t.start()
    return t
