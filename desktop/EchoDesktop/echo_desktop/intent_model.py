"""Echo's learned intent model (shared/intent_model.json): mirror of the phone's IntentModel.kt. Used only when no
Command Pack phrase or rule matched; names the command the person most likely meant, or "AI"."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Optional

from . import catalog
from .understanding import SpokenNumbers


class IntentModel:
    def __init__(self, text: str):
        root = json.loads(text)
        self.threshold = float(root["threshold"])
        self.labels = list(root["labels"])
        self.bias = [float(b) for b in root["bias"]]
        self.weights = {f: [(int(c), float(w)) for c, w in rows] for f, rows in root["weights"].items()}

    def classify(self, text: str) -> tuple:
        u = catalog.strip_prefix(catalog.utterance(SpokenNumbers.normalize(text)))
        words = [re.sub(r"\d+", "0", w) for w in u.words]
        scores = list(self.bias)
        for f in set(words + [a + "_" + b for a, b in zip(words, words[1:])]):
            for c, w in self.weights.get(f, ()):
                scores[c] += w
        top = max(scores)
        e = [math.exp(s - top) for s in scores]
        best = max(range(len(e)), key=lambda i: e[i])
        return self.labels[best], e[best] / sum(e)


def load(path: Path = catalog.SHARED / "intent_model.json") -> Optional[IntentModel]:
    try:
        return IntentModel(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError):
        return None
