"""Webcam vision for Echo: grab one frame when the user asks ("what do you see?") and hand it to the AI.

OpenCV is optional (EchoDesktop core stays standard-library only). Install it once with:
    py -3.12 -m pip install opencv-python
The camera is opened only for the moment of capture and released straight away; no image is written to disk.
"""
from __future__ import annotations

import base64
import time

MAX_SIDE = 768        # keeps the upload small and fast; enough detail for vision models
JPEG_QUALITY = 80
WARMUP_FRAMES = 5     # first frames are often dark while auto-exposure settles


class VisionError(Exception):
    pass


def _cv2():
    try:
        import cv2  # type: ignore
    except ImportError:
        raise VisionError("Camera vision needs OpenCV. Run: py -3.12 -m pip install opencv-python") from None
    return cv2


def scaled_size(width: int, height: int, max_side: int = MAX_SIDE) -> tuple:
    """Size that fits inside max_side x max_side, keeping the aspect ratio (never upscales)."""
    if width <= 0 or height <= 0:
        raise VisionError("The camera returned an empty frame.")
    scale = min(1.0, max_side / max(width, height))
    return max(1, round(width * scale)), max(1, round(height * scale))


def capture_jpeg(camera: int = 0) -> bytes:
    """One JPEG frame from the webcam, mirrored like a selfie view and resized for upload."""
    cv2 = _cv2()
    backend = getattr(cv2, "CAP_DSHOW", 0)          # DirectShow opens fast on Windows
    cap = cv2.VideoCapture(camera, backend) if backend else cv2.VideoCapture(camera)
    try:
        if not cap.isOpened():
            raise VisionError("I couldn't open the webcam. Is another app (or EchoGestures) using it?")
        frame = None
        for _ in range(WARMUP_FRAMES):
            ok, img = cap.read()
            if ok and img is not None:
                frame = img
            time.sleep(0.03)
        if frame is None:
            raise VisionError("The webcam didn't send a picture.")
    finally:
        cap.release()
    h, w = frame.shape[:2]
    nw, nh = scaled_size(w, h)
    if (nw, nh) != (w, h):
        frame = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
    if not ok:
        raise VisionError("Couldn't encode the camera picture.")
    return buf.tobytes()


def data_url(jpeg: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")


def image_message(text: str, jpeg: bytes) -> list:
    """OpenAI-compatible multimodal user content (text + image)."""
    return [{"type": "text", "text": text}, {"type": "image_url", "image_url": {"url": data_url(jpeg)}}]
