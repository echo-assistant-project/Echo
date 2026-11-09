# EchoDesktop

The Windows half of Echo (the phone app is Echo for Android): a translucent, always-on-top orb that you click (or say "Hey Echo" to) and talk to.
Python 3.12 standard library plus Windows' built-in speech recognition, voices and OCR (Setup Echo.exe installs Python; the natural voice and Whisper are optional extras).

## Run

    powershell -ExecutionPolicy Bypass -File Run-EchoDesktop.ps1

or `py -3.12 -m echo_desktop` from this folder.

- **Click the orb** to talk, click again to stop. **Double-click** opens the chat window. **Drag** to move.
  **Right-click** for persona, wake word, settings, memories, Stop and Quit.
- Settings: FreeLLMAPI URL (default `http://127.0.0.1:31415/v1`), API key, Kokoro voice (use
  "Import Kokoro pairing from this PC" after running `Setup-KokoroVoice.ps1`), orb size/opacity/colour.

## What it can do

| Area | Examples |
|---|---|
| Personas (shared with the phone via `shared/personas.json`) | "grind mode", "be casual", "talk to sage", "translate to Spanish", "stop translating" |
| PC control (allow-listed) | "open Spotify" (Start-menu apps only), "open https://…", "google …", "play lofi on YouTube", "volume up", "set volume to 30%", "next song", "lock my PC", "take a screenshot" |
| Timers & status | "set a timer for 10 minutes called tea", "remind me in 20 minutes to stretch", "list my timers", "what time is it", "battery", "brief me" |
| Memory | "remember that my sister is Priya", "what do you remember", "forget about my sister" (confirmation), "forget everything" (confirmation), "call me Ravi" |
| Screen & clipboard understanding | "what's on my screen?", "summarize this page" (needs the Screen understanding consent), "summarize my clipboard" |
| Webcam vision | "what do you see?", "what am I holding?", "look at this", "read this with the camera" (needs the Webcam vision consent, OpenCV, and an image-capable AI model) |

## Safety and privacy

- The AI can only request actions from a fixed list; every argument is validated. No shell commands, file paths or
  arbitrary programs. Screen reading is never triggered by the AI, only by your own words, and screen/clipboard text
  is fenced as data so instructions inside it are ignored and can't trigger actions.
- Settings are in `%APPDATA%\EchoDesktop`. Memories and API keys are encrypted with Windows DPAPI (only your Windows
  account on this PC can read them). Passwords, PINs, codes and card numbers are never stored as memories.
- Webcam vision opens the camera for about a second only when you ask, takes one photo in memory (never saved to disk),
  releases the camera, and sends the photo with your question to your AI service. The AI can never trigger it.
- Screen understanding takes one screenshot only when you ask, OCRs it locally, deletes it, and sends the text to your
  configured AI service.
- "Hey Echo" keeps the microphone open (Windows speech recognition, on this PC) until you turn it off.

## Limits (honest)

- Timers live only while EchoDesktop is running.
- Volume "set to N%" is approximate (Windows volume keys move in 2% steps).
- Wake-word accuracy depends on Windows speech recognition and your microphone; it's not a dedicated wake-word engine.
- Whisper accuracy is measured on real recorded speech (docs/BENCHMARKS.md). Push-to-talk, the wake word and Kokoro playback have no dated end-to-end test with a real microphone and speaker yet.

## Tests

    py -3.12 -m unittest discover -s tests

## Command Pack, interruption and understanding (2026-10-31)

- 3,800+ built-in commands from the shared catalog (`shared/commands/*.json`), e.g. "time in Tokyo", "open device manager",
  "add milk to my shopping list", "convert 5 km to miles", "restart my PC" (asks first; 60-second countdown,
  "cancel shutdown" stops it). Right-click the orb → **Commands…** to search and try them. Full list: `docs/COMMANDS.md`.
- While Echo talks, say "stop", "wait" or "hold on" (or click the orb/stop button) to cut it off. Toggle with the
  `interruptions` setting.
- Push-to-talk uses the recognizer's top 5 guesses with the phone's understanding rules (numbers, "um/uh", sound-alike
  app names, "X and then Y").
