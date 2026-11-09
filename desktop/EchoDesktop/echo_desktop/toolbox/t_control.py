"""Control the PC: Echo's 3,700 built-in commands, keys, typing, mouse, windows, apps, websites, messages."""
from __future__ import annotations

import os
import re
import urllib.parse
from typing import Literal

from . import ToolError, tool
from ..words import many

C = "control"
_cat = None


def catalog_():
    global _cat
    if _cat is None:
        from .. import catalog
        _cat = catalog.load("desktop")
    return _cat


def _focus(ctx):
    f = getattr(ctx, "focus", None)
    if f is not None:
        f.focus_target()


@tool(C, ex={"query": "snap window left"}, keys="echo commands search shortcuts discover what can echo do")
def find_echo_commands(query: str, limit: int = 12) -> list:
    """Search Echo's 3,700 built-in commands (shortcuts, windows, apps, settings, Office/VS Code/browser keys…) by words."""
    from .. import catalog, core
    words = {w for w in core.normalize(query).split() if len(w) > 2}
    scored = []
    for c in catalog_().commands:
        if c.kind in ("echo", "list"):
            continue
        hay = f"{c.title} {c.group} {' '.join(c.phrases)}".lower()
        s = sum(2 if w in c.title.lower() else 1 for w in words if w in hay)
        if s:
            scored.append((s, c))
    scored.sort(key=lambda sc: (-sc[0], sc[1].order))
    return [f"“{catalog.samples(catalog.parse_pattern(c.phrases[0]), lambda s: '5' if s.startswith('n') else 'pizza')[0]}” — {c.title} [{c.group}]"
            for _, c in scored[:max(1, min(limit, 50))]] or ["No matching command."]


@tool(C, app=True, keys="run echo command phrase do it shortcut")
def run_echo_command(phrase: str, ctx=None) -> str:
    """Run one of Echo's built-in commands by its phrase (e.g. 'snap this window left', 'open bluetooth settings', 'new tab')."""
    runner = getattr(ctx, "run_command", None)
    if runner is None:
        raise ToolError("this needs the Echo app running")
    return runner(phrase)


@tool(C, keys="press keys keyboard shortcut hotkey ctrl alt")
def press_keys(keys: str, times: int = 1, ctx=None) -> str:
    """Press a key or shortcut in the app you were using: 'ctrl+s', 'alt+tab', 'enter', 'ctrl+k ctrl+w' (a sequence)."""
    from .. import typer
    try:
        typer.key_sequence(keys)
    except ValueError as e:
        raise ToolError(f"bad keys: {e}")
    _focus(ctx)
    typer.press(keys, max(1, min(times, 50)))
    return f"Pressed {keys}" + (f" ×{times}" if times > 1 else "") + "."


@tool(C, keys="type write text keyboard enter into app")
def type_text(text: str, ctx=None) -> str:
    """Type text into the app you were using (long text is pasted, then your clipboard is put back)."""
    from .. import typer
    _focus(ctx)
    previous = typer.get_clipboard_text()
    if typer.plan(text) == "paste":
        typer.paste(text)
        if previous is not None:
            import time
            time.sleep(0.3)
            typer.set_clipboard_text(previous)
    else:
        typer.send_keys(text)
    return f"Typed {many(len(text), 'character')}."


@tool(C, keys="mouse click left right double")
def mouse_click(button: Literal["left", "right", "middle", "double", "triple"] = "left", x_percent: float = -1, y_percent: float = -1) -> str:
    """Click the mouse (optionally first moving to a spot given as percent across/down the screen)."""
    from .. import pcctl
    if x_percent >= 0 and y_percent >= 0:
        pcctl.mouse("at", {"n": str(x_percent), "n2": str(y_percent)}, {})
    op = {"left": "click", "right": "right_click", "middle": "middle_click", "double": "double_click", "triple": "triple_click"}[button]
    return pcctl.mouse(op, {}, {})[1]


@tool(C, keys="mouse move pointer cursor position")
def move_mouse(x_percent: float, y_percent: float) -> str:
    """Move the pointer to a spot (percent across and down the screen)."""
    from .. import pcctl
    return pcctl.mouse("at", {"n": str(x_percent), "n2": str(y_percent)}, {})[1]


@tool(C, keys="scroll page up down left right wheel")
def scroll(direction: Literal["up", "down", "left", "right"], amount: int = 3) -> str:
    """Scroll in the window under the pointer."""
    from .. import pcctl
    return pcctl.mouse("scroll_" + direction, {"n": str(max(1, min(amount, 50)))}, {})[1]


WINDOW_OPS = ["maximize", "minimize", "restore", "close", "snap_left", "snap_right", "snap_top_left", "snap_top_right", "snap_bottom_left",
              "snap_bottom_right", "top_half", "bottom_half", "center", "bigger", "smaller", "on_top", "not_on_top", "transparent", "opaque",
              "minimize_others"]


