# Third-party licenses

Checked 2026-10-29. "Verified" means read from the source named in the row during this review; everything else must be checked before redistribution.

## Android app (shipped in the APK)

| Component | License | Status |
|---|---|---|
| AndroidX / Jetpack Compose (BOM 2025.08.00), Activity, Lifecycle, Core | Apache-2.0 | Not re-verified (standard AndroidX license). |
| kotlinx-coroutines-android 1.7.3 | Apache-2.0 | Not re-verified. |
| OkHttp 4.12.0 | Apache-2.0 | Not re-verified. |
| MediaPipe tasks-genai 0.10.14 | Apache-2.0 | Not re-verified. Google marks MediaPipe LLM Inference as maintenance-only. |

Test-only (not shipped): JUnit 4.13.2 (EPL-1.0), org.json 20240303 (public-domain dedication in recent releases; not re-verified).

## PC voice host (`tools/KokoroVoice`, not distributed with the app)

| Component | License | Status |
|---|---|---|
| Kokoro-82M weights (hexgrad) | Apache-2.0 | Verified: Hugging Face model card metadata `license: apache-2.0`. |
| kokoro-onnx 0.6.1 | MIT | Partly verified: PyPI metadata has no license field; the README states "kokoro-onnx: MIT". |
| espeakng-loader (dependency of kokoro-onnx) | Not declared on PyPI | PyPI metadata has no license; it appears to ship an eSpeak NG native library. |
| eSpeak NG, phonemizer (dependencies) | Believed GPL-3.0 | **Not verified.** If the voice host is ever redistributed (installer, bundled binaries), GPL-3.0 obligations likely apply. Personal local use is unaffected. |
| onnxruntime, numpy | MIT / BSD-3-Clause | Not re-verified. |

## Model weights the user imports

Any MediaPipe `.task` model the user imports carries its own license (for example Gemma terms). Echo does not bundle one.

## Speech understanding data and models (2026-10-31)

- `shared/intent_model.json` is a small model trained by `tools/SlurpEval/train_intent_model.py` on the **SLURP** dataset
  (Bastianelli, Vanzo, Swietojanski, Rieser: "SLURP: A Spoken Language Understanding Resource Package", EMNLP 2020),
  licensed **CC BY 4.0** (https://github.com/pswietojanski/slurp). Attribution is required when distributing the model.
  SLURP text and audio themselves are not in this repository; the evaluation downloads them to a temporary folder.
- `tools/WhisperHost` uses **faster-whisper** (MIT) with OpenAI **Whisper** model weights (MIT), downloaded from
  Hugging Face at setup; `cryptography` (Apache-2.0/BSD), `requests` (Apache-2.0).

## Skills (`shared/skills`, 2026-11-03)

Markdown only (no scripts). Each collection's licence file is kept at `shared/skills/<collection>/LICENSE.txt`, and every `SKILL.md` names its source repository and commit. Verified: read from the cloned repositories during this review.

| Collection | Skills | License | Status |
|---|---:|---|---|
| obra/superpowers (Jesse Vincent) | 5 | MIT | Verified (root LICENSE). |
| addyosmani/agent-skills (Addy Osmani) | 20 | MIT | Verified (root LICENSE). |
| NousResearch/hermes-agent (Nous Research) | 22 | MIT | Verified (root LICENSE); `humanizer` also carries its own MIT licence (Siqi Chen), kept beside it. |
| anthropics/skills (Anthropic): frontend-design, internal-comms, discernment-nudge | 3 | Apache-2.0 | Verified (per-skill LICENSE.txt). docx/pdf/pptx/xlsx are proprietary and were not taken. |
| alirezarezvani/claude-skills (Alireza Rezvani): contract-and-proposal-writer | 1 | MIT | Verified (root LICENSE). |
| Echo's own everyday skills (`shared/skills/echo`) | 12 | Echo's | Written for Echo. |