# ECHO website integration

An embeddable text-chat widget, a Python API, and an adapter to the repository's existing ECHO conversation engine.

## Run locally

Use Python 3.12. The backend has no third-party runtime dependencies. From the repository root on Windows:

```powershell
Set-Location echo-web
Copy-Item .env.example .env
# Edit .env locally. Replace the API key placeholder and confirm your provider URL/model.
py -3.12 backend/server.py
```

On Linux/macOS, use `cp .env.example .env` and `python3 backend/server.py` from `echo-web`.
Process environment variables take precedence over `.env`. The loader reads assignments as data and does not execute shell expressions.

Open `http://127.0.0.1:8765/demo`. Ask about opening hours, then ask a follow-up. The sample business is fictional.
The default provider configuration uses an already-running FreeLLMAPI service. For hosted staging, configure an
OpenAI-compatible `/v1` service reachable from that host and a model/route it supports. A client website cannot
reach a developer laptop's loopback address. This web service never starts that service or any desktop app.

## Embed

After provisioning a client and a staging API host, add this near the end of the client's HTML body:

```html
<script
  src="https://chat.example.net/widget.js"
  data-site="client-example"
  data-api="https://chat.example.net"
  defer>
</script>
```

`data-site` is a public configuration identifier. It is not a password or API credential. Create a matching client
entry with exact allowed origins. The example JSON shows branding, domains, chat enablement, and approved public
knowledge passages. Keep actual configuration in `clients/private/` or in a separately managed backend file.

The widget uses Shadow DOM, plain text rendering, and in-memory session tokens. It has no build step, external fonts,
browser storage, microphone access, speech output, or device automation. A page reload starts a new visitor session.

## Checks

```powershell
py -3.12 -m unittest discover -s tests -v
npm ci --ignore-scripts
npm run test:widget
```

The optional browser check uses an installed Chrome/Chromium/Edge and a fake model provider through the real API
and shared engine. Set `ECHO_BROWSER` to the browser executable and `ECHO_PYTHON` to Python if discovery needs help.
Node and Playwright are development dependencies only. Screenshots in `artifacts/` are ignored.

Run the existing local engine regression tests separately:

```powershell
Set-Location ../desktop/EchoDesktop
py -3.12 -m unittest discover -s tests
```

See [architecture](docs/ARCHITECTURE.md), [migration status and source audit](docs/MIGRATION.md),
[hosting requirements](docs/HOSTING.md), and [client onboarding](docs/CLIENT_ONBOARDING.md).
