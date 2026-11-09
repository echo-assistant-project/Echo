"""What Echo's setup app checks and does, so you don't have to: find what's already on the PC, then install and
configure only what you ticked — phone tools and the Echo phone app, the natural
voice (Kokoro), faster speech recognition (Whisper), hand gestures, shortcuts, start with Windows, and Claude
Code / Claude Desktop connections. Installs go through Windows' own package manager (winget) from the official
publishers; everything else stays inside your user folders.

Every step is a plain function that reports progress line by line; `Runner` runs the commands (tests use a fake one).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

HERE = Path(__file__).resolve().parents[1]                 # desktop\EchoDesktop
ROOT = HERE.parents[1]                                      # the Echo folder
DEV = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "EchoAndroid"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
WINGET = {"python": "Python.Python.3.12", "ollama": "Ollama.Ollama", "adb": "Google.PlatformTools", "pwsh": "Microsoft.PowerShell"}
# (no download fallback: the APK always comes in the zip, so nothing unverified is ever installed on the phone)
DEFAULT_MODEL = "llama3.2"


# ------------------------------------------------------------------------------------------------ running things
class Runner:
    """Runs a command, streaming its output lines to `say`. Returns the exit code (-1 if it couldn't start)."""

    def __call__(self, cmd: list, say: Callable[[str], None], timeout: float = 3600, cwd: Optional[str] = None) -> int:
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, cwd=cwd,
                                 creationflags=CREATE_NO_WINDOW)
        except OSError as e:
            say(f"couldn't start {Path(cmd[0]).name}: {e.strerror or e}")
            return -1
        timer = threading.Timer(timeout, p.kill)
        timer.start()
        try:
            for raw in p.stdout:
                line = raw.decode("utf-8", "replace").strip()
                if line and not set(line) <= set("-\\|/ █▒░"):          # skip spinners and progress-bar noise
                    say(line[:200])
            return p.wait()
        finally:
            timer.cancel()


def winget_install(run: Runner, package: str, say) -> bool:
    say(f"Installing {package} with Windows Package Manager…")
    code = run(["winget", "install", "-e", "--id", package, "--scope", "user", "--silent", "--accept-package-agreements",
                "--accept-source-agreements", "--disable-interactivity"], say)
    if code != 0:                       # some packages can't install per-user: try the machine-wide installer
        code = run(["winget", "install", "-e", "--id", package, "--silent", "--accept-package-agreements",
                    "--accept-source-agreements", "--disable-interactivity"], say)
    return code == 0 or code == -1978335189          # 0x8A15002B: already installed, nothing newer


# ------------------------------------------------------------------------------------------------ finding things
def which(name: str, extra: tuple = ()) -> Optional[str]:
    found = shutil.which(name)
    if found:
        return found
    links = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links"
    for c in (links / f"{name}.exe", *extra):
        if c and Path(c).is_file():
            return str(c)
    return None


