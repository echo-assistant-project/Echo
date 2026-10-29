# EchoPhone Architecture

Audit date: 2026-10-29

## Build and app flow

- Android application ID: com.echo.assistant.
- MainActivity is the launcher and exposes standalone phone actions.
- FloatingOrbComposeActivity contains the Compose orb, chat with AssistantManager, voice settings, and continuous foreground voice loop.
- The debug app uses Android Gradle Plugin 9.4.1, Kotlin Compose plugin 2.2.10, compile SDK 36, target SDK 35, minimum SDK 26.
- The debug APK is built to F:\Android\Build\EchoPhone\outputs\apk\debug\app-debug.apk. Android SDK, Gradle home, temp, and build output are on F:.
- The project has no Gradle wrapper; use the existing Gradle installation with process-scoped paths rather than the setup script that changes persistent environment variables.

## AI request path

- AssistantManager sends non-streaming OpenAI-compatible requests to the saved FreeLLMAPI URL, normally http://127.0.0.1:31415/v1, with model auto, messages, and an optional Bearer key.
- It probes and chats against the same validated /v1 base and reports HTML/non-JSON responses without attempting unsafe JSON parsing.
- Recent conversation turns are kept in memory for follow-up questions. The existing FreeLLMAPI integration is unchanged by the voice update.
- USB access requires ADB reverse forwarding for tcp:31415. The connection is local to the PC and USB route; do not expose the API publicly.
- The optional local MediaPipe inference path requires a compatible user-selected model. No model is bundled or downloaded by EchoPhone.

## Speech output: Kokoro default

- Default voice in the orb chat is Kokoro-82M voice af_heart. The model runs on the Windows PC in a local Python ONNX Runtime service. Android receives WAV audio and plays it.
- Model files are stored outside the repository at F:\Android\KokoroVoice\models. The int8 ONNX file is 114,119,327 bytes and the voice pack is 28,214,398 bytes. Both are SHA-256 checked by Setup-KokoroVoice.ps1.
- The voice host binds only to 127.0.0.1:31416, requires a random Bearer token, uses TLS, and only accepts synthesis requests at /v1/tts. It does not expose a router-facing network listener.
- Android pins the server certificate SHA-256, validates the allowed loopback endpoint, stores the Bearer key encrypted using Android Keystore, validates the WAV response, and falls back to the selected Android system TTS voice if Kokoro is unavailable.
- Voice credentials are created in F:\Android\EchoVoice\pairing.txt. Setup applies a per-file ACL granting access only to the current Windows user. Treat that file as private.
- USB access requires ADB reverse tcp:31416. The Android app must be paired by entering the endpoint, Bearer key, and certificate fingerprint into the orb voice settings.
- The basic MainActivity standalone controls still use Android TextToSpeech; Kokoro is the default for spoken chat replies in the orb activity. Android speech recognition remains the phone's system recognition service.
- Actual Kokoro inference and the authenticated TLS WAV endpoint have been tested on the PC. Phone-side audio playback has not yet been verified because voice credentials still need to be entered in the phone UI.

## Voice conversation and phone actions

- The orb supports tap-to-start continuous foreground speech recognition, visible transcripts, chat responses, stop control, and restart listening after the reply.
- PhoneActionRouter accepts explicit allow-listed requests for opening apps, websites, Google search, YouTube search, and Spotify search. It does not execute arbitrary model text.
- MainActivity supports app opening, contact lookup, opening the dialer, and preparing a message draft. Calls and texts require the user's final action in Android's own app.
- Background wake-word listening is not implemented or claimed.

## Other existing components

- WakeWordService remains a notification-only scaffold.
- ScreenAwarenessService is an opt-in accessibility service that collects visible node text; it is not wired into the current LLM message path and does not take screenshots.
- No Windows backend source is part of the Android project. The Kokoro local voice host is the only new PC-side companion component.
