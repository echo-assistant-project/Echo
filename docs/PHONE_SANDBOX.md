# Phone sandbox — every phone command, executed on a simulated phone

`app/src/test/java/com/echo/assistant/PhoneSandboxTest.kt` runs Echo's real `EchoBrain` on a simulated Android 14 phone (Robolectric) with a typical set of apps installed (Chrome, Maps, Phone, Contacts, Messages, Gmail, Calendar, Clock, Camera, Photos, Files, Calculator, Play Store, Settings, WhatsApp, YouTube, Spotify, Paytm, Swiggy…) and strict checking on: opening something no installed app handles fails, as on a real phone. Each command is said the way a person would, routed by the real parser, executed, and checked for the effect its kind must have (the right web address, map search, settings screen, app, clock/camera/dialer screen, volume change) and for small wording mistakes.

Run it: `gradle testDebugUnitTest --tests com.echo.assistant.PhoneSandboxTest` (part of the normal test run).

**1727 of 1727 phone commands behaved correctly (100.00%).**

| Result | Count | Meaning |
|---|---:|---|
| worked | 1716 | did its action and answered correctly |
| asked first | 3 | asked for confirmation (the test said No) |
| handled | 8 | refused with a clear reason (system navigation needs Echo's accessibility switch on) |

| Kind | Commands |
|---|---:|
| open | 566 |
| web | 447 |
| say | 222 |
| maps | 154 |
| tool | 72 |
| content | 52 |
| settings | 52 |
| echo | 34 |
| status | 29 |
| intent | 20 |
| list | 18 |
| panel | 12 |
| volume_stream | 11 |
| global | 8 |
| clock | 7 |
| volume | 6 |
| directions | 5 |
| media | 4 |
| ringer | 3 |
| camera | 3 |
| music | 2 |

Not plain “worked” (all correct behaviour):

- `list.remove` — “remove milk from my shopping list” → Remove milk from your shopping list? Tap Remove to confirm.
- `list.clear` — “clear my shopping list” → Clear all 3 items from your shopping list? Tap Clear to confirm.
- `note.delete` — “delete my notes” → Delete your 1 note? Tap Delete to confirm.
- `nav.split` — “split screen” → System navigation needs “Echo screen awareness” turned on (Echo → Screen automation).
- `nav.power` — “show power menu” → System navigation needs “Echo screen awareness” turned on (Echo → Screen automation).
- `nav.close_shade` — “close notifications” → System navigation needs “Echo screen awareness” turned on (Echo → Screen automation).
- `nav.all_apps` — “show all apps” → System navigation needs “Echo screen awareness” turned on (Echo → Screen automation).
- `nav.scroll_down` — “scroll down” → System navigation needs “Echo screen awareness” turned on (Echo → Screen automation).
- `nav.scroll_up` — “scroll up” → System navigation needs “Echo screen awareness” turned on (Echo → Screen automation).
- `nav.scroll_left` — “scroll left” → System navigation needs “Echo screen awareness” turned on (Echo → Screen automation).
- `nav.scroll_right` — “scroll right” → System navigation needs “Echo screen awareness” turned on (Echo → Screen automation).

What the simulated phone can't show: real speech, the real screen-reading accessibility service, and how each manufacturer's apps respond. Those need the phone itself.
