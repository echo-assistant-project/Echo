# Source audit and migration progress

Audit date is November 5, 2026. The repository's `AGENTS.md`, architecture and collaboration instructions were read
before implementation. The original chat workspace path no longer exists on this machine. Work is on a separate
branch of the existing `echo-assistant-project/Echo` repository, with its Android project and packaged local app preserved.

## Actual code traced

| Concern | Existing path and behavior | Web treatment |
| --- | --- | --- |
| Text conversation | `desktop/EchoDesktop/echo_desktop/backend.py` has `Backend.ask`, one-active-turn locking, bounded history and failed-turn protection. | Reused directly. Added `stream` and optional per-session system prompt. |
| Model calls | `desktop/EchoDesktop/echo_desktop/llm.py` has `ChatClient`, `/v1/chat/completions`, SSE parsing and provider error handling. Model `auto` can race providers. | Reused directly with an explicit model or `auto:reliable`, avoiding those parallel races. No model is loaded locally. |
| Prompts | Headless `SYSTEM_PROMPT`; full desktop `DesktopBrain.system_prompt` combines persona, action protocol, local time, memories, skills and knowledge. | Reuse the safe text prompt with client branding and selected approved passages. Desktop action instructions are excluded. |
| Short-term memory | `ChatClient.history` stores role/content exchanges. | Separate instance per client/origin/visitor session. Eight exchanges in memory. |
| Persistent memory | `storage.py` has DPAPI-encrypted settings, MemoryStore and ListStore. Full desktop brain recalls and updates personal facts. | Personal stores and Windows settings are never imported by the web path. No persistent visitor memory yet. |
| Knowledge | The installed desktop `knowledge.py` indexes local document/PDF chunks, searches with lexical/BM25-style scoring and builds a reference prompt. It is absent from the older tracked desktop archive. | Use a small client-scoped lexical retriever over operator-approved public passages. Do not load private desktop indexes or folders. |
| Microphone | Installed `stt.py` uses Windows waveIn/VAD and an authenticated local speech host. `voice.Listener` invokes fixed Windows speech helpers. | Excluded from the web dependency graph and routes. |
| Speech output | The currently installed source uses `gemini_voice.py` through `voice.Speaker`, plus explicit Windows speech support. Repository architecture notes describe an older voice implementation. | Excluded from the web implementation. |
| Desktop actions | Installed `brain.py`, action allowlists, toolbox, computer/browser helpers, confirmations and MCP dispatch. | No imports, routes or tool schemas in the website engine. Text action-looking output is displayed as text. |
| Android | `AssistantManager.kt` builds separate model requests and retains Android chat history; launcher/phone actions use Android APIs. | Android source and APK are unchanged. |
| Packaged desktop | `EchoDesktop.pyz` contains older Python desktop payloads, including brain, client, memory, speech and UI code. | Archive inspected read-only. Its bytes are unchanged. |

The installed desktop source and the tracked archive are different revisions. This implementation does not claim
that all of the installed desktop functionality has been migrated into this repository.

## Implemented

- `echo-web/` with distinct core adapter, API, widget, client configuration and documentation.
- Real widget → API → shared ECHO conversation engine → model-provider request path, with SSE output.
- Client and visitor isolation, bounded sessions, explicit capability checks, approved origins and server-only keys.
- Reference passage selection, visible reference titles, session reset, failed-stream handling and safe plain-text rendering.
- Local wake helper accepts standalone `echo` as well as its existing greeting phrases.

## Local wake word

The source helper is `desktop/EchoDesktop/echo_desktop/helpers/speech.ps1`. It uses the existing Windows speech
recognizer grammar and its existing confidence threshold. Say “ECHO”, pause, and then give the command once the
local app starts listening. This is a Windows companion feature. It does not add browser voice or Android wake-word support.
The helper was also installed into the existing source-based local ECHO runtime. Autostart, microphone activation
and speech-model startup remain disabled until the user explicitly starts the local app/feature. The old packaged
desktop archive must be rebuilt from the matching complete desktop source before distributing this wake change
through that archive. Hardware microphone accuracy still needs an explicit user test.

## Pending migration and production work

- Durable authenticated visitor/customer identities and a managed session store, with retention/deletion controls.
- Full matching desktop/Android source reconciliation before migrating more features.
- Retrieval evaluation on real approved client material, language support and content update/version workflows.
- Production HTTP hosting, TLS, provider readiness checks, distributed quotas, observability and load tests.
- Voice, billing, calls, desktop automation and other integrations require separate scope and validation.

Local code checks cover the existing headless engine and the new API. Desktop preservation is checked without
opening the UI or starting background listeners, given the earlier machine stability issue.
