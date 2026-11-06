# Development setup

This guide is for a second Windows PC as well as the founder's PC. Do not assume a username, drive letter, SDK path, Python installation, model, or API credential is shared.

## Requirements

For Android development:

- Git for Windows.
- Android SDK platform 36 and Build Tools 36.0.0.
- Java 17 or a compatible Android Studio JDK.
- Gradle 9.6.0. This project has no Gradle wrapper.
- About 12 GB free on the selected tool/build volume is recommended by the setup script.

Optional Windows voice host:

- Python 3.12.
- Kokoro model/voice assets (about 143 MB total) and packages listed in tools/KokoroVoice/requirements.txt.
- A Windows PC to run the host. Android TextToSpeech can be used without it.

FreeLLMAPI is not included. The developer must run a compatible service or receive separately issued, revocable backend access.

## Clone and local paths

The co-founder account `praviramc-web` has been verified, but its organization invitation has not been sent yet. After the founder confirms the Owner invitation, and `praviramc-web` accepts it and Owner/repository access is verified:

    git clone https://github.com/echo-assistant-project/Echo.git
    cd Echo

For a local path template:

    Copy-Item scripts\echo-env.example.ps1 .echo-env.ps1
    notepad .echo-env.ps1
    . .\.echo-env.ps1

The template contains paths only. It selects F: when present and otherwise uses the current user's Local AppData. Edit it for the local machine. .echo-env.ps1 is ignored by Git. Never put keys or passwords in it.

## Install tools and build

The setup script locates or downloads Java 17, Android command-line tools, Gradle, and Android SDK packages under the chosen locations. It checks downloaded archives and does not clean unrelated files. By default environment changes apply only to that PowerShell process. -PersistEnvironment opts into user environment changes.

    .\Setup-Build-Deploy.ps1

To build/test later from a configured PowerShell session:

    gradle --no-daemon testDebugUnitTest assembleDebug

The test task currently has no Kotlin/Java test sources (NO-SOURCE). A successful APK build is not a phone UI or microphone test.

The APK goes under ECHO_BUILD_ROOT, which defaults to F:\Android\Build\EchoPhone when F: exists, otherwise the user's local Echo directory. A phone is optional for compilation. Installation requires a connected, USB-debug-authorized device.

## Configure FreeLLMAPI

1. Start FreeLLMAPI on the developer's PC and confirm its OpenAI-compatible API is available.
2. In EchoPhone settings, set the base endpoint to the service root ending in exactly one /v1, normally http://127.0.0.1:31415/v1.
3. Enter that developer's own key if the service requires it. The app's AI key is local to Android app storage; it is not a repository credential.
4. For USB access, run:

       adb reverse tcp:31415 tcp:31415

The app probes /v1/models and sends chat requests to /v1/chat/completions. Do not open the service to the public internet or router. For Wi-Fi, use a trusted network, a deliberately secured HTTPS endpoint, and appropriate firewall controls; this repository does not configure those controls.

## Configure optional Kokoro voice

Kokoro runs on the Windows PC, not on the phone:

    .\Setup-KokoroVoice.ps1
    .\Run-KokoroVoiceHost.ps1

Setup creates a local venv, downloads/checks assets if missing, and generates per-PC certificate, key, bearer token, and pairing file outside Git. Review the download size and network use before running setup on a new machine. Keep the pairing file private.

For USB audio:

    adb reverse tcp:31416 tcp:31416

In the orb voice settings, choose Kokoro and enter the endpoint, bearer key, and certificate fingerprint from that PC's pairing file. Do not copy another developer's key or TLS private key. If the host is unavailable, the app uses Android TextToSpeech.

## Checks

- Android compile and available tests: gradle --no-daemon testDebugUnitTest assembleDebug.
- Kokoro source syntax: use Python 3.12 to compile tools/KokoroVoice/*.py without importing packages or loading models.
- There is no EchoDesktop solution/project, Kotlin/Java test source, or Python backend test suite in the inspected repository.
- Hardware tests for microphone, phone actions, Kokoro playback, and Android permissions require the Android device. Do not claim those passed based on a desktop build.

## Troubleshooting

- Gradle cannot find Android SDK: check local.properties and ANDROID_SDK_ROOT; keep local.properties local/ignored.
- Gradle/JDK startup: use Java 17 and Gradle 9.6.0; check JAVA_HOME, F: space, Gradle cache access, and antivirus/quarantine before deleting caches.
- API connection refused: start FreeLLMAPI, confirm its port and key, check the API base ends in /v1, and run the 31415 reverse command for USB.
- HTML instead of JSON: the configured endpoint may be the FreeLLMAPI web UI rather than its API. Check the endpoint and /v1 path.
- Kokoro unavailable: start the host, verify its model files and per-PC pairing settings, and confirm USB reverse 31416. Never print the token to logs or chat.
- No offline reply: import a model supported by the MediaPipe path. A model file is not bundled.
- No app action: phrase a supported action explicitly and check that the target app is installed. Spotify/YouTube search opens a search destination; it does not guarantee playback.