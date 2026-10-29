# EchoPhone Troubleshooting

Audit date: 2026-10-29

## Build

Use the existing F: development paths. The verified debug APK is:

    F:\Android\Build\EchoPhone\outputs\apk\debug\app-debug.apk

The project has no Gradle wrapper. Avoid Setup-Build-Deploy.ps1 when you do not want persistent environment changes. The direct build used F:\Android\Gradle\Gradle_Home, F:\Android\Sdk, F:\Temp, and F:\Android\Build.

## FreeLLMAPI

EchoPhone keeps the existing FreeLLMAPI base URL at http://127.0.0.1:31415/v1. On a USB-connected phone, add:

    F:\Android\Sdk\platform-tools\adb.exe reverse tcp:31415 tcp:31415

Do not use the phone's localhost without ADB reverse. A 401 means check the configured FreeLLMAPI key; connection refused means check that the PC service is running and reverse forwarding is active. The Kokoro voice change does not alter FreeLLMAPI requests.

## Install and configure Kokoro voice

1. Run F:\Downloads\EchoPhone\Setup-KokoroVoice.ps1 once. It verifies the model/voice files and writes private pairing information to F:\Android\EchoVoice\pairing.txt.
2. Start the local service with F:\Downloads\EchoPhone\Run-KokoroVoiceHost.ps1. It should report that the loopback listener is on port 31416.
3. For USB testing, run:

       F:\Android\Sdk\platform-tools\adb.exe reverse tcp:31416 tcp:31416

   The FreeLLMAPI reverse route on 31415 is separate and should also remain active.
4. Unlock the phone, open Echo, choose Open Echo orb preview, and scroll to voice settings.
5. Keep Kokoro af_heart selected. Enter the endpoint, Bearer key, and certificate SHA-256 from the private pairing file, then save.
6. Use the voice test button. Then ask a short question. If synthesis is unavailable, the orb uses the selected Android system TTS voice.

Never paste the Bearer key or private key into chat or commit them. Do not forward port 31416 from the router. The service binds only to 127.0.0.1. The phone cannot play Kokoro speech until it is unlocked and the app is paired.

## Voice host errors

- Certificate fingerprint mismatch: restart the service with Run-KokoroVoiceHost.ps1 and use the fingerprint from the current pairing file. An older listener may still hold a previous certificate.
- HTTP 401: setup token and app Bearer key do not match; rerun setup only if you intend to rotate credentials, then enter the new key.
- Connection refused: verify host is running and the ADB reverse tcp:31416 route exists.
- Invalid audio format: verify the running host uses tools/KokoroVoice/server.py and the Android app is up to date.
- No Kokoro audio: Android fallback is available if the device has a working TTS engine and voice.

## Feature limits

- Speech recognition uses Android's installed recognition service. It requires microphone permission and may rely on the service's own network settings.
- Continuous conversation is foreground-only and user-started. Always-on wake-word support is not implemented.
- The MediaPipe local chat fallback requires a compatible model file; no model weights are installed by default.
- Screen-awareness service is a partial scaffold. It does not currently send screen contents to the LLM.
- Phone action requests are allow-listed. Calls open the dialer, and text messages open a draft for the user to review.
