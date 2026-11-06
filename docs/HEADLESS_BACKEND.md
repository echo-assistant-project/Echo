# ECHO backend

Run these commands from `desktop/EchoDesktop` with Python 3.12 on Windows.

```powershell
py -3.12 -m echo_desktop.backend --check
py -3.12 -m echo_desktop.backend --text "Hello Echo"
py -3.12 -m echo_desktop.backend --interactive
```

Interactive mode retains the last eight exchanges in memory. `/clear` resets the session and `/exit` quits.
The backend reads the existing encrypted ECHO AI credentials. Configure FreeLLMAPI separately before connecting.

This entry point launches text chat with one active request per session and a 30-second request timeout.
It uses the existing `auto:reliable` provider route directly, with no parallel provider races.
Failed or empty responses leave history intact. Input and history have fixed size limits.
Nonstreaming provider responses have a 2 MB size limit.

Importing or running this entry point does not start a desktop window, microphone, speech helper, local model,
watcher, hotkey, or automatic task. Voice and calling integration are pending separate backend verification.

The desktop defaults now leave speech helper preloading and automatic service startup disabled.
Machine-specific credentials, memories, logs, binaries, and models belong outside the repository.

## Tests

```powershell
py -3.12 -m unittest discover -s tests -p test_backend.py
py -3.12 -m unittest discover -s tests -p test_hedge.py
py -3.12 -m unittest discover -s tests -p test_core.py
```
