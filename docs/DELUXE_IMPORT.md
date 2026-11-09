# Deluxe source import

This branch imports the Windows source, shared assets, and speech helper source from the `Laptop version` folder of the supplied Deluxe archive. The existing package paths remain the canonical paths, so the updated modules replace their older counterparts in place.

| Item | Treatment |
| --- | --- |
| Desktop source and launch script | Use the Deluxe source under `desktop/EchoDesktop/`. Its built-in browser MCP replaces the older bundled Playwright-based browser integration for the current source tree. |
| Legacy `EchoDesktop.pyz` | Retired from the branch because desktop now runs from source. The old standalone launcher and its dependency files remain available at base commit `dee9b70`. |
| Android source and existing APK | Retained. Deluxe contains a different compiled APK without matching Android source. That binary was not imported or installed. |
| Website API and widget, headless backend, sync script, and Android CI | Retained because the archive has no equivalent implementations. |
| Shared commands and personas, Kokoro, Whisper, and skills | Imported at their standard paths. Third-party attribution and license files accompany the source. |
| Installer, bundled APK, PDF and machine-specific quick-start page | Left in the original archive. Use the repository README for the source checkout. |

The shared model client keeps the existing response size and time limits and rejects incomplete SSE streams. The Deluxe preferred-model routing remains available. The Windows wake grammar keeps the standalone “Echo” phrase alongside the greeting phrases. The persona test now checks the Deluxe Kokoro field and its validated fallback.

## Verification

- All 25 desktop tests and all 18 web tests passed. Desktop UI, brain, and browser MCP modules imported without starting the app.
- Parsed 106 Python sources and 26 JSON files. PowerShell syntax checks passed. A bounded text scan found no matching credential, private key, or literal private-network URL patterns.
- The import used a fresh checkout. The source archive, installed application, and earlier working branches remain available independently. The desktop GUI, audio hardware, and Android installation were outside this verification.
