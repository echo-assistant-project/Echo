# Latency & Reliability Benchmarks

Status: **phone latency not measured yet.** PC speech recognition and speed are measured; each result below is dated.

## What the app records

`LatencyLog` keeps the last 50 samples per metric in memory and writes one logcat line per sample with tag `EchoBench` (metric name and milliseconds only; no request, reply, contact, message or screen content). The orb screen's **Diagnostics → Refresh latency summary** shows count, median and p90.

| Metric | From → to |
|---|---|
| `llm_reply_ms` | Request sent to FreeLLMAPI/local model → reply received |
| `action_ms` | Validated action handed to the executor → outcome returned |
| `kokoro_first_audio_ms` | Speak requested → Kokoro WAV playback starts (synthesis + transfer + decode) |
| `android_tts_first_audio_ms` | Speak requested → Android TTS reports start |
| `voice_turn_end_of_speech_to_audio_ms` | Recognizer end-of-speech → Echo's spoken reply starts (the user-perceived voice latency) |

## Reproducible procedure

Prerequisites: debug APK installed, phone unlocked and connected over ADB (USB or wireless debugging), FreeLLMAPI running and `adb reverse tcp:31415 tcp:31415` active; for Kokoro runs also the voice host and `adb reverse tcp:31416 tcp:31416`.

```powershell
$adb = "$env:LOCALAPPDATA\EchoAndroid\Sdk\platform-tools\adb.exe"
& $adb logcat -c
# ... run the scenarios below on the phone ...
& $adb logcat -d -s EchoBench:I EchoAutomation:I > echobench.txt
```

Scenarios (10 repetitions each, same Wi-Fi/USB setup, record date, phone model, Android version, app commit):

1. **Chat, Android TTS:** voice session on, Android voice selected, ask "What is two plus two?".
2. **Chat, Kokoro:** same with Kokoro af_heart selected.
3. **Local intent:** "open YouTube" (no model call).
4. **Stop latency:** during a long spoken reply tap Stop; measure audio-stop delay from a screen recording (not instrumented).
5. **YouTube automation reliability:** "search YouTube for musicals and scroll slowly", wait 3 scrolls, say "stop", then "open the second video". Record: started / stopped on command / opened correct video / refused with a reason. Repeat with rotation, the keyboard open, and a dialog showing.
6. **Messaging safety:** "text <ambiguous first name> saying hi" must halt with options; "text <unique name> saying hi" must show the card; nothing may be sent without tapping Send.

Report medians/p90 for 1–3 and success counts for 5–6. A run counts as passed only when observed on the device.

## Results

_None recorded yet._

## Recognition and understanding results (2026-10-31, this PC: Core Ultra 5 125U, CPU only)

Speech recognition, synthetic speech (Windows OneCore voices Heera/Ravi en-IN, Mark en-US; 180 clips; tools/AsrBench):

| Recognizer | Word error rate | Commands understood | Seconds per phrase |
|---|---|---|---|
| Windows dictation (old EchoDesktop push-to-talk) | 51% | 26% | n/a |
| Whisper base.en | 4.8% | 91% | 1.2 |
| Whisper base.en + Echo vocabulary | 4.1% | 91% | 1.5 |
| Whisper small.en | 2.5% | 94% | 4.5 |

Understanding real people's requests (SLURP, CC BY 4.0; rules tuned on devel, learned model trained on train, scored on the
held-out test split of 2,941 human transcripts; tools/SlurpEval + SlurpEvalTest):

| | Before (devel) | Rules (test) | Rules + learned model (test) |
|---|---|---|---|
| Overall correct | 68.6% | 88.4% | 93.1% |
| Must be handled on the device | 19.3% | 66.1% | 85.4% |
| AI-only requests not misfired | 91.3% | 99.1% | 98.6% |

Not yet measured: SLURP real recordings through Whisper (600 test clips downloaded; transcription was still running),
the Android recognizer and anything on the phone.

## Real human speech (2026-10-31, tools/VoiceAccuracy, this PC: Core Ultra 5 125U, CPU only, int8)

Real recordings with human-written transcripts, dev half, scored with Whisper's English normaliser.
Accuracy = 1 − word error rate. RTF = seconds of computing per second of audio (above 1 = slower than real time).

Echo's live recognizer today (Whisper small.en), all 343 dev clips:

| Speech | Clips | Accuracy | RTF |
|---|---|---|---|
| Audiobooks, clear (LibriSpeech clean) | 40 | 98.1% | 0.65 |
| TED talks | 40 | 96.0% | 0.71 |
| European Parliament speeches | 40 | 93.0% | 1.14 |
| Audiobooks, harder (LibriSpeech other) | 40 | 92.7% | 1.03 |
| Many accents, read aloud (Common Voice) | 29 | 86.4% | 0.84 |
| People talking to an assistant (SLURP) | 40 | 78.9% | 1.38 |
| YouTube & podcasts (GigaSpeech) | 39 | 74.8% | 1.85 |
| Earnings phone calls | 40 | 69.9% | 2.49 |
| Meeting snippets, 1–3 words each (AMI) | 35 | 66.7% | 3.93 |
| **All words** | 343 | **90.7%** | 1.07 |

Bigger model (large-v3-turbo) on the 203 clips it finished, same clips for both:

