# Website Roadmap

This directory contains ECHO's reusable website chat backend and widget. It is not the source of the currently live
Cloudflare page. The live page source must be recovered or supplied before its visual UI can be connected without
rebuilding it from compiled assets.

## Verified starting point

- The live URL serves a static React/Vite build.
- Its deployed JavaScript uses prewritten replies, timers, and browser-local speech synthesis.
- It makes no ECHO API request.
- The live origin returns 404 for `/v1/sites/demo/config`.
- This repository contains a tested Python SSE backend and embeddable widget under `echo-web/`.

## Dependency order

1. Obtain the Cloudflare project's source repository or export, and record its production branch, commit, build
   command, output directory, and environment variable names.
2. Add the real ECHO widget or adapt the existing visual UI to its API without changing the established design.
3. Deploy the backend to a server environment that supports Python streaming or replace it with a separately audited
   compatible service. A Cloudflare Worker cannot run the existing Python server unchanged.
4. Configure a real server-side model provider and run an owner-approved staging smoke test.
5. Verify text, context, reset, cancellation, retry, rate limiting, mobile layout, and two-visitor isolation on the
   staging origin.
6. Add real voice only after live text is working. Browser speech recognition needs a typed fallback and Android
   Chrome verification.
7. Obtain explicit production approval, deploy with a rollback identifier, and test the public URL.

## Out of scope until text staging succeeds

- Website actions or browser automation
- Desktop, filesystem, shell, and phone automation
- Shared personal memory
- Public exposure of laptop services or model credentials
