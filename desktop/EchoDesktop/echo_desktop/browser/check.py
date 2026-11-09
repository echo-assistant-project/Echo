"""Check a page Echo built, the way a person would see it: load it in an invisible browser (throwaway profile) and
report what's on it and any script errors. Used by the coding agent after it previews a website, so it can fix a
broken page before saying it's done. Only pages served on this PC (127.0.0.1)."""
from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

from .cdp import CdpError, Chrome, find_browser

SUMMARY_JS = r"""
(() => {
  const visible = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el);
                          return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const count = sel => [...document.querySelectorAll(sel)].filter(visible).length;
  return {title: document.title, text: (document.body ? document.body.innerText : '').trim().length,
          inputs: count('input:not([type=hidden]),textarea,select,[contenteditable=true]'),
          buttons: count('button,[role=button],input[type=button],input[type=submit]'),
          links: count('a[href]'), images: count('img'),
          wide: document.documentElement.scrollWidth > innerWidth + 2};
})()
"""


def _errors(events) -> list:
    out = []
    for method, p in events:
        if method == "Runtime.exceptionThrown":
            d = p.get("exceptionDetails") or {}
            out.append(((d.get("exception") or {}).get("description") or d.get("text") or "script error").splitlines()[0])
        elif method == "Runtime.consoleAPICalled" and p.get("type") == "error":
            out.append("console.error: " + " ".join(str(a.get("value", a.get("description", ""))) for a in p.get("args", []))[:160])
        elif method == "Log.entryAdded" and (p.get("entry") or {}).get("level") == "error":
            e = p["entry"]
            out.append(f"{e.get('text', '')[:140]} ({e.get('url', '')[-60:]})")
    return list(dict.fromkeys(out))[:6]


def page_report(url: str, width: int = 1280, timeout: float = 20) -> str:
    """'Checked in a browser: …' or '' when no Chrome/Edge is installed. Never raises."""
    if urlparse(url).hostname != "127.0.0.1" or not find_browser():
        return ""
    profile = Path(tempfile.mkdtemp(prefix="echo-page-check-"))
    chrome = Chrome(profile, headless=True)
    try:
        s = chrome.page()
        for domain in ("Runtime.enable", "Log.enable", "Page.enable"):
            s.call(domain)
        s.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        s.call("Page.navigate", {"url": url})
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            r = s.call("Runtime.evaluate", {"expression": "document.readyState", "returnByValue": True})
            if (r.get("result") or {}).get("value") == "complete":
                break
            time.sleep(0.2)
        time.sleep(1.0)                              # let the page's scripts run
        info = (s.call("Runtime.evaluate", {"expression": SUMMARY_JS, "returnByValue": True}).get("result") or {}).get("value") or {}
        errors = _errors(list(s.events))
        s.close()
        parts = [f"title “{info.get('title') or '(none)'}”", f"{info.get('inputs', 0)} text boxes/fields",
                 f"{info.get('buttons', 0)} buttons", f"{info.get('links', 0)} links", f"{info.get('images', 0)} images"]
        report = "Checked in a browser: " + ", ".join(parts) + "."
        if not info.get("text"):
            report += " The page shows no text at all."
        if info.get("wide"):
            report += " It scrolls sideways at 1280 px wide."
        report += (" SCRIPT ERRORS: " + " | ".join(errors) + ". Fix them.") if errors else " No script errors."
        return report
    except (CdpError, OSError, ValueError) as e:
        return f"(Couldn't check the page in a browser: {e})"
    finally:
        chrome.close()
        shutil.rmtree(profile, ignore_errors=True)
