# Skills — the .md how-tos Echo reads

A *skill* is a Markdown file (`SKILL.md`) that teaches an assistant how to do one kind of task well: debug a failing
test, check whether a message is a scam, plan a week of meals. Echo reads them all the time:

- **With the AI:** for each request, Echo picks the one skill that matches best (BM25 over names, descriptions and
  headings, with everyday synonyms like "tablets → medicine") and gives it to the AI as guidance, trimmed to about
  6,000 characters to save FreeLLMAPI tokens. Small talk and plain commands get no skill.
- **When FreeLLMAPI's tokens run out:** Echo recognises the out-of-tokens answer (HTTP 429/402, "quota", "rate
  limit", "credits"…). If a local AI (Ollama) is running, it takes over for 10 minutes. If not, Echo answers from the
  Markdown itself: the most relevant section of the matching skill, or your notes, in plain words. A conversation
  that's too long for the model is trimmed and retried once.
- **Your own:** any `.md` file in `%APPDATA%\EchoDesktop\skills` ("open my skills folder") is a skill too, picked
  up without restarting.

Say: “what skills do you have”, “list your developer skills”, “list your health skills”, “read the scam check skill”,
“open my skills folder”, “stop using your skills” / “use your skills”.

## Courses and tutor mode

47 **course skills** cover 13 fields (Technology, Office, Business, Real estate, Personal finance, Health, Law and
civic, Careers, Communication, Learning, Creative, Home and life, Agriculture). Each one was written for Echo from the
syllabi of the best free or widely used courses in that field (Harvard CS50, Michigan's Python for Everybody, MDN,
Google's certificates and crash courses, Andrew Ng's ML Specialization, Coursera/Wharton/Michigan/Yale courses, SEBI–
NISM, ICMR-NIN, WHO, Red Cross, RERA AP, IGRS AP, the Income Tax portal, NCERT, SWAYAM, ICAR…) and names them in its
`courses:` line.

Why written and not copied: most course material is copyrighted, and much "free" material (MIT OpenCourseWare, CS50,
Khan Academy) is licensed for non-commercial use only — unsuitable for an invested product. Facts, methods and
syllabi aren't copyrightable, so Echo's skills teach the same things in original words and send learners to the
courses themselves. Official Indian figures (tax slabs, helplines, portals) were checked against official or
well-sourced pages in November 2026; rules change, and each skill says where to confirm them.

