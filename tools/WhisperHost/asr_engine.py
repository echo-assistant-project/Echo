"""Echo's speech-recognition pipeline (shared by the Whisper host and the VoiceAccuracy test, so what is measured is
exactly what Echo runs).

Pipeline: clean up the audio (remove DC hum and rumble, even out loudness) -> Whisper with Silero voice-activity
detection -> drop Whisper's known phantom phrases and runaway repetitions.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import numpy as np

SAMPLE_RATE = 16000

# Whisper's well-known "hallucinations" on silence or noise; dropped when the model itself isn't confident.
PHANTOMS = {"thank you", "thank you.", "thanks for watching!", "thanks for watching.", "you", "bye.", "bye", ".", "",
            "thank you for watching.", "please subscribe.", "thank you so much for watching.", "subtitles by the amara.org community"}


@dataclass
class Settings:
    beam_size: int = 5
    best_of: int = 5
    patience: float = 1.0
    prompt: str | None = None
    hotwords: str | None = None
    vad: bool = True
    vad_min_silence_ms: int = 500
    vad_speech_pad_ms: int = 400
    vad_threshold: float = 0.5
    clean_audio: bool = False          # optional loudness/rumble clean-up; not yet measured at scale, so off by default
    condition_on_previous_text: bool = False
    temperatures: tuple = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
    compression_ratio_threshold: float = 2.4
    log_prob_threshold: float = -1.0
    no_speech_threshold: float = 0.6
    repetition_penalty: float = 1.0
    no_repeat_ngram_size: int = 0
    length_penalty: float = 1.0
    extra: dict = field(default_factory=dict)


def clean(audio: np.ndarray) -> np.ndarray:
    """Remove DC offset and low rumble (<~70 Hz), then bring speech to a steady level (-20 dBFS RMS on the loud part),
    with a soft limiter. Quiet far-away voices get louder; clipped loud ones are tamed."""
    if audio.size == 0:
        return audio
    x = audio.astype(np.float32) - float(np.mean(audio))
    # high-pass: subtract a ~14 ms moving average (removes hum/rumble below ~70 Hz, keeps the voice band)
    win = SAMPLE_RATE // 70
    if len(x) > win * 2:
        c = np.cumsum(np.concatenate(([0.0], x.astype(np.float64))))
        half = win // 2
        idx = np.arange(len(x))
        lo = np.clip(idx - half, 0, len(x))
        hi = np.clip(idx + half + 1, 0, len(x))
        y = (x - (c[hi] - c[lo]) / (hi - lo)).astype(np.float32)
    else:
        y = x
    # level from the loudest 30% of 20 ms frames (the speech, not the pauses)
    frame = SAMPLE_RATE // 50
    n = len(y) // frame
    if n >= 3:
        rms = np.sqrt(np.mean(y[: n * frame].reshape(n, frame) ** 2, axis=1) + 1e-12)
        loud = np.sort(rms)[int(n * 0.7):]
        level = float(np.mean(loud))
    else:
        level = float(np.sqrt(np.mean(y ** 2) + 1e-12))
    if level > 1e-5:
        gain = min(10 ** (-20 / 20) / level, 30.0)
        y = y * gain
    return np.tanh(y * 1.2) / math.tanh(1.2) if np.max(np.abs(y)) > 0.95 else y


_REPEAT = re.compile(r"\b(\w+(?:\s+\w+){0,5}?)(?:[\s,.]+\1\b){3,}", re.IGNORECASE)


def tidy(text: str) -> str:
    """Collapse runaway repetitions ('the the the the', 'I don't know. I don't know. ...') that Whisper sometimes loops on."""
    text = _REPEAT.sub(lambda m: m.group(1), text)
    return re.sub(r"\s+", " ", text).strip()


def transcribe(model, audio: np.ndarray, settings: Settings | None = None, language: str | None = "en") -> dict:
    s = settings or Settings()
    x = clean(audio) if s.clean_audio else audio.astype(np.float32)
    kwargs = dict(language=language, beam_size=s.beam_size, best_of=s.best_of, patience=s.patience,
                  condition_on_previous_text=s.condition_on_previous_text, initial_prompt=s.prompt or None,
                  without_timestamps=False, vad_filter=s.vad, temperature=list(s.temperatures),
                  compression_ratio_threshold=s.compression_ratio_threshold, log_prob_threshold=s.log_prob_threshold,
                  no_speech_threshold=s.no_speech_threshold, repetition_penalty=s.repetition_penalty,
                  no_repeat_ngram_size=s.no_repeat_ngram_size, length_penalty=s.length_penalty)
    if s.vad:
        kwargs["vad_parameters"] = {"min_silence_duration_ms": s.vad_min_silence_ms, "speech_pad_ms": s.vad_speech_pad_ms,
                                    "threshold": s.vad_threshold}
    if s.hotwords:
        kwargs["hotwords"] = s.hotwords
    kwargs.update(s.extra)
    segments, info = model.transcribe(x, **kwargs)
    segments = list(segments)
    text = tidy(" ".join(seg.text.strip() for seg in segments))
    logprob = sum(seg.avg_logprob for seg in segments) / len(segments) if segments else -5.0
    no_speech = max((seg.no_speech_prob for seg in segments), default=1.0)
    confidence = math.exp(max(logprob, -5.0))
    if text.lower() in PHANTOMS and (no_speech > 0.4 or confidence < 0.5):
        text, confidence = "", 0.0
    return {"text": text, "confidence": round(confidence, 3), "no_speech": round(no_speech, 3),
            "language": getattr(info, "language", language)}
