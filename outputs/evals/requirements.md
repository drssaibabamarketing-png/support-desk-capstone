# Eval 10: Assignment requirements (weekly loop, response loop, connection, compliance, interface)

Result: **21/21 checks pass**

| Check | Result | Detail |
|---|---|---|
| A. at most 5 clusters; exactly the top 3 are used in the pulse | PASS | 5 clusters, top ['App performance & bugs', 'Mutual funds & SIP', 'Ease of use & positive experience'] |
| A. every theme carries review ids and a stated date window | PASS |  |
| A. the window is a stated 7-day range | PASS | 2026-08-22 to 2026-08-29 |
| A. pulse has supporting quotes with review ids and exactly 3 action ideas | PASS | 3 quotes |
| A. pulse is 250 words or fewer | PASS | 198 |
| A. fee explainer has 6 bullets or fewer, exactly two official source links and a last-checked date | PASS | 6 bullets |
| A. the explainer's last-checked date is the OLDEST of its two sources' recorded dates (conservative) | PASS | 26 Nov 2026 |
| A. the doc append and the email draft are two separate pending actions with separate gates | PASS |  |
| B. every reply is 3 sentences or fewer | PASS |  |
| B. every factual sentence carries exactly one citation | PASS | [] |
| B. out-of-corpus questions get an explicit not-covered reply naming what was searched | PASS | 7 questions |
| B. the three agents run in parallel on three threads (their execution windows overlap; 0.6 s of work finishes in far less) | PASS | wall 0.27s for 3 x 0.2s agents; threads 3 |
| C. a question asked 5+ times in the window appears in the weekly pulse as a support-desk signal | PASS | ['Groww brokerage and charges', 'HDFC scheme exit load'] |
| C. after approval, the fee explainer is the canonical answer and the response loop reuses it (and says so) | PASS | 1 |
| D. no reply to any queued question contains advice language or a return/performance figure | PASS | [] |
| D. no write happened before approval (only the one approved weekly action wrote) | PASS |  |
| E. queue, weekly pulse, sources, approvals, canonical explainers, overview, evals and login pages all load | PASS | {'/queue': 200, '/weekly': 200, '/sources': 200, '/approvals': 200, '/canonical': 200, '/': 200, '/evals': 200, '/login': 200} |
| E. the queue page has the voice controls (mic, language, confirmation, consent) | PASS |  |
| E. an anonymous visitor cannot open the live queue, tickets, weekly actions, approvals, sources or written files (redirected to login or the demo) | PASS | {'/': 302, '/queue': 302, '/ticket/5d306fb7': 302, '/weekly': 302, '/approvals': 302, '/canonical': 302, '/sources': 302, '/saved': 302} |
| E. the public demo loads and shows sample data only (no live ticket id, audit content or approval/submit control) | PASS |  |
| E. without a reviewer session, submitting, approving, the preview API and the weekly API are refused and change nothing | PASS | [302, 302, 302, 403] |
