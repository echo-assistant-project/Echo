# EchoPhone

EchoPhone is the Android app in the Echo project. The repository also contains the optional Windows Kokoro speech service. FreeLLMAPI and EchoDesktop are external/not currently included.

- [Architecture](docs/ARCHITECTURE.md)
- [Feature audit](docs/FEATURE_AUDIT.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Setup for another Windows PC](docs/DEVELOPER_SETUP.md)
- [Collaboration and synchronization](docs/COLLABORATION_GUIDE.md)
- [Unified repository design](docs/UNIFIED_REPOSITORY_DESIGN.md)

## Quick build

Copy scripts/echo-env.example.ps1 to .echo-env.ps1, edit local paths, and load in PowerShell:

    Copy-Item scripts\echo-env.example.ps1 .echo-env.ps1
    . .\.echo-env.ps1
    .\Setup-Build-Deploy.ps1

The setup script provisions Android SDK, Java 17, and Gradle under selected paths. It does not persist Windows environment variables unless explicitly run with -PersistEnvironment. See the developer setup guide.

## Safe synchronization

Run from the repository root:

    .\scripts\sync-project.ps1

This fetches origin/main and fast-forwards local main only when safe. It never switches branches, changes an active feature branch, overwrites uncommitted edits, force-resets, force-pushes, resolves conflicts, or merges PRs. Use -FetchOnly for scheduled background checks. Git transfers commits, not uncommitted edits.

## AI and voice configuration

Each developer configures their own FreeLLMAPI access and local app settings. Kokoro models, TLS private keys, bearer keys, and pairing data are generated per PC and never committed.
