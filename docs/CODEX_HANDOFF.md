# Echo Project — Codex Handoff

Updated: 2026-10-29
Project: F:\Downloads\EchoPhone

## Current repository state

- Existing repository preserved; no new repository initialized.
- Current working branch: feature/safe-sync-setup-ci.
- Latest remote checkpoint: ffffb8b — Add safe sync, Windows setup, and Android CI. Local Stage 9 documentation begins at 6a80599; subsequent local handoff/status checkpoint(s) are also present. Inspect git log/status for the current local tip.
- Local main and origin/main are e3c7a57. Remote feature branch points to ffffb8b and descends from origin/main.
- Remote URL: https://github.com/echo-assistant-project/Echo.git.
- Stage 9 documentation and its handoff/status updates are committed locally after ffffb8b. They remain unpushed. Inspect git log/status for the current tip. Current instruction prohibits publishing them without explicit approval.
- A prior push of ffffb8b succeeded. A draft PR was not created: GitHub connector returned 404 and gh CLI is unavailable. Do not assume PR or CI exists.
- Do not push, create a PR/release, or change collaborators during recovery unless the user explicitly approves.

## Project audit facts

- This checkout contains EchoPhone Android source and an optional Windows Kokoro voice host in tools/KokoroVoice.
- No EchoDesktop .sln/.csproj or other desktop project exists here.
- Android: application ID com.echo.assistant; MainActivity Java launcher; FloatingOrbComposeActivity Kotlin/Compose orb; AssistantManager chat/network/local-model router; PhoneActionRouter allow-listed Android intents.
- Build: AGP 9.4.1, Kotlin Compose plugin 2.2.10, compile SDK 36, target SDK 35, min SDK 26; no Gradle wrapper.
- FreeLLMAPI is external. The Android client uses an OpenAI-compatible /v1/models probe and /v1/chat/completions request with model auto, optional bearer key, and recent in-memory turns.
- MediaPipe local inference code requires a compatible imported model; none is bundled.
- Kokoro host binds to Windows loopback port 31416, authenticates with a bearer token, serves HTTPS/WAV, and uses Kokoro-82M af_heart assets stored outside Git. Android pins the cert and encrypts its Kokoro key through Android Keystore; Android TextToSpeech is fallback.
- FreeLLMAPI key is stored in app SharedPreferences, not Android Keystore.
- Foreground SpeechRecognizer voice session exists. WakeWordService is notification-only and does not detect a wake word.
- ScreenAwarenessService reads accessible UI text in memory but is not connected to chat and does not capture screenshots.
- PhoneActionRouter covers a bounded set of app/web/search intents. Contact/dialer/message-draft flow exists; sending/calling and actual Spotify/YouTube playback are not guaranteed.
- No Kotlin/Java unit test sources or Python backend test suite exist.

## Stage 9 — documentation

Status: COMPLETE locally.

Canonical documents:
- README.md
- docs/ARCHITECTURE.md
- docs/DEVELOPMENT.md
- docs/TEAM_WORKFLOW.md
- docs/SECURITY.md
- docs/CURRENT_STATUS.md
- docs/CODEX_HANDOFF.md

Existing docs/FEATURE_AUDIT.md, docs/TROUBLESHOOTING.md, docs/DEVELOPER_SETUP.md, docs/COLLABORATION_GUIDE.md, and docs/UNIFIED_REPOSITORY_DESIGN.md remain for additional details. No source components were moved.

## Stage 10 — verified outcomes

- Existing project: PASSED.
- Backup: PASSED. F:\Downloads\EchoPhone-final-backup-20261029-192827.zip exists, 168,122 bytes, SHA-256 5879e929f9f08fb4073fed66ceab4755b4eedef4d25957ae79a5ed490002e008, matching the recorded value. Prior handoff says extraction matched commit 98eeb6e.
- Tracked text credential scan: PASSED bounded scan; no matches for selected API key/bearer/private-key patterns. Not an exhaustive binary/remote-history audit.
- Repository privacy/founder role: PASSED based on preceding setup session verification (private Echo repo; Akshaj-echo Owner). Current GitHub connector returned no repo details for re-verification.
- Co-founder role: BLOCKED pending exact GitHub username and accepted invitation.
- Remote files: Stage 6–8 commit present at origin/feature/safe-sync-setup-ci. Stage 9 docs are local and intentionally not pushed under the current instruction.
- History: PASSED; feature branch descends from origin/main e3c7a57; no reset, rebase, or force-push.
- Android: PASSED on 2026-10-29. Existing Gradle 9.6.0, Android SDK 36, Android Studio Java 25; command used one worker and a 768 MB heap. testDebugUnitTest was NO-SOURCE; assembleDebug succeeded. Fresh APK: F:\Android\Build\EchoPhone\outputs\apk\debug\app-debug.apk, 22,532,672 bytes. No device install/test because phone is disconnected.
- First Android build attempt failed when Gradle daemon disappeared after dexing. A one-worker/smaller-heap retry passed. Gradle reported deprecation warnings for Gradle 10.
- Kokoro Python 3.12 syntax: PASSED for tools/KokoroVoice/server.py. Model inference/host runtime not retested during Stage 9.
- EchoDesktop build: NOT TESTED; no desktop source project exists to build.
- Sync script: BLOCKED for end-to-end safety tests. PowerShell parser passed earlier, but sandbox account lacked write access to F:\Downloads\EchoPhone\.git lock and disposable Git object storage. Do not claim data-preservation behavior was test-proven.
- Uncommitted edit protection: NOT TESTED end-to-end.
- Documentation: PASSED against inspected source/config.
- Public deployment: PASSED; no public repo/release/deployment created in Stage 9.
- Task Scheduler: no task created or activated.
- Current CI workflow: committed on the remote feature branch, but NOT TESTED because no PR or workflow run is confirmed.

## Current blockers and next actions

1. Review docs/CURRENT_STATUS.md. It contains the Stage 10 matrix and limitations.
2. If the user approves publishing this documentation checkpoint, push the local branch and create/review a PR; only then can CI run. Until then, keep Stage 9 local.
3. Obtain the co-founder's exact GitHub username before inviting them; verify accepted Owner access afterward.
4. For sync-script safety acceptance, run the smoke tests as the Windows account that owns the F: checkout: fast-forward local main while a feature branch and an untracked edit are present, then assert feature HEAD and file bytes are unchanged. Also test dirty active main refusal, divergence refusal, fetch failure, and concurrent lock.
5. A physical phone is not needed for documentation/build work. For Kokoro playback, phone action, microphone, or permission verification, obey the user's USB connection protocol: ask them to connect first, then verify ADB once.
6. Do not change firewall settings, create a public endpoint, install persistent services, activate scheduled sync, invite a collaborator, or publish remotely without explicit approval.