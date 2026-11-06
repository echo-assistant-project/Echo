# Website Progress

## 2026-11-06 - codex/cloudflare-website-audit

### Verified

- Live Cloudflare URL responds with a static React/Vite page.
- Live HTML points to `assets/index-CmcVfVHp.js` and `assets/index-CoI3_MuU.css`.
- The deployed JavaScript is a preview implementation, not an ECHO backend client.
- The deployed origin has no `echo-web` API route at `/v1/sites/demo/config`.
- `echo-web` retains a tested local path through its widget, Python SSE API, shared ECHO engine, and mocked provider.
- Existing results remain 19 Python web tests, one browser integration test, and 25 desktop backend tests passing in the
  prior audit branch.

### Changes in this branch

- Added source-backed roadmap, blocker list, and progress record for the website backend directory.

### Not verified

- Cloudflare project identifier, dashboard configuration, production branch, deployment commit, and build command.
- The source repository that produced the deployed static assets.
- Any real model provider, public backend, or Android Chrome live chat and voice path.

### Owner action required

1. Grant access to the Cloudflare project or provide the actual website repository/export.
2. Confirm an approved staging backend host and a real model provider that may be used for testing.
3. Approve production deployment only after staging evidence is reviewed.
