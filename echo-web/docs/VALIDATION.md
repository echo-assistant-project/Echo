# Validation record

Checked on November 5, 2026, using Python 3.12, Node 24 and installed Google Chrome on Windows.

| Check | Result |
| --- | --- |
| Existing local headless engine/routing/core tests | 25 passed from `desktop/EchoDesktop`. |
| New API/core/isolation tests | 18 passed from `echo-web`. |
| Browser integration | Passed against a fake HTTP model provider through the real API and shared engine. |
| Live model smoke test | Passed two streamed website turns with approved reference context and retained history. |
| Local synchronous conversation | Passed a real model request using the existing synchronous engine entry point. |
| Standalone ECHO wake grammar | Syntax and generated-audio recognition passed the existing confidence threshold. No microphone opened. |
| Existing packaged local apps | `EchoDesktop.pyz` and `Echo.apk` Git object hashes unchanged; Android source unchanged. |
| JavaScript syntax and patch whitespace | Passed. |
| Web dependency boundary | Fresh process verified no UI, Windows settings, speech, microphone or desktop orchestrator modules imported. |

The browser check covers incremental text before completion, follow-ups, reference titles, reset, upstream error
display and recovery, HTML-like text, Unicode, keyboard closing, mobile bounds, and absence of provider credentials
in browser requests. The API tests cover client/session isolation, exact origins, missing/wrong tokens, capability
gates, body constraints, concurrency, expiration, rate limits and failed/truncated-stream history rollback.

The tests do not establish production readiness, microphone hardware accuracy, full desktop GUI behavior after
the earlier stability issue, Safari/Firefox compatibility, model factual accuracy on real client material, or
multi-worker persistence. Production prerequisites are listed in HOSTING.md. No service was publicly deployed.

To check local wake grammar without opening a microphone:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/test_local_wake.ps1
```
