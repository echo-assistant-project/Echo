# EchoPhone Architecture

Audit date: 2026-10-28

## Build and package

- Android application ID / Kotlin package: com.echo.assistant.
- Launcher activity: MainActivity (Java), declared as the exported launcher.
- Orb/LLM screen: FloatingOrbComposeActivity (Kotlin), opened from the launcher as a preview.
- Build: Android Gradle Plugin 9.4.1, Kotlin Compose plugin 2.2.10, Compose BOM 2025.08.00, compile SDK 36, target SDK 35, minimum SDK 26.
- The project has no Gradle wrapper. Setup-Build-Deploy.ps1 invokes Gradle 9.6.0 and places build/cache/temp paths on F:, but also persists User environment variables and may download/install JDK or Android SDK packages. A direct build with process-scoped variables avoids those machine/user changes.
- local.properties must point to F:/Android/Sdk; it was malformed (s) and has been corrected.

## Runtime flows

### Launcher screen

MainActivity.java provides:
- Speech-to-text by launching the Android platform recognizer (English India locale).
- Text-to-speech using the installed Android engine.
- App launching by matching launcher-app labels.
- Contact lookup for call and message requests.
- Calls open the system dialer for user confirmation; messages open the messaging app with a prefilled draft. The app does not silently place calls or send SMS.
- These actions use simple command-prefix matching and static fallback wording. The launcher itself does not call an LLM.

### Orb preview and PC AI

FloatingOrbComposeActivity.kt provides:
- Compose orb states, tap-to-talk through Android speech recognition, typed prompts, TTS replies, a PC API URL/key form, and local model file selection.
- It calls AssistantManager using a base URL ending in /v1.
- AssistantManager.kt probes GET /v1/models, sends POST /v1/chat/completions with a bearer key and model auto, and reads the first response choice.
- Requests are non-streaming. The client does not currently provide multi-turn conversation history.
- PC screen vision is only a manager parameter accepting an optional base64 JPEG. No code in the current UI captures a screenshot or supplies an image to that parameter.

The installed FreeLLMAPI desktop UI bundle documents OpenAI-compatible Chat Completions at /v1/chat/completions, and examples use Authorization: Bearer <API key> with model auto. The running FreeLLMAPI process on this PC listened at 127.0.0.1:31415 during the audit. That bind is loopback-only and is not reachable from a separate phone over Wi-Fi.

### On-device fallback

- The app imports a user-selected file into private app storage and initializes com.google.mediapipe.tasks.genai.llminference.LlmInference on the first local request.
- The current implementation does not bundle or download weights.
- MediaPipe LLM Inference expects a model/task bundle compatible with its runtime, generally a .task model (not arbitrary GGUF or an arbitrary binary). The code currently copies any selected non-empty file without validating that it can initialize; a failed load is reported only when inference starts.
- No model is present in the installed app's files/models directory, so local inference is not currently available or verified.
- The MediaPipe Android guide currently says that API is maintenance-only and recommends LiteRT-LM for new projects: https://developers.google.com/edge/mediapipe/solutions/genai/llm_inference/android

### Other services

- WakeWordService.kt only creates a foreground-service notification. It does not listen to a microphone or detect a wake word.
- ScreenAwarenessService.kt is an opt-in AccessibilityService that collects visible node text into an in-memory string. It does not capture pixels, does not send text to the LLM, and is not connected to the current prompt flow.
- echo_accessibility_service.xml requests window-content access, which the user must enable in Android accessibility settings.
- The manifest includes Internet/network-state, contacts, overlay, notification, microphone foreground-service declarations, and allows cleartext HTTP. Cleartext should only be used on a trusted network and without exposing keys to untrusted clients.

## Data and secrets

- PC endpoint and unified API key are saved in Android SharedPreferences (echo_connection).
- The key is sent as an HTTP Bearer token. HTTP on a LAN does not encrypt that key; use HTTPS or a trusted isolated network.
- The app uses intents to pass call/message actions to Android apps. It does not send messages without the user's final action.