@tool(C, keys="window maximize minimize snap close move resize arrange")
def window_action(action: Literal["maximize", "minimize", "restore", "close", "snap_left", "snap_right", "snap_top_left", "snap_top_right",
                                  "snap_bottom_left", "snap_bottom_right", "top_half", "bottom_half", "center", "bigger", "smaller",
                                  "on_top", "not_on_top", "transparent", "opaque", "minimize_others"], ctx=None) -> str:
    """Do something with the window you were using: maximize, snap left/right/corners, close, keep on top…"""
    from .. import pcctl
    _focus(ctx)
    return pcctl.window(action)[1]


def _find_window(name: str):
    from .. import catalog, pcctl
    n = name.strip().lower()
    key = next((k for k, (exes, label) in catalog.APPS.items() if n in (k, label.lower()) or n.replace(" ", "") == k), None)
    wins = pcctl.top_windows()
    if key:
        exes = catalog.APPS[key][0]
        hit = [w for w in wins if w[2] in exes]
        if hit:
            return hit[0]
    return next((w for w in wins if n in w[1].lower() or n in w[2].lower()), None)


@tool(C, keys="switch to app window bring front focus")
def switch_to_window(name: str) -> str:
    """Bring an open app or window to the front by app name or title words."""
    from .. import typer
    w = _find_window(name)
    if not w:
        raise ToolError(f"no open window matches {name}; use open_app to start it")
    typer.bring_to_front(w[0])
    return f"Switched to {w[1]}."


@tool(C, ask=True, keys="close quit exit app program window")
def close_window(name: str, ctx=None) -> str:
    """Close an app's window politely (it can still ask to save). Asks first."""
    from .. import pcctl
    from .t_files import confirm
    w = _find_window(name)
    if not w:
        raise ToolError(f"no open window matches {name}")
    confirm(ctx, "Close a window?", w[1])
    pcctl.u32.PostMessageW(w[0], 0x0010, 0, 0)
    return f"Asked {w[1]} to close."


@tool(C, keys="open start launch app program")
def open_app(name: str) -> str:
    """Start an app from the Start menu by name (Chrome, Word, Spotify, Calculator…)."""
    from .. import control
    ok, msg = control.open_app(name)
    if not ok:
        raise ToolError(msg)
    return msg


@tool(C, keys="open website link url browser go to")
def open_website(url: str) -> str:
    """Open a web page in the browser."""
    from .. import control, internet
    u = internet.clean_url(url)
    control.open_url(u)
    return f"Opened {u}."


@tool(C, keys="google search youtube search browser look up open results")
def open_search(query: str, site: Literal["google", "youtube", "images", "maps", "news", "amazon", "flipkart", "wikipedia", "github", "stackoverflow"] = "google") -> str:
    """Open search results for something on Google, YouTube, Maps, Amazon, Wikipedia, GitHub…"""
    from .. import control
    q = urllib.parse.quote_plus(query)
    url = {"google": f"https://www.google.com/search?q={q}", "youtube": f"https://www.youtube.com/results?search_query={q}",
           "images": f"https://www.google.com/search?tbm=isch&q={q}", "maps": f"https://www.google.com/maps/search/?api=1&query={q}",
           "news": f"https://news.google.com/search?q={q}", "amazon": f"https://www.amazon.in/s?k={q}", "flipkart": f"https://www.flipkart.com/search?q={q}",
           "wikipedia": f"https://en.wikipedia.org/w/index.php?search={q}", "github": f"https://github.com/search?q={q}",
           "stackoverflow": f"https://stackoverflow.com/search?q={q}"}[site]
    control.open_url(url)
    return f"Opened {site} results for {query}."


@tool(C, keys="directions route navigate map travel how to get")
def open_directions(destination: str, origin: str = "", mode: Literal["driving", "walking", "bicycling", "transit", "two-wheeler"] = "driving") -> str:
    """Open Google Maps directions to a place."""
    from .. import control
    p = {"api": "1", "destination": destination, "travelmode": "driving" if mode == "two-wheeler" else mode}
    if origin:
        p["origin"] = origin
    control.open_url("https://www.google.com/maps/dir/?" + urllib.parse.urlencode(p))
    return f"Opened directions to {destination}."


@tool(C, keys="email compose write mail draft send")
def compose_email(to: str = "", subject: str = "", body: str = "") -> str:
    """Open a new email in your mail app, filled in (you press Send yourself)."""
    q = urllib.parse.urlencode({k: v for k, v in (("subject", subject), ("body", body)) if v}, quote_via=urllib.parse.quote)
    os.startfile(f"mailto:{urllib.parse.quote(to, safe='@,')}" + (f"?{q}" if q else ""))
    return "Opened a new email. Check it and press Send."


