"""EchoDesktop UI (tkinter, standard library): a translucent always-on-top orb, a chat window, settings and
memory manager. Worker threads talk to Tk only through App.post / App.run_on_main."""
from __future__ import annotations

import math
import queue
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from . import core, voice
from .brain import DesktopBrain
from .storage import MemoryStore, Settings
from .words import many

KEY = "#010203"            # transparent key colour for the orb window
BG = "#07101C"
PANEL = "#0A1625"
TEXT = "#E6F1FA"
MUTED = "#9EB2C3"
ORB_COLORS = [("", "Persona"), ("#42D9FF", "Cyan"), ("#B47CFF", "Violet"), ("#FF7A45", "Ember"), ("#3DDC97", "Mint"),
              ("#FFD166", "Gold"), ("#FF5C8A", "Rose"), ("#FFFFFF", "Pearl")]
SCREEN_DISCLOSURE = ("When you ask “what's on my screen?” or “summarize this page”, EchoDesktop hides its own windows, takes one "
                     "screenshot, reads its text with Windows' built-in OCR, deletes the screenshot, and sends the text with your "
                     "question to the AI service you configured (FreeLLMAPI), which may pass it to the AI providers it uses. "
                     "It never reads the screen at any other time and never acts on what the screen says.")
CAMERA_DISCLOSURE = ("When you ask “what do you see?” or “what am I holding?”, EchoDesktop turns on your webcam for about a "
                     "second, takes one photo, and sends it with your question to the AI service you configured (FreeLLMAPI), "
                     "which may pass it to the AI providers it uses. The photo is never saved to disk, the camera is released "
                     "straight away, and Echo never acts on what it sees. Your AI model must support images.")
TELEGRAM_DISCLOSURE = ("Echo will read the messages people send to YOUR Telegram bot (the token you pasted) and answer them. "
                       "Messages travel through Telegram's servers. Only one Telegram account can use it: the first one that "
                       "writes is shown here for you to approve, everyone else is ignored. When you're messaging from your phone, "
                       "anything that would normally ask you on the PC (power, deleting, risky clicks) is declined automatically, "
                       "and typing, clicking and Echo's settings work only at the PC. Turn it off any time: “turn off Telegram”.")
COMPUTER_DISCLOSURE = ("When you say things like “on my computer, rename the newest file in Downloads to report” or “click "
                       "Save”, Echo looks at your screen (the active window's buttons and fields, the text on screen and, if your "
                       "AI model can see images, a small screenshot) and sends that to the AI service you configured (FreeLLMAPI), "
                       "which may pass it to the AI providers it uses. The AI then moves your mouse and types, one step at a time. "
                       "It only starts from your own words, asks before risky steps (Send, Buy, Pay, Delete, Install, Enter in "
                       "chat apps, typing into terminals), never types passwords, and stops when you say or type anything to Echo. "
                       "Close private windows first.")
WEB_DISCLOSURE = ("When you ask things like “go to Gmail and read my latest email” or “on Amazon, find wireless earbuds under "
                  "2000”, Echo opens its own browser window and the AI clicks, types and reads pages for you, one step at a "
                  "time. Page text is sent to the AI service you configured (FreeLLMAPI). It only works on the sites in Echo's "
                  "command list, never types passwords (you sign in yourself, once, in that window), and asks you before "
                  "anything that sends, buys, posts or deletes. Uses the Chrome or Edge already on this PC, with a "
                  "separate Echo profile; nothing to install.")
WAKE_DISCLOSURE = ("With “Hey Echo” on, EchoDesktop keeps your default microphone open using Windows speech recognition on this PC "
                   "to listen for the wake phrase. Audio isn't recorded or stored. Turn it off any time from the orb's menu.")


def blend(c1: str, c2: str, t: float) -> str:
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    rgb = [round(x + (y - x) * t) for x, y in zip(a, b)]
    out = "#%02x%02x%02x" % tuple(rgb)
    return "#020304" if out.lower() == KEY else out


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("Echo")
        self.settings = Settings()
        self.memory = MemoryStore()
        self._calls: "queue.Queue" = queue.Queue()
        self.brain = DesktopBrain(self.settings, self.memory, self)
        self.state = {"mode": "idle", "prompt": "", "answer": "", "error": "", "status": "", "persona": self.settings["persona"]}
        self.orb = Orb(self)
        self.chat = ChatWindow(self)
        self.root.after(30, self._drain)
        # Hand gestures from EchoGestures (webcam, run separately) arrive on 127.0.0.1 only.
        from . import gestures
        gestures.listen(lambda action: self.post(lambda: self._gesture(action)))
        if self.settings["wake_word"]:
            self.root.after(800, self.start_wake)
        self.hotkey = None
        self.start_hotkey()
        if self.settings["auto_start_helpers"]:          # natural voice / Whisper: started for you if they're set up
            from . import setup_steps
            threading.Thread(target=lambda: setup_steps.start_helpers(lambda m: self.update(status=m)), daemon=True).start()
        if not self.settings.secret("llm_key").strip():
            # first launch (no AI key yet): straight to Settings, with what to paste where
            self.root.after(700, lambda: SettingsWindow(self, welcome=FIRST_RUN_NOTE))

    def start_hotkey(self) -> None:
        """Ctrl+Alt+E (Settings "hotkey") from any app: talk to Echo, or stop it while it talks."""
        from .hotkey import GlobalHotkey
        if self.hotkey is not None:
            self.hotkey.stop()
            self.hotkey = None
        if self.settings["hotkey"]:
            self.hotkey = GlobalHotkey(self.settings["hotkey"], lambda: self.post(self.toggle_talk),
                                       lambda message: self.update(status=message))
            self.hotkey.start()

    def nudge(self, message: str) -> None:
        """A proactive nudge: into the chat and as a caption by the orb (the chat window isn't forced open)."""
        def show():
            self.chat.add("Echo", message, "echo")
            self.orb.caption(message[:80])
        self.post(show)

    # ---- thread-safe adapter used by DesktopBrain ----

    def post(self, fn) -> None:
        self._calls.put((fn, None))

    def run_on_main(self, fn):
        if threading.current_thread() is threading.main_thread():
            return fn()
        done = threading.Event()
        box = {}
        self._calls.put((lambda: box.__setitem__("value", fn()), done))
        done.wait(30)
        return box.get("value")

    def _drain(self):
        try:
            while True:
                fn, done = self._calls.get_nowait()
                try:
                    fn()
                finally:
                    if done:
                        done.set()
        except queue.Empty:
            pass
        self.root.after(30, self._drain)

    def update(self, **state) -> None:
        def apply():
            self.state.update(state)
            self.orb.mode = self.state["mode"]
            self.chat.refresh(state)
        self.post(apply)

    def confirm(self, title: str, text: str) -> bool:
        return bool(self.run_on_main(lambda: messagebox.askyesno(title, text, parent=self.chat.win)))

    def clipboard_text(self) -> str:
        from .typer import clipboard_has_secret
        if clipboard_has_secret():                 # a password copied from the vault is never read back
            return ""
        try:
            return self.root.clipboard_get()
        except tk.TclError:
            return ""

    def hide_for_capture(self):
        self._was_visible = self.chat.win.state() == "normal"
        self.orb.win.withdraw()
        self.chat.win.withdraw()
        self.root.update()

    def restore_after_capture(self):
        self.orb.win.deiconify()
        if getattr(self, "_was_visible", False):
            self.chat.win.deiconify()

    def flash(self, message: str) -> None:
        """A small caption next to the orb for ~2.5 s. It never takes the keyboard focus from your app."""
        self.post(lambda: self.orb.caption(message))

    def open_mcp_window(self) -> None:
        McpWindow(self)

    def open_tools_window(self) -> None:
        ToolsWindow(self)

    def open_vault(self) -> None:
        VaultWindow(self)

    def show_secret(self, name: str, values: dict, seconds: int = 20) -> None:
        SecretView(self, name, values, seconds)

    def ask_secret(self, title: str, prompt: str):
        return self.run_on_main(lambda: simpledialog.askstring(title, prompt, show="•", parent=self.chat.win))

    def notify(self, message: str) -> None:
        def show():
            self.chat.add("Echo", (message if message.startswith("⏰") else "Timer · " + message), "echo")
            self.chat.show()
            self.orb.caption(message[:80])
        self.post(show)

    def open_settings(self) -> None:
        SettingsWindow(self)

    def apply_orb_settings(self) -> None:
        self.orb.apply_settings()

    def turn_finished(self) -> None:
        self.post(self.start_wake)

    # ---- talking ----

    def toggle_talk(self):
        if self.brain.mode not in ("idle", "error"):
            self.brain.stop_all("Stopped.")
            return
        self.brain.speaker.stop()
        self.update(mode="listening", status="Listening…")

        def listen():
            texts, scores = self._listen_whisper()
            if texts is None:                                   # no Whisper host: Windows speech recognition
                texts, scores = self.brain.listener.listen_nbest()
            if texts:
                self.brain.submit_voice(texts, scores, "voice")
            else:
                self.update(mode="idle", status="I didn't catch that.")
                self.post(self.start_wake)
        threading.Thread(target=listen, daemon=True).start()

    def _gesture(self, action: str) -> None:
        """open palm = stop, victory = talk, fist = play/pause, thumbs = volume, swipes = tracks."""
        from . import control
        if action == "stop":
            self.brain.stop_all("Stopped by gesture.")
        elif action == "talk":
            if self.brain.mode in ("idle", "error"):
                self.toggle_talk()
        elif action == "play_pause":
            control.media("toggle")
        elif action in ("volume_up", "volume_down"):
            control.volume("up" if action == "volume_up" else "down")
        elif action in ("previous", "next"):
            control.media(action)
        self.update(status=f"Gesture: {action.replace('_', ' ')}")

    def _listen_whisper(self):
        """Whisper on this PC (tools/WhisperHost) when it is set up and running; None means "use Windows speech"."""
        from . import stt
        pairing = stt.find_whisper_pairing()
        if not pairing:
            return None, None
        self.brain.listener.stop_wake()
        self.update(status="Listening (Whisper)…")
        try:
            pcm = stt.record_utterance()
            if not pcm:
                return [], []
            self.update(status="Recognising…")
            r = stt.transcribe(pcm, pairing, "Echo. " + ", ".join(self.brain.vocabulary()[:60]))
        except Exception as e:  # host not running, no microphone…: fall back
            self.update(status=f"Whisper unavailable ({e}); using Windows speech recognition.")
            return None, None
        text = (r.get("text") or "").strip()
        return ([text], [float(r.get("confidence", 0.8))]) if text and r.get("no_speech", 0) < 0.6 else ([], [])

    def start_wake(self):
        if self.settings["wake_word"] and self.brain.mode in ("idle", "error"):
            self.brain.listener.start_wake(lambda: self.post(self._on_wake))

    def _on_wake(self):
        if self.brain.mode in ("idle", "error"):
            self.toggle_talk()

    def set_wake(self, on: bool):
        if on and not messagebox.askyesno("“Hey Echo” wake word", WAKE_DISCLOSURE + "\n\nTurn it on?", parent=self.chat.win):
            return
        self.settings["wake_word"] = on
        if on:
            self.start_wake()
        else:
            self.brain.listener.stop_wake()

    def quit(self):
        self.brain.stop_all()
        self.brain.listener.stop_wake()
        self.brain.voice_pool.close()
        try:
            self.brain.web.close()               # Echo's browser window (and its debugging port) closes with Echo
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


