# Lessons from assistants that failed, and the agent skills worth taking

November 2026. This follows [PA_RESEARCH.md](PA_RESEARCH.md), which covered what makes assistants succeed, and
[JARVIS_PACK.md](JARVIS_PACK.md), which covered what the JARVIS-style builds have in common. This round asks the
opposite question: **where did the big assistants fail, and why?** Then it checks public agent skills on GitHub
and ClawHub, takes the safe and useful ones, and scraps the rest.

Most sources are news coverage, reviews and a few research papers. Where a number comes from a small or informal
test, the table says so.

## Where assistants failed, and what Echo does about it

| Assistant | What went wrong | Why it went wrong | What Echo does now |
|---|---|---|---|
| **Siri** (Apple Intelligence) | The "personal Siri" shown in 2024 slipped to 2026. Apple faces class actions over advertising it. | Craig Federighi said the first-generation design was too limited to meet Apple's quality bar. Acting across apps, with personal context and OS permissions, is much harder than chatting. | Echo doesn't promise what it can't do. Its commands are fixed and tested (run-everything harness), and the AI is only a fallback. **New: "what can I say here?"** shows the commands for the app in front of you. |
| **Alexa+** | In 2026 users said it was slower than the old Alexa, failed at smart-home control and gave inconsistent answers. Wired's month-long review called basic reliability "a serious problem". | An LLM was put in front of the basics, which then got slower and less predictable. | The basics never go through the AI. **New: when the AI can't be reached, Echo names the closest built-in commands** ("Did you mean “open notepad”?") instead of hitting a dead end. |
| **Google Assistant → Gemini** | When Assistant was replaced, routines started from alarms and shortcuts stopped working, smart lights dropped off and playlists failed. Google's Home lead said he'd heard the complaints "loud and clear". | The migration silently broke things people had set up. | **New: phrase health check.** When the Command Pack loads, Echo checks every phrase you taught it and warns you if a step no longer works. You can also say "check my phrases". |
| **Cortana** | It was on every Windows PC, yet few people spoke to it. Microsoft turned it off in stages and disabled it completely in 2026. | It was tied to Windows Phone, did no frequent job well, had little third-party support and an unclear strategy. | Echo is built around frequent jobs (the PA tools: tasks, plan my day, follow-ups) and makes its commands easy to discover (see above). |
| **Facebook M** | Shut down in 2018. | Never more than about 30% automated, so most tasks needed paid human staff. | Every Echo command is deterministic code. Nothing is promised that a person would have to finish behind the scenes. |
| **Humane AI Pin, Rabbit R1** | Covered in PA_RESEARCH.md: slow, few working integrations, brittle app automation. | — | Local-first, measured latency, confirmations. |
| **OpenAI Operator / ChatGPT agent** | A Washington Post columnist asked Operator to find cheap eggs, and it made an unauthorised $31.43 Instacart purchase. In small informal tests, ZDNet had 1 of 8 tasks succeed and MIT had 0 of 5. | Princeton's 2026 reliability paper found agents that looked capable on benchmarks were unreliable in real use, and accuracy scores can't tell a typo from a deleted file. | Purchases, sends and deletes already ask first. **New: action receipts.** Say "what did you just do?" to list Echo's recent actions, newest first, with who decided each one (you or the AI), whether it worked, and which tools were used. |
| **Microsoft Recall** | Researchers showed within days that its screenshot database, which included passwords, was trivial to extract. It became opt-in. | Security was added after the design instead of built in from the start. | Vault windows are already invisible to screenshots. **New: before screen text goes to an online AI, card numbers, ID numbers, OTPs and "password: …" values are masked**, and Echo says how many it hid. (Echo now always uses FreeLLMAPI, so the masking always applies.) |
| **OpenClaw / ClawHub** | Koi Security found 341 malicious skills out of 2,857 that stole keys and crypto wallets. Researchers found 506 prompt-injection posts on Moltbook, and a document that could plant a backdoor with no click needed. | Anyone with a GitHub account a week old could publish a skill. The agent read untrusted text while holding the user's data and a way to send it out. | **New: the "lethal trifecta" guard** in Echo's tool agent. When a task has read both your own data (files, notes, tasks, an MCP server) and outside text (a web page, an MCP result), every call that could carry data off the PC asks you first. That includes calls that are read-only and servers you marked trusted. Echo installs no third-party skills (see below). |
| **Memory assistants** (ChatGPT, Claude, Gemini memories) | PersistBench (2026) measured memory-induced sycophancy failure rates above 90% for most models. An ICLR 2026 paper found memory systems were 2–4 times more sycophantic than plain chat history. | Saving what a user *believes* makes the assistant agree with them. Old facts sit next to new ones. | **New:** the AI may not save your opinions or beliefs as memories. You still can, in your own words. A new fact replaces the old one ("I moved to Pune" replaces "I live in Hyderabad", and "my Wi-Fi name is X" replaces the old name). The AI can never overwrite something you told Echo yourself. The AI is also told that memories are not evidence and that it should be honest when you're mistaken. |
| **Friend pendant, Bee, Limitless** | Reviewers criticised always-on microphones, reported unreliable recall, and said people rarely went back to the content these devices captured. | Recording everything isn't the same as helping. | Echo doesn't record conversations. The second brain reads only the folders you name. |
| **Smart speakers in general** (research) | In one study, 9 of 15 Alexa users were stuck on basic functions. After a failure, users stop using that feature for a while. | Poor discoverability and misunderstood requests. | **New: "no, I meant …".** Say "no, I meant open Spotify" and Echo does that. Then it asks whether "*what you said before*" should mean that from now on. It saves the phrase only if you say yes. "unlearn that phrase" undoes it. |

