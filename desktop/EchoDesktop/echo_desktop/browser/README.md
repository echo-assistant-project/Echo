# Echo's built-in browser — Echo controls websites

Built into EchoDesktop (`echo_desktop/browser/`, standard library only). It drives the **Chrome or Edge already on
this PC** through the Chrome DevTools Protocol, in Echo's own window with a separate profile
(`%LOCALAPPDATA%\Echo\browser-profile`). No Playwright, no pip packages, no browser download.

```
You: "go to Gmail and read my latest email"
  └─ EchoDesktop  web_agent.py  ──▶  BrowserHub (in-process)  ──CDP──▶  Chrome / Edge
        AI picks a tool each step: open → read → click → read → done
  ◀─ "Your latest email is from Priya: the meeting moved to 4 pm."
Phone: same sentence → adb reverse 127.0.0.1:31419 → EchoDesktop bridge → same agent
```

## Turn it on

1. EchoDesktop → Settings → tick **Control websites for me (Echo browser)** and accept the notice.
2. Phone (optional): tick **Let my phone send website tasks**, copy the **Phone bridge key** into the phone app
   (Settings → PC website control), and run `adb reverse tcp:31419 tcp:31419`.

The first time, sign in to the sites you want (Gmail, Amazon…) yourself in the Echo browser window; it remembers.

## Say things like

- "go to Gmail and read my latest email"
- "on Amazon, find wireless earbuds under 2000"
- "open YouTube and subscribe to MKBHD" → Echo asks "Should I click “Subscribe”?" → "yes"
- "use the browser to check today's featured article on Wikipedia"
- Phone: "check my Gmail on my PC"

## Tools

| Tool | What it does |
|---|---|
| `browser_open` | Open a site by name ("YouTube") or an https URL on an allowed site |
| `browser_read` | Title, URL, visible text, and numbered elements `[ref]` to click/type |
| `browser_click` | Click `[ref]`; send/buy/delete/post-style buttons need the user's yes |
| `browser_type` | Type into `[ref]`, optional Enter |
| `browser_press` | Enter, Tab, Escape, arrows, Page Up/Down… (no Ctrl/Alt shortcuts) |
| `browser_scroll`, `browser_back` | Scroll, go back |

## Safety

- **Allow-list:** only https sites in `shared/commands/*.json` (+ YouTube, Google, and your "Extra websites" setting).
  Leaving the list sends the browser back.
- **Never types passwords** — you sign in yourself, once, in the Echo browser window.
- **Asks first** before clicks labelled send, buy, pay, order, delete, post, publish, submit, confirm, share, sign out…
  Inside Echo only your spoken "yes" approves them; over MCP a Yes/No box appears on the PC.
- The debugging connection is on 127.0.0.1 only and only for Echo's separate profile, never your everyday browser profile.
- Page text is passed to the AI marked as untrusted data, never as instructions.
- Only runs when you ask in your own words; the AI can't start a web task by itself.

## For other AI apps (MCP)

The same browser is an MCP server too: `<python 3.12>\python.exe desktop\EchoDesktop\echo_browser_mcp.py`
(e.g. `claude mcp add -s user echo-browser -- "<python.exe>" "<path>\echo_browser_mcp.py"`).

## More MCP servers

EchoDesktop can load extra MCP servers through `mcp_servers` in its settings file, e.g.
`{"name": "github", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"], "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "…"}}`.
Their tools appear to the web agent as `github.<tool>`, next to `browser.<tool>`.