class Orb:
    def __init__(self, app: App):
        self.app = app
        self.mode = "idle"
        self.phase = 0.0
        self.win = tk.Toplevel(app.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", KEY)
        self.win.configure(bg=KEY)
        self.canvas = tk.Canvas(self.win, bg=KEY, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.apply_settings()
        self._drag = None
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._move)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Double-Button-1>", lambda e: app.chat.show())
        self.canvas.bind("<Button-3>", self._menu)
        # Caption window for quiet tasks: created once and only ever made visible/invisible through its opacity,
        # so Windows never activates it (no focus is taken from the app you're working in).
        self.tip = tk.Toplevel(app.root)
        self.tip.overrideredirect(True)
        self.tip.attributes("-topmost", True)
        self.tip.configure(bg="#0f1720")
        self.tip_label = tk.Label(self.tip, text="", fg="#E8EEF5", bg="#0f1720", font=("Segoe UI", 10), padx=10, pady=5,
                                  wraplength=320, justify="left")
        self.tip_label.pack()
        self.tip.attributes("-alpha", 0.0)
        self._tip_job = None
        self.win.after(200, self._no_activate)
        self._animate()

    def _no_activate(self):
        """Clicking the orb or seeing a caption must not steal focus: WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW."""
        try:
            import ctypes
            for w, extra in ((self.win, 0), (self.tip, 0x20)):          # the caption is also click-through
                hwnd = int(w.wm_frame(), 16)
                ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex | 0x08000000 | 0x00000080 | extra)
        except Exception:
            pass

    def caption(self, message: str):
        self.tip_label.config(text=message[:140])
        self.tip.update_idletasks()
        w, h = self.tip.winfo_reqwidth(), self.tip.winfo_reqheight()
        x = max(4, self.win.winfo_x() + self.size // 2 - w // 2)
        x = min(x, self.win.winfo_screenwidth() - w - 4)
        y = self.win.winfo_y() - h - 6
        if y < 4:
            y = self.win.winfo_y() + self.size + 6
        self.tip.geometry(f"+{x}+{y}")
        self.tip.attributes("-alpha", 0.92)
        if self._tip_job:
            self.tip.after_cancel(self._tip_job)
        self._tip_job = self.tip.after(2500, lambda: self.tip.attributes("-alpha", 0.0))

    def apply_settings(self):
        s = self.app.settings
        self.size = int(min(max(s["orb_size"], 56), 200))
        self.win.attributes("-alpha", float(min(max(s["orb_opacity"], 0.2), 1.0)))
        x, y = s["orb_x"], s["orb_y"]
        if x < 0 or y < 0:
            x = self.win.winfo_screenwidth() - self.size - 40
            y = self.win.winfo_screenheight() - self.size - 120
        self.win.geometry(f"{self.size}x{self.size}+{x}+{y}")
        self.canvas.config(width=self.size, height=self.size)

    def color(self) -> str:
        if self.mode == "error":
            return "#FF6B6B"
        return self.app.settings["orb_color"] or self.app.brain.persona().color

    def _animate(self):
        self.phase = (self.phase + 0.03) % 1.0
        c = self.canvas
        c.delete("all")
        mid = self.size / 2
        active = self.mode in ("listening", "speaking")
        radius = core.orb_radius(self.size * 0.42, self.phase, active)
        color = self.color()
        steps = 9
        for i in range(steps):           # soft radial gradient: dim edge → bright core
            t = i / (steps - 1)
            r = radius * (1 - t * 0.85)
            fill = blend(blend(color, "#0b1422", 0.55), blend(color, "#ffffff", 0.55), t)
            c.create_oval(mid - r, mid - r, mid + r, mid + r, fill=fill, outline="")
        if self.mode in ("thinking", "working"):
            r = radius * 0.95
            c.create_arc(mid - r, mid - r, mid + r, mid + r, start=-self.phase * 360, extent=260, style="arc",
                         outline="#ffffff", width=max(2, self.size // 30))
        elif active:
            for i in range(5):
                h = radius * (0.15 + 0.2 * (math.sin(self.phase * 6.28 + i * 1.3) + 1) / 2)
                x = mid + (i - 2) * radius * 0.2
                c.create_line(x, mid - h, x, mid + h, fill="#ffffff", width=max(2, self.size // 28))
        self.win.after(40, self._animate)

    def _press(self, event):
        self._drag = (event.x_root, event.y_root, self.win.winfo_x(), self.win.winfo_y(), False)

    def _move(self, event):
        if not self._drag:
            return
        sx, sy, wx, wy, moved = self._drag
        dx, dy = event.x_root - sx, event.y_root - sy
        if moved or abs(dx) > 4 or abs(dy) > 4:
            self._drag = (sx, sy, wx, wy, True)
            self.win.geometry(f"+{wx + dx}+{wy + dy}")

    def _release(self, _event):
        if self._drag and self._drag[4]:
            self.app.settings["orb_x"] = self.win.winfo_x()
            self.app.settings["orb_y"] = self.win.winfo_y()
        elif self._drag:
            self.app.toggle_talk()
        self._drag = None

    def _menu(self, event):
        app = self.app
        menu = tk.Menu(self.win, tearoff=0)
        menu.add_command(label="Talk (click orb)", command=app.toggle_talk)
        menu.add_command(label="Open chat", command=app.chat.show)
        personas = tk.Menu(menu, tearoff=0)
        for p in app.brain.personas:
            personas.add_command(label=("✓ " if p.id == app.brain.persona().id else "   ") + f"{p.name} — {p.tagline}",
                                 command=lambda p=p: app.brain.submit(f"switch to {p.id} mode"))
        menu.add_cascade(label="Persona", menu=personas)
        wake_on = bool(app.settings["wake_word"])
        menu.add_command(label=("✓ " if wake_on else "") + "“Hey Echo” wake word", command=lambda: app.set_wake(not wake_on))
        menu.add_command(label="Settings…", command=lambda: SettingsWindow(app))
        menu.add_command(label="Memories…", command=lambda: MemoryWindow(app))
        menu.add_command(label="Commands…", command=lambda: CommandsWindow(app))
        menu.add_command(label="Tools (600+)…", command=lambda: ToolsWindow(app))
        menu.add_command(label="Change log (undo Echo's edits)…", command=lambda: ChangeLogWindow(app))
        menu.add_separator()
        menu.add_command(label="Stop", command=lambda: app.brain.stop_all())
        menu.add_command(label="Quit EchoDesktop", command=app.quit)
        menu.tk_popup(event.x_root, event.y_root)


def icon_button(parent, kind: str, command, tip: str) -> tk.Canvas:
    """Flat round icon button drawn as vectors (send / mic / stop), so no emoji or icon font is needed."""
    c = tk.Canvas(parent, width=34, height=34, bg=BG, highlightthickness=0, cursor="hand2")
    fill = "#C2483F" if kind == "stop" else "#1d3a52"
    c.create_oval(1, 1, 33, 33, fill=fill, outline="")
    ink = "#E6F1FA"
    if kind == "mic":
        c.create_rectangle(14, 8, 20, 19, fill=ink, outline="")
        c.create_oval(14, 5, 20, 11, fill=ink, outline="")
        c.create_oval(14, 16, 20, 22, fill=ink, outline="")
        c.create_arc(10, 10, 24, 24, start=180, extent=180, style="arc", outline=ink, width=2)
        c.create_line(17, 24, 17, 28, fill=ink, width=2)
        c.create_line(13, 28, 21, 28, fill=ink, width=2, capstyle="round")
    elif kind == "stop":
        c.create_rectangle(12, 12, 22, 22, fill=ink, outline="")
    else:
        c.create_polygon(10, 9, 26, 17, 10, 25, 13, 17, fill=ink, outline="")
    c.bind("<Button-1>", lambda e: command())
    c.bind("<Enter>", lambda e: c.itemconfigure(1, fill="#2a5274" if kind != "stop" else "#D9584E"))
    c.bind("<Leave>", lambda e: c.itemconfigure(1, fill=fill))
    c.tip = tip
    return c


class CommandsWindow:
    """Searchable list of the Command Pack; double-click a command to try it."""

    def __init__(self, app):
        self.app = app
        cat = app.brain.catalog
        self.win = tk.Toplevel(app.root)
        self.win.title("Echo commands")
        self.win.configure(bg=BG)
        self.win.geometry("520x560")
        count = len(cat.commands) if cat else 0
        tk.Label(self.win, text=f"{count} commands on this PC. Type to search; double-click to run.", fg=MUTED, bg=BG,
                 anchor="w", font=("Segoe UI", 9)).pack(fill="x", padx=12, pady=(10, 4))
        self.query = tk.StringVar()
        entry = tk.Entry(self.win, textvariable=self.query, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 11))
        entry.pack(fill="x", padx=12, ipady=5)
        self.list = tk.Listbox(self.win, bg=PANEL, fg=TEXT, relief="flat", font=("Segoe UI", 10), activestyle="none", selectbackground="#1d3a52")
        self.list.pack(fill="both", expand=True, padx=12, pady=8)
        self.items = []
        self.query.trace_add("write", lambda *_: self._fill())
        self.list.bind("<Double-Button-1>", self._run)
        self._fill()
        entry.focus_set()

    def _example(self, c):
        from . import catalog
        if c.examples:
            return c.examples[0]
        return catalog.samples(catalog.parse_pattern(c.phrases[0]), lambda n: "5" if catalog.is_number_slot(n) else "pizza")[0]

    def _fill(self):
        cat = self.app.brain.catalog
        q = self.query.get().lower().strip()
        self.list.delete(0, "end")
        self.items = []
        for c in (cat.commands if cat else []):
            if q and q not in c.title.lower() and q not in c.group.lower() and not any(q in p for p in c.phrases):
                continue
            example = self._example(c)
            self.items.append(example)
            self.list.insert("end", f"{c.title}  —  “{example}”  ·  {c.group}")
            if len(self.items) >= 300:
                break

    def _run(self, _event):
        sel = self.list.curselection()
        if sel:
            self.app.brain.submit(self.items[sel[0]], "typed")
            self.app.chat.show()


class ChatWindow:
    def __init__(self, app: App):
        self.app = app
        self.win = tk.Toplevel(app.root)
        self.win.title("Echo")
        self.win.configure(bg=BG)
        self.win.geometry("440x560")
        self.win.protocol("WM_DELETE_WINDOW", self.win.withdraw)
        style = ttk.Style(self.win)
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=PANEL, background=PANEL, foreground=TEXT)
        top = tk.Frame(self.win, bg=BG)
        top.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(top, text="E C H O", fg="#83F5F2", bg=BG, font=("Segoe UI Semibold", 11)).pack(side="left")
        self.persona_var = tk.StringVar()
        self.persona_box = ttk.Combobox(top, textvariable=self.persona_var, state="readonly", width=18,
                                        values=[p.name for p in app.brain.personas])
        self.persona_box.pack(side="right")
        self.persona_box.bind("<<ComboboxSelected>>", self._persona_selected)
        self.status = tk.Label(self.win, text="Ready", fg=MUTED, bg=BG, anchor="w", font=("Segoe UI", 9))
        self.status.pack(fill="x", padx=12)
        self.log = tk.Text(self.win, bg=PANEL, fg=TEXT, wrap="word", relief="flat", padx=10, pady=10, font=("Segoe UI", 10))
        self.log.pack(fill="both", expand=True, padx=12, pady=6)
        self.log.tag_config("you", foreground="#83F5F2")
        self.log.tag_config("echo", foreground=TEXT)
        self.log.tag_config("error", foreground="#FF8A8A")
        self.log.config(state="disabled")
        bottom = tk.Frame(self.win, bg=BG)
        bottom.pack(fill="x", padx=12, pady=(0, 12))
        self.entry = tk.Entry(bottom, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 11))
        self.entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.entry.bind("<Return>", lambda e: self._send())
        for kind, cmd, tip in (("send", self._send, "Send"), ("mic", app.toggle_talk, "Talk"), ("stop", lambda: app.brain.stop_all(), "Stop")):
            icon_button(bottom, kind, cmd, tip).pack(side="left", padx=(6, 0))
        self._sync_persona()
        self.win.withdraw()
        self.add("Echo", "Hi! Click the orb or the mic to talk (say “stop” or click again to interrupt me), or type below. Right-click the orb for personas, commands and settings.", "echo")

    def show(self):
        self.win.deiconify()
        self.win.lift()
        self.entry.focus_set()

    def add(self, who: str, text: str, tag: str):
        self.log.config(state="normal")
        self.log.insert("end", f"{who}: ", tag)
        self.log.insert("end", text + "\n\n", tag)
        self.log.see("end")
        self.log.config(state="disabled")

    def refresh(self, change: dict):
        if change.get("prompt"):
            self.add("You", change["prompt"], "you")
        if change.get("answer"):
            self.add(self.app.brain.persona().name, change["answer"], "error" if change.get("error") else "echo")
        if "persona" in change:
            self._sync_persona()
        label = {"idle": "Ready", "listening": "Listening…", "thinking": "Thinking…", "working": "Working…",
                 "speaking": "Speaking", "error": "Something went wrong"}.get(self.app.state["mode"], "")
        extra = self.app.state.get("status") or ""
        self.status.config(text=label + (f" · {extra}" if extra else ""))

    def _sync_persona(self):
        persona = self.app.brain.persona()
        self.persona_var.set(persona.name)

    def _persona_selected(self, _event):
        persona = next((p for p in self.app.brain.personas if p.name == self.persona_var.get()), None)
        if persona:
            self.app.brain.submit(f"switch to {persona.id} mode")

    def _send(self):
        text = self.entry.get().strip()
        if text:
            self.entry.delete(0, "end")
            self.app.brain.submit(text, "typed")


FIRST_RUN_NOTE = ("Welcome to Echo! One step left: give Echo its AI.\n"
                  "1. Install and open FreeLLMAPI (github.com/tashfeenahmed/freellmapi).\n"
                  "2. Copy its key (starts with freellmapi-) from FreeLLMAPI's window or tray icon.\n"
                  "3. Paste it into “AI API key” below, then press Save.\n"
                  "The full guide is SETUP-GUIDE.md in the folder you unzipped.")


def test_ai_connection(url: str, key: str, timeout: float = 6) -> tuple:
    """(message, ok) for the AI address and key: reachable, key accepted, how many models."""
    import json as _json
    import urllib.error
    import urllib.request
    if not url.endswith("/v1"):
        return "The AI URL should end in /v1 (for example http://127.0.0.1:31415/v1).", False
    req = urllib.request.Request(url + "/models", headers={"Authorization": f"Bearer {key}"} if key else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            models = (_json.loads(r.read() or b"{}") or {}).get("data") or []
        if not models:
            return ("FreeLLMAPI answered, but it has no AI models yet: open its dashboard → Keys and add a provider key "
                    "(for example Google AI Studio)."), False
        return f"Connected: FreeLLMAPI answered with {len(models)} model(s). Press Save.", True
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return "FreeLLMAPI is running but rejected the key. Copy it again from its tray icon (starts with freellmapi-).", False
        return f"FreeLLMAPI answered with an error ({e.code}). Check the URL.", False
    except (urllib.error.URLError, OSError, ValueError):
        return "Nothing answers at that address. Is FreeLLMAPI running? Its tray menu shows the address.", False


class SettingsWindow:
    def __init__(self, app: App, welcome: str = ""):
        self.app = app
        s = app.settings
        top = self.win = tk.Toplevel(app.root)
        top.title("Echo settings")
        top.configure(bg=BG)
        height = min(760, int(top.winfo_screenheight() * 0.85))
        canvas = tk.Canvas(top, bg=BG, highlightthickness=0, width=420, height=height)
        bar = tk.Scrollbar(top, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        win = tk.Frame(canvas, bg=BG, padx=14, pady=12)           # everything below is packed into this scrolling frame
        inner = canvas.create_window((0, 0), window=win, anchor="nw")
        win.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(inner, width=e.width))
        top.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
        self.vars = {}

        def row(label, key, secret=False, value=None):
            tk.Label(win, text=label, fg=MUTED, bg=BG, anchor="w").pack(fill="x")
            var = tk.StringVar(value=value if value is not None else str(s[key]))
            tk.Entry(win, textvariable=var, show="•" if secret else "", bg=PANEL, fg=TEXT, insertbackground=TEXT,
                     relief="flat", width=48).pack(fill="x", pady=(0, 6), ipady=3)
            self.vars[key] = var

        if welcome:
            tk.Label(win, text=welcome, fg=TEXT, bg=PANEL, justify="left", anchor="w", wraplength=390,
                     padx=10, pady=8).pack(fill="x", pady=(0, 10))
            top.lift()
            top.attributes("-topmost", True)
            top.after(1500, lambda: top.attributes("-topmost", False))
        row("AI URL (FreeLLMAPI, ends in /v1)", "llm_url")
        row("AI API key (FreeLLMAPI key, starts with freellmapi-; stored encrypted)", "llm_key", secret=True, value=s.secret("llm_key"))
        test_row = tk.Frame(win, bg=BG)
        test_row.pack(fill="x", pady=(0, 8))
        self.test_note = tk.Label(test_row, text="", fg=MUTED, bg=BG, anchor="w", justify="left", wraplength=250)
        tk.Button(test_row, text="Test connection", command=self._test_ai, bg="#1d3a52", fg=TEXT, relief="flat").pack(side="left")
        if welcome:                                  # first run: no scrolling to the bottom to save the key
            tk.Button(test_row, text="Save", command=self._save, bg="#2a6f97", fg="white", relief="flat").pack(side="left", padx=(6, 0))
        self.test_note.pack(side="left", padx=(8, 0), fill="x", expand=True)
        row("Preferred AI model (optional; empty = FreeLLMAPI picks; e.g. a model from its dashboard)", "llm_model")
        row("Your name", "user_name")
        row("Interpreter language", "target_language")
        row("Kokoro endpoint", "kokoro_endpoint")
        row("Kokoro bearer key (stored encrypted)", "kokoro_key", secret=True, value=s.secret("kokoro_key"))
        row("Kokoro certificate SHA-256", "kokoro_fingerprint")
        row("Extra websites Echo may control (Name=https://…;…)", "web_extra_sites")
        row("My projects Echo may edit (name=C:\\folder; …) — every change is logged and revertible", "workspaces")
        row("Phone bridge key (type this into the phone app)", "bridge_key", value=app.brain.bridge_key())
        row("Shortcut to talk to Echo from any app (e.g. ctrl+alt+e; empty = off)", "hotkey")
        row("Quiet hours for spoken nudges (e.g. 22-7)", "quiet_hours")
        row("adb.exe for “unlock my phone” (empty = find it automatically)", "adb_path")
        row("Telegram bot token from @BotFather (stored encrypted)", "telegram_token", secret=True, value=s.secret("telegram_token"))
        tk.Button(win, text="Import Kokoro pairing from this PC", command=self._import_pairing, bg="#1d3a52", fg=TEXT,
                  relief="flat").pack(fill="x", pady=(0, 8))
        self.flags = {}
        for key, label in (("use_kokoro", "Use Kokoro voice (falls back to the Windows voice)"),
                           ("fast_voice", "Instant voice: keep the voice and recogniser loaded (~260 MB RAM; mic stays off until you talk)"),
                           ("stream_replies", "Speak AI answers while they're still being written"),
                           ("auto_memory", "Let Echo remember things you mention"),
                           ("screen_understanding", "Answer questions about my screen"),
                           ("camera_understanding", "Answer questions using my webcam"),
                           ("web_control", "Control websites for me (Echo browser)"),
                           ("phone_bridge", "Let my phone send website tasks to this PC"),
                           ("phone_link", "Reconnect my phone to this PC's AI whenever it's plugged in"),
                           ("code_autorun", "Let Echo run the code it writes without asking (EchoProjects only)"),
                           ("computer_use", "Let Echo use my mouse and keyboard (asks before risky steps)"),
                           ("mcp_ai_tools", "Let the AI use my MCP tools (asks before anything that changes things)"),
                           ("internet_access", "Let Echo use the internet to look things up and answer (downloads ask first)"),
                           ("ai_tools", "Let the AI use Echo's 600+ built-in tools (changes ask first)"),
                           ("proactive", "Nudge me: tasks due, follow-ups, birthdays, habits, low battery, full disk"),
                           ("privacy_mode", "Privacy mode: no internet lookups (AI questions still go to FreeLLMAPI)"),
                           ("telegram", "Let me message Echo from Telegram (only my approved account)")):
            var = tk.BooleanVar(value=bool(s[key]))
            tk.Checkbutton(win, text=label, variable=var, fg=TEXT, bg=BG, selectcolor=PANEL, activebackground=BG,
                           activeforeground=TEXT, anchor="w").pack(fill="x")
            self.flags[key] = var
        tk.Button(win, text="MCP servers (tools for Echo's AI)…", command=lambda: McpWindow(app), bg="#1d3a52", fg=TEXT,
                  relief="flat").pack(fill="x", pady=(8, 0))
        tk.Button(win, text="Vault: passwords, PINs, cards (the AI never sees them)…",
                  command=lambda: app.brain.submit("open my vault", "typed"), bg="#1d3a52", fg=TEXT, relief="flat").pack(fill="x", pady=(6, 0))
        tk.Label(win, text="Orb size", fg=MUTED, bg=BG, anchor="w").pack(fill="x", pady=(8, 0))
        self.size = tk.Scale(win, from_=56, to=200, orient="horizontal", bg=BG, fg=TEXT, highlightthickness=0)
        self.size.set(s["orb_size"])
        self.size.pack(fill="x")
        tk.Label(win, text="Orb opacity (%)", fg=MUTED, bg=BG, anchor="w").pack(fill="x")
        self.opacity = tk.Scale(win, from_=20, to=100, orient="horizontal", bg=BG, fg=TEXT, highlightthickness=0)
        self.opacity.set(int(s["orb_opacity"] * 100))
        self.opacity.pack(fill="x")
        tk.Label(win, text="Orb colour", fg=MUTED, bg=BG, anchor="w").pack(fill="x")
        self.color = tk.StringVar(value=next((n for h, n in ORB_COLORS if h == s["orb_color"]), "Persona"))
        ttk.Combobox(win, textvariable=self.color, values=[n for _, n in ORB_COLORS], state="readonly").pack(fill="x", pady=(0, 10))
        tk.Button(win, text="Save", command=self._save, bg="#2a6f97", fg="white", relief="flat").pack(fill="x")

    def _test_ai(self):
        """Ask FreeLLMAPI for its model list with the URL and key as typed (not saved yet) and say plainly what's wrong."""
        url = self.vars["llm_url"].get().strip().rstrip("/")
        key = self.vars["llm_key"].get().strip()
        self.test_note.config(text="Testing…", fg=MUTED)

        def work():
            msg, good = test_ai_connection(url, key)
            self.win.after(0, lambda: self.test_note.config(text=msg, fg="#4ADE80" if good else "#FF8A8A"))
        threading.Thread(target=work, daemon=True).start()

    def _import_pairing(self):
        pairing = voice.find_pairing()
        if not pairing:
            messagebox.showinfo("Kokoro", "No pairing.txt found. Run Setup-KokoroVoice.ps1 first.", parent=self.win)
            return
        self.vars["kokoro_key"].set(pairing["key"])
        self.vars["kokoro_fingerprint"].set(pairing["fingerprint"])

    def _save(self):
        s = self.app.settings
        if self.flags["screen_understanding"].get() and not s["screen_understanding"]:
            if not messagebox.askyesno("Screen understanding", SCREEN_DISCLOSURE + "\n\nTurn it on?", parent=self.win):
                self.flags["screen_understanding"].set(False)
        if self.flags["web_control"].get() and not s["web_control"]:
            if not messagebox.askyesno("Website control", WEB_DISCLOSURE + "\n\nTurn it on?", parent=self.win):
                self.flags["web_control"].set(False)
        if self.flags["computer_use"].get() and not s["computer_use"]:
            if not messagebox.askyesno("Mouse and keyboard", COMPUTER_DISCLOSURE + "\n\nTurn it on?", parent=self.win):
                self.flags["computer_use"].set(False)
        if self.flags["camera_understanding"].get() and not s["camera_understanding"]:
            if not messagebox.askyesno("Webcam vision", CAMERA_DISCLOSURE + "\n\nTurn it on?", parent=self.win):
                self.flags["camera_understanding"].set(False)
        if self.flags["telegram"].get() and not s["telegram"]:
            if not messagebox.askyesno("Telegram", TELEGRAM_DISCLOSURE + "\n\nTurn it on?", parent=self.win):
                self.flags["telegram"].set(False)
        from .hotkey import parse as parse_hotkey
        hotkey = self.vars["hotkey"].get().strip().lower()
        if hotkey and parse_hotkey(hotkey) is None:
            messagebox.showinfo("Shortcut", f"“{hotkey}” isn't a shortcut I can use. Try ctrl+alt+e.", parent=self.win)
            hotkey = s["hotkey"]
        old_hotkey = s["hotkey"]
        for key in ("llm_url", "llm_model", "user_name", "target_language", "kokoro_endpoint", "web_extra_sites", "workspaces",
                    "quiet_hours", "adb_path"):
            s[key] = self.vars[key].get().strip()
        s["hotkey"] = hotkey
        s["brain_mode"] = "cloud"                   # FreeLLMAPI only
        s.set_secret("telegram_token", self.vars["telegram_token"].get())
        privacy_was = s["privacy_mode"]
        s["kokoro_fingerprint"] = "".join(ch for ch in self.vars["kokoro_fingerprint"].get().lower() if ch in "0123456789abcdef")
        s.set_secret("llm_key", self.vars["llm_key"].get())
        s.set_secret("kokoro_key", self.vars["kokoro_key"].get())
        if len(self.vars["bridge_key"].get().strip()) >= 16:      # a short key would be too easy to guess
            s.set_secret("bridge_key", self.vars["bridge_key"].get())
        for key, var in self.flags.items():
            if key != "privacy_mode":
                s[key] = bool(var.get())
        if bool(self.flags["privacy_mode"].get()) != bool(privacy_was):      # same as saying "privacy mode on/off"
            self.app.brain._jarvis("PRIVACY_ON" if self.flags["privacy_mode"].get() else "PRIVACY_OFF", {})
        if s["hotkey"] != old_hotkey:
            self.app.start_hotkey()
        s["orb_size"] = int(self.size.get())
        s["orb_opacity"] = self.opacity.get() / 100
        s["orb_color"] = next((h for h, n in ORB_COLORS if n == self.color.get()), "")
        self.app.brain.apply_settings()
        self.app.orb.apply_settings()
        self.win.destroy()


class ChangeLogWindow:
    """Every request in which Echo changed files: see the diff, revert it (a revert can be reverted too)."""

    def __init__(self, app: App):
        self.app, self.journal = app, app.brain.journal
        win = self.win = tk.Toplevel(app.root)
        win.title("Echo · change log")
        win.configure(bg=BG, padx=12, pady=10)
        tk.Label(win, text="Each line is one request. Select one to see exactly what changed; Revert puts the files back.",
                 fg=MUTED, bg=BG, anchor="w").pack(fill="x")
        self.list = tk.Listbox(win, bg=PANEL, fg=TEXT, selectbackground="#2a6f97", relief="flat", height=10, width=100,
                               font=("Segoe UI", 10))
        self.list.pack(fill="x", pady=6)
        self.list.bind("<<ListboxSelect>>", lambda e: self._show())
        row = tk.Frame(win, bg=BG)
        row.pack(fill="x")
        tk.Button(row, text="Revert selected", command=self._revert, bg="#C2483F", fg="white", relief="flat").pack(side="left")
        tk.Button(row, text="Refresh", command=self._fill, bg="#1d3a52", fg=TEXT, relief="flat").pack(side="left", padx=6)
        self.diff = tk.Text(win, bg=PANEL, fg=TEXT, relief="flat", width=100, height=22, font=("Consolas", 9))
        self.diff.pack(fill="both", expand=True, pady=(6, 0))
        self.diff.tag_config("add", foreground="#4ADE80")
        self.diff.tag_config("del", foreground="#FF8A8A")
        self.diff.tag_config("head", foreground="#83F5F2")
        self._fill()

    def _fill(self):
        self.sets = self.journal.recent(100)
        self.list.delete(0, "end")
        for c in self.sets:
            self.list.insert("end", c.summary())
        if not self.sets:
            self.list.insert("end", "Echo hasn't changed any files yet.")

    def _selected(self):
        sel = self.list.curselection()
        return self.sets[sel[0]] if sel and sel[0] < len(self.sets) else None

    def _show(self):
        c = self._selected()
        if not c:
            return
        self.diff.delete("1.0", "end")
        self.diff.insert("end", f"Request: {c.request}\nFolder: {c.folder}\n", "head")
        for f in c.files:
            self.diff.insert("end", f"  {f['action']}: {f['path']}\n", "head")
        self.diff.insert("end", "\n")
        for line in self.journal.diff(c.id).splitlines():
            tag = "add" if line.startswith("+") and not line.startswith("+++") else \
                  "del" if line.startswith("-") and not line.startswith("---") else "head" if line.startswith("@@") else ""
            self.diff.insert("end", line + "\n", tag)

    def _revert(self):
        c = self._selected()
        if not c:
            return
        if not messagebox.askyesno("Revert", f"Revert change #{c.id}?\n\n{c.summary()}", parent=self.win):
            return
        ok, msg = self.journal.revert(c.id)
        if not ok and "changed again" in msg and messagebox.askyesno(
                "Newer edits", msg + "\n\nRestore the old version anyway? (The newer version is kept in the log.)", parent=self.win):
            ok, msg = self.journal.revert(c.id, force=True)
        messagebox.showinfo("Change log", msg, parent=self.win)
        self._fill()


class McpWindow:
    """Edit the MCP server list as JSON, add presets, import from other AI apps."""

    def __init__(self, app: App):
        import json
        from . import mcp_presets
        self.app, self.json = app, json
        win = self.win = tk.Toplevel(app.root)
        win.title("Echo · MCP servers")
        win.configure(bg=BG, padx=12, pady=10)
        tk.Label(win, text="Servers Echo's AI can use. stdio: {\"name\", \"command\", \"args\", \"env\"}   remote: {\"name\", \"url\", "
                           "\"headers\"}   optional: \"trusted\": true, \"enabled\": false", fg=MUTED, bg=BG, wraplength=640,
                 justify="left").pack(fill="x")
        self.text = tk.Text(win, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", width=90, height=20, font=("Consolas", 10))
        self.text.pack(fill="both", expand=True, pady=6)
        self.text.insert("1.0", json.dumps(app.brain.tools.servers(), indent=2, ensure_ascii=False))
        row = tk.Frame(win, bg=BG)
        row.pack(fill="x")
        self.preset = tk.StringVar(value="files")
        ttk.Combobox(row, textvariable=self.preset, values=list(mcp_presets.PRESETS), state="readonly", width=14).pack(side="left")
        tk.Button(row, text="Add preset", command=self._add, bg="#1d3a52", fg=TEXT, relief="flat").pack(side="left", padx=6)
        tk.Button(row, text="Import from Claude / Cursor / VS Code", command=self._import, bg="#1d3a52", fg=TEXT,
                  relief="flat").pack(side="left")
        tk.Button(row, text="Save", command=self._save, bg="#2a6f97", fg="white", relief="flat").pack(side="right")
        self.status = tk.Label(win, text="", fg=MUTED, bg=BG, anchor="w")
        self.status.pack(fill="x", pady=(6, 0))

    def _current(self):
        data = self.json.loads(self.text.get("1.0", "end") or "[]")
        if not isinstance(data, list):
            raise ValueError("the list must be a JSON array [ … ]")
        return data

    def _show(self, servers, note):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", self.json.dumps(servers, indent=2, ensure_ascii=False))
        self.status.config(text=note + "  (Press Save to keep it.)")

    def _add(self):
        from . import mcp_presets
        try:
            merged, added = mcp_presets.merge(self._current(), [mcp_presets.preset_entry(self.preset.get())])
        except ValueError as e:
            return self.status.config(text=f"Fix the JSON first: {e}")
        self._show(merged, f"Added {', '.join(added)}." if added else "Already there.")

    def _import(self):
        from . import mcp_presets
        try:
            found, read = mcp_presets.import_from(None)
            merged, added = mcp_presets.merge(self._current(), found)
        except ValueError as e:
            return self.status.config(text=f"Fix the JSON first: {e}")
        self._show(merged, f"Imported {', '.join(added)} from {', '.join(read)}." if added else "Nothing new found in your other AI apps.")

    def _save(self):
        try:
            servers = self._current()
            for s in servers:
                if not isinstance(s, dict) or not s.get("name") or not (s.get("command") or s.get("url")):
                    raise ValueError("every server needs a name and a command or url")
        except ValueError as e:
            return self.status.config(text=f"Not saved: {e}")
        self.app.brain.tools._save(servers)
        self.app.brain.tools.close()
        self.status.config(text=f"Saved {len(servers)} server(s). They start the next time Echo uses them.")


class ToolsWindow:
    """Browse and try Echo's 600+ built-in tools: search by what you want to do, read what a tool needs, run it."""

    def __init__(self, app: App):
        import json
        from . import toolbox
        self.app, self.json, self.tb = app, json, toolbox
        self.all = sorted(toolbox.load().values(), key=lambda t: (t.category, t.name))
        win = self.win = tk.Toplevel(app.root)
        win.title(f"Echo · {len(self.all)} tools")
        win.configure(bg=BG, padx=12, pady=10)
        tk.Label(win, text="Type what you want to do (e.g. “emi for a car loan”, “find big files”, “is github down”). "
                           "You never need this window — just ask Echo — but it shows what's possible.",
                 fg=MUTED, bg=BG, wraplength=720, justify="left").pack(fill="x")
        self.query = tk.StringVar()
        entry = tk.Entry(win, textvariable=self.query, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 11))
        entry.pack(fill="x", pady=6)
        entry.bind("<KeyRelease>", lambda e: self._filter())
        body = tk.Frame(win, bg=BG)
        body.pack(fill="both", expand=True)
        self.list = tk.Listbox(body, bg=PANEL, fg=TEXT, width=42, height=22, relief="flat", exportselection=False)
        self.list.pack(side="left", fill="y")
        self.list.bind("<<ListboxSelect>>", lambda e: self._show())
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self.info = tk.Label(right, text="", fg=TEXT, bg=BG, wraplength=430, justify="left", anchor="nw")
        self.info.pack(fill="x")
        tk.Label(right, text="Arguments (JSON):", fg=MUTED, bg=BG, anchor="w").pack(fill="x", pady=(8, 0))
        self.args = tk.Text(right, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", height=6, width=55, font=("Consolas", 10))
        self.args.pack(fill="x")
        tk.Button(right, text="Run this tool", command=self._run, bg="#2a6f97", fg="white", relief="flat").pack(anchor="w", pady=6)
        self.out = tk.Text(right, bg=PANEL, fg=TEXT, relief="flat", height=12, width=55, font=("Consolas", 10), wrap="word")
        self.out.pack(fill="both", expand=True)
        self.shown = []
        self._filter()
        entry.focus_set()

    def _filter(self):
        q = self.query.get().strip()
        self.shown = self.tb.router().search(q, 60) if q else self.all
        self.list.delete(0, "end")
        for t in self.shown:
            self.list.insert("end", f"{t.category:8} {t.name}{'  ⚠' if t.ask else ''}")

    def _tool(self):
        sel = self.list.curselection()
        return self.shown[sel[0]] if sel else None

    def _show(self):
        t = self._tool()
        if not t:
            return
        flags = ", ".join(f for f, on in (("asks before changing anything", t.ask), ("uses the internet", t.net), ("needs the Echo app", t.app)) if on)
        self.info.config(text=f"{t.name}\n\n{t.description}\n\n{t.signature()}" + (f"\n({flags})" if flags else ""))
        self.args.delete("1.0", "end")
        self.args.insert("1.0", self.json.dumps(t.example if t.example is not None else
                                                {k: "" for k in t.schema.get("required", [])}, ensure_ascii=False, indent=1))

    def _run(self):
        t = self._tool()
        if not t:
            return
        try:
            args = self.json.loads(self.args.get("1.0", "end").strip() or "{}")
        except ValueError as e:
            self.out.delete("1.0", "end")
            self.out.insert("1.0", f"The arguments aren't valid JSON: {e}")
            return
        self.out.delete("1.0", "end")
        self.out.insert("1.0", "Working…")

        def work():
            r = self.tb.call(t.name, args, self.app.brain.toolbox_ctx)
            self.app.post(lambda: (self.out.delete("1.0", "end"), self.out.insert("1.0", r)))
        threading.Thread(target=work, daemon=True).start()


class MemoryWindow:
    def __init__(self, app: App):
        self.app = app
        self.win = tk.Toplevel(app.root)
        self.win.title("Echo memories")
        self.win.configure(bg=BG, padx=12, pady=10)
        tk.Label(self.win, text="Stored encrypted on this PC. Passwords, PINs, codes and card numbers are never saved.",
                 fg=MUTED, bg=BG, wraplength=380, justify="left").pack(fill="x")
        self.list = tk.Listbox(self.win, bg=PANEL, fg=TEXT, width=60, height=16, relief="flat", selectmode="extended")
        self.list.pack(fill="both", expand=True, pady=8)
        buttons = tk.Frame(self.win, bg=BG)
        buttons.pack(fill="x")
        tk.Button(buttons, text="Delete selected", command=self._delete, bg="#1d3a52", fg=TEXT, relief="flat").pack(side="left")
        tk.Button(buttons, text="Erase all", command=self._erase, bg="#7a2b2b", fg=TEXT, relief="flat").pack(side="right")
        self._load()

    def _load(self):
        self.items = self.app.memory.all()
        self.list.delete(0, "end")
        for item in self.items:
            self.list.insert("end", ("auto · " if item.get("source") == "auto" else "• ") + item["text"])

    def _delete(self):
        ids = {self.items[i]["id"] for i in self.list.curselection()}
        if ids:
            self.app.memory.delete(ids)
            self._load()

    def _erase(self):
        if self.items and messagebox.askyesno("Erase all memories?", f"Delete {many(len(self.items), 'memory')} from this PC?", parent=self.win):
            self.app.memory.clear()
            self._load()

def keep_out_of_screenshots(win) -> None:
    """Vault windows: invisible to screenshots, screen recording and Echo's own screen reading (WDA_EXCLUDEFROMCAPTURE),
    so a password on screen can't reach the AI's view of the screen."""
    try:
        win.update_idletasks()
        import ctypes
        ctypes.windll.user32.SetWindowDisplayAffinity(int(win.wm_frame(), 16), 0x11)
    except (tk.TclError, ValueError, AttributeError, OSError):
        pass


class VaultWindow:
    """Echo's vault, password-manager style: categories, search, one card per item with everything hidden (••••),
    Show / Copy / Edit / Delete, and a friendly Add form with a password generator and strength meter.
    Each secret is sealed separately in the encrypted vault file and is decrypted only for the moment you Show, Copy or
    use it, after Windows Hello. The window is invisible to screenshots and locks itself after 3 idle minutes."""

    CARD, CARD_HOVER, LINE = "#0E1C2E", "#13263D", "#1B2C42"
    PRIMARY, DANGER, OK_GREEN = "#2a6f97", "#7a2b2b", "#4ADE80"
    CATS = [("all", "All items", "▦"), ("login", "Logins", "🔑"), ("card", "Cards", "💳"), ("phone", "Phone unlock", "📱"),
            ("pin", "PINs", "🔢"), ("wifi", "Wi-Fi", "📶"), ("note", "Secure notes", "📝")]
    AVATAR = ["#2DD4BF", "#4F8BFF", "#B47CFF", "#FF9F43", "#FF6FB5", "#4ADE80", "#F5C542", "#42D9FF"]
    MAIN = {"login": "password", "card": "number", "phone": "pin", "pin": "pin", "wifi": "password", "note": "text"}
    IDLE_LOCK_MS = 180_000

    def __init__(self, app: App):
        self.app, self.vault, self.brain = app, app.brain.vault, app.brain
        self.cat, self.revealed, self._idle = "all", {}, None
        win = self.win = tk.Toplevel(app.root)
        win.title("Echo vault")
        win.configure(bg=BG)
        win.geometry("860x600")
        win.minsize(720, 460)
        keep_out_of_screenshots(win)
        # ---- header
        head = tk.Frame(win, bg=BG, padx=18, pady=14)
        head.pack(fill="x")
        tk.Label(head, text="🔒  Vault", fg=TEXT, bg=BG, font=("Segoe UI Semibold", 17)).pack(side="left")
        tk.Label(head, text="   Encrypted on this PC · every secret sealed on its own · the AI never sees it",
                 fg=MUTED, bg=BG, font=("Segoe UI", 9)).pack(side="left", pady=(6, 0))
        self._button(head, "Lock", self.lock, self.LINE).pack(side="right")
        # ---- body: categories | list
        body = tk.Frame(win, bg=BG)
        body.pack(fill="both", expand=True, padx=(18, 18))
        side = tk.Frame(body, bg=BG, width=180)
        side.pack(side="left", fill="y", padx=(0, 14))
        self.cat_buttons = {}
        for key, label, icon in self.CATS:
            b = tk.Label(side, text=f"  {icon}  {label}", fg=TEXT, bg=BG, anchor="w", font=("Segoe UI", 10), padx=8, pady=7,
                         cursor="hand2")
            b.pack(fill="x", pady=1)
            b.bind("<Button-1>", lambda _e, k=key: self._category(k))
            self.cat_buttons[key] = b
        main = tk.Frame(body, bg=BG)
        main.pack(side="left", fill="both", expand=True)
        search = tk.Frame(main, bg=PANEL, padx=10, pady=6)
        search.pack(fill="x")
        tk.Label(search, text="⌕", fg=MUTED, bg=PANEL, font=("Segoe UI", 12)).pack(side="left")
        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *_: self._fill())
        tk.Entry(search, textvariable=self.query, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat",
                 font=("Segoe UI", 11)).pack(side="left", fill="x", expand=True, padx=(6, 0))
        holder = tk.Frame(main, bg=BG)
        holder.pack(fill="both", expand=True, pady=(10, 0))
        self.canvas = tk.Canvas(holder, bg=BG, highlightthickness=0)
        bar = tk.Scrollbar(holder, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.list = tk.Frame(self.canvas, bg=BG)
        inner = self.canvas.create_window((0, 0), window=self.list, anchor="nw")
        self.list.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(inner, width=e.width))
        win.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-e.delta / 120), "units"))
        # ---- footer
        foot = tk.Frame(win, bg=BG, padx=18, pady=12)
        foot.pack(fill="x")
        self._button(foot, "＋  Add item", self._add, self.PRIMARY, bold=True).pack(side="left")
        self._button(foot, "Vault PIN…", self._pin, self.LINE).pack(side="left", padx=(8, 0))
        self.status = tk.Label(foot, text="", fg=MUTED, bg=BG, font=("Segoe UI", 9))
        self.status.pack(side="right")
        for ev in ("<Motion>", "<Key>", "<Button>"):
            win.bind(ev, lambda _e: self._touch(), add="+")
        win.protocol("WM_DELETE_WINDOW", self.close)
        self._category("all")
        self._touch()

    # ---- small helpers
    def _button(self, parent, text, cmd, color, bold=False):
        b = tk.Label(parent, text=text, fg="white", bg=color, padx=14, pady=6, cursor="hand2",
                     font=("Segoe UI Semibold" if bold else "Segoe UI", 10))
        b.bind("<Button-1>", lambda _e: cmd())
        b.bind("<Enter>", lambda _e: b.configure(bg=blend(color, "#ffffff", 0.12)))
        b.bind("<Leave>", lambda _e: b.configure(bg=color))
        return b

    def _say(self, text, ok=True):
        self.status.configure(text=text, fg=self.OK_GREEN if ok else "#FF8A8A")
        self.win.after(5000, lambda: self.status.winfo_exists() and self.status.configure(text=""))

    def _touch(self):
        if not self.win.winfo_exists():
            return
        if self._idle:
            self.win.after_cancel(self._idle)
        self._idle = self.win.after(self.IDLE_LOCK_MS, self.lock)

    def lock(self):
        self.brain.verifier.lock()
        self.close()

    def close(self):
        self.revealed.clear()
        if self._idle:
            try:
                self.win.after_cancel(self._idle)
            except tk.TclError:
                pass
        self.win.destroy()

    def _verify(self, why) -> bool:
        ok, msg = self.brain.verifier.verify(why)
        if not ok:
            self._say(msg, ok=False)
        return ok

    # ---- list
    def _category(self, key):
        self.cat = key
        for k, b in self.cat_buttons.items():
            b.configure(bg=self.CARD_HOVER if k == key else BG, fg=TEXT if k == key else MUTED)
        self._fill()

    def _fill(self):
        if not self.win.winfo_exists():
            return
        items = self.vault.details()
        counts = {k: sum(1 for i in items if k == "all" or i["kind"] == k) for k, _, _ in self.CATS}
        for key, label, icon in self.CATS:
            self.cat_buttons[key].configure(text=f"  {icon}  {label}" + (f"   {counts[key]}" if counts[key] else ""))
        q = self.query.get().strip().lower()
        shown = [i for i in items if (self.cat == "all" or i["kind"] == self.cat)
                 and (not q or q in f"{i['name']} {i['site']} {i['network']} {i['hint']}".lower())]
        for w in self.list.winfo_children():
            w.destroy()
        if not shown:
            box = tk.Frame(self.list, bg=BG, pady=60)
            box.pack(fill="x")
            tk.Label(box, text="🔐", fg=MUTED, bg=BG, font=("Segoe UI Emoji", 30)).pack()
            tk.Label(box, text="Nothing here yet" if not q else "No matches", fg=TEXT, bg=BG, font=("Segoe UI Semibold", 13)).pack(pady=(6, 2))
            tk.Label(box, text="Add passwords, cards, your phone PIN or Wi-Fi — then just say “type my Gmail password” or “unlock my phone”.",
                     fg=MUTED, bg=BG, font=("Segoe UI", 9), wraplength=420).pack()
            return
        for i in sorted(shown, key=lambda x: x["name"].lower()):
            self._card(i)

    def _card(self, item):
        card = tk.Frame(self.list, bg=self.CARD, padx=12, pady=10)
        card.pack(fill="x", pady=4)
        color = self.AVATAR[sum(map(ord, item["name"])) % len(self.AVATAR)]
        av = tk.Canvas(card, width=40, height=40, bg=self.CARD, highlightthickness=0)
        av.create_oval(2, 2, 38, 38, fill=color, outline="")
        av.create_text(20, 20, text=item["name"][:1].upper(), fill="#07101C", font=("Segoe UI Semibold", 14))
        av.pack(side="left")
        mid = tk.Frame(card, bg=self.CARD, padx=12)
        mid.pack(side="left", fill="x", expand=True)
        tk.Label(mid, text=item["name"], fg=TEXT, bg=self.CARD, font=("Segoe UI Semibold", 11), anchor="w").pack(fill="x")
        sub = " · ".join(x for x in (item["hint"], item["site"] or item["network"]) if x)
        tk.Label(mid, text=sub or dict((k, l) for k, l, _ in self.CATS).get(item["kind"], ""), fg=MUTED, bg=self.CARD,
                 font=("Segoe UI", 9), anchor="w").pack(fill="x")
        field = self.MAIN.get(item["kind"], "password")
        secret = tk.Label(mid, text="•" * 12 if field in item["fields"] else "(nothing saved)", fg="#C9D6E2", bg=self.CARD,
                          font=("Consolas", 11), anchor="w")
        secret.pack(fill="x", pady=(3, 0))
        acts = tk.Frame(card, bg=self.CARD)
        acts.pack(side="right")
        for text, cmd in (("👁  Show", lambda: self._show(item, field, secret)), ("⧉  Copy", lambda: self._copy(item, field)),
                          ("Edit", lambda: self._edit(item)), ("🗑", lambda: self._delete(item))):
            b = tk.Label(acts, text=text, fg=TEXT, bg=self.LINE, padx=10, pady=5, cursor="hand2", font=("Segoe UI", 9))
            b.pack(side="left", padx=2)
            b.bind("<Button-1>", lambda _e, c=cmd: c())
        for w in (card, mid):
            w.bind("<Enter>", lambda _e, c=card: self._hover(c, True))
            w.bind("<Leave>", lambda _e, c=card: self._hover(c, False))

    def _hover(self, card, on):
        color = self.CARD_HOVER if on else self.CARD
        stack = [card]
        while stack:
            w = stack.pop()
            if isinstance(w, (tk.Frame, tk.Canvas)) or (isinstance(w, tk.Label) and w.cget("bg") in (self.CARD, self.CARD_HOVER)):
                try:
                    w.configure(bg=color)
                except tk.TclError:
                    pass
            stack.extend(w.winfo_children())

    # ---- actions (each asks Windows Hello / the vault PIN; one approval covers a minute)
    def _show(self, item, field, label):
        if field not in item["fields"]:
            return
        if not self._verify(f"Show “{item['name']}” in your vault"):
            return
        from .vault import Item
        value = self.vault.reveal(Item(item["id"], item["name"], item["kind"]), field, "show in vault")
        label.configure(text=value or "", fg=TEXT)
        self._say(f"Showing {item['name']} for 15 seconds")

        def hide():
            if label.winfo_exists():
                label.configure(text="•" * 12, fg="#C9D6E2")
        self.win.after(15000, hide)

    def _copy(self, item, field):
        if field not in item["fields"] or not self._verify(f"Copy “{item['name']}” from your vault"):
            return
        from .vault import Item
        from . import typer
        value = self.vault.reveal(Item(item["id"], item["name"], item["kind"]), field, "copy in vault")
        if typer.set_clipboard_secret(value or "", 30):
            self._say("Copied · cleared from the clipboard in 30 seconds · kept out of clipboard history")
        else:
            self._say("The clipboard is busy; try again.", ok=False)

    def _delete(self, item):
        if not messagebox.askyesno("Delete from vault", f"Delete “{item['name']}”? This can't be undone.", parent=self.win):
            return
        if self._verify(f"Delete “{item['name']}” from your vault"):
            self.vault.delete(item["id"])
            self._say(f"Deleted {item['name']}")
            self._fill()

    def _edit(self, item):
        if self._verify(f"Change “{item['name']}” in your vault"):
            ItemForm(self, item)

    def _add(self):
        ItemForm(self, None)

    def _pin(self):
        if self.vault.has_pin() and not self._verify("Change your vault PIN"):
            return
        pin = simpledialog.askstring("Vault PIN", "A PIN for the vault, used when Windows Hello isn't available (4 to 32 characters):",
                                     show="•", parent=self.win)
        if pin:
            try:
                self.vault.set_pin(pin)
                self._say("Vault PIN saved")
            except ValueError as e:
                self._say(str(e).capitalize() + ".", ok=False)


