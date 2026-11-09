# Run everything — every command and tool, executed

Run 2026-11-06 02:56 on this PC with `tools/RunEverything/run_all.py` (7.5 minutes; internet live). Sandbox: nothing on the PC changed — actions were intercepted and recorded, confirmations answered No, the AI was a local stand-in.

## Commands (PC): 3810

| Result | Count | Meaning |
|---|---:|---|
| worked | 3679 | ran and answered / did its action (recorded) |
| asked first | 15 | asked for confirmation first (we said No) — correct |
| handled | 115 | gave a clear answer that it couldn't (e.g. nothing selected, app not open, bad sample input) |
| network | 1 | a live internet source failed or was slow |

**3809 of 3810 (99.97%) behaved correctly**; problems: 1.

<details><summary>Every problem</summary>

| Item | Result | Said / args | Answer |
|---|---|---|---|
| mega.tool.wayback_snapshot | network | old version of python.org | That service is busy right now (too many requests). Try again in a minute. |

</details>

| Kind | OK | Problems |
|---|---:|---:|
| app_window | 198 | 0 |
| clip | 66 | 0 |
| content | 52 | 0 |
| dev | 34 | 0 |
| directions | 5 | 0 |
| echo | 88 | 0 |
| folder | 46 | 0 |
| keys | 942 | 0 |
| list | 17 | 0 |
| maps | 154 | 0 |
| mcp | 282 | 1 |
| mouse | 25 | 0 |
| ms_settings | 159 | 0 |
| net | 167 | 0 |
| open | 566 | 0 |
| power | 4 | 0 |
| say | 222 | 0 |
| selection | 32 | 0 |
| status | 14 | 0 |
| sys | 33 | 0 |
| text | 94 | 0 |
| tool | 70 | 0 |
| web | 432 | 0 |
| win_key | 21 | 0 |
| win_tool | 64 | 0 |
| window | 22 | 0 |

## Built-in tools: 607

| Result | Count | Meaning |
|---|---:|---|
| worked | 557 | ran and answered / did its action (recorded) |
| asked first | 5 | asked for confirmation first (we said No) — correct |
| handled | 45 | gave a clear answer that it couldn't (e.g. nothing selected, app not open, bad sample input) |

**607 of 607 (100.00%) behaved correctly**; problems: 0.

Phone: the phone commands can only be *routed* on this PC (JVM tests: every phrase reaches its command); running them needs the phone.
