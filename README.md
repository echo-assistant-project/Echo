# EchoPhone

EchoPhone has two distinct flows today: the launcher screen performs local phone actions (launch apps and open the dialer or messaging app for confirmation), while the separate orb preview contains the FreeLLMAPI chat client.

See docs/ARCHITECTURE.md, docs/FEATURE_AUDIT.md, and docs/TROUBLESHOOTING.md for the verified project state.

## Build

The project has no Gradle wrapper. The existing Windows setup script uses F: paths for the Android SDK, Gradle cache, temp files, and build output; it also changes persistent user environment variables and may install SDK/JDK packages. Review it before running. A direct Gradle build can use those paths via process-only environment variables.

## FreeLLMAPI connection

The installed FreeLLMAPI UI bundle documents an OpenAI-compatible Chat Completions API (/v1/chat/completions) using Authorization: Bearer <API key>. Echo expects the configured base URL to end in /v1 and sends model auto. The port/interface address must come from the running FreeLLMAPI settings. During the audit on this PC, the service listened only on loopback port 31415, so another device could not reach it over Wi-Fi. See docs/TROUBLESHOOTING.md.

## Local model

The app does not bundle or download a model. MediaPipe LLM Inference expects a compatible task-bundle model (typically .task); arbitrary GGUF or ordinary .bin files are not interchangeable. The model has not been imported or tested on the connected phone. Google currently marks MediaPipe LLM Inference as maintenance-only and recommends LiteRT-LM for new Android work.
