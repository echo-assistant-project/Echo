# The JARVIS pack — what the best JARVIS / FRIDAY builds have, and what Echo added

November 2026. Starting point: Pranith Velar's reel *“10 months of building JARVIS, shown in one minute”* (FRIDAY) and
his earlier open-source build (`github.com/pranithvelar/jarvis_experiment`), then about 110 other JARVIS / FRIDAY /
OpenClaw-style projects: YouTube and Instagram demos, GitHub READMEs, product pages and write-ups.

## How the research was done (honestly)

- **The reel:** watched frame by frame (the subtitles and the screen). It shows voice-driven editing in Premiere Pro
  (“click …”, play/pause), YouTube and Spotify control, the phone as a remote, and an incoming phone call handled
  through the assistant. His other Jarvis reels explain a two-tier memory and retrieval (“what were my integrations
  and what came from OpenClaw”).
- **His earlier repo's README:** a Gemini brain with an Ollama fallback when offline, 10 category routers instead of
  60 raw tools, short + long-term memory, LiveKit voice, a floating voice popup, a background screen monitor that
  interrupts when something important happens, Google Workspace via Apps Script, WhatsApp through the browser, and
  screen OCR.
- **The rest:** about 110 search results. Of these, 20 READMEs and pages were read in full: OpenClaw (site and docs),
  alimaandev/Friday, jarvis.institute, Raghava00001/Jarvis, isair/jarvis's issue #386 (“10 capabilities of a complete
  personal AI agent”), projectswithdigambar/jarvis, anubhavchaturvedi-github/jarvis-ai-assistant, harriik/jarvis,
  maxwharris/jarvis, garvit-821/jarvis, rohitmukkala/jarvis, hasan-ikbal/jarvis_ai_gui, prince-monga's assistant,
  OpenJarvis, GAIA, the “Build JARVIS 3.0 / 4.0” tutorials, and Zubair Trabzada's JARVIS videos. The other results
  were read from their titles, chapter lists and descriptions. Spoken-only details were not counted.

## What they have in common, and where Echo stands

