# Security and privacy

## Credentials and repository contents

- The repository is intended to remain private at echo-assistant-project/Echo. The previous setup session verified private visibility and the founder account; the connected GitHub app in this session did not return repository details, so visibility could not be independently rechecked here.
- A bounded pattern scan of tracked working-tree text found no matches for common hard-coded API keys, long bearer strings, or private-key headers. This is not a complete secret audit and does not prove remote history or binary files are clean.
- Do not commit FreeLLMAPI keys, .echo-env.ps1, local.properties, Kokoro pairing files, API tokens, TLS private keys/certificates, Android signing keys, APKs, or model assets. .gitignore covers local configuration and generated/secret patterns used by this project.
- Each developer should receive separate, revocable backend credentials. Never share the founder's personal account or key.
- If a credential is exposed, revoke/rotate it at its provider, remove it from active use, and coordinate history cleanup before any rewrite. Never rewrite shared history without approval.

## AI and voice data

- FreeLLMAPI is external to this repository. Spoken transcripts and typed prompts sent to it are subject to that service's operation and privacy terms.
- The FreeLLMAPI key is stored in Android app SharedPreferences, not Android Keystore encryption in the current code. It is app-private data but should not be treated as hardware-backed secret storage. Do not reuse high-value credentials.
- The app manifest enables cleartext traffic because the default local FreeLLMAPI endpoint is HTTP over loopback/ADB reverse. Do not send API keys over untrusted networks or expose the service publicly; use secured HTTPS for remote network access.
- Kokoro runs on the Windows PC, binds to loopback port 31416, requires a bearer token, uses TLS, and the Android client pins the certificate fingerprint. The Kokoro token is stored through Android Keystore-backed AES/GCM; Windows key/pairing files are local and ACL-restricted by setup.
- ScreenAwarenessService is user-enabled accessibility access. It gathers visible text into device memory; the current chat flow does not transmit that text. No screenshot-capture or continuous screen-upload implementation is present.
- Android microphone, contacts, overlay, and accessibility capabilities require user/device authorization. Calls and messages are presented through system UI for user action.

## AI action boundaries

- PhoneActionRouter maps a small allow-list of phrases to Android intents. LLM output is not executed as shell, scripts, or arbitrary app instructions.
- Do not add silent calling/message sending or bypass Android permissions. Confirm sensitive actions in native Android UI.

## Local and automated build security

- Keep local.properties, ignored path templates, signing data, pairing files, model weights, build output, and Gradle/Python caches local.
- The current Android CI workflow needs no secrets and uses read-only repository permissions. It does not upload artifacts, publish releases, or deploy.
- Check workflow permissions and dependency/action versions before changing CI. Never echo credentials into workflow logs.
- Task Scheduler, firewall changes, public endpoints, and persistent services are not enabled by this project setup.