# Echo

Echo combines a Windows assistant, an Android app, and a browser chat integration. The Windows source in this repository comes from the Deluxe handoff. The existing Android source and web integration remain separately maintained components. See [the import notes](docs/DELUXE_IMPORT.md) for version boundaries and verification.

| Component | Source | Start here |
| --- | --- | --- |
| Windows desktop | `desktop/EchoDesktop/` | [Desktop README](desktop/EchoDesktop/README.md) |
| Android | `app/` | [Developer setup](docs/DEVELOPER_SETUP.md) |
| Website widget and API | `echo-web/` | [Web setup](echo-web/README.md) |
| Shared commands, personas, intent data, and skills | `shared/` | [Commands](docs/COMMANDS.md) and [skills](docs/SKILLS.md) |
| Optional voice and speech helpers | `tools/KokoroVoice/`, `tools/WhisperHost/` | [Third-party licenses](docs/LICENSES.md) |

## Run the Windows assistant

Install Python 3.12 with the Windows launcher. Start FreeLLMAPI separately, then run from the repository root:

```powershell
powershell -File desktop\EchoDesktop\Run-EchoDesktop.ps1
```

Configure the model endpoint and key in Echo Settings. The usual FreeLLMAPI address is `http://127.0.0.1:31415/v1`. Keep the key in your local settings. See [desktop setup](desktop/EchoDesktop/README.md) for optional speech and gesture features.

## Build Android and test the web integration

Open the repository in Android Studio or use JDK 17, Android SDK 36, and Gradle 9.6.0 to run `gradle testDebugUnitTest assembleDebug`. The existing `Echo.apk` is a legacy artifact. The APK supplied in the Deluxe handoff is a separate build, and its matching Android source was absent from that archive.

The browser widget uses the headless engine and its own sessions. Follow [web setup and the client checklist](echo-web/README.md) before configuring a website.

## Checks

```powershell
python -m unittest discover -s echo-web/tests
Set-Location desktop/EchoDesktop
python -m unittest discover -s tests
```

The [headless backend](docs/HEADLESS_BACKEND.md) supports testing text without launching the desktop interface. For details on credentials and collaboration, see [security](docs/SECURITY.md) and [team workflow](docs/TEAM_WORKFLOW.md).