- Lists and notes are DPAPI-encrypted in `%APPDATA%\EchoDesktop\lists.bin`.
- Tests: `py -3.12 -m unittest discover -s tests` (400+ tests).


## Website control over MCP (2026-10-31)

With **Control websites for me** on, `web_agent.py` lets the AI use Echo's built-in browser (`echo_desktop/browser/`,
the Chrome or Edge on this PC, nothing to install) step by step, plus any MCP servers you added (`mcp_client.py`).
Setup, phrases and safety rules: [echo_desktop/browser/README.md](echo_desktop/browser/README.md). The phone sends the same requests through
`bridge.py` (127.0.0.1:31419 via adb reverse, bearer key).

## Webcam vision (2026-10-31)

1. Install OpenCV once: `py -3.12 -m pip install opencv-python`
2. In FreeLLMAPI, make sure the model it routes to supports images (a vision model).
3. In EchoDesktop Settings, tick **Answer questions using my webcam** and accept the notice.
4. Ask: "what do you see?", "what am I holding?", "how many fingers am I holding up on the webcam?"

Close EchoGestures first if it's running: Windows lets only one app use the webcam at a time.
Pick another camera by setting `camera_index` in the settings file (default `0`).

## Coding, building websites and typing for you (2026-10-31)

Uses the same FreeLLMAPI model as everything else; the better the model FreeLLMAPI routes to, the better the code.

| Say | What happens |
|---|---|
| "build me a website for my bakery", "write a python script that renames my photos by date", "code a snake game" | `coder.py`: the AI writes the files, runs them, reads the errors and fixes them in `%USERPROFILE%\EchoProjects\<name>`; websites open in your browser from `127.0.0.1` |
| "make the header blue", "add a contact form to the website", "fix the bug", "keep going" | continues the same project |
| "run it", "show me the website" | runs / previews the project and fixes what fails |
| "open the project in VS Code" | opens the folder (VS Code if installed, else Explorer) |
| "type hello, I'll be there at 5" | types it into the app you were using, as keystrokes (thousands of characters a second) |
| "type it", "type the code" | the project's main file (or Echo's last answer) into your editor |
| "write a polite leave request to my manager and type it" | the AI writes it, Echo pastes it where your cursor is |

Safety: files stay inside the project folder; only `python`, `node`, `npm`, `npx` run (no cmd/PowerShell), with a
90-second limit and the whole process tree stopped afterwards. The first run in each project asks you (or tick **Let Echo
run the code it writes without asking**); installing packages always asks. Typing never presses Enter at the end, and
multi-line text is pasted so chat apps don't send line by line. The AI can never start coding or typing on its own:
these only run from your own words.

## Echo uses your mouse and keyboard (computer use)

Turn on Settings → **Let Echo use my mouse and keyboard**, then say for example:
"on my computer, rename the newest file in Downloads to report", "use my PC to turn on dark mode in Notepad",
"click Save". Each step Echo looks at the screen (`helpers/screen_map.ps1`: the active window's buttons and fields from
Windows UI Automation, all text from Windows OCR, plus a small screenshot if your FreeLLMAPI model can see images —
otherwise it works from the text alone), the AI picks one action, and Echo does it with the real mouse/keyboard.
Asks first before Send/Buy/Pay/Delete/Install/Submit-type clicks, Enter in chat or mail apps, Alt+F4/Win+R and typing
into terminals; never types into password fields or types secrets; stops when you say or type anything to Echo.

## Editing your own projects, with a change log you can undo

Add your folders in Settings → **My projects** (`website=C:\Users\me\my-site; app=D:\code\app`), then say
"work on my website, make the header blue", "in my website, fix the contact form", or type
"work on C:\code\app and add a footer". The coding agent reads, edits, creates, renames and deletes files there.

Every file Echo touches is recorded per request in `%APPDATA%\EchoDesktop\changes` (the original is saved first):

| Say | What happens |
|---|---|
| "show my changes" / "change log" | the last requests with what they changed (`#12 01 Nov 10:42 · make the header blue · 2 modified, 1 created`) |
| "what changed in change 12" | the diff |
| "undo the last change", "undo change 12" | puts those files back as they were (asks first) |
| "force revert change 12" | also when you edited the files again afterwards (your newer version is kept in the log) |