def find_ollama() -> Optional[str]:
    return which("ollama", (Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",))


def find_pwsh() -> Optional[str]:
    return which("pwsh", (Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "PowerShell" / "7" / "pwsh.exe",
                          Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "PowerShell" / "7" / "pwsh.exe"))


def find_claude() -> Optional[str]:
    return shutil.which("claude.cmd") or shutil.which("claude.exe") or shutil.which("claude")


def find_apk() -> Optional[Path]:
    for p in (ROOT / "Echo.apk", ROOT / "release" / "Echo.apk", ROOT / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk",
              # the shared zip: "Echo for Windows" (this folder) next to "Echo for Android\Echo.apk" (older zips: Mobile)
              ROOT.parent / "Echo for Android" / "Echo.apk", ROOT.parent / "Mobile" / "Echo.apk",
              ROOT.parent.parent / "Mobile" / "Echo.apk",
              Path.home() / "Downloads" / "Echo.apk"):
        if p.is_file():
            return p
    return None


def pythonw() -> str:
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return str(w if w.is_file() else exe)


def python_exe() -> str:
    exe = Path(sys.executable)
    p = exe.with_name("python.exe")
    return str(p if p.is_file() else exe)


@dataclass
class Found:
    """What's already on this PC (shown on the setup app's first page)."""
    python: str = ""
    winget: bool = False
    main_ai: bool = False
    ollama: Optional[str] = None
    models: list = field(default_factory=list)
    adb: Optional[str] = None
    phone: str = ""                       # "" none, else the device serial
    phone_note: str = ""
    pwsh: Optional[str] = None
    kokoro: bool = False
    whisper: bool = False
    gestures: bool = False
    claude: Optional[str] = None
    hello: str = ""
    apk: Optional[Path] = None
    shortcut: bool = False


def detect(settings) -> Found:
    from . import llm, stt, vault, voice
    f = Found(python=sys.version.split()[0], winget=bool(shutil.which("winget")))
    f.main_ai = bool(llm.local_models(settings["llm_url"], timeout=2))
    f.ollama = find_ollama()
    f.models = llm.local_models(settings["local_llm_url"] or "http://127.0.0.1:11434/v1", timeout=2)
    f.adb = vault.find_adb(settings["adb_path"] or "")
    if f.adb:
        serial, why = vault.phone_ready(f.adb)
        f.phone, f.phone_note = serial or "", why or ""
    f.pwsh = find_pwsh()
    f.kokoro = voice.find_pairing() is not None
    f.whisper = stt.find_whisper_pairing() is not None
    f.gestures = (DEV / "EchoGestures" / "venv" / "Scripts" / "python.exe").is_file()
    f.claude = find_claude()
    f.apk = find_apk()
    f.shortcut = (start_menu() / "Echo.lnk").is_file()
    try:
        out = subprocess.run(voice.helper_command("hello.ps1", "-Check"), capture_output=True, timeout=30, creationflags=CREATE_NO_WINDOW)
        f.hello = out.stdout.decode("utf-8", "replace").strip().splitlines()[-1] if out.stdout.strip() else "UNAVAILABLE"
    except (OSError, subprocess.TimeoutExpired, IndexError):
        f.hello = "UNAVAILABLE"
    return f


# ------------------------------------------------------------------------------------------------ shortcuts
def start_menu() -> Path:
    return Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"


def startup_folder() -> Path:
    return start_menu() / "Startup"


def desktop_folder() -> Path:
    return Path.home() / "Desktop"


def make_shortcut(run: Runner, link: Path, target: str, args: str, workdir: str, say, description: str = "Echo") -> bool:
    link.parent.mkdir(parents=True, exist_ok=True)
    ps = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:ECHO_LNK); $s.TargetPath = $env:ECHO_TARGET; "
          "$s.Arguments = $env:ECHO_ARGS; $s.WorkingDirectory = $env:ECHO_DIR; $s.Description = $env:ECHO_DESC; $s.Save()")
    env = {"ECHO_LNK": str(link), "ECHO_TARGET": target, "ECHO_ARGS": args, "ECHO_DIR": workdir, "ECHO_DESC": description}
    old = {k: os.environ.get(k) for k in env}
    os.environ.update(env)                       # paths go in through the environment: no quoting problems
    try:
        return run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], say, timeout=60) == 0
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ------------------------------------------------------------------------------------------------ the steps
@dataclass
class Step:
    key: str
    title: str
    size: str                 # what it downloads, roughly ("" = nothing)
    action: Callable          # (say) -> (ok, message)


