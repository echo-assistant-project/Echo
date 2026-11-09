"""Which websites Echo may control: every https site in the Command Pack (shared/commands/*.json) plus your extras.
Pure, unit-tested."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

from ..catalog import SHARED

COMMANDS_DIR = SHARED / "commands"
RISKY = re.compile(r"\b(send|buy|pay|purchase|order|checkout|check out|place order|delete|remove|trash|discard|post|"
                   r"publish|tweet|reply|submit|confirm|subscribe|unsubscribe|transfer|share|upload|sign out|log out|"
                   r"logout|deactivate|cancel (?:order|subscription|membership))\b", re.I)

# Sites Echo handles in code (e.g. "play X on YouTube") rather than through a catalog entry.
BUILT_IN = {"youtube": "https://www.youtube.com/", "google": "https://www.google.com/"}


def host_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _site_urls(command: dict):
    """(name, url) of a compact site row (N = name, U = url)."""
    if isinstance(command.get("U"), str) and isinstance(command.get("N"), str):
        yield command["N"], command["U"]


def load_sites(folder: Path = COMMANDS_DIR, extra: str = "") -> dict:
    """{spoken name (lower): url} for every https site in the shared command catalog, plus extra 'name=url;...'."""
    sites = dict(BUILT_IN)
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for c in data.get("commands", []) if isinstance(data, dict) else []:
            for name, url in _site_urls(c) if isinstance(c, dict) else ():
                if not (url.startswith("https://") and name.strip()):
                    continue
                if "{" in url:                                   # search template -> the site's home page
                    url = f"https://{urlparse(url).hostname}/"
                sites.setdefault(name.strip().lower(), url)
    for pair in (extra or "").split(";"):
        name, _, url = pair.partition("=")
        if name.strip() and url.strip().startswith("https://"):
            sites[name.strip().lower()] = url.strip()
    return sites


_SLD = {"co", "com", "org", "net", "gov", "ac", "edu"}


def base_domain(host: str) -> str:
    """mail.google.com -> google.com, www.amazon.co.in -> amazon.co.in."""
    labels = [l for l in host.lower().split(".") if l]
    if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in _SLD:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def allowed_hosts(sites: dict) -> set:
    return {base_domain(host_of(u)) for u in sites.values() if host_of(u)}


def is_allowed(url: str, hosts: set) -> bool:
    if urlparse(url).scheme != "https":
        return False
    h = host_of(url)
    return bool(h) and any(h == a or h.endswith("." + a) for a in hosts)


def resolve(target: str, sites: dict) -> str:
    """A site name ("YouTube") or a URL -> URL."""
    t = (target or "").strip()
    if t.lower() in sites:
        return sites[t.lower()]
    if re.match(r"^https?://", t, re.I):
        return t
    if re.match(r"^[\w-]+(\.[\w-]+)+(/.*)?$", t):
        return "https://" + t
    matches = sorted((n for n in sites if t.lower() in n or n in t.lower()), key=len)
    return sites[matches[0]] if t and matches else ""


def is_risky(label: str) -> bool:
    return bool(RISKY.search(label or ""))
