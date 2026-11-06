# Echo architecture

Audit: 2026-10-29. This describes the checkout at feature/safe-sync-setup-ci and distinguishes source that exists from integrations that have not been verified.

## System map

    User
      |
      v
    EchoPhone (MainActivity + Compose orb)
      |-- PhoneActionRouter --> Android intents
      |-- Android SpeechRecognizer
      |-- AssistantManager --> external FreeLLMAPI
      |                       \-> optional imported MediaPipe model
      |-- KokoroVoiceClient -- HTTPS, bearer, certificate pin
                               |
                               +-- ADB reverse for USB
                                     |
                                     v
                           Windows Kokoro host (loopback:31416)
                                     |
                                     v
                         Kokoro-82M af_heart ONNX assets
      \-- Android TextToSpeech fallback

## Android architecture

- MainActivity.java is the app launcher and provides standalone phone controls. It can launch apps, look up a contact, open the dialer, and prepare a message draft. Placing a call or sending a message still requires the user to act in Android system UI.
- FloatingOrbComposeActivity.kt implements the Compose orb, conversation UI, voice settings, speech recognition loop, and response playback. The user starts and stops a foreground listening session; this is not always-on wake-word recognition.
- AssistantManager.kt probes the configured /v1/models endpoint and sends non-streaming OpenAI-compatible /v1/chat/completions requests with model auto. Recent turns are held in app memory for context. If remote AI is unavailable, an imported compatible MediaPipe model can answer text requests. No local model is bundled.
- PhoneActionRouter.kt maps a limited set of explicit phrases to Android intents for installed apps, websites, Google search, YouTube search, and Spotify search. Model prose is not executed as code.
- ScreenAwarenessService.kt is an opt-in Android accessibility service. It reads visible UI text into an in-memory field on the device. The current chat path does not send that text to the model, and the service does not capture screenshots.
- WakeWordService.kt is a notification-only scaffold. It does not listen for or detect a wake word.

## Windows-side architecture

There is no EchoDesktop application or .sln/.csproj in this checkout. The PC-side component here is the optional Kokoro voice host:

- tools/KokoroVoice/server.py loads kokoro-onnx and listens on 127.0.0.1:31416.
- Run-KokoroVoiceHost.ps1 loads local model paths, TLS files, and a bearer token into the process environment, then starts Python.
- Setup-KokoroVoice.ps1 installs the isolated Python environment and downloads/checks Kokoro assets when absent. It creates local TLS/pairing material outside the repository and restricts its ACL.
- The service accepts authenticated /v1/tts POST requests and returns WAV audio. It is not an AI chat backend and does not expose a router-facing listener.

## AI/backend architecture

- FreeLLMAPI is external and is neither included nor started by this repository. EchoPhone normally uses an endpoint ending in /v1, often http://127.0.0.1:31415/v1.
- On a USB-connected phone, adb reverse tcp:31415 tcp:31415 makes the phone loopback port reach the PC service. Port forwarding and service startup are separate.
- The Android app also has a MediaPipe LLM Inference code path. It requires a compatible model file imported onto the device. Without that file, offline AI chat is unavailable.
- No backend gateway, hosted API, account service, or model distribution service exists in this repository.

## Speech and action flow

1. Android system SpeechRecognizer converts foreground speech to text.
2. The orb first checks whether an explicit allow-listed phone action matches.
3. Otherwise the request goes to AssistantManager and FreeLLMAPI, or to an imported local MediaPipe model when remote AI is unavailable.
4. For spoken replies, the default orb voice is Kokoro af_heart on the paired PC. The phone calls the authenticated HTTPS service through ADB reverse and validates the pinned certificate and WAV response.
5. If Kokoro is unavailable, the orb falls back to the selected Android TextToSpeech voice. The standalone launcher also uses Android TextToSpeech.
6. After a reply, the foreground conversation loop can resume listening while the session remains active.

Kokoro model files total about 143 MB and are not tracked. Each PC needs its own Python environment, model assets, certificate, bearer token, and pairing configuration.