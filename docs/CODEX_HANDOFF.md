# Echo Project — Codex Handoff

Updated: 2026-10-29
Project: F:\Downloads\EchoPhone
Safety: Local repository only. No source has been pushed or published. No credentials belong in this file.

## Initial state captured for this setup task

- Branch: master
- Initial HEAD: 76c92cc — Baseline EchoPhone before hands-free updates
- Remotes: none
- Branches: master only; no remote tracking branches
- Initial working tree already contained related prior-session work:
  - Modified: .gitignore, AssistantManager.kt, FloatingOrbComposeActivity.kt, MainActivity.java, ARCHITECTURE.md, FEATURE_AUDIT.md, TROUBLESHOOTING.md
  - Untracked: Run-KokoroVoiceHost.ps1, Setup-KokoroVoice.ps1, KokoroVoiceClient.kt, PhoneActionRouter.kt, tools/KokoroVoice/
- Ignored items observed: Gradle/build caches, local.properties, and timestamped backup copies.
- No commits were made before this task. Existing source changes were retained.

## Audit summary

### Present

- Android app: Kotlin/Compose orb and assistant manager; Java launcher; Android manifest/resources; Gradle configuration.
- AI: OpenAI-compatible FreeLLMAPI client in AssistantManager.kt.
- Local Android model path: MediaPipe LLM Inference integration and model import UI; actual local inference requires a compatible model file.
- Voice input: Android SpeechRecognizer path in the foreground orb flow.
- Voice output: Kokoro-82M af_heart host/client integration plus Android TextToSpeech fallback. The Python host uses ONNX Runtime and binds to loopback.
- Android actions: MainActivity contact lookup, dialer and message-draft intents; PhoneActionRouter allow-listed app/web/search intents.
- Other Android components: notification-only WakeWordService and opt-in ScreenAwarenessService scaffold.
- Build/deployment scripts: Setup-Build-Deploy.ps1 and Kokoro setup/host PowerShell scripts.
- Documentation: README and architecture, audit, troubleshooting docs.
- Tests: no test source tree or automated test suite found.
- Co-founder build prerequisites: Android Studio/JDK 17+, Android SDK platform 36/build-tools 36, Gradle 9.6; Kokoro host additionally requires Python 3.12, kokoro-onnx dependencies, and externally downloaded model/voice assets.
- Windows desktop source: none found under this project root. A later unified Android/Desktop repository needs the desktop source supplied or identified before claiming it contains the full ecosystem.
- Git at Stage 3 audit: local-only history through 98eeb6e; no remote.

### Actual verification recorded

- Earlier in the project: debug APK built and installed on authorized Realme device.
- Earlier in the project: Kokoro model inference generated audio; authenticated local HTTPS request returned a valid WAV after certificate-fingerprint verification.
- Earlier in the project: ADB reverse routes for FreeLLMAPI 31415 and Kokoro 31416 were active.
- Phone playback through Kokoro is not yet verified. At last inspection the phone was at its lock screen and EchoPhone had no saved Kokoro pairing values.
- FreeLLMAPI code/configuration was preserved; this setup task did not repeat a live chat request.
- The PowerShell build script has persistent User environment-variable writes and possible SDK/JDK downloads. Prefer process-scoped F: paths for builds.

### Security review

- Scanned current source and reachable history before the source checkpoint, then scanned the staged patch for common API-key/token/password/private-key patterns. No high-confidence matches found; no secret values were printed.
- No credential-named files are tracked in the baseline.
- Kokoro pairing data, API token, server certificate/private key are outside the repository at F:\Android\EchoVoice and have user-only ACLs.
- Updated .gitignore to cover local credentials, signing keys, generated APKs, caches, and model weights without broad filename patterns that could hide source code.
- This is a pattern-based check, not a guarantee against every possible secret or high-entropy value.

## Checkpoints

### Stage 1 — Audit

Status: COMPLETE.

Reviewed Git status, branches, history, remotes, tracked files, project source/configuration, Android manifest, build script, Python host, setup scripts, documentation, and presence of tests/desktop source.

### Stage 2 — Backup and publication readiness

Status: local audit, source checkpoint, and recoverable backup COMPLETE. GitHub setup is deferred until the organization slug and co-founder username are provided.

- Earlier backup: F:\Downloads\EchoPhone-backup-20261029-191446.zip (136 entries; 115,117 bytes; SHA-256 623340d2034e0f40aeb14a00db76e79be8480b577b949e5480c0ce28fe731fdf).
- Latest verified backup: F:\Downloads\EchoPhone-final-backup-20261029-192827.zip (121 entries; 168,122 bytes; SHA-256 5879e929f9f08fb4073fed66ceab4755b4eedef4d25957ae79a5ed490002e008). Fresh extraction matched HEAD 98eeb6e and included source plus Git history; generated build/cache directories and local.properties were excluded.
- Secret scan: completed; no high-confidence matches in current files or existing commit.
- History at archive time: 76c92cc baseline; 6f95709 source checkpoint; c4138d4 handoff checkpoint. No remote history.
- Publication: deferred by user. No organization/repository remote exists. The user will provide the organization slug and co-founder GitHub username later. Current GitHub integration cannot create organizations/repositories or invite owners.
- Available GitHub integration does not expose create-organization, create-repository, or invite-owner operations. Do not substitute a personal public repository or push anywhere else.

## Current Git checkpoint

- Branch: master
- Latest source checkpoint: 6f95709d7e9d1c69381bd83a8c236db52ddc1a6b
- Commit: Add Kokoro voice host and EchoPhone hands-free flow
- Remote: none; no source pushed
- Latest local checkpoint: 98eeb6eda58e5f9fdf26c10c7908284654984d87 (documentation only); no remote and nothing pushed.

## Working requirements and boundaries

- Preserve the existing F:\Downloads\EchoPhone directory and all user work.
- Do not reset, clean, force-push, rewrite history, move the project, or delete unrelated files.
- Keep the remote private and invite only the co-founder as an Owner once organization identity and account are supplied.
- Do not publish until privacy, credential, and history checks pass and the exact organization/repository destination is confirmed.
- Keep Android SDK, Gradle caches, temp, model, and build output on F: where configured.
- Do not place any keys, passwords, tokens, private certificates, or private pairing values in Git or this handoff.

## Commands and outcomes in this setup

- git status --short: initial modifications/untracked files listed above.
- git branch -av: master only.
- git log --oneline --decorate --all: source checkpoint 6f95709 Add Kokoro voice host and EchoPhone hands-free flow; baseline 76c92cc.
- git remote -v: no remotes.
- git ls-files: Android source/config/docs only; no desktop or test project.
- Pattern scan of working tree and reachable history: no high-confidence credential matches.
- Last known build/install: Gradle assembleDebug succeeded; APK installed. Current turn has not changed Kotlin/Gradle source.

## Pending work and next action

1. COMPLETE: local audit, source checkpoint, ignore review, secret-pattern scan, and backup verification are recorded above.
2. WAITING FOR USER: provide the GitHub organization slug and co-founder GitHub username after EchoPhone is ready.
3. COMPLETE: Stage 3 monorepo design and Stage 5 collaboration instructions are documented in docs/UNIFIED_REPOSITORY_DESIGN.md and docs/COLLABORATION_GUIDE.md. No source was moved. Windows desktop source is still absent.
4. Phone-dependent Kokoro playback is NOT TESTED in this session because the Android phone is disconnected. Computer-based work continues without it.
5. WAITING FOR USER APPROVAL: confirm organization display name/slug, repository name, private visibility, founder and co-founder GitHub logins, and exact initial upload scope before any GitHub creation or push.