def plan(choices: dict, found: Found, settings, run: Runner) -> list:
    """The steps for what was ticked, in a sensible order. choices: see setup_wizard.Wizard.choices."""
    steps = [Step("prefs", "Save your preferences", "", lambda say: save_preferences(settings, choices, say))]
    if choices.get("shortcuts", True):
        steps.append(Step("shortcuts", "Add Echo to the Start menu" + (" and desktop" if choices.get("desktop_icon") else ""), "",
                          lambda say: add_shortcuts(run, choices, say)))
    if choices.get("startup"):
        steps.append(Step("startup", "Start Echo when you sign in to Windows", "", lambda say: add_startup(run, say)))
    if choices.get("ollama"):
        if not found.ollama:
            steps.append(Step("ollama_install", "Install Ollama (AI that runs on this PC)", "about 1 GB",
                              lambda say: (winget_install(run, WINGET["ollama"], say), "Ollama installed.")))
        if not any(m.startswith(choices.get("model", DEFAULT_MODEL)) for m in found.models):
            model = choices.get("model", DEFAULT_MODEL)
            steps.append(Step("ollama_model", f"Download the AI model “{model}”", "about 2 GB", lambda say: pull_model(run, model, say)))
    if choices.get("phone"):
        if not found.adb:
            steps.append(Step("adb", "Install Android phone tools (adb)", "about 15 MB",
                              lambda say: (winget_install(run, WINGET["adb"], say), "Phone tools installed.")))
        steps.append(Step("phone_app", "Install the Echo app on your phone and connect it", "about 25 MB",
                          lambda say: install_phone_app(run, settings, say)))
    if choices.get("kokoro") and not found.kokoro:
        if not found.pwsh:
            steps.append(Step("pwsh", "Install PowerShell 7 (the natural voice needs it)", "about 110 MB",
                              lambda say: (winget_install(run, WINGET["pwsh"], say), "PowerShell 7 installed.")))
        steps.append(Step("kokoro", "Set up the natural voice (Kokoro)", "about 350 MB", lambda say: setup_kokoro(run, settings, say)))
    if choices.get("whisper") and not found.whisper:
        steps.append(Step("whisper", "Set up faster speech recognition (Whisper)", "about 600 MB", lambda say: setup_whisper(run, say)))
    if choices.get("gestures") and not found.gestures:
        steps.append(Step("gestures", "Set up hand gestures (webcam)", "about 250 MB", lambda say: setup_gestures(run, say)))
    if choices.get("claude") and found.claude:
        steps.append(Step("claude", "Connect Echo to Claude Code", "", lambda say: connect_claude(run, found.claude, say)))
    if choices.get("claude_desktop"):
        steps.append(Step("claude_desktop", "Connect Echo to Claude Desktop", "", lambda say: connect_claude_desktop(say)))
    return steps


def save_preferences(settings, c: dict, say) -> tuple:
    simple = ("user_name", "persona", "hotkey", "wake_word", "proactive", "quiet_hours", "internet_access", "auto_memory",
              "screen_understanding", "computer_use", "llm_url", "local_model", "camera_understanding")
    for k in simple:
        if k in c and c[k] is not None:
            settings[k] = c[k]
    if c.get("llm_key"):
        settings.set_secret("llm_key", c["llm_key"])
    brain = c.get("brain")
    if brain in ("auto", "local", "cloud"):
        settings["brain_mode"] = brain
    if c.get("ollama") and not c.get("local_model"):
        settings["local_model"] = ""
    say("Preferences saved (they're all in Echo's Settings too).")
    return True, "Saved."


def add_shortcuts(run: Runner, c: dict, say) -> tuple:
    ok = make_shortcut(run, start_menu() / "Echo.lnk", pythonw(), "-m echo_desktop", str(HERE), say, "Echo, your assistant")
    if c.get("desktop_icon"):
        ok = make_shortcut(run, desktop_folder() / "Echo.lnk", pythonw(), "-m echo_desktop", str(HERE), say, "Echo, your assistant") and ok
    return ok, "Echo is in the Start menu" + (" and on your desktop." if c.get("desktop_icon") else ".")


def add_startup(run: Runner, say) -> tuple:
    ok = make_shortcut(run, startup_folder() / "Echo.lnk", pythonw(), "-m echo_desktop", str(HERE), say, "Start Echo at sign-in")
    return ok, "Echo will start when you sign in." if ok else "Couldn't add Echo to startup."