| | small.en (live) | large-v3-turbo |
|---|---|---|
| All words | 88.7% | **91.1%** |
| Earnings calls | 69.9% | 81.1% |
| Common Voice accents | 86.4% | 90.8% |
| YouTube & podcasts | 74.8% | 78.4% |
| Clear audiobooks | 98.1% | 98.1% |
| Speed (RTF) | 1.17 | **4.71** (8–21 on short commands) |

What this means:
- Clear speech is already at 96–98%. Short, noisy, overlapping speech (calls, meetings, one-word clips) is where errors are.
- On a CPU-only laptop, the large model is too slow for live voice: Whisper always processes a 30-second window, so a
  2-second command costs as much as a 30-second one. Live voice keeps small.en. Use large-v3-turbo for videos and
  recordings, or on a PC with an NVIDIA GPU: `Run-WhisperHost.ps1 -Model large-v3-turbo`.
- 100% is not reachable on real-world speech by any recognizer; careful human transcribers typically differ by
  ~4–5% on conversational speech.
- Not run: the held-out test half and the 28 talking videos at full length. The large-model run was stopped
  because the PC ran low on memory (15 GB RAM). A 1-minute smoke test of two NASA videos with Whisper base.en scored 94.6%.
### Speed for live voice (40 real assistant requests, SLURP dev, same clips)

| Recognizer | Words right | Median time per request |
|---|---|---|
| small.en, CPU, 14 threads (before) | 77.1% | 4.07 s |
| small.en, CPU, 8 threads | 77.1% | 3.59 s |
| small.en, CPU, greedy decoding | 75.5% | 4.04 s |
| distil-small.en, CPU | 67.6% | 4.64 s |
| base.en, CPU | 68.8% | 1.56 s |
| small.en int8, **Intel GPU** (OpenVINO) | 72.7% | **1.04 s** |
| **large-v3-turbo int8, Intel GPU** (OpenVINO) — new default | **81.8%** | 2.89 s |

The Whisper host now runs large-v3-turbo on the Intel GPU when `tools\WhisperHost\Setup-OpenVino.ps1` has been run
(compiled model cached: ~2 s to start after the first time), else small.en on the CPU with 8 threads. Beam search isn't
available on the GPU (greedy only). The NPU couldn't load the model with OpenVINO GenAI 2026.3.1. Measured end to end
through EchoDesktop's client: 2.3 s for "Please mute my speaker." (correct).

- A bug in the test runner was fixed before these numbers: Common Voice reuses ids across clips, which had paired some
  recordings with the wrong sentence.

## Speed: "Echo Turbo" (2026-11-01, tools/SpeedBench/bench.py, this PC: Core Ultra 5 125U)

Run it yourself: `py -3.12 tools\SpeedBench\bench.py`. No sound plays and no microphone is used (the helpers get null
audio through `ECHO_SPEECH_BENCH=1`). The AI rows use a **simulated** FreeLLMAPI on this PC (first token after 0.6 s,
then 30 tokens a second), because real AI speed depends on the provider; every other row is real.

| What | Before | Now | Faster |
|---|---:|---:|---:|
| Voice starts speaking (Windows voice) | 823 ms | 64 ms | 12.8× |
| Microphone starts listening (push-to-talk / after "Hey Echo") | 675 ms | 9 ms* | 72× |
| Echo's own overhead per voice command (listen start + parse + voice start) | 1,498 ms | 74 ms | 20× |
| AI reply ready to speak (simulated AI) | 1,870 ms | 739 ms | 2.5× |
| AI question → first spoken word (reply + voice start) | 2,693 ms | 803 ms | 3.4× |
| Command Pack ready at start-up | 1,390 ms | 102 ms | 13.7× |
| One voice command understood (parse) | 0.43 ms | 0.37 ms | — |

\* with the null microphone; attaching a real microphone adds about 35 ms (measured separately), so ~45 ms.

What changed:
- **Warm voice helpers** (`voice.WarmPool`, `speech.ps1 -Standby`): the Windows voice, the dictation recogniser and the
  stop/wait listener are kept loaded and waiting, so a reply or a listen starts at once instead of starting PowerShell and
  System.Speech every time. A waiting helper has not attached the microphone. Costs ~260 MB RAM; Settings → "Instant voice".
- **Streamed AI answers** (`ChatClient.stream`, `streaming.SentenceChunker`): Echo speaks the first sentence while the AI
  is still writing the rest; Kokoro synthesises the next sentence while the current one plays. Replies that start like an
  action (JSON) are still collected whole and checked as before. Settings → "Speak AI answers while they're still being written".
- **Command Pack cache**: the parsed pack is stored under `%LOCALAPPDATA%\EchoDesktop\cache` (keyed by a hash of every
  command file and Echo's source); regexes compile on first use; candidate order is sorted once per first word.
- **Phone**: same streaming (SSE in `AssistantManager.askStreaming`, `VoiceOutput.speakStream`, Kotlin `SentenceChunker`
  with the same test cases) and the `GET /v1/models` check before every question is now cached for 60 s (one fewer round
  trip per question). Unit-tested and built; **not yet measured on the phone**.
- Echo shows its own timings after each reply ("⚡ answer in 12 ms · voice in 41 ms"), and "how fast are you" reads out the
  measured medians for this session.

The AI's own thinking time (first token) is the provider's; Echo can't make that shorter, only stop adding to it.
