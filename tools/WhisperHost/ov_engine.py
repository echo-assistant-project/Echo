"""Whisper on the Intel GPU (OpenVINO GenAI): the fast + accurate backend for Echo on Intel Core Ultra laptops.

Measured on this PC (Core Ultra 5 125U, Intel Graphics). Speed, 5 spoken requests (2026-11-03):
  small.en int8 on the GPU        0.82 s median   <- default: speed first
  large-v3-turbo int8 on the GPU  2.09 s median   (more accurate on real voices: 81.8% vs 77.1% words, SLURP dev)
  small.en (faster-whisper, CPU)  4.67 s median
Pick the turbo model with Run-WhisperHost.ps1 -Model large-v3-turbo.
Beam search isn't available on the GPU, so decoding is greedy. The compiled model is cached, so loads after the first
take a couple of seconds. Lives in its own venv (%LOCALAPPDATA%\\EchoAndroid\\OpenVinoAsr), set up by Setup-OpenVino.ps1.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

HOME = Path(os.environ.get("LOCALAPPDATA", "")) / "EchoAndroid" / "OpenVinoAsr"
DEFAULT_MODEL = "whisper-small.en-int8-ov"
PHANTOMS = {"thank you", "thank you.", "thanks for watching!", "thanks for watching.", "you", "bye.", "bye", ".", "",
            "thank you for watching.", "please subscribe."}


def available(model: str = DEFAULT_MODEL) -> bool:
    return (HOME / "models" / model / "openvino_encoder_model.xml").exists()


class OpenVinoWhisper:
    def __init__(self, model: str = DEFAULT_MODEL, device: str = "GPU"):
        import openvino_genai as ov_genai
        path = HOME / "models" / model
        cache = HOME / "models" / "cache"
        cache.mkdir(parents=True, exist_ok=True)
        try:
            self.pipe = ov_genai.WhisperPipeline(str(path), device, CACHE_DIR=str(cache))
            self.device = device
        except Exception:                       # no usable GPU driver: same model on the CPU
            self.pipe = ov_genai.WhisperPipeline(str(path), "CPU", CACHE_DIR=str(cache))
            self.device = "CPU"
        self.model_name = model.replace("whisper-", "").replace("-int8-ov", "")
        self.config = self.pipe.get_generation_config()
        if ".en-" not in model:
            self.config.language = "<|en|>"
            self.config.task = "transcribe"

    def transcribe(self, audio: np.ndarray, prompt: str | None = None) -> dict:
        """audio: float32 16 kHz mono. Returns the same shape as asr_engine.transcribe."""
        from asr_engine import tidy
        if audio.size < 1600:
            return {"text": "", "confidence": 0.0, "no_speech": 1.0, "language": "en"}
        # The vocabulary prompt is not used here: it was not part of the measured setup.
        text = tidy(str(self.pipe.generate(audio.astype(np.float32).tolist(), self.config)).strip())
        if text.lower() in PHANTOMS:
            text = ""
        return {"text": text, "confidence": 0.9 if text else 0.0, "no_speech": 0.0 if text else 1.0, "language": "en"}