def pull_model(run: Runner, model: str, say) -> tuple:
    exe = find_ollama()
    if not exe:
        return False, "Ollama isn't installed yet."
    say(f"Downloading {model} (the first time takes a while)…")
    ok = run([exe, "pull", model], say, timeout=7200) == 0
    return ok, f"{model} is ready: Echo now works offline." if ok else f"Couldn't download {model}."


def download(url: str, dest: Path, say) -> bool:
    try:
        say(f"Downloading {url.rsplit('/', 1)[-1]}…")
        with urllib.request.urlopen(url, timeout=60) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
        return dest.stat().st_size > 1_000_000
    except (OSError, ValueError):
        return False


def wait_for_phone(adb: str, say, seconds: float = 90, sleep=time.sleep) -> tuple:
    """(serial, None) once one authorised phone is connected. The "Allow USB debugging?" question only appears on the
    phone after adb starts, so give the user time to tap Allow instead of failing at once."""
    from . import vault
    start, told = time.monotonic(), False
    while True:
        serial, why = vault.phone_ready(adb)
        waited = time.monotonic() - start
        asking = "allowed this pc" in (why or "").lower()          # connected, waiting for the user's Allow
        absent = "no phone" in (why or "").lower()                  # just plugged in: give it a few seconds to appear
        if serial is not None or not (asking and waited < seconds or absent and waited < 10):
            return serial, why
        if asking and not told:
            say("Unlock the phone and tap Allow on “Allow USB debugging?” (tick “Always allow from this computer”)…")
            told = True
        sleep(2)


def install_problem(output: str) -> str:
    """adb install's failure, in words the user can act on."""
    o = output.upper()
    if "UPDATE_INCOMPATIBLE" in o or "SIGNATURES DO NOT MATCH" in o:
        return ("An older Echo on the phone was signed differently, so this one can't replace it. Uninstall Echo on the "
                "phone (this removes its phone memories and settings), then run Setup again.")
    if "INSUFFICIENT_STORAGE" in o:
        return "The phone is out of space. Free about 100 MB and run Setup again."
    if "USER_RESTRICTED" in o or "INSTALL_CANCELED" in o:
        return "The phone blocked the install. Allow “Install via USB” in Developer options (and tap Install if asked), then run Setup again."
    if "VERSION_DOWNGRADE" in o:
        return "The phone has a newer Echo already. Uninstall it on the phone first if you want this version."
    return "The phone refused the app. Allow “Install via USB” in Developer options if it asks, then run Setup again."


def install_phone_app(run: Runner, settings, say) -> tuple:
    from . import vault
    adb = vault.find_adb(settings["adb_path"] or "")
    if not adb:
        return False, "Android phone tools aren't installed."
    serial, why = wait_for_phone(adb, say)
    if serial is None:
        return False, why + " On the phone: Settings → About phone → tap Build number 7 times, then Developer options → USB debugging."
    apk = find_apk()
    if apk is None:
        return False, ("I couldn't find Echo.apk. It's in the “Echo for Android” folder of the zip you received: keep that "
                       "folder next to “Echo for Windows” and run Setup again.")
    say(f"Installing {apk.name} on the phone…")
    heard = []
    code = run([adb, "-s", serial, "install", "-r", str(apk)], lambda line: (heard.append(line), say(line)), timeout=300)
    if code != 0:
        return False, install_problem(" ".join(heard))
    from .phone_link import wanted_ports
    settings["phone_link"] = True                 # from now on Echo re-links the phone whenever it reconnects
    for port in wanted_ports(settings):
        run([adb, "-s", serial, "reverse", f"tcp:{port}", f"tcp:{port}"], say, timeout=30)
    return True, ("Echo is on your phone and connected to this PC. The phone's AI goes through this PC: while Echo runs "
                  "here, it reconnects by itself whenever the phone is plugged in or on wireless debugging.")


