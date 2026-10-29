# Troubleshooting

Audit date: 2026-10-28

## 1. Build fails before Kotlin compilation

This project has no gradlew.bat. Existing build tools are under F:. Setup-Build-Deploy.ps1 also writes persistent User environment variables and can download/install tools. Review it before running.

The project's local.properties must contain:

    sdk.dir=F:/Android/Sdk

It contained only s during the audit. This was corrected. A debug build was performed with process-only paths so Gradle cache, temp files, SDK, and output stayed on F:.

## 2. Echo says the PC API is unavailable

The orb client expects a base URL ending in /v1, such as:

    http://<reachable-host>:<port>/v1

It requests GET /models below that base and submits non-streaming POST /chat/completions with model: auto, chat messages, and the configured key as Authorization: Bearer <key>. The FreeLLMAPI desktop UI bundle documents /v1/chat/completions, Bearer keys, and a model field with auto in its example.

Do not use localhost on the phone: that means the phone itself. Find the actual API host/port and API key in FreeLLMAPI's own API/Keys settings. Never paste a real key into a public chat or commit it to source.

### What this PC showed during the audit

- FreeLLMAPI desktop process version observed in its process arguments: 0.16.10.
- No listener existed on port 3001.
- FreeLLMAPI was listening at 127.0.0.1:31415; this is a loopback-only listener.
- http://127.0.0.1:31415/ served the local dashboard.
- Unauthenticated GET /v1/models returned HTTP 401, consistent with an authenticated route.
- The process-private desktop token also returned 401 and is not a valid substitute for a user API key.
- Phone route was cellular (100.109.55.152 on rmnet_data2); the PC was on Wi-Fi at 192.168.1.11.

Therefore a phone cannot reach the observed loopback listener over Wi-Fi, and the tested phone/PC were not on the same LAN route. This is not currently evidence of a Windows firewall block. First configure a supported LAN-reachable API listener in FreeLLMAPI (if its settings support one), or run a PC-side relay/proxy that deliberately exposes the API to the phone. Only then test firewall access for that exact port and network profile. Do not expose the port to public networks.

### Recommended connection sequence

1. In FreeLLMAPI, use its documented API/Keys screen to create or copy a unified API key; keep it private.
2. Determine its supported API base URL and port. A desktop loopback URL cannot be used by a phone.
3. Put the PC and phone on the same reachable Wi-Fi, or use a secured VPN route. Cellular-only routing will not reach a private 192.168.x.x address.
4. In the Echo orb preview, enter the reachable base URL ending in /v1, paste the API key, then choose Save and check PC.
5. HTTP 401 means authentication/key problem; connection refused/timeout means address, listener, route, or firewall problem. The orb screen now shows the HTTP/network diagnostic rather than silently hiding it.
6. After probe succeeds, send a short prompt. A successful /models probe alone does not prove a chat completion works.

## 3. Local model fallback unavailable

The installed app had no files/models directory, so no local model is installed. Echo does not download model weights. The import picker copies a user file, but the current code does not validate model compatibility until first inference.

MediaPipe LLM Inference Android expects a compatible task bundle, commonly a .task file. A generic GGUF or arbitrary .bin model is not interchangeable. Model bundles can consume substantial storage and memory; actual startup/inference depends on the model and device. No model was downloaded or tested in this audit.

Google's Android guide says MediaPipe LLM Inference is maintenance-only, points to task-bundle models, and recommends migrating to LiteRT-LM for new Android applications: https://developers.google.com/edge/mediapipe/solutions/genai/llm_inference/android

## 4. Voice, screen, and background behavior

- Voice recognition is delegated to Android's installed speech recognizer; verify its language/offline settings and microphone permission.
- Android TTS chooses an installed voice heuristically; install/select the desired English voice in system TTS settings if it sounds wrong.
- WakeWordService does not record audio or detect a wake word. Echo currently requires user interaction.
- Screen service reads accessibility-node text only after the user enables it. It neither takes screenshots nor passes collected text to the model.

## 5. Deployment

The debug APK built and was installed successfully on the authorized device with serial 105f4f18; Android reported package com.echo.assistant. The APK output is:

    F:\Android\Build\EchoPhone\outputs\apk\debug\app-debug.apk

The app was not granted elevated call/SMS permissions by ADB. Calls and SMS use Android review intents.
