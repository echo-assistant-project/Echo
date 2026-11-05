# Standard client integration checklist

Use a separate completed copy of this checklist for each client and retain the approved configuration revision.

## 1. Configuration and approval

- [ ] Record the business owner, technical contact, support contact, staging URL and production URL.
- [ ] Assign a unique public `site_id`. Record that it is configuration, not an authentication credential.
- [ ] Approve assistant name, greeting, accent color, supported language, scope and escalation/contact wording.
- [ ] Obtain approved public FAQs, hours, policies, prices and contact details. Remove private information and secrets.
- [ ] Assign unique passage IDs and titles. Confirm what the assistant must say when the answer is unavailable.
- [ ] Configure exact staging/production origins, including scheme and any nonstandard port. Review subdomains separately.
- [ ] Enable only reviewed capabilities. This version supports `chat` only. Reject unsupported capability names.
- [ ] Configure model service, key, quotas and timeouts on the backend. Assign key rotation and payment ownership.
- [ ] Approve provider data handling, visitor notice, retention expectations and any authentication requirements.

## 2. Staging installation

- [ ] Complete the hosted-staging steps in HOSTING.md. Record backend and widget versions/commit IDs.
- [ ] Install the embed script on the client's staging website using its public site ID and HTTPS API host.
- [ ] Review CSP `script-src`, `connect-src` and style nonce requirements. Check for mixed-content or CORS failures.
- [ ] Verify the widget greeting, branding, placement and compatibility with the site's existing styles and navigation.
- [ ] Verify session creation, streamed chunks, follow-up context, New chat and expiry behavior.

## 3. Acceptance testing

- [ ] Test agreed business questions against approved source material, including ambiguous and unknown questions.
- [ ] Test follow-ups, long/Unicode messages, keyboard use, screen-reader labels, phone widths and supported browsers.
- [ ] Test text resembling HTML/scripts and embedded instructions in knowledge. Confirm plain-text display and no device actions.
- [ ] Verify one visitor's session and one client's knowledge never appear in another session/client's context.
- [ ] Verify unknown origins, wrong-site tokens, missing tokens, disabled chat, oversized requests and busy sessions are rejected.
- [ ] Test invalid provider keys, quotas, lost connections, partial streams and recovery without accidental automatic duplicate sends.
- [ ] Confirm no provider key is present in page source, assets, browser network traffic or API errors.
- [ ] Complete all production hosting gates applicable to the release. Record client acceptance and unresolved limitations.

## 4. Launch

- [ ] Obtain explicit launch approval. Record the approved config, widget and backend revisions.
- [ ] Add the exact production origin. Confirm production model connectivity and quotas.
- [ ] Install the reviewed script on production. Perform the agreed smoke tests and monitor error/latency rates.
- [ ] Confirm escalation/support ownership and the person authorized to disable the integration.

## 5. Rollback

- [ ] Keep the previous working script/config revision and backup instructions available before launch.
- [ ] To disable immediately, remove the embed script or set the affected client's enabled capabilities to `[]` and
  restart the backend after draining requests. Existing in-flight replies may finish; further chat requests are rejected.
- [ ] Restore the previous tested backend/widget/config versions if a prior integration exists. Clear caches where needed.
- [ ] Record that an in-memory backend restart clears sessions for every client in that process.
- [ ] Verify the client's website still works with the widget removed. Record the incident, owner and reactivation criteria.
