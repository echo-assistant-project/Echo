# ECHO Website and Backend Audit

Audit date: 2026-11-06

## Repository discovery

The audited checkout is `C:\Users\Kaashi\.codex\visualizations\2026\11\04\01a1a7e0-d974-7ff3-88a4-878a17248bbf\backend-git`.
Its `origin` is `https://github.com/echo-assistant-project/Echo.git`. The remote default branch is `main` at
`e094251`, the merge commit for PR #2. This work is on `codex/website-backend-audit`, created from that commit. A
local safety branch, `backup/pre-audit-2026-11-06`, preserves the pre-audit commit.

`C:\Users\Kaashi\.codex\visualizations\2026\11\05\01a1ab5e-ef71-7313-8c93-84cd805d4fe0\productivity.repo`
is a separate Veritas application with remote `productivity-io/productivity.repo`. It was inspected only to identify
it and was not changed. The historical `F:\ECHO-Website`, `F:\Downloads\EchoPhone`, and `F:\Downloads\EchoDesktop`
paths do not exist on this machine.

ECHO's Android source is in `app/`, Windows source is in `desktop/EchoDesktop/`, and the web implementation is in
`echo-web/`. No separate production website source or deployment configuration exists in this checkout.

## Website integration

The working local path is:

`widget/demo.html` -> `widget/widget.js` -> `backend/server.py` -> `core/engine.py` ->
`desktop/EchoDesktop/echo_desktop/backend.py` -> OpenAI-compatible model provider.

The browser integration test exercised that whole path with a fake provider. It verified widget opening and closing,
streamed text, follow-up context, reset, error handling, keyboard submission, text-safe rendering, retry, and a 390
pixel mobile viewport. Python tests cover client site ID, origin, session, engine, and approved-reference isolation.

This does not prove a public deployment. The repository only has a local demo and no public URL, hosting setup, DNS
record, or deployed provider was found. The widget is integrated locally, not into a verified public website.

## Confirmed defects and repairs

| Severity | Defect | Root cause | Repair |
| --- | --- | --- | --- |
| P2 | No safe readiness probe | `/health` only reported a live Python process | Added `/ready`, which returns only `ready` or `unavailable` based on loaded client configuration. |
| P3 | Failed streamed turn had to be manually re-entered | The widget discarded the source text and had no retry state | Added in-place retry that reuses the existing bubbles. Incomplete shared-engine turns remain uncommitted. |

No cross-client leakage, session-token bypass, unsafe HTML rendering, provider-secret response leakage, unrestricted
tools, or unsupported-origin access was reproduced. Those are test results, not a guarantee about a future host.

## Verification

```powershell
Set-Location C:\Users\Kaashi\.codex\visualizations\2026\11\04\01a1a7e0-d974-7ff3-88a4-878a17248bbf\backend-git\echo-web
py -3.12 -m unittest discover -s tests -v
npm ci --ignore-scripts
npm run test:widget

Set-Location ..\desktop\EchoDesktop
py -3.12 -m unittest discover -s tests -v
```

Results on 2026-11-06:

- Web API, isolation, cancellation, configuration, readiness, and security tests: 19 passed.
- Browser test: passed through widget, API, shared engine, SSE provider fixture, retry, mobile layout, reset,
  context, and text-safe rendering.
- Existing desktop backend tests: 25 passed.
- `npm ci --ignore-scripts` reported no package vulnerabilities.

The provider was mocked. No live-model test ran because this audit did not use a configured provider credential or
authorization to consume one. Android hardware, Windows microphone, speaker, and wake-word behavior were not
launched because this was a backend and website audit.

## Security and production readiness

Verified controls include exact origin allowlists, per-site origin-bound random session tokens, in-memory session
expiry, one active request per conversation, input and body limits, bounded sessions and workers, per-IP limiting,
backend-only provider keys, generic provider-failure messages, cancelled-stream rollback, plain-text rendering, and
a web engine with no microphone, speaker, filesystem, shell, or desktop actions.

Approved reference passages are treated as data in the prompt, but still need human review before production because
language models cannot perfectly resist hostile or misleading content.

Required before public production:

1. Hosted HTTPS backend and static widget behind a reverse proxy with SSE buffering disabled.
2. Private client configuration store, secret management, credential rotation, and strict production origins.
3. Durable sessions or an explicit stateless-session design, retention and deletion policy, and authenticated admin provisioning.
4. Distributed rate limits, quotas, redacted structured logs, monitoring, alerting, backup, and incident runbooks.
5. Proxy, TLS, headers, dependency, abuse, accessibility, and real-device security testing.
6. Owner-approved staging smoke test with a real model provider.

Useful later work includes consented cross-device memory, optional voice, and a permissioned website-action interface.
For navigation, use a host-defined typed action registry such as `navigate`, `search`, and `open-record`. The host
must validate actions and require confirmation for state-changing, account, external, or financial actions. Arbitrary
JavaScript execution must remain out of scope.

## Remote development from Android

The default service binds to `127.0.0.1`, so the current demo cannot be reached from the phone. Do not expose it or a
remote-desktop port directly to the internet. Use an already-approved authenticated remote-desktop or private-network
tool. For a phone preview later, use a private-network HTTPS reverse proxy and configure its exact preview origin in
the relevant client JSON. Keep model credentials only on the laptop or hosted backend.

No remote-access software was installed or configured during this audit.

## Startup instructions

```powershell
Set-Location C:\Users\Kaashi\.codex\visualizations\2026\11\04\01a1a7e0-d974-7ff3-88a4-878a17248bbf\backend-git\echo-web
Copy-Item .env.example .env
# Edit .env locally. Keep ECHO_HOST=127.0.0.1 for this local demo.
py -3.12 backend/server.py
```

Open `http://127.0.0.1:8765/demo` on the laptop. Use `Ctrl+C` to stop it. The readiness probe is
`http://127.0.0.1:8765/ready`.

## Git status

No deployment or merge was performed. The verified audit branch is `codex/website-backend-audit`; commit
`560b6d3469283990d520607a014fee6760098a69` was pushed to its matching GitHub branch. The working tree was clean
after the push. No `.env`, local data, API keys, logs, binaries, or device-specific files were committed.