def setup_kokoro(run: Runner, settings, say) -> tuple:
    pwsh = find_pwsh()
    if not pwsh:
        return False, "PowerShell 7 isn't installed."
    code = run([pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "Setup-KokoroVoice.ps1")], say, timeout=3600)
    from . import voice
    pairing = voice.find_pairing()
    if code != 0 or not pairing:
        return False, "The natural voice didn't finish setting up."
    settings.set_secret("kokoro_key", pairing["key"])
    settings["kokoro_fingerprint"] = pairing["fingerprint"]
    settings["use_kokoro"] = True
    return True, "Natural voice ready (Echo starts it by itself)."


def setup_whisper(run: Runner, say) -> tuple:
    script = ROOT / "tools" / "WhisperHost" / "Run-WhisperHost.ps1"
    code = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-SetupOnly"], say, timeout=3600)
    return code == 0, "Faster speech recognition ready (Echo starts it by itself)." if code == 0 else "Whisper didn't finish setting up."


def setup_gestures(run: Runner, say) -> tuple:
    script = HERE.parent / "EchoGestures" / "Run-EchoGestures.ps1"
    code = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-SetupOnly"], say, timeout=3600)
    if code != 0:
        return False, "Gestures didn't finish setting up."
    make_shortcut(run, start_menu() / "Echo hand gestures.lnk", "powershell.exe",
                  f'-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{script}"', str(script.parent), say,
                  "Control Echo with your hand (webcam)")
    return True, "Hand gestures ready: open “Echo hand gestures” from the Start menu."


def connect_claude(run: Runner, claude: str, say) -> tuple:
    py = python_exe()
    ok = True
    for name, script in (("echo", "echo_mcp.py"), ("echo-tools", "echo_tools_mcp.py")):
        run(["cmd", "/c", claude, "mcp", "remove", "-s", "user", name], lambda _l: None, timeout=60)
        ok = run(["cmd", "/c", claude, "mcp", "add", "-s", "user", name, "--", py, str(HERE / script)], say, timeout=60) == 0 and ok
    return ok, "Claude Code can now use Echo (restart Claude Code)." if ok else "Couldn't register Echo with Claude Code."


def connect_claude_desktop(say) -> tuple:
    cfg = Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"
    try:
        data = json.loads(cfg.read_text("utf-8")) if cfg.is_file() else {}
    except (OSError, ValueError):
        return False, "Claude Desktop's settings file couldn't be read; nothing was changed."
    servers = data.setdefault("mcpServers", {})
    py = python_exe()
    servers["echo"] = {"command": py, "args": [str(HERE / "echo_mcp.py")]}
    servers["echo-tools"] = {"command": py, "args": [str(HERE / "echo_tools_mcp.py")]}
    cfg.parent.mkdir(parents=True, exist_ok=True)
    if cfg.is_file():
        cfg.with_suffix(".json.echo-backup").write_text(cfg.read_text("utf-8"), "utf-8")
    cfg.write_text(json.dumps(data, indent=2), "utf-8")
    say(f"Updated {cfg} (a backup is next to it).")
    return True, "Claude Desktop can now use Echo (restart Claude Desktop)."


# ------------------------------------------------------------------------------------------------ helpers Echo starts itself
def _listening(port: int) -> bool:
    import socket
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def start_helpers(say: Callable[[str], None] = lambda s: None) -> list:
    """When Echo starts: run the natural voice and Whisper hosts in the background if they're set up and not running,
    so nobody has to start them by hand. Returns what was started."""
    from . import stt, voice
    started = []
    hidden = ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File"]
    pwsh = find_pwsh()
    if voice.find_pairing() is not None and pwsh and not _listening(31416):
        subprocess.Popen([pwsh, *hidden[1:], str(ROOT / "Run-KokoroVoiceHost.ps1")], creationflags=CREATE_NO_WINDOW)
        started.append("natural voice")
    if stt.find_whisper_pairing() is not None and not _listening(31417):
        subprocess.Popen([*hidden, str(ROOT / "tools" / "WhisperHost" / "Run-WhisperHost.ps1")], creationflags=CREATE_NO_WINDOW)
        started.append("Whisper")
    if started:
        say("Started " + " and ".join(started) + " in the background.")
    return started