class ItemForm:
    """Add or change one vault item: pick a kind, fill friendly fields (secrets hidden, with an eye to peek), generate
    a strong password, see its strength. Nothing typed here goes anywhere but the sealed vault file."""

    KIND_ORDER = [("login", "🔑 Login"), ("card", "💳 Card"), ("phone", "📱 Phone"), ("pin", "🔢 PIN"), ("wifi", "📶 Wi-Fi"),
                  ("note", "📝 Note")]
    LABELS = {"username": ("Username or email", "you@example.com"), "password": ("Password", ""),
              "site": ("Website — autofill only fills it there", "accounts.google.com"),
              "number": ("Card number", "1234 5678 9012 3456"), "expiry": ("Expiry (MM/YY)", "08/29"), "cvv": ("CVV", "123"),
              "holder": ("Name on card", ""), "pin": ("PIN or password", ""), "network": ("Network name", "Home Wi-Fi"),
              "text": ("Note", "")}

    def __init__(self, vault_window: VaultWindow, item):
        from .vault import KINDS, SECRET_FIELDS
        self.vw, self.item, self.kinds, self.secret_fields = vault_window, item, KINDS, SECRET_FIELDS
        top = self.top = tk.Toplevel(vault_window.win)
        top.title("Change item" if item else "Add to vault")
        top.configure(bg=BG, padx=20, pady=16)
        top.resizable(False, False)
        top.transient(vault_window.win)
        keep_out_of_screenshots(top)
        top.grab_set()
        tk.Label(top, text=f"Change {item['name']}" if item else "Add to your vault", fg=TEXT, bg=BG,
                 font=("Segoe UI Semibold", 14), anchor="w").pack(fill="x")
        tk.Label(top, text="Leave a box empty to keep what's saved." if item else "Only you see this. It's sealed as soon as you save.",
                 fg=MUTED, bg=BG, font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(0, 10))
        self.kind = tk.StringVar(value=item["kind"] if item else "login")
        if not item:
            row = tk.Frame(top, bg=BG)
            row.pack(fill="x", pady=(0, 10))
            self.kind_buttons = {}
            for k, label in self.KIND_ORDER:
                b = tk.Label(row, text=label, fg=TEXT, bg=VaultWindow.LINE, padx=9, pady=5, cursor="hand2", font=("Segoe UI", 9))
                b.pack(side="left", padx=(0, 4))
                b.bind("<Button-1>", lambda _e, kk=k: self._kind(kk))
                self.kind_buttons[k] = b
        self.name = tk.StringVar(value=item["name"] if item else "")
        self._label(top, "Name — what you'll say (“Gmail”, “HDFC card”, “my phone”)")
        self.name_entry = self._entry(top, self.name, secret=False, disabled=bool(item))
        self.fields = tk.Frame(top, bg=BG)
        self.fields.pack(fill="x")
        self.error = tk.Label(top, text="", fg="#FF8A8A", bg=BG, font=("Segoe UI", 9), anchor="w")
        self.error.pack(fill="x", pady=(8, 0))
        btns = tk.Frame(top, bg=BG)
        btns.pack(fill="x", pady=(10, 0))
        vault_window._button(btns, "Save", self._save, VaultWindow.PRIMARY, bold=True).pack(side="right")
        vault_window._button(btns, "Cancel", top.destroy, VaultWindow.LINE).pack(side="right", padx=(0, 8))
        top.bind("<Return>", lambda _e: self._save())
        top.bind("<Escape>", lambda _e: top.destroy())
        self._kind(self.kind.get())

    def _label(self, parent, text):
        tk.Label(parent, text=text, fg=MUTED, bg=BG, font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(6, 2))

    def _entry(self, parent, var, secret, disabled=False):
        row = tk.Frame(parent, bg=PANEL, padx=8, pady=4)
        row.pack(fill="x")
        e = tk.Entry(row, textvariable=var, show="•" if secret else "", bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat",
                     font=("Segoe UI", 11), width=40, state="disabled" if disabled else "normal", disabledbackground=PANEL,
                     disabledforeground=MUTED)
        e.pack(side="left", fill="x", expand=True)
        if secret:
            eye = tk.Label(row, text="👁", fg=MUTED, bg=PANEL, cursor="hand2", font=("Segoe UI", 10))
            eye.pack(side="right")
            eye.bind("<Button-1>", lambda _e: e.configure(show="" if e.cget("show") else "•"))
        return row

    def _kind(self, kind):
        self.kind.set(kind)
        for k, b in getattr(self, "kind_buttons", {}).items():
            b.configure(bg=VaultWindow.PRIMARY if k == kind else VaultWindow.LINE)
        for w in self.fields.winfo_children():
            w.destroy()
        self.vars = {}
        for f in self.kinds[kind][1]:
            label, example = self.LABELS.get(f, (f.capitalize(), ""))
            self._label(self.fields, label + (f"  e.g. {example}" if example and not self.item else ""))
            var = tk.StringVar()
            self._entry(self.fields, var, secret=f in self.secret_fields)
            self.vars[f] = var
            if f == "password":
                self._password_tools(var)
            if f == "number":
                var.trace_add("write", lambda *_a, v=var: self._group_digits(v))

    def _password_tools(self, var):
        row = tk.Frame(self.fields, bg=BG)
        row.pack(fill="x", pady=(4, 0))
        meter = tk.Canvas(row, width=180, height=6, bg=VaultWindow.LINE, highlightthickness=0)
        meter.pack(side="left", pady=4)
        word = tk.Label(row, text="", fg=MUTED, bg=BG, font=("Segoe UI", 9))
        word.pack(side="left", padx=8)

        def update(*_):
            from .vault import strength
            score, text = strength(var.get())
            meter.delete("all")
            if var.get():
                meter.create_rectangle(0, 0, 36 * (score + 1), 6, fill=["#EF4444", "#F97316", "#EAB308", "#22C55E", "#16A34A"][score], width=0)
            word.configure(text=text)
        var.trace_add("write", update)

        def generate():
            from .vault import generate_password
            var.set(generate_password(20))
        gen = tk.Label(row, text="⟳ Generate strong", fg="#83F5F2", bg=BG, cursor="hand2", font=("Segoe UI", 9))
        gen.pack(side="right")
        gen.bind("<Button-1>", lambda _e: generate())

    @staticmethod
    def _group_digits(var):
        digits = "".join(ch for ch in var.get() if ch.isdigit())[:19]
        nice = " ".join(digits[i:i + 4] for i in range(0, len(digits), 4))
        if nice != var.get():
            var.set(nice)

    def _save(self):
        values = {f: v.get() for f, v in self.vars.items() if v.get().strip() != ""}
        try:
            if self.item:
                if values:
                    self.vw.vault.update(self.item["id"], values)
                msg = f"Saved changes to {self.item['name']}"
            else:
                self.vw.vault.add(self.name.get(), self.kind.get(), values)
                msg = f"Added {self.name.get().strip()} · sealed and encrypted"
        except ValueError as e:
            self.error.configure(text=str(e).capitalize() + ".")
            return
        for v in self.vars.values():
            v.set("")
        self.top.destroy()
        self.vw._say(msg)
        self.vw._fill()


class SecretView:
    """Shows one vault item for a few seconds (never spoken, never in the chat), then closes itself."""

    def __init__(self, app: App, name: str, values: dict, seconds: int):
        top = tk.Toplevel(app.root)
        top.title(f"Echo vault · {name}")
        top.configure(bg=BG, padx=14, pady=12)
        top.attributes("-topmost", True)
        keep_out_of_screenshots(top)
        for k, v in values.items():
            tk.Label(top, text=k.capitalize(), fg=MUTED, bg=BG, anchor="w").pack(fill="x")
            e = tk.Entry(top, bg=PANEL, fg=TEXT, relief="flat", width=40)
            e.insert(0, v or "")
            e.configure(state="readonly")
            e.pack(fill="x", pady=(0, 6), ipady=3)
        tk.Label(top, text=f"Closes in {seconds} seconds.", fg=MUTED, bg=BG).pack(fill="x")
        top.after(seconds * 1000, top.destroy)