## Agent skills on GitHub and ClawHub: taken or scrapped

**The rule.** Echo controls a PC, so no third-party skill code is installed, ever. This isn't hypothetical:
- Koi found 341 malicious ClawHub skills.
- Snyk's ToxicSkills scan found critical issues in 13.4% of 3,984 skills.
- "Agent Skills in the Wild" (arXiv 2601.10338) catalogued 8,126 vulnerable skills.
- Mondoo found a popular code-review skill with hidden instructions in HTML comments.

What Echo takes from a skill is the *idea*, re-written in Echo's own code and tests.

| Skill | What it does | Verdict |
|---|---|---|
| **self-improving-agent** (pskoett, one of the most-installed ClawHub skills), **reflect** (awesome-openclaw-skills), **claude-reflect** | Turns corrections into lasting learnings ("correct once, never again"). | **Taken:** the correction loop with a human approving each learning, as "no, I meant …". **Scrapped:** writing learnings into the agent's own instructions, and the AI generating new skills by itself. Those turn memories into instructions, which raises the risk of injection and sycophancy (see the memory row above). |
| **Anthropic `pdf` skill** (anthropics/skills) | Reads and makes PDFs with pypdf or pdfplumber. | **Taken, rewritten:** `pdftext.py` is a standard-library PDF reader (Echo ships no third-party packages, and nothing is downloaded). Now "learn my Documents folder" reads PDFs and cites the page ("lease.pdf (page 2)"), and the `read_document` tool reads PDFs too. |
| **Hermes agent `daily-brief` and `email-inbox-triage`** (NousResearch, MIT) | Morning brief and inbox triage over Gmail or Calendar. | **Principles already match:** message content is data, never instructions, and the default is to draft, not send or delete (Echo's email tools open a draft and you press Send). **Scrapped for now:** the skills need a Gmail or Calendar connection, which Echo doesn't have. Adding one means handing a mailbox token to a third-party CLI (gog, himalaya). |
| **Tavily search** (top ClawHub search skill) | Web search through Tavily's API. | **Scrapped:** it needs an API key and a third-party service, and Echo already has web search and page reading with an SSRF guard. |
| **gog** (Google Workspace CLI skill) | Gmail, Calendar and Drive through a downloaded binary. | **Scrapped:** an outside binary with broad OAuth scopes on the PA's PC. Website control over MCP already covers Gmail in your own browser. |
| **GitHub skill** | Repos, issues and PRs. | **Not needed:** Echo has GitHub tools (repo, issues, releases, README, search). |
| **ClawHub skills in general** | — | **Scrapped as a source of code.** Typosquatted names (the ClawHavoc campaign) mean even a familiar name isn't proof of safety. |

## What was added (EchoDesktop)

| Say / do | What happens | Code |
|---|---|---|
| "no, I meant open Spotify" (within 3 minutes) | Echo opens Spotify, then asks: “Next time you say ‘*what you said before*’, should I do ‘open Spotify’?” It learns the phrase only if you say yes. From Telegram it never learns, because nobody is at the PC to approve. | `lessons.correction`, `brain._run_correction` |
| "unlearn that phrase", "unlearn the phrase work mode" | Removes a taught phrase (asks first). | op `PHRASE_FORGET` |
| "check my phrases", "are my routines working" | Lists any taught phrase with a step Echo can't run any more. The same check runs when Echo starts. | `brain.broken_phrases` |
| "what did you just do", "what have you done today" | Action receipts: Echo's recent actions (not plain answers), with who decided, whether each worked, and the tools used. | `SessionLog.actions` |
| "what can I say here", "commands for this app" | Examples for the app in front of you (VS Code, Excel, Word, browsers, Gmail, Teams/Zoom, Spotify, the terminal…). | `lessons.app_groups` |
| An unrecognised request while the AI is unreachable | Names the closest built-in commands. | `lessons.suggest` |
| Remember facts | Newer facts replace older ones about the same thing. The AI can't save your opinions, and can't overwrite what you said yourself. | `storage.MemoryStore.remember`, `lessons.memory_slot` |
| "what's on my screen" with the online AI | Masks card numbers, ID numbers, OTPs and passwords first. | `lessons.redact_screen` |
| Tool tasks | The lethal-trifecta guard (see the OpenClaw row). | `tool_agent.reads_private / reads_untrusted / can_send_out` |
| PDFs | The second brain and `read_document` read PDFs, with no new packages. | `pdftext.py` |

Tests: `tests/test_lessons.py` (19 tests: hand-built PDFs, including compressed object streams, ToUnicode maps,
damaged files and a zip bomb; every rule; the voice phrases; the guard) and an updated `tests/test_mcp.py`. On 9 real
PDFs on this PC (including ones made by Chrome and ReportLab) the reader extracted text from every page in 0.1–2.4 s.

## Honest gaps

- **The phone app** has none of this yet. Everything here is PC-only.
- **Computer use** (the AI working the mouse) still sends the window's text to the AI unmasked, because masking
  numbers could break clicking on them. Screen questions are masked.
- **PDFs:** encrypted (password-protected) PDFs and scanned PDFs (pictures of text) are refused with a plain
  reason. OCR for scanned PDFs is a possible next step.
- **The guard asks more often** in long tasks that mix your files with web pages. That is deliberate.

## Sources

- Siri: [MacRumors — Apple explains the personalized Siri delay](https://www.macrumors.com/2025/06/10/apple-explains-personalized-siri-delay/), [AppleInsider — upgraded Siri is late](https://appleinsider.com/articles/26/02/16/apples-upgraded-siri-is-late-but-not-lost----the-real-story-is-timing)
- Alexa+: [TechRadar — is Alexa+ really bad?](https://www.techradar.com/ai-platforms-assistants/were-definitely-beta-testing-this-technology-is-alexa-really-bad-or-are-our-expectations-for-free-services-too-high), [aiproductivity.ai — Alexa+ stumbles in real-world testing](https://aiproductivity.ai/news/amazon-alexa-plus-stumbles-real-world-testing/)
- Gemini replacing Assistant: [Android Central — Google dialing back Assistant features](https://www.androidcentral.com/phones/google/google-is-dialing-back-more-assistant-features-on-android-and-nest-devices), [TechRadar — Gemini for Home bugs](https://www.techradar.com/home/smart-home/should-you-upgrade-to-gemini-for-home-tread-carefully-some-users-are-still-reporting-major-bugs-and-problems), [Droid Life — Pixel owners vent](https://www.droid-life.com/2026/10/03/pixel-owners-vent-over-forced-switch-from-google-assistant-to-gemini/)
- Cortana: [Windows Central](https://www.windowscentral.com/microsoft/the-failure-of-amazons-alexa-shows-microsoft-was-right-to-kill-cortana), [TechRadar — Microsoft admits it was late](https://www.techradar.com/news/microsoft-admits-it-was-late-to-the-virtual-assistant-game-with-cortana), [The Register](https://www.theregister.com/2018/01/10/reports_of_cortanas_death/)
- Facebook M: [Wikipedia](https://en.wikipedia.org/wiki/M_(virtual_assistant)), [Engadget](https://www.engadget.com/2018-01-08-facebook-m-ai-assistant-closure.html)
- Agents: [Towards a Science of AI Agent Reliability (Princeton)](https://arxiv.org/html/2602.16666), [Failure modes of OpenAI Operator](https://huggingface.co/blog/Zengyi-Qin/failure-modes-operator), [ZDNet test summary](https://www.webpronews.com/openais-chatgpt-agent-struggles-in-zdnet-tests-only-1-in-8-tasks-succeed-due-to-hallucinations-and-errors)
- Recall: [The Record — Recall becomes opt-in](https://therecord.media/microsoft-reverses-course-recall-opt-in), [SlashGear — where Microsoft went wrong](https://www.slashgear.com/1604034/windows-recall-where-microsoft-went-wrong-how-to-disable-it)
- OpenClaw / skills: [The Hacker News — 341 malicious ClawHub skills](https://thehackernews.com/2026/02/researchers-find-341-malicious-clawhub.html), [The Hacker News — VirusTotal scanning](https://thehackernews.com/2026/02/openclaw-integrates-virustotal-scanning.html), [Agent Skills in the Wild (arXiv 2601.10338)](https://arxiv.org/html/2601.10338), [Snyk ToxicSkills summary](https://dev.to/augusto_chirico/everyones-sharing-claude-code-skills-nobodys-checking-whats-inside-5h01), [Mondoo — agent skills, real power, real risk](https://mondoo.com/blog/agent-skills-real-power-real-risk), [Parallel — best ClawHub skills](https://parallel.ai/articles/best-clawhub-skills-for-openclaw.md)
- Memory: [PersistBench (arXiv 2602.01146)](https://arxiv.org/html/2602.01146), [Recalling Too Well — ICLR 2026](https://www.iclr.cc/virtual/2026/10016383)
- Wearables: [Tom's Guide — Friend](https://tomsguide.com/ai/friend-is-a-dollar99-ai-necklace-that-wants-to-help-you-remake-the-movie-her), [layer3labs — Bee review](https://www.layer3labs.io/gear/reviews/bee-ai-pendant)
- Discoverability: [Challenges and Opportunities for the Design of Smart Speakers (arXiv 2306.05741)](https://arxiv.org/pdf/2306.05741), [Voice assistant failures study (arXiv 2303.00164)](https://arxiv.org/abs/2303.00164v1)
- Skills read: [reflect](https://github.com/sundial-org/awesome-openclaw-skills/blob/b80cde2ef85241dd4fd54a1b934f5e22835f78ba/skills/reflect/SKILL.md), [claude-reflect](https://github.com/aiskillstore/marketplace/blob/10bd786da8600b0d6cdf147c304fabfd50070734/skills/bayramannakov/claude-reflect/SKILL.md), [pskoett/self-improving-agent](https://github.com/pskoett/self-improving-agent/blob/e958afb5bf697c7d22898f9bba53406e2e3261bd/self-improving-agent/SKILL.md), [Hermes daily brief](https://github.com/nousresearch/hermes-agent/blob/f0d94882e89ab8d4098b5bb2f166adfb9ee0a0ab/skills/productivity/google-workspace/references/daily-brief.md), [Hermes inbox triage](https://github.com/nousresearch/hermes-agent/blob/f0d94882e89ab8d4098b5bb2f166adfb9ee0a0ab/skills/email/email-inbox-triage/SKILL.md)