Or right-click the orb → **Change log…** to browse, diff and revert. A revert is itself a change, so it can be undone.
Never edited: Windows, Program Files, ProgramData, Echo's own data, `.ssh`, and secret files (`.env`, keys, `.pem`,
password vaults). Plain "undo" is still Ctrl+Z in the app you're using. Changes made by other MCP servers' tools or by
typing into apps aren't in Echo's log.

## MCP: Echo uses any tools, and any AI can use Echo

**Echo's AI uses your MCP servers** (`mcp_client.py`, `mcp_tools.py`, `tool_agent.py`):

| Say | What happens |
|---|---|
| "add the files tools" / "add the fetch tools" / "add the github tools" | adds a ready-made server: files, fetch, git, time, memory, thinking, playwright, everything, github |
| "import my MCP servers" (or "… from Claude Desktop / Claude Code / Cursor / VS Code / Windsurf") | copies the servers you already set up for those apps |
| "what tools do you have", "reload my tools", "remove the git tools", "trust the fetch tools" | manage them |
| "use github to list my open pull requests", "with the files tools, find my resume and summarise it" | the AI uses those tools step by step |
| anything else | the AI may decide to use them itself (`use_tools`), when Settings → "Let the AI use my MCP tools" is on |

stdio servers (`command`/`args`/`env`, started hidden, `npx`/`uvx` resolved on Windows) and remote Streamable-HTTP
servers (`url`/`headers`, https only) are supported; edit them in Settings → MCP servers. Tools that declare
`readOnlyHint` run freely; every other tool asks you first (server, tool and arguments shown) unless you trust that
server. Tool results are treated as untrusted data.

**Any MCP-capable AI app can control this PC through Echo** (`mcp_server.py`, started with `echo_mcp.py`): tools
`find_commands`, `run_command` (Echo's 3,800+ PC commands), `type_text`, `press_keys`, `look` (screen map + optional
screenshot), `click`, `scroll`, `list_windows`, `focus_window`, `open_app`, `open_url`, `ask_user`, `speak`.
Risky steps pop up a confirmation on the PC that the AI can't answer; passwords are never typed; keys go to the app you
were using, never to the AI app's own window. The toolbox server (`echo_tools_mcp.py`, 600+ tools) works the same way.

Both servers share one stdio core (`mcp_rpc.py`): they answer `initialize` at once and load the heavy parts on a
background thread, calls run in parallel (keyboard/mouse steps take turns), every call has a time limit, cancelled
calls are dropped, and the toolbox's tool list is cached on disk.

The safest way to register them is the full path of Python 3.12 (`py -0p` lists it). With `py`, write `-3.12` with no
space: `py - 3.12 …` makes Python wait for a script on stdin, so the server never answers.

```text
Claude Code:     claude mcp add -s user echo -- "<python3.12>\python.exe" "<repo>\desktop\EchoDesktop\echo_mcp.py"
                 claude mcp add -s user echo-tools -- "<python3.12>\python.exe" "<repo>\desktop\EchoDesktop\echo_tools_mcp.py"
                 (or: claude mcp add echo -- py -3.12 "<repo>\desktop\EchoDesktop\echo_mcp.py")
Claude Desktop:  %APPDATA%\Claude\claude_desktop_config.json →
                 {"mcpServers": {"echo": {"command": "py", "args": ["-3.12", "<repo>\\desktop\\EchoDesktop\\echo_mcp.py"]}}}
Cursor:          %USERPROFILE%\.cursor\mcp.json → same "mcpServers" block
VS Code:         %APPDATA%\Code\User\mcp.json → {"servers": {"echo": {"command": "py", "args": ["-3.12", "<repo>\\desktop\\EchoDesktop\\echo_mcp.py"]}}}
```

## Voice test

Say "test my voice" (or run `Run-VoiceTest.ps1`): a window types whatever you say, shows how long recognition took,
and scores it if you type what you really said. With the Intel-GPU recognizer set up
(`tools\WhisperHost\Setup-OpenVino.ps1`) it uses Whisper large-v3-turbo on the GPU.
