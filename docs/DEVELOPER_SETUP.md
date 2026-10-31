# EchoPhone developer setup

This guide is for a second Windows PC. It does not depend on the founder's username, drive letters, SDK installation, API keys, or model files.

## What is in this repository

The repository contains the EchoPhone Android app and optional Windows-side Kokoro TTS service. EchoDesktop, FreeLLMAPI, and a local LLM model are not included. They must be installed or configured separately.

GitHub shares tracked source, build files, scripts, and documentation. Android SDKs, Gradle caches, Python virtual environments, API keys, Kokoro model weights, TLS keys/certificates, pairing tokens, APKs, and machine-specific configuration stay local.

## 1. Clone the private repository

An organization Owner must invite the co-founder as an Owner using their exact GitHub username. They must accept before private repository access works. Never share the founder's login or keys.

Install Git for Windows. In PowerShell:

    git clone https://github.com/echo-assistant-project/Echo.git
    cd Echo

Authenticate through Git Credential Manager's browser flow if prompted. Never paste a token into a command, file, or chat.

## 2. Install tools and build Android

Install Android Studio (recommended), Git for Windows, and Python 3.12 if using Kokoro.

Android uses Java 17, Gradle 9.6.0, Android API 36, and Build Tools 36.0.0. Reserve at least 12 GB at the selected SDK/cache/build location. The setup script does not clean disk contents.

Copy the local path template and load it in PowerShell:

    Copy-Item scripts\echo-env.example.ps1 .echo-env.ps1
    notepad .echo-env.ps1
    . .\.echo-env.ps1

The template uses F: when available, otherwise the current user's Local AppData. Edit for another drive if needed. It contains paths only and is ignored by Git.

Provision tools and build:

    .\Setup-Build-Deploy.ps1

By default environment changes apply to that process only. The script does not change persistent Windows variables unless explicitly run with -PersistEnvironment.

The APK is written under ECHO_BUILD_ROOT. A phone is optional to build; install requires an authorized Android device.

For local build and available test tasks after provisioning:

    gradle --no-daemon testDebugUnitTest assembleDebug

There are currently no Kotlin/Java unit-test sources, so the test task has zero project tests.

## 3. Configure FreeLLMAPI safely

FreeLLMAPI is not included. Each developer installs/runs a compatible instance or receives separately issued, revocable backend access. Do not share the founder's API key.

In EchoPhone AI settings, configure that developer's endpoint. Typical PC-local base: http://127.0.0.1:31415/v1. The app stores this locally on the device. For USB testing, use ADB reverse for that port. Do not expose an API listener to the public internet.

A different port requires matching API URL and ADB reverse settings. Remote addresses should only be used with deliberate binding to a trusted interface and appropriate authentication/firewall rules.

## 4. Configure optional Kokoro voice

The Windows host requires Python 3.12, pinned packages in tools/KokoroVoice/requirements.txt, and model assets totaling about 143 MB. The setup script downloads assets only if absent and keeps them outside Git. It creates a per-PC virtual environment, TLS identity, API key, and private pairing file.

After loading .echo-env.ps1:

    .\Setup-KokoroVoice.ps1
    .\Run-KokoroVoiceHost.ps1

Use that PC's pairing file to configure its own EchoPhone device. Each PC generates its own TLS and bearer credentials. Never copy another developer's pairing file or private key. Never put API keys in path templates, Git, issue comments, or Actions.

The service binds to loopback. For a USB-connected phone, use the ADB reverse command from that PC's pairing file. Public/router forwarding is not configured.

## 5. Checks and limits

There is no Python backend test suite. CI performs a Python syntax check without importing or downloading models. Kokoro inference requires separately installed models.

Phone playback, microphone permissions, and phone actions require a physical Android device and are not verified by desktop builds.

No EchoDesktop .NET project or solution exists here, so no Windows desktop build workflow can be added or claimed. Kokoro is Python.

## 6. Branch and PR workflow

From a clean checkout, use docs/COLLABORATION_GUIDE.md:

    .\scripts\sync-project.ps1
    git switch -c feature/short-description

Review, stage, commit, and push only intended files:

    git status --short
    git diff
    git add path\to\changed-file
    git diff --cached
    git commit -m "Describe the change"
    git push -u origin feature/short-description

Open a pull request targeting main in GitHub. The other founder reviews the diff and CI evidence before merge. Never force-push shared branches.

## 7. Per-machine configuration checklist

- FreeLLMAPI: separate installation/access and separately issued key, saved only in app settings.
- Android SDK, JDK, Gradle: installed per machine.
- Kokoro: local venv, model files, TLS files, token, and pairing data per PC.
- Phone permissions, ADB authorization, pairing: per device.
- No private credentials are needed by project files or CI.
