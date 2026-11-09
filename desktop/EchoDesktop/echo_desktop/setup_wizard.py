"""Echo's setup app. Double-click “Setup Echo.exe” (or run `python -m echo_desktop.setup_wizard`): it looks at what
this PC already has, asks a few plain questions, then installs and configures everything you ticked, showing each
step as it goes. Nothing is installed that you didn't tick, and every choice can be changed later in Settings."""
from __future__ import annotations

import queue
import subprocess
import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from . import setup_steps as S

BG, PANEL, TEXT, MUTED = "#07101C", "#0A1625", "#E6F1FA", "#9EB2C3"
CARD, LINE, PRIMARY, GOOD, BAD, TEAL = "#0E1C2E", "#1B2C42", "#2a6f97", "#4ADE80", "#FF8A8A", "#83F5F2"
PAGES = ["Welcome", "About you", "AI brain", "Your phone", "Extras", "Review", "Setting up", "Done"]


def _hover(widget, color):
    widget.bind("<Enter>", lambda _e: widget.configure(bg=_lighter(color)))
    widget.bind("<Leave>", lambda _e: widget.configure(bg=color))


def _lighter(hex_color: str, t: float = 0.12) -> str:
    c = [int(hex_color[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{int(v + (255 - v) * t):02x}" for v in c)


class Wizard:
    def __init__(self, root: tk.Tk, settings, detect: Callable = S.detect, runner: Optional[S.Runner] = None,
                 launch: Callable[[], None] = None, open_vault: Callable[[], None] = None):
        self.root, self.settings, self.detect = root, settings, detect
        self.run = runner or S.Runner()
        self.launch = launch or (lambda: subprocess.Popen([S.pythonw(), "-m", "echo_desktop"], cwd=str(S.HERE),
                                                          creationflags=S.CREATE_NO_WINDOW))
        self.open_vault = open_vault
        self.found: Optional[S.Found] = None
        self.page = 0
        self.events: "queue.Queue" = queue.Queue()
        self.results: list = []
        s = settings
        self.v = {
            "user_name": tk.StringVar(value=s["user_name"] or ""), "persona": tk.StringVar(value=s["persona"] or "echo"),
            "hotkey": tk.StringVar(value=s["hotkey"] or "ctrl+alt+e"), "wake_word": tk.BooleanVar(value=bool(s["wake_word"])),
            "auto_memory": tk.BooleanVar(value=bool(s["auto_memory"])), "proactive": tk.BooleanVar(value=bool(s["proactive"])),
            "brain": tk.StringVar(value="cloud"), "llm_url": tk.StringVar(value=s["llm_url"]), "llm_key": tk.StringVar(),
            "phone": tk.BooleanVar(value=False), "kokoro": tk.BooleanVar(value=False), "whisper": tk.BooleanVar(value=False),
            "gestures": tk.BooleanVar(value=False), "internet_access": tk.BooleanVar(value=bool(s["internet_access"])),
            "computer_use": tk.BooleanVar(value=bool(s["computer_use"])), "screen_understanding": tk.BooleanVar(value=bool(s["screen_understanding"])),
            "claude": tk.BooleanVar(value=False), "claude_desktop": tk.BooleanVar(value=False),
            "startup": tk.BooleanVar(value=True), "desktop_icon": tk.BooleanVar(value=True),
        }
        root.title("Set up Echo")
        root.configure(bg=BG)
        self.f = max(1.0, root.winfo_fpixels("1i") / 96.0)         # follow Windows display scaling
        root.geometry(f"{self.px(920)}x{self.px(640)}")
        root.minsize(self.px(840), self.px(580))
        rail = tk.Frame(root, bg=PANEL, width=self.px(190), padx=18, pady=22)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)
        tk.Label(rail, text="E C H O", fg=TEAL, bg=PANEL, font=("Segoe UI Semibold", 13)).pack(anchor="w")
        tk.Label(rail, text="Setup", fg=MUTED, bg=PANEL, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 18))
        self.rail = []
        for name in PAGES:
            lab = tk.Label(rail, text=name, fg=MUTED, bg=PANEL, font=("Segoe UI", 10), anchor="w", pady=5)
            lab.pack(fill="x")
            self.rail.append(lab)
        right = tk.Frame(root, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(right, bg=BG, padx=34, pady=26)
        self.body.pack(fill="both", expand=True)
        self.nav = tk.Frame(right, bg=BG, padx=34, pady=18)
        self.nav.pack(fill="x")
        self.back = self._button(self.nav, "Back", self.prev, LINE)
        self.next = self._button(self.nav, "Next", self.forward, PRIMARY, bold=True)
        self.next.pack(side="right")
        self.back.pack(side="right", padx=(0, 8))
        self.show(0)
        threading.Thread(target=self._detect, daemon=True).start()
        root.after(100, self._pump)

    # ---- widgets
    def px(self, n: int) -> int:
        return int(n * self.f)

    def _button(self, parent, text, cmd, color, bold=False):
        b = tk.Label(parent, text=text, fg="white", bg=color, padx=18, pady=8, cursor="hand2",
                     font=("Segoe UI Semibold" if bold else "Segoe UI", 10))
        b.bind("<Button-1>", lambda _e: cmd())
        _hover(b, color)
        return b

    def _title(self, text, sub=""):
        tk.Label(self.body, text=text, fg=TEXT, bg=BG, font=("Segoe UI Semibold", 18), anchor="w").pack(fill="x")
        if sub:
            tk.Label(self.body, text=sub, fg=MUTED, bg=BG, font=("Segoe UI", 10), anchor="w", justify="left",
                     wraplength=self.px(620)).pack(fill="x", pady=(4, 14))

    def _check(self, parent, key, text, note=""):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=3)
        tk.Checkbutton(row, variable=self.v[key], text=text, fg=TEXT, bg=BG, selectcolor=PANEL, activebackground=BG,
                       activeforeground=TEXT, font=("Segoe UI", 10), anchor="w").pack(side="left")
        if note:
            tk.Label(row, text=note, fg=MUTED, bg=BG, font=("Segoe UI", 9)).pack(side="left", padx=(6, 0))

    def _field(self, label, key, secret=False, width=40):
        tk.Label(self.body, text=label, fg=MUTED, bg=BG, font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(8, 2))
        box = tk.Frame(self.body, bg=PANEL, padx=8, pady=5)
        box.pack(fill="x")
        tk.Entry(box, textvariable=self.v[key], show="•" if secret else "", bg=PANEL, fg=TEXT, insertbackground=TEXT,
                 relief="flat", font=("Segoe UI", 11), width=width).pack(fill="x")

    def _choice(self, value, title, sub):
        card = tk.Frame(self.body, bg=CARD, padx=14, pady=10, cursor="hand2")
        card.pack(fill="x", pady=4)
        dot = tk.Frame(card, bg=CARD, width=2)          # spacer; the ● in the title shows the choice
        dot.pack(side="left")
        txt = tk.Frame(card, bg=CARD)
        txt.pack(side="left", fill="x", expand=True)
        tk.Label(txt, text=title, fg=TEXT, bg=CARD, font=("Segoe UI Semibold", 10), anchor="w").pack(fill="x")
        tk.Label(txt, text=sub, fg=MUTED, bg=CARD, font=("Segoe UI", 9), anchor="w", justify="left", wraplength=self.px(560)).pack(fill="x")
        for w in (card, txt, *txt.winfo_children()):
            w.bind("<Button-1>", lambda _e: self.v["brain"].set(value))
        self._choices = [c for c in getattr(self, "_choices", []) if c[1].winfo_exists()] + [(value, card, dot, txt)]
        if not getattr(self, "_traced", False):
            self.v["brain"].trace_add("write", lambda *_: self._paint_choices())
            self._traced = True
        self._paint_choices()

    def _paint_choices(self):
        """The picked option stands out: lighter card, a teal title and a ● marker."""
        for value, card, dot, txt in getattr(self, "_choices", []):
            if not card.winfo_exists():
                continue
            on = self.v["brain"].get() == value
            bg = "#14324D" if on else CARD
            for w in (card, dot, txt, *txt.winfo_children()):
                w.configure(bg=bg)
            title = txt.winfo_children()[0]
            title.configure(fg=TEAL if on else TEXT, text=("●  " if on else "○  ") + title.cget("text").lstrip("●○ "))

    # ---- navigation
    def show(self, n):
        self.page = n
        for i, lab in enumerate(self.rail):
            lab.configure(fg=TEXT if i == n else (GOOD if i < n else MUTED), font=("Segoe UI Semibold" if i == n else "Segoe UI", 10),
                          text=("✓  " if i < n else "●  " if i == n else "○  ") + PAGES[i])
        for w in self.body.winfo_children():
            w.destroy()
        getattr(self, f"page_{n}")()
        self.back.pack_forget() if n in (0, 6, 7) else self.back.pack(side="right", padx=(0, 8))
        self.next.configure(text={5: "Set up Echo", 7: "Open Echo"}.get(n, "Next"))
        self.next.pack_forget() if n == 6 else self.next.pack(side="right")

    def forward(self):
        if self.page == 5:
            return self.start()
        if self.page == 7:
            self.launch()
            return self.root.destroy()
        self.show(self.page + 1)

    def prev(self):
        if self.page > 0:
            self.show(self.page - 1)

    # ---- pages
    def page_0(self):
        self._title("Let's set up Echo", "Answer a few questions and Echo does the rest: it downloads and installs what you pick, "
                                         "connects your phone, and adds itself to the Start menu. Nothing is installed that you "
                                         "don't tick, and everything can be changed later in Settings.")
        tk.Label(self.body, text="What's already on this PC", fg=TEXT, bg=BG, font=("Segoe UI Semibold", 11), anchor="w").pack(fill="x", pady=(6, 4))
        self.checks = tk.Frame(self.body, bg=BG)
        self.checks.pack(fill="x")
        self._fill_checks()

    def _fill_checks(self):
        if not getattr(self, "checks", None) or not self.checks.winfo_exists():
            return
        for w in self.checks.winfo_children():
            w.destroy()
        f = self.found
        if f is None:
            tk.Label(self.checks, text="Looking around…", fg=MUTED, bg=BG, font=("Segoe UI", 10), anchor="w").pack(fill="x")
            return
        rows = [(True, f"Python {f.python}"),
                (f.winget, "Windows Package Manager (installs things for you)"),
                (f.main_ai, "Your AI server (FreeLLMAPI) is running" if f.main_ai else "No AI yet: install FreeLLMAPI (link on the AI page), then paste its key there"),
                (bool(f.phone), "Phone connected" if f.phone else ("Phone tools installed; no phone connected" if f.adb else "Phone tools not installed")),
                (f.hello == "AVAILABLE", "Windows Hello for your vault" if f.hello == "AVAILABLE" else "Windows Hello not set up (the vault can use a PIN)"),
                (f.kokoro, "Natural voice"), (f.whisper, "Whisper speech recognition"), (bool(f.claude), "Claude Code")]
        for ok, text in rows:
            row = tk.Frame(self.checks, bg=BG)
            row.pack(fill="x", pady=1)
            tk.Label(row, text="✓" if ok else "○", fg=GOOD if ok else MUTED, bg=BG, font=("Segoe UI Semibold", 11), width=2).pack(side="left")
            tk.Label(row, text=text, fg=TEXT if ok else MUTED, bg=BG, font=("Segoe UI", 10), anchor="w").pack(side="left")

    def page_1(self):
        self._title("About you", "So Echo can greet you and fit how you like to work.")
        self._field("Your name", "user_name")
        from . import core
        names = [p.name for p in core.load_personas()]
        tk.Label(self.body, text="Echo's personality", fg=MUTED, bg=BG, font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(8, 2))
        ttk.Combobox(self.body, textvariable=self.v["persona"], values=[n.lower() for n in names], state="readonly").pack(fill="x")
        self._field("Shortcut to talk to Echo from any app", "hotkey")
        tk.Frame(self.body, bg=BG, height=8).pack()
        self._check(self.body, "wake_word", "Wake Echo by saying “Hey Echo”", "(listens on this PC only)")
        self._check(self.body, "auto_memory", "Remember things I mention")
        self._check(self.body, "proactive", "Nudge me about tasks due, birthdays, low battery", "(quiet 10 pm – 7 am)")

    def page_2(self):
        self._title("Echo's AI brain", "Simple commands work without any AI. For conversation, pick where Echo thinks.")
        self._choice("cloud", "FreeLLMAPI — recommended", "Free models from many providers behind one address. Enter it and its key below.")
        self._choice("skip", "Decide later", "Built-in commands, tools and the vault work right away.")
        if not (self.found and self.found.main_ai):
            how = tk.Frame(self.body, bg=CARD, padx=12, pady=8)
            how.pack(fill="x", pady=(8, 0))
            for line in ("1.  Download FreeLLMAPI for Windows (the .exe, not Docker) and run it.",
                         "2.  In its dashboard, add one free provider key (e.g. Google AI Studio → Get API key).",
                         "3.  Click its tray icon, copy its key (starts with freellmapi-) and paste it below."):
                tk.Label(how, text=line, fg=TEXT, bg=CARD, font=("Segoe UI", 9), anchor="w", justify="left").pack(fill="x")
            ttk.Button(how, text="Open the FreeLLMAPI download page",
                       command=lambda: __import__("webbrowser").open("https://github.com/tashfeenahmed/freellmapi/releases/latest")
                       ).pack(anchor="w", pady=(6, 0))
        self._field("AI server address (ends in /v1)", "llm_url")
        self._field("FreeLLMAPI key (starts with freellmapi-, stored encrypted)", "llm_key", secret=True)

    def page_3(self):
        f = self.found
        self._title("Your phone (optional)", "Echo can install its app on your Android phone and connect it to this PC.")
        self._check(self.body, "phone", "Set up my Android phone", "(about 40 MB)")
        steps = tk.Frame(self.body, bg=CARD, padx=16, pady=12)
        steps.pack(fill="x", pady=(10, 0))
        tk.Label(steps, text="On the phone, once:", fg=TEXT, bg=CARD, font=("Segoe UI Semibold", 10), anchor="w").pack(fill="x")
        for line in ("1.  Settings → About phone → tap “Build number” 7 times.",
                     "2.  Settings → Developer options → turn on “USB debugging”.",
                     "3.  Plug the phone into this PC and tap “Allow” when it asks."):
            tk.Label(steps, text=line, fg=MUTED, bg=CARD, font=("Segoe UI", 10), anchor="w").pack(fill="x", pady=1)
        state = ("✓ Phone connected" if f and f.phone else (f.phone_note if f and f.adb else "Phone tools will be installed for you"))
        tk.Label(self.body, text=state, fg=GOOD if f and f.phone else MUTED, bg=BG, font=("Segoe UI", 10), anchor="w").pack(fill="x", pady=(10, 0))
        if f and not f.apk:
            tk.Label(self.body, text="Echo.apk isn't next to this folder: keep “Echo for Android” beside “Echo for Windows” as it came in the zip.", fg=MUTED, bg=BG,
                     font=("Segoe UI", 9), anchor="w").pack(fill="x")

    def page_4(self):
        f = self.found
        self._title("Extras", "Tick what you'd like. Sizes are what gets downloaded once.")
        cols = tk.Frame(self.body, bg=BG)
        cols.pack(fill="x")
        left, right = tk.Frame(cols, bg=BG), tk.Frame(cols, bg=BG)
        left.pack(side="left", fill="both", expand=True)
        right.pack(side="left", fill="both", expand=True)
        tk.Label(left, text="Voice & senses", fg=TEXT, bg=BG, font=("Segoe UI Semibold", 10), anchor="w").pack(fill="x", pady=(0, 4))
        self._check(left, "kokoro", "Natural voice (Kokoro)", "✓ ready" if f and f.kokoro else "about 350 MB")
        self._check(left, "whisper", "Better speech recognition", "✓ ready" if f and f.whisper else "~600 MB")
        self._check(left, "gestures", "Hand gestures (webcam)", "✓ ready" if f and f.gestures else "~250 MB")
        self._check(left, "internet_access", "Answer from the internet")
        self._check(left, "screen_understanding", "Answer questions about my screen")
        self._check(left, "computer_use", "Let Echo use my mouse & keyboard", "(asks before risky steps)")
        tk.Label(right, text="Convenience", fg=TEXT, bg=BG, font=("Segoe UI Semibold", 10), anchor="w").pack(fill="x", pady=(0, 4))
        self._check(right, "startup", "Start Echo when I sign in")
        self._check(right, "desktop_icon", "Echo icon on my desktop")
        if f and f.claude:
            self._check(right, "claude", "Let Claude Code use Echo")
        self._check(right, "claude_desktop", "Let Claude Desktop use Echo")

    def choices(self) -> dict:
        c = {k: (v.get().strip() if isinstance(v.get(), str) else v.get()) for k, v in self.v.items()}
        brain = c.pop("brain")
        c["brain"] = "cloud" if brain == "cloud" else None
        c["ollama"] = False                       # the local llama model was removed: Echo uses FreeLLMAPI
        c["shortcuts"] = True
        c["persona"] = c["persona"] or "echo"
        return c

    def page_5(self):
        self.steps = S.plan(self.choices(), self.found or S.Found(), self.settings, self.run)
        self._title("Ready to set up", "Echo will do these steps for you. You can keep using your PC while it works.")
        for st in self.steps:
            row = tk.Frame(self.body, bg=CARD, padx=14, pady=8)
            row.pack(fill="x", pady=2)
            tk.Label(row, text="•", fg=TEAL, bg=CARD, font=("Segoe UI Semibold", 11)).pack(side="left")
            tk.Label(row, text=st.title, fg=TEXT, bg=CARD, font=("Segoe UI", 10), anchor="w").pack(side="left", padx=8)
            if st.size:
                tk.Label(row, text=st.size, fg=MUTED, bg=CARD, font=("Segoe UI", 9)).pack(side="right")

    def page_6(self):
        self._title("Setting up Echo…", "This can take a while for big downloads. Echo shows each step as it goes.")
        self.bar = ttk.Progressbar(self.body, maximum=max(1, len(self.steps)))
        self.bar.pack(fill="x", pady=(0, 10))
        self.rows = []
        for st in self.steps:
            row = tk.Frame(self.body, bg=CARD, padx=14, pady=7)
            row.pack(fill="x", pady=2)
            icon = tk.Label(row, text="○", fg=MUTED, bg=CARD, font=("Segoe UI Semibold", 11), width=2)
            icon.pack(side="left")
            box = tk.Frame(row, bg=CARD)
            box.pack(side="left", fill="x", expand=True)
            tk.Label(box, text=st.title, fg=TEXT, bg=CARD, font=("Segoe UI", 10), anchor="w").pack(fill="x")
            note = tk.Label(box, text="", fg=MUTED, bg=CARD, font=("Segoe UI", 9), anchor="w")
            note.pack(fill="x")
            self.rows.append((icon, note))

    def page_7(self):
        ok = sum(1 for r in self.results if r[0])
        self._title("Echo is ready" if ok == len(self.results) else "Almost there",
                    f"{ok} of {len(self.results)} steps done." + ("" if ok == len(self.results) else
                    " The ones marked ✗ can be tried again by running Setup Echo again."))
        for (good, msg), st in zip(self.results, self.steps):
            row = tk.Frame(self.body, bg=BG)
            row.pack(fill="x", pady=1)
            tk.Label(row, text="✓" if good else "✗", fg=GOOD if good else BAD, bg=BG, font=("Segoe UI Semibold", 11), width=2).pack(side="left")
            tk.Label(row, text=msg or st.title, fg=TEXT if good else BAD, bg=BG, font=("Segoe UI", 10), anchor="w",
                     wraplength=self.px(600), justify="left").pack(side="left")
        tips = tk.Frame(self.body, bg=CARD, padx=16, pady=12)
        tips.pack(fill="x", pady=(14, 0))
        key = (self.settings["hotkey"] or "ctrl+alt+e").upper().replace("+", " + ")
        for line in (f"Press {key} anywhere and say “what can you do”.",
                     "Say “open my vault” to add passwords and cards; the AI never sees them.",
                     "Say “learn my Documents folder”, then ask about your notes."):
            tk.Label(tips, text="•  " + line, fg=TEXT, bg=CARD, font=("Segoe UI", 10), anchor="w").pack(fill="x", pady=1)

    # ---- doing it
    def start(self):
        self.results = []
        self.show(6)
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self):
        for i, st in enumerate(self.steps):
            self.events.put(("begin", i, ""))
            try:
                ok, msg = st.action(lambda line, i=i: self.events.put(("line", i, line)))
            except Exception as e:                      # a broken step must not stop the others
                ok, msg = False, f"{st.title} failed: {e}"
            self.events.put(("end", i, (bool(ok), msg)))
        self.events.put(("done", -1, None))

    def _detect(self):
        try:
            found = self.detect(self.settings)
        except Exception:
            found = S.Found()
        self.events.put(("found", -1, found))

    def _pump(self):
        try:
            while True:
                kind, i, data = self.events.get_nowait()
                if kind == "found":
                    self.found = data
                    if self.page == 0:
                        self._fill_checks()
                elif kind == "begin":
                    self.rows[i][0].configure(text="◐", fg=TEAL)
                    self.rows[i][1].configure(text="Working…")
                elif kind == "line":
                    self.rows[i][1].configure(text=str(data)[:110])
                elif kind == "end":
                    good, msg = data
                    self.results.append(data)
                    self.rows[i][0].configure(text="✓" if good else "✗", fg=GOOD if good else BAD)
                    self.rows[i][1].configure(text=msg[:110], fg=MUTED if good else BAD)
                    self.bar.configure(value=i + 1)
                elif kind == "done":
                    self.root.after(600, lambda: self.show(7))
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(100, self._pump)


def main() -> None:
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)        # crisp text on high-DPI screens
    except (AttributeError, OSError):
        pass
    from .storage import Settings
    root = tk.Tk()
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TProgressbar", background=PRIMARY, troughcolor=PANEL, bordercolor=PANEL, lightcolor=PRIMARY, darkcolor=PRIMARY)
    style.configure("TCombobox", fieldbackground=PANEL, background=PANEL, foreground=TEXT, arrowcolor=TEXT)
    from .__main__ import record_location
    record_location()
    Wizard(root, Settings())
    root.mainloop()


if __name__ == "__main__":
    main()
