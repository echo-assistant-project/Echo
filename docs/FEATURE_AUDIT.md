# Feature Audit

Audit date: 2026-10-29
Project: F:\Downloads\EchoPhone

## Current results

| Area | Status | Evidence and limits |
|---|---|---|
| Android debug build | PASS | Gradle assembleDebug completed successfully; APK is 22,532,410 bytes. |
| Android deployment | PASS | ADB install -r completed; package com.echo.assistant is installed on the connected Realme RMX5116IN. |
| FreeLLMAPI preservation | PASS | AssistantManager and the existing 31415 configuration were not changed for Kokoro. Both reverse routes 31415 and 31416 are active. Prior verified FreeLLMAPI API behavior remains the expected backend. |
| Kokoro assets | PASS | Int8 ONNX and voices pack are present on F: and match expected SHA-256 hashes. A real af_heart inference generated 24 kHz samples. |
| Kokoro host security | PASS | Host binds 127.0.0.1:31416; Bearer authentication and TLS are enabled. The live certificate fingerprint matched pairing data after restarting the stale listener. Private key, token, and pairing file have current-user-only ACLs. |
| Kokoro HTTP synthesis | PASS | Authenticated, fingerprint-checked request returned HTTP 200, audio/wav, and a valid RIFF/WAVE payload. |
| Android Kokoro playback | NOT YET VERIFIED | APK is installed and USB reverse is active. Phone is at its lock screen; the app still needs the private key and certificate fingerprint entered in voice settings. |
| Android TTS fallback | IMPLEMENTED, NOT DEVICE-TESTED HERE | The orb falls back to the selected installed Android voice if Kokoro service or playback fails. |
| Voice input / conversation | IMPLEMENTED, DEVICE TEST PENDING | The orb uses the Android speech recognizer in a foreground, stop-able listening loop. It is not an always-on wake-word service. |
| App actions | PARTIAL | The orb router handles explicit app and website/search requests. MainActivity handles contacts, opening the dialer, and drafting messages; sending/calling remains user-confirmed. |
| Local on-device LLM | NOT VERIFIED | MediaPipe runtime exists, but no compatible local model is bundled or installed. |
| Screen awareness | PARTIAL SCAFFOLD | Accessibility text collection exists but is not connected to the LLM request; screenshot vision is not currently working. |

## Compilation fixes made in this continuation

- PhoneActionRouter.kt: made the parsed URI null check explicit for Kotlin's nullable type.
- KokoroVoiceClient.kt: switched to the current OkHttp URL parsing extension.
- MainActivity.java: accesses Kotlin data class properties through generated Java getters.
- FloatingOrbComposeActivity.kt: removed a stale Zira cache filename.

## Files added or changed for Kokoro

- Setup-KokoroVoice.ps1: verifies/downloads pinned model assets as needed, prepares TLS identity and a random pairing token, and restricts secret file ACLs.
- Run-KokoroVoiceHost.ps1 and tools/KokoroVoice/server.py: start the authenticated loopback-only synthesis service.
- KokoroVoiceClient.kt: encrypted bearer-key storage, certificate pinning, request and WAV validation.
- FloatingOrbComposeActivity.kt: Kokoro af_heart default voice option and Android TTS fallback, alongside voice controls and continuous foreground conversation.
- PhoneActionRouter.kt: allow-listed app/web action mapping.

## Remaining verification

1. Unlock the phone and enter endpoint, Bearer key, and SHA-256 fingerprint from the private pairing file in the orb voice settings.
2. Use the voice test button, then ask a short AI question and confirm Kokoro audio plays on the phone.
3. Verify Android TTS fallback by stopping the Windows voice host and testing one spoken reply.
4. Confirm microphone permission and speech recognition on the phone. These were not granted by ADB.
