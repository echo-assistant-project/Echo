# Architecture

## Request flow

```text
Client website / widget.js
  → GET /v1/sites/{public-site-id}/config
  → POST /v1/sites/{public-site-id}/sessions
  ← random visitor session token
  → POST /v1/sites/{public-site-id}/messages + Bearer session token
  → core/engine.py selects this client's approved passages
  → existing echo_desktop.backend.Backend.stream
  → existing echo_desktop.llm.ChatClient.stream
  → operator-configured OpenAI-compatible provider
  ← SSE delta / done / error events
```

## Boundaries

| Area | Responsibility |
| --- | --- |
| `core/config.py` | Validate branding, exact origins, public site IDs, knowledge, enabled text capabilities. |
| `core/engine.py` | Adapt the shared engine and retrieve up to three matching approved passages for one client. |
| `backend/server.py` | HTTP, CORS, body limits, streamed responses, static widget asset, bounded request workers. |
| `backend/sessions.py` | Random session tokens, client/origin binding, expiration, bounded capacity and rate limiting. |
| `widget/` | Embedding, accessible text input, streamed display, reset, errors and responsive presentation. |
| `clients/` | Trusted operator-managed client configuration. No keys belong here. |
| `docs/` | Setup, migration, hosting gates and the repeatable onboarding process. |

## Reuse and state

The authoritative conversation engine remains in `desktop/EchoDesktop/echo_desktop/backend.py`.
The web adapter imports it directly from the same repository. It does not copy the engine or import `DesktopBrain`.
The shared engine now has an optional system prompt and a text-stream method alongside its unchanged synchronous
entry point. It maintains eight exchanges, rejects concurrent turns, and commits a streamed turn after successful
provider completion. A failed, empty, oversized, or abandoned stream leaves conversation history unchanged.

Each visitor gets a distinct engine/client/history. Session access verifies the public site ID, browser origin,
and random token together. Reset removes that session. Expired idle sessions are pruned when allocating capacity.
In-memory state is intentionally single-process and disappears on restart.

Approved knowledge is configured per client. Retrieval uses lexical overlap over that client's titles and text,
with at most three passages in a request. It has no shared search index, desktop file access, upload endpoint,
web crawler or embeddings. Passages are marked as reference data in the prompt. Returned reference titles show
the selected passages; they do not establish that every generated sentence is factually verified.

## Public IDs and access control

Public site IDs select configuration. They do not authenticate a customer, website operator or visitor.
Session tokens prevent one session being read or used as another client's session. Exact origin validation and
CORS constrain browser embedding. Non-browser callers can forge an Origin header, so these controls do not protect
private knowledge or establish visitor identity. Use approved public content only in this implementation.
Production customer authentication and stronger issuance controls remain explicit hosting gates.

Model credentials come only from the backend environment or its ignored `.env` file. They never appear in public
configuration, widget code, session tokens or API error messages. Browser tokens are held in memory and sent in
Authorization headers. The server does not log request bodies, headers, keys, or conversation text.

## API

| Method and path | Input | Result |
| --- | --- | --- |
| `GET /health` | None | Process liveness only. Does not claim provider readiness. |
| `GET /widget.js` | None | Standalone widget script. |
| `GET /demo` | None | Fictional local integration page. |
| `GET /v1/sites/{id}/config` | Approved Origin, or browser Referer for same-origin GET | Public branding and enabled capabilities. |
| `POST /v1/sites/{id}/sessions` | Approved Origin, JSON `{}` | Random `session_token`, `expires_in`. |
| `POST /v1/sites/{id}/messages` | Approved Origin, session Bearer token, JSON `{"message":"..."}` | SSE `delta`, then `done` with reference metadata, or `error`. |
| `DELETE /v1/sites/{id}/sessions/current` | Approved Origin, session token | Session removed, unless a turn is active. |

Requests accept text only, at most 4,000 characters and 16 KB of JSON. Replies are limited to 32,000 characters.
Extra request fields such as tools, prompts, paths and credentials are rejected. Busy sessions return 409.
Invalid/expired tokens return 401. Disallowed origins/capabilities return 403. Capacity and rate limits return
503 and 429 respectively. Streaming errors after headers use an SSE error event and keep private provider details
out of the browser. Worker slots limit HTTP concurrency, including requests waiting for the upstream model.