| Feature (how often it appears) | Echo before | Now |
|---|---|---|
| Voice in/out, wake word, interrupting it (almost all) | ✓ | ✓ |
| Open apps, system control, media, volume (almost all) | ✓ 3,800+ commands | ✓ |
| Memory across sessions (very common) | ✓ encrypted memories | ✓ plus **session recap** |
| Screen reading / “what's on my screen” (common) | ✓ | ✓ |
| Webcam vision, hand gestures (common) | ✓ | ✓ |
| Scheduled automations, daily briefing (common) | ✓ watches, briefings | ✓ |
| Floating orb / HUD (common) | ✓ orb | ✓ |
| Tools and plugins, MCP (common) | ✓ 605 tools, MCP both ways | ✓ |
| **Offline brain**: local LLM (Ollama) when the cloud is down (common) | ✗ | removed (FreeLLMAPI only; it already switches between many providers) |
| **Proactive**: speaks up unprompted (OpenClaw's heartbeat; Pranith's background monitor) | partly (watches you set up) | ✓ **nudges** |
| **Second brain**: ask your own notes and documents (common in 2026 builds) | ✗ | ✓ **notes search with sources** |
| **Global shortcut** to summon it (Friday Ctrl+Alt+F, Jarvis Ctrl+Alt+J, GAIA Ctrl+Shift+G) | ✗ | ✓ **Ctrl+Alt+E** |
| **Privacy / blackout mode**: one switch, nothing leaves the PC (Friday) | ✗ | partly: **privacy mode** stops internet lookups; AI questions still go to FreeLLMAPI |
| **Lives in your chat app** (OpenClaw's #1 feature: Telegram, WhatsApp…) | ✗ | ✓ **Telegram, one approved account** |
| **Click by name** in any app (the Premiere demo) | via the AI only | ✓ **instant, no AI needed** |
| Phone calls through the phone app (several) | ✓ on the phone | ✓ |
| Face login, emotion detection (a few) | ✗ | not added (see below) |
| Self-written plugins / custom tool builder (Friday, OpenClaw) | taught phrases | not added (see below) |
| Google Workspace (Gmail, Calendar…) via Apps Script or OAuth (several) | website control, MCP servers | unchanged |

## What was added

| Say | What happens |
|---|---|
| **Ctrl+Alt+E** (any app) | Echo listens; press again while it talks to stop it. Change or turn off in Settings. |
| “which brain are you using”, “use the local brain”, “auto brain” | Echo thinks with FreeLLMAPI only (the local Ollama brain was removed); these say so. |
| “privacy mode on/off” | **Privacy mode:** internet lookups off; questions to the AI still go to your FreeLLMAPI providers. Off restores your settings. |
| “anything I should know”, “stop nudging me” | **Nudges** every 10 minutes, each once a day: tasks due within the hour or overdue, follow-ups and birthdays today, daily habits not done by 7 pm, battery ≤15% (≤8% speaks even at night), system drive under 5% free. Quiet hours 22–7 by default. |
| “learn my Documents folder”, “what do my notes say about the lease”, “refresh my notes” | **Second brain:** text, Markdown, code, CSV/JSON, Word, PowerPoint and Excel files are split into passages and searched with BM25. The AI answers from the best passages and names the files; without an AI, Echo reads the best passage. The index is DPAPI-encrypted and refreshed incrementally. System folders and whole drives are refused. PDFs aren't read yet. |
| “where did we leave off”, “catch me up” | **Session recap:** what you asked last time, Echo's last answer, and your open tasks. The last 300 turns are kept encrypted; anything that looks like a password is never logged; “clear our chat” empties it. |
| “click Export”, “press the save button”, “double click Recycle Bin” | **Click by name:** Echo reads the window's buttons, menus, tabs and text, picks the best match and clicks it at once. Risky buttons (Send, Buy, Delete…) still ask first. If it isn't found and AI computer use is on, the AI takes over. |
| Message your Telegram bot | **Telegram:** off by default. Paste your @BotFather token in Settings and tick the box; the first account that writes must be approved on the PC, and everyone else is ignored. From the phone, anything that would ask on the PC is declined, and typing, clicking and Echo's own settings say “only at the PC”. |

All the new voice phrases are desktop-only (`shared/commands/98-jarvis.json`, made by `tools/generate_jarvis_commands.py`,
which routes every sample and drops any phrase an older command already answers). Code: `llm.BrainRouter`,
`proactive.py`, `knowledge.py`, `session.py`, `hotkey.py`, `telegram_bridge.py`, `computer.find_named`, `brain._jarvis`.
Tests: `tests/test_jarvis.py`.

## The vault: passwords, PINs and cards the AI never sees

Other builds and products handle secrets in different ways:
- **1Password's agentic autofill:** “raw credentials should never enter the LLM context”. A person approves each use, and the credential is typed straight into the target.
- **Siri:** shows saved passwords only after Face ID.
- **Alexa:** asks for a spoken 4-digit code for purchases, which anyone nearby can overhear.
- **Several Jarvis builds:** add face or fingerprint login.

Echo combines these.

| Step | What happens |
|---|---|
| Add | Only in the **Vault window** (“open my vault”, or Settings → Vault), by typing. Never by voice, never through the AI. |
| Store | `%APPDATA%\EchoDesktop\vault.bin`, DPAPI-encrypted, separate from everything else. Inside it, every secret (password, PIN, card number, CVV, expiry, username, name on card, notes) is sealed again on its own, tied to its item, so even the opened file holds nothing readable; each one is decrypted only at the moment it's shown, copied or used. No AI tool, MCP server, prompt, memory or chat log reads it; a test checks that none of that code even imports it. |
| Ask | By voice. Echo's command recogniser picks the action (no AI): “unlock my phone”, “type my Gmail password”, “sign me in to Netflix”, “type my card number / CVV / expiry”, “copy my Wi-Fi password”, “show my HDFC card”. |
| Approve | **Windows Hello** (face, fingerprint or PIN). The prompt names the item and the window it will go into. If Hello isn't set up, Echo asks for the vault PIN (stored as a PBKDF2 hash). One approval covers 60 seconds; “lock my vault” ends that early. Three failures lock the vault for 5 minutes. |
| Act | The secret goes straight where it's needed: typed as keystrokes into the app you were using (never into chat apps, terminals or Echo itself; Enter is left to you), sent to the phone over USB/ADB to unlock it (on stdin, never on a command line), copied for 30 seconds (kept out of Windows clipboard history and cloud clipboard, and never read back by Echo or the AI), or shown in a small window for 20 seconds. |
| Never | Spoken, shown in the chat, written to any log, or available to the AI, MCP apps or Telegram. “When was my vault used” lists names and times only. |

**Autofill:** say “autofill” or “fill my login” on a sign-in page, or “log me in” to also press Enter.
1. Echo reads the page locally, with no AI: the address bar, the username box and the password box. Password boxes' contents are never read.
2. It picks the login saved for that website.
3. If the website is a look-alike, it stops before Windows Hello is even asked. For example, a Gmail login saved for accounts.google.com is never filled on g00gle-login.xyz or google.com.evil.io. The same check guards “type my Gmail password”.
4. It clicks each box, replaces what's there, and types.

The Vault window looks like a password manager: categories with counts, search, and one card per item with everything hidden (••••). Each card has Show (15 seconds), Copy (30 seconds), Edit and Delete. The Add form has a password generator and a strength meter. It locks itself after 3 idle minutes. Vault windows are invisible to screenshots and screen recording, so a password shown on screen can't reach the AI's view.

Phone unlock needs the phone connected to the PC with USB debugging allowed. An app on the phone can't unlock the phone's
own lock screen, because Android doesn't allow it.

Code: `vault.py`, `helpers/hello.ps1`, `brain._vault`, `ui.VaultWindow`. Tests: `tests/test_vault.py`.

## Not added, and why

- **Face login and emotion detection:** biometric data for little gain on a personal PC that Windows Hello already
  locks.
- **The AI writing its own plugins or tools:** that would run code an AI wrote on its own. Echo's taught phrases
  (“when I say work mode, open VS Code and Spotify”) cover the safe part. Security researchers found that many
  community agent skills contained vulnerabilities, which is a further reason to keep this out.
- **Heartbeat files fetched from the internet** (Moltbook-style standing orders): remote instructions are a
  prompt-injection risk for an assistant that controls a PC.
- **Answering phone calls with an AI voice:** this needs a paid telephony service (Retell, Twilio). It's a good next
  step if the team wants it.
