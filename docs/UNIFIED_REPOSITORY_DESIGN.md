# Unified Echo Repository — Design Decision

Date: 2026-10-29
Reviewed repository: `F:\Downloads\EchoPhone`

## Decision

Use one private GitHub organization repository for EchoPhone and EchoDesktop once both source projects and the destination identity are confirmed. Keep this checkout in its current Android-root layout for now. Do not move files or create empty module directories.

The repository currently contains a complete Android/Gradle project rooted here: `settings.gradle`, root `build.gradle`, `app/`, and `Setup-Build-Deploy.ps1` are all at the checkout root. The build script expects to run from the EchoPhone project root, and its build outputs and Android tooling use fixed `F:\Android\...` paths. Moving the project now would change paths used by build/setup scripts and documentation while there is no Windows source to integrate.

## Current source inventory relevant to a monorepo

| Area | Current state | Design consequence |
|---|---|---|
| Android | EchoPhone is the only complete project. Gradle root is the repository root; no Gradle wrapper is checked in. | Preserve the current root and build entry points until a tested migration is approved. |
| Windows | No EchoDesktop source is present in this checkout. | Do not create `apps/windows/EchoDesktop` as an empty or placeholder project. Obtain and audit its actual source first. |
| Kokoro TTS | Python service code exists at `tools/KokoroVoice/server.py`; setup and launch scripts are at the Android project root and use machine-local `F:\Android\...` state. | This is real code, but relocating it alone would break path assumptions. Consider moving the service and scripts together only in a dedicated, approved migration with adjusted paths and verification. |
| AI gateway | FreeLLMAPI is an external local application; no gateway server implementation is present here. | Do not create `services/ai-gateway` until actual gateway source is supplied or implemented as a separate approved feature. |
| Shared code | No cross-platform shared library or schema project is present. | Add `shared/` only when actual shared contracts or code exist. |
| Tests/CI | No test source tree or CI workflow was found. | Do not make branch protection depend on checks that do not exist. Add real build checks in a separate change. |

## GitHub name and duplicate check

The connected account (`Akshaj-echo`) has no organization memberships and no EchoPhone/Echo repository in its accessible repository list. A global GitHub search returned `Executeds/echophone-android-public`; it is owned by another account, and its README describes a separate SMS and notification forwarding product. It is not this Echo assistant and is not available to this account. Search also found the unrelated organization `echo-project-org`, so `echo-project` is a poor organization slug choice. No matching Echo assistant repository was identified under the connected account or its organizations. Recommendation: organization display name `Echo Assistant Project`, preferred slug `echo-assistant-project`, repository name `Echo`. Public search did not show this exact organization slug, but that does not guarantee availability; verify it on GitHub before creation. Recheck the exact organization slug/repository immediately before creating anything.

## Proposed target after source review

```text
Echo/
├── apps/
│   ├── android/EchoPhone/       # existing Gradle project, moved only after approval
│   └── windows/EchoDesktop/     # actual supplied desktop project
├── services/
│   └── kokoro-tts/              # existing Python service, if extracted with its scripts safely
├── shared/                      # only real shared contracts/libraries
├── scripts/                     # cross-project tooling only
├── docs/
└── README.md
```

`services/ai-gateway/` is intentionally omitted until Echo contains an AI gateway implementation. `tools/KokoroVoice` should not be renamed or moved for appearance alone. Windows-only and Android-only setup scripts may remain next to their respective project if that keeps them reliable.

## Migration gates

Before any file move:

1. Locate and inspect the real EchoDesktop source, build instructions, and dependencies.
2. Decide whether it should join the same repository and verify licensing/credentials/private data.
3. Create a backup and a dedicated migration branch.
4. Write a path map for Gradle, PowerShell, Python model/configuration, documentation, and build outputs.
5. Move one component at a time, update all paths, and build EchoPhone from its new directory.
6. Verify the Windows build using its real toolchain and run available automated checks.
7. Keep the old checkout recoverable until both builds pass; roll back the migration branch if verification fails.

No source files were moved in the design stage.
