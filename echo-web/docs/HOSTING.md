# Hosting readiness

This change supplies a working integration adapter for local development and controlled hosted staging. It has
not been deployed. Python's bounded standard-library HTTP server is a development/staging transport. Production
requires an operational hosting review and a hardened HTTP server/ASGI adapter or equivalent managed ingress.

## Before hosted staging

- Provision a host and an OpenAI-compatible model endpoint reachable from that host. Confirm its model/route and quota.
- Store the provider key in the host's secret manager/environment. Keep `.env` local and out of Git.
- Set `ECHO_CLIENTS_FILE` to reviewed configuration. Use exact HTTPS staging origins and approved public content.
- Bind to the platform's internal interface/port using `ECHO_HOST` and `ECHO_PORT`. Terminate public TLS at the proxy.
- Preserve `/widget.js`, `/v1/...` and `/health` routes. Disable proxy response buffering for SSE and allow upstream
  requests to finish within the configured model and proxy timeouts. Disable compression if it delays streamed chunks.
- Keep model endpoint credentials and internal addresses out of frontend configuration. Test provider errors and key rotation.

## Before production

- Add customer/operator authentication and controlled visitor session issuance where required. Public site IDs and
  Origin headers do not authorize private knowledge. Keep all content public until that protection is implemented.
- Replace the in-memory session/rate stores for multiple workers or replicas. Define restart behavior, retention,
  visitor notice/consent, deletion and data-region requirements for the chosen model provider.
- Add distributed abuse controls, spend limits, provider concurrency quotas and verified reverse-proxy IP handling.
  The current in-process limits use the TCP peer address, so a proxy can make visitors share one limit.
- Add provider readiness probes separate from `/health`, redacted operational telemetry, alerting, support ownership,
  request correlation and recovery procedures. Decide whether the client needs service-level guarantees.
- Exercise slow readers, stalled providers, disconnects, partial streams, malformed headers, resource exhaustion,
  rolling restarts, traffic bursts and expected client load. SSE disconnect cancellation is best effort, bounded by
  upstream network timeouts; it is not a guarantee that provider billing stops instantly.
- Version/pin widget releases, configure cache invalidation, review dependencies, run a security/accessibility review,
  and establish a reviewed release/rollback process. The sample configuration and generic answers are not client sign-off.
- Review host Content Security Policy. Permit the API host in `script-src` and `connect-src`. If `style-src` needs
  a nonce, put the site's generated CSP nonce on the embed script; the widget copies it to its style element.

## Current limits

Default limits are four request workers, 100 in-memory sessions, 30 session/message requests per TCP peer per
minute, a 30-minute idle TTL, 4,000 input characters, 32,000 reply characters and eight retained exchanges.
Rate controls and session reset are implemented; end-user authentication, distributed persistence, automatic
provider retry and billing are not. No guarantee of production availability or compliance is made by passing local tests.
