# Echo

Echo is a cross-device assistant project. This repository currently contains EchoPhone for Android and an optional Windows Kokoro voice host. It does not contain EchoDesktop, FreeLLMAPI, or a bundled language model.

EchoPhone combines an Android Compose interface, an OpenAI-compatible FreeLLMAPI client, optional MediaPipe local text inference, Android speech recognition, and spoken replies through Kokoro-82M af_heart on a paired Windows PC or Android TextToSpeech fallback.

## Start here

- [Architecture](docs/ARCHITECTURE.md)
- [Development and setup](docs/DEVELOPMENT.md)
- [Team workflow and synchronization](docs/TEAM_WORKFLOW.md)
- [Security](docs/SECURITY.md)
- [Current status and verification](docs/CURRENT_STATUS.md)
- [Codex handoff](docs/CODEX_HANDOFF.md)

Older notes remain in [feature audit](docs/FEATURE_AUDIT.md), [troubleshooting](docs/TROUBLESHOOTING.md), and [repository design](docs/UNIFIED_REPOSITORY_DESIGN.md).

## Build EchoPhone

On Windows, install Git for Windows and use Android Studio/JDK or the supplied setup script. The project does not include gradlew.bat.

    Copy-Item scripts\echo-env.example.ps1 .echo-env.ps1
    notepad .echo-env.ps1
    . .\.echo-env.ps1
    .\Setup-Build-Deploy.ps1

See [Development](docs/DEVELOPMENT.md) for prerequisites, tests, backend setup, and Kokoro setup. Paths are machine-specific; secrets and model files are not in Git.

## Current verification

The Android debug build and available Gradle unit-test task were run on 2026-10-29. The APK is at F:\Android\Build\EchoPhone\outputs\apk\debug\app-debug.apk. The unit-test task reports NO-SOURCE; this project currently has no Kotlin/Java unit tests. See [Current status](docs/CURRENT_STATUS.md) for results and blockers.

## Collaboration

The private repository is https://github.com/echo-assistant-project/Echo. Use main for stable shared work and short-lived feature/* or fix/* branches for changes. The safe synchronization script is scripts/sync-project.ps1; it does not transfer uncommitted edits. See [Team workflow](docs/TEAM_WORKFLOW.md).

A Windows desktop app, continuous wake-word recognition, working screen vision, phone-side Kokoro playback verification, and automatic sync are not currently established features.