# Website Bugs and Blockers

## P1 - Live site is a simulated preview

Evidence: the deployed script selects replies from local prewritten data, advances state using timers, and only uses
`speechSynthesis` when its local sound toggle is enabled. It does not call the ECHO backend.

Impact: a visitor cannot send a genuine model prompt, retain server-backed conversation context, or receive a real
provider response on the public URL.

Resolution: connect the actual live source to a hosted ECHO API after the source and hosting configuration are
available. Do not represent the preview as live AI functionality in the meantime.

## P1 - No public ECHO API exists at the deployed origin

Evidence: `GET /v1/sites/demo/config` on the Cloudflare URL returned HTTP 404 on 2026-11-06.

Impact: adding only a script setting cannot make the public page chat with ECHO.

Resolution: provision a backend host, configure exact allowed origins, and give the frontend its public API base URL.

## P1 - Deployed website source is unavailable in accessible GitHub repositories

Evidence: authenticated GitHub repository listing for the available account exposes only
`echo-assistant-project/Echo`. That repository has no Vite, Cloudflare Worker, or deployed website source.

Impact: modifying this repository cannot safely update the live page while preserving its UI.

Resolution: provide the website repository or Cloudflare project access, including deployment metadata. A compiled
asset is evidence of behavior, not an appropriate editable source of record.

## P2 - Current backend is local development infrastructure

Evidence: `echo-web/.env.example` binds to loopback and references a local OpenAI-compatible endpoint.

Impact: it is not reachable by public visitors and does not prove a production model provider.

Resolution: use a private hosted backend with HTTPS, server-side secrets, durable or intentionally stateless sessions,
distributed limits, monitoring, and approved staging tests.