@tool(C, keys="gmail compose email browser draft")
def compose_gmail(to: str = "", subject: str = "", body: str = "") -> str:
    """Open a Gmail compose window in the browser, filled in (you press Send)."""
    from .. import control
    control.open_url("https://mail.google.com/mail/?" + urllib.parse.urlencode({"view": "cm", "fs": "1", "to": to, "su": subject, "body": body}))
    return "Opened Gmail compose. Check it and press Send."


@tool(C, keys="whatsapp message send share text chat")
def whatsapp_message(text: str, phone: str = "") -> str:
    """Open WhatsApp with a message ready (to a number with country code, or pick the chat yourself). You press Send."""
    from .. import control
    num = re.sub(r"\D", "", phone)
    if num and len(num) == 10:
        num = "91" + num
    control.open_url(f"https://wa.me/{num}?text=" + urllib.parse.quote(text))
    if not num:          # no number: WhatsApp asks which chat, so "just press Send" would be untrue
        return "Opened WhatsApp with the message. No number was given, so pick the chat to send it to, then press Send."
    return "Opened WhatsApp with the message to that number. Press Send when ready."


@tool(C, keys="calendar event add schedule meeting google calendar")
def google_calendar_event(title: str, start: str, duration_minutes: int = 60, details: str = "", location: str = "") -> str:
    """Open Google Calendar with a new event filled in (you press Save). start like '2026-11-05 15:30'."""
    from datetime import datetime, timedelta
    from .. import control
    from .t_time import parse_date, parse_time
    d, _, t = start.strip().partition(" ")
    s = datetime.combine(parse_date(d), parse_time(t or "09:00"))
    e = s + timedelta(minutes=duration_minutes)
    control.open_url("https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(
        {"action": "TEMPLATE", "text": title, "dates": f"{s:%Y%m%dT%H%M%S}/{e:%Y%m%dT%H%M%S}", "details": details, "location": location}))
    return "Opened Google Calendar with the event. Press Save."


CLIP_OPS = ["UPPER", "LOWER", "TITLE", "SENTENCE", "TRIM", "SORT_LINES", "REVERSE_LINES", "DEDUPE_LINES", "JOIN_LINES", "QUOTE", "BRACKETS",
            "BULLETS", "NUMBERED", "SLUG", "SNAKE", "CAMEL", "JSON_PRETTY", "JSON_MINIFY", "B64_ENC", "B64_DEC", "URL_ENC", "URL_DEC",
            "HTML_ESC", "HTML_UNESC", "STRIP_HTML", "KEBAB", "PASCAL", "CONSTANT", "SWAP_CASE", "SORT_NUMERIC", "REMOVE_EMPTY",
            "LINE_NUMBERS", "SQL_IN", "JSON_ARRAY", "CSV_TO_MD", "COMMENT_HASH", "COMMENT_SLASH", "UNCOMMENT", "INDENT", "DEDENT",
            "STRAIGHT_QUOTES", "REMOVE_ACCENTS", "WRAP_80"]


@tool(C, keys="selected text selection transform convert replace highlighted")
def transform_selection(operation: str, ctx=None) -> str:
    """Change the text selected in your app, in place: UPPER, LOWER, TITLE, SORT_LINES, JSON_PRETTY, B64_ENC, SNAKE, BULLETS, … (undo with Ctrl+Z)."""
    from .. import pcctl
    op = operation.strip().upper()
    if op not in CLIP_OPS:
        raise ToolError("operations: " + ", ".join(CLIP_OPS))
    _focus(ctx)
    return pcctl.clip(op)[1]


@tool(C, keys="selected text selection read get highlighted copy")
def get_selected_text(ctx=None) -> str:
    """The text selected in the app you were using (your clipboard is put back)."""
    from .. import pcctl, typer
    _focus(ctx)
    prev = typer.get_clipboard_text()
    try:
        t = pcctl._selection()
    finally:
        if prev is not None:
            typer.set_clipboard_text(prev)
    return t if t else "Nothing is selected."


@tool(C, keys="show desktop minimize all hide windows")
def show_desktop() -> str:
    """Show the desktop (press again to bring windows back)."""
    from .. import typer
    typer.press("win+d")
    return "Showing the desktop."


@tool(C, keys="virtual desktop new next previous switch workspace")
def virtual_desktop(action: Literal["new", "next", "previous", "close", "task_view"]) -> str:
    """Make, switch or close virtual desktops, or open Task View."""
    from .. import typer
    typer.press({"new": "win+ctrl+d", "next": "win+ctrl+right", "previous": "win+ctrl+left", "close": "win+ctrl+f4", "task_view": "win+tab"}[action])
    return f"Virtual desktop: {action.replace('_', ' ')}."


@tool(C, keys="emoji panel picker insert")
def emoji_panel() -> str:
    """Open the Windows emoji panel."""
    from .. import typer
    typer.press("win+period")
    return "Opened the emoji panel."


@tool(C, keys="clipboard history paste previous items")
def clipboard_history() -> str:
    """Open Windows clipboard history (Win+V)."""
    from .. import typer
    typer.press("win+v")
    return "Opened clipboard history."