- **“teach me Excel”** (or first aid, investing, Python, negotiation…): Echo turns the skill into a course and
  teaches one lesson at a time. With the AI, it explains each lesson simply, gives an example and asks a check
  question (using the `tutor-mode` skill's teaching method). Without the AI or out of tokens, Echo reads the lesson.
  “next lesson”, “repeat the lesson”, “stop the lesson”.
- **“which course should I take to learn Python”**: the courses behind that skill, with links.

## Safety

Echo controls a PC, so skills are treated as untrusted text:
- Only **Markdown** was taken from GitHub, never scripts. Skills that don't work without their scripts were left out.
- Every file passed an audit for hidden HTML comments, invisible characters, "download and run" commands, "ignore
  your rules", "don't tell the user", "send your keys" and "auto-approve" instructions, and long encoded blobs. Two
  reference files have HTML comments that were read by hand (code-example notes) and allowed.
- Echo runs the same audit on **every load**, including your own folder, and skips any file that fails.
- The AI is told a skill is guidance only: it grants nothing beyond Echo's own rules and confirmations.
- Only **MIT** and **Apache-2.0** skills were taken; each collection's licence is kept next to it
  (`shared/skills/<collection>/LICENSE.txt`), and every skill names its source repository and commit.

## Where they came from — and what was scrapped

| Source | Result |
|---|---|
| obra/superpowers, addyosmani/agent-skills, NousResearch/hermes-agent, anthropics/skills, alirezarezvani/claude-skills | 340 skills audited; 51 taken (below) |
| Skills that failed the audit (49 of 340) | Scrapped: hidden HTML comments, pipe-to-shell installs, wallet/key handling, "auto-approve", "ignore instructions" |
| Skills that need their own scripts, CLIs or paid services (Docker-only GPU clouds, Apple-only apps, Airtable, Shopify, 1Password CLI…) | Scrapped: they don't work on a Windows voice assistant, or need code Echo won't run |
| anthropics/skills docx, pdf, pptx, xlsx | Scrapped: proprietary licence (Echo has its own PDF and Office readers) |
| ComposioHQ/awesome-claude-skills (864 files) | Scrapped: no licence, and mostly wrappers for Composio's paid API |
| **MoltHub** (Moltbot's skill registry, the same ecosystem now called ClawHub) and Moltbook skill files | Scrapped as a source: 341 malicious skills were found there, and Moltbook's skill tells agents to fetch and follow remote files |
| Skills for older people and least-effort users | GitHub had almost none that were licensed and safe, so Echo has 12 of its own (scams, bills, medicines, doctor visits, video calls, payments, meals, decisions, chores, replies, trips) |


## All 110 skills

| Collection | Skills |
|---|---:|
| Echo's course skills (written for Echo from the syllabi of the courses each one names) | 47 |
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) (MIT) | 22 |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) (MIT) | 20 |
| Echo's own (written for Echo) | 12 |
| [obra/superpowers](https://github.com/obra/superpowers) (MIT) | 5 |
| [anthropics/skills](https://github.com/anthropics/skills) (Apache-2.0) | 3 |
| [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) (MIT) | 1 |

## Course skills by field

| Field | Skill | Built from |
|---|---|---|
| Agriculture | small-farm-basics | [ICAR and Krishi Vigyan Kendras (local training and advice)](https://icar.org.in/); Kisan Call Centre (1800-180-1551, free, local languages); [PM-KISAN portal](https://pmkisan.gov.in/); [Pradhan Mantri Fasal Bima Yojana (crop insurance)](https://pmfby.gov.in/) |
| Business | bookkeeping-gst | [Introduction to Financial Accounting (Wharton, University of Pennsylvania, Coursera)](https://www.coursera.org/learn/wharton-accounting); [GST tutorials (GSTN, official)](https://tutorial.gst.gov.in/); [CBIC GST portal](https://cbic-gst.gov.in/); [Khan Academy Accounting and Financial Statements](https://www.khanacademy.org/economics-finance-domain/core-finance/accounting-and-financial-stateme) |
| Business | customer-service | [HubSpot Academy Customer Service courses (free)](https://academy.hubspot.com/); [Customer Service Fundamentals (Coursera)](https://www.coursera.org/); [Google Business Profile Help: reviews](https://support.google.com/business/) |
| Business | digital-marketing | [Google Skillshop and Grow with Google (digital marketing courses)](https://skillshop.withgoogle.com/); [HubSpot Academy Inbound Marketing (free)](https://academy.hubspot.com/); [Meta Blueprint (Facebook/Instagram ads)](https://www.facebookblueprint.com/); [Google Search Central SEO Starter Guide](https://developers.google.com/search/docs/fundamentals/seo-starter-guide) |
| Business | negotiation | [Successful Negotiation: Essential Strategies and Skills (University of Michigan, Coursera)](https://www.coursera.org/learn/negotiation-skills); [Program on Negotiation (Harvard Law School) free reports](https://www.pon.harvard.edu/); Getting to Yes (Fisher, Ury, Patton) — the classic book behind most courses |
| Business | project-management | [Google Project Management Professional Certificate (Coursera)](https://www.coursera.org/professional-certificates/google-project-management); [PMI Kickoff (free, Project Management Institute)](https://www.pmi.org/); [Agile with Atlassian Jira (Coursera)](https://www.coursera.org/learn/agile-atlassian-jira) |
| Business | sales-basics | [HubSpot Academy Inbound Sales (free)](https://academy.hubspot.com/); [Successful Negotiation (University of Michigan, Coursera)](https://www.coursera.org/learn/negotiation-skills); [Sales Training: Practical Sales Techniques (HubSpot Academy)](https://academy.hubspot.com/courses) |
| Business | small-business-india | [Startup India Learning Program (free, Government of India)](https://www.startupindia.gov.in/); [Udyam Registration portal (MSME)](https://udyamregistration.gov.in/); [Entrepreneurship Specialization (Wharton, Coursera)](https://www.coursera.org/specializations/wharton-entrepreneurship); [SIDBI / Udyami Mitra resources](https://www.udyamimitra.in/) |
| Careers | interview-prep | [Google Interview Warmup (practice tool)](https://grow.google/certificates/interview-warmup/); [National Career Service (Government of India)](https://www.ncs.gov.in/); [Successful Negotiation (University of Michigan, Coursera) — for salary talks](https://www.coursera.org/learn/negotiation-skills) |
| Careers | resume-and-job-search | [Google Career Certificates and job search resources (Grow with Google)](https://grow.google/); [National Career Service (Government of India)](https://www.ncs.gov.in/); [LinkedIn Learning / LinkedIn Help: profile tips](https://www.linkedin.com/help/linkedin); [Coursera career resources](https://www.coursera.org/articles) |
| Communication | english-fluency | [British Council LearnEnglish (free)](https://learnenglish.britishcouncil.org/); [BBC Learning English](https://www.bbc.co.uk/learningenglish/); [Purdue OWL grammar resources](https://owl.purdue.edu/owl/general_writing/grammar/) |
| Communication | public-speaking | [Introduction to Public Speaking (University of Washington, Coursera)](https://www.coursera.org/learn/public-speaking); [Toastmasters International (Pathways, local clubs)](https://www.toastmasters.org/); [TED Masterclass / TED speaker resources](https://www.ted.com/participate/organize-a-local-tedx-event/tedx-organizer-guide/speakers-program) |
| Creative | graphic-design-basics | [Canva Design School (free)](https://www.canva.com/designschool/); [Graphic Design Specialization (CalArts, Coursera)](https://www.coursera.org/specializations/graphic-design); [Google Fonts knowledge (typography basics)](https://fonts.google.com/knowledge) |
| Creative | phone-photography | [Photography Basics and Beyond: From Smartphone to DSLR (Michigan State University, Coursera)](https://www.coursera.org/specializations/photography-basics); [Google Pixel / Samsung camera help guides](https://support.google.com/pixelcamera); [Snapseed (Google) help](https://support.google.com/snapseed) |
| Creative | video-editing | [DaVinci Resolve free training (Blackmagic Design)](https://www.blackmagicdesign.com/products/davinciresolve/training); [YouTube Creators (official creator lessons)](https://www.youtube.com/creators/); [Microsoft Clipchamp help](https://support.microsoft.com/clipchamp) |
| Health | better-sleep | [CDC Sleep and Sleep Disorders tips](https://www.cdc.gov/sleep/); [NHS Every Mind Matters — sleep](https://www.nhs.uk/every-mind-matters/mental-wellbeing-tips/how-to-fall-asleep-faster-and-sleep-better/); [Sleep Foundation guides](https://www.sleepfoundation.org/) |
| Health | first-aid | [Indian Red Cross Society first aid training](https://indianredcross.org/); [British Red Cross free first aid learning](https://www.redcross.org.uk/first-aid); [American Red Cross First Aid/CPR courses](https://www.redcross.org/take-a-class); [St John Ambulance first aid advice](https://www.sja.org.uk/get-advice/first-aid-advice/) |
| Health | fitness-beginners | [WHO Guidelines on Physical Activity and Sedentary Behaviour (2020)](https://www.who.int/publications/i/item/9789240015128); [NHS Couch to 5K and Fitness Studio](https://www.nhs.uk/live-well/exercise/); [Fit India Movement](https://fitindia.gov.in/) |
| Health | nutrition-indian-diet | [ICMR-NIN Dietary Guidelines for Indians (2024)](https://www.nin.res.in/dietaryguidelines/); [Stanford Introduction to Food and Health (Coursera)](https://www.coursera.org/learn/food-and-health); [FSSAI Eat Right India](https://eatrightindia.gov.in/); [WHO Healthy diet fact sheet](https://www.who.int/news-room/fact-sheets/detail/healthy-diet) |
| Health | stress-and-wellbeing | [The Science of Well-Being (Yale, Coursera)](https://www.coursera.org/learn/the-science-of-well-being); [WHO Doing What Matters in Times of Stress](https://www.who.int/publications/i/item/9789240003927); [Tele MANAS (Government of India, 24×7 free)](https://telemanas.mohfw.gov.in/) |
| Home and life | cooking-basics | [Stanford Introduction to Food and Health (Coursera)](https://www.coursera.org/learn/food-and-health); [FSSAI Eat Right India — safe food at home](https://eatrightindia.gov.in/); [WHO Five Keys to Safer Food](https://www.who.int/publications/i/item/9789241594639) |
| Home and life | kitchen-garden | [ICAR (Indian Council of Agricultural Research) and state agricultural universities' kitchen-garden guides](https://icar.org.in/); [Royal Horticultural Society (RHS) Grow Your Own advice](https://www.rhs.org.uk/vegetables); Kisan Call Centre (free farming advice, 1800-180-1551) |
| Law and civic | consumer-complaints-india | [National Consumer Helpline (1915)](https://consumerhelpline.gov.in/); [e-Daakhil (online consumer commission filing)](https://edaakhil.nic.in/); [Department of Consumer Affairs — Consumer Protection Act, 2019](https://consumeraffairs.nic.in/); [RBI Complaint Management System (banks)](https://cms.rbi.org.in/) |
| Law and civic | renting-a-home | [Model Tenancy Act, 2021 (Ministry of Housing and Urban Affairs)](https://mohua.gov.in/); [IGRS Andhra Pradesh (stamp duty and registration)](https://registration.ap.gov.in/); State police portals (tenant verification) |
| Law and civic | rti-application | [RTI Online (central government departments)](https://rtionline.gov.in/); [Right to Information Act, 2005 (official portal)](https://rti.gov.in/); [Central Information Commission](https://cic.gov.in/) |
| Learning | help-kids-homework | [Khan Academy and Khan Academy Kids](https://www.khanacademy.org/); [NCERT textbooks and e-Pathshala](https://ncert.nic.in/); [UNICEF Parenting](https://www.unicef.org/parenting) |
| Learning | study-and-exam-prep | [Learning How to Learn (Coursera)](https://www.coursera.org/learn/learning-how-to-learn); [NCERT textbooks (free, the base for most Indian exams)](https://ncert.nic.in/textbook.php); [SWAYAM and NPTEL (free courses)](https://swayam.gov.in/); [Khan Academy](https://www.khanacademy.org/) |
| Learning | tutor-mode | [Learning How to Learn (Barbara Oakley and Terrence Sejnowski, Coursera)](https://www.coursera.org/learn/learning-how-to-learn); [Khan Academy (mastery learning)](https://www.khanacademy.org/); [SWAYAM (Government of India free courses)](https://swayam.gov.in/) |
| Office | business-writing | [Business Writing (University of Colorado Boulder, Coursera)](https://www.coursera.org/learn/writing-business); [Purdue Online Writing Lab (OWL)](https://owl.purdue.edu/); [Plain Language Guidelines (US government)](https://www.plainlanguage.gov/guidelines/) |
| Office | excel-spreadsheets | [Excel Skills for Business Specialization (Macquarie University, Coursera)](https://www.coursera.org/specializations/excel); [Microsoft Excel video training](https://support.microsoft.com/excel); [GCFGlobal Excel tutorials (free)](https://edu.gcfglobal.org/en/excel/); [Google Sheets training (Google Workspace Learning Center)](https://support.google.com/a/users/answer/9282959) |
| Office | presentations | [Microsoft PowerPoint training](https://support.microsoft.com/powerpoint); [GCFGlobal PowerPoint tutorials (free)](https://edu.gcfglobal.org/en/powerpoint/); [Introduction to Public Speaking (University of Washington, Coursera)](https://www.coursera.org/learn/public-speaking) |
| Office | word-documents | [Microsoft Word training](https://support.microsoft.com/word); [GCFGlobal Word tutorials (free)](https://edu.gcfglobal.org/en/word/); [Google Docs training (Google Workspace Learning Center)](https://support.google.com/docs) |
| Personal finance | income-tax-india | [Income Tax Department e-filing portal (tutorials and calculators)](https://www.incometax.gov.in/); [Income Tax Department taxpayer services and FAQs](https://incometaxindia.gov.in/); [NISM / SEBI investor material (tax on investments)](https://investor.sebi.gov.in/) |
| Personal finance | insurance-basics | [IRDAI Policyholder education (Bima Bharosa, consumer handbooks)](https://policyholder.gov.in/); [IRDAI official site](https://irdai.gov.in/); [Khan Academy Insurance](https://www.khanacademy.org/college-careers-more/personal-finance) |
| Personal finance | investing-basics-india | [SEBI–NISM Investor Certification (free)](https://www.nism.ac.in/sebi-investor-certification-examination/); [SEBI Investor website (free study material)](https://investor.sebi.gov.in/); [NISM Investor Awareness Program](https://www.nism.ac.in/investor-education/investor-awareness-program); [AMFI Mutual Funds Sahi Hai (investor education)](https://www.mutualfundssahihai.com/) |
| Personal finance | personal-budgeting | [RBI Financial Education (Money Kumar booklets and guides)](https://www.rbi.org.in/FinancialEducation/); [National Centre for Financial Education (NCFE)](https://www.ncfe.org.in/); [Khan Academy Personal Finance](https://www.khanacademy.org/college-careers-more/personal-finance) |
| Real estate | property-buying-due-diligence | [RERA Andhra Pradesh (project and agent registration search)](https://rera.ap.gov.in/); [IGRS Andhra Pradesh — encumbrance certificate, market value, registration](https://registration.ap.gov.in/); [Meebhoomi (AP land records: 1-B, Adangal, maps)](https://meebhoomi.ap.gov.in/); [Real Estate (Regulation and Development) Act, 2016 — MoHUA](https://mohua.gov.in/) |
| Real estate | property-investment-math | [Introduction to Corporate Finance (Wharton, Coursera) — time value of money](https://www.coursera.org/learn/wharton-finance); [Khan Academy Housing (renting vs buying, mortgages)](https://www.khanacademy.org/economics-finance-domain/core-finance/housing); [RBI Financial Education](https://www.rbi.org.in/FinancialEducation/) |
| Real estate | real-estate-marketing | [HubSpot Academy Inbound Marketing (free)](https://academy.hubspot.com/); [Google Skillshop (Search and Business Profile)](https://skillshop.withgoogle.com/); [RERA Andhra Pradesh (advertising rules and registration)](https://rera.ap.gov.in/) |
| Technology | cloud-devops-basics | [The Missing Semester of Your CS Education (MIT)](https://missing.csail.mit.edu/); [AWS Cloud Practitioner Essentials (AWS Skill Builder)](https://skillbuilder.aws/); [Microsoft Learn: Azure Fundamentals (AZ-900) path](https://learn.microsoft.com/training/); [Google Cloud Skills Boost](https://www.cloudskillsboost.google/) |
| Technology | coding-interview-prep | [MIT 6.006 Introduction to Algorithms (MIT OpenCourseWare)](https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/); [Tech Interview Handbook](https://www.techinterviewhandbook.org/); [NPTEL Programming, Data Structures and Algorithms](https://nptel.ac.in/); [CS50x (Harvard)](https://cs50.harvard.edu/x/) |
| Technology | cybersecurity-basics | [Google Cybersecurity Professional Certificate (Coursera)](https://www.coursera.org/professional-certificates/google-cybersecurity); [Cisco Networking Academy: Introduction to Cybersecurity](https://www.netacad.com/); [CISA Secure Our World](https://www.cisa.gov/secure-our-world); [CERT-In advisories (India)](https://www.cert-in.org.in/) |
| Technology | data-analysis | [Google Data Analytics Professional Certificate (Coursera)](https://www.coursera.org/professional-certificates/google-data-analytics); [Kaggle Learn: Pandas, Data Cleaning, Data Visualization](https://www.kaggle.com/learn); [Khan Academy Statistics and Probability](https://www.khanacademy.org/math/statistics-probability) |
| Technology | machine-learning-basics | [Machine Learning Specialization (Andrew Ng, DeepLearning.AI / Stanford, Coursera)](https://www.coursera.org/specializations/machine-learning-introduction); [Google Machine Learning Crash Course](https://developers.google.com/machine-learning/crash-course); [Practical Deep Learning for Coders (fast.ai)](https://course.fast.ai/); [Elements of AI (University of Helsinki)](https://www.elementsofai.com/) |
| Technology | python-programming | [CS50's Introduction to Programming with Python (Harvard)](https://cs50.harvard.edu/python/); [Python for Everybody (University of Michigan, Dr. Chuck)](https://www.py4e.com/); [Google's Python Class](https://developers.google.com/edu/python); [The official Python Tutorial](https://docs.python.org/3/tutorial/) |
| Technology | sql-databases | [Stanford Databases: Relational Databases and SQL (Stanford Online)](https://online.stanford.edu/); [Khan Academy Intro to SQL](https://www.khanacademy.org/computing/computer-programming/sql); [SQLBolt interactive lessons](https://sqlbolt.com/); [PostgreSQL Tutorial (official docs)](https://www.postgresql.org/docs/current/tutorial.html) |
| Technology | web-development | [MDN Learn Web Development (Mozilla)](https://developer.mozilla.org/en-US/docs/Learn_web_development); [freeCodeCamp Responsive Web Design and JavaScript certifications](https://www.freecodecamp.org/learn); [The Odin Project Foundations](https://www.theodinproject.com/); [web.dev Learn (Google)](https://web.dev/learn) |

### Developers (42)

| Skill | What it's for | From |
|---|---|---|
| adversarial-ux-test | Roleplay a hostile user to find and triage UX pain points. | [hermes](https://github.com/NousResearch/hermes-agent/tree/c314285f077e/optional-skills/dogfood/adversarial-ux-test) |
| api-and-interface-design | Guides stable API and interface design. Use when designing APIs, module boundaries, or any public interface. | [addyosmani](https://github.com/addyosmani/agent-skills/tree/301b02b12bff/skills/api-and-interface-design) |
| ci-cd-and-automation | Automates CI/CD pipeline setup. Use when setting up or modifying build and deployment pipelines. | [addyosmani](https://github.com/addyosmani/agent-skills/tree/301b02b12bff/skills/ci-cd-and-automation) |
| cloud-devops-basics | Run software reliably — the command line, git, servers, cloud basics (AWS/Azure/Google Cloud), Docker, deployments, monitoring and costs. | echo-courses |
| code-review-and-quality | Conducts multi-axis code review. Use before merging any change. Use when reviewing code written by yourself, another agent, or a human. | [addyosmani](https://github.com/addyosmani/agent-skills/tree/301b02b12bff/skills/code-review-and-quality) |
| code-simplification | Simplifies code for clarity. Use when refactoring code for clarity without changing behavior. | [addyosmani](https://github.com/addyosmani/agent-skills/tree/301b02b12bff/skills/code-simplification) |
| code-wiki | Generate wiki docs + Mermaid diagrams for any codebase. | [hermes](https://github.com/NousResearch/hermes-agent/tree/c314285f077e/optional-skills/software-development/code-wiki) |
| coding-interview-prep | Prepare for software engineering interviews — data structures and algorithms, problem-solving method, Big-O, system design basics and… | echo-courses |
| context-engineering | Optimizes agent context setup. Use when starting a new session, when agent output quality degrades, when switching between tasks, or when… | [addyosmani](https://github.com/addyosmani/agent-skills/tree/301b02b12bff/skills/context-engineering) |
| cybersecurity-basics | Protect a person, family or small business from hacking and fraud — passwords, two-factor, updates, backups, phishing, Wi-Fi, phones, and… | echo-courses |
| data-analysis | Turn raw data (CSV, Excel, exports) into answers — cleaning, summarising, charts and honest conclusions, in Excel, Google Sheets or Python… | echo-courses |
| debugging-and-error-recovery | Guides systematic root-cause debugging. Use when tests fail, builds break, something that worked yesterday broke, behavior doesn't match… | [addyosmani](https://github.com/addyosmani/agent-skills/tree/301b02b12bff/skills/debugging-and-error-recovery) |
| deprecation-and-migration | Manages deprecation and migration. Use when removing old systems, APIs, or features. | [addyosmani](https://github.com/addyosmani/agent-skills/tree/301b02b12bff/skills/deprecation-and-migration) |
| docker-management | Manage Docker containers, images, volumes, and Compose. | [hermes](https://github.com/NousResearch/hermes-agent/tree/c314285f077e/optional-skills/devops/docker-management) |
| documentation-and-adrs | Records decisions and documentation. Use when you need to document an architecture decision (ADR) or the reasoning behind a design choice,… | [addyosmani](https://github.com/addyosmani/agent-skills/tree/301b02b12bff/skills/documentation-and-adrs) |
| dogfood | Exploratory QA of web apps: find bugs, evidence, reports. | [hermes](https://github.com/NousResearch/hermes-agent/tree/c314285f077e/skills/software-development/dogfood) |
| doubt-driven-development | Subjects every non-trivial decision to a fresh-context adversarial review before it stands. | [addyosmani](https://github.com/addyosmani/agent-skills/tree/301b02b12bff/skills/doubt-driven-development) |
| finishing-a-development-branch | Use when implementation is complete, all tests pass, and you need to decide how to integrate the work. | [superpowers](https://github.com/obra/superpowers/tree/2ce8aa15d05b/skills/finishing-a-development-branch) |
| frontend-design | Guidance for distinctive, intentional visual design when building new UI or reshaping an existing one. | [anthropic](https://github.com/anthropics/skills/tree/ca45fc496a34/skills/frontend-design) |
| frontend-ui-engineering | Builds production-quality, accessible, responsive user-facing UIs. Use when building or modifying interfaces and pages, creating… | [addyosmani](https://github.com/addyosmani/agent-skills/tree/301b02b12bff/skills/frontend-ui-engineering) |
| git-workflow-and-versioning | Structures git workflow practices. Use when making any code change. Use when committing, branching, resolving conflicts, splitting… | [addyosmani](https://github.com/addyosmani/agent-skills/tree/301b02b12bff/skills/git-workflow-and-versioning) |
| grill-me | Adversarial plan interview before implementation. | [hermes](https://github.com/NousResearch/hermes-agent/tree/c314285f077e/optional-skills/software-development/grill-me) |
| incremental-implementation | Delivers changes incrementally in thin, verifiable slices. Use when implementing any feature or change that touches more than one file, or… | [addyosmani](https://github.com/addyosmani/agent-skills/tree/301b02b12bff/skills/incremental-implementation) |
| machine-learning-basics | Understand and apply machine learning and AI — when ML fits, framing a problem, splitting data, choosing a simple model, measuring it… | echo-courses |
| node-inspect-debugger | Debug Node.js via --inspect + Chrome DevTools Protocol CLI. | [hermes](https://github.com/NousResearch/hermes-agent/tree/c314285f077e/optional-skills/software-development/node-inspect-debugger) |
| observability-and-instrumentation | Instruments code so production behavior is visible and diagnosable. Use when adding logging, metrics, tracing, or alerting. | [addyosmani](https://github.com/addyosmani/agent-skills/tree/301b02b12bff/skills/observability-and-instrumentation) |
| performance-optimization | Optimizes application performance across frontend, backend, queries, and databases. | [addyosmani](https://github.com/addyosmani/agent-skills/tree/301b02b12bff/skills/performance-optimization) |
| planning-and-task-breakdown | Breaks work into ordered tasks. Use when you have a spec or clear requirements and need to break work into implementable tasks. | [addyosmani](https://github.com/addyosmani/agent-skills/tree/301b02b12bff/skills/planning-and-task-breakdown) |
| python-programming | Learn, write, read and fix Python code — from first steps to clean, tested scripts. | echo-courses |
| receiving-code-review | Use when receiving code review feedback, before implementing suggestions, especially if feedback seems unclear or technically questionable… | [superpowers](https://github.com/obra/superpowers/tree/2ce8aa15d05b/skills/receiving-code-review) |
| rest-graphql-debug | Debug REST/GraphQL APIs: status codes, auth, schemas, repro. | [hermes](https://github.com/NousResearch/hermes-agent/tree/c314285f077e/optional-skills/software-development/rest-graphql-debug) |
| security-and-hardening | Hardens code against vulnerabilities. Use when auditing an input handler for vulnerabilities, when handling user input, authentication,… | [addyosmani](https://github.com/addyosmani/agent-skills/tree/301b02b12bff/skills/security-and-hardening) |
| shipping-and-launch | Prepares production launches. Use when preparing to deploy to production, or when asking what needs to be in place before shipping. | [addyosmani](https://github.com/addyosmani/agent-skills/tree/301b02b12bff/skills/shipping-and-launch) |
| sketch | Throwaway HTML mockups: 2-3 design variants to compare. | [hermes](https://github.com/NousResearch/hermes-agent/tree/c314285f077e/optional-skills/creative/sketch) |
| spec-driven-development | Creates specs before coding. Use when starting a new project, feature, or significant change and no specification exists yet. | [addyosmani](https://github.com/addyosmani/agent-skills/tree/301b02b12bff/skills/spec-driven-development) |
| spike | Throwaway experiments to validate an idea before build. | [hermes](https://github.com/NousResearch/hermes-agent/tree/c314285f077e/skills/software-development/spike) |
| sql-databases | Design databases and write SQL queries — SELECT, filtering, joins, grouping, indexes and safe changes. | echo-courses |
| test-driven-development | Drives development with tests using the red-green-refactor loop. Use when implementing any logic, fixing any bug, or changing any behavior. | [addyosmani](https://github.com/addyosmani/agent-skills/tree/301b02b12bff/skills/test-driven-development) |
| using-git-worktrees | Use when starting feature work that needs isolation from current workspace or before executing implementation plans - ensures an isolated… | [superpowers](https://github.com/obra/superpowers/tree/2ce8aa15d05b/skills/using-git-worktrees) |
| verification-before-completion | Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - requires running verification commands and… | [superpowers](https://github.com/obra/superpowers/tree/2ce8aa15d05b/skills/verification-before-completion) |
| web-development | Build websites and web apps with HTML, CSS and JavaScript — layout, responsive design, forms, accessibility, fetching data, and getting a… | echo-courses |
| writing-plans | Use when you have a spec or requirements for a multi-step task, before touching code. | [superpowers](https://github.com/obra/superpowers/tree/2ce8aa15d05b/skills/writing-plans) |

### Work and business (17)

| Skill | What it's for | From |
|---|---|---|
| bookkeeping-gst | Keep a small business's books in India — recording income and expenses, invoices, cash vs bank, profit and loss, GST basics (registration,… | echo-courses |
| business-writing | Write clear professional emails, letters, proposals, reports and messages — structure, tone, brevity and plain language. | echo-courses |
| customer-service | Serve customers so they come back — fast replies, handling complaints and angry customers, refunds, reviews, and simple service processes. | echo-courses |
| digital-marketing | Market a business or website online — positioning, Google Business Profile, SEO, social media, WhatsApp, ads with small budgets, and… | echo-courses |
| excel-spreadsheets | Get things done in Excel or Google Sheets — formulas, XLOOKUP, SUMIFS, pivot tables, charts, cleaning data, budgets and trackers. | echo-courses |
| interview-prep | Prepare for job interviews — researching the company, common questions, STAR stories, technical rounds, HR and salary questions, online… | echo-courses |
| negotiation | Negotiate well and fairly — salary, price, rent, property deals, vendor contracts — with preparation, anchoring, BATNA, trading concessions… | echo-courses |
| presentations | Plan and design slide decks that persuade — story structure, one idea per slide, visuals, charts and delivery, in PowerPoint, Google Slides… | echo-courses |
| project-management | Run a project from idea to done — goals, scope, task breakdown, timeline, budget, risks, team updates, Agile/Kanban, and closing. | echo-courses |
| property-buying-due-diligence | Check a flat, house or plot before buying in India (with Andhra Pradesh / Amaravati specifics) — title, encumbrance certificate, land… | echo-courses |
| property-investment-math | Work out whether a property is a good investment — total cost, home-loan EMI, rental yield, cash flow, appreciation, buy vs rent, and… | echo-courses |
| public-speaking | Speak confidently in front of people — planning a talk, opening and closing, voice and body language, nerves, Q&A, toasts and short… | echo-courses |
| real-estate-marketing | Market properties and a real-estate business — listings that sell, photos, pricing, portals, the website, WhatsApp follow-up, site visits… | echo-courses |
| resume-and-job-search | Find a job — resume/CV that passes screening, LinkedIn profile, where to look, applications, referrals, cover messages, and tracking. | echo-courses |
| sales-basics | Sell honestly and effectively — finding leads, first contact, discovery questions, presenting value, handling objections, closing and… | echo-courses |
| small-business-india | Start and run a small business in India — idea validation, business model, registration (Udyam, GST, shop licence), pricing, cash flow,… | echo-courses |
| word-documents | Make clean, professional documents in Word or Google Docs — styles, headings, tables of contents, page numbers, letters, reports, mail… | echo-courses |

### Everyday life (incl. older people) (40)

| Skill | What it's for | From |
|---|---|---|
| better-sleep | Sleep better — sleep hygiene, a wind-down routine, fixing insomnia habits, shift work, naps, and when snoring or tiredness needs a doctor. | echo-courses |
| competitor-news-monitor | Watch named companies for material news; cited digests. | [hermes](https://github.com/NousResearch/hermes-agent/tree/c314285f077e/skills/research/competitor-news-monitor) |
| consumer-complaints-india | Get a consumer problem fixed in India — defective products, bad service, refunds denied, e-commerce, banks, telecom, real estate — from a… | echo-courses |
| contract-and-proposal-writer | Use when drafting a freelance contract, proposal, SOW, NDA or MSA for US, EU, UK or DACH jurisdictions. | [rezvani](https://github.com/alirezarezvani/claude-skills/tree/7f92edacf851/business-growth/skills/contract-and-proposal-writer) |
| cooking-basics | Cook everyday Indian and simple meals with confidence — kitchen basics, techniques (tadka, pressure cooking, sautéing), measuring, fixing… | echo-courses |
| creative-ideation | Generate ideas via named methods from creative practice. | [hermes](https://github.com/NousResearch/hermes-agent/tree/c314285f077e/optional-skills/creative/creative-ideation) |
| decision-questionnaire | Turn an unanswerable decision into a questionnaire doc. | [hermes](https://github.com/NousResearch/hermes-agent/tree/c314285f077e/optional-skills/productivity/decision-questionnaire) |
| discernment-nudge | After you give a substantive answer or draft that the user may act on — advice or recommendations, drafted artifacts such as goals, plans,… | [anthropic](https://github.com/anthropics/skills/tree/ca45fc496a34/skills/discernment-nudge) |
| doctor-visit-prep | Prepare for a doctor or hospital visit — a one-page summary of symptoms, medicines and questions, and what to carry. | echo |
| english-fluency | Improve spoken and written English — grammar that matters, common Indian-English mistakes, vocabulary, pronunciation, speaking practice,… | echo-courses |
| explain-tech-simply | Explain a phone, computer or internet thing to someone new to technology, or walk them through a task step by step. | echo |
| first-aid | Give first aid until help arrives — emergencies (not breathing, choking, heart attack, stroke, bleeding, burns, fractures, fainting,… | echo-courses |
| fitness-beginners | Start exercising safely at any age — walking to running, home strength workouts without equipment, flexibility, staying consistent, and… | echo-courses |
| graphic-design-basics | Design posters, social posts, flyers, logos, brochures and banners that look professional — hierarchy, alignment, contrast, colour, fonts,… | echo-courses |
| help-kids-homework | Help children learn and do homework without doing it for them — maths, reading, science, projects, building study habits and screen-time… | echo-courses |
| humanizer | Humanize text: strip AI-isms and add real voice. | [hermes](https://github.com/NousResearch/hermes-agent/tree/c314285f077e/skills/creative/humanizer) |
| income-tax-india | Understand and file income tax in India — new vs old regime, slabs, standard deduction, rebate, deductions, Form 16, AIS/26AS, which ITR… | echo-courses |
| insurance-basics | Choose and use insurance in India — term life, health (family floater, super top-up), motor, home, and how to read a policy and make a… | echo-courses |
| internal-comms | A set of resources to help me write all kinds of internal communications, using the formats that my company likes to use. | [anthropic](https://github.com/anthropics/skills/tree/ca45fc496a34/skills/internal-comms) |
| interview-me | Extracts what the user actually wants instead of what they think they should want. | [addyosmani](https://github.com/addyosmani/agent-skills/tree/301b02b12bff/skills/interview-me) |
| investing-basics-india | Understand investing in India — risk and return, FDs, PPF, NPS, mutual funds and SIPs, index funds, stocks, gold, asset allocation, taxes… | echo-courses |
| kitchen-garden | Grow vegetables, herbs and plants at home — balcony, terrace or backyard gardens in Indian climates, pots and soil mix, seasons, watering,… | echo-courses |
| medicine-routine | Help organise a daily medicine routine — a clear timetable, reminders, refill dates and a list to show the doctor. | echo |
| nutrition-indian-diet | Eat healthily with everyday Indian food — balanced plates, portions, protein from regular foods, millets and whole grains, less… | echo-courses |
| personal-budgeting | Take control of money at home — a simple monthly budget, tracking spending, cutting costs without misery, emergency fund, paying off debt,… | echo-courses |
| phone-photography | Take great photos with a phone — light, composition, focus and exposure, portraits, food and product photos, property interiors, night… | echo-courses |
| read-a-bill-or-letter | Explain an official letter, bill, bank statement, notice or form in plain words — what it is, how much, by when, and what to do. | echo |
| renting-a-home | Rent or let out a home in India — searching, visits, the rent agreement (11-month vs registered lease), deposit, police verification,… | echo-courses |
| rti-application | Use the Right to Information Act to get information from government offices in India — writing the RTI, fees, online filing, timelines,… | echo-courses |
| safe-online-payments | Guide safe UPI, card and net-banking payments and what to do if money went to the wrong place. | echo |
| scam-check | Decide whether a message, call, link or request for money is a scam. Use when someone asks "is this a scam", "is this real", "someone… | echo |
| simple-english | Rewrite text to ASD-STE100 Simplified Technical English. | [hermes](https://github.com/NousResearch/hermes-agent/tree/c314285f077e/optional-skills/creative/simple-english) |
| small-farm-basics | Help small farmers in India plan and run a farm — soil testing, crop choice by season, seeds, water and drip irrigation, integrated pest… | echo-courses |
| social-media-content-calendar | Plan multi-platform social campaigns: briefs to posting. | [hermes](https://github.com/NousResearch/hermes-agent/tree/c314285f077e/optional-skills/creative/social-media-content-calendar) |
| songwriting-and-ai-music | Songwriting craft and Suno AI music prompts. | [hermes](https://github.com/NousResearch/hermes-agent/tree/c314285f077e/skills/creative/songwriting-and-ai-music) |
| stress-and-wellbeing | Support mental wellbeing — handling stress and worry, low mood, burnout, grounding and breathing exercises, building good habits,… | echo-courses |
| study-and-exam-prep | Study effectively and prepare for exams (school, college, competitive exams like UPSC, JEE, NEET, banking, government jobs) — study plans,… | echo-courses |
| tutor-mode | Teach any topic the way good teachers do — find the learner's level, explain in small steps with examples, check understanding with… | echo-courses |
| video-call-family | Help someone make or join a video call with family or friends (WhatsApp, Google Meet, Zoom, Teams), and fix the usual problems (no sound,… | echo |
| video-editing | Make and edit videos — planning a short video, shooting on a phone, editing (cuts, B-roll, music, text, captions), formats for… | echo-courses |

### Least effort (11)

| Skill | What it's for | From |
|---|---|---|
| chores-autopilot | Turn a messy pile of chores and errands into a short, ordered plan with the least effort, and set it running with Echo (tasks, reminders,… | echo |
| decide-for-me | Make a small everyday decision for the user quickly instead of listing options — what to watch, eat, wear, buy between two items, which… | echo |
| document-to-action-items | Extract cited obligations, deadlines, tasks from documents. | [hermes](https://github.com/NousResearch/hermes-agent/tree/c314285f077e/skills/productivity/document-to-action-items) |
| email-inbox-triage | Triage an inbox: prioritize threads, draft replies safely. | [hermes](https://github.com/NousResearch/hermes-agent/tree/c314285f077e/skills/email/email-inbox-triage) |
| lazy-meal-plan | Plan a week of easy meals with the least effort, from what's already at home, and make one shopping list. | echo |
| meeting-action-items | Turn meeting notes into cited decisions, owners, tickets. | [hermes](https://github.com/NousResearch/hermes-agent/tree/c314285f077e/skills/productivity/meeting-action-items) |
| one-three-one-rule | 1-3-1 decision briefs: problem, three options, one pick. | [hermes](https://github.com/NousResearch/hermes-agent/tree/c314285f077e/optional-skills/communication/one-three-one-rule) |
| product-price-monitor | Watch product, flight, or listing prices; alert on target. | [hermes](https://github.com/NousResearch/hermes-agent/tree/c314285f077e/skills/productivity/product-price-monitor) |
| quick-reply | Write short replies to messages and emails for the user with minimum effort — yes/no/later answers, polite refusals, thank-yous,… | echo |
| quick-trip-plan | Plan a simple trip with little effort — a day-by-day outline, a rough budget, what to book first and a packing list. | echo |
| weekly-review-planning | Weekly reset: commitments, stalled work, next-week plan. | [hermes](https://github.com/NousResearch/hermes-agent/tree/c314285f077e/skills/productivity/weekly-review-planning) |
